# Roadmap: improvements and known issues

Priorities are based on measurements (`docs/eval-2026-10-01.md`, build logs), not guesses.
Re-run `scripts/eval_retrieval.py` after every retrieval change and record the new table.

## Measured baseline (v0.2.0, demo library, 14 blind paraphrase questions)

| configuration | hit@5 | MRR@10 |
|---|---|---|
| Italian query, hybrid + rerank | 0.29 | 0.25 |
| Italian + English `--also`, hybrid + rerank | **0.50** | 0.43 |
| English query, hybrid + rerank | 0.36 | 0.26 |

These are deliberately hard questions (no shared words, no author/doc filter, archaic spelling).
With filters and corpus vocabulary, as in `docs/demo-query-1.md`, results are much better, but blind
retrieval is the main weakness.

## P1: retrieval quality

1. **Stronger embedding model.** `multilingual-e5-small` is the weak link (vector-only hit@5 = 0.14 on
   Italian questions). Try `multilingual-e5-base`, `bge-m3` (dense + sparse) or a recent small
   multilingual model, and re-embed. Cost: indexing time ×2–4, RAM +0.5–1.5 GB. Decide with the eval table.
2. **Language-aware fusion.** BM25 on an Italian query against English books adds noise (hybrid scored
   below vector-only). Skip or down-weight FTS pools whose query language differs from the document
   language, and give `--also` translations full FTS weight.
3. **Bigger rerank pool.** Rerank 30 candidates instead of 18 and measure the hit@5 gain against latency.
4. **Contextual retrieval (optional LLM).** Prepend a 1–2 sentence LLM-written context to each chunk
   before embedding ("Emma's realisation, after Knightley's proposal, that she misjudged everyone…").
   Published results report large drops in failed retrievals. Cost on the demo corpus: about 6.4k calls,
   ~2.6M input tokens (mostly cacheable per book), ~0.5M output tokens; fine with a small/cheap model.
5. **Query expansion inside the tool.** The calling agent already writes `--also`; for non-agent use, add
   an optional LLM step that writes the translation and period vocabulary automatically.

## P2: abstraction layer

6. **LLM-compiled wiki (optional).** Per-section summaries → per-book card → per-entity and per-theme pages
   (RAPTOR / "LLM wiki" pattern), saved as notes with source ids. Extractive gists stay as the free baseline.
7. **Typed entities and aliases.** Replace the capitalisation heuristic with GLiNER or spaCy (it/en) to get
   person / place / work / organisation types and merge aliases (Knightley = Mr. Knightley; Ahab = Captain Ahab).
   Shakespeare speaker abbreviations (Ham., Macb.) should map to full names.
8. **Relations, not just co-occurrence.** Optional LLM extraction of (subject, relation, object) triples with
   evidence ids, à la LightRAG, for questions like "who influenced whom".
9. **Themes across books.** Cluster section embeddings into themes and label them (YAKE or LLM), so the
   graph can show theme nodes linking books.

## P3: ingestion and structure

10. **OCR pipeline for scans.** `ocrmypdf` and `tesseract` (ita+eng) are not installed: scanned PDFs are only
    flagged. Add `scriptorium add --ocr` that runs ocrmypdf automatically. Docling is an option for complex layouts.
11. **Old Word formats.** `.doc/.rtf/.odt` need `libreoffice-writer` (only `libreoffice-core` is installed).
12. **Verse detector false positives.** A short-line prose passage in *Sense and Sensibility* (§17) kept its
    hard line breaks. Use per-document line-length statistics instead of a fixed 52-character median.
13. **Play structure.** Hamlet yields only 5 sections (the Folio marks few scenes); speaker names leak into
    keywords. Detect speaker prefixes and use them as metadata.
14. **Printed page numbers.** PDF pages are physical pages; rare books need the printed folio. Detect running
    page numbers in headers and footers and store both.
15. **Bibliographic metadata.** Import from Zotero / BibTeX / CSV catalogues instead of filenames only.

## P4: performance and operations

16. **Indexing speed** (~5 chunks/s on this laptop under load): batch embedding in a separate process,
    int8-quantised ONNX model, or an optional `model2vec` fast mode for very large collections.
17. **PDF extraction** (~0.25 s/page with the layout model): parallelise across files; keep the cache.
18. **Query latency** (6–10 s warm via MCP, 10–20 s from the CLI): reranking dominates. Cache embeddings of
    repeated queries; consider a lighter reranker for interactive use, and keep the MCP server running.
19. **Global MCP registration.** Optional: copy the `.cursor/mcp.json` block into `~/.cursor/mcp.json`.

## Known issues / fixes queue

- `search --kind note` scores notes on a different scale from books (both reranked; fine), but notes are
  titled "Front matter" when the body has no subheadings: use the note title as the section.
- `Library.add` copies files; very large PDF collections may prefer `--move` or symlinks (`--link`, todo).
- Mixed-language libraries share one FTS stemmer (set per library); per-document stemming needs one FTS
  column per language.
- `remap` recomputes the entity graph and keywords but not the structure; structure changes need `build --force`.
