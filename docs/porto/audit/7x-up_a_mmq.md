# UP_A — `mmq.cu` / `mmq.cuh`: cosa ha fatto upstream in 436 commit

Ramo `overlap`, HEAD `9b7f9eea7`. Base comune `5c3a58686` (9 luglio 2026).
`upstream/master` = `0b1bad14f` (11 agosto 2026).
Bersaglio: DeepSeek-V4-Flash IQ2_XXS (`ffn_down_exps` Q2_K), RTX 3060 sm_86, decode 14,77 t/s, prefill ~20 t/s.

---

## VERDETTO IN UNA RIGA

**Niente di utile. Non vale una notte.** Degli 8 commit distinti, sette non toccano il
nostro cammino e l'ottavo (#25441) vale **~0,15% di prefill e zero di decode** — sotto
la deriva del banco. Il commit grosso (#24127, 5078 righe) e' un **refactor a numeri
invariati su Ampere**, verificato campo per campo, e ci **conflitta** con due commit
nostri vivi. `should_use_mmq` non e' cambiato per noi.

---

## 0. Due premesse del mandato sono false, e cambiano il giudizio

### 0.1 `mmq.cuh` non e' cresciuto di +3483: e' stato SPEZZATO ed e' SCESO

| ref | `mmq.cu` | `mmq.cuh` |
|---|---|---|
| base comune `5c3a58686` | 326 | **3396** |
| nostro HEAD `9b7f9eea7` | 326 | **3423** |
| `upstream/master` | 338 | **1378** |

Il `+3483/-874` e' la somma delle righe toccate, non il netto. Il netto e' **−2018**.
Il motivo e' `6eddde06a` (#24127, Johannes Gäßler, **13 luglio — quattro giorni dopo la
nostra base**), che spezza `mmq.cuh` in otto file nuovi e ne sposta dentro il contenuto:

```
mmq-config-ampere.cuh      366      mmq-config-rdna2.cuh     261
mmq-config-blackwell.cuh    37      mmq-config-rdna4.cuh     282
mmq-config-cdna.cuh        177      mmq-load-tiles.cuh      1671   <- vecchi load_tiles_*
mmq-config-pascal.cuh      261      mmq-vec-dot.cuh         1251   <- vecchi vec_dot_*
```

Totale +5078/−3497. `60bccc376` aggiunge poi `mmq-config-rdna3.cuh` e `-rdna3-5.cuh`.
**Non e' una riscrittura degli algoritmi**: e' una redistribuzione con cambio di API
(§4). I kernel di caricamento tile e di prodotto scalare sono gli stessi, spostati.

### 0.2 `mmq.*` L'ABBIAMO TOCCATO — due commit, vivi, dentro la funzione riscritta

Il mandato dice «`mmq.*` non l'abbiamo mai toccato: eventuali porti li' sono puliti».
E' falso.

```
$ git log 5c3a58686..HEAD --oneline -- ggml/src/ggml-cuda/mmq.cu ggml/src/ggml-cuda/mmq.cuh
6e99d8bfe  mmq: il tile del cammino esperti era 128 colonne per servirne 12   (10 ago)
37da31659  mmq: il valore forzato non puo' essere una GUARDIA del ciclo       (10 ago)
```

Entrambi vivono **dentro `mul_mat_q_case`**, cioe' esattamente la funzione che #24127
smonta. La leva e' `LLAMA_MMQ_X_IDS={32,48,64}`, solo per `MUL_MAT_ID`, spenta di
difetto, con la cura del secondo commit (`mmq_x_forced` **fuori** dalla guardia del ciclo,
altrimenti cambia la selezione di tutto il modello: 13,25 → 12,59 t/s, SHA 33D76723EB8D →
2CE6DA51313F).

Superficie pulita davvero: `mmid.cu`/`mmid.cuh` e `quantize.cu`/`quantize.cuh` — li' il
fork non ha mai messo mano (`git log 5c3a58686..HEAD` su quei file: vuoto).

---

## 1. Inventario: 8 commit distinti, non 13

Il mandato conta le coppie file-commit (7 su `.cu` + 6 su `.cuh`). I commit sono **8**.

