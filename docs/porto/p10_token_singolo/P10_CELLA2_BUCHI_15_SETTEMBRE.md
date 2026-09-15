# P10 · cella 2 — i due buchi di inattivita' della GPU fra il grafo e l'host, e le sincronizzazioni per forward — 15 settembre 2026

Cella di **diagnosi e correzione**. Domanda: dove stanno i due buchi da ~1 ms che P9 aveva
trovato (1,9 ms per token di GPU ferma, sempre alla stessa fase del forward), chi sono le **78
`cudaStreamSynchronize`** per forward, quante servono davvero, e quanto si recupera togliendo
quelle che non servono — **senza cambiare un bit del testo generato**.

Riferimento: **V1 = 37,486 ms/token, 26,677 t/s** (P10 cella 1, binari P8 con la leva B accesa,
MTP spento, profilo `lungo_131k`, 131k di contesto).

`bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, il lanciatore quotidiano, i modelli e
lo snapshot P0 non sono stati toccati. Si e' lavorato solo sull'albero P8
(`D:\ds4_work\p8_work\source`, build in `D:\ds4_work\p8_work\build`). **Nessun commit.**
I binari esatti di V1 sono stati messi da parte in `D:\ds4_work\p8_work\bin_v1_p10` **prima** di
ricompilare, cosi' V1 resta rifacibile.

---

## 0. In sette righe

1. **I due buchi non sono due dello stesso genere.** Il grande (1,267 ms per forward, uno per
   token) e' **il confine fra un forward e il successivo**: sta esattamente al nodo 0 del grafo
   CUDA, fra l'ultimo kernel del grafo N (la testa di uscita, `mul_mat_vec_q<q6_k>`, 1,74 ms) e il
   primo kernel del grafo N+1. Il piccolo (0,080 ms per forward, presente in meta' dei forward) e'
   **dentro** il replay, al nodo 45, e non contiene nessuna chiamata CUDA se non il
   `cudaGraphLaunch` ancora in corso: e' il driver che non riesce a consegnare i nodi alla velocita'
   con cui la GPU li consuma.
2. **Le 78 sincronizzazioni di P9 sono 43,6 al punto di partenza di questa cella** (la leva B di P8
   ne aveva gia' tolte ~34). Si dividono in tre classi, tutte identificate nel codice: **1**
   necessaria (l'attesa del forward, `llama_context::synchronize`), **15,6** code bloccanti di una
   copia (`ggml_backend_cuda_buffer_set_tensor`), **27,0** svuotamenti della coda prima di un
   ingresso (`ggml_backend_sched_compute_splits`). **42,6 su 43,6 sono di comodo.**
3. **La causa e' che le copie degli ingressi vanno su uno stream diverso da quello del grafo**
   (`cudaStreamPerThread` contro lo stream del contesto CUDA): l'ordine puo' essere garantito solo
   da attese dell'host, una per ingresso.
4. **Correzione 1**: gli ingressi si copiano con `set_tensor_async` **sullo stream del grafo**, con
   una sola sincronizzazione per split. Stessi byte, stessi offset, stessa destinazione.
5. **Correzione 2**: il verdetto di compatibilita' del grafo CUDA
   (`ggml_cuda_graph_check_compability`, che riscandisce **8.191 nodi a ogni forward**) si memorizza
   per `uid`, lo stesso invariante che upstream usa gia' per saltare il confronto nodo per nodo.
   Erano 174 µs per token di host puro, misurati come un blocco senza nessuna chiamata CUDA dentro.
6. **I 2 split a bs=1 sono uno CUDA e uno CPU**: `-ot per_layer_token_embd.weight=CPU` tiene un
   tensore da 26,8 GiB in un buffer host, e l'unica operazione che lo legge
   (`ggml_get_rows` in `build_inp_ple`) finisce sul backend CPU. Per forward c'e' **un solo**
   `cudaGraphLaunch`, quindi di split CUDA ce n'e' uno solo.
7. **Esito misurato**: le sincronizzazioni per forward passano da **43,61 a 9,12**, il buco del
   confine da **1,267 a 1,031 ms**, la GPU inattiva da **2,801 a 2,600 ms**, e le impronte restano
   **identiche 4 su 4**. Al token pero' arrivano **−0,154 ms** (37,486 → **37,332 ms/token**,
   26,677 → **26,786 t/s**, media di due repliche): **il cancello di −0,5 ms non e' raggiunto**,
   perche' dei 1,267 ms del buco solo 0,415 erano chiamate CUDA e 0,505 sono un blocco di host
   (campionamento su 248.320 logit, servizio, `set_inputs`) che questa cella non tocca — e un quarto
   di quello che si toglie se lo riprende il buco 2, che cresce. In compenso si e' misurato per la
   prima volta il **rumore fra repliche su `T1` a 131k: 0,152 ms** sull'aggregato, non 0,5.

---

## 1. Cancello di partenza e stato dei processi

Guardia eseguita prima di ogni avvio e prima di ogni build:
`netstat -ano | findstr LISTENING | findstr :8100` vuoto, `tasklist | findstr llama-server` vuoto,
nessun processo di compilazione. Nessun server non mio e' stato trovato: si e' proceduto ogni volta.
Un solo server o sonda alla volta per tutta la cella.

**Stato a fine cella, verificato**: nessun `llama-server`, nessun `nsys`, nessuna sessione nsys
(`nsys sessions list` vuota), porta 8100 libera, nessuna build in corso, nessun processo residuo.

Ordine delle quattro corse: (1) profilata «prima» sui binari V1 → (2) build → (3) V2 al banco,
replica 1 → (4) profilata «dopo» sui binari V2 → (5) V2 al banco, replica 2. **Nessuna build e'
stata lanciata con un server acceso**, e nessuna corsa e' partita con una build in corso.

---

## 2. A — dove sono i due buchi, e chi sono le sincronizzazioni

### 2.1 Come e' stata fatta la misura del «prima»

| | |
|---|---|
| corsa | `20260915_160208_P10_p10_c2_prima_v1` in `D:\ds4_work\banco_p0_run` |
| preset | `preset_V1_p10.json` — **gli stessi identici binari e la stessa configurazione di V1** (leva B accesa, MTP spento, 64 slot, contesto 262.144, `-ctk/-ctv q8_0`, `-np 1`, greedy seed 1234, ragionamento acceso) |
| profilo | `lungo_131k`, budget `screening` (1.024 token per caso) |
| profilatore | Nsight Systems 2024.5.1, `nsys launch --session-new=p10c2 -t cuda --cuda-graph-trace=node`, raccolta spenta per tutta la corsa e aperta con `nsys start` **dentro il decode**, 8 s dopo il primo delta SSE, per **5 s** |
| perche' una sola finestra | P9 aveva registrato che la **seconda** cattura nella stessa sessione perde eventi (difetto 1 di P9). Qui si profila solo `L01`, e il controllo di integrita' geometrico passa |
| impronte | **4 su 4 identiche a V1** (`b626d0e377e6075e`, `b626d0e377e6075e`, `99ba1423cf128585`, `dc916b9c428225c2`): la corsa profilata e' la stessa corsa, guardata da dentro |
| costo del profilatore | `L01` 38,823 ms/token contro 37,353 senza (+3,9%), `L02` 39,194 contro 37,692 (+4,0%). **I ms/token di questa corsa non sono un banco** e servono solo a scomporre |
| RAM/VRAM minime | RAM disponibile **2,73 GB** (sotto la soglia dei 4 GB: pesa il profilatore), VRAM libera **1.162 MiB** |

### 2.2 Il confine del forward si legge dal grafo, non da un kernel periodico

P9 trovava i forward da un kernel periodico (`moe_grouped_plan_decode`, 48 volte per forward).
Qui si usa un confine piu' preciso: **i nodi di un replay di grafo CUDA hanno `graphNodeId`
crescenti**, quindi il punto in cui l'identificatore torna indietro e' il primo nodo del grafo
successivo. Il confine coincide con il grafo, non con una fase arbitraria.

Serve anche a **buttare via i forward sporchi**: ogni tanto il backend CUDA ri-cattura il grafo
(le proprieta' di un nodo sono cambiate) e quel forward gira nodo per nodo con migliaia di
`cudaLaunchKernel`. Nella finestra di 5 s ce ne sono **7 su 134**: senza escluderli il controllo di
integrita' fallisce (47,6 `plan_decode` per forward invece di 48) e ogni media e' sporca.
**Tutti i numeri che seguono sono sui 127 forward puliti**, e il controllo di integrita' geometrico
passa: `plan_decode` 48,0/48, `topk_moe` 48,0/48, `weighted_reduction` 48,0/48, `gated_delta_net`
36,0/36, `ssm_conv` 36,0/36, `flash_attn_ext` 12,0/12.

### 2.3 La GPU inattiva, per fascia

127 forward puliti, 4.256 kernel ciascuno. Parete **36,807 ms**/forward (col profilatore),
**GPU inattiva 2,801 ms**/forward.

| fascia | buchi/forward | ms/forward | che cosa |
|---|---:|---:|---|
| **> 100 µs** | **1,50** | **1,346** | i due buchi di questa cella |
| 5-20 µs | 64,20 | 0,885 | tutti **dentro** il grafo, nell'indicizzatore QSA (§7.3) |
| < 2 µs | 4.048,8 | 0,381 | latenza fra nodi dentro il grafo |
| 2-5 µs | 60,59 | 0,147 | — |
| 20-100 µs | 0,50 | 0,041 | — |

### 2.3-bis I due buchi in una tabella

| buco | fase del forward | ultimo kernel prima → primo dopo | causa | durata/forward | per forward |
|---|---|---|---|---:|---:|
| **1** | **il confine**: nodo 0 del grafo CUDA, fra la fine del grafo N e l'inizio del grafo N+1 | `mul_mat_vec_q<q6_k>` (la testa di uscita, 1.740 µs) → `k_bin_bcast` | tutta la consegna fra grafo e host: campionamento e servizio, `set_inputs`, split CPU del PLE, **15 copie di ingresso con 42 sincronizzazioni**, **scansione di compatibilita' su 8.191 nodi**, lancio del grafo | **1,267 ms** | 1,00 |
| **2** | **dentro il replay**, nodo 45 su 4.256 | `mul_mat_vec_q` → `scale_f32` (nodi contigui dello stesso grafo) | il `cudaGraphLaunch` e' **ancora in corso**: il driver consegna 8.191 nodi a ~0,75 µs l'uno e la GPU divora i primi piu' in fretta | **0,080 ms** | 0,50 |

### 2.4 Buco 1 — il confine fra due forward (nodo 0)

| | |
|---|---|
| kernel prima | `mul_mat_vec_q<q6_k>` che dura **1.740 µs**: e' la **testa di uscita** (`output.weight`, 497 MiB), l'ultimo nodo del grafo |
| kernel dopo | `k_bin_bcast`, il **primo nodo** del grafo successivo (`graphNodeId` torna indietro proprio qui) |
| quante volte | **1,00 per forward** |
| durata | **1,267 ms per forward** (mediana 1,258, minimo 1,095, massimo 1,717) |
| fase | **il confine del forward**: nodo 0. Non «fine strato», non «planner MoE», non «indicizzatore»: e' la consegna fra il grafo N e il grafo N+1 |
| dentro | 42,0 `cudaStreamSynchronize` (0,243 ms), 15,0 `cudaMemcpyAsync` (0,112 ms), 1 `cudaGraphLaunch` (0,060 ms), 16 copie per 2,237 MiB |

**Il bilancio del buco**: 0,415 ms sono chiamate CUDA, **0,852 ms sono lavoro dell'host che il
tracciamento CUDA non vede** (nsys avverte che il campionamento della CPU richiede privilegi di
amministratore e lo disabilita — difetto ereditato da P9).

La cronologia di un confine pulito (istanza da 1,301 ms), con gli scostamenti dall'inizio del buco:

| da → a (µs) | durata | che cosa c'e' dentro |
|---|---:|---|
| 0 → 81,5 | **82** | l'host e' ancora dentro la `cudaStreamSynchronize` che aspetta il forward; a +30 µs parte la **D2H dei logit** (993.280 byte = 248.320 float, 40 µs), gia' accodata prima sullo stream |
| 81,5 → 292,8 | **211** | cinque sincronizzazioni cortissime (4,4 / 1,4 / 0,8 / 0,6 / 0,7 µs) piu' una a +292,8: sono `ggml_backend_sched_synchronize` che scorre i backend |
| 292,8 → 797,9 | **505** | **nessuna chiamata CUDA**: campionamento su 248.320 logit, risposta SSE del server, `mctx->apply()`, `set_inputs` (di cui il riempimento del pool QSA misurato a parte vale ~105 µs, §7.2) |
| 797,9 → 1.068,8 | **271** | **le 15 copie degli ingressi**, intervallate da 41 sincronizzazioni. Il DMA vero dentro e' ~55 µs: **il resto e' andata e ritorno con il driver** |
| 1.068,8 → 1.242,9 | **174** | **nessuna chiamata CUDA**: e' `ggml_cuda_graph_check_compability`, che scorre tutti gli **8.191 nodi** del grafo (§3.2) |
| 1.242,9 → 1.301 | **58** | dal `cudaGraphLaunch` al primo kernel |

### 2.5 Buco 2 — dentro il replay, al nodo 45

| | |
|---|---|
| kernel prima / dopo | `mul_mat_vec_q` → `scale_f32`, **nodi consecutivi dello stesso grafo** (`graphNodeId` contigui) |
| quante volte | **0,50 per forward** (in meta' dei forward non c'e') |
| durata | **0,080 ms per forward**, mediana 0,139 quando c'e' |
| dentro | **nessuna copia, nessuna sincronizzazione**: solo il `cudaGraphLaunch` **ancora in corso** (la chiamata dura 6,1 ms di tempo host) |
| lettura | non e' l'host che «esce dal grafo»: e' **la consegna del grafo al driver**. `cudaGraphLaunch` su un grafo da 8.191 nodi su WDDM non e' istantanea; la GPU divora i primi ~45 nodi (kernel da 1-15 µs) piu' in fretta di quanto il driver riesca a sottometterli e si ferma ad aspettare il pacchetto successivo |

Questo buco **non e' aggredibile** con le leve di questa cella: non c'e' nessuna sincronizzazione da
togliere. Si restringe solo dando al driver un vantaggio all'avvio, oppure riducendo il numero di
nodi (leva 2 di P9, un'altra cella).

### 2.6 Le sincronizzazioni per forward, classificate

Senza stack l'attribuzione si fa dal contesto (quale chiamata CUDA precede la sincronizzazione sullo
stesso filo) e dalla durata; ogni classe corrisponde a un punto preciso del codice.

| classe | per forward | ms/forward | dove nel codice | necessaria? |
|---|---:|---:|---|---|
| **attesa del forward** (> 1 ms) | **1,00** | 29,803 | `llama_context::synchronize` → `ggml_backend_sched_synchronize` → `ggml_backend_cuda_synchronize`. L'host deve avere i logit per campionare | **SI'**. E' attesa pura, si sovrappone al lavoro della GPU e non costa nulla |
| **coda bloccante di una copia** | **15,59** | 0,144 | `ggml_backend_cuda_buffer_set_tensor` (`ggml-cuda.cu:2215`): `cudaMemcpyAsync` su `cudaStreamPerThread` **piu'** `cudaStreamSynchronize` | **NO** |
| **svuotamento della coda prima di un ingresso** | **27,02** | 0,022 | `ggml_backend_synchronize(split_backend)` in `ggml_backend_sched_compute_splits` (una volta nel ramo `GGML_TENSOR_FLAG_INPUT`, due nel ramo generico) | **NO** |
| **totale** | **43,61** | 29,970 | | **1 su 43,6** |

> **Perche' 43,6 e non 78.** Le 78 di P9 sono state contate sui binari **nudi**, senza la leva B.
> Con B accesa (che e' il riferimento V1) le copie del bias QSA passano da 14 a 2 e con loro
> spariscono ~34 sincronizzazioni. La struttura pero' e' la stessa: **~2,8 sincronizzazioni per
> ingresso copiato**.

### 2.7 Perche' servono due attese per ogni ingresso

`ggml_backend_sched_compute_splits`, per ogni ingresso di split:

```c
    if (input->flags & GGML_TENSOR_FLAG_INPUT) {
        ggml_backend_synchronize(split_backend);      // svuota la coda della GPU
        ggml_backend_tensor_copy(input, input_cpy);   // copia BLOCCANTE
    } else {
        ggml_backend_synchronize(split_backend);      // idem
        ... ggml_backend_synchronize(input_backend);
        ggml_backend_tensor_copy(input, input_cpy);   // copia BLOCCANTE
    }
