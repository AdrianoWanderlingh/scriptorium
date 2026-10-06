# Roadmap: improvements and known issues

Priorities are based on measurements (`docs/eval-2026-10-01.md`, build logs), not guesses.
Re-run `scripts/eval_retrieval.py` after every retrieval change and record the new table.

## Measured (demo library, blind paraphrase questions, hit@5)

| configuration | v0.2.0 (dev, 14 q) | v0.3.0 dev (14 q) | v0.3.0 **test** (28 held-out q) |
|---|---|---|---|
| Italian query, default | 0.29 | 0.79 | **0.64** |
| Italian + English `--also`, default | 0.50 | 0.86 | **0.79** |
| English query, default | 0.36 | 0.93 | **0.79** |
| Verbatim quotation (6) | – | 1.00 (hit@1) | – |

Done in v0.3.0 (see `docs/BUILD_LOG.md`): stronger embedder (EmbeddingGemma), BM25 demoted to
candidate injector, whole-chunk reranking fused with vector order, exact-phrase boost.
Tried and rejected, with numbers: sentence windows with e5 (worse on dev), larger rerank pools 20–30
(no gain, 2–3× slower), BM25 fused in the ranking (−10 to −35 points on English), int8/q4 Gemma
(not faster on this CPU), 700-char windows with Gemma (+7–11 hit@1, same hit@5, 2× indexing time).

## P1: retrieval quality

1. **Drama.** Play text (speaker tags, Folio spelling) scores low with every embedder tried: Hamlet and
   Macbeth account for most remaining misses. Spelling modernisation helped (rank 1416 → 519) but did not
   fix it. Next: strip speaker prefixes before embedding (P3 #13). Low priority unless a library is drama.
2. **Latency** (11–14 s/query warm on this laptop, half reranker, half snippets). Options: rerank pool 6,
   lexical snippets for hits beyond the top 3, or 700-char chunks whose best window is the snippet.
3. **BM25 on modernised text** for Early Modern documents (needs a second text column for the FTS index).
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

16. **Indexing speed** (EmbeddingGemma ~4 chunks/s, ~30 min for the 6.4k-chunk demo): for very large
    collections offer `SCRIPTORIUM_EMBED_MODEL=intfloat/multilingual-e5-small` (~4× faster, much weaker)
    or a `model2vec` fast mode; quantised Gemma was not faster here.
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
