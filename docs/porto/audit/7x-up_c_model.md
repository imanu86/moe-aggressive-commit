# UP_C — `src/`: modello, grafo, KV, quant

Ramo `overlap`, HEAD `9b7f9eea7`. `merge-base HEAD upstream/master` = `5c3a58686` (9 luglio).
Upstream avanti di **436** commit, di cui **67** toccano `src/`. Noi 133.

Nessuna compilazione, nessun avvio, nessuna patch. Tutto quello che segue e' **letto nel diff**
o **letto in un log gia' su disco**; i due marchi sono espliciti riga per riga.

---

## 0. Il perimetro, e perche' e' piu' piccolo di 67

`git diff --stat HEAD upstream/master -- src/` = 62 file, +8.536/−3.512. Ma la massa e' in
architetture che non carichiamo (minimax-m3 601, granite-switch 426, hy-v3 394, laguna 333,
muse-glimmer 208, nanbeige 184, pockettts 146…). I file che ci riguardano davvero:

| file | righe di divergenza | quanto e' *nostro* |
|---|---|---|
| `src/models/deepseek4.cpp` | 946 | molto (HC fusa, predittore route, cattura strato) |
| `src/models/dflash.cpp` | 626 | molto (DSpark, backbone DSV4) |
| `src/llama-kv-cache-dsv4.cpp` | 1.200 | **riscritto** (anello KV, rollback parziale) |
| `src/llama-context.cpp` | 1.021 | molto (cancelli, VRAM a fasi, leve) |
| `src/llama-graph.cpp` | 717 | medio |
| `src/llama-model.cpp` | 371 | poco |
| `src/llama-arch.cpp` | 33 | **niente** |
| `src/llama-quant.cpp` | **23** | **niente — mai toccato** |

Quest'ultima riga e' il risultato piu' utile della tabella: **tutta** la divergenza di
`llama-quant.cpp` sono aggiunte upstream. Vedi §4.

Dei 67, **44 sono architetture o vocab/sampler/grammar che non tocchiamo**. Ne restano 23
degni di lettura, e di questi 4 li abbiamo gia' (vedi §5.1).

---

## 1. Le risposte, in testa

**Q1 — DSV4/MLA, meno nodi, meno `k_bin_bcast`?**
Upstream ha fatto **esattamente due cose grosse** su questo grafo dal 9 luglio: la fusione
hyper-connection (#25585) e l'op indexer (#24231). **Le abbiamo gia' portate entrambe**
(`0adb16c64`, `0441857cb`). Il `k_bin_bcast` **e' l'HC**: la catena non fusa fa 4 `mul` + 3
`add` nel `pre` e 16 `mul` + 16 `add` nel `post`, cioe' **39 istanze per strato × 43 = 1.677**,
che e' il conto degli «~1.300 a token» del profilo (1,80 ms/token, 2%). Chi li toglie e' gia'
in casa; il residuo dopo `LLAMA_DSV4_HC_FUSO=5` e' il solo `pre`, **7 × 43 = 301 istanze**.
Quello che resta da prendere e' minuto: **#25702** (−84 nodi), **#25370** (−~80 nodi, via i
`ggml_cast` delle maschere). Alla calibrazione dell'audit 45 (+16,5% per 24.000 nodi =
**0,0069 %/nodo**) sono **+1,1 %** messi insieme, cioe' dentro la deriva del banco (2,4%).
**L'unica leva di Q1 che vale piu' del rumore e' `dee2a846b` (#25832), e non e' una fusione:
e' un piazzamento** (§2.1).

**Q2 — il prefill?**
**Non c'e' niente. E il perche' e' gia' misurato da noi, non da dedurre.** Il libro mastro
dell'audit 38 assegna **36-41 ms dei 44,27 ms/token** agli **esperti letti via PCIe
zero-copy** (43 strati × U esperti unici × 6,75 MiB). Il grafo — nodi, split, sottomissione —
vale **0,3-0,8 ms/token**, l'1-2%. Un porto che togliesse *tutti* i nodi che upstream ha
tolto in questa finestra sposterebbe il prefill di meno dell'1%. La leva del prefill e' `-ub`
(audit 38 §6: `-ub 512` = ×2,4-4,0), ed e' un flag. **Risultato negativo, e vale come
risultato**: upstream non ha una leva di prefill in `src/`, perche' il nostro prefill non e'
graph-bound.

