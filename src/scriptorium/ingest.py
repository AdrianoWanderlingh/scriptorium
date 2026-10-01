"""Turn heterogeneous files (txt, md, pdf, html, docx, csv, xlsx, epub, ...) into
plain markdown plus metadata. PDFs keep page offsets so citations can point to pages."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

FILENAME_META = re.compile(r"^(?P<author>.+?)\s+-\s+(?P<title>.+?)(?:\s+\((?P<year>\d{3,4})\))?$")


@dataclass
class Document:
    doc_id: str
    title: str
    author: str
    year: str
    source_path: str
    fmt: str
    text: str
    sha: str
    page_offsets: list[tuple[int, int]] = field(default_factory=list)  # (char_offset, page_no)
    meta: dict = field(default_factory=dict)

    def page_at(self, offset: int) -> int | None:
        page = None
        for start, number in self.page_offsets:
            if start > offset:
                break
            page = number
        return page


def slugify(value: str, max_len: int = 48) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:max_len].rstrip("-") or "doc"


def file_sha(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _sidecar(path: Path) -> Path | None:
    for candidate in (path.with_suffix(path.suffix + ".meta.json"), path.with_suffix(".meta.json")):
        if candidate.exists():
            return candidate
    return None


def _sidecar_meta(path: Path) -> dict:
    sidecar = _sidecar(path)
    return json.loads(sidecar.read_text()) if sidecar else {}


def source_sha(path: Path) -> str:
    """Fingerprint of a source: its bytes plus its metadata sidecar, so editing metadata re-indexes."""
    sidecar = _sidecar(path)
    if not sidecar:
        return file_sha(path)
    return hashlib.sha1((file_sha(path) + file_sha(sidecar)).encode()).hexdigest()[:16]


def _filename_meta(path: Path) -> dict:
    match = FILENAME_META.match(path.stem)
    if not match:
        return {"title": path.stem.replace("_", " ")}
    return {k: v for k, v in match.groupdict().items() if v}


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _pdf(path: Path) -> tuple[str, list[tuple[int, int]], dict]:
    if os.environ.get("SCRIPTORIUM_PDF_ENGINE") == "docling":
        from docling.document_converter import DocumentConverter

        result = DocumentConverter().convert(str(path))
        return result.document.export_to_markdown(), [], {}

    import pymupdf
    import pymupdf4llm

    with pymupdf.open(path) as pdf:
        info = {k: v for k, v in (pdf.metadata or {}).items() if v and k in ("title", "author")}
    pages = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False)
    parts, offsets, cursor = [], [], 0
    for page in pages:
        text = page["text"].strip()
        offsets.append((cursor, page["metadata"].get("page_number", page["metadata"].get("page", len(offsets) + 1))))
        parts.append(text)
        cursor += len(text) + 2
    text = "\n\n".join(parts)
    if len(text.strip()) < 20 * max(1, len(pages)):
        info["warning"] = "little extractable text: probably a scan, run `ocrmypdf -l ita+eng in.pdf out.pdf` first"
    return text, offsets, info


def _csv(path: Path) -> str:
    """One paragraph per row, 'column: value' pairs: retrievable record by record."""
    text = _read_text(path)
    dialect = csv.Sniffer().sniff(text[:4096]) if text.strip() else csv.excel
    rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
    lines = [f"# {path.stem}", ""]
    for i, row in enumerate(rows, 1):
        pairs = "; ".join(f"{k}: {v}" for k, v in row.items() if k and v not in (None, ""))
        lines.append(f"Record {i} — {pairs}")
        lines.append("")
    return "\n".join(lines)


def _via_libreoffice(path: Path) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(f"{path.suffix} needs LibreOffice (soffice) to convert; install it or save as .docx")
    out = Path(tempfile.mkdtemp())
    subprocess.run(
        [soffice, "--headless", "--convert-to", "docx", "--outdir", str(out), str(path)],
        check=True,
        capture_output=True,
    )
    return next(out.glob("*.docx"))


def _markitdown(path: Path) -> str:
    from markitdown import MarkItDown

    return MarkItDown(enable_plugins=False).convert(str(path)).text_content


def load(path: Path) -> Document:
    path = path.resolve()
    ext = path.suffix.lower()
    offsets: list[tuple[int, int]] = []
    extra: dict = {}
    if ext in (".txt", ".md", ".markdown"):
        text = _read_text(path)
    elif ext == ".pdf":
        text, offsets, extra = _pdf(path)
    elif ext == ".csv":
        text = _csv(path)
    elif ext in (".doc", ".rtf", ".odt"):
        text = _markitdown(_via_libreoffice(path))
    else:
        text = _markitdown(path)

    meta = {**extra, **_filename_meta(path), **_sidecar_meta(path)}
    title = meta.pop("title", path.stem)
    author = meta.pop("author", "")
    year = str(meta.pop("year", ""))
    doc_id = meta.pop("doc_id", None) or slugify(f"{author.split()[-1] if author else ''} {title}")
    return Document(
        doc_id=doc_id,
        title=title,
        author=author,
        year=year,
        source_path=str(path),
        fmt=ext.lstrip("."),
        text=text,
        sha=source_sha(path),
        page_offsets=offsets,
        meta=meta,
    )
