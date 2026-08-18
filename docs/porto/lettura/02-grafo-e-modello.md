# 02 — Grafo e modello (llama-context, llama-graph, deepseek4, dflash)

> **STATO: COMPLETO.** Lettura del codice, nessuna esecuzione.
> Ogni affermazione e' marcata `LETTO NEL CODICE` o `DEDOTTO, non verificato`.
>
> Repo letto: `D:\llama-overlap` @ `bd06d4ddf`. Base upstream: `5c3a58686`.
> Nostro codice = `git -C D:/llama-overlap diff 5c3a58686..HEAD -- <path>`.
>
> **Blocco assegnato**: `src/llama-context.cpp` (4768 righe), `src/llama-graph.cpp` (3809),
> `src/models/deepseek4.cpp` (1478), `src/models/dflash.cpp` (683), `src/models/models.h` (2166).
> Diffstat vs base: context **+671**, context.h **+32**, graph **+341**, graph.h **+62**,
> deepseek4 **+457**, dflash **+441**, models.h **+137** — totale **+1965 / −176**.
>
> Le sezioni marcate **[fuori blocco]** vengono da due sub-letture mirate su
> `ggml/src/ggml-cuda/`, `ggml/src/ggml-backend.cpp`, `common/arg.cpp` e
> `src/llama-model-loader.cpp`: servivano per chiudere le domande 3 e 4 e sono riportate con
> `file:riga`. Tutti i path sono relativi a `D:\llama-overlap\`.

---

## A. CONTATORI

| Nome nel log | file:riga (incremento / stampa) | Cumulativo o istantanea | Unita' | Nostro? |
|---|---|---|---|---|
| **`graphs reused`** | incremento `src/llama-context.cpp:1599`; campo `src/llama-context.h:425`; stampa `src/llama-context.cpp:4706`, `common/sampling.cpp:526`, `tools/server/server-context.cpp:725-727` | **CUMULATIVO** dalla nascita del contesto. Azzerato **solo** da `perf_reset()` (`llama-context.cpp:3751`), che **il server non chiama mai** | conteggio di **ubatch**, NON di token | campo upstream; la stampa nel server e' nostra |
| `DSPROF ctx=… reuse=N sync n=N tot X ms` | dump `src/llama-context.cpp:44-56`; incrementi `1600` (reuse), `938-939` (sync) | **cumulativo** per contesto, stampato **ogni 25 forward di tipo `block`** (`llama-context.cpp:1718`) | ms / conteggi | **nostro** |
| `DSPROF <fase> n | build | alloc | input | compute` | accumuli a `llama-context.cpp:1613` (build), `1688` (alloc), `1706` (input), `1716` (compute); fasi `enc`/`inject`/`block`/`tok1` scelte a `1582-1585` | **cumulativo** in µs, stampato in ms | ms | **nostro** |
| `splits(block)` / `nodes(block)` | `src/llama-context.cpp:1690-1691` (campi a `42`, stampa a `59`) | **ISTANTANEA all'ultimo REBUILD** di un ubatch `block`. **NON si aggiorna sui grafi riusati** | conteggio | **nostro** |
| `n_hits` / `n_misses` cache esperti | `src/llama-context.cpp:3754-3776` (`cache_esperti_get_stats`), API C `4713-4720` | **cumulativo**, letto dal backend CUDA via `ggml_backend_cuda_cache_esperti_contatori` | conteggio di **richieste di esperto** | **nostro** |
| `vram_a_fasi: fase=… buffer di calcolo X → Y MiB` | `src/llama-context.cpp:912-918` | **istantanea a transizione di fase** | MiB, ms | **nostro** (leva spenta) |
| `acceptmoe-spia: contesto disarma: spec=…` | `src/llama-context.cpp:2326-2327` | **evento**, una riga per forward disarmato | conteggi | **nostro** (spenta) |
| `resolve_fused_ops: <nome> enabled` / `not supported` | `src/llama-context.cpp:651`, `654` | **una volta sola** all'avvio (`auto_fhc`/`auto_flid` si azzerano a `675`/`681`) | — | nostro (i probe HC e LID) |
| `eval time`, `t/s` (`t_eval_us`, `n_eval`) | `src/llama-context.cpp:949-959`, dentro `synchronize()` | cumulativo | µs / token | upstream |

**Tre avvertenze di lettura, tutte `LETTO NEL CODICE`:**

1. **`graphs reused` conta UBATCH, non token.** L'incremento sta dentro `process_ubatch`
   (`llama-context.cpp:1599`). Il server stampa quello di **`ctx_tgt`** (`server-context.cpp:727`):
   il contesto della bozza ha il suo, mai stampato.
2. **`graphs reused` non si azzera nel server.** `perf_reset()` e' raggiungibile solo da
   `llama_perf_context_reset()` (`llama-context.cpp:4709`), chiamata da
   `tools/completion/completion.cpp:161` e `common/common.cpp:1455` — **non dal server**. Per avere
   il dato di **una** richiesta serve la **differenza fra due stampe consecutive**.
3. Il commento upstream a `llama-context.cpp:944-946` avverte che senza `synchronize()` fra token
   singoli le statistiche finiscono nel bucket del prompt.

**`graphs reused = 627 su 1200 token` — che cosa significa davvero.**
Con `--spec-draft-n-max 1` il bersaglio alterna forward a **2 token** (anchor + bozza) e a **1
token**. `allow_reuse` confronta `ubatch.n_tokens` (`src/llama-graph.h:747`): **ogni alternanza
2↔1 rompe il riuso**. 627/1200 ≈ 52% e' il valore atteso da un'alternanza quasi perfetta fra due
taglie. `LETTO NEL CODICE` la guardia; `DEDOTTO, non verificato` l'attribuzione del 52% —
`DSPARK_PROF=1` separa gia' i bucket `block` (n>1) e `tok1` e la falsifica in una corsa.

---

## B. VARIABILI D'AMBIENTE

Config di riferimento: `-c 10000 -ub 64 -ngl 99 -t 7 --no-mmap`, bozza `-ngld 99
--spec-draft-n-max 1`, `-ot "ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped"`,
`-otd "blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU"`,
`LLAMA_DSV4_HC_FUSO=5`, `LLAMA_DSV4_INDEXER_FUSO=0`, `LLAMA_MAPPED_IBRIDO=1`,
`LLAMA_OVERLAP_ASYNC=1`, `K=2`, `GGML_CUDA_GRAPH_OPT=0`.

### B.1 `src/llama-context.cpp`

| Variabile | riga | Difetto | Ramo RAGGIUNGIBILE con questa config? |
|---|---|---|---|
| `DSPARK_PROF` | 45 | 0 | **NO** (non impostata). A 0 costa una lettura di `static bool` per forward |
| **`LLAMA_DSV4_HC_FUSO`** | 306 | **0 = niente fuso** | **SI', = 5** → `comb`+`post` fusi, **`pre` NO** |
| `LLAMA_DSV4_INDEXER_FUSO` | 329 | 0 | impostata a **0** → **ramo fuso NON raggiunto**; maschera `lid` resta f32 |
| `LLAMA_GRAPH_REUSE_DISABLE` | 349 | 0 (`llama-context.h:410`) | non impostata → **riuso ATTIVO** |
| `LLAMA_KV_RING` | 551 | assente | **NO** |
| **`LLAMA_OVERLAP_K`** (qui per il **pin**) | 1638, `atof` | 0.0 | **SI', K=2** → pin dei nodi `_overlap_cpu` sul backend CPU **attivo** |
| `LLAMA_OVERLAP_PIN` | 1652 | **acceso** (spento solo con `=0`) | **SI', attivo** |
| `LLAMA_VRAM_A_FASI` | 2148 | 0 | **NO** — `vram_a_fasi()` non viene mai chiamata |
| `LLAMA_VRAM_A_FASI_UB` | 2168 | 64 | irrilevante (padre spento) |
| `LLAMA_VRAM_A_FASI_MIN` | 2176 | 0 | irrilevante |
| `LLAMA_ACCEPTMOE_ESATTE` | 2297 | 1 | irrilevante |
| `LLAMA_ACCEPTMOE_SPIA` | 2323 | 0 | **NO** |
| `LLAMA_CACHE_ESPERTI_DMA` | 2955 | 0 | **NO** — a 0 si salta anche la **scansione di TUTTI i nodi** in `graph_compute` (2959-2967) |

### B.2 `src/llama-graph.cpp`

| Variabile | riga | Difetto | Raggiungibile? |
|---|---|---|---|
| `LLAMA_DSV4_COMPRESS_DEBUG` | 756 | 0 | **NO** |
| `LLAMA_GRAPH_RESULT_DEBUG` | 1209 | 0 | **NO** |
| **`LLAMA_OVERLAP_K`** (qui per **costruire** lo split) | 1825, `atof` | 0.0 | **SI', K=2** |
| **`LLAMA_OVERLAP_BATCH_MAX`** | 1849 | **1** | **SI' — ed e' il cancello che decide tutto** (sotto) |
| `LLAMA_ACCEPTMOE` | 2195 | 0 | **NO** — niente inserito fra router e `MUL_MAT_ID` |
| `LLAMA_ACCEPTMOE_BATCH_MAX` | 2207 | 8 | irrilevante |
| `LLAMA_ACCEPTMOE_SOGLIA` | 2212 | 0.0 | irrilevante |

> **IL CANCELLO PIU' IMPORTANTE DEL BLOCCO** — `LETTO NEL CODICE`, `src/llama-graph.cpp:1848-1856`:
> lo split overlap si costruisce **solo se `n_tokens <= batch_max`**, e `batch_max` **vale 1**.
> Con `--spec-draft-n-max 1` il forward di verifica del bersaglio ha **2 posizioni**: su quei
> forward **lo split NON viene costruito**. `K=2` agisce **solo sui forward a 1 token**.
> La motivazione e' scritta a `llama-graph.cpp:1836-1847`: con taglie che alternano 1 e 2, il
> replay di un CUDA graph catturato con l'altra taglia degenerava in ripetizione
> (144 righe/126 uniche → 41/11), e con `GGML_CUDA_DISABLE_GRAPHS=1` tornava sano.

### B.3 `src/models/deepseek4.cpp`

| Variabile | riga | Difetto | Raggiungibile? |
|---|---|---|---|
| `LLAMA_DSV4_SINKHORN_ITERS` | 55 | dal GGUF (**20**) | **NO** — sonda che **invalida l'uscita** (avviso esplicito riga 59) |
| `LLAMA_CACHE_ESPERTI_SLOT` | 1393 | 0 | se >0 il **predittore di route** entra nel grafo (cancello a 1419) |
| `LLAMA_CACHE_ESPERTI_W` | 1397 | 0, clampato a [0,8] | **a 0 il ciclo `for k=1..W` non gira**: nessun nodo `cache_pf-*` |
| `LLAMA_CACHE_ESPERTI_FATE` | 1406 | 0 | — |
| `LLAMA_CACHE_ESPERTI_BATCH` | 1415 | **8** | cancello del predittore: `n_tokens ∈ [1,8]` ⇒ **il batch di verifica a 2 PASSA**; il prefill a `ub 64` **no** |

### B.4 `src/models/dflash.cpp`

| Variabile | riga | Difetto | Raggiungibile? |
|---|---|---|---|
| `DSPARK_NO_MARKOV` | 15 | 0 | **NO** → la testa di Markov **viene costruita** (`dflash.cpp:468`, `680`) |
| `LLAMA_DFLASH_SINKHORN_ITERS` | 76 | dal GGUF | **NO** se non impostata. **Non e' una sonda**: sulla bozza e' una cura legittima (commento 63-75) |

### B.5 Variabili citate nella config ma **non** in questo blocco

- **`LLAMA_MAPPED_IBRIDO`** → `ggml/src/ggml-cuda/ggml-cuda.cu:1435-1439` e `:5528-5546`. **[fuori blocco]**
- **`LLAMA_OVERLAP_ASYNC`** → non compare in nessuno dei cinque file del blocco (grep vuoto).
- **`GGML_CUDA_GRAPH_OPT`** → `ggml/src/ggml-cuda/ggml-cuda.cu:5018-5021`. **[fuori blocco]**
  **`=0` e' un NO-OP**: il gate e' `env != nullptr && atoi(env) == 1`, quindi assente e `0` sono lo
  stesso stato, che e' gia' il difetto. `LETTO NEL CODICE`.

---

## C. COMPLESSITA' DELLE FUNZIONI CALDE, E CHIAMATE PER TOKEN

Modello: **43 strati**, `hc = dsv4_hc_mult = 4` (`GGML_ASSERT(hc == 4)`, `deepseek4.cpp:341`),
**256 esperti**, **6 attivati**, `dsv4_hc_sinkhorn_iters = 20` (dal GGUF).
Il grafo si ricostruisce **una volta ogni ~2 forward** (48% dei forward, dal contatore).

### C.1 Le tre parti HC — nodi di grafo

| Parte | funzione | nodi NON fusi (hc=4) | fusi | chiamate/strato | chiamate/forward |
|---|---|---|---|---|---|
| **`pre`** (riduzione) | `build_hc_pre(x, weights, il)` — `deepseek4.cpp:260-289` | 8 `view` + **4 `mul` + 3 `add`** ≈ **15 nodi, 7 kernel veri** | **1** | 2 (attn + ffn) | **86** (+1 dalla testa, mai fusa) |
| **`comb`** (Sinkhorn) | `build_hc_sinkhorn` — `deepseek4.cpp:291-326` | `soft_max` 1 + `fill` 1 + `add` 1 + `norm_cols` 6 + 19×(`norm_rows` 3 + `norm_cols` 6) = **~180 nodi** | **1** | 2 | **86** |
| **`post`** (ricombinazione) | `build_hc_post` — `deepseek4.cpp:389-425` | 4×(1 `view` + 1 `mul` + 4×(2 `view`+`mul`+`add`)) + 4 `reshape` + **3 `concat` che COPIANO** ≈ **~79 nodi** | **1** | 2 | **86** |

`norm_cols` = `permute`+`cont`+`sum_rows`+`add`+`permute`+`div` = **6 nodi** (`deepseek4.cpp:305-311`).
`norm_rows` = `sum_rows`+`add`+`div` = **3 nodi** (`deepseek4.cpp:313-317`).

**Verifica aritmetica** (`DEDOTTO` sul conteggio, `LETTO NEL CODICE` sulla struttura):
per strato, tutto non fuso: `2×(180+15) + 2×79 = 548` nodi; ×43 = **~23.600**; piu' il resto del
grafo (~10.500) fa **~34.100**, che coincide con i **34.329** misurati a `FUSO=0` e con i **10.507**
a `FUSO=7` annotati in memoria.

### C.2 MoE — `build_moe_ffn`, `src/llama-graph.cpp:2018-2420`

Chiamata **una volta per strato**, **43 volte per forward** (`deepseek4.cpp:1332`). Per chiamata:

- **router**: `mul_mat`(gate_inp, con `GGML_PREC_F32` forzato a `2052`) → `softplus` → `sqrt`
  (`2080`) → `add`(bias) (`2091`) — **4 nodi**
- **selezione**: `ggml_argsort_top_k(selection_probs, 6)` — **`llama-graph.cpp:2134`**
- **pesi**: `get_rows` (`2148`) + `sum_rows` + `clamp` + `div` (`2162-2169`) + `scale` (`2175`)
- **esperti**: **3 `MUL_MAT_ID`** — `up` (`2291`), `gate` (`2304`), `down` (`2393`) — piu' 2 `clamp`
  e `swiglu_split` (`2329-2335`)
- **coda**: 6 `view_2d` + 5 `add`

⇒ **129 `MUL_MAT_ID` per forward** (3×43), ciascuno con 6 indici:
**258 attivazioni di esperto per posizione**, coerente col modello di costo in memoria.

### C.3 Predittore di route — `deepseek4.cpp:1391-1441`

`cache_w` `mul_mat` `[n_embd × 256]` + `add` + `argsort_top_k` **per ogni strato** ⇒ **43×W**
`mul_mat` extra per forward. Costo dichiarato: 2,1 MFLOP a previsione, **1,4% del token**
(`deepseek4.cpp:1366`). **A `W=0` il ciclo non gira.**
Il nodo prodotto e' un **ramo morto nominato** `cache_pf-<strato>-<n>` (`1437`), espanso a mano
(`1438`) e **intercettato per nome dal backend CUDA**.

### C.4 I tre grafi della bozza — `src/models/dflash.cpp`

Scelti da `build_arch_graph` (`211-221`) e dal tipo di ubatch:

1. **encoder** (`graph<true>`, `240-253`): `fc` (`mul_mat`) + `rms_norm`. **~4 nodi.** Una volta per ciclo.
2. **iniezione K/V** (`ubatch.embd != nullptr`, `500-574`): per strato `mul_mat(wkv)` + `rms_norm`
   + `rope` + `concat` + 2 `cpy` in cache. **Nessun MoE.**
3. **decode a token** (`build_dsv4`, `348-471`): backbone DSV4 **completo, MoE compreso**, su **3
   strati** — piu' la testa di Markov, che ha un ciclo `for i < block_drafts` con
   `get_rows`+`mul_mat`+`add`+`concat` (+`argmax` **dentro il grafo**, `323`) **per posizione**.

---

## D. HOST vs DEVICE, E OGNI CONFINE DI SINCRONIZZAZIONE

### D.1 Cosa gira sull'HOST, e quante volte per forward

| Punto | file:riga | Quando | Costo |
|---|---|---|---|
| `res->can_reuse(gparams)` | `llama-context.cpp:1589` → `llama-graph.cpp:1301` | **ogni forward** | confronti scalari + `dsv4_can_reuse_*` |
| `graph_params()` — sonda `predizione_attiva` su ogni backend | `llama-context.cpp:2894-2906` | **ogni forward** | N chiamate `get_proc_address` **(nostro)** |
| costruzione del grafo | `llama-context.cpp:1609` | **48% dei forward** | ~10.500 nodi a `FUSO=5` |
| **pin del ramo CPU** — `strstr` su **ogni nodo** | `llama-context.cpp:1652-1663` | **solo dopo rebuild** | O(n_nodi) `strstr`. Con K=2 e' **acceso** **(nostro)** |
| `cache_esperti_prepara` | `llama-context.cpp:1668-1679` | **solo dopo rebuild** | O(n_nodi) lato backend **(nostro)** |
| `set_inputs` | `llama-context.cpp:1700-1704` | **ogni forward** | scrive le `kq_mask`: **O(n_kv × n_tokens)** su memoria host |
| `oracolo_avanza` | `llama-context.cpp:2054-2071` | solo se `batch.n_tokens == 1` | inerte senza `LLAMA_CACHE_ORACOLO` **(nostro)** |
| stato ACCEPTMOE | `llama-context.cpp:2288-2334` | ogni ubatch | 2 `int32`; il ciclo `una_seq` e' tagliato da `acceptmoe_spec > 0` **(nostro)** |
| scansione `cache_dma` | `llama-context.cpp:2959-2967` | **mai** (`LLAMA_CACHE_ESPERTI_DMA` spenta) | — |

### D.2 I confini di sincronizzazione

`llama_context::synchronize()` (`llama-context.cpp:929-969`) → `ggml_backend_sched_synchronize`.
Chiamanti raggiungibili con questa config (`LETTO NEL CODICE`):

- **tutte le `llama_get_logits*` / `llama_get_embeddings*`** (`llama-context.cpp:4260-4380`) e i
  getter di stato (`4572-4645`) sincronizzano **prima** di toccare `buf_output`.
  Con la speculazione ci sono **due contesti** ⇒ **≥2 rendezvous host↔device per ciclo**
  (uno bozza, uno bersaglio). `DEDOTTO, non verificato` il numero esatto: dipende da quante volte
  il server rilegge i logit per ciclo.
- `llama-context.cpp:1595-1597`: con `pipeline_parallel` si sincronizza **anche nel ramo di riuso**,
  prima di `set_inputs` — ma `pipeline_parallel` e' **falso** con un solo device.
- `llama-context.cpp:1886` (solo `LLM_ARCH_T5`): **irraggiungibile**.
- `llama-context.cpp:2622` (rialloc di `buf_output`): **raro**, solo a crescita.
- `llama-context.cpp:694`, `898` (dentro `sched_reserve()` / `vram_a_fasi()`): **fuori dal ciclo**.

**I ~76 confini per token del ledger NON stanno in questo blocco**: sono i join fra split di
`ggml_backend_sched_compute_splits` (`ggml/src/ggml-backend.cpp:2150`). **[fuori blocco]**
Cio' che **questo** blocco decide e' **quanti split esistono**, e lo decide in due punti:

1. **il pin** (`llama-context.cpp:1652-1663`): ogni gruppo `_overlap_cpu` forzato su CPU crea un
   confine CUDA→CPU e uno CPU→CUDA. Con `LLAMA_OVERLAP_BATCH_MAX=1` quei nodi **esistono solo nei
   grafi a 1 token**;
2. **la collocazione dei pesi**, decisa da `-ot`/`-otd` e dall'ibrido — vedi D.3.

`splits(block)` / `nodes(block)` (`llama-context.cpp:1690-1691`) sono la sonda giusta, **gia'
scritta e mai accesa** in questa configurazione.

### D.3 La regola che decide CPU vs GPU per gli esperti **[fuori blocco, ma decisiva]**

`ggml/src/ggml-cuda/ggml-cuda.cu:5528-5546` — `LETTO NEL CODICE`:

```c
if (g_cuda_mapped_uva && op->op == GGML_OP_MUL_MAT_ID) {
    ...  ibrido = getenv("LLAMA_MAPPED_IBRIDO") ...            // = 1
    ...  soglia = getenv("LLAMA_MAPPED_IBRIDO_SOGLIA") : 2     // = 2 (difetto)
    if (ibrido && src[0] sta su buffer Mapped) {
        const bool cache_ammessa = ggml_cuda_cache_esperti_percorso_gpu_richiesto();
        if (get_op_batch_size(op) < soglia && !cache_ammessa) return false;  // -> lo prende la CPU
    }
}
```

E `ggml_backend_cuda_mapped_buffer_type_is_host` (`ggml-cuda.cu:1410-1439`) ritorna
**`ibrido && g_cuda_mapped_uva`** ⇒ con `LLAMA_MAPPED_IBRIDO=1` vale **vero**, quindi **il backend
CPU accetta il buffer mappato** e legge **gli stessi byte senza copiarli** (host e device sono lo
stesso indirizzo, verificato a `ggml-cuda.cu:1397`).

**`get_op_batch_size` per `MUL_MAT_ID` e' `op->ne[2]`, cioe' `n_tokens`.**
Con `--spec-draft-n-max 1` e soglia **2**:

| forward del bersaglio | `n_tokens` | esperti mappati vanno su… |
|---|---|---|
| verifica (anchor + bozza) | **2** | `2 < 2` e' **falso** → **GPU** |
| forward a un token | **1** | `1 < 2` e' **vero** → **CPU** (salvo `cache_ammessa`) |

⇒ **il margine e' di un token esatto**, e l'alternanza 2↔1 che rompe il riuso del grafo e' **la
stessa** che sposta il MoE fra GPU e CPU. Le due cose non sono indipendenti.

---

## DOMANDE SPECIFICHE

### 1. `LLAMA_DSV4_HC_FUSO`: cosa fonde, e cosa cambia fra 5 e 7

#### E' una BITMASK, non un livello

`LETTO NEL CODICE`, `src/llama-context.cpp:306-312`:

```
fuso_mask & 1  ->  cparams.fused_dsv4_hc_comb    (comb)
fuso_mask & 2  ->  cparams.fused_dsv4_hc_pre     (pre)
fuso_mask & 4  ->  cparams.fused_dsv4_hc_post    (post)
auto_fhc = (fuso_mask != 0)
```

- **`FUSO=5` = 1|4 = `comb` + `post`. `pre` NON e' fuso.**
- **`FUSO=7` = 1|2|4 = tutte e tre.**
- **L'UNICA differenza fra 5 e 7 e' `pre`.**

#### Le tre parti — dove sono e cosa fanno (`LETTO NEL CODICE`)

Le hyper-connection tengono **4 flussi residuali paralleli** invece di uno. Ogni blocco — **attn e
ffn, quindi due volte per strato** — fa pre → (calcolo) → post.

**`pre`** — `src/models/deepseek4.cpp:260-289`. **Riduce i 4 flussi a uno**, con pesi per token:
`out[:, t] = Σ_{ih=0..3} x[:, ih, t] · w[ih, t]`.
Non fuso: 4 `ggml_view_2d` su `x`, 4 su `weights`, 4 `ggml_mul` broadcast, 3 `ggml_add`.
Fuso: **`ggml_dsv4_hc_pre`** → kernel `ggml/src/ggml-cuda/dsv4-hc.cu:103-137`.

**`comb`** — non fusa `deepseek4.cpp:291-326`, fusa `371-374`. Costruisce la matrice **4×4
doppiamente stocastica** che rimescola i flussi: affine(`scale[2]`,`base[2h..]`) → `soft_max` →
`+eps` → **20 iterazioni di Sinkhorn** (normalizza colonne, poi righe+colonne alternate).
Fusa: **`ggml_dsv4_hc_comb`** → `dsv4-hc.cu:36-101`, tutte le 20 iterazioni **in registri**.

**`post`** — `deepseek4.cpp:389-425`. **Riespande** a 4 flussi:
`out[:, dst, t] = x[:, t]·post[dst, t] + Σ_{src=0..3} residual[:, src, t]·comb[dst, src, t]`.
Non fusa: 20 `mul` + 16 `add` + **3 `ggml_concat` che copiano progressivamente l'uscita**
(commento esplicito a `deepseek4.cpp:398-399`). Fusa: **`ggml_dsv4_hc_post`** → `dsv4-hc.cu:140-179`.

`pre` e `comb` **nascono nella stessa funzione**: `build_hc_pre` a 6 argomenti
(`deepseek4.cpp:328-387`) calcola **una sola `mul_mat`** (`mixes`, riga 346) su
`rms_norm(reshape(x))` e ne ritaglia **tre viste** — `pre` a offset 0 (riga 355), `post` a offset
`hc` (361), `comb` a offset `2·hc` (379). Poi chiama la `build_hc_pre` a 3 argomenti (riga 386),
che e' la parte fusibile col bit 2.

#### Quali kernel spariscono passando da 5 a 7

Per **ciascuna** delle **86** chiamate per forward (2 per strato × 43 strati):
**4 `MUL` broadcast + 3 `ADD` = 7 lanci → 1 lancio**.

⇒ **602 lanci di kernel in meno per forward** e **~1.290 nodi di grafo in meno** (86 × ~15).
In traffico: il chain non fuso materializza **4 tensori intermedi** `[n_embd × n_tok]` f32 e ne
somma 3, cioe' muove ~7× i byte del kernel fuso, che legge `x` una volta e scrive `dst` una volta.
`LETTO NEL CODICE` la struttura; `DEDOTTO` l'aritmetica. **+2,15% di ciclo e' coerente.**

**La testa non e' mai fusa.** `build_hc_head` (`deepseek4.cpp:427-447`) chiama `build_hc_pre` con
**`il = -1`**, e la guardia e' `if (cparams.fused_dsv4_hc_pre && il >= 0)` (`deepseek4.cpp:273`;
identica per `post` a `400`). Motivo dichiarato: il probe esige `il >= 0`
(`llama-context.cpp:628`, `GGML_ASSERT(node.il >= 0)`).

#### Perche' cambia l'accordo bozza-bersaglio (−2,66% di p1)

**Il meccanismo e' l'ARITMETICA, non la topologia.** `LETTO NEL CODICE`:

Kernel fuso `pre` — `ggml/src/ggml-cuda/dsv4-hc.cu:129-135`:
```c
float sum = x[i0*sx0 + it*sx2] * weights[it*sw1];
for (int64_t ih = 1; ih < hc; ++ih) {
    const float xv = x[i0*sx0 + ih*sx1 + it*sx2];
    const float wv = weights[ih*sw0 + it*sw1];
    sum += xv * wv;                       // <-- FFMA: il prodotto NON viene arrotondato
}
```
Cammino non fuso: ogni `ggml_mul` produce **un tensore f32 arrotondato**, e i 3 `ggml_add`
arrotondano di nuovo. Sono **due aritmetiche diverse**, non due implementazioni della stessa.

E il flag di compilazione lo conferma e lo amplifica: **`-use_fast_math`** e' attivo su tutto
`ggml-cuda` — `ggml/src/ggml-cuda/CMakeLists.txt:197` — che implica `--fmad=true`, `--ftz=true`,
`--prec-div=false`. `LETTO NEL CODICE` il flag; `DEDOTTO, non verificato` che nvcc emetta `FFMA`
(non ho ispezionato il PTX; e' il comportamento documentato di `-fmad=true`).

Conseguenza: **`pre` fuso e non fuso differiscono di ~1 ulp**, e `pre` sta **all'ingresso di ogni
blocco**, 86 volte per forward.

**Il pezzo strutturale — perche' il segno e' negativo e non casuale** (`DEDOTTO, non verificato`,
ma su fatti tutti letti):

1. Bozza e bersaglio leggono **la stessa variabile** nei **loro** costruttori
   (`llama-context.cpp:306`, una volta per contesto): a `FUSO=7` **entrambi** fondono `pre`.
2. **Ma non hanno lo stesso numero di strati**: il bersaglio ne ha **43**, la bozza **3**
   (`dflash.cpp:70-71`: «3 blocchi x ~185 nodi di Sinkhorn»). La perturbazione si accumula su 43
   strati contro 3: **le due catene non si spostano della stessa quantita'**.
3. I due **condividono `lm_head` e `tok_embd`** (`dflash.cpp:452-459` e `577-584`): il disaccordo
   si manifesta **interamente nello stato nascosto**, non nella proiezione finale.
4. La testa HC **non** e' fusa in nessuno dei due: l'ultima riduzione resta al cammino storico. La
   differenza e' tutta **a monte**, e a monte il bersaglio ha **14× piu' strati**.

Quindi `FUSO=7` **muove il bersaglio piu' di quanto muova la bozza**, e la bozza — tarata contro il
bersaglio non fuso — perde accordo. Il baratto **+2,15% di ciclo / −2,66% di p1** e' esattamente
cio' che la nota in memoria («ogni kernel fuso in piu' abbassa l'accordo bozza-bersaglio») descrive.

**Come falsificarlo senza scrivere codice**: `LLAMA_DSV4_HC_FUSO` e' una sola variabile letta da
entrambi i contesti — **non si puo' fondere solo il bersaglio**. Ma si puo' attaccare da un altro
lato: se il p1 cala **anche** con `DSPARK_NO_MARKOV=1` (che toglie l'unica parte non-DSV4 della
bozza, `dflash.cpp:13-23`), la causa e' nel **backbone**, non nella testa. E se `FUSO=1`
(solo `comb`) e `FUSO=4` (solo `post`) muovono il p1 **meno** di `FUSO=2` (solo `pre`), la tesi
"e' `pre` che pesa" e' confermata: **la maschera per pezzo e' gia' la sonda**, e il commento a
`llama-context.cpp:302-304` lo dice esplicitamente.

### 2. 43 strati, 256 esperti, 6 attivati: dove si decide la lista e in che forma arriva al backend

**La decisione — `src/llama-graph.cpp:2131-2137`** (`LETTO NEL CODICE`):

```cpp
ggml_tensor * selected_experts = selected_experts_in;
if (selected_experts == nullptr) {
    selected_experts = ggml_argsort_top_k(ctx0, selection_probs, n_expert_used); // [6, n_tokens]
}
```

Catena completa, **per strato**, **tutta dentro il grafo, tutta su device**:

1. `logits = W_gate · h` — `llama-graph.cpp:2050`, con `GGML_PREC_F32` forzato per
   `SQRT_SOFTPLUS` (riga 2052)
2. `probs = sqrt(softplus(logits))` — riga 2080 (DSV4 **esige** `SQRT_SOFTPLUS`,
   `deepseek4.cpp:76-78` altrimenti lancia)
3. `selection_probs = probs + exp_probs_b` (bias di selezione DeepSeek-V3) — riga 2091
4. **`selected_experts = argsort_top_k(selection_probs, 6)`** — riga **2134**, tipo **`I32`**,
   forma **`[6, n_tokens]`**
5. `weights = get_rows(probs, selected_experts)` — riga 2148, poi normalizzazione (2159-2173) e
   `w_scale` (2175)

**Due eccezioni nel bersaglio** (`LETTO NEL CODICE`):

- **strati a hash** — `deepseek4.cpp:1327-1330`: per `il < hparams.dsv4_hash_layer_count` la lista
  **non** viene dal router ma da una tabella indicizzata dall'**id del token**:
  `ggml_get_rows(layer.ffn_gate_tid2eid, res->t_inp_tokens)`, con `exp_probs_b` azzerato. Entra in
  `build_moe_ffn` come `selected_experts_in`, quindi il passo 4 **si salta**.
- **ACCEPTMOE** — `llama-graph.cpp:2182-2247`: riscriverebbe `selected_experts` **e** `weights` per
  residenza. **Inerte** (`LLAMA_ACCEPTMOE` non impostata) — e a leva spenta **niente** viene
  inserito nel grafo.

**In che forma arriva al backend.** `selected_experts` e' il **terzo src** (`src[2]`) di ogni
**`GGML_OP_MUL_MAT_ID`**, prodotto da `build_lora_mm_id` alle righe 2291 (`up`), 2304 (`gate`),
2393 (`down`). E' un tensore **`I32 [6, n_tokens]`** che **vive in VRAM e non passa mai
dall'host**.

Conferma indipendente della forma, dal nostro codice (`llama-context.cpp:2961-2963`):
```cpp
node->op == GGML_OP_MUL_MAT_ID && node->src[0] != nullptr && node->src[2] != nullptr &&
strstr(node->src[0]->name, "ffn_gate_exps") != nullptr &&
node->src[2]->ne[0] * node->src[2]->ne[1] <= 64
```

**Questo e' il fatto centrale per la cache esperti**: il backend legge la lista da un **puntatore
device**, non da un array host. Da qui la necessita' di un **predittore** per portare la lista
sull'host in anticipo — che e' esattamente quello che fa `deepseek4.cpp:1391-1441`: **non**
intercetta la lista vera, **ne costruisce un'altra**,
`argsort_top_k(W_gate[L+k] · h[L], n_predetti)`, la nomina `cache_pf-<strato>-<n>` (riga 1437) e la
espande come **ramo morto** (riga 1438) perche' il backend CUDA la **intercetti per nome**.
Cancelli: `cache_slot > 0` **e** `n_tokens ∈ [1, LLAMA_CACHE_ESPERTI_BATCH=8]` (riga 1419) — il
batch di verifica a 2 **passa**, il prefill a `ub 64` **no**.

### 3. Cattura e riuso dei grafi CUDA (`graphs reused = 627/1200`)

**Sono DUE meccanismi — e la scoperta principale e' che NON sono due decisioni indipendenti.**

#### 3a. Riuso del grafo **ggml** — e' questo che stampa `graphs reused`

`llama-context.cpp:1589`: `if (!graph_reuse_disable && res->can_reuse(gparams))`.
Se vero si **saltano** `res->reset()`, `ggml_backend_sched_reset`, `build_graph`, il pin,
`cache_esperti_prepara` e `ggml_backend_sched_alloc_graph`; si va dritti a `set_inputs` +
`graph_compute`. `n_reused++` a 1599.

La guardia e' in **due strati** (`llama-graph.cpp:1301-1331`):

1. **`params.allow_reuse(other)`** — `llama-graph.h:743-816`. Confronta `ubatch.equal_seqs()`,
   **`ubatch.n_tokens`** (`:747`), `n_seq_tokens`, `n_seqs`, `n_seqs_unq`, `seq_id_unq[]` (`:766`),
   presenza di `token`/`embd`, **`n_outputs`** (`:775`), i sampler (`:779`), `arch`, `gtype`,
   `cvec`, `loras`, `cross` (`:806-815`) — e **una riga nostra**, `:783-785`:
   `if (cache_esperti_predizione != other.cache_esperti_predizione) return false;`
   (campo dichiarato a `:733`, calcolato a `llama-context.cpp:2894-2906`).
2. **`input->can_reuse(params)`** per **ogni** input. Il default virtuale
   (`llama-graph.h:110-115`) ritorna **false**: un input non istruito **impedisce** il riuso.
   Per DSV4: `llm_graph_input_dsv4::can_reuse` (`llama-graph.cpp:~934`) confronta i piani
   `csa`/`hca`/`lid` e — **riga nostra**, `llama-graph.cpp:803` — **il TIPO della maschera `lid`**
   (f16 se `cparams.fused_lid`, f32 altrimenti). Con `INDEXER_FUSO=0` e' sempre f32.

#### 3b. Cattura/replay del **CUDA graph** — `ggml/src/ggml-cuda/` **[fuori blocco]**

Tutto **upstream**; verificato che le funzioni siano byte-identiche alla base.

- **Punto di decisione**: `ggml-cuda.cu:4879-4979` (`ggml_backend_cuda_graph_compute`).
  Default `use_cuda_graph = false` (`:4920-4922`).
- **Chiave del grafo**: `ggml_cuda_graph_get_key` = **il puntatore al primo nodo**
  (`ggml-cuda.cu:3233-3235`).
- **Condizioni che forzano la ricattura**, tutte `LETTO NEL CODICE`:
  - architettura `< AMPERE` → disabilitato permanentemente (`:4862-4877`);
  - **nodo non supportato**: unica condizione rimasta = `GGML_OP_MUL_MAT_ID` con
    `ggml_cuda_mul_mat_id_needs_sync` vero (`:3200-3231`; **questo hunk e' NOSTRO**, backport
    upstream #26802, commit `c770ec41c`, semanticamente equivalente al test inline precedente);
  - **numero di nodi cambiato** (`:3253-3256`);
  - **qualsiasi proprieta' di qualsiasi nodo cambiata**, via `memcmp` (`:3258-3274`);
  - warmup non completo: servono **2 chiamate stabili di fila** per catturare (`:4938-4957`);
  - `instance == nullptr` (`:4955`);
  - **sfratto per inattivita'**: spazzata ogni 5 s, distrutti i grafi non usati da ≥10 s
    (`common.cuh:1422-1431`) — e con la voce sparisce anche il warmup;
  - fallimento di `cudaGraphExecUpdate` → re-istanzia (`:3291-3307`).
- **`number_consecutive_updates` / `disable_due_to_too_many_updates` NON ESISTONO PIU'** in questo
  albero (grep vuoto): sostituiti dal booleano `warmup_complete` (`common.cuh:1229`).

**LA GUARDIA CONTRO IL RIUSO DI UN GRAFO STANTIO, E IL SUO BUCO** — `ggml-cuda.cu:3243-3248`,
`LETTO NEL CODICE`:

```c
if (cgraph->uid != 0 && cgraph->uid == graph->uid) {
    GGML_LOG_DEBUG("CUDA Graph id %zu reused\n", cgraph->uid);
    GGML_ASSERT((int)graph->node_props.size() == cgraph->n_nodes);
    return false;                       // <-- nessun altro confronto
}
```

**Se l'uid coincide, l'unica proprieta' verificata e' il NUMERO DI NODI.** Non i puntatori dei
tensori, non `data`, non `ne`/`nb`. Il confronto completo (`:3258-3274` — intera struct del nodo +
`src[j]->data` + `ne`/`nb` delle sorgenti) **si esegue solo se l'uid e' cambiato o e' 0**.
E a `:4605` c'e' il corollario: quando si fa replay, **il walker dei nodi non viene percorso
affatto** — nessun controllo host.

Il difetto che questo produce e' **gia' documentato nel nostro codice**,
`ggml/src/ggml-cuda/cache-esperti.cuh:351-358`: «un grafo CUDA catturato con n_tok=1 puo' essere
rieseguito per n_tok=2 (il corto circuito su `cgraph->uid` salta ogni confronto e l'unica guardia
e' il NUMERO di nodi, **identico fra le due taglie**)». E' **la stessa famiglia di difetti** del
commento a `llama-graph.cpp:1836-1847`, ed **e' la ragione per cui `LLAMA_OVERLAP_BATCH_MAX` vale 1**.

#### 3c. LA CATENA CHE UNISCE I DUE — il pezzo che vale la lettura

`DEDOTTO`, ma da righe tutte lette:

```
riuso ggml vero (llama-context.cpp:1589)
  => NON si chiama ggml_backend_sched_reset (che sta solo nel ramo else, :1602)
  => sched->is_alloc resta true (ggml-backend.cpp:2430 lo azzera, :2478 lo alza)
  => ggml_backend_sched_graph_compute_async salta split_graph (:2495)
  => gli uid degli split restano identici (:1730 li rigenera solo dentro split_graph)
  => ggml_cuda_graph_update_required esce al corto circuito (:3243-3248)
  => cudaGraphLaunch di un exec catturato in una chiamata precedente
