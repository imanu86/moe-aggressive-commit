# Audit 10 — teardown e “secondo server”

Perimetro verificato: `ds4-p4a/ds4.c` SHA-256
`2F4555965716ADB494496E3D4EB6BF5FA1769D36BAB3527A37CEC63C1E7CBF20`
e `ds4-p4a/ds4_cuda.cu` SHA-256
`F0DD5CFC6E001A61E818F8569E74E9AD07D536C55108418FEF7851712224BA36`.
Solo lettura statica; nessuna build o esecuzione.

## (1) BUG

### B1 — Il teardown prosegue dopo una `cudaDeviceSynchronize` fallita

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:9056-9066`,
  `ds4-p4a/ds4_cuda.cu:9070-9163`.
- **Severità:** **ALTA**.
- **Scenario concreto:** un errore CUDA asincrono/sticky è pendente allo
  shutdown -> `cudaDeviceSynchronize()` ritorna errore -> il codice continua
  comunque a distruggere handle, liberare device memory, fare
  `cudaFreeHost`/`cudaHostUnregister` e chiudere stream, ignorando tutti gli
  esiti. La riga d'errore della sync viene emessa solo se
  `cuda_q1_0_profile_requested()` è vero; negli altri assetti il teardown
  degradato è silenzioso. Esito sbagliato: lo shutdown viene trattato come
  riuscito senza avere né la prova che il lavoro fosse drenato né la prova
  che le risorse siano state accettate dal driver per il rilascio
  (`ds4-p4a/ds4_cuda.cu:9057-9065`, `ds4-p4a/ds4_cuda.cu:9121-9145`).

Questo è il candidato codice più forte per un vecchio processo che muore con
molto lavoro di cleanup ancora demandato alla distruzione del contesto. Non
spiega da solo i cinque minuti: il sorgente non osserva lo stato WDDM dopo
l'ultima API CUDA.

### B2 — Il tracer dichiara rilasciata una risorsa prima di sapere se il driver l'ha rilasciata

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:674-693`,
  `ds4-p4a/ds4_cuda.cu:8985-9011`.
- **Severità:** **MEDIA**.
- **Scenario concreto:** `cudaFreeHost` o `cudaHostUnregister` fallisce durante
  il teardown -> `ds4_alloc_trace_release(ptr)` ha già sottratto il puntatore
  dal live-set -> il chiamante scarta il `cudaError_t` -> la telemetria dice
  “zero live” mentre la registrazione può restare di proprietà del contesto.
  Questo vale in particolare per le registrazioni mmap iterate a
  `ds4-p4a/ds4_cuda.cu:8989-8994` e per tutti i buffer host-pinned liberati
  tramite le macro a `ds4-p4a/ds4_cuda.cu:829-831`.
- **Manifestazione già possibile:** RAM/VRAM di processo apparentemente pulite
  e nessuna riga di errore, ma teardown driver non provato. Non esiste inoltre
  un balance/mark dopo `ds4_gpu_cleanup`; gli ultimi summary sono
  `decode-start` e `request-end` (`ds4-p4a/ds4_cuda.cu:31039`,
  `ds4-p4a/ds4_cuda.cu:31114`).

### B3 — Nessun reset/destroy esplicito del contesto CUDA

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:9056-9164`,
  `ds4-p4a/ds4.c:22887-22914`.
- **Severità:** **MEDIA**.
- **Scenario concreto:** shutdown sano -> il primo `cudaDeviceSynchronize`
  drena il lavoro preesistente -> vengono distrutti gli oggetti applicativi ->
  `ds4_gpu_cleanup` termina dopo la distruzione del prefetch stream, senza
  `cudaDeviceReset`, `cuDevicePrimaryCtxReset` o `cuCtxDestroy` -> il primary
  context, la sua VA e l'eventuale bookkeeping di deallocazione restano affidati
  alla terminazione del processo. Se l'orchestratore considera il server
  “spento” prima che il processo e il contesto siano completamente ritirati da
  WDDM, il nuovo processo può partire contro lo stato driver ancora in
  pensionamento pur vedendo RAM e VRAM nominalmente pulite
  (`ds4-p4a/ds4_cuda.cu:9132-9164`, `ds4-p4a/ds4.c:22899-22914`).

La ricerca completa nei due sorgenti non trova alcuna chiamata di reset/destroy
del contesto. Sul percorso sano non resta invece lavoro kernel noto: la sync è
la prima istruzione del cleanup (`ds4-p4a/ds4_cuda.cu:9056-9067`). Perciò,
dal solo codice, il mistero del secondo server non è attribuibile a una coda
MoE precisa; è attribuibile al massimo al confine di teardown del contesto non
forzato, oppure a uno dei percorsi degradati B1/B4/B5.

### B4 — Il “safe leak” del route worker salta tutto il distruttore della cache CUDA

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:31748-31805`,
  `ds4-p4a/ds4_cuda.cu:37707-37735`,
  `ds4-p4a/ds4_cuda.cu:37826-37901`.
