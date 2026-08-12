# Audit 10 — contabilita' trasporto differita

Audit solo statico sul tree corrente. Sorgenti letti: `ds4-p4a/ds4.c`
SHA-256 `2F4555965716ADB494496E3D4EB6BF5FA1769D36BAB3527A37CEC63C1E7CBF20`;
`ds4-p4a/ds4_cuda.cu`
SHA-256 `F0DD5CFC6E001A61E818F8569E74E9AD07D536C55108418FEF7851712224BA36`.
Le severita' sotto riguardano l'affidabilita' della misura/attribuzione del
transport ledger; non implicano corruzione dei tensori serviti al modello.

## (1) BUG

### BUG-1 — ALTA — teardown/shed puo' perdere un batch DOV gia' provato completo

**Prova.** Lo stato DOV contiene `transport_deferred` separato da
`armed_generation`/timestamp (`ds4-p4a/ds4_cuda.cu:37471-37499`). Il distruttore
degli eventi azzera `armed_generation`, `armed_ns`, `complete_ns` e lo stato
consumer, ma non ritira ne' azzera `transport_deferred`
(`ds4-p4a/ds4_cuda.cu:37540-37553`). Il release della cache sincronizza
esplicitamente l'upload stream e poi chiama proprio quel distruttore
(`ds4-p4a/ds4_cuda.cu:37725-37735`), senza chiamare
`cuda_moe_drain_overlap4_retire`. Quindi la prova positiva esiste, ma il ledger
non la usa. Al prossimo defer nello stesso epoch, il fail-safe vede ancora
`pending->active` e lo chiude con `drain_ok=0`
(`ds4-p4a/ds4_cuda.cu:28565-28587`): byte omessi e `complete=0`
(`ds4-p4a/ds4_cuda.cu:28530-28534`).

**Scenario concreto.** Input/stato: `DS4_CUDA_TRANSPORT_LEDGER=1`,
`DS4_CUDA_DRAIN_OVERLAP4=1`, `DS4_CUDA_PIN_BACKBONE=1`; una route ha armato
DOV e il worker ha gia' pubblicato `route_completed`, ma il poll non ha ancora
ritirato il batch. Lo shed PIN controlla soltanto
`route_submitted_sequence == route_completed_sequence`
(`ds4-p4a/ds4_cuda.cu:37355-37375`), sincronizza stream 0 e invoca il release
(`ds4-p4a/ds4_cuda.cu:37389-37414`). Esito sbagliato: un H2D riuscito viene
omesso; al successivo arm il ledger diventa incompleto e, se quella coppia
ricompare, puo' risultare `first_touch` nonostante un H2D riuscito precedente.
Se non arriva un altro arm prima del report, resta invece il BUG-3.

### BUG-2 — MEDIA — cancel dopo l'arm non ha una transizione di ledger

**Prova.** `cuda_moe_route_worker_cancel_and_join` imposta `route_stop`, joina
il worker e, con staged-KV attivo, prova la quiescenza dell'upload stream, ma
non committa, non scarta e non azzera il batch differito
(`ds4-p4a/ds4_cuda.cu:31748-31805`). Il solo poll che potrebbe ritirarlo gira
dentro il `while (!route_stop)` del worker
(`ds4-p4a/ds4_cuda.cu:42443-42450`), e l'uscita dal ciclo ritorna senza cleanup
DOV (`ds4-p4a/ds4_cuda.cu:43288-43296`). Un errore del fence consumer chiama
esattamente cancel+invalidate (`ds4-p4a/ds4_cuda.cu:48071-48087`; nel ramo
split `ds4-p4a/ds4_cuda.cu:49846-49873`); l'invalidate non tocca il sidecar DOV
(`ds4-p4a/ds4_cuda.cu:37267-37335`).

**Scenario concreto.** Input/stato: DOV e ledger attivi; generazione N armata,
batch pendente; il consumer fallisce il `cudaStreamWaitEvent` oppure un altro
watchdog cancella il worker prima della sua prossima iterazione idle. Esito
sbagliato: lo slot non viene ne' committato ne' scartato al cancel; resta
orfano. Puo' essere committato piu' tardi da un worker respawnato se l'epoch e'
ancora lo stesso, scartato dal cambio d'epoch, oppure convertito in omissione
dal fail-safe di BUG-1. La contabilita' dipende quindi dal lifecycle successivo,
non dall'esito gia' provato del batch.

**Risposta (a).** Un cancel prima dell'arm non crea un pendente; inoltre il
claim riuscito di N ritira il pendente di N-1 prima di servire N
(`ds4-p4a/ds4_cuda.cu:42501-42510`). Un cancel *dopo* l'arm, invece, non decide
il pendente: nella finestra sopra resta orfano.

### BUG-3 — MEDIA — `final ledger_complete=1` puo' omettere il batch di coda

