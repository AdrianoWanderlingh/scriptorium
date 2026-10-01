"""scriptorium — command line for private book knowledge bases."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from . import render
from .library import Library

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)
state: dict = {"library": os.environ.get("SCRIPTORIUM_LIBRARY")}


def lib() -> Library:
    name = state["library"] or (Library.list_all() or [None])[0]
    if not name:
        raise typer.BadParameter("no library: create one with `scriptorium new NAME`")
    return Library(name)


def emit(data, text: str, as_json: bool) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2) if as_json else text)


def _version(value: bool) -> None:
    if value:
        from . import __version__

        typer.echo(f"scriptorium {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    library: str | None = typer.Option(None, "--library", "-l", help="Library name (or $SCRIPTORIUM_LIBRARY)"),
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show version"),
):
    if library:
        state["library"] = library


@app.command()
def new(
    name: str,
    description: str = "",
    topic: str = "",
    language: str = typer.Option("English", help="Stemming language for keyword search (English, Italian, ...)"),
):
    """Create a library."""
    lib_ = Library.create(name, description=description, topic=topic, fts_language=language)
    typer.echo(f"Created {lib_.root}")


@app.command("list")
def list_():
    """List libraries."""
    for name in Library.list_all():
        lib_ = Library(name)
        typer.echo(f"{name}: {len(lib_.docs)} documents — {lib_.config.description}")


@app.command()
def add(
    paths: list[Path],
    build_after: bool = typer.Option(True, "--build/--no-build"),
    move: bool = typer.Option(False, help="Move instead of copy"),
):
    """Add files or folders (txt, md, pdf, html, docx, pptx, xlsx, csv, epub, json...) to the library."""
    lib_ = lib()
    added = lib_.add(paths, move=move)
    typer.echo(f"Added {len(added)} files to {lib_.sources}")
    if build_after:
        lib_.build(log=typer.echo)
        _refresh_skill(lib_.name)


@app.command()
def build(force: bool = typer.Option(False, help="Re-embed everything")):
    """(Re)index new or changed sources; incremental by default."""
    lib_ = lib()
    lib_.build(force=force, log=typer.echo)
    _refresh_skill(lib_.name)


def _refresh_skill(name: str) -> None:
    from .skill import refresh

    refresh(name)


@app.command()
def remap():
    """Recompute map and entity graph from the existing index (no re-embedding)."""
    lib().remap(log=typer.echo)


@app.command()
def overview(as_json: bool = typer.Option(False, "--json")):
    """Compact map of the library."""
    o = lib().overview()
    emit(o, render.overview(o), as_json)


@app.command()
def search(
    query: str,
    k: int = typer.Option(8, "-k"),
    author: str | None = None,
    doc: str | None = None,
    kind: str | None = None,
    per_doc: int | None = None,
    full: bool = False,
    also: list[str] = typer.Option([], "--also", "-a", help="Extra phrasing / translation (repeatable)"),
    no_rerank: bool = False,
    as_json: bool = typer.Option(False, "--json"),
):
    """Hybrid search (semantic + keywords + rerank); returns snippets with citable ids."""
    hits = lib().search(query, k=k, author=author, doc=doc, kind=kind, per_doc=per_doc, rerank=not no_rerank, also=also)
    emit(hits, render.hits(hits, full=full), as_json)


@app.command()
def read(id: str, before: int = 0, after: int = 0, as_json: bool = typer.Option(False, "--json")):
    """Read passage(s) by id."""
    r = lib().read(id, before=before, after=after)
    emit(r, render.passages(r), as_json)


@app.command()
def outline(doc: str, depth: int | None = None, as_json: bool = typer.Option(False, "--json")):
    """Sections of a document with keywords and gist."""
    o = lib().outline(doc, depth=depth)
    emit(o, render.outline(o), as_json)


@app.command()
def section(doc: str, idx: int, max_chars: int = 12000):
    """Read a whole section."""
    r = lib().read_section(doc, idx, max_chars=max_chars)
    typer.echo(f"Source: {r['cite']}\n\n{r['text']}")


@app.command()
def related(entity: str, top: int = 12, as_json: bool = typer.Option(False, "--json")):
    """Entities co-occurring with ENTITY, with evidence passage ids."""
    r = lib().related(entity, top=top)
    emit(r, render.related(r), as_json)


@app.command()
def style(
    author: str | None = None,
    doc: str | None = None,
    theme: str | None = None,
    examples: int = 3,
    as_json: bool = typer.Option(False, "--json"),
):
    """Style card + exemplar passages for writing in a voice."""
    s = lib().style(author=author, doc=doc, theme=theme, examples=examples)
    emit(s, render.style(s), as_json)


@app.command()
def note(
    title: str,
    body: str | None = None,
    body_file: Path | None = None,
    source: list[str] = typer.Option([], "--source", "-s"),
    tag: list[str] = typer.Option([], "--tag"),
):
    """Save a synthesis into the library wiki (it becomes searchable)."""
    text = body_file.read_text() if body_file else (body or typer.get_text_stream("stdin").read())
    r = lib().write_note(title, text, sources=source, tags=tag)
    typer.echo(f"Saved {r['note']} ({r['chunks']} chunks, id {r['id']})")


@app.command()
def graph(
    top: int = typer.Option(150, help="Entities to show"),
    per_doc: int = typer.Option(5, help="Entities guaranteed per document"),
    out: Path | None = typer.Option(None, help="Output HTML (default: libraries/<name>/graph.html)"),
    open_browser: bool = typer.Option(False, "--open", help="Open in the default browser"),
):
    """Interactive HTML graph of documents, key entities and wiki notes (+ graph.json)."""
    from .graph import build_graph, write_html

    lib_ = lib()
    path = write_html(build_graph(lib_, top=top, per_doc=per_doc), out or lib_.root / "graph.html")
    typer.echo(f"Wrote {path} and {path.with_suffix('.json')}")
    if open_browser:
        import webbrowser

        webbrowser.open(path.as_uri())


@app.command("note-delete")
def note_delete(slug: str):
    """Delete a wiki note (file and index entries)."""
    typer.echo("deleted" if lib().delete_note(slug) else "no such note file (index entries removed)")


@app.command()
def skills():
    """Regenerate all `knowledge-base-<name>` skills and symlink them, plus the `scriptorium`
    manager skill, into ~/.cursor/skills and ~/.claude/skills."""
    from .skill import install_all

    for link in install_all():
        typer.echo(f"{link} -> {link.resolve()}")


@app.command()
def serve():
    """Run the MCP server (stdio) exposing all libraries."""
    from .mcp_server import main as run

    if state["library"]:
        os.environ["SCRIPTORIUM_LIBRARY"] = state["library"]
    run()