- **Severità:** **ALTA**.
- **Scenario concreto:** transient read non cancellabile entro il join, oppure
  route upload stream non quiescente entro 5 s -> il worker viene detached o la
  cache viene quarantinata e `route_worker_safe_leaked=1`
  (`ds4-p4a/ds4_cuda.cu:31763-31780`, `ds4-p4a/ds4_cuda.cu:31724-31745`) ->
  allo shutdown `cuda_moe_expert_cache_release` ritorna subito -> non sincronizza
  né distrugge route stream/eventi DOV, non libera slab/transient device e non
  libera mailbox/staging host-pinned. Esito: tutto rimane vivo fino alla morte
  del contesto, esattamente la classe di residuo che può scaricare lavoro di
  teardown sul WDDM dopo l'uscita del server
  (`ds4-p4a/ds4_cuda.cu:37709-37723`,
  `ds4-p4a/ds4_cuda.cu:37845-37875`).
- **Prova da log:** `writer slot/cache safe-leaked permanently`, `persistent
  I/O slot/cache safe-leaked permanently`, oppure `route upload stream
  quarantine ... cache=safe-leaked` sono discriminatori diretti
  (`ds4-p4a/ds4_cuda.cu:31776-31796`,
  `ds4-p4a/ds4_cuda.cu:31739-31744`). Se nessuna compare nel run precedente,
  B4 è escluso per quel run.

### B5 — Il rotator Q1 detached promette di conservare il ring, ma il chiamante può liberare l'arena

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:36247-36292`,
  `ds4-p4a/ds4_cuda.cu:9578-9591`.
- **Severità:** **ALTA**.
- **Scenario concreto:** il worker `q1-0-ssd-wrap` non termina entro il join
  bounded di 50 ms mentre una lettura cancellata può ancora ritornare -> viene
  detached e il commento richiede che “file handle, events, and ring remain
  valid” (`ds4-p4a/ds4_cuda.cu:36268-36284`) -> questo ramo non imposta
  `g_cuda_dynamic_arena_storage_safe_leaked` -> il chiamante ritorna in
  `cuda_dynamic_arena_storage_release`, vede il latch ancora falso e può
  eseguire `cudaFreeHost(g_dynamic_arena.host_base)`, che contiene i ring.
  Esito sbagliato: I/O/thread detached può completare su storage già liberato;
  allo shutdown può diventare corruzione o teardown driver anomalo
  (`ds4-p4a/ds4_cuda.cu:9580-9589`).
- **Portata:** condizionale al rotator Q1; non è armato dalla sola configurazione
  di campagna elencata. Il ramo `commit_safe_leaked`, invece, imposta
  correttamente il latch globale e impedisce la free
  (`ds4-p4a/ds4_cuda.cu:35595-35612`,
  `ds4-p4a/ds4_cuda.cu:9690-9692`).

### B6 — Il batch ledger DOV pendente non viene ritirato nel teardown/rebuild

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:37483-37500`,
  `ds4-p4a/ds4_cuda.cu:37540-37553`,
  `ds4-p4a/ds4_cuda.cu:37725-37735`.
