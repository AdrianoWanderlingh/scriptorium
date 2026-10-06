# Scriptorium

Local knowledge bases from digitised books, rare texts and your own writings — CPU only, no GPU, no
API key. An agent uses it as a **Skill** (`knowledge-base-<name>`) or an **MCP server**.

The agent never reads whole books: it reads a compact *map* of the library, retrieves short snippets
with citable ids, then opens only the passages it needs. Typical answers use ~1% of the text of the
books involved, with every claim traceable to `[doc#chunk]`.

## Setup

Python 3.12+ and [uv](https://docs.astral.sh/uv/). First `search` or `build` downloads ONNX models
into `~/.cache/scriptorium/models/` (~1.2 GB, once). Indexed libraries live in `libraries/<name>/`
and are **not** in git (sources, cache, vectors).

```bash
git clone https://github.com/AdrianoWanderlingh/scriptorium.git
cd scriptorium
uv sync
S=.venv/bin/scriptorium
```

## Use

```bash
$S new fotoITA --description "Fotografia italiana: libri, cataloghi, miei scritti" \
   --topic "fotografia italiana" --language Italian
$S -l fotoITA add ~/Documents/libri-foto ~/Documents/miei-scritti   # copies + builds incrementally
$S skills          # symlinks `scriptorium` + `knowledge-base-*` into ~/.cursor/skills and ~/.claude/skills
$S -l fotoITA graph --open                                          # interactive graph (HTML + graph.json)

$S -l fotoITA overview
$S -l fotoITA search "Ghirri e il colore" --also "Ghirri colour Kodachrome" --per-doc 2
$S -l fotoITA read ghirri-kodachrome#0042 --after 1
$S -l fotoITA outline ghirri-kodachrome
$S -l fotoITA related "Luigi Ghirri"
$S -l fotoITA style --author "Ghirri" --theme "paesaggio padano"
$S -l fotoITA note "Ghirri e la pianura" --body-file sintesi.md -s ghirri-kodachrome#0042
```

| Command | What it does |
|---|---|
| `new NAME` | Create an empty library |
| `add PATH` | Copy files/folders in and index them |
| `build` | Re-index after manual edits in `libraries/NAME/sources/` |
| `overview` | Map: documents, keywords, entities, wiki notes |
| `search "…"` | Hybrid search; always add `--also` (translation / synonyms) |
| `read ID` | Full passage; `--before` / `--after` for neighbours |
| `outline DOC` | Chapters with keywords and a gist sentence |
| `related "Name"` | People/places/works that co-occur |
| `style --author X` | Voice card + exemplar passages (then write in that rhythm, do not copy sentences) |
| `note "Title"` | Save a synthesis; it becomes searchable |
| `skills` | Install agent skills for this clone |
| `graph --open` | Navigable HTML graph |

**Metadata** (citations depend on it): name files `Author - Title (Year).ext`, or put
`file.ext.meta.json` next to them (`{"author": ..., "title": ..., "year": ...}`).

**Scanned PDFs** (no text layer): `ocrmypdf -l ita+eng in.pdf out.pdf` first.

**`--also`**: extra phrasings in the language of the books. Italian questions on English books jump
from ~64% to ~79% hit@5 on the held-out eval when a translation is passed.

Never invent quotes: cite `[id]` next to each claim; `read` anything you will rely on.

Demo corpus (18 Gutenberg classics):
`uv run python scripts/fetch_demo_corpus.py && $S new classici-inglesi --language English && $S -l classici-inglesi add corpus/classici-inglesi`.
Worked example: `docs/demo-query-1.md`.

## In a chat

After `$S skills`, open a **new** chat in this repo and say e.g. "usa scriptorium, aggiungi questi PDF"
or "cerca cosa dice la libreria sul colore". The `scriptorium` skill handles ingest; `knowledge-base-<name>`
handles search, citation and writing in a voice.

If skills are not loaded, ask the agent: **read `README.md` and help me use Scriptorium** (then describe
the task). Prefer MCP tools from `.cursor/mcp.json` when connected (`scriptorium serve`): models stay loaded.

## Layout

```
libraries/<name>/
  library.json   sources/   cache/ (extracted text by file hash)
  index.lance/   (chunks: text + vector + metadata, BM25 index)
  map/docs.json  (outline, keywords, gists)   map/entities.json (entity graph)
  wiki/*.md      (agent-written notes, also indexed)
  graph.html / graph.json   build-log.jsonl
```

## Stack (all local, no GPU)

| Stage | Choice | Why |
|---|---|---|
| Ingestion | MarkItDown (docx, pptx, xlsx, html, epub, json, xml) · PyMuPDF4LLM with layout model (pdf, page-aware) · own CSV row→record · LibreOffice for doc/rtf/odt · optional Docling (`SCRIPTORIUM_PDF_ENGINE=docling`) | one pipeline for mixed formats, page numbers kept for citations |
| Structure | own parser: volumes / chapters / acts / cantos / markdown headings, unwraps prose, keeps verse | chunks never cross a chapter; citations say *where* |
| Embeddings | `google/embeddinggemma-300m` via fastembed (ONNX, CPU) | multilingual (Italian query ⇄ English books); chosen by measurement over e5-small (hit@5 on Italian questions 0.11 → 0.54 vector-only), ~1.2 GB RAM, ~4 chunks/s to index |
| Index | **LanceDB** (embedded, single folder): vectors + native BM25 full-text with stemming | hybrid search with SQL filters, no server |
| Fusion / rerank | vector ranking over query + `--also`; BM25 only injects candidates; jina multilingual reranker on whole chunks, fused with vectors; verbatim matches first | precision without GPU |
| Abstraction layer | outline per book with YAKE keywords + central "gist" sentence; entity graph from co-occurrence (PMI); agent-written wiki notes re-indexed | cheap orientation, links, knowledge that compounds |
| Voice | stylometric style card (sentence length, punctuation, log-odds distinctive vocabulary, openings) + retrieved exemplars | write in an author's voice without fine-tuning |
| Interfaces | Typer CLI · MCP server (`mcp` SDK v2) · SKILL.md generator | works in Cursor, Claude, any MCP client |

## Quality and docs

- `uv run pytest`: unit tests are model-free; `test_end_to_end.py` runs the real models (~25 s).
- `uvx ruff check . && uvx ruff format --check .`
- `uv run python scripts/eval_retrieval.py > docs/eval-$(date +%F).md`: retrieval benchmark (hit@k, MRR).
- `docs/ROADMAP.md`, `docs/BUILD_LOG.md`, `CHANGELOG.md`, `libraries/<name>/build-log.jsonl`.
