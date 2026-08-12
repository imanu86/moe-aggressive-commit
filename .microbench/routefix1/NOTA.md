# ROUTEFIX1 — precheck single-token: il veto muto parla (FATTO 1) + resync opzionale (FATTO 2)

Data: 2026-07-29. Tree bersaglio: `ds4-p4a` CORRENTE (ds4_cuda.cu preimage hash
sotto; il file NON e' tracciato da git — `?? ds4-p4a/` — quindi il patch e'
stato costruito con diff -u a header git-style, come le consegne di campagna).
`routefix1.patch`: solo `ds4-p4a/ds4_cuda.cu`, 76 inserimenti / 2 sostituzioni,
due hunk. `git apply --check` PASS sul tree corrente. Niente build (vietata),
niente server, D:\ non toccato.

## Verifica della diagnosi dspark2fix3 (riga per riga)

CONFERMATO tutto l'impianto:

- Precheck 42193-42232: i termini sono esattamente quelli tabulati. Il ramo
  compose (**42221-42227**, preimage) e' l'UNICO che azzera `request_valid`
  senza stampare: la riga `[gpu-route-request] result=invalid` (42209-42219)
  gira PRIMA del ramo compose, quindi non lo copre; sparse-bake stampa dentro
  la validate; `cuda_moe_tiering_advance_call_tick` stampa (36530-36534);
  selected-range stampa (42260-42268); all-hit tier-state stampa (42302).
- "request-invalid" nasce a 42286 (unico produttore), funnel 42382-42385.
- `ds4_gpu_moe_route_consumer_done` ha UN call-site (ds4.c:14176-14181, coda
  del layer decode); lo store dell'evento e' a ds4_cuda.cu:31604; il claim
  della 131 valida la prior 130 a 31341-31351 ("consumer-event-generation");
  fail-closed 31286-31315 (che con compose acceso avvelena anche l'arena:
  hits_disabled/submissions_blocked a 31300-31304, coerente con la cascata).
- `route_consumed_sequence/generation` scritti AL CLAIM (31380-31383), prima
  della validazione: il "gpu-writing coi numeri della 131" e' red herring,
  confermato. Nessuna deadline in tutta la catena: soli check di contenuto.
- G133 epoch (42200-42201): `cuda_g133_epoch_valid` controlla solo NON-ZERO
  (32102-32104), non la freschezza: un'epoch stantia ma non nulla PASSA.
  Se fosse questo termine a fallire, la riga 42210 STAMPEREBBE (con campi
  6/6/0 e byte combacianti, perche' l'epoch non e' fra i campi stampati).

TRE CORREZIONI sostanziali alla diagnosi (cambiano il peso del candidato, non
la necessita' del discriminatore):

1. **Lo staging a wave NON avanza la generazione.** `cuda_moe_selected_stage_wave`
   (43576) transita dall'arena solo da LETTORE (`cuda_dynamic_arena_copy_expert_async`,
   43718-43736) piu' gli hook observer-mirror (43707) che pero' richiedono
   l'observer dinamico ATTIVO. Nessuna chiamata su quel percorso muove
   `g_dynamic_arena.snapshot_generation`.
2. **L'unico avanzatore e' `ds4_gpu_dynamic_arena_publish` (11064)** — e stampa
   SEMPRE `ds4: [arena] publish generation=N loads=M` (11073-11076). Gli altri
   scrittori del campo o azzerano (9444, teardown) o toccano l'ALTRA arena
   (`g_q1_0_dynamic_arena`: 10241, 11311, 11476, 11560). I tre driver di
   publish in fase inference stampano tutti una riga distintiva:
   `[arena-observe] WRAP published` (14190), `[reap-mass]`/wrap (14779),
   `[prefill-mass-wrap] result=published` (15357, solo alla finalize del
   prefill). Quindi il log del run GIA' ESISTENTE contiene il secondo
   discriminatore: grep di `[arena] publish generation=` fra il claim della
   129 e quello della 130.
3. **Sotto l'assetto di campagna (ENFORCE + compose) il mismatch "non puo'"
   formarsi legittimamente**: la config compose-enforce imposta
   `g_dynamic_arena.tiering_exclusive = 1` (33280-33282) e
   `cuda_dynamic_arena_begin_internal` RIFIUTA ogni transazione con
   tiering_exclusive attivo (10661) — e senza txn niente publish. In piu' il
   begin del percorso mailbox (47173-47187) rifiuta di armarsi con observer
   dinamico o REAP attivi, e il prefill-mass pubblica solo alla finalize.
   Percio': o il run non era in ENFORCE (con TRACK+compose i wrap restano
   possibili e il candidato 42221 torna primo), o il predicato che boccia la
   130 e' un ALTRO termine (e allora la riga 42210 c'era, coi campi "sani" e
   il vero colpevole non stampato: epoch G133), o la generazione e' mossa da
   uno scrittore sconosciuto. Il FATTO 1 separa i tre casi da solo.

