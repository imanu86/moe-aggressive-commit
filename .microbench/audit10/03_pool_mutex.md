# Audit 10 — pool, mutex, teardown

## (1) BUG

### B1 — ABA del refcount durante ultimo release e nuovo acquire del pool shared dedicato

- **File:riga verificata:** `ds4-p4a/ds4.c:11463-11467`, `ds4-p4a/ds4.c:11524-11548`, `ds4-p4a/ds4.c:11701-11709`, `ds4-p4a/ds4.c:11817-11818`.
- **Severità: MEDIA.**
- **Prova:** l'ultimo `release` porta `refs` a zero, imposta `shutdown`, sblocca `p->mutex` e lascia `initialized=true` per tutta la join dei thread (`ds4-p4a/ds4.c:11524-11538`); solo dopo la join torna sotto `p->mutex` e azzera lo stato (`ds4-p4a/ds4.c:11539-11548`). Un `acquire` concorrente che entra in quella finestra vede soltanto `initialized`, incrementa `refs` e ritorna successo senza controllare `shutdown` (`ds4-p4a/ds4.c:11463-11467`).
- **Scenario concreto:** grafo A distrugge l'ultima istanza dedicata; mentre A sta joinando i worker, il grafo B viene creato e riceve un ref “fantasma”. A poi azzera comunque `initialized/started/n_threads`, perdendo il ref di B. Gli eval di B degradano inline (`ds4-p4a/ds4.c:11701-11709`) ma il summary continua a dichiarare `pool=dedicated` perché guarda solo `s->use_dedicated` (`ds4-p4a/ds4.c:11817-11818`): esito osservabile sbagliato e perdita silenziosa della separazione dei core. Caso ABA più grave: dopo l'azzeramento A, un grafo C crea una nuova incarnazione con `refs=1`; quando B viene distrutto, il suo release senza identità di generazione può consumare il ref di C e spegnere il pool di C (`ds4-p4a/ds4.c:11524-11538`). Il job eventualmente già partito termina prima della join, quindi questa timeline non prova un UAF dei buffer, ma prova corruzione del lifecycle/refcount.

### B2 — i flag lane esplicitamente a `0` disabilitano comunque il g132 di shared1

- **File:riga verificata:** `ds4-p4a/ds4.c:11957-11971`, `ds4-p4a/ds4_cuda.cu:51141-51147`, `ds4-p4a/ds4.c:11987-11995`.
- **Severità: MEDIA.**
- **Prova:** shared1 testa la sola presenza di `DS4_G132_CPU_LANE` o `DS4_G132_CPU_LANE_GENERAL` con `getenv(...) != NULL` e forza `use_pool=false` (`ds4-p4a/ds4.c:11957-11968`); la lane CUDA, invece, è richiesta solo se il valore è esattamente `"1"` (`ds4-p4a/ds4_cuda.cu:51141-51147`).
- **Scenario concreto:** `DS4_CPU_SHARED_EXPERT=1`, dedicated assente/0 e `DS4_G132_CPU_LANE=0` (oppure `_GENERAL=0`) esportato dal runner. La lane è realmente spenta, ma shared1 gira single-thread per tutti i 43 layer. A banco compaiono `[shared-cpu] ... pool=single-thread` (`ds4-p4a/ds4.c:11987-11995`), nessuna riga `[g132-cpu-lane] result=ready` (`ds4-p4a/ds4_cuda.cu:51246-51254`) e `shared_cpu_ms` cresce: il valore “0” non è neutrale come atteso per una leva env.

## (2) INTERFERENZE FRA LEVE

### I1 — `DS4_CPU_SHARED_EXPERT=1` senza dedicated + `DS4_NEXTN_CPU_DRAFTER=1`: stessa coda g132, corretta ma con head-of-line blocking

