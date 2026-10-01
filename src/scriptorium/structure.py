"""Recover the logical structure of a book (volumes, chapters, acts, cantos, markdown
headings) and cut it into citation-friendly chunks that never cross a section."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from .ingest import Document

ROMAN = r"[IVXLCDM]+"
NUM = rf"(?:{ROMAN}|\d+|[A-Za-z]+)"
LEVEL1 = r"VOLUME|Volume|VOLUMEN|BOOK|Book|LIBRO|Libro|PART|Part|PARTE|Parte|ACT|Act|Actus|ATTO|Atto|TOMO|Tomo"
LEVEL2 = r"CHAPTER|Chapter|CAPITOLO|Capitolo|CAP\.|Cap\.|CANTO|Canto|SCENE|Scene|Scena|Scoena|Scaena|SECTION|Section|SEZIONE|Sezione|STAVE|Stave"
HEADING_RE = re.compile(rf"^\s*(?:(?P<l1>{LEVEL1})|(?P<l2>{LEVEL2}))\b[ .]*{NUM}\b.*$")
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
ROMAN_TITLE_RE = re.compile(rf"^{ROMAN}\.\s+[A-Z][^.!?\"“]{{2,70}}$")
INITIAL_SIGNATURE_RE = re.compile(r"^[A-Z]\.\s")
GUTENBERG_START = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I)
GUTENBERG_END = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG", re.I)
ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|St|Sig|Sr|Jr|Prof|Mt|vol|cap|pag|p|pp|ecc|cfr|ca|n)\.", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?…])[\"'”’»)]*\s+(?=[\"'“‘«(\[]?[A-ZÀ-Ý0-9])")


@dataclass
class Chunk:
    doc_id: str
    chunk_idx: int
    section_idx: int
    section: str
    page: int | None
    char_start: int
    text: str


@dataclass
class Section:
    idx: int
    title: str
    level: int
    chunk_start: int = 0
    chunk_end: int = 0


def split_sentences(text: str) -> list[str]:
    protected = ABBREV.sub(lambda m: m.group(0).replace(".", "\u2024"), text)
    return [s.replace("\u2024", ".").strip() for s in SENT_SPLIT.split(protected) if s.strip()]


def _strip_boilerplate(text: str) -> tuple[str, int]:
    start = 0
    if m := GUTENBERG_START.search(text):
        start = m.end()
    end = m.start() if (m := GUTENBERG_END.search(text, start)) else len(text)
    return text[start:end], start


def _blocks(text: str, base: int):
    """Yield (offset, normalized_block). Hard-wrapped prose is unwrapped, verse keeps its lines."""
    for m in re.finditer(r"(?:[^\n]*\S[^\n]*\n?)+", text):
        raw = m.group(0)
        raw_lines = raw.splitlines(keepends=True)
        if len(raw_lines) > 1 and any(MD_HEADING_RE.match(ln.strip()) for ln in raw_lines):
            # markdown headings glued to the neighbouring paragraph: give each its own block
            groups, pos = [], 0
            for ln in raw_lines:
                if MD_HEADING_RE.match(ln.strip()) or not groups or MD_HEADING_RE.match(groups[-1][1][-1].strip()):
                    groups.append((pos, [ln]))
                else:
                    groups[-1][1].append(ln)
                pos += len(ln)
            for start, group in groups:
                yield from _blocks("".join(group), base + m.start() + start)
            continue
        lines = [ln.rstrip() for ln in raw_lines if ln.strip()]
        if not lines:
            continue
        is_structured = any(ln.lstrip().startswith(("|", "- ", "* ", "#")) for ln in lines)
        is_verse = len(lines) > 1 and statistics.median(len(ln) for ln in lines) < 52
        if is_structured or is_verse:
            block = "\n".join(ln.strip() for ln in lines)
        else:
            block = re.sub(r"\s+", " ", " ".join(lines)).strip()
        yield base + m.start(), block


def _heading(block: str, allow_caps: bool) -> tuple[int, str] | None:
    if "\n" in block or len(block) > 120:
        return None
    if m := MD_HEADING_RE.match(block):
        return len(m.group(1)), m.group(2).strip("*_ ")
    if m := HEADING_RE.match(block):
        return (1 if m.group("l1") else 2), block.strip()
    if ROMAN_TITLE_RE.match(block):
        return 2, block.strip()
    if (allow_caps and 3 < len(block) < 70 and block.isupper() and re.search(r"[A-Z]{3}", block)
            and not INITIAL_SIGNATURE_RE.match(block)):
        return 2, block.strip()
    return None


def _is_chapter_subtitle(block: str, next_block: str | None) -> bool:
    n_words = len(block.split())
    return (next_block is not None and len(block) < 70 and n_words <= 10 and "\n" not in block
            and block[:1].isupper() and not re.search(r"[\"“”'‘]", block[:2])
            and not block.endswith((",", ";", ":")) and (not block.endswith(".") or n_words <= 6))


def structure(doc: Document, chunk_chars: int = 1400) -> tuple[list[Section], list[Chunk]]:
    body, base = _strip_boilerplate(doc.text)
    blocks = list(_blocks(body, base))
    keyword_heads = sum(1 for _, b in blocks if _heading(b, allow_caps=False))
    allow_caps = keyword_heads < 3

    sections: list[Section] = [Section(0, "Front matter", 1)]
    parents: dict[int, str] = {}
    paragraphs: list[tuple[int, int, str]] = []  # (section_idx, offset, text)
    pending_title: Section | None = None
    for i, (offset, block) in enumerate(blocks):
        head = _heading(block, allow_caps)
        if head and head[1].casefold().strip(" .") == doc.title.casefold().strip(" ."):
            continue
        if head:
            level, title = head
            if pending_title is not None and level == 2 and title.isupper() and not HEADING_RE.match(title):
                pending_title.title += f" — {title.title()}"
                pending_title = None
                continue
            parents = {k: v for k, v in parents.items() if k < level}
            full = " / ".join([*parents.values(), title])
            parents[level] = title
            sections.append(Section(len(sections), full, level))
            pending_title = sections[-1] if HEADING_RE.match(title) and len(title) < 25 else None
            continue
        next_block = blocks[i + 1][1] if i + 1 < len(blocks) else None
        if pending_title is not None and _is_chapter_subtitle(block, next_block):
            pending_title.title += f" — {block.rstrip('.')}"
            pending_title = None
            continue
        pending_title = None
        paragraphs.append((sections[-1].idx, offset, block))

    if len(sections) <= 2 and sum(len(p[2]) for p in paragraphs) > 40 * chunk_chars:
        sections, paragraphs = _synthetic_sections(paragraphs, 20 * chunk_chars)

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_start, buf_section = 0, 0

    def flush():
        nonlocal buf
        if buf:
            text = "\n\n".join(buf)
            chunks.append(Chunk(doc.doc_id, len(chunks), buf_section, sections[buf_section].title,
                                doc.page_at(buf_start), buf_start, text))
            buf = []

    for section_idx, offset, text in paragraphs:
        pieces = [text] if len(text) <= chunk_chars * 1.3 else _split_long(text, chunk_chars)
        for piece in pieces:
            if section_idx != buf_section or (buf and sum(map(len, buf)) + len(piece) > chunk_chars):
                flush()
            if not buf:
                buf_start, buf_section = offset, section_idx
            buf.append(piece)
    flush()

    for section in sections:
        idxs = [c.chunk_idx for c in chunks if c.section_idx == section.idx]
        if idxs:
            section.chunk_start, section.chunk_end = idxs[0], idxs[-1]
    sections = [s for s in sections if any(c.section_idx == s.idx for c in chunks)]
    return sections, chunks


def _split_long(text: str, size: int) -> list[str]:
    out, cur = [], ""
    for sent in split_sentences(text) if "\n" not in text else text.split("\n"):
        if cur and len(cur) + len(sent) > size:
            out.append(cur.strip())
            cur = ""
        cur += sent + (" " if "\n" not in text else "\n")
    if cur.strip():
        out.append(cur.strip())
    return out


def _synthetic_sections(paragraphs, span: int):
    sections, out, acc = [Section(0, "Part 1", 1)], [], 0
    for _, offset, text in paragraphs:
        if acc > span:
            sections.append(Section(len(sections), f"Part {len(sections) + 1}", 1))
            acc = 0
        out.append((sections[-1].idx, offset, text))
        acc += len(text)
    return sections, out