**Q3 — `--cache-type-k q8_0`: cosa serve lato `src/`?**
Serve **il porto di `69e62fc77` (#25871)**, che impone `type_k == type_v` per MLA/DSV4 (nel
grafo DSV4 K e V **sono lo stesso tensore**: `build_attn_mha(q, k_all, k_all, …)`) e
auto-accende FA. E serve togliere il divieto in `llama-kv-cache-dsv4.cpp:1239` (`LLAMA_KV_RING
requires F16 or F32 compressed K`).
**Ma il premio non esiste, ed e' aritmetica dal log, non opinione.** Da
`bussate_base100.server.log` a ctx 10.240, con l'anello acceso:

| buffer | dove | MiB | risponde a `type_k`? |
|---|---|---|---|
| raw SWA (256 celle × 43 strati) | CUDA0 | 10,75 | si' |
| anello caldo CSA+HCA+LID | CUDA0 | 18,12 | si' |
| stato compressori csa/hca/lid | CUDA0 | 11,64 | **no, e' F32 per costruzione** |
| CSA/HCA/LID compressi (2560+256+2560 celle) | **CUDA0_Mapped (host)** | 70,62 | si', ma non e' VRAM |

**KV in VRAM = 40,51 MiB. Quello che q8_0 dimezza = 28,87 → ~15,3 MiB. Risparmio 13,5 MiB.**
Uno slot di cache esperti costa **6,75 MiB** (log: `cache-esperti: 448 slot da 6.75 MiB = 3026
MiB in VRAM`). **13,5 MiB = 2 slot su 448 = +0,45%.** E i 339→512 che valgono 9,93→12,64 t/s
sono 173 slot, cioe' **1.168 MiB**: per comprarli con la KV bisognerebbe che la KV in VRAM
fosse ottanta volte quella che e'. Non lo e' **perche' l'anello l'ha gia' spostata in host**.
La premessa «meno VRAM = piu' slot» e' giusta; il numeratore e' sbagliato di due ordini.
**Verdetto: la KV quantizzata non e' una leva di slot a questo contesto. #25871 si porta come
guard-rail (impedisce una configurazione silenziosamente incoerente), non come guadagno.**

