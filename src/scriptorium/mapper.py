"""The abstraction layer: a compact, LLM-free map of the library.

For every book: outline with per-section keywords and a one-sentence gist.
For the whole library: themes, and an entity graph (people, places, ships, works...)
built from co-occurrence inside chunks, so an agent can follow links cheaply."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

import numpy as np

from .structure import Chunk, Section, split_sentences
from .textstats import keywords

HONORIFIC = (
    r"(?:Mr|Mrs|Miss|Ms|Dr|Sir|Lady|Lord|Captain|Capt|Colonel|Father|Mother|St|Saint|King|Queen|Prince"
    r"|Signor|Signora|Don|Donna|Padre|San|Santa)\.?\s+"
)
CAP_WORD = r"[A-ZÀ-Ý][a-zà-ÿ]+(?:[A-Z][a-zà-ÿ]+)*(?:['’-][A-Za-zà-ÿ]+)?"
CONNECT = r"(?:\s+(?:of|de|di|da|del|della|dei|degli|van|von|la|le|du)\s+|\s+)"
ENTITY_RE = re.compile(rf"(?<![\w'’])((?:{HONORIFIC})?{CAP_WORD}(?:{CONNECT}{CAP_WORD})*)")
SENT_START = re.compile(r"(?:^|[.!?…:;]\s*[\"'“‘«(\[]*\s*|\n\s*[\"'“‘«(\[]*|[\"“«]\s*)$")
STOP_CAPS = set(
    """The A An And But Or If In On At It He She They We You I His Her My Your Our Their This That
These Those There Here What Which Who When Where Why How Not No Yes Oh O So Then Now Well Let As For With To
Of By From Is Was Be Are Were Have Had Do Did Nor Yet Thus Upon Thou Thee Thy Ye Why Nay Aye Ay Enter Exit
Exeunt All One Two Some Such Very Mr Mrs Miss Sir Lady Il Lo La Le Gli Un Una Uno E Ed Ma Che Non Si Per Con
Di Da Del Della In Nel Nella Questo Questa Quello Quella Poi Ecco Come Quando Dove Perché Anche Ah Chapter
Volume Book Part Capitolo Libro Parte Canto Act Scene Actus Scena Record""".split()
)
CALENDAR = set(
    """Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June
