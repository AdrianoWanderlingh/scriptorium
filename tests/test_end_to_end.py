"""Full CLI round trip with the real models on a throwaway library (≈30 s on CPU)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CLI = Path(sys.executable).parent / "scriptorium"

ESSAY = """# Note sulla fotografia di paesaggio

## La pianura

Il paesaggio padano è fatto di orizzonti bassi, nebbia e cieli enormi. Fotografare la pianura
significa accettare il vuoto come soggetto principale dell'immagine.

## Il colore

Il colore non è decorazione: è la temperatura emotiva del luogo. Le tinte pastello dei muri di
provincia raccontano il tempo meglio di qualsiasi didascalia.
"""

CATALOG = "photographer,book,year\nLuigi Ghirri,Kodachrome,1978\nGabriele Basilico,Milano ritratti di fabbriche,1981\n"


def run(*args: str, home: Path) -> str:
    env = {**os.environ, "SCRIPTORIUM_HOME": str(home), "PYTHONWARNINGS": "ignore"}
    out = subprocess.run([str(CLI), "-l", "test", *args], env=env, capture_output=True, text=True, check=True)
    return out.stdout


def test_round_trip(tmp_path: Path):
    home = tmp_path / "libs"
    src = tmp_path / "src"
    src.mkdir()
    (src / "Autore Prova - Saggio sul paesaggio (2024).md").write_text(ESSAY)
    (src / "Catalogo fotolibri.csv").write_text(CATALOG)

    run("new", "test", "--description", "test library", "--language", "Italian", home=home)
    built = run("add", str(src), home=home)
    assert "2 files" in built and "'docs': 2" in built

    hits = run("search", "empty flat horizons as the subject of the picture", "-k", "2", home=home)
    assert "prova-saggio-sul-paesaggio#0000" in hits and "vuoto come soggetto" in hits

    hits = run("search", "Basilico fabbriche", "-k", "1", home=home)
    assert "Gabriele Basilico" in hits

    assert "Il colore non è decorazione" in run("read", "prova-saggio-sul-paesaggio#0000", "--after", "1", home=home)
    assert "Saved" in run(
        "note",
        "Sintesi colore",
        "--body",
        "Il colore come temperatura emotiva.",
        "-s",
        "prova-saggio-sul-paesaggio#0001",
        home=home,
    )
    assert "note-sintesi-colore" in run("search", "temperatura emotiva", "--kind", "note", "-k", "1", home=home)
    assert "'changed': 0" in run("build", home=home)