**Q4 — `llama-quant.cpp`?**
**Si', due commit, e uno e' obbligatorio.** `56d6e9dde` (#25716) e' *esattamente* «riquantizzare
selettivamente»: oggi `--pure` **ignora** `--tensor-type`. E `4937ca83f` (#25787) esclude
`ffn_gate_tid2eid` dalla quantizzazione — il nostro GGUF ha `deepseek4.hash_layer_count = 3`,
quindi **tre** di quei tensori i32: senza il fix una requant di DSV4 **muore** (i32 non ha
dequantizzatore, `llama-quant.cpp:224` tira). Il file e' pulito al 100%: 23 righe di
divergenza, tutte upstream. Vedi §4 per il pezzo che *non* si porta (la firma del loader).

---

## 2. Le schede

### 2.1 `dee2a846b` — PR #25832 — «adjust logic for offloading ops to weight's backend»

**Il candidato numero uno di tutto il fronte `src/`.** Audit 45 §1.3 l'aveva spezzata in due e
messo la meta' `ggml-backend.cpp` in UP_D; qui giudico la meta' `src/`, che e' **separata,
piccola e mirata al nostro grafo**.

**Cosa cambia, letto nel diff** — due pezzi:

*(a)* `llama-context.cpp` `graph_get_cb()` (nostro `:3013-3027`): il forcing sul device dello
strato passa da `strcmp(name,"norm")==0` a `(strcmp(name,"norm")==0 || strcmp(name,"l_last")==0)`.
Il commento nuovo dice il motivo: «force the last op of the layer on the specified backend to
avoid running it on the backend of the next layer due to scheduling».

*(b)* `models/deepseek4.cpp`: nel ciclo strato, subito dopo `cb(cur, "hc_ffn_pre", il)` (nostro
`:1319`) entrano tre righe

```
ggml_build_forward_expand(gf, residual);
ggml_build_forward_expand(gf, post);
ggml_build_forward_expand(gf, comb);
```

e l'ultimo `cb` dello strato diventa `cb(inpL, "l_last", il)` invece di `"l_out"` (nostro `:1455`).
Le tre `forward_expand` **fissano l'ordine**: `residual`, `post` e `comb` — i tre tensori che
`build_hc_post` consumera' a fine strato — vengono materializzati **prima** del blocco FFN
invece che dopo, quindi non restano vivi a cavallo del MoE e non trascinano l'ultimo nodo
dello strato nel backend dello strato dopo.

**Perche' dovrebbe pagare, agganciato a un numero nostro.** E' la stessa lezione di
`64745aced` («l'ordine di esecuzione e' del grafo, non del sorgente — expand esplicito del
ramo GPU»), applicata all'HC invece che all'overlap. E il numero che attacca e' il nostro piu'
caro: **il confine costa 0,94 ms l'uno, il 18,5% del ciclo**, e **il join e' il 73,4% del
tempo**. Il cancello `ubatch.n_tokens < 32 || full_offload` e' **sempre vero da noi**, per due
vie indipendenti: `n_tokens = 2` nel decode speculativo; e `full_offload` =
`model.n_gpu_layers() > hparams.n_layer_all`, dove `n_gpu_layers()` ritorna `params.n_gpu_layers`
(`llama-model.cpp:1685`) che vale **≥ 44** — il log dice `offloading output layer to GPU` e
`offloaded 44/44 layers` — contro `n_layer_all = 43` (`deepseek4.block_count = 43`).
**Quindi il ramo e' vivo anche al prefill.** [MISURATO il cancello, DEDOTTO l'effetto]

**Rischio di conflitto.** *(a)* PULITO: le nostre 15 righe di `graph_get_cb` sono
verbatim la forma pre-fix, il pick e' una condizione. *(b)* MEDIO: il punto d'innesto esiste
identico (`residual`/`post`/`comb` con gli stessi nomi, `cb(cur,"hc_ffn_pre",il)` alla stessa
posizione logica), ma la nostra classe e' `llama_model_deepseek4::graph` con `capture_layer_inp`
in testa al ciclo e il ramo `dsv4_hash_layer_count` in mezzo: la patch va rifatta a mano, non
applicata. Il rename `l_out`→`l_last`: verificato che **nessuno in `src/` legge quel nome**;
l'unico consumatore in tutto il repo e' `tools/cvector-generator/cvector-generator.cpp:331`,
che non usiamo. **Attenzione**: se lo rinominiamo, i nostri dump per nome (`GGML_SCHED_DEBUG`,
sonde per nome) mostreranno `l_last-N`.

**Quale numero deve muoversi.** Numero di split e ms di join da `GGML_SCHED_PROFILO=1`:
il join deve scendere sotto il 73,4%. Secondariamente il ciclo, oggi 130,5 ms. Se split e join
non si muovono, la parte *(b)* e' inerte e va tolta — **e i tre `forward_expand` vanno provati
da soli**, perche' sono la meta' che non ha rischio di nome.

---

### 2.2 `56d6e9dde` — PR #25716 — «quant : allow using manual tensor types with --pure»

**Cosa cambia, letto nel diff.** Due righe in `llama_tensor_get_type` (nostro `:676` e `:704`):

```
-    if (!params->pure && ggml_is_quantized(default_type)) {
+    if (ggml_is_quantized(default_type)) {
...
-        if (!manual) {
+        if (!manual && !params->pure) {
```

Prima: con `--pure` **tutto** il blocco dei pattern manuali era saltato, quindi
`--tensor-type` era **ignorato in silenzio**. Dopo: i pattern manuali valgono sempre, e `--pure`
disattiva solo la logica automatica della mistura.

**Perche' dovrebbe pagare, agganciato a un numero nostro.** E' l'unica forma in cui una
requant selettiva e' *predicibile*: «tutto al tipo base della ftype, TRANNE questi pattern».
Senza `--pure` i tensori non nominati restano in mano a `llama_tensor_get_type_impl`, che
cambia tipo per strato e per forma (`:520`, `:576`, `:599`, `:607`) — cioe' l'esperimento non
e' controllato. E c'e' un secondo effetto, indiretto ma decisivo: `tensor_requires_imatrix()`
(`:1041`) riceve `metadata[i].target_type`, che ora **e' il tipo del pattern**. Quindi il
precheck di `:1045-1055` (`throw "this quantization requires an imatrix!"`, che oggi ferma la
corsa vera) **passa** se i pattern puntano a tipi che non esigono imatrix. Il precheck non e'
cambiato upstream — e' `#25716` che cambia cosa gli si fa vedere. [DEDOTTO dal codice, non
provato con una corsa]

**Rischio di conflitto.** **ZERO.** `llama-quant.cpp` non l'abbiamo mai toccato; le due righe
sono a distanza zero dal contesto upstream.

**Quale numero deve muoversi.** Nessuno sul banco. Il cancello e' un `--dry-run`:
`llama-quantize --pure --tensor-type '<pattern>=<tipo>' --dry-run` deve stampare il tipo del
pattern sui tensori che lo matchano e il tipo base su tutti gli altri. Oggi stampa il tipo base
ovunque.

---

### 2.3 `4937ca83f` — PR #25787 — «exclude i32 ffn_gate_tid2eid routing table»

**Cosa cambia.** Tre righe in `tensor_allows_quantization` (nostro `:307`):

```
+    // do not quantize the i32 token-id -> expert-id routing table (DeepSeek-V4)
+    quantize &= name.find("ffn_gate_tid2eid.weight") == std::string::npos;
```

