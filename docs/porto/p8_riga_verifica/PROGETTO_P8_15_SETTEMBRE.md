# P8 · progetto — abbassare la riga di verifica MTP con leve *lossless* — 15 settembre 2026

Cella di **sola progettazione**. Nessuna build, nessun server, nessun uso della GPU (un'altra misura
sta girando sulla macchina). Nessun file del motore modificato: le patch sono **non applicate**, in
`docs/porto/p8_riga_verifica/p8_A.patch`, `p8_B.patch`, `p8_C.patch`, e sono diff contro
`D:\ds4_work\p0_snapshot_20260914\source` (base pulita).

Alberi letti in sola lettura: `C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source`
(codice in esercizio) e `D:\ds4_work\p0_snapshot_20260914\source` (base delle patch). **I cinque file
toccati o citati sono byte-identici fra i due alberi** (`src/models/qwen4exp.cpp`,
`ggml/src/ggml-backend.cpp`, `ggml/src/ggml-cuda/getrows.cu`, `ggml/src/ggml-cuda/getrows.cuh`,
`ggml/src/ggml-cuda/mmvq.cu`): verificato con `cmp`. **Nessuna leva di questo progetto richiede le
patch P3–P7**; e nessuna tocca i file che quelle patch modificano (`moe-demand.cuh`,
`fork-moe-kernels.cuh`, `llama-moecpu.*`, `moe_cpu_executor.*`, `llama-context.cpp`,
`llama-graph.cpp`), quindi A/B/C si impilano su P4/P5 senza conflitto testuale.

---

## 0. Verdetto in sette righe

1. **I 3 lanci di grafo a 2 righe non sono un problema di grafi CUDA: sono un tetto di contabilità
   dello scheduler.** `GGML_SCHED_MAX_SPLIT_INPUTS = 30` (`ggml/src/ggml-backend.cpp:768`) e il
   controllo `if (split->n_inputs >= split->inputs_capacity) need_new_split = true`
   (`ggml-backend.cpp:1341-1348`) aprono uno **split nuovo sullo stesso backend** ogni 30 ingressi.
   A 1 riga il grafo di decode ha ~20 ingressi → 1 split CUDA → **1 lancio**. A 2 righe ne ha ~63 →
   **3 lanci**. A 3 righe ~87 → ancora 3, ed è esattamente il `graph splits = 4 (with bs=3), 2 (with
   bs=1)` del log (3 CUDA + 1 non-CUDA).
2. **Gli ingressi in più sono quasi tutti *viste* del bias QSA**, e questo spiega anche la voce H2D.
   `qsa->bias` è un ingresso di grafo in **buffer host** (`qwen4exp.cpp:854-859`,
   `llama-memory-hybrid-idx.cpp:407,421`). Ogni tensore che lo legge è un *input di split* e lo
   scheduler **ne copia l'intera estensione, anche se è la vista di una sola riga**: `ggml_nbytes` di
   `view(bias, n_kv, 1, …)` vale `n_kv*4` = **822.272 B** a 205k.
3. **Il conto torna al copiatore**: a 1 riga 12 viste `b1` (una per strato QSA, `qwen4exp.cpp:1123`)
   + 1 `bias` intero + 1 `cell_blk` = **14 copie da 822.272 B** (nsys: 14, 11,3 MiB). A 2 righe 24
   viste `bias_row` (`:985`) + 24 viste `b1` + 1 `cell_blk` = **49** (nsys: 49, 38,7 MiB). Non è
   «il bias ricaricato per riga»: è **ricaricato per riga e per strato**, 24 volte più del necessario.
4. **Ogni split costa oltre al lancio**: `ggml_backend_sched_compute_splits` fa
   `ggml_backend_synchronize(split_backend)` **prima** di copiare gli ingressi
   (`ggml-backend.cpp:1950-1956` e `:1951` per gli ingressi utente) e la copia è **bloccante**
   (`ggml_backend_tensor_copy`). Tre split = tre svuotamenti della coda GPU intervallati da decine di
   copie sincrone: è l'origine dei **+2,17 ms di GPU inattiva**, non una tassa di cattura.
5. **`k_get_rows` a 3,7 GiB/s non è un problema di byte ma di geometria del lancio**:
   `get_rows_cuda_q` (`getrows.cu:189-191`) lancia sempre blocchi da 256 thread con 2 valori per
   thread; una cella KV `q8_0` è lunga **128 valori (136 B)**, quindi **64 thread su 256 lavorano** e
   si spende un blocco intero per riga raccolta. Restringere il blocco alla riga è bit-identico.
6. **I 6,60 ms di mmvq sono il prezzo della bit-identità, e il codice che lo paga non è quello che
   credevamo**: con esperti IQ3_XXS il ramo `QWEN_MOE_SCALAR_BATCH=2` **non si applica** (copre solo
   IQ2_S/IQ3_S/IQ4_NL, `mmvq.cu:1124`); a 2-3 righe gira `mul_mat_vec_q_moe` (`mmvq.cu:785-790`),
   *un warp per token*, che non condivide **nulla** fra i token: le 20 rotte per strato sono
   dequantizzate 20 volte anche se gli esperti distinti sono **16,47**.
