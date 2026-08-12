# UP_B — `ggml/src/ggml-cuda/` (tutto tranne `mmq.cu`, `mmq.cuh`, `cpy.cu`)

Repo `D:\llama-overlap`, ramo `overlap`, HEAD `9b7f9eea7`.
`git merge-base HEAD upstream/master` = `5c3a58686` (9 luglio). Upstream avanti di 436 commit.
34 commit toccano `ggml/src/ggml-cuda/`; tolti quelli di `mmq.*` e `cpy.cu` restano **21** nella mia fetta.

Profilo di riferimento (nsys `--cuda-graph-trace=node`, banco senza bozza, 512 slot, token da 97,4 ms):

| kernel | ms/token | % |
|---|---|---|
| `kern_fj_copia` (nostro) | 34,36 | 37% |
| `mul_mat_vec_q` | 26,62 | 29% |
| `mul_mat_vec_q_moe_masch` | 9,64 | 10% |
| `mul_mat_q` | 5,25 | 6% |
| `mul_mat_vec_f<half>` | 5,14 | 6% |
| `kern_decidi` (nostro) | 1,67 | 2% |
| `k_bin_bcast` (add+mul) | 1,80 | 2% (~1.300 istanze/token) |
| `flash_attn_ext_f16` | 1,31 | 1% |
| `rms_norm_f32` | 1,08 | 1% |
| **totale GPU** | **93,28** | |

---

# 0. Il titolo, prima di tutto

