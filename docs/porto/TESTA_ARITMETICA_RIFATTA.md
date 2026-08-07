# ARITMETICA DELLA TESTA, RIFATTA COL p1 GIUSTO

*7/8/2026, dopo il braccio di controllo `TESTA_CTRL_LUNGHEZZA_NON_FLAG`.
Zero macchina: è il modello di `TESTA_METRICA.md` ricalcolato con il p1 della
lunghezza giusta. Sbarra: SOTA **9,9 t/s = 101 ms/token**.*

## Perché va rifatta

Il verdetto di produzione aveva preso **p1 = 0,705**, misurato su run da **300
token**. Ma `TESTA_METRICA.md` prescrive già, scritto:

> «Run ≥ 1.200 token: l'accettazione cresce col run (0,503 a 120 → 0,636 a 300
> → 0,699 a 1500). I verdetti su ≤300 token **sottostimano**; 300 token va bene
> solo per smoke test, **non per verdetti**.»

Quel p1 violava il protocollo del cantiere stesso. Il valore nel regime dei
bracci veri (tutti a 1.200 token) è **0,82-0,89, mediana ≈ 0,87** — misurato,
non stimato: vedi la riga di ledger e [[rbudget-inerte-su-completion]].

Non è una scelta di configurazione da fare: **la regola c'era già.**

## Il conto

Modello invariato (da `TESTA_METRICA.md`), sbarra aggiornata alla SOTA di oggi:

```
  passo(h) = 69 + 120,7·(1−h)  ms          (pavimento 52,7 + calcolo 16,3 + trasporto)
  pareggio: (1 + p1) / (passo(h) + c_testa)  >  1/101
```

| colpi h | passo | t/s con testa GRATIS |  | budget per `c_testa` |  | p1 soglia |
|---|---|---|---|---|---|---|
| | | p1=0,705 | **p1=0,87** | p1=0,705 | **p1=0,87** | |
| **17,3%** (misurato, np=2) | 168,8 ms | 10,10 | **11,08** | 3,4 ms | **20,1 ms** | 0,671 |
| 30% | 153,5 ms | 11,11 | **12,18** | 18,7 ms | **35,4 ms** | 0,520 |
| 44% | 136,6 ms | 12,48 | **13,69** | 35,6 ms | **52,3 ms** | 0,352 |
| 56,5% (misurato a np=1) | 121,5 ms | 14,03 | **15,39** | 50,7 ms | **67,4 ms** | 0,203 |

**Controprova del modello sulla misura**: col DSpark reale (`c_testa` ≈ 105 ms
per posizione, h=17,3%, p1=0,87) il modello prevede **6,83 t/s** contro i
**5,00-7,53** misurati, mediana ~7. Il modello riproduce il fallimento: non è
un conto ottimistico costruito a posteriori.

## Cosa cambia e cosa NO

**NON cambia il segno.** La soglia era già superata a 0,705 (0,705 > 0,671 a
h=17,3%). La catena perdeva — e perde ancora — **per il costo del proponente,
non per l'accuratezza**. I bracci catena misurati giravano già a 1.200 token,
quindi avevano già p1 ≈ 0,87 e perdevano lo stesso: il p1 corretto **non
resuscita la catena**, rimette in sesto le proiezioni.

**CAMBIA il margine, di sei volte.** Il budget per il costo del proponente
passa da **3,4 a 20,1 ms** nel caso pessimistico. Con 3,4 ms non esiste
proponente costruibile: è meno di un risveglio di condvar (~79 µs × 43 strati
≈ 3,4 ms — cioè l'intero budget se ne andava in orchestrazione). Con 20 ms una
testa piccola dentro il grafo GPU ci sta.

**E conferma la direzione già scritta**: «la testa da costruire deve essere
*economica*, prima che *brava*». Il DSpark a 105 ms/posizione è **5× fuori
budget anche col miglior tasso di colpi**. Fuori, definitivamente.

## La leva vera resta la stessa: i COLPI

Il budget va da **20 a 67 ms** passando da h=17,3% a h=56,5%. È la variabile
che apre più spazio di qualunque miglioramento del p1 — e vive nel cantiere
overlap/cache, non qui.

Attenzione al 56,5%: è misurato **a una posizione** (braccio SOTA). Nel regime
a due posizioni l'unione delle route consecutive è ~446 contro 380 slot, e la
misura disponibile lì è **17,3%** su due slot separati. Il vero h della catena
è fra i due e **non è mai stato misurato**: è il braccio che fissa la soglia, e
finché non c'è il numero prudente resta il 17,3%.

## Il seguito, in ordine

1. **Misurare h della catena vera** (un grafo solo, stesso contesto, due
   posizioni consecutive). Fissa il budget fra 20 e 52 ms e decide se vale la
   pena costruire una testa.
2. Solo dopo, e solo se il budget è ≥ ~30 ms: prezzare una testa che stia
   **dentro il grafo GPU** senza orchestrazione host — è lì che il DSpark è
   morto, non nei FLOP (165 M di MAC = 0,02 ms di conti diventati 538 ms).
3. Le tre ipotesi per allargare la finestra CPU dell'overlap (esperto
   condiviso, trasporto anticipato, token diverso) restano **non misurate**:
   vanno prezzate prima di scrivere codice, come questa.

Vedi `TESTA_METRICA.md` (definizione e modello), `LEDGER_RUN.tsv` righe
`TESTA_CTRL_LUNGHEZZA_NON_FLAG` e `OVL_DIO_COPPIA_SOTA`.
