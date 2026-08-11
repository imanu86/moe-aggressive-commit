# CACCIA ESTERNA — 11 agosto 2026

Caccia su letteratura, repo, fork e HuggingFace per i quesiti aperti del banco
**DS4-Flash IQ2_XXS (80,76 GiB, 43 strati, 256 esperti, 6/token) su RTX 3060 12 GB (sm_86)
+ 96 GB RAM**, sotto fork llama.cpp, Windows 11.

Banco verificato in loco durante la caccia:

| | |
|---|---|
| GPU | GeForce RTX 3060, 12288 MiB, **sm_86** |
| Driver | **596.21** |
| PCIe | **gen 4, x16** (max) |
| Toolkit CUDA installato | **12.6** (`nvcc release 12.6, V12.6.85`) |

Questi tre numeri decidono da soli metà dei verdetti qui sotto.

Regola di lettura del progetto: **ogni numero esterno vale solo insieme alla configurazione
che l'ha prodotto.** Un 2× su A100 con NVLink non dice niente su una 3060 PCIe 4.0 x16.

---

## SOMMARIO IN VENTI RIGHE

1. **Nessuno guida il motore di copia da una lista prodotta sul device.** Non è che gli altri
   l'hanno risolto meglio: **non esiste l'API**. L'unica primitiva NVIDIA in cui i parametri
   della copia sono *puntatori letti in ordine di stream* è `cuFileReadAsync` (GPUDirect
   Storage), ed è per il **disco**, su **Linux**. La strada è chiusa per tutti.
2. **La famiglia «stream memory ops» è chiusa proprio sul tuo banco**: `cuStreamWaitValue32` /
   `cuStreamWriteValue32` **richiedono TCC su Windows**, e una GeForce non può stare in TCC.
   Questo elimina d'un colpo il disegno «il device scrive un flag, lo stream aspetta».
3. **Quello che esiste davvero è il pattern proxy**: il device scrive descrittori in memoria
   host mappata con store fire-and-forget, un thread host pinnato fa polling ed emette la
   copia. È il meccanismo di NVSHMEM/NCCL GPU-initiated e di GICC. È **implementabile oggi**
   sul tuo banco, ed è la sola strada nota che dia «il device decide, il DMA esegue».
4. **Seconda strada aperta: i nodi condizionali dei grafi CUDA.** Il corpo di un nodo
   condizionale **può contenere nodi memcpy** e la condizione **si scrive da kernel**
   (`cudaGraphSetConditional`). IF/WHILE sono in **CUDA 12.4 → li hai**. Lo SWITCH a *n* rami,
   che è quello che servirebbe davvero, è **CUDA 12.8 → non lo hai** (ma il driver 596 basta,
   serve solo aggiornare il toolkit).
5. **Tutti gli altri sistemi evitano il problema spostando la decisione sull'host**, non
   spostando la copia sul device. ProMoE, MoE-Infinity, Klotski, Mixtral-offloading: predittore
   host → `cudaMemcpyAsync` host. ktransformers e Fiddler: non spostano l'esperto, spostano il
   *token* sulla CPU. leloch (llama.cpp): tiene `MUL_MAT_ID` **sulla CPU**, così la lista è
   host-side per costruzione.
6. **Il nostro `kern_copia` è, di fatto, l'unica implementazione esistente di trasporto deciso
   dal device.** Il prezzo — gli SM — è un prezzo che nessun altro paga perché nessun altro fa
   quella cosa. Siamo oltre lo stato dell'arte e ne paghiamo il conto.