7. **Ordine proposto: A → B → C → D1 → (D2) → E.** A e B hanno la stessa radice e insieme valgono
   **−1,6…−2,3 ms a 205k** e **−0,7…−1,4 ms al banco**; C **−0,4…−1,1 ms**; D1+concat **−0,2 ms**;
   E **−1,2…−2,0 ms** ma è la sola leva difficile. Cancello: `R` sotto **11 ms** prima di rimettere
   in discussione la bozza a 2 token.

---

## 1. Il fatto nuovo che governa A e B

### 1.1 Come nasce uno split, e perché due split possono avere lo stesso backend

`ggml_backend_sched_split_graph`, passo 5 (`ggml/src/ggml-backend.cpp:1297-1400`):

```c
            bool need_new_split = false;
            if (node_backend_id == cur_backend_id && split->n_inputs > 0) {
                for (int j = 0; j < GGML_MAX_SRC; j++) {
                    ...
                    // check if the split has too many inputs
                    // FIXME: count the number of inputs instead of only checking when full
                    if (split->n_inputs >= split->inputs_capacity) {
                        ... need_new_split = true; break;
                    }
                }
            }
            if (node_backend_id != cur_backend_id || need_new_split) { /* nuovo split */ }
```

`inputs_capacity` parte da `GGML_SCHED_MAX_SPLIT_INPUTS = 30` (`:768`, `:849`). Quindi **ogni 30
ingressi il grafo viene tagliato anche se il backend non cambia**. Un `ggml_backend_graph_compute_async`
per split, e il backend CUDA fa **un `cudaGraphLaunch` per chiamata**
(`ggml-cuda.cu:4663-4676`, `ggml_cuda_graph_evaluate_and_capture`): *split CUDA = lancio di grafo*.

Questo chiude la domanda A: non è uno `ggml_cpy` verso l'host, non sono nodi non catturabili, non è
un puntatore instabile. È il tetto degli ingressi.

### 1.2 Perché gli ingressi sono ~63 a due righe

Un *input di split* è un `src` che vive su un altro backend. Le **viste** contano una per una: il
loro `backend_id` è ereditato dal `view_src` (`ggml-backend.cpp:1269-1271`), e la copia che lo
scheduler crea è grande `ggml_nbytes(view)`. Per `b1 = ggml_view_4d(bias, 1, n_kv, 1, ns, …)`
(`qwen4exp.cpp:1123-1124`) `ggml_nbytes` = `n_kv*4`.

| | 1 riga | 2 righe | 3 righe |
|---|---:|---:|---:|
| `bias_row` = `view_2d(inp->bias, …)` in `build_qsa_top_k:985` (ramo per-token, attivo solo se `n_tps>1`) | 0 | 12×2 = **24** | 36 |
| `b1` = `view_4d(bias, …)` in `gather_query`, `build_attn_qsa:1123` | 12 | **24** | 36 |
| `inp->bias` intero (`:1005`, solo nel ramo non per-token) | 1 | 0 | 0 |
| `inp->cell_blk` intero (`:997` o `:983`) | 1 | 1 | 1 |
| **copie da 822.272 B previste** | **14** | **49** | **73** |
| **copie da 822.272 B misurate (nsys, §3.2 di P7c3)** | **14** | **49** | n.d. |
| MiB per forward previsti / misurati | 11,0 / 11,3 | 38,4 / 38,7 | 57,2 / — |

Le due colonne misurate combaciano riga per riga: **il modello del meccanismo è verificato sui dati
già raccolti**, senza una nuova corsa. Da qui discende anche che gli strati QSA con lo stesso
`dsv4_compress_ratios` condividono un solo `llm_graph_input_qsa` (`qwen4exp.cpp:844-877`) e che di
rapporti distinti ce n'è **uno solo**: con due, a 1 riga le copie sarebbero 16, non 14.

Aggiungendo ~14 ingressi minori (token, posizioni, `k_idxs`, `v_idxs`, `blk_pos`, `pool_*`,
`out_ids`, ids dei MoE…): **~20 a 1 riga (1 split), ~63 a 2 righe (3 split), ~87 a 3 righe (3
split)**. Coerente con il log (`c4_p7c4_s0_spento_r1_moecpu.txt:11`) e con i 3 rapporti per forward
di `LLAMA_MOE_HIT_REPORT` (T23).

### 1.3 Che cosa costa davvero uno split in più

`ggml_backend_sched_compute_splits` (`ggml-backend.cpp:1787-1960`), per ogni split, **prima** di
accodare i kernel:

```c
            if (input->flags & GGML_TENSOR_FLAG_INPUT) {
                ggml_backend_synchronize(split_backend);     // svuota la coda della GPU
                ggml_backend_tensor_copy(input, input_cpy);  // copia BLOCCANTE
            } else {
                ... ggml_backend_synchronize(split_backend);
                ... ggml_backend_tensor_copy(input, input_cpy);   // via generica, :1938-1947
            }
```

Quindi: **svuotamento della coda + N copie sincrone + lancio**, tre volte invece di una. La GPU resta
ferma mentre l'host emette le copie. I +2,17 ms di inattiva sono questo, e **non scalano con la
profondità del contesto**: il numero di copie (49) non dipende da `n_kv`, solo la loro dimensione.
È il motivo per cui la leva A vale **anche al banco a 32k**, dove la leva B vale poco.

---

## 2. Le cinque leve

### A — tornare a un lancio di grafo

