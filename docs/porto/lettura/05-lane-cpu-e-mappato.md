# 05 — La lane CPU e il buffer mappato ibrido

Lettura del codice (nessuna esecuzione). Repo: `D:\llama-overlap`, base upstream `5c3a58686`.
Ogni affermazione porta `file:riga` ed è marcata **LETTO NEL CODICE** oppure **DEDOTTO, non verificato**.

## Dove vive il blocco (localizzazione)

| pezzo | file | righe |
|---|---|---|
| worker CPU, spin, dispatch, join, sonda | `ggml/src/ggml-backend.cpp` | 776–964, 1786–1899, 1901–2298 |
| confine forzato dopo la partizione | `ggml/src/ggml-backend.cpp` | 1529–1562 |
| costruzione dei due rami (`_overlap_cpu` / `_overlap_gpu`) | `src/llama-graph.cpp` | 1782–1960 |
| cancello d'ingresso allo split | `src/llama-graph.cpp` | 2241–2256 |
| pin dei nodi `_overlap_cpu` sulla CPU | `src/llama-context.cpp` | 1621–1664 |
| buffer `CUDA0_Mapped` + `is_host` | `ggml/src/ggml-cuda/ggml-cuda.cu` | 1263–1471 |
| rifiuto `supports_op` (ibrido + SOGLIA) | `ggml/src/ggml-cuda/ggml-cuda.cu` | 5511–5546 |
| kernel di partizione (chi va alla CPU) | `ggml/src/ggml-cuda/cache-esperti.cu` | 3339–3465 |
| `LLAMA_OVERLAP_VERIFICA` | `ggml/src/ggml-cuda/ggml-cuda.cu` | 2610–2690 |
| manifesto delle variabili | `tools/server/server.cpp` | 30–121 |

---

# A. CONTATORI

Tutti i contatori del worker sono **cumulativi dall'avvio del processo e non vengono MAI azzerati**
(`ggml-backend.cpp:850-853`, unici scrittori `:893`, `:912-914` con `fetch_add`; nessun `store(0)` in
tutto il file). La stampa avviene ogni 50 grafi (`:2268`) e **divide sempre per `prof.n_graphs`
cumulativo** (`:2287-2292`). **LETTO NEL CODICE.**

Conseguenza: ogni numero stampato è una **media mobile da inizio processo**, non una misura
dell'ultimo intervallo. Una corsa lunga "annega" un transitorio; due corse identiche di lunghezza
diversa non sono confrontabili riga per riga.

| nome nel log | sorgente | file:riga (scrittura) | unità | natura |
|---|---|---|---|---|
| `worker N lavori/grafo` | `w->n_lavori / prof.n_graphs` | `ggml-backend.cpp:914` | conteggio, intero troncato | cumulativo / cumulativo |
| `attesa-evento X ms` | `w->us_attesa_ev` | `ggml-backend.cpp:912` | µs→ms, per grafo | cumulativo |
| `calcolo X ms` | `w->us_calcolo` | `ggml-backend.cpp:913` | µs→ms, per grafo | cumulativo |
| `attesa-lavoro X ms` | `w->us_attesa_lav` | `ggml-backend.cpp:893` | µs→ms, per grafo | cumulativo |
| `join (sched) X ms` | `prof.us_join` | `ggml-backend.cpp:1983` | µs→ms, per grafo | cumulativo |
| `copie join-async N` | `prof.n_join_async` | `ggml-backend.cpp:2032` | conteggio per grafo | cumulativo |
| `N grafi`, `split/grafo` | `prof.n_graphs`, `prof.n_splits` | `:2268`, `:1958`+`:2145` | conteggi | cumulativo |
| `ingressi / sync / calc CPU / calc altri` | `prof.us_*` | `:2144`, `:1919`, `:2157`, `:2159` | µs→ms, per grafo | cumulativo |

**Punti esatti di misura** (LETTO NEL CODICE, `ggml-backend.cpp:887-925`):

```
ciclo del worker:
  t_attesa0 = now                         :890
  attendi(PRONTO|FERMA)                   :891   <-- spin + condvar
  us_attesa_lav += now - t_attesa0        :893
  t_ev0 = now                             :905
  ggml_backend_event_synchronize(evento)  :906   <-- attesa dei produttori GPU
  t_calc0 = now                           :907
  ggml_backend_graph_compute(cpu, grafo)  :910   <-- il ramo CPU, BLOCCANTE
  us_attesa_ev  += t_calc0 - t_ev0        :912
  us_calcolo    += now - t_calc0          :913
```

**Sono somme su UN SOLO thread**, quello del worker (`ggml-backend.cpp:2236`, un unico
`std::thread` per sched, creato pigro al primo dispatch). Non sono somme su tutti i thread CPU.
**LETTO NEL CODICE.**

Ma `calcolo` misura **tempo di parete di una chiamata che internamente usa tutto il threadpool**:
`ggml_backend_graph_compute` sul backend CPU esegue con `n_threads` impostato da
`llama-context.cpp:2938-2952` (`cparams.n_threads`, cioè `-t 7`). Quindi 15,5 ms di `calcolo` sono
15,5 ms di parete con 7 thread dentro, non 15,5 ms-core. **DEDOTTO** dalla catena
`worker→backend_cpu→threadpool`, non verificato con un profilo.

### Il fatto strutturale più importante di questa sezione

I tre stati del worker sono **esaustivi e mutuamente esclusivi**: il ciclo `:889-924` è
`attendi → sync evento → calcola → attendi …` senza altri rami. Quindi

```
attesa-evento + calcolo + attesa-lavoro  ==  tempo di PARETE totale / n_graphs
```

Coi numeri della sonda: `9,3 + 15,5 + 12,3 = 37,1 ms per grafo`. **DEDOTTO, non verificato**, ma
la struttura del ciclo lo impone.

Ne segue che **`attesa-lavoro` non misura la lane: è il residuo del tempo di parete**. Contiene
(a) le attese fra uno strato e l'altro dentro lo stesso grafo, e (b) **l'intero intervallo fra un
grafo e il successivo** — campionamento, HTTP, e soprattutto i grafi della bozza, durante i quali
questo worker non ha nulla da fare. Perciò la deriva `8,3 → 12,3-13,4 ms` a `calcolo` fermo
significa letteralmente **"tutto il resto del sistema è rallentato di ~4-5 ms per grafo"**, non
"il worker aspetta di più per un problema suo". Con ~3,5 grafi/token quei 4-5 ms fanno 14-17 ms su
un ciclo di 130 ms: **lo stesso ordine di grandezza del 13-15% perso al riavvio del 12/8**.
`attesa-lavoro` è il *termometro della regressione*, non la sua causa. **DEDOTTO.**

---

# B. VARIABILI D'AMBIENTE

Tutte lette **una sola volta** dentro una lambda `static const` → **cambiarle a caldo non ha
effetto**, e il valore vale per l'intero processo (LETTO NEL CODICE, tutte le righe sotto).

