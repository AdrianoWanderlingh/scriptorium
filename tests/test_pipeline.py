"""Model-free tests of the parts most likely to break on real books: ingestion of mixed
formats, structure recovery, entity extraction and stylometry."""

from __future__ import annotations

from pathlib import Path

import pytest

from scriptorium.ingest import load
from scriptorium.mapper import build_entity_index, chunk_entities, related
from scriptorium.structure import split_sentences, structure
from scriptorium.style import style_card

NOVEL = """[Title header]

VOLUME I

CHAPTER I

Emma Woodhouse, handsome, clever, and rich, with a comfortable home and happy
disposition, seemed to unite some of the best blessings of existence; and had
lived nearly twenty-one years in the world with very little to distress or vex her.

Mr. Knightley, a sensible man about seven or eight-and-thirty, was a very old
and intimate friend of the family. Mr. Knightley walked to Hartfield.

CHAPTER II

Mr. Weston was a native of Highbury. Mr. Knightley and Mr. Weston talked of Hartfield.
"""


def test_txt_structure_and_metadata(tmp_path: Path):
    path = tmp_path / "Jane Austen - Emma (1816).txt"
    path.write_text(NOVEL)
    doc = load(path)
    assert (doc.author, doc.title, doc.year, doc.doc_id) == ("Jane Austen", "Emma", "1816", "austen-emma")
    sections, chunks = structure(doc, chunk_chars=300)
    titles = [s.title for s in sections]
    assert "VOLUME I / CHAPTER I" in titles and "VOLUME I / CHAPTER II" in titles
    first = next(c for c in chunks if c.section == "VOLUME I / CHAPTER I")
    assert "handsome, clever, and rich, with a comfortable home" in first.text  # hard wraps undone
    assert all(len(c.text) <= 420 for c in chunks)


def test_chapter_subtitle_is_merged(tmp_path: Path):
    path = tmp_path / "Herman Melville - Moby Dick (1851).txt"
    path.write_text("CHAPTER 1\n\nLoomings.\n\nCall me Ishmael. Some years ago I went to sea.\n")
    sections, chunks = structure(load(path))
    assert sections[0].title == "CHAPTER 1 — Loomings"
    assert chunks[0].text.startswith("Call me Ishmael")


def test_verse_keeps_line_breaks(tmp_path: Path):
    path = tmp_path / "William Blake - Poems.txt"
    path.write_text(
        "THE TYGER\n\nTyger, tyger, burning bright\nIn the forests of the night,\nWhat immortal hand or eye\n"
    )
    _, chunks = structure(load(path))
    assert "burning bright\nIn the forests" in chunks[0].text


def test_csv_rows_become_records(tmp_path: Path):
    path = tmp_path / "catalogo.csv"
    path.write_text("autore,titolo,anno\nLuigi Ghirri,Kodachrome,1978\nGianni Berengo Gardin,Morire di classe,1969\n")
    doc = load(path)
    assert "Record 1 — autore: Luigi Ghirri; titolo: Kodachrome; anno: 1978" in doc.text


def test_html_and_pdf(tmp_path: Path):
    pymupdf = pytest.importorskip("pymupdf")
    html = tmp_path / "Autore Prova - Libro HTML.html"
    html.write_text("<h1>Libro HTML</h1><h2>Capitolo 1</h2><p>La luce della pianura padana.</p>")
    sections, chunks = structure(load(html))
    assert any("Capitolo 1" in s.title for s in sections)
    assert "pianura padana" in chunks[0].text

    pdf_path = tmp_path / "Autore Prova - Libro PDF.pdf"
    pdf = pymupdf.open()
    for n in range(3):
        pdf.new_page().insert_text((72, 72), f"Pagina numero {n + 1}: fotografia e paesaggio.")
    pdf.save(pdf_path)
    doc = load(pdf_path)
    assert [p for _, p in doc.page_offsets] == [1, 2, 3]
    assert doc.page_at(doc.text.index("Pagina numero 3")) == 3


def test_sentences_respect_abbreviations():
    assert split_sentences("Mr. Knightley came. Mrs. Weston smiled! Then they left.") == [
        "Mr. Knightley came.",
        "Mrs. Weston smiled!",
        "Then they left.",
    ]


def test_entities_and_graph():
    names = {n for n, _ in chunk_entities("Captain Ahab spoke to Starbuck on the Pequod. The whale swam.")}
    assert {"Captain Ahab", "Starbuck", "Pequod"} <= names and "The" not in names
    texts = ["Then Ahab met Starbuck near the Pequod."] * 5 + ["Stubb laughed at Ahab and Flask."] * 4
    assert chunk_entities(texts[0])[0] == ("Ahab", False)
    index = build_entity_index([f"md#{i:04d}" for i in range(len(texts))], texts)
    linked = [r["entity"] for r in related(index, "Ahab")]
    assert linked[0] in {"Starbuck", "Pequod"} and "Flask" in linked
    assert "Stubb" not in index["entities"]  # only ever seen at sentence start: ambiguous


def test_style_card_excludes_names_and_measures_punctuation():
    target = ["Emma felt the affection; Emma felt the attachment; she was agreeable. " * 20]
    background = ["The whale rose from the sea and the ship turned. " * 20]
    card = style_card(target, background, "en")
    assert card["punctuation_per_1000_words"]["semicolon"] > 50
    assert "emma" not in card["distinctive_words"] and "affection" in card["distinctive_words"]