| # | hash | PR | titolo | `.cu` | `.cuh` | ci tocca? |
|---|---|---|---|---|---|---|
| 1 | `6eddde06a` | #24127 | refactor MMQ kernel configuration | 55 | 4214 | **solo struttura** |
| 2 | `f6f12e43f` | #25613 | tighter MMQ src1 buffer size for native fp4 | 13 | 13 | no |
| 3 | `5839ba352` | #25441 | **dedup MoE gate/up activation quantization** | 17 | — | **SI, solo prefill** |
| 4 | `1a064ab09` | #25730 | Improve NVFP4 W4A4 activation quantization | 33 | 107 | no |
| 5 | `1425386fd` | #25778 | fix external compilation of q1_0 MMQ | 30 | 10 | no |
| 6 | `60bccc376` | #26199 | add rdna3.5 and 3 to mmq configs | — | 16 | no |
| 7 | `caa596ab3` | #26141 | disable MMQ under 48 KiB shared memory | 9 | — | no-op da noi |
| 8 | `9b2a08881` | #25707 | add Q2_0 support | 4 | 15 | no |

---

## 2. Domanda 1 — I nostri tipi (IQ2_XXS, Q2_K, Q8_0) e il cammino `mul_mat_id`

### 2.1 I tipi: nessun cambio di aritmetica

Letto il diff riga per riga:

- **#25707 (Q2_0)** aggiunge `GGML_TYPE_Q2_0`, che e' un **tipo nuovo** (blocco a 2 bit
  con scala per blocco, famiglia legacy), **non** `Q2_K`. Le 15 righe in `mmq.cuh` sono
  la sua `CASE` di config e la sua voce in `mmq_get_q8_1_ds_layout`. `Q2_K` non e'
  toccato. Zero per noi.
- **#25778** e' un **puro riordino** dello `switch` in `mmq.cu`: sposta `MXFP4`/`NVFP4`
  in fondo e `IQ1_S` in cima al blocco IQ, con commenti `// ----` a separare le
  famiglie. Serve a far compilare `q1_0` fuori albero. Nessun `case` cambia
  comportamento. Zero.
- **#25730** e' NVFP4 W4A4: aggiunge `y_scale` a `mmq_args` (scala per token
  dell'attivazione) e un `src1_scale` allocato **solo** se
  `src0->type == GGML_TYPE_NVFP4 && use_native_fp4`, dove `use_native_fp4` richiede
  `blackwell_mma_available(cc)`. Su sm_86 e' `nullptr` sempre. Zero.
- **#25613** stringe `nbytes_src1_q8_1` per fp4 e sostituisce il termine di padding
  `get_mmq_x_max_host(cc)*sizeof(block_q8_1_mmq)` con
  `ggml_cuda_mmq_get_J_max(type, fallback, cc, ne11)*sizeof(block_q8_1_mmq)`. Per noi
  il termine passa da `128 * ~144 B ≈ 18 KiB` a un valore <= quello. **18 KiB su 12 GB:
  non e' una leva VRAM.** Zero.
- **#26199** aggiunge `mmq-config-rdna3.cuh` e `mmq-config-rdna3-5.cuh` e il relativo
  ramo in `ggml_cuda_mmq_get_config`. Solo AMD. Zero.

### 2.2 Il cammino `mul_mat_id`: **ncols_max e' ancora `ne12`**

La cosa che volevo verificare per prima: upstream ha risolto il difetto trovato
dall'audit 56 (per il cammino esperti il lanciatore sceglie un tile di 128 colonne
quando un esperto ne serve in media 12, cioe' 91% riempitivo)?

**No.** In `mmq.cu` upstream l'argomento finale di `mmq_args` per il ramo `ids` e'
ancora `ne12` (era `use_stream_k, ne12`, ora solo `ne12` perche' `use_stream_k` e'
migrato nella config). E in `launch_mul_mat_q`:

```c
const int ntx  = (args.ncols_max + config.J - 1) / config.J;
```

