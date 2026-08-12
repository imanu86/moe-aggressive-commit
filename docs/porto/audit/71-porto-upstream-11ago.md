# Porto upstream — audit dei 153 commit (11 agosto 2026)

- HEAD nostro: `c770ec41c` — «porto upstream #26802: corretto e neutro, ma INERTE sul nostro carico»
- tip upstream: `7b13a8404` (11/8 20:20) — `ci : add missing release check (#26923)`
- range nominale: `git log HEAD..upstream/master --no-merges` = **153**
- carico di riferimento: DeepSeek-V4-Flash IQ2_XXS, RTX 3060 sm_86, ctx 10000, `-ub 64`, decode **14,77 t/s**

**Risposta corta.** Dei 153, ne valgono il porto **sei**, e di questi **nessuno muove
direttamente un numero del profilo**. Quattro sono correttezza o assicurazione, uno e' uno
strumento di misura, uno e' una **primitiva** che serve a noi per aggredire il join. La ragione
e' un fatto misurabile, non un'opinione: in questa finestra upstream **non ha toccato un solo
kernel che compare nel nostro profilo**.

---

## 0. Il primo risultato non e' un commit, e' la forma del repo

Prima di guardare qualunque diff:

```
git rev-parse --is-shallow-repository   -> true
git merge-base HEAD upstream/master     -> (vuoto, exit 1)
git rev-list --count upstream/master    -> 153
git rev-list --count HEAD               -> 114
git rev-list --parents -n1 f5919bf45    -> f5919bf45   (nessun genitore: e' un innesto)
```

**Non esiste un antenato comune.** Entrambi i rami sono innestati (shallow). Tre conseguenze.

### 0.1 «153 commit indietro» e' un artefatto della profondita' di fetch

`HEAD..upstream/master` = *tutto* `upstream/master` che abbiamo in locale (153 e' il conteggio
totale del ramo upstream fetchato). Non e' «ci mancano 153»: e' «di upstream ne abbiamo
fetchati 153, e nessuno di essi e' antenato del nostro HEAD».

### 0.2 Esiste un buco invisibile fra la nostra base e il piu' vecchio dei 153

Il nostro commit radice `c2e51866f` e' del **14 luglio**; il piu' vecchio dei 153
(`f5919bf45`) e' del **2 agosto**. Prova che il buco e' reale, misurata su file che il nostro
fork non ha **mai** toccato:

| file (mai nostro)                       | delta HEAD vs `f5919bf45` |
|-----------------------------------------|---------------------------|
| `docs/ops/WebGPU.csv`                   | 3581 righe                |
| `ggml/src/ggml-hexagon/htp/unary-ops.c` | 1330 righe                |
| `ggml/src/ggml-cuda/mmq.cuh`            | 3483 + / 874 −            |
| `ggml/src/ggml-cuda/quantize.cu`        | confligge da sola         |

Nessuno dei 153 tocca `mmq.cuh` o `quantize.cu`. Quindi quelle differenze vengono da **commit
upstream fra il 14/7 e il 2/8 che non abbiamo e che non sono nemmeno nella lista**. Il debito
vero e' piu' grande di 153, e non sappiamo di quanto finche' il repo resta shallow.

Corollario diagnostico: molti dei «conflitti» qui sotto **non sono colpa del nostro fork**, sono
il buco. Li ho separati caso per caso.

### 0.3 Verifica meccanica dei 153

