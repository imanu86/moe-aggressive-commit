# Audit 10/07 — catena NextN completa

## 1. BUG

### B1 — Il budget host-pin non contabilizza la finestra primaria già registrata — MEDIA

**Prova.** Su Windows il runtime registra una finestra contigua del modello primario grande fino all'intero `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB` e salva solo `g_model_window_bytes`; nel ramo di successo non incrementa `g_model_registered_range_bytes` (`ds4-p4a/ds4_cuda.cu:17281-17298`). INDEXERZC usa invece proprio `g_model_registered_range_bytes` per il controllo del medesimo budget e lo incrementa soltanto dopo ogni `cudaHostAllocMapped` riuscita (`ds4-p4a/ds4_cuda.cu:4020-4052`). Il commento dichiara esplicitamente che finestra registrata e INDEXERZC dovrebbero condividere lo stesso budget fisico WDDM (`ds4-p4a/ds4_cuda.cu:3918-3923`).

**Scenario concreto.** Input/stato: budget campagna 2 GiB, registrazione contigua primaria riuscita per 2 GiB, poi `DS4_CUDA_INDEXER_HOST_ZEROCOPY=1`. Stato osservato dal controllo INDEXERZC: contatore ancora zero. Esito sbagliato: vengono accettate ulteriori allocazioni host-pinned fino a circa un altro budget invece di fare `host-pin-budget-exceeded`; con `DS4_NEXTN_PIN=2` si aggiungono anche tutti i tensori MTP densi, testa ed esperti bloccati via `VirtualLock` (`ds4-p4a/ds4.c:22409-22442`). Il risultato non altera i token, ma può produrre pressione di memoria/fault e degradare o far fallire altre allocazioni.

### B2 — `DRAFT_K` non viene limitato alla finestra utile del job — BASSA

