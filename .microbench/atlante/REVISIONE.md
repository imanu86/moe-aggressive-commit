# REVISIONE DELL'ATLANTE DELLE LEVE — alla luce dei fatti 27-28/7

Data: 2026-07-28. Analisi documentale, zero run, zero build, zero modifiche al codice.

## Fonti lette integralmente

| Documento | Ruolo |
|---|---|
| `C:\Users\imanu\source\repos\reap-loop\docs\DS4_LEVER_ATLAS_20260724.md` | Atlante (foto "prima", 812 leve, 10 censimenti fusi) |
| `C:\Users\imanu\source\repos\reap-loop\docs\DS4_LEVER_ANALYSIS_POST_20260724.md` | Verdetti operativi del 24/7 |
| `C:\Users\imanu\source\repos\reap-loop\docs\DS4_ATLAS_RECONCILIATION_20260726.md` | Riconciliazione con la matrice M0-M4 |
| `C:\Users\imanu\source\repos\reap-loop\docs\CLAIMS_CURRENT.md` | Ultimo aggiornamento 11/7 — **non copre nulla di questa revisione** |
| `C:\Users\imanu\source\repos\reap-loop\docs\ASYNC_PIPELINE_PLAN.md` | 11/7 — **superato**: presuppone overlap=0 e PCIe gen3; entrambi falsificati |
| `C:\Users\imanu\source\repos\moe-aggressive-commit\reap-loop-ledger-main\docs\EXPERIMENTS_LEDGER.md` righe 16400-17270 | I fatti nuovi |
| `C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a\{ds4.c,ds4_cuda.cu}` | Verifica di esistenza delle leve nel binario **corrente** |