- **Meccanismo:** il drafter prende `g_shared1_pool_mutex` per l'intero `ds4_g132_parallel_for` (`ds4-p4a/ds4.c:11303-11310`); shared1 prende lo stesso mutex e lo conserva attraverso entrambi i matvec, SwiGLU e quantizzazione intermedia (`ds4-p4a/ds4.c:11711-11721`). Non c'è più corruzione dello slot `fn/ctx/done`, ma un submit lungo del drafter può ritardare il job shared dello stesso token e viceversa.
- **Manifestazione a banco:** crescita di `shared_wait_ms{p50/p90}` e `shared_cpu_ms{p50/p90}` nel summary shared (`ds4-p4a/ds4.c:11791-11818`); crescita di `step_ms_avg/max`, `fwd_dense_avg` o `head_avg` nel summary NextN (`ds4-p4a/ds4.c:20811-20829`). Non esiste un contatore separato di attesa sul `g_shared1_pool_mutex`, quindi la firma è una crescita correlata dei due summary senza fallback shared.
- **Guardia suggerita:** combinazione ammessa per correttezza, ma non promuoverla senza confronto dei due summary. Se l'head-of-line è materiale, usare il dedicated shared; vietare il braccio legacy shared+NextN nei run di prestazione che non attribuiscono separatamente questi tempi.

### I2 — `DS4_CPU_SHARED_EXPERT_DEDICATED=N` + `DS4_NEXTN_CPU_DRAFTER=1`: code separate, ma core e DRAM non sono riservati

- **Meccanismo:** shared dedicato usa esclusivamente `g_shared1_dedicated` (`ds4-p4a/ds4.c:11694-11710`), mentre NextN usa g132 tramite `ds4_nextn_g132_submit` (`ds4-p4a/ds4.c:801-813`, `ds4-p4a/ds4.c:11300-11311`). Il pool g132 è dimensionato come `g_pool.n_threads` (`ds4-p4a/ds4.c:923-943`); l'affinità viene applicata solo ai thread dedicated (`ds4-p4a/ds4.c:11489-11505`), quindi non impedisce ai worker g132 non pinnati di essere schedulati sugli stessi core. Entrambe le leve leggono grandi pesi mmap, dunque resta contesa di scheduler/DRAM anche senza coda comune.
- **Manifestazione a banco:** `pool=dedicated` con `shared_cpu_ms` in aumento (`ds4-p4a/ds4.c:11791-11818`) insieme a `step_ms_avg`, `fwd_dense_avg` o `head_avg` in aumento (`ds4-p4a/ds4.c:20811-20829`). Se la pressione affama anche il route worker, aumentano `pickup_lag_ms`, `job_ms` o `read_total_ms` in `[worker-prof]` (`ds4-p4a/ds4_cuda.cu:5021-5032`).
- **Guardia suggerita:** nessun divieto di correttezza; non trattare `AFFINITY=1` come esclusione dei core. Limitare `N` e promuovere la combinazione solo se i tre summary (shared, NextN, worker-prof) restano stabili.

### I3 — dedicated shared + creazione/distruzione concorrente di grafi: interferenza di lifecycle

- **Meccanismo:** è la finestra B1: `acquire` accetta `initialized=true` durante lo shutdown (`ds4-p4a/ds4.c:11463-11467`), mentre l'ultimo `release` sblocca il mutex durante la join e poi azzera incondizionatamente la stessa incarnazione (`ds4-p4a/ds4.c:11533-11548`).
- **Manifestazione a banco:** un nuovo grafo stampa l'arm dedicated (`ds4-p4a/ds4.c:11937-11949`) ma lavora inline (`ds4-p4a/ds4.c:11701-11709`); il summary resta `pool=dedicated` e `shared_cpu_ms` sale (`ds4-p4a/ds4.c:11791-11818`). Una successiva distruzione può spegnere il pool di un terzo grafo, ripetendo la firma.
- **Guardia suggerita:** vietare create/destroy concorrenti di grafi shared dedicati; serializzare operativamente l'ultima distruzione con la successiva creazione finché il pool non possiede un'identità di generazione verificabile.

