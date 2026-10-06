"""A named knowledge base: sources on disk, a LanceDB hybrid index, a compact map and a wiki."""

from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa

from . import mapper, models
from .config import EMBED_DIM, EMBED_MODEL, HOME, SUPPORTED_EXTENSIONS, LibraryConfig
from .ingest import Document, load, slugify, source_sha
from .structure import split_sentences, structure
from .style import describe, style_card
from .textstats import detect_lang, is_early_modern, modernize

SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("doc_id", pa.string()),
        ("kind", pa.string()),
        ("title", pa.string()),
        ("author", pa.string()),
        ("year", pa.string()),
        ("section", pa.string()),
        ("section_idx", pa.int32()),
        ("chunk_idx", pa.int32()),
        ("page", pa.int32()),
        ("text", pa.string()),
        ("vector", pa.list_(pa.float32(), EMBED_DIM)),
    ]
)
RRF_K = 60
RERANK_POOL = 10  # top vector hits the cross-encoder reads (~0.5 s each on CPU); 20-30 measured no better
KEYWORD_POOL = 3  # top BM25 hits per phrasing added to that pool


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" \t.,;:!?\"'“”‘’«»").lower()


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def chunk_id(doc_id: str, idx: int) -> str:
    return f"{doc_id}#{idx:04d}"


