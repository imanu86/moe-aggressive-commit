# FASE 2 — Drain sovrapposto al compute (voce P.2): invarianti, disegno, strumentazione

Data: 2026-07-28 sera. Base: `ds4-p4a/ds4_cuda.cu`, SHA-256
`5688dcd362deb80fb25a95715a9ef350cbb87c5f9515b56e1d31d041fffa51b4`.

## 0. Esito dichiarato della consegna

La Fase 1 (DEADLOCK.md) si chiude con "serve strumentazione": il meccanismo
che ha ucciso i due bracci non e' attribuibile con certezza dalla lettura, e
l'evidenza disponibile punta contro l'attribuzione alle patch. Per mandato
("esito valido e preferibile a un terzo cadavere"), `drain3.patch` e' di
**sola strumentazione**. Questo documento contiene comunque per intero la
parte analitica della Fase 2 — i quattro invarianti sul codice ATTUALE e il
disegno della leva nella forma sicura — cosi' che il futuro drain4.patch si
scriva su vincoli gia' inchiodati, DOPO che il protocollo discriminante di
DEADLOCK.md §7 ha dato il suo verdetto.

## 1. I quattro invarianti protetti dalla sync bloccante (codice attuale)

L'analisi originale (.microbench/drain/ANALISI.md) li aveva identificati
correttamente; qui sono rilocalizzati sul sorgente corrente e per ciascuno
e' detto come il disegno li conserva.

### I1 — Visibilita' di dati e puntatori

Oggi: gli H2D e i kernel di pubblicazione di `device_route_ptrs` /
`device_slot_by_layer_expert` viaggiano sull'upload stream non bloccante
(publish per-route :41474-41487; flush batch/demand/zerocopy ENFORCE
:40819-40847, col commento-contratto a :40835-40837: i puntatori devono
raggiungere `route_ptrs` PRIMA che lo stream sia drenato, perche' e' il
drain a renderli visibili). I kernel consumer girano su stream 0; fra i due
stream non esiste ordine implicito. Lo spigolo di visibilita' e' il drain
host (`cudaStreamSynchronize` :41541-41545; poll con deadline
:39331-39334) eseguito PRIMA di `*route_ready_host = sequence` (:41625).

Nel disegno: lo spigolo resta ma passa da host a device —
`cudaEventRecord(ready_ev, route_upload_stream)` accodato DOPO l'ultimo
publish della generazione, e `cudaStreamWaitEvent(0, ready_ev, 0)` accodato
PRIMA del primo kernel consumer che legge slot caricati o `route_ptrs`.
Nessun kernel che dereferenzia i dati in volo puo' eseguire prima del
completamento fisico delle copie. La pubblicazione di `route_ready_host`
smette di implicare "copie complete" e torna a significare solo "route
decise e accodate" — cio' che il consumer usa davvero per procedere con
l'ENQUEUE (l'esecuzione e' comunque gated dall'evento).

### I2 — Stato host degli slot e transazione di promozione

Oggi: gli slot sono `LOADING` prima della copia (:41283) e diventano
`VALID` SOLO dopo il drain riuscito (:41563-41566 non-ENFORCE;
:39350-39352 ENFORCE); su fallimento le promozioni sono rimborsate e la
cache invalidata (:39343-39348, :41567-41577); il commit del tiering e'
sullo stesso confine (:39353-39354).