July August September October November December Lunedì Martedì Mercoledì Giovedì Venerdì Sabato Domenica Gennaio
Febbraio Marzo Aprile Maggio Giugno Luglio Agosto Settembre Ottobre Novembre Dicembre""".split()
)


HONORIFICS = set(re.findall(r"[A-Za-z]+", HONORIFIC))
CONNECTORS = {"of", "de", "di", "da", "del", "della", "dei", "degli", "la", "le", "van", "von", "du"}


def _clean_entity(raw: str) -> str | None:
    tokens = re.sub(r"['’]s$", "", raw).split()
    while tokens and tokens[0].strip(".") in STOP_CAPS and tokens[0].strip(".") not in HONORIFICS:
        tokens = tokens[1:]
    while tokens and (tokens[-1] in STOP_CAPS or tokens[-1] in CONNECTORS):
        tokens = tokens[:-1]
    if not tokens or all(t.strip(".") in HONORIFICS for t in tokens):
        return None
    name = " ".join(tokens)
    return None if len(name) < 3 else name


def chunk_entities(text: str) -> list[tuple[str, bool]]:
    """(entity, ambiguous) per capitalized mention. A single capitalized word at the start
    of a sentence is ambiguous: it may just be an ordinary word."""
    out = []
    for m in ENTITY_RE.finditer(text):
        name = _clean_entity(m.group(1))
        if not name:
            continue
        at_start = bool(SENT_START.search(text[max(0, m.start() - 6) : m.start()])) and m.group(1).startswith(name)
        out.append((name, at_start and " " not in name))
    return out


def section_map(sections: list[Section], chunks: list[Chunk], vectors: np.ndarray, lang: str) -> list[dict]:
    by_section: dict[int, list[int]] = defaultdict(list)
    for i, c in enumerate(chunks):
        by_section[c.section_idx].append(i)
    out = []
    for s in sections:
        idxs = by_section.get(s.idx, [])
        if not idxs:
            continue
        text = "\n\n".join(chunks[i].text for i in idxs)
        kws = keywords(text, lang, top=6) if len(text) > 200 else []
        centroid = vectors[idxs].mean(axis=0)
        central = idxs[int(np.argmax(vectors[idxs] @ centroid))]
        out.append(
            {
                "idx": s.idx,
                "title": s.title,
                "level": s.level,
                "chunks": [chunks[idxs[0]].chunk_idx, chunks[idxs[-1]].chunk_idx],
                "chars": len(text),
                "keywords": kws,
                "gist": _gist(chunks[central].text, kws),
                "gist_id": f"{chunks[central].doc_id}#{chunks[central].chunk_idx:04d}",
            }
        )
    return out


def _gist(text: str, kws: list[str]) -> str:
    sentences = [s for s in split_sentences(text.replace("\n", " ")) if 40 < len(s) < 320] or [text[:280]]
    terms = [k.lower() for k in kws]
    return max(sentences, key=lambda s: sum(t in s.lower() for t in terms) + min(len(s), 200) / 400)


def doc_keywords(section_maps: list[dict], top: int = 15) -> list[str]:
    score: Counter = Counter()
    for s in section_maps:
        for rank, kw in enumerate(s["keywords"]):
            score[kw.lower()] += 1 / (rank + 1)
    return [k for k, _ in score.most_common(top)]


def build_entity_index(chunk_ids: list[str], texts: list[str], min_count: int = 4) -> dict:
    mentions: Counter = Counter()
    starts: Counter = Counter()
    lowercase: Counter = Counter()
    per_chunk: dict[str, set] = {}
    for cid, text in zip(chunk_ids, texts, strict=True):
        found = chunk_entities(text)
        for name, at_start in found:
            mentions[name] += 1
            starts[name] += at_start
        per_chunk[cid] = {n for n, _ in found}
        lowercase.update(w for w in re.findall(r"\b[a-zà-ÿ]+\b", text))
    # a single word that is mostly written lowercase is an ordinary word (Time, Nature, March...)
    keep = {
        n
        for n, c in mentions.items()
        if c >= min_count and starts[n] / c <= 0.5 and (" " in n or lowercase[n.lower()] < c)
    }
    entities: dict[str, dict] = {}
    chunk_ents: dict[str, list[str]] = {}
    for cid, names in per_chunk.items():
        names = sorted(names & keep)
        if not names:
            continue
        chunk_ents[cid] = names
        doc = cid.split("#")[0]
        for n in names:
            e = entities.setdefault(n, {"n": mentions[n], "docs": Counter(), "chunks": []})
            e["docs"][doc] += 1
            e["chunks"].append(cid)
    # days and months are noise unless they behave like a character (Chesterton's Sunday, Thursday)
    for name in [n for n in entities if n in CALENDAR]:
        e = entities[name]
        if not (e["n"] >= 30 and max(e["docs"].values()) >= 0.7 * sum(e["docs"].values())):
            del entities[name]
    dropped = CALENDAR - entities.keys()
    for cid in list(chunk_ents):
        chunk_ents[cid] = [n for n in chunk_ents[cid] if n not in dropped]
        if not chunk_ents[cid]:
            del chunk_ents[cid]
    for e in entities.values():
        e["docs"] = dict(e["docs"].most_common())
    return {"entities": entities, "chunk_entities": chunk_ents}


def related(index: dict, name: str, top: int = 12) -> list[dict]:
    entities, chunk_ents = index["entities"], index["chunk_entities"]
    if name not in entities:
        return []
    n_chunks = max(1, len(chunk_ents))
    df_a = len(entities[name]["chunks"])
    together: dict[str, list[str]] = defaultdict(list)
    for cid in entities[name]["chunks"]:
        for other in chunk_ents.get(cid, []):
            if other != name:
                together[other].append(cid)
    scored = []
    for other, cids in together.items():
        df_b = len(entities[other]["chunks"])
        c = len(cids)
        pmi = math.log(c * n_chunks / (df_a * df_b))
        scored.append((c * max(pmi, 0.01), other, cids))
    scored.sort(reverse=True)
    return [
        {"entity": o, "together": len(cids), "mentions": entities[o]["n"], "evidence": cids[:3]}
        for _, o, cids in scored[:top]
    ]