| variabile | letta a | difetto nel codice | difetto nel manifesto (`server.cpp`) |
|---|---|---|---|
| `LLAMA_OVERLAP_ASYNC` | `ggml-backend.cpp:1817` | 0 (spento) | `:68` = 0 ✓ |
| `LLAMA_OVERLAP_SPIN` | `ggml-backend.cpp:861` | **2 000 000** | `:73` = 2000000 ✓ |
| `LLAMA_OVERLAP_JOIN_ASYNC` | `ggml-backend.cpp:1827` | 0 | **ASSENTE dal manifesto** |
| `LLAMA_OVERLAP_FINESTRA` | `ggml-backend.cpp:1860` | 0 (spenta) | **ASSENTE dal manifesto** |
| `LLAMA_OVERLAP_K` | `llama-graph.cpp:1825` (`atof`) **e** `llama-context.cpp:1638` (`atof`) | 0.0 | `:71` = 0 ✓ |
| `LLAMA_OVERLAP_BATCH_MAX` | `llama-graph.cpp:1849` | 1 | `:69` = 1 ✓ |
| `LLAMA_OVERLAP_PIN` | `llama-context.cpp:1652` | **1** (acceso; spento solo con il carattere `'0'`) | `:72` = 1 ✓ |
| `LLAMA_OVERLAP_GRIGLIA_VARIABILE` | `cache-esperti.cu:3456` | 0 (griglia FISSA) | `:70` = 0 ✓ |
| `LLAMA_OVERLAP_VERIFICA` | `ggml-cuda.cu:2636` | 0 | `:74` = 0 ✓ |
| `LLAMA_MAPPED_IBRIDO` | `ggml-cuda.cu:1436` **e** `:5530` (due lambda separate) | 0 | `:66` = 0 ✓ |
| `LLAMA_MAPPED_IBRIDO_SOGLIA` | `ggml-cuda.cu:5534` | **2** | `:67` = 2 ✓ |
| `GGML_SCHED_PROFILO` | `ggml-backend.cpp:1806` | 0 | assente (è di diagnostica) |

### Rami raggiungibili con la configurazione indicata

Configurazione: `MAPPED_IBRIDO=1 SOGLIA=2 OVERLAP_ASYNC=1 K=2 BATCH_MAX=2 PIN=1
GRIGLIA_VARIABILE=0 JOIN_ASYNC=0 SLOT=512 FORK=2 LRU=1`.

| ramo | raggiungibile? | perché |
|---|---|---|
| `build_moe_ffn_overlap` costruisce i due rami | **SÌ** | `K=2>0` (`llama-graph.cpp:1828-1832`), `n_tokens ≤ BATCH_MAX=2` (`:1853`), arch DEEPSEEK4 (`:2246`) |
| pin dei nodi `_overlap_cpu` sulla CPU | **SÌ** | `overlap_k>0 && overlap_pin && backend_cpu` (`llama-context.cpp:1655`) |
| confine forzato dopo `PARTIZIONA` | **SÌ** | `ASYNC=1` (`ggml-backend.cpp:1540`) |
| dispatch al worker | **SÌ, ma condizionato al profilo 1a/1b/CPU** (`ggml-backend.cpp:2210-2231`) |
| join con finestra larga | **NO** | `FINESTRA=0` → ramo `split_id > split_spedito \|\| e_cpu` (`:1976`): **finestra larga UNO split** |
| `join_async` (copia di ritorno accodata) | **NO** | `JOIN_ASYNC=0` (`:1929`) → `copia_join_async` sempre falso (`:2014`), `copie join-async` stampa 0 |
| `supports_op` rifiuta la MMID mappata | **NO** | `SLOT=512 > 0` ⇒ `percorso_gpu_richiesto()` vero (`cache-esperti.cu:329-332`) ⇒ `cache_ammessa` vero ⇒ **il rifiuto è sospeso** (`ggml-cuda.cu:5541-5544`) |
| `is_host` del buffer mappato | **VERO** | `ggml-cuda.cu:1439`: `ibrido && g_cuda_mapped_uva`. **Non guarda la cache**: resta vero anche quando `supports_op` accetta |
| fallback "un esperto per volta" **sui pesi MAPPATI** | **NO, secondo il codice** | serve `!buffer_supported(peso, backend_dello_split)` (`:1597`) perché il peso diventi un `split->inputs[]`, ma il mappato è supportato **sia** da CUDA (`ggml-cuda.cu:5984-5987`) **sia** dalla CPU quando `is_host` (`ggml-cpu.cpp:488-490`). **Contraddice i 277 misurati: vedi «cose che non tornano» n. 6** |
| fallback "un esperto per volta" **su pesi in buffer `CPU` puro** | **SÌ in linea di principio, NO con questi numeri** | `is_host` sempre vero e CUDA non lo supporta; ma per finire su uno split CUDA serve `offload_op` = `ne[2] ≥ 32` (`ggml-cuda.cu:6008`, `:6217`) e la bozza gira a ubatch 16 |
| fusione mmvq sulla MMID mappata | **NO** (disattivata apposta) | `ggml-cuda.cu:2053-2057` |
| `LLAMA_OVERLAP_VERIFICA` a regime | **NO** anche se acceso | salta in cattura, e sotto CUDA graph il codice host gira **solo alla cattura** (`ggml-cuda.cu:2626-2651`) |
| `GRIGLIA_VARIABILE` | ramo vecchio **NON** preso; griglia fissa `TOK_MAX` (`cache-esperti.cu:3459`) |

---

# C. COMPLESSITÀ (per grafo / per strato)

**Per strato** (LETTO NEL CODICE):

- `kern_partiziona`: 1 blocco, `TOK_MAX` thread fissi (`cache-esperti.cu:3461`). Per token:
  `ne0 ≤ 16` (DSV4: 6) letture di `dove[]`+`chi[]`, poi 3 passate di ordinamento per chiave su
  `ne0` elementi (`:3406-3412`) e 2 scritture da `ne0` (`:3415-3420`). **O(ne0)** per token con
  costanti minuscole: il costo è il lancio, non il lavoro.
- Con `ASYNC=1` ogni strato paga **un lancio di grafo in più** per il confine forzato
  (`ggml-backend.cpp:1529-1543`); il commento stima `~5-10 µs × 43 = 0,3-0,4 ms/token`.
- Ramo CPU per strato: `k_cpu` esperti × 3 `MUL_MAT_ID` (up/gate/down) + swiglu (+2 clamp se
  `swiglu_clamp_exp[il] > 1e-6`), `llama-graph.cpp:1905-1921`.
- Ramo GPU per strato: `k_gpu = n_expert_used − k_cpu` esperti, stessa forma (`:1886-1899`).
- Coda comune per strato: 1 `concat` + 1 `get_rows` (riordino) + 1 `mul` (`:1939-1946`).

**Per grafo** (LETTO NEL CODICE + aritmetica):

- Il dispatch è **al più uno in volo alla volta** (`split_spedito < 0` in `:2210`), e al più
  `GGML_SCHED_OVERLAP_MAX_EVENTI = 64` dispatch per grafo (`:816`, `:2212`).
- La sonda dice `10 lavori/grafo`: con 43 strati, **solo ~10 strati su 43 riescono a spedire**.
  Le cause possibili di scarto sono tutte nel cancello `:2210-2231`: `split_spedito` ancora
  occupato, `split_id+2 ≥ n_splits`, `splits[split_id+1].backend_id != split_backend_id`,
  destinazione non-CPU, o un ingresso che non viene da quel backend. **DEDOTTO, non verificato:**
  il codice non conta i rifiuti, quindi *quale* dei cinque motivi domini non è misurabile oggi.
- `ggml_sched_split_dipende_dal_worker` è **O(n_inputs × n_nodes_worker)** con confronto di
  puntatori (`:1883-1899`), ma gira **solo se `FINESTRA>0`**: a difetto è codice morto.
- Il fallback per-esperto (`:2090-2126`) fa un `cudaMemcpyAsync` **per corsa contigua di id usati**,
  non per esperto: con 6 esperti sparsi su 256 le corse sono ~6, moltiplicate per 3 tensori
  (up/gate/down) e per gli strati che ci cadono. `6 × 3 × ~15 strati ≈ 270` è l'ordine dei 277
  osservati — **ma la catena che ci porta NON si chiude leggendo il codice: vedi «cose che non
  tornano» n. 12.**