| | |
|---|---|
| **meccanismo attuale** | `GGML_SCHED_MAX_SPLIT_INPUTS 30` (`ggml/src/ggml-backend.cpp:768`), usato come capacità iniziale in `ggml_backend_sched_split_inputs_grow` (`:849`) e confrontato in `ggml-backend.cpp:1341-1348`. 63 ingressi ⇒ 3 split CUDA ⇒ 3 `cudaGraphLaunch` + 3 `ggml_backend_synchronize` + gli ingressi ricopiati split per split |
| **modifica proposta** | `p8_A.patch`: capacità iniziale letta da `GGML_SCHED_SPLIT_INPUTS` (default invariato 30), così **si confrontano le due configurazioni con lo stesso binario**. Al banco: `GGML_SCHED_SPLIT_INPUTS=96`. `nodes_size` e `context_buffer_size` (`:2042`, `:2051`) restano sul macro di compilazione: sono già sovradimensionati (`ggml_sched_max_splits = graph_size`, migliaia), e il totale reale degli ingressi è ~63 |
| **ms attesi** | **−0,5…−1,2 ms** sulla riga (parte dei +2,17 di GPU inattiva: 2 svuotamenti e ~35 copie bloccanti emesse in meno), **indipendenti dalla profondità**. Incertezza alta: è il termine meno modellato dei sei |
| **lossless** | **sì, per costruzione**: cambia solo dove il grafo viene tagliato. Nessun kernel, nessun ordine di riduzione, nessun byte diverso. È l'unica leva del progetto su cui l'identità non richiede un argomento |
| **rischio cattura/replay** | basso. Meno split = meno grafi CUDA distinti da catturare; la chiave di cattura è `cgraph->nodes[0]` (`ggml-cuda.cu:2820`) e con un solo split la chiave è più stabile, non meno. Il conteggio `graphs reused` deve **salire**, non scendere |
| **come si prova** | `GGML_SCHED_DEBUG=2` (`ggml-backend.cpp:2022`, il server gira già con `-lv 4`) stampa la tabella degli split e l'assegnazione dei nodi: conferma in dieci minuti quanti ingressi ha ogni split e dove cade il taglio. Poi profilo `fumo` con bozza 1: il rapporto `LLAMA_MOE_HIT_REPORT=1` deve passare da **3 a 1 per forward**, e `H2D` da 38,7 a ~16,5 MiB (le copie ridondanti fra split spariscono anche senza B) |
| **difficoltà** | **bassa** (una funzione, una riga) |

> Nota sul perché A da sola toglie anche byte: un ingresso usato da due split è copiato **due volte**
> (`ggml-backend.cpp:1821-1947` gira su `split->n_inputs` di *ogni* split). I 49 conteggiati da nsys
> sono già il totale gonfiato dai tre split; con un solo split restano le 48+1 viste distinte ma
> emesse una volta sola.

### B — il bias QSA residente sul dispositivo

