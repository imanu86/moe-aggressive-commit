# 1. BUG

Verdetto statico: con i quattro env nuovi assenti
(`DS4_CUDA_ROUTE_SNAPSHOT_RESYNC`,
`DS4_CUDA_INDEXER_HOST_ZEROCOPY`,
`DS4_CPU_SHARED_EXPERT_DEDICATED`,
`DS4_CPU_SHARED_EXPERT_AFFINITY`) e con
`DS4_NEXTN_CPU_DRAFTER=0`, non ho trovato un ramo che cambi i byte
matematici del forward sano. La neutralita' stretta, pero', **non e'
zero-work/zero-log**: INDEXERZC aggiunge un test nel percorso di risoluzione
pesi; ROUTEFIX aggiunge un log anche a flag spento sul mismatch compose;
LEDGERFIX non ha un flag proprio. Quindi lo SHA testo atteso
`c7525d909341a57a` resta l'esito staticamente atteso del controllo sano, ma
l'identita' dei contatori di ammissione non e' dimostrabile dal solo
sorgente in presenza di deadline/contesa.

1. **INDEXERZC supera il budget host-pin dichiarato — severita' MEDIA.**
   `ds4-p4a/ds4_cuda.cu:17283-17295` registra la finestra contigua iniziale
   fino all'intero `cuda_host_register_budget_bytes()`, ma non incrementa
   `g_model_registered_range_bytes`. Il controllo INDEXERZC usa invece solo
   `g_model_registered_range_bytes + alloc_bytes` a
   `ds4-p4a/ds4_cuda.cu:4017-4022` e lo incrementa dopo l'allocazione a
   `ds4-p4a/ds4_cuda.cu:4048-4052`. Scenario concreto di campagna:
   `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB=2`, finestra iniziale registrata da
   2 GiB, poi `INDEXER_HOST_ZEROCOPY=1` e primo accesso ai 42 tensori
   indexer -> altri circa 346,5 MiB possono essere pinnati pur avendo gia'
   consumato il tetto nominale -> pressione WDDM oltre budget, possibile
   `cudaHostAlloc` fallito/fail-open parziale e profilo di residenza diverso
   da quello dichiarato. Il contatore non rappresenta quindi il consumo
   cumulativo fisico che il commento promette.

2. **Il fail-open INDEXERZC non copre l'allocazione del registro C++ —
   severita' MEDIA.** Dopo `cudaHostAlloc`, lettura e mapping riusciti,
   `g_indexer_zc_entries.push_back(...)` non e' dentro `try/catch`
   (`ds4-p4a/ds4_cuda.cu:4025-4049`). Scenario: heap host frammentato o
   esaurito durante la crescita del vector -> `push_back` genera
   `std::bad_alloc`/terminazione invece di passare da
   `cuda_indexer_zerocopy_failopen` (`ds4-p4a/ds4_cuda.cu:3967-3975`) ->
   processo terminato e buffer pinnato non rilasciato, non il fallback
   fd-cache promesso.

3. **DSPARK2FIX3 non possiede un flag proprio: con NextN acceso la
   telemetria e' sempre attiva — severita' MEDIA.**
   `DS4_NEXTN_CPU_DRAFTER` e' letto a engine-open
   (`ds4-p4a/ds4.c:22653-22663`) e crea il drafter
   (`ds4-p4a/ds4.c:23485-23490`). Una volta creato, FIX3 passa sempre un
   `ds4_mtp_cpu_telemetry *` non nullo
   (`ds4-p4a/ds4.c:10101-10108`); cio' abilita letture d'orologio aggiuntive
   attorno ai matvec routed (`ds4-p4a/ds4.c:7113-7144`) e aggiorna tre
   accumulatori sotto mutex (`ds4-p4a/ds4.c:10146-10156`). Scenario:
   `NEXTN_CPU_DRAFTER=1` ma operatore convinto di avere “FIX3 spento” ->
   ogni draft step paga la strumentazione; il take fotografa `pub_steps` e
   deriva da quel valore quanti draft sono disponibili
   (`ds4-p4a/ds4.c:20583-20591`, `ds4-p4a/ds4.c:20615-20626`). Un
   completamento che cade vicino al take non bloccante puo' quindi passare
   da disponibile a pending (o viceversa) -> `k_delivered/k_accepted/pending`
   diversi nel summary, pur con stessa matematica del modello. L'unico modo
   di spegnere FIX3 e' spegnere tutto NextN.

