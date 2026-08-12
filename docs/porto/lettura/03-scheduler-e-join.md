# 03 — Lo scheduler: split, ingressi, sync, join (`ggml/src/ggml-backend.cpp`)

Lettura statica, nessuna esecuzione. Repo `D:\llama-overlap`, `HEAD = bd06d4ddf`,
file di 2.978 righe. Base upstream del confronto `5c3a58686`: **+617 / −10 righe**
(`git -C D:/llama-overlap diff 5c3a58686..HEAD --stat -- ggml/src/ggml-backend.cpp`).
LETTO NEL CODICE.

Convenzione: `bk:NNNN` = `D:\llama-overlap\ggml\src\ggml-backend.cpp:NNNN`;
`cu:NNNN` = `D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu:NNNN`;
`ctx:NNNN` = `D:\llama-overlap\src\llama-context.cpp:NNNN`;
`gr:NNNN` = `D:\llama-overlap\src\llama-graph.cpp:NNNN`.
Ogni affermazione e' marcata **[L]** = LETTO NEL CODICE oppure **[D]** = DEDOTTO,
non verificato.

> **Avvertenza sui numeri di riga della memoria.** La nota
> `[[277-copie-per-token-fallback-scheduler]]` cita `ggml-backend.cpp:1946`. In
> QUESTO albero quel blocco sta a **`bk:2042-2126`** (la lambda `copy_experts` e'
> a `bk:2090`). `bk:1946` qui e' dentro la lambda `esci`. Le due numerazioni
> vengono da alberi diversi: non confondere. **[L]**

---

## Il quadro strutturale che decide tutto il resto

Tre fatti letti nel codice cambiano il senso di ogni numero della sonda.
Vengono prima perche' senza di loro le risposte alle sei domande si leggono male.

### F1 — `n_copies == 1`, quindi **tutti** gli `events[][]` sono `NULL`

`sched->n_copies = parallel ? GGML_SCHED_MAX_COPIES : 1` (`bk:2324`), e gli
eventi si allocano **solo se `n_copies > 1`** (`bk:2359-2363`). Il flag `parallel`
e' `cparams.pipeline_parallel`, che richiede `model.n_devices() > 1`
(`ctx:497-502`). Il FORK e' single-device. Quindi `n_copies == 1` e
**`sched->events[b][c] == NULL` per ogni b,c**. **[L]**

Conseguenza meccanica: nel ciclo degli ingressi, i tre rami "a evento"
(`bk:2021-2022`, `bk:2036-2037`, `bk:2132-2133`) **non vengono mai presi**: si
cade sempre nell'`else`, cioe' su `sync_profilato(split_backend)` — un
`cudaStreamSynchronize` bloccante sull'host. **Il percorso a evento non e'
"escluso dalla misura": e' morto.** **[L]**

### F2 — `prof` e' **UN SOLO static condiviso da tutti gli scheduler del processo**

`static ggml_sched_profilo_acc prof;` a `bk:1905` e' una statica **di funzione**,
non un membro di `sched`. Il processo ha almeno due scheduler (bersaglio e
bozza: `sched` e' membro di `llama_context`, `ctx:712`, e la bozza e' un secondo
contesto). Quindi la riga `sched-profilo: ... per grafo: ...` e' una media pesata
su una popolazione **mista** di grafi bersaglio (grandi) e grafi bozza (piccoli).
**[L] per la statica condivisa; [D] per i due contesti (evidenza: `cparams.ctx_other`,
`ctx:194`, e `-md/--spec-type draft-dspark` nella riga di comando).**

**Il fattore di diluizione si ricava da tre strade indipendenti che concordano:**

| strada | conto | risultato |
|---|---|---|
| ledger 11/8 §16.4 | «2,17 grafi/token» × 1,85 token/ciclo | **4,0 grafi per ciclo** |
| worker | attesa-evento 9,271 + calcolo 15,445 + attesa-lavoro 8,302 = 33,0 ms/grafo = durata media di UN grafo; ciclo 127,9 ms | **3,9 grafi per ciclo** |
| split | ASYNC=0 → 3,7 split/grafo (ledger §8.2), ASYNC=1 → 35,2; grafo bersaglio storico 130,6 (Fase 2), 5,0 (K=0) | **≈4 grafi per ciclo**, bozza ≈3,2 split |

Quindi: **il grafo BERSAGLIO ha ~131 split e ~43 lavori worker; i numeri stampati
sono diluiti di ~4×.** «35,2 split/grafo» e «10 lavori/grafo» non sono il grafo:
sono la media su 1 grafo bersaglio + ~3 grafi bozza. **[D], ma con tre conferme
indipendenti che chiudono allo 0,3%.**

Ricostruzione dei valori VERI per grafo bersaglio (moltiplicare per ~4):
`ingressi ≈ 11,3 ms`, `sync ≈ 8,6`, `calc CPU ≈ 3,4`, `calc altri ≈ 12,1`,
`join ≈ 98,8`, `worker calcolo ≈ 61,8`. **[D]**

### F3 — gli accumulatori **non si azzerano mai**

`prof` e' costruita una volta (statica); nessuna riga la resetta. La stampa a
`bk:2268` (`++prof.n_graphs % 50 == 0`) divide **somme cumulative** per
`n_graphs` cumulativo. Idem i quattro atomici del worker
(`bk:850-853`): `fetch_add` e basta, nessun `store(0)`. **[L]**

**Quindi ogni riga stampata e' una MEDIA CORRENTE DALL'AVVIO DEL PROCESSO**, non
una finestra. Il prefill e il transitorio (primo tocco delle pagine mappate,
warmup CUDA, prima cattura dei grafi) restano dentro per sempre, diluendosi.
Il metodo corretto — gia' stabilito il 6/8, `LEDGER_RUN.tsv` riga 111 — e' la
**finestra marginale** fra due stampe consecutive:

```
    valore_marginale = (X_n * n − X_m * m) / (n − m)      con n, m multipli di 50
```