Nel disegno: il commit diventa ottimistico (VALID all'armamento
dell'evento) ed e' CORRETTO per la stessa ragione per cui oggi e' corretto
il riuso dei buffer (I3): nessun attore puo' OSSERVARE uno slot VALID con
copia in volo, perche' l'unico lettore (i kernel consumer) sta dietro il
waitEvent, e l'unico riciclatore (il worker alla generazione successiva)
sta dietro il claim-gate che esige il done-event ESEGUITO su stream 0
(:30973-30976) — e con l'overlap il done-event sta, in ordine di stream,
DOPO waitEvent(upload) + kernel consumer. La catena device sostituisce il
drain host. Restano BLOCCANTI, invariati: il drain anticipato prima del
fallback SSD (:40137-40172 — chiude/rimborsa una transazione prima di una
lettura potenzialmente lenta: e' un rollback, mai ottimistico) e ogni
percorso di errore/rollback (mai invalidare o rimborsare con copie in
volo: su qualunque fallimento di record/armamento si ricade sulla sync
bloccante attuale).

### I3 — Lifetime dei buffer condivisi

Oggi: `route_host_*`, `route_transient_*`, `device_route_ptrs` e gli slot
sono condivisi fra generazioni. Il guardiano e' il claim-gate: il worker
non puo' iniziare N+1 (quindi non puo' riscrivere staging o slot) finche'
i consumer di N non sono terminati su stream 0 — documentato nel commento
zero-copy :40360-40368, implementato a :30953-31021 col done-event
registrato da ds4.c:12088-12093 → :31231-31232. Il lease G132
(`cpu-staging-reader-active`, :30959-30965) e' un secondo guardiano
ortogonale.

Nel disegno: INVARIATO ed e' il pilastro che rende tutto il resto legale.
Con overlap, `cudaEventQuery(done_event) == cudaSuccess` al claim di N+1
prova transitivamente anche che upload(N) e' fisicamente completo (il
record sta dopo i kernel, che stanno dopo il waitEvent). Il gate resta
fail-closed e non aspetta: la semantica non cambia di un bit.

### I4 — Esattezza del registro dei trasporti

Oggi: un batch H2D e' committato al registro SOLO con drain riuscito e
batch completo (`ds4_transport_h2d_batch_finish`, :27916-27963; il
commento a :27932-27935 dice il perche': CUDA non rivela quale sottoinsieme
di un batch asincrono fallito ha attraversato il PCIe).

Nel disegno: con overlap armato il worker non ha piu' la prova del
completamento al momento del finish → il batch va INVALIDATO
(`ds4_transport_h2d_batch_invalidate`, :27909-27914), che espone
onestamente `complete=false` invece di contabilizzare una copia non
provata. Versione piena (facoltativa, non necessaria alla correttezza):
conservare il batch per generazione e committarlo al claim di N+1, quando
il completamento e' provato dal gate. La versione minima va DICHIARATA
nella riga di report del registro, mai taciuta.

## 2. La forma sicura: parametro di template, non flag a runtime

