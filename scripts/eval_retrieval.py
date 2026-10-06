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

# Held out: written after the first evaluation and never used to tune anything.
TEST = [
    (
        "Il gatto svanisce lentamente finché resta sospeso solo il suo sorriso",
        "the cat fades away until only its smile is left hanging in the air",
        "grin without a cat",
    ),
    (
        "Il principe tiene in mano il teschio del buffone che lo portava in spalla da bambino",
        "holding the skull of the jester who carried him around as a child",
        "Alas poore Yorick",
    ),
    (
        "Il poeta lancia il suo urlo selvaggio sopra i tetti del mondo",
        "the poet sends his wild untamable shout across the rooftops of the earth",
        "barbaric yawp",
    ),
    (
        "Il figlio disprezza la madre che si è risposata poche settimane dopo il funerale del padre",
        "the son scorns his mother for remarrying within weeks of his father's burial",
        "Frailty, thy name",
    ),
    (
        "Gli angeli caduti convocano un consiglio nella loro capitale infernale",
        "the fallen angels are summoned to a council in their infernal capital",
        "At Pandemonium",
    ),
    (
        "Il poeta chiede all'agnellino chi gli abbia dato la vita",
        "the poet asks the young sheep who its maker is",
        "Little Lamb, who made thee",
    ),
    (
        "La gallina trova un chicco e nessun animale della fattoria vuole aiutarla a seminarlo",
        "the hen finds a seed of grain and none of the farm animals will help her sow it",
        "Who will plant this wheat",
    ),
    (
        "L'unico sopravvissuto resta a galla aggrappato alla cassa da morto del suo amico",
        "the lone survivor stays afloat on a casket turned into a float",
        "coffin life-buoy",
    ),
    (
        "Knightley rimprovera Emma per aver umiliato la povera zitella durante la gita",
        "Knightley scolds Emma for humiliating the poor old spinster at the picnic",
        "badly done, indeed",
    ),
    (
        "Un giovane scozzese rompe una vetrina col bastone per un insulto alla Madonna",
        "a young Highlander shatters a newsagent's display glass with his cane over an insult to the Virgin",
        "smashed the shop window",
    ),
    (
        "Uno scienziato ateo sorvola il mondo su una nave volante insieme a un vecchio monaco",
        "an atheist scientist flies through the sky in an airship with an old monk",
        "flying ship of Professor Lucifer",
    ),
    (
        "Un nuovo arrivato sostiene che la vera poesia sta dalla parte dell'ordine, contro il poeta anarchico",
        "a newcomer argues that true poetry is on the side of rules and propriety, against the rebel bard",
        "a poet of order",
    ),
    (
        "Un quartiere bohémien di Londra con edifici rossi che sembrano una nuvola al crepuscolo",
        "a bohemian district of London whose crimson buildings look like an evening cloud",
        "suburb of Saffron Park",
    ),
    (
        "Alla merenda dei matti viene posto un indovinello senza risposta su un uccello nero e una scrivania",
        "at the mad tea party, an answerless riddle about a black bird and a desk is asked",
        "raven like a writing-desk",
    ),
    (
        "Il capitano dice che ogni cosa visibile è una maschera di cartone da sfondare",
        "everything visible is only a cardboard disguise that must be struck through",
        "pasteboard masks",
    ),
    (
        "Marianne trova ridicolo che un uomo che si lamenta dei reumatismi possa ancora innamorarsi",
        "Marianne thinks a man who complains about rheumatism is too old and frail for love",
        "flannel waistcoat",
    ),
    (
        "Emma interpreta l'indovinello in versi del pastore come una proposta di matrimonio per Harriet",
        "Emma reads the clergyman's word puzzle in verse as a marriage proposal for her friend",
        "a very good hint",
    ),
    (
        "Un culto vudù di adoratori del diavolo diffuso in America tra meticci che sembrano bianchi",
        "a voodoo sect of devil-worship spreading in America among people of mixed race",
        "God of the Gongs",
    ),
    (
        "Un giornalista vuole scrivere uno scandalo sulla leggenda di famiglia di un vecchio duca conservatore",
        "a journalist plans an exposé on the family curse of an old Tory nobleman",
        "Devil's Ear of Eyre",
    ),
    (
        "Al primo inseguimento compare l'equipaggio nascosto guidato da un vecchio orientale col turbante",
        "a hidden crew led by an old Parsee in a turban appears for the first lowering of the boats",
        "All ready there, Fedallah",
    ),
    (
        "Il narratore è inorridito di dover dividere il letto della locanda con un selvaggio tatuato",
        "the narrator is horrified to share a bed at the inn with a tattooed savage",
        "infernal harpooneer was a cannibal",
    ),
    (
        "Una vecchia signora in una valle ha un giardino curatissimo senza un filo d'erba cattiva",
        "an elderly woman in a valley keeps a tidy cottage garden with no weeds at all",
        "pleasant valley of Ashton",
    ),
    (
        "Descrizione di una cittadina di mare con la passeggiata sul molo e le cabine da bagno",
        "a seaside town described with its harbour walkway and bathing machines",
        "the walk to the Cobb",
    ),
    (
        "Il visone ride all'idea che il grosso orso possa annegare nel ruscello",
        "the mink laughs at the thought of the huge bear drowning in the stream",
        "Buster Bear getting",
    ),
    (
        "Il segretario del consiglio anarchico, temuto per il suo ghigno storto",
        "the anarchist committee's secretary whose crooked grin is dreaded",
        "twisted smile was regarded",
    ),
    (
        "Un regalo misterioso, uno strumento musicale, arriva a casa della zitella chiacchierona",
        "a mysterious gift of a musical instrument arrives at the chatty old maid's house",
        "large-sized square pianoforte",
    ),
    (
        "Una ragazza falsa elogia la dolcezza della padrona di casa e Marianne si rifiuta di risponderle",
        "an insincere young woman praises their hostess's sweetness and Marianne refuses to agree",
        "What a sweet woman Lady Middleton is",
    ),
    (
        "Il direttore del giornale ateo perde la pazienza col suo rivale credente",
        "the editor of the atheist paper loses patience with his devout rival",
        "enlighten my pagan darkness",
    ),
]