**Verifica di esistenza fatta sul sorgente corrente (non riportata dall'Atlante).** Tutte le sonde e le
leve citate qui sotto sono presenti nel binario in uso: `DS4_METAL_DECODE_STAGE_PROFILE` (`ds4.c:11211`),
`DS4_METAL_INDEXER_STAGE_PROFILE` (`ds4.c:11364`, `13413`), `DS4_METAL_LAYER_STAGE_PROFILE` (`ds4.c:13414`,
`14734`), `DS4_METAL_Q_STAGE_PROFILE` (`ds4.c:13415`), `DS4_METAL_GRAPH_TOKEN_PROFILE` (`ds4.c:15002`),
`DS4_CUDA_STREAM_HOT_RESERVE_MB` (`ds4_cuda.cu:6810`), `DS4_CUDA_SLOW_TOKEN_LOG/_MS` (`:7083/:7094`),
`DS4_CUDA_VRAM_PRIO_LOG_EVERY_TOKENS` (`:7114`), `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE` (`:7053`),
`DS4_CUDA_GRAPH_TENSOR_DEVICE` (`:7854`), `DS4_CUDA_KV_MANAGED` (`:7887`), `DS4_CUDA_EXPERT_CACHE_GROW`
(`:28600`), `DS4_CUDA_ROUTE_READ_WHOLE` (`:28854`), `DS4_CUDA_ROUTE_PREFETCH_HINT` (`:28863`),
`DS4_CUDA_EXPERT_ZEROCOPY` (`:31134`), `DS4_CUDA_MOE_IO_QD` (`:38909`), `DS4_CUDA_MOE_DIRECT_CACHE_HITS`
(`:41515`), `DS4_G132_CPU_LANE` (`:46135`).

**`DS4_N_INDEXER_TOP_K` è ancora una costante** (`ds4.c:124`), e il getter
`metal_graph_decode_indexer_top_k(g)` (`ds4.c:11023`) continua a scartare `g` e a ritornare 512. Lo stub
predisposto dell'Atlante è ancora lì, ancora non cablato.

**Campi realmente disponibili nella strumentazione** (letti nel sorgente, non dedotti):

- `[slow-token]` (`ds4_cuda.cu:31424`): `pos, total_ms, worker_wait_ms, pread_calls, pread_bytes,
  transient_serves, evict_backbone_delta, tokens_in_step`. Emessa solo se `total_ms >
  DS4_CUDA_SLOW_TOKEN_MS` (default 1500).
- `[vram-prio]` (`ds4_cuda.cu:28638`): `phase, inverted, elastic, evict_backbone, evict_expert, evict_kv,
  backbone_evicted_bytes, backbone_reload_bytes, backbone_reloads, expert_relaxed_saves,
  expert_slots_current/resident/requested, vram_free_at_decode_start, vram_free_now,
  backbone_reserve_mib, hysteresis_mib, stabilized, stabilized_slots, evicts_total, mem_status`.
  Periodica se `DS4_CUDA_VRAM_PRIO_LOG_EVERY_TOKENS>0`.
- `[zc]` (`ds4_cuda.cu:31304`): fra gli altri `hit_rate, miss_per_token, distinct_per_token,
  evictions_caused_by_miss, t_deliver_ms, t_orchestration_ms, t_drain_ms,
  transient_timeout_fallbacks/_aborts`.
- Profilo per-token (`ds4.c:15029`): `metal graph token pos=… encode=… execute=… read=… total=…`.

---

## Il filtro: gli otto fatti, tradotti in criteri di scarto

| # | Fatto | Cosa scarta meccanicamente |
|---|---|---|
| 1 | Percorso esperti = `t_deliver` 3,6 + `t_orchestration` 36,5 ≈ **40 ms su 280-363** (11-14%) | Ogni leva di trasporto/coda/granularità I/O: il tetto teorico è 40 ms, il realistico è una frazione |
| 2 | Zero-copy UVA falsificata due volte (banco kernel vero 1,493 vs 0,321 ms/expert; runtime +22%) | `EXPERT_ZEROCOPY` in tutti e tre i modi; la variante "fence removal via puntatori host" |
| 3 | A ctx 150k su 12 GB **CACHE_N=140 è il tetto aritmetico**; la VRAM libera è fabbisogno dell'attenzione | Ogni leva che tenta di **alzare** gli slot o di **liberare** VRAM per alzarli |
| 4 | Backbone **0,00 MiB/token** su 15 campioni: tutto il consumo al decode-start | Riserve "per la crescita", isteresi anti-oscillazione, controllo adattivo del budget VRAM |
| 5 | Raffiche = `worker_wait_ms` ~95% di `total_ms`, `evict_backbone_delta=0` | Ogni leva sugli sfratti **come cura delle raffiche** |
| 6 | Timeout 0,25 s = fail-fast BUONO (0 stalli / 221,8 ms vs 40 stalli / 281,0 ms a 10 s) | Alzare `TRANSIENT_IO_TIMEOUT_S`; ritarare i timeout "per pazienza" |
| 7 | La profondità KV reale dei test è **`pos=873`**, mai 150.000 | Tutte le leve del ramo indexer sono **inerti** nel regime misurato (gate a `n_comp>512` ⇒ `pos≥2051`) — e diventano di **prima fascia** nel regime del gate utente |
| 8 | Riavvio = 39%; deriva di sessione ≈ +25% | Ogni **grandezza** storica misurata su macchina sporca. I **segni** sopravvivono, i numeri no |

**Il fatto 7 è il più violento e l'Atlante non lo poteva sapere.** L'intera "caccia aperta" del §6
dell'Atlante (204 ms @ctx768 → 1776 ms @ctx8192) e l'intera campagna 1 "a 150k" hanno misurato **l'ingombro**
di una KV grande, mai **il costo** di una KV profonda. Il ledger documenta con precisione cosa succede a
`pos=2051`: primo token 22.791 ms, poi 25.972 e 25.956, `fd-cache load 0 → 1.066`, `evictions 0 → 1.098`,
e un costo permanente di **~85-90 ms/token**. Nulla di tutto questo è nei 280 ms che stiamo inseguendo.

---

# A. TABELLA DELLE LEVE DELL'ATLANTE

Legenda stato: **MAI** = mai provata; **FALS** = provata e falsificata; **SPORCA** = provata su macchina
sporca o binario diverso, da rifare; **ATTIVA** = già nel preset 150k; **MORTA-COSTR** = irraggiungibile
per costruzione nella config attiva.

## A.1 — Le "15 che contano" dell'Atlante §1

| # | Leva | Documentata | Stato reale oggi | Verdetto alla luce di 1-8 |
|---|---|---|---|---|
| 1 | `DS4_METAL_PREFILL_CHUNK` | ATLAS §1#1, §2.1, §6-A; POST §1.4 `[RIBALTATA]`; RIC "già 250" | **ATTIVA=250**. Il meccanismo vero è emerso dopo: a ctx8192 chunk 2048 → context buffers 333 MiB → cache **133/320** → 0,51 t/s; chunk 600 → 175/320 → 3,19 t/s | **Riqualificare (C-3).** Non è una leva di prefill: è una leva di **VRAM per la cache esperti**. Ma il fatto 3 dice che a 150k gli slot non si possono alzare ⇒ il bersaglio residuo è **ridurre gli sfratti di backbone**, non aprire slot. A3 250→600 a 150k (≈462,7 MiB) **mai eseguita** |
| 2 | `DS4_N_INDEXER_TOP_K` (costante 512) | ATLAS §1#2, §4; POST §1.3 | **MAI**, e ancora costante (`ds4.c:124`; getter stub `ds4.c:11023`) | **Vivo ma fuori regime.** Fatto 7: a `pos=873` il gate non scatta mai. Diventa la leva #1 **solo** nel regime del gate utente. Richiede rebuild (3 righe) |
| 3 | `DS4_METAL_INDEXER_STAGE_PROFILE` | ATLAS §1#3, §3; POST §1.12 | **MAI** (1 sola menzione nel ledger, riga 4997, come "mai acceso") | **Inutile oggi** (fatto 7: non c'è ramo indexer da attribuire a `pos=873`). **Obbligatoria** al primo run a KV profonda |
| 4 | `GRAPH_TOKEN_PROFILE` + `DECODE_STAGE_PROFILE` | ATLAS §1#4; POST §1.12 | `GRAPH_TOKEN_PROFILE` **usata** (`manifest_47.env:43`); `DECODE_STAGE_PROFILE` **MAI** — verificato: "il log non contiene record `metal layer stage part=decode`" (ledger 16509-16517) | **Prima mossa di B.** È l'unica sonda che scompone i ~240 ms non spiegati per stadio. Caveat noto: ogni boundary sincronizza ⇒ serve ad **attribuire**, non a misurare t/s |
| 5 | `DS4_CUDA_STREAM_RESERVE_MB` | ATLAS §1#5, §2.3; POST §1.2 | **ATTIVA=1024**, provata come parametro, **mai come causa con il contatore visibile** | **Riqualificare (C-8).** Oggi il contatore esiste (`[vram-prio] evict_backbone`) e dice 0,90-0,98 sfratti/token **anche a cache 140**. Mai A/B a 150k con quel numero sott'occhio |
| 6 | `DS4_CUDA_WEIGHT_CACHE_VERBOSE` | ATLAS §1#6, §3 | Usata storicamente in `-Diagnostics`; **superata** da `[vram-prio]` | **Deprecare.** Cambia un valore di ritorno (`cuda:4196`) e conta la stessa cosa che `[vram-prio]` conta meglio e gratis |
| 7 | `DS4_CUDA_KV_MANAGED` | ATLAS §1#7, §3; POST §1.3 `[MAI-TESTATA-PROMETTENTE]`; RIC "bassa priorità" | **FALS**: ledger riga 5324 — `cudaMemAdvise` **fallisce a runtime** (`invalid device ordinal` su WDDM). Paga +2 MiB per allocazione per un servizio mai erogato | **MORTA.** Doppiamente: l'advise fallisce, e il ring staged (ATTIVO nella ricetta 150k) rende comunque irraggiungibile il ramo. **Cassare la riga dall'Atlante** |
| 8 | `DS4_METAL_GRAPH_TOKEN_SPLIT_LAYERS` | ATLAS §1#8, §3; POST Top-10 #8 | **FALS** — Add.43b, A/B a 4 posizioni: `0` e `4` danno RELOADS 16/16, steady 0,55/0,55, slot 148/148. RIC: "falsificata" | **MORTA.** Non riproporre |
| 9 | `DS4_CUDA_MOE_ROUTE_NO_DEFAULT_SYNC` | ATLAS §1#9; POST §1.2; RIC "già 1, beneficio piccolo" | **ATTIVA=1** | Chiusa. Fatto 1 la confina comunque nei 40 ms |
| 10 | `EXPERT_CACHE_GROW` + `RELEASE_PREFILL_SCRATCH` | ATLAS §1#10, §3; POST §1.2 | `RELEASE_PREFILL_SCRATCH` **ATTIVA=1** nella ricetta 150k. `GROW` **MAI** (0 occorrenze nel ledger) | **GROW probabilmente dannosa.** Fatto 4: l'incastro è statico e tutto il consumo è al decode-start; GROW sposta lì la misura di `free_b` e sceglierebbe un N **più alto** — che è esattamente ciò che il gestore elastico ha già fatto (189 slot) provocando ~1.126 sfratti/token. Provarla solo con la clausola "se sceglie >140, abortire" |
| 11 | `DS4_METAL_GRAPH_RAW_CAP` | ATLAS §1#11, §2.1 | **MAI** | Bassa. Serviva a isolare la leva #1 dalla geometria KV, problema che il fatto 3 ha già chiuso per altra via |
| 12 | `DS4_CUDA_MOE_DIRECT_CACHE_HITS` | ATLAS §1#12, §3; POST Top-10 #9 | **MAI** ma **misurata inutile**: ledger 17161 riporta `all_hit=0` nelle run strumentate | **MORTA per aritmetica e per misura.** Richiede layer con 6/6 esperti residenti; a `hit_rate` 0,25-0,30 sono ~0,06% dei layer, e il contatore dice zero. Il "−1,6 GiB/token D2D" non esiste su questa config |
| 13 | `DS4_G73_PAGEABLE_OVERFLOW_GB` | ATLAS §1#13; POST §1.1 `[CONFERMATA]`; RIC "già 0" | **CHIUSA**: 14 GiB peggiorava 2,41 → 2,07 t/s; oggi 0 | Riga dell'Atlante **stantia**: la descriveva come "attiva in produzione, mai isolata". È stata isolata e spenta |
| 14 | `DS4_CUDA_MOE_IO_QD` | ATLAS §1#14, §3; POST Top-10 #6; RIC "vecchio path non utile" | **FALS** — Add.43b: il disco **non scala con la profondità di coda** (4 stream = 1,38 GB/s vs 1 stream 1,45) e il runtime è già al 70-100% di ciò che il disco consegna | **MORTA.** Uccisa due volte: dal disco (nessuna banda sbloccabile) e dal fatto 1 (agirebbe sull'11%) |
| 15 | `think:false` / MTP morto per default | ATLAS §1#15, §2.8; POST §1.10; RIC "MTP vero: il runner usa `--mtp-draft 1`" | **MAI provato davvero.** Il GGUF MTP locale è **verificato** (RIC) | **La leva più grossa rimasta** — vedi B-1. È l'unica che divide il **costo fisso per token**, non una sua frazione |

## A.2 — Il "tesoro nascosto" dell'Atlante §3, rivalutato

| Leva | Stato oggi | Verdetto |
|---|---|---|
| Le 5 sonde `_STAGE_PROFILE` | `DECODE`/`LAYER`/`Q`/`INDEXER` **MAI**; `GRAPH_TOKEN` usata | **B-2.** L'unica strada per attribuire i 240 ms. Costo zero, rischio zero |
| `PREFILL_CHUNK=768 @ctx8192` | Superata dal regime: oggi 250 @150k | Riqualificare come A3 250 vs 600 **a 150k** (C-3) |
| `KV_MANAGED=1` | FALS (advise fallisce su WDDM) | Morta |
| `TOKEN_SPLIT_LAYERS=0` | FALS (Add.43b) | Morta |
| `EXPERT_CACHE_GROW` + `RELEASE_PREFILL_SCRATCH` | Metà attiva, metà rischiosa | Vedi A.1 #10 |
| `MOE_DIRECT_CACHE_HITS=1` | `all_hit=0` misurato | Morta |
| `MOE_IO_QD=2/4` | FALS dal benchmark disco | Morta |
| `DS4_G132_CPU_LANE=1` | **MAI** (0 occorrenze nel ledger) | **Uccisa dal fatto 1.** Dequantizza IQ2 su CPU in parallelo: agisce dentro i 40 ms del percorso esperti, e compete con l'unico route worker. Tetto <40 ms, costo un thread pool. Scartare |
| `DS4_MTP_BATCH_VERIFY` + `think:false` | **MAI** | **B-1.** Unica leva sul costo fisso |
| `EXPERT_TIER_ADAPTIVE_BUDGET` + 4 param | FALS (muove `replacement_budget`, non `g133_promote_budget`) | Morta per costruzione |
| `MOE_CACHE_POLICY=layer-top1` | MAI, e spegne il resolver GPU-resident | Trappola. Non toccare |
| `PREFILL_MASS_LAYER_FULL_EVERY` | **MAI** (0 occorrenze) | Bassa: policy di residenza alternativa, ma il fatto 3 dice che il numero di slot non è la variabile libera |
| `DS4_G73_ALLOW_Q1_SIDECAR` | **MAI** (0 occorrenze) | Fuori dalla linea velocità. Appartiene alla traccia Q1/qualità |
| `NO_INDEXER_DIRECT_ONE` / `NO_INDEXER_WMMA` / `NO_TOPK*` | MAI | **Inerti a `pos=873`** (fatto 7). Due sono trappole. Rimandare al regime KV profonda |

## A.3 — Le costanti hardcoded dell'Atlante §4

| Costante | Verdetto oggi |
|---|---|
| `DS4_N_INDEXER_TOP_K = 512` | **Ancora la più calda**, ma solo oltre `pos=2051`. Vedi B-4 |
| `2048` in `ds4_default_prefill_cap_for_prompt` | Neutralizzata: il preset passa 250 esplicitamente |
| `cudaMallocManaged` incondizionato | Parzialmente affrontato da `GRAPH_TENSOR_DEVICE` (A/B **neutro**, +0,095%). Il fatto 3 spiega perché: i 42-96,7 MiB recuperati non sono convertibili in slot |
| `cudaDeviceSynchronize()` in `ds4_gpu_tensor_contents` / `split_after_layers=4` | Il secondo è falsificato; il primo mai isolato ma dentro i ~2 ms di `execute` |
| `cudaStreamSynchronize(0)` per layer nel resolver | Già disattivato (`NO_DEFAULT_SYNC=1`) |
| `moe_resolve_resident_routes_kernel<<<1,1>>>` ×40/token | Vivo. **Non ancora attribuito**: candidato del "buco" (D-H3) |
| FNV-1a byte-per-byte su 7 MB a ogni ammissione, mai riletto | ~8-12 ms per ammissione, seriale, nel route worker ⇒ **dentro `worker_wait_ms`**. Vivo e ora indiziato dal fatto 5. Non è una env: serve una patch |
| Doppia memcpy 6,75 MiB per sostituzione slot | Idem, dentro il worker |
| Scansioni lineari senza indice (`pick_ram_slot`, `expert_cache_find`) | Idem. Ipotesi F dell'Atlante: **strutturalmente invisibile** perché gira su thread diverso. Oggi `worker_wait_ms` la rende **visibile in aggregato** |
| `chunk = 1 MiB` in `os_pread_cancellable_timeout` | **Affrontata da PREP-6** (`ROUTE_READ_WHOLE`: 9 → 3 pread/esperto, verificato attivo). Misura sporca (−5,1%) |
| `CreateEventW` per ogni `os_pread` | Vivo, dentro il worker |
| `SSD_RING_SLOTS=2`, `H2D_RING_SLOTS=2` | Vivo; le env `SSD_WRAP_*` restano decorative |
| Upload dell'intera mappa slot (44 KB) per layer con admission | ~1,7 MB/token H2D sincronizzante. Dentro i 40 ms |
| `completion == 64` per il summary | Trappola d'harness, non di runtime |

## A.4 — Famiglie compresse (nessun verdetto individuale, sono rumore o morte)

| Famiglia | Verdetto |
|---|---|
| ~26 var geometria kernel `MOE_{TILE4,GATE_ROW*,DOWN_ROW*,ATOMIC_DOWN,NO_*}` + ~10 `DISABLE_*_FUSION` | Rumore. Fatto 1: agiscono su una frazione dell'11% |
| `DS4_IQ1_S_*`, `DS4_IQ1_MIXED_*`, `DS4_NESTED_RESIDUAL_*`, matrice Q1_0 a 7 booleani, `Q1_0_IQ2_PINNED_*`, `Q1_0_SSD_WRAP_*` | Inerti su IQ2 puro |
| `DS4_SPEX_*` | MORTA-COSTR: `EXPERT_CACHE_N≠0` disabilita la claim. E il fatto 1 la confinerebbe comunque nei 40 ms |
| `DS4_CUDA_REAP_MASS_*` | MORTA-COSTR: l'observer rifiuta il resolver GPU-resident (`cu:37257`). Comporlo = rebuild |
| `G133_KNOCK_X/Y`, `G133_PROMOTE_BUDGET`, `G133_DECAY`, `EXPERT_TIER_HYSTERESIS` | Morte/capacity-bound. Il fatto 3 chiude definitivamente il capacity-bound |
| `KEEP_MODEL_PAGES`, `NO_DIRECT_IO`, `NO_MODEL_PREFETCH`, `MODEL_PREFETCH_SYNC` | No-op su Windows |
| `MODEL_SHA256`, `*_SIDECAR_SHA256`, `MODEL_BYTES` | Provenance, nessun hash calcolato |
| `--kv-*` (KV su disco), G133 a 2²⁰, allineamento 2048 | Tetti irrilevanti |
| `NO_TOPK2048`, `NO_TOPK_CHUNKED`, `MOE_NO_SELECTED_LOAD`, `NO_DECODE_LUT_GATE`, `NO_DIRECT_DOWN_SUM6`, `CACHE_POLICY=layer-top1`, `ATTENTION_OUTPUT_PRELOAD`, `MTP_SPEC_DISABLE=0` | Trappole confermate |
| `DS4_CUDA_MOE_CACHE_POLICY=lru` | Valore **non riconosciuto** dal parser = no-op identico a unset. **Igiene: rimuovere la riga dai preset** |

## A.5 — Leve NON nell'Atlante, nate dopo, già in produzione o in flag

L'Atlante è del 24/7. Queste sono nate dopo e vanno **aggiunte** a qualunque revisione dell'inventario:

| Leva | Origine | Stato |
|---|---|---|
| `DS4_CUDA_STREAM_HOT_RESERVE_MB` | patch indexer Codex 25/7; **presente in `ds4-p4a/ds4_cuda.cu:6810`** | Ha portato 4000/4000 a freddo superando il cliff a `pos=2051`. **Mai A/B sul binario corrente**, mai a 150k. Vedi B-3 |
| `DS4_CUDA_ROUTE_READ_WHOLE` / `_PREFETCH_HINT` | PREP-6, 27/7 | WHOLE verificato attivo (`preads_per_expert=3`), misura **sporca** −5,1%. HINT mai provato |
| `DS4_CUDA_EXPERT_ZEROCOPY` (0/1/2) | P.5a, 27/7 | **FALS** (fatto 2). Resta OFF |
| `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE` / `_MAX_FALLBACKS` | fix (b), 28/7 | A/B **neutro** (+0,5%), criterio 1 **non verificato**: zero raffiche incontrate, 0 fallback scattati |
| `DS4_CUDA_SLOW_TOKEN_LOG` / `_MS` | fix (b), 28/7 | Nuova. **Sottoutilizzata**: default 1500 ms la fa scattare solo sulle raffiche. Vedi D-H1 |
| `DS4_CUDA_VRAM_PRIO_LOG_EVERY_TOKENS` | fix (b), 28/7 | Ha prodotto il fatto 4 |
| `DS4_CUDA_VRAM_*` (inverted priority, elastic, `MIN_EXPERT_SLOTS`, `EXPERT_SHIELD_TICKS`, `ELASTIC_MAX_SLOTS`) | gestore VRAM, 27/7 | Il gestore **funziona dove può e non basta**: 189 slot, sfratti in caricamento 768→8, ma in decode ~1.126/token identici. Uccise dai fatti 3+4 |
| `DS4_CUDA_G73_ROUTE_IO_QD` | P3-B | Path exact-decode distinto dal vecchio `MOE_IO_QD` |

---

# B. LEVE MAI PROVATE CHE RESTANO PLAUSIBILI

Ordinate per **impatto atteso sul numero che attaccano**. Il numero di riferimento è il token da
**~222-282 ms su macchina fresca** (221,8 ms best, 275,2-283,6 ms dopo 3 ore di uptime), di cui ~40 ms
sono percorso esperti e **~240 ms non sono attribuiti a nulla**.

### B-1. `DS4_MTP_BATCH_VERIFY` + `--mtp <gguf>` + `--mtp-draft 2` + `think:false` + `temperature=0`

**Numero attaccato: l'intero costo fisso per token (~240 ms), non una sua frazione.** È l'unica leva
dell'inventario che non prova a rendere più veloce il token, ma a **produrne due per volta**.

*Meccanismo.* Il token è latency-bound a profondità effettiva ~1 (audit S: ~287 kernel di solo controllo,
43 rendezvous, 603 submission H2D, 819 pread per token). Un verify batch a `draft_n=2` paga il costo di
orchestrazione **una volta** per due posizioni candidate. Aritmetica esplicita, dichiarata come proiezione:
costo fisso ~240 ms + percorso esperti che raddoppia (40 → ~80 ms) = ~320 ms per batch; con accettazione
`p`, ms/token accettato = `320/(1+p)`. A `p=0,5` → 213 ms = **4,7 t/s** contro 3,56 (+32%); a `p=0,8` →
178 ms = **5,6 t/s**. È l'unico percorso aritmetico verso il gate utente da 5 t/s che non richieda di
spiegare i 240 ms.

*Perché non è mai stata provata.* Tre precondizioni che non si sono mai verificate insieme: il runner usa
`--mtp-draft 1` (nessuna speculazione), il think mode è ON di default e sovrascrive `temperature=1.0`
annullando la condizione `temperature<=0`, e `--mtp <file>` non era caricato. Il GGUF MTP locale è
**verificato** (riconciliazione 26/7).

*Rischi dichiarati.* (a) `--mtp-draft` è clampata a 16 ma il buffer reale è `toks[17]`; a 2 è irrilevante.
(b) `think:false` cambia il carico: il confronto va fatto **think:false contro think:false**, mai contro
la baseline think-on. (c) Se l'accettazione è <0,25 la leva è neutra o negativa.

*La misura che la uccide.* Un solo run: se il tasso di accettazione osservato è <0,25, chiudere.

### B-2. Le quattro sonde `_STAGE_PROFILE` mai accese, in un solo run a 150k

**Numero attaccato: i ~240 ms non attribuiti — per attribuzione, non per riduzione.**

*Meccanismo.* `DS4_METAL_DECODE_STAGE_PROFILE=1` + `DS4_METAL_LAYER_STAGE_PROFILE=1` +
`DS4_METAL_Q_STAGE_PROFILE=1` emettono `metal layer stage part=decode|attn name=… il=… pos=…` per ogni
boundary di stadio dentro il layer. È **l'unica** strumentazione che separa attention / HC / norm / router
/ shared / routed dentro l'`encode`. Verificato che non è mai stata accesa: il manifest 47 ha
`GRAPH_TOKEN_PROFILE=1` ma non `DECODE_STAGE_PROFILE`, e il log non contiene record `metal layer stage
part=decode` (ledger 16509-16517, che dichiara esplicitamente: "non esiste nei dati consegnati una durata
reale dello shared expert o dell'attention").

*Caveat non negoziabile.* Ogni boundary sincronizza. Il run serve ad **attribuire**, mai a dichiarare t/s.
Precedente storico: un run profilato girò 6,5× più lento del non profilato.

*La misura che la uccide.* Nessuna: è una sonda, non un'ipotesi. Ma se la somma degli stadi copre <60% di
`total_ms`, il tempo è fuori dal grafo (driver, worker, host) e serve un'altra sonda.

### B-3. `DS4_CUDA_STREAM_HOT_RESERVE_MB=256` a KV realmente profonda

**Numero attaccato: il cliff a `pos=2051` (22.791 ms sul primo token) e gli ~85-90 ms/token permanenti
dell'indexer.** Cioè il costo che il gate utente pagherà e che noi non abbiamo mai misurato (fatto 7).

*Meccanismo.* Le quattro matmul F16 dell'indexer si accendono a `n_comp>512` e spingono il working set
denso oltre il reserve della cache VRAM: da lì l'LRU ricarica quasi tutto ad ogni token (`fd-cache load 0 →
1.066`, `evictions 0 → 1.098`, ~6,7 GiB caricati per token). La patch etichetta **solo** quelle quattro
matmul (`indexer_f16`) e concede loro un reserve separato. Senza la variabile il comportamento è identico.

*Stato.* La leva **esiste nel binario corrente** (`ds4-p4a/ds4_cuda.cu:6810`) — verificato. Il suo unico
successo (4000/4000 a freddo) fu su un binario diverso (`320A0A…`) con un confondente dichiarato nel
ledger stesso ("i due binari non differiscono soltanto per `STREAM_HOT_RESERVE`").

*La misura che la conferma.* Un run con prompt reale lungo oltre `pos=2051`, OFF vs ON, guardando
`[vram-prio] evicts_total` e il `total_ms` dei token 2050-2055. Se ON tiene gli `evicts` piatti attraverso
il confine, chiuso.

### B-4. Rendere `DS4_N_INDEXER_TOP_K` una env (rebuild da 3 righe) — **solo dopo B-3**

**Numero attaccato: gli ~85-90 ms/token permanenti dell'indexer.** Alzando il valore sopra `ctx/4` il ramo
non si accende mai: è il test diretto di quanto costa l'indexer, senza confonderlo col reserve. Lo stub
`metal_graph_decode_indexer_top_k(g)` accetta `g` e lo scarta: la mezza leva è ancora lì (verificato oggi
su `ds4.c:11023`). *Attenzione*: cambia la semantica del modello (top-k dell'attention indicizzata), quindi
è un esperimento di **attribuzione**, non una configurazione servibile.

### B-5. `CACHE_N` **verso il basso** (140 → 120 → 100) — la direzione che nessuno ha provato

**Numero attaccato: gli 0,90-0,98 sfratti di backbone per token che restano anche a cache 140.**

*Meccanismo.* Tutta la campagna ha esplorato 140 → 189 → 320, cioè **verso l'alto**, e ha trovato il muro.
Nessun braccio è mai sceso sotto 140. Il fatto 3 dice che 140 è il tetto; non dice che è l'ottimo. A 140 il
sistema sfratta ancora ~750 backbone per run. Ogni slot rimosso libera 6,75 MiB. La scommessa è
**asimmetrica**: si rinuncia a una parte di un affare che vale l'11% del token (fatto 1) per eliminare un
costo che vive dentro l'89% non spiegato.

*Costo del sacrificio, quantificato.* Da 140 a 100 slot il miss rate sale di ~12 esperti/token; a 0,321
ms/expert (banco kernel vero, K6) sono **~3,9 ms/token** di costo certo.

*La misura che lo uccide.* `backbone_reload_bytes / tokens` dalla riga `[vram-prio]`. A ~22 GB/s
misurati, se il reload è <200 MiB/token il beneficio massimo è <9 ms e la leva non vale i 3,9 ms del
sacrificio: chiudere. Se è >1 GiB/token, è una delle voci grosse del buco.

### B-6. `DS4_CUDA_ROUTE_READ_WHOLE=1` rimisurata su macchina fresca (ABBA)

**Numero attaccato: `worker_wait_ms`, cioè il 95% delle raffiche (fatto 5) e una quota ignota dei token
normali.** Non è una leva di banda (il disco non ha headroom, Add.43b) ma di **numero di round-trip**: 9 →
3 pread per esperto, con lo stesso staging e zero byte in più. Il fatto 1 le mette un tetto (i 40 ms), ma
il fatto 5 dice che l'attesa del worker è il meccanismo delle raffiche, e le raffiche costano ~30% del
tempo reale che la mediana non vede (A_anchor: 31 token oltre 1,5 s per 75,7 s totali).

*Stato.* Attiva e verificata (`preads_per_expert=3`), ma la sola misura esistente (−5,1%) è **sporca**
(secondo braccio di una catena in deriva). `DS4_CUDA_ROUTE_PREFETCH_HINT` mai provata, da isolare dopo.

### B-7. `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1` in un run che incontri davvero una raffica

Non è una leva di velocità: è un **cambio di modalità di guasto**. Il criterio 2 (costo) è superato
(+0,5%, neutro). Il criterio 1 (recupero) è **non verificato**: zero raffiche in entrambi i bracci, 0
fallback scattati. Va tenuta OFF finché un run non ne incontra una — e allora è l'unica cosa che
trasforma un abort in una degradazione.

---

## B-bis. Scartate esplicitamente, con il fatto che le uccide

| Leva mai provata | Fatto che la uccide |
|---|---|
| `DS4_G132_CPU_LANE=1` | **Fatto 1.** Dequant IQ2 su CPU agisce dentro i 40 ms; e `cores-2` worker competono con l'unico route worker, che è dove vive `worker_wait_ms` |
| `DS4_CUDA_MOE_DIRECT_CACHE_HITS=1` | **Fatto 1** + `all_hit=0` misurato. Il beneficio promesso (−1,6 GiB/token D2D) richiede layer 6/6 residenti che non esistono a `hit_rate` 0,29 |
| `DS4_CUDA_MOE_IO_QD=2/4` | **Fatto 1** + benchmark disco (nessuna banda con più QD) |
| `DS4_CUDA_KV_MANAGED=1` | Advise **fallisce a runtime** su WDDM + ring staged attivo rende il ramo irraggiungibile |
| `DS4_CUDA_EXPERT_CACHE_GROW=1` | **Fatto 4**: l'incastro è statico; GROW sposta la misura di `free_b` esattamente all'istante in cui il consumo è già avvenuto e sceglierebbe N>140, cioè il regime della tempesta |
| `DS4_METAL_GRAPH_RAW_CAP`, `PREFILL_VRAM_SEED_*`, `STREAMING_EXPERT_CACHE_RESERVE_GB` in salita | **Fatto 3**: nessuna VRAM è convertibile in slot |
| `DS4_CUDA_NO_Q8_F16_CACHE` e famiglia disattivazioni attention | **Fatto 3**, testato: Test (a) FALSIFICATO — stessa tempesta (1.143 sfratti/token), sizing invariato 320/320 |
| `DS4_CUDA_REAP_MASS_*`, `DS4_SPEX_*` | MORTA-COSTR (rifiutano il resolver GPU-resident / disabilitate da `CACHE_N≠0`) + fatto 1 |
| `EXPERT_TIER_ADAPTIVE_BUDGET`, `G133_PROMOTE_BUDGET`, `G133_KNOCK_*` | **Fatto 3**: sono tutte a valle di un capacity wall aritmetico |
| Alzare `TRANSIENT_IO_TIMEOUT_S` a 2-10 s | **Fatto 6**: misurato peggiore (+27%, 40 stalli) |
| `PREFILL_MASS_LAYER_FULL_EVERY`, `ARENA_WRAP_FILE_QD`, `SEQUENTIAL_FILE` | Fatto 1 + benchmark disco. L'unica strada TTFT residua è "leggere meno byte" (P4 write-through), che è codice, non una leva |

---

# C. LEVE DA RIQUALIFICARE

Verdetti storici emessi in condizioni che ora sappiamo sbagliate.

### C-1. `DS4_EXPERT_TIER_MIN_FREQUENCY` — **l'Atlante dice MORTA, la campagna la misura ATTIVA**

POST §1.5 la classifica `[MORTA]`: "saltata dal ramo G133, pur essendo loggata come attiva". Ma la campagna
1 riporta come **valido e immune alla deriva** (sono contatori, non tempi): con `MIN_FREQUENCY=2` i
campioni con ≥1 promozione salgono dal **25,5% al 41%** e l'hit rate dal **25,6% al 30,2%**, con un prezzo
di +41% sfratti di range (0,95 → 1,34/token). O l'Atlante ha sbagliato la lettura del gate, o il ramo è
cambiato con `G73_OPEN=0`. **È l'unica leva di tiering con un meccanismo misurato in questa campagna, ed è
etichettata morta nel documento che usiamo per decidere.** Priorità di riqualificazione: alta, costo un
braccio su macchina fresca. Attenzione al fatto 1: +4,6 punti di hit rate valgono ~9 esperti/token ×0,321
ms ≈ **3 ms**, contro +0,39 sfratti/token di costo. Rischia di essere un pareggio: misurare entrambi i lati.

### C-2. `DS4_G73_OPEN` — il 7,8× non è mai stato riprodotto

ATLAS §1 e POST §1.1 lo danno come `[RIBALTATA]` con 0,62 → 4,85 t/s. La riconciliazione: "il vecchio 4,85
con `G73_OPEN=0` non si riprodusse sul binario successivo (2,19 contro 2,41 open/pinned)"; A2 "non è
validabile col runner corrente: il manifest fissa OPEN=1, il gate D2H è incompatibile con OPEN=0 e un
fallimento finale del rotatore può false-pass". In più il ledger (riga 5166) registra che l'8× era
**confuso** con `TOKEN_SPLIT_LAYERS=0`. Oggi il manifest batch-12 ha già `DS4_G73_OPEN=0`. **Il numero
7,8× va cancellato dall'Atlante**: è un'osservazione di binario, non una baseline.

### C-3. `DS4_METAL_PREFILL_CHUNK` — meccanismo diverso da quello documentato

L'Atlante lo spiega come "~1,3 GB di `batch_*` managed" (ipotesi A del §6). La spiegazione vera, emersa il
27/7, è **quanta VRAM resta alla cache esperti**: a ctx8192 chunk 2048 → context buffers 333 MiB → cache
133/320 → 0,51 t/s; chunk 600 → 175/320 → 3,19 t/s. Sotto il fatto 3 quella catena causale **non è più
disponibile a 150k** (gli slot non salgono comunque). Resta da misurare l'altro lato: chunk 250 → 600
libera ~462,7 MiB che potrebbero ridurre gli sfratti di backbone. **A3 a 150k mai eseguita.**

### C-4. `DS4_G133_TRANSIENT_IO_TIMEOUT_S` — da "inerte" a leva primaria della coda, con segno invertito

POST §1.5: `[CONFERMATA] — inerte senza KV_STAGED_RING`. Il ring **è attivo** nella ricetta 150k, quindi la
leva è viva. E il segno è opposto all'intuizione: 0,25 s → 0 stalli / 221,8 ms; 10 s → 40 stalli / 281,0 ms
(+27%). Inoltre ha **cancellato in silenzio una classe di leve dallo spazio di ricerca**: tre bracci
(zero-copy, PREFETCH, TIERFREQ2) sono stati uccisi da `reason=transient-io-timeout` → `cuda decode failed`.
**Ogni verdetto negativo su una leva che rallenta un layer va riletto: potrebbe essere il guardiano, non la
leva.**

### C-5. Tutti i tempi dei bracci successivi al primo, in ogni catena

Fatto 8, quantificato tre volte: 363,4 → 619 ms in una serata (macchina sporca, RAM libera 1 GiB); 363,4 →
221,8 ms al riavvio (−39%); 221,8 → 275,2 ms dopo 183 minuti di uptime con shutdown sempre grazioso
(+24%). Sono **non validi come grandezza**: WHOLE −5,1%, TIERFREQ2 −32%, l'intera matrice M0-M4 (M2
+7,31% "sotto la soglia utente del 10%, quindi varianza"), i confronti M5/A1. **Restano validi solo i
contatori.** Regola operativa già dettata: baseline prima di **ogni** braccio, massimo ~3 bracci per
sessione, shutdown via endpoint.

### C-6. `DS4_CUDA_STREAM_RESERVE_MB` — mai A/B con il contatore che ora esiste

ATLAS §1#5: "provata come parametro, mai come causa"; l'ipotesi D del §6 (ciclo di eviction in
`cuda_model_stream_alloc`) era "totalmente non strumentata". Oggi lo è: `[vram-prio]` conta
`evict_backbone`, `backbone_evicted_bytes`, `backbone_reload_bytes`, `backbone_reloads`. E il numero non è
zero neanche nel regime buono (0,90-0,98/token). **L'ipotesi D non è mai stata chiusa, è stata dimenticata
quando il regime è cambiato.**

### C-7. `DS4_CUDA_KV_STAGED_RING` — da "mai testata, con bug" ad "attiva, mai isolata"

POST §1.3: `[MAI-TESTATA-PROMETTENTE] con BUG` (illegal-memory sul restore a big-ctx). È **nella ricetta
150k validata** (`ring on`). Non è mai stata isolata in un A/B on/off sul binario corrente, e nel frattempo
è diventata la ragione per cui `KV_MANAGED` è irraggiungibile e per cui `TRANSIENT_IO_TIMEOUT_S` è viva.
Riga dell'Atlante da riscrivere.

### C-8. L'intero §6 dell'Atlante ("CACCIA APERTA: cosa scala col ctx") va archiviato

Il fatto da spiegare era "204 ms/token a ctx768 → 1776 ms/token a ctx8192". È **spiegato**: chunk di
prefill che divora la VRAM della cache esperti. Le ipotesi A/B/C/D/E/F/G/H/I di quel capitolo sono state
formulate su un regime (ctx8192, chunk 2048, CACHE_N=320, `pos` bassa) che non è quello del gate. In
particolare l'ipotesi **C (residenza managed su WDDM come moltiplicatore ~100×) è falsificata** da due
misure indipendenti: il microbench zero-copy mostra WDDM al 98,2% del picco PCIe sulla lettura mapped, e la
parità Linux nativo (encode ~390 ms vs execute ~2 ms, stessi t/s senza WDDM) esclude l'OS. **Chi legge
l'Atlante oggi trova un capitolo di 9 ipotesi di cui almeno 5 sono chiuse e nessuna è marcata come tale.**

### C-9. `DS4_CUDA_GRAPH_TENSOR_DEVICE` — chiudere formalmente

A/B valido su P0.1: `weighted_delta=+0,095%`, `performance=NEUTRAL_VARIANCE`, `promotion=NO`, con 42,0-96,7
MiB recuperati al decode-start. Il fatto 3 spiega **perché** è neutra: quei MiB non sono convertibili in
slot. Non è "da riprovare": è chiusa.

### C-10. Igiene di preset dichiarata e mai eseguita

`MOE_CACHE_POLICY=lru` (valore invalido, no-op) ancora nei preset; `EXPERT_TIER_MIN_FREQUENCY=3` +
`HYSTERESIS=1.25` dichiarate inerti ma lasciate; `Q8_F16_CACHE_RESERVE_MB` inerte sotto `NO_Q8`; e la
trappola operativa `g7_measure.ps1:3103-3108` che **cancella tutte le `DS4_*`** prima di lanciare il
server, rendendo nullo il dot-sourcing del preset. Nessuna di queste è stata sistemata in quattro giorni.

---

# D. IL BUCO — dove stanno i ~240 ms/token

**Il bilancio, su macchina fresca (221,8 ms best / 275,2-283,6 ms tipico):**

| Voce | ms/token | Come lo sappiamo |
|---|---|---|
| Consegna esperti (`t_deliver`, enqueue H2D) | 3,6 | contatore `[zc]`, campagna 1 |
| Orchestrazione esperti (`t_orchestration`, drain incluso) | 36,5 | contatore `[zc]`, campagna 1 |
| Costo dati totale al miss rate attuale (banco kernel vero, K6) | ≤60,5 | `.microbench/iq2_kernel` |
| **Non attribuito** | **~180-240** | residuo |
| Indexer | **0** | fatto 7: `pos=873 < 2051`, il gate non scatta |
| Crescita del backbone | **0** | fatto 4: 0,00 MiB/token su 15 campioni |
| Sfratti come causa delle raffiche | **0** | fatto 5: `evict_backbone_delta=0` nelle raffiche |

Quattro prove indipendenti dicono che **il movimento dati non è mai stato il collo**: parità Linux nativo,
attribuzione encode/execute (390 vs 2 ms), banco int8, banco IQ2 col kernel vero. Il residuo è **tempo
dell'host**: polling, API CUDA bloccanti, rendezvous, lanci.

## Ipotesi verificabili con la strumentazione che già esiste

### D-H1. È attesa del route worker anche sui token NORMALI, non solo nelle raffiche

*Meccanismo.* Il fatto 5 dice che nelle raffiche `worker_wait_ms` è il 95% di `total_ms`. Nessuno ha mai
guardato quel rapporto sui token normali, perché `DS4_CUDA_SLOW_TOKEN_MS` vale 1500 di default e la riga
non viene emessa. Se il rapporto è ~40% anche a 280 ms, allora ~110 ms/token sono rendezvous con il worker
— e la conclusione "il percorso esperti è l'11%" è **vera per il costo di consegna e falsa per il costo di
attesa**: `t_orchestration_ms` misura l'enqueue, non il tempo passato ad aspettare.

*La singola misura.* `DS4_CUDA_SLOW_TOKEN_LOG=1` con **`DS4_CUDA_SLOW_TOKEN_MS=1`** ⇒ la riga esce su ogni
token. Mediana di `worker_wait_ms / total_ms` su 800 token.
**Conferma** se >0,30. **Uccide** se <0,08: allora il worker non è il buco e va cercato nel grafo (D-H2).

*Corollario gratis nello stesso run.* La stessa riga dà `pread_calls`, `pread_bytes` e `transient_serves`
per token: si ottiene simultaneamente il numero di round-trip I/O per token normale (atteso ~819 pread
prima di PREP-6, ~273 dopo) e il conto della deriva (D-H5).

### D-H2. È dentro il grafo, in uno stadio che non abbiamo mai separato

*Meccanismo.* `encode` contiene tutto (polling CPU, API bloccanti, I/O, H2D/D2H, dipendenze fra stream), e
`execute` è solo il drain finale. Il vecchio sillogismo "encode=98,6% quindi WDDM escluso" è già
falsificato nel ledger. L'unica scomposizione mancante è per **stadio di layer**.

*La singola misura.* `DS4_METAL_DECODE_STAGE_PROFILE=1` + `_LAYER_STAGE_PROFILE=1` su ~50 token a 150k.
**Conferma** che il buco è nel grafo se la somma degli stadi copre >80% di `total_ms` **e** un singolo
stadio (attention, HC, router, shared) supera il 25%. **Uccide** l'ipotesi se la somma degli stadi copre
<50%: allora il tempo è fuori dal grafo (worker, driver, host loop) e si torna a D-H1.

### D-H3. È il numero di lanci di controllo, non il lavoro

*Meccanismo.* Audit S, per token: 43 router-select + 43 resolver residenti + ~201 kernel di pubblicazione +
`moe_resolve_resident_routes_kernel<<<1,1>>>` ×40 = **~287 kernel di solo controllo**, più 43
chiusure/drain e ~603 submission H2D. Il dato Linux più netto in tutto il ledger: packed-copy +
batched-publish riducono le submission di **8,7×** e il t/s **peggiora** (1,80 vs 2,54) ⇒ "il collo è il
**rendezvous per layer**, non il numero di submission". A ~0,5-1 ms per rendezvous, 43/token = 21-43 ms.

*La singola misura.* Dallo stesso run di D-H2: il tempo attribuito allo stadio "router/resolver/publish"
sommato sui 43 layer. **Conferma** se >40 ms/token. **Uccide** se <10 ms/token.

### D-H4. È il ri-streaming del backbone, che non è mai stato convertito in millisecondi

*Meccanismo.* Anche nel regime buono (CACHE_N=140) restano 722-781 sfratti di backbone per run =
0,90-0,98/token. Nessuno ha mai moltiplicato quel numero per i byte. La riga `[vram-prio]` espone
`backbone_reload_bytes` e `backbone_reloads`, ma nel ledger sono sempre citati gli **eventi**, mai i
**byte**.

*La singola misura.* `backbone_reload_bytes / tokens` dalla riga `[vram-prio] phase=request-end`, diviso
22 GB/s (banda H2D misurata, K6). **Conferma** se >50 ms/token equivalenti. **Uccide** se <10 ms/token — e
in quel caso uccide anche B-5, perché il sacrificio di slot non comprerebbe nulla.

### D-H5. È deriva mascherata da stato stazionario

*Meccanismo.* Fatto 8: −39% al riavvio, +24-25% dopo 3 ore. La causa proposta nel ledger è la cache file
che smette di tenere il modello: letture prima servite dalla RAM finiscono su SSD. Se è così, una parte
variabile del "buco" **non è runtime**: è I/O che riappare.

*La singola misura.* `pread_bytes / token` dalla riga `[slow-token]` a `SLOW_TOKEN_MS=1`, confrontato fra
macchina appena riavviata e stessa config dopo 2-3 ore. **Conferma** se cresce di >2×. **Uccide** se resta
piatto: allora la deriva è altrove (frammentazione dell'arena, working set, termico) e va cercata con
`[vram-prio]` + contatori di sistema.

### D-H6. Il buco è stato misurato nel regime sbagliato (non è un'ipotesi: è un errore di campionamento)

Fatto 7. A `pos=873` l'indexer è spento, la KV è corta, l'attention lavora su 873 posizioni ma con buffer
dimensionati per 150.000. Tutto ciò che sappiamo dei 240 ms vale per quel punto. Il ledger documenta che
**oltre `pos=2051` si aggiungono ~85-90 ms/token permanenti** più un cliff da 22,8 s. Nessun run con prompt
lungo vero è mai stato eseguito.

*La singola misura.* Un run con prompt reale da decine di migliaia di token, con
`DS4_CUDA_VRAM_PRIO_LOG_EVERY_TOKENS=32` e `DS4_CUDA_SLOW_TOKEN_LOG=1`. **Conferma** che il regime del
gate è diverso se `total_ms` mediano oltre `pos=3000` supera del 30% quello a `pos<2000`. È il
prerequisito di qualunque dichiarazione sul gate a 5 t/s: **finché non esiste, non stiamo misurando il
problema dell'utente.**

### D-H7. Il picco intra-token di VRAM (l'unico residuo aperto del fatto 4)

Fatto 4, caveat: restano 1083 MiB liberi in stazionario che **non sono utilizzabili** (con 189 slot, +331
MiB, la tempesta scoppia). Esiste quindi un picco intra-token che il campionamento a fine token non vede.

*La singola misura.* Bisezione su `CACHE_N` (140, 150, 160, 170) leggendo `evict_backbone` per token da
`[vram-prio]` a `LOG_EVERY_TOKENS=1`. Il picco, espresso in slot, è il valore al quale il contatore salta
di un ordine di grandezza. **Conferma** l'esistenza del picco se la transizione è netta (binaria).
**Uccide** l'idea di un picco se la crescita è graduale: allora è saturazione, non picco.

## Ordine di esecuzione consigliato

Un solo run copre D-H1, D-H4, D-H5 e metà D-H7 (`SLOW_TOKEN_LOG=1`, `SLOW_TOKEN_MS=1`,
`VRAM_PRIO_LOG_EVERY_TOKENS=32`, tutto il resto invariato, macchina appena riavviata, baseline in testa).
Costo zero, nessuna perturbazione dichiarata. **Fare questo prima di qualunque leva.** Poi B-2
(attribuzione per stadio, run separato perché perturba). Poi D-H6, che è il run che ci dice se abbiamo
inseguito il problema giusto. Solo dopo B-1 (MTP), che è l'unica leva con un'aritmetica che arriva a 5 t/s.

---

## Nota di metodo

Tre pattern ricorrenti che questa revisione documenta e che valgono più di ogni singola leva:

1. **Il documento di riferimento invecchia più in fretta della campagna.** L'Atlante ha 4 giorni e contiene
   già: una leva morta presentata come promettente (`KV_MANAGED`), una morta presentata come attiva
   (`PAGEABLE_OVERFLOW=14`), una attiva presentata come morta (`MIN_FREQUENCY`), un capitolo di caccia
   (§6) chiuso e non marcato, e un moltiplicatore (WDDM managed) falsificato da due misure.
2. **Ogni verdetto negativo va riletto contro il guardiano.** Tre bracci sono stati uccisi da
   `TRANSIENT_IO_TIMEOUT_S=0.25` prima di produrre un numero.
3. **Un microbench che non usa il kernel vero può invertire il verdetto** (int8 lineare 25,86 GB/s = leva
   d'oro; kernel IQ2 reale 4,30 GB/s = leva morta). La stessa cautela vale per ogni misura fatta a
   `pos=873` e dichiarata "a 150k".
