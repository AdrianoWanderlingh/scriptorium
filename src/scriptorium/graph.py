"""Navigable view of the abstraction layer: documents, the most relevant entities and wiki notes,
linked by co-occurrence. Writes a self-contained HTML page (vis-network) plus graph.json."""

from __future__ import annotations

import colorsys
import json
import math
import re
from collections import Counter
from pathlib import Path

from . import mapper
from .library import Library, _sql

TEMPLATE = Path(__file__).with_name("graph_template.html")


def _palette(keys: list[str]) -> dict[str, str]:
    out = {}
    for i, key in enumerate(sorted(keys)):
        r, g, b = colorsys.hls_to_rgb((i * 0.618034) % 1, 0.55, 0.62)
        out[key] = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
    return out


def _select_entities(lib: Library, top: int, per_doc: int) -> list[str]:
    ents = lib.entity_index["entities"]

    def score(name: str) -> float:
        e = ents[name]
        return math.log1p(e["n"]) * (1 + 0.6 * (len(e["docs"]) - 1))

    chosen: dict[str, None] = {}
    for doc_id in lib.docs:
        local = sorted(
            (n for n, e in ents.items() if doc_id in e["docs"]), key=lambda n: ents[n]["docs"][doc_id], reverse=True
        )
        chosen.update(dict.fromkeys(local[:per_doc]))
    for name in sorted(ents, key=score, reverse=True):
        if len(chosen) >= top:
            break
        chosen.setdefault(name)
    return list(chosen)[: max(top, len(chosen))]


def _snippets(lib: Library, ids: set[str], width: int = 240) -> dict[str, str]:
    if not ids:
        return {}
    rows = (
        lib.table()
        .search()
        .where("id IN (" + ", ".join(_sql(i) for i in sorted(ids)) + ")")
        .select(["id", "text"])
        .limit(len(ids))
        .to_list()
    )
    return {r["id"]: re.sub(r"\s+", " ", r["text"])[:width] + "…" for r in rows}


def build_graph(lib: Library, top: int = 150, per_doc: int = 5, edges_per_node: int = 6) -> dict:
    ents = lib.entity_index["entities"]
    names = _select_entities(lib, top, per_doc)
    selected = set(names)
    colors = _palette(sorted({m["author"] or "?" for m in lib.docs.values()} | {"Wiki"}))

    nodes, edges, evidence_ids = [], [], set()
    for doc_id, m in lib.docs.items():
        nodes.append(
            {
                "id": f"doc:{doc_id}",
                "label": m["title"][:38],
                "group": "doc",
                "author": m["author"] or "?",
                "color": colors[m["author"] or "?"],
                "value": 30 + math.sqrt(m["chunks"]),
                "shape": "box",
                "info": {
                    "type": "document",
                    "id": doc_id,
                    "author": m["author"],
                    "title": m["title"],
                    "year": m["year"],
                    "format": m["fmt"],
                    "keywords": m["keywords"][:10],
                    "sections": [f"§{s['idx']} {s['title']}" for s in m["sections"][:14]],
                },
            }
        )

    seen_pairs: set[tuple[str, str]] = set()
    for name in names:
        e = ents[name]
        home = max(e["docs"], key=e["docs"].get)
        author = lib.docs.get(home, {}).get("author") or "?"
        links = [r for r in mapper.related(lib.entity_index, name, top=40) if r["entity"] in selected]
        evidence = e["chunks"][:2]
        evidence_ids.update(evidence)
        nodes.append(
            {
                "id": f"ent:{name}",
                "label": name,
                "group": "entity",
                "author": author,
                "color": colors[author],
                "value": math.sqrt(e["n"]),
                "shape": "dot",
                "info": {
                    "type": "entity",
                    "name": name,
                    "mentions": e["n"],
                    "docs": e["docs"],
                    "related": [f"{r['entity']} ({r['together']})" for r in links[:10]],
                    "evidence": evidence,
                },
            }
        )
        for r in links[:edges_per_node]:
            pair = tuple(sorted((name, r["entity"])))
            if pair in seen_pairs or r["together"] < 2:
                continue
            seen_pairs.add(pair)
            edges.append(
                {
                    "from": f"ent:{pair[0]}",
                    "to": f"ent:{pair[1]}",
                    "value": r["together"],
                    "title": f"together in {r['together']} passages, e.g. {', '.join(r['evidence'])}",
                }
            )
        for doc_id, count in e["docs"].items():
            if doc_id in lib.docs and count >= max(3, 0.1 * e["n"] / max(1, len(e["docs"]))):
                edges.append(
                    {
                        "from": f"ent:{name}",
                        "to": f"doc:{doc_id}",
                        "value": 1,
                        "dashes": True,
                        "title": f"{count} passages in {doc_id}",
                        "color": {"opacity": 0.25},
                    }
                )

    for path in sorted(lib.wiki.glob("*.md")):
        text = path.read_text()
        sources = re.findall(r"\[([\w-]+#\d{4})\]", text)
        title = lib._note_title(path)
        nodes.append(
            {
                "id": f"note:{path.stem}",
                "label": title[:40],
                "group": "note",
                "author": "Wiki",
                "color": colors["Wiki"],
                "value": 25,
                "shape": "star",
                "info": {
                    "type": "note",
                    "slug": path.stem,
                    "title": title,
                    "sources": sorted(set(sources)),
                    "text": text.split("---", 2)[-1][:1200],
                },
            }
        )
        for doc_id, n in Counter(s.split("#")[0] for s in sources).items():
            if doc_id in lib.docs:
                edges.append(
                    {"from": f"note:{path.stem}", "to": f"doc:{doc_id}", "value": n, "title": f"cites {n} passages"}
                )
        mentioned = [n for n in names if n in text]
        for name in mentioned[:12]:
            edges.append({"from": f"note:{path.stem}", "to": f"ent:{name}", "value": 1, "dashes": True})

    snippets = _snippets(lib, evidence_ids)
    for node in nodes:
        if node["group"] == "entity":
            node["info"]["evidence"] = [{"id": i, "text": snippets.get(i, "")} for i in node["info"]["evidence"]]
    return {
        "library": lib.name,
        "description": lib.config.description,
        "colors": colors,
        "nodes": nodes,
        "edges": edges,
    }


def write_html(graph: dict, out: Path) -> Path:
    payload = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")
    template = TEMPLATE.read_text()
    out.write_text(template.replace("__DATA__", payload).replace("__TITLE__", f"Scriptorium · {graph['library']}"))
    out.with_suffix(".json").write_text(json.dumps(graph, ensure_ascii=False, indent=1))
    return out