La lezione convergente della campagna (G132 in lane.patch: "L0 neutralita'
PASSATA IN PIENO ... G132 e' un PARAMETRO DI TEMPLATE ... a flag spenti il
codice non esiste nel percorso compilato", ledger :17694-17699) contro i due
cadaveri del drain. Forma per drain4:

- terzo parametro `template <bool G73, bool G132, bool DOV>` su
  `cuda_moe_route_worker` / `cuda_moe_tiering_enforce_request` /
  `routed_moe_launch_impl` / `cuda_moe_gpu_resident_routes_finish`;
- il dispatch esistente (:48796-48816, dove gia' si scelgono le quattro
  istanze `<G73,G132>`) aggiunge le istanze `<...,true>` selezionate SOLO da
  `DS4_CUDA_DRAIN_OVERLAP=1` letto una volta all'init;
- ogni riga nuova sta dentro `if constexpr (DOV)`: nelle istanze `false` il
  codice NON ESISTE nel percorso compilato — la neutralita' a flag spento
  non e' una proprieta' da verificare a runtime ma un fatto del linker
  (stessa argomentazione del fix Fable, .microbench/lane_fable/NOTA.md
  "Nessun cambiamento con flag spenti");
- lo stato nuovo (2 eventi per parita' di generazione + generazione armata)
  vive in un SIDECAR globale separato, MAI dentro `cuda_moe_expert_cache`
  (lezione drain2 §"A2 neutrality", che resta valida come igiene);
- gli eventi sono creati solo con flag acceso, alla prepare, come gia'
  faceva drain2 (righe 107-113 del suo diff — quella parte era giusta).

Costo accettato e dichiarato: raddoppio delle istanze template del worker
(4→8) = piu' testo nel binario. E' lo stesso costo gia' pagato per G132.

## 3. Il disegno della leva (per drain4, su carta)

### 3.1 Obiettivo minimo — il drain del layer L sotto il compute di L

Worker, ramo `DOV`, al posto della coppia [drain bloccante → VALID →
ready]:

1. `cudaEventRecord(ready_ev[gen & 1], route_upload_stream)` dopo l'ultimo
   publish (ENFORCE: dopo il flush di :40819-40847; non-ENFORCE: dopo
   :41528-41536);
2. su successo del record: commit ottimistico (I2), pubblicazione della
   generazione armata nel sidecar (release), batch registro invalidato
   (I4), poi `route_ready_host` come oggi;
3. su QUALUNQUE fallimento (record, evento mancante, `ok == 0`,
   rollback): identico percorso bloccante attuale, riga per riga.

Consumer, ramo `DOV`, in `routes_finish` dopo l'uscita dallo spin ready e
il check di `route_failed_host`: se la generazione armata coincide con
quella sottomessa → `cudaStreamWaitEvent(0, ready_ev[gen & 1], 0)`; su
errore del wait → fail-closed della mailbox (come i percorsi esistenti) e
NULL.

Guadagno atteso: il worker smette di spendere 0,8 ms/layer (35 ms/token,
fino a 58 col QD) fermo sul drain; `route_ready` arriva prima; il thread di
decode riprende prima la staffetta. Su un mediano di 220 ms e' un bersaglio
di circa -16% SE il tempo e' davvero host-serial-bound (tesi delle quattro
conferme del 28/7). La GPU non guadagna nulla per definizione: i kernel
dipendenti aspettano gli stessi byte — e' il costo HOST che si toglie dal
percorso critico.

### 3.2 Obiettivo pieno — stadi worker sotto H2D dentro lo stesso layer

Gia' esistente a monte: le pread scrivono in slice di staging per-miss
(:40176-40181) e gli H2D sono accodati asincroni per-route: la lettura del
miss i+1 gia' si sovrappone all'H2D del miss i. Il pezzo mancante e' solo a
valle (il drain finale), che e' il §3.1. Dentro il ramo split
(SPLIT_FUSED=1, assetto di campagna) il waitEvent va posizionato DOPO la
passata hit e DOPO il kernel di ownership del fix Fable (:48103) e PRIMA
della passata miss (:48086 e seguenti, i kernel che dereferenziano
`route_ptrs`): cosi' il compute hit esegue sotto le copie residue e solo i
kernel che leggono i dati in volo aspettano. Il fix Fable non va toccato:
il suo kernel scrive hit-mask e slot split_down (stato per-richiesta gia'
in VRAM), non legge gli slot in volo — resta prima del waitEvent.

### 3.3 Cosa resta vietato

- NIENTE sovrapposizione TRA layer: router(L+1) ← FFN(L), tetto 1 gia'
  dimostrato (.microbench/rendezvous/ANALISI.md; ledger :17353). Il
  disegno non tenta di accodare nulla oltre la generazione corrente.
- Drain anticipato pre-SSD: resta bloccante (I2).
- Niente Q1/IQ1: quei percorsi usano `drain_completed`
  (:50418, :51208, :51609, :51846) e il dispatch mixed resta sulle istanze
  `DOV=false`.
- Niente ammissione/residenza/cache: la leva tocca solo il confine di
  consegna, non chi entra o esce dalla VRAM.

### 3.4 Il percorso d'errore (la parte che i cadaveri non avevano risolto)

Con overlap armato, un errore CUDA ASINCRONO sull'H2D emerge dopo che
`route_ready` e' gia' stato consumato: il contratto failed-before-ready
(:41590-41603 prima di :41625) vale solo per errori sincroni. Copertura nel
disegno: l'errore sticky avvelena il contesto e viene intercettato al
confine successivo — il record del done-event del consumer
(:31231-31238) o la `cudaEventQuery` del claim (:30973-30990) falliscono →
fail-closed → quarantena, cioe' ESATTAMENTE il percorso gia' esistente per
i contesti avvelenati (e' il modo in cui il runtime ha gestito l'IMA della
lane, ledger :17713-17726). La finestra di ritardo della diagnosi e' di una
generazione; nessun dato corrotto e' osservabile (I1-I3 reggono il caso:
il waitEvent non lascia eseguire consumer su copie fallite — lo stream con
errore non completa l'evento).

## 4. Telemetria: senza queste due voci il braccio non e' giudicabile

Le voci sono GIA' nel formato della riga `[worker-prof]` con drain3.patch
(baseline a zero per costruzione). Contratto di alimentazione per drain4:

- `drain_overlap_ms` (WP_DRAIN_OVERLAP_NS): quota di drain avvenuta SOTTO
  il compute = intervallo `ready_publish → primo cudaStreamQuery(upload) ==
  cudaSuccess` osservato dal loop idle del worker. Alimentazione: nel ramo
  `DOV`, con un overlap outstanding, il loop idle (:40937-40964) esegue UNA
  `cudaStreamQuery` per iterazione finche' non torna Success e somma lo
  span dal timestamp di ready. Zero costo a flag spento (il codice non
  esiste), costo a flag acceso ~1 chiamata driver per iterazione idle solo
  nelle finestre con copie in volo.
- `gpu_stall_on_drain_ms` (WP_GPU_STALL_ON_DRAIN_NS): porzione della sync
  del resolver del layer successivo (:46188-46197, gia' cronometrata in
  `route_resolve_sync_seconds`) trascorsa mentre un overlap era ancora
  outstanding = stallo GPU attribuibile al drain spostato. Alimentazione
  host-side nello stesso punto, nessun evento CUDA aggiuntivo.

Criteri di giudizio del futuro braccio:
- successo: `drain_overlap_ms ≈ drain_ms` fisico, `gpu_stall_on_drain_ms ≈ 0`,
  mediana -30/-50 ms/token, `deadline_exhausted = 0`, `cache_invalidates`
  invariato;
- falsificazione onesta: `drain_overlap_ms` pieno ma mediana invariata ⇒ il
  drain non era sul percorso critico ⇒ leva chiusa, senza appello;
- squalifica del run (non della leva): `deadline_slack` collassato o
  `cache_invalidates` esploso anche nel braccio di riferimento ⇒ tempesta di
  macchina, rifare secondo il protocollo di DEADLOCK.md §7.

## 5. Contenuto effettivo di drain3.patch (consegnato)

`git apply --check` OK sul tree corrente; `--numstat`: +52/-2 su
`ds4-p4a/ds4_cuda.cu`. Cinque hunk:

1. enum workerprof (:4373): sei contatori nuovi in coda (prima di
   WP_TOKENS) — WP_DRAIN_OVERLAP_NS, WP_GPU_STALL_ON_DRAIN_NS,
   WP_DEADLINE_SLACK_NS, WP_DEADLINE_SLACK_EVENTS, WP_DEADLINE_EXHAUSTED,
   WP_CACHE_INVALIDATES;
2-3. riga `[worker-prof]` (:4765, :4812): sei campi nuovi IN CODA alla riga
   (i parser a chiave non si spostano; le -2 righe del numstat sono le due
   code di format/argomenti riscritte DENTRO la funzione di report, che
   esce subito a profiler spento, :4704-4705);
4. `cuda_moe_expert_cache_invalidate` (:36592): conteggio invalidazioni,
   dietro `cuda_worker_profile_enabled()` (int cachato, :4406-4413);
5. percorso transiente ENFORCE (:40236): campionamento del budget residuo
   del guardiano al primo ingresso transiente della richiesta, dietro
   `wprof` (gia' issato a :39823) — un `cuda_wall_sec` (QPC) quando attivo,
   un ramo non preso quando spento.

Proprieta' di neutralita', per costruzione: nessun membro aggiunto a
struct condivise; nessuna chiamata CUDA aggiunta su nessun percorso;
nessuna riga esistente ristrutturata fuori dalla funzione di report
(flag-gated in testa); gli unici rami nuovi sui percorsi caldi sono test su
int cachati, non presi a flag spento. I contatori sono alimentati solo con
`DS4_CUDA_WORKER_PROFILE=1`, che e' gia' nel protocollo standard dei run.
Residuo dichiarato: l'ingrandirsi dell'enum sposta `.bss` del profiler e il
testo del binario — la stessa classe di perturbazione di qualunque
ricompilazione; e' esattamente cio' che il run di controllo a flag spenti
del protocollo (regola del ledger :17375) esiste per coprire.

## 6. SHA-256

```
5688dcd362deb80fb25a95715a9ef350cbb87c5f9515b56e1d31d041fffa51b4  ds4-p4a/ds4_cuda.cu (preimage del diff)
[vedi drain3.sha256 accanto a questo file per l'hash della patch e dei documenti]
```
