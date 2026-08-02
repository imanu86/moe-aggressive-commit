# Audit di sovrapposizione: cosa togliere, cosa tenere, cosa correggere

Otto letture Codex parallele, 2/8. Rapporti in `ds4-port/AUDIT_*.md`.

L'audit che **doveva precedere il porto** e non l'ha fatto: abbiamo trapiantato 3562
righe su upstream senza leggere i 314 commit che lo separavano dalla nostra base.

## Tre commit spiegano quasi tutto

Contati sui rapporti, per numero di assunzioni nostre invalidate:

```
15 volte   36ee8c1   Add CUDA tensor parallelism and session batching     18/07
13 volte   bbd069d   Add CUDA and ROCm SSD streaming                      14/06
11 volte   9ba160a   Implement SSD streaming                              04/06
```

Non 314 da leggere: **tre**. Mezz'ora di diff avrebbe cambiato quattordici mandati.

- `9ba160a` + `bbd069d`: upstream costruisce **il proprio** streaming SSD e trasporto
  CUDA a giugno — il territorio su cui il nostro fork lavorava da maggio.
- `36ee8c1` (18/07): **rimuove la cache residente CUDA lasciando gli stub**, cambia il
  contratto della mappa del modello, e introduce un fast path che mette `tensor->ptr`
  scavalcando le API tensor-aware.

Da soli spiegano: l'arena che duplica, la cache che si accende a meta', il KV ring che
va in illegal memory access, e quattro famiglie di leve senza aggancio.

## DA TOGLIERE

| cosa | perche' | riga |
|---|---|---|
| **l'arena dal preset di produzione** | duplica il selected-loader CUDA upstream, che e' "esatto e bounded" | `ds4_cuda.cu:22953` (`bbd069d`) |
| **la nostra cattura router** | legge ID+pesi con due `cudaMemcpy` sincrone e **duplica il readback gia' fatto dal worker upstream**: ogni layer routed fa il D2H degli ID **due volte** | `ds4-port ds4_cuda.cu:2096`, `:2127` vs `upstream ds4.c:20985` |
| **il nostro rendezvous route worker** | upstream avvia gia' il selected-load in modo asincrono: il nostro e' **una seconda thread sul cammino critico** | `src/cuda/route_worker.cpp` (nostro `3c225d2`) vs `upstream ds4.c:21048` |
| **la nostra politica di trasporto nei quant** | contraddice il selected-load SSD CUDA upstream | `upstream ds4_cuda.cu:20862` |
| **la finestra host del masked budget sotto `--ssd-streaming`** | duplica i byte gia' copiati nell'arena e compete col pinned staging upstream | `ds4-port ds4_cuda.cu:6086` |
| **la via `STREAMING_EXPERT_CACHE_N`-only** | accende la slab **ma non il tracking**: `copy_hit()` alloca, la capture esce a vuoto. **E' il 5,6x** | `src/cuda/vram_expert_cache.cpp:288`, `:312` |
| l'helper `SEQUENTIAL_SCAN` | rimasto senza chiamante | `src/platform/os_file.c:146` |

## DA TENERE — non hanno corrispondente upstream

| cosa | perche' |
|---|---|
| **`DS4_CUDA_MOE_IO_QD`** | upstream legge dal disco **una richiesta per volta** (`cuda_model_stage_read()` bloccante); sovrappone solo H2D. **Il +14,8% e' reale**, misurato su tre run |
| `MOE_ROUTE_PACKED_COPY` | tre piani contigui: da tre submission D2D a una `cudaMemcpy2D` |
| `MOE_ROUTE_PROFILE` | upstream cronometra il selected-load ma non la promozione |
| **tutto il layer di piattaforma Windows** | upstream apre ancora con `open(O_RDONLY)` e mmap POSIX. Le quattro `OVERLAPPED` persistenti non hanno equivalente |
| **la nostra mass-LFRU** | **non c'e' contesa**: l'LFU route-hotness di upstream vive in Metal, su CUDA la nostra e' l'unica — e migliore del vecchio LRU che ammetteva ogni miss |
| sizing post-attention, riserva 0,5 GiB, spare fisico, backoff OOM | upstream non ce l'ha |
| ledger transazionale slot/sostituzioni e budget di replacement | upstream non ce l'ha |

## DA CORREGGERE — difetti, non sovrapposizioni

1. **La ritenzione del compact al confine prefill/decode.** I 1728 MiB **non sono
   nostri**: e' upstream che deduplica fino ai 256 esperti Flash e non rilascia
   (`invalidate()` azzera solo `valid`). Il nostro sizing misura `cudaMemGetInfo` dopo,
   e trova zero. **Rilascio al decode-start, gia' in lavorazione.**
2. **`DS4_CUDA_MOE_DECODE_GRAPH=0` ACCENDE il ramo** (`ds4_cuda.cu:2148`): e'
   `getenv != NULL`. Una variabile messa a zero per spegnerla la attiva.
3. **`cudaHostRegister` tenta gli 80,76 GB interi** (budget `UINT64_MAX` senza knob,
   `ds4_cuda.cu:6027`): e' la riga `host registration skipped` di ogni run.
4. **Ordine di teardown**: `model_close` precede `ds4_gpu_cleanup`, quindi
   `cudaHostUnregister` riceve una view gia' smappata (`src/platform/os_mmap.c:76`).
5. **Con `--mtp` senza `--dspark`** si allocano buffer GPU di capture per una funzione
   spenta.
6. **Il KV ring** assume che tutti i consumer KV passino da API tensor-aware; `36ee8c1`
   ha introdotto un fast path con `tensor->ptr` diretto. Da qui l'illegal memory access.

## Il conto onesto

Delle 3562 righe portate, una parte va **rimossa**. Il tronco nudo batte le
configurazioni con la nostra politica non perche' la nostra politica sia peggiore, ma
perche' su questo substrato **accende meccanismi a meta' e ne duplica altri**.

Cio' che resta e' piu' piccolo e piu' difendibile: la coda di I/O Windows, il packing
delle promozioni, il layer di piattaforma, e la policy di sfratto — che e' l'unica su
CUDA.

## Ordine di esecuzione

1. Rilascio del compact (in corso) -> rimisurare: `result=sized capacity>0`?
2. Togliere la via `N`-only, o allineare `tracking_enabled()` a `enabled()` ->
   rimisurare il 5,6x
3. Togliere cattura router e rendezvous -> rimisurare l'orchestrazione
4. Togliere l'arena dal preset
5. I cinque difetti
6. Preset finale e tre run di conferma