4. **ROUTEFIX non e' log-neutrale a flag spento — severita' MEDIA.**
   Il mismatch compose entra a `ds4-p4a/ds4_cuda.cu:42558-42561`; con env
   resync assente il helper restituisce zero
   (`ds4-p4a/ds4_cuda.cu:31913-31919`), ma il codice stampa comunque
   `result=invalid-compose-snapshot ... resync=off`
   (`ds4-p4a/ds4_cuda.cu:42606-42620`) prima di riprodurre
   `failures++/request_valid=0` (`ds4-p4a/ds4_cuda.cu:42621-42623`).
   Scenario: stesso stato `arena_generation != tiering_generation`, flag
   assente -> prima della patch nessuna riga in quel ramo, dopo la patch una
   `fprintf` dal route worker -> log non byte-identico e worker ritardato
   proprio sul percorso di errore. I byte di inferenza non cambiano per
   questa sola aggiunta, ma la neutralita' osservabile dichiarata e' falsa.

5. **INDEXERZC a OFF non e' zero-work nel percorso caldo — severita'
   BASSA.** Ogni `cuda_model_range_ptr` che non ha gia' risolto
   override/window/range esistente raggiunge il test nuovo
   (`ds4-p4a/ds4_cuda.cu:4071-4118`). Il `getenv` e' memoizzato e gira una
   sola volta (`ds4-p4a/ds4_cuda.cu:3944-3950`), ma la chiamata al helper e
   il branch restano a ogni fallthrough prima della fd-cache
   (`ds4-p4a/ds4_cuda.cu:4118-4127`). Inoltre cleanup/reload chiama sempre
   il release del vector vuoto e azzera quattro globali
   (`ds4-p4a/ds4_cuda.cu:3956-3965`,
   `ds4-p4a/ds4_cuda.cu:8985-9010`). Scenario: flag assente, ctx oltre la
   soglia indexer e molte risoluzioni fd-cache -> stessi puntatori finali,
   ma istruzioni e primo lookup ambiente aggiuntivi; su un confine
   orchestration/deadline non si puo' promettere contatori temporali cifra
   per cifra. Non risultano allocazioni heap o log a OFF.

6. **LEDGERFIX e' sempre compilata e allunga il clear anche con DOV
   spento, se il transport ledger e' acceso — severita' BASSA.**
   `ds4_transport_clear` esce subito solo se il ledger e' spento
   (`ds4-p4a/ds4_cuda.cu:28591-28594`); col ledger acceso incrementa la nuova
   epoca sotto lo spinlock (`ds4-p4a/ds4_cuda.cu:28608-28611`). Il clear
   gira al request-begin (`ds4-p4a/ds4_cuda.cu:16224-16227`) e al
   decode-begin (`ds4-p4a/ds4_cuda.cu:31091-31095`) anche se DOV e' OFF.
   Scenario: `TRANSPORT_LEDGER=1`, `DRAIN_OVERLAP4=0` -> due sezioni
   critiche per richiesta hanno una scrittura in piu'; nessuno slot
   pendente viene usato, ma la risposta alla domanda “puo' spostare timing
   anche con DOV spento?” e' **si', solo a questi confini freddi**. Non ho
   trovato un effetto logico sui contatori di ammissione, soltanto una
   violazione della neutralita' temporale assoluta.

7. **Quattro struct usate fra thread cambiano layout — severita' BASSA come
   rischio d'identita', non ABI esterna.**

   - LEDGERFIX aggiunge `epoch` a `ds4_transport_ledger_state`
     (`ds4-p4a/ds4_cuda.cu:28220-28240`) e inserisce
     `transport_deferred`/`transport_deferred_epoch` prima dei tre atomici
     di `cuda_moe_drain_overlap4_state`
     (`ds4-p4a/ds4_cuda.cu:37471-37499`). Nel secondo caso cambiano quindi
     anche offset/cache-line degli atomici letti da worker e decode.
   - SHAREDCORE aggiunge due bool in coda a `ds4_shared1`
     (`ds4-p4a/ds4.c:11630-11635`), oggetto allocato con
     `sizeof(*s)` (`ds4-p4a/ds4.c:11851-11858`) e condiviso col worker.
   - DSPARK2FIX3 inserisce tre `double` prima dell'handle thread e di tutto
     lo stato worker/decode successivo (`ds4-p4a/ds4.c:9931-9957`);
     l'oggetto e' allocato con `sizeof(*d)`
     (`ds4-p4a/ds4.c:20480-20483`).

   Scenario concreto: parent lever attiva (DOV/shared1/NextN) -> stessa
   sorgente logica ma oggetto piu' grande e/o campi condivisi a offset
   diversi -> heap/BSS e false-sharing diversi, quindi timing e ammissioni
   asincrone non sono garantibili cifra per cifra. Tutti gli accessi sono
   ricompilati nello stesso binario, quindi non ho trovato corruzione da ABI;
   il problema e' il requisito molto piu' forte di identita' al byte. ROUTEFIX
   non modifica struct; INDEXERZC introduce una struct/vector file-local
   nuovo (`ds4-p4a/ds4_cuda.cu:3928-3939`) ma non allarga struct esistenti.

