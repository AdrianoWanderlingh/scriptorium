"""Retrieval evaluation on the demo library with known-answer questions.

Each question is paraphrased (Italian and English) without the words of the target passage; the
gold passage is the chunk containing a distinctive phrase. Reports hit@1, hit@5 and MRR@10 per
retrieval configuration, so changes to models or ranking can be measured instead of guessed.

    uv run python scripts/eval_retrieval.py [library] > docs/eval-<date>.md
"""

from __future__ import annotations

import re
import sys
import time

from scriptorium.library import Library

GOLD = [
    # (italian question, english paraphrase, phrase that identifies the gold passage)
    (
        "Il narratore va per mare quando si sente malinconico e cupo",
        "the narrator goes to sea whenever he feels gloomy",
        "Call me Ishmael",
    ),
    (
        "Emma si vergogna di aver preteso di decidere il destino sentimentale di tutti",
        "Emma is ashamed of having tried to arrange everyone's love life",
        "insufferable vanity",
    ),
    (
        "Un uomo confessa di aver cercato una moglie ricca per pagare i debiti",
        "a man admits he courted a rich woman to pay his debts",
        "marrying a woman of fortune",
    ),
    (
        "La figura misteriosa nel corridoio era solo il proprio riflesso",
        "the mysterious figure in the corridor was only one's own reflection",
        "in a mirror?",
    ),
    (
        "La bambina cade a lungo in un pozzo profondissimo",
        "the girl falls slowly down an extremely deep hole",
        "the well was very deep",
    ),
    (
        "La vita è un'ombra che passa, una storia raccontata da un idiota",
        "life is a passing shadow, a tale told by an idiot",
        "walking Shadow",
    ),
    (
        "Il ribelle preferisce comandare all'inferno piuttosto che obbedire in paradiso",
        "the rebel prefers ruling in hell to obeying in paradise",
        "Better to reign in Hell",
    ),
    (
        "Il capitano scrive una lettera: lei gli trafigge l'anima, la ama ancora",
        "the captain writes a letter saying she pierces his soul and he still loves her",
        "You pierce my soul",
    ),
    (
        "Discorso funebre: amici, romani, concittadini, ascoltatemi",
        "funeral oration asking friends and fellow citizens to listen",
        "lend me your ears",
    ),
    ("Il poeta canta e celebra sé stesso", "the poet sings in praise of his own self", "I celebrate myself"),
    (
        "Una belva che arde luminosa nelle foreste della notte",
        "a fierce beast blazing bright in the night forests",
        "burning bright",
    ),
    (
        "Il prete dice allo scienziato che ha inventato dal nulla una persona inesistente",
        "the priest tells the scientist he invented a non-existent person from nothing",
        "uncreated being",
    ),
    (
        "Il principe si chiede se sia meglio vivere o morire",
        "the prince wonders whether it is better to live or to die",
        "To be, or not to be",
    ),
    (
        "Il capitano inchioda una moneta d'oro all'albero per chi avvisterà la balena",
        "the captain nails a gold coin to the mast as a reward for sighting the whale",
        "ounce of gold",
    ),
]

CONFIGS = [
    ("it · vector only", dict(mode="vector", rerank=False), "it"),
    ("it · keywords only (BM25)", dict(mode="fts", rerank=False), "it"),
    ("it · hybrid", dict(rerank=False), "it"),
    ("it · hybrid + rerank", dict(), "it"),
    ("it + en (--also) · hybrid + rerank", dict(), "it+en"),
    ("en · hybrid", dict(rerank=False), "en"),
    ("en · hybrid + rerank", dict(), "en"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).lower()


def main() -> None:
    lib = Library(sys.argv[1] if len(sys.argv) > 1 else "classici-inglesi")
    rows = lib.table().search().where("kind = 'book'").select(["id", "text"]).limit(None).to_list()
    gold = {}
    for _, _, phrase in GOLD:
        ids = {r["id"] for r in rows if norm(phrase) in norm(r["text"])}
        if not ids:
            raise SystemExit(f"gold phrase not found in the index: {phrase!r}")
        gold[phrase] = ids

    print(
        f"# Retrieval evaluation — {lib.name}\n\n{len(GOLD)} known-answer questions; gold = chunk(s) "
        "containing a distinctive phrase that the question does not use.\n"
    )
    print("| configuration | hit@1 | hit@5 | MRR@10 | s/query |\n|---|---|---|---|---|")
    misses: dict[str, list[str]] = {}
    for label, kwargs, lang in CONFIGS:
        h1 = h5 = mrr = 0.0
        t0 = time.time()
        for it, en, phrase in GOLD:
            query, also = {"it": (it, None), "en": (en, None), "it+en": (it, [en])}[lang]
            hits = [h["id"] for h in lib.search(query, k=10, also=also, **kwargs)]
            rank = next((i for i, h in enumerate(hits, 1) if h in gold[phrase]), None)
            h1 += rank == 1
            h5 += rank is not None and rank <= 5
            mrr += 1 / rank if rank else 0
            if not rank or rank > 5:
                misses.setdefault(label, []).append(f"{phrase} (rank {rank or '>10'})")
        n = len(GOLD)
        print(f"| {label} | {h1 / n:.2f} | {h5 / n:.2f} | {mrr / n:.2f} | {(time.time() - t0) / n:.1f} |")
    print("\n## Misses (not in top 5)\n")
    for label, items in misses.items():
        print(f"- **{label}**: " + "; ".join(items))


if __name__ == "__main__":
    main()
