# PINBUDGETFIX — budget host-pin onesto + fallback PIN EXHAUSTED sano

Data: 2026-07-29. Mandato: audit10 01-B1/01-B2, 06-ZC1/ZC2/ZC3, 09-#2 (con 07-B1 e 09-#1 convergenti su B1).
Patch: `pinbudgetfix.patch` (solo `ds4-p4a/ds4_cuda.cu`, 25 hunk, ~374 righe aggiunte / 13 rimosse).
`git apply --check` PULITO sul tree corrente al momento della generazione (vedi SHA in fondo).

## Verifica dei claim (tutti sul codice del tree corrente)

| Difetto | Verificato | Prova (file:riga sul tree base) |
|---|---|---|
| 01-B1 / 06-ZC1 / 07-B1 / 09-#1 | SI | finestra registrata senza incremento (`ds4_cuda.cu:17287-17298`), arena KV `cudaHostAlloc` non contata (`:21873-21885`), 4 staging modello non contati (`:6532-6538`), staging route non contato (`:39313-39344`); il check indexer usa solo `g_model_registered_range_bytes` (`:4019-4021`), il per-range idem (`:4144`) |
| 01-B2 | SI | dopo `PIN EXHAUSTED` (`:8746-8762`) la fd-cache torna NULL (`:8804-8806`); il chiamante arriva al `cudaMalloc` diretto (`:4189-4196`) SENZA check riserve (le riserve sono a `:8025-8048` e usate solo dallo stream alloc `:8671-8697`); push con 9 campi su 13 → `streamed=0` (`:4214`, struct `:1940-1957`), invisibile a `pick_victim` (`:8498`) |
| 06-ZC2 | SI | loop `while (cap != 0)` (`:39231`), staging host a dimensione FISSA `CUDA_MOE_ROUTE_COUNT` (`:39313-39344`), shrink -10% su QUALSIASI errore (`:39744-39749`), terminale `cuda_moe_expert_cache_release()` (`:39760`) |
| 06-ZC3 | SI | free dell'arena solo se `release_arena` (`:21810-21817`); il request-end passa `release_arena=sticky` → caso sano non rilascia (`:21832-21839`, chiamato da `:31111`) |
| 09-#2 | SI | `g_indexer_zc_entries.push_back` fuori try/catch (`:4049`); il TU usa gia' 60 blocchi `try` → eccezioni attive nel build, il catch e' coerente |

## Come sono chiusi

**01-B1/06-ZC1 — contabilita' GLOBALE per-kind.** Ledger host-pin SEMPRE ATTIVO nei wrapper del
tracer (macro che intercettano OGNI `cudaMallocHost`/`cudaHostAlloc`/`cudaHostRegister`/
`cudaFreeHost`/`cudaHostUnregister` del TU): mappa ptr→{bytes,kind} + totale live/peak. Il numero
dichiarato coincide col pinnato CUDA reale PER COSTRUZIONE (anche i kind non enumerati finiscono
in `other`). Kind: `window`, `range`, `indexer_zc`, `kv_arena`, `model_stage`, `route_stage`,
`other`, taggati al sito con lo stesso pattern del label del tracer. UNA riga `[host-pin] kind=...`
per allocazione dichiarata, con `kind_live/total_live/total_peak/masked/budget`.
**Budget separati per kind, motivati:** il kind masked (finestra+register-mmap+indexerzc, stessa
risorsa WDDM promessa dal commento `:3918-3923`) e' gestito da `g_model_registered_range_bytes`
contro `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB`, e ORA la finestra lo consuma (era il buco
principale: 4 audit convergenti). `kv_arena`/`model_stage`/`route_stage` sono costi funzionali
deterministici della config (ctx, chunk, route count): ammetterli contro lo stesso tetto da 2 GiB
gia' saturato dalla finestra spegnerebbe KV-staged e lo streaming pesi alla config di campagna —
restano fuori dal budget masked ma DICHIARATI per-kind e sommati nel totale di ogni riga. Il
controllo sulla SOMMA esiste ed e' opt-in: `DS4_CUDA_HOST_PIN_TOTAL_BUDGET_GB` (0/assente =
nessun tetto = comportamento odierno; impostato = ogni pin host CUDA viene rifiutato PRIMA del
driver se sforerebbe la somma; ogni chiamante ha gia' un percorso di failure gestito e auditato).
**Conseguenza onesta da conoscere:** a budget=2 la finestra (min(modello, budget)) satura il kind
masked → indexerzc fa fail-open `host-pin-budget-exceeded` DICHIARATO (prima pinnava 346,5 MiB
oltre il tetto in silenzio). Per il braccio finestra+indexerzc: `DS4_CUDA_HOST_PIN_WINDOW_GB`
(nuovo, opt-in, default = sizing invariato) cappa la SOLA finestra sotto il budget, es.
`BUDGET=2` + `WINDOW_GB=1.6` → finestra 1638,4 MiB + indexer ~346,5 MiB nello stesso tetto.