- **Severità:** **MEDIA**.
- **Scenario concreto:** l'ultima generazione DOV ha consegnato un batch a
  `transport_deferred`, ma il worker non ha ancora eseguito poll/retire -> un
  teardown o uno shed PIN2 sincronizza con successo `route_upload_stream` ->
  distrugge gli eventi e azzera `armed_generation`, ma non chiama
  `ds4_transport_h2d_batch_finish_deferred` e non azzera
  `transport_deferred`. Esito: il batch resta `active`; al successivo defer
  dopo un rebuild viene chiuso come pendente stantio con `drain_ok=0`, bench
  segnato `ledger_complete=0` e byte H2D omessi benché la sync precedente ne
  avesse provato il completamento (`ds4-p4a/ds4_cuda.cu:28565-28588`).
- **Impatto sul mistero:** è stato pendente non agganciato allo shutdown, ma è
  solo stato CPU/contabilità; non trattiene da solo alcun oggetto CUDA/WDDM.
  Il report request-final può già sottocontare un batch di coda per disegno
  (`ds4-p4a/ds4_cuda.cu:28500-28503`,
  `ds4-p4a/ds4_cuda.cu:31129`).

### B7 — `VirtualLock` NextN e aumento del working set non hanno un rilascio simmetrico

- **File:riga verificata:** `ds4-p4a/ds4.c:22333-22355`,
  `ds4-p4a/ds4.c:22418-22443`,
  `ds4-p4a/ds4.c:22887-22914`.
- **Severità:** **BASSA**.
- **Scenario concreto:** `DS4_NEXTN_PIN=2` blocca fino al working set modulo +
  esperti + testa e aumenta min/max working set -> `ds4_engine_close` non
  esegue `VirtualUnlock`/`munlock` né ripristina il working set -> i lock
  restano fino allo smontaggio delle mmap o alla morte del processo. In un
  teardown rallentato prima di `model_close`, o in un uso con più aperture
  nello stesso processo, diversi GiB restano non sfrattabili più a lungo del
  necessario (`ds4-p4a/ds4.c:22340-22355`,
  `ds4-p4a/ds4.c:22907-22910`).
- **Impatto sul secondo processo:** non è un oggetto CUDA e Windows lo revoca
  con l'unmap/uscita; non spiega da solo WDDM sporco dopo che il vecchio PID è
  realmente morto.

### Diagnosi economica a fine processo

La prova A/B più economica suggerita dal codice è un
**reset esplicito del device come ultimissima operazione del clean shutdown**,
dopo: distruzione di sessioni/worker, `cudaDeviceSynchronize`, rilascio di tutte
le risorse e prima di dichiarare il processo spento. Oggi l'ultima operazione
CUDA può essere `cudaStreamDestroy(g_model_prefetch_stream)` e poi la funzione
ritorna (`ds4-p4a/ds4_cuda.cu:9160-9164`). Un `cudaDeviceReset` lì renderebbe
sincrono e osservabile il confine che oggi è demandato all'uscita del processo;
se elimina la quiete di 300 s, la causa è context/WDDM teardown, non cache MoE.
È diagnosi, non patch.

Guardia indispensabile: eseguire il reset solo sul percorso **clean**, dopo che
tutti i thread sono joinati. Non usarlo nei rami B4/B5 con thread detached, che
possono ancora accedere al contesto/storage
(`ds4-p4a/ds4_cuda.cu:31763-31780`,
`ds4-p4a/ds4_cuda.cu:36268-36284`). Sul clean path conviene anche rendere
visibili gli esiti di ogni free/unregister e fare un balance finale: oggi gli
esiti sono scartati (`ds4-p4a/ds4_cuda.cu:9070-9163`).

## (2) INTERFERENZE FRA LEVE

### I1 — `DS4_CUDA_DRAIN_OVERLAP4` + ledgerfix + `DS4_CUDA_PIN_BACKBONE`

- **Meccanismo:** PIN2 può cedere lo slab chiamando
  `cuda_moe_expert_cache_release` dopo una sync di stream 0
  (`ds4-p4a/ds4_cuda.cu:37385-37414`). Se una generazione DOV ha ancora il
  ledger differito, la release sincronizza l'upload ma distrugge lo stato DOV
  senza ritirare il batch (`ds4-p4a/ds4_cuda.cu:37725-37735`,
  `ds4-p4a/ds4_cuda.cu:37540-37553`).