Identico al nostro `(args.ncols_max + mmq_x - 1) / mmq_x`. La selezione di `J` minimizza
ancora `ntiles_x`, quindi con `ncols_max = ne12 = n_token` sceglie ancora **J = 128** per
il cammino esperti. **La nostra osservazione resta nostra e resta non risolta upstream.**

---

## 3. Domanda 2 — `should_use_mmq`: NESSUN CAMBIO PER NOI

Ho letto le due versioni intere di `ggml_cuda_should_use_mmq` fianco a fianco. A valle
dello `switch` dei tipi il corpo e' **identico riga per riga**. Le uniche due differenze:

**(a) La lista dei tipi e' solo riordinata**, piu' `GGML_TYPE_Q2_0`. `IQ2_XXS`, `Q2_K`,
`Q8_0` erano dentro e restano dentro. Zero effetto semantico.

**(b) Il cancello nuovo di #26141**, inserito **prima** di `turing_mma_available`:

```c
    // MMQ tiles require at least 48 KiB per-block shared memory; fall back to BLAS otherwise.
    {
        const int    id    = ggml_cuda_get_device();
        const size_t smpbo = ggml_cuda_info().devices[id].smpbo;
        if (smpbo < 48 * 1024) {
            return false;
        }
    }
```

Motivo dichiarato nel commit: su una Moore Threads MTT S70 (28 KiB) `mul_mat_q_switch_J`
stampava `J_best=0` e faceva `GGML_ABORT`. Nessun tile entrava.

Su sm_86 `smpbo` (`cudaDevAttrMaxSharedMemoryPerBlockOptin`) vale **99 KiB / 101376 B**
[DEDOTTO da specifica]. Ma non serve fidarsi della specifica: **e' gia' dimostrato dal
comportamento misurato**. Il ciclo di selezione, sia nostro sia upstream, scarta ogni `J`
il cui `mmq_get_nbytes_shared` supera `smpbo`; l'audit 56 ha misurato che il cammino
esperti prende **J = 128**, il tile piu' grande della tabella. Se `smpbo` fosse sotto i
48 KiB, `J = 128` non sarebbe selezionabile. Il cancello non scatta.

> **Risposta secca.** Su Ampere `should_use_mmq` risponde ancora **si' incondizionatamente**
> (`turing_mma_available(sm_86) → return true`). La soglia MMQ/MMVQ **non e' cambiata**.
> Non cambia quale kernel prendiamo. Niente da portare.

**Nota sul cancello vero.** `should_use_mmq` non e' comunque cio' che decide fra
`mul_mat_q` e `mul_mat_vec_q` da noi. Il ramo che decide e' in `ggml-cuda.cu:2402-2422`
(nostro HEAD): per `mul_mat_id`, se `ne2 <= MMVQ_MAX_BATCH_SIZE` **e**
`ne2 <= get_mmvq_mmid_max_batch(type, cc)` si va a **MMVQ e si esce**; `should_use_mmq`
viene interrogato solo dopo, cioe' **solo quando il batch e' grande**. E' il fatto che
chiude la §5.

---

## 4. Domanda 4 — Che cosa SONO le 5078 righe di #24127

E' una **tabella di configurazione al posto di una selva di `#if`**, piu' lo spostamento
dei kernel in due header. Non e' una riscrittura degli algoritmi: `load_tiles_*` e
`vec_dot_*` sono gli stessi corpi, spostati in `mmq-load-tiles.cuh` e `mmq-vec-dot.cuh`
con `mmq_y` → `I` e `mmq_x` → `J`.

Il cuore nuovo:

```c
struct ggml_cuda_mmq_config {
    ggml_type                 type;        // src0->type
    int                       nthreads;    // thread per blocco CUDA
    int                       occupancy;   // occupancy bersaglio del kernel MMA
    int                       I;           // larghezza tile SRAM su src0->ne[1]
    int                       J;           // larghezza tile SRAM su src1->ne[1]  (era mmq_x)
    ggml_cuda_mmq_sram_layout sram_layout;
    int                       K_vram;
    bool                      stream_k;    // era un campo runtime di mmq_args
    bool                      fallback;    // era il template param need_check
};
```

popolata da una macro `CASE(...)` una riga per `(tipo, J, fallback)`, in un file per
architettura. `mmq-config-ampere.cuh` sono 366 righe di sole `CASE`.

