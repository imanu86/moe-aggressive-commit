# SHAREDCORE — shared expert su CPU senza contesa sui core

Data: 2026-07-29. Mandato: eliminare i ~46 ms/token di contesa sui core del
braccio S1 (`DS4_CPU_SHARED_EXPERT=1`, PRE 266 vs 220 ms, meccanismo sano:
fallback=0, shared_wait_ms p50=0,025). Nessuna build, nessun server, `D:\`
mai aperto; scritto solo in `.microbench/sharedcore/`.

Patch: `sharedcore.patch` — 1 file, **+328/−4** (`git apply --numstat`:
`328 4 ds4-p4a/ds4.c`), 7 hunk. `git apply --check` **PASS sul tree
corrente** (preimage sha sotto). Righe citate come «:N» = tree corrente
(preimage); «post :N» = file patchato.

## FATTO 1 — LA MAPPA DEI THREAD (dal codice, non dai tempi)

**(a) Chi calcola lo shared.** Un thread worker per grafo (`[shared-cpu]`,
creato in `ds4_shared1_create`, ds4.c:11644; loop `ds4_shared1_worker_main`
:11432) esegue `ds4_shared1_eval` (:11380). L'eval fan-outa i due matvec sul
**pool g132**: submit `ds4_g132_parallel_for` a :11414 e :11419 sotto
`g_shared1_pool_mutex` (:11413). Il pool g132 (worker `ds4_g132_worker_main`
:865, spawn :936-943) è dimensionato a **tutta la macchina**:
`g_g132_pool.n_threads = g_pool.n_threads` (:932), con `g_pool.n_threads` =
`min(cpu_online,12)` o `DS4_THREADS` (:745-758). La partizione del chiamante
gira sul worker `[shared-cpu]` stesso (:976). Quindi ogni layer accende un
burst di **n_threads thread compute per ~1,4 ms** (shared_cpu_ms p50 1,375).

**(b) Chi serve le letture (miss path).** UN SOLO thread: il route worker
CUDA `cuda_moe_route_worker` (ds4_cuda.cu:42070; spawn :38534 e :39245). I
miss sono serviti dentro `cuda_moe_tiering_enforce_request` (:40903),
chiamata dal worker a :42411; le letture girano **sul thread del worker
stesso**: lo dichiara il commento di strumentazione cu:4605-4608 («entrambe
le letture strumentate — pread a chunk e overlapped QD4 — girano su quel
thread») e lo mostrano i siti `cuda_moe_transient_pread_chunked`
(cu:41367/41378/41390; funzione :31034). Nessun `ds4_parallel_for` esiste in
ds4_cuda.cu: le letture non hanno pool.

**(c) Cosa condividono.** NON una coda né un lock (mutex diversi, moduli
diversi): condividono **l'intero set di core, senza alcuna separazione**.
Prove dal codice: (1) pool g132 = tutta la macchina, punto (a); (2) in tutto
il tree non esiste una sola chiamata di affinità (`SetThreadAffinityMask` /
`SetThreadIdealProcessor` / `pthread_setaffinity`: zero hit nei sorgenti) e
l'unica priorità è il BACKGROUND_BEGIN del worker SSD-wrap (cu:34846,
G73_OPEN-only) — il route worker gira a priorità normale su core qualunque;
(3) l'overlap temporale è per costruzione: lo schedule shared parte a
ds4.c:13857, PRIMA del prepare routed (:13894-13902) che pubblica la
richiesta servita dal route worker, e il join è a :14137 — il burst matvec
si sovrappone esattamente alla finestra in cui il route worker legge i miss
dello STESSO layer; (4) quando il route worker è idle cede il quanto con
`SwitchToThread` (cu:42134-42138), che con 11-12 matvec runnable atterra sul
burst. Canali secondari dichiarati: il worker `[shared-cpu]` attende il D2H
con `cudaEventSynchronize` su eventi SENZA `cudaEventBlockingSync`
(cu:16362-16365, wait :16434-16441) → spin del driver su un core durante la
finestra `d2h_wait`; e la banda DRAM (26,7 MB/layer di pesi Q8 streamati).
Con ~12 thread compute + decode + route worker + thread del driver su 16
core logici, il route worker perde timeslice durante ogni burst: è la
contesa osservata (~1,1 ms/layer), non attesa al join (wait p50 0,025 ms).

## FATTO 2 — LA SEPARAZIONE, dietro flag

`DS4_CPU_SHARED_EXPERT_DEDICATED=N` (default 0 = percorso odierno; N>16
clampato a 16; valore non numerico → 0 con log). Due livelli:

- **N>0 = pool separato** (post :11302-11565): N thread dedicati creati una
  volta al primo arm (`ds4_shared1_dedicated_acquire`, refcount fra grafi,
  ultimo `ds4_shared1_destroy` li spegne e joina). L'eval instrada i due
  matvec sul pool dedicato (post :11683-11698); il worker `[shared-cpu]`
  NON prende partizioni: dorme su condvar e il suo core torna allo
  scheduler → i thread compute sono esattamente N, gli altri core restano
  al route worker/decode/driver. Submit non disponibile → inline, mai in
  errore. Il pool g132 con dedicated attivo **non viene neppure
  inizializzato** da shared1 (post :11947-11950).
- **`DS4_CPU_SHARED_EXPERT_AFFINITY=1` in più = anche affinità** (solo
  Windows, la macchina di campagna): maschera 1-core per thread applicata
  dal creatore sull'HANDLE (da `_beginthreadex`, diritti pieni) con
  `SetThreadAffinityMask` + `SetThreadIdealProcessor` (post :11477-11499).
  Scala dei core dal logico più alto in giù SALTANDO i sibling SMT
  (16 logici → 15,13,11,9,…; mai CPU0; fallimento = soft, thread libero).
  Così «meno thread» e «core riservati» si misurano separatamente.

**Log all'attivazione (una riga)**:
`ds4: [shared-cpu] dedicated pool armed threads=N affinity=yes|no|requested-not-applied applied=K/N read-pool=untouched (route worker, g132 e g_pool invariati)`.
I contatori esistenti sono intatti: schedule/join/worker e i punti di misura
di `shared_cpu_ms`/`shared_wait_ms`/`scheduled`/`completed` non cambiano di
una riga; cambia solo il valore del campo `pool=` nel summary e nella riga
armed (`dedicated` | `g132` | `single-thread`, post :11805/:11982).

**Perché non riesplode la bomba dei due submitter (dspark2fix).** Il pool
dedicato è NUOVO, non un terzo submitter del g132 a slot singolo: là restano
i due di oggi (ramo g132 di shared1 quando dedicated è spento, drafter
NextN), entrambi su `g_shared1_pool_mutex`, zero righe toccate. Il pool
dedicato ha il SUO `submit_mutex` tenuto per l'intera durata del job
(submit+attesa, post :11542-11565): due grafi armati serializzano per
costruzione e non esiste alcun percorso di submit parallelo alla stessa
pool. Lo shutdown avviene solo a refs=0, e ogni istanza rilascia il ref DOPO
il join del proprio worker (post :11819-11821): nessun submitter può essere
in volo durante lo spegnimento.

## Neutralità e residui dichiarati

- Flag tutti spenti: `ds4_shared1_create` ritorna NULL a :11551 prima di
  qualunque getenv nuova → zero costo, zero thread; residuo = la classe di
  ricompilazione già accettata dal protocollo (come shared1 NOTA §4).
- `DS4_CPU_SHARED_EXPERT=1` senza DEDICATED (o `=0` esplicito): un solo test
  bool `s->use_dedicated` per eval (43/token, sul worker, non sul decode
  thread); rami e byte del percorso g132 identici a oggi.
- `ds4_shared1` è struct PRIVATA di ds4.c (typedef :10623, unico uso in
  questo file, allocata con calloc nel modulo): i due bool nuovi sono
  appesi IN CODA (post :11618-11622); nessuna struct condivisa cambia
  layout (il grafo tiene solo il puntatore, :10738).
- Affinità: solo _WIN32 (altrove `affinity=requested-not-applied`); N>cpu
  disponibili → i thread oltre la scala restano liberi; con cpus dispari la
  scala può toccare CPU0 e in quel caso il thread resta libero (guardia
  `core<=0`); il secondo grafo riusa N/affinità del primo arm (dichiarato
  nel commento, post :11444-11446).
- Zone di altri agenti non toccate: il patch tocca SOLO ds4.c dentro il
  blocco shared1 (nessuna riga di ds4_cuda.cu, quindi niente precheck route
  worker :42193-42286, indexer, transport ledger; niente dspark*/logids/
  lane/econ/pin2/Q1; `ds4_nextn_g132_submit` intatto — l'inserto inizia
  DOPO la sua chiusa).

## Verifiche eseguite (statiche)

- `git apply --check .microbench/sharedcore/sharedcore.patch`: PASS sul tree
  corrente; `--numstat`: `328 4 ds4-p4a/ds4.c` (unico file).
- Roundtrip su copia del tree: file risultante byte-identico al postimage
  atteso (sha sotto); CRLF preservati (patch generato byte-preciso).
- Bilanciamento `{} () []`: delta simmetrici (+33/+33, +151/+151, +13/+13).
- Verifica simbolo-per-simbolo contro il sorgente: os_thread/os_mutex/
  os_cond/os_once (src/platform/os_thread.h; `_beginthreadex` → HANDLE con
  diritti pieni, os_thread.c:37-49), `os_cpu_count` (:746 già in uso),
  `ds4_parallel_fn` (:664), worker matvec e ctx (:11392-11410),
  `DS4_MAYBE_UNUSED` (:141), pattern generation/done/condvar identico ai
  pool esistenti (:698-736, :865-901).

## SHA-256

Preimage (tree corrente al momento della consegna):

```text
716718325c7f3d8e57543301419c3f586b62de8ea0710b7fe4f6e9111dbbcd58  ds4-p4a/ds4.c
```

Atteso dopo `git apply`:

```text
44257ba6b983b29f9dff9c62da08956f13a170f2b04f68b92168704efdadefec  ds4-p4a/ds4.c
```

Artefatto:

```text
4c657481df19a4572af41c7265f4e7a9bf15c448fec70950e5784ae3bc97292c  .microbench/sharedcore/sharedcore.patch
```