8. **Il resync ROUTEFIX non ha una fotografia sincronizzata dell'arena —
   severita' MEDIA, solo flag ON.** Il worker fotografa le generazioni e poi
   legge `txn/hits_disabled/submissions_blocked` come campi plain prima
   dello store nel tiering (`ds4-p4a/ds4_cuda.cu:42570-42593`). Un'altra
   transazione scrive quegli stessi campi plain al begin
   (`ds4-p4a/ds4_cuda.cu:10890-10893`) e pubblica generazione/flag/txn in
   piu' store distinti (`ds4-p4a/ds4_cuda.cu:11229-11244`). Scenario:
   compose in modalita' non esclusiva, worker vede `txn==NULL`, poi una
   transazione parte o pubblica fra guardia e store -> il tiering puo'
   adottare una generazione gia' superata -> richiesta successiva
   `snapshot-generation-mismatch`/fail-closed. I check per-entry impediscono
   byte non pubblicati, ma non il fallimento spurio. Guardia operativa:
   autorizzare il resync solo nel regime ENFORCE che rende
   `tiering_exclusive=1` (`ds4-p4a/ds4_cuda.cu:33588-33590`) e con il log di
   publish coerente; vietarlo in TRACK/arena mutabile.

**Ordine di rischio per rompere l'identita' del controllo a flag spenti**
(env nuovi assenti, DOV/shared1/NextN anch'essi OFF):

1. **INDEXERZC** — branch nel resolver pesi realmente raggiungibile a OFF,
   `getenv` lazy e teardown sempre chiamato.
2. **LEDGERFIX** — nessun kill-switch proprio; scrittura di epoca se il
   ledger e' acceso e layout del sidecar DOV cambiato.
3. **ROUTEFIX** — nessun lavoro nel run sano senza mismatch, ma funzione
   worker ingrandita e log sempre-attivo sul mismatch.
4. **SHAREDCORE** — con shared1 OFF il return precede tutti i nuovi getenv;
   resta testo/BSS nuovo.
5. **DSPARK2FIX3** — con NextN OFF il drafter non e' allocato e nessun
   call-site nuovo gira.

Se il “controllo” tiene ON le leve madri, l'ordine cambia: con DOV+ledger ON
LEDGERFIX sale al primo posto; con NextN ON DSPARK2FIX3 sale subito dietro
perche' non e' disattivabile separatamente.

# 2. INTERFERENZE FRA LEVE

1. **`DS4_CUDA_DRAIN_OVERLAP4=1` +
   `DS4_CUDA_TRANSPORT_LEDGER=1` + LEDGERFIX sempre attiva.** Il batch viene
   consegnato allo slot globale al posto del finish classico
   (`ds4-p4a/ds4_cuda.cu:42325-42351` e
   `ds4-p4a/ds4_cuda.cu:43117-43132`) e committato al retire
   (`ds4-p4a/ds4_cuda.cu:37566-37585`). Manifestazione a banco:
   `h2d_bytes_total`, `first_touch/repeat_h2d`, `ledger_complete` e
   `h2d_active_ms/pcie_busy_pct` **devono** differire dal binario pre-fix;
   l'intervallo viene chiuso all'osservazione del retire, non all'arm.
   Guardia: non usare i contatori transport pre/post patch come test di
   neutralita'; per l'identita' dei contatori di ammissione tenere DOV OFF,
   oppure accettare esplicitamente che solo i contatori transport cambino.

2. **ROUTEFIX (anche resync OFF) + DOV + LEDGERFIX.** La `fprintf` del
   mismatch gira sul route worker (`ds4-p4a/ds4_cuda.cu:42606-42623`);
   LEDGERFIX prende il timestamp e il lock solo quando lo stesso worker
   osserva/ritira l'overlap (`ds4-p4a/ds4_cuda.cu:28505-28522`,
   `ds4-p4a/ds4_cuda.cu:37566-37580`). Manifestazione: run fallito con byte
   H2D uguali ma `h2d_active_ms`/`pcie_busy_pct` gonfiati dal ritardo di
   osservazione; compare `invalid-compose-snapshot`. Guardia: escludere ogni
   run con quel log dai confronti temporali del ledger; non vietare la
   combinazione per correttezza dei byte.

