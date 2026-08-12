# 1. BUG

## B1 — riuso prematuro dell'OVERLAPPED dopo il cancel recuperabile

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:31454-31459`, `ds4-p4a/ds4_cuda.cu:31513-31523`, `ds4-p4a/src/platform/os_file.c:363-365`, `ds4-p4a/src/platform/os_file.c:418-431`.
- **Severità: ALTA.**
- **Scenario concreto:** una `ReadFile` transiente e' ancora pendente quando il consumer raggiunge la deadline. Il consumer marca la sequence e chiama `CancelIoEx` (`ds4_cuda.cu:31454-31459`). Il lettore Windows aspetta il completamento del cancel per soli 50 ms; se non arriva, ritorna `-1` lasciando `state->active == 1` e lo slot OVERLAPPED vivo (`os_file.c:418-431`). Il worker entra allora nel fallback e chiama `os_pread_cancellable_reset`, che azzera solo `cancel_sequence`, non `active` (`ds4_cuda.cu:31513-31523`; implementazione del reset in `os_file.c:317-326`). La prima rilettura senza deadline trova lo slot ancora pending e fallisce `EBUSY` (`os_file.c:363-365`). Esito sbagliato: il retry dichiarato recuperabile abortisce con `[transient-timeout] reason=fallback-unavailable fallback_skipped_reason=fallback-pread-failed` (`ds4_cuda.cu:41753-41775`); con `G73_OPEN=0` il launcher rifiuta il terminale esatto e termina il layer (`ds4_cuda.cu:48497-48512`).
- **Prova/chiudibilità:** non e' una rarita' logica; scatta ogni volta che il completamento del cancel supera 50 ms. E' chiudibile imponendo come precondizione del fallback `os_pread_cancellable_pending()==0`/ack esplicito del cancel; il commento «the cancellable call has returned ... slot can be reset» a `ds4_cuda.cu:31513-31518` non e' vero per il ramo Windows `os_file.c:418-431`.

## B2 — `route_transient_read_deadline` ha una data race e puo' restare scaduta durante il fallback

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:29110-29117`, `ds4-p4a/ds4_cuda.cu:31524-31533`, `ds4-p4a/ds4_cuda.cu:47914-47916`, `ds4-p4a/ds4_cuda.cu:47935-47955`.
- **Severità: ALTA.**
- **Scenario concreto:** `route_transient_read_deadline` e' un `double` ordinario, mentre le sequence circostanti sono atomiche (`ds4_cuda.cu:29110-29117`). Il worker modifica il double da deadline scaduta a `0.0` e ripubblica la stessa sequence (`ds4_cuda.cu:31531-31533`); contemporaneamente il consumer legge sequence e double (`ds4_cuda.cu:47914-47916`, `:47935-47936`). Questa e' una data race C++ e la ripubblicazione dello stesso valore atomico non costituisce un cambio di stato inequivoco. Se il consumer continua a vedere il double scaduto, entra nel ramo `transient_timeout_recovery_sequence == sequence`, ignora `route_transient_read_bytes` e, allo scadere della grace fissa, esegue `cancel_and_join` (`ds4_cuda.cu:47941-47955`). Esito sbagliato: un fallback senza deadline che sta avanzando puo' essere cancellato e terminare come `route-stop-during-fallback` o `cancel-sequence-during-fallback` (`ds4_cuda.cu:31563-31575`).
- **Prova/chiudibilità:** il percorso sarebbe progress-aware soltanto dopo aver osservato deadline zero, nel ramo che rinnova `wait_deadline` quando i byte crescono (`ds4_cuda.cu:47978-47992`). Serve una pubblicazione atomica versionata/ack della transizione a fallback; quindi la corsa e' chiudibile, non una proprieta' inevitabile del disegno.

