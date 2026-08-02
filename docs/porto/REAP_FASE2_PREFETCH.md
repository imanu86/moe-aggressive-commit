# Reap-loop fase 2 — prefetch, non evizione

Scritto il 2 agosto 2026, mentre gira il primo run che produce la mappa del
calore. Decisione dell'utente: la fase 2 si costruisce. Questo documento fissa
**quale** fase 2, e perché quella e non l'altra.

## Perché prefetch e non evizione

Il conto di capienza (`docs/porto/mappa/capienza.py`) falsifica una cosa
precisa: **decidere chi sfrattare** per calore. Al gradino RAM↔SSD, dove il
reap-loop lavora, la RAM tiene ~65% degli esperti, e lì:

```
LRU (cio' che Windows fa gia')   92,3%
insieme caldo statico            92,6%    <- +0,3 punti
Belady (tetto assoluto)          94,5%
spazio per QUALUNQUE politica     2,2 punti
```

Belady è ottimo **per l'evizione**: nessuna politica di sfratto può fare
meglio. Ma non vincola l'**ammissione anticipata**. Una politica che porta in
RAM un esperto *prima* che serva non è limitata da quel tetto: il margine
diventa dal 92,3% al 100%, cioè **7,7 punti invece di 2,2**. Tre volte e mezzo.

E usa la stessa mappa del calore che la fase 1 produce già.

## Il meccanismo, verificato sul codice

Tutti e tre i pezzi esistono e sono stati verificati sul sorgente il 2/8:

**1. I pesi degli esperti sono un tensore 3D con gli esperti sull'ultima
dimensione** (`src/llama-model.cpp:2816`):

```cpp
layer.ffn_gate_exps = create_tensor(..., {n_embd, n_ff, n_expert}, flags);
```

Quindi l'esperto `i` occupa lo slab

```
tensor->data + i * tensor->nb[2]      lungo  tensor->nb[2] byte
```

Aritmetica pura, nessuna tabella da mantenere. Tre piani per strato:
`ffn_gate_exps`, `ffn_up_exps`, `ffn_down_exps`.

**2. Con mmap, `tensor->data` punta DENTRO il file mappato**
(`src/llama-model-loader.cpp:1387`):

```cpp
cur->data = (uint8_t *)mapping->addr() + w.offs;
```

Non è una copia in memoria privata: è la pagina stessa. Quindi l'indirizzo che
l'aritmetica del punto 1 produce è direttamente l'argomento di
`PrefetchVirtualMemory`, senza traduzioni.

**3. L'osservatore sa già quali esperti sono caldi** — è la fase 1, che gira e
non costa niente di misurabile (regime 7,56 con osservatore acceso contro 7,18
con lo stesso binario spento).

## Il disegno

Il **consumatore** della fase 1 già drena l'anello e aggiorna la mappa del
calore fuori dal percorso critico. Lì dentro, e non altrove, va la politica:

```
ogni N record drenati:
    ricalcola l'insieme caldo (i K esperti piu' caldi)
    per ogni esperto ENTRATO nell'insieme da quando l'abbiamo guardato:
        PrefetchVirtualMemory(processo, 3 intervalli: gate, up, down)
```

Vincoli che il disegno deve rispettare, per non ripetere gli errori della sera:

- **niente nella sezione critica.** Il produttore resta un `fetch_add` piu'
  scrittura lineare. Tutto il resto sta nel consumatore.
- **niente `cudaMemGetInfo`-equivalenti**: non trasformare "RAM apparentemente
  libera" in capacita'. Il prefetch va limitato a un tetto fisso di byte in
  volo, altrimenti si compete con la cache di Windows invece di aiutarla.
- **misurare il numero di miss, non i byte.** Regola gia' in atlante: se una
  leva non riduce il NUMERO di accessi che vanno su disco, e' gia' falsificata.

## Cosa manca prima di scrivere

1. **La mappa del calore vera**, da llama.cpp. Finora abbiamo simulato sul
   tracciato `[route-ids]` di DwarfStar: giusto come proxy (la routing e' una
   proprieta' del modello) ma non e' il dato del motore in uso. Il run in corso
   la produce.
2. **Rileggere `capienza.py` su quel tracciato.** Se anche lì il margine di
   prefetch e' piccolo, la fase 2 va ripensata di nuovo prima di scriverla.
3. **Un contatore dei miss** — senza, non sapremo dire se il prefetch ha
   funzionato. Windows non espone i soft fault per-processo in modo comodo: la
   via probabile e' contare in `osserva()` i primi tocchi di ogni esperto per
   finestra, che e' un proxy del lavoro di caricamento.

## Cosa NON fare

Non riscrivere la politica di evizione. È falsificata, e i 2,2 punti di tetto
non ripagano nemmeno la complessita' di misurarli.