### 4.1 Verifica campo per campo: su Ampere i numeri NON cambiano

Questo era il punto che valeva la lettura. Preso `GGML_TYPE_IQ2_XXS` (e `Q2_K`, e
`Q8_0`: **hanno tutti gli stessi valori**) da `mmq-config-ampere.cuh`:

```
CASE(GGML_TYPE_IQ2_XXS, 256, 1, 128, J, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_0, MMQ_ITER_K, true, fallback);
                        ^^^  ^  ^^^                                     ^^^^^^^^^^  ^^^^
                   nthreads  |  I                                       K_vram      stream_k
                        occupancy
```

Contro il nostro HEAD:

| campo | nuovo (Ampere) | vecchio (nostro HEAD, sm_86) | dove |
|---|---|---|---|
| `nthreads` | 256 | `mmq_get_nwarps_host = 256/32 = 8 warp` → **256** | `mmq.cuh:298` |
| `occupancy` | 1 | `__launch_bounds__(..., 1)` per `__CUDA_ARCH__ >= VOLTA` | `mmq.cuh:3537` |
| `I` | 128 | `get_mmq_y_host(cc)` → **128** | `mmq.cuh:142` |
| `K_vram` | `MMQ_ITER_K` = 256 | `MMQ_ITER_K` = 256 | `mmq.cuh:13` |
| `stream_k` | `true` | `(NVIDIA && >= VOLTA) \|\| CDNA` → **true** | `mmq.cu` |
| insieme `J` (fallback=false) | 8,16,24,32,40,48,64,80,96,112,128 | ciclo `8..mmq_x_max=128` passo 8 filtrato da `mmq_get_granularity_host` (8 sotto 48, 16 da 48 in su) → **stesso insieme** | `mmq.cuh:273` |

Tutto pari. Anche la scelta grossa fra stream-k a `nsm` blocchi e tiling pieno — che
sembrava nuova — **e' gia' al nostro HEAD, identica riga per riga**:

```c
const int tiles_efficiency_percent = 100 * ntiles_dst / (nsm*tiles_nwaves);
const dim3 block_nums_stream_k(GGML_CUDA_CC_IS_NVIDIA(cc) && tiles_efficiency_percent >= 90 ? ntiles_dst : nsm, 1, 1);
```

**Conclusione: #24127 non muove un solo numero sul nostro ferro.**

### 4.2 L'unica differenza semantica trovata, e riguarda `fallback`

Nel vecchio codice `need_check` (= `nrows_x % mmq_y != 0`) era un template param
indipendente dalla scelta di `mmq_x`. Nel nuovo, `fallback = ne01 % 128 != 0` viene
deciso in `mmq.cu` e **restringe l'insieme dei `J` disponibili**: per Ampere con
`fallback = true` esistono solo `J ∈ {8, 16, 32, 64, 128}` (niente 24, 40, 48, 80, 96,
112). E' una scelta di tempo-di-compilazione, non di prestazione.

Ci riguarda solo se `ne01` (righe della matrice esperto) non e' multiplo di 128.
**Da verificare prima di qualunque porto** — se `n_ff_exp` non e' multiplo di 128, il
tile scelto in prefill cambierebbe, e con esso lo SHA.

### 4.3 Cherry-pick parziale: **impossibile**, e va detto

- `mul_mat_q_case` diventa `mul_mat_q_switch_J` + un wrapper; `mmq_x` diventa `J`
  ovunque; `use_stream_k` esce da `mmq_args` ed entra nella config.
- `#24127` **rimuove `ggml_cuda_op_mul_mat_q`** (il cammino legacy dello split
  multi-GPU). Verificato: `git log -S'ggml_cuda_op_mul_mat_q'` nel range da solo
  `6eddde06a`. Quella rimozione ha il suo pendant in `ggml-cuda.cu`, che fra noi e
  upstream diverge di **1416 righe** — cioe' un altro cantiere intero.
- E ricade sopra i nostri `6e99d8bfe` + `37da31659`.

