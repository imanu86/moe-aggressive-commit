# drain4fix2 — con DOV attivo, chi prova al consumer che gli upload sono completi? (analisi statica, nessuna patch)

Data: 2026-07-29. Nessuna compilazione, nessun server, `D:\` non toccato.
Tree analizzato: `ds4-p4a/ds4_cuda.cu` SHA-256
`f759225aa817b539295c986bd50cab7a999ecf3b60930e68120472bf1c24b142`
(drain4+drain4fix+shared1+dspark1+dspark2+dspark2fix+logids composti — il
tree del binario 3DE06FD01C7CFB4D). Config del run analizzato: g73=0,
general=0, scoped=1, dov=1, SPLIT_FUSED=1, TIER=ENFORCE, kv150k.

**Esito: nessuna patch.** La catena di prova e' basata su ORDINE (di stream
e di gate fail-closed), non su tempi: sotto carico anomalo ogni arco degrada
a "piu' tardi" o a "fail-closed", mai a "sbagliato". La correttezza non
dipende dai tempi normali. In §5 una proposta OPZIONALE di irrobustimento
dietro flag separato (non necessaria in assetto di campagna) e il motivo per
cui il "fallback a tempo sul worker" sarebbe un peggioramento.

## 1. La risposta secca

**Nessuno prova al consumer-host che gli upload sono completi — ed e'
corretto cosi': quel contratto non esiste piu'.** Con DOV,
`route_ready_host` significa solo «route decise e accodate» (disegno §I1).
La prova di completamento e' spezzata in DUE, una per ciascun attore che ne
ha davvero bisogno:

1. **Ai kernel consumer** (l'unico lettore dei byte in volo) la prova la da'
   il DEVICE: `cudaStreamWaitEvent(0, ready_event[gen&1])` accodato prima
   della passata miss. I kernel non possono eseguire prima che l'evento —
   registrato dal worker DOPO l'ultimo publish sull'upload stream — sia
   fisicamente completo. Vale con qualunque ritardo di qualunque attore.
2. **Al worker** (l'unico riciclatore di staging/transient/slot) la prova la
   da' il claim-gate, per transitivita': `cudaEventQuery(done_event) ==
   cudaSuccess`, dove il done-event sta — in ordine di stream 0 — DOPO il
   waitEvent. Query non bloccante, fail-closed: o la prova c'e', o non si
   procede affatto.

Il thread di decode non consuma mai "copie complete": tra ready e
l'accodamento dei kernel fa solo lavoro di enqueue.

## 2. La catena completa per QUESTA config (file:riga del tree analizzato)

```
P1  worker    ultimo publish (flush demand/publish/zerocopy) poi ARM:
              cudaEventRecord(ready_event[N&1], route_upload_stream)
              — arm :40028-40116, chiamato a :41709 (ENFORCE); commit
              ottimistico VALID+tiering DENTRO l'arm, dopo il record
P2  worker    *route_ready_host = N                          :42577
P3  consumer  esce dallo spin ready (:47206), check route_failed :47352
              FENCE: cudaStreamWaitEvent(0, ready_event[N&1], 0)
              — ramo split (SPLIT_FUSED=1): :49131-49161, DOPO il blocco
                G132/kernel Fable (con general=0 il blocco e' compilato
                via) e PRIMA della passata miss
              — non-split: :47380-47398 dentro routes_finish
              match per GENERAZIONE (armed_generation == submitted, coppia
              release/acquire sul sidecar), non per tempo
P4  GPU       i kernel della passata miss (stream 0) eseguono solo dopo
              che l'evento e' ESEGUITO = upload(N) fisicamente completo
P5  decode    accoda il resto dei consumer FFN; ds4.c:14170 registra il
              done-event SOLO se tutto e' stato accodato (`if (ok)`);
              il record sta su stream 0 DIETRO il fence di P3
P6  GPU       resolver(N+1) — accodato da begin(N+1) dopo P5 — esegue dopo
              il done-record; solo la sua ESECUZIONE pubblica la richiesta
              N+1 nella memoria host-mapped che il worker polla
P7  worker    vede la sequence N+1 (quindi P5-P6 sono gia' ESEGUITI sul
              device), claim-gate :31179-31247: query del done-event
              :31198-31204 == Success per costruzione, transizioni mailbox
              CAS, fail-closed su qualunque incoerenza
