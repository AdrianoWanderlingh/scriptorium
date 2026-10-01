"""Build the demo corpus from NLTK's Project Gutenberg selection.

Most books are written as .txt; a few are deliberately converted to other formats
(HTML, PDF, DOCX, CSV) so the ingestion pipeline is exercised on mixed inputs."""

from __future__ import annotations

import csv
import html
import re
import sys
from pathlib import Path

import nltk

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus/classici-inglesi")
SKIP = {"bible-kjv.txt"}
AS_HTML = {"carroll-alice.txt"}
AS_PDF = {"chesterton-thursday.txt"}
AS_DOCX = {"austen-persuasion.txt"}

HEADER = re.compile(r"^\[(?P<title>.+?) by (?P<author>.+?)(?: (?P<year>\d{4}))?\]")
CHAPTER = re.compile(r"^(CHAPTER|Chapter|BOOK|Book|VOLUME)\b.*$")


def paragraphs(raw: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]


def to_html(title: str, author: str, raw: str) -> str:
    parts = [f"<html><head><title>{html.escape(title)}</title></head><body>",
             f"<h1>{html.escape(title)}</h1><p><em>{html.escape(author)}</em></p>"]
    for p in paragraphs(raw):
        text = html.escape(re.sub(r"\s+", " ", p))
        parts.append(f"<h2>{text}</h2>" if CHAPTER.match(text) else f"<p>{text}</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def to_pdf(title: str, author: str, raw: str, path: Path) -> None:
    import pymupdf

    story = pymupdf.Story(html=to_html(title, author, raw))
    writer = pymupdf.DocumentWriter(str(path))
    rect, where = pymupdf.paper_rect("a5"), pymupdf.paper_rect("a5") + (36, 36, -36, -36)
    more = True
    while more:
        device = writer.begin_page(rect)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    with pymupdf.open(path) as doc:
        doc.set_metadata({"title": title, "author": author})
        doc.saveIncr()


def to_docx(title: str, author: str, raw: str, path: Path) -> None:
    import docx

    document = docx.Document()
    document.core_properties.title, document.core_properties.author = title, author
    document.add_heading(title, level=0)
    for p in paragraphs(raw):
        text = re.sub(r"\s+", " ", p)
        if CHAPTER.match(text):
            document.add_heading(text, level=1)
        else:
            document.add_paragraph(text)
    document.save(path)


def main() -> None:
    nltk.download("gutenberg", quiet=True)
    from nltk.corpus import gutenberg

    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []
    for fileid in gutenberg.fileids():
        if fileid in SKIP:
            continue
        raw = gutenberg.raw(fileid)
        first, _, body = raw.partition("\n")
        m = HEADER.match(first)
        title, author, year = m["title"].rstrip(", "), m["author"], m["year"] or ""
        author = re.sub(r"\b([A-Z])\.(?=[A-Z])", r"\1. ", author)
        stem = f"{author} - {title}" + (f" ({year})" if year else "")
        stem = stem.replace("/", "-")
        catalog.append({"file": fileid, "title": title, "author": author, "year": year,
                        "words": len(gutenberg.words(fileid))})
        if fileid in AS_HTML:
            (OUT / f"{stem}.html").write_text(to_html(title, author, body))
        elif fileid in AS_PDF:
            to_pdf(title, author, body, OUT / f"{stem}.pdf")
        elif fileid in AS_DOCX:
            to_docx(title, author, body, OUT / f"{stem}.docx")
        else:
            (OUT / f"{stem}.txt").write_text(body)
        print(f"  {fileid:28} -> {stem}")

    with (OUT / "Scriptorium - Catalogo del corpus.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(catalog[0]))
        writer.writeheader()
        writer.writerows(catalog)
    print(f"{len(catalog)} books written to {OUT}")


if __name__ == "__main__":
    main()
