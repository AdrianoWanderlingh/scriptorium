"""Small language-agnostic text utilities shared by the map and style layers."""

from __future__ import annotations

import re
from collections import Counter

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?")

STOP = {
    "en": set("""a about above after again against all am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most my
myself no nor not now of off on once only or other our ours ourselves out over own same she should so some
such than that the their theirs them themselves then there these they this those through to too under until
up very was we were what when where which while who whom why will with would you your yours yourself shall
thee thou thy thine upon unto hath doth o oh yet let may might must us ye one said mr mrs miss haue
hast art thus doe vs th o'er ere wilt shalt hee shee bee wee mee selfe vpon""".split()),
    "it": set("""a ad al alla alle allo agli ai anche avere aveva che chi ci come con contro cui da dal dalla
dalle dai degli dei del della delle dello di dove e ed egli ella era erano essere fa fra gli ha hanno i il
in io la le lei li lo loro lui ma mi mia mie miei mio ne nei nel nella nelle nello noi non nostro o per
perché più poi quale quando quello questa queste questi questo se sei si sia siamo sono su sua sue sui
sul sulla suo suoi ti tra tu tua tuo un una uno vi voi è così già solo ogni tutto tutti""".split()),
}

YAKE_LANG = {"en": "en", "it": "it"}


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def detect_lang(text: str) -> str:
    sample = [w.lower() for w in words(text[:60000])]
    scores = {lang: sum(1 for w in sample if w in stop) for lang, stop in STOP.items()}
    return max(scores, key=scores.get) if sample else "en"


def content_counts(text: str, lang: str) -> Counter:
    stop = STOP.get(lang, set())
    return Counter(w for w in (x.lower() for x in words(text)) if len(w) > 2 and w not in stop)


def keywords(text: str, lang: str, top: int = 8) -> list[str]:
    import yake

    extractor = yake.KeywordExtractor(lan=YAKE_LANG.get(lang, "en"), n=2, top=top * 3, dedupLim=0.7)
    stop = STOP.get(lang, set())
    seen, out = set(), []
    for phrase, _score in extractor.extract_keywords(text[:15000]):
        key = phrase.lower()
        tokens = key.split()
        if (key in seen or any(key in s or s in key for s in seen) or tokens[0] in stop or tokens[-1] in stop
                or len(key.strip(".")) < 4):
            continue
        seen.add(key)
        out.append(phrase)
        if len(out) >= top:
            break
    return out