```

e `ggml_backend_tensor_copy` con sorgente su host finisce in
`ggml_backend_cuda_buffer_set_tensor`, che fa `cudaMemcpyAsync` **su `cudaStreamPerThread`** seguita
da `cudaStreamSynchronize`.

**Il punto e' che i due stream sono diversi.** Lo stream di calcolo del contesto CUDA e' creato con
`cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)` (`ggml-cuda/common.cuh:1492`), quindi non ha
**nessun** ordine rispetto a `cudaStreamPerThread`. L'unico modo di garantire che (a) la copia non
sovrascriva un buffer che il grafo precedente sta ancora leggendo e (b) il grafo successivo non
parta prima che la copia sia finita, e' **fermare l'host due volte per ogni ingresso**. Nella
cattura si vede il ritmo, identico ingresso dopo ingresso: `sync` ~5,4 µs, `sync` ~0,5 µs,
`memcpyAsync` ~5,4 µs; e per le tre copie grandi (526.336 e 262.144 byte) la sincronizzazione di
coda dura 18-29 µs, cioe' **l'host sta fermo per tutto il DMA**.

Conto: 15 copie × ~11,3 µs di andata e ritorno + ~75 µs di attesa dei tre DMA grandi = **~245 µs**,
contro i 271 µs misurati del blocco. Il DMA vero e' ~55 µs: **quattro quinti di quel blocco sono
protocollo, non byte**.

### 2.8 I 2 split a bs=1

Dal log del server, alla riserva del grafo di decode: `graph nodes = 8131 (with bs=3), 8094 (with
bs=1)`, `graph splits = 2`. Dalla cattura: **un solo `cudaGraphLaunch` per forward**, e i
`graphNodeId` dei 4.256 kernel di un forward sono un'unica sequenza crescente. Quindi **di split
CUDA ce n'e' uno solo** e il secondo non e' CUDA.

Chi e'. La riga di lancio contiene `-ot per_layer_token_embd.weight=CPU`: il tensore
`per_layer_token_embd` (160 × 320.001.536, iq4_nl, **26,8 GiB**) resta in un buffer **host**.
L'unica operazione che lo legge e' `ggml_get_rows(model.per_layer_tok_embd, rows)` dentro
`build_inp_ple` (`src/models/qwen4exp.cpp:1724`), e lo scheduler assegna al backend CPU le
operazioni i cui pesi vivono in un buffer che la GPU non possiede
(`ggml_backend_sched_split_graph`, passo 1). **Da li' il secondo split.** Il suo risultato, `emb`
= `[ple_head_dim × n_heads, n_tokens]` in f32, e' poi un ingresso dello split CUDA: nell'istogramma
delle copie H2D compaiono infatti **due copie da 10.240 byte** per forward (2.560 float = `n_embd`),
compatibili con quel trasferimento.

**Non e' quindi un difetto da correggere**: e' la conseguenza voluta di tenere 26,8 GiB fuori dalla
VRAM. Conta pero' nel bilancio del buco, perche' lo split CPU gira **dentro** il confine, sull'host,
in serie con tutto il resto.

---

## 3. B — le due correzioni

Tutte e due dietro un interruttore d'ambiente, acceso di default, cosi' il prima/dopo si fa **con un
solo binario**. Vietati e non usati: disattivare i CUDA graph, cambiare l'aritmetica, cambiare la
politica della cache.

### 3.1 Correzione 1 — gli ingressi di split copiati sullo stream del grafo

**File**: `ggml/src/ggml-backend.cpp` (nuove funzioni a `:1832` e `:1842`, attesa unica per split a
`:1893-1901`, uso a `:1919-1923` e `:1933-1937`) e `src/llama-context.cpp` (`:1394` la lettura
dell'interruttore, `:1459` la sincronizzazione esplicita prima di `set_inputs`).
**Interruttore**: `GGML_SCHED_ASYNC_INPUTS` (default **1**; `0` = comportamento di V1).

**Che cosa cambia.** Una sola `ggml_backend_synchronize(split_backend)` all'inizio dello split,
poi ogni ingresso host→device va con `ggml_backend_tensor_set_async(split_backend, input_cpy,
input->data, 0, ggml_nbytes(input))`, cioe' `cudaMemcpyAsync` **sullo stream del grafo**. Nessuna
altra attesa.

**Perche' e' corretto.** La garanzia passa dall'host allo **stream**: la copia e' accodata dopo il
grafo precedente (quindi non puo' sovrascrivere un buffer che quello sta ancora leggendo) e prima
del grafo successivo (quindi il grafo non puo' leggere byte vecchi). La sincronizzazione unica in
testa allo split resta a coprire il caso in cui lo split precedente sia su un altro backend.

**Perche' e' senza perdita.** Con sorgente su host, `ggml_backend_tensor_copy` fa *esattamente*
`ggml_backend_tensor_set(dst, src->data, 0, ggml_nbytes(src))` (`ggml-backend.cpp:495`): stessa
`cudaMemcpyAsync` H2D, stessi byte, stesso offset, stessa destinazione. **Cambia solo lo stream su
cui e' accodata e chi garantisce l'ordine.** Nessun kernel, nessuna riduzione, nessun ordine di
somma.

**Che cosa resta fuori dal ramo asincrono** (e continua com'era):
- i **pesi** (`GGML_BACKEND_BUFFER_USAGE_WEIGHTS`): quando un tensore di esperti sta su host lo
  scheduler copia **solo gli esperti instradati** (ramo `copy_experts`), e una copia intera sarebbe
  un'altra cosa;
- le copie device→host (sorgente non host);
- le destinazioni che non stanno nel buffer predefinito del backend, o che sono viste
  (`dst->view_src != NULL`), o con layout diverso: sono le stesse condizioni che l'assert dentro
  `ggml_backend_cuda_set_tensor_async` pretende;
- il percorso a piu' copie (`pipeline parallelism`), dove l'ordine e' gia' gestito con eventi.

**La precondizione, dichiarata.** Con le copie asincrone, fra
`ggml_backend_sched_graph_compute_async` e la successiva riscrittura dei tensori d'ingresso ci deve
essere una sincronizzazione — altrimenti `set_inputs` potrebbe riscrivere `input->data` mentre la
copia e' ancora in volo. `ggml_backend_sched_graph_compute` (la versione non-async) la fa gia'. Per
il percorso di llama.cpp la precondizione **e' stata resa esplicita**, non assunta: in
`llama_context::process_ubatch`, subito prima di `res->set_inputs(&ubatch)`, c'e' ora una
`ggml_backend_sched_synchronize`. Al punto operativo costa **zero**: a quel punto il campionatore ha
gia' letto i logit, quindi la coda e' gia' vuota.

### 3.2 Correzione 2 — il verdetto di compatibilita' del grafo si ricorda

**File**: `ggml/src/ggml-cuda/ggml-cuda.cu` (`:2838-2864`, uso a `:4767`).
**Interruttore**: `GGML_CUDA_GRAPH_COMPAT_CACHE` (default **1**; `0` = comportamento di V1).

**Il fatto.** `ggml_backend_cuda_graph_compute` chiama `ggml_cuda_graph_check_compability(cgraph)`
**a ogni forward**, e quella funzione scorre `cgraph->n_nodes` — a 131k sono **8.191 nodi** —
leggendo `node->op` di tensori sparsi in memoria. Nella cattura e' il blocco di **174 µs senza
nessuna chiamata CUDA** fra l'ultima copia e il `cudaGraphLaunch` (§2.4). 8.191 nodi a ~21 ns di
inseguimento di puntatori fanno esattamente quel numero.

**Che cosa cambia.** Il verdetto si memorizza in una tabella indicizzata dalla stessa chiave del
grafo CUDA (`cgraph->nodes[0]`), valida finche' `cgraph->uid` e `cgraph->n_nodes` non cambiano.

**Perche' e' senza perdita.** Il verdetto dipende **solo** dalla topologia (gli `op` dei nodi e, per
i `MUL_MAT_ID`, la forma che decide `ggml_cuda_mul_mat_id_needs_sync`). Quella topologia e'
esattamente cio' che `uid` identifica: lo scheduler assegna un `uid` nuovo a ogni split ogni volta
che ri-divide il grafo (`ggml-backend.cpp`, fine di `ggml_backend_sched_split_graph`), e llama.cpp
ri-divide ogni volta che `llm_graph_result::can_reuse` dice di no. **E' lo stesso invariante su cui
poggia gia' `ggml_cuda_graph_update_required`** per saltare il confronto nodo per nodo (`uid`
uguale → ritorna subito). Qui si riusa per saltare anche la scansione. A `uid` e numero di nodi
invariati la scansione darebbe, nodo per nodo, esattamente il valore memorizzato.

### 3.3 Che cosa NON e' stato fatto, e perche'

| candidato | perche' no |
|---|---|
| **rendere incrementale il riempimento del pool QSA** (`llama-memory-hybrid-idx.cpp:425-460`: quattro `std::fill` su `n_kv` piu' un doppio ciclo da `n_kv` iterazioni, rifatti da zero a ogni token anche se fra due token consecutivi cambiano O(r) valori) | **misurato con un micro-banco fuori dal server**: a `n_kv = 131.584` e `r = 4` costa **103-105 µs** (due misure concordi), non le centinaia che sembravano. Vale ~0,1 ms contro una modifica di ~120 righe con stato da invalidare: rapporto sbagliato per questa cella |
| togliere lo split CPU del PLE | vuol dire portare 26,8 GiB in VRAM (impossibile) o riscrivere il gather su memoria mappata: non e' «la modifica piu' piccola» |
| attaccare il campionamento su 248.320 logit (dentro i 505 µs) | non e' plumbing fra grafo e host, ed e' a un passo dal divieto di «cambiare l'aritmetica» |
| il buco 2 (nodo 45) | non contiene nessuna sincronizzazione da togliere: e' consegna del grafo al driver (§2.5) |

---

## 4. C — la misura al banco

Corsa **V2**: `20260915_162514_P10_p10_c2_v2_buchi_mtp_spento_r1`, preset
`preset_V2_p10.json`, stessa identica configurazione di V1 (profilo `lungo_131k`, budget
screening 1.024 token, greedy seed 1234, ragionamento acceso, MTP spento, 64 slot, contesto
262.144), **senza profilatore**. Cambiano solo i binari (ricompilati) e le due variabili
dichiarate. Verificato nel `config.redacted.json` della corsa:
`GGML_SCHED_ASYNC_INPUTS = "1"`, `GGML_CUDA_GRAPH_COMPAT_CACHE = "1"`,
`binari = D:\ds4_work\p8_work\build\bin`. Nessun guasto, nessun NaN, nessun avviso.

### 4.1 ms/token e t/s

| caso | V1 ms/tok | V1 t/s | V2 ms/tok | V2 t/s | Δ ms | Δ t/s | Δ % |
|---|---:|---:|---:|---:|---:|---:|---:|
| L01@ctx131k | 37,353 | 26,772 | 37,392 | 26,743 | **+0,040** | −0,029 | −0,11% |
| L02@ctx131k | 37,692 | 26,531 | 37,497 | 26,669 | **−0,196** | +0,138 | +0,52% |
| **aggregato (2.048 tok)** | **37,486** | **26,677** | **37,408** | **26,732** | **−0,078** | **+0,055** | **+0,21%** |

(aggregato = `tempo_generazione_s / token_accettati`; V1 76,771 s, V2 76,612 s, 2.048 token
entrambi.)

### 4.1-bis La replica, e il rumore vero fra repliche su `T1` a 131k

Il guadagno di r1 (−0,078 ms) e' sotto il cancello, quindi — come prevede il mandato — **la misura
e' stata ripetuta una volta**: corsa `20260915_165455_P10_p10_c2_v2_buchi_mtp_spento_r2`, stesso
preset, processo nuovo.

| | L01 ms/tok | L02 ms/tok | **aggregato ms/tok** | **t/s** | RAM min |
|---|---:|---:|---:|---:|---:|
| V1 (riferimento, P10 cella 1) | 37,353 | 37,692 | **37,486** | **26,677** | 3,03 GB |
| V2 replica 1 | 37,392 | 37,497 | **37,408** | **26,732** | 2,77 GB |
| **V2 replica 2** | **37,124** | **37,461** | **37,256** | **26,841** | **6,77 GB** |
| V2, media delle due repliche | 37,258 | 37,479 | **37,332** | **26,786** | — |

Tre cose da leggere, in ordine:

1. **Il rumore fra repliche su `T1` a 131k e' ~0,15 ms sull'aggregato e ~0,27 ms sul singolo caso**
   (V2 r1 contro V2 r2, stessa identica configurazione: −0,152 aggregato, −0,268 su L01). E' la
   **prima misura diretta** di questo rumore sul token singolo: il valore di 0,5 ms citato nel
   mandato viene da P8 e riguarda la riga di verifica `R`, non `T1`. **Il pavimento di rumore e'
   piu' basso di quanto si pensasse**, ma resta dello stesso ordine dell'effetto cercato.
2. **La stima migliore del guadagno e' −0,154 ms** (media delle due repliche V2 contro l'unica
   corsa V1), con estremi −0,078 e −0,230. **Nessuno dei tre valori arriva al cancello di −0,5.**
3. **Solo la replica 2 e' formalmente valida** per la regola dei 4 GB di RAM disponibile
   (6,77 GB): la macchina si era liberata. V1 (3,03) e V2 r1 (2,77) sono entrambe sotto soglia —
   e V1 lo era gia' in P10 cella 1. **Non esiste in questa cella un riferimento V1 sopra soglia**,
   e il confronto eredita questo difetto (§7.3).

### 4.2 Impronte — **identiche, 4 su 4**

| caso | V1 | V2 | identica |
|---|---|---|:--:|
| riscaldamento_1 | `b626d0e377e6075e` | `b626d0e377e6075e` | si |
| riscaldamento_2 | `b626d0e377e6075e` | `b626d0e377e6075e` | si |
| L01@ctx131k | `99ba1423cf128585` | `99ba1423cf128585` | si |
| L02@ctx131k | `dc916b9c428225c2` | `dc916b9c428225c2` | si |

**Le due correzioni sono lossless sul testo**, come lo erano per costruzione. Vale anche per la
corsa profilata «dopo»: 4 impronte su 4 identiche.

### 4.3 Split, nodi, lanci, memoria

| | V1 | V2 |
|---|---|---|
| `graph nodes` (bs=3 / bs=1) dal log del server | 8131 / 8094 | **8131 / 8094** (invariati) |
| `graph splits` alla riserva del decode | 2 | **2** (invariati) |
| `cudaGraphLaunch` per forward (dalla cattura) | 1,00 | **1,00** |
| kernel per forward | 4.256 | **4.256** |
| **`cudaStreamSynchronize` per forward** | **43,61** | **9,12** |
| copie H2D per forward | 15,59 (**stream 14**, `cudaStreamPerThread`) | 15,23 (**stream 63**, quello del grafo) |
| prefill L01 (t/s) | 251,75 | 251,65 |
| VRAM libera minima | 1.213 MiB | 1.213 MiB |
| RAM disponibile minima | 3,03 GB | **2,77 GB** |

**La patch non tocca il grafo**: stessi nodi, stessi split, stesso numero di kernel, un solo lancio
di grafo. Cambia solo **chi garantisce l'ordine** e **quante volte l'host si ferma**. Le copie sono
migrate dallo stream per-thread allo stream del grafo, che e' esattamente l'effetto voluto.

*Difetto dichiarato*: la RAM disponibile minima e' **2,77 GB in V2 contro 3,03 in V1**, entrambe
sotto la soglia di 4 GB della regola dell'utente (lo era gia' V1 in P10 cella 1). La macchina
e' sotto pressione di memoria per tutta la giornata; il confronto V1/V2 resta fra due corse nella
stessa condizione, ma nessuno dei due valori e' un assoluto.

---

## 5. Il profilo prima/dopo

Corsa «dopo»: `20260915_163619_P10_p10_c2_dopo_v2`, stessa procedura del «prima» (§2.1) sui binari
V2. Controllo di integrita' geometrico **passato**, 130 forward puliti (1 solo scartato per
ri-cattura, contro 7 nel prima). Impronte identiche 4 su 4. Le due analisi complete sono in
`log/prima_V1_buchi.{md,json}` e `log/dopo_V2_buchi.{md,json}`.

### 5.1 Le due cifre che contano

| | prima (V1) | dopo (V2) | Δ |
|---|---:|---:|---:|
| parete per forward (col profilatore) | 36,807 ms | 36,700 ms | **−0,107** |
| **GPU inattiva per forward** | **2,801 ms** | **2,600 ms** | **−0,201** |
| **buco 1** (confine, nodo 0) | **1,267 ms** | **1,031 ms** | **−0,236** |
| buco 2 (nodo 45, dentro il replay) | 0,080 ms | 0,138 ms | **+0,058** |
| fascia 5-20 µs (dentro il grafo) | 0,885 ms | 0,883 ms | −0,002 |
| fascia < 2 µs | 0,381 ms | 0,378 ms | −0,003 |
| **`cudaStreamSynchronize` per forward** | **43,61** | **9,12** | **−34,5** |
| — di cui code bloccanti di una copia | 15,59 | **0** | −15,6 |
| — di cui svuotamenti prima di un ingresso | 27,02 | 8,12 | −18,9 |
| — di cui attesa del forward (necessaria) | 1,00 | 1,00 | 0 |

### 5.2 Il confine, riga per riga, prima e dopo

Cronologia di un confine pulito (istanza mediana), scostamenti in µs dall'inizio del buco:

| segmento | prima | dopo | Δ | che cosa |
|---|---:|---:|---:|---|
| l'host esce dalla sincronizzazione del forward (dentro c'e' la D2H dei logit, 40 µs) | 82 | 87 | +5 | invariato |
| sincronizzazioni di `ggml_backend_sched_synchronize` e host | 211 | 229 | +18 | invariato |
| **host senza nessuna chiamata CUDA** (campionamento su 248.320 logit, SSE, `mctx->apply`, `set_inputs`) | **505** | **504** | −1 | **non toccato da questa cella** |
| **copie degli ingressi** | **271** | **133** | **−138** | 41 sincronizzazioni → **1**; copie accodate una dietro l'altra sullo stream del grafo |
| **scansione di compatibilita' del grafo** (8.191 nodi) | **174** | **5** | **−169** | il verdetto ora si ricorda |
| dal `cudaGraphLaunch` al primo kernel | 58 | 73 | +15 | la GPU deve aspettare il DMA dell'ultimo ingresso, che prima era gia' finito |
| **totale del buco** | **1.301** | **1.030** | **−271** | |

**Le due correzioni hanno fatto esattamente quello per cui erano scritte**, e si vede una per una:
il blocco delle copie e' dimezzato e ha una sola attesa invece di 41, e il blocco da 174 µs di pura
scansione dell'host **e' sparito** (5 µs).

### 5.3 Quello che il buco 2 si riprende

Il buco al nodo 45 **cresce**, da 0,080 a 0,138 ms per forward (e da 0,50 a 0,84 occorrenze per
forward): con gli ingressi accodati in modo asincrono l'host arriva al `cudaGraphLaunch` ~300 µs
prima, ma la GPU non puo' partire finche' il DMA dell'ultimo ingresso non e' finito, e poi divora i
primi nodi mentre il driver e' ancora indietro con la consegna. **Un quarto di quello che si toglie
al confine si ripresenta dentro il replay.** Non e' un errore della patch: e' la misura di quanto
la consegna di un grafo da 8.191 nodi costi su WDDM (`cudaGraphLaunch` dura 6,1-6,3 ms di tempo
host, ~0,75 µs per nodo).

---

## 6. Verdetto

> **Le due correzioni funzionano, sono lossless, e non bastano.**
>
> Il meccanismo e' verificato dal profilatore, non dedotto: le `cudaStreamSynchronize` per forward
> passano da **43,61 a 9,12** (le 15,6 code bloccanti delle copie spariscono del tutto), le copie
> degli ingressi migrano sullo **stream del grafo**, il buco del confine scende da **1,267 a 1,031
> ms** e il blocco da **174 µs** di scansione dei nodi sparisce. Il testo non cambia di un bit:
> **4 impronte su 4 identiche a V1**, sia al banco sia sotto profilatore.
>
> Ma il guadagno che arriva al token e' **−0,154 ms** (media di due repliche V2 contro V1:
> 37,486 → **37,332 ms/token**, 26,677 → **26,786 t/s**; le due repliche danno −0,078 e −0,230)
> e **−0,107 ms di parete** sotto profilatore. **Il cancello di adozione della cella — almeno
> −0,5 ms/token — non e' raggiunto, e non lo e' per un fattore tre.**
>
> La replica ha anche dato la **prima misura diretta del rumore fra repliche su `T1` a 131k**:
> **0,152 ms sull'aggregato, 0,268 sul singolo caso** (due corse V2 identiche). E' meno dei 0,5 ms
> che il mandato dava per scontati, ma e' dello stesso ordine dell'effetto: il guadagno e' reale
> — il profilatore lo vede meccanismo per meccanismo — e **piccolo**.
>
> Le tre ragioni, tutte misurate:
> 1. **Il grosso del buco non era sincronizzazioni.** Dei 1,267 ms del confine, solo 0,415 erano
>    chiamate CUDA; **0,852 ms erano lavoro dell'host**, e di quelli 0,505 sono un blocco che questa
>    cella non tocca (campionamento su 248.320 logit, risposta del server, `mctx->apply`,
>    `set_inputs`).
> 2. **Un quarto di quello che si toglie torna indietro** dentro il replay: il buco al nodo 45
>    cresce di 0,058 ms perche' il grafo viene lanciato prima e il driver non tiene il passo (§5.3).
> 3. **Quello che restava di davvero eliminabile era piccolo**: 138 µs di protocollo sulle copie e
>    169 µs di scansione. Insieme 0,31 ms lordi, 0,20 ms netti di GPU inattiva, ~0,15 ms al token.
>
> **Che cosa farne.** La patch **non costa nulla** (nessun nodo in piu', nessun byte in piu',
> nessuna VRAM, nessun rischio sul testo) e toglie 34,5 sincronizzazioni e ~0,24 ms di inattivita'
> per token. Va **tenuta accesa** come igiene del percorso, ma **non va contata come leva adottata**
> e non cambia il tetto di P9: a ~37,3 ms/token il punto operativo resta dove era.
>
> **Dove sta davvero il confine adesso.** Dopo questa cella il buco del confine e' 1,03 ms per
> token e **e' quasi tutto host non-CUDA**: 0,50 ms di campionamento/servizio/`set_inputs` piu'
> ~0,23 ms di code e attese residue. La fascia 5-20 µs **dentro** il grafo vale da sola **0,88 ms
> per token** — piu' del buco del confine — e nessuno l'ha ancora spiegata (§8.2). Sono quelli i
> due bersagli successivi, non le sincronizzazioni.

---

## 7. Difetti

1. **Niente campionamento della CPU.** nsys avverte che `--sample` e `--cpuctxsw` richiedono
   privilegi di amministratore e li disabilita. Gli 0,85 ms di host dentro il buco grande sono
   attribuiti per differenza e per esclusione (chiamate CUDA tracciate, micro-banco del pool QSA,
   lettura del codice), **non misurati direttamente**. Il blocco da 505 µs resta il pezzo meno
   scomposto di tutta la cella.
2. **Una sola cattura per lato**, come in P9, e nessuna replica del profilo. Le medie sono su 127
   forward puliti (prima) e 130 (dopo), non su una distribuzione. Le due catture vengono da due
   processi diversi in due momenti diversi: la differenza di parete fra loro (−0,107 ms) e' dello
   stesso ordine del guadagno che si vuole misurare, e infatti il conto della GPU inattiva
   (−0,201 ms) e quello della parete non coincidono. **La parte solida di §5 e' la scomposizione
   del buco riga per riga (§5.2), non i decimi di millisecondo di parete.**
3. **RAM disponibile minima sotto la soglia dei 4 GB in tre corse su quattro** (2,73 e 2,77 e 3,03
   GB; solo la replica 2 di V2 sta sopra, con 6,77). Sulle profilate pesa anche il profilatore. Il
   guaio vero e' che **il riferimento V1 e' una sola corsa, e sotto soglia**: il confronto di §4 e'
   fra una corsa V1 sotto soglia e due corse V2 di cui una sopra e una sotto. Le impronte sono
   identiche ovunque, quindi la scomposizione regge; **il delta di 0,154 ms no, non del tutto**.
   Rifare V1 a macchina libera chiuderebbe il punto e costa una corsa.
4. **L'attribuzione delle sincronizzazioni e' per contesto, non per stack**: si guarda la chiamata
   CUDA che precede sullo stesso filo. Le tre classi tornano con il codice riga per riga e i
   conteggi tornano con la struttura dei rami, ma non e' una prova diretta.
5. **L'identita' dello split CPU e' dedotta**, non letta da una tabella degli split: un solo
   `cudaGraphLaunch` dice che di split CUDA ce n'e' uno; `-ot` dice qual e' l'unico tensore forzato
   su host. La corsa «dopo» e' stata lanciata con `GGML_SCHED_DEBUG=1` apposta per avere la tabella
   degli split (`## SPLIT #n: BACKEND # k inputs`), ma **quelle righe non compaiono**: sono
   `GGML_LOG_DEBUG`, e nel percorso di log di questo server non arrivano ne' al file ne' a stderr.
   Il tentativo e' registrato, la prova diretta manca.
