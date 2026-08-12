# FASE A+B — L'invalidazione totale della cache expert: invariante, proporzionalita', innesti reali

Data: 2026-07-29. Sorgente analizzato: `ds4-p4a/ds4_cuda.cu`
SHA-256 `c110c5603a417d7da9cf4a75f1f5168d170fff1e26827746a252c4e17d52386f`
(52.296 righe; e' il tree con drain3-strumentazione gia' applicata — l'hash
NON coincide con quello delle due autopsie, `5688dcd3...`, perche' il
contatore `cache_invalidates` e la voce `deadline_slack` sono gia' dentro;
le righe citate sotto sono di QUESTO file. `ds4-p4a/` e' untracked in git:
HEAD `b024b8e` non contiene il file, quindi l'identita' del base e' l'hash
qui sopra, non un blob).
Nessuna compilazione, nessun server, nessun accesso a `D:\`.
Fonti lette per intero: `.microbench/drain3/DEADLOCK.md`,
`.microbench/drain3x/DEADLOCK.md`, piu' i percorsi citati con file:riga.

## Verdetto in dieci righe

1. L'invalidazione totale (`cuda_moe_expert_cache_invalidate`, :36621) ha
   **16 siti di chiamata**, non uno: 2 di inizializzazione, 5 sul percorso
   selected-load del decode, 2 nel worker, 7 nel consumer (tabella in
   sez. 1). Il contatore drain3 li somma tutti senza distinguerli.
2. **Le due invalidazioni del run sano NON sono la tassa del percorso di
   decode**: sono con ogni probabilita' i due reset di INIZIALIZZAZIONE
   (`set-model-file` all'apertura dell'engine, ds4.c:19953 → :16987, e la
   CREAZIONE della cache, :38471), che buttano **zero voci** perche' la
   cache in quell'istante e' vuota o non esiste ancora (sez. 4). Il dato
   K2 (`cache_invalidates=1` a zero passi di decode) discrimina: a quel
   punto era passato solo `set-model-file`. La tassa ordinaria in decode
   misurata finora e' **ZERO**, non due.
3. L'invariante protetto dal reset totale esiste ed e' ricostruito con
   file:riga (sez. 2): nessuna voce della mappa device puo' puntare a uno
   slot i cui byte non sono i pesi completi e correnti di quella coppia
   (layer,expert). Il codice lo documenta esplicitamente (:31104-31108).
4. L'invariante **puo'** essere protetto in modo proporzionato: il registro
   per-richiesta `promotion_reservations` contiene gia' esattamente le voci
   compromesse (≤6 slot, ≤12 chiavi di mappa su ~140 slot e 11.008 chiavi);
   la condizione di liceita' e' la quiescenza provata dello stream di
   upload, che nel caso dominante di fallimento (pread-timeout con drain
   riuscito) e' gia' dimostrata dal drain stesso (sez. 3).
5. Il reset totale resta necessario e va conservato in quattro classi di
   siti: watchdog con worker ucciso (il registro vive sullo stack del
   worker morto), percorso legacy non-ENFORCE (nessun registro vittime),
   drain non quiescibile, errori CUDA del selected-load (sez. 3.4).
6. Consegnata `invalidate.patch` (30 hunk, +265/−31, `git apply --check`
   verde): rollback scopato opt-in dietro `DS4_CUDA_SCOPED_INVALIDATE=1`
   nella forma provata del parametro di template sul route worker, piu'
   telemetria per-evento e per-sito che rende ogni invalidazione
   giudicabile da sola (sez. 5). A flag spento le specializzazioni
   selezionate sono le stesse istanze di oggi.
7. Due difetti PREESISTENTI documentati e NON toccati dalla patch: (a) il
   reset totale su drain fallito corre una gara con le publish ancora in
   volo (cudaMemset sul legacy stream non ordina rispetto a uno stream
   non-blocking: una voce stantia puo' riapparire DOPO il reset); (b) il
   percorso `route-failure-invalidate` con timeout del drain di
   completamento non invalida NULLA e il respawn riconsegna una cache
   potenzialmente strappata (sez. 2.4). Sono i buchi dell'invariante di
   oggi, non della leva.

---

## 1. L'inventario completo degli innesti (il "chi" delle invalidazioni)

`cuda_moe_expert_cache_invalidate(void)` — :36621-36666. Effetto: tutti gli
slot → EMPTY (con demotion tier dei VALID), mappa host tutta −1, mappa
device tutta −1 via `cudaMemset` sincrona (:36645-36648), azzeramento di
`route_ready_host`/`route_failed_host`/`route_request_host`, hit-mask, esiti
G73, `tick` e `count`. Chiamanti (grep esaustivo, 16 siti):

| # | riga | sito | quando scatta | riga stderr adiacente | classe |
|---|---|---|---|---|---|
| 1 | :16987 | `ds4_gpu_set_model_file` (da ds4.c:19953, apertura engine) | sempre, una volta al load del modello | nessuna | **init** |
| 2 | :38471 | `cuda_moe_expert_cache_prepare`, blocco di creazione | alla CREAZIONE della cache (v. sez. 4: con `DS4_CUDA_EXPERT_CACHE_GROW=1` avviene a decode-start, non in prefill) | `[expert-cache-grow] mode=two-phase result=ok` al sito grow (:30468) | **init** |
| 3 | :39404 | `cuda_moe_tiering_finish_vram_reservations`, `!transfer_ok \|\| !commit_on_success`, `count>0` | fallimento richiesta ENFORCE con promozioni prenotate | `[tiering-enforce] result=failed` (:40952) + `route worker failed` (:41673) | fallimento worker |
| 4 | :41654 | worker, percorso inline non-ENFORCE, `ok=0 && admitted>0` | fallimento richiesta con tiering OBSERVE/OFF | `route worker failed` | fallimento worker |
| 5-9 | :44394, :44443, :44480, :44510, :44596 | selected-load compatto (decode thread) | fallimenti copia spex / fill / D2D cache / drain upload / **upload mappa host→device (:44596, SILENZIOSO)** | varie; :44596 nessuna | fallimento decode |
| 10 | :46287 | consumer, resolver NotReady (solo G73) | deadline resolver | `resolver sync failed` | watchdog (post cancel_and_join) |
| 11 | :46328 | consumer, worker perso | `route_stop`/`route_worker_failed` durante l'attesa | `resolver lost worker` | watchdog |
| 12 | :46371 | consumer, stallo del recupero FIX-B | dopo deadline assoluta + recupero fallito | `reached absolute deadline` | watchdog |
| 13 | :46391 | consumer, deadline assoluta transiente | cancellazione per ripiego non disponibile | idem | watchdog |
| 14 | :46420 | consumer, stallo lettura transiente | nessun progresso byte entro la finestra | `transient route read timed out` | watchdog |
| 15 | :46430 | consumer, starvation 5 s | worker vivo ma fermo | `route worker starved` | watchdog |
| 16 | :46476 | consumer, `route_failed_host == sequence` | **ogni richiesta fallita**, worker vivo | `observed failure; falling back` (:46463) | fallimento consumer |

Tre osservazioni strutturali:

- **Ogni fallimento ENFORCE con promozioni invalida DUE volte**: il worker a
  :39404 e poi il consumer a :46476 sulla stessa sequence. Nel contatore
  drain3 un solo episodio vale 2. Nella forma estrema il conto sale ancora:
  se a fallire e' il drain ANTICIPATO (:40212, `commit_on_success=1`),
  l'invalidate parte li' dentro, il loop rompe con
  `resident-copy-before-transient`, e il finish FINALE (:40926) riesegue
  refund+invalidate sulle stesse reservation (`admitted_count` non viene
  azzerato su quel ramo): **tre tick per un solo episodio**, piu' un
  doppio refund dei budget di policy (anomalia preesistente, bounded dal
  cap, documentata qui e non corretta di nascosto).
- I watchdog (10-15) invalidano SOLO se `cancel_and_join` riesce, cioe' a
  stream di upload quiescente o safe-leak (in quel caso niente invalidate:
  cache in quarantena permanente). Il fallimento "ordinario" (16) invece
  invalida col worker VIVO, gate g133 permettendo.
- L'unico sito di fallimento senza alcuna riga stderr propria e' :44596
  (upload della mappa host→device del selected-load). In un run "senza
  errori a log" e' l'unico candidato di fallimento veramente silenzioso.

## 2. FASE A.1 — L'invariante che il reset totale protegge

### 2.1 Le tre viste che devono concordare

1. `slots[]` (host): stato/chiave/(layer,expert) per slot (:28148-28156).
2. `host_slot_by_layer_expert` (host): (layer,expert) → slot.
3. `device_slot_by_layer_expert` (device): (layer,expert) → slot, letta dal
   **resolver kernel** (`moe_resolve_resident_routes_kernel`, :25684) per
   classificare hit/miss e costruire `route_ptrs` che i consumer kernel
   dereferenziano.

**INVARIANTE**: per ogni voce device (L,E)→S visibile al resolver, lo slot S
contiene i byte COMPLETI e CORRENTI dell'esperto (L,E), e le viste host
concordano (slots[S] VALID con quella chiave; mappa host [L,E]=S; `count`
coerente). Una voce che lo viola non produce un errore: produce un **HIT su
pesi sbagliati o parziali**, cioe' corruzione numerica silenziosa del
forward pass.

### 2.2 Perche' una richiesta fallita puo' violarlo

Il servizio di una richiesta e' una transazione distribuita per ogni
esperto promosso (percorso ENFORCE, :40520-40716):

1. host: slot reclamato, `entry.state = LOADING` (:40563), chiave/(L,E)
   sovrascritte (:40707-40712); la vittima eventualmente sfrattata e'
   registrata nella reservation (:40548-40562);
2. stream upload (non-blocking, :38257 circa): H2D asincrono dei tre
   tensori (:40584-40616);
3. stesso stream, DOPO l'H2D: publish kernel che muta la mappa device
   ({vecchia chiave→−1 se ancora ==S, nuova chiave→S}, :25918-25931) — o
   append a un batch il cui flush avviene A FINE richiesta (:40907-40919),
   e nel demand pipeline anche gli H2D sono differiti al flush;
4. host, SOLO dopo drain riuscito: commit (`slots→VALID`, mappa host,
   `count`, :39279-39330 e :39407-39411).

Su un fallimento a meta' (pread-timeout, copy/publish-launch, drain), la
transazione resta strappata. Il caso velenoso e' la **vittima**: l'ordine di
stream garantisce publish-dopo-H2D, quindi fra l'H2D eseguito e la publish
non eseguita (loop rotto prima dell'enqueue, o batch mai flushato su `!ok`)
la mappa device dice ancora (L_v,E_v)→S mentre i byte di S sono gia'
(parzialmente) quelli del candidato. Un resolver successivo servirebbe la
vittima da byte altrui. Il commento di refund lo dice testualmente: "Its
device slot may be partially overwritten; failure rollback therefore
restores the candidate and coherently demotes the no-longer-valid victim
before whole-cache invalidation" (:39365-39368).

E il vincolo di liceita' di QUALSIASI riparazione e' anch'esso scritto nel
sorgente: "A joined host worker is not a drained CUDA producer:
route_upload_stream is non-blocking, so neither the default stream nor
thread join orders its old H2D copies/publication kernels. [...] refuse
both invalidation and respawn until that stream is quiescent; quarantine
instead" (:31104-31108, testa di `cuda_moe_route_upload_stream_quiesce`).

Quindi: **il reset totale non e' un capriccio**. E' il modo brutale ma
corretto (a stream fermo) di ristabilire l'invariante quando l'host non sa
QUALI voci della mappa device siano compromesse.

### 2.3 Perche' oggi butta TUTTO invece delle sole voci compromesse

Perche' i siti che invalidano non hanno (o non usano) l'informazione:

- il **consumer** (:46476) non puo' averla: `admitted[]` e
  `promotion_reservations[]` sono variabili di stack del worker
  (:39854-39856) — il thread di decode letteralmente non le vede;
- il **worker** (:39404) ce l'ha in mano — le reservation gli arrivano come
  parametro — e le usa gia' per il rollback COERENTE dello stato tier
  (refund, :39345-39374), ma subito dopo butta l'indice intero. Il registro
  per il rollback proporzionato **esiste gia'**; non e' mai stato collegato
  all'invalidazione.

### 2.4 Dove il reset totale gia' oggi NON basta (onesta' sull'invariante)

Due corner preesistenti, da conoscere per giudicare la leva (la patch non
li tocca, non li peggiora e li rende visibili in telemetria):

- **Gara del reset su drain fallito**: a :39404 l'invalidate puo' partire
  con lo stream di upload ancora in moto (G73 aperto: il drain torna
  `cudaErrorNotReady` alla deadline, :34005-34026). La `cudaMemset` della
  mappa device viaggia sul legacy default stream, che NON ordina rispetto a
  uno stream `cudaStreamNonBlocking`: una publish ritardataria puo'
  eseguire DOPO il memset e ripiantare una voce (L,E)→S su uno slot ormai
  EMPTY e riassegnabile. Con G73_OPEN=0 (assetto di campagna) il drain
  polla senza deadline (:34012 non scatta mai), quindi il caso non si
  presenta: e' un rischio del solo assetto open.
- **Fallimento che non invalida nulla**: a :46471-46474, con policy g133
  condivisa attiva e `cuda_moe_route_worker_drain_completed` scaduto (5 s),
  il consumer torna NULL SENZA invalidare; `fail_closed`+`cancel_and_join`
  uccidono il worker e il prepare successivo lo **respawna sulla cache
  intatta** (:38018-38027) — intatta ma potenzialmente strappata dalla
  richiesta uccisa. E' il complementare del problema in esame: la punizione
  o e' collettiva o non c'e'.

## 3. FASE A.2 — La proporzionalita' e' possibile: perimetro e prova

### 3.1 L'insieme compromesso e' esattamente il registro della richiesta

Per una richiesta ENFORCE fallita, le uniche voci che POSSONO violare
l'invariante sono quelle di `promotion_reservations[0..admitted_count)`
(≤ CUDA_MOE_ROUTE_COUNT = 6, :27729):

- lo **slot prenotato** `reservation.cache_slot` (byte eventualmente
  sovrascritti a meta');
- la **chiave candidata** (candidate_layer, candidate_expert): publish
  eventualmente eseguita → voce device −1 oppure →S, mai un terzo valore
  (il candidato non era residente altrove: "vram-map-miss", :40144-40151,
  rifiuta la doppia residenza);
- la **chiave vittima** (victim_layer, victim_expert, se victim_valid):
  publish eventualmente NON eseguita → voce device →S stantia, oppure gia'
  −1.

Tutto il resto della cache e' intatto **per costruzione**: `pick_vram_slot`
reclama solo gli slot del registro (`claimed[]`), gli hit della richiesta
sono protetti dallo sfratto (claim degli hit_slots, :41283-41297), le
richieste sono serializzate dalla mailbox a generazioni (claim fail-closed,
:30953-31071), e dentro una stessa richiesta candidato e vittima non
possono coincidere (un candidato e' per definizione un MISS, quindi non
residente, quindi non puo' essere vittima; le vittime occupano slot
distinti quindi sono chiavi distinte).

Le rotte TRANSIENTI (serve SSD senza promozione) non entrano nel registro e
non toccano ne' slot ne' mappe: scrivono i buffer per-richiesta e
`route_ptrs` via `moe_publish_transient_route_kernel` (:40848-40858), stato
che il resolver della richiesta successiva riscrive. Un fallimento con
`admitted_count == 0` — il pread-timeout puro, cioe' l'innesco del livelock
— **non ha compromesso nulla**: oggi il consumer butta ~140 slot per zero
voci sporche.

### 3.2 La precondizione: quiescenza provata dello stream

Il rollback mirato della mappa device e' lecito solo a stream di upload
quieto (sez. 2.2). Tre casi:

- **transfer_ok=1, commit_on_success=0** (il fallimento e' del loop, il
  drain e' riuscito — include pread-timeout, publish-launch, batch-flush):
  la quiescenza e' GIA' PROVATA dal drain stesso. E' il caso dominante e
  quello del livelock.
- **transfer_ok=0 con drain a deadline (solo G73 aperto)**: quiescenza non
  provata → si ri-polla `cudaStreamQuery` con lo stesso bound di 5 s di
  `cancel_and_join`; se non si dimostra → **reset totale come oggi**.
- **admitted_count==0**: niente da rollbackare, nessun requisito.

### 3.3 Il rollback mirato (cosa fa, voce per voce)

Per ogni reservation attiva: mappa host — azzera vittima e candidato se
puntano allo slot; mappa device — scrive −1 su ENTRAMBE le chiavi
(idempotente e corretto in ogni interleaving possibile della publish, vedi
3.1); slot — reset identico a quello del reset totale (EMPTY, chiave/eta'
azzerate); `count` — decrementato solo per le vittime valide (le sole voci
che erano contate); stato tier — GIA' ripristinato/demansionato da
`refund_failed_promotions`, che resta chiamata prima, nell'ordine di oggi.
Il tutto e' idempotente (il secondo passaggio del doppio-finish trova gli
slot gia' EMPTY e non riconta): il difetto preesistente del doppio refund
non viene amplificato.

### 3.4 Dove il reset totale RESTA necessario (e la patch lo conserva)

| sito | perche' proporzionato impossibile/ingiustificato |
|---|---|
| watchdog 10-15 | il worker e' stato ucciso: il registro era sul suo stack; nessuna vista affidabile di cosa fosse in volo |
| non-ENFORCE :41654 | il percorso inline non registra le vittime (aggiorna mappa host subito, :41586); costruire il registro li' = ristrutturare codice condiviso, la trappola che ha ucciso drain/drain2. La campagna gira ENFORCE |
| selected-load 5-9 | thread di decode, fallimenti CUDA-shaped, mappa host gia' mutata in loco; con F10 two-phase in prefill `cache==NULL` e i siti non scattano comunque |
| init 1-2 | non sono invalidazioni: sono inizializzazioni (buttano 0 voci) |
| scoped non dimostrabile | quiescenza non provata o cudaMemcpy di riparazione fallita → fallback al reset totale identico a oggi |

## 4. FASE A.3 — Le due invalidazioni del run sano: due innesti DISTINTI, nessuno dei due e' il percorso dell'autopsia

### 4.1 Cosa dice il codice

- All'apertura dell'engine, PRIMA di qualunque prefill:
  `ds4_gpu_set_model_file` (ds4.c:19953) → invalidate a :16987. La cache
  non esiste ancora (`slots` vuoto, puntatori device NULL): il reset e' un
  no-op contabile. **+1 per ogni run, sempre.**
- La creazione della cache invalida a :38471, dentro il blocco one-time di
  `prepare`. QUANDO avviene dipende da `DS4_CUDA_EXPERT_CACHE_GROW`
  (:30117-30120):
  - **grow=1 (two-phase F10)**: durante il prefill `prepare` DIFFERISCE
    (cattura la geometria e torna NULL, :37879-37895 e :37965-37969); la
    creazione avviene a **decode-start**, dentro
    `ds4_gpu_vram_ledger_decode_start` (:30456-30484), dopo il rilascio
    dello scratch di prefill (`DS4_CUDA_RELEASE_PREFILL_SCRATCH`,
    :30404-30436) e la fotografia della VRAM libera. **+1 al confine
    prefill→decode, PRIMA del primo token.** La riga
    `[expert-cache-grow] mode=two-phase result=ok capacity=...` (:30468) e'
    la firma verificabile nei log gia' raccolti.
  - **grow assente**: la creazione avviene alla prima chiamata MoE del
    prefill (prepare da :44175/:46043). +1 durante il prefill.
  In entrambi i casi il reset avviene su una cache **appena allocata e
  vuota**: zero voci buttate, zero tempesta.

### 4.2 Lettura dei due dati misurati

- **K2_controllo, 0 passi di decode, `cache_invalidates=1`**: e' passato
  solo `set-model-file`. Coerente con grow=1 (creazione non ancora
  avvenuta: il campione e' stato preso prima di decode-start) o con un
  campione preso durante il puro caricamento. NON coerente con "creazione
  gia' avvenuta": avrebbe segnato 2.
- **K1_lane_kernel, 2250 token sani, `cache_invalidates=2` (riga finale,
  che e' CUMULATIVA — :4759-4760)**: set-model-file + creazione. **Zero
  invalidazioni durante i 2250 token di decode.**

L'ipotesi "una di avvio piu' una di decode" e' quindi da restringere: la
seconda avviene si' al confine del decode, ma e' la **creazione due-fasi
della cache** (un'inizializzazione legittima e, nel disegno attuale,
inevitabile), non un'invalidazione del percorso guardiano→route_failed→
consumer. Quel percorso stampa SEMPRE almeno `observed failure seq=...`
(:46463) piu' una riga worker (`route worker failed`, :41673): un run
"completato senza errori" con quelle righe assenti non lo ha attraversato.

### 4.3 Cosa resta non determinabile dalla lettura, e come la patch lo chiude

Dalla sola lettura non posso escludere che UNO dei due tick di K1 venga da
un sito di fallimento silenzioso (:44596 e' l'unico candidato) o che il
run K1 girasse senza grow con la creazione in prefill: i numeri combaciano
comunque. La discriminazione definitiva e' strumentale e la patch la rende
permanente: ogni evento ora stampa
`ds4: [cache-invalidate] scope=full site=<nome> valid_dropped=N loading_dropped=M`
(sotto `DS4_CUDA_WORKER_PROFILE`, lo stesso guardiano del contatore
drain3). Un run sano deve mostrare esattamente:
`site=set-model-file valid_dropped=0` + `site=expert-cache-prepare
valid_dropped=0`, e la riga `[worker-prof]` finale
`cache_invalidates_total=2 ... cache_full_valid_dropped=0`. Qualunque
scostamento ha nome e costo.

**Conseguenza per la lettura del contatore**: `cache_invalidates` da solo
NON e' la misura della tassa; la tassa e' `cache_full_valid_dropped` (voci
valide realmente buttate). Con i dati di stasera la tassa ordinaria del
decode e' zero e il meccanismo dell'autopsia resta un meccanismo **della
forma degradata**, non del regime sano — il che rafforza, non indebolisce,
il valore del rollback scopato: il suo teatro e' esattamente la tempesta.

## 5. FASE B — invalidate.patch

### 5.1 Perimetro e flag

`DS4_CUDA_SCOPED_INVALIDATE=1`, letto UNA volta in
`cuda_g73_route_dispatch_init` (la stessa cucitura di G73/G132). Il flag
seleziona `cuda_moe_route_worker<G73, G132, SCOPED=true>` →
`cuda_moe_tiering_enforce_request<G73, G132, SCOPED>` →
`cuda_moe_tiering_finish_vram_reservations<SCOPED>`: la forma di template
richiesta dal mandato. A flag spento il dispatch seleziona le STESSE
istanze `<G73, G132, false>` di oggi (parametro con default), dentro le
quali il ramo `if constexpr (SCOPED)` non esiste.

Cosa fa a flag acceso, solo su richiesta ENFORCE fallita:

1. `admitted_count == 0` → nessun rollback necessario; firma la sequence
   come "gia' ripulita" (`no-reservations`). **E' il caso del
   transient-io-timeout puro: da ~140 slot buttati a zero.**
2. `admitted_count > 0` → `cuda_moe_tiering_scoped_invalidate`: quiescenza
   (gia' provata da `transfer_ok`, altrimenti ri-poll bounded 5 s come
   cancel_and_join), poi rollback voce-per-voce del solo registro
   (sez. 3.3) e firma della sequence.
3. Il consumer, nel blocco che oggi esegue il reset totale (:46476),
   consuma la firma: se combacia, salta il reset (il rollback e' gia'
   avvenuto sul thread che possiede il registro). La firma
   (`g_moe_route_failure_scoped_sequence`, atomica file-scope, release →
   acquire attraverso il handshake ready/failed gia' esistente) e' scritta
   SOLO dalle istanze SCOPED=true: a flag spento il ramo del consumer e'
   morto.
4. Quiescenza non dimostrabile o cudaMemcpy di riparazione fallita →
   fallback esplicito al reset totale (`worker-enforce-failure-scoped-
   fallback`): il comportamento di oggi e' il pavimento, mai rimosso.

### 5.2 L'invariante della Fase A, preservato — elenco puntuale

- Voci device del candidato e della vittima → −1 in OGNI interleaving
  possibile della publish (dimostrazione in 3.1: per ciascuna chiave i
  valori possibili sono solo {−1, S}); scritture eseguite esclusivamente a
  stream provato quieto (precondizione 3.2), quindi nessuna publish puo'
  ripiantarle dopo.
- Slot del registro → EMPTY: mai piu' serviti come hit finche' una nuova
  ammissione non li ricommitta con drain riuscito.
- Viste host (mappa, slots[], `count`) riallineate nello stesso passaggio,
  sul thread worker, PRIMA di `route_failed_host = sequence`: quando il
  consumer decide, lo stato e' gia' coerente (stesso ordine
  release/acquire del protocollo esistente).
- Stato tier: invariato rispetto a oggi (refund resta chiamato per primo).
- Tutto cio' che non e' nel registro non viene toccato — ed e' esattamente
  cio' che la richiesta fallita non ha toccato (3.1).
- I percorsi in cui la prova non e' costruibile conservano il reset totale
  (3.4): la patch non introduce NESSUN caso in cui l'invariante sia
  protetto meno di oggi.

### 5.3 Neutralita' a flag spento — cosa cambia e cosa no

- **Percorso caldo (layer sani): zero istruzioni nuove.** Il check del
  consumer sta DENTRO il blocco `route_failed_host == sequence`, che un
  layer sano non esegue mai; il worker OFF e' la stessa specializzazione
  di oggi; la getenv nuova gira una volta all'init.
- **Nessun cambio di layout condiviso**: `cuda_moe_expert_cache` intatta
  (la lezione di drain.patch); lo stato nuovo e' una singola atomica
  file-scope.
- Deltas accettati della classe-ricompilazione (gli stessi che drain3 ha
  stabilito come canale legittimo): simboli in piu' nel testo (le istanze
  SCOPED=true esistono nel binario ma nessun puntatore le seleziona a flag
  spento — identico al G73 di oggi), slittamento .bss, e telemetria sotto
  `DS4_CUDA_WORKER_PROFILE`: la riga `[worker-prof]` estende la coda in
  `cache_invalidates_total=` (rinominata dal mandato) +
  `cache_invalidates_scoped=` + `cache_scoped_entries_dropped=` +
  `cache_full_valid_dropped=`, e ogni invalidazione stampa la riga
  per-evento `[cache-invalidate] scope=... site=...`. Chi parsa la riga
  drain3 di ieri deve aggiornare il nome del campo: e' il costo esplicito
  della richiesta del mandato.
- I 16 siti ora passano un tag `site` alla funzione (parametro nuovo,
  percorso freddo): e' l'inventario della sez. 1 reso eseguibile.
- **Non toccati**: ramo split col fix Fable, kernel row-parallel G132,
  ammissione/residenza/soglie/dimensionamento, Q1, le cartelle drain3/
  drain3x/lane*/backbone*.

### 5.4 Telemetria (il metro del giudizio)

- `cache_invalidates_total` — reset totali (per sito, via righe evento).
- `cache_invalidates_scoped` — eventi di rollback mirato.
- `cache_scoped_entries_dropped` — voci di indice buttate dagli eventi
  scopati (per evento: `reservations=`, `slots_emptied=`,
  `victims_unmapped=`, `note=drain-clean|quiesced|no-reservations`).
- `cache_full_valid_dropped` — voci VALID buttate dai reset totali: la
  TASSA vera. Run sano atteso: `total=2, scoped=0, full_valid_dropped=0`.
- Attesa nella forma degradata (flag acceso): `scoped>0` con
  `slots_emptied≤6` per evento al posto di `total` che cresce a coppie con
  `full_valid_dropped≈count` — e, se la tesi dell'autopsia e' giusta, la
  scomparsa della tempesta all-miss a valle del primo fallimento.

### 5.5 Protocollo di verifica (invariato rispetto a drain3, 3 aggiunte)

Coppie A/B in ordine invertito fra le accensioni, n≥3, fail-fast,
`DS4_CUDA_WORKER_PROFILE=1`, `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1`;
flag leva spento in entrambi i bracci per il controllo di neutralita',
acceso solo nel braccio B del test funzionale. In piu': (1) verificare nel
run sano la firma attesa di 5.4; (2) verificare nei log K1/K2 gia'
raccolti la presenza di `[expert-cache-grow] mode=two-phase` per chiudere
la lettura di sez. 4 senza nuovi run; (3) un braccio con timeout
transiente indotto (deadline corta) per osservare `scoped` in azione prima
di qualunque conclusione di velocita'.

## 6. Identita' dei file

- Base del diff: `ds4-p4a/ds4_cuda.cu`
  SHA-256 `c110c5603a417d7da9cf4a75f1f5168d170fff1e26827746a252c4e17d52386f`
  (untracked; HEAD `b024b8e9224c2ce243a110ed00a8b7e7348b14b0` non lo
  contiene).
- Patch: `.microbench/invalidate/invalidate.patch`, 30 hunk, +265/−31,
  SHA-256 `e1686501ccccd97aa9b8cb8aa268296411c012571f7e17ec1b124e489b709b8f`,
  verificata con `git apply --check` sul tree corrente.
- Verifica: `git apply --check --stat .microbench/invalidate/invalidate.patch`
  dal root del repo.