- Il gather degli id (`:2070-2087`) fa un `get_async` + `sync` **per ogni ids_tensor nuovo**, con
  memoizzazione su `prev_ids_tensor`: un `ggml_backend_synchronize` per strato, non per esperto.

---

# D. HOST vs DEVICE, e i confini

**Il buffer `CUDA0_Mapped`** (`ggml-cuda.cu:1263-1471`, LETTO NEL CODICE):

- allocato con `cudaHostAlloc(cudaHostAllocMapped | cudaHostAllocPortable)` (`:1363`), poi
  `cudaHostGetDevicePointer` (`:1373`);
- `get_base` restituisce **il puntatore DEVICE** (`:1312`): i tensori portano indirizzi device;
- `set_tensor`/`get_tensor` traducono per differenza `host + (t->data − dev)` (`:1317-1321`) e
  fanno una `memcpy` **host**, non una `cudaMemcpy` (`:1325`, `:1330`);
- `g_cuda_mapped_uva` è vero se `host == dev` (`:1397`), condizione necessaria perché la CPU possa
  leggere quegli indirizzi;
- il tipo condivide **il puntatore a funzione** `get_name` con il tipo CUDA normale (`:1456`), così
  `ggml_backend_buft_is_cuda` lo riconosce come CUDA: **il buffer è CUDA per il backend CUDA e,
  se `is_host`, anche host per il backend CPU. Accettato da entrambi.**

**I confini nel decode con la lane accesa** (LETTO NEL CODICE, `ggml-backend.cpp:2196-2249`):

```
split 1a  (CUDA)  … attenzione + kern_partiziona          -> overlap_produttori = true
   |  D2H async degli ingressi del ramo CPU        :2230   (HOST->DEVICE boundary #1)
   |  cudaEventRecord lato host                    :2242   (confine #2, fuori cattura)
   |  spedisci al worker                           :2243
split 1b  (CUDA)  … ramo GPU, gira MENTRE il worker calcola
split 1c  (CPU)   … il ramo CPU, in mano al worker
   |  join: il thread sched si blocca              :1981   (confine #3)
   |  copie di ritorno CPU->CUDA                   :1998-2141 (confine #4)
```

Il punto **3** è quello che la sonda chiama `join (sched)`. Il punto **2** è l'unica cosa che rende
legale il disegno: l'evento è registrato **lato host fra due lanci**, fuori da ogni cattura CUDA
graph (commento `:2204-2205`).

**La regola del proprietario unico**: `ggml_graph_compute` usa il thread chiamante come worker-0 del
pool e il pool ha **un solo slot cgraph/cplan** (commento `:803-808`). Da lì il termine `e_cpu` in
`:1968-1976`: **qualunque split CPU forza il join**, sempre, anche con `FINESTRA` alta. Non è
cautela, è un vincolo di correttezza.

**Il rifiuto CPU delle op di cache** (`ggml-cpu.cpp:427-436`, LETTO NEL CODICE): `PARTIZIONA`,
`KV_RING`, `KV_RING_STORE`, `ACCEPTMOE_IDS`, `ACCEPTMOE_PESI` **non possono mai** cadere sulla CPU —
leggono tabelle di residenza che vivono sul device.

---

# DOMANDE SPECIFICHE

## 1. Il worker CPU: thread, scelta degli esperti, sincronizzazione, misure

**Quanti thread.** **UNO**, e uno solo per sched (`ggml-backend.cpp:1029` un puntatore singolo;
`:2234-2237` creazione pigra al primo dispatch; `:2380-2383` distruzione). Non c'è un pool di
worker. **LETTO NEL CODICE.**
Ma quel thread chiama `ggml_backend_graph_compute` sul backend CPU (`:910`), che internamente apre
il threadpool a `n_threads = cparams.n_threads` (impostato in `llama-context.cpp:2938-2952`). Con
`-t 7` il ramo CPU gira quindi su 7 thread, guidati dal worker come thread chiamante.
**DEDOTTO** dalla catena di chiamate.

**Come vengono scelti gli esperti.** Non li sceglie il worker: li sceglie **`kern_partiziona` sulla
GPU** (`cache-esperti.cu:3349-3421`, LETTO NEL CODICE). Politica, camminando gli slot in ordine, in
tre fasi per **chiave di residenza**:

- `chiave = 0` → **non residente** in cache (o `dove[]` stantio, o slot **in transito**);
- `chiave = 1` → residente ma `usato == 0`, cioè prossimo allo sfratto;
- `chiave = 2` → residente e fresco.

Dentro ogni fase l'ordine di slot originale; niente argsort, determinismo per costruzione
(`:3341-3348`). L'uscita è `[id in ordine di partizione | permutazione inversa]` (`:3414-3420`).
**Il taglio non lo fa il kernel**: `k_cpu` non entra nemmeno nel kernel — sono le **viste** nel grafo
a tagliare (`llama-graph.cpp:1868-1873`, e commento `:1864`: «k sta nei parametri dell'op ma NON nel
kernel: cambiare K non ricattura i graph»).

Quindi **alla CPU vanno i primi `k_cpu` in ordine di partizione, cioè i NON RESIDENTI** — esattamente
gli esperti che la GPU dovrebbe altrimenti tirare dal PCIe. È la scelta giusta di disegno, ed è anche
il motivo per cui la lane è strutturalmente accoppiata ai *miss* della cache: **più la cache è
buona, meno lavoro utile ha la lane**.

**Come si sincronizza con la GPU.**
- *Ingresso*: `ggml_backend_event_synchronize(w->evento)` (`ggml-backend.cpp:906`). L'evento è
  registrato lato host subito dopo aver accodato le copie D2H degli ingressi del ramo CPU
  (`:2230` poi `:2242`), quindi significa **"attenzione + partizione + ingressi pronti"** e nulla di
  più: il ramo GPU (split 1b) non è ancora stato lanciato e può quindi essere scavalcato.
- *Uscita*: `ggml_sched_worker_unisci` (`:940-951`), chiamato dal thread dello sched al primo split
  successivo (`:1977-1992`), più i tre punti difensivi (`:1939-1947` percorso d'errore,
  `:2420` reset, `:2510` synchronize) e la chiusura di fine grafo (`:2261-2266`).
- *Sicurezza dal deadlock*: `abortito` letto prima e dopo l'attesa (`:900`, `:908`), e un evento mai
  registrato è già "completo" (commento `:810-815`).

**Dove sono misurate le tre voci, e su chi sommano.** Vedi sezione A: `attesa-evento` è il solo
`event_synchronize` (`:906`), `calcolo` è il solo `graph_compute` (`:910`), `attesa-lavoro` è la
`attendi()` (`:891`). **Sono somme su UN thread** (il worker), **cumulative dall'avvio**, divise per
`prof.n_graphs` cumulativo. E, punto chiave: **le tre voci partizionano l'intero tempo di parete**,
quindi `attesa-lavoro` include tutti gli intervalli in cui il worker non ha lavoro — compresi i grafi
della bozza.

**I 15,5 ms di `calcolo`.** Sono il costo di parete di ~10 chiamate `graph_compute` CPU per grafo,
cioè **~1,55 ms per lavoro** con 7 thread dentro. Il fronte aperto è tutto qui: durante quei 15,5 ms
la GPU ha da correre solo lo split 1b, che vale ~0,25 ms per split (commento `:1843`). **Il rapporto
è ~6:1 contro la copertura**, e la finestra larga uno split non può cambiarlo.