## FATTO 1 — strumentazione del ramo muto (consegnata)

Hunk 2 del patch, dentro `cuda_moe_route_worker<G73,G132,SCOPED,DOV>` (42069),
al posto del corpo muto 42225-42226. Quando il ramo boccia, ora stampa UNA riga:

```
ds4: [gpu-route-request] result=invalid-compose-snapshot sequence=130 layer=0
     arena=<G_arena> tiering=<G_tier> txn=0 hits_disabled=0
     submissions_blocked=0 mode=2 resync=off
```

- i due `snapshot_generation` (arena vs tiering) = il motivo del veto;
- `txn/hits_disabled/submissions_blocked/mode` = provenienza: quieti + riga
  `[arena] publish` a monte nel log ⇒ pubblicazione reale; quieti senza
  publish a monte ⇒ scrittore sconosciuto (sotto ENFORCE non dovrebbe potere);
- `resync=off|arena-busy` dice se la leva del FATTO 2 era spenta o rifiutata.

Lettura del prossimo run NextN (nessun flag nuovo richiesto):
- appare `result=invalid-compose-snapshot` ⇒ diagnosi dspark2fix3 CONFERMATA,
  coi numeri; controllare `[arena] publish` a monte per la provenienza;
- appare invece `result=invalid` (riga vecchia, campi sani) ⇒ il colpevole e'
  nel primo gruppo di termini; con DS4_G133_TIER=1 l'indiziato e' l'epoch
  G133 (unico termine armato non stampato in quella riga);
- non appare nessuna delle due ⇒ il fallimento non e' il precheck (tick o
  percorso diverso) e la catena va riletta da 42382.

## FATTO 2 — resync dietro flag (consegnato, default spento)

`DS4_CUDA_ROUTE_SNAPSHOT_RESYNC=1` (helper `cuda_route_snapshot_resync_requested`,
hunk 1, dispatch una-tantum stile DS4_G73_OPEN; default = comportamento
attuale). Nel ramo di mismatch, PRIMA di bocciare, il worker riaggancia
`g_moe_tiering.snapshot_generation` all'ultima generazione d'arena PUBBLICATA
— solo se l'arena e' quiescente e la fonte sana:

```
!txn && !hits_disabled && !submissions_blocked
&& backing == PRIMARY && arena.snapshot_generation != 0
```

e stampa `result=resync-compose-snapshot sequence=... arena=... tiering_before=...`
(al piu' una volta per pubblicazione: dopo l'adozione i confronti tornano
uguali). Se la guardia rifiuta, la richiesta viene bocciata come oggi con
`resync=arena-busy` nella riga del FATTO 1.

**Vincolo non negoziabile (byte mai non-pubblicati): garantito, e non dal
valore adottato ma dai check per-entry gia' esistenti.** Catena:

1. Nessun puntatore a byte nasce dal solo `snapshot_generation` del tiering.
   Ogni accesso al backing prestato passa da
   `cuda_moe_tiering_snapshot_ram_ptrs` (33348-33379), che ad OGNI chiamata
   esige: generazioni uguali, arena fuori transazione (hits_disabled/
   submissions_blocked), e il binding per-entry `READY` ESATTAMENTE alla
   generazione richiesta (`cuda_dynamic_arena_binding_valid`, 33366-33371).
2. Un binding `READY` con `snapshot_generation == G` in `active[]` lo scrive
   solo `ds4_gpu_dynamic_arena_publish` per la G committata: la validazione
   (11017-11036) controlla slot/layer/expert/content_generation DOPO il join
   dei worker di copia, e solo dopo attiva i binding (11039-11047, swap 11058)
   e per ultimo il valore G (11064). Chi legge G legge quindi uno stato la cui
   pubblicazione e' completa (stessa disciplina plain-load/TSO su cui gia'
   vivono 33352-33359, 40963-40978 e il ramo 42221 stesso).