3. **ROUTEFIX ON + NextN/dspark2fix3 + compose tiering.** Il resync trasforma
   il veto compose in adozione e log `resync-compose-snapshot`
   (`ds4-p4a/ds4_cuda.cu:42558-42605`), mentre NextN decide offerte e
   accettazioni in modo asincrono (`ds4-p4a/ds4.c:24025-24030`). Non e'
   provato dal tree che NextN generi il mismatch; l'interferenza certa e'
   diagnostica: accendere resync cambia proprio il guasto che il braccio
   NextN dovrebbe attribuire. Manifestazione: sparisce
   `request-invalid`, cambiano route failures e
   `k_delivered/k_accepted/pending`. Guardia: vietare ROUTEFIX ON nei run di
   attribuzione NextN; abilitarlo solo dopo avere osservato
   `invalid-compose-snapshot` con arena quiescente e una
   `[arena] publish generation=` coerente.

4. **INDEXERZC ON + transport ledger/LEDGERFIX.** INDEXERZC ritorna il
   puntatore UVA prima della fd-cache/H2D
   (`ds4-p4a/ds4_cuda.cu:4118-4123`); il ledger dichiara esplicitamente che
   host-mapped GPU reads non sono attribuibili e non vengono inferite
   (`ds4-p4a/ds4_cuda.cu:28195-28201`). Manifestazione: il PCIe reale puo'
   crescere di tutti i byte densi indexer per token mentre
   `h2d_bytes_total` e `pcie_busy_pct` del ledger restano bassi; spariscono
   i `fd-cache load` indexer. Guardia: vietare l'uso del transport ledger
   come misura di banda totale in questo braccio; usare contatori PCIe
   esterni e trattare il ledger come solo expert-H2D.

5. **INDEXERZC ON + `DS4_CUDA_PIN_BACKBONE=1`.** INDEXERZC intercetta
   `indexer_f16` prima di `cuda_model_range_ptr_from_fd`
   (`ds4-p4a/ds4_cuda.cu:4113-4127`); PIN2 si attiva solo quando
   `cuda_model_stream_alloc` seleziona una vittima backbone
   (`ds4-p4a/ds4_cuda.cu:8701-8724`). Togliendo l'allocazione VRAM
   dell'indexer si toglie anche la pressione che avrebbe provocato
   `PIN blocked_backbone` e lo shed. Manifestazione:
   `pin_backbone_blocked/pin_expert_cache_sheds/pin_rebuild_slots` piatti,
   cache esperti non dimezzata; il guadagno non e' la somma dei due bracci.
   Guardia: misurare INDEXERZC e PIN2 separatamente prima della combinazione;
   vietare la combinazione come braccio di attribuzione, non come
   configurazione funzionale.

6. **INDEXERZC ON + budget di campagna
   `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB=2`.** La finestra iniziale
   puo' consumare tutto il budget senza caricare
   `g_model_registered_range_bytes`
   (`ds4-p4a/ds4_cuda.cu:17281-17296`), poi INDEXERZC usa quel contatore
   incompleto (`ds4-p4a/ds4_cuda.cu:4017-4052`). Manifestazione:
   `pinned_bytes` annunciati anche oltre il cap nominale, oppure
   `pin_failed ... action=fail-open` in un punto dipendente dalla pressione
   WDDM; residenza mista zero-copy/fd-cache. Guardia: combinazione da
   **vietare per il banco di neutralita'** finche' il cap non e' verificato
   sul consumo totale; non interpretare un fail-open parziale come braccio
   INDEXERZC pienamente ON.