**Perche' dovrebbe pagare.** Non e' velocita', e' **la corsa che finisce**. Il nostro GGUF ha
`deepseek4.hash_layer_count = 3` (log riga 35 del dump kv), e `deepseek4.cpp:1328` fa
`ggml_get_rows(ctx0, layer.ffn_gate_tid2eid, res->t_inp_tokens)` — quindi i tre tensori i32
esistono. Senza l'esclusione il quantizzatore li prende in carico e muore a `:224`
(«type %s unsupported for integer quantization: no dequantization available»). **Se un giorno
riquantizziamo DSV4 senza questo, la corsa muore dopo aver gia' scritto meta' del file.**

**Rischio di conflitto.** **ZERO.** Stesso file mai toccato.

**Quale numero deve muoversi.** Nessuno. E' un cancello binario: `llama-quantize --dry-run`
sul nostro GGUF DSV4 deve arrivare in fondo.

Nota: nella stessa zona upstream ha aggiunto altre tre esclusioni (indexer MiniMax
`k_proj`/`q_proj`, codebook audio `a.rvq.codebook`/`mm.a.code_embd`). Sono inerti per noi ma
**vengono gratis nello stesso hunk** — non vale la pena separarle.

---

### 2.4 `69e62fc77` — PR #25871 — «enforce the same K and V cache types for DeepSeek V4»

**Cosa cambia.** In `llama_init_from_model` (nostro `:4141`): sostituisce l'errore secco
«V cache quantization requires flash_attn» con (i) un rifiuto se
`(hparams.is_mla() || arch == LLM_ARCH_DEEPSEEK4) && type_k != type_v`, e (ii) l'auto-accensione
di FA quando `type_v` e' quantizzato e `flash_attn_type == AUTO`.

**Perche' e' *corretto*, e perche' non paga.** La ragione del vincolo si legge nel nostro
grafo: `build_csa_lid_attention`, `build_hca_attention` e `build_raw_attention` chiamano tutte
`build_attn_mha(q, k_all, k_all, …)` — **K e V sono lo stesso tensore**. Dare `type_k=q8_0` e
lasciare `type_v=f16` oggi non fa errore: fa una configurazione che non ha senso e che nessuno
segnala. Questo e' il valore del porto.
Il guadagno invece e' quello di §1/Q3: **13,5 MiB, 2 slot su 448**. In piu' ci sono due
ostacoli in casa, entrambi nostri:
- `llama-kv-cache-dsv4.cpp:1239-1241` **tira** con K quantizzata (`LLAMA_KV_RING requires F16
  or F32 compressed K`). Spegnere l'anello per quantizzare e' un cambio al contrario: manda in
  VRAM i 70,62 MiB oggi in host.
- gli **stati compressori** (11,64 MiB, il 29% della KV in VRAM) sono `GGML_TYPE_F32` cablato
  (`:999-1000`) e **non rispondono a `type_k`** per costruzione.

`n_embd_head_k = 512` (log riga 104) e' divisibile per 32, quindi il cancello di `:4119-4128`
passerebbe con q8_0/q5_0/q4_0. Il vincolo geometrico **non** e' il problema.

**Rischio di conflitto.** BASSO. Il blocco vive in `llama_init_from_model`, zona che non
abbiamo riscritto; l'unica accortezza e' che il nostro `llama-context.cpp:570-574` ha una
**seconda** copia dello stesso controllo (che tira invece di ritornare `nullptr`) e va tenuta
coerente.

**Quale numero deve muoversi.** Nessuno: il cancello e' che una corsa con
`--cache-type-k q8_0` senza `--cache-type-v q8_0` **rifiuti** invece di partire.

---

### 2.5 `33a75f41c` — PR #25702 — «DeepseekV4: reduce graph splits»

**Cosa cambia.** In `build_overlap_compressed_kv_from_state` (nostro `:507-560`): oggi si
tagliano due viste `prev_idxs`/`cur_idxs` di `state_read_idxs` e si fanno **quattro**
`ggml_get_rows` (due su `kv_state`, due su `score_state`); dopo si fanno **due** `get_rows`
sull'intero `state_read_idxs` e si prendono le due meta' come `ggml_view_2d` con offset
`n_read*nb[1] + …`.

**Quanto vale, contato.** La funzione e' chiamata due volte per grafo, non per strato
(`:1104` per la CSA, `:1156` per la LID), ma la CSA copre **21 strati** e la LID **21**: sono
**42 invocazioni**, −2 `get_rows` ciascuna = **−84 nodi** su 10.507 (HC fusa) o 34.329 (HC
spenta). Alla calibrazione 0,0069 %/nodo: **+0,58%**, sotto la deriva del banco (2,4%).
L'audit 45 gli attribuiva anche «split 5→2 a bs=64»: **non l'ho potuto verificare staticamente**
— gli `state_read_idxs` sono ingressi `CUDA_Host`, i `kv_state` sono `CUDA0`/`CUDA0_Mapped`, e
quale dei due vinca l'assegnazione lo dice solo `GGML_SCHED_DEBUG=2`. Se i 3 split spariscono
davvero, a 0,94 ms l'uno sono **2,8 ms su 130,5** = **+2,2%**, e allora vale.

