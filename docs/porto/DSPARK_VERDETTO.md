# DSpark — il verdetto, con il confronto pulito

3 agosto 2026, alba. Chiude la questione aperta dal handoff del 2/8.

## Il dato

Due bracci identici tranne la speculazione: stesso binario (fork), `-ngl 22`,
ctx 4096, 300 token, stesso prompt, stesso momento.

```
                          ms/token    t/s     accettazione   VRAM
A  senza speculazione       388,69    2,57         —        6.193 MiB
B  con speculazione         376,08    2,66      0,641      11.974 MiB
                            -12,6     +3,5%
```

**La speculazione funziona e guadagna il 3,5%.** Il draft indovina: 4,11 token
accettati per ciclo su 5 abbozzati.

## Ma il confronto che conta è un altro

```
ncmoe42, backbone tutto in VRAM, SENZA speculazione     7,21 t/s
-ngl 22 + draft in VRAM, CON speculazione               2,66 t/s
```

Il draft occupa 5.781 MiB, e per fargli posto bisogna togliere venti strati di
backbone dalla VRAM. Quei venti strati valgono il salto da 2,57 a 7,21 — quasi
**tre volte**. La speculazione ne restituisce il 3,5%.

## Perché il premio non si materializza

L'ammortamento è reale e misurato: il 78% del costo di un token è per PASSATA
(108 ms) e solo il 22% per token (30 ms), quindi verificare 5 token in una
passata dovrebbe risparmiare molto.

Ma il draft se lo mangia. Dai numeri: amortizzare la passata su 4,11 token
dovrebbe rendere ~80 ms/token, e ne rende 12,6. La differenza — ~70 ms/token,
cioè ~290 ms per ciclo — è il costo del draft.

Un draft da **19,85 miliardi di parametri**, a sua volta un MoE, per un bersaglio
da 671: un decimo del modello, dove la speculazione ne vorrebbe un cinquantesimo.

## E la seconda GPU non lo salva

Nella configurazione buona la passata costa 108 ms invece di ~300, quindi
l'ammortamento ha **meno** da recuperare, mentre il costo del draft resta
uguale. Il guadagno sarebbe minore di questo 3,5%, non maggiore.

## Quello che è stato provato, e che resta fatto

```
draft caricato su GPU              SI, prima volta nella campagna
draft-dspark sul vanilla b10227    supportato ma il draft NON si carica:
                                   upstream non implementa DFlash con backbone
                                   DSV4 (342 righe di differenza in dflash.cpp)
quantizzazione del draft           MXFP4 4,39 bpw -> Q2_K 2,89 bpw
                                   10.386 MiB -> 6.842 MiB, --allow-requantize
costo in accettazione              0,765 (4 bit) -> 0,605-0,641 (Q2_K)
```

Il file quantizzato resta in `D:\ds4-models\DSpark-draft-Q2K.gguf`.

## Gli errori di confronto fatti su questa questione

Tre, tutti dello stesso tipo, tutti corretti da un controllo:

1. **"il fork costa il 21%"** — era il compute buffer da 12 GB che sbordava in
   memoria condivisa. Con `-ub 64` il fork fa 7,21 contro i 7,18 dell'ufficiale.
2. **"DSpark perde"** — confrontavo 2,66 (ctx 4096, 300 token) con 3,73 (ctx
   10000, 900 token). A parità di condizioni guadagna il 3,5%.
3. **"il draft costa 200 ms a passata"** — dedotto assumendo 5 passate, mentre
   DSpark e' semi-autoregressivo e ne fa una sola (`block_size=5`).

Il verdetto finale coincide con quello sbagliato, ma per la ragione giusta e
con i numeri sotto.