**01-B2 — fallback con riserve + range sfrattabile.** Il `cudaMalloc` diretto ora (a) verifica
`free >= size+riserva` con le STESSE riserve del percorso streaming (hot per `indexer_f16`,
normale per il resto; fwd-decl delle due funzioni) e fallisce STABILE con log esplicito se le
violerebbe; (b) alloca alla granularita' align-256 del pool e inserisce il range con
`streamed=1, last_used_tick=++g_model_tick, pinned=is_hot` — stesso shape del push fd-cache
(`:8875`) — quindi visibile a `pick_victim`/`span_release` e riciclabile nel pool eventi.
Il pool delle vittime non si restringe piu' permanentemente.

**06-ZC2 — host separato da VRAM nel retry.** Flag `host_pin_failed` settato sui 7 `cudaHostAlloc`
del prepare (3 di controllo + packed/gate/up/down staging, tutte dimensioni indipendenti da
`cap`): in coda al loop, se host → NIENTE shrink, UNA riga che dichiara la risorsa giusta
(`host-pin staging (fixed-size) failed -> no slot shrink` + totale host-pin) e `break` verso lo
stesso terminale di `cap=0` (PIN2 rebuild-failed + release + exact-streaming). Un fallimento VRAM
continua a fare il retry -10% come oggi.

