# PINBUDGETFIX2 — inventario CUDA-pinned + OS-locked riconciliabile

Data: 2026-07-30. Patch: `pinbudgetfix2.patch` (target:
`ds4-p4a/ds4.c` e `ds4-p4a/ds4_cuda.cu`; 10 hunk, +63/-1).
`git apply --check --whitespace=error-all` è pulito sul tree corrente.
Non compilato e nessun server avviato, come richiesto.

## Causa dei ~30,7 GiB

Il difetto osservato è reale — il totale non è riconciliabile con i kind
stampati — ma i byte non sono inventati e non provengono da un doppio conto
della finestra masked.

Nei tre log forniti compare, prima dell'arena KV:

```
CUDA dynamic arena ready pinned=30.00 GiB ... bytes=32211468288
```

`32211468288 B = 30719,25 MiB`. Il sorgente alimenta esattamente quel valore
con il `cudaHostAlloc` mapped dell'arena dinamica, e con il retry unmapped:

- `ds4-p4a/ds4_cuda.cu:11051-11053`;
- `ds4-p4a/ds4_cuda.cu:11061`;
- la conferma applicativa è la riga `ready ... bytes=` a `:11195-11207`.

L'allocazione non chiamava `ds4_hostpin_tag`, quindi il wrapper la inseriva in
`DS4_HOSTPIN_KIND_OTHER`; `ds4_hostpin_log_alloc()` sopprime esplicitamente
`other` (`:3964-3975`). Per questo i 30719,25 MiB entravano nel totale senza
una riga.

La riconciliazione di `X_ctl_coevo`/`X_neu7c95` è esatta:

```
model_stage 256,000004
+ dynamic_arena 30719,250000
+ kv_arena 2011,530273
+ route_stage 40,500000
= 33027,280277 MiB  -> log 33027,3 MiB
```

In `X_izc1` si aggiungono circa 297 MiB di `indexer_zc`, producendo i
33324,3 MiB osservati. Il `cudaHostRegister` della mappa MTP secondaria
(`ds4_cuda.cu:17832-17835`) non è la sorgente del salto nei log consegnati;
restava però un altro possibile grande `other`, quindi la patch gli assegna
anche il kind esplicito `mtp_window`.

## Correzione

1. Aggiunge i kind CUDA `dynamic_arena` e `mtp_window`. Tagga entrambi i
   tentativi mapped/unmapped dell'arena primaria (`:11051`, `:11061`), i due
   tentativi dell'arena Q1 residente (`:10673`, `:10678`) e il register MTP
   (`:17832`). Non cambia byte, flag, ordine, fallback o ammissione.
2. Il punto `VirtualLock`/`mlock` resta in `ds4.c`. Un solo stato
   `g_ds4_nextn_os_locked_bytes` conserva i payload dei soli lock riusciti,
   già calcolati nella variabile `locked` e già stampati da `[nextn-cpu]`.
   L'hook read-only `ds4_nextn_os_locked_bytes()` evita di duplicare lo stato
   nel TU CUDA. Il modo 0 pubblica zero.
3. A fine `ds4_gpu_vram_ledger_request_end()` viene emessa una sola riga
   `[host-pin-summary]`: tutti i kind CUDA (compreso `other`), totale
   `cuda_pinned`, kind/totale `nextn_os_lock` e somma `combined`.
4. Il mutex del ledger viene preso una volta sola al request-end. Sul percorso
   per-token non è aggiunto alcun branch, lock, contatore o sincronizzazione.
   I tag nuovi operano esclusivamente attorno ad allocazioni fredde.

Il tetto opt-in `DS4_CUDA_HOST_PIN_TOTAL_BUDGET_GB` continua a governare solo
le API CUDA, esattamente come prima; l'OS-lock entra nell'inventario combinato
ma non nell'ammissione, per rispettare il vincolo di nessun cambiamento di
comportamento.

## Criterio di accettazione

Alla configurazione `ctx=150000`, la riga request-end deve soddisfare:

```
cuda_pinned_total_mib =
  other + window + range + indexer_zc + kv_arena + model_stage +
  route_stage + dynamic_arena + mtp_window

combined_mib = cuda_pinned_total_mib + os_locked_total_mib
```

Tolleranza del confronto sui campi stampati a un decimale: pochi MiB; lo
stato interno è sommato in byte interi.

Valori attesi per i kind richiesti:

| kind | atteso |
|---|---:|
| `window` | 2048,0 MiB quando la finestra masked è abilitata |
| `kv_arena` | circa 1979–2162 MiB (2011,5 MiB nei tre log forniti) |
| `model_stage` | 256,0 MiB |
| `route_stage` | 40,5 MiB |
| `indexer_zc` | 0 oppure circa 346,5 MiB se il flag è attivo e il budget lo ammette |
| `nextn_os_lock` | circa 4270 MiB con `DS4_NEXTN_PIN=2`, limitato ai lock riusciti |

Nota indispensabile per leggere i log di campagna: con
`DS4_CUDA_DYNAMIC_ARENA_GB>0`, `ds4_gpu_set_model_map()` salta la finestra
masked (`ds4_cuda.cu:17691-17697`). Nei tre log consegnati l'arena è ON:
quindi `window=0` e `dynamic_arena=30719,25 MiB`; quel valore va incluso nel
totale, non eliminato. Nel braccio senza arena dinamica si applica invece
l'atteso `window=2048 MiB`.

## Perimetro

- Nessun cambiamento all'allocatore range indicato (`:8481-9200`), al
  transiente/`os_file`, al teardown/ledger retire, al precheck route worker o
  alla logica NextN: in `ds4.c` si copia soltanto il contatore `locked`
  esistente nel piccolo hook diagnostico.
- Nessun rilascio, budget, flag, dimensione o layout di struct modificato.
- Gli unici file scritti da questa consegna sono questa nota e la patch.

## SHA-256

- base `ds4-p4a/ds4.c`:
  `2d97991e6037c434e484ab6a8c8cc2a364e7cf69aa403ad5e6baa815d3dd6e5c`
- base `ds4-p4a/ds4_cuda.cu`:
  `f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37`
- `pinbudgetfix2.patch`:
  `c8416cf618253e43931256343d005c66515d15223bf275563765c9e3aa72e047`