**Prova.** Il defer lascia aperto `h2d_active_batches` e non abbassa
`complete` (`ds4-p4a/ds4_cuda.cu:28565-28588`). Lo snapshot finale, se trova
batch attivi, aggiunge soltanto l'intervallo fino all'istante del report ma
copia `complete` senza qualificare il pending (`ds4-p4a/ds4_cuda.cu:28625-28650`).
`ds4_transport_request_end` stampa subito `final` e poi disarma, senza retire o
test dello slot pendente (`ds4-p4a/ds4_cuda.cu:28710-28717`); il lifecycle
CUDA lo chiama senza drenare DOV (`ds4-p4a/ds4_cuda.cu:31101-31129`).
`finish_deferred` non controlla `armed`, percio' un retire tardivo nello stesso
epoch puo' anche mutare i contatori *dopo* la riga finale, ormai invisibilmente
(`ds4-p4a/ds4_cuda.cu:28505-28518`).

**Scenario concreto.** Input/stato: ultimo layer/token della richiesta con un
batch DOV armato; il thread decode arriva al request-end prima del poll idle.
Esito sbagliato: `h2d_bytes_total`, `first_touch_bytes` o `repeat_h2d_bytes`
mancano fino a sei esperti, ma la riga puo' dichiarare `ledger_complete=1`.
Se l'H2D finisce dopo il report, anche `h2d_active_ms` e' troncato; se era gia'
finito ma non osservato, lo stesso campo e' invece gonfiato fino al report.

### BUG-4 — BASSA — `pcie_busy_pct` non e' occupazione fisica del link

**Prova.** La finestra parte prima della chiamata che accoda la prima copia
(`ds4-p4a/ds4_cuda.cu:41973-41999`; percorso transiente
`ds4-p4a/ds4_cuda.cu:42150-42176`) e termina quando il worker *osserva* la
quiescenza dell'intero `route_upload_stream`
(`ds4-p4a/ds4_cuda.cu:37589-37613`). Sul medesimo stream sono accodati anche
i kernel publish (`ds4-p4a/ds4_cuda.cu:39968-39992`), flushati prima dell'arm
(`ds4-p4a/ds4_cuda.cu:42305-42317`); l'arm registra l'evento soltanto dopo
l'ultimo publish (`ds4-p4a/ds4_cuda.cu:40695-40710`).
Il report chiama comunque il rapporto fra questa finestra e il wall time
`pcie_busy_pct` (`ds4-p4a/ds4_cuda.cu:28659-28683`).

**Scenario concreto.** Input/stato: decode orchestration-bound, worker
deschedulato dopo che l'upload e' fisicamente finito. Esito sbagliato:
`pcie_busy_pct` sovrastima sistematicamente il tempo H2D per enqueue,
publish e lag di osservazione. Il solo batch di coda di BUG-3 puo' invece
sottostimare se il trasferimento e' ancora realmente in volo al `final`.
Quindi, sotto DOV, il bias dei batch chiusi e' verso l'alto; sul tail non ha
segno garantito.

## (2) INTERFERENZE FRA LEVE

### `DRAIN_OVERLAP4` + `PIN_BACKBONE` + transport ledger — combinazione da vietare per misure ledger

**Meccanismo.** PIN puo' cedere lo slab quando il job host e' `completed`, stato
che sotto DOV non implica ancora retire del ledger
(`ds4-p4a/ds4_cuda.cu:37355-37375`). Lo shed sincronizza davvero stream 0 e
poi rilascia la cache (`ds4-p4a/ds4_cuda.cu:37389-37414`), ma il release perde
il raccordo col pendente come in BUG-1 (`ds4-p4a/ds4_cuda.cu:37725-37735`).

**Manifestazione a banco.** Una riga `PIN degrade result=ok` seguita, al primo
nuovo H2D DOV, da `ledger_complete=0`; `h2d_bytes_total` inferiore al controllo
nonostante upload riusciti; possibile spostamento da `repeat_h2d_bytes` a
`first_touch_bytes`. I contatori PIN che identificano l'evento sono aggiornati
nello shed (`ds4-p4a/ds4_cuda.cu:37431-37441`).

**Guardia suggerita.** Per l'A/B di contabilita' vietare questa tripla:
`DS4_CUDA_PIN_BACKBONE=0`, oppure scartare integralmente ogni run con
`pin_expert_cache_sheds>0`. La sola uguaglianza submitted/completed non e' una
guardia sufficiente sotto DOV (`ds4-p4a/ds4_cuda.cu:37355-37365`).

### `DRAIN_OVERLAP4` + `INDEXER_HOST_ZEROCOPY` + transport ledger — denominatore PCIe incompleto