**Prova.** Il worker copia soltanto `d->k` e avvia sempre `k+1` forward, incluso il passo di row-fill (`ds4-p4a/ds4.c:10052-10058`, `ds4-p4a/ds4.c:10087-10099`). Il limite reale del ciclo (`max_tokens`, capacità dell'output e spazio contesto) viene calcolato più tardi dal thread decode (`ds4-p4a/ds4.c:24032-24037`) e passato solo a `take`, che tronca ciò che consegna (`ds4-p4a/ds4.c:20637-20645`); non entra mai nel mailbox del job.

**Scenario concreto.** Input/stato: `DS4_NEXTN_DRAFT_K=7`, ma rimane spazio per un solo draft prima di `max_tokens` o del bordo contesto. Esito sbagliato prestazionale: la chain può eseguire fino a otto forward pur potendone consumare uno; dopo che `take` marca il job consumato, il worker se ne accorge solo al confine del passo successivo (`ds4-p4a/ds4.c:20656-20658`, `ds4-p4a/ds4.c:10093-10099`). Non si drafta oltre gli array o il contesto, ma si butta lavoro e si sottraggono core/banda al target.

### B3 — Il log per-ciclo tronca `accept_pos` a sette posizioni — BASSA

**Prova.** Il contratto e il parser consentono `DRAFT_K` fino a 16 (`ds4-p4a/ds4.c:9882-9885`, `ds4-p4a/ds4.c:22692-22700`), mentre `pos_buf` e il relativo loop sono cablati a sette (`ds4-p4a/ds4.c:20743-20748`). Il summary finale per-posizione usa invece correttamente `d->k` (`ds4-p4a/ds4.c:20830-20839`).

**Scenario concreto.** Input/stato: `DS4_NEXTN_DRAFT_K=8..16` e accettazioni oltre posizione 7. Esito sbagliato: la riga per-ciclo mostra soltanto sette simboli e nasconde la coda accettata/rifiutata, falsando la diagnosi temporale del banco. Con il valore di campagna `K=7` il difetto non si manifesta.

### B4 — Il discriminatore generico del precheck non stampa l'epoch G133 che può bocciarlo — BASSA

**Prova.** `request_valid` comprende `cuda_g133_epoch_valid(request.g133_epoch)` (`ds4-p4a/ds4_cuda.cu:42530-42538`), ma la riga `result=invalid` stampa route, miss e dimensioni, non `g133_epoch` (`ds4-p4a/ds4_cuda.cu:42546-42556`). Il nuovo ramo routefix discrimina soltanto il successivo mismatch compose-snapshot (`ds4-p4a/ds4_cuda.cu:42558-42623`).

**Scenario concreto.** Input/stato: G133 attivo, epoch nullo/non valido, route/miss/layer/byte tutti sani. Esito sbagliato diagnostico: compare `result=invalid` con tutti i campi stampati coerenti, ma il log non prova quale termine abbia fallito. Questo non spiega un log che contiene `result=invalid-compose-snapshot`; impedisce però di chiudere senza ambiguità l'altro ramo del discriminatore storico.

## 2. INTERFERENZE FRA LEVE

### I1 — `DS4_NEXTN_CPU_DRAFTER=1` + `DS4_CPU_SHARED_EXPERT=1` + `DS4_CPU_SHARED_EXPERT_DEDICATED=0`

**Meccanismo.** Ogni kernel pooled del drafter prende `g_shared1_pool_mutex` durante il submit G132 (`ds4-p4a/ds4.c:11295-11311`). Shared1 non dedicato prende lo stesso mutex e lo conserva attraverso entrambi i matvec, SwiGLU e prequant (`ds4-p4a/ds4.c:11711-11721`). I due lavori sono quindi serializzati per lunghi burst, oltre alla normale contesa su core e DRAM. Shared1 viene programmato prima del routing MoE di ciascun layer target (`ds4-p4a/ds4.c:14192-14202`).

**Manifestazione a banco.** Aumento di `step_ms_avg`, soprattutto `fwd_dense_avg`/`head_avg`, e di `pending` nel summary NextN (`ds4-p4a/ds4.c:20811-20829`); sul lato shared aumentano `shared_wait_ms`, esposto dal log shared (`ds4-p4a/ds4.c:11795`). Sul target può inoltre aumentare `worker-prof pickup_lag_ms`/`job_ms` perché il route worker concorre con i burst CPU (`ds4-p4a/ds4_cuda.cu:5022-5036`).

**Guardia suggerita.** Vietare questa coppia con `DEDICATED=0`; se shared1 è indispensabile, richiedere un pool dedicato effettivamente armato e verificare la riga `dedicated pool armed` (`ds4-p4a/ds4.c:11929-11953`).

### I2 — `DS4_NEXTN_CPU_DRAFTER=1` + sharedcore (`DS4_CPU_SHARED_EXPERT_DEDICATED=N`, `...AFFINITY=1`)

**Meccanismo.** Il ramo dedicato elimina il mutex G132 e usa un pool proprio (`ds4-p4a/ds4.c:11694-11710`), ma l'affinità assegna soltanto i thread shared a CPU logiche alte/non-SMT (`ds4-p4a/ds4.c:11399-11417`): non esclude da quei core i worker G132 del drafter né il route worker. La riga di armamento dichiara infatti route worker, G132 e pool generale “invariati” (`ds4-p4a/ds4.c:11940-11949`). Resta dunque contesa simultanea su scheduler, cache e banda DRAM.

**Manifestazione a banco.** `shared_wait_ms` resta basso ma salgono insieme `shared_cpu_ms`, `fwd_dense_avg`/`head_avg`, `pending` e, se il route worker viene deschedulato, `pickup_lag_ms`/`wait_ms_per_token` (`ds4-p4a/ds4.c:11795`, `ds4-p4a/ds4.c:20811-20829`, `ds4-p4a/ds4_cuda.cu:5022-5039`).

**Guardia suggerita.** Non vietare a priori; limitare `N` e accettare la combinazione solo se un A/B mostra invariati `pickup_lag_ms` e token latency. `AFFINITY=1` non va trattato come prenotazione esclusiva dei core.

### I3 — NextN pageable/`DS4_NEXTN_PIN` parziale + streaming esperti GPU

**Meccanismo.** Con NextN il modello MTP secondario rimane nel proprio mmap host e la registrazione CUDA secondaria viene saltata (`ds4-p4a/ds4.c:22638-22648`, `ds4-p4a/ds4.c:22841-22855`). Il route worker legge invece gli esperti del modello primario tramite `g_model_file`, tre `pread` per miss (`ds4-p4a/ds4_cuda.cu:42911-42930`, `ds4-p4a/ds4_cuda.cu:42932-42966`). Non è quindi “la stessa mappatura”: sono modello/file logici distinti, salvo la testa base che NextN legge dal modello primario (`ds4-p4a/ds4.c:22366-22373`). Se i lock NextN falliscono, MTP e testa generano fault dal volume C: mentre il singolo route worker fa I/O primario; se i lock riescono, resta la contesa DRAM/core ma non il page-in ripetuto (`ds4-p4a/ds4.c:22421-22449`).

**Chi rallenta chi / manifestazione.** La contesa storage è bidirezionale, ma il danno visibile è asimmetrico: un `pread` lento allunga subito `read_gate_ms/read_up_ms/read_down_ms` del percorso target (`ds4-p4a/ds4_cuda.cu:5025-5036`); un drafter lento non blocca il rendezvous, perché `take` non aspetta e torna `pending` (`ds4-p4a/ds4.c:24044-24060`). Sul drafter crescono `fwd_q4_avg` se faultano gli esperti, `head_avg` se faulta la testa, e `pending` (`ds4-p4a/ds4.c:20811-20829`).

**Guardia suggerita.** Accettare `PIN=2` solo con `failed=0` nella riga di pin; con byte falliti, vietare il confronto prestazionale oppure classificare separatamente il run come I/O-conteso (`ds4-p4a/ds4.c:22444-22449`).

### I4 — `DS4_NEXTN_PIN=2` + `DS4_CUDA_INDEXER_HOST_ZEROCOPY=1` + budget host-pin 2 GiB

**Meccanismo.** NextN blocca densi, testa e tutti e tre i tensori esperti MTP (`ds4-p4a/ds4.c:22393-22442`); INDEXERZC crea buffer `cudaHostAllocMapped` non sfrattabili e li serve direttamente via UVA (`ds4-p4a/ds4_cuda.cu:4025-4053`). Si sommano memoria fisica non reclamabile e traffico: il percorso INDEXERZC dichiara il tocco del 100% dei byte pinnati per token (`ds4-p4a/ds4_cuda.cu:3987-4004`). B1 rende inoltre inaffidabile il tetto nominale.

**Manifestazione a banco.** Riga NextN con `failed>0`, `[indexer-zc] pin_failed reason=cudaHostAlloc|host-pin-budget-exceeded`, crescita dei tre `fwd_*`/`head`, `pending`, e crescita dei tempi `worker-prof read_*` se il sistema entra in pressione (`ds4-p4a/ds4.c:22444-22449`, `ds4-p4a/ds4_cuda.cu:3967-3975`, `ds4-p4a/ds4_cuda.cu:5025-5036`).

**Guardia suggerita.** Vietare la tripla finché B1 non è corretto o finché un inventario esterno della RAM bloccata non dimostra margine; per il banco causale provare PIN2 e INDEXERZC in bracci separati.

### I5 — NextN batch verify + compose tiering + `DS4_CUDA_ROUTE_SNAPSHOT_RESYNC`

**Meccanismo.** NextN chiama il verifier batch dopo che il free-check è passato (`ds4-p4a/ds4.c:24351-24361`). La successiva richiesta single-token viene rifiutata se le generazioni arena/tiering differiscono (`ds4-p4a/ds4_cuda.cu:42558-42561`). Routefix può adottare la generazione arena soltanto con arena quiescente, backing primario e generazione non nulla (`ds4-p4a/ds4_cuda.cu:42575-42604`); il servizio ricontrolla comunque la parità delle generazioni e fallisce chiuso (`ds4-p4a/ds4_cuda.cu:41294-41308`). Il verifier batch è un marcatore temporale utile, non una prova che sia lui a pubblicare una nuova generazione.

**Manifestazione a banco.** Senza resync: `result=invalid-compose-snapshot` sulla prima request interessata. Con resync sano: `result=resync-compose-snapshot`. Con arena non quiescente: `resync=arena-busy`. Se la request viene già claimata ma muore prima del consumer boundary, il `consumer_done` di quel layer non gira (`ds4-p4a/ds4.c:14512-14521`) e il claim seguente può mostrare la cascata `consumer-event-generation` (`ds4-p4a/ds4_cuda.cu:31617-31648`). Questa è la lettura coerente dell'abort storico a seq=130: il secondo errore è conseguenza del primo veto, non prova di wrap del ring.

**Guardia suggerita.** Non accendere routefix come rimedio generico. Consentirlo solo quando il log prova `invalid-compose-snapshot`, arena quiescente e una pubblicazione valida a monte; altrimenti vietare la combinazione e lasciare il fail-closed. Se compare `result=invalid` anziché `invalid-compose-snapshot`, routefix non copre il termine fallito (`ds4-p4a/ds4_cuda.cu:42546-42561`).

### I6 — NextN + `DS4_CUDA_PIN_BACKBONE=1`

**Meccanismo.** I due “pin” agiscono su oggetti diversi: `DS4_NEXTN_PIN=2` applica lock host ai tensori del modello MTP e alla testa base (`ds4-p4a/ds4.c:22366-22442`); `DS4_CUDA_PIN_BACKBONE=1` impedisce invece di reclamare range backbone in VRAM e, sotto pressione, cede l'intero slab esperti GPU primario (`ds4-p4a/ds4_cuda.cu:8086-8096`, `ds4-p4a/ds4_cuda.cu:37337-37413`). L'espulsione/ricarica degli esperti GPU non invalida né sblocca gli esperti MTP del drafter.

**Manifestazione a banco.** L'interferenza è indiretta: gli shed/rebuild dello slab aumentano exact streaming e I/O primario, mentre NextN continua a consumare CPU/DRAM. Cercare `[vram-prio] PIN degrade`, aumento di `read_*` e `pending`, non mismatch di token o fault di puntatore (`ds4-p4a/ds4_cuda.cu:37431-37441`, `ds4-p4a/ds4_cuda.cu:5025-5039`, `ds4-p4a/ds4.c:20811-20829`).

**Guardia suggerita.** Combinazione ammessa, ma vietarla nel braccio che misura isolatamente il beneficio NextN se avviene anche un solo shed; quel run misura due cambi di working set.

## 3. ESCLUSIONI

### Rebase e accept parziale: stato sano

- Il rebase non “sposta” ciecamente gli indici: richiede posizione consecutiva, registra il token realmente committato e valida induttivamente ogni offset contro `job_first_token`/`pub_drafts`; al primo mismatch uccide il job e richiede reset KV (`ds4-p4a/ds4.c:20594-20633`). Un tail posizionalmente stantio non viene quindi consegnato.
- Quando `take` consegna almeno un tail, marca l'intero vecchio job consumato (`ds4-p4a/ds4.c:20634-20658`). Dopo un accept parziale il verifier ricostruisce/committa il prefisso esatto e passa a `cycle_end` la riga HC dell'ultima posizione davvero accettata (`ds4-p4a/ds4.c:24541-24572`); `cycle_end` crea una nuova chain, non riusa il suffix rifiutato (`ds4-p4a/ds4.c:20771-20772`).
- Il KV MTP persistente resta coerente anche in accept parziale: il row-holdback rende consegnabile un draft solo dopo che esiste la sua riga KV (`ds4-p4a/ds4.c:10157-10174`); al job successivo il worker conserva le righe fino a `q_valid` e scarta quelle speculative oltre il frontier, oppure resetta sulle discontinuità (`ds4-p4a/ds4.c:10070-10085`). Per un prefisso parzialmente accettato, le righe conservate corrispondono proprio ai token della vecchia chain che il target ha confermato. Non è emersa corruzione della chain in questo caso.

### Free-check del ciclo 2 e `k_accepted=0`

- `k_accepted=0` con `k_delivered>0` significa precisamente che l'argmax target appena disponibile non coincide con `drafts[0]`; il codice chiude il ciclo e riparte da `CUR_HC` senza lanciare il batch verifier (`ds4-p4a/ds4.c:24091-24105`). Cause sane oltre allo stantio posizionale: divergenza normale tra target e MTP; la scelta progettuale di ancorare il primo passo a un HC una posizione più vecchio del probe GPU (`ds4-p4a/ds4.c:9863-9870`); differenze numeriche/argmax del forward CPU Q4 e della testa CPU (`ds4-p4a/ds4.c:10101-10116`) su margini piccoli.
- Lentezza/page fault non produce direttamente un free-check miss: se non esiste ancora un draft consegnabile, `take` ritorna zero e il ciclo viene classificato `pending` o `stale`, senza arrivare al confronto (`ds4-p4a/ds4.c:24044-24060`). Un `k_accepted=0` persistente con `src=live` va quindi cercato nella qualità/condizionamento del draft; con `src=pending|stale` va cercato nella latenza.
- L'abort storico a seq=130 non è causato dal free-check del ciclo 2: il free-check fallito ritorna prima del verifier (`ds4-p4a/ds4.c:24097-24105`), mentre la catena route descritta in I5 richiede una request single-token successiva a un batch verify (`ds4-p4a/ds4.c:24351-24361`, `ds4-p4a/ds4_cuda.cu:42558-42623`).

### Finestre, limiti e sicurezza dell'output

- `DRAFT_K=7` non supera buffer o contratto: viene clampato a 1..16 all'apertura (`ds4-p4a/ds4.c:22692-22712`), `take` limita la consegna a `draft_cap` (`ds4-p4a/ds4.c:20637-20645`) e il decode limita `draft_cap` a output, `max_tokens` e spazio contesto (`ds4-p4a/ds4.c:24032-24037`). Resta soltanto lo spreco di calcolo descritto in B2.
- Il target, non MTP, decide sempre l'output: `first_token` passa dal normale `ds4_session_eval`, poi ogni suffix è verificato e si committa soltanto il prefisso consecutivo concorde (`ds4-p4a/ds4.c:24012-24023`, `ds4-p4a/ds4.c:24363-24369`). Un cattivo draft riduce l'accettazione, non cambia i token emessi.

### PIN, route worker e altre leve

- `PIN=2` non dà proprietà esclusiva delle pagine e non congela la route selection: esegue `VirtualLock`/`mlock` sui tensori, conta separatamente successi e fallimenti e non registra alcun collegamento con la cache esperti CUDA (`ds4-p4a/ds4.c:22333-22343`, `ds4-p4a/ds4.c:22421-22449`). Lo sfratto GPU degli esperti primari non può invalidare gli esperti del modello MTP separato.
- La pool G132 “lane” esterna è già vietata con NextN all'apertura, evitando due orchestratori proprietari dello slot (`ds4-p4a/ds4.c:22681-22690`). Questo non vieta shared1: la sua interferenza residua è quella esplicitata in I1/I2.
- DOV ritira l'overlap precedente al claim successivo (`ds4-p4a/ds4_cuda.cu:42501-42510`) e il ledger differito vive nello stesso stato worker-owned fino alla prova di retire (`ds4-p4a/ds4_cuda.cu:37483-37499`). Il verifier NextN percorre l'encoder batch e i suoi command buffer, non il layer decode che registra `route_consumer_done` (`ds4-p4a/ds4.c:18384-18455`, `ds4-p4a/ds4.c:14512-14521`); nel codice esaminato non emerge una violazione d'ordine specifica NextN+DOV/ledgerfix.
- Routefix resta fail-closed sui byte: il resync è ammesso solo su arena quiescente/primaria (`ds4-p4a/ds4_cuda.cu:42575-42604`) e il serve-gate ricontrolla la generazione prima del servizio (`ds4-p4a/ds4_cuda.cu:41294-41308`). È sano come guardia condizionata; non prova da solo la causa della deriva di snapshot.