### I4 — `DS4_CPU_SHARED_EXPERT=1` legacy + flag lane presenti con valore falso

- **Meccanismo:** la presenza di `DS4_G132_CPU_LANE`/`_GENERAL` devia shared a single-thread (`ds4-p4a/ds4.c:11957-11968`), mentre CUDA abilita la lane soltanto con valore `"1"` (`ds4-p4a/ds4_cuda.cu:51141-51147`).
- **Manifestazione a banco:** `pool=single-thread` nell'arm/summary shared (`ds4-p4a/ds4.c:11987-11995`, `ds4-p4a/ds4.c:11791-11818`) e assenza della riga lane ready (`ds4-p4a/ds4_cuda.cu:51246-51254`).
- **Guardia suggerita:** nei runner, per indicare OFF rimuovere completamente entrambe le variabili lane; vietare `...=0` finché i due parser non hanno semantica coerente.

### I5 — lane G132 + NextN: combinazione già vietata, guardia sana

- **Coppia/tripla:** `DS4_NEXTN_CPU_DRAFTER=1` + `DS4_G132_CPU_LANE=1`; `_GENERAL=1` è rilevante solo insieme alla lane, perché il dispatch general richiede entrambi i valori a `"1"` (`ds4-p4a/ds4_cuda.cu:50554-50559`).
- **Meccanismo evitato:** il worker lane chiama direttamente le due entry che submittano al g132 (`ds4-p4a/ds4_cuda.cu:51014-51018`, `ds4-p4a/ds4_cuda.cu:51035-51037`; corpi submit `ds4-p4a/ds4.c:4978-4979`, `ds4-p4a/ds4.c:5145-5146`) e non prende `g_shared1_pool_mutex`. NextN prenderebbe invece quel mutex: sarebbero due lock discipline diverse sullo stesso slot.
- **Manifestazione a banco:** non deve esistere un banco combinato: `ds4_engine_open` fallisce prima di creare il drafter e stampa “mutually exclusive” (`ds4-p4a/ds4.c:22681-22690`).
- **Guardia suggerita:** mantenere il divieto; includere anche la tripla con `_GENERAL=1` nella matrice dei flag, senza tentare di affidarsi al mutex shared.

## (3) ESCLUSIONI

### E1 — nessun deadlock fra `g_shared1_pool_mutex` e `submit_mutex` dedicato nel call graph corrente

- Il ramo dedicated e il ramo g132 sono mutuamente esclusivi nello stesso eval (`ds4-p4a/ds4.c:11694-11722`). Il primo prende `submit_mutex` e poi `p->mutex` (`ds4-p4a/ds4.c:11558-11575`); il secondo prende `g_shared1_pool_mutex` e, dentro `ds4_g132_parallel_for`, `g_g132_pool.mutex` (`ds4-p4a/ds4.c:11712-11721`, `ds4-p4a/ds4.c:964-981`). Nessun sito letto prende sia `g_shared1_pool_mutex` sia `submit_mutex`; i worker dedicated prendono solo `p->mutex` (`ds4-p4a/ds4.c:11420-11452`). Non c'è quindi un arco inverso capace di chiudere un ciclo.

### E2 — shared1 e drafter non submittano più alla stessa pool sotto lock diversi nelle combinazioni ammesse

- I due submit g132 di shared1 sono dentro un'unica presa di `g_shared1_pool_mutex` (`ds4-p4a/ds4.c:11711-11721`); il submit NextN usa lo stesso mutex (`ds4-p4a/ds4.c:11300-11311`). I soli altri call-site diretti di `ds4_g132_parallel_for` sono le entry della lane (`ds4-p4a/ds4.c:4978-4979`, `ds4-p4a/ds4.c:5145-5146`), e lane+NextN è respinto a open (`ds4-p4a/ds4.c:22681-22690`), mentre shared legacy cede il g132 quando i flag lane sono presenti (`ds4-p4a/ds4.c:11957-11968`). Resta il bug semantico B2 sui valori falsi, non una corsa sullo slot.

