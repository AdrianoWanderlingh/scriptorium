# Query ufficiale n. 1 — "L'errore di giudizio sul carattere"

**Domanda posta al sistema (libreria `classici-inglesi`)**

> Come trattano Jane Austen e Chesterton (Father Brown) l'errore di giudizio sul carattere altrui:
> chi si sbaglia, perché, e come se ne accorge? Voglio citazioni esatte con la loro collocazione,
> e poi un breve paragrafo nuovo, nello stile di Austen, sullo stesso tema.

## Come ha lavorato l'agente (7 chiamate, ~5.500 token di contesto)

| Passo | Chiamata | Esito |
|---|---|---|
| 1 | `search` (it + 2 riformulazioni inglesi), `--author Austen --per-doc 3` | passi pertinenti da tutti e tre i romanzi |
| 2 | `outline chesterton-the-wisdom-of-father-brown` | mappa dei 12 racconti, individuati "The Man in the Passage" e "The Absence of Mr Glass" |
| 3 | `search` mirata su Father Brown | la scena dello specchio, §IV |
| 4 | `search` **solo in italiano** su Emma | trovato al primo posto il celebre passo della "insufferable vanity" (score 2.30) |
| 5 | `read` ×3 | verifica testuale dei passi citati |
| 6 | `style --author Austen --theme ...` | scheda di stile + esempi |
| 7 | `note` | sintesi salvata nella wiki della libreria |

I cinque libri coinvolti contano circa 440.000 parole (≈ 600.000 token): l'agente ne ha letto meno dell'1%,
scelto dal sistema, e ogni affermazione è ancorata a un id verificabile.

## Risposta

**Austen: l'errore nasce dalle maniere, ed è un difetto morale prima che intellettuale.**
In *Sense and Sensibility* Elinor formula la teoria: si cade in "a total misapprehension of character…
guided by what they say of themselves, and very frequently by what other people say of them, without
giving oneself time to deliberate and judge" (cap. 17) [austen-sense-and-sensibility#0144].
In *Persuasion* la teoria diventa esito narrativo: Lady Russell deve ammettere di essere stata
"unfairly influenced by appearances in each" — ha diffidato dei modi di Wentworth perché non
corrispondevano alle sue idee, e si è fidata di quelli di Mr Elliot per la loro "propriety and
correctness" (cap. 24) [austen-persuasion#0413]. Anne lo aveva intuito prima: "she could not be
satisfied that she really knew his character" (cap. 17) [austen-persuasion#0262].
In *Emma* l'errore è il motore dell'intero romanzo, annunciato fin dal primo capitolo ("a disposition to
think a little too well of herself") [austen-emma#0001] e confessato nel momento del riconoscimento:
"With insufferable vanity had she believed herself in the secret of every body's feelings… She was
proved to have been universally mistaken" (Vol. III, cap. XI) [austen-emma#0664].

**Chesterton: l'errore nasce dal punto di vista, e la cura è l'umiltà.**
In "The Man in the Passage" tre "capable and respectable men" descrivono la stessa figura come "a woman,
… a beast, … a devil" [chesterton-the-wisdom-of-father-brown#0120]. Era uno specchio: ognuno ha visto
sé stesso senza riconoscersi. Il giudice chiede perché solo il prete abbia riconosciuto la propria
figura, e Brown risponde: "I don't know unless it's because I don't look at it so often"
[chesterton-the-wisdom-of-father-brown#0122]. In "The Absence of Mr Glass" lo stesso schema colpisce
la scienza: il criminologo Dr Hood costruisce una ricostruzione brillante attorno a un uomo che non
esiste, e Brown lo smonta con un elogio ironico: "Dr Hood, you are a great poet! You have called an
uncreated being out of the void… there was never anybody so absent as Mr Glass"
[chesterton-the-wisdom-of-father-brown#0021].

**Il collegamento.** Per Austen si giudica male perché ci si fida dei modi e della propria
"penetration": il rimedio è il tempo e l'auto-esame. Per Chesterton si giudica male perché ci si
guarda troppo: il rimedio è non guardarsi. In entrambi chi sbaglia è la persona più sicura di sé
(Emma, Lady Russell, Sir Wilson Seymour, Dr Hood), e chi vede giusto è una figura defilata (Anne
Elliot, Father Brown).

**Paragrafo nuovo nello stile di Austen** (pastiche guidato dalla scheda di stile: frasi di circa 24
parole, punti e virgola, trattini, lessico di "feelings / opinion / acquaintance"; nessuna frase copiata):

> Mrs. Hartley had long prided herself on reading a countenance as readily as a letter; and it was
> therefore no small mortification to discover, within the compass of a single evening, that she had
> read two of them entirely backwards. The gentleman whose reserve she had called pride proved only to
> be shy;—the gentleman whose ease she had called good principle proved only to be practised. She sat a
> long while with her feelings, and could find nothing to say in her own defence, but that she had been
> very much pleased, and very little attentive; and she resolved—with a sincerity which, she was sure,
> would last at least until the next ball—to think a great deal less of her own penetration, and a great
> deal more of other people's conduct.

## Perché un motore di ricerca o un LLM generico non bastano

- **Citazioni verificabili.** Un LLM generico ricorda a memoria le frasi famose (la "insufferable
  vanity"), ma tende a inventare o a parafrasare quelle meno note, come Elinor al cap. 17 o il giudice
  in Father Brown, e non sa dare il capitolo o il passo. Qui ogni citazione ha un id che si può riaprire.
- **Ricerca su testi tuoi.** Il web restituisce saggi *su* questi libri, non il testo della *tua*
  edizione. Con libri rari, scritti tuoi o materiale non digitalizzato pubblicamente il web non ha
  proprio nulla da restituire.
- **Collegamenti tra fonti.** L'accostamento Lady Russell / Sir Wilson Seymour è nato dall'aver
  messo insieme nella stessa sessione passi di due autori diversi.
- **Lingua.** La domanda è in italiano e i libri in inglese: il passo di Emma è stato trovato con una
  query solo italiana.
- **Effetto cumulativo.** La sintesi è salvata come nota (`note-austen-e-chesterton-l-errore-di-giudizio-sul-carattere`)
  ed è ricercabile: la prossima volta l'agente parte da lì.