## 2. `LLAMA_OVERLAP_K=2`: che cosa è il 2, e cosa cambia a 3 o 4

**Il 2 è il numero MEDIO di esperti (su `n_expert_used`, che in DSV4 è 6) affidati al ramo CPU per
strato.** LETTO NEL CODICE, `llama-graph.cpp:1824-1832`:

```c
static const double k_medio = getenv("LLAMA_OVERLAP_K") -> atof, difetto 0.0
const int k_cpu = (k_medio <= 0.0) ? 0
                : (int)(k_medio*(il+1)) - (int)(k_medio*il);     // Bresenham su il
if (k_cpu <= 0 || k_cpu >= n_expert_used) return nullptr;        // fuori -> percorso classico
```

Tre cose non ovvie:

1. **È frazionario e varia per strato.** La distribuzione è Bresenham su `il`: media esatta `x`,
   valori solo `floor(x)` e `ceil(x)` alternati (`:1819-1821`). `K=2,33` dà la sequenza `2,2,3`.
   A valore intero è identico al comportamento precedente **bit per bit** (`:1822-1823`).
2. **Il taglio è nelle viste, non nel kernel** (`:1868-1873`): cambiare K **non ricattura i CUDA
   graph** — le forme restano statiche perché ogni strato costruisce le sue viste alla costruzione
   del grafo (`:1814-1817`).
3. `k_cpu >= n_expert_used` **spegne lo split** e ricade sul percorso classico: quindi `K=6` non
   significa "tutto alla CPU", significa **lane spenta**.

**Perché alzare K sposta lavoro sulla CPU.** Meccanicamente: `k_gpu = n_expert_used − k_cpu`
(`:1860`), e le due viste `ids_cpu`/`ids_gpu` tagliano la stessa riga di `part` in `k_cpu` e `k_gpu`
elementi (`:1868-1871`). Ogni esperto in più al ramo CPU è una riga in più nelle tre `MUL_MAT_ID`
CPU e una in meno in quelle GPU. Ma la ragione *strutturale* è più forte: la partizione mette in
testa i **non residenti** (Q1), quindi i primi `k_cpu` sono i miss. Alzare K non ridistribuisce
lavoro simmetrico: **toglie alla cache le domande che avrebbe servito** e le dà alla CPU seriale.

Il commento del codice fornisce l'aritmetica (`:1801-1812`, costi misurati 0,242 ms/esperto CPU,
0,060 GPU residente, 0,271 copia se assente, colpi 40%):

| K | ramo CPU | ramo GPU | collo |
|---|---|---|---|
| 2 | 0,484 | 0,674 | **GPU** |
| 3 | 0,726 | 0,343 | **CPU** |
| 2,33 | 0,564 | 0,564 | pareggio |

Cioè **fra K=2 e K=3 i due rami si scambiano il ruolo di collo**, e la macchina ha misurato il
pianoro (`9,98` contro `10,02`, indistinguibili). **K=4 è oltre il pareggio: la CPU diventa il collo
con largo margine** — il ramo GPU scende a ~0,2 ms mentre la CPU sale a ~0,97, e lo strato costa
`max()`. Questo spiega la nota di memoria «`K=4` alza i colpi spostando lavoro sulla CPU seriale».
**LETTO NEL CODICE** (l'aritmetica è nel commento; i costi unitari sono dichiarati misurati altrove,
non li ho verificati).

## 3. `LLAMA_OVERLAP_SPIN`: dove, che tipo, quanta CPU, e se i due milioni sono giustificati

**Dove.** Un solo sito: `ggml_sched_worker_attendi` (`ggml-backend.cpp:859-885`), chiamata da
`ggml_sched_worker_ciclo:891` (attesa di lavoro) e da `ggml_sched_worker_unisci:947` (attesa del
FATTO, cioè **il join lato sched spinna anche lui**). **LETTO NEL CODICE.**

**Che tipo di attesa** (`:870-885`):

```c
for (int giri = 0; giri < spin && s != a && s != b; giri++)
    s = w->stato.load(std::memory_order_acquire);     // niente pause, niente yield
if (s != a && s != b) { condvar.wait(...); }          // poi si parcheggia
```

Attesa attiva **pura**: nessuna `_mm_pause`, nessuna `std::this_thread::yield`, nessun backoff. È un
carico-e-confronta su una linea di cache condivisa. **LETTO NEL CODICE.**

**Quanta CPU brucia.** Il ciclo è ~1-2 ns per giro su x86 (carico L1 + branch), quindi
**2 000 000 giri ≈ 2-4 ms di core al 100%** prima di parcheggiarsi. **DEDOTTO, non verificato**
(nessun micro-benchmark nel repo).

Confronto coi numeri della sonda: `attesa-lavoro 12,3 ms/grafo` su `10 lavori/grafo` fa **~1,2 ms di
attesa media per lavoro**, sotto il budget di spin. Quindi **il worker spinna praticamente sempre e
non si parcheggia quasi mai** dentro il grafo: quei ~12 ms/grafo sono ~12 ms di core bruciati a
vuoto. Con `-t 7` su 8 core il worker è un ottavo thread che gira: **~14% della CPU della macchina,
e per giunta in contesa col threadpool a 7 thread che deve calcolare il ramo CPU**. **DEDOTTO.**

