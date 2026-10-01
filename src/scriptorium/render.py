"""Compact plain-text renderings: what an agent actually reads. Every passage carries its
citable id, so the agent can drill down with read(id) instead of pulling whole chapters."""

from __future__ import annotations

import textwrap


def hits(results: list[dict], full: bool = False) -> str:
    if not results:
        return "No results."
    out = []
    for h in results:
        body = h["text"] if full else h["snippet"]
        out.append(f"[{h['id']}] {h['cite'].rsplit(' [', 1)[0]}  (score {h['score']})\n  « {body} »")
    return "\n".join(out) + "\n\n→ read(id, before, after) for full passages · cite with the [id]"


def passages(result: dict) -> str:
    if "error" in result:
        return result["error"]
    parts = [f"Source: {result['cite']}"]
    for p in result["passages"]:
        parts.append(f"\n[{p['id']}] ({p['section']})\n{p['text']}")
    return "\n".join(parts)


def overview(o: dict) -> str:
    lines = [f"Library '{o['library']}' — {o['description'] or o['topic']}", "", f"Documents ({len(o['docs'])}):"]
    for d in o["docs"]:
        who = f"{d['author']}, " if d["author"] else ""
        year = f" ({d['year']})" if d["year"] else ""
        lines.append(f"- {d['id']}: {who}{d['title']}{year} [{d['format']}, {d['sections']} sections] — "
                     + ", ".join(d["keywords"]))
    if o["cross_book_entities"]:
        lines += ["", "Entities linking several documents:", "  " + "; ".join(o["cross_book_entities"])]
    lines += ["", "Most mentioned: " + ", ".join(o["top_entities"])]
    if o["notes"]:
        lines += ["", "Wiki notes: " + "; ".join(f"{n['slug']} ({n['title']})" for n in o["notes"])]
    lines += ["", "→ outline(doc) for a book's map · search(query) for passages · related(entity) for links"]
    return "\n".join(lines)


def outline(o: dict) -> str:
    if "error" in o:
        return f"{o['error']}. Known: {', '.join(o['known'])}"
    lines = [f"{o['cite']} — keywords: {', '.join(o['keywords'][:12])}", ""]
    for s in o["sections"]:
        lines.append(f"§{s['idx']} {s['title']}  [{', '.join(s['keywords'])}]")
        lines.append(textwrap.indent(textwrap.shorten(s["gist"], 220), "    ") + f"  ({s['gist_id']})")
    lines.append("\n→ read_section(doc, idx) for a whole section · read(id) for one passage")
    return "\n".join(lines)


def related(r: dict) -> str:
    if "error" in r:
        return r["error"]
    lines = [f"{r['entity']}: {r['mentions']} mentions in " + ", ".join(f"{d} ({n})" for d, n in r["docs"].items())]
    if r["other_matches"]:
        lines.append("Other matching entities: " + ", ".join(r["other_matches"]))
    lines.append("Most strongly linked (co-occurring in the same passage):")
    for x in r["related"]:
        lines.append(f"- {x['entity']} — together in {x['together']} passages, e.g. {', '.join(x['evidence'])}")
    lines.append("First mentions: " + ", ".join(r["first_mentions"]))
    return "\n".join(lines)


def style(s: dict) -> str:
    if "error" in s:
        return f"{s['error']}. Authors: {', '.join(s['authors'])}"
    c = s["card"]
    p = c["punctuation_per_1000_words"]
    lines = [
        f"STYLE CARD — {', '.join(s['target'])} ({c['words']:,} words analysed)",
        *[f"- {t}" for t in s["guidance"]],
        f"- Punctuation per 1000 words: " + ", ".join(f"{k} {v}" for k, v in p.items()),
        f"- Distinctive vocabulary (vs rest of library): {', '.join(c['distinctive_words'])}",
        f"- Typical sentence openings: {', '.join(c['typical_sentence_openings'])}",
        "", "EXEMPLAR PASSAGES (imitate rhythm and diction, do not copy):",
    ]
    for e in s["exemplars"]:
        lines.append(f"\n{e['cite']}\n« {e['text']} »")
    return "\n".join(lines)