P8  worker    SOLO ORA tocca staging/transient/slot per N+1: upload(N)
              e' provato completo per transitivita' (I3)
```

Punto chiave di P6-P7: il worker non puo' nemmeno VEDERE la richiesta N+1
prima che il done-event di N sia eseguito, perche' e' il resolver(N+1) —
dietro quel record in ordine di stream — a scrivere la publication word. La
prova arriva sempre PRIMA del bisogno, a qualunque velocita' giri la
macchina.

## 3. Stress sotto carico anomalo: arco per arco

| arco | se e' LENTO | correttezza |
|---|---|---|
| copie H2D/publish (upload stream) | l'evento fira piu' tardi; i kernel miss e tutto cio' che segue su stream 0 (done, resolver N+1) slittano | intatta: e' l'ordine, non il tempo |
| worker 60 ms/job (il caso del run) | ready piu' tardi; il consumer spinna di piu'; l'overlap della gen precedente era GIA' ritirato al claim (P7 precede il servizio). Nella catena di prova non entra nessuna assunzione sulla durata del job | intatta |
| GPU satura / resolver lento | il worker resta in idle: il poll della richiesta e' senza deadline per disegno; il poll DOV dell'overlap e' telemetria (se non osserva mai il completamento, fence e claim-gate valgono comunque; retire_at_claim chiude la finestra) | intatta |
| decode lento fra ready e fence | i kernel non sono ancora accodati: nessun lettore esiste prima del fence | intatta |
| done-event mai registrato (consumer uscito prima, layer fallito) | ds4.c:14170 e' sotto `if (ok)`: niente record → il claim di N+1 fallisce CHIUSO (:31210-31216) → quarantena; il worker non ricicla nulla | fail-closed |
| errore CUDA asincrono sulle copie | lo stream con errore non completa l'evento → il fence non passa → nessun kernel legge byte falliti; l'errore sticky emerge al confine successivo (record del done :31429-31461 → ok=false → niente done → claim chiuso; o sync del resolver → con G73=0 abort()) | fail-closed |

Gli UNICI archi con un tempo dentro sono i watchdog PRE-ESISTENTI del
serving, identici a DOV spento: spin consumed 5 s, starvation 5 s (reset su
progresso di lettura), guardiano transiente `DS4_G133_TRANSIENT_IO_TIMEOUT_S`
(0,25 s) + FIX-B (`RECOVERABLE`, cap streak 64 :8100-8135, streak
:41112-41135, reset :41757-41764), cancel_and_join (join 5 s + quiesce 5 s).
Questi NON fanno parte della catena di prova: quando scattano portano a
cancel+quiesce+invalidate/quarantena — fail-closed, come oggi. **Verdetto:
la leva e' robusta per costruzione; la macchina sporca non ha rivelato una
fragilita' della catena, ha esercitato i watchdog di serving che esistevano
gia'.**

## 4. Rilettura del run D1-abort dentro questo quadro

- `reason=none cuda=none` ⇔ `enforce_request` ha ritornato 0: il worker
  lascia il proprio `failure_reason` a "none" quando e' il ramo ENFORCE a
  fallire (init :42090-42092, chiamata :41708-41710, stampa :42545-42556).
  La ragione VERA sta nella riga
  `[tiering-enforce] result=failed layer=4 sequence=994 reason=...`
  (:41748-41755), un rigo sopra nel log completo — e' il dato da recuperare.
- 994 = 23×43+5: una richiesta per layer per token e' la cadenza NORMALE del
  worker; `errors=1` dice che 993 richieste sono riuscite e UNA e' fallita
  (token 24, layer 4). Il run non "falliva sempre": e' una catastrofe di
  coda.
- I totali quotati sono medie e sono compatibili con 993 job da ~3-4 ms piu'
  UNA coda da ~57 s (60.017 ms totali di job). 57 s ≈ cap FIX-B (64 ripieghi
  × ~0,9 s per ciclo budget+recovery): l'identikit piu' probabile e' il
  guardiano transiente in tempesta IO — la classe di DEADLOCK.md §3/§6,
  coerente con Z0 (flag TUTTI spenti, 1.980 ms/token, 252k sfratti) sulla
  stessa macchina degradata. Discriminatori nel log gia' raccolto: la riga
  [tiering-enforce], le righe transient/FIX-B intorno alle 10:31, e nel
  `[worker-prof] final` i campi `read_*_ms`, `deadline_slack_ms`,
  `deadline_exhausted`, `cache_invalidates_*`.
- Sul quesito 4 del messaggio precedente: un fallimento POST-arm dentro la
  stessa richiesta e' impossibile per costruzione (l'arm e' l'ultimo atto
  del job prima di ready: dopo, il worker non esegue piu' nulla che possa
  fallire per quella generazione). Il fallimento osservato e' PRE-arm in una
  richiesta successiva, e il suo percorso di ricaduta e' quello bloccante di
  oggi — che infatti ha girato: refund + firma scoped + failed→ready, e il
  consumer «observed failure; falling back». Cio' che e' TERMINALE e'
  l'assetto G73_OPEN=0: qualunque route failure abortisce la richiesta (ramo
  split, `finished_cache == NULL` senza replay per non-G73 → `ok = 0` a
  :49059-49061 → launch ritorna 0 → decode failed), da sempre e a
  prescindere da DOV.

## 5. Irrobustimenti valutati

1. **Fallback a tempo sul worker (ipotizzato dal coordinatore): SCONSIGLIATO.**
   Introdurrebbe una dipendenza temporale in una catena che oggi non ne ha:
   un auto-disarm o un time-limit renderebbe di nuovo ambiguo il significato
   di ready ("forse drenato, forse no, dipende dal cronometro") — la stessa
   ambiguita' che i quattro invarianti esistono per escludere. I tempi
   appartengono ai watchdog del serving, che gia' presidiano ogni attesa.
2. **OPZIONALE, dietro flag separato (`DS4_CUDA_DRAIN_OVERLAP4_STRICT_QUIESCE=1`),
   NON necessario in campagna**: `cuda_moe_route_upload_stream_quiesce` e'
   no-op senza staged-KV (:31285-31293). Se un watchdog uccide il worker con
   un overlap armato e staged-KV spento, l'invalidate puo' correre con copie
   in volo — finestra EREDITATA (esisteva gia' per le copie del job in
   corso), che DOV estende di una generazione. In campagna staged-KV e'
   attivo e la finestra e' chiusa. Il flag renderebbe il quiesce
   incondizionato nei soli percorsi di cancel raggiunti dai rami DOV.
   Proposta a catalogo, da implementare solo se si vorra' correre DOV senza
   staged-KV.
3. **Diagnostica (candidata a un futuro drain4diag, non urgente)**: nel ramo
   DOV del worker, su enforce fallito, impostare
   `failure_reason="enforce-request-failed"` e loggare
   `dov_outstanding=%d` (per costruzione 0: stamparlo trasforma la prova
   statica di §2 in un check falsificabile sul campo); più un riepilogo
   una-tantum alla release (arm/retire/veti). Tutto in istanze DOV=true,
   zero presenza a flag spento.

## 6. Il dato positivo, registrato con le unita' giuste

La riga `[worker-prof] final` stampa CUMULATIVI di run, non per-token
(:4840: `v = final_line ? cur : win`; scala ms=1e-6 :4842). Quindi:
`drain_overlap_ms=125.461` = totale del run = **~5,45 ms/token** (23 token)
= ~0,126 ms per generazione armata (994 arm). Con `drain_ms=0.000` e
`gpu_stall_on_drain_ms=0.000`: **il meccanismo funziona** — arm, fence,
retire e telemetria esercitati 993 volte senza una violazione — e la quota
di drain spostata sotto il compute e' PICCOLA in questo regime perche' il
serving era dominato da zero-copy/RAM (poco in volo da sovrapporre), oltre
che su macchina degradata. Il guadagno vero va misurato sul rerun pulito e
sara' proporzionale ai byte realmente in volo per layer (il bersaglio del
disegno — worker fermo 0,8 ms/layer sul drain — appartiene ai regimi
H2D-pesanti). Criteri di giudizio: gia' fissati in
`.microbench/drain3/ANALISI.md` §4; protocollo: DEADLOCK.md §7 (ordine
invertito fra le accensioni, FIX-B attivo, n≥3, verdetto sul regime).

## 7. SHA-256

```
f759225aa817b539295c986bd50cab7a999ecf3b60930e68120472bf1c24b142  ds4-p4a/ds4_cuda.cu (tree analizzato, nessuna modifica)
```