Confrontare «l'ultima riga della corsa A» con «l'ultima riga della corsa B` e'
valido **solo se le due righe stanno allo stesso `n_graphs`** e le due corse
hanno lo stesso prefill. Altrimenti si confrontano due storie diverse. **[L]**

---

## A. CONTATORI

Tutti in **microsecondi** internamente (`ggml_time_us()`), stampati in **ms** con
la divisione `/1000.0/prof.n_graphs`. Tutti **CUMULATIVI, mai azzerati** (F3).

| nome nel log | campo | incremento | stampa | tipo | unita' stampata |
|---|---|---|---|---|---|
| `%lld grafi` | `prof.n_graphs` | `bk:2268` (`++` nella condizione) | `bk:2272` | cumulativo | conteggio |
| `%.1f split/grafo` | `prof.n_splits` | `bk:2145` (split lavorati) **e** `bk:1958` (lo split affidato al worker, contato senza lavorarlo) | `bk:2273` | cumulativo | split/grafo |
| `ingressi %.3f ms` | `prof.us_ingressi` | `bk:2144`, finestra aperta a `bk:1995` | `bk:2274` | cumulativo | ms/grafo |
| `di cui sync %.3f` | `prof.us_sync` | **`bk:1919`, unico sito** | `bk:2275` | cumulativo | ms/grafo |
| `calc CPU %.3f ms` | `prof.us_calc_cpu` | `bk:2157` | `bk:2276` | cumulativo | ms/grafo |
| `calc altri %.3f ms` | `prof.us_calc_altro` | `bk:2159` | `bk:2277` | cumulativo | ms/grafo |
| `worker %lld lavori/grafo` | `w->n_lavori` (atomico) | `bk:914` | `bk:2287` | cumulativo | **divisione INTERA** (vedi sotto) |
| `attesa-evento %.3f ms` | `w->us_attesa_ev` | `bk:912` | `bk:2288` | cumulativo | ms/grafo |
| `calcolo %.3f ms` | `w->us_calcolo` | `bk:913` | `bk:2289` | cumulativo | ms/grafo |
| `attesa-lavoro %.3f ms` | `w->us_attesa_lav` | `bk:893` | `bk:2290` | cumulativo | ms/grafo |
| `join (sched) %.3f ms` | `prof.us_join` | `bk:1983` | `bk:2291` | cumulativo | ms/grafo |
| `copie join-async %.1f` | `prof.n_join_async` | `bk:2032` | `bk:2292` | cumulativo | copie/grafo |

Note che cambiano la lettura:

- **`lavori/grafo` e' una divisione fra interi**: `(long long)(w->n_lavori.load()/prof.n_graphs)`
  (`bk:2287`) — la parentesi chiude PRIMA del cast. Quindi «10» significa
  `[10, 11)`. Non usarlo per rapporti fini. **[L]**
- **Il blocco `worker ...` esiste solo se `sched->worker != NULL`** (`bk:2281`),
  cioe' solo dopo che almeno un lavoro e' stato spedito. La sua assenza nel log
  e' il testimone che l'overlap non si e' MAI ingaggiato. **[L]**
- **Le tre regioni sono disgiunte per costruzione**: il join si misura a
  `bk:1980-1983`, PRIMA che `t_ingressi0` parta a `bk:1995`; il calcolo a
  `bk:2149-2160`, DOPO che `us_ingressi` sia stato chiuso a `bk:2144`. Quindi
  `us_sync ⊂ us_ingressi`, e `us_join`, `us_ingressi`, `us_calc_*` non si
  sovrappongono. **[L]**
- **`prof` non e' atomica** (int64_t nudi). Con `-np 1` c'e' un solo thread di
  sched, quindi nessuna corsa; con piu' slot serviti in parallelo sarebbe una
  corsa vera. **[L]**
- **Cio' che NON e' misurato da nessun contatore**, dentro `compute_splits`:
  il blocco di dispatch `bk:2210-2249` per intero — le `ggml_backend_tensor_get_async`
  D2H degli ingressi del ramo CPU (`bk:2230`), la creazione pigra del thread
  worker (`bk:2234-2237`), `ggml_backend_event_new` (`bk:2239`),
  `ggml_backend_event_record` (`bk:2242`), `ggml_sched_worker_spedisci` con mutex
  + `notify_one` (`bk:2243`); e `ggml_backend_event_record` finale a `bk:2254`.
  **Un intero confine host↔device per strato e' fuori dal bilancio.** **[L]**
- Fuori da `compute_splits` e quindi **fuori dal bilancio**: `ggml_backend_sched_synchronize`
  (`bk:2504-2522`, chiamato da `ggml_backend_sched_graph_compute` a `bk:2485`),
  che fa `ggml_sched_worker_unisci` + un `ggml_backend_synchronize` per backend.
  **E' li' che finisce la coda GPU residua del grafo.** **[L]**

---

## B. VARIABILI D'AMBIENTE lette in questo file

Regime di riferimento: `IBRIDO=1`, `ASYNC=1`, `K=2`, `BATCH_MAX=2`, `PIN=1`,
`JOIN_ASYNC=0` (confermato in `docs/porto/dopo_il_riavvio.ps1:88-104`, con
`-ot 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'`, `-ngl 99`, `-ub 64`,
`-np 1`, `-t 7`). Tutte lette **una sola volta** in una lambda `static` — cioe'
**non si possono cambiare a caldo** e il primo processo che le legge fissa il
comportamento per tutta la vita. **[L]**

| variabile | riga | difetto | valore nel regime | ramo raggiungibile? |
|---|---|---|---|---|
| `GGML_SCHED_PROFILO` | `bk:1806` | off | **1** | si': accende timer e stampa |
| `LLAMA_OVERLAP_ASYNC` | `bk:1817` | off | **1** | si': accende confine forzato (`bk:1540`), dispatch (`bk:2210`), worker |
| `LLAMA_OVERLAP_JOIN_ASYNC` | `bk:1827` | **0** | **0** | **NO** — `join_async` (`bk:1929`) e' falso, il ramo `bk:2027-2033` e' irraggiungibile |
| `LLAMA_OVERLAP_FINESTRA` | `bk:1860` | **0** | non impostata → 0 | **NO** — `finestra == 0`, quindi `ggml_sched_split_dipende_dal_worker` (`bk:1883`) non viene MAI chiamata e il ramo `bk:1973-1975` e' morto |
| `LLAMA_OVERLAP_SPIN` | `bk:861` | **2.000.000** | difetto | si': lo spin gira in `ggml_sched_worker_attendi` (`bk:873`) sia sul worker sia **sul thread di sched dentro il join** |
| `GGML_SCHED_DEBUG` | `bk:2313` | 0 | 0 | no (stampa assegnazioni) |
| `GGML_SCHED_DEBUG_INFO` | `bk:1161` | off | off | no |
| `GGML_SCHED_DEBUG_REALLOC` | `bk:2320` | 0 | 0 | no |

Fuori file, ma decisive per la raggiungibilita' dei rami di QUESTO file:
`LLAMA_MAPPED_IBRIDO` (`cu:1435`, `cu:5529`), `LLAMA_MAPPED_IBRIDO_SOGLIA`
(`cu:5533`), `LLAMA_OVERLAP_K` e `LLAMA_OVERLAP_PIN` (`gr:1824`, `ctx:1639/1652`),
`LLAMA_OVERLAP_BATCH_MAX` (`gr:1848`), `GGML_OP_OFFLOAD_MIN_BATCH` (`cu:6217`,
difetto **32**).

**Due leve inerti nel regime adottato**: `LLAMA_OVERLAP_JOIN_ASYNC` e
`LLAMA_OVERLAP_FINESTRA`. Con `FINESTRA=0` la funzione `ggml_sched_split_dipende_dal_worker`
(29 righe, `bk:1883-1899`) e' codice morto: costa zero e non fa nulla. **[L]**

---

## C. COMPLESSITA'

**Per split** (`bk:1949-2257`), con `I = split->n_inputs` (≤ 30, `bk:761`),
`N = split->graph.n_nodes`, `W = n_nodes` del grafo worker, `E = n_expert` (256):

| pezzo | costo | note |
|---|---|---|
| join `deve_unire` | O(1) con `finestra=0`; **O(I·W)** con `finestra>0` (`bk:1883-1899`) | scansione a puntatori, doppio ciclo annidato |
| ciclo ingressi | O(I) chiamate a `ggml_backend_sched_get_tensor_backend` (hash lookup) | |
| test `copia_join_async` | **O(I·W)** se `join_async` e' acceso (`bk:2006-2011`) | ciclo lineare sui nodi del worker **per ogni ingresso** |
| gather degli id | O(ne0·ne1) per lo scan + O(E) per il bitset (`bk:2077-2084`) | ammortizzato da `prev_ids_tensor` (`bk:2070`): si rifa solo se il tensore id cambia |
| raggruppamento esperti | O(E) per lo scan del bitset (`bk:2104-2126`) | emette **una** `set_tensor_async` per **corsa di id consecutivi usati** |
| ricerca id fra gli ingressi | O(I) (`bk:2062-2068`) | |
| lancio | O(1) chiamata; il costo vero e' dentro il backend |