| | |
|---|---|
| **meccanismo attuale** | `qsa->bias = ggml_new_tensor_3d(F32, n_kv, n_tps, n_stream)` + `ggml_set_input` (`qwen4exp.cpp:854-859`). Lo riempie l'**host**, direttamente su `bias->data` (`llama-memory-hybrid-idx.cpp:421` e `:443-459`; l'assert `ggml_backend_buffer_is_host` a `:407` dice dove vive). Nel ramo gather se ne prendono **due viste per token e per strato** (`qwen4exp.cpp:985` e `:1123`), e ognuna è un input di split copiato per intero: 49 copie da 822.272 B per forward a 205k |
| **contenuto del bias** | tre intervalli per token nel percorso veloce (`llama-memory-hybrid-idx.cpp:454-458`): `0` fino a `query_tail`, `1e9` sulla coda incompleta, `-INFINITY` oltre `query_used`. È la visibilità per cella, nient'altro |
| **modifica proposta (B1, in patch)** | `p8_B.patch`: **una** copia sul backend di calcolo, `qsa->bias_dev = ggml_cont(ctx0, qsa->bias)`, creata una sola volta per insieme di ingressi e solo nel ramo `gather && !blk_bias && n_tps <= 3`; tutte le viste si prendono su `bias_dev`. Ingressi grandi: 49 → **2** (il bias intero e `cell_blk`) |
| **modifica futura (B2, non in patch)** | generare il bias **sul dispositivo** da `(pos, r, n_kv)` con un kernel di riempimento a tre intervalli. Toglie anche l'ultima copia e gli `std::fill` host (O(n_kv) per token, ~0,1 ms a 205k, sul percorso critico prima del grafo). Da tenere per la fase lunga: a 262k vale altri ~0,4 ms |
| **ms attesi (B1)** | H2D per forward a **205k**: 38,4 → 2,35 MiB a 2 righe e 11,0 → 1,57 a 1 riga ⇒ sulla **riga** `+1,14 → +0,03 ms`, cioè **−1,11 ms**; in più **−0,39 ms su `T1`** (regalo al ciclo intero). A **32k**: **−0,18 ms** sulla riga. Incertezza ±15% (banda DMA 23,6 GiB/s misurata) |
| **effetto collaterale** | gli ingressi scendono a ~15 ⇒ **il grafo torna a 1 split da solo**: B rende A ridondante. Restano separate perché A è una riga e si prova per prima, e perché A protegge anche il prefill |
| **lossless** | **sì**. `GGML_OP_CONT` su F32 è una copia esatta; i consumatori vedono gli stessi valori agli stessi offset (`bias_dev` è contiguo, `nb[1] = n_kv*4` come l'originale). Nessun kernel numerico cambia |
| **rischio cattura/replay** | **basso ma da guardare**. (a) Il nodo `CONT` deve finire su CUDA: se lo scheduler lo assegnasse alla CPU la copia resterebbe una sola e il guadagno pure — nessun caso peggiore. (b) Un nodo in più cambia `n_nodes` ⇒ **una ricattura** al primo forward della nuova forma (tassa nota, `tassa-ricattura-grafo`), poi `graphs reused` deve tornare ai valori di M1. (c) Il puntatore sorgente è la copia allocata da `ggml-alloc` nel buffer di calcolo, **stabile fra i replay** come oggi (regola `ingressi-di-grafo-solo-puntatori-stabili`): non si introducono puntatori nuovi. (d) **Memoria**: `bias_dev` costa `n_kv*n_tps*4` = 1,6 MiB a 205k / 2,4 a 3 righe. La guardia `!blk_bias` è essenziale: nel ramo di prefill il bias è `n_blocks × n_tokens` e una seconda copia sarebbe grande. (e) 1,6 MiB in più nel buffer di calcolo possono far fallire il primo `ggml_gallocr_alloc_graph` e provocare **una** ri-riserva (`ggml-backend.cpp:1621-1633`): è una tassa una tantum, ma va vista nel log (`failed to allocate graph, reserving`) e non deve ripetersi a ogni forward |
| **come si prova** | profilo `fumo` con bozza 1: istogramma H2D di nsys — le copie da `n_kv*4` devono passare da 49 a **1**; `R` prima/dopo sullo stesso checkpoint; **impronte identiche a M1 su `ctx32k` (8 su 8)** |
| **difficoltà** | **bassa/media** (5 punti di modifica in un file, tutti locali) |

### C — il gather QSA delle celle KV

| | |
|---|---|
| **meccanismo attuale** | `k_g`/`v_g` = `ggml_get_rows(k_cells, gather_idx)` (`qwen4exp.cpp:1105,1109`), una coppia per token e per strato QSA. Con `-ctk q8_0 -ctv q8_0` (preset M1) la riga di una cella è `hd_k*n_h_kv = 128` valori = **136 B**, quindi gira il template quantizzato `k_get_rows` e il lanciatore `get_rows_cuda_q` (`getrows.cu:186-215`): `block_dims = 256`, **2 valori per thread**, `block_num_y = 1`. Su 256 thread ne lavorano **64**; si spende un blocco per riga raccolta, e i thread inerti occupano gli slot che limitano quanti blocchi stanno su un SM. Risultato misurato: 6,5 MiB in 1,73 ms = **3,7 GiB/s, il 16% del bus** |
| **conteggio che lo conferma** | `k_get_rows` passa da 36 a 60 lanci (+2 per strato QSA per riga in più: `k_g` e `v_g`), 12 strati QSA (= i 12 `flash_attn_ext_f16` del profilo). `k_get_rows_scalar` 24→48 sono `expanded`/`m_g` (righe da 1 valore, già trattate a parte da `GGML_CUDA_SCALAR_GATHER`) |
| **modifica proposta** | `p8_C.patch`: in `get_rows_cuda_q` scegliere il blocco in funzione di `ne00` (`block_size` dimezzato finché `block_size >= ne00`, pavimento `WARP_SIZE`). Per `ne00 = 128` → **64 thread, tutti attivi**; per righe lunghe il comportamento non cambia. Dietro `GGML_CUDA_GETROWS_NARROW` (default acceso) per l'A/B con un solo binario. È lo stesso schema già presente nel file per il caso `ne00 == 1` (`getrows.cu:284`) e per il percorso vettoriale (`:298-311`): **stile della casa, non invenzione** |
| **ms attesi** | il kernel è limitato dalla parallelismo di memoria in volo, non dalla banda: 4× thread-slot liberati ⇒ 1,5…2,5× di banda effettiva. Sulla **riga** `1,73 → 0,7…1,15`, cioè **−0,6…−1,0 ms**; in più **−0,6…−0,9 ms su `T1`**. Incertezza **alta**: è l'unica leva il cui guadagno dipende da un'ipotesi di occupancy non misurata |
| **e la deduplicazione fra le righe (proposta §5.2 di P7c3)?** | **superata, e comunque non gratuita.** (i) La sovrapposizione fra le due top-2048 resta non misurata e non c'è traccia nei log `c3_*` per stimarla (le tracce disponibili sono `routes.bin`, rotte MoE, non selezioni QSA). (ii) Anche con sovrapposizione alta, l'unione va calcolata **a runtime** sul dispositivo (fusione di due liste da 2048 + scatter), e il costo del dedup si mangia una parte del risparmio. (iii) Soprattutto: FA per riga dovrebbe attendere su un insieme unito, quindi o si maschera (cambia il numero di tile e l'ordine di accumulazione della softmax ⇒ **non bit-identico**) o si ri-scatterizza per riga (e allora si sono spostati i byte, non tolti). **La leva vera è la geometria del lancio, che è bit-identica e vale di più** |
| **lossless** | **sì**. Ogni thread legge e scrive esattamente ciò che leggeva e scriveva: non c'è riduzione, non c'è ordine di somma. `GGML_ASSERT(ne00 % 2 == 0)` resta valido |
| **rischio cattura/replay** | **nullo sul replay** (la geometria è fissata alla cattura). Rischio di *regressione* su altre forme di `get_rows` quantizzato: la guardia `block_size >= ne00` lascia invariato tutto ciò che ha righe ≥ 256 valori, cioè le `get_rows` sui pesi |
| **come si prova** | profilo `fumo` bozza 1, confronto `k_get_rows` (ms e lanci) con e senza `GGML_CUDA_GETROWS_NARROW=0`; impronte identiche a M1 obbligatorie (devono esserlo **banalmente**: se cambiano, la patch ha un difetto di indicizzazione) |
| **difficoltà** | **bassa** |

### D — il radix sort (0,73) e il concat (0,24)

| | |
|---|---|
| **meccanismo attuale (sort)** | `ggml_top_k(expanded_row, width)` per token (`qwen4exp.cpp:987`) ⇒ `ggml_cuda_op_argsort` ⇒ `DeviceRadixSort::SortPairs(… , ncols, 0, sizeof(float)*8, …)` (`argsort.cu:88-146`): **4 passate onesweep su chiavi a 32 bit su tutte le n_kv celle**, più `init_indices` e una copia D2D della riga (822 KB). Due righe = due ordinamenti indipendenti |
| **cosa NON è lossless** | (a) ordinare i **blocchi** invece delle celle (r volte meno chiavi): i punteggi sono costanti per blocco e i pareggi sono ovunque (tutte le celle mascherate valgono `-inf`), quindi l'ordine di uscita fra chiavi uguali — che il radix stabile fissa a indice crescente — non è riproducibile da un algoritmo a blocchi senza una dimostrazione sui pareggi. Cambiato l'ordine, cambia l'ordine di raccolta di `k_g`/`v_g` e **cambia l'accumulazione della softmax in FA**. (b) chiavi a 16 bit: cambia la struttura dei pareggi, quindi la selezione. (c) top-k per selezione invece che per ordinamento: stesso problema |
| **D1 — togliere la trasposta per token (in progetto, non in patch)** | `expanded_row = get_rows(cont(transpose(row)), cell_blk)` (`qwen4exp.cpp:982-984`) genera `cpy_scalar_transpose` ×24 a 2 righe (**+0,144 ms**). Trasponendo **una volta sola** il punteggio `[n_blocks, n_tps]` e prendendo per token una vista `[1, n_blocks]` con passo `nb[1]`, le trasposte diventano una. **Lossless** (solo movimento dati). Atteso **−0,12…−0,14 ms** |
| **D1-bis — la catena di `concat`** | `result = ggml_concat(result, current, 1)` per token in `build_attn_qsa:1157` (e `:988` per gli indici) costruisce il risultato a catena: `concat_cont` 49→109 lanci, **+0,096 ms**. Scrivere ogni token in una vista di un tensore preallocato (`ggml_cpy` su vista) toglie la catena. **Lossless**. Atteso **−0,05…−0,09 ms** |
| **D2 — un solo ordinamento segmentato (facoltativa, non in patch)** | costruire `expanded` per entrambi i token e fare **un** `ggml_top_k` su `[n_kv, n_tps]`: `argsort.cu` userebbe `DeviceSegmentedRadixSort` (ramo `is_capturing`, `:92`) invece di due `DeviceRadixSort`. Attesi **−0,2…−0,4 ms** (metà degli `init_indices`, delle copie D2D e degli avvii). **Non dimostrabilmente lossless**: entrambi sono radix stabili sulle stesse chiavi e *dovrebbero* dare lo stesso ordine, ma la garanzia è a carico di CUB. Va trattata come una leva a cancello di impronta: se una sola delle 8 impronte `ctx32k` cambia, si scarta senza discussione |
| **rischio cattura/replay** | nullo per D1 e D1-bis (meno nodi, non più). D2 riduce i nodi ma cambia il kernel scelto da CUB: da rimisurare `graphs reused` |
| **difficoltà** | **bassa** (D1, D1-bis), **media** (D2) |

### E — mmvq a 2-3 righe

| | |
|---|---|
| **meccanismo attuale** | Per i tensori della cache esperti `ggml_cuda_mul_mat_id` va **sempre** su MMVQ (`ggml-cuda.cu:2135-2142`, assert e ritorno immediato). Dentro `mul_mat_vec_q_switch_ncols_dst` (`mmvq.cu:1014-1155`): il ramo `QWEN_MOE_SCALAR_BATCH=2` che riproduce la geometria a token singolo è **ristretto a IQ2_S / IQ3_S / IQ4_NL** (`mmvq.cu:1124`); per **IQ3_XXS**, che è il quanto dominante degli esperti di UD-IQ3_XXS, si cade su `mul_mat_vec_q_moe_launch` (`:1155-1161`) |
| **com'è fatto `mul_mat_vec_q_moe`** (`mmvq.cu:785-800`) | griglia `(nrows_x/c_rows_per_block, nchannels_dst)`, blocco `(warp_size, ncols_dst)`: **un warp per token, ciascuno indipendente**, `channel_x = ids[channel_dst + token_idx*ids_stride]`. I due token condividono il blocco ma **non l'esperto**: a slot `j` il token 0 e il token 1 hanno esperti diversi, e quando per caso coincidono la matrice viene letta e dequantizzata **due volte** |
| **perché 6,60 ms e non 1,2** | mmvq **non è limitato dalla banda**: 480 esperti × 1,8923 MiB = 908 MiB per forward a 1 riga in ~6,6 ms della sua quota MoE = **137 GiB/s su 360 teorici**. È limitato dalla **dequantizzazione** (vec_dot IQ3_XXS) e il costo scala con le **rotte**, non con gli esperti distinti: 10 → 20 rotte per strato = **+100% della quota MoE**, cioè esattamente i +6,6 ms misurati. I «1,2 ms di byte in più» della domanda presuppongono un regime limitato dalla VRAM in cui il kernel non si trova |
| **modifica proposta** | condividere la lettura+dequantizzazione dell'esperto fra i token che lo usano: le 20 rotte per strato contengono **16,47 esperti distinti** (contatori del dispositivo, T22), cioè **3,53 doppioni per strato**. Il pianificatore `moe_grouped_plan_decode` calcola già `plan->n_unique`; serve esporre, per esperto unico, la maschera dei token che lo usano, e un kernel che tenga `tmp[c_rows][n_token_condivisi]` accumulando **con lo stesso ordine di K e la stessa riduzione di warp per colonna** |
| **ms attesi** | doppioni = 3,53/20 = **17,6%** delle rotte; se lettura+dequant è il 70-80% del costo del kernel: **−1,2…−2,0 ms** sulla riga. Incertezza alta (dipende dalla quota dequant/dot, non misurata separatamente) |
| **lossless** | **sì, ma solo se la geometria per colonna non cambia**: stessa `blocks_per_iter`, stessa partenza `threadIdx.x / (qi/vdr)`, stessa `warp_reduce_sum`. Se per condividere si cambia `c_rows_per_block` o il numero di warp, l'ordine di somma cambia e **il testo può cambiare**. Va scritto come «stesso kernel, due accumulatori», non come «kernel a due colonne» |
| **rischio cattura/replay** | medio: nuove istanze di template ⇒ ricattura; e il kernel dipende da dati del pianificatore, che devono restare puntatori stabili (regola `ingressi-di-grafo-solo-puntatori-stabili`) |
| **verifica preliminare da dieci minuti** | stampare i tipi dei tensori esperti del GGUF: se gli esperti sono in parte **IQ2_S**, per quella parte `QWEN_MOE_SCALAR_BATCH=2` è attivo e la geometria è già quella a token singolo; per la parte IQ3_XXS no. **Sospetto da verificare: la variabile del preset M1 potrebbe essere inerte su gran parte del MoE.** Se lo è, la bit-identità osservata (`mismatch = 0`) viene da `mul_mat_vec_q_moe` e non dal ramo «scalar», e questo va scritto nel registro perché cambia il significato della leva già catalogata il 10/9 |
| **difficoltà** | **alta** — ultima della fila |

---

## 3. Che cosa NON proporre (e perché)

- **Alzare `GGML_SCHED_MAX_SPLIT_INPUTS` a compilazione invece che a runtime**: toglie l'A/B con un
  binario solo (regola `batterie-a-caldo-non-bracci-freddi`) e triplica `context_buffer_size`.
- **Spegnere `QWEN_MOE_SCALAR_BATCH` / `QWEN4EXP_INDEXER_F32_BATCH`**: −1,85 ms/riga misurati il
  10/9, ma fuori dal cancello (cambia il testo). Restano fuori da P8 per definizione.
- **Prefetch durante la testa**: chiuso in P7c3 §4 per due ragioni indipendenti.
- **Dedup del gather QSA fra le righe**: vedi C, riquadro dedicato. Non è lossless a costo zero e il
  numero che la giustificherebbe non esiste.
- **Top-k a blocchi / chiavi corte**: vedi D, non lossless.
- **Toccare la cache esperti (ammissione, sfratto, corsia CPU)**: è P4/P5/P7, e cambia i byte
  trasferiti. P8 è per definizione la fila delle leve che **non** cambiano i byte del trasporto.

---

## 4. Ordine di esecuzione, una leva per cella

| cella | leva | ms attesi sulla riga (205k) | ms attesi al banco (≤32k) | difficoltà | perché in questa posizione |
|---|---|---:|---:|---|---|
| P8c1 | **A** — tetto degli ingressi di split | −0,5…−1,2 | −0,5…−1,2 | bassa | una riga, lossless per costruzione, A/B con lo stesso binario, e verifica immediata sul conteggio dei lanci |
| P8c2 | **B** — bias QSA residente | −1,11 | −0,18 | bassa/media | stessa radice di A; da sola riporta il grafo a un lancio; il grosso del guadagno è sul servizio lungo |
| P8c3 | **C** — geometria di `get_rows` quantizzato | −0,6…−1,0 | −0,6…−1,0 | bassa | indipendente dalle prime due, bit-identica per costruzione, regala altrettanto a `T1` |
| P8c4 | **D1 + D1-bis** — trasposta per token e catena di concat | −0,17…−0,23 | −0,17…−0,23 | bassa | pulizia del grafo, si fa nello stesso file di B |
| P8c5 | **D2** — ordinamento segmentato unico | −0,2…−0,4 | −0,2…−0,4 | media | **solo se le impronte reggono**; si scarta al primo disaccordo |
| P8c6 | **E** — condivisione dell'esperto fra i token in mmvq | −1,2…−2,0 | −1,2…−2,0 | alta | l'unica che richiede un kernel nuovo; si apre solo dopo che A-D hanno mostrato quanto resta |

**Cumulato atteso su `R = 15,66 ms`** (205k): A-D ⇒ **12,4…13,3 ms**; con D2 ⇒ 12,0…13,1; con E ⇒
**10,3…11,8 ms**. Al banco (dove B vale meno) A-D ⇒ ~13,0…13,9, con E ⇒ ~11,2…12,6.
La soglia operativa della cella («sotto ~11 ms» prima di rimettere in discussione la bozza a 2
token) **non si raggiunge senza E**, oppure si raggiunge componendo A-D con la corsia CPU di P4/P5
che attacca il termine gather (6,53 ms) che P8 non tocca per definizione.

---

## 5. Protocollo di misura (identico per ogni cella)

1. **Guardia**: `Get-Process llama-server,paired_probe,paired_probe_prof` = 0 e porta 8100 libera
   (`netstat`) prima di qualunque avvio. Macchina quieta: **nessuna misura entro 15 minuti da una
   build** (regola `dopo-una-build-la-macchina-non-e-quieta`).
2. **Cancello di correttezza, prima di ogni altra cosa**: profilo `fumo`, MTP con **bozza 1**, greedy,
   seed 1234 — le **impronte SHA256 devono essere identiche a M1 su `ctx32k`, 8 su 8**. L'impronta
   deve includere `reasoning_content` (regola `qwen38-il-banco-e-deterministico-il-testo-e-un-oracolo`),
   altrimenti si firma la stringa vuota. Una sola impronta diversa ⇒ la leva è morta, si chiude senza
   sweep e senza discussione.
3. **Misura della riga `R`**: `prova_verifica.py --tag … --width 2 --tokens 64` sul checkpoint a
   205.370 token, prima e dopo, **stesso processo** per le due fasi (misura relativa). Registrare
   `mismatch` (deve restare 0) e i tre numeri: 1 riga, 2 righe, differenza.
4. **Scomposizione**: la stessa corsa con `--profile` e `analizza_nsys.py`. Per A e B guardare
   esplicitamente: numero di rapporti `LLAMA_MOE_HIT_REPORT=1` **per forward** (3 → 1), istogramma
   delle copie H2D (49 → 1 per il blocco da `n_kv*4`), `GPU inattiva`.
5. **Poi, e solo poi**, `solo_libero` sul preset M1 (riferimento **B = 28,66 t/s**): si apre il
   confronto con la bozza a 2 token (`preset_M2_p7.json`) **solo quando `R` è sceso sotto ~11 ms**,
   perché la soglia di pareggio della seconda posizione è `(H + R)/ms-per-token` e sopra gli 11 ms
   resta oltre lo 0,553 misurato in P7c1.
6. **Una leva per cella.** Se due leve entrano insieme e `R` non scende, non è attribuibile.

---

## 6. Difetti dichiarati di questo progetto

1. **Nessuna misura nuova**: tutto è dedotto dal codice e dai numeri di P7c3. Il modello degli
   ingressi di split è verificato *a posteriori* su 14 e 49 copie (§1.2) — combacia, ma è una
   ricostruzione, non una lettura diretta. `GGML_SCHED_DEBUG=2` la conferma in dieci minuti.
2. **I ms di A sono la stima più debole**: i +2,17 ms di GPU inattiva non sono stati attribuiti voce
   per voce (svuotamenti, emissione delle copie, coda del split precedente). Il range −0,5…−1,2 è
   prudente in basso e non ha un limite superiore dimostrato.
3. **Il guadagno di C dipende da un'ipotesi di occupancy**: 4× thread-slot liberati non danno
   necessariamente 2× di banda su letture da 136 B. Se il dato risultasse ospitato in VRAM e non in
   memoria host mappata, il guadagno sarebbe anche maggiore, ma non è stato verificato dove vive la
   cache KV in questa configurazione (il preset usa `QWEN4EXP_ATTN_MAPPED=1`, che lo suggerisce ma
   non lo prova).
4. **Il numero di rapporti di compressione distinti (uno) è dedotto dal conteggio delle copie**, non
   letto da `hparams.dsv4_compress_ratios`. Se fossero due, le copie a 1 riga sarebbero 16: il dato
   misurato dice 14. Da confermare quando si riaprirà il log del caricamento.
5. **Per E non è stato verificato quali tipi hanno davvero i tensori esperti**: la leva è descritta
   per IQ3_XXS perché è il tipo dominante del pacchetto UD-IQ3_XXS, ma la presenza di IQ2_S
   cambierebbe quale ramo di `mmvq.cu` gira su quale strato. È la prima verifica da fare in P8c6.
6. **Le patch non sono state compilate.** Sono diff testuali contro `p0_snapshot_20260914`, ancorate
   a stringhe uniche e generate con `diff -u` (non scritte a mano), ma nessun compilatore le ha viste.

---

## 7. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/p8_riga_verifica/PROGETTO_P8_15_SETTEMBRE.md` | questo progetto |
| `docs/porto/p8_riga_verifica/p8_A.patch` | tetto degli ingressi di split, `ggml/src/ggml-backend.cpp` (non applicata) |
| `docs/porto/p8_riga_verifica/p8_B.patch` | bias QSA residente sul dispositivo, `src/models/qwen4exp.cpp` (non applicata) |
| `docs/porto/p8_riga_verifica/p8_C.patch` | geometria di `get_rows` quantizzato, `ggml/src/ggml-cuda/getrows.cu` (non applicata) |

Le tre patch si applicano con **`patch -p1 --binary`** dalla radice di un albero uscito da
`D:\ds4_work\p0_snapshot_20260914\source`. Il `--binary` serve: i sorgenti hanno fine riga CRLF e
senza quel flag `patch` rifiuta con *different line endings*; `git apply` non le prende per lo stesso
motivo. Verificate con `patch -p1 --binary --dry-run` su una copia dei tre file: **tre su tre
applicano pulite**, e il risultato è stato confrontato byte a byte con l'albero di lavoro. Sono
indipendenti fra loro e non toccano gli stessi file.

---

## 8. Bozza di voce di registro

> **15 settembre 2026 — fase P8, cella di progetto: le leve lossless della riga di verifica MTP.**
>
> *Ipotesi.* Dei 15,66 ms della riga di verifica, una parte non è né byte di esperti né aritmetica
> del modello, ma contabilità: tre lanci di grafo invece di uno, e un bias ricopiato dall'host più
> volte del necessario. Se è così, si toglie senza cambiare un solo bit del testo.
>
> *File toccati.* Nuovi: `docs/porto/p8_riga_verifica/PROGETTO_P8_15_SETTEMBRE.md`,
> `p8_A.patch`, `p8_B.patch`, `p8_C.patch`. **Nessun sorgente del motore modificato, nessuna build,
> nessuna corsa, nessun commit**: un'altra misura era in corso sulla macchina. Le patch sono diff
> contro `D:\ds4_work\p0_snapshot_20260914\source`, verificato byte-identico a `qwen38_clean\source`
> sui file interessati.
>
> *Risultato.* **La causa dei tre lanci di grafo è trovata e non è nei grafi CUDA.** Lo scheduler
> apre uno split nuovo *sullo stesso backend* ogni `GGML_SCHED_MAX_SPLIT_INPUTS = 30` ingressi
> (`ggml-backend.cpp:768`, `:1341-1348`), e un split CUDA è un `cudaGraphLaunch`
> (`ggml-cuda.cu:4663`). Il grafo di decode ha ~20 ingressi a 1 riga (1 lancio) e ~63 a 2 righe
> (3 lanci). **Gli ingressi in più sono viste del bias QSA**: il bias è un ingresso in buffer host
> (`qwen4exp.cpp:854`, `llama-memory-hybrid-idx.cpp:407`) e lo scheduler copia ogni vista per intero,
> `n_kv` float, anche quando la vista è una riga sola. Il conto previsto — 12 viste `b1` + 2 tensori
> interi a 1 riga, 24 `bias_row` + 24 `b1` + 1 a 2 righe — dà **14 e 49 copie da 822.272 B**, contro
> le **14 e 49** contate da nsys il 14/9: il meccanismo è verificato sui dati già in casa. Il costo
> non è solo la copia: prima degli ingressi di ogni split c'è un `ggml_backend_synchronize` e le
> copie sono bloccanti (`ggml-backend.cpp:1938-1956`), ed è lì che stanno i **+2,17 ms di GPU
> inattiva**. Due altre voci hanno una causa banale: `k_get_rows` va a 3,7 GiB/s perché
> `get_rows_cuda_q` lancia 256 thread per righe da 128 valori e ne usa 64 (`getrows.cu:189`); e i
> +6,60 ms di mmvq sono il prezzo della bit-identità nel kernel `mul_mat_vec_q_moe`, **un warp per
> token, nessuna condivisione**, che paga 20 rotte per strato mentre gli esperti distinti sono 16,47.
> Terzo fatto da verificare: con esperti IQ3_XXS il ramo `QWEN_MOE_SCALAR_BATCH=2` **non si applica**
> (`mmvq.cu:1124` copre solo IQ2_S/IQ3_S/IQ4_NL): la variabile del preset M1 potrebbe essere inerte
> su gran parte del MoE.
>
> *Decisione.* Si apre P8 con cinque leve in fila, una per cella, tutte a byte del trasporto
> invariati: **A** tetto degli ingressi di split (−0,5…−1,2 ms, una riga, lossless per costruzione),
> **B** bias QSA residente sul dispositivo (−1,11 ms a 205k, −0,18 al banco; da sola riporta il grafo
> a un lancio), **C** geometria di `get_rows` quantizzato (−0,6…−1,0 ms, e altrettanti su `T1`),
> **D** trasposta per token e catena di concat (−0,2 ms) con l'ordinamento segmentato unico come
> facoltativa a cancello di impronta, **E** condivisione dell'esperto fra i token in mmvq
> (−1,2…−2,0 ms, difficoltà alta, ultima). Cancello di correttezza identico per tutte: **impronte
> SHA256 identiche a M1 su `ctx32k`, 8 su 8**, `reasoning_content` incluso; criterio di successo sul
> **costo della riga**, non sui t/s. La bozza a 2 token si rimette in discussione **solo** quando
> `R` scende sotto ~11 ms.
>
> *Limite.* Nessuna misura nuova: tutto è dedotto dal codice e dai numeri di P7c3. La stima di A è la
> più debole (i 2,17 ms di inattiva non sono attribuiti voce per voce) e quella di C dipende da
> un'ipotesi di occupancy non verificata. Le patch non sono state compilate.
>
> *Prossima azione.* P8c1 = leva A, con `GGML_SCHED_DEBUG=2` come verifica da dieci minuti che gli
> split siano dove il modello dice, poi profilo `fumo` con bozza 1 e `R` prima/dopo.