**Meccanismo.** Il ledger dichiara fuori dominio le letture GPU da memoria
host-mapped (`ds4-p4a/ds4_cuda.cu:28196-28201`). INDEXERZC serve precisamente
i pesi tramite `cudaHostAllocMapped`/UVA, senza `cudaMemcpy` per token
(`ds4-p4a/ds4_cuda.cu:3907-3914`), e dichiara che i kernel toccano il 100% dei
byte pinnati per token (`ds4-p4a/ds4_cuda.cu:3989-4004`). Quel traffico compete
sullo stesso link con gli H2D expert, ma non entra in `h2d_bytes_total`.

**Manifestazione a banco.** `h2d_active_ms` degli esperti puo' crescere per
contesa, mentre `h2d_bytes_total` non include i 363.331.584 B/token
`predicted_touch_per_token`; il throughput implicito byte/attivo e
`pcie_busy_pct` non rappresentano il tubo PCIe totale. La riga `[indexer-zc]
active=1 ... predicted_touch_per_token=...` rende riconoscibile il caso
(`ds4-p4a/ds4_cuda.cu:3993-4004`).

**Guardia suggerita.** Non usare i campi del transport ledger per confrontare
la banda PCIe totale con INDEXERZC acceso. Per caratterizzare ledgerfix,
tenere `DS4_CUDA_INDEXER_HOST_ZEROCOPY=0`; altrimenti giudicare il link solo
con un contatore PCIe esterno e trattare il ledger come traffico expert-only.

### `DRAIN_OVERLAP4` + `CPU_SHARED_EXPERT` senza dedicated, oppure + `NEXTN_CPU_DRAFTER` — bias del tempo di osservazione

**Meccanismo.** Il retire idle dipende da quando il route worker torna a fare
`cudaStreamQuery` (`ds4-p4a/ds4_cuda.cu:37589-37613`). Shared1 non-dedicated
esegue entrambi i matvec sulla pool g132 sotto il mutex comune
(`ds4-p4a/ds4.c:11694-11721`); il drafter instrada i propri job pesanti sulla
stessa pool (`ds4-p4a/ds4.c:801-809`, `ds4-p4a/ds4.c:11300-11310`). Queste
leve non duplicano i batch, ma cambiano scheduling CPU e durata decode: il lag
fra completamento fisico e osservazione DOV non e' piu' confrontabile.

**Manifestazione a banco.** A byte H2D e miss simili, aumentano
`h2d_active_ms`/`drain_overlap_ms`; `pcie_busy_pct` puo' anche scendere se il
denominatore `decode_ms` cresce piu' del numeratore
(`ds4-p4a/ds4_cuda.cu:28659-28683`). Con shared1 e NextN insieme, le submit
g132 serializzano sul medesimo mutex, quindi il sintomo puo' essere a gradini,
non proporzionale ai byte (`ds4-p4a/ds4.c:11284-11310`).

**Guardia suggerita.** Per un A/B sul tempo DOV, spegnere drafter/shared CPU,
oppure usare `DS4_CPU_SHARED_EXPERT_DEDICATED=N` con affinita' verificata:
quel ramo non usa g132 e lascia il thread submitter in attesa su condvar
(`ds4-p4a/ds4.c:11314-11342`, `ds4-p4a/ds4.c:11694-11710`). Non confrontare
`pcie_busy_pct` fra assetti CPU diversi come se fosse una misura hardware.

### `DRAIN_OVERLAP4` + `G73_OPEN=0` + qualunque abort di route — run non valido per il ledger

**Meccanismo.** Una route fallita ritorna NULL dopo scoped/full invalidate
(`ds4-p4a/ds4_cuda.cu:48046-48069`) e il ramo non-G73 rifiuta il fallback
salvo lo stato speciale PIN shed (`ds4-p4a/ds4_cuda.cu:48488-48512`). Il
claim di una nuova generazione ritira prima il pendente precedente
(`ds4-p4a/ds4_cuda.cu:42501-42510`), quindi un normale fallimento *pre-arm*
non lascia il batch precedente. Un abort *post-arm* (per esempio errore del
fence) ricade invece in BUG-2/BUG-3.

**Manifestazione a banco.** `route_worker_errors`/riga `observed failure`,
decode terminato anticipatamente, riga `final` con tail mancante e
potenzialmente `ledger_complete=1`; alla richiesta successiva i byte non
ricompaiono per effetto della guardia d'epoca.

**Guardia suggerita.** Scartare ogni run con route failure, cancel, quarantine
o decode abort, indipendentemente da `ledger_complete`. ROUTEFIX puo' evitare
la specifica classe snapshot-mismatch, ma non rende valido un report chiuso
dopo un cancel post-arm.

## (3) ESCLUSIONI

### Nessun doppio conteggio H2D dal retry recoverable della stessa richiesta

