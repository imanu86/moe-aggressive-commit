# FASE 1 — Il "deadlock" che ha ucciso drain.patch e drain2.patch

Data: 2026-07-28 sera. Sorgente analizzato: `ds4-p4a/ds4_cuda.cu`,
SHA-256 `5688dcd362deb80fb25a95715a9ef350cbb87c5f9515b56e1d31d041fffa51b4`
(blob git `d937b98f`; e' il tree con lane.patch + fix Fable applicati — l'hash
coincide col "risultato atteso" dichiarato in `.microbench/lane_fable/NOTA.md`).
Nessuna compilazione, nessun server, nessun accesso a `D:\`.

Fonti lette per intero: `.microbench/drain/drain.patch` + `ANALISI.md`,
`.microbench/drain2/drain2.patch` + `NOTA.md`,
`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md` (sezioni 28/7),
`.microbench/rendezvous/ANALISI.md`, `.microbench/pickup/DIAGNOSI.md`,
`.microbench/lane*/`, `.microbench/backbone*/`.

## Verdetto in dieci righe

1. Nel codice ATTUALE un deadlock di primitive fra decode, route worker e GPU
   e' **impossibile per costruzione**: ogni attesa e' o bounded da watchdog o
   rivolta a un device che progredisce da solo, e non esistono due lock presi
   in ordini opposti (sezione 2, tabella completa).
2. La firma che ha ucciso i due bracci (primo token 86,7 s, mediana 2.135 ms,
   `drain` 226 ms/token, worker `idle_token` 13.648 ms/token, ABORT al token 7
   con `transient-io-timeout`) e' la firma di un **livelock di servizio**:
   guardiano IO → fallimento → `invalidate` della cache → all-miss → tempesta
   → di nuovo guardiano (sezione 3, con file:riga di ogni arco).
3. `drain.patch` era **realmente non-neutra** a flag spento: tre modifiche
   strutturali attive comunque, elencate e localizzate (sezione 4). Ma la loro
   grandezza fisica e' di **nanosecondi**, non di secondi: non possono produrre
   la firma osservata (aritmetica in sezione 4.3).
4. `drain2.patch` a flag spento esegue **una getenv + un confronto + tre load**
   in piu' rispetto al sorgente. Nessuna modifica strutturale raggiungibile a
   flag spento esiste nel suo diff (verifica indipendente, sezione 5). Il suo
   "FALLITO IDENTICO" **non e' spiegabile col suo codice**.
5. La stessa identica firma e' stata prodotta, lo stesso giorno, **tre volte
   senza alcuna patch drain nel binario** (L2b, V3, tempesta warmup L1 —
   sezione 6). Le due condanne runtime sono n=1 in ordine non invertito, lo
   stesso artefatto d'ordine che il ledger ha documentato quel pomeriggio.
6. Conclusione di Fase 1: **la causa dei due cadaveri non e' inchiodabile
   dalla sola lettura**. Cio' che e' certo, cio' che e' escluso e cio' che
   serve strumentare sono in sezione 7. Per mandato, la consegna e'
   DEADLOCK.md + patch di **sola strumentazione** (drain3.patch) + protocollo
   discriminante. Il disegno della leva resta su carta in ANALISI.md.

---

## 1. La staffetta attuale, per come e' scritta davvero

Percorso per layer con `DS4_CUDA_MOE_GPU_RESIDENT_ROUTES=1`,
`SPLIT_FUSED=1`, `TIER=ENFORCE`, `G73_OPEN=0` (assetto di campagna):

1. **decode / begin** (`cuda_moe_gpu_resident_routes_begin`,
   ds4_cuda.cu:45923-46160):
   - aspetta che il worker abbia CONSUMATO la richiesta precedente
     (spin `SwitchToThread` su `route_consumed_*`, bound 5 s poi
     fail-closed, :46034-46058);
   - verifica il mailbox slot `generation & 1` (FREE o CONSUMER_DONE,
     :46074-46087) e lo porta in GPU_WRITING;
   - pubblica il timestamp di submit (:46095-46101) e lancia
     `moe_resolve_resident_routes_kernel<<<1,1>>>` **su stream 0**
     (:46102-46128); aggiorna `route_submitted_*` (:46153-46157).
2. **GPU / resolver** (kernel): scrive il payload della richiesta in memoria
   host-mapped e per ultima, dopo `__threadfence_system()`, la publication
   word `route_request_host->sequence` (parametri con `absolute_deadline`
   a :25657, store del payload fino a :25709; protocollo confermato in
   `.microbench/rendezvous/ANALISI.md` sez. 3).
3. **worker / pickup** (`cuda_moe_route_worker`, :40901):
   - polla `route_request_host->sequence` con `SwitchToThread()` per giro
     (:40937-40964);
   - copia lo snapshot (:40982-40988) e chiama il **claim**
     (:40989-40992 — su claim fallito il worker fa `break` ed ESCE dal
     thread).
4. **worker / claim gate** (`cuda_moe_route_mailbox_worker_claim`,
   :30953-31021). Per generation > 1 esige, PRIMA di toccare qualunque
   buffer condiviso:
   - `route_consumer_event_generation == N-1` e slot precedente coerente;
   - `cudaEventQuery(route_consumer_done_event) == cudaSuccess`
     (:30973-30976).
   Se una condizione manca **fallisce chiuso** (:30984-30990), non aspetta:
   `cuda_moe_route_mailbox_fail_closed` (:30922-30951) mette lo slot in
   QUARANTINED, alza `route_worker_failed` e spegne la dynamic arena.
5. **worker / servizio** (ENFORCE, `cuda_moe_tiering_enforce_request`):
   - il guardiano viene ARMATO IN TESTA alla funzione:
     `transient_request_deadline = now + DS4_G133_TRANSIENT_IO_TIMEOUT_S`
     quando `request.absolute_deadline <= 0` e staged-KV non attivo per la
     richiesta (:39823-39831; con `G73_OPEN=0` la deadline della richiesta
     arriva sempre 0 da :46592-46605, quindi questo e' il ramo di campagna);
   - promozioni: pread → H2D **asincrono** sull'upload stream → publish
     kernel sull'upload stream (percorso non-ENFORCE gemello a
     :41336-41487; ENFORCE accumula e flusha a :40819-40847);
   - ramo transiente (SSD): pubblica la deadline in
     `route_transient_read_deadline` (:40196-40210), tre pread con deadline
     (:40222-40254); scaduta → `failure_reason = "transient-io-timeout"`
     (:40302-40307), salvo ripiego FIX-B se
     `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1` (:40256-40301);
   - **drain finale** = spigolo di visibilita':
     `cuda_moe_tiering_finish_vram_reservations` (:40848-40869 → :39319-39356)
     che polla l'upload stream fino alla deadline
     (`cuda_g73_finish_launched_copy`, :33955-33976); solo dopo il drain gli
     slot passano LOADING→VALID e le promozioni sono committate
     (:39350-39354). Nel percorso non-ENFORCE il drain e'
     `cudaStreamSynchronize(route_upload_stream)` (:41541-41545).
6. **worker / rilascio**: eventuale `*route_failed_host = sequence`
   (:41594), transizione mailbox WORKER_OWNS→UPLOAD_ENQUEUED
   (:41616-41619), `*route_ready_host = sequence` (:41625),
   `route_completed_*` (:41642-41643).
7. **decode / finish** (`cuda_moe_gpu_resident_routes_finish`, :46163):
   - prima **sincronizza stream 0** (il resolver): con G73 spento e'
     `cudaStreamSynchronize(0)` senza deadline (:46195); con G73 e' un poll
     con deadline che su scadenza fa `cancel_and_join` (:46191-46213);
   - poi spin su `route_ready_host == sequence` (:46242-46362) con TRE
     watchdog: worker perso (:46244-46254), deadline assoluta della lettura
     transiente con recovery FIX-B (:46277-46316), stallo/starvation 5 s o
     `transient_stall_seconds` (:46318-46355). Ogni watchdog termina in
     `cuda_moe_route_worker_cancel_and_join` + `invalidate` + ritorno NULL
     (= fallback esatto per quel layer);
   - su `route_failed_host == sequence`: log, eventuale drain del worker,
     **`cuda_moe_expert_cache_invalidate()`** e NULL (:46385-46400).
8. **decode / chiusura layer**: dopo aver accodato TUTTI i consumer del
   layer su stream 0, ds4.c:12088-12093 chiama
   `ds4_gpu_moe_route_consumer_done()` che registra
   `route_consumer_done_event` su stream 0 (:31231-31232). E' l'evento che
   il claim della generazione successiva interroghera'.

Nota sull'ordinamento che rende il gate fail-closed sicuro OGGI: il record
del done-event (8) e' accodato su stream 0 PRIMA del resolver della
generazione successiva (1-2 del layer dopo). Il worker puo' vedere la nuova
sequence solo DOPO che il resolver e' stato eseguito, quindi solo DOPO che il
record e' stato eseguito: la `cudaEventQuery` del claim non puo' trovare
l'evento incompleto in regime sano. Il drain bloccante non partecipa a questo
spigolo: protegge i quattro invarianti elencati in ANALISI.md, non il gate.

## 2. Chi aspetta chi: la tabella completa

| chi | aspetta che cosa | primitiva | bound | uscita su sforamento | file:riga |
|---|---|---|---|---|---|
| decode (begin) | worker consumi richiesta N-1 | spin + SwitchToThread su `route_consumed_*` | 5 s | fail-closed mailbox | 46034-46058 |
| decode (finish) | resolver su stream 0 | `cudaStreamSynchronize(0)` (G73 off) / poll con deadline (G73) | ∞ / deadline | — / cancel_and_join | 46183-46216 |
| decode (finish) | `route_ready_host == seq` | spin + SwitchToThread | 5 s stallo, deadline assoluta transiente | cancel_and_join + invalidate | 46242-46362 |
| worker (claim) | consumer di N-1 ESEGUITO | `cudaEventQuery` (done-event) | **0 — gate, non attesa** | fail-closed + QUARANTINED + `break` del thread | 30973-30990, 40989-40992 |
| worker (drain) | upload stream vuoto | `cudaStreamSynchronize` / poll con deadline | ∞ / deadline | — / NotReady = terminal-fallthrough | 41541-41545, 39331-39334, 33955-33976 |
| worker (pread) | byte dal file | pread cancellabile con deadline | deadline 0,25 s | `transient-io-timeout` | 40222-40254, 40302-40307 |
| decode (kill) | join del worker | `os_thread_join_timeout` | 5 s | detach + safe-leak permanente | 31090-31125 |
| decode (kill) | upload stream quieto | poll `cudaStreamQuery` | 5 s | quarantena cache (safe-leaked) | 31059-31088 |
| decode (respawn) | worker pronto | spin su `route_worker_ready` | 2 s | cancel_and_join, niente route per la richiesta | 37699-37784 |

Le attese host→GPU hanno un device che progredisce da solo (l'upload stream
contiene solo H2D e publish kernel accodati dal worker stesso; stream 0
contiene lavoro accodato dal decode stesso). Le attese host→host hanno tutte
watchdog. Il solo punto senza bound (la `cudaStreamSynchronize(0)` a :46195)
aspetta un kernel gia' lanciato che termina sempre. **Non esiste un ciclo di
attesa circolare**: un deadlock di primitive non e' costruibile in questo
codice. Quello che il ledger ha chiamato "firma di blocco reciproco" e' il
ciclo di servizio della sezione 3.

## 3. Il meccanismo del blocco osservato (livelock di servizio)

Ricostruzione della firma misurata dalla bisezione
(ledger :17364-17377: `drain` 226,1 ms/token contro 35,3; `idle_token`
13.648 ms/token contro 78; ABORT `transient-io-timeout` al token 7; primo
token 86,7 s):

1. **Armamento**: il budget del guardiano (0,25 s) parte all'ingresso del
   servizio (:39827-39831) e viene consumato da TUTTO cio' che precede e
   circonda le pread: retry di ammissione RAM (:40103-40107), publish
   anticipato + **drain anticipato bloccante** (:40137-40172), poi le tre
   pread (:40222-40254). In regime di tempesta il drain anticipato da solo
   arriva a centinaia di ms (226 ms/token misurati) e il budget e' gia'
   morto prima della prima lettura.
2. **Verdetto**: `read_result < 0` → `"transient-io-timeout"`
   (:40302-40307) → `ok = 0` → `*route_failed_host = sequence` (:41594).
3. **Punizione collettiva**: il consumer vede il fallimento (:46385) e
   chiama `cuda_moe_expert_cache_invalidate()` (:46399, definita a
   :36571-36609): **tutta** la residenza expert azzerata, mappa device
   compresa.
4. **All-miss**: i layer successivi non trovano piu' nulla in VRAM: fino a
   6 esperti × ~7,08 MB per layer da rileggere, ripromuovere, ripubblicare e
   ridrenare → `drain` e letture esplodono → il guardiano scatta di nuovo →
   GOTO 2. Questo e' l'anello del livelock.
5. **Kill e respawn**: quando invece a sforare e' l'attesa del consumer, i
   watchdog di :46277-46355 chiamano `cancel_and_join` (:31090): cancel
   della pread, `route_stop`, join fino a 5 s, quiesce dell'upload stream
   fino a 5 s. Il thread e' morto; la richiesta di rotta SUCCESSIVA passa da
   `cuda_moe_route_worker_respawn` (:37699, invocato dalla prepare a
   :37964): cancel+quiesce+record del done-event+attesa ready fino a 2 s.
6. **La firma dei contatori**: durante 4 e 5 il worker e' VIVO e AFFAMATO
   (nessuna richiesta da servire mentre il decode e' impantanato nel
   fallback esatto/negli invalidate/nei respawn): l'ozio finisce in
   `idle_token_ms` (attribuzione a :4599-4618). 13.648 ms/token × 7 token ≈
   95 s ≈ l'intera durata del run: il worker non era bloccato su una
   primitiva, era senza lavoro. Un deadlock vero avrebbe fermato tutto; qui
   i token USCIVANO, a 2.135 ms l'uno, finche' il server ha abortito.
7. **Il primo token da 86-91 s**: al primo token la cache expert e' vuota
   per costruzione (43 layer quasi all-miss, arena in riempimento, page
   cache in competizione). Il ledger ha misurato in modo indipendente sia un
   prefill da 86,6 s (V3, :17561) sia una tempesta di warmup da ~1.991
   ms/passo per 140 passi con 154.893 sfratti backbone (L1 sera,
   :17701-17711) — **entrambi su binari senza alcuna patch drain**. La
   grandezza combacia con i 2.135 ms/token del braccio incriminato.

Questo meccanismo esiste INTERO nel sorgente attuale, si attiva senza
bisogno di alcuna patch, e il guardiano non-recuperabile lo trasforma in
abort (il ledger lo sapeva gia': "una singola lettura lenta aborta l'intera
richiesta", :17197; tre bracci uccisi cosi' — zero-copy, PREFETCH,
TIERFREQ2 — piu' I2/I3 la sera, :17804-17822).

## 4. Cadavere 1 — drain.patch: cosa si attivava comunque

### 4.1 Le tre modifiche attive a flag spento (confermate sul diff)

1. **Call-site ristrutturati**: la sync ENFORCE finale diventava
   `overlap_armed ? cudaSuccess : finish_launched_copy(...)` con
   `allow_overlap=1` cablato dal chiamante e il test del flag DENTRO
   `cuda_moe_route_upload_overlap_arm` (drain.patch righe 238-247 e
   308-313): il percorso OFF attraversava il costrutto nuovo a ogni layer.
   Idem nel drain non-ENFORCE del worker.
2. **Load aggiuntivi su atomici condivisi**: un
   `route_upload_ready_generation.load(acquire)` dopo il drain ENFORCE
   (righe 283-285) e un load acquire di `route_submitted_generation` nel
   consumer PRIMA del test del flag (righe 332-333). Eseguiti a ogni layer
   anche a OFF.
3. **Layout della struct condivisa**: due `cudaEvent_t` + un
   `std::atomic<uint64_t>` + una `uint32_t` inseriti in mezzo a
   `cuda_moe_expert_cache` (righe 17-42): mailbox, generazioni e contatori
   che decode e worker si contendono slittano di 24 byte, con possibile
   ridistribuzione delle cache line fra gli spinner.

Queste sono violazioni reali del contratto di neutralita' e bastavano da
sole a RESPINGERE la patch. La diagnosi di `.microbench/drain2/NOTA.md`
(:15-56) e' corretta su tutti e tre i punti.

### 4.2 Cosa NON possono spiegare

Aritmetica: a OFF, per layer, il delta eseguito e' ~4 confronti + 1-2 load
atomici + 1 getenv nella prepare. Ordine di grandezza: decine di nanosecondi
per layer, microsecondi per token. Il falso sharing da slittamento di struct
puo' rallentare uno spin di qualche fattore, non fermare un worker per 13,6
SECONDI a token ne' produrre un primo token da 86,7 s. La firma osservata e'
5 ordini di grandezza sopra il delta meccanico della patch. E il profilo del
braccio rotto non mostra "spin piu' lento": mostra il worker SENZA LAVORO e
il drain a 226 ms — cioe' il livelock della sezione 3.

### 4.3 Su cosa poggia la condanna runtime

Una coppia di run n=1, nello stesso ordine dopo il riavvio (ledger
:17364-17371), il giorno stesso in cui: (a) L2b aveva prodotto abort al
token 7 con primo token 91 s SENZA la patch, giudicato "stallo, non
attribuibile alla leva" (:17308); (b) il pomeriggio, l'A/B ammissione e'
stato dichiarato NON interpretabile proprio per l'artefatto d'ordine
temporale, con regola nuova "rifare in ORDINE INVERTITO" (:17441-17445) —
regola mai applicata retroattivamente alla bisezione del drain.

## 5. Cadavere 2 — drain2.patch: la modifica strutturale NON esiste

Rilettura integrale del diff (513 righe), ramo per ramo, sul suo blob base
`509cab7c`. A flag spento (`g_moe_drain_overlap.requested == 0`) il codice
eseguibile aggiunto e' TUTTO qui:

| sito | delta eseguito a OFF |
|---|---|
| `cuda_moe_expert_cache_prepare` | 1 `getenv("DS4_CUDA_DRAIN_OVERLAP")` + 1 confronto `0u == 0u` nella condizione di riuso |
| drain ENFORCE finale | 1 load di `g_moe_drain_overlap.requested` (ramo esterno `if (!requested)`) |
| drain worker non-ENFORCE | 1 load idem |
| consumer finish | 1 load idem |
| struct condivisa | **INVARIATA** (sidecar globale separato) |
| blocchi legacy | byte-identici (verifica sha in NOTA.md :96-113, quattro blocchi estratti) |

L'unico effetto sistemico residuo e' lo slittamento di `.bss` dovuto al
sidecar e all'ingrandirsi del testo — la stessa classe di perturbazione di
QUALSIASI ricompilazione. Non esiste nel diff una ristrutturazione, una
inizializzazione CUDA, un evento creato, un ordine di operazioni cambiato
che sia raggiungibile a flag spento. **"FALLITO IDENTICO" con un delta di
tre load e una getenv non e' una spiegazione: e' la confutazione della
spiegazione.** Se il braccio drain2 e' morto con la stessa firma, la causa
era fuori dal suo codice: stessa patologia di macchina della sezione 6,
oppure un difetto di procedura del braccio (binario/env non quello inteso).
Dalla lettura non e' decidibile quale — ed e' esattamente il caso previsto
dal mandato: serve strumentazione, non un terzo tentativo alla cieca.

## 6. La stessa firma senza patch drain: tre occorrenze documentate

| run | binario | patch drain? | firma | fonte ledger |
|---|---|---|---|---|
| L2b (spin 2000 µs) | catena L, pre-drain | NO | primo token 91 s, ABORT token 7 | :17308 |
| V3 (arena 42 GB) | 9C06BE71 | NO | prefill 86,6 s, ABORT token 10 | :17561, :17594-17600 |
| L1 sera (ancora lane) | FFA6018A→8845CAD4 | NO | 140 passi a ~1.991 ms/token, 154.893 sfratti backbone, poi rientro | :17701-17711 |
| bisezione drain | 49C488BA | SI (OFF) | primo token 86,7 s, 2.135 ms/token, ABORT token 7 | :17364-17377 |
| braccio drain2 | 246899570CF0FD3B | SI (OFF) | "identico" (nessun record nel ledger principale) | mandato |

Quattro-cinque occorrenze della stessa firma in un giorno, tre delle quali
su binari senza alcuna patch drain. Il meccanismo di sezione 3 le spiega
tutte; il delta a flag spento delle due patch non ne spiega nessuna.

## 7. Esito di Fase 1 e cosa serve per vedere il colpevole

**Certo (dalla lettura):**
- il codice attuale non ammette deadlock di primitive (sez. 2);
- drain.patch violava la neutralita' strutturale in tre punti (sez. 4.1);
- il delta a flag spento di entrambe le patch non puo' produrre la firma
  (sez. 4.2, 5);
- il livelock guardiano→invalidate→all-miss esiste nel sorgente vergine e
  produce esattamente quella firma (sez. 3, 6).

**Non decidibile dalla lettura:** se i due bracci morti siano caduti sul
livelock di macchina o su un difetto di procedura. Attribuirlo sarebbe
tirare a indovinare — vietato dal mandato.

**Strumentazione consegnata** (`drain3.patch`, +52/-2, dettagli in
ANALISI.md):
- `deadline_slack_ms` / `deadline_slack_events` / `deadline_exhausted`:
  budget del guardiano residuo al primo ingresso transiente della
  richiesta. Nei run sani ≈ budget pieno; se nei run degradati collassa,
  l'abort `transient-io-timeout` e' PROVATO sintomo (budget bruciato a
  monte, dentro la richiesta) e non causa (IO lento).
- `cache_invalidates`: il bordo del ciclo di sezione 3, oggi invisibile.
- `drain_overlap_ms` / `gpu_stall_on_drain_ms`: le due voci richieste dal
  mandato per giudicare un futuro braccio overlap, gia' nel formato della
  riga `[worker-prof]`; oggi stampano 0 per costruzione e fissano la
  baseline.

**Protocollo discriminante** (senza il quale nessun verdetto su un futuro
drain4 e' valido; costo ~1 h):
1. Binario A = tree attuale + drain3.patch; binario B = A + la patch leva
   (quando esistera'). Flag leva SEMPRE spenti; `DS4_CUDA_WORKER_PROFILE=1`;
   `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE=1` (il guardiano killer ha gia'
   cancellato tre leve e due bracci I2/I3: senza ripiego ogni tempesta
   diventa abort e contamina il confronto).
2. Coppie A/B in **ordine invertito** fra le accensioni (regola del ledger
   :17441-17445): B-A dopo un riavvio, A-B dopo il successivo; n≥3 per
   braccio col protocollo fail-fast; verdetto solo sul regime (ultimi 40
   passi) e sui rapporti interni al run.
3. Lettura: se il degrado segue la POSIZIONE nel ciclo di accensione e non
   il binario, la condanna delle patch drain cade definitivamente; se segue
   il binario con `deadline_slack` pieno, allora esiste davvero un difetto
   codice-dipendente e i contatori nuovi dicono in quale anello del ciclo
   di sezione 3 cercare.