Il porto e' una **riscrittura a mano** di `mul_mat_q_switch_J` con dentro il nostro
`mmq_x_forced` rinominato `J_forced`, piu' il trascinamento del refactor di
`ggml-cuda.cu`. Per **zero** numeri mossi. **Non si fa.**

---

## 5. Domanda 3 — Il prefill: c'e' qualcosa? Un commit solo, e vale ~0,15%

### 5.1 `5839ba352` (#25441) — CUDA: dedup MoE gate/up activation quantization

**Che cosa cambia, letto nel diff.** Nel cammino `ids` di `ggml_cuda_mul_mat_q`:

```c
// gate/up activations are broadcast across experts (ne11 == 1): quantize each token once and
// scatter to its slots. ids_src1 then holds the inverse map (token slot -> compact row).
const bool dedup_bcast = ne11 == 1 && n_expert_used > 1;
```

Quando l'attivazione e' *broadcast* sugli esperti (`ne11 == 1`, cioe' `gate` e `up` —
**non** `down`, che ha `ne11 == n_expert_used`), il codice vecchio ri-quantizzava la
stessa riga `n_expert_used` volte. Il nuovo:

1. `ggml_cuda_launch_mm_ids_helper(..., /*write_inverse =*/ dedup_bcast, stream)` fa
   scrivere in `ids_src1` la mappa **inversa** (slot del token → riga compatta);
2. `quantize_scatter_mmq_q8_1_cuda` riusa **lo stesso kernel** `quantize_mmq_q8_1` con
   un template `bool scatter`: griglia sui **token** invece che sulle righe compatte,
   e il blocco quantizzato viene scritto in tutti gli slot:

```c
const int nwrite = scatter ? n_expert_used : 1;
for (int slot = 0; slot < nwrite; ++slot) {
    const int64_t i = ids[(int64_t) blockIdx.x * n_expert_used + slot];
    ...
}
```

**Bit-esatto per costruzione**: `amax`, `d`, `q.x..q.w` sono calcolati dalle stesse
istruzioni sugli stessi dati; cambia solo il bersaglio della scrittura. Upstream fornisce
anche `GGML_CUDA_NO_MOE_QUANT_DEDUP=1` per tornare al cammino vecchio a binario fermo.

**Ci tocca?** Si': il ramo `else` non-fp4 chiama `quantize_scatter_mmq_q8_1_cuda`, e
`IQ2_XXS` (layout `D4`) e `Q2_K` (layout `D2S6`) passano di li'. Ma **solo in prefill**,
per il ramo di `ggml-cuda.cu:2405-2409` gia' citato: a decode con batch 2 il
`mul_mat_id` va a MMVQ (o al nostro kernel mascherato dalla cache) e `ggml_cuda_mul_mat_q`
non viene nemmeno chiamato.

**Quanto vale, agganciato al profilo.** L'audit 56 §3c ha gia' contato questa voce:

> «quantize q8_1 delle 3.072 righe ≈ **0,03 ms/token**»

3.072 = 512 token × 6 esperti, cioe' esattamente il lavoro che il dedup toglie. A ub 512
sono **15,4 ms su una passata di 6.860 ms = 0,22%**.

Il risparmio non e' 6×, perche' le **scritture restano**: si scrive comunque una copia per
slot. Modello del traffico (4 B letti per valore f32, ~1,06 B scritti per valore int8+ds):

```
vecchio:  6N x (4 + 1,06) = 30,4 N
nuovo:    N x 4 + 6N x 1,06 = 10,4 N          → 2,9x meno traffico, cioe' -66%
```

**Risparmio atteso: ~10 ms su 6.860 = +0,15% di prefill.**

**Il numero che deve muoversi.** `nsys --cuda-graph-trace=node` su 2-3 ubatch a ub 512:
la somma di `quantize_mmq_q8_1<*, false>` deve passare da **~15 ms/passata a ~5**, e il
conteggio dei blocchi lanciati da `3072 x block_num_y` a `512 x block_num_y`. Il prefill
end-to-end deve passare da 113,5 a **113,7 t/s**.

