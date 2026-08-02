# Dove finisce la VRAM su 0731 — e perche' la cache esperti non nasce

Venti letture Codex parallele sull'albero `ds4-port`, notte del 2/8. Rapporti in
`ds4-port/LETTURA_*.md`, commit `d26cdf6`.

## Il fatto da spiegare

```
VRAM totale                      12287 MiB
model_range_live (backbone)       8394
cache q8/f16                      2088
cuda_tmp                             6
                                ──────
tracciati                        10488
free_bytes a decode-start            0        <- 1799 MiB non spiegati
```

Conseguenza: `[iq2-expert-cache-size] result=disabled capacity=0`, quindi
`expert_slots_resident=0` e **nessun esperto resta in VRAM**. Ogni token
trasferisce 258 esperti x 6,75 MiB = **1,74 GiB** dalla RAM via PCIe.

## Le due cause, con riga

### 1. Il working set compact del prefill — fino a 1728 MiB, mai restituito

Tre agenti indipendenti (`CACHE_ESPERTI`, `ROUTE_WORKER`, `TEARDOWN`) convergono:

- Il transport alloca gate/up/down come `compact_count * bytes_per_plane` piu' il
  remap `slot_selected`, **prima** del sizing della cache (`ds4_cuda.cu:29038`).
- Sono **high-water**: `invalidate()` azzera solo `valid`, i `cudaMalloc` restano
  fino ad `adapter_release` (`ds4_cuda.cu:28870`).
- Il prefill batch passa `n_tokens*6` ID e **deduplica fino ai 256 esperti del
  modello**: 256 x 6,75 MiB = **1728 MiB**.
- Il request-end non reclama transport, cache ne' arena.

**Il prefill si prende la VRAM per il suo caso peggiore e la tiene per sempre. Il
decode, che ne ha molto piu' bisogno, trova zero.**

### 2. Lo slack degli slab da 1792 MiB — ~566 MiB invisibili

`VRAM_ALLOC`: i range del modello usano first-fit in slab da **1792 MiB**; il
backing fisico e' `sum(a.bytes)` ma il contatore cresce solo dei **byte utili**, e
il ledger pubblica quello. Tail, slack e fori non compaiono.

```
8393,6 MiB utili  ->  5 slab x 1792  =  8960 MiB allocati  ->  566 MiB di slack
```

Non e' spreco vero (serve per il first-fit) ma **falsa la lettura**: credevo di
avere 3894 MiB liberi e ne avevo ~3300.

## Cosa e' stato ESCLUSO, con riga

Vale quanto il ritrovamento, perche' evita di ricontrollarlo:

| tema | verdetto |
|---|---|
| cuBLAS | nessun workspace esplicito; 64 MiB solo come budget teorico nel packer |
| multi-GPU | non alloca nulla con `n_gpus==1`, nemmeno il probe peer |
| kernel Q4_K | nessun `cudaMalloc` proprio: aliasa `down->ptr` e `gate->ptr` |
| grafi CUDA | tengono `cudaGraph_t`/`cudaGraphExec_t`, non buffer |
| `cuda_tmp` | slab unico high-water, non cumulativo |
| attenzione | a `prefill_cap=256` vale 252 MiB, non i 4 GiB che temevo |
| KV | 174 MiB migrabili, misurati col ring |

## Tre difetti trovati per strada

1. **`DS4_CUDA_MOE_DECODE_GRAPH=0` ACCENDE il ramo** (`ds4_cuda.cu:2148`): il test
   e' `getenv != NULL`. Una variabile messa a zero per spegnerla la attiva. Chi la
   usasse per un A/B misurerebbe due volte la stessa cosa.
2. **`cudaHostRegister` prova a registrare gli 80,76 GB interi**
   (`ds4_cuda.cu:6027`, budget `UINT64_MAX` senza knob) e fallisce: e' la riga
   `host registration skipped: out of memory` presente in ogni run dall'inizio.
   Con una finestra invece del modello intero, riuscirebbe.
3. **Con `--mtp` ma senza `--dspark`**, `session_create` configura la capture senza
   controllare `e->dspark`: alloca buffer GPU per una funzione spenta.

## Il contesto che spiega tutto: upstream ha fatto la stessa cosa, prima

Fra il fork (base 12/05) e 0731 (28/07) ci sono **314 commit upstream**: 209 di
antirez, 35 di Donato Capitella (ROCm), ~42 da 27 contributori esterni, 30 merge.

E fra questi:

```
2026-06-04   Implement SSD streaming
2026-06-05   cuda: stub streaming expert cache hooks
2026-06-07   Improve SSD streaming expert cache eviction   (+6 fix lo stesso giorno)
2026-06-14   Refactor streaming expert cache API
2026-07-22   Add resident IQ2 MoE sorted-path isolation
```

**Upstream ha costruito il proprio streaming SSD e la propria cache esperti a
giugno.** Il nostro fork ha lavorato sugli stessi problemi a luglio, senza saperlo.

Questo spiega ogni cosa incontrata nel porto: l'arena costa invece di rendere
perche' duplica il loro streaming; `ADMIT_KNOCKS_SSD` non e' portabile perche' il
loro seed RAM e' ranking upstream; la catena della vittima non esiste perche' la
loro cache non mette mai il backbone fra i candidati; il route worker e'
"deliberatamente diverso".

**Non stiamo aggiungendo una capacita' che manca: stiamo affiancando la nostra a
una loro che gia' c'e'.** La strategia "portiamo tutte le 16k righe" e' quindi
sbagliata. Va portato solo cio' che agisce su un meccanismo che upstream NON ha.

## Piano, in ordine di valore atteso

1. **Rilasciare o rimpicciolire il working set compact prima del sizing della
   cache.** E' il difetto n.1, vale fino a 1728 MiB, ed e' codice upstream da
   correggere li'. Verifica gia' disponibile: il contatore
   `selected_capacity_bytes` esiste, va confrontato con il buco a decode-start.
2. **Portare le tre leve di trasporto che mancano**: `ROUTE_BATCHED_PUBLISH`,
   `SPLIT_HIT_MISS`, `ROUTE_NO_DEFAULT_SYNC` (nostre, 16-19 luglio). Sono le uniche
   che agiscono sui 258 trasferimenti per token, cosa che upstream non ha mai
   affrontato. Con il 60% del tempo in orchestrazione, e' li' che c'e' spazio.
3. **Correggere i tre difetti** sopra: costano poco e uno di essi (il grafo che si
   accende a zero) puo' falsare qualunque misura futura.
4. **Portare `[host-pin]`**, l'unica delle 14 famiglie di telemetria mancanti che
   serva davvero: senza, la memoria host si deduce per differenza.

## Cosa NON fare

- Non riaccendere l'arena finche' il punto 1 non e' risolto: oggi toglie VRAM
  senza aggiungere residenza, perche' lo standby di Windows tiene gia' 49,7 GB
  del modello.
- Non portare le 8 leve `ARENA_WRAP_*`: il tronco carica a domanda, non in blocco.
- Non toccare `G73_OPEN`: commuta le specializzazioni del dispatcher, e su 0731
  quel dispatcher ha la route Q4_K che il fork non aveva.