**06-ZC3 — rilascio arena dietro flag.** `DS4_CUDA_KV_ARENA_RELEASE=1` rilascia l'arena al restore
di fine richiesta anche nel caso sano. **DEFAULT PROPOSTO: 0 (trattenuta)** — ragioni: (1) il
re-`cudaHostAlloc` da ~2 GiB e' page-locking reale pagato a OGNI decode-start successivo, (2) le
baseline del ledger sono tutte misurate con arena persistente (continuita' degli A/B), (3) con la
contabilita' nuova l'arena trattenuta non e' piu' silenziosa: `[kv-staged] restored ...
arena_released=0/1 hostpin_total_mib=...` + riga `[host-pin] kind=kv_arena` alla (ri)allocazione.
Chi vuole l'headroom (1,93-2,11 GiB tra richieste) accende il flag e paga la riallocazione.

**09-#2 — fail-open vero.** `push_back` del registro indexer in `try/catch(...)`: su eccezione
`cudaFreeHost` del buffer appena pinnato + `cuda_indexer_zerocopy_failopen("registry-bad-alloc")`
+ NULL → fd-cache, come promesso. Le entry gia' valide restano servite zero-copy.

## Totale pinnato per-kind atteso a ctx 150k (config di campagna: MASKED_BUDGET=2, KV staged ON, routes ENFORCE, chunk 64 MiB, INDEXERZC=1)

| kind | atteso | nota |
|---|---:|---|
| window (masked) | 2.048,0 MiB | min(modello, budget), page-aligned; ora CONTATA nel budget masked |
| indexer_zc (masked) | 0 MiB | fail-open ONESTO a budget saturo; con `WINDOW_GB=1.6` → 346,53 MiB (+84 B slack) |
| kv_arena | 1.979,3–2.162,0 MiB | 06 deriva 2.075.425.792 B, 01 deriva 2.162,0 MiB (inventario tensori divergente ~183 MiB); la riga `[host-pin] kind=kv_arena` stampa il numero ESATTO a runtime — e' lo scopo della cura |
| model_stage | 256,0 MiB | 4 × (64 MiB + align 1 B su Windows) |
| route_stage | 40,5 MiB | 42.467.328 B = 6 route × 7.077.888 B |
| other | < 1 MiB | topk_host ring (2 KiB), 3 flag di controllo mapped, ecc. |
| **TOTALE CUDA host-pin** | **~4.324–4.507 MiB (4,22–4,40 GiB)** | vs "2 GiB" dichiarati prima; con `KV_ARENA_RELEASE=1` scende di ~1,9-2,1 GiB tra le richieste |

(NextN `VirtualLock` ~4,27 GiB resta FUORI da questo conto: non e' pin CUDA, come da 06/07.)

## Vincoli rispettati

- **Neutralita' al byte dei percorsi caldi a parita' di esito:** tutta la contabilita' gira SOLO
  dentro le allocazioni/free e nei loro log (percorsi freddi). Nessun percorso per-token toccato:
  fast-path finestra, hit registry indexer, `pick_victim`, stream-alloc, kernel INVARIATI.
  Gli esiti delle allocazioni cambiano solo dove era il difetto o dietro env nuovi (default off).
- **Nessuna struct condivisa cambiata di layout:** solo stato nuovo globale del modulo
  (enum/array/mappa/mutex) + variabili locali.
- **Zone di altri agenti NON toccate:** os_file.c/transiente, teardown (`ds4_gpu_cleanup`,
  `cuda_model_range_release_all`), release cache (`cuda_moe_expert_cache_release`), ledger retire,
  sharedcore/ds4.c. Il reset dell'accumulatore masked a `:9010` resta coerente: il release_all gira
  prima della ri-registrazione della finestra in `set_model_map`, e i free/unregister passano
  comunque dai wrapper (il ledger decrementa da solo, anche nel teardown altrui).
- **Non compilato** (vietato dal mandato). Rischi di compile ritenuti bassi: il TU usa gia'
  try/catch (60 blocchi), `std::mutex`/`unordered_map` gia' inclusi, fwd-decl statiche legali.

## Env nuovi (tutti default = comportamento odierno)

- `DS4_CUDA_HOST_PIN_TOTAL_BUDGET_GB` — tetto opzionale sulla SOMMA host-pin CUDA del processo.
- `DS4_CUDA_HOST_PIN_WINDOW_GB` — cap opzionale della sola finestra masked (headroom per indexerzc).
- `DS4_CUDA_KV_ARENA_RELEASE` — 1 = rilascia l'arena KV pinnata al request-end (default 0).

## AVVISO CONCORRENZA + SHA-256

Durante la stesura un ALTRO agente (audit 10/10 teardown, marker `10-B1`/`10-B2`) stava riscrivendo
`ds4_cuda.cu` a raffiche (il file e' oscillato su 4 hash in ~15 minuti). La patch e' generata e
verificata contro lo stato sotto. Se al momento dell'apply fossero atterrate le modifiche 10-B2 ai
wrapper di free, l'UNICO hunk in conflitto e' quello su `ds4_trace_cuda_free_host`/`_host_unregister`:
risoluzione = spostare `ds4_hostpin_note_free(ptr);` DENTRO il ramo `err == cudaSuccess`, prima di
`ds4_alloc_trace_release(ptr);` (stessa semantica 10-B2: si scala solo su rilascio accettato).
Tutti gli altri 23 hunk stanno in regioni che il teardown-agent non tocca.

- `ds4-p4a/ds4_cuda.cu` (base su cui la patch applica, verificata con `git apply --check` pulito): `f0dd5cfc6e001a61e818f8569e74e9ad07d536c55108418fef7851712224ba36`
- `ds4-p4a/ds4_cuda.cu` atteso DOPO la patch (copia patchata byte-identica, CRLF preservati): `a2832707aaa6f9268acc816fbb3744920f1a7ce1ca3ed18f2813bdfafb315cc6`
- `pinbudgetfix.patch`: `d8ffdf02b7836287211419d2ca02b1bc337b73c93e14dbae990e149b862d3a90`