**E qui sta il problema.** La dispersione migliore mai ottenuta su quel banco e' **0,1%**
(113,47 / 113,55 / 113,59, tre riproduzioni), e la **deriva del banco e' 2,4%**
([[capienza-non-paga-colpi-non-valuta]]). Un guadagno dello 0,15% e' **1,5 volte la
dispersione ottima e un sedicesimo della deriva**: non e' misurabile con onesta'. Il
cancello utile non e' il t/s, e' `nsys` sul kernel.

**Rischio di conflitto: BASSO.** ~350 righe su 4 file, di cui:

| file | righe | il fork l'ha toccato? |
|---|---|---|
| `quantize.cu` | 290 | **no** |
| `quantize.cuh` | 25 | **no** |
| `mmid.cu` | 31 | **no** |
| `mmid.cuh` | 2 (firma: `+ bool write_inverse`) | **no** |
| `mmq.cu` | 17 | **no** (i nostri due commit sono in `mmq.cuh`) |
| `mmf.cu` | 2 (solo il nuovo argomento alla helper) | **no** |

Il diff `mmid.*` fra noi e upstream e' **esattamente** questo commit (31+2 righe), quindi
li' la base e' allineata. Su `quantize.cu` il diff totale e' 559 righe perche' contiene
anche #25613/#25730/#26688 (fp4), che vanno lasciati fuori: il porto e' **selettivo**, non
un `git cherry-pick` pulito.

### 5.2 E il resto del prefill? Niente

Nessuno degli altri 7 commit tocca il batch grande su Ampere. In particolare:

- **#24127 non accelera il prefill**: §4.1, tutti i campi pari, e l'euristica
  `tiles_efficiency_percent >= 90` che governa la forma della griglia stream-k era **gia'
  al nostro HEAD**.
- **#26141** riguarda solo il prefill (il commit lo dice: «Only prefill (batch > 1) is
  affected»), ma per farlo **abortire** su ferro che non abbiamo.

Il `mul_mat_q` da 5,25 ms/token del profilo resta dove sta. Se il prefill si deve curare,
**non si cura da questa fetta**: si cura dal riempitivo del tile (audit 56/57, leva
nostra, non upstream) o dal trasporto.

---

## 6. Classifica

| pos | commit | perche' | quale numero si muove | costo |
|---|---|---|---|---|
| **1** | *nessuno* | vedi verdetto | — | — |
| 2 | `5839ba352` #25441 | −66% traffico del quantize attivazioni gate/up in prefill | `quantize_mmq_q8_1` 15 → 5 ms/passata (nsys); prefill 113,5 → 113,7 t/s | ~350 righe, 4 file, porto selettivo, cancello bit-esatto obbligatorio |
| 3 | `caa596ab3` #26141 | 9 righe di robustezza: evita `GGML_ABORT` su GPU con < 48 KiB SRAM | **nessuno** | banale, ma inutile: non abbiamo quel ferro |

Sotto la riga, in ordine: #25613, #25730, #25778, #26199, #25707, #24127.

**Se devo consigliare una cosa sola: non fare niente qui e spendere la notte altrove.**
Il #2 in classifica vale meno della deriva del banco.

---

## 7. Cosa NON portare, e perche'

### 7.1 `6eddde06a` #24127 — il refactor. NON PORTARE.

Tre ragioni, in ordine di forza:

1. **Zero numeri mossi su Ampere** (§4.1, verifica campo per campo). Si paga tutto e non
   si compra niente.
