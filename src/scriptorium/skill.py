"""Generate an Agent Skill (SKILL.md) that turns a library into `knowledge-base-<name>`."""

from __future__ import annotations

import sys
from pathlib import Path

from .library import Library

TEMPLATE = """---
name: knowledge-base-{name}
description: Search, cite and write from the private "{name}" knowledge base — {about}. Use when the user asks about {topic}, wants facts, exact quotes, comparisons or links between works in this collection, or wants text written from these references or in the voice of one of its authors.
---

# Knowledge base: {name}

{description}

Contents: {docs} documents — {authors}.

The library is a local index (hybrid semantic + keyword search, entity graph, style cards).
Every passage has a citable id like `{example_id}`. Never invent quotes: quote only text you
retrieved, and cite ids.

## Commands

Run with the Shell tool (first call loads models, ~5 s):

```bash
KB="{cli} --library {name}"
$KB overview                          # map: documents, keywords, cross-document entities, notes
$KB search "query" --also "translation" --also "synonyms" [-k 8] [--author X] [--doc id1,id2] [--per-doc 2] [--full]
$KB read ID [--before 1] [--after 1]  # full passage(s) around an id
$KB outline DOC_ID                    # chapters/sections with keywords + gist
$KB section DOC_ID SECTION_IDX        # a whole chapter
$KB related "Entity"                  # people/places/works that co-occur, with evidence ids
$KB style --author "X" [--theme "..."]  # voice card + exemplar passages
$KB note "Title" --body-file note.md --source ID --source ID   # save a synthesis to the wiki
```

If the `scriptorium` MCP server is connected, prefer its tools (same names, faster, models stay loaded).

## Workflow

1. **Orient cheaply**: `overview` once per task (skip if you already know the collection), `outline` for one book.
2. **Retrieve**: 1-3 `search` calls. Always add `--also` with the query translated into the language of the
   sources ({langs}) and with period or technical vocabulary: semantic search crosses languages, keyword
   search does not. Use `--per-doc 1` to compare works, `--author` / `--doc` to focus.
3. **Verify**: `read` the ids you will rely on (snippets are partial). Expand with `--before/--after`.
4. **Link**: `related "Name"` to discover connections you did not search for.
5. **Answer** with citations `[id]` next to each claim. Say explicitly when the library does not cover something.
6. **Writing in a voice**: `style --author X --theme "topic"`, follow the card, reuse vocabulary and rhythm,
   never copy sentences; cite the reference passages you drew facts from.
7. **Make it compound**: when you produce a synthesis worth keeping, save it with `note` (with `--source` ids).
"""


def export(name: str, dest_root: Path) -> Path:
    lib = Library(name)
    authors = sorted({d["author"] for d in lib.docs.values() if d["author"]})
    example = next(iter(lib.docs), "doc") + "#0012"
    cli = Path(sys.executable).parent / "scriptorium"
    langs = ", ".join(sorted({d["lang"] for d in lib.docs.values()}))
    text = TEMPLATE.format(
        name=name, about=lib.config.description or lib.config.topic, topic=lib.config.topic or name, langs=langs,
        description=lib.config.description, docs=len(lib.docs),
        authors=", ".join(authors[:20]) + (" …" if len(authors) > 20 else ""),
        example_id=example, cli=cli,
    )
    out = dest_root / f"knowledge-base-{name}" / "SKILL.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out
