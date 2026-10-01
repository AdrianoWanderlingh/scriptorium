"""Stylometric "style card" for an author or a book: measurable voice traits plus the words
and sentence openings that distinguish it from the rest of the library. Paired with
retrieved exemplar passages, it lets any LLM write in that voice without fine-tuning."""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter

from .structure import split_sentences
from .textstats import content_counts, words

PUNCT = {"comma": ",", "semicolon": ";", "colon": ":", "dash": "—|--", "exclamation": "!",
         "question": r"\?", "parenthesis": r"\("}
QUOTED = re.compile(r"[\"“][^\"”]{2,2000}[\"”]")


def _mattr(tokens: list[str], window: int = 500) -> float:
    if len(tokens) <= window:
        return len(set(tokens)) / max(1, len(tokens))
    step = max(1, (len(tokens) - window) // 50)
    vals = [len(set(tokens[i:i + window])) / window for i in range(0, len(tokens) - window, step)]
    return statistics.mean(vals)


def _log_odds(target: Counter, background: Counter, top: int) -> list[str]:
    """Monroe et al. log-odds ratio with informative Dirichlet prior."""
    prior = background + target
    a0, n_t, n_b = sum(prior.values()), sum(target.values()), sum(background.values())
    scored = []
    for w, y_t in target.items():
        if y_t < 5:
            continue
        a_w, y_b = prior[w], background[w]
        delta = (math.log((y_t + a_w) / (n_t + a0 - y_t - a_w))
                 - math.log((y_b + a_w) / (n_b + a0 - y_b - a_w)))
        var = 1 / (y_t + a_w) + 1 / (y_b + a_w)
        scored.append((delta / math.sqrt(var), w))
    scored.sort(reverse=True)
    return [w for _, w in scored[:top]]


def style_card(texts: list[str], background_texts: list[str], lang: str) -> dict:
    text = "\n\n".join(texts)
    sentences = [s for s in split_sentences(re.sub(r"\s*\n\s*", " ", text)) if len(s) > 1]
    lengths = [len(words(s)) for s in sentences if words(s)]
    tokens = [w.lower() for w in words(text)]
    n_words = max(1, len(tokens))
    punct = {name: round(len(re.findall(p, text)) * 1000 / n_words, 1) for name, p in PUNCT.items()}
    quoted_chars = sum(len(m.group(0)) for m in QUOTED.finditer(text))
    openers = Counter(" ".join(w.lower() for w in words(s)[:2]) for s in sentences if len(words(s)) >= 4)
    target = content_counts(text, lang)
    capitalized = Counter(w.lower() for w in words(text) if w[0].isupper())
    for w in [w for w, n in target.items() if capitalized[w] > 0.5 * n]:
        del target[w]  # proper names say nothing about voice
    background = Counter()
    for t in background_texts:
        background.update(content_counts(t, lang))
    return {
        "words": n_words,
        "sentence_length": {"mean": round(statistics.mean(lengths), 1) if lengths else 0,
                            "median": statistics.median(lengths) if lengths else 0,
                            "p90": sorted(lengths)[int(len(lengths) * 0.9)] if lengths else 0},
        "word_length": round(statistics.mean(len(w) for w in tokens), 2) if tokens else 0,
        "lexical_variety_mattr500": round(_mattr(tokens), 3),
        "punctuation_per_1000_words": punct,
        "dialogue_share": round(quoted_chars / max(1, len(text)), 2),
        "distinctive_words": _log_odds(target, background, 30) if background else [w for w, _ in target.most_common(30)],
        "typical_sentence_openings": [o for o, _ in openers.most_common(12)],
    }


def describe(card: dict) -> list[str]:
    """Plain-language writing guidance derived from the numbers."""
    tips = []
    sl = card["sentence_length"]["mean"]
    tips.append(f"Average sentence ≈ {sl:.0f} words (90% under {card['sentence_length']['p90']}): "
                + ("long, periodic sentences with subordinate clauses." if sl > 25 else
                   "medium-length sentences." if sl > 15 else "short, direct sentences."))
    p = card["punctuation_per_1000_words"]
    if p["semicolon"] > 8:
        tips.append("Heavy use of semicolons to chain clauses.")
    if p["dash"] > 5:
        tips.append("Frequent dashes for asides and interruptions.")
    if p["exclamation"] > 5:
        tips.append("Emphatic, exclamatory register.")
    if p["question"] > 6:
        tips.append("Many (rhetorical) questions.")
    if card["dialogue_share"] > 0.3:
        tips.append("Dialogue-driven: a large share of the text is direct speech.")
    elif card["dialogue_share"] < 0.08:
        tips.append("Mostly narration or exposition, little direct speech.")
    tips.append("Lexical variety (MATTR) " + str(card["lexical_variety_mattr500"])
                + (": rich, varied vocabulary." if card["lexical_variety_mattr500"] > 0.55 else
                   ": deliberately repetitive / plain vocabulary." if card["lexical_variety_mattr500"] < 0.45 else "."))
    return tips