**Per grafo**: `ggml_backend_sched_split_graph` (`bk:1236-1732`) fa 5 passate su
tutti i nodi, la passata 5 con un ciclo interno su `GGML_MAX_SRC = 10`
(`ggml.h:224`) — quindi **O(n_nodes · 10)** con hash lookup per src, piu'
`ggml_graph_view` + `ggml_backend_graph_optimize` per split (`bk:1658-1662`).
Gira **a ogni token** (via `ggml_backend_sched_alloc_graph`, `bk:2472`) salvo
riuso del grafo. Con la fusione HC il grafo e' 10.507 nodi. **[L]**

`ggml_backend_sched_compute_splits` e' **O(n_splits · I)** in chiamate, ma il
tempo di parete e' dominato dalle attese, non dal conto.

---

## D. HOST vs DEVICE — la lista ORDINATA dei punti di sincronizzazione

### D.1 Chi blocca l'host e chi no

| chiamata | riga | cosa fa davvero | blocca l'host? |
|---|---|---|---|
| `ggml_backend_synchronize(CUDA)` | `bk:418` → `cu:3164` | `cudaStreamSynchronize(cuda_ctx->stream())` | **SI'** |
| `ggml_backend_synchronize(CPU)` | `bk:420-422` | `iface.synchronize == NULL` (`ggml-cpu.cpp:201`) → **ritorna subito** | no (≈0) |
| `ggml_backend_event_wait(CUDA, ev)` | `bk:556` → `cu:4987` | `cudaStreamWaitEvent` | **no**, e' device-side |
| `ggml_backend_event_synchronize(ev)` | `bk:549` → `cu:6036` | `cudaEventSynchronize` | **SI'** |
| `ggml_backend_graph_compute_async(CUDA)` | `bk:454` → `cu:4879` | scansione nodi + `cudaGraphLaunch` (`cu:4854`) o lanci diretti | **no** (vedi Domanda 2) |
| `ggml_backend_graph_compute(CPU)` | `bk:448` | `graph_compute` + `synchronize` (no-op) | **SI'**, e' calcolo vero |
| `ggml_backend_tensor_copy(host→CUDA)` | `bk:481-489` → `cu:731-737` | `cudaMemcpyAsync` su **`cudaStreamPerThread`** + `cudaStreamSynchronize(cudaStreamPerThread)` | **SI'** |
| `ggml_backend_tensor_set_async(CUDA)` | `bk:258` → `cu:3069` | `cudaMemcpyAsync` H2D **sullo stream di calcolo** | no |
| `ggml_backend_tensor_get_async(CUDA)` | `bk:272` → `cu:3078` | `cudaMemcpyAsync` D2H **sullo stream di calcolo** | no |
| `ggml_backend_event_record(ev, CUDA)` | `bk:542` → `cu:4981` | `cudaEventRecord` sullo stream di calcolo | no |
| `ggml_sched_worker_unisci` | `bk:940-951` | spin fino a 2·10⁶ giri + condvar | **SI'**, e brucia un core |

**Dettaglio che pochi vedono**: la copia bloccante dell'ingresso
(`ggml_backend_tensor_copy`, `bk:2026` e `bk:2137`) NON gira sullo stream di
calcolo ma su `cudaStreamPerThread` (`cu:735`). Non c'e' ordinamento implicito
fra i due stream: l'unica cosa che rende corretta quella copia e' il
`cudaStreamSynchronize(cuda_ctx->stream())` immediatamente precedente
(`bk:2024` / `bk:2039` / `bk:2135`). **La barriera non e' cautela: e' portante.** **[L]**

### D.2 La sequenza, in ordine, per UNO strato MoE con il fork acceso

Struttura degli split per strato (3 per strato, cfr. Domanda 6):
`S_a` = CUDA, chiude con `CACHE_ESPERTI_PARTIZIONA` (`overlap_produttori=true`);
`S_b` = CUDA, ramo GPU esperti; `S_c` = CPU, ramo CPU esperti.

```
 #  dove   riga        cosa                                                  contatore
 ------------------------------------------------------------------------------------
 1  HOST   bk:2039     cudaStreamSynchronize(stream calcolo)                 us_sync
                       [drena TUTTA la coda GPU dello strato precedente]
 2  HOST   bk:2026/    cudaMemcpyAsync H2D su cudaStreamPerThread +          us_ingressi
           bk:2137     cudaStreamSynchronize(cudaStreamPerThread)            − us_sync
                       [l'uscita del ramo CPU dello strato precedente entra]
 3  HOST   bk:2150     graph_compute_async(CUDA, S_a) -> SOLO sottomissione  us_calc_altro
 4  DEV    bk:2230     cudaMemcpyAsync D2H di cur e ids_cpu, sullo           NESSUNO
                       stream di calcolo, DOPO i kernel di S_a
 5  HOST   bk:2242     cudaEventRecord(evento[n], stream calcolo)            NESSUNO
 6  HOST   bk:2243     spedisci: mutex + notify_one al worker                NESSUNO
 7  HOST   bk:2150     graph_compute_async(CUDA, S_b) -> sottomissione       us_calc_altro
                       [S_b ha n_inputs == 0: nessun sync, nessuna copia]
 8  HOST   bk:1956     split_id == split_spedito -> continue (S_c saltato)   n_splits++
 9  HOST   bk:1981     ggml_sched_worker_unisci: spin + condvar              us_join
    WORK   bk:906      cudaEventSynchronize(evento[n])                       us_attesa_ev
                       [aspetta che la GPU abbia finito S_a + le due D2H]
    WORK   bk:910      ggml_backend_graph_compute(CPU, S_c)                  us_calcolo
10  -> torna al punto 1 dello strato successivo
```

Per grafo bersaglio (43 strati MoE): **~43 `cudaStreamSynchronize` sullo stream
di calcolo + ~43 `cudaStreamSynchronize(cudaStreamPerThread)` dentro le copie +
~43 join = ~129 rendezvous host↔device**, piu' il `sched_synchronize` finale
fuori dal ciclo. Diviso per ~1,85 token/ciclo: **~70 confini per token** —
coerente con i «~76 confini a token» della nota di memoria. **[D]** (il conto
poggia su 43 strati con il fork e su 1,85 token/ciclo).

---

# DOMANDE SPECIFICHE

## 1. `us_sync`: dentro quale chiamata si accumula, esattamente

**`us_sync` cresce in UN SOLO punto: `bk:1919`**, dentro la lambda
`sync_profilato` (`bk:1912-1920`), che misura una sola cosa:
`ggml_backend_synchronize(b)`. Verificato con grep esaustivo su tutto il file:
`us_sync` compare a `bk:1795` (dichiarazione), `bk:1919` (incremento), `bk:2275`
(stampa). Nient'altro. **[L]**

`sync_profilato` e' invocata da **sei** siti, tutti dentro il ciclo degli
ingressi:

