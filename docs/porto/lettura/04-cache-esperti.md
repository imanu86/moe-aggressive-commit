# 04 — Cache esperti (`ggml/src/ggml-cuda/cache-esperti.cu` + `.cuh`)

Lettura statica, nessuna esecuzione. Repo: `D:\llama-overlap`.
File letto **per intero**: `D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cu` (3.956 righe) e
`D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cuh` (645 righe).
File collegati letti nei punti d'aggancio: `ggml-cuda.cu` (righe 130-160, 225-270, 369-640,
1357-1560, 2180-2400, 4700-4910, 5520-5560), `mmvq.cu` (1190-1320, 1330-1520, 1700-1860),
`kv-ring.cu` (110-175), `src/models/deepseek4.cpp` (1390-1440).

Ogni affermazione e' marcata **[LETTO]** (sta nel codice, con file:riga) oppure
**[DEDOTTO]** (inferenza mia, non verificata da misura).

Configurazione di riferimento: `SLOT=512, FORK=2, FORK_BLOCCHI=8, LRU=1, SFRATTO_PAR=1,
BATCH=8, BATTITO=45, W=0, CURA=0, SCUDO=0, MASSA=0, PREFETCH_FILTRO=0, CODA_MAX=0,
SPIN=256(difetto), PF_TUTTI=1(difetto), MAPPED_IBRIDO=1`.

---

## A. CONTATORI

### A.1 Dove vivono, e quando nascono

**[LETTO]** Sono **32 `uint64_t` contigui in VRAM**, allocati con una sola
`cudaMalloc` (`cache-esperti.cu:1410`) e aliasati come puntatori dentro la struct
(`:1411-1441`). `CACHE_ESPERTI_CONTATORI = 32` (`:62`).

| # | campo | incrementato a (file:riga) | atomico? |
|---|---|---|---|
| 0 | `colpi` | `:2554` (colpo normale), `:2585` (colpo su transito riusato, solo `CURA>=2`) | `atomicAdd` |
| 1 | `buchi` | `:2635` | `atomicAdd` |
| 2 | `prenotati` | `:2742`, `:2832` (solo `kern_prenota`) | no |
| 3 | `saltati` | `:2720`, `:2773`, `:2784` (solo `kern_prenota`) | no |
| 4 | `in_ritardo` | `:2564` | `atomicAdd` |
| 5 | `scartati` | `:2698`, `:2800`, `:2805` (solo `kern_prenota`) | no |
| 6 | `guasti` | `:2531` (id fuori range), `:2619` (vittima < 0), `:2707/2762/2816` | misto |
| 7 | `riusi_transito` | `:2586` | `atomicAdd` |
| 8 | `promozioni_sorpassate` | `:2317` (`cache_promuovi`) | no |
| 9/10 | `predetti_consumati` / `scaduti` | `:2271` / `:2262` | no |
| 11-15 | `vittime_non_residenti` … `vittime_usate_predette` | `:2028-2035` (solo ramo `cura/scudo/dma` di `cache_vittima`) | no |
| 16/17 | `vittime_domanda` / `vittime_prefetch` | `:1920`, `:1968`, `:2036`, `:2066` (sequenziale), `:2202` (parallela) | no |
| 18 | `lanci_cura` | `:2501` | no |
| 19 | `spin_esauriti` | `:2591` | `atomicAdd` |
| 20 | `prefetch_mancanti` | `:2789` | no |
| 21/22 | `pressione_servizio` / `pressione_dma` | `:2798` / `:2799` | no |
| 23-27 | `bussate_buco_1 … 8_piu` | `:2636-2640` | no |
| 28-31 | `installati_riusi_0 … 4_piu` | `:1870-1873` (`cache_registra_sfratto`) | no |

**[LETTO]** Le scritture non atomiche sono tutte dentro un `if (threadIdx.x == 0)`
oppure dopo `if (threadIdx.x != 0) continue;` (`:2614`), anche con `SFRATTO_PAR=1`
e blocco a 256 fili: **niente corse sui contatori**. Verificato riga per riga in
`kern_decidi` (`:2487-2645`) e in `cache_vittima_par` (`:2193`).

**[LETTO]** Contatori separati, non nel blocco dei 32: `am_cont[8]` per AcceptMoE
(`:1442`), `fj_sonda[4]` per il fork (`:1713`), `div[5]` per il rilevatore di
replay (`:3604`), piu' una decina di contatori **host** per il DMA
(`runtime->dma_*`, `runtime->domanda_*`, `:187-212`).

### A.2 CUMULATIVI O ISTANTANEE? — la risposta secca

**[LETTO] I 32 contatori sono CUMULATIVI DALL'INIT E NON VENGONO MAI AZZERATI.**
L'unica `cudaMemset` sul blocco e' in `ggml_cuda_cache_esperti_init`
(`:1569`, `cudaMemset(runtime->cache.colpi, 0, 32*sizeof(uint64_t))`).
`ggml_cuda_cache_esperti_dump` (`:3768-3956`) fa **solo una lettura**
(`cudaMemcpy(v, runtime->cache.colpi, sizeof(v), D2H)`, `:3777`) e non scrive nulla.
`ggml_cuda_cache_esperti_batti` (`:1148-1165`) chiama `dump` e basta.

Quindi ogni dump del battito e' un **totale progressivo dall'avvio**, non un
intervallo. **Per ottenere l'intervallo fra due battiti bisogna sottrarre i due dump.**

**[LETTO]** Gli unici punti dove i contatori tornano a zero:
1. la prima `init` (`:1569`);
2. `ggml_cuda_cache_esperti_fasi` (`:1083` `free` + `:1091` `forse_init`), cioe'
   **solo con `LLAMA_VRAM_A_FASI`**. E li' il dump viene stampato *prima* della free
   (`:1074-1076`) proprio per non perdere la serie.
La leva a fasi non e' nella configurazione in esame: **con la config di riferimento
i contatori non si azzerano mai per tutta la corsa.**

**[LETTO] ECCEZIONE, ed e' la trappola.** Sulla stessa riga di stampa convivono
cumulativi e istantanee:

```
cache-esperti: riuso installazioni sfrattate: totale=%llu, vive-censurate=%llu | mai=… 1=… 2-3=… 4+=…
```
`:3811-3817`. Qui `totale` (= v[28]+v[29]+v[30]+v[31]) e le quattro classi sono
cumulative, ma **`vive-censurate` e' un'ISTANTANEA calcolata sull'host al momento
del dump**: `:3803-3810` copia l'array `installato[n_slot]` e conta i non-zero.
E' quindi limitata da `n_slot` (max 512) e descrive lo **stato corrente della cache**,
non la storia. Confrontare `vive-censurate` fra due corse a capienza diversa
confronta due numeri che hanno per soffitto due valori diversi.

**[LETTO]** Anche `LLAMA_VRAM_A_FASI_CALDO`/`fasi` non e' l'unico dump: il dump esce
pure da `ggml_cuda_cache_esperti_runtime_libera` (`:1837`, a chiusura del backend).

### A.3 PIU' DUMP CON LO STESSO PREFISSO — sì, e si distinguono male

**[LETTO]** Esistono **due runtime indipendenti** della cache, uno per contesto CUDA:
`ggml_cuda_cache_esperti_runtime_crea(bozza, device)` viene chiamato in
`ggml-cuda.cu:1482` con `bozza = 0` (bersaglio) o `bozza = 1` (bozza). Ognuno ha
il **suo** battito, la sua variabile d'ambiente e i suoi 32 contatori:
- bersaglio: `LLAMA_CACHE_ESPERTI_SLOT`, `LLAMA_CACHE_ESPERTI_BATTITO` (`:321`, `:356`);
- bozza: `LLAMA_CACHE_BOZZA_SLOT`, `LLAMA_CACHE_BOZZA_BATTITO` (stesse righe, ramo `bozza`).

La bozza produce dump **solo se `LLAMA_CACHE_BOZZA_SLOT > 0`** (`batti` esce subito
se `!runtime->attiva`, `:1150`).