3. Durante una transazione le load scrivono SOLO slot non-attivi (available =
   non referenziati da `active[]`, 10775-10781): i byte dietro un binding
   valido alla G corrente non vengono riscritti mentre G e' pubblicata. E
   sotto ENFORCE (l'assetto NextN) `tiering_exclusive` esclude in radice ogni
   transazione concorrente al servizio post-resync.
4. Caso patologico (valore adottato spurio, scrittore sconosciuto): nessun
   binding porta quella generazione ⇒ tutte le entry risultano miss ⇒
   fail-closed "snapshot-miss" (41173-41181, stampata) o SSD (router open):
   rumoroso, MAI byte non pubblicati.

Residui dichiarati (non byte-safety, ma da sapere):
- **Deriva di policy**: gli stati `RAM_PROBATION` seminati alla config
  (33243-33265) non vengono ricalcolati sul nuovo snapshot; un'entry sfrattata
  dalla nuova generazione degrada a snapshot-miss (fail-closed o SSD),
  un'entrante nuova serve comunque via binding (snapshot_ram_ptrs non consulta
  `tier.state`). Onesto ma sub-ottimale finche' una config non risemina.
- **Serve-gate**: `[tiering-enforce] result=snapshot-generation-mismatch`
  (40963-40978) resta fail-closed: se una publish atterra fra precheck e
  servizio la richiesta muore STAMPANDO — corretto, e' il contratto.
- Il resync scrive `g_moe_tiering.snapshot_generation` dal thread worker;
  i lettori concorrenti (classify G73 a 45949, lane G132 a 51075 — che tra
  l'altro prende il reader-claim sullo slot, 51098) gia' leggono questi campi
  plain-load; un u64 allineato su x86 non si straccia. Stesso modello di
  memoria del codice esistente, nessuna struct condivisa modificata.

**Precondizione d'uso** (scritta qui perche' il flag non diventi un cerotto):
accendere il resync SOLO se il FATTO 1 mostra `txn=0 hits_disabled=0
submissions_blocked=0` E il log ha una riga `[arena] publish generation=`
coerente a monte. Se il mismatch appare sotto ENFORCE senza publish a monte,
NON accendere il flag: c'e' uno scrittore da trovare, e adottarne il valore
nasconderebbe il guasto (il fail-closed di oggi e' l'unico comportamento
giusto in quel caso).

## Ripiego concordato (senza patch, da subito)

Il braccio NextN gira senza la leva compose: togliere
`DS4_CUDA_PREFILL_TIER_COMPOSE=1` (31863-31870) dall'assetto del run (e con
esso il ramo 42221 non si arma: `compose_prefill_mass_tiering=0`). Costo: si
perde il backing prestato dallo snapshot prefill-mass in fase decode (le miss
tornano SSD/probation); beneficio: nessun predicato di snapshot sul percorso
single-token, quindi il blocco di seq 130 non puo' riprodursi da quel ramo.
E' la misura di accettazione piu' pulita se serve PRIMA del run col FATTO 1.

## Verifiche eseguite

- `git apply --check .microbench/routefix1/routefix1.patch`: PASS sul tree
  corrente; `--numstat`: `76  2  ds4-p4a/ds4_cuda.cu` (unico file).
- Round-trip: patch applicato a una copia vergine ⇒ hash identico alla copia
  editata (post-image sotto). Tree del repo RIPRISTINATO al byte (hash
  preimage verificato dopo il revert).
- Bilanciamento delta `{} () []` pre→post: +6/+6, +22/+22, +3/+3. OK.
- Nessuna compilazione (vietata dal mandato: rebuild ds4 su pod, non PC),
  nessun server avviato, D:\ e C:\ds4-models non toccati.
- Perimetro: nessuna riga di shared1/drain4+fix/dspark1/dspark2+fix2+fix3/
  logids/lane/econ/pin2 toccata; niente Q1; nessun campo aggiunto a struct
  condivise (contatori/stato solo function-local).

## SHA-256

Preimage (tree corrente):

```text
ds4-p4a/ds4_cuda.cu
dd1e4cd8b3b2d93c4414b6a80a2dfe153fd0bd20a11125decece4addda14ad71
```

Post-image (tree corrente + routefix1.patch):

```text
ds4-p4a/ds4_cuda.cu
e17ad97b4f58dd9e6e54fc13ee1ed0ddefd399197f48e4d9af5637ce085dd2f4
```

Artefatto patch:

```text
.microbench/routefix1/routefix1.patch
b20fe014622ca6618ccbe48ec2a2f220b775fead661d98435c5ebb745bc802b6
```