2. **Conflitto certo con codice nostro vivo e gia' costato caro.** `mul_mat_q_case`
   ospita `LLAMA_MMQ_X_IDS` e la cura di `37da31659`. Quella cura e' stata trovata **dal
   cancello bit-esatto, non dalla lettura del diff** — il commit lo dice. Riscrivere quella
   funzione dentro una API nuova (`mmq_x` → `J`, `use_stream_k` fuori da `mmq_args`,
   `need_check` → `fallback` che ora **vincola** l'insieme dei tile) e' esattamente il
   genere di lavoro che ha gia' prodotto una regressione muta del 5% una volta.
3. **Trascina `ggml-cuda.cu`.** Rimuove `ggml_cuda_op_mul_mat_q`, e i suoi chiamanti sono
   nel file che fra noi e upstream diverge di 1416 righe.

**Quando riconsiderarlo.** Solo se si decide un allineamento *completo* a upstream come
progetto a se'. In quel caso il refactor ha un premio collaterale onesto: la tabella
`CASE(type, nthreads, occupancy, I, J, ...)` e' **il posto giusto dove vive la nostra
leva**. Oggi `LLAMA_MMQ_X_IDS` e' un `getenv` innestato in un ciclo di ricerca; li'
diventerebbe una riga di tabella per `(IQ2_XXS, J, fallback)`, e la spazzata dell'audit 57
si farebbe cambiando dati invece che flusso di controllo. E' un argomento di
**manutenibilita', non di prestazione** — non paga una notte da solo.

### 7.2 `1a064ab09` #25730 e `f6f12e43f` #25613 — fp4. NON PORTARE.

Vivono sotto `blackwell_mma_available(cc)`. Su sm_86 sono rami morti. Portarli significa
aggiungere `y_scale` a `mmq_args` e un `ggml_cuda_pool_alloc<float>` in piu' per ogni
chiamata, per codice che non gira. Costo netto positivo.

### 7.3 `60bccc376` #26199 — AMD. NON PORTARE. `9b2a08881` #25707 — tipo nuovo. NON PORTARE.

### 7.4 Il precedente citato nel mandato non e' di quest'area

Il mandato cita «#20793: +1% su 4090, −50% su AMD» come revert su quest'area. **Non lo e'.**
`3fc4e1052` (#20793) e' *«sched: reintroduce less synchronizations during split compute»*,
revertito da `86b94708f` (#25138): e' **`ggml/src/ggml-backend.cpp`**, cioe' lo
scheduler — la stessa area di [[join-73-percento-finestra-uno-split]] (`ggml-backend.cpp:1881`,
join al primo split successivo). **Nel range non c'e' nessun revert su `mmq.*`.**

Il monito resta valido e va girato a chi ha quella fetta: upstream **ha gia' provato e
ritirato** un tentativo di ridurre le sincronizzazioni fra split. Chi punta a quel +50%
deve leggere `86b94708f` **prima** di ripercorrere `3fc4e1052`, perche' quel sentiero e'
gia' stato battuto e chiuso.

---

## 8. Cose emerse che non erano nel mandato ma vanno a verbale

1. **Il nostro fork ha due commit vivi in `mmq.cuh`** (§0.2). Va corretto in qualunque
   inventario del porto: la superficie `mmq.*` **non e' pulita**.
2. **`ncols_max = ne12` per il cammino esperti e' ancora upstream** (§2.2). Il difetto
   dell'audit 56 non e' stato visto da nessuno: il tile a 128 colonne per servirne 12 e'
   ancora nel `master`. E' materiale da PR, se mai lo vorremo mandare su.
3. **Il vincolo `fallback` sui `J` disponibili e' nuovo** (§4.2). Chiunque porti #24127
   deve prima verificare `n_ff_exp % 128` sul nostro modello.
4. **La strada che upstream sta battendo sul prefill MoE non e' MMQ, e' il quantize.**
   #25441 con la fusione quantize+scatter, e (dall'audit 56 riga 40) la fusione
   SwiGLU+quantize dichiarata a +25% da altri. Il collo che loro attaccano non e' la GEMM:
   e' cio' che sta **intorno** alla GEMM. Coerente con
   [[orchestration-bound-not-byte-bound]] — settima conferma.

---

*Metodo: nessuna compilazione, nessun avvio, nessuna patch, nessun cherry-pick. Solo
lettura di `git show`/`git diff` sui tredici diff file-commit, delle due versioni intere
di `ggml_cuda_should_use_mmq`, di `mmq-config-ampere.cuh`, di `mul_mat_q_switch_J` e
`launch_mul_mat_q` in entrambe le versioni, del kernel `quantize_mmq_q8_1<ds_layout,
scatter>`, e del ramo di dispatch `ggml_cuda_mul_mat_id` al nostro HEAD.
Tutto cio' che e' marcato [DEDOTTO] non e' stato misurato su questa macchina.*
