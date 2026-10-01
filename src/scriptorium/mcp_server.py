"""MCP server: exposes every library as a small set of token-efficient tools.

Run with `scriptorium serve` (stdio). Models stay loaded between calls, so after the first
query each search takes about a second on CPU."""

from __future__ import annotations

import os
from functools import lru_cache

from mcp.server.mcpserver import MCPServer

from . import render
from .library import Library

DEFAULT = os.environ.get("SCRIPTORIUM_LIBRARY")

server = MCPServer(
    name="scriptorium",
    instructions=(
        "Private knowledge bases built from digitised books and the user's own writings. "
        "Workflow: overview → outline/search → read the passages you need → cite with [id]. "
        "Answer only from retrieved passages when the user asks about the library; say when it is silent. "
        "For writing in a voice: style(author, theme) then draft, citing ids. "
        "Save durable syntheses with write_note so the library gets smarter over time."
    ),
)


@lru_cache(maxsize=8)
def _lib(name: str | None) -> Library:
    name = name or DEFAULT or (Library.list_all() or [None])[0]
    if not name:
        raise ValueError("no libraries yet: run `scriptorium new NAME` and `scriptorium add NAME files...`")
    return Library(name)


@server.tool()
def list_libraries() -> str:
    """List available knowledge bases with their description."""
    out = []
    for name in Library.list_all():
        lib = Library(name)
        out.append(f"- {name}: {lib.config.description or lib.config.topic} ({len(lib.docs)} documents)")
    return "\n".join(out) or "No libraries."


@server.tool()
def overview(library: str | None = None) -> str:
    """Map of a library: documents with keywords, entities that link documents, wiki notes. Start here."""
    return render.overview(_lib(library).overview())


@server.tool()
def search(
    query: str,
    also: list[str] | None = None,
    library: str | None = None,
    k: int = 8,
    author: str | None = None,
    doc: str | None = None,
    kind: str | None = None,
    per_doc: int | None = None,
    full: bool = False,
) -> str:
    """Hybrid semantic + keyword search with reranking. Returns short snippets with citable ids.
    `also`: 1-3 extra phrasings fused with the query — ALWAYS include a translation into the language of
    the books plus period/technical vocabulary (e.g. query 'matrimonio per denaro', also ['marrying for
    money', 'fortune settlement income']). Filters: author (substring), doc (comma-separated doc ids),
    kind ('book' or 'note'), per_doc (max hits per document; 1-2 to compare works)."""
    return render.hits(
        _lib(library).search(query, k=k, author=author, doc=doc, kind=kind, per_doc=per_doc, also=also), full=full
    )


@server.tool()
def read(id: str, library: str | None = None, before: int = 0, after: int = 0) -> str:
    """Full text of a passage by id (e.g. 'austen-emma#0042'), optionally with neighbouring passages."""
    return render.passages(_lib(library).read(id, before=before, after=after))


@server.tool()
def outline(doc: str, library: str | None = None, depth: int | None = None) -> str:
    """Table of contents of one document with per-section keywords and a one-sentence gist."""
    return render.outline(_lib(library).outline(doc, depth=depth))


@server.tool()
def read_section(doc: str, section: int, library: str | None = None, max_chars: int = 12000) -> str:
    """Whole text of one section (chapter, act, canto...) by its § index from outline()."""
    r = _lib(library).read_section(doc, section, max_chars=max_chars)
    return f"Source: {r['cite']}\n\n{r['text']}"


@server.tool()
def related(entity: str, library: str | None = None, top: int = 12) -> str:
    """Entity graph: which people, places, works... appear together with the given one, with evidence ids."""
    return render.related(_lib(library).related(entity, top=top))


@server.tool()
def style(
    author: str | None = None,
    doc: str | None = None,
    theme: str | None = None,
    library: str | None = None,
    examples: int = 3,
) -> str:
    """Style card for writing in the voice of an author (or of specific doc ids): measured traits,
    distinctive vocabulary and exemplar passages, optionally on a theme."""
    return render.style(_lib(library).style(author=author, doc=doc, theme=theme, examples=examples))


@server.tool()
def write_note(
    title: str, body: str, sources: list[str] | None = None, tags: list[str] | None = None, library: str | None = None
) -> str:
    """Save a synthesis (markdown) into the library wiki; it becomes searchable (kind='note').
    Always pass the passage ids it is based on as sources."""
    r = _lib(library).write_note(title, body, sources=sources, tags=tags)
    return f"Saved {r['note']} (id {r['id']})"


@server.tool()
def read_note(slug: str, library: str | None = None) -> str:
    """Read a wiki note by slug."""
    return _lib(library).read_note(slug)


def main() -> None:
    server.run()