7. **Upstream llama.cpp ha esattamente il nostro problema, e c'è una PR merged oggi**
   (#26802, 11 agosto 2026) che riduce il raggio del danno: i grafi CUDA non vengono più
   disabilitati per i MoE quantizzati, perché il percorso MMQ **non ha bisogno del sync**.
8. **C'è gente sul NOSTRO modello, adesso**: la RFC #24528 di llama.cpp è stata misurata da
   terzi **su DeepSeek-V4-Flash** → **+28…33% di decode** al 20% di copertura.
9. **vLLM ha già fatto il nostro confronto e ha scelto il DMA.** Kernel di copia custom contro
   `cudaMemcpyAsync`: il kernel vince sul piccolo, perde sul grande, e *«interferes with the model
   computation, as both utilize GPU cores»* — **a 0% di colpi dava il 6% in meno che non fare
   offload affatto**. La loro mossa vincente è stata **consolidare i blocchi a 0,5–2 MB e darli al
   DMA**: +5…15%.
10. **`cudaMemcpyBatchAsync` (CUDA 12.8) è la lista di descrittori che cercavi**, e il nostro
    quadrante è quello buono: **3,42× su H2D con elementi da 1 KB**. Ti serve solo aggiornare il
    toolkit da 12.6.
11. **Priorità di stream: ~0, per costruzione.** *«Blocks must retire for higher priority blocks to
    get scheduled.»* Il green context su sm_86 è legale (min 4 SM, multipli di 2) ma **NVIDIA
    dichiara che non è una partizione dura**, e servirebbero entrambi i lati in green context.
12. **Sul quesito 4 il campo ha un nome per il nostro problema**: «expert-set expansion». Il
    nostro 36% di sovrapposizione **non è anomalo, è ~15× la casualità** e in termini relativi
    è la località di routing più forte fra i numeri pubblicati.
13. **La conferma più preziosa**: nessuno dei lavori che guadagna, guadagna predicendo meglio.
    Il campo sta convergendo dove eravamo già arrivati.

---

# QUESITO 1 — LA LISTA È SUL DEVICE, LA COPIA LA GUIDA L'HOST

## 1.1 Inventario completo dei meccanismi NVIDIA, con verdetto per il nostro banco

| Meccanismo | CUDA min | Chi decide i parametri | Su sm_86 | Su Windows/WDDM | Ce l'hai (12.6)? | Verdetto |
|---|---|---|---|---|---|---|
| `cudaMemcpyAsync` | — | **host**, al momento della chiamata | sì | sì | sì | serve la lista sull'host |
| nodo memcpy in grafo | 10.0 | **host**, all'istanziazione | sì | sì | sì | parametri congelati |
| `cudaGraphExecMemcpyNodeSetParams` | 10.2 | **host**, fra i replay | sì | sì | sì | serve la lista sull'host |
| `cudaGraphNodeSetEnabled` | 11.6 | **host** | sì | sì | sì | idem |
| **device graph launch** | 12.0 | fissi all'istanziazione; il **device sceglie quale grafo** | *da verificare* | sì | sì | **selezione, non parametrizzazione** |
| **nodi condizionali IF / WHILE** | **12.4** | condizione scritta **dal kernel**; il corpo può contenere **memcpy** | sì | sì | **sì** | **APERTO** |
| nodi condizionali **IF/ELSE + SWITCH** | **12.8** | idem; SWITCH sceglie fra *n* sottografi | sì | sì | **no** | serve upgrade toolkit |
| `cudaMemcpyBatchAsync` | **12.8** | **host** | sì | sì | **no** | abbatte l'overhead di lancio, non sposta la decisione |
| stream memory ops (`cuStreamWaitValue32`, `cuStreamWriteValue32`, batch-memop node) | 8.0 | il device scrive il valore | — | **NO — richiede TCC** | — | **CHIUSO sul tuo banco** |
| `cuFileReadAsync` (GDS) | — | **`size` e `file_offset` sono PUNTATORI, letti in ordine di stream** | — | **NO — GDS è Linux** | — | l'unica primitiva «il device decide, il motore esegue»… e non è per la RAM |
| memcpy dentro un kernel | — | — | — | — | — | **non esiste, e non è mai esistito** |

### I due fatti decisivi

**(a) Le stream memory ops sono chiuse su Windows.** Dalla doc driver NVIDIA
([Stream Memory Operations](https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__MEMOP.html)):
il supporto si interroga con `CU_DEVICE_ATTRIBUTE_CAN_USE_STREAM_MEM_OPS`, e
*«the only requirement for basic support is that on Windows, a device must be in TCC mode»*.
Una GeForce non entra in TCC. Quindi tutto il disegno «kernel scrive il flag → lo stream di
copia lo aspetta» **non è realizzabile qui**, e non lo sarà finché resti su GeForce+Windows.
Questa è la porta che credo tu non sapessi fosse chiusa: sotto Linux sarebbe aperta.

**Da verificare sul banco in cinque minuti** (non l'ho potuto fare, serve compilare):
`cudaDeviceGetAttribute` con `cudaDevAttrGraphConditionalNodeSupport`,
`cudaDevAttrDeviceGraphLaunchSupport` (o l'equivalente driver
`CU_DEVICE_ATTRIBUTE_CAN_USE_STREAM_MEM_OPS`, che qui deve dare **0**), e `asyncEngineCount`.
La documentazione NVIDIA **non** pubblica il requisito di compute capability per device graph
launch né per i nodi condizionali: l'attributo di runtime è l'unica risposta affidabile.

**(b) I nodi memcpy dei grafi lanciati da device accettano ESATTAMENTE la nostra memoria.**
Dalla [CUDA Programming Guide, §CUDA Graphs](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html):

- *«The graph can only contain kernel nodes, memcpy nodes, memset nodes, and child graph nodes.»*
- *«Only copies involving device memory and/or **pinned device-mapped host memory** are permitted.»*

La nostra RAM esperti è pinnata e mappata sul device: è precisamente la categoria ammessa.
Ma subito dopo: *«Device graphs can only be updated from the host.»* Quindi **il device può
scegliere fra grafi preistanziati, non può comporre una copia nuova.** È un meccanismo
*combinatorio*, non *parametrico*. Ed è questa la frase che chiude il quesito 1 nella sua
formulazione originale.

## 1.2 Le due strade che restano aperte (e sono due, non zero)

### STRADA A — il proxy host (pattern NCCL/NVSHMEM). Implementabile OGGI, CUDA 12.6, Windows.

Non è un'idea mia: è il modo in cui la comunicazione GPU-initiated funziona in produzione
quando l'hardware non ha il percorso diretto.

- **[GPU-Initiated Networking for NCCL, arXiv 2511.15076](https://arxiv.org/html/2511.15076v1)** —
  il backend *Proxy* usa *«a dedicated CPU proxy thread per communicator, pinned to NUMA nodes
  near the local rank's GPU and NIC, which continuously polls queues. GPU threads enqueue
  operation descriptors — 64 bytes containing source/destination window handles, offsets, sizes
  and completion actions — into lock-free queues allocated in CPU memory using **fire-and-forget
  stores**.»*
- **[GICC, arXiv 2604.22126](https://arxiv.org/pdf/2604.22126)** — stesso schema, generalizzato.
- Il ramo «vero» (GPU scrive direttamente la doorbell del NIC, IBGDA) esiste **solo per la
  NIC**. Non esiste l'equivalente per il copy engine PCIe H2D.

**Trasposto al nostro caso.** Il kernel di top-k scrive la lista dei miss (expert_id, slot) in
un anello in memoria host mappata, con una sequenza monotòna; un thread host pinnato fa polling
sulla sequenza ed emette `cudaMemcpyAsync` (o `cudaMemcpyBatchAsync`, se sali a 12.8) su uno
stream di copia dedicato; il thread scrive poi un flag di completamento nella stessa memoria
mappata. Sul lato GPU la barriera **non** può essere `cuStreamWaitValue32` (vedi sopra): deve
essere un **kernel-cancello** che gira su un solo blocco e fa spin su quel flag via UVA. Un
kernel è catturabile in un grafo, quindi la cattura sopravvive.

Costi e rischi da mettere in conto, tutti misurabili sul banco:
- **1 blocco su 1 SM** occupato dallo spin (contro i 112 blocchi di `kern_copia` oggi — e il
  microbench dice già che a 8 blocchi si guadagna +5%);
- **latenza di sottomissione WDDM**: Windows batcha le sottomissioni; il thread proxy deve
  forzare il flush (`cudaStreamQuery`) e la latenza di andata-e-ritorno va misurata prima di
  costruirci sopra. È il rischio numero uno di questa strada;
- 43 giri per token (uno per strato) — a 50-100 µs di giro sono 2-4 ms, contro i 34 ms attuali,
  ma questo è **dedotto, non misurato**.

Il premio, se funziona: il trasporto passa al copy engine, gli SM tornano tutti al matmul, e i
34 ms di copia si sovrappongono al calcolo invece di rubarglielo.

**Nota d'onestà:** nessuno ha pubblicato questo pattern applicato al trasporto esperti H2D.
Il pattern è provato, l'applicazione no.

### STRADA B — i nodi condizionali dei grafi. Serve toolkit ≥ 12.8 per essere davvero utile.

Dal [blog NVIDIA sui conditional nodes](https://developer.nvidia.com/blog/dynamic-control-flow-in-cuda-graphs-with-conditional-nodes)
e dalla Programming Guide:

- IF e WHILE: **CUDA 12.4**. IF/ELSE e **SWITCH a n rami**: **CUDA 12.8**.
- *«The condition value can be set in a CUDA kernel by calling `cudaGraphSetConditional`.»*
- Il corpo di un nodo condizionale ammette *«kernel nodes, empty nodes, child graph nodes,
  memset nodes, **memcopy nodes**, nested conditional nodes»*.

Quindi **un kernel può decidere, dentro il grafo, se una memcpy H2D avviene o no**. Questo è
tanto quanto ci si può avvicinare. Il limite è che ogni possibile coppia (sorgente, destinazione)
deve esistere come nodo preistanziato: la combinatoria è 256 esperti × 512 slot, che non sta in
piedi. **Diventa praticabile solo se si rinuncia alla cache pienamente associativa**: con una
cache *direct-mapped* o a bassa associatività, la destinazione è funzione dell'expert_id e la
combinatoria collassa da 256×512 a 256×W. Con W=1 sono 256 nodi memcpy per posizione di
riempimento.

È un baratto vero e non gratuito: la nostra nota `prefetch-falsificato-sfratto-vale-23-punti`
dice che nessuna euristica implementabile batte la LRU, e una direct-mapped **perde** contro la
LRU per conflitti. Va simulato prima di scriverne una riga (regola `simulatore-router-sceglie-le-leve`):
**quanto costa in colpi passare da LRU-associativa a direct-mapped o 2-vie?** Se il calo di
colpi costa meno del 28% di SM che recuperi, la strada paga.

### STRADA C — non copiare affatto: fondere il gather dentro il matmul

Oggi sul percorso di miss paghiamo tre movimenti: leggi da host (PCIe) → scrivi in VRAM →
rileggi da VRAM nel matmul. A batch 1 ogni byte di peso serve **una volta sola**. Un matmul che
legge direttamente la memoria host mappata via UVA paga **solo il primo**. Non elimina il costo
SM, ma elimina scrittura e rilettura VRAM, e soprattutto elimina un kernel e una barriera.
La cache resta utile solo sui **colpi**.

Questa è la direzione in cui va anche upstream: PR #26802 (§ quesito 3) esiste proprio perché
il percorso **MMQ consuma gli `ids` sul device** e quindi non ha bisogno del sync host.

### STRADA D — spostare il top-k sulla CPU (la scorciatoia di leloch)

Se `MUL_MAT_ID` gira sulla CPU, la lista è host-side **per costruzione** e il problema
sparisce. È esattamente ciò che fa la RFC #24528, con numeri misurati sul nostro modello
(§ quesito 3). Costo: si rientra nel regime che la nostra nota
`cpu-nasconde-trasporto-inefficiente` ha già bocciato — la CPU assorbe lavoro e la cache smette
di vedere le domande. Da tenere come termine di paragone, non come piano.

## 1.3 Come lo risolvono gli altri: **non lo risolvono, lo aggirano**

| Sistema | Dove sta la decisione | Chi emette la copia | Nota |
|---|---|---|---|
| **ProMoE** ([2410.22134](https://arxiv.org/abs/2410.22134), [codice](https://github.com/promoe-opensource/promoe)) | predittore **host** | host, `cudaMemcpyAsync` | spezza ogni esperto in 3 chunk **non per banda ma per prelazione**: *«an ongoing copy operation cannot be preempted midway»* |
| **MoE-Infinity** ([repo](https://github.com/EfficientMoE/MoE-Infinity)) | tracce di attivazione, **host** | host | |
| **Mixtral-offloading** ([2312.17238](https://arxiv.org/html/2312.17238v1)) | LRU **host** | host | |
| **Klotski** ([2502.06888](https://arxiv.org/html/2502.06888)) | pipeline multi-batch, **host** | host | |
| **ktransformers** ([SOSP'25](https://madsys.cs.tsinghua.edu.cn/publication/ktransformers-unleashing-the-full-potential-of-cpu/gpu-hybrid-inference-for-moe-models/SOSP25-chen.pdf)) | gate su GPU | **non copia l'esperto**: manda il token alla CPU | *Expert Deferral* riordina gli strati perché il calcolo CPU si sovrapponga all'attenzione GPU |
| **Fiddler** ([2402.07033](https://arxiv.org/pdf/2402.07033)) | idem | idem | |
| **vLLM RFC #38256** ([issue](https://github.com/vllm-project/vllm/issues/38256), PR #37190) | tensore di mapping **sul device**, `slot_ids = mapping[topk_ids]` | **copie H2D sincrone**, host | richiede `--enforce-eager`: **niente grafi** |
| **llama.cpp RFC #24528** | `MUL_MAT_ID` **sulla CPU** | thread 0 della CPU | la lista è host-side per costruzione |

**Lo schema è universale e va detto chiaro: indicizzazione lato device, trasporto lato host.**
Nessuno, in nessuno di questi lavori, guida il motore di copia da una lista prodotta dal device.

## 1.4 Cosa NON esiste — l'elenco, perché è un risultato

1. **Non esiste** un'API per avviare un DMA da dentro un kernel. Confermato dalla doc CUDA e
   dal CUDA Handbook: SDMA si comanda **solo** con chiamate `Memcpy*()` **dall'host**.
2. **Non esiste** l'aggiornamento dei parametri di un nodo memcpy da codice device: *«Device
   graphs can only be updated from the host.»* L'aggiornamento device-side dei parametri
   introdotto in CUDA 12.4 riguarda i **nodi kernel**.
3. **Non esiste** un `cudaMemcpyAsync` i cui puntatori siano letti al momento dell'esecuzione…
   **tranne una eccezione**: `cuFileReadAsync`, dove `size` e `file_offset` sono passati **come
   puntatori** e valutati in ordine di stream. È la prova che NVIDIA *sa* fare questa cosa —
   ma l'ha esposta solo per **storage→GPU**, solo su **Linux**, solo con **GDS**.
   ([cuFile API Reference](https://docs.nvidia.com/gpudirect-storage/api-reference-guide/index.html))
4. **Non esiste** un lavoro pubblicato che guidi il copy engine H2D da una lista device-side per
   il trasporto esperti MoE. Zero risultati su arXiv, GitHub e forum NVIDIA.

**Conclusione del quesito 1:** la strada che avevi in mente non è chiusa solo per te. È chiusa
per tutti, per assenza di API. Restano tre aggiramenti (proxy host, condizionali, fusione) e
uno solo è implementabile stasera senza aggiornare nulla: **il proxy host**.

---

# QUESITO 3 — L'UPSTREAM DI LLAMA.CPP

## 3.1 Il reperto che conta più di tutti: la RFC #24528

**[ggml-org/llama.cpp Discussion #24528](https://github.com/ggml-org/llama.cpp/discussions/24528)** —
*«RFC: MoE expert cache, VRAM caching of hot CPU-resident experts with hybrid hit/miss execution»*,
autore **leloch**. Nasce dalla PR **[#24524](https://github.com/ggml-org/llama.cpp/pull/24524)**,
chiusa il 12 giugno 2026 da am17an **non per motivi tecnici** ma per violazione delle linee guida
(due backend in una PR, 2.222 righe, disclosure di codice generato da IA). Nessuna revisione
tecnica è stata fatta. Filoni precedenti: #20757, #21609, #21614, #21620, #23170 — tutti falliti
con **regressioni sul decode da trasferimenti PCIe sincroni**.

**Il disegno inverte l'approccio**: tiene `MUL_MAT_ID` **sulla CPU**; dentro il kernel CPU, il
thread 0 spedisce alla GPU le righe degli esperti in cache tramite un buffer VRAM persistente,
mentre gli altri thread calcolano i miss normalmente.

**Configurazione dell'autore**: 4× RTX 3090, EPYC 7R13 48 core, 256 GB DDR4-3200 8 canali,
`llama-bench tg300`.

| Modello | cache | vanilla | Δ |
|---|---|---|---|
| GLM-5.1 754B IQ2_M | 17,49 t/s | 13,96 t/s | **+25%** |
| Qwen3.5 397B Q3_K_XL | 30,25 t/s | 28,18 t/s | +7% |
| 13 modelli / 9 architetture, offload forzato | — | — | da +10% a +57% |

**E qui la parte che ci riguarda direttamente — validazione indipendente sul NOSTRO modello:**

- **noonghunna** (2× RTX 3090, DDR4 8 canali), **su DeepSeek-V4-Flash**: **+28…+33% di decode**
  al **20% di copertura**. E riporta che **il tasso di colpi cresce linearmente fino al ~31% di
  copertura**, senza saturare presto — cioè il contrario della previsione «basta un pool piccolo».
- **xashr** (RTX 5090, 128 GB DDR5), Laguna S 2.1 e DeepSeek V4: **+21…+52% TG**, ma
  **−14%…−66% di prefill** a seconda di mmap e streaming da disco.

Dettagli tecnici da rubare, misurati da loro:
- **il 10% degli esperti prende l'80-81% dei colpi** (il loro modello, non il nostro: la nostra
  nota `non-esiste-nucleo-caldo` dice il contrario per DS4 — **da verificare chi ha ragione su
  quale modello**);
- **impacchettamento delle copie H2D**: noonghunna misurava **due operazioni H2D per dispatch**;
  il dispatch impacchettato le ha portate a una, **eliminando ~40.596 operazioni** in tracce
  appaiate. Questo è parente stretto delle nostre **277 copie per token**;
- **la cache serve solo batch ≤ 8**; i ubatch di prefill la bypassano del tutto;
- **speculativo**: si compone (GLM-5.2 **+64,9%** in pila con MTP) **ma richiede un drafter
  residente su CPU** — un drafter su GPU impedisce l'ingaggio della cache per via del riordino
  device nel percorso shared-draft. Ci riguarda: il nostro drafter dove sta?
- ammissione adattiva con `GGML_CUDA_MOE_CACHE_ADMIT_AFTER`; ~1.700 righe in `moe-cache.cu/.cuh`;
  hot-set persistente su disco in `~/.cache/llama.cpp/`.
- **la priorità di stream è stata provata e scartata.** Vale la pena leggere il perché prima di
  rifarlo noi (rilevante per il quesito 2).

## 3.2 Che cosa è ENTRATO (merged) che potremmo non avere

| PR | Titolo | Autore | Merge | Perché ci riguarda |
|---|---|---|---|---|
| **[#26802](https://github.com/ggml-org/llama.cpp/pull/26802)** | CUDA: only disable CUDA graphs when `mul_mat_id` actually needs a stream sync | grafail | **11 ago 2026** (commit `ebb546b`) | **Il quesito 1 visto da upstream.** Prima i grafi CUDA erano disabilitati per *qualunque* modello con un nodo MUL_MAT_ID non quantizzato o oltre il limite di batch MMVQ. Ora un predicato replica esattamente il dispatch e disabilita i grafi **solo quando il fallback sincronizzante gira davvero**. I percorsi **MMQ** (quantizzato) e **MMF** (float) **non hanno bisogno del sync**: consumano gli `ids` sul device. Numeri: RTX 5090 / CUDA 13.3, Qwen3-30B-A3B Q4_K_M **+13% a npl=16**, +8% a npl=32; LFM2-8B-A1B bf16 357,17 → 374,34 t/s (+5%). Nessuna regressione su GLM-5.2 753B a batch 1. |
| **[#16991](https://github.com/ggml-org/llama.cpp/pull/16991)** | CUDA: add stream-based concurrency | am17an | 30 nov 2025 | Stream CUDA concorrenti su **singola GPU** per il ramo Q/K/V, con `cudaStreamWaitEvent` a fork e join. **Funziona solo se i grafi CUDA sono attivi** e solo a batch 1. Gate: `GGML_CUDA_GRAPH_OPT=1` → poi `GGML_CUDA_DISABLE_GRAPH_OPT`. RTX 5090: gpt-oss-20B MoE 1,06×, Qwen3-30B MoE 1,09×, Llama-8B Q8_0 1,05×; RTX 4090 Qwen3-30B MoE 1,08×. **È il precedente diretto per separare trasporto e calcolo su stream distinti.** |
| **[#18535](https://github.com/ggml-org/llama.cpp/pull/18535)** | ggml: add env var `GGML_OP_OFFLOAD_MIN_BATCH` | DocShotgun | 8 gen 2026 | Rende configurabile la **soglia di batch che innesca l'op-offload dello scheduler** — cioè proprio il ramo `ggml-backend.cpp` che ci emette 221.963 `cudaMemcpyAsync`. Default **32**. Su RTX 4090 + 7950X: soglia 50.000 (offload spento) 146,81 T/s contro soglia 32 (acceso) 2.322,76 T/s — in **prefill**. **Manopola da provare subito**: il nostro batch speculativo è 2, quindi sotto soglia; il ramo di fallback che ci fa male è un altro, ma la variabile permette di isolarli. |
| **[#24162](https://github.com/ggml-org/llama.cpp/pull/24162)** | DeepSeek V4 | am17an | 29 giu 2026 | Supporto upstream del nostro modello: CSA e HCA, `comp_plan` costruito dal contesto ed eseguito su GPU, due `llama_kv_cache` aggiuntivi non unificati, ISWA per-strato, riuso del grafo attraverso i confini di compressione. **DGX Spark, 284B, IQ2_XXS: pp ~148 t/s, tg ~6 t/s.** Post-merge: bachi di context caching (#25259, #25382, #25468, #25530). |
| **[#25784](https://github.com/ggml-org/llama.cpp/pull/25784)** | DeepseekV4 MTP + DSpark | am17an | 2 ago 2026 | **DSpark upstream.** Da confrontare riga per riga con la nostra composizione (nota `dspark-composizione-vera`). |
| **[#26452](https://github.com/ggml-org/llama.cpp/pull/26452)** | convert: add option to create separate dspark GGUF | am17an | 2 ago 2026 | |
| **[#26458](https://github.com/ggml-org/llama.cpp/pull/26458)** | common: support the DSpark sidecar resolution | ServeurpersoCom | 2 ago 2026 | |
| — | cuda: add `sqrt_softplus` in topk-moe for dsv4 | am17an | 21 lug 2026 | fusione topk-moe estesa a DS4 |
| — | Enable CUDA graphs on Volta+Turing | heislera763 | 16 lug 2026 | i grafi si stanno allargando, non restringendo |
| [#13386](https://github.com/ggml-org/llama.cpp/pull/13386) | `--no-op-offload` | hjc4869 | 11 mag 2025 | l'interruttore originale dell'op-offload |
| [#18148](https://github.com/ggml-org/llama.cpp/pull/18148) | llama: offload output layer to GPU first | JohannesGaessler | 18 dic 2025 | |

## 3.3 Che cosa è stato PROVATO E RITIRATO — la lezione più utile

**[#20793](https://github.com/ggml-org/llama.cpp/pull/20793)** *«Sched: Reintroduce less
synchronizations between token»* (aendk, merged 26 giu 2026) →
**[#25138](https://github.com/ggml-org/llama.cpp/pull/25138)** revert (ORippler, 30 giu 2026).

Eliminava le sincronizzazioni superflue fra copie H2D e grafo, passando da uno schema
`sassassg` a `saaasg` con `ggml_backend_cuda_cpy_tensor_async()`.

- **Su NVIDIA (RTX 4090): ~1%.** Perplessità identica.
- **Su AMD/HIP: −35% di prefill su modelli densi (tre R9700), fino a −50% su più ISA** → issue
  #25062 → revert. Verdetto del maintainer: *«We definitely should not be breaking HIP
  performance like this for a few % on other»* platform.

**Perché ci riguarda molto.** La nostra nota `join-73-percento-finestra-uno-split` dice che il
join è il 73,4% del tempo e che sovrapponendo la finestra si prende **+50%**. Upstream ha
attaccato la *stessa area di codice* e ha raccolto **1%** su una 4090. La differenza non è che
si sbagliano: è che **il loro regime non è il nostro** — 4090 con tutto residente contro 3060 con
metà modello in RAM. **Questo è il precedente che rende la nostra leva credibile e insieme
spiega perché nessuno l'ha ancora presa**: nel regime in cui la comunità misura, non c'è.

## 3.4 Che cosa è in volo e non è entrato (il fronte caldo, agosto 2026)

| PR/Issue | Titolo | Autore | Stato | Nota |
|---|---|---|---|---|
| [#26322](https://github.com/ggml-org/llama.cpp/pull/26322) | CUDA: add MOE_FFN | am17an | **draft** | kernel unico per tutta la FFN MoE: router GEMV/GEMM + top-k + softmax + gate/up + SwiGLU + down, con `quantize_scatter_mmq` e scale ordinate. **EPYC 7742, Qwen 35B MoE Q4_K_S: prefill +8% (11,4→12,3 t/s) e +10% (12,7→14,0 t/s).** Ma **rompe l'offload parziale: 7 t/s → 0,7 t/s** e OOM inattesi. È il nostro caso d'uso, quindi da seguire. |
| [#26160](https://github.com/ggml-org/llama.cpp/pull/26160) | cuda: fuse MoE expert weighting and reduction (+3%…+9% prefill) | coder543 | chiusa, non merged | |
| [#26003](https://github.com/ggml-org/llama.cpp/pull/26003) | llama: add `--lazy-experts` for MoE models larger than RAM | pwilkin | aperta | |
| [#26414](https://github.com/ggml-org/llama.cpp/pull/26414) | llama-hot-experts: pin hottest MoE experts in RAM via `--pin-hot-experts` | Ghimli | aperta | parente della nostra pin-by-mass |
| [#26563](https://github.com/ggml-org/llama.cpp/pull/26563) / [#26824](https://github.com/ggml-org/llama.cpp/pull/26824) | Expert caching + heatmap, mmap pinning based on heatmap | miltos22 | entrambe chiuse | terza squadra indipendente sullo stesso problema |
| [#26294](https://github.com/ggml-org/llama.cpp/pull/26294) / [#26295](https://github.com/ggml-org/llama.cpp/pull/26295) | CUDA: fix duplicate expert id compaction in `mul_mat_id` | Nas01010101 | aperta / chiusa | **da guardare**: gli id duplicati nel top-k toccano il conteggio dei nostri miss |
| [#20757](https://github.com/ggml-org/llama.cpp/issues/20757) | Two-tier GPU+RAM expert cache (pluggable eviction) | e1n00r | aperta, mai implementata | RTX PRO 2000 8 GB, GPT-OSS-120B (128 esperti/strato, 36 strati, ~57 GB): freddo 1,9-2,5 t/s @48-56% colpi → **regime 12-14 t/s @98-100%**, contro 0,5-1 t/s di puro offload CPU. Propone **SLRU** con ammissione a frequenza (*ammetti al secondo miss*): **+8-15 punti** di colpi a regime sulla LRU semplice, perché *«il prefill attiva tutti gli esperti in distribuzione piatta e ripulisce il buffer di slot»*. Il nostro `prefetch-falsificato` dice che SLRU non batte la LRU **da noi** — regimi diversi, ma l'argomento «proteggere dal prefill all'ammissione, non allo sfratto» merita un giro di banco. |
| [#25089](https://github.com/ggml-org/llama.cpp/pull/25089) | sycl: allow graphs for MoE decode (MUL_MAT_ID fused path) | Captain-Tripps | aperta | stessa patologia sul backend SYCL |

## 3.5 Fuori da llama.cpp

**[vLLM RFC #38256](https://github.com/vllm-project/vllm/issues/38256)** (e1n00r, PR #37190,
~980 righe Python). Astrazione `ExpertWeightProvider`; esperti in **pinned CPU memory**; cache
GPU a slot fissi con sfratto **LFRU**; **tensore di mapping persistente sul device**
`[num_experts] → slot_index`, aggiornato in loco, e i router output rimappati **dentro il grafo**:
*«slot lookup is pure indexing (`slot_ids = mapping[topk_ids]`)»*, sullo schema delle block table
della KV cache. Niente sync host sul top-k: **deduplica agli id unici e carica ognuno una volta.**
Ma: **copie H2D sincrone** nella PR 1, e **richiede `--enforce-eager`** (niente grafi).
Banco: RTX PRO 2000 8 GB, GPT-OSS-20B MXFP4, decode **30 tok/s**, colpi 97-100%.

L'idea da rubare è la **tabella di rimappatura residente sul device**: rende
l'*indicizzazione* graph-safe. È la metà del problema che si può chiudere senza inventare nulla.

**ik_llama.cpp** ha una pagina dedicata all'inferenza ibrida CPU/GPU; il fork è il posto dove
guardare per le varianti di quantizzazione e di `-ot`. (Rimasto fuori dal budget di questa
caccia: vale un giro dedicato.)

---

# QUESITO 4 — SPECULAZIONE E RESIDENZA

## 4.1 Sì, esiste, e ha un nome: **expert-set expansion**

Otto lavori negli ultimi otto mesi. Il paragrafo di apertura di **AcceptMoE**
([2608.02989](https://arxiv.org/abs/2608.02989)) è quasi il nostro appunto interno:

> «Token count, activated-expert union size, and expert-weight traffic are therefore distinct
> cost measures: reducing the token workload need not shrink the expert union proportionally.»

**I tre numeri concreti sull'unione che esistono in letteratura:**

| Fonte | Misura | Numero |
|---|---|---|
| AcceptMoE, Qwen3-30B-A3B | disaccoppiamento token↔esperti | EVICT taglia il **74,7% dei token verificati** ma solo il **32,5% degli esperti attivati** |
| **MoE-Spec** [2602.16052](https://arxiv.org/html/2602.16052v1), OLMoE 64 esperti top-8 | unione vs taglia dell'albero | albero 31 → **39** esperti unici; 63 → **48**; 255 → **54** su 64. **Satura.** |
| **DraftExpert** [2607.24434](https://arxiv.org/abs/2607.24434), DeepSeek-V2-Lite / Moonlight | costo verifica K token vs 1 token AR | **2,35–3,10×**; con troncamento per confidenza **1,48–1,70×**; col prefetch **1,25–1,40×** |

Traffico H2D pubblicato da AcceptMoE (l'unica tabella del genere in letteratura):

| Modello | SD standard | AcceptMoE | Δ |
|---|---|---|---|
| Qwen3-30B-A3B-Instruct | **2394 MiB/token** | 633 MiB/token | −73,6% |
| Qwen3-Coder-30B-A3B | 2025 MiB/token | 464 MiB/token | −77,1% |
| GPT-OSS-120B | 1243 MiB/token | 298 MiB/token | −76,0% |

Per riferimento: **noi siamo a 832 MiB/token**.

## 4.2 Il nostro 36% non è anomalo: è ~15× la casualità

Baseline casuale della sovrapposizione fra token consecutivi: **E = K²/N**
([2606.15453](https://arxiv.org/html/2606.15453)).

| Configurazione | N, K | casuale | misurata | rapporto |
|---|---|---|---|---|
| Mixtral | 8, 2 | **25%** | ~30% ([2511.05814](https://arxiv.org/html/2511.05814)) | ~1,2× |
| vari LLM | vario | K²/N | ~2× la casuale | ~2× |
| **DS4-Flash (noi)** | **256, 6** | **2,34%** | **36%** | **~15×** |

**Il nostro 36% è, in termini relativi, la località di routing più forte fra i numeri
pubblicati.** È basso in assoluto solo perché con 256 esperti a grana fine la baseline è 2,3%:
chi ha 8 esperti parte da 25% gratis.

Il riferimento da leggere è **«Not All Models Suit Expert Offloading: On Local Routing
Consistency of Mixture-of-Expert Models»** ([2505.16056](https://arxiv.org/html/2505.16056v3),
[codice e tracce](https://github.com/ljcleo/moe-lrc)). Due cose loro che ci colpiscono in pieno:

1. **gli shared expert PEGGIORANO la consistenza di routing** — *«all models in groups 1 and 2 do
   not use shared experts»*. DeepSeek li ha. DeepSeekMoE sta a SRP 36,94, DeepSeek-V2-Lite 37,92,
   contro 78,16 di LLaMA-MoE-v2 e 49,36 di Mixtral;
2. **una cache pari a 2× i parametri attivi dà il miglior segment caching su quasi tutti i
   modelli**. Per noi 2× = **516 slot. Ne abbiamo 512.** Cioè: **siamo già esattamente al punto
   raccomandato dalla letteratura, e questo è il miglior argomento esterno a favore della nostra
   nota `capienza-non-paga-colpi-non-valuta`.**

**Aritmetica sull'unione K-token (derivata, non misurata da loro):** 258 attivazioni/token; col
36% ogni token in più aggiunge 6×0,64 = 3,84/strato = 165; unione(K) ≈ 258 / **423** / 588 / 753.
Con 512 slot: **K=2 entra, K=3 no.** Il nostro dato interno (764 a W=5 contro 918 lineari)
conferma la saturazione che MoE-Spec misura.

Per contesto: AcceptMoE gestisce lo sforamento col **wave partitioning** a **48 slot per strato
su 128 esperti = 37,5% di residenza**. La nostra residenza è **512 / (43×256) = 4,6%**.
**Siamo in un regime otto volte più affamato di qualunque cosa pubblicata.**

## 4.3 Chi vincola cosa — e nessuno peggiora l'accettazione

| Lavoro | Cosa vincola | Costo in qualità | Hardware |
|---|---|---|---|
| **AcceptMoE** [2608.02989](https://arxiv.org/abs/2608.02989) | **ammissibilità dell'esperto condizionata alla residenza in cache** | −0,27 punti medi su 12 coppie | RTX PRO 6000 Blackwell; **RTX 5090 32 GB** per l'offload |
| **EcoSpec** [2607.12696](https://arxiv.org/abs/2607.12696) | scelta dei token di bozza per costo marginale in esperti nuovi | −0…−2,6% di lunghezza accettata | 8× H200, **tutto in HBM** |
| **MoE-Spec** [2602.16052](https://arxiv.org/abs/2602.16052) | budget fisso B di esperti per strato | −3 punti GSM8K; τ −1,4% | A100 80 GB, FP16, in HBM |
| **EVICT** [2605.00342](https://arxiv.org/abs/2605.00342) | tronca il prefisso dell'albero | dichiarato lossless | A100 80 GB, niente offload |
| **DraftExpert** [2607.24434](https://arxiv.org/abs/2607.24434) | drafter a **impronta fissa** | accettazione **sale** 23%→83-87% | **RTX 4090 24 GB** + Snapdragon 8 Elite |

**Il campo è unanime: restringi l'unione, non K.** L'ipotesi «peggioro l'accettazione per stare
in cache» non è mai stata pubblicata da nessuno.

**Il reperto più trasferibile è AcceptMoE**: *se non è residente, il bersaglio non lo usa*.
Paga 0,27 punti, vale **2,06×** in offload e **−73,6…−77,1% di traffico H2D**. Ed è l'unico che
riduce il **numero di miss**, cioè l'unico che passa il filtro della nostra nota
`transport-identity-non-vram-full-copy`.

**DraftExpert** è il più vicino come hardware (4090, batch 1, single-user): DeepSeek-V2-Lite
CPU→GPU **2,19 → 2,99 t/s (1,36×)**; Moonlight 1,94 → 2,50 (1,29×). Riscrive l'unità di merito
da «token accettati per forward» a **«token accettati per esperto nuovo caricato»** — che è
esattamente la valuta giusta secondo il nostro modello di costo.

---

# QUESITO 2 — LA COPIA CHE RUBA CALCOLO

**In tre righe:** la priorità di stream **non separa gli SM, per costruzione e non per bug**; il
green context su sm_86 esiste sulla carta ma **NVIDIA scrive che non è una partizione dura** e il
contesto primario continua a girare sugli SM riservati; **la strada aperta su Windows è togliere
la copia dagli SM e darla ai copy engine**, e `cudaMemcpyBatchAsync` (CUDA 12.8) è esattamente
l'API a lista di descrittori.

## 2.1 Il precedente che vale più di tutti: vLLM ha già fatto il nostro confronto

**[vLLM — KV Offloading Connector, gennaio 2026](https://vllm.ai/blog/2026-01-08-kv-offloading-connector)**
— H100 80 GB HBM3, Xeon SapphireRapids 2,1 GHz (8 core). Hanno confrontato *esattamente* le due
opzioni che ci dividono:

- **kernel di copia custom**: migliore sui **blocchi piccoli**, varianza più alta;
- **DMA (`cudaMemcpyAsync`)**: migliore sui **blocchi grandi**;
- bidirezionale a blocchi da 2 MB: **DMA 83,4 GB/s contro 68,5 GB/s del kernel custom**;
- e la frase che è la nostra diagnosi scritta da altri: *«the custom kernel approach interferes
  with the model computation, as both utilize GPU cores»* — **a 0% di colpi il kernel custom dava
  il 6% di throughput IN MENO che non fare offload affatto.**

**Decisione finale loro**: DMA + **ridisegno del layout per portare i blocchi fisici da kilobyte a
0,5–2 MB contigui** → **+5…+15%** di throughput concorrente a latenza comparabile.

→ Se il kernel custom vince sul piccolo e perde sul grande, e i nostri pezzi sono piccoli e tanti,
la mossa non è «kernel contro DMA»: è **consolidare i pezzi e poi darli al DMA**.

Conferma quantitativa in letteratura — **ConCCL**
([arXiv 2412.14335](https://arxiv.org/abs/2412.14335)), sulla frazione dello speedup ideale
raggiunta:

| Strategia | % dello speedup ideale |
|---|---|
| concorrenza calcolo/comunicazione naive | **21%** |
| + prioritizzazione dello schedule + partizionamento SM | **42%** |
| + comunicazione offloadata ai **DMA engine** | **72%** (fino a 1,67×) |

**Il partizionamento SM raddoppia; l'offload al DMA quasi quadruplica.** È l'argomento più forte
trovato sull'ordine delle priorità, e dice che stiamo guardando la manopola secondaria.

## 2.2 `cudaMemcpyBatchAsync` — la lista di descrittori esiste, e il nostro è il quadrante buono

[CUDA 12.8 release notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html):
*«Added batch CUDA asynchronous memory copy APIs (`cuMemcpyBatchAsync` and `cuMemcpyBatch3DAsync`)»*.

```c
cudaError_t cudaMemcpyBatchAsync(const void** dsts, const void** srcs,
                                 const size_t* sizes, size_t count,
                                 cudaMemcpyAttributes* attrs, size_t* attrsIdxs,
                                 size_t numAttrs, cudaStream_t stream);
```

**Numeri misurati** ([forum NVIDIA](https://forums.developer.nvidia.com/t/cudamemcpybatchasync/360302),
CUDA 12.8, pool 16 GB, 1 GB per corsa):

| Direzione | elementi da 1 KB | … | elementi da 32 MB |
|---|---|---|---|
| **H2D** | **3,42×** | decrescente | 1,0× |
| D2D | ~1,0× | ~1,0× | ~1,0× (limite noto) |

**Tante copie H2D piccole è precisamente il nostro caso**: le 277 copie per token del ledger sono
l'input naturale di questa API — **una chiamata, N copie, zero SM**. Nessuna restrizione di
piattaforma documentata: è una feature del driver usermode, quindi disponibile su Windows.
**Serve CUDA ≥ 12.8: tu hai 12.6.** Il driver 596.21 è ampiamente sufficiente, serve solo il
toolkit. Esiste anche `cudaMemcpy3DBatchAsync` per copie 2D/3D con stride, utile se il layout di
un esperto è regolare.

## 2.3 Priorità di stream — non fa quello che sembra

Robert Crovella (NVIDIA), [forum](https://forums.developer.nvidia.com/t/questions-of-cuda-stream-priority/250343/4):
*«The guaranteed behavior is that the CWD (block scheduler) will preferentially choose blocks from
higher priority streams, **when depositing new blocks on SMs**»*; e sulla prelazione: *«The CWD/GPU
may use preemption, but it is not guaranteed. In english, may does not mean must or will.»*

Nel [thread sulla prelazione](https://forums.developer.nvidia.com/t/how-high-priority-stream-preemption/78183/4)
la frase è netta — **«Blocks must retire for higher priority blocks to get scheduled»** — e il
controesempio citato è letteralmente il nostro: un kernel a grid-stride-loop dimensionato per
massimizzare l'occupancy **impedisce** a un blocco più prioritario di entrare.

**`kern_copia` è lungo (34 ms) e residente: una volta depositati i suoi blocchi, nessuna priorità
li sfratta.** La leva che stai già usando — 8 blocchi invece di 112 — è lo stesso meccanismo preso
dal lato giusto: non chiedi al depositore di preferirti, gli lasci gli SM liberi in partenza.

**Aggravante Windows.** Crovella: *«If you are working on a GPU in Windows WDDM driver mode,
complex concurrency scenarios are very hard to arrange»*. E in
[NVIDIA/cccl #6925](https://github.com/NVIDIA/cccl/discussions/6925) (RTX 5090, Windows 11, CUDA 13.0)
un ingegnere NVIDIA risponde: *«there are certain limitations of WDDM that make it incompatible
with PDL and stream workloads. **It should be supported in CUDA graphs.**»*
Il motivo è il batching in command buffer: **solo il lavoro sottomesso nello stesso command buffer
può girare concorrente**; `cudaEventQuery(0)` forza il flush della coda software.

→ **NVIDIA indica i CUDA Graphs come LA via per la concorrenza su WDDM.** Che è anche la via per
far sparire le sottomissioni per token che abbiamo già a ledger.

E per completezza: **leloch (RFC #24528) ha provato la priorità di stream e l'ha scartata.**

## 2.4 Green context / partizionamento SM — legale su sm_86, ma non isola

**La doc dice che sm_86 è supportato.**
[CUDA Driver API — Green Contexts](https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__GREEN__CONTEXTS.html),
requisiti di `cuDevSmResourceSplitByCount`:

| Compute capability | minimo SM | vincolo |
|---|---|---|
| 7.x | 2 | multiplo di 2 |
| **8.x (noi)** | **4** | **multiplo di 2** |
| 9.0+ | 8 | multiplo di 8 |

Sulla 3060 (28 SM) i tagli 4/24, 6/22, 8/20 sono legali. `CU_DEV_RESOURCE_TYPE_SM` è l'unico tipo
supportato. Driver API in **CUDA 12.4** (→ ce l'hai), runtime API in **CUDA 13.1**. Nessuna
restrizione documentata per GeForce né per Windows.

**Ma NVIDIA scrive nero su bianco che non isola:** *«it is not guaranteed that the kernels launched
in them will run concurrently»*; *«it is possible for the workload to run on more SMs than was
provisioned (but never less)»*; *«Even when different SM resources and work queues are provisioned
per green context, concurrent execution of independent GPU work is not guaranteed.»*

**Il reperto che chiude la questione, misurato con `%smid`**
([forum NVIDIA](https://forums.developer.nvidia.com/t/green-context-sm-provisioning-vs-the-primary-context/377440),
**RTX 5060 Ti sm_120, 36 SM, Linux, CUDA 12.8, driver r570**): green context da 8 SM con lavoro
latency-critical a 60 Hz, carico pesante nel **contesto primario** → p95 da **0,59 ms a 2,97 ms**,
max 5,25 ms. Strumentando `%smid`: **i kernel del contesto primario giravano su tutti e 36 gli SM,
inclusi gli 8 riservati.** Spostando il carico pesante in un **secondo green context** (28 SM):
impatto **+1 µs p50**. Risposta NVIDIA: *«Green contexts reserve a minimum SM count […] but they
do not create a hard partition at the warp-dispatch level. A long-running primary-context grid can
occupy the same physical SMs until it yields.»*

**Traduzione per il nostro fork: servono ENTRAMBI i lati in green context**, e llama.cpp gira tutto
nel contesto primario. È un refactor del backend CUDA, non una patch. In più c'è un bug aperto dal
12.4: **cuBLAS non rileva correttamente il numero di SM** sotto green context (workaround
`cublasSetSmCountTarget()`).

**E anche partizionando, il 28% non torna tutto indietro.** Su
[RTX PRO 4000 Blackwell](https://forums.developer.nvidia.com/t/green-context-sm-partitioning-on-rtx-pro-4000-blackwell-hard-48-sm-cap-and-dram-bandwidth-contention/378499):
un kernel di riordino a 16 SM fa **70 GB/s da solo** e **37 GB/s (−47%)** concorrente con un GEMM;
a 8 SM scende a 26 GB/s (−63%). Conferma accademica — Elvinger et al., SoCC 2025
([2501.16909](https://arxiv.org/abs/2501.16909)): *«Allocating kernels to separate SMs helps
eliminate some sources of interference, but contention for shared resources like L2 cache and
memory bandwidth can still cause significant slowdowns.»*
**Parte del nostro 28% è L2 e memoria, non SM.** E questo indica dove guardare per primo (§2.5).

**Chiuso per noi**: MPS e `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` sono **Linux 64-bit only**.
**libsmctrl** (Bakita & Anderson, UNC — [RTAS'23](https://www.cs.unc.edu/~jbakita/rtas23.pdf),
[repo](http://rtsrv.cs.unc.edu/cgit/cgit.cgi/libsmctrl.git/about/)) è l'**unico masking SM davvero
duro** su Ampere consumer — scrive direttamente i campi QMD a offset +84/+88 del descrittore di
lancio, granularità **TPC = 2 SM**, cc 3.5+ — ma è **Linux-only per costruzione** (`dlopen` di
`libcuda.so`, `/proc/gpu*`, aritmetica sui puntatori nelle struct del driver).

## 2.5 Non temporali, L2, `cp.async`

**Utilizzabile stasera, zero dipendenze:**

- **`__ldcs` / `__stcs`** (`ld.global.cs` / `st.global.cs`): politica **evict-first in L1 e L2**,
  documentata proprio *«to limit cache pollution by temporary streaming data that may be accessed
  once or twice»*. Da mettere **su entrambi i lati**: il load dalla host mappata e lo store nella
  cache VRAM.
- **Finestra L2 `cudaAccessPropertyStreaming`**
  ([L2 Cache Control](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/l2-cache-control.html)):
  *«Devices of compute capability **8.0 and above** have the capability to influence persistence of
  data in the L2 cache»* → **include 8.6**. Si imposta per stream (`cudaStreamAttrValue.accessPolicyWindow`)
  **o per nodo di grafo**. `cudaAccessPropertyStreaming` = *«preferentially evicted»*.
  **Questa è la contromisura documentata contro la parte della contesa che NON è SM**: impedire a
  `kern_copia` di sfrattare i matmul dai ~3 MB di L2 della 3060. **È la prima cosa da provare.**

**`cp.async` — risposta alla domanda precisa.** LDGSTS è **CC 8.0+ → sm_86 sì**. Ma:
*«The only direction supported for asynchronous copy operations with LDGSTS is from **global to
shared** memory.»* Taglie 4/8/16 byte; **16 byte → L1 BYPASS**. Il beneficio dichiarato è proprio
quello che cercavi: *«This not only **reduces register usage** by copying the data directly to
shared memory, but also ensures all loads from global memory are in-flight.»*

**Sulla sorgente in memoria host mappata: NON esiste documentazione, né a favore né contro.**
Cercato in PTX ISA, Programming Guide, CCCL e forum NVIDIA: **buco reale nella letteratura.**
Ragionamento *dedotto, non misurato*: sotto UVA un puntatore da `cudaHostAlloc(…Mapped)` è un
indirizzo `.global` valido lato device — è così che `kern_copia` lo legge oggi con `ld.global` —
quindi `cp.async.cg.shared.global` *dovrebbe* accettarlo. **È un microbench da 30 righe che
possiamo risolvere da soli, ed è l'unico punto del quesito 2 dove il mondo è muto.**
Due caveat che ridimensionano il premio: (1) la destinazione è **shared**, non global, quindi il
percorso diventa host→shared (senza registri) + shared→VRAM (store normale), e il guadagno si
prende solo sulla metà load, pagando shared memory e barriera; (2) segnalazioni di inefficienza
con `LDGSTS.E.BYPASS.128`.

**Chiuso su Ampere per tutti**: `cp.async.bulk` / TMA è **CC 9.0+**; shared→global asincrono non
esiste in hardware su sm_86 (*«the reverse direction is not hardware accelerated»*).

## 2.6 Dimensionare il kernel di copia: la regola pratica, e perché il tuo +5% è previsto

Regola dal forum NVIDIA: *«PCIe is slow and you will not need many threads to fully use the
bandwidth. Set the grid size to the number of SMs and the block size to a multiple of warps of 32.»*

**Il dato NVIDIA con configurazione**
([Improving GPU Memory Oversubscription Performance](https://developer.nvidia.com/blog/improving-gpu-memory-oversubscription-performance/)):
su **A100 PCIe Gen4 x86** (32 GB/s di picco), l'accesso grid-stride sta vicino al picco mentre
l'accesso random-warp resta **piatto a 3–4 GB/s** — identico alla V100 Gen3, **cioè indipendente
dal link**. Loro usano **128 thread per blocco** e accessi **allineati a 128 byte**. E la causa che
nominano non è la banda: *«degrades due to the **GPU MMU address translation misses** that add to
latency for load instructions.»*

→ **Questo spiega il tuo +5% a 8 blocchi contro 112.** Più warp concorrenti su memoria host
mappata = più miss sulla TLB del GPU MMU, e **la TLB è la risorsa scarsa, non il link**. Supporto
in letteratura: [MASK, ASPLOS'18](https://pages.cs.wisc.edu/~jayneel/papers/asplos18_mask.pdf) —
poche TLB miss simultanee bastano a togliere al warp scheduler i warp pronti.

**Aritmetica di Little (DEDOTTA, da verificare al banco).** Byte in volo = BW × latenza. A 25 GB/s
con latenza di lettura host via PCIe ~1,5 µs → **~37 KB in volo**. Con `int4` (16 B/thread) e ~8
load indipendenti per warp: 4 KB per warp → **servono ~9–10 warp in tutto**.

- 8 blocchi × 128 thread = **32 warp** → già ~3× il fabbisogno
- 112 blocchi × 128 thread = **448 warp** → **45× sovradimensionato**, e l'unica cosa che compra è
  thrashing di TLB e MSHR

L'unico input non misurato è la latenza di lettura host via PCIe sulla nostra macchina.

**Il precedente industriale**: i «channel» di NCCL **sono blocchi CUDA**, uno per SM, e
`NCCL_MAX_NCHANNELS` esiste esattamente per questo — *«Reducing the number of channels also
reduces the number of CUDA blocks used for communication, hence the impact on GPU computing
resources.»* Le implementazioni ring consumano **16+ SM**; con SHARP scendono a **6 o meno**.
**Il tuo «8 blocchi invece di 112» è la manopola `NCCL_MAX_NCHANNELS`: è pratica standard, non un
trucco locale.**

Suite riusabile per costruire la curva blocchi→GiB/s e blocchi→t/s:
[te42kyfo/gpu-benches](https://github.com/te42kyfo/gpu-benches) (RRZE-HPC), che contiene già uno
scan di occupancy e un benchmark di transfer host/UM.

## 2.7 Copy engine sulla 3060 — e perché il conteggio conta meno di quanto sembri

[Forum NVIDIA, proprio sulla 3060](https://forums.developer.nvidia.com/t/of-cuda-copy-engines-on-geforce-rtx-3060/334975):
stessa GPU, `deviceQuery` riportava **5 copy engine su CUDA 12.3** e **1 su driver 12.8/12.9** dopo
un passaggio Win10→Win11, con Nsight che confermava *«the asynchronous H2D and D2H data transfers
do not occur concurrently»*. Nessuna spiegazione tecnica da NVIDIA. **Da verificare sul nostro
banco con `deviceQuery`, non da assumere.**

Ma il punto vero è un altro: **più copy engine non aumentano la banda del link.** Aggiungono
concorrenza bidirezionale e code DMA indipendenti. Noi siamo **unidirezionali H2D** e già a
~24 GiB/s contro i 29,3 GiB/s teorici del PCIe 4.0 x16 → **~82% del teorico, cioè il tetto
pratico. Sull'asse banda non c'è niente da prendere. Sull'asse SM c'è tutto: il copy engine costa
ZERO SM.** E con un ciclo di lavoro del 22%, un engine che fa 24 GiB/s per il 22% del tempo costa
0 SM, mentre il kernel che fa la stessa cosa costa 8–20 SM per 34 ms.

## 2.8 Altre due conferme esterne dai lavori MoE

- **PreScope** ([2509.23638](https://arxiv.org/html/2509.23638)) decompone ogni esperto in tre
  sotto-tensori trasferiti da **tre CUDA stream indipendenti in concorrenza** — *«fills the
  scheduler gaps on the bus so that throughput approaches the PCIe peak»* — con pinned memory e
  **buffer pre-registrati**. Risultato: **79% di utilizzo PCIe**. Configurazione **non** nostra:
  V100 PCIe3 / A100 PCIe4, Xeon Gold 6230R, **batch 64**, BF16. Ma il nostro microbench del blocco
  **non ha provato copie concorrenti su stream multipli**: ha confrontato *modalità* di copia, non
  *concorrenza* di copie.
- **Conferma esterna del nostro tetto**: **SpecMoEOff**
  ([2508.21706](https://arxiv.org/abs/2508.21706)) pubblica la banda H2D **misurata**:
  **RTX 4090D → 23 GB/s**, A30 → 25 GB/s su PCIe 4.0 x16. I nostri 24 GiB/s **sono il tetto
  hardware reale**, non un artefatto. Quindi i 5,5 GiB/s di produzione = **ciclo di lavoro del
  22%** contro il 79% di PreScope. **Nessuno pubblica una baseline del ciclo di lavoro H2D.**
- **ProMoE**: chunk per **prelazione**, non per banda — *«an ongoing copy operation cannot be
  preempted midway»*.

## 2.9 Ordine consigliato per sm_86 + Windows, dal costo più basso

| # | Leva | Costo | Aspettativa | Base |
|---|---|---|---|---|
| 1 | **Finestra L2 `cudaAccessPropertyStreaming`** sullo stream/nodo di copia + `__ldcs`/`__stcs` | ~20 righe | attacca la parte **non-SM** della contesa (3 MB di L2) | doc CC 8.0+ |
| 2 | **Sweep 1→16 blocchi × 128 thread, `int4`, allineato a 128 B** | banco | consolida e supera il +5%; Little dice ~10 warp bastano | blog NVIDIA + NCCL |
| 3 | **`cudaMemcpyBatchAsync`** su stream dedicato (**serve toolkit ≥ 12.8**) | media | **la leva grossa: 0 SM, fino a 3,42× a taglie piccole** | release notes + forum |
| 4 | **Consolidare i pezzi per esperto verso 0,5–2 MB contigui** | media | è la mossa che ha dato +5…15% a vLLM e sposta il pareggio verso il DMA | vLLM H100 |
| 5 | **CUDA Graphs** | media-alta | l'unica via indicata da NVIDIA per la concorrenza su WDDM | NVIDIA/cccl #6925 |
| 6 | **Microbench `cp.async` da host mappata** | ~30 righe | risolve un buco che la letteratura non copre | nessuna fonte |
| 7 | Priorità di stream | 3 righe | **~0**, ma costa poco escluderla | Crovella |
| 8 | Green context | refactor del backend | serve **entrambi** i lati; bug cuBLAS SM count | doc + forum 5060 Ti |

Nota di metodo coerente col ledger: **il trasporto è già all'82% del tetto PCIe con un ciclo di
lavoro del 22%. Non c'è banda da prendere.** Tutta la posta di questo quesito è **chi paga il
trasporto**: 8–20 SM per 34 ms, oppure un engine che non tocca gli SM. Tre fonti indipendenti —
vLLM, ConCCL, NCCL — danno la stessa risposta, e **nessuna delle tre indica il partizionamento SM
come la mossa principale.**

---

# QUESITO 5 — LA PREVISIONE: NON RIPESCATA, MA RILETTA

Rispettato: non riporto lavori sulla *qualità* della predizione. Ma la caccia fa emergere una
rilettura del nostro esperimento che va messa a verbale.

**Il nostro test dell'oracolo (5,97 contro 5,89) teneva fisso il MECCANISMO.** Il piano esatto
veniva usato per pre-caricare **con `kern_copia`**, cioè col trasporto che ruba SM. In quel
confronto la previsione non poteva che valere zero: cambiava *quando* si copiava, non *come*.

Ma tutti i sistemi esterni usano il predittore per una ragione diversa da quella che abbiamo
testato: **il predittore serve a portare la lista sull'host**, e portare la lista sull'host è
l'unica cosa che permette di usare `cudaMemcpyAsync` e quindi il copy engine. In ProMoE,
MoE-Infinity, Klotski, Mixtral-offloading la previsione **non compra colpi: compra il
meccanismo**.

Quindi la formulazione corretta della nostra falsificazione è più stretta di quella che abbiamo
scritto: *«la previsione non paga **a meccanismo invariato**»*. Se la strada A (proxy host) o la
strada D funzionano, la previsione torna sul tavolo come **abilitatore**, non come euristica.
E il test discriminante è diverso da quello fatto: non «oracolo contro cieco a parità di
`kern_copia`», ma «oracolo + `cudaMemcpyAsync` contro cieco + `kern_copia`».

Marcatura: **dedotto, non misurato.** Il costo per falsificarlo è basso e vale la pena pagarlo
prima di scrivere il proxy.

---

# DOVE SIAMO OLTRE LO STATO DELL'ARTE

1. **Trasporto deciso dal device.** `kern_copia` è, per quanto ho trovato, **l'unica
   implementazione esistente** di un trasporto esperti guidato da una lista prodotta sul device.
   Tutti gli altri spostano la decisione sull'host. Il costo in SM non è un nostro difetto: è il
   prezzo dell'unica strada che l'hardware lascia aperta.
2. **Ciclo di lavoro del canale.** Nessuno pubblica il ciclo di lavoro H2D in produzione.
   PreScope pubblica il proprio 79% senza baseline. La diagnosi «il canale non era lento, era
   fermo» **non ha equivalente pubblicato**.
3. **Regime.** Nessun lavoro pubblicato combina 12 GB di VRAM + modello quantizzato ~80 GiB +
   256 esperti + speculativo + cache esperti. Il punto più vicino è DraftExpert su RTX 4090 24 GB
   con DeepSeek-V2-Lite a **2-3 t/s**. **A 14,77 t/s siamo fuori scala rispetto a tutto il
   pubblicato su hardware comparabile.**
4. **Sovrapposizione pairwise a 256 esperti.** Il paper LRC si ferma a 64 esperti e usa metriche
   su segmento. **Il nostro 36% su 256/top-6 non ha confronto diretto.**
5. **Il fallback dello scheduler.** Nessuno ha diagnosticato le copie per-esperto emesse da
   `ggml_backend_sched`. La cosa più vicina è la issue #20757, che conta «144 copie RAM→GPU per
   token» ma non collega il conteggio al fallback.

---

# COSA NON ESISTE — l'elenco secco

**Chiuso per tutti, su qualunque hardware NVIDIA:**

1. Nessuna API per far partire un DMA da dentro un kernel. **Mai esistita.**
2. Nessun aggiornamento dei parametri di un nodo memcpy da codice device
   (*«Device graphs can only be updated from the host»*).
3. Nessuna `cudaMemcpyAsync` con parametri letti all'esecuzione — **tranne** `cuFileReadAsync`,
   che è storage-only e Linux-only.
4. Nessuna prelazione garantita per priorità di stream. La doc dice *«may»*, e NVIDIA conferma
   che «may» non è «must».
5. Nessuna partizione SM dura via green context: *«they do not create a hard partition at the
   warp-dispatch level»*.
6. Nessun `cp.async` shared→global o global→global su Ampere: *«the reverse direction is not
   hardware accelerated»*. TMA / `cp.async.bulk` è CC 9.0+.
7. Nessuna aggregazione utile D2D con `cudaMemcpyBatchAsync` (~1,0× a tutte le taglie).
8. Nessun'altra lista di descrittori scatter/gather per i copy engine oltre a
   `cuMemcpyBatchAsync` / `cuMemcpy3DBatchAsync`.
9. **Nessuna conferma pubblicata che `cp.async` accetti sorgente in memoria host mappata.**
   Né a favore né contro: buco reale nella letteratura, e microbench da 30 righe per chiuderlo.
10. Nessun lavoro pubblicato che guidi il copy engine H2D da una lista device-side, in nessun
    dominio, non solo nel MoE.

**Chiuso per noi (esiste, ma non su sm_86 + GeForce + Windows):**

11. Stream memory ops (`cuStreamWaitValue32`/`WriteValue32`, batch-memop node): **serve TCC**,
    e TCC non è disponibile su GeForce.
12. MPS e `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE`: **Linux 64-bit only**.
13. **libsmctrl** — l'unico masking SM davvero duro su Ampere consumer: **Linux-only per
    costruzione**.
14. PDL (programmatic dependent launch) e overlap via stream su WDDM: NVIDIA dichiara
    l'incompatibilità e rimanda ai CUDA Graphs.
15. GPUDirect Storage / cuFile: **Linux**.

**Sul lato letteratura MoE:**

16. Nessun repo pubblico per AcceptMoE, EcoSpec, EVICT, MoE-Spec, DraftExpert, MoE-SpeQ, SP-MoE,
    PreScope. Codice disponibile solo per **ProMoE**, **mixtral-offloading**, **moe-lrc**,
    **SpecPrefetch**.
17. Nessuno accorcia K per la residenza. La risposta unanime è: **restringi l'unione, non K.**
18. Nessuna cache esperti MoE è entrata in llama.cpp upstream: cinque tentativi falliti
    (#20757, #21609, #21614, #21620, #23170), la RFC #24528 non è merged, e #24524 è stata chiusa
    **prima di qualunque revisione tecnica**.

---

# LE OTTO COSE CHE RACCOGLIEREI, IN ORDINE DI COSTO CRESCENTE

1. **Finestra L2 `cudaAccessPropertyStreaming` + `__ldcs`/`__stcs`** (~20 righe, zero
   dipendenze): attacca la parte della contesa che **non è SM** — i 3 MB di L2 che `kern_copia`
   sfratta ai matmul. La letteratura dice che parte del nostro 28% è L2 e memoria, non SM.
2. **`GGML_OP_OFFLOAD_MIN_BATCH`** (#18535, già upstream): zero righe, isola il ramo di fallback
   dello scheduler dal nostro trasporto.
3. **PR #26802** (merged oggi): verificare se il nostro fork disabilita i grafi CUDA su
   `mul_mat_id` quando non serve. Con IQ2_XXS dovremmo essere sul percorso MMQ, che **non
   sincronizza**.
4. **Sweep 1→16 blocchi × 128 thread, `int4`, allineato a 128 B**: il conto di Little dice che
   ~10 warp bastano a saturare il PCIe; a 112 blocchi siamo **45× sovradimensionati** e paghiamo
   solo TLB thrashing.
5. **Aggiornare il toolkit a ≥ 12.8 e provare `cudaMemcpyBatchAsync`** sulle nostre copie
   piccole e numerose: **0 SM, fino a 3,42×**. Il driver 596.21 basta già.
6. **Consolidare i pezzi per esperto verso 0,5–2 MB contigui** e poi darli al DMA: è la mossa
   che ha dato +5…15% a vLLM, e sposta il punto di pareggio kernel/DMA a nostro favore.
7. **Il proxy host** (pattern NCCL/NVSHMEM): l'unica strada che toglie il trasporto dagli SM
   *mantenendo la decisione sul device*. Prima misurare la latenza di andata-e-ritorno WDDM,
   che è il rischio numero uno.
8. **Ammissibilità condizionata alla residenza** (AcceptMoE): se non è residente, il bersaglio
   non lo usa. Riduce il **numero di miss** — unico criterio che passa `transport-identity`.
   Costo dichiarato 0,27 punti, guadagno 2,06× e −75% di traffico.

E, fuori classifica perché è lettura e non codice: **la cache di leloch, misurata da terzi sul
nostro modello** (+28…33% su DS4-Flash, 2×3090). Leggere `moe-cache.cu` per il **dispatch
impacchettato** che ha eliminato ~40.596 copie H2D.

---

## FONTI

**Documentazione NVIDIA**
- [CUDA Programming Guide — CUDA Graphs](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html)
- [CUDA Driver API — Stream Memory Operations](https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__MEMOP.html)
- [CUDA Driver API — Green Contexts](https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__GREEN__CONTEXTS.html) · [Programming Guide 4.6](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/green-contexts.html)
- [Programming Guide 4.11 — Asynchronous Data Copies](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/async-copies.html) · [4.13 — L2 Cache Control](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/l2-cache-control.html)
- [Dynamic Control Flow in CUDA Graphs with Conditional Nodes](https://developer.nvidia.com/blog/dynamic-control-flow-in-cuda-graphs-with-conditional-nodes)
- [Enabling Dynamic Control Flow in CUDA Graphs with Device Graph Launch](https://developer.nvidia.com/blog/enabling-dynamic-control-flow-in-cuda-graphs-with-device-graph-launch/)
- [CUDA Runtime API — Graph Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__GRAPH.html) · [Memory Management](https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__MEMORY.html)
- [CUDA 12.8 Release Notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html) · [CUDA C++ Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html)
- [Improving GPU Memory Oversubscription Performance](https://developer.nvidia.com/blog/improving-gpu-memory-oversubscription-performance/)
- [NCCL Environment Variables](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html) · [MPS Architecture (Linux only)](https://docs.nvidia.com/deploy/mps/architecture.html)
- [GDS cuFile API Reference](https://docs.nvidia.com/gpudirect-storage/api-reference-guide/index.html)

**Forum NVIDIA / NVIDIA GitHub (misure di terzi)**
- [Green-context SM provisioning vs the primary context (RTX 5060 Ti, %smid)](https://forums.developer.nvidia.com/t/green-context-sm-provisioning-vs-the-primary-context/377440)
- [Green Context SM Partitioning on RTX PRO 4000 Blackwell](https://forums.developer.nvidia.com/t/green-context-sm-partitioning-on-rtx-pro-4000-blackwell-hard-48-sm-cap-and-dram-bandwidth-contention/378499)
- [Questions of CUDA stream priority (Crovella)](https://forums.developer.nvidia.com/t/questions-of-cuda-stream-priority/250343/4) · [How high priority stream preemption](https://forums.developer.nvidia.com/t/how-high-priority-stream-preemption/78183/4)
- [NVIDIA/cccl #6925 — PDL e WDDM](https://github.com/NVIDIA/cccl/discussions/6925)
- [cudaMemcpyBatchAsync — benchmark](https://forums.developer.nvidia.com/t/cudamemcpybatchasync/360302)
- [# of CUDA copy engines on GeForce RTX 3060](https://forums.developer.nvidia.com/t/of-cuda-copy-engines-on-geforce-rtx-3060/334975)
- [cp.async only supports global to shared](https://forums.developer.nvidia.com/t/cuda-ptx-cp-async-only-supports-global-to-shared-memory-copy/245979)

**llama.cpp**
- [Discussion #24528 — RFC MoE expert cache](https://github.com/ggml-org/llama.cpp/discussions/24528)
- [PR #24524](https://github.com/ggml-org/llama.cpp/pull/24524) · [Issue #20757](https://github.com/ggml-org/llama.cpp/issues/20757)
- [PR #26802](https://github.com/ggml-org/llama.cpp/pull/26802) · [PR #16991](https://github.com/ggml-org/llama.cpp/pull/16991) · [PR #18535](https://github.com/ggml-org/llama.cpp/pull/18535)
- [PR #24162](https://github.com/ggml-org/llama.cpp/pull/24162) · [PR #25784](https://github.com/ggml-org/llama.cpp/pull/25784) · [PR #26322](https://github.com/ggml-org/llama.cpp/pull/26322)
- [PR #20793](https://github.com/ggml-org/llama.cpp/pull/20793) · [PR #25138 (revert)](https://github.com/ggml-org/llama.cpp/pull/25138)
- [PR #26003](https://github.com/ggml-org/llama.cpp/pull/26003) · [PR #26414](https://github.com/ggml-org/llama.cpp/pull/26414) · [PR #26294](https://github.com/ggml-org/llama.cpp/pull/26294)

**vLLM**
- [RFC #38256 — Incremental MoE Expert Offloading](https://github.com/vllm-project/vllm/issues/38256)
- [KV Offloading Connector — kernel custom contro DMA, gen 2026](https://vllm.ai/blog/2026-01-08-kv-offloading-connector)

**Letteratura**
- ProMoE [2410.22134](https://arxiv.org/abs/2410.22134) · [codice](https://github.com/promoe-opensource/promoe)
- AcceptMoE [2608.02989](https://arxiv.org/abs/2608.02989) · DraftExpert [2607.24434](https://arxiv.org/abs/2607.24434)
- MoE-Spec [2602.16052](https://arxiv.org/html/2602.16052v1) · EVICT [2605.00342](https://arxiv.org/abs/2605.00342) · EcoSpec [2607.12696](https://arxiv.org/abs/2607.12696)
- MoE-SpeQ [2511.14102](https://arxiv.org/html/2511.14102) · SpecMoEOff [2508.21706](https://arxiv.org/abs/2508.21706) · PreScope [2509.23638](https://arxiv.org/html/2509.23638)
- Local Routing Consistency [2505.16056](https://arxiv.org/html/2505.16056v3) · [moe-lrc](https://github.com/ljcleo/moe-lrc)
- Caching & Prefetching in MoE Offloading [2511.05814](https://arxiv.org/abs/2511.05814)
- Mixtral-offloading [2312.17238](https://arxiv.org/html/2312.17238v1) · [codice](https://github.com/dvmazur/mixtral-offloading)
- Klotski [2502.06888](https://arxiv.org/html/2502.06888) · Fiddler [2402.07033](https://arxiv.org/pdf/2402.07033) · [MoE-Infinity](https://github.com/EfficientMoE/MoE-Infinity)
- ktransformers [SOSP'25](https://madsys.cs.tsinghua.edu.cn/publication/ktransformers-unleashing-the-full-potential-of-cpu/gpu-hybrid-inference-for-moe-models/SOSP25-chen.pdf)
- GPU-Initiated Networking for NCCL [2511.15076](https://arxiv.org/html/2511.15076v1) · GICC [2604.22126](https://arxiv.org/pdf/2604.22126)
- ConCCL — Optimizing ML Concurrent Computation and Communication with GPU DMA Engines [2412.14335](https://arxiv.org/abs/2412.14335)
- Elvinger et al., Understanding GPU Resource Interference One Level Deeper, SoCC'25 [2501.16909](https://arxiv.org/abs/2501.16909)
- MASK — GPU TLB thrashing, ASPLOS'18 [PDF](https://pages.cs.wisc.edu/~jayneel/papers/asplos18_mask.pdf)
- libsmctrl — Bakita & Anderson, UNC [RTAS'23](https://www.cs.unc.edu/~jbakita/rtas23.pdf) · [repo](http://rtsrv.cs.unc.edu/cgit/cgit.cgi/libsmctrl.git/about/)
- [te42kyfo/gpu-benches](https://github.com/te42kyfo/gpu-benches) — suite di microbenchmark riusabile
