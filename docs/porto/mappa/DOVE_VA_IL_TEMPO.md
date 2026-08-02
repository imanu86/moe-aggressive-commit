# Dove vanno i 288 ms per token

Misurato il 2026-08-02 con `DS4_CUDA_WORKER_PROFILE=1` e
`DS4_CUDA_MOE_ROUTE_PROFILE=1` sul braccio G, ctx 10000, 600 token.
Log: `D:\ds4_work\porto_run\G_100140_DS4_CUDA_MOE_ROUTE_PROFILE=1_DS4_CUDA_WORKER_PROFILE=1.server.log`

**Quel run non misura la velocita'**: la profilazione la altera. Misura la
ripartizione.

Il tempo per token e' ~288 ms da sempre, in ogni configurazione provata. Questa
e' la prima volta che ne guardiamo dentro invece di constatarlo.

## La ripartizione

Dalla finestra `[worker-prof]` (32 token, 1376 job = **43 job per token**, cioe'
un job per strato):

```
job_ms                237,2 ms/token
  read_gate           167,3   70,5%   l'attesa delle letture
  drain                20,3    8,6%
  deliver               5,8    2,4%
wait_ms                 0,0            il lavoro non aspetta mai di partire
pickup_lag_ms           0,0
job_faults              0

read_bytes          1,578 GiB/token    coerente col conto teorico di 1,74
read_calls            718  /token      2,8 letture per esperto
read_mb_s            3249              <- IL MURO
inflight_avg          2,32              su un massimo di 4
worker_model    synchronous
cache_invalidates       43 /token
```

## Il muro: 3,25 GB/s di letture

Non e' il disco: Task Manager lo dava allo 0-1% durante il run. E' la velocita'
con cui Windows serve le pagine del file mappato dalla **standby list** via soft
fault, ed e' coerente con i 3,58-4,78 GB/s misurati il 1/8 per quella via.

`1,578 GiB/token / 3,25 GB/s = 486 ms` se le letture fossero seriali. Con 2,32 in
volo in media si arriva ai 167 ms osservati. **La sovrapposizione e' cio' che ci
tiene a galla, e non e' piena.**

## Perche' la coda non si riempie

`cuda_stream_selected_fill_spans_overlapped` (`ds4_cuda.cu:3865-4012`, per-layer):

> Su Windows legge span di esperti in parallelo e li copia in VRAM tramite
> **quattro buffer pinned**. **Sincronizza prima del ritorno**; al fallimento il
> chiamante ripete tutto in seriale.

Da qui il tetto di 4. E la media a 2,32 si spiega senza ipotesi: 6 esperti x 3
piani = **18 span per strato** su 4 buffer sono ~5 giri, e **ogni giro finisce con
un'attesa**. A ogni confine la conduttura si svuota e si riempie, 43 volte per
token.

## Le tre letture per esperto

718 letture per 258 esperti = 2,8. Un esperto ha tre piani (gate, up, down) e li
leggiamo **separatamente**. Se fossero contigui nel file sarebbero una lettura
invece di tre: da 718 a 258 chiamate per token.

Su un runtime dove il 70% del tempo e' attesa di letture, dividere per tre il
numero di chiamate e' il verso giusto — l'opposto di
`DS4_CUDA_ROUTE_PREFETCH_HINT`, che le aumentava e ha perso il 35,7%.

## Cosa NON e' il problema

- **La coda di ingresso**: `wait_ms=0`, `pickup_lag_ms=0`. Il lavoro non aspetta
  mai di partire.
- **La pubblicazione della route**: `[routeprof] publish=0,15ms` contro
  `transport=6,5ms` per chiamata. Rapporto 1 a 43.
- **Le invalidazioni**: 43 per token riguardano `g_stream_selected_cache`, il
  buffer di staging dello strato corrente, **non** la cache esperti VRAM.
  Invalidarlo a ogni strato e' corretto per costruzione. Verificato a
  `ds4_cuda.cu:1897`.

## La discriminante da fare

```
IO_QD = 12    se inflight_avg sale   -> il limite sono i buffer: si alza e basta
              se resta ~2,3          -> il limite e' la sincronizzazione per strato
```

Nel secondo caso l'unica via per tenere piena la conduttura e' **conoscere gli
esperti dello strato successivo prima di calcolarlo**. E' un'ipotesi che discende
dalle misure, non un fatto.

## Nota sulla semantica di `[routeprof]`

`const double scale = 1000.0 / (double)calls;` — il numero stampato e' la **media
di millisecondi per chiamata su tutte le chiamate fatte finora**, non una
finestra. Per questo cala: e' una media che si abbassa dopo il riscaldamento. Si
assesta a **6,5 ms per chiamata**. Letto dal codice (`ds4_cuda.cu:29443`), non
dedotto.