7. **SHAREDCORE affinity + NextN CPU drafter.** I thread shared dedicati
   vengono fissati sui logical CPU alti
   (`ds4-p4a/ds4.c:11490-11504`), ma il codice lascia esplicitamente il pool
   g132 intatto (`ds4-p4a/ds4.c:11957-11962`). NextN continua a inviare i
   job pesanti proprio a g132 (`ds4-p4a/ds4.c:801-812`), i cui thread non
   ricevono una maschera complementare: l'affinita' shared non “riserva” i
   core allo scheduler. Manifestazione: `shared_cpu_ms` puo' migliorare
   mentre `fwd_q4_avg/fwd_dense_avg/head_avg` peggiorano e
   `k_delivered/pending` cambiano; possibile ritorno di contesa sul route
   worker. Guardia: vietare la combinazione nel test che vuole isolare
   l'effetto affinity; per il test combinato trattare i core come condivisi,
   non riservati.

8. **SHAREDCORE OFF (`DEDICATED=0`) + shared1 + NextN.** Non e' una nuova
   race: entrambi serializzano sullo stesso `g_shared1_pool_mutex`
   (`ds4-p4a/ds4.c:11295-11310`,
   `ds4-p4a/ds4.c:11711-11721`). E' pero' un'interferenza prestazionale:
   il drafter puo' aspettare i due matvec shared e viceversa.
   Manifestazione: code in `step_ms`, `shared_cpu_ms` e minor numero di
   draft pronti, senza fallback shared. Guardia: non attribuire tali code a
   DSPARK2FIX3 (che misura soltanto); usare `DEDICATED=N` per separare i
   pool, oppure vietare shared1+NextN nei bracci di baseline.

# 3. ESCLUSIONI

1. **Lettura env delle cinque patch.**

   - ROUTEFIX: `getenv` memoizzato in static int
     (`ds4-p4a/ds4_cuda.cu:31913-31919`); il helper e' chiamato solo dentro
     il raro mismatch (`ds4-p4a/ds4_cuda.cu:42558-42575`). Nessun getenv
     ripetuto per richiesta sana; il primo getenv avviene comunque sul
     thread worker/failure path.
   - INDEXERZC: `getenv` memoizzato
     (`ds4-p4a/ds4_cuda.cu:3944-3950`); nessun getenv ripetuto, ma il test
     del cached int e' nel resolver caldo (`ds4-p4a/ds4_cuda.cu:4118`).
     I `getenv` a `ds4-p4a/ds4_cuda.cu:4082-4088` e
     `ds4-p4a/ds4_cuda.cu:4125` erano gia' nel percorso e non sono delle
     cinque patch.
   - SHAREDCORE: **non memoizzato**, ma freddo. `DEDICATED` e' letto
     direttamente a ogni `ds4_shared1_create`
     (`ds4-p4a/ds4.c:11382-11397`,
     `ds4-p4a/ds4.c:11929-11936`); `AFFINITY` viene letto solo se N>0
     (`ds4-p4a/ds4.c:11399-11402`). Con shared1 spento, il return a
     `ds4-p4a/ds4.c:11851-11855` precede entrambi.
   - DSPARK2FIX3: nessun nuovo env. Il parent
     `DS4_NEXTN_CPU_DRAFTER` e' letto una volta per engine-open e salvato
     nell'engine (`ds4-p4a/ds4.c:22653-22663`,
     `ds4-p4a/ds4.c:22709-22712`).
   - LEDGERFIX: nessun env proprio. Il parent DOV e' memoizzato
     (`ds4-p4a/ds4_cuda.cu:37502-37508`) e risolto nel dispatch di init
     (`ds4-p4a/ds4_cuda.cu:50554-50573`); il transport ledger e' memoizzato
     separatamente (`ds4-p4a/ds4_cuda.cu:28268-28274`).

2. **DOV spento: nessun lock/slot pendente LEDGERFIX per layer.**
   Le chiamate defer stanno dentro `if constexpr (DOV)`
   (`ds4-p4a/ds4_cuda.cu:42325-42355`,
   `ds4-p4a/ds4_cuda.cu:43117-43133`) e il dispatch seleziona le istanze
   `DOV=false` quando il flag e' zero
   (`ds4-p4a/ds4_cuda.cu:50572-50639`). Il retire differito e lo slot
   `transport_deferred` non girano quindi a DOV OFF. Resta soltanto
   l'incremento di epoca ai confini se il transport ledger e' ON, gia'
   registrato fra i bug di neutralita'. Non risultano nuove chiamate CUDA
   da LEDGERFIX.

