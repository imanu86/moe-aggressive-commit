# Il rango non è decorazione: per frequenza il gate PEGGIORA

4 agosto 2026, mattina. L'ablazione che mancava, su NeuraForge a 8000 token —
la corsa lunga che non avevamo mai fatto.

## La domanda

Era dimostrato che **bloccare** aiuta, non che aiuti bloccare **per massa**. Se
il blocco per sola frequenza di bussata avesse reso quanto quello per massa,
tutto il lavoro sul rango sarebbe stato decorazione, e andava detto.

## Il dato

Tre bracci, ctx 10000, prompt NeuraForge, `TOPK=1200`, controllo messo **in
mezzo** perché i due bracci col blocco vedessero cache rispettivamente fredda e
calda. Tutti hanno prodotto esattamente 5.822 token.

```
                  ms/token   t/s    mediana   min    <4 t/s  <2 t/s   p10
M1  massa (2^-r)   165,46    6,04    6,84    1,12    11,8%   2,7%    3,62
M0  controllo      177,73    5,63    6,65    0,38    19,4%   4,5%    2,62
M2  frequenza      195,67    5,11    6,49    0,26    24,8%   3,9%    2,63
```

**Per massa: +7,3% sul controllo. Per frequenza: −9,2%.**

Bloccare per sola frequenza è **peggio che non bloccare affatto**. I diciotto
punti fra i due criteri sono l'informazione del rango che fa lavoro: è la
differenza fra una politica che aiuta e una che danneggia.

Il meccanismo è quello previsto dall'analisi: la frequenza tiene in RAM
l'esperto bussato spesso ma sempre da sesto — che occupa posto senza portare
uscita — e sfratta quello scelto di rado ma da primo. Lo si vedeva nei due casi
limite della mappa (strato 18 esperto 74: 639 bussate, mai primo; strato 2
esperto 29: 159 bussate, il 90,6% da primo), e ora si vede nel tempo.

## Il cancello di identità regge

```
M1 massa        22.918 caratteri   sha 26639992d995d473
M0 controllo    22.918 caratteri   sha 26639992d995d473
M2 frequenza    22.918 caratteri   sha 26639992d995d473
```

Uscita identica bit per bit fra i tre. Il gate non nega esperti al router:
impedisce solo lo sfratto delle pagine. Nessuna delle differenze di velocità
viene da un modello che calcola meno.

## Ma la mappa invecchia

A 1500 token il blocco per massa dava **min 2,87 e zero campioni sotto i 2**.
A 8000 dà **min 1,12 e il 2,7% sotto i 2**.

La protezione si assottiglia sulla corsa lunga. È il difetto atteso: la massa
si accumula da inizio corsa e **non dimentica mai**, quindi a fine corsa la
mappa descrive una fase che non c'è più. È l'argomento diretto per il
decadimento, che oggi non c'è.

Resta comunque il miglior decimo percentile dei tre — 3,62 contro 2,62 e 2,63,
cioè il 38% in più sul caso sfavorevole.

## Quanto fidarsi

Un run per braccio. La varianza fra controlli misurata nelle sessioni
precedenti è ±4%.

```
massa contro frequenza    18 punti    ben fuori dal rumore: SOLIDO
massa contro controllo   7,3 punti    sopra il rumore, ma n=1: PROBABILE
```

Anomalia annotata: il prefill di M2 è stato di 2.583 ms/token contro i ~400
degli altri due (191 secondi invece di 30). Non tocca il confronto, che usa
l'`eval time` misurato a parte, ma non ha spiegazione.

## Due etichette da correggere

I «20,84 GiB residenti» stampati dalla politica sono **cumulativi** — i byte
bloccati sommati sulle 58 passate. Il residente vero è `K × 6,75 MB = 8,1 GB`.

E a 8000 token compaiono **fallimenti veri** di `VirtualLock`: 47 su 3.190
(1,5%) per la massa, 72 su 3.248 per la frequenza. A 1500 token erano zero: la
rotazione più lunga arriva a toccare il limite della quota, che viene alzata
una volta sola all'inizio.
