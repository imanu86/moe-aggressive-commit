# 31 — FUNZIONI MAI USATE: cosa offre già il binario e noi non guardiamo

Data: 10 agosto 2026, notte. Radice `D:\llama-overlap`, ramo `overlap`, HEAD `1e07e00`.
**Niente compilato, niente eseguito, nessun server toccato.** Strumenti: lettura integrale
di `common/arg.cpp` (4.199 righe, **338 argomenti**, 133 con variabile `LLAMA_ARG_*`),
`tools/server/*` (endpoint e flusso slot/cache/checkpoint), grep di **tutti** i `getenv`
in `ggml/src` + `src` + `common`, `build/CMakeCache.txt` + `build.ninja` (le flag VERE
del binario), e — a costo zero — i log delle corse già in cassa in `D:\ds4_work\llama_run\`,
che hanno risposto da soli a tre domande che credevo da braccio. Marcatura:
[MISURATO] = log o file letti, [DEDOTTO] = aritmetica, [IPOTESI] = da falsificare.
Perimetro: NON ripeto ciò che UPSTREAM_390/RACCOLTA/PAVIMENTO hanno già schedato
(fusioni am17an, #25325/#25370/#26385, GGML_CUDA_GRAPH_OPT già misurato no-op, PDL=Hopper).

---

## IN PRIMA RIGA — tre cose trovate SPENTE o ACCESE a nostra insaputa

### 1. `--slot-save-path` + `POST /slots/{id}?action=save|restore` — il prefill da 82 minuti si paga UNA volta

- **Come si attiva**: `--slot-save-path D:\ds4_work\slot_cache\` all'avvio; poi
  `POST /slots/0?action=save` con body `{"filename":"prompt_105k.bin"}`, e
  `action=restore` per riprenderlo — anche **dopo un riavvio del server**
  (`server-context.cpp:4526-4556`, save via `llama_state_seq_save_file` a `:2559`).
- **Contro quale numero**: il prefill a ~20 t/s → **82 minuti a 105k**. Il restore è
  lettura file + `state_set`: ordine di **secondi**, non ore.
- **Funziona col nostro stack? [MISURATO indirettamente]**: la stessa serializzazione è
  già usata OGGI dai checkpoint del server, e i log la mostrano al lavoro sul nostro
  DSV4+kv-ring: `created context checkpoint … size = 14.283 MiB` (b1_blk1_R3, c=10240).
  Quindi lo state write/read DSV4 del fork esiste e gira. Non è mai stato usato per la
  PERSISTENZA, che è esattamente il nostro flusso: **riavviamo il server a ogni braccio**,
  e ogni riavvio ributta via tutto il contesto calcolato.
- **Caveat da verificare con UNA corsa** (prompt ~6k basta):
  (a) p1/SHA della generazione dopo restore contro prefill fresco (cancello: spec off, K=0);
  (b) il file pesa ∝ **capienza**, non righe usate (difetto pre-#25325 già a verbale in
  UPSTREAM_390 riga 2): a `-c 105k` aspettarsi centinaia di MiB anche per prompt corti
  — i KV buffer del target a 10k sono 10,75+52,5+5+13,12 ≈ 81 MiB [MISURATO log] →
  a 105k ~850 MiB [DEDOTTO]; su NVMe restano secondi;
  (c) la bozza NON ha stato serializzato (`draft = 0.000 MiB` nei log spec): alla
  ripresa DSpark riparte dagli hidden del target — impatto atteso ~solo il primo ciclo
  [IPOTESI];
  (d) interazione col ring (`LLAMA_KV_RING`): il log `[kv-staged] restored …
  reason=request-end` suggerisce che il ciclo di vita è già gestito, da confermare.
- **Costo di provarla**: una corsa da dieci minuti, zero patch. Il filename è libero
  (l'hash del prompt lo fa lo script chiamante, non il server).

### 2. La Flash Attention è ATTIVA sul target — e nessuno l'ha mai messo a verbale [MISURATO]

Il default è `-fa auto` e la probe decide da sola. Nei log di ieri:

    1.05.889.785 I resolve_fused_ops: Flash Attention enabled            ← contesto TARGET (n_ubatch=64)
    1.12.699.953 W resolve_fused_ops: layer 0 is assigned to device CPU but Flash Attention is assigned to device CUDA0
    1.12.699.954 W resolve_fused_ops: Flash Attention not supported, set to disabled   ← contesto BOZZA

Conseguenze:
- **PAVIMENTO ragionava "senza FA"** ("nei lanci visti nessun -fa"): l'attenzione del
  target passa invece dai kernel `fattn`, la maschera va castata a f16 (i "2 cast per
  strato" di PAVIMENTO §2e sono il prezzo della FA), e la race #26385 su `block_reduce`
  va ri-mappata: il soft_max dell'attenzione del TARGET non passa più di lì (restano
  router, Sinkhorn e il ramo bozza).
- **Il braccio `-fa off` non è mai esistito** in 190 corse: una corsa dice quanto la FA
  ci dà o ci toglie (a ctx 10k l'attenzione è piccola, atteso ±1-2% [DEDOTTO]; ma a
  contesto LUNGO — il fronte prefill/105k — la FA è la differenza fra kernel con e senza
  streaming della maschera: lì il braccio va rifatto).
- La bozza ha FA spenta per un dettaglio di PIAZZAMENTO (blk.0 su buffer host-visible):
  è il caso esatto del compagno #25832 già schedato in UPSTREAM_390 riga 6.
- **Costo**: una corsa (`-fa off` esplicito); SHA diverso atteso e legittimo.

### 3. Prompt-cache RAM da 8 GiB e checkpoint da 14 MiB: accesi in OGNI corsa da sempre [MISURATO]

Tutti i log di produzione contengono:

    prompt cache is enabled, size limit: 8192 MiB          (default cache_ram_mib=8192, common.h:630)
    idle slots will be saved to prompt cache upon starting a new task
    context checkpoints enabled, max = 32, min spacing = 8192
    created context checkpoint 1 of 32 (… size = 14.283 MiB)
    created speculative checkpoint (… size = 13.451 MiB, draft = 0.000 MiB)   (lv10)
    restoring speculative checkpoint (… size = 14104328)

- La cache prompt in RAM finora **non ha mai lavorato davvero** (update da 0,01-0,31 ms
  = no-op [DEDOTTO dai tempi]: ogni corsa usa un prompt solo e il riuso in-slot basta).
  Ma c'è, e ha due facce: (a) nei banchi futuri multi-prompt farebbe save/restore
  automatico fra prompt alternati (gratis, dentro la stessa sessione); (b) nei bracci
  di misura è una VARIABILE non dichiarata → `--cache-ram 0` per spegnerla quando serve
  il vuoto attorno alla misura.
- I **checkpoint speculativi** costano ~14 MiB a save e ~14 a restore, e i restore
  ricorrono (log lv10, coppie created/restoring a ~1-3 s di distanza). Oggi è ~1-3 ms
  per evento [DEDOTTO], spiccioli; ma il peso è ∝ capienza (pre-#25325): a `-c 105k`
  diventa ~150 MiB per evento → il pick #25325 smette di essere "igiene" e diventa
  prestazione sul fronte contesto lungo. Il numero 14 MiB dà finalmente la scala al
  "costo non cronometrato" di audit 16.
- Anche il **riuso del prefisso in-slot** (`cache_prompt=true` di default) è sempre
  stato attivo: dentro una corsa multi-richiesta, il prefill delle richieste dopo la
  prima è scontato del prefisso comune. Da dichiarare quando si leggono i tempi di
  prompt processing del ledger (regola: il cancello va sul contenuto).

---

## TABELLA — ordinata per valore atteso da noi

"Contro" = il numero nostro su cui agisce (prefill 82' / 12,66 t/s / 31% trasporto /
20% MMVQ / 49% pavimento / +18% spec / fiducia). "Attiva?" = stato nel binario/config attuale.

| # | Leva | Come si attiva | Cosa fa / contro cosa | Attiva? | Costo prova |
|---|---|---|---|---|---|
| 1 | **Slot save/restore su disco** | `--slot-save-path` + `POST /slots/:id?action=save\|restore\|erase` | persiste il KV di un prompt attraverso i riavvii → **prefill 82' pagato una volta** | NO (endpoint rifiuta senza flag) | **una corsa** |
| 2 | **Flash attention: sapere cosa gira** | `-fa off` (braccio) / lasciare auto | il target usa FA a nostra insaputa → fiducia nel modello dei costi + kernel attn a ctx lungo | **SÌ sul target, NO sulla bozza** [MISURATO] | **una corsa** |
| 3 | **`--spec-draft-conf-min P`** | flag già nel binario (default 0=spento) | usa la testa di confidenza DSpark (la `conf_proj` "mai usata" di audit 18!) per **troncare il blocco alla prima posizione debole** — consumatore già implementato nel NOSTRO `speculative.cpp:1207-1218` | NO | **una corsa** (es. `--spec-draft-n-max 3 --spec-draft-conf-min 0.4`). AVVERTENZA: riapre il fronte chiuso n-max, ma con meccanismo NUOVO (adattivo per posizione, non n fisso) — dichiararlo nel ledger |
| 4 | **Checkpoint: contarli e alleggerirli** | `-ctxcp N` / `-cms N` (default 32 / 8192); il costo vero con l'accumulatore di audit 16; la cura è il pick #25325 | save+restore da 14 MiB l'uno sul percorso spec → oggi ~0, a 105k ~150 MiB/evento → +18% spec e contesto lungo | **SÌ** (32 checkpoint, spec_ckpt sempre) [MISURATO] | gratis (grep log lv5) / pick |
| 5 | **Prompt-cache RAM 8 GiB** | c'è già; `--cache-ram 0` per spegnerla; `--cache-ram -1` illimitata | save/restore automatico fra prompt alternati nella stessa sessione; variabile nascosta nei bracci | **SÌ, mai lavorato** [MISURATO] | gratis (riga nel ledger) |
| 6 | **`GGML_OP_OFFLOAD_MIN_BATCH`** (default 32) + `--no-op-offload` | env / flag | soglia con cui le op su pesi host vengono spedite alla GPU nel prefill (`ggml-cuda.cu:6084`); con `-ub 64 > 32` l'op-offload è ATTIVO sui tensori CPU della bozza; mai comparso in un ledger | SÌ (soglia 32) | una corsa (prefill con soglia alta/bassa) |
| 7 | **`-dio` (direct I/O)** | flag (default off) | load del modello senza passare dal page cache: 87 GiB letti oggi bufferizzati dentro 96 GiB già pieni → meno churn/pageout fra i bracci, load più corto | NO | una corsa (cronometrare il load) |
| 8 | **`-tb` / `--threads-batch`** | flag (default = `-t`) | thread SEPARATI per il prefill: il fronte "thread oltre 8" fu chiuso sul DECODE; il prefill CPU può salire a 8 senza toccare il decode a 7 | NO (eredita 7) | una corsa |
| 9 | **`--mlock`** | flag (default off) | VirtualLock del modello (con `--no-mmap` già attivo): assicura la RAM contro i pageout — pertinente alla stabilità cercata con lo SHA `B396AB2137B2` | NO | una corsa (occhio ai limiti di working set Windows) |
| 10 | **`--prio N` / `--poll N`** (+ varianti `-batch` e `-draft`) | flag (default normal / 50) | priorità e busy-wait dei thread CPU: la lane K e il fork/join vivono di latenza di risveglio su Windows | NO (default) | una corsa; attese basse [IPOTESI] |
| 11 | **`-bs --backend-sampling`** (target) | flag experimental (default off) | campionamento sul backend; l'eco di #25262 senza porting. Collisione possibile con la verifica spec che legge i logits su CPU | NO | una corsa; attesa ≤1-3% |
| 12 | **`--spec-draft-threads*`** | flag (default = `-t`) | thread dedicati alla bozza (il `process()` costa 73 ms CPU con GPU ferma — memoria dspark-97%): oggi bozza e target condividono i 7 thread | NO | una corsa |
| 13 | **GGUF/rope da CLI**: `--rope-scaling yarn`, `--yarn-orig-ctx`, `--rope-scale`, `--override-kv` | flag | se la verifica metadati YaRN (UPSTREAM_390 prima-riga 3) trova il GGUF degradato, i parametri si INIETTANO da riga di comando senza riconvertire | n/a | gratis dopo la verifica metadati |
| 14 | **`--chat-template-file` / `--jinja` / `GET /props`** | flag / endpoint | template controllato da file per il banco-contenuto (UPSTREAM_390 prima-riga 4) e lettura della config effettiva | template = embedded GGUF | gratis |
| 15 | **Attrezzi già compilati in `build/bin`** | — | `test-backend-ops.exe` (M2/M5 di PAVIMENTO + `-o SOFT_MAX` per #26385), `llama-batched-bench.exe` (curva prefill/gen senza server), `llama-fit-params.exe` (stima memoria senza load), `test-save-load-state.exe` (fedeltà dello state DSV4 **senza** server → cancello per la riga 1), `llama-debug`/`eval-callback` (dump tensori) | compilati, mai usati | gratis quando il banco è libero |

---

## Censimento per perimetro (cosa c'è, in una riga per famiglia)

### 1. `common/arg.cpp` — 338 argomenti; la nostra riga ne usa ~20

Famiglie e verdetti (i singoli rilevanti sono già in tabella):

- **CPU/affinità**: `-t`, `-tb`, `-C/-Cr` (mask/range), `--cpu-strict`, `--prio`,
  `--poll`, tutte con gemelle `-batch` e `-draft` → righe 8/10/12 della tabella.
- **Batch/contesto**: `-c`, `-n`, `-b` (logico, default 2048), `-ub` (fisico, default
  512; noi 64 per VRAM), `--keep`, `--swa-full`, `-ctxcp/-cms`, `-cram`, `-kvu`,
  `--cache-idle-slots`, `--context-shift` (default OFF).
- **KV**: `-ctk/-ctv` (f16 default; q8_0/q4… disponibili) — sul nostro ring è
  probabilmente inerte, MAI provato; `-nkvo` (no KV offload); `--defrag-thold`
  deprecato no-op.
- **Offload/memoria**: `-ngl`, `-ot` (usati), `-cmoe/-ncmoe` (scorciatoie per exps→CPU),
  `--no-op-offload`, `--mmap/--no-mmap` (usato), `-dio`, `--mlock`, `--numa`
  (single socket: inerte), `--repack/-nr` (repack CPU, vedi sotto), `--no-host`,
  `-sm/-ts/-mg` (multi-GPU: inerti), `-fit/-fitt/-fitc` (default **on**, noi `--fit off`
  esplicito: corretto — senza quello il fit avrebbe ristretto ngl/ctx da solo).
- **Speculativa**: `--spec-type` (usato), `-md/-ngld/-otd` (usati),
  `--spec-draft-n-max/-n-min/-p-min/-p-split/-conf-min/-ubatch-size/-backend-sampling`,
  `-ctkd/-ctvd`, `--spec-draft-device`, famiglie ngram (`mod/simple/map-k/map-k4v`) e
  lookup (`-lcs/-lcd`) → i default: n_max=3 (noi 1), p_min=0, conf_min=0,
  **backend_sampling=true** ma il ramo DSpark non lo consuma (usa `common_sampler_sample`
  su CPU: `speculative.cpp:1220`) → di fatto inerte da noi.
- **Server**: `--host/--port/--api-key`, `-np` (usato), `-cb` (cont batching, default on),
  `--cache-prompt` (default ON), `--cache-reuse` (default 0; **morto da noi**, sotto),
  `-sps` (similarità slot, default 0,1), `--slots` (endpoint attivo di default),
  `--slot-save-path` (riga 1), `--metrics` (Prometheus, default off), `--props`
  (il POST è un placeholder vuoto nel codice: inutile), `--threads-http`,
  `--sleep-idle-seconds` (il server può dormire dopo N secondi di idle: rilascia il
  banco fra i bracci — MAI usato, possibile igiene per la VRAM residua [IPOTESI]),
  `--slot-prompt-similarity`, `--no-webui`.
- **Campionamento**: 40+ flag (top-k/p, min-p, XTC, DRY, mirostat, penalties,
  `--adaptive-target`…) — irrilevanti per il metro (il banco fissa il sampling), MA
  `-s/--seed` e `--samplers` sono il complemento del determinismo già conquistato.
- **Log**: `-lv` (usato, 4=trace: è ciò che rende visibili le righe di cache/checkpoint
  citate qui — tenerlo), `--log-file`, `--log-timestamps/-prefix`, `--log-colors`.
- **Rimossi** (fail rumoroso se usati): `--draft-max/-min`, `--spec-ngram-size-*`.

### 2. `tools/server` — endpoint

`/health`, `/metrics` (con `--metrics`), `/props` (GET utile, POST vuoto), `/slots`
(GET attivo di default: stato+prompt per slot), `/slots/:id?action=save|restore|erase`
(riga 1), `/completion(s)`, `/v1/completions`, `/v1/chat/completions` (+`/control`:
interruzione del reasoning a caldo), `/v1/responses`, `/v1/messages` (API Anthropic),
`/infill`, `/embedding(s)`, `/rerank`, `/tokenize`, `/apply-template`,
`/v1/*/input_tokens` (conteggio token senza generare — utile per verificare il
contenuto del banco senza toccare il KV), router multi-modello (`/models/*`).
Flusso interno già attivo: selezione slot per LCP (`server-context.cpp:1569-1677`),
prompt-cache RAM (`:243-273,1384-1392`), checkpoint (`:2336-2361,2989-3023`).

### 3. Variabili d'ambiente della BASE (esistenti nel nostro albero, non nostre)

| Env | Cosa fa | Verdetto |
|---|---|---|
| `GGML_OP_OFFLOAD_MIN_BATCH` | soglia op-offload (default 32) | riga 6 tabella |
| `GGML_CUDA_DISABLE_FUSION` | spegne TUTTE le fusioni CUDA | braccio diagnostico A/B gratis |
| `GGML_CUDA_DISABLE_GRAPHS` | spegne i CUDA graph | già usato in casa (A/B 95,5 ms) |
| `GGML_CUDA_GRAPH_OPT` | stream concorrenti in cattura | già misurato: no-op da noi |
| `GGML_CUDA_PDL` | programmatic dependent launch | morto: richiede Hopper |
| `GGML_CUDA_CUBLAS_COMPUTE_TYPE=f32\|f16\|bf16` | forza il compute type cuBLAS | tocca il prefill denso; mai provato; [IPOTESI] ±0 |
| `GGML_CUDA_ENABLE_UNIFIED_MEMORY` | `cudaMallocManaged` per i buffer device | su Windows/WDDM niente oversubscription: **morta qui** |
| `GGML_CUDA_NO_PINNED` | vieta il pinned host | kill switch di debug |
| `GGML_CUDA_REGISTER_HOST` | abilita `cudaHostRegister` dei buffer host | **senza chiamanti** in llama (`ggml-cuda.cu:5184`, usata solo via proc_address): inerte |
| `GGML_CUDA_P2P` / `GGML_CUDA_ALLREDUCE` | peer access / allreduce multi-GPU | single GPU: inerti (su Windows default `internal`) |
| `GGML_SCHED_DEBUG(=2)` / `GGML_SCHED_DEBUG_REALLOC` | dump split/grafo dello scheduler | diagnosi gratis dei 45 split |
| `LLAMA_GRAPH_REUSE_DISABLE` | spegne il riuso del grafo fra forward | kill switch A/B |
| `LLAMA_ATTN_ROT_DISABLE` | spegne la rotazione K del KV quantizzato | nota: il log dice `attn_rot_k = 1` sulla cache dell'**indexer** — la rotazione è attiva lì [MISURATO]; kill switch se mai servisse escluderla |
| `LLAMA_KV_CACHE_DEBUG`, `LLAMA_BATCH_DEBUG`, `LLAMA_GRAPH_INPUT_DEBUG`, `LLAMA_GRAPH_RESULT_DEBUG`, `LLAMA_TRACE`, `LLAMA_DEBUG_DUMP/FILTER` | diagnostica mirata | gratis quando serve |
| `LLAMA_ARG_*` (133) | OGNI flag principale ha l'equivalente env | utile per script di braccio senza riscrivere la riga |
| `GGML_NO_BACKTRACE`, `GGML_BACKEND_PATH`, `GGML_DISABLE_VULKAN` | contorno | — |

(Le `GGML_VK_*`/`METAL_*`/`OPENCL_*`/`HEXAGON_*`/`SYCL_*` esistono ma i backend sono
spenti in build: rumore da ignorare.)

### 4. Build (`CMakeCache.txt` + `build.ninja`) — cosa c'è DAVVERO nel binario [MISURATO]

- `CMAKE_CUDA_ARCHITECTURES=86`, Release, generatore Ninja, MSVC.
- **CPU: `/arch:AVX2`** effettivo nel ninja; system_info conferma
  `AVX=1 AVX2=1 F16C=1 FMA=1, LLAMAFILE=1, OPENMP=1, REPACK=1`. La CPU è un
  **Ryzen 7 5800X (Zen 3): l'AVX-512 non esiste in hardware** → la build CPU è al
  tetto della macchina. Fronte chiuso con verdetto: nessun margine di build sul ramo
  CPU via ISA. (Resta solo l'alternativa toolchain clang-cl [IPOTESI mai misurata,
  costo ricompilazione, attesa bassa].)
- **`GGML_CUDA_FA_ALL_QUANTS=OFF`**: i kernel FA per le combinazioni K/V quantizzate
  NON standard non sono compilati — dormiente finché il KV resta f16; se mai si prova
  `-ctk q8_0` sul KV standard, va ricompilato con ON.
- `GGML_CUDA_FA=ON`, `GGML_CUDA_GRAPHS=ON`, `FORCE_MMQ/CUBLAS=OFF`, `NO_VMM=OFF`.
- `GGML_CPU_REPACK=ON` + default runtime `--repack` attivo: `repack.cpp` copre
  **Q2_K** (oltre a Q4_0/Q4_K/IQ4_NL) → gli esperti della bozza su CPU possono già
  essere serviti dai kernel repack 8x8 [DA VERIFICARE nel log di load, riga "repack"];
  se sì, la "verifica MoE-CPU" (collo DSpark) sta già usando i kernel migliori.
- `GGML_SCHED_MAX_COPIES=4`: inerte con un solo device (pipeline_parallel=false).
- `GGML_LTO=OFF`, `GGML_BLAS=OFF` (il sgemm llamafile c'è), `LLAMA_CURL=OFF`.

---

## Acceso che non sapevamo / spento che merita un braccio

**Acceso a nostra insaputa (da dichiarare nel ledger da oggi):**
1. **Flash Attention sul target** (auto-probe) — e spenta sulla bozza per piazzamento.
2. **Prompt-cache RAM 8 GiB** + `cache_idle_slots` + **riuso prefisso in-slot**
   (`cache_prompt=true`, similarità 0,1): dentro una corsa multi-richiesta il prompt
   processing dopo la prima richiesta è scontato.
3. **Checkpoint**: 32 di contesto (spacing 8192) + gli speculativi da ~14 MiB con
   restore ricorrenti.
4. **Op-offload** con soglia 32 sul prefill dei tensori host.
5. **Repack CPU** dei quant idonei (Q2_K incluso) sui buffer CPU.
6. **Warmup** (`--warmup` default): un forward fittizio al load → la cache esperti
   NON è mai davvero fredda alla prima richiesta: la sonda del transitorio freddo
   (RACCOLTA lavoro 2) va letta sapendolo, o il braccio va lanciato con `--no-warmup`.
7. Il **fit dei parametri** sarebbe attivo di default: il nostro `--fit off` esplicito
   è ciò che lo tiene fuori — giusto così, da non perdere nei lanci futuri.

**Spento (o mai usato) che merita:** righe 1, 2, 3, 6, 7, 8, 9 della tabella.

**Morti per costruzione — a verbale perché nessuno li riproponga:**
- `--cache-reuse` e context-shift: `llama_kv_cache_dsv4::get_can_shift() = false`
  (`llama-kv-cache-dsv4.cpp:1296-1299`) — il KV compresso non sa shiftare.
- `GGML_CUDA_ENABLE_UNIFIED_MEMORY` (WDDM), `GGML_CUDA_PDL` (Hopper),
  `GGML_CUDA_REGISTER_HOST` (senza chiamanti), `GGML_CUDA_GRAPH_OPT` (no-op misurato),
  multi-GPU (`-sm/-ts/--rpc`), `--numa`.
- AVX-512 in build: la CPU non ce l'ha.

---

## Dati che si ottengono SOLO eseguendo (in ordine di resa)

1. **Slot save/restore**: peso del file e tempo di save/restore a `-c 10k` e a contesto
   lungo; p1/SHA post-restore contro prefill fresco (cancello: spec off, K=0);
   comportamento col ring attivo. (`test-save-load-state.exe` come pre-cancello senza server.)
2. **Braccio `-fa off`**: t/s e ms/posizione contro l'attuale (FA on, a nostra insaputa);
   da rifare anche a contesto lungo dove l'attenzione pesa.
3. **`--spec-draft-conf-min`**: accettazione, lunghezza media di blocco e t/s con
   n-max 3-5 + soglia 0,3-0,6 (contro il chiuso n-max fisso).
4. **Frequenza e costo cumulato dei checkpoint spec** per corsa (una corsa a lv 5, o
   l'accumulatore di audit 16) → decide il valore del pick #25325 oggi, non a 105k.
5. **Load con `-dio`** contro attuale (tempo + pressione RAM durante il load).
6. **Prefill con `GGML_OP_OFFLOAD_MIN_BATCH`** a 16/32/64 e con `--no-op-offload`.
7. **`-tb 8`** sul prefill; `--prio 2 --poll 100` sulla lane K (attese basse).
8. Righe `repack` nel log di load (conferma che gli exps CPU della bozza sono repackati).

---

## Chiusura

Il binario contiene già: la persistenza del contesto su disco (mai accesa), una cache
di prompt in RAM (accesa e mai usata), un sistema di checkpoint che paga 14 MiB a
battito (acceso e mai contato), la Flash Attention (accesa e mai dichiarata), e la
testa di confidenza della bozza con il suo consumatore (spenta). Quattro delle cinque
si provano con una corsa l'una. La riga di comando usa 20 argomenti su 338; di quelli
che restano, la maggior parte è rumore per noi — ma i cinque sopra non lo sono, e due
di loro toccano i due numeri peggiori che abbiamo: gli 82 minuti di prefill e la
fiducia nelle misure.