3. **Ledger spento ma DOV acceso:** `batch_begin` non arma il batch
   (`ds4-p4a/ds4_cuda.cu:28377-28388`); `defer` vede `active==0` e rientra
   (`ds4-p4a/ds4_cuda.cu:28565-28574`); il retire chiama comunque
   `finish_deferred`, che rientra alla prima guardia
   (`ds4-p4a/ds4_cuda.cu:28505-28508`). Quindi nessun lock del ledger e
   nessun pending attivo, ma rimangono call/branch worker-side: la frase
   “zero lavoro nuovo” del dossier e' troppo forte.

4. **Correttezza byte del resync:** anche con ROUTEFIX ON il solo numero di
   snapshot non produce un puntatore. Il resolver exige generazioni uguali,
   arena non bloccata e binding `READY` della stessa generazione
   (`ds4-p4a/ds4_cuda.cu:33656-33680`) prima di restituire i tre puntatori
   (`ds4-p4a/ds4_cuda.cu:33681-33686`). Ho escluso letture di byte
   non-pubblicati; il residuo trovato e' la corsa che puo' causare un
   fail-closed spurio, non una lettura unsafe.

5. **Nessun side effect OFF ulteriore.**

   - INDEXERZC: il vector globale esiste sempre
     (`ds4-p4a/ds4_cuda.cu:3935-3939`), ma a OFF resta vuoto; niente
     `cudaHostAlloc`, fd-read o log. Il solo hook sempre eseguito e' il
     release vuoto gia' elencato.
   - SHAREDCORE: il pool globale e il relativo BSS esistono sempre
     (`ds4-p4a/ds4.c:11354-11368`), ma mutex/cond/thread vengono
     inizializzati soltanto da `acquire`
     (`ds4-p4a/ds4.c:11459-11476`) dopo shared1 ON e N>0. Nessun log nuovo a
     env assenti.
   - DSPARK2FIX3: con NextN OFF non viene allocato `ds4_nextn_drafter`
     (`ds4-p4a/ds4.c:23485-23490`), e request begin/end sono chiamati solo
     se `s->nextn` e' non nullo (`ds4-p4a/ds4.c:23531-23545`). Nessun
     contatore, clock o log FIX3 gira.
   - ROUTEFIX: nessuna allocazione, contatore o log nuovo nel percorso sano;
     l'unica eccezione OFF e' il log del mismatch gia' classificato.
   - LEDGERFIX: nessuna allocazione dinamica; gli stati aggiunti sono
     statici zero-inizializzati (`ds4-p4a/ds4_cuda.cu:28241`,
     `ds4-p4a/ds4_cuda.cu:37500`).

6. **Inizializzazione telemetria DSPARK2FIX3 sana.** `step_tm` non viene
   letto non inizializzato: il forward azzera sempre la struct passata
   (`ds4-p4a/ds4.c:9756-9759`) prima di aggiornarla e la completa a
   `ds4-p4a/ds4.c:9837-9846`.

7. **Pool SHAREDCORE: invarianti principali sani.** Il submit mutex copre
   pubblicazione, broadcast e attesa completa
   (`ds4-p4a/ds4.c:11554-11576`); un avvio parziale riduce `n_threads` al
   numero realmente partito prima di pubblicare il pool
   (`ds4-p4a/ds4.c:11476-11514`); l'ultimo release avviene solo dopo il join
   del worker shared dell'istanza (`ds4-p4a/ds4.c:11821-11833`) e poi
   spegne/joina i worker dedicati (`ds4-p4a/ds4.c:11521-11548`). Non ho
   trovato il doppio submitter/race di slot che aveva colpito i tentativi
   precedenti.

8. **Nessuna modifica a layout ABI pubblico o a
   `cuda_moe_expert_cache`/mailbox.** Le modifiche di layout trovate sono
   tutte in struct file-local allocate/compilate nello stesso modulo
   (`ds4-p4a/ds4.c:9893-9972`,
   `ds4-p4a/ds4.c:11579-11635`,
   `ds4-p4a/ds4_cuda.cu:28220-28241`,
   `ds4-p4a/ds4_cuda.cu:37471-37500`). Questo esclude mismatch di ABI fra
   translation unit o host/device; non esclude la perturbazione di
   heap/BSS/cache-line rilevante per il protocollo di identita' temporale.