**Su 21 commit, uno solo vale la pena: `846e991ec` (#25896, `sqrt_softplus` in topk-moe).**
È l'unico che tocca un cammino nostro caldo e non ce l'abbiamo. Tutto il resto è già
portato, o non raggiungibile, o zero.

E un risultato negativo che vale quanto uno positivo:

> **Il 29% del profilo (`mul_mat_vec_q`, 26,62 ms) e il 6% (`mul_mat_vec_f`, 5,14 ms)
> non hanno UN SOLO commit a monte in 436.**
> `git log HEAD..upstream/master -- ggml/src/ggml-cuda/mmvq.cu` → un solo commit,
> ed è l'aggiunta del tipo `Q2_0` (che non usiamo).
> `mmvf.cu`, `binbcast.cu`, `fattn-mma-f16.cuh`, `fattn-common.cuh`, `fattn-vec.cuh`
> → **zero commit**.
> Il 35% del tempo GPU sta in file che upstream non ha toccato. Non c'è niente da prendere lì.

E una cosa trovata di lato che vale più del porto (§7.2):

> I ~1.300 `k_bin_bcast` **non vengono dal MoE**: il MoE ne fa **4 per strato**.
> Il grosso è nelle nostre **hyper-connections**, e quanti ne restano dipende da
> quali bit di `LLAMA_DSV4_HC_FUSO` sono accesi — una maschera che **di default è 0,
> tutto spento** (`llama-context.cpp:305-312`).
> Il moltiplicatore strutturale più grosso è il ciclo di **Sinkhorn**
> (`deepseek4.cpp:320-323`: 20 iterazioni × 4 binbcast × 2 chiamate = **~158 lanci per
> strato**), che il bit `comb` (=1) copre.
> Quello che nel banco resta **aperto** è il bit `pre` (=2): con «FUSO=5 batte FUSO=7»
> (5 = `comb`+`post`) `pre` è ancora spento, e vale **~600 lanci per forward —
> sette volte il porto**. È già scritto: aspetta il cancello dell'accordo
> bozza-bersaglio, non un merge.

---

# 1. IL REPERTO — `a1f96d4fc` e l'assert su `CUDA0_Mapped`

## Verdetto: **la segnalazione è FALSA per il nostro albero, e il commit non ci servirebbe comunque.** Anzi, portarlo ci fa danno.

Tre fatti, tutti verificati sul disco.

### (a) L'assert da noi è GIÀ rilassato, e in modo che copre esattamente `CUDA0_Mapped`

Merge-base `5c3a58686`, `ggml_cuda_graph_evaluate_and_capture`:

```c
assert(node->buffer->buft == ggml_backend_cuda_buffer_type(cuda_ctx->device));
...
assert(node->src[j]->buffer->buft == ggml_backend_cuda_buffer_type(cuda_ctx->device) ||
       (integrated && ggml_backend_buft_is_cuda_host(node->src[j]->buffer->buft)));
```

`ggml-cuda.cu:4788-4796` **oggi da noi**:

```c
#ifndef NDEBUG
    assert(ggml_backend_buft_is_cuda(node->buffer->buft));
    for (int j = 0; j < GGML_MAX_SRC; j++) {
        if (node->src[j] != nullptr) {
            assert(node->src[j]->buffer);
            assert(ggml_backend_buft_is_cuda(node->src[j]->buffer->buft) ||
                   (integrated && ggml_backend_buft_is_cuda_host(node->src[j]->buffer->buft)));
        }
    }
#else
    GGML_UNUSED(integrated);
#endif  // NDEBUG
```

Il confronto per **puntatore al buffer type** è diventato un confronto per **identità di
backend**. E `ggml_backend_buft_is_cuda` (`ggml-cuda.cu:822`) è:

```c
return buft->iface.get_name == ggml_backend_cuda_buffer_type_get_name;
```

mentre `ggml_backend_cuda_mapped_buffer_type()` (`ggml-cuda.cu:1456`) installa
**quello stesso puntatore a funzione** come proprio `get_name`, e il commento a
`ggml-cuda.cu:1288` dice che è deliberato:

> «si riusa `ggml_backend_cuda_buffer_type_get_name` come get_name, così
> `ggml_backend_buft_is_cuda()` — che confronta il PUNTATORE a funzione — riconosce
> questo buffer come CUDA».

Quindi `ggml_backend_buft_is_cuda(CUDA0_Mapped)` è **vero** e l'assert non scatta,
né sul nodo né sulle sorgenti. Con `NDEBUG` tolto, quella riga passa.

### (b) Anche se avessimo tenuto la forma stretta, `a1f96d4fc` NON ci avrebbe salvati

La sua scappatoia è `(integrated && ggml_backend_buft_is_cuda_host(node->buffer->buft))`.
Due mancate, indipendenti:

1. `integrated` è **falso**. `ggml_cuda_init()` lo forza a `false` fuori da HIP
   (e `c7d872292` in questa stessa finestra lo conferma: `#if defined(GGML_USE_HIP)
   ... #else info.devices[id].integrated = false;`). Una 3060 è discreta.
2. `ggml_backend_buft_is_cuda_host` (`ggml-cuda.cu:1201`) confronta contro
   `ggml_backend_cuda_host_buffer_type_name`. Il nostro `CUDA0_Mapped` usa
   `ggml_backend_cuda_buffer_type_get_name`. **Non è un `cuda_host`**, per costruzione:
   `cuda_host` è `cudaMallocHost` impacchettato come buffer CPU con `is_host = true`;
   il nostro è `cudaHostAlloc(cudaHostAllocMapped)` che espone il puntatore **device**.

Sono due meccanismi diversi che il commit non tocca.

### (c) Era comunque l'assert sbagliato di cui preoccuparsi

`a1f96d4fc` rilassa l'assert sul **`node->buffer`**, cioè sull'**uscita** del nodo.
`CUDA0_Mapped` ospita i pesi degli esperti: sono **sorgenti**, non uscite. Il primo a
saltare sarebbe stato quello sulle `src[]`, che upstream **non** ha rilassato per il
nostro caso (la sua eccezione lì è la stessa `integrated && is_cuda_host`).

## Cosa fare

**NON PORTARE.** E di più: il diff di `a1f96d4fc` **riscrive quella riga alla forma
`==` stretta**. Se un giorno il merge lo tira dentro senza guardare, **ci rimette
l'assert che ci ammazzerebbe la build di debug al primo nodo esperto**. Nella
risoluzione del conflitto va tenuta **la nostra** forma (`ggml_backend_buft_is_cuda`).
Vale la pena metterci un commento nel codice.

Numero che deve muoversi: **nessuno.** È un no-op a runtime (`#ifndef NDEBUG`) e a
release non è nemmeno compilato.

---

# 2. Il commit che vale — `846e991ec` (#25896)

**`cuda: add sqrt_softplus in topk-moe for dsv4`** — `ggml-cuda.cu`, `topk-moe.cu`, `topk-moe.cuh`

### Cosa cambia, letto nel diff

Tre pezzi:

1. `topk-moe.cuh`: aggiunge `bool sqrt_softplus{}` a `ggml_cuda_topk_moe_args`.
2. `topk-moe.cu`: aggiunge `sqrt_softplus_warp_inplace<>()` —
   `sqrtf(v > 20.0f ? v : logf(1.0f + expf(v)))` — e il ramo `use_sqrt_softplus`
   nel kernel; e in `ggml_cuda_should_use_topk_moe` accetta `GGML_UNARY_OP_SOFTPLUS`
   oltre a `SIGMOID`.
3. `ggml-cuda.cu` / `ggml_cuda_topk_moe_fusion`: riconosce la coppia
   `UNARY(SOFTPLUS)` + `SQRT` con `nodes[i+1]->src[0] == nodes[i]`, e riscrive
   l'indicizzazione del pattern con un `i_probs` calcolato invece degli `i+2/i+3/i+4`
   fissi (perché ora l'attivazione di gating può occupare 1 o 2 nodi).

### Perché ci riguarda

`src/models/deepseek4.cpp:76-77` **rifiuta il modello** se il gating non è
`LLAMA_EXPERT_GATING_FUNC_TYPE_SQRT_SOFTPLUS`, e `src/llama-graph.cpp:2078-2081`
costruisce `probs = ggml_sqrt(ctx0, ggml_softplus(ctx0, logits))`.

Il nostro `ggml_cuda_topk_moe_fusion` (`ggml-cuda.cu:3426-3431`) fa:

```c
if (nodes[node_idx]->op == GGML_OP_UNARY) {
    if (ggml_get_unary_op(nodes[node_idx]) != GGML_UNARY_OP_SIGMOID) {
        return false;                                   // <-- DS4 esce QUI
    }
    args.sigmoid = true;
}
```

→ **la fusione topk-moe è morta per DeepSeek-V4 nel nostro albero.** Non è
"sub-ottimale": è un `return false` al primo nodo. Non c'è nessun `sqrt_softplus`
in `topk-moe.cu`, `topk-moe.cuh` o `ggml-cuda.cu` da noi (verificato con grep:
zero occorrenze).

Conseguenza: per **ogni strato MoE** il gating gira come catena di nodi separati —
`softplus`, `sqrt`, `add` del bias, `argsort`, `view`, `get_rows`, e la
normalizzazione dei pesi (`sum_rows` + `div`, più l'eventuale `scale`) — invece di
un solo `topk_moe_cuda`.

### A quale voce del profilo si aggancia, e con quale numero

La lista di op che la catena fusa assorbe è nel nostro codice, `ggml-cuda.cu:3886-3907`:
`{gating, RESHAPE, ADD, ARGSORT, VIEW, GET_ROWS, RESHAPE, SUM_ROWS, CLAMP, DIV,
RESHAPE, SCALE}`. Di queste, due sono `k_bin_bcast`:

- **`ADD`** `probs + exp_probs_b` — `llama-graph.cpp:2091` (`ffn_moe_probs_biased`)
- **`DIV`** `weights / weights_sum` — `llama-graph.cpp:2169` (`ffn_moe_weights_norm`,
  attivo perché `expert_weights_norm = true`)

E **non su tutti i 43 strati**: i 3 strati hash (`il < 3`, `deepseek4.cpp:1327-1330`)
ricevono `selected_experts_in` già pronto, non hanno il nodo `ARGSORT` e il pattern
non può agganciarsi comunque.

> **2 lanci × 40 strati = 80 lanci `k_bin_bcast` in meno per forward, su ~1.300.
> Circa il 6%** di quella voce, cioè **~0,11 ms su 97,4**. Più i lanci di
> `argsort`/`get_rows`/`softplus`/`sqrt`/`sum_rows`/`clamp`/`scale`, che nella
> tabella del profilo non compaiono nemmeno (sotto la soglia di taglio) ma sono
> altrettanti nodi a ~1,4 µs l'uno.

**Non tocca** il `MUL experts*weights` (`llama-graph.cpp:2406`, mai fuso nemmeno a
monte) né la catena dei 5 `ADD` di aggregazione (`:2430`), che la nostra multi-add
(`ggml-cuda.cu:3993-4013`) collassa già in **un lancio solo** con `n_fuse=5`.

È **lanci**, non banda. Non è una leva da +10%; è una leva da **frazione di punto**,
dentro la deriva del banco del 2,4%.

### Rischio di conflitto col nostro fork

**Medio-alto**, ed è il motivo per cui va guardato bene prima di toccarlo:

- `ggml_cuda_topk_moe_fusion` sta a `ggml-cuda.cu:3412`, cioè **dentro** il file dove
  abbiamo +1.072 righe rispetto al merge-base. Il diff upstream riscrive
  l'indicizzazione del pattern (`i+2/i+3/i+4` → `i_probs+2/...`) e l'inserimento
  di `ops`; il nostro `ggml_cuda_try_fuse` locale ha già le sue varianti
  (`ggml-cuda.cu:4187/4193/4201/4206/4396/4403`) che indicizzano `ops[3]`, `ops[8]`,
  `ops[9]`. **Vanno riletti tutti**, non solo il blocco toccato.
- Il `GET_ROWS` finale della catena fusa produce il tensore `ids` — che è **la stessa
  cosa che il nostro predittore di route intercetta** (`cache_pf-<strato>-<n>`,
  `ggml-cuda.cu:4714`, il gancio di `kern_prenota`). Se la fusione fa sparire il nodo
  `VIEW`/`GET_ROWS` intermedio, va verificato che il nome/nodo che intercettiamo
  esista ancora. **Questo è il punto che può rompere silenziosamente il prefetch,
  non la fusione in sé.**
- `ggml_cuda_can_fuse` deve poter attraversare i nodi di gating: da noi c'è già
  `{ GGML_OP_UNARY, GGML_OP_MUL }` con `GGML_UNARY_OP_SOFTPLUS` a
  `ggml-cuda.cu:4545` (fusione **diversa**, softplus+mul). Attenzione che le due non
  si rubino il nodo.

### Quale numero deve muoversi

- **`k_bin_bcast`: da ~1.300 istanze a ~1.220** (−80). Se ne scendono di più o di meno,
  il pattern si è agganciato dove non doveva.
- Il **conteggio nodi del grafo** (oggi 10.507 dopo le fusioni HC) deve scendere di
  ~40×(numero di nodi assorbiti dal pattern). È la misura più pulita e senza rumore:
  si legge alla cattura, non serve il banco.
- **t/s: aspettarsi ~+0,1%, cioè NIENTE di misurabile** (la deriva del banco è 2,4%).
  Se i t/s si muovono, non è questa fusione: è la build (vedi
  «+3,8% non attribuito, ed è della build»).
- **Il cancello vero è l'accordo bozza-bersaglio**, non i t/s. Vale qui la lezione di
  «FUSO=5 batte FUSO=7»: ogni kernel fuso in più può abbassare l'accordo. Un
  `topk_moe_cuda` che rifà `sqrt(softplus)` in un ordine diverso **non è
  bit-identico** alla catena `softplus`→`sqrt`→`add`→`argsort`. Va misurato **prima**
  l'accordo, poi il resto.

---

# 3. Già nostro — non c'è niente da portare (verificato byte a byte)

| commit | PR | stato |
|---|---|---|
| `0dc74e332` | #25585 DeepseekV4 fused hyper-connection ops | **`dsv4-hc.cu` e `dsv4-hc.cuh` sono IDENTICI ai nostri** (confronto contenuto, a meno di CRLF). Nostro commit `0adb16c64` («fusione hyper-connection (+16,5%)»). Gli innesti in `ggml-cuda.cu` ci sono: `GGML_OP_DSV4_HC_{COMB,PRE,POST}` a righe 2990-2997 e 5954-5960. |
| `3b5321936` | #25545 CUDA `GGML_OP_LIGHTNING_INDEXER` | **`lightning-indexer.cu` IDENTICO al nostro.** Nostro commit `0441857cb`. Innesti a `ggml-cuda.cu:2987` e `:5964`. |
| `ebb546b7e` | #26802 `mul_mat_id_needs_sync` | già portato oggi. |
| `9bd4c09ea` | #26385 data-race in `block_reduce` | **risolto da noi in modo diverso e più forte** — vedi sotto. |

## `9bd4c09ea` (#26385) — già coperto, e meglio

Upstream sceglie di **non** mettere la barriera dentro `block_reduce` («comes at a
potential perf cost») e la mette ai chiamanti: un `__syncthreads()` in `soft_max_f32`
prima della seconda riduzione, doppio buffer in
`soft_max_f32_parallelize_cols_single_row`, e `s_sum + 32` in `group_norm_f32`.

Noi abbiamo fatto l'opposto: **barriera d'uscita dentro `block_reduce`**,
`common.cuh:642`, con il commento che cita #26385 e la ragione nostra:

> «Da noi il punto vivo è il softmax dello stato HCA (ncols=128, 4 warp), la cui
> uscita finisce nell'anello persistente: un innesco corrompe la sessione, non un token.»

La nostra copre **tutti** i riusi (softmax, group_norm, il kernel cooperativo a
4 riduzioni) invece dei tre siti noti, e la barriera sta sotto `if (block_size >
WARP_SIZE)` — condizione **uniforme sul blocco** (`block_size` è o costante di
template o `blockDim.x`), quindi rispetta la regola delle barriere sullo stesso sito.

**NON PORTARE.** Portarlo aggiungerebbe barriere ridondanti ai chiamanti.
L'unico pezzo che avrebbe un senso è il **doppio buffer** di
`soft_max_f32_parallelize_cols_single_row`, che permetterebbe di togliere la nostra
barriera d'uscita e recuperare un `__syncthreads()` per blocco in `rms_norm_f32`
(1,08 ms, 1% del profilo). Sotto la deriva del banco (2,4%): **non misurabile, non
vale il rischio.**

---

# 4. La classifica

| # | commit | PR | verdetto | numero che deve muoversi |
|---|---|---|---|---|
| **1** | `846e991ec` | #25896 sqrt_softplus in topk-moe | **PORTARE, con attenzione al gancio del prefetch** — ma **dopo** aver chiuso il cancello sul bit `pre` di `LLAMA_DSV4_HC_FUSO`, che vale sette volte tanto | istanze `k_bin_bcast` −80 (da ~1.300 a ~1.220); nodi del grafo −~40×N; t/s **~+0,1%, non misurabile** |
| **2** | `074944998` | #24776 top_k/argsort a blocchi | **valutare — è VRAM, non t/s** | picco VRAM in prefill lungo (vedi §5) |
| **3** | `3cec3bcd1` | #25157 `cudaMemGetInfo` non fatale | opzionale, 7 righe, rischio zero | nessuno (robustezza al muro VRAM) |
| — | tutti gli altri 18 | | **NON PORTARE** | — |

Non c'è un secondo posto vero. Il #2 è una leva di **capienza**, non di velocità, e
il #3 è igiene.

**E fuori classifica, perché non è un porto: il bit `pre` (=2) di
`LLAMA_DSV4_HC_FUSO`.** Vale ~600 lanci per forward contro gli 80 del primo in
classifica. Non è codice da scrivere, è un cancello da chiudere (§7.2).

---

# 5. `074944998` (#24776) — l'unico altro che tocca qualcosa di nostro

**`ggml : process data in smaller chunks in CUDA ggml_top_k() and ggml_argsort()`** —
`argsort.cu`, `argsort.cuh`, `top-k.cu`

### Cosa cambia nel diff

Introduce `argsort_f32_i32_cuda_cub_chunk_nrows(nb01, nrows)`: quante righe stanno in
64 MiB (`chunk_bytes = 1 << 26`), almeno 1. Poi sia `ggml_cuda_op_argsort` sia
`ggml_cuda_op_top_k` ciclano a blocchi di quel numero di righe, e in `top-k.cu`
il buffer temporaneo passa da `ncols * nrows` a `ncols * chunk_nrows`.

### Perché ci riguarda

DS4 usa `ggml_top_k` nel lightning indexer: `deepseek4.cpp:696`,
`ggml_cont(ctx0, ggml_top_k(ctx0, indexer_score, n_top_k))` con
`n_top_k = min(indexer_score->ne[0], hparams.indexer_top_k)`.

E il nostro `top-k.cu` **prende il ramo con il buffer intero**. Il ramo buono
(`CUB_TOP_K_AVAILABLE`, che cicla riga per riga e non alloca) richiede
`CCCL_MAJOR_VERSION >= 3 && CCCL_MINOR_VERSION >= 2` (`top-k.cu:5-11`). **CUDA 12.6
spedisce CCCL 2.x**, quindi compiliamo il ramo `#elif defined(GGML_CUDA_USE_CUB)`, che
fa `ggml_cuda_pool_alloc<int> temp_dst_alloc(pool, ncols * nrows)` — **`ncols × nrows`
interi**, cioè `n_kv × n_token_del_batch × 4` byte.

Ordine di grandezza a 104k di contesto, prefill `-ub 512`:
`104.000 × 512 × 4 B ≈ 213 MiB` di pool temporaneo, che diventerebbero
`64 MiB / (104.000×4 B) = 157` righe per blocco → **~65 MiB**. Circa **150 MiB
liberati**, più il temp storage di CUB che scala con lo stesso fattore.

Questo si aggancia direttamente al nostro commit `0441857cb`
(«il buffer a 104k deve scendere 16 volte»): è **la stessa esigenza**, risolta a monte
in modo generale.

### Cosa NON fa

**In decode non cambia nulla.** Con 1-2 token, `nrows` è piccolo, `chunk_nrows = nrows`,
il ciclo fa un giro solo. Nessun effetto sui 97,4 ms/token. È una leva di
**capienza in prefill**, ed è così che va misurata.

### Rischio di conflitto

**Basso.** `argsort.cu` / `top-k.cu` sono file che non abbiamo toccato
(`git log HEAD -- ...`: nessun commit nostro). L'unica avvertenza è che il ciclo
introduce **N lanci invece di 1** dentro la cattura del CUDA graph: va bene (sono
lanci deterministici sullo stesso stream), ma `argsort_f32_i32_cuda_cub` alloca dal
`ggml_cuda_pool` **dentro** il ciclo. Sotto cattura le allocazioni dal pool sono già
la norma nel resto del backend, però va verificato che il pool non faccia
`cudaMalloc` reale a metà cattura al primo giro.

### Quale numero deve muoversi

**Il picco VRAM in prefill a contesto lungo**, letto con la nostra traccia
`ggml_cuda_kv_ring_vram_trace`. **Non** i t/s di decode. Se si muovono i t/s, è rumore.

---

# 6. I NON PORTARE, con la ragione

## 6a. Non tocchiamo mai quel codice

| commit | PR | ragione |
|---|---|---|
| `598863317` | #26111 kernel wkv7 warp-per-riga | RWKV. DS4 non ha `GGML_OP_RWKV_WKV7`. Zero. |
| `b62b35098` | #22675 SSD matmul a blocchi per Mamba-2 | `ssm-scan.cu`. Nessun Mamba. Zero. |
| `958d9c0b6` | #25617 layout conv alternativo | `conv2d.cu` + un `supports_op` su `IM2COL`/`CONV_2D`. Nessuna convoluzione nel grafo DS4. Zero. |
| `f8def7fe1` | #25928 ROLL richiede src contiguo | `GGML_OP_ROLL` non compare nel grafo DS4 (è roba ricorrente). **Restringe** `supports_op`: portarlo non può che togliere. Zero. |
| `a3e5b96ac` | #25678 concat quantizzato non contiguo | `GGML_OP_CONCAT` su tensore **quantizzato**: nel decode DS4 non c'è. Rilassa un vincolo che non incontriamo. Zero. |
| `c5a4a0bb8` | #25962 GET_ROWS sui K-quant | aggiunge `get_rows` per `Q2_K`/`Q3_K`/`Q4_K`/… Il nostro `get_rows` (`getrows.cu`, `supports_op` a `ggml-cuda.cu:5684`) copre F32/F16/BF16/I32/Q1_0/Q4_0/Q4_1/Q5_0/Q5_1/Q8_0 — e **il modello non fa `get_rows` su un K-quant**: i 43 tensori `q2_K` e gli 86 `iq2_xxs` (dal log: `scudo_gate_on_w2.server.log`) sono i pesi degli esperti, che passano per `mul_mat_id`, non per `get_rows`. Nessun cammino nuovo si apre. |
| `305ba519a` | #25929 get_rows vettoriale int4 | vale solo se `src0->type == dst->type`, `ne00 % 4 == 0`, allineamento a 16 B **e** ≥128 blocchi. Il `get_rows` del gating MoE ha `ne00 == 1` (`[1, n_expert, n_tokens]`): fallisce subito. Il `get_rows` dell'embedding è F32→F32 ma è **uno per token**: sotto la soglia dei 128 blocchi e comunque invisibile nel profilo. |

## 6b. Tipi di quantizzazione che non abbiamo

| commit | PR | ragione |
|---|---|---|
| `9b2a08881` | #25707 supporto Q2_0 | tipo nuovo. Il modello è F32/F16/Q8_0/Q2_K/IQ2_XXS/I32 — niente `Q2_0`. E tocca `mmvq.cu`, dove abbiamo **+648 righe** sul merge-base: **costo di conflitto reale contro guadagno nullo**. |
| `15e755f30` | #25603 `__byte_perm` per Q2_0 | vedi sopra, e tocca `vecdotq.cuh` + `mmq-load-tiles.cuh`. |
| `602f828b4` | #25628 `__byte_perm` per Q1_0 | `Q1_0` è nell'elenco dei tipi che compiliamo ma non è nel modello. |
| `1a064ab09` | #25730 quantizzazione attivazioni NVFP4 W4A4 | `BLACKWELL_MMA_AVAILABLE`. Siamo **sm_86**. Codice morto per noi. |

## 6c. Hardware che non abbiamo

| commit | PR | ragione |
|---|---|---|
| `fa72aeccb` | #26046 rimozione rocWMMA FlashAttention | `ggml_cuda_should_use_wmma_fattn` (`fattn-wmma-f16.cuh:26-32`) è vero solo per **Volta**, RDNA3, MTHREADS. Su sm_86 è **già falso**: il ramo WMMA non è mai preso. La rimozione è a **costo zero e guadagno zero** a runtime. L'unico effetto è **meno tempo di compilazione nvcc** (spariscono `fattn-wmma-f16.cu/.cuh` e le loro istanze di template). Se un giorno il build fa male, questo è il commit da prendere per quello e per nient'altro. |
| `c7d872292` | #24233 `prop.integrated` su HIP | `#if defined(GGML_USE_HIP)`. Fuori da HIP resta `integrated = false`, che è quello che abbiamo. Zero. |
| `3f08ef2c5` | #25749 CUDA graph su Volta+Turing | abbassa la soglia da `GGML_CUDA_CC_AMPERE` a `GGML_CUDA_CC_VOLTA` in `ggml_cuda_graph_set_enabled`. Noi siamo **sm_86 = Ampere**: la nostra soglia (`ggml-cuda.cu:4867`, ancora `AMPERE`) **ci lascia già dentro**. Zero, e tocca un'area delicata. |
| `153d324bc` | #26081 load-mode auto, niente mmap su iGPU | nella nostra cartella è **una riga**: `.mmap_support = props->type != GGML_BACKEND_DEVICE_TYPE_IGPU` in `get_props`. Su GPU discreta vale `true` = comportamento di oggi. Il resto del PR sta in `src/llama-model-loader` e **non è nella mia fetta**. Attenzione però: introduce un campo nuovo in `ggml_backend_dev_props` — se un altro agente porta la parte llama, questa riga va con quella, non da sola. |

## 6d. Rischio senza contropartita

### `79bba02a6` (#25228) — CUDA Virtual Devices. **Il più pericoloso della lista.**

Cosa fa: `GGML_CUDA_DEVICES=N` per **emulare N GPU su una sola**. Rinomina
`info.device_count` in `physical_device_count`, aggiunge
`physical_device`/`physical_share_count`/`virtual_index` a `cuda_device_info`
(`common.cuh`), e inserisce `ggml_cuda_get_physical_device()` **dentro
`ggml_cuda_set_device()`**, cioè sul cammino di ogni singola chiamata CUDA del backend.

Perché è NO:

- Il fork è **single-device** per costruzione. `GGML_CUDA_DEVICES` non lo useremo mai.
- Tocca `ggml_cuda_set_device`, i peer-copy, l'init NCCL. Il nostro
  `cache-esperti.cu` (~4.000 righe) e il thread di servizio DMA vivono su
  **stream dedicati con fork/join** e chiamano il backend da un thread che non è
  quello del grafo. Una traduzione device→physical in mezzo a quel cammino è
  esattamente il genere di modifica che si paga con una corruzione intermittente.
- Guadagno atteso: **zero**.

### `5b87ed30f` (#26688) — warning

Due pezzi: un `GGML_UNUSED(dev)` sotto `GGML_CUDA_NO_PEER_COPY`, e uno `#endif`
spostato in `quantize.cu` così che `nvfp4_native_scale_error` stia dentro
`BLACKWELL_MMA_AVAILABLE`. Con CUDA 12.6 (`CUDART_VERSION` 12060 < 12080) quel blocco
non si compila comunque. **Cosmetico.** Zero rischio, zero guadagno: prenderlo o no
non cambia niente. Se lo si prende, prenderlo perché il rumore in compilazione
nasconde i warning veri, non perché paghi.

### `e1a1abb78` (#26171) — gemmv transpose-free

Aggiunge in `ggml_cuda_mul_mat` uno scambio degli operandi quando `ne01 == 1`
(matrice 1×K) per usare `mul_mat_vec_f` invece di cuBLAS. **Il cancello è
`ne11 > MMVF_MAX_BATCH_SIZE` (=8)**: nel decode `ne11` è 1 (banco senza bozza) o 2
(con `--spec-draft-n-max 1`). **Il ramo non è raggiungibile nel decode.** In prefill
con `-ub 64` lo sarebbe, ma serve anche un `mul_mat` con `ne01 == 1` e `src0` F32
contiguo, che nel grafo DS4 non ho trovato. È l'unico altro commit che tocca
`ggml_cuda_mul_mat`, e non paga.

Regola nostra applicabile: *una leva esiste solo se il suo ramo è raggiungibile*.

### `687e77892` (#26767) — fusione rms_norm+mul+rope

**Già scartato con motivo dall'utente**, e il motivo tiene: la fusione richiede
`rope->src[0] == mul`, ma in `src/models/deepseek4.cpp:936` il q-norm è
`ggml_rms_norm` **senza peso** e il rope prende una **view**. MLA non produce mai
quel pattern. Non l'ho rifatto.

### `5839ba352` (#25441) — dedup della quantizzazione attivazioni gate/up MoE

Al confine con la fetta mmq (tocca `mmq.cu`) ma i pezzi vivi sono in
`mmid.cu/cuh`, `quantize.cu/cuh`, `mmf.cu`. Idea: per `mul_mat_id` con `ne11 == 1`
l'attivazione di un token viene ri-quantizzata **`n_expert_used` volte**; il commit la
quantizza una volta e la sparge (`write_inverse` nel `mm_ids_helper`).

Perché per noi non paga oggi:

- Il guadagno dichiarato è sul cammino **MMQ** in **prefill** (misura upstream: prefill
  @8192 su una 5090 NVFP4). Nel decode a 1-2 token `mul_mat_id` va per **MMVQ**, dove
  `src1` è quantizzato **una volta per tensore**, non per esperto.
- `quantize_q8_1` **non compare nel profilo**: non c'è un numero da muovere.
- La parte fp4/NVFP4 è Blackwell. Resta il ramo q8_1, ma su `mmid.cu` che è la
  cerniera fra `mul_mat_id` e la **nostra** cache esperti: rischio di conflitto reale.

Se un giorno il prefill torna a essere il collo (oggi è curato con `ub 512` e
`-cms 32`), è qui che si guarda. **Non oggi.**

---

# 7. Le quattro domande, in ordine

## 1) Quali toccano un cammino che percorriamo davvero?

**Tre su ventuno.**

- `846e991ec` — sì, e ci trova un `return false` (fusione topk-moe morta per DS4).
- `074944998` — sì, `ggml_top_k` del lightning indexer, ma solo in **prefill lungo** e
  solo per la **VRAM**.
- `3cec3bcd1` — marginale: `cudaMemGetInfo` che fallisce al muro VRAM.

Tutti gli altri: ramo non raggiungibile (`e1a1abb78`, `3f08ef2c5`, `f8def7fe1`),
hardware/tipo che non abbiamo (`fa72aeccb`, `c7d872292`, `1a064ab09`, `9b2a08881`,
`15e755f30`, `602f828b4`, `153d324bc`), operazione che non usiamo (`598863317`,
`b62b35098`, `958d9c0b6`, `a3e5b96ac`, `c5a4a0bb8`, `305ba519a`), già nostro
(`0dc74e332`, `3b5321936`, `9bd4c09ea`, `ebb546b7e`), o cosmetico (`5b87ed30f`).

## 2) `k_bin_bcast`: ~1.300 istanze/token per 1,80 ms — c'è qualcosa che le fonde?

**Da upstream: 80 su 1.300, cioè il 6%. Il resto è roba NOSTRA, e la leva è già in
casa — è una variabile d'ambiente.**

### Prima il fatto duro su upstream

`git log HEAD..upstream/master -- ggml/src/ggml-cuda/binbcast.cu` → **zero commit**.
In 436 commit nessuno ha toccato quel kernel. Non c'è una versione più veloce da
prendere, e non servirebbe: **1,80 ms / 1.300 = 1,4 µs per istanza**. È il costo di un
nodo di CUDA graph replay, non del calcolo. Il kernel non è lento — **sono troppi**.
L'unica leva è ridurre il **numero di nodi**.

L'unica fusione nuova in tutta la mia fetta è `846e991ec`: **80 lanci** (§2).

### Poi il fatto che conta: da dove vengono davvero

Conteggio statico sul grafo DS4 (per forward, 43 strati = 2 raw + 21 CSA + 20 HCA,
di cui 3 hash):

| sorgente | file:riga | lanci/strato | note |
|---|---|---|---|
| **hyper-connections, `build_hc_pre` ×2** | `deepseek4.cpp:328-387` | **fino a 184** | vedi sotto |
| hyper-connections, `build_hc_post` ×2 | `deepseek4.cpp:389-425` | fino a 72 | ciclo annidato 4×4 |
| CSA / lightning indexer | `deepseek4.cpp:1094,1146,561,208,725` | 11 | solo i 21 strati `ratio==4` |
| compressori HCA | `deepseek4.cpp:1079,479,208` | 4 | solo i 20 strati `ratio==128` |
| gating + esperti MoE | `llama-graph.cpp:2091,2169,2406,2430` | **4** | 8 op ma i 5 ADD di `:2430` collassano in 1 lancio |
| residuo `moe_out + ffn_shexp` | `deepseek4.cpp:1450` | 1 | |
| norm (RMS_NORM+MUL) | `llama-graph.cpp:1500` | **0** | già fusa, `ggml-cuda.cu:4528` |
| attenzione MLA (flash) | | **0** | |
| esperto condiviso | `deepseek4.cpp:1443` | **0** | `LLM_FFN_PAR` + `swiglu_split` → nessun MUL |

**Il moltiplicatore singolo più grosso non è il MoE: è il Sinkhorn.**
`deepseek4.cpp:320-323`, `for i < dsv4_hc_sinkhorn_iters` con **20 iterazioni** di
default, **4 binbcast per iterazione** (2 ADD + 2 DIV), **2 chiamate per strato**:
**~158 lanci per strato, ~6.800 per forward** — se il pezzo non è fuso.

### La conseguenza operativa

Le tre fusioni HC sono dietro una maschera, `llama-context.cpp:305-312`:

```
1 = comb (affine + softmax + eps + Sinkhorn),  2 = pre,  4 = post;  7 = tutto
```

e il **difetto del binario è 0, tutte spente**. A leve spente il conteggio arriva a
**~11.500 lanci per forward**. Il profilo ne misura ~1.300, quindi il banco girava con
`LLAMA_DSV4_HC_FUSO` settata — coerente con «la fusione HC vale +16,5%» e con
«FUSO=5 batte FUSO=7» (5 = `comb`+`post`, cioè con **`pre` ancora non fuso**).

Da qui tre conseguenze, tutte più grosse del porto:

1. **Il bit `pre` (=2) vale ~14 lanci/strato, ~600 per forward** — cioè **sette volte**
   il porto di `846e991ec`. È già scritto, è già nel binario, ed è spento perché il
   cancello dell'accordo bozza-bersaglio non è passato. **Prima di portare, chiudere
   quel cancello.**
2. `LLAMA_DSV4_SINKHORN_ITERS` (`deepseek4.cpp:54-64`) è una **sonda già in casa** che
   dice quanto pesano quei lanci — con l'avvertenza scritta nel codice che a iters
   forzate **l'uscita non è valida**. Serve a misurare il pavimento di lanci, non a
   configurare.
3. `LLAMA_DSV4_INDEXER_FUSO` (`llama-context.cpp:328-333`) è **anch'essa spenta di
   default**, vale 2 lanci/strato sui 21 CSA, e soprattutto è la leva della VRAM a
   contesto lungo (il commento a `:315-327` la quantifica: 3.264 MiB di `relu(kq)`
   materializzato a ctx 104k, ub 512).

**Conclusione: sui binbcast upstream ha il 6%. Il 94% è nostro, e la parte
raccoglibile è dietro un bit di `LLAMA_DSV4_HC_FUSO` che aspetta un cancello di
accordo, non un porto.**

## 3) `flash_attn_ext_f16<512,512,1,8>` — miglioramenti?

**Nessuno. Zero commit.**

```
git log HEAD..upstream/master -- ggml/src/ggml-cuda/fattn-mma-f16.cuh   -> vuoto
git log HEAD..upstream/master -- ggml/src/ggml-cuda/fattn-common.cuh    -> vuoto
git log HEAD..upstream/master -- ggml/src/ggml-cuda/fattn-vec.cuh       -> vuoto
```

L'unico commit `fattn*` è `fa72aeccb`, e tocca `fattn-tile`, `fattn-wmma-f16` e la
**selezione** del kernel in `fattn.cu` — rimuovendo il ramo WMMA che su sm_86 non
prendiamo mai. Il nostro kernel (`DKQ=512, DV=512` = MLA, `ncols1=1, ncols2=8`) esce
da `ggml_cuda_get_best_fattn_kernel` **prima** del punto toccato:
`return BEST_FATTN_KERNEL_MMA_F16` sta sopra il blocco WMMA cancellato.

Il che è coerente col fatto che `flash_attn_ext_f16` costa **1,31 ms, l'1%**: non è un
posto dove qualcuno stia ottimizzando, e non è un posto dove ci convenga guardare.

## 4) CUDA graph, stream, cattura

L'area è **quasi vuota**, e la parte che c'è va rifiutata.

Ho passato tutti e 21 i commit cercando
`cuda_graph|StreamCapture|BeginCapture|EndCapture|graph_evaluate|cudaStream|curr_stream_no|stream_context|cudaEvent`
nel diff ristretto a `ggml/src/ggml-cuda/`. Solo due hanno righe vere:

- **`3f08ef2c5`** — una riga, la soglia CC. Ampere ci sta già dentro. **Zero.**
- **`79bba02a6`** — la traduzione device→physical dentro `ggml_cuda_set_device` e nei
  peer-copy. **Il rischio più alto della lista contro guadagno nullo.** Vedi §6d.

Gli altri "hit" erano righe di contesto.

Nota su cosa **non** è cambiato e conta: `ggml_cuda_graph_evaluate_and_capture`,
il `fork_event` / `join_events` sugli stream secondari, `cudaStreamBeginCapture(...,
cudaStreamCaptureModeRelaxed)` e `ggml_backend_cuda_graph_optimize` sono
**identici a monte** in questa finestra, a parte `ebb546b7e` (già portato) e
`a1f96d4fc` (§1, da rifiutare). Il nostro fork/join su stream dedicato non ha
nessuna pressione da upstream: **il merge lì non ci sposta niente**, e va tenuto così.

---

# 8. Cosa NON ho verificato

- Non ho compilato, non ho avviato il server, non ho applicato nessuna patch né
  cherry-pick.
- Il conteggio dei `k_bin_bcast` (§7.2) è **statico, letto nel sorgente del grafo**,
  non misurato. Regge il rapporto fra le sorgenti (HC ≫ MoE) e il numero del porto
  (80 = 2 × 40 strati non-hash), che sono conteggi esatti. **Non** regge il totale
  assoluto: il mio conto a `LLAMA_DSV4_HC_FUSO=5` dà ~1.470, il profilo ne misura
  ~1.300, e la differenza probabile è nella multi-add che collassa più coppie di
  quante ne abbia contate. **Il totale vero si legge alla cattura, non qui.**
- Non ho verificato con quale valore di `LLAMA_DSV4_HC_FUSO` sia stato preso il
  profilo: l'ho **dedotto** (dev'essere ≠ 0, altrimenti i lanci sarebbero ~11.500).
  Va letto nel log della corsa, non da questa nota — vale la regola «il riferimento
  si legge dal LOG».
- Il risparmio VRAM di `074944998` è **calcolato** (64 MiB / `nb01`), non misurato.
- Non ho controllato i file `mmq*` e `cpy.cu`: sono di un altro agente.
- `153d324bc` e `5839ba352` hanno pezzi **fuori** dalla mia fetta (`src/llama-*`,
  `mmq.cu`): il mio verdetto vale solo per la parte in `ggml/src/ggml-cuda/`.