**Il difetto da due milioni è giustificato o è un residuo?** Il commento lo giustifica
esplicitamente (`:856-858`: «il difetto copre ~1-2 ms, l'attesa fra due strati») e il commento in
testa al file lo argomenta con un numero (`:796-801`: un risveglio a condvar costa ~79 µs misurati,
a 43 strati sarebbero 3,4 ms/token; e «il core che lo spin occupa è quello che `-t 7` lascia libero
apposta»). **Quindi NON è un residuo: è calibrato.** Il confronto coi 256 di
`LLAMA_CACHE_ESPERTI_SPIN` **non è pertinente**: quello è un contatore di **letture di un flag dentro
un kernel CUDA** (`cache-esperti.cu:2571`, `cuh:114` «letture massime del flag con cura=2»), cioè
giri di un thread GPU, non di un thread CPU. **Due grandezze diverse su due processori diversi: i
quattro ordini di grandezza non hanno mai avuto bisogno di essere giustificati l'uno rispetto
all'altro.** **LETTO NEL CODICE.**

Resta però un problema reale che il commento **non** copre: la premessa «il core che lo spin occupa è
quello che -t 7 lascia libero» vale per l'attesa *fra strati*, ma `attendi()` è usata anche
**dopo l'ultimo lavoro del grafo**, quando il ramo CPU non ha più nulla da fare e il thread continua
a bruciare 2-4 ms mentre la GPU e i 7 thread stanno lavorando al grafo della bozza. In quella
finestra il core non è "libero apposta": è conteso. **DEDOTTO, non verificato.**

## 4. `LLAMA_MAPPED_IBRIDO` e `SOGLIA=2`: si può avere il mappato SENZA `is_host`?

### Che cosa decidono

`LLAMA_MAPPED_IBRIDO` è letto in **due posti indipendenti** con due lambda distinte (LETTO NEL
CODICE):

**(a) `ggml_backend_cuda_mapped_buffer_type_is_host`** — `ggml-cuda.cu:1411-1440`:
```c
return ibrido && g_cuda_mapped_uva;
```
Nient'altro. **Non guarda la cache, non guarda la soglia, non guarda il batch.**

**(b) `ggml_backend_cuda_device_supports_op`** — `ggml-cuda.cu:5528-5546`:
```c
if (g_cuda_mapped_uva && op->op == GGML_OP_MUL_MAT_ID) {
    if (ibrido && src[0] è nel buffer mappato) {
        const bool cache_ammessa = ggml_cuda_cache_esperti_percorso_gpu_richiesto();
        if (get_op_batch_size(op) < soglia && !cache_ammessa) return false;   // rifiuta
    }
}
```
`get_op_batch_size(MUL_MAT_ID) = op->ne[2]` = **numero di token** (`:5996-5999`). Quindi
**`SOGLIA=2` significa: rifiuta la MMID sui pesi mappati quando i token sono meno di 2, cioè a
batch 1** → decode alla CPU, prefill alla GPU. **LETTO NEL CODICE.**

`percorso_gpu_richiesto()` = `slot_richiesti(target) > 0 || slot_richiesti(bozza) > 0`
(`cache-esperti.cu:329-332`). **Con `SLOT=512` è sempre vero**, quindi **il rifiuto è sospeso** e la
MMID resta sulla GPU.

### La risposta: SÌ, e la leva è una sola

**`is_host` è vero se e solo se `LLAMA_MAPPED_IBRIDO != 0` e `g_cuda_mapped_uva`** (`:1439`). Il
buffer mappato **esiste indipendentemente**: lo si sceglie da riga di comando con
`-ot "<pattern>=CUDA0_Mapped"` (`ggml/include/ggml-cuda.h:37-41`, `common/arg.cpp:269-283`), e la sua
allocazione (`:1357-1404`) non consulta mai la variabile. **Quindi:**

> **`LLAMA_MAPPED_IBRIDO=0` dà il buffer mappato con `is_host` FALSO.**
> I kernel continuano a leggere la RAM host via PCIe (`get_base` restituisce comunque il puntatore
> device, `:1312`), lo scheduler assegna tutto a CUDA, e **la condizione del fallback per-esperto
> `ggml_backend_buffer_is_host(input->buffer)` (`ggml-backend.cpp:2046`) diventa falsa**: quel ramo
> non è più raggiungibile **da questo buffer**. **LETTO NEL CODICE.**

**AVVERTENZA, e va letta prima di comprare l'aspettativa**: dalla lettura risulta che quel ramo
**non era raggiungibile dal buffer mappato nemmeno con `IBRIDO=1`** — vedi «cose che non tornano»
n. 6. `is_host` è solo *una* delle due condizioni; l'altra (`!buffer_supported`) il mappato non la
soddisfa mai, perché condivide `get_name` col tipo CUDA. **Quindi spegnere `IBRIDO` cambia con
certezza chi calcola le MMID, ma NON è dimostrato che tolga i 277 `cudaMemcpyAsync`** — la loro
origine va prima identificata con `GGML_SCHED_DEBUG=2`.

### Il prezzo, e perché è esattamente la casella che vi serve

Con `IBRIDO=0`, `ggml_backend_cpu_device_supports_buft` **rifiuta il buffer mappato** — è
letteralmente `return ggml_backend_buft_is_host(buft) || is_extra_buffer_type(buft)`
(`ggml/src/ggml-cpu/ggml-cpu.cpp:488-490`, LETTO NEL CODICE), e il mappato non è un extra buffer
type. Conseguenza in `ggml_backend_sched_split_graph:1597`:

```c
if (src_backend_id != cur_backend_id && !ggml_backend_sched_buffer_supported(sched, src, cur_backend_id))
    -> il peso diventa split->inputs[] e va COPIATO
```

Quindi **qualunque nodo forzato sulla CPU dal pin `_overlap_cpu` chiederebbe una copia dei pesi
esperti**, e — non essendo più `is_host` — **non prenderebbe nemmeno il percorso per-esperto**, ma il
ramo generico `:2127-2138` che copia il **tensore intero** (tutti i 256 esperti dello strato).
**DEDOTTO, non verificato**, ma segue direttamente dalle due condizioni.

Cioè: **la lane CPU e `is_host` sono accoppiate per costruzione. Non si può tenere la lane e togliere
`is_host`.** E per la casella che vi interessa — **bozza accesa + lane CPU SPENTA + fork + 512
slot** — l'accoppiamento non morde:

```
LLAMA_MAPPED_IBRIDO=0        -> is_host falso; il backend CPU non accetta piu' il mappato, quindi
                                TUTTE le MMID esperti restano su CUDA per collocazione
LLAMA_OVERLAP_K=0            -> build_moe_ffn_overlap ritorna nullptr (llama-graph.cpp:1830)
                                nessun nodo _overlap_cpu, il pin non trova niente (llama-context.cpp:1655)
LLAMA_OVERLAP_ASYNC=0        -> niente confine forzato, niente worker (ggml-backend.cpp:1540, 2210)
LLAMA_CACHE_ESPERTI_SLOT=512 -> percorso_gpu_richiesto vero (irrilevante: il rifiuto è già spento
                                perché `ibrido` è falso)
```

Tutte e quattro le condizioni sono coerenti e nessuna si contraddice. **La casella è raggiungibile
oggi, senza toccare una riga.**

**Due avvertenze prima di provarla** (entrambe LETTE NEL CODICE):

1. Il cammino `IBRIDO=0` è stato reso raggiungibile **solo l'11/8**: il commento a
   `ggml-cuda.cu:3047-3063` racconta che con l'ibrido spento gli esperti mappati passavano per
   `set_tensor_async`/`get_tensor_async` e l'assert falliva sul confronto per puntatore del buffer
   type; la cura è `cuda_buffer_ammesso` (`:3064-3067`). Testuale: *«fino a oggi il cammino "tutti
   gli esperti sulla GPU" non era lento — era IRRAGGIUNGIBILE»*.
2. **La cura non è completa.** Tre delle quattro funzioni usano `cuda_buffer_ammesso`
   (`:3073`, `:3082`, `:3092`), ma **`ggml_backend_cuda_get_tensor_2d_async` a `:3103` ha ancora il
   confronto stretto** `buf->buft == ggml_backend_cuda_buffer_type(cuda_ctx->device)`. Se quel
   percorso viene toccato con un tensore mappato e `IBRIDO=0`, l'assert scatta. Vedi «cose che non
   tornano».

## 5. `LLAMA_OVERLAP_PIN=1` e `GRIGLIA_VARIABILE=0`

**`LLAMA_OVERLAP_PIN`** (`llama-context.cpp:1641-1663`, LETTO NEL CODICE). Dopo `build_graph`,
scorre tutti i nodi e per ognuno il cui **nome contiene `_overlap_cpu`** chiama
`ggml_backend_sched_set_tensor_backend(sched, nodo, backend_cpu)`:

```c
static const bool overlap_pin = [] { const char * v = getenv("LLAMA_OVERLAP_PIN");
                                     return !(v && *v && *v == '0'); }();   // :1651-1654
if (overlap_k > 0.0 && overlap_pin && backend_cpu != nullptr) { ... strstr(name,"_overlap_cpu") ... }
```

- **Difetto = acceso**, e si spegne **solo** con il primo carattere `'0'` (`*v == '0'`): `PIN=false`,
  `PIN=no`, `PIN=off` lo lasciano **acceso**. Asimmetria rispetto a tutte le altre variabili del
  blocco, che usano `*v != '0'`.
- **Ramo raggiungibile**: sì con `K=2`. Il pin è il motivo per cui i nodi `_overlap_cpu` finiscono
  sulla CPU: senza, lo scheduler li assegnerebbe a CUDA **per collocazione dei pesi**
  (commento `:1621-1624`).
- Il pin **si perde a ogni riuso del grafo** e va rifatto a ogni rebuild (commento `:1625-1626`):
  è dentro il ramo `else` del riuso (`:1601`), quindi con `n_reused` alto viene eseguito raramente —
  ma le assegnazioni precedenti sopravvivono perché `sched_reset` non è stato chiamato.
- `PIN=0` è il **braccio di controllo** «3a puro»: entrambi i rami su CUDA, SHA identico a `K=0`
  (commento `:1641-1650`). Col pin acceso lo SHA **diverge legittimamente** (kernel CPU vs GPU).
- **La lettura è `atof`** (`:1639`), allineata al costruttore (`llama-graph.cpp:1825`). Il commento
  `:1629-1636` documenta che prima era `atoi`, e che con `0<K<1` il pin **non vedeva** il ramo CPU:
  split GPU/GPU e ASYNC mai ingaggiato.

**`LLAMA_OVERLAP_GRIGLIA_VARIABILE`** (`cache-esperti.cu:3450-3459`, LETTO NEL CODICE):

```c
const int n_thread = griglia_variabile ? n_tok : GGML_CACHE_ESPERTI_TOK_MAX;
kern_partiziona<<<1, n_thread, 0, stream>>>(...);          // :3461
```

A `0` (difetto) la griglia è **fissa** a `TOK_MAX` thread: il numero di thread non dipende dalla
taglia del batch, quindi **il replay di un CUDA graph catturato con un'altra taglia resta corretto**.
A `1` si torna al vecchio `<<<1, n_tok>>>` — esiste solo come braccio diagnostico per stabilire se
era quella la causa della degenerazione a batch 2. **Ramo NON raggiungibile** nella configurazione
data. Il kernel ha anche un testimone dedicato: `if ((int)blockDim.x < vero) atomicAdd(&div[4],1)`
(`:3384`), cioè **conta i replay in cui la griglia catturata è più piccola del batch vero** — l'unico
punto in cui il rilevatore precedente era cieco (`:3377-3383`).

## 6. La finestra di sovrapposizione: dove si apre, dove si chiude, perché è larga uno split

**Si apre** a `ggml-backend.cpp:2210-2249`, **dopo** il lancio async dello split produttore
(`:2150`) e **prima** dello split successivo. Condizioni (tutte necessarie, `:2210-2217`):

```c
overlap && split->overlap_produttori && split_spedito < 0 && !callback_eval
  && split_id + 2 < n_splits && n_spediti < 64
  && splits[split_id+1].backend_id == split_backend_id      // il "1b" è sullo stesso backend
  && dev_type(splits[split_id+2]) == CPU                    // il "1c" è CPU
  && ogni ingresso di 1c viene da questo backend e non è un INPUT utente
```

`overlap_produttori` è messo a vero **solo** sullo split che finisce sul nodo immediatamente
successivo a un `GGML_OP_CACHE_ESPERTI_PARTIZIONA` (`:1540-1548`, con `dopo_partizione` impostato a
`:1544`). Il confine è **forzato** da `ASYNC=1`: senza, partizione e ramo GPU starebbero nello stesso
split e l'evento non distinguerebbe ciò che il ramo CPU deve **aspettare** da ciò che deve
**scavalcare** (`:1529-1539`).

**Si chiude** a `:1967-1992`. Con `FINESTRA=0` (il difetto) la condizione è:

```c
const bool deve_unire = (split_id > split_spedito || e_cpu);        // :1976
```

Gli split si scorrono in ordine crescente (`:1949`) e lo split spedito è `split_id+2`; il giro
successivo ha `split_id+1`, che **non** è `> split_spedito`… ma il giro dopo ancora sì. In pratica:
si esegue lo split `+1` (il ramo GPU), poi al giro `+2` si incontra lo split spedito e si salta
(`:1956-1961`), e **al primo split dopo di quello si unisce**. La finestra utile è quindi il **solo
split 1b**.

**Perché è larga uno split.** Il commento `:1840-1845` lo dice ed è l'affermazione centrale del
blocco: la condizione originale univa al primo split successivo perché «qualunque split che viene
DOPO PUÒ dipenderne» — una **maggiorazione conservativa** trasformata in politica. Con i numeri
misurati:

```
lavoro GPU per split   33 ms / 130,7 = 0,25 ms
lavoro CPU per lavoro  29,5 ms / 42  = 0,70 ms       -> tre volte più stretta
```

**La cura esiste ma è spenta**: `LLAMA_OVERLAP_FINESTRA` (`:1858-1865`) sostituisce «viene dopo,
quindi PUÒ dipenderne» con «**dipende davvero**», via `ggml_sched_split_dipende_dal_worker`
(`:1883-1899`, confronta `split->inputs[]` con i nodi del grafo del worker, viste risolte da entrambi
i lati). Il termine `e_cpu` resta in **entrambi** i rami perché è un vincolo di correttezza, non
cautela (`:1969-1971`).

**Il rischio dichiarato** (`:1850-1857`): l'allocatore del grafo calcola la vita dei tensori
assumendo **esecuzione sequenziale**, quindi uno split che corre troppo avanti può riusare memoria
che il worker sta ancora leggendo. Il tetto numerico serve a rendere l'esposizione **misurabile**
invece che aperta. Nota onesta del commento: **il rischio esiste già oggi per uno split**.

---

# COSE CHE NON TORNANO

**1. I contatori del worker sono divisi per un `n_graphs` che NON è il loro.**
`static ggml_sched_profilo_acc prof;` (`ggml-backend.cpp:1905`) è una **static di funzione**, quindi
**condivisa da tutti gli sched del processo**. Ma `sched->worker` è **per-sched** (`:1029`). Con
decodifica speculativa ci sono **due `llama_context` distinti e quindi due sched**: `ctx_tgt` e
`ctx_dft` (`tools/server/server-context.cpp:1019-1020`, LETTO NEL CODICE; la bozza è quella con
`cparams.ctx_other != nullptr`, cfr. `llama-context.cpp:2183`). E `build_moe_ffn_overlap` è
ingaggiato **solo per DEEPSEEK4** (`llama-graph.cpp:2246`): **il worker esiste solo nello sched
target**, mentre `prof.n_graphs` conta target **+** bozza. Tutte e quattro le voci del worker sono quindi **diluite
dal numero di grafi della bozza**, di un fattore pari a `(grafi_target+grafi_bozza)/grafi_target`.
`10 lavori/grafo` potrebbe essere `~35 lavori per grafo target` diviso 3,5. **DEDOTTO, non
verificato** — ma è testabile subito: basta confrontare `n_lavori/n_graphs` con il numero di strati
DSV4 che costruiscono lo split.
*Corollario sgradevole*: anche `split/grafo`, `ingressi`, `sync`, `calc CPU/altri` mescolano i due
contesti, e la riga del worker **non viene stampata affatto** quando il 50° grafo capita di essere
uno della bozza (`:2281` `sched->worker != NULL`).

**2. Nessun contatore azzerabile, e il denominatore parte prima del numeratore.**
Non esiste una via per resettare né `prof` né i contatori del worker (nessuno `store(0)` in
`ggml-backend.cpp`). Ogni numero è una media da inizio processo: **una sonda progettata per
confrontare regimi non può distinguere due regimi dentro la stessa corsa.** Peggio: il worker nasce
**pigro, al primo dispatch** (`:2234-2237`), mentre `prof.n_graphs` conta **da subito**, prefill
compreso — e in prefill lo split non si costruisce nemmeno (`n_tokens > BATCH_MAX`,
`llama-graph.cpp:1853`), quindi quei grafi entrano nel denominatore a numeratore zero.
Questo, più il punto 1, spiega perché il confronto `8,3 → 12,3` fra due corse "identiche" possa
essere in parte un artefatto di **durata e composizione diverse** delle due corse, oltre che una
regressione vera. **Il modo pulito di usare questa sonda è leggere la DIFFERENZA fra due stampe
consecutive**, ricostruendo i totali come `valore × n_graphs`; il log li dà entrambi.

**3. `attesa-lavoro` è etichettata come voce del worker ma misura il resto del mondo.**
Il commento la descrive come «quanto sta fermo fra un lavoro e l'altro (spin+parcheggio)»
(`:846`), il che suggerisce una proprietà della lane. In realtà, essendo le tre voci una partizione
del tempo di parete, è **il complemento a uno di tutto il resto**. Un rallentamento del prefill,
della bozza o del campionamento la fa salire senza che nulla nella lane sia cambiato.

**4. `LLAMA_OVERLAP_JOIN_ASYNC` e `LLAMA_OVERLAP_FINESTRA` non sono nel manifesto.**
Il manifesto (`server.cpp:37-121`) elenca 7 variabili `LLAMA_OVERLAP_*` ma **omette queste due**,
entrambe esistenti e con difetto 0 (`ggml-backend.cpp:1827`, `:1860`). Il commento del manifesto dice
*«Keep the defaults aligned with their call sites»*: qui non è disallineato, è **assente**. Una corsa
con `FINESTRA=8` non lascerebbe traccia nel record di lancio.

**5. La cura del guardiano `IBRIDO=0` è applicata a 3 funzioni su 4.**
`cuda_buffer_ammesso` (`ggml-cuda.cu:3064-3067`) è usata a `:3073` (`set_tensor_async`), `:3082`
(`get_tensor_async`), `:3092` (`set_tensor_2d_async`) — ma **non a `:3103`**
(`ggml_backend_cuda_get_tensor_2d_async`), che conserva il confronto stretto
`buf->buft == ggml_backend_cuda_buffer_type(cuda_ctx->device)`. È esattamente il difetto che il
commento `:3047-3063` descrive come scoperto l'11/8 provando `LLAMA_MAPPED_IBRIDO=0`, **lasciato in
piedi in una delle quattro sedi**.
*Verificato dopo*: l'unico chiamante di `ggml_backend_tensor_get_2d_async` è
`ggml-backend-meta.cpp:1755` (backend "meta", multi-device), e il nostro fork è single-device
([[ds4-single-device-no-multigpu]]). **Quindi NON è un blocco per la casella «lane spenta +
IBRIDO=0»: è un'incoerenza latente**, da chiudere per igiene ma non prima della corsa.
**LETTO NEL CODICE.**

**6. IL PUNTO PIÙ GRAVE: leggendo il codice, il buffer MAPPATO non può innescare il fallback
per-esperto — eppure i 277 `cudaMemcpyAsync` sono stati misurati.**

La catena, tutta LETTA NEL CODICE:

1. il fallback per-esperto (`ggml-backend.cpp:2044-2126`) agisce su `input`, e `input` è un elemento
   di `split->inputs[]`;
2. un peso entra in `split->inputs[]` **solo se** `src_backend_id != cur_backend_id && !ggml_backend_sched_buffer_supported(src, cur_backend_id)` (`:1597`);
3. `ggml_backend_sched_buffer_supported` è `supports_buft(backend, buf->buft)` (`:1225`);
4. per il buffer mappato **CUDA lo supporta sempre**: `ggml_backend_cuda_device_supports_buft` è
   `ggml_backend_buft_is_cuda(buft) && buft->device == dev` (`ggml-cuda.cu:5984-5987`), e il tipo
   mappato condivide **apposta** il puntatore `get_name` col tipo CUDA (`:1456`) ed espone lo stesso
   `device` (`:1463`);
5. **e la CPU lo supporta quando `is_host` è vero** (`ggml-cpu/ggml-cpu.cpp:488-490`).

Cioè: **con `IBRIDO=1` il buffer mappato è supportato da ENTRAMBI i backend, quindi non diventa mai
un `split->inputs[]`, quindi non può essere copiato — né per esperto né in blocco.** La condizione
`is_host` al passo (2) è *necessaria* al fallback ma **non sufficiente**, e il mappato fallisce
l'altra metà proprio per la scelta di design che lo fa riconoscere come CUDA.

Il candidato naturale è allora il buffer `CPU` **puro** (`is_host` vero incondizionatamente, e CUDA
NON lo supporta), che negli script di banco è dove sta la **bozza**: `-otd
'blk\.0\....=CUDA0_Mapped, ffn_(gate|up|down)_exps\.weight=CPU'` contro `-ot
'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'` per il bersaglio (es. `braccio_blocchi.ps1:37`,
`:104`; stessa forma in `braccio_k.ps1`, `braccio_fj.ps1`, `braccio_bozza.ps1`, `braccio_cura.ps1`).
Ma **anche questa strada non si chiude**: perché quei pesi finiscano su uno split CUDA serve il ramo
di offload `:1122-1128`, che richiede `ggml_backend_cuda_device_offload_op` = `get_op_batch_size(op)
>= op_offload_min_batch_size`, cioè **`ne[2] >= 32`** (`ggml-cuda.cu:6008`, difetto 32 da
`GGML_OP_OFFLOAD_MIN_BATCH` a `:6217`). La bozza gira con `--spec-draft-ubatch-size 16`
(`braccio_blocchi.ps1:102`): **16 < 32, l'offload non scatta.**

**Quindi, sul codice e sulla configurazione che ho letto, nessuna delle due strade porta ai 277.**
Delle due l'una: o la corsa che li ha misurati aveva una collocazione diversa da quella degli script
letti (per esempio `GGML_OP_OFFLOAD_MIN_BATCH` abbassato, o un `-ub` che alza `ne[2]`, o il prefill
invece del decode), oppure uno dei cinque anelli sopra è sbagliato. **DEDOTTO, non verificato — ed è
il punto da chiudere per primo**, perché la nota di memoria attribuisce i 277 a `is_host`, cioè a
`LLAMA_MAPPED_IBRIDO`, e **se l'attribuzione è sbagliata allora spegnere `IBRIDO` non li toglie**, e
la casella «lane spenta + IBRIDO=0» non compra quello che ci si aspetta da lei.

**Come chiuderlo senza indovinare**, con strumenti già nel repo: `GGML_SCHED_DEBUG=2` stampa
l'assegnazione vera dei nodi ai backend (indicata da `llama-context.cpp:1627` come la verifica
dedicata) e `GGML_SCHED_DEBUG_INFO=1` la fa uscire a livello INFO invece che DEBUG, che il filtro
del server mangia (`ggml-backend.cpp:1148-1157`). Una sola corsa corta con quelle due variabili dice
di quale buffer sono i pesi che vengono copiati e verso quale split.