6. **La precondizione della correzione 1 e' un contratto nuovo per `ggml_backend_sched`**: chi usa
   `ggml_backend_sched_graph_compute_async` deve sincronizzare prima di riscrivere gli ingressi.
   Per llama.cpp e' garantita ed esplicita (§3.1), ma e' una condizione in piu' rispetto a upstream
   e va ricordata se un giorno la patch viene portata altrove.
7. **Il mio editor ha normalizzato i fine-riga** dei tre file (che li hanno misti) alla prima
   scrittura. Sono stati rimessi com'erano con `ripristina_fine_riga.py` e i binari sono stati
   **ricompilati dopo** il ripristino, cosi' la patch contiene solo le modifiche vere (208 righe,
   8 blocchi).

---

## 8. Aperture

1. **I 505 µs di host non scomposti** dentro il buco del confine sono ora la voce singola piu'
   grande di tutta la consegna fra grafo e host. Per aprirli serve o NVTX nel server o un
   contatore di fase a `ggml_time_us()` dietro interruttore. E' la prossima cella naturale.
2. **La fascia 5-20 µs vale 0,885 ms per token** e sta tutta **dentro** il grafo: 36 buchi da ~14 µs
   fra `concat_cont` e `k_get_rows_float_vec` (0,512 ms, tre per strato di attenzione), 11 fra
   `scale_f32` e `mul_mat_vec_f` (0,184 ms), 12 prima dell'istogramma del radix sort (0,119 ms).
   Sono nodi consecutivi dello stesso grafo sullo stesso stream: **non e' l'host**. E' piu' della
   somma dei due buchi del confine dopo questa cella, e non e' spiegato.