| sito | argomento | quando | costo reale nel regime |
|---|---|---|---|
| `bk:2024` | `split_backend` | ingresso con `GGML_TENSOR_FLAG_INPUT`, ramo `else` di `events != NULL` | **reale** (CUDA): `cudaStreamSynchronize` |
| `bk:2039` | `split_backend` | ingresso normale, ramo `else` di `events != NULL` — **il sito principale** | **reale** (CUDA) |
| `bk:2054` | `input_backend` | dentro il fallback esperti, prima di leggere gli id | **≈0**: `input_backend` e' il backend CPU, `iface.synchronize == NULL` |
| `bk:2073` | `ids_backend` | dopo `tensor_get_async` degli id di routing | **reale** se `ids_backend` e' CUDA (caso normale: `ids_backend = split_backend`, `bk:2058`) |
| `bk:2131` | `input_backend` | fallback generico, `cpy_tensor_async` fallita | **≈0** se sorgente CPU |
| `bk:2135` | `split_backend` | fallback generico, ramo `else` di `events != NULL` | **reale** (CUDA) |

**Cosa NON ci finisce dentro** (la parte della domanda):

1. **`ggml_backend_event_synchronize`** a `bk:2022` e a `bk:2133`, e
   **`ggml_backend_event_wait`** a `bk:2037`. Il commento a `bk:1910-1911` («i
   percorsi a eventi (CUDA-CUDA) restano fuori») **e' letteralmente vero**: quei
   tre siti non passano da `sync_profilato`. **[L]**
   **MA il commento e' fuorviante nel nostro regime**: per F1 quei rami non
   vengono MAI presi, perche' `sched->events[b][c] == NULL` sempre. Non stiamo
   escludendo un costo: stiamo descrivendo codice morto. Ogni attesa del ciclo
   degli ingressi e' un `cudaStreamSynchronize` e **e' contata**. **[L]**
2. **`ggml_backend_event_synchronize(w->evento)` del worker** (`bk:906`): sta su
   un altro thread e va in `us_attesa_ev`, non in `us_sync`. **[L]**
3. **`ggml_backend_synchronize(split_backend)` a `bk:2186`**: e' nel ramo
   `callback_eval`, non contato — e irraggiungibile in produzione
   (`sched->callback_eval` e' nullo, `ctx:1605` lo imposta da `cparams.cb_eval`).
   **[L]**
4. **`ggml_backend_synchronize` a `bk:1773`** (dentro `alloc_splits`, sul
   percorso di riallocazione del grafo): fuori dalla regione misurata. **[L]**
5. **`ggml_backend_synchronize` a `bk:2514`** (dentro
   `ggml_backend_sched_synchronize`): **fuori da `compute_splits` per intero**.
   E' il drenaggio finale della coda GPU dopo l'ultimo split. **Non e' contato da
   niente.** **[L]**
6. **La copia bloccante `ggml_backend_tensor_copy`** (`bk:2026`, `bk:2137`):
   contiene essa stessa un `cudaStreamSynchronize(cudaStreamPerThread)`
   (`cu:736`), ma non passa da `sync_profilato`. Finisce in
   `us_ingressi − us_sync`, cioe' nella voce che il commento a `bk:1909-1910`
   chiama «copie». **Quella voce non e' solo banda: contiene un'attesa.** **[L]**

**Conclusione operativa**: `us_sync` = «tempo in cui l'host e' fermo dentro
`cudaStreamSynchronize` sullo stream di calcolo, chiamato dal ciclo degli
ingressi». Non e' il costo di una barriera: e' **il tempo di esecuzione GPU non
ancora consumato al momento della barriera**. `sync` che cresce da 2,166 a 6,208
significa «all'arrivo della barriera la GPU aveva piu' lavoro arretrato», e le
cause possibili sono tre e non una: (a) la GPU e' piu' lenta, (b) l'host arriva
alla barriera prima, (c) la barriera cade in un punto diverso della coda. **[D]**

## 2. `us_calc_altro`: solo sottomissione, e dove finisce il tempo GPU

**CONFERMATO: e' solo la sottomissione asincrona.** `us_calc_altro` misura il
tempo di parete di `ggml_backend_graph_compute_async(split_backend, &split->graph)`
(`bk:2150`, timer `bk:2149`/`bk:2155`) quando il device NON e' di tipo CPU
(`bk:2156-2159`). Per CUDA quella chiamata e'
`backend->iface.graph_compute` (`bk:456`) = `ggml_backend_cuda_graph_compute`
(`cu:4879-4979`), che **non contiene alcun `cudaStreamSynchronize`,
`cudaDeviceSynchronize` o `cudaMemcpy` sincrono** sul percorso normale —
verificato con grep sull'intero `ggml-cuda.cu`: l'unico
`cudaStreamSynchronize(cuda_ctx->stream())` sta a `cu:3167`, dentro
`ggml_backend_cuda_synchronize`. **[L]**

Cosa fa davvero quella chiamata:
- `ggml_cuda_set_device` (`cu:4882`);
- init/battito della cache esperti (`cu:4889-4890`), che al primo giro fa
  `cudaMalloc` e periodicamente stampa;
- scansione di tutti i nodi per i `PARTIZIONA` e `pubblica_fine`
  (`cu:4905-4918`) → **una** `cudaMemcpyAsync` H2D sullo stream
  (`cache-esperti.cu:3633`), asincrona;
- decisione grafo CUDA e `ggml_cuda_graph_evaluate_and_capture` (`cu:4972`), che
  finisce in `cudaGraphLaunch` (`cu:4854`) o nei lanci diretti dei kernel.

Nessuno di questi blocca l'host. **[L]**

Simmetricamente, `us_calc_cpu` (`bk:2157`) misura
`ggml_backend_graph_compute_async(CPU, ...)` = `ggml_backend_cpu_graph_compute`,
che e' **bloccante** (il backend CPU non ha coda). Il commento a `bk:1796`
(«bloccante») e a `bk:1797` («lancio») e' quindi corretto per entrambe le voci.
**[L]**

**Dove finisce il tempo di ESECUZIONE GPU** — quattro canali, in ordine di
grandezza attesa:

1. **`us_sync`** — il canale principale. Ogni `cudaStreamSynchronize` a
   `bk:2039` paga il lavoro GPU accumulato dal sync precedente. **[L]**
2. **`us_attesa_ev`** del worker (`bk:912`) — `cudaEventSynchronize` sull'evento
   «produttori finiti»: e' esattamente il tempo di esecuzione GPU dello split
   `S_a` piu' le due D2H. 9,271 ms/grafo diluito, cioe' **~37 ms per grafo
   bersaglio**. **[L] per il meccanismo, [D] per il fattore 4.**
3. **`us_ingressi − us_sync`** — dentro `ggml_backend_tensor_copy` c'e' un
   `cudaStreamSynchronize(cudaStreamPerThread)` (`cu:736`); se quello stream ha
   arretrato, e' attesa mascherata da «copia». **[L]**
4. **Fuori bilancio**: `ggml_backend_sched_synchronize` (`bk:2504`), chiamato da
   `ggml_backend_sched_graph_compute` (`bk:2485`) DOPO `compute_splits`. Il
   residuo della coda finisce li' e **nessun contatore lo vede**. **[L]**

**E un quinto canale, dedotto:** la coda di lancio asincrona di CUDA e' finita
(tipicamente ~1024 lanci pendenti); quando si riempie, `cudaGraphLaunch` /
`cudaLaunchKernel` **bloccano l'host**. In quel regime una parte del tempo GPU
compare **dentro `us_calc_altro`**, che smette di essere «solo sottomissione».
Con 10.507 nodi e i grafi CUDA attivi e' un regime possibile. **[D], non
verificato.** Discriminante: `calc altri` che sale mentre `sync` scende, a parita'
di lavoro.

## 3. Il fallback «un esperto per volta»

**Dove.** `bk:2042-2126`. Codice **upstream**, non nostro (i nostri interventi
nell'intorno sono solo le sostituzioni `ggml_backend_synchronize` →
`sync_profilato` a `bk:2054` e `bk:2073`: hunk `@@ -1585,7 +2051,7 @@` e
`@@ -1604,7 +2070,7 @@` del diff). **[L]**

**La condizione completa** (`bk:2044-2049`) — sono **quattro** predicati in AND,
non uno:

```c
split->graph.n_nodes > 0 &&
ggml_backend_buffer_get_usage(input->buffer) == GGML_BACKEND_BUFFER_USAGE_WEIGHTS &&
ggml_backend_buffer_is_host(input->buffer) &&
(node->src[0] == input_cpy && node->op == GGML_OP_MUL_MAT_ID)   // node = split->graph.nodes[0]
```

**Prerequisito nascosto, ed e' quello che conta**: perche' il ciclo arrivi qui,
il tensore dei pesi deve gia' essere un **`split->inputs[]`**. Lo diventa solo a
`bk:1597`, cioe' se
`src_backend_id != cur_backend_id && !ggml_backend_sched_buffer_supported(src, cur_backend_id)`.
Cioe': **i pesi devono stare in un buffer che il backend di destinazione NON
supporta**, ed essere `is_host`. **[L]**

**Quante `cudaMemcpyAsync` genera e da cosa dipende.** Il conteggio e' esatto e
leggibile a `bk:2104-2126`: si emette **una** `copy_experts` (`bk:2090`) per ogni
**corsa massimale di id consecutivi usati** nella bitmap `used_ids`. Ogni
`copy_experts` e' una `ggml_backend_tensor_set_async` (`bk:2096`) = **una**
`cudaMemcpyAsync` H2D sullo stream di calcolo (`cu:3075`). Quindi:

```
   copie = Σ (su ogni ingresso-peso che entra nel ramo)  #corse_consecutive(id usati)
```

Dipende da: (a) numero di split che attraversano il ramo — cioe' quanti strati
hanno i pesi esperti in un buffer non supportato dalla destinazione; (b) numero
di token dell'ubatch (piu' token → piu' esperti distinti → piu' corse, fino a
saturare); (c) `n_expert_used` (top-K); (d) la **compattezza** degli id: id
adiacenti si fondono in una copia sola, quindi con 256 esperti quasi tutti usati
le copie crollano, mentre con pochi esperti sparsi si tende a 1 copia per
esperto. Il gather degli id costa una D2H + un `cudaStreamSynchronize`
(`bk:2072-2073`) **una sola volta per tensore id distinto**, grazie alla cache
`prev_ids_tensor` (`bk:2070`, `bk:2086`). **[L]**

