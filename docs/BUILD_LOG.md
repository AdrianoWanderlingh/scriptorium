# Build log: how Scriptorium was built

A chronological record of the decisions, problems and fixes during development. Per-run indexing logs
are machine-written to `libraries/<name>/build-log.jsonl`.

## 2026-10-01 · v0.1.0: MVP

**Environment.** Laptop i7-1255U (2P + 8E cores), 15 GB RAM with ~2 GB free and swap in use, no GPU, no
LLM API key. Constraints: CPU only, small models, no dependence on an LLM.

**Stack decisions.**
- Index: LanceDB (embedded, vectors + native BM25 + SQL filters in one folder). Rejected: Qdrant/Chroma
  (a server or separate FTS needed for hybrid), FAISS (no metadata/FTS).
- Embeddings: `intfloat/multilingual-e5-small` through fastembed as a custom ONNX model (no torch).
  Sanity check: the Italian query "matrimonio e ricchezza" ranked the English Austen sentence first.
- Reranker: `jina-reranker-v2-base-multilingual` (fastembed). 30 pairs ≈ 0.7 s cold test, much slower under load.
- Ingestion: MarkItDown (office/html/epub), PyMuPDF4LLM (pdf, page-aware), own CSV → one record per row.
- MCP SDK installed as v2: `FastMCP` is now `mcp.server.mcpserver.MCPServer`.

**Demo corpus.** NLTK Gutenberg (17 books, Bible excluded), written as txt plus HTML (Alice), PDF via
PyMuPDF Story (Thursday), DOCX via python-docx (Persuasion), CSV catalogue.
- LibreOffice cannot convert: only `libreoffice-core` is installed (no Writer). Used python-docx.

**Structure recovery, problems found and fixed.**
- Father Brown had 3 sections: titles look like "I. The Absence of Mr Glass" → added roman-numeral titles.
- Signatures like "P. HIRSCH" were taken as headings → excluded initials.
- Moby-Dick chapter subtitles ("Loomings.") not attached → subtitle merge with guards.
- The book title was repeated as a parent section in HTML/PDF/DOCX → skip headings equal to the title.

**First build.** 18 docs, 6,445 chunks, 1,826 entities, 20 min, 2.4 GB peak RSS.
- PDF extraction 52 s for 199 pages (layout model): kept for quality, cached by file hash.

**Search, problems found and fixed.**
- 26 s/query: reranking 30 full chunks took 14 s. Fixed by reranking the best 1–2 sentence window
  (plus context) of the top 18 candidates.
- Cross-lingual weakness (Willoughby missing from "matrimonio per denaro") → multi-query `also`
  (translation + period vocabulary) fused with RRF. Willoughby's confession then ranked 2nd.
- Thread count barely mattered (2→10 threads: 3.6→3.0 s); the machine is throttled by other load.
- Model cache was in `/tmp` (wiped at reboot) → `~/.cache/scriptorium/models`.

**Map quality, problems found and fixed.**
- Archaic function words (thy, thou, haue) in keywords → archaic stopwords plus keyword filter.
- "MacIan" split into "Mac" → camel-case names allowed.
- Common capitalised words (Time, Nature, March) as cross-book entities → drop single words mostly
  written lowercase in the corpus. Possessives merged (Ahab's → Ahab).
- Style card dominated by character names → words mostly capitalised are excluded from distinctive vocabulary.

**Tests.** Two tests failed at first and exposed real bugs: markdown headings glued to paragraphs (MarkItDown
output) were not detected, and a name after a stripped sentence-initial word ("Then Ahab") was marked
ambiguous. A third failure was a wrong test expectation (Stubb only appears sentence-initially), and the
test was corrected. Result: 9 tests (8 model-free plus 1 end-to-end CLI run).

**Demo query.** Misjudgment of character in Austen vs Father Brown: 7 calls, ~5.5k tokens read out of
~600k tokens of source, every quote verified with `read` (`docs/demo-query-1.md`).

## 2026-10-01 · v0.2.0: graph, skills, evaluation, hardening

- **Graph**: `scriptorium graph` writes `graph.html` (vis-network, self-contained data) and `graph.json`:
  books, top entities (guaranteed per-book coverage plus a cross-book boost), wiki notes, co-occurrence edges,
  evidence snippets in the side panel. Visual check in the browser: clusters per author, neighbourhood isolation works.
  Days and months were noise nodes → dropped unless concentrated in one book (keeps Chesterton's Sunday).
- **Skills**: the versioned manager skill `skills/scriptorium` ("usa scriptorium") plus generated
  `knowledge-base-<name>` skills, symlinked into `~/.cursor/skills` and `~/.claude/skills` by
  `scriptorium skills`, and refreshed after `add`/`build`.
- **Evaluation**: `scripts/eval_retrieval.py`, 14 blind questions → `docs/eval-2026-10-01.md`. Finding:
  blind Italian retrieval is weak (hit@5 0.29); `--also` translations raise it to 0.50; the reranker is what
  makes Italian queries work at all (hit@1 0 → 0.21). This drove the ROADMAP priorities.
- **Fixes**:
  - Metadata sidecar edits now trigger re-indexing (the fingerprint includes `.meta.json`).
  - FTS availability is checked explicitly instead of a bare `except`.
  - `zip(strict=True)` everywhere lengths must match.
  - LanceDB deprecation logs silenced (`LANCEDB_LOG=error`).
- **Ops**: `build-log.jsonl` per library (version, models, timings, warnings), `scriptorium --version`,
  ruff lint and format configuration (rule exceptions documented in `pyproject.toml`).
- **Lesson**: a ruff "unsafe fix" (RUF005) silently broke PyMuPDF `Rect` arithmetic in the corpus script.
  It was caught on review, reverted, and marked with `noqa` and the reason. Never apply unsafe fixes unreviewed.