# Exact quotations (what a user pastes to locate a passage); query used as is in every config.
EXACT = [
    ("To morrow, and to morrow, and to morrow", "walking Shadow"),
    ("Alas poore Yorick", "Alas poore Yorick"),
    ("All visible objects, man, are but as pasteboard masks", "pasteboard masks"),
    ("I sound my barbaric yawp over the roofs of the world", "barbaric yawp"),
    ("Better to reign in Hell than serve in Heaven", "Better to reign in Hell"),
    ("Spanish ounce of gold", "ounce of gold"),
]

SETS = {"dev": GOLD, "test": TEST, "exact": [(q, q, p) for q, p in EXACT]}

CONFIGS = [
    ("it · vector only", dict(mode="vector", rerank=False), "it"),
    ("it · default (hybrid + rerank)", dict(), "it"),
    ("it + en (--also) · default", dict(), "it+en"),
    ("en · vector only", dict(mode="vector", rerank=False), "en"),
    ("en · default", dict(), "en"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).lower()


def main() -> None:
    lib = Library(sys.argv[1] if len(sys.argv) > 1 else "classici-inglesi")
    rows = lib.table().search().where("kind = 'book'").select(["id", "text"]).limit(None).to_list()
    gold = {}
    for items in SETS.values():
        for _, _, phrase in items:
            ids = {r["id"] for r in rows if norm(phrase) in norm(r["text"])}
            if not ids:
                raise SystemExit(f"gold phrase not found in the index: {phrase!r}")
            gold[phrase] = ids

    print(
        f"# Retrieval evaluation — {lib.name}\n\nEmbedder `{lib.indexed_model}`. Known-answer questions; "
        "gold = chunk(s) containing a distinctive phrase that the question does not use. `dev` "
        f"({len(GOLD)}) guided the design, `test` ({len(TEST)}) is held out, `exact` ({len(EXACT)}) "
        "are verbatim quotations.\n"
    )
    misses: dict[str, list[str]] = {}
    for set_name, items in SETS.items():
        print(f"\n## {set_name}\n")
        print("| configuration | hit@1 | hit@5 | MRR@10 | s/query |\n|---|---|---|---|---|")
        for label, kwargs, lang in CONFIGS if set_name != "exact" else [("as typed · default", {}, "en")]:
            h1 = h5 = mrr = 0.0
            t0 = time.time()
            for it, en, phrase in items:
                query, also = {"it": (it, None), "en": (en, None), "it+en": (it, [en])}[lang]
                hits = [h["id"] for h in lib.search(query, k=10, also=also, **kwargs)]
                rank = next((i for i, h in enumerate(hits, 1) if h in gold[phrase]), None)
                h1 += rank == 1
                h5 += rank is not None and rank <= 5
                mrr += 1 / rank if rank else 0
                if not rank or rank > 5:
                    misses.setdefault(f"{set_name} · {label}", []).append(f"{phrase} (rank {rank or '>10'})")
            n = len(items)
            print(f"| {label} | {h1 / n:.2f} | {h5 / n:.2f} | {mrr / n:.2f} | {(time.time() - t0) / n:.1f} |")
    print("\n## Misses (not in top 5)\n")
    for label, found in misses.items():
        print(f"- **{label}**: " + "; ".join(found))


if __name__ == "__main__":
    main()