3. **Il buco 2 e il tempo di consegna del grafo** (`cudaGraphLaunch` dura 6,1 ms di tempo host per
   8.191 nodi, ~0,74 µs per nodo): e' l'argomento piu' forte a favore della leva 2 di P9 (fondere le
   catene `hc_`), perche' meno nodi vuol dire meno consegna, non solo meno lanci.
4. **La ri-cattura periodica del grafo** (7 forward su 134 nella finestra) costa un forward eseguito
   nodo per nodo piu' `cudaGraphInstantiate`. Amortizzata e' poca cosa (~0,005 ms/token) ma nessuno
   ha mai chiesto **perche'** le proprieta' dei nodi cambino: e' la cache degli esperti che muove i
   puntatori?

---

## 9. Bozza di voce di registro

> **15 settembre 2026 — fase P10, cella 2: i due buchi di inattivita' della GPU fra il grafo e
> l'host, e le 78 sincronizzazioni per forward.**
>
> *Ipotesi.* P9 aveva trovato 3,3 ms di GPU inattiva per token, due terzi dei quali in due buchi da
> ~1 ms sempre alla stessa fase, e 78 `cudaStreamSynchronize` per forward contro un solo
> `cudaGraphLaunch`. Se quelle attese sono di comodo — l'host che garantisce a mano un ordine che lo
> stream garantirebbe da solo — toglierle deve restituire quasi tutto il buco, senza toccare un bit
> del testo.
>
> *File toccati.* Motore, albero P8 `D:\ds4_work\p8_work\source` (3 file, 8 blocchi, 208 righe di
> diff): `ggml/src/ggml-backend.cpp` (ingressi di split copiati con `set_tensor_async` sullo stream
> del grafo, una sola sincronizzazione per split, dietro `GGML_SCHED_ASYNC_INPUTS`, default acceso),
> `ggml/src/ggml-cuda/ggml-cuda.cu` (il verdetto di `ggml_cuda_graph_check_compability` memorizzato
> per `uid`, dietro `GGML_CUDA_GRAPH_COMPAT_CACHE`, default acceso), `src/llama-context.cpp` (la
> precondizione resa esplicita: una sincronizzazione prima di `set_inputs`). Nuovi nel repository:
> `docs/porto/p10_token_singolo/P10_CELLA2_BUCHI_15_SETTEMBRE.md`, `p10_cella2.patch`,
> `buchi_p10.py`, `tabella_p10c2.py`, `avvia_p10_nsys.ps1`, `fai_patch_p10_c2.ps1`,
> `ripristina_fine_riga.py`, `copia_log_p10c2.py`, `log/`;
> `docs/porto/banco_p0/preset_V2_p10.json`. **Nessun commit.** `bin_prod`, `qwen38_clean\source`,
> `qwen38_clean\build\bin`, lanciatore quotidiano, modelli e snapshot P0 invariati. I binari esatti
> di V1 sono stati messi da parte in `D:\ds4_work\p8_work\bin_v1_p10` prima di ricompilare.
>
> *Configurazioni.* Punto operativo unico per tutte e quattro le corse: profilo `lungo_131k`,
> budget screening (1.024 token per caso), greedy seed 1234, ragionamento acceso, **MTP spento**,
> 64 slot, contesto 262.144, `-np 1`. `preset_V1_p10.json` (riferimento) e `preset_V2_p10.json`
> (candidato), che differiscono solo per i binari e per le due variabili dichiarate. Corse
> profilate sotto `nsys launch -t cuda --cuda-graph-trace=node` con la raccolta spenta e **una
> sola** finestra da 5 s aperta dentro il decode (la seconda cattura nella stessa sessione perde
> eventi: difetto 1 di P9).
>
> *Run validi / invalidi.* **Quattro corse, zero guasti, zero NaN, zero processi residui.** Due
> profilate (prima sui binari V1, dopo sui binari V2) e due al banco senza profilatore (V2 replica
> 1 e replica 2). **Impronte identiche al riferimento in tutte**: 4 su 4 per corsa, 16 su 16 in
> totale. Nelle catture, **i forward in cui il backend ri-cattura
> il grafo vanno scartati** (7 su 134 nel prima, 1 su 131 nel dopo): girano nodo per nodo con
> migliaia di `cudaLaunchKernel` e fanno fallire il controllo di integrita' geometrico. Aggiunto
> allo strumento il criterio del numero modale di kernel. RAM disponibile minima **sotto la soglia
> dei 4 GB in tre corse su quattro** (2,73 / 2,77 / 3,03 GB); **solo la replica 2 di V2 sta sopra**
> (6,77 GB). Il riferimento V1 e' una sola corsa e sta sotto soglia: dichiarato, non nascosto.
>
> *Risultato e limite.* **I due buchi non sono della stessa specie.** Il grande (1,267 ms per
> forward, uno per token) e' **il confine fra un forward e il successivo**: sta al nodo 0 del grafo
> CUDA, fra la testa di uscita del grafo N (`mul_mat_vec_q<q6_k>`, 1,74 ms) e il primo nodo del
> grafo N+1. Il piccolo (0,080 ms) e' **dentro** il replay, al nodo 45, e non contiene nessuna
> chiamata CUDA se non il `cudaGraphLaunch` ancora in corso: e' il driver che consegna 8.191 nodi
> piu' lentamente di quanto la GPU li consumi (la chiamata dura 6,1 ms di tempo host, ~0,75 µs per
> nodo). **Le 78 sincronizzazioni di P9 erano 43,61 al punto di partenza** (la leva B di P8 ne aveva
> gia' tolte ~34) e si dividono in tre classi: **1 necessaria** (l'attesa del forward, che e' attesa
> pura e si sovrappone alla GPU), **15,59** code bloccanti di una copia
> (`ggml_backend_cuda_buffer_set_tensor`), **27,02** svuotamenti della coda prima di un ingresso
> (`ggml_backend_sched_compute_splits`). **42,6 su 43,6 sono di comodo**, e la causa e' che le copie
> degli ingressi vanno su `cudaStreamPerThread` mentre il grafo gira sullo stream del contesto: due
> stream senza ordine fra loro, quindi l'ordine puo' essere garantito solo fermando l'host due volte
> per ingresso. **Le due correzioni funzionano e si vedono una per una**: sincronizzazioni
> **43,61 → 9,12** (le code bloccanti spariscono del tutto), copie migrate sullo stream del grafo,
> blocco delle copie **271 → 133 µs** con una sola attesa invece di 41, blocco di scansione dei
> nodi **174 → 5 µs**, buco del confine **1,267 → 1,031 ms**, GPU inattiva **2,801 → 2,600 ms**.
> **Ma al token arrivano solo −0,154 ms** (37,486 → 37,332 ms/token; 26,677 → 26,786 t/s, media di
> due repliche V2 che danno −0,078 e −0,230) e −0,107 ms di parete sotto profilatore. Misurato per
> la prima volta anche il **rumore fra repliche su `T1` a 131k: 0,152 ms** sull'aggregato e 0,268
> sul singolo caso — meno dei 0,5 ms che si davano per scontati, ma dello stesso ordine
> dell'effetto. **Tre ragioni, misurate**: (a) dei 1,267 ms del buco solo
> 0,415 erano chiamate CUDA, **0,852 erano host**, e 0,505 di quelli sono un blocco che questa cella
> non tocca (campionamento su 248.320 logit, risposta del server, `mctx->apply`, `set_inputs`);
> (b) **un quarto di quello che si toglie torna indietro**: il buco al nodo 45 cresce da 0,080 a
> 0,138 ms, perche' il grafo parte prima e il driver resta indietro; (c) quello che restava
> eliminabile era 0,31 ms lordi. Fatto collaterale: **i 2 split a bs=1 sono uno CUDA e uno CPU** —
> `-ot per_layer_token_embd.weight=CPU` tiene 26,8 GiB in un buffer host e `ggml_get_rows` su quel
> tensore finisce sul backend CPU; per forward c'e' un solo `cudaGraphLaunch`, quindi di split CUDA
> ce n'e' uno solo. Falsificata per strada una scorciatoia che sembrava ovvia: rendere incrementale
> il riempimento del pool QSA (quattro `std::fill` su `n_kv` piu' un doppio ciclo, rifatti da zero a
> ogni token) **vale solo ~0,105 ms**, misurati con un micro-banco fuori dal server, non le centinaia
> di microsecondi che sembravano. *Limiti*: niente campionamento della CPU (nsys lo disabilita senza
> privilegi di amministratore), quindi gli 0,85 ms di host sono attribuiti per differenza e non
> misurati; una sola cattura per lato; **il riferimento V1 e' una sola corsa e sta sotto la soglia
> di RAM**, quindi il delta di 0,154 ms non e' un confronto pulito quanto la scomposizione;
> l'identita' dello split CPU e' dedotta, non letta da una tabella degli split (il tentativo con
> `GGML_SCHED_DEBUG=1` non ha prodotto righe: sono `GGML_LOG_DEBUG` e non arrivano al log).
>
> *Decisione.* **Le due correzioni sono lossless e fanno quello per cui sono scritte, ma il cancello
> di adozione della cella (−0,5 ms/token) non e' raggiunto, e non lo e' per un fattore cinque.** La
> patch non costa nulla — nessun nodo in piu', nessun byte, nessuna VRAM, nessun rischio sul testo —
> e toglie 34,5 sincronizzazioni e ~0,24 ms di inattivita' per token: **si tiene accesa come igiene
> del percorso, ma non si conta come leva adottata** e non sposta il tetto di P9. **Il confine fra
> grafo e host non e' piu' un problema di sincronizzazioni: e' un problema di lavoro dell'host.**
>
> *Regressioni.* Nessuna. Impronte identiche 4/4 in tutte le corse (banco e profilate), stessi nodi
> di grafo, stessi split, stesso numero di kernel per forward, prefill invariato (251,75 → 251,65
> t/s, dentro il rumore), VRAM libera minima identica.
>
> *Stato dei processi.* Nessun `llama-server`, nessun `nsys`, nessuna sessione nsys, porta 8100
> libera, nessuna build in corso.
>
> *Prossima azione.* **Rifare V1 a macchina libera** (una corsa) per avere un riferimento sopra la
> soglia di RAM e chiudere il delta, ora stimato fra −0,08 e −0,23 ms. Poi:
> **i 505 µs di host non scomposti** dentro il buco del confine sono la voce
> singola piu' grande della consegna fra grafo e host: per aprirli serve NVTX nel server o un
> contatore di fase a `ggml_time_us()` dietro interruttore, ed e' una corsa, non un ciclo di
> sviluppo. Subito dopo, la **fascia 5-20 µs**, che vale **0,885 ms per token** — piu' del buco del
> confine dopo questa cella — e sta tutta **dentro** il grafo (36 buchi da ~14 µs fra `concat_cont`
> e `k_get_rows_float_vec`, tre per strato di attenzione): nodi consecutivi dello stesso grafo sullo
> stesso stream, quindi non e' l'host, e nessuno l'ha spiegata.

