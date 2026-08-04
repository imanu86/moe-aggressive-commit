# Il tetto è ~6,5 t/s ed è orchestrazione: togliere tutta la memoria non lo sposta

4 agosto 2026, mezzogiorno. Chiude la linea sulla gerarchia di memoria.

## L'esperimento

L'idea è dell'utente: se il modello ci sta **intero** in RAM, il problema del
paging non si ottimizza — sparisce.

```
DS4-0731-IQ2XXS      80,76 GiB    NON ci sta nei 63,9
IQ1_S-XL-merged      57,31 GiB    CI STA
```

Stesso prompt (NeuraForge, 8000 token, ctx 10000), stessa configurazione,
stesso binario.

## Il paging sparisce davvero

```
                        fault duri/s
                     mediana   media   a zero
Q1  senza gate            0       90   31/45 campioni
Q1  con gate              0      232   26/46
Q2  con gate            795    1.591    7/64
Q2  senza gate        1.124    1.831    7/70
```

## E la velocità non si muove

```
Q1  senza gate      6,36 t/s
Q1  con gate        6,20
Q2  con gate        5,94 / 6,04 / 6,55
Q2  senza gate      5,22 / 5,63 / 6,45
```

**Q1 sta dentro l'intervallo di Q2**, pur avendo eliminato l'intero carico di
paging *e* il 29% dei byte per esperto.

È la conferma più forte che la campagna abbia prodotto della tesi
orchestration-bound: togliere tutta la memoria dal problema non lo tocca.

Il prefill invece migliora molto — 7,11 t/s contro 2,3-2,5 — perché lì i byte
contano davvero: si legge tutto una volta, in sequenza.

## La predizione falsificabile, confermata

Il secondo braccio serviva a questo: se tutto è residente, il gate non ha
niente da proteggere e **deve** risultare neutro. Se avesse dato ancora un
guadagno, avrebbe voluto dire che il suo meccanismo non è quello che credo.

Risultato: 6,36 senza, 6,20 con. Dentro il rumore. Il gate agisce sul paging, e
dove non c'è paging non agisce.

## La qualità, con l'avvertenza

```
                      car.   righe  tag  prof  sbil  css{  req  rip  dup%
Q1                  13.829    451   74    7     5     53  7/7   4  18,8%
Q2  (col gate)      21.600    634   92    7     0     59  7/7  16  17,2%
riferimento 25/7    24.111    706  100    7     0     87  7/7  10,8%
```

Q1 arriva a **7/7**: ci sono tutti e sette gli elementi che il prompt chiede, e
**non degenera** — la ripetizione massima è 4, la più bassa delle tre pagine.

Ma è **36% più corta** e ha **5 tag sbilanciati** dove Q2 ne ha zero: l'HTML non
è ben formato. Quella è la regressione vera, e non si vede dal conteggio dei
requisiti.

**Avvertenza dichiarata prima del run**: l'IQ1_S è un checkpoint più vecchio
del 0731, quindi il confronto di qualità mescola checkpoint e quantizzazione in
un numero solo. Quello sulla velocità e sul paging regge — architettura, taglia
e fisica della memoria sono quelle.

## Il quadro

**Il tetto è ~6,4-6,5 t/s ed è orchestrazione.** Due strade opposte ci arrivano
e nessuna lo supera:

```
Q2 + gate        6,55    togliendo i crolli
Q1 residente     6,36    non avendo niente da paginare
```

Tutto il lavoro sulla gerarchia di memoria — residenza, mappa per rango, massa,
blocco, prefetch — ci ha portati **al** tetto. Il tetto sta altrove.

E il gate resta utile per quello che fa: porta la configurazione che gira
davvero (Q2, che è il checkpoint buono) al livello che altrimenti richiederebbe
di scendere a 1 bit. Con uscita identica bit per bit, che Q1 non può offrire.

## Cosa resta aperto

L'unica leva mai provata che toglie lavoro invece di spostarlo è
**l'ammissione al routing** — negare al router un esperto marginale e freddo,
rinormalizzando il gating sui sei ammessi. Cambia l'uscita, quindi vuole un
cancello di qualità e non di identità, e il metro c'è
(`docs/porto/rubrica_html.py`).

Tutto il resto misurato finora sposta byte. Il tetto non è fatto di byte.