**7. `is_host` e `supports_op` leggono la stessa variabile ma decidono con criteri diversi.**
`supports_op` sospende il rifiuto quando la cache è attiva (`:5541`, `cache_ammessa`); `is_host`
**no** (`:1439`). Risultato con `SLOT=512 IBRIDO=1`: la MMID resta sulla GPU **e** il buffer continua
a dichiararsi host — cioè **l'ibrido è "acceso" per l'ammissibilità dei buffer e "spento" per
l'assegnazione delle op, contemporaneamente**. Nessuno ha scelto questa combinazione: è il residuo
di due leve nate in momenti diversi. Non produce copie (vedi n. 6), ma tiene il backend CPU
formalmente abilitato a prendersi qualunque op sui pesi esperti, e **rende l'assegnazione dipendente
dall'ordine di priorità dei backend invece che da una decisione esplicita**. **LETTO NEL CODICE**
per le due condizioni, **DEDOTTO** per la conseguenza.

**8. `LLAMA_OVERLAP_PIN` si spegne solo col carattere `'0'`.**
`return !(v && *v && *v == '0')` (`llama-context.cpp:1653`) contro `return v && *v && *v != '0'` di
tutte le altre. `PIN=false` lascia il pin **acceso**. Un braccio "senza pin" scritto con qualunque
altra sintassi ha misurato il pin acceso.