```

**Quindi `graphs reused = 627` NON e' solo un contatore di build risparmiate: e' anche il numero
di REPLAY di CUDA graph.** I due riusi sono **lo stesso evento**. E l'inverso vale: ogni
ricostruzione ggml costa una **ri-cattura CUDA** (uid nuovo → `update_required` vero →
`cudaStreamBeginCapture` a `:4969`), il cui costo (~50 ms) e' gia' a verbale nel nostro commento a
`llama-context.cpp:855-856`.

**Nota su `GGML_CUDA_GRAPH_OPT=0`**: e' **upstream** (PR #16991), gate a `ggml-cuda.cu:5018-5021`
con `env != nullptr && atoi(env) == 1`. **`0` e' identico ad assente, che e' gia' il difetto: e'
un no-op.** E anche a `1` sarebbe inerte per noi: accetta solo nodi con `ggml_nrows(node) <= 1`
(`:5069`, con TODO esplicito) e solo nomi contenenti `"attn_norm"` (`:5096`) con fan-out
esattamente 3 (`:5084`) — l'MLA di DSV4 non ha un QKV a 3 vie. `LETTO NEL CODICE` i filtri;
`DEDOTTO` la conseguenza.

**Trappola upstream, bonificata in casa il 18/8**: upstream testa `GGML_CUDA_DISABLE_GRAPHS`
con `getenv(...) != nullptr` (a presenza: **anche `=0` DISABILITA i grafi**). Negli alberi
vivi (overlap, subtract) dal 18/8 il cancello e' A VALORE (`atoi`, `common.cuh`): `=0` ≡
assente. A ogni rebase da upstream la bonifica va ri-applicata; i binari pre-18/8 restano
a presenza (LEDGER_18_AGOSTO.md).

### 4. Il modello di bozza (dflash / DSpark): aggancio, e dove finiscono i suoi tensori

#### Come si aggancia al bersaglio (`LETTO NEL CODICE`)

- **`cparams.ctx_other`** e' il puntatore al contesto del bersaglio, ed e' **il discriminante
  "sono la bozza"** usato ovunque: `llama-context.cpp:1677`
  (`prepara(..., ctx_other != nullptr ? 1 : 0)`), `llama-graph.cpp:2203-2204` (ACCEPTMOE **escluso**
  sulla bozza), `llama-context.cpp:2172` (VRAM a fasi **solo sul bersaglio**).
- **Pesi condivisi col bersaglio**: la bozza **non ha** `output` ne' `tok_embd` propri —
  `dflash.cpp:452-459` (`lm_head`) e `dflash.cpp:577-584` (`tok_embd`), entrambi via
  `llama_get_model(cparams.ctx_other)`.
- **Feature del bersaglio**: `target_layer_ids` dai metadati GGUF (`dflash.cpp:29-33`), con
  `n_embd_inp_enc = |target_layers| × n_embd` (riga 33). Il grafo **encoder**
  (`dflash.cpp:240-253`) prende gli stati concatenati dei layer-tap, li proietta con `fc` e li
  normalizza. Lato bersaglio la cattura e' `capture_layer_inp` (`deepseek4.cpp:1280-1289`),
  abilitata da `cparams.embeddings_layer_inp[il]`; **nostro** e' lo slot in piu'
  (`llama-context.cpp:160-162`, `n_layer + 1`: «index n_layer captures the output of the final
  layer»), con l'assert allargato a `llama-context.cpp:1408`.
- **Testa di Markov** (`dflash.cpp:256-344`): riscrive `res->t_logits` aggiungendo il bias
  `w2 · w1[prev]` **incatenato per posizione del blocco**, con **`ggml_argmax` dentro il grafo**
  (riga 323). `block_size` dai metadati GGUF (`dflash.cpp:268-271`). TODO onesto a riga 296:
  la catena e' **greedy**, i parametri di campionamento non toccano il condizionamento.
- **Testa di confidenza** (opzionale, `dspark_conf_proj`): predice l'accettazione per posizione e
  la pubblica in `res->t_h_nextn` (`dflash.cpp:332-340`).
- **Nodi massimi**: `llama-context.cpp:2823` — **riga nostra** — aggiunge `LLM_ARCH_DFLASH` alla
  lista che usa `max(n_tokens*40, 32*n_tensors)`, «DSpark drafters may reuse the deepseek4-style
  MLA/MoE/HC graph».

#### **IL PROPONENTE CALCOLA ESPERTI SU CPU? — SI'. CONFERMATO, NON DEDOTTO.**

**Fatto 1 — la bozza ha un MoE e lo esegue.** `LETTO NEL CODICE`:
`src/models/dflash.cpp:415-427` chiama **`build_moe_ffn`** con `layer.ffn_up_exps`,
`layer.ffn_gate_exps`, `layer.ffn_down_exps`, `n_expert`, `hparams.n_expert_used`. I tensori sono
creati per ogni strato a `dflash.cpp:180-182`. **Non e' una deduzione: e' una chiamata.**
Vale sul ramo `dflash_dsv4_backbone`, rilevato dalla presenza di `attn_q_a.weight`
(`dflash.cpp:54`) e imboccato a `dflash.cpp:595-598` — che e' il ramo attivo per DSpark.
`build_moe_ffn` riceve `selected_experts_in = nullptr` (riga 427): **la bozza fa il proprio
`argsort_top_k`, indipendente da quello del bersaglio.**

**Fatto 2 — `-otd` manda quei tensori su CPU per tutti gli strati tranne `blk.0`.** **[fuori blocco]**
La semantica dell'override e' **PRIMO-CHE-MATCHA**, `LETTO NEL CODICE` a
`src/llama-model-loader.cpp:1162-1190`:

```cpp
1167  for (const auto * overrides = tensor_buft_overrides; overrides->pattern != nullptr; ++overrides) {
1168      std::regex pattern(overrides->pattern);
1169      if (std::regex_search(tensor_name, pattern)) {         // regex_search, NON regex_match
1170          if (overrides->buft == ggml_backend_cpu_buffer_type()) {
1172              buft = select_weight_buft(hparams, t_meta, op, buft_list_cpu);
1179          } else { buft = overrides->buft; }
1187          break;                                              // <-- primo match, poi esce
```

L'ordine di iterazione e' l'ordine di riga di comando (`common/arg.cpp:290-308`,
`overrides.push_back` in sequenza). Quindi:

| tensore della bozza | regola che vince | buffer finale |
|---|---|---|
| `blk.0.ffn_{gate,up,down}_exps.weight` | **#1** (`blk\.0\.…=CUDA0_Mapped`) | **`CUDA0_Mapped`** |
| `blk.1.*_exps.weight`, `blk.2.*_exps.weight` | **#2** (`…=CPU`) | **`CPU`** (o extra-buft CPU) |
| tutto il resto | nessuna | CUDA0 (`-ngld 99`) |

**Il modello di bozza ha 3 blocchi**, confermato da tre fonti indipendenti:
`dflash.cpp:71` («Il conto: **3 blocchi** x ~185 nodi di Sinkhorn»), `PATCH_CACHE_BOZZA.md:14-16`
(«`blk.1` e `blk.2` restano `CPU`»), e `audit/36-acceptmoe-spenta.md:26` («`n_layer=3` nel log»).
⇒ **due strati su tre della bozza hanno gli esperti su buffer `CPU`.**

**Fatto 3 — quei `MUL_MAT_ID` girano davvero su CPU in decode.** `LETTO NEL CODICE`,
`ggml/src/ggml-backend.cpp:1111-1132`: il nodo segue il backend del primo `src` marcato
`USAGE_WEIGHTS`; per un buffer `CPU` il backend CUDA non e' candidato. L'unica scappatoia
(`:1122-1129`) richiede `ggml_backend_offload_op`, che per CUDA e'
`get_op_batch_size(op) >= op_offload_min_batch_size` con soglia **32**
(`ggml-cuda.cu:6005-6008`, `:6217`). Il decode della bozza ha un batch di poche posizioni ⇒
**resta su CPU**; solo il prefill (batch ≥ 32) viene offloadato, **copiando i pesi per-op**.

**Fatto 4 — nessuna nostra leva MoE tocca la bozza.** `LETTO NEL CODICE`:
- `build_moe_ffn_overlap` e' dietro `arch == LLM_ARCH_DEEPSEEK4` (`llama-graph.cpp:2246`) ⇒
  la bozza e' `LLM_ARCH_DFLASH` ⇒ **lo split CPU/GPU non si costruisce sulla bozza**;
- ACCEPTMOE e' dietro `arch == LLM_ARCH_DEEPSEEK4 && cparams.ctx_other == nullptr`
  (`llama-graph.cpp:2203-2204`) ⇒ **doppiamente escluso**;
- **predittore di route** e **cache esperti** vivono in `deepseek4.cpp` ⇒ **assenti dalla bozza**.

⇒ **Il MoE della bozza gira sul cammino classico, su CPU, nudo**: nessuna cache, nessuna
sovrapposizione, nessuna partizione. **La deduzione su cui avete costruito e' confermata dalla
lettura.**

#### Cosa resta su GPU nella bozza

Il regex `-otd` matcha **solo** `ffn_(gate|up|down)_exps.weight`. **NON** matcha:
- `ffn_{gate,up,down}_shexp` — **esperti condivisi** (`dflash.cpp:184-186`): restano su GPU;
- `ffn_gate_inp.weight`, `ffn_exp_probs_b`, `ffn_norm` — **il router resta su GPU**;
- tutto MLA (`wq_a`, `wq_b`, `wkv`, `wo_a`, `wo_b`), le hyper-connection (`hc_*`), `fc`,
  `output_norm`, `markov_w1/w2`, `conf_proj`.

⇒ **per ognuno dei 2 strati con esperti su CPU c'e' almeno un confine GPU→CPU→GPU per forward**:
il router gira su GPU e produce `selected_experts` in VRAM, i 3 `MUL_MAT_ID` girano su CPU,
e l'uscita deve risalire per la somma con lo shared expert (`dflash.cpp:437`) e per l'`hc_post`
(`dflash.cpp:440`). `DEDOTTO, non verificato` sul conteggio esatto degli split — si legge con
`GGML_SCHED_DEBUG=2`, che il commit `b839bf1ee` ha reso visibile anche a livello INFO
(`GGML_SCHED_DEBUG_INFO`).

#### Nota sul buffer `CUDA0_Mapped` **[fuori blocco]**

`ggml-cuda.cu:1357-1404`: **`cudaHostAlloc(cudaHostAllocMapped|cudaHostAllocPortable)`** (riga
1363) + **`cudaHostGetDevicePointer`** (1373). **Nessun `cudaHostRegister`.** I byte restano in
**RAM host**; `get_base` restituisce il puntatore **device** (`:1310-1313`).
`is_host` = **`ibrido && g_cuda_mapped_uva`** (`:1439`), quindi con `LLAMA_MAPPED_IBRIDO=1` e'
**vero** e **anche la CPU accetta quel buffer**. Il `get_name` condivide **di proposito** il
puntatore a funzione col buft CUDA normale (`:1456`, commento `:1288-1290`), cosi'
`ggml_backend_buft_is_cuda` (`:822-824`) lo accetta comunque.

---

## COSE CHE NON TORNANO

1. **Il conto dei nodi di Sinkhorn nel commento e' sottostimato ×2.**
   `deepseek4.cpp:42-45` dice «~185 nodi per strato x 43 strati = ~7.900 lanci per forward», ma la
   stessa riga dice anche «**quaranta volte per strato**» — cioe' 2 blocchi × 20 iterazioni.
   `build_hc_pre` a 6 argomenti e' chiamata **due volte per strato** (`deepseek4.cpp:1298` e
   `1314`; idem sulla bozza, `dflash.cpp:377` e `409`), quindi il Sinkhorn e' **~370 nodi per
   strato, ~15.900 per forward**. Il conto dei nodi totali (34.329 → 10.507) torna **solo** col
   fattore 2. Stesso errore in `dflash.cpp:71` («3 blocchi x ~185 = ~550» → sono ~1.100).

2. **`LLAMA_OVERLAP_K=2` e' inerte sui forward di verifica.** `llama-graph.cpp:1848-1856` esclude
   `n_tokens > 1` e `LLAMA_OVERLAP_BATCH_MAX` vale **1**. Con `--spec-draft-n-max 1` il forward del
   bersaglio ha **2** posizioni quando la bozza c'e'. **Lo split si costruisce solo sui forward a 1
   token.** Tutti i verdetti «K=2 vale X» andrebbero riletti sapendo su **quale frazione** dei
   forward agisce. `DSPARK_PROF=1` separa gia' i due bucket (`block` / `tok1`).

3. **La soglia dell'ibrido e' 2, e il nostro batch di verifica e' esattamente 2.**
   `ggml-cuda.cu:5534-5544`: `get_op_batch_size(op) < soglia` con `soglia = 2`. A `n_tokens = 2` la
   condizione e' **falsa per un token**, e gli esperti mappati restano su GPU; a `n_tokens = 1`
   scendono su CPU. **Il regime cambia sotto i piedi a ogni alternanza**, ed e' la **stessa**
   alternanza che rompe il riuso del grafo. Qualunque media su 1.200 token mescola due regimi.

4. **I riferimenti di riga nel nostro commento sui CUDA graph sono stantii.**
   `llama-context.cpp:846-856` cita `ggml-cuda.cu:3145` e `ggml-backend.cpp:1710`; oggi sono
   **`ggml-cuda.cu:3243-3248`** e **`ggml-backend.cpp:1730`**. La sostanza tiene, i numeri no.

5. **`splits(block)` e `nodes(block)` mentono sui grafi riusati.** `llama-context.cpp:1687-1692`:
   aggiornati **solo nel ramo `else`** (rebuild). Con il 52% di riuso, il valore stampato e'
   l'ultimo rebuild, non lo stato corrente. E' un'istantanea e va letta come tale.

6. **Il pin del ramo CPU non viene riapplicato sui grafi riusati** — e il commento lo dice
   (`llama-context.cpp:1625-1626`: «Va rifatto a ogni rebuild; **il riuso del grafo conserva le
   precedenti**»). Corretto, ma significa che l'assegnazione dei backend e' stabile **solo finche'
   il grafo non si ricostruisce**: `GGML_SCHED_DEBUG=2` va letta al **primo decode dopo un
   rebuild**, non a caso.

7. **La testa HC non e' mai fusa, e la guardia sembra difensiva piu' che necessaria.**
   `deepseek4.cpp:273` e `400` richiedono `il >= 0`; `build_hc_head` passa `-1`
   (`deepseek4.cpp:446`). La motivazione e' il probe (`llama-context.cpp:628`,
   `GGML_ASSERT(node.il >= 0)`). Costa 7 lanci per forward — irrilevante — ma rende la numerica
   **disomogenea fra i 43 strati e la testa**, che e' esattamente il tipo di crepa che un cancello
   SHA non vede.

8. **`ACCEPTMOE` a leva spenta non e' del tutto gratis lato host.** Il blocco
   `llama-context.cpp:2288-2334` gira **a ogni ubatch**; la condizione `acceptmoe_spec > 0`
   (riga 2306) taglia subito il ciclo `una_seq`, ma le due scritture in `acceptmoe_stato_host`
   avvengono comunque. Trascurabile, ma **non zero** come suggerisce il commento a
   `llama-graph.cpp:2186` («A leva spenta NIENTE viene inserito») — che parla del **grafo**, non
   dell'host.

9. **`graph_params()` interroga tutti i backend a OGNI forward** (`llama-context.cpp:2894-2906`,
   riga nostra) con `ggml_backend_reg_get_proc_address`, che fa una ricerca per **stringa**. E' sul
   cammino caldo, prima di `can_reuse`. Costo probabilmente trascurabile, ma e' l'unico
   `get_proc_address` che gira anche quando il grafo viene riusato.

10. **`LLAMA_OVERLAP_K` viene letta due volte, in due unita' di traduzione**
    (`llama-graph.cpp:1825` per costruire, `llama-context.cpp:1638` per il pin), con due
    `static const` **indipendenti**. Oggi entrambe usano `atof` — ma la correzione documentata a
    `llama-context.cpp:1631-1639` racconta che per un periodo una usava `atoi`, e con `0<K<1`
    «il pin non vedeva il ramo CPU costruito: split GPU/GPU, ASYNC mai ingaggiato». E' una trappola
    ancora aperta per chi ne aggiunga una terza.

11. **`GGML_CUDA_GRAPH_OPT=0` nello script non fa nulla** (gate `atoi(env) == 1`,
    `ggml-cuda.cu:5019`). Non e' un difetto — e' una riga protettiva — ma non va contata come
    «leva impostata». La cugina `GGML_CUDA_DISABLE_GRAPHS` si comportava all'opposto (**`=0`
    disabilitava**, test su `!= nullptr`): bonificata il 18/8, ora A VALORE — ma solo nei
    binari compilati dal 18/8 in poi (LEDGER_18_AGOSTO.md).

---

## RIASSUNTO (15 righe)

1. `LLAMA_DSV4_HC_FUSO` e' una **bitmask**: 1=`comb`, 2=`pre`, 4=`post` (`llama-context.cpp:306-312`).
2. **`FUSO=5` = comb+post; `FUSO=7` aggiunge `pre`: l'unica differenza fra 5 e 7 e' `pre`.**
3. `pre` riduce i 4 flussi HC a uno, `comb` costruisce la 4×4 doppiamente stocastica (20 Sinkhorn),
   `post` li riespande (`deepseek4.cpp:260`, `291`+`371`, `389`).
4. Da 5 a 7 spariscono **602 lanci** (86 chiamate × 7 kernel) e **~1.290 nodi** per forward.
5. Il p1 cala perche' il kernel fuso usa **FMA** (`dsv4-hc.cu:129-135`) sotto **`-use_fast_math`**
   (`ggml-cuda/CMakeLists.txt:197`): **aritmetica diversa**, non implementazione diversa.
6. E la perturbazione si amplifica su **43 strati** nel bersaglio contro **3** nella bozza: i due
   si spostano di quantita' diverse e l'accordo cala. La maschera per pezzo **e' gia' la sonda**.
7. Gli esperti si scelgono **dentro il grafo**: `argsort_top_k(probs+bias, 6)` → **`I32 [6, n_tok]`**
   (`llama-graph.cpp:2134`), `src[2]` dei 3 `MUL_MAT_ID` per strato (**129 per forward**).
8. **La lista non passa mai dall'host**: vive in VRAM. Da qui la necessita' di un **predittore**.
9. `graphs reused` e' **cumulativo**, conta **ubatch** non token, riguarda **solo il bersaglio** e
   **il server non lo azzera mai** (`llama-context.cpp:1599`, `4706`, `server-context.cpp:727`).
10. Il riuso si rompe soprattutto su **`ubatch.n_tokens` che alterna 1 e 2** (`llama-graph.h:747`).
11. **Riuso ggml e replay CUDA sono LO STESSO EVENTO**: riuso ⇒ `is_alloc` resta vero ⇒
    `split_graph` saltato ⇒ uid invariati ⇒ corto circuito a `ggml-cuda.cu:3243-3248`, dove
    **l'unica guardia e' il numero di nodi** — non i puntatori.
12. **La bozza calcola esperti: e' una chiamata a `build_moe_ffn`, `dflash.cpp:415`.** Con `-otd`
    (semantica **primo-che-matcha**, `llama-model-loader.cpp:1167-1187`) `blk.0` va su
    `CUDA0_Mapped` e **`blk.1`/`blk.2` su `CPU`**: 2 strati su 3.
13. **Nessuna nostra leva MoE tocca la bozza**: overlap e ACCEPTMOE sono dietro
    `arch == LLM_ARCH_DEEPSEEK4`; cache e predittore vivono in `deepseek4.cpp`. Il MoE della bozza
    e' **CPU seriale, nudo**.
14. **`LLAMA_OVERLAP_K=2` non si ingaggia sui forward a 2 token** (`llama-graph.cpp:1853`,
    `BATCH_MAX=1`): agisce solo sui forward a 1 token.
15. **La soglia dell'ibrido e' 2 e il batch di verifica e' 2**: gli esperti mappati restano su GPU
    a 2 token e scendono su CPU a 1. Ogni media su 1.200 token **mescola due regimi**.
