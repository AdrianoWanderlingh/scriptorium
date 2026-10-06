---
name: scriptorium
description: Private book knowledge bases (Scriptorium). Use when the user says "usa scriptorium", "scriptorium", "knowledge base", "biblioteca", or asks to ingest/add books, PDFs, scans or their own writings into a library, create a new library on a topic, search or cite what a collection says, write text from those references or in an author's voice, or show the knowledge graph.
---

# Scriptorium

Local, CPU-only knowledge bases built from books and documents. Each library is a folder under
`libraries/<name>/` in this repo (or `$SCRIPTORIUM_HOME`) with its sources, a hybrid search index, a
map (outline, keywords, entity graph) and a wiki of notes. Each library also has its own skill
`knowledge-base-<name>` with the query workflow.

From the clone root:

```bash
S=.venv/bin/scriptorium
$S list                # libraries and sizes: run this first if you do not know which library to use
```

Pick the library from the user's words (topic, name). If none fits and the user wants to store material,
create one. Ask only if two libraries are equally plausible.

## Ingest (create / add)

```bash
$S new NAME --description "what is inside" --topic "when to use it" --language Italian   # or English
$S -l NAME add PATH [PATH...]      # files or folders; copies them in and indexes incrementally
$S -l NAME build                   # re-index after manual changes in libraries/NAME/sources/
$S skills                          # refresh the knowledge-base-* skills (also done after add/build)
```

- Formats: txt, md, pdf, docx, pptx, xlsx, csv, html, epub, json, xml (doc/rtf/odt need LibreOffice Writer).
- Metadata: name files `Author - Title (Year).ext`, or write `file.ext.meta.json` with
  `{"author": "...", "title": "...", "year": "..."}` next to the file. Do this before `add` when the
  user gives you authors/titles: citations depend on it.
- Scanned PDFs (no text layer): build warns "probably a scan"; OCR first with
  `ocrmypdf -l ita+eng in.pdf out.pdf` (install `ocrmypdf tesseract-ocr-ita` if missing).
- Indexing is CPU-bound: about 4 passages/s (a 300-page book ≈ 1–2 min). Tell the user before starting
  a big batch; run it in the background and report progress.
- Every build appends a record to `libraries/NAME/build-log.jsonl` (timings, warnings, skipped files).

## Query, cite, write

Follow the `knowledge-base-NAME` skill. In short: `overview` → `search "query" --also "translation"` →
`read ID` → answer with `[id]` citations; `style --author X --theme "..."` before writing in a voice;
save durable syntheses with `note` (they become searchable and appear in the graph).

## Graph

```bash
$S -l NAME graph --open            # libraries/NAME/graph.html (+ graph.json for Gephi etc.)
```

Books (boxes), most relevant entities (dots, size = mentions), wiki notes (stars); edges = passages in
common. Click for details and evidence ids, double-click to isolate a neighbourhood.

## MCP

The same tools are available as an MCP server (`scriptorium serve`); the repo's `.cursor/mcp.json`
registers it. If its tools (`search`, `read`, `overview`, …) are available, prefer them: models stay loaded.
