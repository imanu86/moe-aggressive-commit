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

## ATTENZIONE A COME SI LEGGE QUESTA TABELLA

**La colonna «testa gratis» non è una previsione: è un limite superiore.**
Assume `c_testa = 0`, cioè un proponente a costo nullo. **Non esiste, e non è
mai stato agganciato niente del genere**: l'unico proponente mai girato è il
**drafter DSpark**, un modello *separato* di 3 strati e 6.831 MiB su CPU
(`general.name = "Dspark Flash Drafter"`). Il modello DS4 dichiara
`deepseek4.nextn_predict_layers = 1` nei metadati ma carica `n_layer = 43` e
`n_layer_all = 43`: **nessuno strato di testa in più**. La testa dentro il
grafo è il pezzo da costruire, e nel cantiere non ne esiste una riga.

I 15,39 della riga h=56,5% sono **doppiamente ipotetici**: proponente gratis
*e* un tasso di colpi misurato a **una** posizione, che `TESTA_METRICA.md`
dichiara non tenibile a due (unione delle route consecutive ~446 contro 380
slot). Quella riga è un tetto irraggiungibile, non un bersaglio.

## Il modello è validato DUE volte — e il contatore del drafter è una trappola

**Primo punto** (regime del cantiere testa): `c_testa` ≈ 105 ms/posizione,
h=17,3%, p1=0,87 → previsti **6,83 t/s** contro **5,00-7,53** misurati.

**Secondo punto** (braccio catena `ovl_k2_DIO`, regime diverso), che è anche il
più stringente perché tutti i termini sono misurati nello stesso run:

```
  misurato:   255,2 ms/passo   (152,9 s / 599 passi)   colpi h = 39,7%
  modello:    passo(0,397) = 69 + 120,7·0,603 = 141,8 ms
  differenza: 113,4 ms  ->  e' il costo VERO del drafter
  141,8 + 113,4 = 255,2   contro   255,2 misurati     (0,2% di scarto)
```

**Ma il log dice 18,7 ms.** `dur(b,g,a)` di `common_specu` riporta
11.209 ms su 599 chiamate = 18,7 ms/chiamata, cioè **il 7,3% del tempo di
generazione** — e sembra dire che il drafter sia quasi gratis. Non lo è:
`dur(g)` cronometra solo la *generazione* della bozza, non `process()`, che
inietta i token accettati nella KV della bozza con due forward CPU e **non ha
cronometro**. **Il contatore vede il 16% del costo reale.**

Chiunque prezzi un proponente guardando `dur(g)` sbaglia di **sei volte**. È
il ventiseiesimo strumento assente della campagna, ed è ancora aperto.

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

## ⛔ LA SEZIONE QUI SOTTO È RITIRATA — IL BRACCIO ERA DEGENERATO

*7/8/2026, ore 10:45. Il controllo del testo, chiesto dall'arbitro e costato
zero, ha invalidato il braccio `ovl_k2_CRONO` su cui poggia tutto il paragrafo
successivo.*

```
  OVERLAP (CRONO)   accettazione 0,950   testo: 36 righe /  6 UNICHE   <- DEGENERATO
  DSPARK  (BINDSP)  accettazione 0,738   testo: 52 righe / 52 uniche   <- sano
```

Il testo di `CRONO` ripete la stessa riga fino alla fine. **Accettazione
altissima su testo degenerato è la firma già a registro**: un flusso in loop è
banale da indovinare. Quindi cadono, tutti:

- i **21,8 ms** del proponente (misurati su un run corrotto);
- «**dentro budget di 2,2×**» e la conclusione «**costruire la testa
  risolve un problema che non esiste**»;
- l'**11× su `process()`**, perché il confronto metteva un run **degenerato**
  contro uno **sano**: la differenza non è attribuibile al binario.

**E il difetto SI RIPRODUCE**: `OVL_T1_GRIGLIA_NON_RIPRODUCE` poggiava su *un*
braccio sano. I punti ora sono tre — DIO sano, GRIGLIA sano, **CRONO
degenerato** — cioè **uno su tre**. L'intermittenza è confermata, e la guardia
a batch 1 come *scelta di progetto* si rafforza.

**L'errore di metodo, mio**: ho applicato il cancello del testo al braccio dove
**cercavo** il difetto e non a quello dove **misuravo altro**. Un cancello di
validità non è condizionato allo scopo del braccio.

**Regola operativa**: nessun numero da un braccio catena a batch 2 è adottabile
senza il conteggio **righe/uniche nello stesso messaggio** in cui il numero
viene riportato. Riferimenti: sano 43/43 e 43/49; degenere 41/11, 5 righe con
coda `'code','code'`, e ora **36/6**.

Resta valido solo ciò che viene dal braccio `DIO`, il cui testo era sano.

## ⚠ [RITIRATO] RIBALTATO DAL CRONOMETRO: IL PROPONENTE NON È IL PROBLEMA

*7/8/2026, ore 10:30. Aggiunto `common_time_meas` su `process()`
(`speculative.cpp:2564` era l'unica delle quattro fasi senza cronometro) e la
ripartizione **per ciclo**, non per chiamata. Braccio `ovl_k2_CRONO`, stessa
config di `ovl_k2_DIO`.*

```
  ms per passo (misurato)        243,0
    proponente TOTALE            21,8   <- i QUATTRO cronometri, non una sottrazione
       gen                       18,2
       process                    3,6   (646 chiamate / 602 cicli = 1,07)
    passo del BERSAGLIO         221,2
    modello passo(h=39,7%)      141,8
    NON ATTRIBUITO               79,5   <- lato BERSAGLIO
```

**Il drafter costa 21,8 ms contro un budget di 47,1: è DENTRO, di 2,2×.**

Quindi va ritirato quanto scritto sopra («DSpark 2,4× fuori budget»): quel
numero nasceva dall'attribuire al proponente i 113,4 ms ottenuti **per
sottrazione** dal modello. I cronometri dicono che il proponente ne usa 21,8, e
che gli altri ~92 stanno **altrove**. Attribuire per differenza è la stessa
famiglia di errore che questa campagna paga da due giorni.

**Conseguenza sulla decisione**: costruire una testa per abbattere il costo del
proponente **risolverebbe un problema che non esiste**. L'accuratezza era già
sopra soglia (p1 0,87 contro 0,35) e ora anche il costo è dentro budget. Il
collo sta nel **passo del bersaglio**, che a `h=39,7%` costa 221,2 ms contro i
141,8 del modello.

**Sospetto immediato, non misurato**: i bracci catena girano con **`ASYNC=0`**,
cioè con l'overlap **spento**, mentre la SOTA 9,9 lo ha acceso. La
composizione catena+overlap non è mai stata misurata. È **un braccio**.

**E `process` non è chiamata due volte per ciclo**: 646/602 = **1,07** a
`n_max=1`. Il rapporto 1,74-1,85 osservato sui bracci `n_max=3` è una proprietà
del regime a più posizioni, non una struttura del meccanismo.

## Il numero (superato) ottenuto per sottrazione

Al tasso di colpi reale del braccio catena (**h = 39,7%**, non un'ipotesi):

```
  budget per c_testa   =  101 × 1,87  −  141,8  =  47,1 ms
  DSpark reale         =  113,4 ms                 ->  2,4× FUORI budget
```

Non c'è margine di interpretazione: **il DSpark è fuori di 2,4 volte al suo
stesso tasso di colpi**, e la parte che lo affonda (i 95 ms di `process()`) è
proprio quella che nessun contatore misura.

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