Il watchdog recoverable cancella soltanto il `pread`, senza fermare il worker
(`ds4-p4a/ds4_cuda.cu:31440-31459`). Il fallback rilegge soltanto i tensori non
completati secondo `stage_done` (`ds4-p4a/ds4_cuda.cu:31462-31562`); il flusso
torna poi allo stesso punto e imposta `read_result=1` una sola volta
(`ds4-p4a/ds4_cuda.cu:41731-41764`). Il batch H2D viene aperto e appeso solo
piu' avanti, quando la singola copia e' accodata con successo
(`ds4-p4a/ds4_cuda.cu:41973-42030`; percorso transiente
`ds4-p4a/ds4_cuda.cu:42150-42207`). Non esiste quindi un secondo append H2D
per i byte riletti. Le riletture parziali possono aumentare correttamente i
byte file realmente letti, perche' `cuda_moe_transient_pread_chunked` registra
ogni `got` effettivo (`ds4-p4a/ds4_cuda.cu:31372-31414`).

**Risposta (b):** doppio conteggio H2D non trovato. Il retry avviene prima
dell'unico enqueue/append; il solo traffico duplicabile e' file I/O realmente
rieseguito.

### La guardia d'epoca impedisce la contaminazione cross-request

Ogni `clear()` azzera tabella, finestre e contatori e incrementa `epoch` sotto
lo stesso lock (`ds4-p4a/ds4_cuda.cu:28591-28614`). Il retire differito prende
quel lock e, su epoch diverso, azzera soltanto la copia pending senza toccare
il nuovo ledger (`ds4-p4a/ds4_cuda.cu:28505-28518`). Il vero request-begin
chiama il clear prima del lavoro della nuova richiesta
(`ds4-p4a/ds4_cuda.cu:16224-16238`). Non c'e' una finestra TOCTOU fra confronto
e commit.

**Risposta (c):** il pendente della richiesta abortita puo' restare orfano e
falsare il suo vecchio `final`, ma non contamina byte, pair counters o
first/repeat della richiesta successiva. Al retire/fail-safe successivo viene
scartato per epoch mismatch.

### Ordine e unicita' del commit nel percorso DOV normale sono sani

Il poll non ritira due volte: dopo il retire pubblica `complete_ns`
(`ds4-p4a/ds4_cuda.cu:37566-37586`) e sia poll sia claim-gate escono quando
`complete_ns != 0` (`ds4-p4a/ds4_cuda.cu:37595-37627`). Il retire azzera il
batch dopo il commit (`ds4-p4a/ds4_cuda.cu:28559-28562`). Inoltre il claim di
N+1 deve riuscire e ritira N prima del servizio/degli enqueue di N+1
(`ds4-p4a/ds4_cuda.cu:42501-42518`): i commit riusciti restano in ordine di
generazione.

### `first_touch`/`repeat_h2d` sono coerenti nel differito sano

La classificazione avviene nel commit, sotto il lock: `repeat` deriva dal
contatore per-pair, poi lo stesso commit incrementa `h2d_transfers` e somma i
byte nella classe scelta (`ds4-p4a/ds4_cuda.cu:28535-28559`). Poiche' il punto
precedente prova l'ordine dei commit, un batch precedente non puo' essere
classificato dopo il successivo. Un batch con errore stream viene omesso e
marca `complete=0`, senza fingere che una copia parziale sia riuscita
(`ds4-p4a/ds4_cuda.cu:28519-28534`).

**Risposta (e):** coerenza confermata nel percorso normale e nel retry
recoverable. Si rompe solo per omissione nei BUG-1/BUG-3: la copia successiva
puo' apparire `first_touch` perche' quella riuscita ma orfana non ha mai
incrementato il pair counter.

### Route snapshot resync non scavalca il retire della generazione precedente

Il worker esegue claim e `retire_at_claim` prima del precheck della richiesta
nuova (`ds4-p4a/ds4_cuda.cu:42501-42530`); il ramo ROUTEFIX resync/reject viene
valutato dopo (`ds4-p4a/ds4_cuda.cu:42570-42618`). Quindi un
`invalid-compose-snapshot` non puo' lasciare non ritirato il batch della
generazione precedente, e un resync riuscito non puo' provocarne un doppio
commit.

### All-hit/zero-copy e DOV spento non fabbricano batch

`ds4_transport_h2d_batch_defer` e' no-op quando il batch non e' attivo
(`ds4-p4a/ds4_cuda.cu:28569-28574`); `batch_begin` non si arma se ledger o
richiesta sono disarmati (`ds4-p4a/ds4_cuda.cu:28377-28390`). Il ramo DOV
chiama defer solo dopo un arm riuscito (`ds4-p4a/ds4_cuda.cu:42323-42352`;
non-ENFORCE `ds4-p4a/ds4_cuda.cu:43117-43153`). A DOV spento resta il finish
bloccante, che chiude e classifica nella stessa chiamata
(`ds4-p4a/ds4_cuda.cu:28419-28467`).