Per ciascuno: `git apply --check -R` (gia' presente?) e `git apply --check` (si applica pulito?).

| esito     | conteggio | significato |
|-----------|-----------|-------------|
| ALREADY   | **0**     | nessuno dei 153 e' gia' nel nostro albero |
| CLEAN     | **47**    | `git apply` passa senza conflitti |
| CONFLICT  | **106**   | serve lavoro a mano |

E qui c'e' il secondo risultato scomodo: **«pulito» e «utile» sono insiemi disgiunti**. I 47 che
si applicano da soli sono opencl, sycl, metal, webgpu, ci, vendor, ui, mtmd, convert, gguf-py,
piu' qualche ritocco a `vocab`/`grammar`/`model-saver`/`imatrix` e una fix SWA per EXAONE 4.5.
**Nemmeno uno tocca CUDA, lo scheduler, il nostro modello o la speculazione.**

### Rebase o cherry-pick?

**Cherry-pick, e non e' nemmeno una scelta.** Il rebase e' *meccanicamente impossibile*: senza
antenato comune, `git rebase upstream/master` riproporrebbe tutti e 114 i nostri commit —
compreso l'innesto radice, che «aggiunge» l'intero albero — su una radice non imparentata. Non
e' «rischioso», e' un non-senso: conflitto su ogni file del repository.

**Prima di qualunque porto: `git fetch upstream --unshallow`.** Finche' il repo e' shallow non
esistono `merge-base`, `range-diff`, ne' il modo di sapere quali prerequisiti mancano a un
cherry-pick. Costa banda, non tempo di banco. E' l'unica azione di questo audit che va fatta
comunque, qualunque sia poi la decisione sui singoli commit.

---

## 1. Il risultato che decide tutto il resto: la finestra non tocca i nostri kernel caldi

Elenco completo dei file `ggml/src/ggml-cuda/` toccati da un commit **reale** dei 153
(escluso l'innesto):

```
ggml-cuda.cu   (6 commit)   rope.cu/.cuh  (1)   common.cuh (1)
cpy.cu         (1)          wkv.cu        (1)   softmax.cu (1)
norm.cu        (1)          quantize.cu   (1)
```

Confronto col profilo (`nsys --cuda-graph-trace=node`, banco senza bozza, 512 slot):

| kernel                       | ms/token | quota | toccato dai 153? |
|------------------------------|---------:|------:|------------------|
| `kern_fj_copia` (nostro)     |    34,36 |  37 % | no (e' nostro)   |
| `mul_mat_vec_q`              |    26,62 |  29 % | **NO**           |
| `mul_mat_vec_q_moe_maschera` |     9,64 |  10 % | no (e' nostro)   |
| `mul_mat_q`                  |     5,25 |   6 % | **NO**           |
| `mul_mat_vec_f<half>`        |     5,14 |   6 % | **NO**           |
| `kern_decidi` (nostro)       |     1,67 |   2 % | no (e' nostro)   |
| `k_bin_bcast`                |     1,80 |   2 % | **NO**           |
| `flash_attn_ext_f16`         |     1,31 |   1 % | **NO**           |
| `rms_norm_f32`               |     1,08 |   1 % | solo indiretto   |

Ricerche mirate sui diff, per non fidarmi dei titoli:

```
git log HEAD..upstream/master -G"cuda_graph"  -> solo l'innesto
git log HEAD..upstream/master -G"mul_mat_id"  -> ebb546b7e (gia' portato), Granite-Switch
git log HEAD..upstream/master -G"n_expert_used" -> solo MTP di altri modelli
```

**Nella finestra 2–11 agosto upstream non ha fatto lavoro di kernel MoE, ne' su mmvq/mmq, ne'
su flash-attn, ne' su binbcast, ne' sui grafi CUDA** (oltre a #26802 che e' gia' nostro).

Due tetti aritmetici da tenere sul tavolo mentre si legge la classifica:

- **Tetto host.** La GPU occupa 93,28 ms dei 97,4 ms del token: **il non-GPU e' 4,12 ms, 4,2 %**.
  Qualunque commit che non tocchi un kernel della tabella ha per costruzione un tetto del 4,2 %,
  e in pratica una frazione di quello.
- **Tetto sui 6 % piu' piccoli.** Anche azzerare `mul_mat_q` per intero varrebbe 5,25 ms su 97,4.

---

## 2. I commit da portare

Schede complete. L'ordine e' quello della classifica del § 3.

---

### 2.1 `c8e03ce81` — PR #26649 — «mtmd/ggml: add ggml_build_forward_order»

**Che cosa cambia davvero** (letto in `ggml/src/ggml.c` e `ggml/include/ggml.h`).
Tre righe di codice:

```c
void ggml_build_forward_order(struct ggml_cgraph * cgraph, struct ggml_tensor * tensor) {
    ggml_build_forward_impl(cgraph, tensor, /*expand=*/true, /*compute=*/false);
}
```

Inserisce un tensore e i suoi antenati **nella posizione corrente del grafo senza marcarli per
il calcolo**; il flag viene messo dopo, quando un nodo che calcola li raggiunge. E' quindi una
**primitiva di ordinamento pura**: sposta la posizione dei nodi nella lista, non che cosa viene
eseguito. Il resto del commit e' l'uso in `tools/mtmd/clip.cpp` (irrilevante per noi) e la
motivazione upstream (`ggml_build_forward_expand` usato come hint d'ordine rompeva
`ggml_build_forward_select`).

**Perche' dovrebbe pagare da noi.** Non paga da solo: **paga come attrezzo**. La leva piu' grande
che abbiamo misurato e' il join — `GGML_SCHED_PROFILO=1` dice join 73,4 %, di cui **47,5 % la CPU
calcola mentre la GPU aspetta**, perche' `ggml-backend.cpp` fa il join al primo split successivo e
la finestra (0,25 ms) e' **tre volte piu' stretta** del lavoro CPU (0,70 ms). Oggi per allargare
quella finestra abbiamo un solo strumento, ed e' invasivo: il `confine_partizione` che forziamo a
mano in `ggml_backend_sched_split_graph` (nostro codice, `ggml-backend.cpp:1529-1544`). Con
`ggml_build_forward_order` la finestra si allarga **dal lato del costruttore del grafo**: si
ordina il ramo GPU prima del consumatore del ramo CPU, senza toccare lo scheduler.
E' l'unico commit dei 153 che tocca un meccanismo su cui abbiamo un numero grande aperto.

**Rischio di conflitto.** Additivo, quasi nullo. Il nostro `ggml.c` ha gia'
`ggml_build_forward_impl(cgraph, tensor, expand, compute)` (riga 7304) e gia'
`ggml_build_forward_select` (7323) che chiama proprio la variante `compute=false`. Quindi la
funzione nuova e' **una riga di corpo** su infrastruttura che abbiamo. Il commit risulta
CONFLICT solo per deriva di contesto in `ggml.h`/`clip.cpp`: **non va cherry-pickato, va
riscritto a mano in 5 righe** tenendo lo stesso nome, cosi' quando faremo l'unshallow il porto
combacia.

**Come si misura.** Il porto in se': **zero, e va detto**. Il numero e' quello del lavoro che
abilita — `GGML_SCHED_PROFILO=1` dopo il riordino: la quota di join deve scendere sotto 73,4 %,
e la finestra di sovrapposizione salire da 0,25 ms verso 0,70. Sul t/s la stima aperta e' +50 %,
ed e' la stima piu' grande che abbiamo.

---

### 2.2 `69bf64379` — PR #26731 — «CUDA: fix thread/block count in quantized cpy kernel launches»

**Che cosa cambia davvero** (`ggml/src/ggml-cuda/cpy.cu`). Tutti i lanci `cpy` quantizzati
erano sbagliati in due modi diversi:

```c
// f32 -> q8_0 : blocchi giusti, ma UN THREAD per blocco
- const int64_t num_blocks = ne / QK8_0;
- cpy_f32_q<...><<<num_blocks, 1, 0, stream>>>
+ const int64_t num_blocks = (ne/QK8_0 + CUDA_CPY_BLOCK_SIZE - 1) / CUDA_CPY_BLOCK_SIZE;
+ cpy_f32_q<...><<<num_blocks, CUDA_CPY_BLOCK_SIZE, 0, stream>>>

// q8_0 -> f32 : num_blocks = ne, cioe' 32 volte troppi blocchi, sempre a 1 thread
- const int64_t num_blocks = ne;
```

Stessa correzione per Q4_0, Q4_1, Q5_0, Q5_1, IQ4_NL. In pratica il percorso KV quantizzata
girava a **1/32 di occupazione**, con una griglia fino a 32x sovradimensionata.

**Perche' dovrebbe pagare da noi.** **Oggi e' inerte**: usiamo KV in F16 (il profilo mostra
`flash_attn_ext_f16` e nessun kernel `cpy_*_q*`). Il valore e' di **secondo ordine e va detto
per quello che e'**: rimuove la ragione tecnica per cui la KV quantizzata non e' mai stata una
strada praticabile. E la KV quantizzata e' la sola sorgente di VRAM non ancora spremuta, e la
VRAM la sappiamo convertire in t/s: **339 → 512 slot ha fatto 9,93 → 12,64 t/s** sul banco senza
lane. Prima di provarci pero' serve un pre-controllo (§ 4.9): con MLA la KV e' gia' latente e
compressa, quindi il premio potrebbe essere piccolo *prima ancora* di misurare.

**Rischio di conflitto.** Bassissimo. `cpy.cu` nel nostro albero e' **identico** a quello del
genitore upstream (`git diff 69bf64379~1 HEAD -- cpy.cu` = vuoto): il file si applica **verbatim**.
Confligge solo `tests/test-backend-ops.cpp`, che si puo' lasciare indietro.

**Come si misura.** Pre-controllo prima del porto: leggere dal log di caricamento la taglia del
buffer KV a ctx 10000. Se e' sotto ~500 MiB la leva e' morta e il porto resta solo igiene.
Se e' sopra: portare, poi `-ctk q8_0 -ctv q8_0`, e il numero che deve muoversi e' **il numero di
slot della cache esperti a pari VRAM**, non il t/s diretto. Controllo di sanita' in `nsys`:
`cpy_f32_q8_0` deve comparire con blocchi da 64+ thread, non da 1.

---

### 2.3 `dbadb68ee` — PR #22789 — «ggml: use dynamic allocation for split graph inputs»

**Che cosa cambia davvero** (`ggml/src/ggml-backend.cpp`, +57/−6). Tre cose distinte:

1. `split->inputs[GGML_SCHED_MAX_SPLIT_INPUTS]` e `sched->graph_inputs[...]` diventano array
   dinamici con `realloc` a raddoppio. Gli `GGML_ASSERT(n_inputs < 30)` diventano una crescita.
   **Il taglio forzato dello split resta**: il controllo «troppi input» diventa
   `split->n_inputs >= split->inputs_capacity` e continua a mettere `need_new_split = true`.
   Quindi il numero di split **non cambia** al primo giro; cambia solo che non si aborta piu'.
2. `memset` dei nuovi slot quando `sched->splits` raddoppia — bug reale: prima i campi nuovi
   erano indeterminati, e con `inputs` che ora e' un puntatore diventerebbe un free su spazzatura.
3. `graph_size` passa da `n_splits * 30 * 2 * n_copies` (stima pessima fissa) a
   `total_inputs * 2 * n_copies` (conteggio vero).

**Perche' dovrebbe pagare da noi.** Due agganci, entrambi piccoli e onesti:
- **Assicurazione.** Facciamo 35,2 split per grafo con gli esperti in `CUDA0_Mapped`: siamo
  esattamente il caso che il commit descrive («wide MoE models on multi-backend setups»).
  Oggi non aborta; il giorno che alziamo `-ub`, o che il ramo overlap aggiunge un confine in
  piu', l'assert e' a 30 input di distanza e non da' preavviso.
- **Grafo piu' piccolo.** Con 35 split e `n_copies=1`, `graph_size` scende di ~1900 nodi su
  ~10.500 (dopo la fusione HC). Meno nodi = hash set piu' piccolo da azzerare a ogni eval.
  Ordine di grandezza atteso: **decine di microsecondi su 97,4 ms, cioe' sotto lo 0,1 %.**
  Non e' una leva, e non va venduto come tale.

**Rischio di conflitto.** **Il piu' alto fra quelli che consiglio, ed e' invasivo.**
`ggml-backend.cpp` e' il file col ramo di overlap CPU||GPU (+634/−36 nostre), e una delle tre
hunk cade **dentro** il blocco che abbiamo modificato: alle righe 1529-1548 c'e' il nostro
`confine_partizione` / `split->overlap_produttori`, immediatamente sotto il controllo
«too many inputs» che il commit riscrive. Va fatto a mano, hunk per hunk, ~30 righe, e va
riletta la nostra logica del confine dopo il merge.

**Come si misura.** Nessun t/s atteso. I due numeri di verifica sono:
(a) `GGML_SCHED_PROFILO=1` deve dare **lo stesso numero di split** (35,2) — se cambia, il merge
ha alterato il taglio e va rifatto;
(b) il `graph_size` loggato deve scendere di ~1900 nodi.
Se (a) cambia, ogni altro numero del banco e' invalidato: il confine si paga 0,94 ms l'uno.

---

### 2.4 `9bd4c09ea` — PR #26385 — «CUDA: Fix data-races when reusing SMEM in block_reduce»

**Che cosa cambia davvero** (`common.cuh`, `norm.cu`, `softmax.cu`). `block_reduce` scrive e
rilegge `shared_vals` senza `__syncthreads()` finale: chi la chiama due volte sullo **stesso**
buffer di shared memory ha una corsa. Il fix non tocca `block_reduce` (costerebbe a tutti), ma
i chiamanti:
- `soft_max_f32`: `__syncthreads()` esplicito fra la riduzione del max e quella della somma,
  **solo se `block_size > WARP_SIZE`**;
- `soft_max_f32_parallelize_cols_single_row`: due buffer distinti (`shared_vals[2][32]`) per max
  e somma, alzati al chiamante;
- `group_norm_f32`: doppio buffer (`s_sum + 32`) e shared size raddoppiata.

**Perche' dovrebbe pagare da noi.** Correttezza, non velocita', e **probabilmente inerte**:
con flash attention attiva il softmax dell'attenzione sta dentro `flash_attn_ext_f16` e
`soft_max_f32` **non compare nel profilo**; `group_norm` non lo usa nessun LLM. Il motivo per
cui lo tengo in classifica e' un altro: il nostro pavimento di rumore e' ±1,6 % e ci e' costato
caro trovarlo. Una corsa in un kernel che gira sotto la soglia dell'1 % produce esattamente il
tipo di rumore non riproducibile che ci ha gia' fatto annunciare numeri inesistenti.

**Rischio di conflitto.** Basso. `norm.cu` e `softmax.cu` sono **identici** al genitore upstream
e si applicano verbatim. Confligge solo `common.cuh` (nostro), dove il commit cambia **due
righe**: `T * shared_vals` → `[[maybe_unused]] T * shared_vals` piu' un commento. Additivo.

**Come si misura.** Pre-controllo: in `nsys` cercare `soft_max_f32`. **Se non compare, non
portarlo** — e' un porto senza numero. Se compare: due corse greedy identiche
(`LLAMA_SPEC_DRAFT_TOPK=1`) devono dare output bit-identico prima e dopo; se prima non lo erano
e dopo si', il commit ha appena spiegato una parte del nostro ±1,6 %.

---

### 2.5 `a035a8887` — PR #26389 — «server: Adding spec-decode counters to /metrics endpoint»

**Che cosa cambia davvero.** +58 righe, tutte additive:
`tools/server/server-task.{h,cpp}` accumulano `n_draft_total` / `n_draft_accepted` per slot;
`tools/server/server-context.cpp` li espone in `/metrics` in formato Prometheus con i nomi
allineati a vLLM (`spec_decode_num_drafts`, `spec_decode_num_draft_tokens`,
`spec_decode_num_accepted_tokens`).

**Perche' dovrebbe pagare da noi.** Non paga in t/s: paga in **costo di misura**, che su un banco
solo e' la risorsa scarsa vera. Su 349 corse abbiamo studiato la correlazione colpi→t/s (0,20)
leggendo i colpi dal log. Un contatore cumulativo interrogabile a fine corsa rende quella lettura
un `GET`, elimina il parsing e — importante — elimina la classe di errore in cui il conteggio
proviene da una finestra diversa dal t/s riportato (`ms/ciclo` e' gia' una media condizionata che
ci ha fregati una volta).

**Rischio di conflitto.** Basso-medio, additivo. `server-task.{h,cpp}` non sono nei nostri file
modificati: applicano puliti. Solo la hunk di `server-context.cpp` (il nostro file da +500/−213)
va inserita a mano dentro l'handler `/metrics`.

**Come si misura.** Non c'e' un numero da muovere: c'e' un numero da **rendere leggibile**.
Verifica: `curl /metrics` deve riportare un rapporto accettati/bozze coerente con quello che il
log riporta oggi. Se i due divergono, e' un risultato di per se'.

---

### 2.6 `596a5795b` — PR #25784 — **solo una riga**, non il commit

**Che cosa cambia davvero.** Il commit intero e' 1532 righe (§ 4.6, da non portare). Ma dentro
c'e' una correzione di una riga in `common/speculative.cpp`:

```c
-GGML_ASSERT(n_embd == llama_model_n_embd(llama_get_model(ctx_tgt)) &&
+GGML_ASSERT(n_embd == llama_model_n_embd_out(llama_get_model(ctx_tgt)) &&
         "MTP input row width must match the target h_nextn width");
```

**Perche' dovrebbe pagare da noi.** Abbiamo esattamente quella riga sbagliata:
`common/speculative.cpp:1328`. Il lato bozza usa gia' `n_embd_out` (riga 1327), il lato bersaglio
no. Oggi passa perche' per DSV4-Flash i due coincidono; e' un assert che protegge male.

**Rischio di conflitto.** Nullo. Una riga, in un punto che nel nostro albero e' identico.

**Come si misura.** Non si misura. E' igiene, e va in fondo alla lista proprio per questo.
La includo perche' costa un minuto e perche' un assert che non controlla la cosa giusta e' un
allarme spento.

---

### 2.7 Nota: la meta' buona di `687e77892`

Il commit «CUDA: fuse rms_norm + mul + rope» va **scartato per la fusione** (§ 4.1), ma contiene
un indurimento indipendente: la fusione `ROPE + VIEW + SET_ROWS` gia' esistente passa da
`return true` a `ggml_cuda_check_fusion_memory_ranges(...)`, cioe' controlla che i tensori non si
sovrappongano prima di fondere. Nel nostro albero quel `return true` sta a
`ggml/src/ggml-cuda/ggml-cuda.cu:3677`, e abbiamo un anello KV con scritture `set_rows` su
un buffer circolare — la classe di aliasing che il controllo copre. **Otto righe**, additive.
Numero atteso: zero sul t/s; verifica: nessuna fusione persa in `GGML_CUDA_DEBUG` e output
identico. Da fare **solo** se e quando si tocca quella zona per altro.

---

## 3. Classifica unica, valore/rischio

| # | commit | PR | valore | rischio | costo | verdetto |
|---|--------|----|--------|---------|-------|----------|
| 1 | `c8e03ce81` | 26649 | **alto (abilitante)** | nullo | 5 righe, **riscritto** non pickato | **fare subito** |
| 2 | `69bf64379` | 26731 | medio (secondo ordine) | nullo | verbatim su `cpy.cu` | fare, dopo il pre-controllo KV |
| 3 | `a035a8887` | 26389 | medio (misura) | basso | 1 hunk a mano | fare |
| 4 | `9bd4c09ea` | 26385 | medio (rumore) | basso | 2 file verbatim + 2 righe | fare **se** `soft_max_f32` compare |
| 5 | `596a5795b` (1 riga) | 25784 | basso (igiene) | nullo | 1 riga | fare |
| 6 | `dbadb68ee` | 22789 | basso (assicurazione) | **alto** | ~30 righe nel file dell'overlap | fare **per ultimo**, isolato |
| — | `687e77892` (solo range check) | 26767 | basso | basso | 8 righe | opportunistico |

**Ordine operativo.** 1 → 5 → 3 → 4 → 2 → 6, e cioe': prima le cose a rischio zero che non
richiedono banco (1, 5), poi lo strumento di misura (3) **prima** delle misure, poi i due che
hanno un pre-controllo (4, 2), infine da solo e con un giro di banco dedicato quello invasivo (6).

Il costo di banco totale e' **una corsa di controllo** (il riferimento dopo 1+5+3+4), piu' una
corsa dedicata per 6, piu' l'esperimento KV quantizzata se il pre-controllo di 2 lo giustifica.
Nessuno di questi porti merita una campagna: nessuno ha un numero atteso sopra il rumore.

---

## 4. Quelli da NON portare, e perche'

Questa e' la parte che conta piu' della classifica. Upstream ha gia' fatto un revert su
quest'area (#20793: +1 % su una 4090, −50 % su AMD): **il loro regime non e' il nostro**.

### 4.1 `687e77892` #26767 — «CUDA: fuse rms_norm + mul + rope» — **il piu' ovvio, e sbagliato**

Sembra fatto apposta: attacca `rms_norm_f32` (1 %), un `mul` di `k_bin_bcast` (2 %, ~1.300
istanze/token) e il `rope`, e riduce **lanci**, che e' la valuta di un regime orchestration-bound.
Ma **il pattern non esiste nel nostro grafo**, e si vede leggendo il modello, non il titolo.

La condizione della fusione e' `rope->src[0] == mul` (`ggml_cuda_should_fuse_rms_norm_mul_rope`).
In `src/models/deepseek4.cpp`, nel percorso MLA:

- riga 936: `q = ggml_rms_norm(ctx0, q, norm_rms_eps)` — **senza peso**. Non c'e' nessun `MUL`:
  la sequenza `RMS_NORM, MUL, ROPE` non puo' formarsi.
- righe 954-967: `kv = build_norm(kv, attn_kv_norm, ...)` produce `RMS_NORM, MUL`, ma poi c'e'
  `ggml_reshape_3d`, poi `ggml_view_3d`, e **solo allora** `ggml_rope_ext(ctx0, kv_pe, ...)`.
  `rope->src[0]` e' una **view**, non il `mul`. Stessa struttura per `q_pe` (righe 943-948).

Il pattern che upstream ha fuso e' quello Qwen3/Gemma (`q_norm`/`k_norm` per testa, applicato
direttamente prima del rope). **MLA non lo produce mai**, perche' rope tocca solo la fetta
posizionale del vettore, e la fetta e' una view. Verdetto: **inerte per costruzione**, e costa
344 righe su `ggml-cuda.cu`, che e' uno dei nostri file caldi.
(La sola parte utile e' l'indurimento di § 2.7.)

### 4.2 `153d324bc` #26081 — «load-mode auto, avoids mmap on iGPUs» — **secondo ovvio, e neutro**

Tocca mmap, e tutto il nostro impianto (`CUDA0_Mapped`, esperti in RAM host mappata) vive di
mmap: sembra da leggere con attenzione. Letto: aggiunge `mmap_support` alle props di device, e
per CUDA lo pone a `props->type != GGML_BACKEND_DEVICE_TYPE_IGPU`. Su una 3060 discreta
`auto` **risolve a mmap**, e in `llama-model-loader.cpp` `use_mmap` e' vero anche per `AUTO`.
Comportamento **identico** al nostro di oggi. Costo: 33 file, di cui **6 nostri**
(`common/arg.cpp`, `common/common.h`, `ggml-backend-meta.cpp`, `ggml-cpu.cpp`, `ggml-cuda.cu`,
`include/llama.h`). Valore misurabile: **zero**. Non portare.

### 4.3 `1269cb1ff` #26531 + `1c3c9674d` #26577 + `3db4ff877` #26672 — **la trappola dflash**

`1c3c9674d` si chiama letteralmente «fix **dflash** wo_a reshape on load», ed e' il nostro
modello. E' la trappola migliore della lista. Ricostruito nell'ordine:

- `1269cb1ff` introduce `TENSOR_ALLOW_RESHAPE` nel loader e riscrive `create_tensor` per
  ricalcolare `ne`/`nb` a mano;
- `1c3c9674d` **usa** quel flag per cambiare `wo_a` da 2D `{n_head*n_embd_head/o_groups,
  o_lora_rank*o_groups}` a 3D `{..., o_lora_rank, o_groups}`;
- `3db4ff877` ripara il ricalcolo di `1269cb1ff`, che per un tipo **quantizzato** calcolava
  `nb[1] = ne[0]*nb[0]` invece di `ggml_row_size(type, ne[0])` — cioe' stride sbagliati di un
  fattore pari alla dimensione del blocco.

Nel nostro albero: `TENSOR_ALLOW_RESHAPE` **non esiste** (grep: zero occorrenze) e
`src/models/dflash.cpp:166` ha ancora la forma 2D. **Non abbiamo il bug perche' non abbiamo il
refactor.** Portare i tre significa importare un bug e la sua toppa, su un modello IQ2_XXS dove
proprio gli stride quantizzati sono la cosa che si rompe in silenzio. E `wo_a` e' consumato da
`build_mla_o`, che noi abbiamo modificato. Non portare, e non portarne nemmeno uno.

### 4.4 `563dec81c` #26474 — «allocate indexer cache only in full indexer layers»

Sembra VRAM gratis sull'indicizzatore lightning, e la VRAM la sappiamo convertire in slot.
Letto: il filtro nuovo e'
`il < n_layer() && (arch != LLM_ARCH_GLM_DSA || hparams.is_indexer_full(il))` — cioe' **cambia
qualcosa solo per GLM_DSA**. Per ogni altra architettura il filtro e' equivalente a prima.
In piu' agisce su `llama_kv_cache_dsa`, mentre noi passiamo per `llama_kv_cache_dsv4` (nostro,
+672/−223), e `is_indexer_full` **non esiste nel nostro albero**: non compilerebbe.
Non portare. **L'idea invece resta nostra da valutare**: se in DSV4-Flash esistono strati dove
l'indicizzatore non e' pieno, lo stesso filtro e' VRAM libera — ma e' lavoro nostro su
`llama-kv-cache-dsv4.cpp`, non un cherry-pick.

### 4.5 `dd1ea5243` #25532 (+ `030ebb558`, `96278e39f` #25262, `935cad649`, `4801e3c56`) — backend sampling multi-output

E' la famiglia che sembra piu' promettente sulla carta: campionare sulla GPU toglie il rientro
dei logit sull'host, e i confini CPU/GPU li paghiamo 0,94 ms l'uno. Aritmetica prima del porto:
con un vocabolario dell'ordine di 10^5 e due uscite (batch 2, `--spec-draft-n-max 1`) i logit
sono **~1 MB per token**; al 24 GiB/s misurato dal microbench del trasporto sono **~40 µs**,
e la **sincronizzazione resta comunque**,
perche' la speculazione deve vedere gli id per decidere l'accettazione. Tetto realistico: **~0,2 %**.
Costo: 1282 righe su 24 file, fra cui **cinque dei nostri piu' modificati**
(`llama-context.cpp` 309 righe, `llama-graph.cpp` 152, `speculative.cpp`, `server-context.cpp`,
`llama-cparams.h`). E' il conflitto piu' grande della lista a fronte del guadagno piu' piccolo.
Non portare.

### 4.6 `596a5795b` #25784 — «DeepseekV4 MTP + DSpark» — **non e' un porto, e' un progetto**

1532 righe su `llama-kv-cache-dsv4.cpp` (+345), `models/deepseek4.cpp` (+489),
`models/dflash.cpp` (+270), `llama-graph.{cpp,h}`, `llama-context.cpp` — cioe' **esattamente i
quattro file che il nostro fork ha riscritto**. Aggiunge la testa MTP nativa di DeepSeek-V4
(`NEXTN_*`, `llm_arch_is_hybrid`, rollback dello stato ricorrente) mentre noi abbiamo **gia'**
DSpark funzionante e strumentato (`dflash.cpp:256` `build_dspark_markov_head`, tap 41/42/43,
testa di Markov, `DSPARK_NO_MARKOV=1` per la diagnostica).
La domanda vera — «la testa MTP nativa accetta piu' della testa di Markov?» — e' legittima e
grossa, ma si risponde con un esperimento progettato, non con un cherry-pick su un banco solo.
Non portare ora. Se un giorno si affronta, si affronta **dopo** l'unshallow, in un worktree, e
la metrica e' accettati/bozze a pari t/s, non il t/s.

### 4.7 `0ef6e55ed` #26398 (template chat DSV4-Flash 0731) e `a6aa6f545` #26524 (sampler) — **cambiano il banco**

Entrambi cambiano **cosa viene generato**, non quanto in fretta: il primo il prompt effettivo
(nuovo template jinja + `additional_context` per il response_format), il secondo la finestra di
storia dei sampler penalizzanti. Abbiamo gia' perso una campagna intera perche' il banco
misurava `/completion` senza chat template: **a campagna aperta questi due sono vietati**.
Se e quando si adotta il template nuovo, va rifatto il riferimento da zero e il confronto con
tutto lo storico decade.

### 4.8 `f785fc9ea` #26904 e `7bd8282c3` #26510 — refactor di `speculative.cpp`

Il primo toglie 80 righe da `common/speculative.cpp` e 6 dall'header (**cambio di API**), il
secondo e' −45/+16 di deduplicazione. Zero comportamento, zero numeri, conflitto garantito su un
file che abbiamo modificato pesantemente. Il refactor upstream lo si assorbe **una volta sola**,
quando si fa l'unshallow e si allinea tutto; assorbirlo adesso significa pagarlo due volte.

### 4.9 `9a688e51e` #26605 — «fit: Fix memory allocation for MTP layers»

Terzo ovvio-ma-no. Si presenta come una correzione di contabilita' VRAM, e la VRAM e' la nostra
valuta. Letto (`common/fit.cpp`): prima `hp_ngl = n_layer + n_layer_nextn` **sempre**, ora il
termine `n_layer_nextn` si somma **solo se `mparams->load_mtp`** — cioe' l'auto-fit smetteva di
sovrastimare gli strati quando la testa MTP non viene caricata.

Perche' non ci tocca, in tre passaggi: (a) partiamo con **`-ngl 99` esplicito**, quindi il
percorso di auto-fit non decide niente per noi; (b) `load_mtp` **non esiste nel nostro albero**
(grep: zero occorrenze in `include/llama.h`, `common/common.h`, `common/fit.cpp`), quindi il
commit non compilerebbe senza trascinarsi dietro `596a5795b`; (c) la seconda meta' del commit
tocca `create_tensor_qkv` in `llama-model.cpp` con `TENSOR_SKIP`, che e' infrastruttura di
un'altra famiglia. Non portare.

### 4.10 Il resto, per famiglie

- **~60 commit** di backend non nostri: sycl, vulkan, metal, opencl, webgpu, hexagon, cann,
  zdnn, zendnn, openvino, virtgpu, spacemit. Nessun effetto possibile: non compiliamo quei
  backend.
- **~25 commit** di CI/build/vendor (`2e2d99cfd`, `a1f96d4fc`, `0666ad2b2`, `70dfba5ae`,
  `936918514`, `aea252fb4`, `d8d988722`, `22dc605c4`, `6ea215d17`, `61141f148`, `1e396e72a`,
  `e5275f6f7`, `704485942`, `4c6766fd7`, `61881b1f7`, `94bc47f28`, `e23e9440e`, `fe2adf0e7`,
  `d52ec04a6`, `6b5224cfc`, `9303cdd8d`, `34e9ee57f`, `2468576f2`, `6ad4ab0ea`, `9ba73fd1f`).
- **~15 commit** ui/webui e **~10** server-tools/router/isolamento docker (`dd2c7c447`,
  `4ae84dea2`, `18f7ad7fc`, `7ba604f1c`, `dff15d4ac`, `e1470ee6a`, `99111b19c`, `f2b52a87e`,
  `f9e832c10`, `4308a4f03`): non usiamo nulla di questo percorso.
- **~12 commit** di altre architetture (Granite-Switch, Muse Glimmer, Nemotron, GLM-4.7-Flash,
  Qwen3-Next, MiniMax M3, EXAONE, DeepSeek **V3.2** `2b63e0610`): modelli che non carichiamo.
- **~12 commit** di conversione/gguf-py/model-saver/imatrix. Caso a parte:
  - `eb5667a16` #26673 «convert: fix DeepseekV4 rope parameters with transformers 5.x» —
    **non si porta** (tocca solo `conversion/deepseek.py`, il nostro GGUF esiste gia'), **ma si
    controlla**: se il GGUF e' stato prodotto con transformers 5.x, `rope_scaling` puo' aver
    perso `rope_type`. Si verifica con `gguf_dump` sulle chiavi rope, e costa zero banco.
    Se fosse sbagliato spiegherebbe qualita' e non velocita' — quindi non tocca i nostri numeri,
    ma tocca il senso di quello che generiamo.
  - `38406d597` #26861 (imatrix su soli esperti toccati): utile **solo** se un giorno ci
    quantizziamo il modello in casa.
- `598863317` #26111 (kernel wkv7): RWKV, architettura che non usiamo.
- `f8def7fe1` #25928 (ROLL contiguo su CUDA/Metal): `GGML_OP_ROLL` non compare nel nostro grafo.
- `5b87ed30f` #26688 (warning di variabili inutilizzate): confligge anche su `quantize.cu`, che
  **non abbiamo mai toccato** — e' il buco invisibile. Non vale il merge a mano per dei warning.
- `a1f96d4fc` #26544: nella parte CUDA e' **solo** un assert rilassato per iGPU dentro
  `ggml_cuda_graph_evaluate_and_capture`. Nota a margine da tenere: e' l'assert
  `node->buffer->buft == ggml_backend_cuda_buffer_type(device)`, cioe' **quello che salterebbe
  per primo sui nostri buffer `CUDA0_Mapped`** se mai compilassimo senza `NDEBUG`.
- `42e98813e` #26555: una riga in un file di test, per GCC 16.1 su MSYS2. Compiliamo con MSVC.
- `0b14b87d7` #26508: avviso che la porta di default passera' da 8080 a **9931**. Non e' un
  porto, e' una scadenza: i nostri script di banco hanno 8080 cablato.

---

## 5. Riepilogo in una riga per ciascuno dei sei

| commit | il numero che deve muoversi |
|--------|------------------------------|
| `c8e03ce81` | nessuno adesso; poi la quota di join sotto 73,4 % e la finestra da 0,25 verso 0,70 ms |
| `69bf64379` | slot della cache esperti a pari VRAM, dopo `-ctk/-ctv q8_0` (e solo se il buffer KV e' grande) |
| `a035a8887` | nessuno: rende leggibile accettati/bozze da `/metrics` invece che dal log |
| `9bd4c09ea` | bit-identita' fra due corse greedy; portare solo se `soft_max_f32` compare in `nsys` |
| `596a5795b` (1 riga) | nessuno: e' un assert che oggi controlla la cosa sbagliata |
| `dbadb68ee` | split per grafo **invariati** a 35,2 (se cambiano, il merge e' sbagliato); `graph_size` −1900 nodi |

## 6. Che cosa fare comunque, indipendentemente dai porti

1. **`git fetch upstream --unshallow`.** Senza, questo audit non e' ripetibile e il conteggio
   «153» continuera' a significare qualcosa che non e'.
2. Dopo l'unshallow, rifare `HEAD..upstream/master`: il numero vero sara' piu' grande, e il buco
   14/7 – 2/8 diventera' leggibile. Solo allora ha senso chiedersi se conviene un
   **allineamento in blocco** (un merge upstream in un worktree) invece del cherry-pick a goccia:
   con 4 file nostri riscritti e ~1 mese di deriva, il costo del cherry-pick cresce a ogni giro,
   mentre l'allineamento si paga una volta.
3. Il controllo `gguf_dump` sui parametri rope del nostro GGUF (§ 4.9). Costa zero banco.