- **A banco:** `ledger_complete=0`, `h2d_bytes_total` sotto il controllo,
  `h2d_active_ms` esteso fino alla generazione successiva; nello stesso tratto
  compaiono `PIN degrade result=ok` / `PIN rebuild result=ok`
  (`ds4-p4a/ds4_cuda.cu:37331-37441`,
  `ds4-p4a/ds4_cuda.cu:39690-39702`,
  `ds4-p4a/ds4_cuda.cu:28576-28582`).
- **Guardia/combinazione:** non usare i numeri del ledger come criterio di
  confronto nei run che fanno shed/rebuild con DOV; oppure vietare
  `PIN_BACKBONE+DOV+TRANSPORT_LEDGER` finché lo shutdown/rebuild non ha un
  retire del pendente dopo la sync. Correttezza dei byte GPU non coinvolta.

### I2 — `DS4_CUDA_DRAIN_OVERLAP4` + `TRANSIENT_TIMEOUT_RECOVERABLE` + invalidazione/cancel

- **Meccanismo:** DOV può lasciare un upload outstanding di una generazione;
  un timeout transiente porta al cancel/join. Con `KV_STAGED_RING=1`, il
  quiesce prova per 5 s il route stream; su timeout l'intera cache diventa
  safe-leaked (`ds4-p4a/ds4_cuda.cu:31717-31745`,
  `ds4-p4a/ds4_cuda.cu:31748-31805`). `SCOPED_INVALIDATE` può aumentare la
  frequenza del percorso di recovery, ma non cambia il fail-safe.
- **A banco:** una delle tre righe B4, seguita da assenza del summary
  `[gpu-resident-routes] final` perché la release ritorna prima
  (`ds4-p4a/ds4_cuda.cu:37707-37724`, summary a
  `ds4-p4a/ds4_cuda.cu:37751-37824`); al riavvio immediato, sfratti anomali
  pur con VRAM nominalmente libera sono compatibili con teardown del contesto
  precedente ancora pesante.
- **Guardia/combinazione:** un run con `safe-leaked` va marcato **poisoned** e
  non confrontato; attendere la morte effettiva del PID prima del rilancio.
  Non chiamare reset in-process dopo detach. Per la campagna pulita,
  `DOV+SCOPED` è ammesso solo con zero righe safe-leak.

### I3 — `DS4_NEXTN_PIN=2` + `DS4_CUDA_INDEXER_HOST_ZEROCOPY=1` + `KV_STAGED_RING=1`

- **Meccanismo:** NextN usa `VirtualLock` fuori da qualunque budget CUDA
  (`ds4-p4a/ds4.c:22333-22443`); INDEXERZC aggiunge buffer
  `cudaHostAllocMapped` e li carica nello stesso contatore del budget
  register-mmap (`ds4-p4a/ds4_cuda.cu:4017-4052`); KV staged può aggiungere
  un'arena `cudaHostAlloc` grande quanto il registro KV
  (`ds4-p4a/ds4_cuda.cu:21854-21885`). Quindi il budget masked da 2 GiB non
  limita il totale realmente non pageable: i lock NextN e l'arena KV gli
  sono esterni.
- **A banco:** `pin mode=2 locked=...`, `[indexer-zc] active ... alloc=...`,
  più eventuale `staged KV pinned arena alloc` fallita; sintomi indiretti:
  aumento di transient timeout/read latency e maggiore volume di
  `cudaFreeHost` al teardown (`ds4-p4a/ds4.c:22444-22449`,
  `ds4-p4a/ds4_cuda.cu:3992-4004`,
  `ds4-p4a/ds4_cuda.cu:21873-21880`).
- **Guardia/combinazione:** nel braccio ctx 150k vietare la tripla finché non
  si contabilizzano insieme `VirtualLock + cudaHostAlloc + cudaHostRegister`;
  per isolare il mistero del secondo server usare `NEXTN_PIN=0/1` oppure
  INDEXERZC off, mantenendo invariato il resto. Questa interferenza può
  aggravare il costo di teardown WDDM, non crea una perdita sul clean path.

### I4 — `DS4_CPU_SHARED_EXPERT`/sharedcore + NextN drafter + ordine engine/session

