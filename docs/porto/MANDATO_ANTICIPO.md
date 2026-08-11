# MANDATO — l'anticipo di uno strato

> ## ⛔ FALSIFICATO l'11/8, quattro ore dopo essere stato scritto.
>
> Misurato: con la pianificazione **esatta** il prefetch fa 5,97 t/s contro i
> 5,89 di quella **cieca**, e i 11,89 a prefetch spento. La previsione non e'
> il collo — **il costo e' del meccanismo**. Con la previsione perfetta si
> muovono 1.984 GiB contro i 2.048 del cieco: il 3% in meno, dove ci si
> aspetterebbe la meta'.
>
> E l'aritmetica qui sotto usa una banda mai vista su questo cammino: a domanda
> il trasporto viaggia a **5,5 GiB/s**, col prefetch a 9,9, contro i 24,4 del
> DMA che avevo assunto. E' orchestration-bound.
>
> **Dove sono i punti**: nello SFRATTO. Belady sulla traccia vera fa 63,4%
> contro il 40,3% della LRU a 339 slot — **+23 punti a parita' di capienza**.
> E il trasporto **in blocco** (un evento per token invece di 43xW) e' l'unica
> leva che attacca il costo per-operazione.
>
> Dettaglio completo in `LEDGER_11_AGOSTO.md` §4. Il testo che segue resta come
> registro di cosa si pensava e su quali numeri, non come indicazione.

## La tesi, in una riga

Il trasporto non e' caro: e' **in ritardo**. Pagarlo un solo strato prima, sul
motore di copia invece che sugli SM, toglie 34 ms dal percorso critico.

## I numeri che lo reggono, tutti misurati

Profilo Nsight dell'11/8 (finestra di solo decode):

```
  lavoro GPU per ciclo, totale   ~54 ms   su un ciclo vero di 136-145 ms
    34 ms  kern_copia         50,5%   IL TRASPORTO -- ed e' un KERNEL sugli SM
     5 ms  mul_mat_vec_q       7,6%   la parte densa
     3 ms  mul_mat_vec_q_moe   4,8%   LA MATEMATICA DEGLI ESPERTI
```

Traccia di route di neuraforge (7.267 posizioni, `docs/porto/massa_finestre.py`):

```
  domande per token                    258      (43 strati x 6)
  gia' residenti dal token prima      36,4%
  mancanti per token                   164
  mancanti per strato                    3,8    ->  25,7 MiB
  tempo di uno strato                    1,78 ms
  banda necessaria                      14,4 GiB/s
  banda DMA misurata                    24,4 GiB/s    <- ci sta, 40% di margine
```

Premio se i 34 ms escono dal critico: **145 -> 111 ms per ciclo, 13,2 -> 17,1 t/s.**

## Perche' il prefetch di oggi non ci arriva

`cache_predici` (`cache-esperti.cu:2252`) e' alimentato da `rotte`, cioe' dalle
route **del batch corrente**. Prevedere il token dopo dal token prima non puo'
superare il 36-47%, e la tabella delle finestre dice che **non e' questione di
quanta storia si guarda**: da W=2 a W=100 il predittivo sta fra 44,5% e 47,1%.
Due punti e mezzo su un fattore cinquanta di ampiezza.

Il tetto e' del metodo, non della sua taratura. Guardare indietro e' finito.

## Cosa collegare

Il **predittore di route** ([[predittore-route-gate-strato-dopo]]): il gate
dello strato L+1 applicato allo stato nascosto di L. Misurato **71% da solo,
90,2% con la recency, allo 0,2% del calcolo**. Esiste, e' misurato, e non e'
mai stato collegato alla coda DMA.

Un solo strato di anticipo basta: la finestra e' 1,78 ms e il trasporto ne
chiede 1,05.

## I cancelli, scritti PRIMA

1. **BIT-ESATTO.** Anticipare una copia non cambia i byte. SHA `33D76723EB8D`
   sul braccio di riferimento (jprompt, ub 64, 339 slot, 1.200 token, TOPK=1,
   sfratto parallelo). **Da rifare prima di tutto**: la build dell'11/8 ha
   rilinkato `ggml-cuda.dll` col lavoro DOMANDA_DMA (leva spenta), e finche'
   quel cancello non ripassa nessun numero di decode vale.
2. **La leva spenta di difetto**, e a leva spenta il binario identico.
3. **Il numero da guardare non e' i colpi**, sono i **ms di `kern_copia` per
   ciclo**. I colpi possono salire senza che il t/s si muova — successo gia'
   visto tre volte ([[capienza-non-paga-colpi-non-valuta]]).
4. **Il tetto va misurato prima della politica.** `LLAMA_CACHE_ORACOLO` esiste
   e prende una pista `ORACOLO1`: con la traccia di neuraforge in mano si puo'
   misurare il caso a previsione PERFETTA e sapere quanto vale il corridoio
   prima di scrivere una riga di predittore. Se l'oracolo non da' 17 t/s, il
   predittore non li dara' mai.

## Attenzione a una trappola gia' pagata

`oracolo_pista.py` legge male i dump **di prefill**: `ffn_moe_topk` e' una vista
dei primi 6 di ogni riga di `ffn_moe_argsort` (256 colonne), e `ggml_nbytes` di
una vista misura l'estensione. Sui dump di decode (un token per chiamata) la
lettura ingenua e' corretta. Per costruire una pista da un dump multi-token si
usi il lettore di `docs/porto/conta_esperti.py`, che deduce il passo da
`INDICE.tsv` e ha il cancello giusto (**la riga intera dev'essere una
permutazione di 0..255**).
