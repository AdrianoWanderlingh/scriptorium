# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

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
