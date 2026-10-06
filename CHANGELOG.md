# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.3.0] - 2026-10-01

Retrieval rebuilt on measurements (`docs/eval-2026-10-01-v0.3.0.md`). Held-out test set, hit@5:
Italian question 0.11 → 0.64, Italian + English `--also` 0.79, verbatim quotations 1.00 (hit@1).

### Changed
- Embedder `google/embeddinggemma-300m` (768-d) replaces `multilingual-e5-small`; model prompts per spec.
  Libraries record their embedder in `library.json`; `build` re-embeds automatically when it changes,
  `search` refuses mismatched vectors with a clear message.
- Ranking: vector similarity (best of `query` + `also`) ranks; BM25 hits only join the rerank pool
  (top 3 per phrasing); the reranker reads whole chunks (was: 900-char windows) on a pool of ~10–16
  and its order is fused with the vector order; verbatim matches of the query go first.
- Snippets are chosen only for the returned hits, on sentence pairs (half the cost).
- Early Modern English spelling (Folio: haue, vp, Ideot) is modernised in the text sent to the
  embedder, for documents detected as such; stored text and citations keep the original.

### Added
- 28 held-out test questions and 6 exact-quotation checks in `scripts/eval_retrieval.py`.

### Fixed
- Build stats counted chunks on a stale table handle (notes indexed in the same build were missing).
- Opening a library whose stored vectors have another dimension no longer fails on schema mismatch.

## [0.2.0] - 2026-10-01

### Added
- `scriptorium graph [--open]`: interactive HTML graph (books, key entities, wiki notes, evidence) and `graph.json`.
- `scriptorium skills`: manager skill `scriptorium` and per-library `knowledge-base-<name>` skills,
  symlinked into `~/.cursor/skills` and `~/.claude/skills`; library skills refresh after `add`/`build`.
- `libraries/<name>/build-log.jsonl`: one record per build (version, models, timings, warnings).
- `scripts/eval_retrieval.py` and the first evaluation report `docs/eval-2026-10-01.md`.
- `search(mode="vector"|"fts"|"hybrid")` for evaluation; `scriptorium --version`.
- `docs/ROADMAP.md`, `docs/BUILD_LOG.md`, this changelog; ruff lint and format configuration.

### Changed
- `scriptorium skill` replaced by `scriptorium skills` (all libraries at once).
- The graph HTML template lives in `graph_template.html`.
- Days and months are kept as entities only when they behave like a character in one book.

### Fixed
- Editing a `.meta.json` sidecar now re-indexes the document (it was ignored).
- The full-text index presence is checked explicitly (no silent `except Exception`).
- `zip()` calls are strict where lengths must match.
- LanceDB deprecation warnings no longer pollute CLI and agent output.

## [0.1.0] - 2026-10-01

### Added
- Libraries with incremental builds; ingestion of txt, md, pdf (page-aware), docx, pptx, xlsx, csv, html, epub, json, xml.
- Structure recovery (volumes, chapters, acts, cantos, markdown headings), citation-friendly chunks.
- LanceDB hybrid search (multilingual e5 vectors + BM25), multi-query RRF, multilingual reranking, snippets.
- Map: outline with keywords and gists, entity graph (`related`), style cards (`style`), wiki notes (`note`).
- CLI, MCP server (10 tools), generated Agent Skill, demo corpus script, tests.