**Rischio di conflitto.** BASSO-MEDIO. Il corpo della funzione e' verbatim la forma pre-fix
(righe `:531-547`), ma la firma e la classe sono le nostre.

**Quale numero deve muoversi.** `graph splits (with bs=64)`, oggi **5**, dal log di
`sched_reserve`. Se non scende a 2, restano 84 nodi e non vale il rischio.

---

### 2.6 `2ed3c1abb` — PR #25370 — «KQ masks f16, no zero bias, no raw_k repeats»

**Cosa cambia, e cosa e' gia' nostro.** Il commit ha tre parti. Le prime due sono **inerte per
costruzione da noi** (confermo il verdetto dell'audit 45 §1.1, verificato di nuovo):
`dsv4_repeat_streams` (nostro `:213`) esce subito con `n_stream == 1`, e
`dsv4_build_kq_zero_bias` (nostro `:222`) ritorna `nullptr` a meno di
`kv_unified && flash_attn && kq_mask->ne[3] != 1`, che da noi non capita mai.
Resta viva la terza: le maschere `csa`/`hca` nascono **F16** quando FA e' accesa, e spariscono
i due `ggml_cast` per strato compresso (nostro `:784-789` e `:852-857`).

**Ma qui c'e' una cosa che l'audit 45 non aveva visto, e cambia il porto.** Il nostro
`llama-graph.cpp` ha **gia'** il parametro `cparams` in `dsv4_build_comp_inputs` e **gia'** il
ramo F16 in `dsv4_set_kq_mask` — ma **al contrario di upstream**. Noi (`:864-868`):

```
// La maschera lid nasce f16 SOLO con l'op indexer fusa accesa (l'op la esige f16);
// csa/hca restano f32 come sempre.
const bool lid_f16 = strcmp(name, "lid") == 0 && cparams.fused_lid;
```

upstream: `cparams.flash_attn && strcmp(name, "lid") != 0`. **Sono complementari**: noi f16
sulla LID e f32 su csa/hca, upstream f16 su csa/hca e f32 sulla LID. Portarlo alla lettera
**spegne la nostra op indexer fusa** (che esige la maschera f16). La forma giusta e' l'unione:
`(strcmp(name,"lid")==0 ? cparams.fused_lid : cparams.flash_attn)`.

**Quanto vale.** ~80 nodi (audit 45), cioe' **+0,55%** — sotto la deriva. Al prefill lungo
l'audit 45 stimava ~1,7 GiB/ubatch di traffico di cast; con la nostra aritmetica a ctx 10.240 e
ub 64 la maschera CSA e' 2.560 × 64 × 4 B = 640 KiB per grafo, cioe' **niente**. La stima
dell'audit 45 vale a 105k × ub 512, non nel regime di oggi.

**Rischio di conflitto.** **ALTO**, ed e' il commit piu' insidioso del lotto, perche' *sembra*
un pick pulito e invece incrocia `LLAMA_DSV4_INDEXER_FUSO`. Se lo si prende, il cancello
obbligatorio e' **SHA a leve spente**.

**Quale numero deve muoversi.** `graph nodes (with bs=1)`, e `LLAMA_DSV4_INDEXER_FUSO=1` deve
continuare a produrre lo stesso SHA di prima. Se il secondo cancello non passa, il porto e'
sbagliato.

---

### 2.7 `67b9b0e7f` — PR #25945 — «llama-arch: fix DeepSeek4 APE tensor op»

**Cosa cambia.** Due righe in `LLM_TENSOR_INFOS`: `ATTN_COMPRESSOR_APE` e
`INDEXER_COMPRESSOR_APE` passano da `GGML_OP_ADD` a `GGML_OP_GET_ROWS`. Verificato: da noi sono
ancora `GGML_OP_ADD`.

**Perche' dovrebbe pagare.** L'op dichiarata in `LLM_TENSOR_INFOS` e' quella con cui
`llama-model.cpp` interroga `ggml_backend_dev_supports_op` per scegliere il buffer del peso.
Dichiarare `ADD` per un tensore che viene consumato da `GET_ROWS` fa scegliere il buffer sulla
domanda sbagliata — e **il fatto e' verificabile nel nostro sorgente**: i tre APE sono
consumati da `ggml_get_rows` a `deepseek4.cpp:1078` (HCA), `:1093` (CSA) e `:1145` (LID),
mai da un `ggml_add` diretto. La dichiarazione e' semplicemente falsa anche da noi.
Upstream misura **tg 23,14 → 24,63** (+6,4%) — ma su offload **multi-device**, che non e' il
nostro caso (`ds4-single-device-no-multigpu`). Da noi tutto finisce comunque su CUDA0 o
CUDA0_Mapped: **atteso ~0**. [DEDOTTO]

**Rischio di conflitto.** **ZERO** — `llama-arch.cpp` non l'abbiamo toccato in quella mappa.

**Quale numero deve muoversi.** Il buffer dei tensori APE nel log di `load_tensors`. Se non
cambia buffer, il commit e' corretto e inerte, e va preso lo stesso come igiene: costa 2 righe.

---

### 2.8 `298219f98` — PR #26051 — «llama: various bug fixes»

Sette fix OOB. I due che ci toccano: `llama-kv-cache.cpp` mette `state_read_data` in
`try/catch` (uno stato corrotto oggi propaga l'eccezione fino al server invece di far fallire
il restore), e `llama-model.cpp`/`llama-quant.cpp` aggiungono
`GGML_ASSERT(n_layer > 0 && n_layer <= LLAMA_MAX_LAYERS)`. Gli altri sono grammar/vocab/sampler.
**Zero perf, rischio nullo, PULITO** dove non abbiamo riscritto. Confermo il verdetto degli
audit precedenti. Il `try/catch` ha valore reale per noi perche' facciamo **rollback parziale**
e prompt cache: e' l'unico punto in cui uno stato mezzo scritto puo' arrivare.

---

### 2.9 `563dec81c` — PR #26474 — l'IDEA per il nostro `llama-kv-cache-dsv4.cpp`

Il mandato chiedeva di valutarla, non di portarla. **Verificato: e' gia' applicata da noi, e
comunque non ci sarebbe premio.**

L'idea upstream: la cache dell'indexer si allocava su *tutti* gli strati, ora solo su quelli
`is_indexer_full()`. Da noi `kv_lid` e' gia' costruito con `filter_csa`
(`llama-kv-cache-dsv4.cpp:1273`), cioe' **solo i 21 strati con `dsv4_compress_ratios[il] ==
DSV4_CSA_RATIO`**, e il log lo conferma: `lightning-indexer KV cache … 21 layers`, non 43.
Il filtro e' gia' stretto quanto puo' essere: la LID serve dove c'e' la CSA, e la CSA sta su 21
strati.

E il premio ipotetico: quella cache pesa **13,12 MiB in host mappato + 2,62 MiB di anello caldo
in VRAM**. Anche azzerandola del tutto, **2,62 MiB = 0,39 slot**. `is_indexer_full` non esiste
da noi (grep: zero) e per DSV4 non ha un analogo: non c'e' una nozione di strato indexer
«parziale». **Fronte chiuso con un numero.**

---

### 2.10 I due `dflash.cpp`, per completezza

`571d0d540` (#25823, «rotate injected K/V for DFlash»): tocca **solo `graph<false>`**, il
backbone Qwen3. Il nostro drafter e' DSpark su backbone DSV4 → `graph_dsv4`
(`hyper_connection.count = 4`, `target_layers = [41,42,43]` nel dump del draft). **Non tocca il
nostro cammino.** Confermo il «dormiente per costruzione» dell'audit precedente, con la ragione
piu' precisa: non e' dormiente perche' manca #26180, e' dormiente perche' e' un'altra funzione.

`cc078b45b` (#26905, dflash per nemotron-3.5): aggiunge gli `_s` (scale NVFP4) ai
`build_lora_mm`, e **due delle sue righe cadono dentro `graph_dsv4`** (`output_s` a `:659`).
Sono no-op con scale nulle, e i campi `output_s`/`ffn_*_s` esistono gia' da noi (grep: 5
occorrenze in `llama-model.h`). **Neutro, nessun motivo di portarlo, nessun motivo di temerlo
al prossimo rebase.**

---

## 3. La classifica

| # | commit | PR | costo | rischio | atteso | cancello |
|---|---|---|---|---|---|---|
| **1** | `4937ca83f` | #25787 | 3 righe | **zero** | **la requant DSV4 non muore** | `--dry-run` arriva in fondo |
| **2** | `56d6e9dde` | #25716 | 2 righe | **zero** | `--pure`+`--tensor-type` funziona; sblocca il precheck imatrix | `--dry-run` stampa i tipi dei pattern |
| **3** | `dee2a846b` (src) | #25832 | ~10 righe in 2 file, a mano | MEDIO (rename `l_out`) | join < 73,4%, split in calo | `GGML_SCHED_PROFILO=1` |
| **4** | `67b9b0e7f` | #25945 | 2 righe | **zero** | ~0 da noi (single-device) | buffer APE in `load_tensors` |
| **5** | `298219f98` | #26051 | ~25 righe sparse | **zero** | 0 perf, robustezza del restore | compila |
| **6** | `33a75f41c` | #25702 | ~15 righe, a mano | BASSO-MEDIO | −84 nodi (+0,58%); **+2,2% se i 3 split spariscono** | `graph splits (bs=64)` 5 → 2 |
| **7** | `69e62fc77` | #25871 | ~16 righe | BASSO | 0 t/s, guard-rail | rifiuto di `-ctk q8_0` senza `-ctv` |
| **8** | `2ed3c1abb` | #25370 | ~60 righe, **da riconciliare** | **ALTO** | ~80 nodi (+0,55%) | SHA a leve spente **e** `INDEXER_FUSO=1` invariato |

**I primi due si fanno subito e non toccano il banco**: `llama-quant.cpp` non e' nel binario del
server. **Il terzo e' l'unico che puo' spostare il decode.** Dal quarto in giu' si e' sotto la
deriva del banco (2,4%) e ogni verdetto costa piu' del guadagno che misura.

---

## 4. I NON portare, con la ragione

**`llama-quant.cpp:885` — la firma del loader.** Nel diff di `llama-quant.cpp` c'e' un quinto
hunk che cambia `use_mmap` in `llama_load_mode` e aggiunge `load_mtp`. **Non si porta**:
trascina `e6dd0e29a` (#20834, refactor load-mode, 33 file) e `82dbc4f01` (#26296, `load_mtp`).
I due hunk buoni (§2.2, §2.3) sono a distanza zero e indipendenti da questo.

**`596a5795b` (#25784, DSV4 MTP + DSpark).** Confermato: 1.532 righe sui quattro file che
abbiamo riscritto. Gia' preso il pezzo che valeva (`c91bb3678`, una riga).

**`1269cb1ff` / `1c3c9674d` / `3db4ff877` — la trappola dflash. VERIFICATO, la mina e' reale.**
`TENSOR_ALLOW_RESHAPE`: **zero occorrenze** in `src/`. Il nostro `wo_a` e' creato 2D a
`deepseek4.cpp:121` (`{n_head*n_embd_head/o_groups, o_lora_rank*o_groups}`) e reshapeato **nel
grafo** a `:1016` (`ggml_mul_mat(ctx0, ggml_reshape_3d(ctx0, wo_a, …), out)`). Non abbiamo il
bug perche' non abbiamo il refactor. Portarli significa: (1) importare `TENSOR_ALLOW_RESHAPE`,
(2) spostare il reshape dal grafo al load, (3) rompere gli stride su IQ2_XXS, (4) portare la
toppa. Su un tensore che passa da `build_mla_o`, che abbiamo modificato. **Il tuo giudizio
regge, e il guadagno era −43 nodi = 0,03%.**

**`563dec81c` (#26474).** Confermato inerte e non compilabile (`is_indexer_full`: zero
occorrenze). L'idea: chiusa in §2.9, con 2,62 MiB.

**`0ef6e55ed` (template) e `a6aa6f545` (sampler).** Confermato: cambiano *cosa* si genera.

**`a09d8abf8` (#26180, «Support rotated kv cache quant»).** Sembra la risposta a Q3 dal titolo.
**Non lo e'**: 14 righe in `src/models/minimax-m3.cpp` e basta. Zero righe DSV4.

**`da5b44862` (#25729, «set output of view src»).** Titolo ggml, contenuto `llama-sampler.cpp`:
appiattisce i logits nei sampler **di backend**. Non usiamo i sampler di backend (famiglia
#25532 gia' bocciata). Inerte.

**`432d7ffe2` (#25676).** Sincronizza prima di `embd_seq.clear()`. `embd_seq` e' vuoto da noi
(niente embedding/pooling): il ramo non entra mai. Aggiunge pero' una `synchronize()` nel
distruttore, corretta. Inerte, prendibile col lotto igiene.

**`153d324bc` (#26081) e `e6dd0e29a` (#20834), `ad256ded3` (#26135).** Famiglia load-mode: su
3060 discreta `auto` risolve a mmap, comportamento identico. 33 file per zero.

**`13f2b28b0` (#25521) e `7f575c39d` (#25588) — e qui correggo l'audit precedente.**
Gli audit dicevano «non ci ha morso, il nostro `clear_compressed(true)` e' piu' duro».
Rileggendo il diff: **#25588 implementa il rollback parziale del KV compresso**
(`seq_rm(seq_id, p0, -1)` sui tre `kv_csa`/`kv_hca`/`kv_lid` con `p0/ratio`) invece di
ritornare `false` — cioe' **la stessa cosa che abbiamo costruito noi in `6e0da6d31`**, e
#25521 toglie il `clear_compressed` da `seq_cp`, `seq_add`, `seq_div`, dove noi lo teniamo
(`llama-kv-cache-dsv4.cpp:1676`, `:1688`, `:1694`). **Non si portano** — abbiamo una
implementazione nostra, misurata («i 79 forward rigiocati vanno a zero»), su un file che
diverge di 1.200 righe. Ma **la riga da guardare e' `seq_cp` a `:1676`**: se il server fa
`seq_cp` nel riuso del prompt cache, quel `clear_compressed(true)` azzera **tutti** i buffer
compressi e forza un re-prefill. Upstream l'ha tolto. **Non e' un porto: e' una domanda da
farsi sul nostro codice, e si risponde con un contatore su `seq_cp`.**

**`91d2fc387` (#25325).** Declassata gia' dall'audit 45 (i nostri anelli sono a capienza per
costruzione, «solo usate» ≈ tutte). Confermo dal codice: il nostro
`dsv4_state_write_k_cache` (`:527`) non ha il parametro `n_rows`. Resta ε.

**Le altre 44** (architetture nuove, vocab, grammar, mtmd, TP, MTP di altri modelli,
model-saver, mmproj): non le carichiamo.

---

## 5. Due cose che il mandato non chiedeva ma cambiano il conto

### 5.1 Quattro dei commit «da portare» sono gia' in casa — e uno e' proprio il piu' grosso

`0dc74e332` (#25585, fusione HC) **e' gia' nostro**: `llama-context.cpp:298` porta il commento
«LEVA (porto #25585)», i tre `llm_fused_op_dsv4_hc_*_probe` ci sono, `cparams.fused_dsv4_hc_*`
ci sono, `ggml_dsv4_hc_pre/comb/post` sono chiamati in `deepseek4.cpp:274,372,401`.
Idem `00f5442cc` (#24231, lightning indexer) via `0441857cb`.
Quindi: **la risposta a Q1 e' che l'80% del lavoro di upstream su questo grafo l'abbiamo gia'
fatto**, e il resto vale l'1%.

Una nota di igiene che ho trovato leggendo: **`LLAMA_DSV4_HC_FUSO` ha default 0 nel sorgente**
(`llama-context.cpp:307`, `atoi(fuso)` con `fuso == nullptr` → 0). Il +16,5% e i 10.507 nodi
esistono solo con la variabile d'ambiente. Se «i default diventano i valori vinti»
(`edf00a030`) doveva coprire anche questa, non l'ha coperta. Il log che ho letto
(`bussate_base100.server.log`) infatti dice **34.329 nodi**, cioe' HC **spenta**.

### 5.2 Il conto della VRAM, che vale piu' di qualunque porto di questo fronte

Dal log, in ordine di comparsa: modello **7.383,67 MiB** (CUDA0) + 74.304 MiB mappati in host +
1.010 MiB CUDA_Host; KV in VRAM **40,51 MiB**; compute buffer **114,05 MiB**; liberi dopo il
contesto **3.709 MiB**; poi la cache esperti si prende `448 slot da 6,75 MiB = 3.026 MiB`.
Totale VRAM impegnata ≈ **11,6 GiB su 12,287**.

**La KV e' lo 0,35% di quella VRAM.** Tutte le leve «meno KV = piu' slot» — q8_0, indexer
parziale, anello piu' aggressivo — pescano in un secchio che, **svuotato del tutto**, contiene
**6 slot su 448**. Il secchio dove ci sono gli slot e' il modello denso (7.383,67 MiB) e il
compute buffer, non la KV.

---

## 6. In tre righe

1. **Q1 e' gia' vinta**: le due fusioni DSV4 di upstream sono in casa; quel che resta vale l'1%
   e sta sotto la deriva. L'unica leva vera del fronte e' `dee2a846b`, che non e' una fusione
   ma un **piazzamento al confine** — e il confine e' il nostro costo piu' caro.
2. **Q2 e' un risultato negativo, e con la prova in casa**: il prefill e' il 90% trasporto
   esperti su PCIe; upstream in `src/` non ha nulla che lo tocchi.
3. **Q3 e' aritmeticamente chiusa**: la KV in VRAM e' 40,51 MiB, un porto perfetto ne toglie
   13,5, cioe' **2 slot su 448**. **Q4 e' l'unico posto dove upstream ci da' qualcosa di
   gratis**: 5 righe, rischio zero, e senza una di esse la requant di DSV4 non parte.