**Come si spegne senza spegnere la lane CPU** — e la risposta onesta e' che *a
questo sito non conviene spegnerlo*:

- Se il ramo NON si prende, si cade nell'`else` a `bk:2127-2139`:
  `cpy_tensor_async` fallisce (richiede CUDA su entrambi i lati, `cu:3113-3119`)
  → `sync_profilato(input_backend)` + `sync_profilato(split_backend)` +
  `ggml_backend_tensor_copy` del **tensore intero** (tutti i 256 esperti), in
  modo **bloccante**. **Spegnere il ramo peggiora di un ordine di grandezza.** E'
  esattamente il «IBRIDO=0 ASYNC=1 disastro (212 split, 3.266 ms)» del ledger
  §8.3. **[L] per il meccanismo, [D] per l'identificazione col braccio.**
- La leva corretta e' **a monte**: fare in modo che i pesi non siano un
  `split->inputs[]`. Tre modi, tutti compatibili con la lane CPU accesa:
  1. **`-ot ...=CUDA0_Mapped`** (quello che gia' facciamo). Il tipo mappato
     condivide il puntatore `get_name` con il tipo CUDA (`cu:1288-1290`,
     `cu:822-824`), quindi `ggml_backend_buft_is_cuda` e' vero e
     `ggml_backend_cuda_device_supports_buft` (`cu:5987`) lo accetta →
     `buffer_supported(CUDA)` vero → **nessuna copia**. E con `IBRIDO=1`
     `is_host` e' vero (`cu:1441`), quindi anche il backend CPU lo accetta →
     **nessuna copia neanche sul lato CPU**. Il buffer mappato e' l'unico che
     soddisfa entrambi. **[L]**
  2. **`GGML_OP_OFFLOAD_MIN_BATCH`** (`cu:6217`, difetto 32): alza la soglia e
     `ggml_backend_cuda_device_offload_op` (`cu:6005-6009`) smette di tirare su
     GPU le mul_mat_id con pesi host, chiudendo il ramo `1.off` a `bk:1122-1128`.
     Non tocca il pin del ramo CPU (`ctx:1659`), che agisce per NOME.
  3. **`sched->op_offload = false`** (`cparams.op_offload`, `bk:2367`): stessa
     cosa, globale.

**Attenzione**: `bk:2045-2046` legge `input->buffer` **senza** passare da
`view_src`, mentre venti righe sopra `bk:2013` lo fa (`input_buffer`). Per un
ingresso che sia una vista, i due predicati guardano buffer diversi. E' upstream,
ma e' una crepa reale. **[L]**

## 4. `copia_join_async` e `LLAMA_OVERLAP_JOIN_ASYNC`

**Cosa fa.** `bk:2014-2033`. Quando l'ingresso di uno split e' un tensore
**prodotto dallo split appena unito** (il ramo CPU), invece della sequenza
«barriera + copia bloccante» accoda la copia H2D **asincrona sullo stream del
backend di destinazione**: `ggml_backend_tensor_set_async(split_backend,
input_cpy, input->data, 0, nbytes)` (`bk:2030`) = `cudaMemcpyAsync` sullo stream
di calcolo (`cu:3075`). **[L]**

**Quale guardia lo protegge** — quattro condizioni in AND (`bk:2014-2017`), piu'
due a monte:

```c
join_async                                   // bk:1929: ASYNC && JOIN_ASYNC
&& split_unito >= 0                          // bk:2004: la join e' avvenuta IN QUESTA iterazione
&& prodotto_dallo_split_unito                // bk:2006-2011: identita' di puntatore fra
                                             //   input e un nodo del grafo del worker
&& dev_type(input_backend) == CPU            // bk:2015
&& input_buffer != NULL
&& ggml_backend_buffer_is_host(input_buffer) // bk:2016
&& split_backend->iface.set_tensor_async != NULL   // bk:2017
```

La correttezza poggia su due cose e sono entrambe scritte bene:
(a) il join e' gia' avvenuto (`bk:1981`), quindi la **sorgente host e' pronta**;
(b) `set_tensor_async != NULL` e' **la stessa condizione** che rende la copia
davvero asincrona — che e' precisamente l'errore di upstream #20793 (guardia
sulla *dichiarazione* di capacita', copia asincrona solo sotto una macro di
build), corretto qui. **[L]**

**Perche' il contatore stampa 0.0.** La premessa della domanda va **corretta**:

