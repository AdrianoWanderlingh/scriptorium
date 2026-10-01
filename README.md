# Scriptorium

Private knowledge bases from digitised books, rare texts and your own writings — CPU only, open source,
usable by any agent as a **Skill** (`knowledge-base-<name>`) or an **MCP server**.

An agent never reads whole books: it reads a compact *map* of the library, then retrieves short
snippets with citable ids, then opens only the passages it needs. Typical answers use ~1% of the
text of the books involved, with every claim traceable to `[doc#chunk]`.

## Stack (all local, no GPU)

| Stage | Choice | Why |
|---|---|---|
| Ingestion | MarkItDown (docx, pptx, xlsx, html, epub, json, xml) · PyMuPDF4LLM with layout model (pdf, page-aware) · own CSV row→record · LibreOffice for doc/rtf/odt · optional Docling (`SCRIPTORIUM_PDF_ENGINE=docling`) | one pipeline for mixed formats, page numbers kept for citations |
| Structure | own parser: volumes / chapters / acts / cantos / markdown headings, unwraps prose, keeps verse | chunks never cross a chapter; citations say *where* |
| Embeddings | `intfloat/multilingual-e5-small` via fastembed (ONNX) | multilingual (Italian query ⇄ English books), small enough for 2 GB free RAM |
| Index | **LanceDB** (embedded, single folder): vectors + native BM25 full-text with stemming | hybrid search with SQL filters, no server |
| Fusion / rerank | Reciprocal Rank Fusion over multi-query (query + translations) → `jina-reranker-v2-base-multilingual` on best window | precision without GPU |
| Abstraction layer | outline per book with YAKE keywords + central "gist" sentence; entity graph from co-occurrence (PMI); agent-written wiki notes re-indexed | cheap orientation, links, knowledge that compounds |
| Voice | stylometric style card (sentence length, punctuation, log-odds distinctive vocabulary, openings) + retrieved exemplars | write in an author's voice without fine-tuning |
| Interfaces | Typer CLI · MCP server (`mcp` SDK v2) · SKILL.md generator | works in Cursor, Claude, any MCP client |

## Use

```bash
uv sync
S=.venv/bin/scriptorium

$S new fotoITA --description "Fotografia italiana: libri, cataloghi, miei scritti" \
   --topic "fotografia italiana" --language Italian
$S -l fotoITA add ~/Documents/libri-foto ~/Documents/miei-scritti   # copies + builds incrementally
$S -l fotoITA skill                                                 # → ~/.cursor/skills/knowledge-base-fotoITA

$S -l fotoITA overview
$S -l fotoITA search "Ghirri e il colore" --also "Ghirri colour Kodachrome" --per-doc 2
$S -l fotoITA read ghirri-kodachrome#0042 --after 1
$S -l fotoITA outline ghirri-kodachrome
$S -l fotoITA related "Luigi Ghirri"
$S -l fotoITA style --author "Mio Nome" --theme "paesaggio padano"
$S -l fotoITA note "Ghirri e la pianura" --body-file sintesi.md -s ghirri-kodachrome#0042
```

Metadata: name files `Author - Title (Year).ext`, or put a `file.ext.meta.json` next to them
(`{"author": ..., "title": ..., "year": ...}`). Scanned PDFs: run `ocrmypdf -l ita+eng in.pdf out.pdf` first.

MCP: `.cursor/mcp.json` in this repo starts `scriptorium serve`; copy that block into `~/.cursor/mcp.json`
to have the tools in every project. Tools: `list_libraries, overview, search, read, outline,
read_section, related, style, write_note, read_note`.

Demo corpus (18 Gutenberg classics from NLTK, in txt/pdf/docx/html/csv):
`uv run python scripts/fetch_demo_corpus.py && $S new classici-inglesi && $S -l classici-inglesi add corpus/classici-inglesi`.
See `docs/demo-query-1.md` for a worked query.

## Layout

```
libraries/<name>/
  library.json   sources/   cache/ (extracted text by file hash)
  index.lance/   (chunks: text + vector + metadata, BM25 index)
  map/docs.json  (outline, keywords, gists)   map/entities.json (entity graph)
  wiki/*.md      (agent-written notes, also indexed)
```

Tests: `uv run pytest` (unit tests are model-free; `test_end_to_end.py` runs the real models, ~25 s).