## B3 — le letture di ammissione RAM sono fuori dal watchdog e non sono cancellabili

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:41279-41286`, `ds4-p4a/ds4_cuda.cu:41515-41535`, `ds4-p4a/ds4_cuda.cu:36450-36460`, `ds4-p4a/ds4_cuda.cu:36580-36606`, `ds4-p4a/ds4_cuda.cu:6558-6560`, `ds4-p4a/src/platform/os_file.c:629-635`, `ds4-p4a/ds4_cuda.cu:47978-48016`, `ds4-p4a/ds4_cuda.cu:31748-31780`.
- **Severità: ALTA.**
- **Scenario concreto:** la deadline transiente nasce all'ingresso di `cuda_moe_tiering_enforce_request` (`ds4_cuda.cu:41279-41286`), ma prima del percorso transiente il worker tenta `cuda_moe_tiering_load_to_ram` per uno `SSD_COLD` (`ds4_cuda.cu:41515-41535`). Tale funzione legge gate/up/down con `cuda_pread_full` (`ds4_cuda.cu:36580-36606`), che delega a `os_pread` senza deadline (`ds4_cuda.cu:6558-6560`) e su Windows attende `GetOverlappedResult(..., TRUE)` (`os_file.c:629-635`). In una tempesta I/O, input = una di queste letture bloccata oltre 5 s; stato = `route_transient_read_sequence` non ancora pubblicata. Il consumer classifica il worker come `starved`, non come transiente, e chiama `cancel_and_join` (`ds4_cuda.cu:47978-48016`). Il cancel agisce sul diverso slot `route_transient_pread`; la `os_pread` stack-local non lo osserva. Dopo altri 5 s il join puo' scadere e rendere cache/worker `safe-leaked` permanente (`ds4_cuda.cu:31748-31780`). Esito sbagliato: il timeout configurato non limita proprio la lettura SSD che puo' dominare il servizio.

## B4 — `deadline_exhausted` non conta le deadline scadute durante l'I/O

- **File:riga verificata:** `ds4-p4a/ds4_cuda.cu:41651-41684`, `ds4-p4a/ds4_cuda.cu:31343-31350`, `ds4-p4a/ds4_cuda.cu:31419-31423`, `ds4-p4a/ds4_cuda.cu:5039-5040`.
- **Severità: MEDIA.**
- **Scenario concreto:** il contatore `WP_DEADLINE_EXHAUSTED` viene incrementato soltanto una volta, se la deadline e' gia' scaduta al primo ingresso transiente (`ds4_cuda.cu:41651-41684`). Le scadenze normali fra chunk o dopo un chunk ritornano `-1` senza incrementarlo (`ds4_cuda.cu:31343-31350`, `:31419-31423`). Input = deadline positiva all'ingresso e I/O che la supera; esito telemetrico sbagliato = `deadline_exhausted=0` pur con retry/abort reali. Il campo stampato a `ds4_cuda.cu:5039-5040` significa quindi «budget gia' esaurito prima della prima pread transiente», non «numero di deadline scadute».

# 2. INTERFERENZE FRA LEVE

## I1 — `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1` × `DS4_G133_TRANSIENT_IO_TIMEOUT_S` aggressivo × tempesta di letture

- **Meccanismo:** dopo un timeout il fallback parte immediatamente, senza sleep, jitter o backoff (`ds4_cuda.cu:41731-41764`). Se il cancel cade a meta' tensore, `transient_stage_done` avanza solo dopo il completamento dell'intero gate/up (`ds4_cuda.cu:41706-41720`); il fallback ricomincia quel tensore dall'offset iniziale (`ds4_cuda.cu:31539-31561`). Inoltre `transient_request_deadline` e' `const` per tutta la richiesta (`ds4_cuda.cu:41282-41286`): dopo il primo fallback i miss successivi continuano a ricevere la vecchia deadline scaduta (`ds4_cuda.cu:41698-41727`) e passano subito a un'altra rilettura senza deadline. Il limite e' per expert fallback, non per batch (`ds4_cuda.cu:41736-41764`).
- **Manifestazione a banco:** salgono insieme `transient_timeout_fallbacks`, `[slow-token] pread_calls/pread_bytes`, `read_gate/up/down_ms` e `worker_ms/job`; i byte/call sono differenze dei contatori di ogni pread realmente emessa/completata (`ds4_cuda.cu:34149-34165`). `deadline_exhausted` puo' restare zero per B4. Il cap produce infine `[transient-timeout] reason=fallback-budget-exhausted` (`ds4_cuda.cu:41741-41752`); i totali fallback/abort sono esposti anche nella riga `[zc]` (`ds4_cuda.cu:34025-34038`, `:34069-34073`).
- **Guardia/combinazione:** vietare un timeout inferiore al p99 della lettura di un tensore piu' la latenza di completamento del cancel finche' B1/B2 non sono chiusi. Il cap limita la durata della tempesta ma non e' backoff; abbassarlo trasforma l'amplificazione in abort anticipato.

## I2 — `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1` × `DS4_CUDA_SCOPED_INVALIDATE=0` × pressione/sfratti

- **Meccanismo:** un fallimento transiente porta `ok=0`; senza SCOPED, il worker puo' invalidare l'intera cache se esistono promozioni (`ds4_cuda.cu:40768-40795`) e il consumer esegue comunque il reset totale se non trova una firma scoped (`ds4_cuda.cu:48046-48069`). L'invalidate azzera ogni slot VALID/LOADING e la mappa (`ds4_cuda.cu:37267-37307`). Il token/richiesta successivo diventa all-miss, aumenta letture e H2D, e rende piu' probabile il timeout successivo.
- **Manifestazione a banco:** ciclo `cache_invalidates_total`/`cache_full_valid_dropped` in salita, `miss_experts` verso 6 per layer, `repeat_file_bytes` e `evicts_total` in crescita, seguito da timeout/abort. Gli sfratti del model cache sono un loop senza backoff che elimina una vittima per iterazione (`ds4_cuda.cu:8665-8702`, `:8764-8781`) e ogni reload rilegge il range a chunk (`ds4_cuda.cu:8791-8869`).
- **Guardia/combinazione:** in una campagna timeout sotto pressione, richiedere SCOPED insieme a RECOVERABLE; vietare il braccio `SCOPED=0 + RECOVERABLE=1` come misura di prestazione. Con SCOPED e `count==0`, il worker firma esplicitamente `no-reservations` e impedisce il reset collettivo (`ds4_cuda.cu:40772-40789`).

## I3 — `DS4_CUDA_DRAIN_OVERLAP4=1` × `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1`

- **Meccanismo:** il retry avviene prima di ogni H2D e prima dell'unico arm DOV (`ds4_cuda.cu:41731-41783`, `:41979-42028`, `:42323-42345`). Quindi DOV non puo' nascondere il tempo del retry SSD: ne sovrappone soltanto l'H2D finale. Una tempesta fa crescere la permanenza del job worker, non il numero di arm dello stesso batch.
- **Manifestazione a banco:** `read_*_ms` e `worker_ms/job` salgono, mentre `drain_overlap_ms` puo' restare piccolo; `h2d_bytes_total` non raddoppia per il solo retry. Se compare `ledger_complete=0`, cercare errore/commit differito stantio, non un doppio arm (`ds4_cuda.cu:28565-28588`).
- **Guardia/combinazione:** non giudicare il guadagno DOV su run con `transient_timeout_fallbacks>0`; imporre come gate di banco fallback/abort zero oppure separare i token con fallback prima del confronto.

## I4 — `DS4_CPU_SHARED_EXPERT=1` × `DS4_NEXTN_CPU_DRAFTER=1` × timeout transiente

- **Meccanismo:** senza sharedcore dedicato, shared1 e NextN serializzano i submit sullo stesso mutex g132 (`ds4.c:11283-11310`, `ds4.c:11694-11721`), mentre il burst shared viene schedulato prima della rotta dello stesso layer (`ds4.c:14192-14212`). Con pool dedicato, la contesa sul mutex sparisce ma N thread shared aggiuntivi restano concorrenti del route worker (`ds4.c:11929-11949`). NextN usa comunque il g132 per i job pesanti (`ds4.c:796-813`). Il risultato e' pressione CPU/DRAM durante le pread del worker, senza alcun backoff lato timeout.
- **Manifestazione a banco:** `worker-prof pickup_ms` alto indica starvation CPU prima del servizio; `read_*_ms` alto con pickup normale indica contesa memoria/I/O. `shared_cpu_ms` cresce mentre `shared_wait_ms` puo' restare basso; NextN mostra `step_ms_avg` alto.
- **Guardia/combinazione:** con RECOVERABLE attivo non usare contemporaneamente shared1 sul g132 e drafter a piena ampiezza; usare sharedcore con N conservativo e affinità realmente applicata, lasciando almeno un core non occupato per route/decode, oppure spegnere una delle due leve nel braccio timeout.

## I5 — `DS4_CPU_SHARED_EXPERT=1` × `DS4_NEXTN_CPU_DRAFTER=1` (verify) × tempesta sfratti

- **Meccanismo:** il verify batch usa gli shexp su GPU e marca `vram_dirty` (`ds4.c:17342-17353`); al layer 0 successivo shared1 rilascia quegli span (`ds4.c:12076-12083`). Il release rimuove ogni range streamed shexp e lo parcheggia nel pool (`ds4_cuda.cu:8623-8647`). Verify ripetuti producono quindi stage→release→stage, aggiungendo letture del modello allo stesso volume C: conteso dalle pread transiente.
- **Manifestazione a banco:** `shared-cpu vram_sweeps` e byte rilasciati aumentano insieme a `g_model_evict_count`, reload/fd-cache e `read_*_ms`; seguono fallback timeout pur senza aumento di `deadline_exhausted`.
- **Guardia/combinazione:** vietare shared1+verify speculativo nel braccio dedicato ai timeout finche' `vram_sweeps` non dimostra assenza di ping-pong; in alternativa usare un braccio senza una delle due leve come controllo obbligatorio.

## I6 — `DS4_NEXTN_PIN=2` × timeout transiente

- **Meccanismo:** PIN=2 include tutti gli esperti NextN nel working set bloccato (`ds4.c:22315-22319`, `ds4.c:22409-22443`) oltre a dense+head. Il codice aumenta anche il working-set minimo del processo (`ds4.c:22346-22356`). Sotto RAM limitata questo riduce la memoria liberamente contendibile dal modello mmap/page cache mentre route worker e drafter leggono grandi regioni.
- **Manifestazione a banco:** `pin mode=2 locked` pieno, NextN stabile ma `read_*_ms`, `repeat_file_bytes` e fallback transiente peggiorano; se il lock fallisce, il log `failed` separa il caso (`ds4.c:22444-22449`).
- **Guardia/combinazione:** non usare PIN=2 nel braccio timeout senza un controllo PIN=1/0 e memoria libera documentata; vietarlo se i fallback compaiono soltanto col working set bloccato.

# 3. ESCLUSIONI

## E1 — il retry recuperabile non arma due volte lo stesso batch DOV

Il retry opera soltanto sulle slice host e termina prima di copia, publish e arm (`ds4_cuda.cu:31539-31563`, `ds4_cuda.cu:41731-41783`). La copia H2D viene accodata una sola volta dopo `read_result==1` (`ds4_cuda.cu:41979-42028` o `:42156-42205`); l'arm ENFORCE e il `defer` del ledger hanno un solo sito finale (`ds4_cuda.cu:42323-42345`). Fra generazioni, il claim della nuova richiesta precede il servizio e ritira l'overlap precedente (`ds4_cuda.cu:42501-42510`). Il fail-safe del ledger chiude come incompleto un pendente inatteso invece di sommarlo due volte (`ds4_cuda.cu:28565-28588`). Risposta (a): **nessun doppio arm/doppio conteggio causato dal retry**; la deadline locale resta invece scaduta per i miss successivi, interferenza I1.

## E2 — non esiste una coda route non limitata

Il submit riusa un ring mailbox a due slot e rifiuta uno slot non FREE/CONSUMER_DONE (`ds4_cuda.cu:47720-47733`); il consumer aspetta la stessa `sequence` fino a ready/failure (`ds4_cuda.cu:47900-47912`). Quindi il retry non accumula job route dietro al worker: allunga il job corrente e blocca il decode. Risposta (b): **nessuna amplificazione nella mailbox**, ma amplificazione reale sul volume/tempo I/O per rilettura del tensore e per attori concorrenti (I1, I4-I6). Nel codice non esiste backoff del fallback (`ds4_cuda.cu:41731-41764`).

## E3 — la deadline transiente e' codice vivo; `deadline_exhausted` e' il contatore sbagliato per provarlo

Per `G73_OPEN=0` la request arriva con deadline zero dal launcher (`ds4_cuda.cu:48297-48310`), ma il worker ne crea una propria all'ingresso ENFORCE (`ds4_cuda.cu:41279-41286`). La pread la controlla prima di ogni chunk e dopo ogni chunk (`ds4_cuda.cu:31343-31350`, `:31419-31423`), e il consumer legge la stessa deadline per il cancel recuperabile (`ds4_cuda.cu:47935-47969`). Risposta (d): **non e' codice morto** quando esistono miss SSD transienti; `deadline_exhausted=0` dice soltanto che al primo ingresso transiente rimaneva ancora slack (B4). Se anche `deadline_slack_events=0`, allora in quel run il sito strumentato non e' stato raggiunto (all-hit/RAM, worker-prof off, o altro percorso I/O).

## E4 — DOV non usa la deadline come prova di correttezza

L'arm registra l'evento dopo l'ultimo publish e pubblica la generazione (`ds4_cuda.cu:40695-40715`, `:40733-40740`); il consumer mette `cudaStreamWaitEvent` prima dei kernel lettori (`ds4_cuda.cu:37649-37676`). Il claim successivo ritira soltanto dopo il done-event della generazione precedente (`ds4_cuda.cu:31617-31637`, `ds4_cuda.cu:37616-37627`). Ritardi e timeout cambiano la latenza o portano fail-closed, non sostituiscono questa prova con un cronometro.

## E5 — ledgerfix non committa byte DOV senza prova e non contamina la richiesta successiva

Il commit differito avviene soltanto al retire (`ds4_cuda.cu:37566-37586`); un errore dell'upload chiude il batch come incompleto (`ds4_cuda.cu:37604-37613`). L'epoca viene fotografata al defer e verificata sotto lock al commit (`ds4_cuda.cu:28505-28518`, `:28583-28587`); il clear incrementa l'epoca (`ds4_cuda.cu:28591-28614`). Restano il sottoconteggio dichiarato del batch di coda e l'eventuale `ledger_complete=0`, ma non doppio conteggio né attribuzione alla richiesta nuova.

## E6 — routefix e indexer-zc non partecipano alla corsa timeout

Routefix gira nel precheck snapshot, prima di entrare nel servizio ENFORCE e prima che nasca `transient_request_deadline` (`ds4_cuda.cu:42558-42620`, `ds4_cuda.cu:42803-42810`, `ds4_cuda.cu:41279-41286`): puo' accettare/rifiutare una request, non riarmare cancel o DOV. Indexer-zc intercetta soltanto i range etichettati `indexer_f16` nel model range lookup (`ds4_cuda.cu:3908-3948`, `:3978-4005`, `:4121`); non usa `route_transient_pread`, i marker di cancel o il sidecar DOV. Le sue conseguenze PCIe/VRAM vanno misurate separatamente, ma non spiegano `fallback-unavailable`.

## E7 — `PIN_BACKBONE` non libera lo slab durante un job route in volo

Prima dello shed confronta sequence submitted/completed e rinvia se differiscono (`ds4_cuda.cu:37355-37375`); prima dei free sincronizza stream 0 (`ds4_cuda.cu:37385-37405`) e poi usa il release che cancella/joina il worker (`ds4_cuda.cu:37408-37428`, `ds4_cuda.cu:37707-37727`). Non e' una sorgente di doppio arm DOV nel tree verificato.