- **Meccanismo:** la sessione possiede drafter e grafo: `session_free` ferma
  prima la chain, poi distrugge shared worker/pool dedicato e tensor graph
  (`ds4-p4a/ds4.c:23499-23514`,
  `ds4-p4a/ds4.c:20528-20549`,
  `ds4-p4a/ds4.c:12711-12844`). L'engine, separatamente, spegne g132 e il pool
  generale prima del cleanup CUDA (`ds4-p4a/ds4.c:22887-22899`). Se
  l'orchestratore chiama `engine_close` con una sessione ancora viva, il
  drafter/shared può essere dentro una submit mentre il pool viene spento, o
  può usare ring/tensori dopo il cleanup globale.
- **A banco:** hang nel join di shutdown, summary `[nextn-cpu]` o
  `[shared-cpu] final` mancante, oppure CUDA error durante le free tardive.
  Il pool shared dedicato, sul percorso corretto, rilascia l'ultimo ref solo
  dopo il join del proprio worker (`ds4-p4a/ds4.c:11821-11848`,
  `ds4-p4a/ds4.c:11518-11548`).
- **Guardia/combinazione:** vietare `engine_close` con sessioni vive/assertare
  ordine `session_free -> engine_close`. Non serve vietare sharedcore+NextN
  se tale ordine è rispettato.

### I5 — `DS4_CUDA_INDEXER_HOST_ZEROCOPY` + shutdown con sync fallita

- **Meccanismo:** sul clean path INDEXERZC è rilasciato correttamente da
  `cuda_model_range_release_all` (`ds4-p4a/ds4_cuda.cu:3953-3965`,
  `ds4-p4a/ds4_cuda.cu:8985-8989`). Se però la sync iniziale fallisce, vengono
  eseguite fino a 42 `cudaFreeHost` ignorandone l'esito e il registro viene
  comunque svuotato.
- **A banco:** `[indexer-zc] active=1` nel run, nessuna prova di release al
  final, alloc tracer a zero per B2; il secondo server può pagare il retirement
  delle registrazioni del primo.
- **Guardia/combinazione:** INDEXERZC ammesso solo se la cleanup sync è
  `cudaSuccess`; in un braccio diagnostico loggare/validare ogni
  `cudaFreeHost`. Non è necessario vietarlo con routefix o sharedcore.

## (3) ESCLUSIONI

- **Ordine generale sano, se la sync riesce:** `ds4_gpu_cleanup` esegue
  `cudaDeviceSynchronize` prima di qualunque distruttore CUDA
  (`ds4-p4a/ds4_cuda.cu:9056-9069`). Questo esclude upload/kernel ordinari
  ancora in coda come spiegazione del secondo server sul percorso clean.

- **Route stream e DOV:** il worker viene cancellato/joinato, poi l'upload
  stream viene sincronizzato; dopo vengono distrutti consumer event e i due
  eventi DOV, quindi device/host buffers e infine lo stream
  (`ds4-p4a/ds4_cuda.cu:37711-37735`,
  `ds4-p4a/ds4_cuda.cu:37826-37875`). L'ordine è sano salvo il ramo
  `route_worker_safe_leaked` di B4.

- **Tutti gli stream globali trovano un distruttore:** model prefetch
  create/release (`ds4-p4a/ds4_cuda.cu:6140`,
  `ds4-p4a/ds4_cuda.cu:9160-9163`); model upload
  (`ds4-p4a/ds4_cuda.cu:6514`,
  `ds4-p4a/ds4_cuda.cu:9136-9139`); async read ring
  (`ds4-p4a/ds4_cuda.cu:16519-16530`,
  `ds4-p4a/ds4_cuda.cu:16543-16566`); SPEX prefetch
  (`ds4-p4a/ds4_cuda.cu:16893-16899`,
  `ds4-p4a/ds4_cuda.cu:17028`); KV staged
  (`ds4-p4a/ds4_cuda.cu:21697-21731`,
  `ds4-p4a/ds4_cuda.cu:9166-9184`); route
  (`ds4-p4a/ds4_cuda.cu:39383-39387`,
  `ds4-p4a/ds4_cuda.cu:37725-37735`,
  `ds4-p4a/ds4_cuda.cu:37874-37875`); lane G132
  (`ds4-p4a/ds4_cuda.cu:51180-51201`,
  `ds4-p4a/ds4_cuda.cu:51270-51410`).