- **Il contatore stampa 0.0 perche' la leva era spenta, non perche' il ramo non
  funzioni.** `LLAMA_OVERLAP_JOIN_ASYNC` ha difetto 0 (`bk:1827-1830`) **e tutti
  gli script della campagna lo impostano esplicitamente a `'0'`**:
  `dopo_il_riavvio.ps1:103`, `due_per_due.ps1:117`, `freddo_fuso.ps1:86`,
  `curva_capienza.ps1:88`, `spin.ps1:54`. Con `join_async == false` il ramo
  `bk:2027-2033` non e' raggiungibile e `n_join_async` resta 0 per costruzione.
  **[L]**
- **Da acceso il ramo gira**: `LEDGER_11_AGOSTO.md` §16.3 misura
  **10,7 copie/grafo** con `JOIN_ASYNC=1`, contro 0,0 con la leva spenta, e
  `sync` scende del 13% (2,166 → 1,884). **10,7 su 10 lavori/grafo = ~1,07 copie
  per lavoro worker**, cioe' **esattamente una per strato**: e' il tensore
  `esperti_cpu` che entra nella `concat` (`gr:1938`). Il meccanismo copre il 100%
  dei casi che dovrebbe coprire. **[L] dal ledger, [D] per l'identificazione del
  tensore.**

**Il tetto strutturale che RESTA, e che farebbe stampare 0 anche da acceso.**
`split_unito` e' dichiarata **dentro il ciclo**, a `bk:1953`, e riazzerata a
`-1` a ogni iterazione. Viene valorizzata solo a `bk:1990`, e solo se
`dipende_dal_worker` (`bk:1979`). Quindi:

> il ritorno asincrono e' possibile **solo** per gli ingressi dello **split
> immediatamente successivo al join**, e per nessun altro.

Se il consumatore dell'uscita CPU non fosse il primo split dopo il join — o se
quel primo split fosse a sua volta CPU (`set_tensor_async == NULL`, `ggml-cpu.cpp:196`)
— il contatore leggerebbe 0 pur con la leva accesa. **E' la stessa finestra larga
uno split della Domanda 5, applicata al ritorno.** Nella topologia di oggi la
coincidenza tiene (10,7 ≈ 1 per strato); e' una proprieta' del grafo, non una
garanzia del codice. **[L]**

## 5. Il join: dove aspetta, e perche' la finestra e' larga uno split

**Dove.** `bk:1981`: `ggml_sched_worker_unisci(sched->worker)`, cronometrata a
`bk:1980` / `bk:1983` → `us_join`. La funzione (`bk:940-951`) fa:
`ggml_sched_worker_attendi(w, FATTO, FERMA)` (`bk:947`), che e'
**spin fino a `LLAMA_OVERLAP_SPIN` = 2.000.000 giri** su `w->stato`
(`bk:871-875`), poi parcheggio su condvar (`bk:876-883`). Cioe': **il thread di
sched brucia un core in attesa attiva mentre aspetta la CPU**. **[L]**

Esistono altri due `unisci` (`bk:2262` a fine grafo, `bk:2421` in `sched_reset`,
`bk:2511` in `sched_synchronize`) e uno nel percorso d'errore (`bk:1942`):
**nessuno di questi e' cronometrato**, quindi il lavoro spedito negli ultimi
split non compare in `us_join`. **[L]**

**La condizione** (`bk:1967-1993`):

```c
const bool e_cpu = dev_type(split_backend) == CPU;
const bool deve_unire = finestra > 0
    ? (e_cpu || split_id > split_spedito + finestra || dipende_dal_worker(...))
    : (split_id > split_spedito || e_cpu);          // <-- il nostro regime
```

**Perche' la finestra e' larga esattamente uno split.** Con `finestra == 0` la
regola e' `split_id > split_spedito`. La cronologia e':

| iterazione | split | cosa accade |
|---|---|---|
| `P` | `S_a` (CUDA) | ingressi, lancio, **dispatch**: `split_spedito = P+2` (`bk:2245`) |
| `P+1` | `S_b` (CUDA) | `P+1 > P+2`? **no**; `e_cpu`? **no** (il dispatch pretende `splits[P+1].backend_id == split_backend_id`, `bk:2216`) → **niente join**. Ingressi (0) + lancio |
| `P+2` | `S_c` (CPU) | `split_id == split_spedito` → `continue` a `bk:1960` |
| `P+3` | `S_a` strato dopo | `P+3 > P+2` → **JOIN** |

Fra la spedizione e il join passa **un solo split**, `S_b`, e per giunta un
`S_b` con `n_inputs == 0` (i suoi ingressi vengono dallo stesso backend, quindi
`bk:1597` non ne registra nessuno). Il lavoro che l'host compie nella finestra e'
percio' **una sola `graph_compute_async`, cioe' una sottomissione** — i ~0,25 ms
del commento a `bk:1843`, contro i ~0,70 ms di ramo CPU da coprire. **[L]**

**E c'e' un secondo tetto, piu' duro del primo**, che il commento a `bk:1850-1857`
non nomina: `e_cpu` resta nella condizione **anche con `finestra > 0`**
(`bk:1973`). Il prossimo split CPU e' il ramo CPU dello **strato successivo**:
quindi anche con `FINESTRA=8` la finestra non puo' superare i ~3 split che
separano due rami CPU consecutivi. Il vincolo e' vero (un solo proprietario del
threadpool, `bk:803-808`), ma significa che **la curva `FINESTRA=1..8` satura per
costruzione dopo 3**, ed e' esattamente il piatto misurato il 11/8
(`sync` 1,911 / 1,941 / 1,878 a finestra 1/4/8). La «falsificazione» del ledger
§16.3 e' quindi confermata anche a tavolino. **[L]**

**Il punto che riordina il quadro.** Nella finestra l'host **non aspetta** la GPU
di `S_b`: la sottomette e basta. Poi si blocca sul join, dove aspetta, **in
serie**: (i) `cudaEventSynchronize` del worker sull'evento «produttori finiti» =
il tempo GPU di `S_a`; (ii) il calcolo CPU del ramo. Il ramo GPU `S_b` gira in
concorrenza con (ii) ma **non** con (i), perche' (i) e' un'attesa
**sullo stesso stream** che precede `S_b`. Numeri: `attesa-evento 9,271` +
`calcolo 15,445` = **24,716** ms/grafo, contro `join (sched) 24,698`: **entro lo
0,1%**. Il join e' interamente spiegato da quei due addendi: **non c'e' overhead
di rendezvous dentro** (lo spin lo assorbe). **[L] per il meccanismo, [L] per i
numeri, presi da `docs/porto/dopo_il_riavvio.ps1:16-21`.**

## 6. Gli split: da cosa dipende il numero, e quanti confini attraversa un token

**Da cosa dipende.** Un nuovo split si apre a `bk:1546` per tre cause e solo tre:

1. `node_backend_id != cur_backend_id` — cambio di backend (upstream);
2. `need_new_split` da **peso su backend incompatibile** (`bk:1508-1514`) o da
   **split pieno** (`n_inputs == GGML_SCHED_MAX_SPLIT_INPUTS == 30`,
   `bk:1517-1525`) (upstream);
3. **`confine_partizione`** (`bk:1540-1543`, **nostro**): `ASYNC` acceso **e** il
   nodo precedente era un `GGML_OP_CACHE_ESPERTI_PARTIZIONA`. Lo split che si
   chiude prende `overlap_produttori = true` (`bk:1548`).