### E3 — con sharedcore attivo, drafter e shared non incrociano alcuna coda

- `s->use_dedicated` forza `s->use_pool=false` e impedisce perfino l'init g132 da shared1 (`ds4-p4a/ds4.c:11957-11962`); l'eval dedicated usa soltanto `ds4_shared1_dedicated_parallel_for` (`ds4-p4a/ds4.c:11694-11710`). NextN instrada i job pesanti al g132 e quelli piccoli/nested inline (`ds4-p4a/ds4.c:801-813`). L'interferenza residua è di core/DRAM (I2), non di `fn/ctx/done`, condvar o queue.

### E4 — teardown normale del pool dedicato: nessun UAF del job e nessun thread dedicated orfano

- `ds4_shared1_destroy` segnala shutdown al worker dell'istanza e lo joina prima di rilasciare il ref dedicated (`ds4-p4a/ds4.c:11821-11835`). Ogni submit dedicated attende `done == n_threads` prima di restituire (`ds4-p4a/ds4.c:11565-11576`), quindi dopo la join del worker shared non resta un `ctx` dell'istanza usato dai worker del pool. Quando il refcount corretto arriva a zero, il release segnala shutdown, joina tutti i thread `started` e solo dopo azzera lo stato (`ds4-p4a/ds4.c:11533-11548`). L'eccezione è la corsa ABA B1, che corrompe la proprietà del ref ma non libera direttamente il `ctx` di un job in corso.

### E5 — distruzione grafo e ring CUDA ordinati

- `ds4_session_free` distrugge prima il drafter e poi il grafo (`ds4-p4a/ds4.c:23499-23509`); il destroy del drafter segnala e joina il suo thread prima di liberarne scratch e mutex (`ds4-p4a/ds4.c:20528-20549`). `metal_graph_free` rilascia shared1 prima dei tensor del grafo (`ds4-p4a/ds4.c:12711-12726`). Dopo la join shared, `ds4_gpu_async_read_free` sincronizza stream 0 e lo stream privato, attende gli slot pending e solo dopo distrugge eventi e host pinned memory (`ds4-p4a/ds4_cuda.cu:16543-16566`). Nel percorso di shutdown grazioso rappresentato da queste funzioni non emerge un UAF dei ring shared.

### E6 — teardown g132/lane separato dal pool dedicated

- Il pool dedicated conserva mutex/cond process-globali e spegne solo i propri thread nel refcount release (`ds4-p4a/ds4.c:11370-11379`, `ds4-p4a/ds4.c:11521-11548`). Il g132 ha invece shutdown proprio, con broadcast, join dei worker e distruzione delle primitive (`ds4-p4a/ds4.c:903-920`); la lane CUDA joina prima il proprio orchestratore e poi invoca quello shutdown (`ds4-p4a/ds4_cuda.cu:51270-51288`, `ds4-p4a/ds4_cuda.cu:51420-51431`). Non esiste teardown incrociato fra `g_shared1_dedicated` e g132.

### E7 — DOV/route worker non condivide le code CPU oggetto dell'audit

- Il route worker ha lifecycle autonomo: cancel, stop e join timeout sono gestiti nello stato `g_moe_expert_cache` (`ds4-p4a/ds4_cuda.cu:31748-31783`) e il cleanup della cache lo chiama prima di sincronizzare/distruggere l'upload stream e gli eventi DOV (`ds4-p4a/ds4_cuda.cu:37707-37735`). Non chiama le entry g132 censite in E2. La sua possibile quarantena/detach su timeout è esplicitamente un safe-leak del route cache (`ds4-p4a/ds4_cuda.cu:31763-31780`), non un thread orfano prodotto da sharedcore.