- **Eventi e buffer del pool di riciclo:** gli eventi per buffer differiti
  sono distrutti e i device buffer liberati in
  `cuda_model_range_release_all`; arene e registrazioni mmap vengono poi
  svuotate (`ds4-p4a/ds4_cuda.cu:8989-9011`). La sync globale precedente
  rende sano questo ordine nel cleanup finale.

- **Host-mapped indexer nuovo:** è agganciato sia al cleanup sia al cambio
  model map tramite `cuda_model_range_release_all`; ogni entry fa
  `cudaFreeHost` e azzera latch/contatori
  (`ds4-p4a/ds4_cuda.cu:3953-3965`,
  `ds4-p4a/ds4_cuda.cu:8985-8988`,
  `ds4-p4a/ds4_cuda.cu:17196-17205`). Nessuna entry indexer normale resta
  deliberatamente al driver.

- **KV staged:** il cleanup libera host arena, azzera i `host_ptr` dei tensor,
  distrugge eventi/stream e libera gli slot device
  (`ds4-p4a/ds4_cuda.cu:9067-9069`,
  `ds4-p4a/ds4_cuda.cu:9166-9200`). Nessun buco specifico trovato.

- **Dynamic arena normale:** observer, prefill/reap state e rotator vengono
  rilasciati prima di `cudaFreeHost` dell'arena; l'upload stream viene
  sincronizzato prima della free (`ds4-p4a/ds4_cuda.cu:9689-9722`,
  `ds4-p4a/ds4_cuda.cu:9578-9617`). Restano soltanto i safe-leak espliciti e
  B5.

- **shared1/sharedcore nuovo:** il worker shared è joinato, poi cala il
  refcount del pool dedicato; l'ultimo ref spegne e joina tutti i worker, poi
  sono liberati i due ring CUDA e i buffer CPU
  (`ds4-p4a/ds4.c:11821-11848`,
  `ds4-p4a/ds4.c:11518-11548`). Il nuovo pool è dunque agganciato allo
  shutdown grazioso della sessione.

- **NextN chain:** il drafter imposta `shutdown`, sveglia e joina il thread
  prima di liberare stato CPU e buffer (`ds4-p4a/ds4.c:20528-20549`);
  `session_free` lo esegue prima di `metal_graph_free`
  (`ds4-p4a/ds4.c:23499-23509`). La chain è agganciata; solo i lock delle
  pagine di B7 non hanno rilascio simmetrico.

- **Pool CPU ordinari:** g132 e pool generale impostano shutdown, broadcast,
  joinano i worker e distruggono le primitive
  (`ds4-p4a/ds4.c:903-920`,
  `ds4-p4a/ds4.c:777-794`). Nel percorso corretto non sopravvivono al cleanup
  CUDA.

- **routefix, scoped invalidate, logids ed econ:** routefix aggiunge solo
  letture/scritture di generazione nel worker; il ramo resync non crea
  stream/eventi/host allocations (`ds4-p4a/ds4_cuda.cu:42562-42604`).
  SCOPED/logids non aggiungono ownership CUDA nel teardown; lane econ viene
  revocata prima del join (`ds4-p4a/ds4_cuda.cu:51272-51288`). Nessun residuo
  specifico trovato.

- **RAM/VRAM tornate a 585 MiB:** è coerente con il percorso normale appena
  tracciato e rende improbabile una grossa arena/slab dimenticata. Non esclude
  B2/B3: il codice non misura primary-context retirement, VA teardown o
  registrazioni il cui rilascio è fallito dopo essere state tolte dal tracer
  (`ds4-p4a/ds4_cuda.cu:686-693`,
  `ds4-p4a/ds4_cuda.cu:9136-9164`).

- **Limite della prova:** dai due sorgenti non è possibile dimostrare quale
  coda WDDM resti viva per circa 300 s. È invece dimostrato che sul clean path
  non c'è una coda applicativa non drenata nota, che non viene mai forzata la
  distruzione del contesto, e che i percorsi safe-leak demandano esplicitamente
  il rilascio alla morte del processo (`ds4-p4a/ds4_cuda.cu:9056-9164`,
  `ds4-p4a/ds4_cuda.cu:31763-31780`).