**9. `LLAMA_OVERLAP_VERIFICA` non verifica niente a regime, ed è documentato.**
`ggml-cuda.cu:2626-2651`: sotto CUDA graph il codice host gira **solo alla cattura**, e in cattura il
D2H è illegale quindi si salta. Il commento è esplicito («costo zero, copertura zero») — lo segnalo
perché **è una verifica il cui nome promette molto più di quel che dà**, e nel log non c'è modo di
distinguere «verificato, zero disallineamenti» da «mai eseguito».

**10. Nessuna diagnostica sui dispatch RIFIUTATI.** Il cancello `:2210-2231` ha cinque motivi di
rifiuto e **non ne conta nessuno**. `10 lavori/grafo` su 43 strati è il sintomo; la causa non è
misurabile senza aggiungere un contatore. È il numero che serve per sapere se la lane è limitata
dalla struttura del grafo o dal fatto che ce n'è **uno solo in volo alla volta**
(`split_spedito < 0`, `:2210`).

**11. `join (sched)` è un SOTTOSTIMA: il join di fine grafo non è cronometrato.**
`prof.us_join` è incrementato in un solo punto, `:1980-1984`, dentro il ramo `deve_unire`. Ma ci
sono altri tre `ggml_sched_worker_unisci` **non profilati**: `:2262` (**il lavoro spedito negli
ultimi split, unito a fine grafo**), `:1942` (percorso d'errore), `:2421` (`sched_reset`) e `:2511`
(`sched_synchronize`). Il primo non è un caso limite: **se l'ultimo dispatch del grafo cade negli
ultimi due split, tutta la sua attesa è invisibile alla sonda.** Quindi i `24,9 ms` di join sono un
pavimento, non il valore. **LETTO NEL CODICE.**

**12. Un solo lavoro in volo, ma `MAX_EVENTI = 64`.** Si allocano fino a 64 eventi
(`:816`, `:2238-2240`) mentre la struttura ne può usare **uno per volta** (`split_spedito` è uno
scalare). Gli eventi 1..63 servono solo perché `n_spediti` non viene riusato dentro il grafo; è
memoria, non un bug, ma segnala che il disegno prevedeva più lavori concorrenti e l'implementazione
ne fa uno.

---

# RIASSUNTO (20 righe) — priorità alle domande 1 e 4

1. **Il "worker" è UN thread** (`ggml-backend.cpp:1029`, `:2236`), creato pigro al primo dispatch, uno per sched.
2. Ma calcola chiamando il backend CPU, che apre il threadpool a `-t 7`: **7 thread dentro una chiamata bloccante** (`:910` + `llama-context.cpp:2938-2952`).
3. **Gli esperti alla CPU li sceglie la GPU**: `kern_partiziona` ordina per residenza (0 non residente / 1 in sfratto / 2 fresco) e le **viste** tagliano i primi `k_cpu` (`cache-esperti.cu:3349-3421`, `llama-graph.cpp:1868-1871`).
4. **Alla CPU vanno i MISS della cache.** Più la cache funziona, meno lavoro utile ha la lane: sono in competizione per costruzione.
5. Sincronizzazione: ingresso su un `cudaEvent` registrato **lato host fra due lanci** (`:2242`), uscita sul `join` al primo split successivo (`:1981`).
6. **`attesa-evento`, `calcolo`, `attesa-lavoro` sono misurate su UN thread** (il worker), **cumulative dall'avvio**, **mai azzerate**, divise per `prof.n_graphs` (`:850-853`, `:2287-2292`).
7. Le tre voci **partizionano l'intero tempo di parete**: `9,3+15,5+12,3 = 37,1 ms/grafo` è il tempo di parete per grafo, non un bilancio della lane.
8. Quindi **`attesa-lavoro` è il residuo del mondo esterno**: la deriva `8,3 → 12,3` a `calcolo` fermo dice «il resto del sistema è rallentato di 4-5 ms/grafo», coerente col 13-15% del riavvio del 12/8.
9. **`prof` è una static di funzione condivisa fra sched**: i contatori del worker (solo target) sono divisi per i grafi di target **+ bozza**. I `10 lavori/grafo` sono probabilmente ~35 per grafo target.
10. **`K=2` = numero medio di esperti alla CPU su 6**, frazionario e distribuito per strato con Bresenham (`llama-graph.cpp:1824-1829`); il taglio è nelle viste, quindi **cambiare K non ricattura i CUDA graph**.
11. Fra `K=2` e `K=3` i due rami **si scambiano il collo** (pareggio a 2,33); `K=4` mette la CPU seriale largamente in testa. `K>=6` **spegne** lo split.
12. **`SPIN=2.000.000` è calibrato, non un residuo**: copre i ~1-2 ms fra strati per evitare 43 risvegli condvar da 79 µs (`:796-801`, `:856-858`).
13. Il confronto con `LLAMA_CACHE_ESPERTI_SPIN=256` **non è pertinente**: quello è un poll **dentro un kernel CUDA** (`cache-esperti.cu:2571`). Due processori diversi.
14. Ma con ~1,2 ms di attesa media per lavoro il worker **non si parcheggia quasi mai**: brucia i ~12 ms/grafo di `attesa-lavoro` in attesa attiva pura (nessuna `pause`, nessuna `yield`), ~14% della CPU, **in contesa coi 7 thread che calcolano**.
15. **`is_host` dipende da UNA sola cosa**: `LLAMA_MAPPED_IBRIDO != 0 && g_cuda_mapped_uva` (`ggml-cuda.cu:1439`). Non guarda cache, soglia né batch.
16. **SÌ, si può avere il mappato senza `is_host`: `LLAMA_MAPPED_IBRIDO=0`.** Il buffer è scelto da `-ot ...=CUDA0_Mapped` e la sua allocazione non guarda la variabile (`ggml-cuda.cu:1357-1404`, `common/arg.cpp:277-289`); i kernel continuano a leggere la RAM via PCIe.
17. **Prezzo**: senza `is_host` il backend CPU non accetta più quel buffer (`ggml-cpu.cpp:488-490`), quindi **la lane CPU non è più alimentabile senza copiare i pesi**. Lane e `is_host` sono accoppiate per costruzione.
18. **Per la casella mai provata (bozza + lane spenta + fork + 512 slot) l'accoppiamento non morde**: `IBRIDO=0` + `K=0` + `ASYNC=0` è coerente, tutti i rami tornano al percorso GPU, **è raggiungibile oggi senza toccare codice**.
19. **Ma NON aspettatevi da lì i 277 memcpy in meno.** Leggendo il codice il fallback per-esperto **non è raggiungibile dal buffer mappato nemmeno oggi**: serve anche `!buffer_supported`, e il mappato è supportato da CUDA (condivide `get_name`) e dalla CPU (via `is_host`). **La loro origine va identificata con `GGML_SCHED_DEBUG=2` prima di attribuirla a `IBRIDO`** — è il buco n. 6 delle «cose che non tornano».
20. La finestra di sovrapposizione **è larga uno split** perché la condizione di join usa «viene dopo, quindi PUÒ dipenderne» invece di «dipende» (`:1976`); la cura esiste già (`LLAMA_OVERLAP_FINESTRA`, `:1858`) ma è a 0 e **non è nemmeno nel manifesto**.