Quindi `n_splits` e' funzione di **(topologia del grafo, assegnazione dei nodi ai
backend)** e di nient'altro. Non dipende da slot, colpi, FORK, spin, capienza,
zavorra, join-async, finestra. **[L]**

**Perche' 35,2 e' «costante in ogni configurazione provata».** Perche' tutte le
configurazioni sotto esame avevano lo **stesso** grafo, la **stessa** assegnazione
e la stessa miscela bersaglio/bozza. Le leve che lo muovono davvero, e i valori
storici a ledger:

| leva | effetto su split/grafo | fonte |
|---|---|---|
| `LLAMA_OVERLAP_ASYNC` 0→1 | **3,7 → 35,2** | LEDGER 11/8 §8.2 |
| `LLAMA_OVERLAP_K` / `PIN` (fork on/off) | 5,0 (K=0) → 87,7 (Fase 1) → 130,6 (Fase 2) *misure senza diluizione bozza* | LEDGER_RUN.tsv righe 124/131/150 |
| `LLAMA_MAPPED_IBRIDO` 1→0 | **212 split** | LEDGER 11/8 §8.3 |
| `LLAMA_DSV4_HC_FUSO` | cambia n_nodes (34.329 → 10.507) | memoria |
| accettazione della bozza `p1` | cambia il **mix** dei grafi, quindi la MEDIA senza toccare nessun grafo | F2 |

**L'ultima riga e' un allarme per chi caccia la regressione**: `35,2` puo' muoversi
per un motivo che non sta nello scheduler. Nella coppia 05:06/06:07 non si e'
mosso, e `worker calcolo` e' rimasto a 15,4-15,5: **il mix e' stabile e il
confronto ingressi/sync regge.** **[D], ma e' il controllo giusto da citare.**

**Quanti confini attraversa un token.** Struttura per strato MoE con il fork
(letta in `gr:1865-1940` + `bk:1540`): `S_a` CUDA che chiude con `PARTIZIONA`,
`S_b` CUDA (ramo GPU), `S_c` CPU (ramo CPU); il `concat` + `get_rows(perm_inv)` +
coda dello strato **non aprono un quarto split**, perche' il prossimo confine
forzato e' solo dopo la `PARTIZIONA` successiva. Quindi **3 split per strato**, e
`3 × 43 + 2 ≈ 131` — che coincide con i **130,6** misurati in Fase 2. **[L] per
la struttura, [D] per il 43.**

Per **grafo bersaglio**:
- 43 split CPU, 88 split CUDA;
- **43 attraversamenti GPU→CPU** (le due `cudaMemcpyAsync` D2H di `cur` e
  `ids_cpu` a `bk:2230`: **86 copie**);
- **43 attraversamenti CPU→GPU** (`esperti_cpu`, copiato in modo bloccante a
  `bk:2026`/`bk:2137` all'inizio dello `S_a` successivo);
- **~129 rendezvous host↔device** (43 `cudaStreamSynchronize` + 43
  `cudaStreamSynchronize(cudaStreamPerThread)` dentro le copie + 43 join).

Per **token** (~1,85 token/ciclo): **~70 confini**. **[D]**

---

# COSE CHE NON TORNANO

**N1 — «277 copie per token dal fallback dello scheduler» non regge alla lettura
dei predicati, nella configurazione del bersaglio.**
La riga di comando mette **tutti** i pesi esperti del bersaglio in
`CUDA0_Mapped` (`dopo_il_riavvio.ps1:106`,
`-ot 'ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped'`). Quel buft e':
- accettato da CUDA, perche' `ggml_backend_buft_is_cuda` confronta il puntatore
  di `get_name`, condiviso di proposito (`cu:822-824`, `cu:1288-1290`, `cu:5987`);
- accettato dalla CPU con `IBRIDO=1`, perche' `is_host` e' vero (`cu:1441`).

Quindi `ggml_backend_sched_buffer_supported` e' **vera da entrambi i lati**, la
riga `bk:1597` non crea nessuna copia, i pesi **non diventano mai
`split->inputs[]`** e il ramo `bk:2042` **non e' raggiungibile per il bersaglio**.
**[L]**

Il candidato che invece lo raggiunge e' **il modello di bozza**:
`$OTD = 'blk\.0\....=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU'`
(`dopo_il_riavvio.ps1:33`). I pesi esperti della bozza, dal blocco 1 in poi,
stanno in `ggml_backend_cpu_buffer_type`: **`is_host` vero, `buft_is_cuda`
falso** → CUDA non li supporta → diventano split input → il ramo si accende.
**[D], non verificato.**

Se e' cosi', cambia il senso di due conclusioni del ledger §8.3: quelle copie
sarebbero del **grafo della bozza**, non del bersaglio, e la frase «i byte non
passano di li'» andrebbe riletta. **Il controllo costa una corsa**:
`GGML_SCHED_DEBUG=2 GGML_SCHED_DEBUG_INFO=1` stampa
`## SPLIT #n: <backend> # k inputs: [nome (taglia)]` (`bk:1172-1180`): basta
guardare se fra i nomi degli ingressi compaiono `ffn_*_exps.weight`, e di quale
modello.

**N2 — la nota «la condizione e' `is_host`, cioe' `LLAMA_MAPPED_IBRIDO`» inverte
il segno.** Con `IBRIDO=1` il buffer mappato e' host **e** cuda, quindi
**nessuno** copia. Con `IBRIDO=0` `is_host` diventa falso: il backend CPU smette
di accettare il buft, il ramo CPU pinnato (`ctx:1659`) forza comunque i nodi su
CPU, e i pesi diventano split input con `is_host == false` → **il ramo per-esperto
viene saltato** e si cade sulla copia del **tensore intero**, bloccante
(`bk:2127-2139`). E' il «212 split, 3.266 ms» del ledger. Cioe': `IBRIDO=0` non
toglie le copie, le rende **catastrofiche**. **[L]**

**N3 — il dispatch e' un buco nel bilancio.** `bk:2210-2249` non ha alcun timer:
2 `cudaMemcpyAsync` D2H, un `cudaEventRecord`, un mutex + `notify_one`, e alla
prima chiamata la creazione di un `std::thread` e di un `cudaEvent`. Per grafo
bersaglio sono ~43 passaggi. Se il costo per confine e' cresciuto (l'ipotesi
«+140 µs per confine»), **questo pezzo non lo mostrerebbe**: comparirebbe come
`sync` piu' alto al giro dopo. Aggiungere `us_dispatch` e' ~4 righe. **[L]**

**N4 — «di cui sync» non e' tutto il tempo di attesa negli ingressi.**
`us_ingressi − us_sync` viene letto come «copie» (commento `bk:1909-1910`), ma
contiene il `cudaStreamSynchronize(cudaStreamPerThread)` di `cu:736`. Se la
regressione fosse nel driver o nel percorso pinnato, si vedrebbe **li'**, e la
lettura «copie» la mascherebbe. Nella coppia 05:06/06:07:
`ingressi − sync` va da **0,673 a 0,676 ms** — piatto. **Il delta e' tutto in
`sync`.** **[L] + aritmetica sui numeri forniti.**

**N5 — la finestra `LLAMA_OVERLAP_FINESTRA` non puo' fare cio' che il commento
promette.** `bk:1850-1857` la presenta come «una curva invece di un salto», ma
`e_cpu` resta in AND-OR anche nel ramo nuovo (`bk:1973`): il join e' forzato al
prossimo split CPU, che dista 3 split. Da `FINESTRA=3` in su la leva e'
**identica a se stessa**. Il piatto misurato non e' una saturazione fisica: e' il
codice. **[L]**