**[LETTO] COME SI DISTINGUONO — e perche' e' pericoloso.**
Nella config di riferimento un dump stampa **13 righe** (`:3775, 3783, 3792, 3811,
3827, 3835, 3896, 3902, 3910, 3917, 3932, 3944, 3953`; le righe `:3839/3859/3880`
escono solo con DMA acceso, la `:3771` solo con l'oracolo). Di quelle 13, solo
**due** portano l'etichetta e **undici no**:

| riga | testo | distingue? |
|---|---|---|
| `:3775` | `"%s: dump contatori"` con `cache_nome(runtime)` → **`cache-esperti:`** o **`cache-bozza:`** | **SI'** |
| `:3932-3935` | `acceptmoe[bersaglio]` / `acceptmoe[bozza]` | **SI'** |
| tutte le altre (`:3783, 3792, 3811, 3827, 3835, 3896, 3902, 3910, 3917, 3944, 3953`, piu' `:3839/3859/3880` col DMA) | prefisso **hard-coded** `"cache-esperti: …"` | **NO** |

Cioe': la riga `cache-esperti: domanda … (colpi … buchi …)` **esce identica per il
bersaglio e per la bozza**. L'unico modo di attribuirla e' risalire alla riga
`… : dump contatori` che la precede. Il codice stesso documenta la trappola gemella
a `:3920-3928` (l'audit/36: «un cancello che legge l'ultima riga acceptmoe del log
legge la BOZZA e dichiara spenta una leva accesa»).

**[LETTO]** In piu': i due runtime **non condividono l'orologio del battito**
(`ultimo_battito` per-runtime, `:118`) e `batti` e' chiamato dall'ingresso di
`graph_compute` di **quel** backend (`ggml-cuda.cu:4890`). Bersaglio e bozza girano
a cadenza diversa e i loro dump si **interfogliano** nel log.

### A.4 Cosa vuol dire ciascun numero della riga principale

**[LETTO]** `:3783-3790`:
- `domanda` = `colpi + buchi`;
- `colpi %` = `colpi/domanda`; `miss %` = `buchi/domanda` — **sono complementari, non
  due misure indipendenti**;
- `in ritardo = %.1f%% dei prenotati` usa `v[4]/v[2]`. Con `W=0` `prenotati` e' 0 e
  la percentuale stampa `0.0%` **per divisione mancata, non per assenza di ritardi**.

**[LETTO] `conta`, cioe' quando una domanda viene contata**: `:2982-2983` in
`assicura` e `:3270-3271` in `fork_gate`:
`conta = (strato != runtime->ultimo_strato_contato)`. Gate/up/down dello stesso
strato chiedono gli stessi id: **conta solo la prima chiamata della terna**.
Quindi `domanda` = (n. strati MoE) x n_expert_used x n_token, **non** il triplo.
`ultimo_strato_contato` e' condiviso fra cammino fork e cammino normale: in
`FORK` la fase 0 conta, le fasi 1 e 2 no. **[LETTO]** Corretto per costruzione.

---

## B. VARIABILI D'AMBIENTE, con raggiungibilita'

Legenda raggiungibilita' **nella config di riferimento** (`LRU=1, SFRATTO_PAR=1, W=0,
FORK=2, CURA=0, SCUDO=0, MASSA=0, DMA=0`):
**VIVA** = il ramo gira; **MORTA-CONFIG** = il ramo esiste ma non e' raggiunto;
**MORTA-STRUTTURALE** = il kernel che la legge non viene mai lanciato.

| variabile | letta a | cosa fa | stato |
|---|---|---|---|
| `LLAMA_CACHE_ESPERTI_SLOT` | `:321` | capienza; 0 = spenta | **VIVA** |
| `LLAMA_CACHE_BOZZA_SLOT` | `:321` (ramo bozza) | capienza cache bozza | dipende |
| `LLAMA_CACHE_ESPERTI_BATCH` | `:345` (dif. 8) | tetto token/passaggio; cancello a `ggml-cuda.cu:2231` | **VIVA** |
| `LLAMA_CACHE_ESPERTI_BATTITO` | `:356` (dif. 60) | secondi fra i dump | **VIVA** |
| `LLAMA_CACHE_ESPERTI_LRU` | `:1235` (dif. **1**) | sceglie il ramo LRU di `cache_vittima` | **VIVA** |
| `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` | `:1255` (dif. 0) | blocco a 256 fili + riduzione cooperativa | **VIVA** |
| `LLAMA_CACHE_ESPERTI_FORK` | `:1597` (dif. 0) | 1 = fork/join, 2 = + sonda | **VIVA** |
| `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI` | `:1644` (dif. 32) | griglia di `kern_fj_copia` | **VIVA** |
| `LLAMA_CACHE_ESPERTI_FORK_ESATTO` | `:1660` (dif. 0) | 1 = un-token fuori dal fork; 2 = clone generico mascherato | **VIVA** (a 0) |
| `LLAMA_CACHE_ESPERTI_FORK_SERIALE` | `:1632` (dif. 0) | join immediato: sonda di diagnosi | **VIVA** (a 0) |
| `LLAMA_CACHE_ESPERTI_FORK_PRIORITA` | `:1686` (dif. 0) | stream copia a priorita' piu' bassa | **VIVA** (a 0) |
| `LLAMA_CACHE_ESPERTI_CURA` | `:1216` (dif. 0) | 5 classi di vittima + spin sul transito | **MORTA-CONFIG** (§5) |
| `LLAMA_CACHE_ESPERTI_SCUDO` | `:1243` (dif. 0) | protegge `predetto[]` dallo sfratto | **MORTA-STRUTTURALE** (§5) |
| `LLAMA_CACHE_ESPERTI_SPIN` | `:1221` (dif. 256) | letture del flag `atterrato` | **MORTA-CONFIG** (serve `CURA>=2`) |
| `LLAMA_CACHE_ESPERTI_MASSA` | `:1239` (dif. 0) | politica LFU decaduta | **MORTA-CONFIG** (e se accesa **scavalca** LRU) |
| `LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO` | `:1226` (dif. 0) | in `kern_prenota` sceglie il cammino "mancanti" | **MORTA-STRUTTURALE** |
| `LLAMA_CACHE_ESPERTI_CODA_MAX` | `:1230` (dif. 0) | tetto sull'arretrato dell'anello | **MORTA-STRUTTURALE** |
| `LLAMA_CACHE_ESPERTI_DMA` | `:1275` (dif. 0) | prefetch coi motori DMA | **MORTA-CONFIG** (+ incompatibile col fork, `:1639`) |
| `LLAMA_CACHE_ESPERTI_DMA_HIT_PM/_RISCALDAMENTO/_FINESTRA` | `:1292-1305` | cancello del DMA fra-strati | morta con DMA=0 |
| `LLAMA_CACHE_ESPERTI_DOMANDA_DMA` | `:1271` (dif. 0) | sostituisce `kern_copia` con `cudaMemcpyAsync` fuori cattura | **MORTA-CONFIG** (e spegne il fork, `:1639`) |
| `LLAMA_CACHE_ESPERTI_W` | `:1277`, `:1605` qui; **il vero consumatore e' `src/models/deepseek4.cpp:1397`** (dif. **0**) | quanti nodi `cache_pf-*` costruire | **VIVA a 0** ⇒ rende morte le sei leve sopra |
| `LLAMA_CACHE_ESPERTI_PF_TUTTI` | `ggml-cuda.cu:4735` (dif. acceso) | prenota tutte le posizioni del batch invece della sola prima | **MORTA-STRUTTURALE** (dentro il blocco `cache_pf-`) |
| `LLAMA_CACHE_ESPERTI_FATE` | `deepseek4.cpp:1405` | 15 candidati invece di 6 | morta con W=0 |
| `LLAMA_VRAM_A_FASI*` (`_SLOT`,`_MARGINE`,`_SLOT_MAX`,`_CALDO`) | `:994-1005`, `:848` | ridimensiona la cache al confine prefill/decode | non attiva |
| `LLAMA_VRAM_ZAVORRA` | `:292` | MiB allocati e mai usati (braccio di controllo) | non attiva |
| `LLAMA_CACHE_ORACOLO` | `:3679` | piano di route registrato | non attiva |
| `LLAMA_OVERLAP_GRIGLIA_VARIABILE` | `:3456` | rimette `<<<1,n_tok>>>` nella partizione | non attiva |
| `LLAMA_MAPPED_IBRIDO` | **due punti**: `ggml-cuda.cu:1435-1439` (`is_host`) e `ggml-cuda.cu:5531` (`supports_op`) | vedi sotto | **VIVA a meta'** |
| `LLAMA_MAPPED_IBRIDO_SOGLIA` | `ggml-cuda.cu:5535` (dif. 2) | la soglia del secondo punto | **MORTA-CONFIG** |

**[LETTO] `MAPPED_IBRIDO` ha DUE effetti indipendenti, e la cache ne sospende UNO SOLO.**

- **Effetto (a), NON sospeso**: `ggml_backend_cuda_mapped_buffer_type_is_host`
  (`ggml-cuda.cu:1411-1440`) ritorna `ibrido && g_cuda_mapped_uva`. Con
  `MAPPED_IBRIDO=1` il buffer mappato si dichiara **host**, quindi
  `ggml_backend_cpu_device_supports_buft` lo accetta e lo scheduler puo' mettere
  quelle op sulla CPU. Questa riga **non sa niente della cache** e resta attiva.
  E' la condizione che apre il ripiego per-esperto dello scheduler.
- **Effetto (b), sospeso**: il rifiuto in `supports_op` (`ggml-cuda.cu:5529-5547`,
  `get_op_batch_size(op) < soglia && !cache_ammessa`) e' **disattivato** appena
  `ggml_cuda_cache_esperti_percorso_gpu_richiesto()` e' vero, cioe' appena
  `SLOT>0` **oppure** `BOZZA_SLOT>0` (`:329-332`). Con `SLOT=512` il ramo
  `return false` non viene **mai** preso, e con lui muore anche
  `LLAMA_MAPPED_IBRIDO_SOGLIA`.

**[DEDOTTO]** Quindi con `SLOT=512` e `MAPPED_IBRIDO=1` si e' nel regime misto:
il CUDA accetta l'op (b sospeso) **ma** la CPU la accetta pure (a attivo), e chi
decide e' `ggml_backend_cuda_device_offload_op` / lo scheduler. Non e' "ibrido
spento": e' "ibrido con un solo cancello su due".

---

## C. COMPLESSITA' (cammino caldo, per token)

Sia `S` = `n_slot`, `E` = evizioni (= buchi, vedi §1.4), `F` = `CACHE_ESPERTI_SFRATTO_FILI` = 256
(`:67`), `n_id` = 6 x n_token, `L` = strati MoE (43 su DSV4).

| lavoro | dove | costo |
|---|---|---|
| `cache_promuovi` | `:2286-2339`, chiamato a `:2507` | **O(1)** con W=0 (il flag `atterrato[idx]` e' 0, esce al primo giro, `:2299`) |
| decadimento massa | `:1883-1884` | **O(1)** per sfratto (una tacca) |
| colpo | `:2544-2555` | **O(1)** |
| **scansione vittima, sequenziale** | `:1931-1956` | **O(S)** letture a un solo filo |
| **scansione vittima, parallela** | `:2128-2153` | `ceil(S/F)` iterazioni **per filo**, **S transazioni totali**, + `log2(F)=8` `__syncthreads` di riduzione (`:2157-2167`) |
| barriere del protocollo | `:2606`, `:2608` | 2 `__syncthreads` **per id**, sempre, anche sui colpi |
| `kern_copia` | `:2853-2880` | O(buchi x byte_slot / griglia); griglia **fissa** 4xSM (`:2884-2891`) |
| `kern_fj_maschera` | `:3168-3184` | **O(n x n_id)** a **un solo filo** (`<<<1,1>>>`, `:3287`) — n = lunghezza lista |
| `kern_fj_copia` | `:3191-3217` | O(buchi x byte_slot / (FORK_BLOCCHI x 256)) |
| `kern_partiziona` | `:3349-3421` | O(ne0) per token, griglia fissa `TOK_MAX=32` (`:3459-3461`) |
| `kern_acceptmoe` | `:3482-3572` | O(ne0) per token, griglia fissa |
| dump | `:3768` | **O(S)** copia D2H di `installato[]` (`:3805`) — **una volta ogni BATTITO**, non per token |

**[LETTO] L'unico lavoro proporzionale alla CAPIENZA sul cammino caldo e' la
scelta della vittima.** Tutto il resto e' proporzionale al delta o costante,
come pretende la «regola 1» del contratto (`cache-esperti.cuh:68-71`).

**[LETTO]** Il conteggio delle barriere e' **uniforme**: `if (par) __syncthreads()`
a `:2606`/`:2608` e' fuori da ogni `if` sui dati, e `sfratto_coop_scansiona` e'
chiamata da tutto il blocco dallo **stesso sito** (`:2612`). Il commento a
`:2099-2109` spiega che il disegno precedente violava proprio questo.
Coerente con la regola di metodo «le barriere CUDA devono stare sullo stesso sito».

---

## D. HOST vs DEVICE, e i confini

### D.1 Chi sta dove

**[LETTO] Sul DEVICE, dentro il grafo (nessuna sincronizzazione per strato):**
`kern_decidi` (`:2487`), `kern_copia` (`:2853`), `kern_fj_maschera` (`:3168`),
`kern_fj_copia` (`:3191`), `kern_partiziona` (`:3349`), `kern_acceptmoe` (`:3482`),
`kern_prenota` (`:2665`), `kern_dma_*` (`:2344-2406`), le sonde fork (`:3224-3231`).
Tutte le mutazioni di `dove/chi/usato/ultimo` avvengono **solo** in kernel sullo
stream principale (contratto in `cache-esperti.cuh:186-188`).

**[LETTO] Sull'HOST:** init/free, il registro delle basi (`:382-416`), il thread di
servizio DMA (`:656-731`), il dump, il rilevatore di replay (`:3600-3652`),
l'oracolo (`:3674-3758`), la VRAM a fasi (`:984-1137`).

### D.2 I confini host↔device che esistono davvero

| confine | file:riga | quando |
|---|---|---|
| `cudaMemcpy` D2H dei 32 contatori | `:3777` | **una volta per BATTITO** (45 s), dall'ingresso di `graph_compute` |
| `cudaMemcpy` D2H di `installato[n_slot]` | `:3805` | idem |
| `cudaMemcpy` D2H di `div[5]`, `am_cont[8]`, `fj_sonda[4]` | `:3641`, `:3931`, `:3943` | idem |
| `cudaMemcpyAsync` H2D di `pub_host` (rilevatore replay) | `:3633` | **una per `graph_compute`**, fuori cattura |
| `cudaStreamSynchronize` | `:2928` | **solo** con `DOMANDA_DMA=1` — non nella config |
| `cudaMemcpy` sincrona in `ricarica_calda` | `:942` | solo con `VRAM_A_FASI_CALDO` |
| eventi inter-stream del fork | `:3292-3301`, `:3320` | **per strato**, ma sono **device-side**: `cudaStreamWaitEvent` non blocca l'host |

**[LETTO]** Il fork **non introduce nessun confine host**: `ev_fork`/`ev_copia` sono
creati `cudaEventDisableTiming` (`:1708-1709`) e usati solo con
`cudaStreamWaitEvent`. La lezione «il join e' un EVENTO CUDA, non un flag volatile»
e' scritta a `:3164-3166`.

**[LETTO]** Il thread di servizio (`:656`) viene comunque **creato sempre** per il
bersaglio (`:1573-1577`), anche con DMA spento: nel ramo non-DMA fa polling
dell'anello mappato con `sleep_for(100us)` dopo 200 giri a vuoto (`:689-696`).
Con `W=0` la testa dell'anello non avanza mai: il thread gira a vuoto per tutta la
corsa. **[DEDOTTO]** Costa un core in idle-poll e nulla di piu'; ma e' un thread
in piu' che compete per lo scheduler dell'host, e nel regime «la CPU calcola mentre
la GPU aspetta» non e' gratis.

---

# DOMANDE SPECIFICHE

## 1. `cache_vittima` — i quattro cicli, l'ordine, le uscite, il costo

### 1.1 I quattro rami, nell'ordine in cui sono provati

**[LETTO]** `cache_vittima` (`:1879-2069`) e' `__device__`, prende `cache_esperti &`
e un `bool prefetch`, e prima di tutto fa **una tacca di decadimento della massa**
(`:1883-1884`, O(1)). Poi prova i rami **in quest'ordine, ognuno con `return`**:

| # | condizione | ciclo | righe |
|---|---|---|---|
| 1 | `if (c.politica_massa)` | `for (passo = 0; passo < c.n_slot; passo++)` | **1890** |
| 2 | `if (c.lru)` | `for (passo = 0; passo < c.n_slot; passo++)` | **1931** |
| 3 | `if (c.cura \|\| c.scudo \|\| c.dma)` | `for (passo = 0; passo < c.n_slot; passo++)` | **1981** |
| 4 | (nessuna: fallback orologio) | `while (giri < 3 * c.n_slot)` | **2044** |

**Ordine effettivo: `massa` → `lru` → `(cura\|scudo\|dma)` → `orologio`.**

### 1.2 Le uscite anticipate, ramo per ramo

- **Ramo 1 (massa, `:1890-1909`)**: `continue` sugli slot IN TRANSITO (`:1893`);
  **`break` immediato** al primo slot non residente **o** con `usato == 0` (`:1901-1904`).
  Altrimenti scorre tutti gli `n_slot` cercando la massa minima. Costo **atteso**
  basso a cache non satura, **peggiore = O(n_slot)**.
- **Ramo 2 (LRU, `:1931-1956`)**: `continue` sui transiti; **`break` immediato** al
  primo slot **non residente** (`:1941-1944`); `continue` sui protetti da
  `predetto[]` **solo se `scudo || dma`** (`:1945-1951`) — nota che **`cura` NON
  compare in questa condizione**. Poi minimo di `ultimo[]`. **Nessuna altra uscita:
  a cache satura il ciclo e' SEMPRE O(n_slot) completo.** Fallback ai protetti a `:1957`.
- **Ramo 3 (cura/scudo/dma, `:1981-1998`)**: **nessun break**, una sola scansione
  completa che tiene il primo candidato per ciascuna delle 5 classi, poi sceglie
  per priorita' (`:1999-2005`). **Sempre O(n_slot)**, e in piu' se la classe scelta
  e' >= 3 **azzera `usato[]` su tutti gli slot**: un **secondo O(n_slot)** (`:2014-2018`).
- **Ramo 4 (orologio, `:2044-2053`)**: uscita al primo slot con `usato == 0`,
  consumando le seconde chance. Costo **atteso O(1)-O(pochi)**, **peggiore
  3 x n_slot** (il `while` e' il tetto anti-loop).

### 1.3 QUALE RAMO SI PRENDE DAVVERO con `LRU=1` e `SFRATTO_PAR=1`

**[LETTO] Nessuno dei quattro, sul cammino a domanda.**

`decidi_fili` (`:2899-2902`) ritorna `CACHE_ESPERTI_SFRATTO_FILI = 256` se e solo se
`sfratto_par && lru && !politica_massa`. Il lancio e' quindi
`kern_decidi<<<1, 256>>>` (`:2991`, `:3284`), il kernel vede `par = blockDim.x > 1`
(`:2497`) e a `:2612` sceglie:

```
const int vittima = par ? cache_vittima_par(c, false, coop)
                        : cache_vittima(c, false);
```

Con la config si prende **`cache_vittima_par`** (`:2184-2205`), che replica **solo il
ramo LRU** e lo fa cosi':
1. `cache_vittima_par_prepara` (`:2175-2182`, solo filo 0, prima della barriera A):
   una tacca di massa + `coop.mano = *c.mano`;
2. `sfratto_coop_scansiona` (`:2120-2168`, **tutto il blocco, stesso sito**):
   `for (slot = filo; slot < c.n_slot; slot += 256)` — la scansione a passo di
   blocco — poi 8 giri di riduzione ad albero con `__syncthreads`;
3. la vittima e' `coop.rango[0] + mano` (`:2189-2190`), le mutazioni solo al filo 0
   (`:2193-2203`).

**[LETTO]** L'identita' e' garantita dalla **chiave lessicografica**
`(classe, ultimo, rango dalla mano)` (`:2139-2148`), con `classe` 0 = non residente,
1 = residente, 2 = protetto: riproduce (a) primo non residente, (b) minimo `ultimo`
coi pareggi al primo dalla mano, (c) protetti solo in ultima istanza. Il rango e'
distinto per ogni slot ⇒ **il minimo e' unico ⇒ la vittima non dipende dall'ordine
dell'albero**. Argomentazione a `:2082-2097`.

**[LETTO] Ma `cache_vittima` SEQUENZIALE resta viva in un solo posto:
`kern_prenota`** (`:2724`, `:2814`), che gira `<<<1,1>>>` (`:3144`).
**Con `W=0` `kern_prenota` NON VIENE MAI LANCIATO** (vedi §5): quindi nella config
di riferimento **la funzione `cache_vittima` e' codice morto**, e i quattro cicli
delle righe 1890/1931/1981/2044 **non vengono eseguiti mai**.

### 1.4 Costo atteso e peggiore in funzione di `n_slot`

**[LETTO]** Ramo effettivo (`cache_vittima_par`), **per sfratto**:
- iterazioni per filo: `ceil(n_slot / 256)` → **2** a 512, **2** a 448, **2** a 339, **1** a 256;
- **transazioni di memoria totali**: `n_slot` letture di `chi[]` (coalescenti),
  `n_slot` letture **sparse** di `dove[]` (gather casuale, `:2135`), `n_slot`
  letture di `ultimo[]` (8 B, coalescenti) ⇒ **~16 x n_slot byte toccati per sfratto**;
- + 9 `__syncthreads` (1 a `:2156` + 8 di riduzione).
- **Non c'e' uscita anticipata**: la scansione parallela visita **sempre tutti gli
  `n_slot`**, anche quando esiste uno slot non residente. Il caso atteso **coincide
  col caso peggiore**: `Θ(n_slot)` transazioni, `Θ(n_slot/256)` iterazioni per filo.

**[LETTO]** Su questo cammino **ogni buco produce esattamente uno sfratto**
(`:2597-2613`: `if (!servito) comando = 1` ⇒ `cache_vittima_par`) e non ci sono
altri produttori di sfratti, perche' `vittime_prefetch` puo' crescere solo in
`kern_prenota`, che non gira. **Quindi `sfratti == buchi`** nella config di
riferimento.

**[LETTO] Ed e' anche un cancello di coerenza gratis.** I due contatori NON hanno lo
stesso cancello: `buchi` sale solo `if (conta)` (`:2634`), `vittime_domanda` sale a
**ogni** sfratto (`:2202`), senza guardare `conta`. Coincidono solo perche' le
chiamate 2 e 3 della terna (o le fasi 1 e 2 del fork) sono **tutte colpi** e non
sfrattano mai. **Se nel log `vittime cura domanda` > `buchi`, allora le fasi non
contate stanno mancando la cache** — cioe' la residenza si e' mossa fra gate e up,
che nel fork sarebbe un difetto grave. Vale la pena controllarlo a ogni dump.

### 1.5 IL FATTO MISURATO: perche' l'attesa scala con la CAPIENZA e NON con gli sfratti

I dati: attesa host per grafo **512 → 6,17-6,21 ms; 448 → 6,33-6,76; 339 → 5,02;
256 → 15,17** con sfratti **88.588 / 99.422 / 106.913** (piu' sfratti a meno slot).

**[LETTO] Il solo termine O(capienza) del file e' la scansione della vittima.** Con
sfratti = buchi, il lavoro totale di scansione per corsa e' `sfratti x n_slot`:

| slot | sfratti | sfratti x n_slot | normalizzato | attesa misurata | normalizzata |
|---|---|---|---|---|---|
| 512 | 88.588 | 45,3 M | 1,000 | 6,19 | 1,000 |
| 448 | 99.422 | 44,5 M | 0,982 | ~6,55 | 1,058 |
| 339 | 106.913 | 36,2 M | 0,799 | 5,02 | **0,811** |

**[DEDOTTO]** Il prodotto `sfratti x n_slot` riproduce il segno e (a 339) quasi
esattamente il rapporto misurato — **inclusa la parte controintuitiva**: piu'
sfratti con meno slot, e meno attesa lo stesso, perche' ogni sfratto costa MENO.
Il punto 448 e' fuori del 7,5%, ma li' la misura stessa ha una forbice del ±3%.
**Il modello "sfratti" da solo e' falsificato; il modello "sfratti x capienza" no.**

**[DEDOTTO] MA IL MODELLO NON CHIUDE IN VALORE ASSOLUTO.** Con ~43 strati x ~2,4
sfratti = ~100 sfratti/token, spiegare 6,19 ms vorrebbe **~60 µs per sfratto**,
cioe' ~120 ns per slot visitato con 256 fili in parallelo. E' un ordine di grandezza
(o due) fuori da qualunque stima ragionevole per due giri di gather su `dove[]`,
un array da 64 KiB che sta **interamente in L2**. Quindi:
- la scansione spiega bene la **differenza** fra i bracci;
- **non** spiega il **livello** dell'attesa.

**[DEDOTTO] IL SECONDO CANDIDATO, ED E' PIU' FORTE DEL PRIMO: l'attesa non traccia
gli slot, traccia la VRAM LIBERA.** Coi numeri della domanda 6:

| slot | VRAM libera | attesa |
|---|---|---|
| 512 | **206 MiB** | 6,19 |
| 448 | **228 MiB** | ~6,55 |
| 339 | **874 MiB** | 5,02 |

512 e 448 hanno **quasi lo stesso margine** (206 vs 228 MiB) e **quasi la stessa
attesa**; 339 ha **4x il margine** e l'attesa crolla. La correlazione con il margine
e' molto piu' pulita di quella con la capienza — ed e' esattamente il tipo di costo
**HOST** (residency management WDDM alla sottomissione) che una sonda «attesa host
per grafo» misura. **Non l'ho verificato**: e' la prima cosa da falsificare, e si
falsifica **senza toccare gli slot**, con `LLAMA_VRAM_ZAVORRA` (`:287-316`), che
esiste in questo file **proprio per separare capienza da margine** e che a 512 slot
con zavorra 0 vs 600 MiB darebbe la risposta in due bracci.

**[LETTO] Il punto a 256 slot e' un regime diverso e va tenuto fuori dal fit**:
li' i colpi crollano al 11%, quindi i buchi ~x2,2 rispetto a 512 e i **byte copiati**
(6,75 MiB per buco, `kern_fj_copia`) esplodono. `:3917-3919` stampa proprio
`byte a domanda = buchi x byte_slot`. A 256 domina il trasporto, non la scansione.

---

## 2. I contatori: dove, come, e la trappola del confronto

Risposta operativa completa in **§A.1-A.4**. In sintesi, e questo e' il punto che
riguarda il sospetto di aver letto istantanee diverse:

1. **[LETTO] Sono CUMULATIVI dall'init, mai azzerati** (`:1569` unica `memset`;
   `dump` a `:3768` **non scrive**). Con `BATTITO=45` il log contiene **N dump
   progressivi**: il primo dump di una corsa e il quinto non sono confrontabili
   fra loro **ne'** con dump di un'altra corsa presi a un'altra profondita'.
   **Confrontare due corse richiede o l'ultimo dump di entrambe, o la differenza
   fra due dump alla stessa distanza in token.**
2. **[LETTO] `vive-censurate` e' l'unica ISTANTANEA** e sta sulla stessa riga dei
   cumulativi (`:3802-3817`): e' `popcount(installato[])` calcolato sull'host a
   `:3803-3810`, limitato da `n_slot`. Fra 512 e 339 slot ha due soffitti diversi.
3. **[LETTO] Il log contiene PIU' dump con lo stesso prefisso.** Bersaglio e bozza
   sono due runtime (`ggml-cuda.cu:1482`) con battiti indipendenti. **Solo la riga
   `… : dump contatori` (`:3775`) e la riga `acceptmoe[…]` (`:3932`) sono etichettate**;
   tutte le altre dodici righe hanno il prefisso `cache-esperti:` **hard-coded**.
   Un `grep "cache-esperti: domanda"` restituisce **sia** il bersaglio **sia** la
   bozza, mescolati nell'ordine temporale.
4. **[LETTO]** `miss %` e `colpi %` sono complementari (stesso denominatore
   `colpi+buchi`): non sono due misure.
5. **[LETTO]** `in ritardo … % dei prenotati` divide per `prenotati`, che con W=0 e' 0:
   lo `0.0%` stampato non significa niente (`:3790`).

---

## 3. `FORK`, `FORK_BLOCCHI`, `FORK_ESATTO`

### 3.1 Cosa fa `FORK` (noi: 2)

**[LETTO]** Precondizioni verificate in init, tutte fail-loud:
`W=0` **esplicito** (`:1604-1611`), solo bersaglio (`:1596`), incompatibile con
DMA/DOMANDA_DMA (`:1639-1642`), allocazioni riuscite (`:1706-1730`), terna su **un
solo stream** (`:3256-3259`, altrimenti `GGML_ABORT`).

**[LETTO]** La terna gate/up/down di ogni strato viene spezzata in tre fasi
(`ggml_cuda_cache_esperti_fork_fase`, `:3238-3261`; consumate a `ggml-cuda.cu:2275-2356`):

- **fase 0 (gate)** — `fork_gate` (`:3263-3314`):
  1. `kern_decidi<<<1,256>>>` sul flusso di calcolo, slot nel **tampone persistente**
     `fj_slot` (`:3284`);
  2. `kern_fj_maschera<<<1,1>>>` (`:3287`): fotografa `c.lista` in `fj_lista` e
     costruisce `fj_maschera[i]` = 1 se lo slot della colonna i e' fra le vittime
     appena installate (`:3168-3184`);
  3. `cudaEventRecord(ev_fork)` + `cudaStreamWaitEvent(stream_fork, ev_fork)` +
     **`kern_fj_copia<<<FORK_BLOCCHI, 256>>>` sullo stream fork** (`:3292-3297`);
  4. `cudaEventRecord(ev_copia, stream_fork)` (`:3301`);
  5. sul flusso di calcolo: `ggml_cuda_mul_mat_vec_q_maschera(..., voluto=0)` —
     **solo le colonne residenti** (`ggml-cuda.cu:2306`);
  6. le viste ombra si salvano in `fj_salva` (`ggml-cuda.cu:2310-2314`).
- **fase 1 (up)** — `ggml-cuda.cu:2318-2353`: `assicura` (tutti colpi), passata
  residente dell'up, **poi** `fork_join` (`:3316-3321`,
  `cudaStreamWaitEvent(stream, ev_copia)`), **poi** le due passate `voluto=1`
  (mancanti del gate salvato + mancanti dell'up).
- **fase 2 (down)**: cammino normale (`ggml-cuda.cu:2355`).

**[LETTO]** `FORK=2` aggiunge **due lanci per strato**: `kern_fj_sonda_fork` sullo
stream fork (`:3299`) e `kern_fj_sonda_calcolo` sul flusso di calcolo prima del join
(`:3318`); la sonda misura quante volte la copia era **gia' finita** (`:3224-3231`,
stampa a `:3941-3946`). E' una sonda diagnostica: **con FORK=2 stiamo pagando due
lanci per strato x 43 strati = 86 lanci/token che FORK=1 non paga.**

### 3.2 Perche' cambia il risultato bit per bit

**[LETTO] La spiegazione dichiarata** (`cache-esperti.cuh:513-533`, `cu:1647-1663`):
il fork non spezza nessuna somma — ogni colonna (posizione-esperto, token) e'
calcolata **per intero** da una sola delle due passate. L'unica divergenza sarebbe la
**scelta del kernel a UN TOKEN**: il cammino non forkato usa `mul_mat_vec_q`
generico (piu' warp per blocco, somme parziali in shared + `warp_reduce_sum`),
il fork usa il MoE mascherato `mul_mat_vec_q_moe_maschera` (`mmvq.cu:1336`, **un
warp per colonna**, riduzione solo dentro il warp). Stesso valore matematico,
**albero di riduzione diverso ⇒ arrotondamenti diversi**. A batch >= 2 entrambi i
cammini usano gia' il kernel MoE, quindi li' sarebbe bit-uguale per costruzione.

**[LETTO] MA IL CODICE STESSO DICE CHE QUESTA SPIEGAZIONE NON REGGE** (`:1612-1638`,
commento di `FORK_SERIALE`): «Il fork non e' bit-esatto e **la causa non e' stata
trovata**». Il confronto SASS del clone mascherato contro il non mascherato da'
FADD 10=10, FFMA 2=2, FMUL 2=2, SHFL.BFLY 10=10: **aritmetica e albero identici
istruzione per istruzione**. Restano due ipotesi:
- **(B)** la mappa maschera↔slot e' sbagliata a batch >= 2;
- **(C)** una colonna legge uno slot **mentre la copia lo riscrive**.

**[DEDOTTO] Sull'ipotesi (B) la lettura del codice dice che e' sana**:
`kern_fj_maschera` scrive `maschera[i]` con `i = token*ne0 + posizione`
(`:3176-3182`, indicizzato come `slot_out` che `kern_decidi` riempie con lo stesso
indice lineare, `:2524`/`:2553`), e il kernel mascherato legge
`maschera[token_idx * nchannels_tot + channel_dst]` (`mmvq.cu:1373`) con
`nchannels_tot = nchannels_dst = dst->ne[1] = ids->ne[0] = ne0` (`mmvq.cu:1257`).
Gli indici **coincidono**. Se questa lettura e' giusta, **(B) e' falsificato da
codice e resta (C)** — cioe' una corsa d'ordine vera. Da confermare con
`FORK_SERIALE=1`, che e' esattamente lo strumento previsto.

**[DEDOTTO] Dove (C) puo' mordere**, e non e' dove il commento la cerca:
`kern_decidi` della fase 0 **aggiorna `dove/chi` PRIMA che i byte siano copiati**
(`:2623-2631`, la copia parte dopo, sullo stream fork). Da quel momento **ogni altro
lettore delle tabelle vede lo slot come RESIDENTE** anche se i byte sono in volo. I
lettori sono: `kern_partiziona` (`:3396-3399`) e `kern_acceptmoe` (`:3514-3515`),
entrambi validano su `dove[]+chi[]` e **non hanno modo di sapere che la copia e'
in volo** — il bit `CACHE_ESPERTI_TRANSITO` protegge solo il cammino prefetch, non
il cammino a domanda del fork. Se uno di questi due nodi sta nel grafo fra la fase 0
e il join, promette alla GPU byte che non sono ancora arrivati.

### 3.3 `FORK_BLOCCHI` (noi: 8)

**[LETTO]** Letta a `:1644-1646` (difetto **32**), usata **solo** a `:3294`:
`kern_fj_copia<<<runtime->fj_blocchi, 256, 0, stream_fork>>>`.
Il commento a `:1664-1679` riporta la misura: `kern_fj_copia` muove 832 MiB/token in
34,36 ms = 23,6 GiB/s (gia' al tetto PCIe), quindi **il costo non e' la banda, sono
gli SM rubati alla MMVQ concorrente**; 8 blocchi battono 112 **coprendo venti volte
meno** (12,42 contro 11,91 t/s).

**[LETTO]** `FORK_BLOCCHI` **non tocca** `kern_copia` (la copia del cammino non
forkato), che resta su `blocchi_copia()` = 4 x n_SM (`:2884-2891`; su una 3060 a 28
SM = **112 blocchi**).

### 3.4 `FORK_ESATTO`

**[LETTO]** Letta a `:1660-1663`, clampata a 0..2; ignorata ad alta voce se il fork
e' spento (`:1736-1741`). Consumata a `ggml-cuda.cu:2273`:
```
if (fj_attivo && !(fj_esatto == 1 && fj_untoken)) { …fork… }
```
- **0** (nostra config) = comportamento di oggi: anche a un token si usa il MoE
  mascherato;
- **1** = i forward a **un token** escono del tutto dal fork e ripercorrono il
  cammino di `FORK=0` (bit-esatto per costruzione, si perde la sovrapposizione li');
- **2** = restano nel fork ma sul **clone mascherato del kernel generico**
  (`mmvq.cu:1458 mul_mat_vec_q_maschera`, con `static_assert(ncols_dst == 1)` a
  `mmvq.cu:1466`): bit-esatto **e** sovrapposto, kernel nuovo.

**[LETTO]** La decisione e' uniforme su tutto il forward (`dst->ne[2]` e' lo stesso
per tutti i MUL_MAT_ID del grafo, `ggml-cuda.cu:2260-2264`), quindi la terna non
puo' restare aperta a meta'. Il **testimone** e' `fj_un_token` (`:3327-3329`,
stampato a `:3952-3954`): se resta 0 e lo SHA diverge lo stesso, `ESATTO` sta
curando la cosa sbagliata.

---

## 4. `kern_copia`: come muove un esperto

**[LETTO]** `kern_copia` (`:2853-2880`) riceve la struct per valore piu' le tre basi
in memoria mappata e i tre passi. Legge `n = c.lista[0]` (scritto da `kern_decidi`
a `:2644`) e per **ogni** voce `j`:

```
voce  = c.lista[1+j];  esperto = voce & 0xffff;  slot = voce >> 16;   // :2863-2865
dst   = (char*)c.slab + slot * c.byte_slot;                            // :2866
```
poi **tre cicli grid-stride separati, uno per tensore** (`:2868-2878`):
gate a `dst`, up a `dst + off_up`, down a `dst + off_down`, ciascuno con
`for (i = filo; i < passo_X / sizeof(int4); i += gridDim.x*blockDim.x) dX[i] = sX[i];`

Quindi: **i "tre pezzi" sono i tre tensori dell'esperto** — gate, up, down — che
nello slot stanno **contigui** (`byte_slot = gate+up+down` arrotondato, `:1188-1191`;
`off_up`/`off_down` a `:1192-1193`). Una sola voce di residenza copre tutti e tre
(`cache-esperti.cuh:103-105`).

**[LETTO] Quanti blocchi**: `blocchi_copia()` (`:2884-2891`) = `4 * multiProcessorCount`,
deciso **una volta all'avvio** (`static const`), ripiego 96. Su una 3060 (28 SM) =
**112 blocchi x 256 fili = 28.672 fili**. Il commento a `:2846-2852` spiega il
perche': a un blocco solo si misurarono ~4,9 GiB/s (4 KiB in volo su ~1 µs di
latenza PCIe), con la griglia intera i byte in volo diventano ~450 KiB e il bus
satura.

**[DEDOTTO]** Aritmetica su 6,75 MiB per esperto = 7.077.888 B = **442.368 `int4`**:
- `kern_copia` (112 blocchi): **~15,4 `int4` per filo** per esperto, ~458 KiB in volo;
- `kern_fj_copia` con `FORK_BLOCCHI=8` (2.048 fili): **~216 `int4` per filo** per
  esperto, **~32 KiB in volo** — coerente col commento «per saturare il PCIe bastano
  ~25-50 KiB in volo (~10 blocchi)» (`:3188-3190`).

**[LETTO] Interazione con `FORK_BLOCCHI`**: `kern_fj_copia` (`:3191-3217`) e' un
**clone** di `kern_copia` con **una sola differenza**: legge `lista_fork` (l'istantanea
privata in `fj_lista`) invece di `c.lista`. Il motivo e' scritto a `:3152-3159`: il
`kern_decidi` della chiamata `up` **riscrive `c.lista[0] = 0`** mentre la copia gira
sullo stream fork; un blocco che leggesse il conteggio dopo quella scrittura
vedrebbe zero lavori e **i byte non arriverebbero, in silenzio**.

**[LETTO] E `kern_copia` continua a essere lanciato anche col fork acceso**: nelle
fasi 1 e 2 il cammino passa da `assicura` (`ggml-cuda.cu:2323`, `:2372`) che a
`:2998-3000` lancia sempre `kern_copia<<<112,256>>>`, «anche quando la lista sara'
vuota (~2 µs): il conteggio vive sul device e l'host non puo' saperlo» (`:2963-2966`).
**[DEDOTTO]** Sono **86 lanci a vuoto da 112 blocchi per token** (2 per strato x 43).

---

## 5. Le leve, una per una, con la raggiungibilita' VERIFICATA

### 5.1 `CURA` — **confermato: irraggiungibile con LRU=1, ma non del tutto morta**

**[LETTO]** Letta a `:1216-1218`. Il codice **si autodenuncia** a `:1318-1324`:
```
if (runtime->cache.cura && (runtime->cache.lru || runtime->cache.politica_massa))
    fprintf(stderr, "cache-esperti: CURA e' INERTE con lru=%d/massa=%d -- cache_vittima() esce nel ramo precedente…");
```
**Verificato**: `cache_vittima` prova `massa` (`:1886`) → `lru` (`:1925`) → 
`(cura||scudo||dma)` (`:1973`), ognuno con `return`. Con `lru=1` il **blocco a 5
classi non e' mai raggiunto**. ✔ confermato.

**[LETTO] MA la denuncia e' INCOMPLETA in due modi:**
1. `CURA` **non e' inerte del tutto** con LRU: `if (c.cura || c.scudo || c.dma)`
   e' vero anche in `kern_decidi:2500` (`lanci_cura++`, `cache_scadi_previsioni`),
   `:2567` (spin su transito, `cura>=2`), `:2627` (`predetto[vittima]=0`), e in
   `cache_promuovi:2309-2327`. Quindi con `CURA=1, LRU=1` la cache **paga il costo**
   di marcare/scadere `predetto[]` e **non ne raccoglie mai il beneficio**: il ramo
   LRU legge `predetto[]` solo sotto `(c.scudo || c.dma)` (`:1945`) — **`cura` non
   compare in quella condizione**. E' peggio che inerte: e' **costo puro**.
2. Con `cura >= 2` viene allocato anche `batch_slot[n_slot]` (`:1387-1389`).

### 5.2 `SCUDO` — **confermato "marca ma non prenota", e c'e' di peggio**

**[LETTO]** Letta a `:1243-1244`. La denuncia del codice e' a `:1329-1333`:
«SCUDO senza DMA = protezione SOLA — `kern_prenota` marca i residenti e NON prenota».
**Verificato** a `:2673-2683`:
```
if (c.scudo && !c.dma) {
    for (i…) if (slot >= 0 && c.chi[slot] == k) cache_predici(c, strato, esperto, slot);
    return;                       // <-- ritorna PRIMA di qualunque prenotazione
}
```
✔ confermato.

**[LETTO] MA C'E' UN LIVELLO IN PIU', E LA DENUNCIA NON LO DICE.**
`kern_prenota` e' lanciato **solo** da `ggml_cuda_cache_esperti_prenota` (`:3137-3145`),
che e' chiamata **solo** da `ggml-cuda.cu:4761`, dentro il blocco che intercetta i
nodi `GGML_OP_VIEW` di nome `"cache_pf-*"` (`ggml-cuda.cu:4714-4715`). Quei nodi li
costruisce `src/models/deepseek4.cpp:1420-1436` **dentro `for (k = 1; k <= cache_w; k++)`**,
con `cache_w = LLAMA_CACHE_ESPERTI_W` (difetto **0**, `deepseek4.cpp:1396-1400`).

**Con `W=0` il ciclo non gira, non esiste nessun nodo `cache_pf-*`, `kern_prenota`
non viene MAI lanciato.** Quindi:
- **`SCUDO` non marca neppure**: nessuno chiama mai `cache_predici` → `predetto[]`
  resta tutto 0 → la classe "protetta" della scansione LRU (`:1945`, `:2142`) e'
  **sempre vuota**. `SCUDO` e' **doppiamente morta**, non solo "protezione sola".

### 5.3 ALTRI CASI UGUALI — cercati, e ne ho trovati **cinque**

**[LETTO] (a) `PREFETCH_FILTRO`** (`filtro_mancanti`, letta `:1226-1227`): usata in
**un solo punto**, `kern_prenota:2695` (sceglie fra il cammino storico e il cammino
"mancanti"). `kern_prenota` non gira ⇒ **MORTA-STRUTTURALE**. Nessun avviso in init.
Viene pero' **stampata nel dump** (`:3896-3898`) accanto a `prefetch mancanti=…`,
il che invita a leggerla come una leva misurata.

**[LETTO] (b) `CODA_MAX`** (letta `:1230-1232`): usata solo a `:2695` e `:2794`,
dentro `kern_prenota` ⇒ **MORTA-STRUTTURALE**. Anche lei stampata nel dump (`:3896`).

**[LETTO] (c) `SPIN`** (letta `:1221-1223`, difetto **256**): usata in **un solo
punto**, `kern_decidi:2571`, dentro `if (c.cura >= 2 && in_transito)`. Con `CURA=0`
il ramo non esiste; anche con `CURA=2` servirebbe uno slot IN TRANSITO, che solo
`kern_prenota` puo' creare. **Doppiamente morta.** Stampata nel dump a `:3902-3905`
insieme a `spin esauriti=…`, che sara' sempre 0.

**[LETTO] (d) `PF_TUTTI`** (`ggml-cuda.cu:4734-4746`, difetto acceso): sta **dentro**
il blocco `cache_pf-` ⇒ **MORTA-STRUTTURALE con W=0**.

**[LETTO] (e) `MASSA`** (letta `:1239-1240`): non e' irraggiungibile — e' il
**contrario**, e' pericolosa: e' il **primo** ramo di `cache_vittima` (`:1886`),
quindi `MASSA=1` **scavalca silenziosamente `LRU=1`**. In piu' spegne `SFRATTO_PAR`
via `decidi_fili` (`:2901`) e viene rifiutata da DMA (`:1281-1288`). L'unico avviso
che esiste e' quello di `SFRATTO_PAR` (`:1264-1267`), non uno che dica "MASSA vince
su LRU".

**[LETTO] (f) — e questo e' quello che mi preoccupa di piu' —**
`ggml_cuda_cache_esperti_predizione_attiva` (`:3012-3014`) ritorna
`!cache_dma_strato_quieto(runtime)`, che con DMA spento e' **sempre `true`**. Il
nome dice "predizione attiva" e con `W=0` la predizione **non esiste**: qualunque
chiamante che decida in base a questa funzione sta leggendo un `true` che non
significa quello che dice. (Chiamata da `src/llama-context.cpp` / `server-context.cpp`
attraverso il registro dei backend.)

### 5.4 `DMA` e `SFRATTO_PAR` e `PRIORITA`, per completezza

- **[LETTO] `DMA`** (`:1275-1290`): pretende LRU pura (`:1281-1288`); **incompatibile
  col fork** (`:1639-1642`, «FORK/JOIN e DMA non sono componibili: fork SPENTO»).
  Con `FORK=2` non si puo' accendere senza perdere il fork. Difetto 0 ⇒ morta.
- **[LETTO] `SFRATTO_PAR`** (`:1255-1268`): **VIVA**. Cancelli: `cc >= 7.0`
  (`:1257-1263`, la 3060 e' 8.6 ⇒ passa) e avviso se non c'e' LRU pura (`:1264-1267`).
  Effetto: `decidi_fili` (`:2899-2902`) → `kern_decidi<<<1,256>>>`.
- **[LETTO] `FORK_PRIORITA`** (`:1684-1705`): **raggiungibile** (dentro `fj_leva>0`),
  difetto 0. Se accesa avvisa quando `prio_lo == prio_hi` (device senza priorita'
  distinte) ⇒ leva inerte, e **lo dice**. E' il modello di avviso giusto.

---

## 6. Dove sta la VRAM della cache, e perche' i conti non tornano

### 6.1 Le allocazioni, tutte

**[LETTO]** Lo **slab** e' l'unica allocazione proporzionale agli slot:
```
byte_slab = (size_t) n_slot * runtime->cache.byte_slot;                       // :1353
cudaMalloc(&runtime->cache.slab, byte_slab)                                   // :1359
```
`byte_slot = byte_gate + byte_up + byte_down`, arrotondato in su al **minimo comune
multiplo delle tre taglie di blocco quantizzato** (`:1188-1191`; l'allineamento
nasce a `:772-782`, perche' `mmvq` divide `nb[2]` per la taglia del blocco e
altrimenti lo stride **tronca in silenzio**).
`512 x 6,75 MiB = 3.456 MiB`. **Fallimento = fail-loud e cache spenta**, mai ripiego
a meta' taglia (`:1355-1364`).

**[LETTO]** Le altre allocazioni device sono **irrisorie**:

| buffer | riga | byte a 512 slot |
|---|---|---|
| `chi[n_slot]` | `:1374` | 2,0 KiB |
| `usato[n_slot]` | `:1375` | 512 B |
| `ultimo[n_slot]` (solo LRU) | `:1404` | 4,0 KiB |
| `riusi_installazione[n_slot]` | `:1379` | 2,0 KiB |
| `installato[n_slot]` | `:1380` | 512 B |
| `dove[64*256]`, `massa[64*256]` | `:1373`, `:1378` | 64 + 64 KiB |
| `atterrato[256]`, `confermata`, `transiti`, `mano`, `mano_massa`, `lista[65]` | `:1376-1409` | ~1,5 KiB |
| `colpi[32]`, `am_cont[8]` | `:1410`, `:1442` | 320 B |
| fork: `fj_slot[64]`, `fj_maschera[64]`, `fj_lista[65]`, `fj_sonda[4]` | `:1710-1713` | ~600 B |
| `predetto/predetti_n/predetti` | `:1382-1386` | **non allocati** con cura=scudo=dma=0 |
| `batch_slot` | `:1388` | **non allocato** (serve `cura>=2`) |

**Totale non-slab: ~140 KiB.** Il resto della curva slot↔VRAM e' **tutto** lo slab.

**[LETTO]** L'anello di prefetch (`:1447`) e' `cudaHostAlloc(...Mapped)` = **memoria
HOST pinnata** (34,9 KiB), non VRAM. Idem `dma_rotte_host`, `dma_vera_host`,
`dma_gate_colpi_host`, `domanda_lista_host`.

**[LETTO] Nessun pool temporaneo dentro `cache-esperti.cu`**: tutte le `cudaMalloc`
sono in `init` (`:1359-1442`), piu' due temporanee **solo** nella ricarica calda
(`:924-925`, subito liberate a `:943-944`).

### 6.2 Il pool temporaneo esiste, ma sta FUORI, e non restituisce mai

**[LETTO]** Il cammino cache alloca dal pool del contesto CUDA:
`ggml_cuda_pool_alloc<int32_t> slot_dev(ctx.pool(), n_id)` (`ggml-cuda.cu:2362`,
`:2322`) — pochi interi. Ma il **pool** e' l'oggetto interessante:

- **`ggml_cuda_pool_vmm`** (`ggml-cuda.cu:486-628`, usato se il device supporta VMM,
  rilevato a `:236-247`; `GGML_USE_VMM` e' definito per difetto, `common.cuh:253-255`):
  `alloc()` **mappa nuova memoria fisica** con `cuMemCreate` quando serve
  (`:524-598`) e `pool_size += reserve_size` (`:598`). **`free()` (`:618-627`)
  decrementa solo `pool_used`: `pool_size` non scende MAI** finche' il contesto vive.
  E' un allocatore **a massimo storico**.
- **`ggml_cuda_pool_leg`** (`:369-482`, ripiego): tiene fino a 256 buffer in cache
  **per sempre** (`free()` a `:468-481` li rimette nel pool), sovralloca del **5%**
  (`look_ahead_size = 1.05*size`, `:442-443`) e li libera **solo** se una
  `cudaMalloc` fallisce (`clear_pool()` a `:446-457`) o alla distruzione.

### 6.3 L'aritmetica misurata, e cosa dice

| slot | slab | VRAM occupata | VRAM libera | Δslab vs 512 | ΔVRAM vs 512 | **assorbito** |
|---|---|---|---|---|---|---|
| 512 | 3.456 MiB | 11.910 | 206 | — | — | — |
| 448 | 3.024 | 11.888 | 228 | −432 | **−22** | **410** |
| 339 | 2.288 | 11.242 | 874 | −1.168 | **−668** | **500** |

(le tre righe chiudono: 11.910+206 = 11.888+228 = 11.242+874 = 12.116 MiB, cioe' la
stessa quota di VRAM contabilizzabile — la misura e' coerente.)

**Da 448 a 339** si liberano 736 MiB di slab e la VRAM occupata scende di **646**:
passa l'88%. **Da 512 a 448** si liberano 432 MiB e ne scendono **22**: passa il 5%.

**[DEDOTTO] La forma della curva e' la firma di un consumatore CON UN SOFFITTO**:
assorbe tutto quello che gli si libera **finche' raggiunge il proprio massimo
storico (~410-500 MiB)**, poi smette. Il pool descritto in §6.2 ha **esattamente**
quella forma: cresce fino al picco di domanda e non torna piu' indietro.

**[DEDOTTO] Il meccanismo piu' probabile**: a 512 slot lo slab (3.456 MiB) viene
preso **per primo** — `ggml_cuda_cache_esperti_forse_init` e' chiamata **all'ingresso
di `graph_compute`** (`ggml-cuda.cu:4889`), quindi **prima** che i nodi di quel grafo
allochino dal pool. Con 206 MiB residui il pool non riesce a salire al suo massimo
naturale e resta compresso; con 448 slot ha 432 MiB in piu' e ci sale; da li' in poi
e' saturo e i megabyte liberati passano davvero. Con `ggml_cuda_pool_leg` questo e'
letterale: `alloc` fallisce → `clear_pool()` → riprova (`:446-457`), e il pool finisce
**piu' piccolo** proprio nel braccio a VRAM stretta.

**[NON VERIFICATO — e va verificato]** Non ho misurato **chi** e' il consumatore.
Candidati, in ordine di probabilita': (1) il pool CUDA (VMM o leg); (2) lo spazio di
lavoro cuBLAS, allocato pigramente per stream; (3) la memoria delle istanze di CUDA
graph (`cudaGraphInstantiate`, `ggml-cuda.cu:4845`, una per `graph_key`, e questo
fork ne tiene piu' d'una).

**[LETTO] LO STRUMENTO PER CHIUDERLA C'E' GIA' ED E' SPENTO.** Il pool VMM e' gia'
instrumentato: `ggml_cuda_kv_ring_vram_trace(device, "cuda_vmm_pool_before/after_cuMemCreate", …)`
a `ggml-cuda.cu:537-557`, e `ggml_cuda_device_malloc` a `:132`. La sonda stampa
`free/used/delta_used/cumulative_used` in MiB (`kv-ring.cu:125-153`). Serve compilare
con `LLAMA_KV_RING_VRAM_TRACE_BUILD` e accendere `LLAMA_KV_RING_VRAM_TRACE=1`:
**due bracci e la domanda e' chiusa**, senza scrivere una riga nuova.

### 6.4 E la conseguenza per la domanda 1

**[DEDOTTO]** Se il consumatore ha un soffitto, allora **fra 512 e 448 il margine di
VRAM libera non cambia** (206 → 228 MiB) e infatti **l'attesa non cambia**
(6,19 → ~6,55); fra 448 e 339 il margine quadruplica e **l'attesa crolla**. La
capienza e' una **variabile confondente**: quello che si muove davvero e' il margine.
Il braccio pulito e' `LLAMA_VRAM_ZAVORRA` a capienza ferma (`:274-316`) — che questo
file contiene **proprio per questo motivo**, scritto nero su bianco a `:276-281`:
«in ~200 corse non e' mai stato possibile [separare capienza da margine] perche' le
due cose si sono sempre mosse insieme».

---

# COSE CHE NON TORNANO

1. **[LETTO] Il fork non e' bit-esatto e il codice lo sa** (`:1612-1638`), ma
   l'intestazione `.cuh:513-522` continua a promettere «a batch>=2 il fork e'
   bit-uguale **per costruzione**». Le due affermazioni non possono essere entrambe
   vere. La configurazione in produzione (`FORK=2`, `FORK_ESATTO=0`) e' quella **non
   bit-esatta**: **i colpi e lo SHA di questi bracci non sono confrontabili con
   quelli di `FORK=0`.**

2. **[DEDOTTO] `kern_decidi` pubblica la residenza prima che i byte esistano.**
   `:2623-2631` scrive `chi/dove/usato/installato` e **poi** la copia parte sullo
   stream fork. `kern_partiziona` (`:3396`) e `kern_acceptmoe` (`:3514`) validano su
   `dove[]+chi[]` e **non vedono** che i byte sono in volo — il bit `TRANSITO`
   copre solo il prefetch. Se uno di quei due nodi cade fra la fase 0 e il join,
   promette alla GPU byte non ancora arrivati. E' il candidato (C) del commento
   `FORK_SERIALE`, ma **fuori** dal punto in cui il commento lo cerca.

3. **[LETTO] Con `LRU=1` il bit `usato[]` non viene mai azzerato.** Il ramo LRU
   (`:1931-1971`) e `cache_vittima_par` (`:2184-2205`) non toccano `usato[]`; lo
   azzera solo il ramo cura (`:2014-2018`) e l'orologio (`:2049`), entrambi
   irraggiungibili. `usato` viene messo a 1 su ogni colpo (`:2547`) e su ogni
   installazione (`:2624`) e **non torna mai a 0**. Conseguenza: in
   `kern_partiziona` (`:3396-3399`) la chiave vale 2 per **tutti** i residenti e la
   **classe 1 ("residente prossimo allo sfratto") e' sempre vuota** — la partizione
   dell'overlap degenera in due classi invece di tre. Nessuno lo dice.

4. **[LETTO] 86 lanci a vuoto di `kern_copia` per token.** Con il fork acceso le
   fasi 1 e 2 passano da `assicura`, che lancia sempre `kern_copia<<<112,256>>>`
   (`:2998`) su una lista che sara' vuota per costruzione. Il commento a `:2963-2966`
   giustifica il lancio ("l'host non puo' sapere il conteggio"), ma **con il fork la
   fase e' nota all'host** (`fork_fase`, `:3238`) e per le fasi 1/2 il lancio si
   potrebbe saltare. **[DEDOTTO]** ~2 µs x 86 = ~170 µs/token, sul cammino critico.

5. **[LETTO] `FORK=2` costa 86 lanci in piu' per token** (`kern_fj_sonda_fork` +
   `kern_fj_sonda_calcolo`, `:3299`/`:3318`) e la sua uscita e' **solo diagnostica**
   (`:3941-3946`). Se la configurazione di produzione e' `FORK=2`, sta pagando una
   sonda. `FORK=1` da' lo stesso trasporto senza le sonde: **la differenza fra 1 e 2
   non e' mai stata isolata** per quanto si vede dal codice.

6. **[LETTO] `SFRATTO_PAR` avvisa solo per il caso sbagliato.** `:1264-1267` avvisa
   se manca la LRU pura, ma **non** avvisa quando `n_slot` e' piccolo: con 256 slot
   e 256 fili la scansione e' un solo giro e la riduzione (8 `__syncthreads`) puo'
   costare piu' della scansione stessa. Per la bozza il codice lo sa e la spegne a
   mano (`:1207`, «32 slot: la scansione e' gia' corta»); per il bersaglio non c'e'
   nessun cancello analogo.

7. **[LETTO] Il thread di servizio gira sempre**, anche a DMA spento e W=0
   (`:1573-1577`, ciclo a `:686-730`): poll dell'anello + `sleep_for(100 µs)` dopo
   200 giri a vuoto. E' un thread host che non serve a niente nella config di
   riferimento e non c'e' nessuna leva per non crearlo.

8. **[LETTO] `predizione_attiva()` mente** (`:3012-3014`): ritorna `true` con `W=0`,
   quando nessuna predizione viene mai emessa.

9. **[LETTO] Il dump stampa quattro leve morte come se fossero misurate**:
   `filtro`, `coda_max`, `spin`, e i contatori `prefetch mancanti / contropressione
   servizio / dma / spin esauriti / transiti riusati` (`:3896-3909`), tutti
   strutturalmente 0 con `W=0`. Uno zero da leva spenta e uno zero da kernel mai
   lanciato **si leggono identici** — e' esattamente l'errore di metodo che il file
   combatte altrove con i testimoni (`:3818-3834`, `:3920-3928`, `:3947-3954`).
   **Manca il testimone del prefetch**: un contatore "lanci di `kern_prenota` visti
   dal device" renderebbe distinguibili i due silenzi.

10. **[LETTO] `CACHE_ESPERTI_MAX_STRATI` = 64 (`:73`) ma `CACHE_ESPERTI_STRATI_MAX`
    = 128 (`:48`)**: due tetti diversi, nomi quasi identici (differiscono solo per
    l'ordine delle ultime due parole), usati in tabelle diverse (`dove/massa/predetti`
    contro `pub_host/div`). E la chiave impacchetta lo strato su **6 bit** in
    `cache_registra_sfratto` (`(cm >> 16) & 0x3f`, `:1857`, `:1865`, `:1938`, ...)
    ma su 16 bit in `chiave_di` (`:1170`). Con 43 strati non morde; con >= 64
    strati la maschera `0x3f` **aliaserebbe in silenzio**.

11. **[LETTO] `dove` e' indicizzata in due modi diversi.** `chiave_di` usa
    `(strato << 16) | esperto` (`:1170`), ma **l'indice** di `dove/massa` e'
    `(strato << 8) | (esperto & 0xff)` (`:2535`, `:2628`, `:3396`, ...). I due
    impacchettamenti convivono correttamente solo perche' `n_esperti == 256` e'
    **preteso in init** (`:759-764`). Il vincolo e' verificato, ma la doppia
    convenzione e' una mina per chiunque tocchi il file.

12. **[LETTO] `blocchi_copia()` interroga sempre il DEVICE 0** (`:2887`,
    `cudaDeviceGetAttribute(&sm, cudaDevAttrMultiProcessorCount, 0)`) ed e' una
    `static const` calcolata una volta per processo. Su una macchina a una GPU non
    morde; su due GPU diverse la griglia di `kern_copia` sarebbe tarata sulla scheda
    sbagliata, in silenzio. (Coerente col fatto che il fork e' dichiarato
    single-device, ma qui non c'e' nessun cancello che lo dica.)

13. **[LETTO] `usato[]` viene azzerato solo in rami irraggiungibili.** Le uniche
    scritture a 0 sono `:823` (ricarica calda), `:2016` (ramo cura), `:2049`
    (orologio), `:2311`/`:2320` (`cache_promuovi`), `:2730`/`:2820` (`kern_prenota`):
    **nessuna e' raggiungibile** con `LRU=1, W=0, CURA=0, DMA=0`. Vedi il punto 3.

14. **[DEDOTTO] La spiegazione "l'attesa scala con la capienza" e' probabilmente
    una confusione fra capienza e margine di VRAM** — vedi §1.5 e §6.4. Se e' cosi',
    tutti i verdetti presi variando gli slot hanno **due variabili** e non una.

---

# RIASSUNTO (20 righe) — priorita' a 1, 2, 6

1. **[D1]** `cache_vittima` (`:1879`) prova quattro rami con `return`: **massa
   (`:1890`) → lru (`:1931`) → cura|scudo|dma (`:1981`) → orologio (`:2044`)**.
2. **[D1]** Con `LRU=1, SFRATTO_PAR=1` **non se ne prende nessuno**: `decidi_fili`
   (`:2901`) lancia `kern_decidi<<<1,256>>>` e a `:2612` si va su **`cache_vittima_par`**.
3. **[D1]** `cache_vittima` sequenziale sopravvive solo in `kern_prenota`, che con
   `W=0` **non e' mai lanciato** ⇒ i quattro cicli sono **codice morto** oggi.
4. **[D1]** Costo del ramo vero: **nessuna uscita anticipata**, `Θ(n_slot)`
   transazioni per sfratto (`chi` + gather casuale su `dove` + `ultimo`),
   `ceil(n_slot/256)` iterazioni per filo, 9 `__syncthreads` di riduzione.
5. **[D1]** Sfratti **==** buchi in questa config: `cache_vittima_par` e' chiamata
   una volta per buco e nessun altro produce sfratti.
6. **[D1]** Il modello **"sfratti"** e' falsificato; **"sfratti x capienza"** riproduce
   l'ordine misurato (45,3 / 44,5 / 36,2 M contro 6,19 / ~6,55 / 5,02 ms) — ma non
   spiega il **livello** (servirebbero 60 µs per sfratto, due ordini di troppo).
7. **[D1]** Ipotesi piu' forte, **non verificata**: l'attesa traccia la **VRAM libera**
   (206 / 228 / 874 MiB), non gli slot. 512 e 448 hanno lo stesso margine e la stessa
   attesa. Si falsifica con `LLAMA_VRAM_ZAVORRA` (`:287`) a capienza ferma.
8. **[D2]** I 32 contatori sono **CUMULATIVI DALL'INIT**: unica `memset` a `:1569`,
   il dump (`:3768`) **legge e basta**. Il battito non azzera niente.
9. **[D2]** Quindi ogni dump e' un totale progressivo: **due corse si confrontano
   solo sull'ultimo dump di entrambe, o per differenza a pari profondita'**.
10. **[D2]** L'unica **istantanea** e' `vive-censurate` (`:3802-3810`, popcount di
    `installato[]` fatto sull'host), e sta **sulla stessa riga** dei cumulativi.
11. **[D2]** Nel log ci sono **due dump** (bersaglio e bozza, due runtime,
    `ggml-cuda.cu:1482`) e delle **13 righe stampate solo 2 sono etichettate**:
    `"…: dump contatori"` (`:3775`) e `acceptmoe[bersaglio|bozza]` (`:3932`).
12. **[D2]** Tutte le altre righe, `domanda/colpi/buchi` inclusa, hanno il prefisso
    `cache-esperti:` **hard-coded**: un grep le mescola. E' la trappola gia' pagata (audit/36).
13. **[D3]** `FORK=2` = fork/join + **sonda** (86 lanci/token in piu'). `FORK_BLOCCHI=8`
    e' la griglia di `kern_fj_copia` (`:3294`): meno SM rubati alla MMVQ, non piu' banda.
14. **[D3]** `FORK_ESATTO` 0/1/2 riguarda **solo i forward a un token**; a batch>=2
    dovrebbe essere bit-uguale — ma `:1612-1638` dice che **non lo e' e non si sa perche'**.
15. **[D4]** `kern_copia` (`:2853`) muove i **tre tensori** (gate/up/down, contigui
    nello slot) con tre cicli grid-stride a `int4`, `<<<4*SM=112, 256>>>` (`:2884`);
    `kern_fj_copia` e' il clone che legge l'**istantanea** della lista, con 8 blocchi.
16. **[D5]** `CURA` confermata irraggiungibile con LRU (`:1318` lo dichiara), ma
    **paga comunque** marcatura e scadenza dei predetti: costo senza beneficio.
17. **[D5]** `SCUDO` e' peggio di "marca e non prenota": con `W=0` **non marca
    neppure**, perche' `kern_prenota` non e' mai lanciato. Stessa sorte per
    `PREFETCH_FILTRO`, `CODA_MAX`, `SPIN`, `PF_TUTTI` — e nessuna di queste ha un avviso.
18. **[D6]** La VRAM della cache e' **una sola `cudaMalloc`**, `n_slot*byte_slot`
    (`:1353-1359`); tutto il resto e' ~140 KiB. **Nessun pool nel file.**
19. **[D6]** Il pool temporaneo sta in `ggml-cuda.cu` ed e' **a massimo storico**:
    VMM `free()` non smappa (`:618-627`), leg tiene 256 buffer per sempre (`:468`).
20. **[D6]** Da qui il paradosso: 512→448 libera 432 MiB di slab e ne rende 22
    (il pool assorbe 410); 448→339 ne libera 736 e ne rende 646 (il pool e' saturo).
    **La sonda per chiuderla esiste gia'**: `LLAMA_KV_RING_VRAM_TRACE` sui punti
    `cuda_vmm_pool_after_cuMemCreate` (`ggml-cuda.cu:537-557`).