class Library:
    def __init__(self, name: str):
        self.name = name
        self.root = HOME / name
        if not (self.root / "library.json").exists():
            raise FileNotFoundError(f"library '{name}' not found in {HOME}. Create it with `scriptorium new {name}`")
        self.config = LibraryConfig.load(self.root / "library.json")
        self.sources = self.root / "sources"
        self.cache = self.root / "cache"
        self.map_dir = self.root / "map"
        self.wiki = self.root / "wiki"
        self._db = None
        self._docs = None
        self._entities = None

    # ------------------------------------------------------------------ lifecycle
    @classmethod
    def create(cls, name: str, description: str = "", topic: str = "", fts_language: str = "English") -> Library:
        root = HOME / name
        for sub in ("sources", "cache", "map", "wiki"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        if not (root / "library.json").exists():
            LibraryConfig(
                name=name, description=description, topic=topic, fts_language=fts_language, embed_model=EMBED_MODEL
            ).save(root / "library.json")
        return cls(name)

    @staticmethod
    def list_all() -> list[str]:
        return sorted(p.parent.name for p in HOME.glob("*/library.json")) if HOME.exists() else []

    def add(self, paths: list[Path], move: bool = False) -> list[Path]:
        added = []
        for path in paths:
            files = [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
            for f in files:
                if f.suffix.lower() not in SUPPORTED_EXTENSIONS and not f.name.endswith(".meta.json"):
                    continue
                dest = self.sources / (f.relative_to(path) if path.is_dir() else f.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                (shutil.move if move else shutil.copy2)(f, dest)
                added.append(dest)
        return added

    # ------------------------------------------------------------------ storage helpers
    @property
    def db(self):
        if self._db is None:
            self._db = lancedb.connect(self.root / "index.lance")
        return self._db

    def table(self):
        if "chunks" in self.db.table_names():
            return self.db.open_table("chunks")
        return self.db.create_table("chunks", schema=SCHEMA)

    @property
    def indexed_model(self) -> str:
        """Embedder of the stored vectors; libraries built before v0.3 have no record and used e5-small."""
        return self.config.embed_model or "intfloat/multilingual-e5-small"

    def _check_model(self) -> None:
        if self.indexed_model != EMBED_MODEL:
            raise RuntimeError(
                f"library '{self.name}' was indexed with {self.indexed_model}, the current embedder is "
                f"{EMBED_MODEL}: run `scriptorium -l {self.name} build` to re-embed it"
            )

    def _json(self, name: str, default):
        path = self.map_dir / name
        return json.loads(path.read_text()) if path.exists() else default

    def _save_json(self, name: str, data) -> None:
        tmp = self.map_dir / (name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(self.map_dir / name)

    @property
    def docs(self) -> dict:
        if self._docs is None:
            self._docs = self._json("docs.json", {})
        return self._docs

    @property
    def entity_index(self) -> dict:
        if self._entities is None:
            self._entities = self._json("entities.json", {"entities": {}, "chunk_entities": {}})
        return self._entities

    def _cached_load(self, path: Path) -> Document:
        sha = source_sha(path)
        cached = self.cache / f"{sha}.json"
        if cached.exists():
            data = json.loads(cached.read_text())
            data["page_offsets"] = [tuple(x) for x in data["page_offsets"]]
            doc = Document(**data)
            doc.source_path = str(path)
            return doc
        doc = load(path)
        cached.write_text(json.dumps(asdict(doc), ensure_ascii=False))
        return doc

    # ------------------------------------------------------------------ build
    def build(self, force: bool = False, log=print) -> dict:
        t0 = time.time()
        if self.indexed_model != EMBED_MODEL:
            log(f"  embedder changed ({self.indexed_model} → {EMBED_MODEL}): re-embedding everything")
            if "chunks" in self.db.table_names():
                self.db.drop_table("chunks")
            self._docs = {}
            self.config.embed_model = EMBED_MODEL
            self.config.save(self.root / "library.json")
            force = True
        files = sorted(
            p
            for p in self.sources.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.name.endswith(".meta.json")
        )
        table = self.table()
        by_source = {d["source"]: doc_id for doc_id, d in self.docs.items()}
        seen, changed = set(), 0
        events: list[dict] = []
        for n, path in enumerate(files, 1):
            rel = str(path.relative_to(self.sources))
            sha = source_sha(path)
            old_id = by_source.get(rel)
            if old_id and self.docs[old_id]["sha"] == sha and not force:
                seen.add(old_id)
                continue
            t = time.time()
            doc = self._cached_load(path)
            if doc.doc_id in self.docs and self.docs[doc.doc_id]["source"] != rel:
                doc.doc_id = f"{doc.doc_id}-{sha[:4]}"
            sections, chunks = structure(doc, self.config.chunk_chars)
            if not chunks:
                log(f"  [{n}/{len(files)}] {rel}: no text extracted, skipped")
                events.append({"source": rel, "status": "skipped", "reason": "no text extracted"})
                continue
            lang = detect_lang(doc.text)
            spell = modernize if is_early_modern(doc.text) else str
            vectors = models.embed_passages(
                [spell(c.text) for c in chunks], [f"{doc.title} — {c.section}" for c in chunks]
            )
            if old_id:
                table.delete(f"doc_id = {_sql(old_id)}")
            table.delete(f"doc_id = {_sql(doc.doc_id)}")
            table.add(
                pa.Table.from_pylist(
                    [
                        {
                            "id": chunk_id(doc.doc_id, c.chunk_idx),
                            "doc_id": doc.doc_id,
                            "kind": "book",
                            "title": doc.title,
                            "author": doc.author,
                            "year": doc.year,
                            "section": c.section,
                            "section_idx": c.section_idx,
                            "chunk_idx": c.chunk_idx,
                            "page": c.page if c.page is not None else -1,
                            "text": c.text,
                            "vector": v.tolist(),
                        }
                        for c, v in zip(chunks, vectors, strict=True)
                    ],
                    schema=SCHEMA,
                )
            )
            if old_id and old_id != doc.doc_id:
                self.docs.pop(old_id, None)
            self.docs[doc.doc_id] = {
                "title": doc.title,
                "author": doc.author,
                "year": doc.year,
                "fmt": doc.fmt,
                "source": rel,
                "sha": sha,
                "lang": lang,
                "chunks": len(chunks),
                "pages": len(doc.page_offsets) or None,
                "meta": doc.meta,
                "sections": mapper.section_map(sections, chunks, vectors, lang),
            }
            self.docs[doc.doc_id]["keywords"] = mapper.doc_keywords(self.docs[doc.doc_id]["sections"])
            self._save_json("docs.json", self.docs)
            seen.add(doc.doc_id)
            changed += 1
            seconds = round(time.time() - t, 1)
            events.append(
                {
                    "source": rel,
                    "doc_id": doc.doc_id,
                    "status": "indexed",
                    "chunks": len(chunks),
                    "sections": len(sections),
                    "lang": lang,
                    "seconds": seconds,
                    **({"warning": doc.meta["warning"]} if "warning" in doc.meta else {}),
                }
            )
            log(f"  [{n}/{len(files)}] {doc.doc_id}: {len(chunks)} chunks, {len(sections)} sections ({seconds}s)")

        for doc_id in [d for d in self.docs if d not in seen]:
            table.delete(f"doc_id = {_sql(doc_id)}")
            self.docs.pop(doc_id)
            changed += 1
            events.append({"doc_id": doc_id, "status": "removed"})
            log(f"  removed {doc_id} (source deleted)")
        self._save_json("docs.json", self.docs)

        indexed_notes = set(
            table.search().where("kind = 'note'").select(["doc_id"]).limit(None).to_arrow()["doc_id"].to_pylist()
        )
        for path in sorted(self.wiki.glob("*.md")):
            if force or f"note-{path.stem}" not in indexed_notes:
                self._index_note(path)
                changed += 1
                log(f"  indexed note {path.stem}")

        if changed or force or not (self.map_dir / "entities.json").exists():
            log("  full-text index + entity graph...")
            self._fts_and_entities()
        stats = {
            "docs": len(self.docs),
            "chunks": self.table().count_rows(),
            "changed": changed,
            "entities": len(self.entity_index["entities"]),
            "seconds": round(time.time() - t0, 1),
        }
        self._log_build(stats, events, force=force)
        log(f"  done: {stats}")
        return stats

    def _log_build(self, stats: dict, events: list[dict], **params) -> None:
        from . import __version__
        from .config import EMBED_MODEL, RERANK_MODEL

        record = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "version": __version__,
            "embed_model": EMBED_MODEL,
            "rerank_model": RERANK_MODEL,
            **params,
            **stats,
            "events": events,
        }
        with (self.root / "build-log.jsonl").open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _fts_and_entities(self) -> None:
        table = self.table()
        self._refresh_fts()
        rows = table.search().where("kind = 'book'").select(["id", "text"]).limit(None).to_arrow()
        self._entities = mapper.build_entity_index(rows["id"].to_pylist(), rows["text"].to_pylist())
        self._save_json("entities.json", self._entities)

    def remap(self, log=print) -> None:
        """Recompute the map (keywords, gists, entity graph) from the stored index, without re-embedding."""
        from .structure import Chunk, Section

        table = self.table()
        for doc_id, meta in self.docs.items():
            rows = (
                table.search()
                .where(f"doc_id = {_sql(doc_id)}")
                .select(["chunk_idx", "section_idx", "section", "page", "text", "vector"])
                .limit(None)
                .to_list()
            )
            rows.sort(key=lambda r: r["chunk_idx"])
            chunks = [
                Chunk(doc_id, r["chunk_idx"], r["section_idx"], r["section"], r["page"], 0, r["text"]) for r in rows
            ]
            vectors = np.asarray([r["vector"] for r in rows], dtype=np.float32)
            sections = [Section(s["idx"], s["title"], s["level"]) for s in meta["sections"]]
            meta["sections"] = mapper.section_map(sections, chunks, vectors, meta["lang"])
            meta["keywords"] = mapper.doc_keywords(meta["sections"])
            log(f"  remapped {doc_id}")
        self._save_json("docs.json", self.docs)
        self._fts_and_entities()
        log(f"  entities: {len(self.entity_index['entities'])}")

    # ------------------------------------------------------------------ citation
    def cite(self, row_or_id) -> str:
        row = self._row(row_or_id) if isinstance(row_or_id, str) else row_or_id
        if row is None:
            return f"[{row_or_id}] (unknown id)"
        who = f"{row['author']}, " if row["author"] else ""
        year = f" ({row['year']})" if row["year"] else ""
        page = f", p. {row['page']}" if row.get("page", -1) not in (-1, None) else ""
        return f"{who}{row['title']}{year} — {row['section']}{page} [{row['id']}]"

    def _row(self, cid: str) -> dict | None:
        rows = self.table().search().where(f"id = {_sql(cid)}").limit(1).to_list()
        return rows[0] if rows else None

    # ------------------------------------------------------------------ retrieval
    def _where(self, author: str | None, doc: str | None, kind: str | None) -> str | None:
        clauses = []
        if author:
            clauses.append(f"lower(author) LIKE {_sql('%' + author.lower() + '%')}")
        if doc:
            ids = [d.strip() for d in doc.split(",")]
            clauses.append("doc_id IN (" + ", ".join(_sql(d) for d in ids) + ")")
        if kind:
            clauses.append(f"kind = {_sql(kind)}")
        return " AND ".join(clauses) or None

    def search(
        self,
        query: str,
        k: int = 8,
        author: str | None = None,
        doc: str | None = None,
        kind: str | None = None,
        per_doc: int | None = None,
        rerank: bool = True,
        also: list[str] | None = None,
        mode: str = "hybrid",
    ) -> list[dict]:
        """`also`: extra phrasings of the same need (e.g. the query translated into the language
        of the books, synonyms, period vocabulary); a passage scores by its best-matching phrasing.
        `mode`: "hybrid" (default), "vector" or "fts" — single-retriever modes exist for evaluation.

        Measured on scripts/eval_retrieval.py (docs/eval-*.md): semantic vectors rank; keyword (BM25)
        hits only join the reranker's pool and the exact-phrase check, because fusing them into the
        ranking hurt paraphrased questions. The rerank order is fused with the vector order, since
        either alone is less reliable at the top."""
        if mode not in ("hybrid", "vector", "fts"):
            raise ValueError(f"unknown mode {mode!r}")
        self._check_model()
        table = self.table()
        where = self._where(author, doc, kind)
        queries = [query, *(also or [])]
        qvecs = models.embed_queries(queries)
        cols = [
            "id",
            "doc_id",
            "kind",
            "title",
            "author",
            "year",
            "section",
            "section_idx",
            "chunk_idx",
            "page",
            "text",
        ]
        rows: dict[str, dict] = {}
        sim: dict[str, float] = {}
        if mode != "fts":
            for qv in qvecs:
                vq = table.search(qv).distance_type("cosine").select(cols).limit(100 if per_doc else 50)
                for row in (vq.where(where, prefilter=True) if where else vq).to_list():
                    rows[row["id"]] = row
                    sim[row["id"]] = max(sim.get(row["id"], -1.0), 1 - row["_distance"])
        keyword: list[list[str]] = []
        if mode != "vector" and any("text" in idx.columns for idx in table.list_indices()):
            for q in queries:
                fq = table.search(q, query_type="fts").select(cols).limit(20)
                found = (fq.where(where) if where else fq).to_list()
                rows.update((r["id"], r) for r in found)
                keyword.append([r["id"] for r in found])
        vector_order = sorted(sim, key=sim.get, reverse=True)
        if mode == "fts":
            vector_order = list(dict.fromkeys(i for lst in keyword for i in lst))
        pool = list(dict.fromkeys(vector_order[:RERANK_POOL] + [i for lst in keyword for i in lst[:KEYWORD_POOL]]))
        if rerank and pool:
            texts = [f"{rows[c]['title']} — {rows[c]['section']}\n{rows[c]['text']}" for c in pool]
            score = dict(zip(pool, models.rerank(query, texts), strict=True))
            fused: dict[str, float] = defaultdict(float)
            for order in (sorted(pool, key=score.get, reverse=True), pool):
                for rank, c in enumerate(order):
                    fused[c] += 1 / (RRF_K + rank)
            pool = sorted(pool, key=fused.get, reverse=True)
        phrases = [p for p in (_norm(q) for q in queries) if len(p) > 8]
        nearby = dict.fromkeys(vector_order[:RERANK_POOL] + [i for lst in keyword for i in lst])
        exact = [c for c in nearby if any(p in _norm(rows[c]["text"]) for p in phrases)]
        ranked = list(dict.fromkeys(exact + pool + vector_order))

        hits, per = [], Counter()
        for cid in ranked:
            row = rows[cid]
            if per_doc and per[row["doc_id"]] >= per_doc:
                continue
            per[row["doc_id"]] += 1
            hits.append(
                {
                    "id": cid,
                    "score": round(sim.get(cid, 0.0), 3),
                    "cite": self.cite(row),
                    "doc_id": row["doc_id"],
                    "section": row["section"],
                    "text": row["text"],
                }
            )
            if len(hits) >= k:
                break
        for hit, window in zip(hits, self._best_windows([h["text"] for h in hits], qvecs), strict=True):
            hit["snippet"] = window["snippet"]
        return hits

    @staticmethod
    def _best_windows(texts: list[str], qvecs: np.ndarray, max_chars: int = 380) -> list[dict]:
        """Per text, the 1-2 sentence window closest to any query vector: the snippet."""
        windows, owners = [], []
        for i, text in enumerate(texts):
            sents = split_sentences(text.replace("\n", " ")) or [text]
            j = 0
            while j < len(sents):
                nxt = sents[j + 1] if j + 1 < len(sents) else ""
                step = 2 if nxt and len(sents[j]) + len(nxt) < max_chars else 1
                windows.append(" ".join(sents[j : j + step])[:max_chars])
                owners.append(i)
                j += step
        out = [{"snippet": t[:max_chars]} for t in texts]
        if not windows:
            return out
        sims = (models.embed_passages(windows, batch_size=16) @ qvecs.T).max(axis=1)
        best: dict[int, float] = {}
        for owner, window, s in zip(owners, windows, sims, strict=True):
            if owner not in best or s > best[owner]:
                best[owner] = s
                out[owner] = {"snippet": window}
        return out

    def read(self, cid: str, before: int = 0, after: int = 0) -> dict:
        doc_id, _, idx = cid.partition("#")
        idx = int(idx or 0)
        rows = (
            self.table()
            .search()
            .where(f"doc_id = {_sql(doc_id)} AND chunk_idx >= {idx - before} AND chunk_idx <= {idx + after}")
            .select(["id", "doc_id", "title", "author", "year", "section", "chunk_idx", "page", "text"])
            .limit(before + after + 1)
            .to_list()
        )
        rows.sort(key=lambda r: r["chunk_idx"])
        if not rows:
            return {"error": f"unknown id {cid}"}
        return {
            "cite": self.cite(next((r for r in rows if r["id"] == cid), rows[0])),
            "passages": [{"id": r["id"], "section": r["section"], "text": r["text"]} for r in rows],
        }

    def read_section(self, doc_id: str, section_idx: int, max_chars: int = 12000) -> dict:
        rows = (
            self.table()
            .search()
            .where(f"doc_id = {_sql(doc_id)} AND section_idx = {int(section_idx)}")
            .select(["id", "section", "chunk_idx", "text", "title", "author", "year", "page"])
            .limit(None)
            .to_list()
        )
        rows.sort(key=lambda r: r["chunk_idx"])
        text, used = [], 0
        for r in rows:
            if used + len(r["text"]) > max_chars:
                text.append(f"[... truncated, continue with read('{r['id']}')]")
                break
            text.append(f"[{r['id']}] {r['text']}")
            used += len(r["text"])
        return {"cite": self.cite(rows[0]) if rows else doc_id, "text": "\n\n".join(text)}

    # ------------------------------------------------------------------ map
    def overview(self) -> dict:
        ents = self.entity_index["entities"]
        bridges = sorted(
            (e for e in ents.items() if len(e[1]["docs"]) > 1),
            key=lambda e: (len(e[1]["docs"]), e[1]["n"]),
            reverse=True,
        )[:20]
        top = sorted(ents.items(), key=lambda e: e[1]["n"], reverse=True)[:30]
        return {
            "library": self.name,
            "description": self.config.description,
            "topic": self.config.topic,
            "docs": [
                {
                    "id": d,
                    "author": m["author"],
                    "title": m["title"],
                    "year": m["year"],
                    "format": m["fmt"],
                    "sections": len(m["sections"]),
                    "chunks": m["chunks"],
                    "keywords": m["keywords"][:6],
                }
                for d, m in sorted(self.docs.items(), key=lambda x: (x[1]["author"], x[1]["year"]))
            ],
            "top_entities": [f"{n} ({e['n']})" for n, e in top],
            "cross_book_entities": [f"{n} ({', '.join(list(e['docs'])[:4])})" for n, e in bridges],
            "notes": [{"slug": p.stem, "title": self._note_title(p)} for p in sorted(self.wiki.glob("*.md"))],
        }

    def outline(self, doc_id: str, depth: int | None = None) -> dict:
        meta = self.docs.get(doc_id)
        if not meta:
            return {"error": f"unknown doc {doc_id}", "known": list(self.docs)}
        sections = [s for s in meta["sections"] if depth is None or s["level"] <= depth]
        return {
            "doc": doc_id,
            "cite": f"{meta['author']}, {meta['title']} ({meta['year']})",
            "keywords": meta["keywords"],
            "sections": [
                {
                    "idx": s["idx"],
                    "title": s["title"],
                    "keywords": s["keywords"][:5],
                    "gist": s["gist"],
                    "gist_id": s["gist_id"],
                }
                for s in sections
            ],
        }

    def find_entity(self, name: str) -> list[str]:
        ents = self.entity_index["entities"]
        if name in ents:
            return [name]
        low = name.lower()
        exact = [n for n in ents if n.lower() == low]
        if exact:
            return exact
        partial = [n for n in ents if low in n.lower()]
        return sorted(partial, key=lambda n: ents[n]["n"], reverse=True)[:8]

    def related(self, name: str, top: int = 12) -> dict:
        matches = self.find_entity(name)
        if not matches:
            return {"error": f"no entity like '{name}'"}
        best = matches[0]
        e = self.entity_index["entities"][best]
        return {
            "entity": best,
            "mentions": e["n"],
            "docs": dict(list(e["docs"].items())[:8]),
            "other_matches": matches[1:],
            "first_mentions": e["chunks"][:3],
            "related": mapper.related(self.entity_index, best, top),
        }

    # ------------------------------------------------------------------ style
    def style(
        self, author: str | None = None, doc: str | None = None, theme: str | None = None, examples: int = 3
    ) -> dict:
        targets = {
            d
            for d, m in self.docs.items()
            if (author and author.lower() in m["author"].lower()) or (doc and d in doc.split(","))
        }
        if not targets:
            return {"error": "no matching documents", "authors": sorted({m["author"] for m in self.docs.values()})}
        rows = self.table().search().where("kind = 'book'").select(["doc_id", "text"]).limit(None).to_arrow()
        texts = defaultdict(list)
        for d, t in zip(rows["doc_id"].to_pylist(), rows["text"].to_pylist(), strict=True):
            texts[d].append(t)
        lang = Counter(self.docs[d]["lang"] for d in targets).most_common(1)[0][0]
        card = style_card(
            [t for d in targets for t in texts[d]], [t for d, ts in texts.items() if d not in targets for t in ts], lang
        )
        if theme:
            ex = self.search(theme, k=examples, doc=",".join(targets), per_doc=2)
            exemplars = [{"cite": h["cite"], "text": h["text"][:900]} for h in ex]
        else:
            gist_ids = [s["gist_id"] for d in sorted(targets) for s in self.docs[d]["sections"][1::7]][:examples]
            exemplars = [{"cite": r["cite"], "text": r["passages"][0]["text"][:900]} for r in map(self.read, gist_ids)]
        return {"target": sorted(targets), "card": card, "guidance": describe(card), "exemplars": exemplars}

    # ------------------------------------------------------------------ wiki (agent-compiled notes)
    def _note_title(self, path: Path) -> str:
        m = re.search(r"^title:\s*(.+)$", path.read_text(), re.M)
        return m.group(1).strip() if m else path.stem

    def write_note(
        self, title: str, body: str, sources: list[str] | None = None, tags: list[str] | None = None
    ) -> dict:
        slug = slugify(title, 64)
        sources = sources or []
        front = [f"title: {title}", f"updated: {date.today().isoformat()}"]
        if tags:
            front.append("tags: [" + ", ".join(tags) + "]")
        if sources:
            front.append("sources: [" + ", ".join(sources) + "]")
        refs = "\n".join(f"- {self.cite(s)}" for s in sources)
        text = "---\n" + "\n".join(front) + "\n---\n\n" + f"# {title}\n\n{body.strip()}\n"
        if refs:
            text += f"\n## Sources\n\n{refs}\n"
        path = self.wiki / f"{slug}.md"
        path.write_text(text)
        n = self._index_note(path)
        self._refresh_fts()
        return {"note": str(path), "id": chunk_id(f"note-{slug}", 0), "chunks": n}

    def _index_note(self, path: Path) -> int:
        title = self._note_title(path)
        doc = Document(
            doc_id=f"note-{path.stem}",
            title=title,
            author="Wiki",
            year=date.today().isoformat()[:4],
            source_path=str(path),
            fmt="md",
            text=path.read_text().split("---", 2)[-1],
            sha="",
        )
        _, chunks = structure(doc, self.config.chunk_chars)
        vectors = models.embed_passages([c.text for c in chunks], [f"{title} — {c.section}" for c in chunks])
        table = self.table()
        table.delete(f"doc_id = {_sql(doc.doc_id)}")
        table.add(
            pa.Table.from_pylist(
                [
                    {
                        "id": chunk_id(doc.doc_id, c.chunk_idx),
                        "doc_id": doc.doc_id,
                        "kind": "note",
                        "title": title,
                        "author": "Wiki",
                        "year": doc.year,
                        "section": c.section,
                        "section_idx": c.section_idx,
                        "chunk_idx": c.chunk_idx,
                        "page": -1,
                        "text": c.text,
                        "vector": v.tolist(),
                    }
                    for c, v in zip(chunks, vectors, strict=True)
                ],
                schema=SCHEMA,
            )
        )
        return len(chunks)

    def _refresh_fts(self) -> None:
        self.table().create_fts_index(
            "text",
            replace=True,
            language=self.config.fts_language,
            stem=True,
            remove_stop_words=True,
            ascii_folding=True,
        )

    def delete_note(self, slug: str) -> bool:
        slug = slug.removeprefix("note-")
        path = self.wiki / f"{slug}.md"
        self.table().delete(f"doc_id = {_sql('note-' + slug)}")
        self._refresh_fts()
        if path.exists():
            path.unlink()
            return True
        return False

    def read_note(self, slug: str) -> str:
        path = self.wiki / f"{slug.removeprefix('note-')}.md"
        return path.read_text() if path.exists() else f"no note '{slug}'"