---

## 10. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/p10_token_singolo/P10_CELLA2_BUCHI_15_SETTEMBRE.md` | questo esito |
| `docs/porto/p10_token_singolo/p10_cella2.patch` | la patch, `diff -d` contro lo stato P8 cumulativo (3 file, 8 blocchi, 208 righe) |
| `docs/porto/banco_p0/preset_V2_p10.json` | preset della corsa V2 (JSON senza BOM) |
| `docs/porto/p10_token_singolo/buchi_p10.py` | l'analizzatore dei buchi e delle sincronizzazioni: confine dal `graphNodeId`, scarto dei forward ri-catturati, classifica delle sync |
| `docs/porto/p10_token_singolo/tabella_p10c2.py` | la tabella di confronto fra due corse del banco |
| `docs/porto/p10_token_singolo/avvia_p10_nsys.ps1` | la corsa profilata (guardia, `nsys launch`, una finestra, chiusura, sovrascrittura dell'ambiente per il prima/dopo) |
| `docs/porto/p10_token_singolo/fai_patch_p10_c2.ps1` | genera la patch dallo stato base conservato in `D:\ds4_work\p8_work\prove\p10_c2_base` |
| `docs/porto/p10_token_singolo/ripristina_fine_riga.py` | rimette i fine-riga originali sulle righe non toccate (difetto 7) |
| `docs/porto/p10_token_singolo/copia_log_p10c2.py` | porta in `log/` gli artefatti delle corse, chiave redatta |
| `docs/porto/p10_token_singolo/micro_qsa_p10.cpp` + `log/micro_qsa_risultato.txt` | il micro-banco che falsifica la leva del pool QSA incrementale: 103-105 µs, non centinaia (§3.3) |
| `docs/porto/p10_token_singolo/log/prima_V1_buchi.{md,json}` | anatomia dei buchi **prima** |
| `docs/porto/p10_token_singolo/log/dopo_V2_buchi.{md,json}` | anatomia dei buchi **dopo** |
| `docs/porto/p10_token_singolo/log/V2_*`, `V2r2_*`, `prima_V1_*`, `dopo_V2_*` | esito lato client delle quattro corse, estratti dei log del server, minimi di RAM/VRAM, argomenti con la chiave redatta |
| `docs/porto/p10_token_singolo/log/confronto_V1_V2.{md,json}` | la tabella di §4.1 |
| `docs/porto/p10_token_singolo/log/confronto_V2_r1_r2.{md,json}` | la replica di §4.1-bis (il rumore fra repliche) |
| `D:\ds4_work\p8_work\bin_v1_p10` | i binari esatti di V1, messi da parte prima di ricompilare |
| `D:\ds4_work\p8_work\prove\p10_c2_base` | i tre file del motore com'erano prima di questa cella |
| `D:\ds4_work\banco_p0_run\20260915_160208_P10_p10_c2_prima_v1` | corsa profilata **prima** (nsys 21 MB + sqlite 46 MB: non copiati nel repository) |
| `D:\ds4_work\banco_p0_run\20260915_163619_P10_p10_c2_dopo_v2` | corsa profilata **dopo** (nsys 21 MB + sqlite 57 MB) |
| `D:\ds4_work\banco_p0_run\20260915_162514_..._r1`, `..._165455_..._r2` | le due corse V2 al banco |