**N6 — divisione intera in `lavori/grafo`.** `bk:2287`: la parentesi chiude prima
del cast, quindi si perde la parte frazionaria. Con ~10 lavori/grafo l'errore e'
fino al 10%: non usare quel numero per il rapporto lavori/split.

**N7 — `prof` e' condivisa fra bersaglio e bozza, ed e' non atomica.** Con
`-np 1` non e' una corsa, ma **e' una conflazione**: tutte le medie «per grafo»
sono medie su una popolazione mista (F2). Separare `prof` per `sched` costa lo
spostamento di una statica dentro `struct ggml_backend_sched`, e renderebbe
finalmente confrontabili le corse. **[L]**

**N8 — `bk:2045-2046` non passa da `view_src`** mentre `bk:2013` si': due
predicati sullo stesso ingresso guardano buffer diversi se l'ingresso e' una
vista. Upstream, ma reale. **[L]**

---

# RIASSUNTO (20 righe)

1. **`us_sync` cresce in un solo punto: `bk:1919`**, dentro `sync_profilato`, che
   avvolge esclusivamente `ggml_backend_synchronize`. Sei siti la chiamano:
   `bk:2024`, `2039`, `2054`, `2073`, `2131`, `2135`.
2. Di quei sei, **quattro sono `cudaStreamSynchronize` veri** (destinazione CUDA)
   e due costano ~0 (`ggml-cpu.cpp:201`: il backend CPU non ha `synchronize`).
3. Il commento «i percorsi a eventi CUDA-CUDA restano fuori» **e' letteralmente
   vero** (`bk:2022`, `2037`, `2133` non passano da `sync_profilato`)…
4. …**ma e' fuorviante**: con una sola GPU `pipeline_parallel` e' falso
   (`ctx:497`), quindi `n_copies == 1` e **tutti gli `events[][]` sono NULL**
   (`bk:2359`). Quei rami sono codice morto: non stiamo escludendo un costo.
5. **Fuori da `us_sync` restano quattro attese vere**: il `cudaEventSynchronize`
   del worker (`bk:906` → `us_attesa_ev`), il
   `cudaStreamSynchronize(cudaStreamPerThread)` dentro `ggml_backend_tensor_copy`
   (`cu:736`, finisce in «copie»), il `sched_synchronize` finale (`bk:2514`,
   **non contato da nulla**), e l'intero blocco di dispatch (`bk:2210-2249`).
6. **`us_calc_altro` e' SOLO sottomissione: confermato.**
   `ggml_backend_cuda_graph_compute` (`cu:4879-4979`) non contiene alcun
   `cudaStreamSynchronize`; l'unico e' in `ggml_backend_cuda_synchronize`
   (`cu:3167`). Finisce in `cudaGraphLaunch` (`cu:4854`), asincrona.
7. **Il tempo di esecuzione GPU finisce, in ordine**: (a) `us_sync`, (b)
   `us_attesa_ev` del worker, (c) dentro le «copie» via `cudaStreamPerThread`,
   (d) nel `sched_synchronize` fuori bilancio. Un quinto canale, **[D]**: se la
   coda di lancio CUDA si riempie, `cudaGraphLaunch` blocca e il tempo GPU entra
   in `us_calc_altro` — discriminante: `calc altri` sale mentre `sync` scende.
8. **Gli accumulatori non si azzerano mai** (`bk:1905` statica, mai resettata):
   ogni riga e' una **media corrente dall'avvio**. I confronti fra corse valgono
   solo a `n_graphs` uguale; il modo giusto e' la **finestra marginale** fra due
   stampe.
9. **`prof` e' una sola statica condivisa da bersaglio e bozza** (`bk:1905`): i
   valori «per grafo» sono medie su ~1 grafo bersaglio + ~3 grafi bozza. Il
   fattore ~4 e' confermato da tre strade indipendenti. **Il grafo bersaglio vero
   ha ~131 split e ~43 lavori worker.**
10. **Il fallback per-esperto** (`bk:2042-2126`, upstream) emette **una
    `cudaMemcpyAsync` per corsa di id consecutivi usati** (`bk:2090`, `2104-2126`).
    Ma per arrivarci il peso deve essere **gia' un `split->inputs[]`**, cioe' in
    un buffer che la destinazione non supporta: i nostri `CUDA0_Mapped` **non lo
    sono mai**. Il candidato reale sono i pesi della **bozza** (`-otd ...=CPU`).
11. **Spegnerlo a quel sito peggiora**: si cade sulla copia del tensore intero,
    bloccante (`bk:2127-2139`). Le leve giuste sono a monte: buft mappato,
    `GGML_OP_OFFLOAD_MIN_BATCH`, `op_offload` — nessuna tocca il pin del ramo CPU,
    che agisce per nome (`ctx:1659`).
12. **`copia_join_async` funziona**: stampa 0.0 perche' `JOIN_ASYNC` e' spento
    per difetto **e** messo esplicitamente a `'0'` in tutti gli script. Da acceso
    fa 10,7 copie/grafo = ~1 per lavoro worker.
13. Il suo tetto strutturale: `split_unito` e' **locale al ciclo** (`bk:1953`),
    quindi il ritorno asincrono vale **solo per lo split subito dopo il join**.
14. **Il join e' a `bk:1981`**, e aspetta **in spin** fino a 2·10⁶ giri
    (`bk:871-875`): il thread di sched brucia un core mentre aspetta la CPU.
15. **La finestra e' larga uno split perche' `split_spedito = split_id + 2`**
    (`bk:2245`) e lo split `+2` viene saltato (`bk:1956`): fra dispatch e join
    passa solo `S_b`, che per giunta ha `n_inputs == 0`. L'host copre **una
    sottomissione**, non un'esecuzione.
16. `us_join` (24,698) **= `attesa-evento` (9,271) + `calcolo` (15,445) = 24,716**,
    entro lo 0,1%: il join non ha overhead di rendezvous, e' interamente quelle
    due attese in serie.
17. **`LLAMA_OVERLAP_FINESTRA` non puo' funzionare**: `e_cpu` resta nel ramo
    nuovo (`bk:1973`), quindi il join e' forzato al prossimo split CPU, a 3 split
    di distanza. Da `FINESTRA=3` in su la leva e' identica a se stessa.
18. **Il numero di split dipende solo da topologia + assegnazione ai backend.**
    Nostro contributo: il confine forzato dopo `PARTIZIONA` (`bk:1540-1548`).
    Struttura: **3 split per strato** → `3×43+2 ≈ 131` per grafo bersaglio.
19. **Confini per token**: 43 GPU→CPU (86 D2H) + 43 CPU→GPU + ~129 rendezvous
    host↔device per grafo bersaglio → **~70 per token** a 1,85 token/ciclo.
20. **Per chi caccia la regressione**: `ingressi − sync` e' piatto (0,673 →
    0,676) e `worker calcolo` e' fermo (15,445 → 15,536), quindi il **mix
    bersaglio/bozza non e' cambiato** e la crescita e' tutta in `sync`, cioe' in
    `cudaStreamSynchronize` chiamato da `bk:2039`. Tre spiegazioni restano
    aperte e la sonda non le distingue: GPU piu' lenta, host che arriva prima,
    barriera in un punto diverso della coda. **Il buco da tappare per
    distinguerle e' `us_dispatch` (N3), quattro righe.**
