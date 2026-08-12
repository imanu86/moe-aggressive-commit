# drain4 — drain sovrapposto al compute (implementazione del disegno di drain3/ANALISI.md)

Data: 2026-07-29. Nessuna compilazione, nessun server, nessun accesso a `D:\`.

Base del diff: `ds4-p4a/ds4_cuda.cu`, SHA-256
`07d00271b4e6f6172b40d58859cbaeab552245da03fef25b185e5f6e4e033f9c`
(tree CORRENTE: disegno drain3 + kernel row-parallel + join asincrono lane +
invalidazione proporzionata SCOPED + strumentazione drain3 gia' applicati —
NON il blob `5688dcd3...` su cui fu scritto il disegno).

Patch: `drain4.patch`, SHA-256
`f595ad3f0e760e0e5c6a236ec3b52a5d1929e366a2aa7e495fb61229b7daf63f`,
`git apply --check` OK sul tree corrente, `--numstat` +573/-34 su un solo
file. Roundtrip verificato: base + patch e' byte-identico al file su cui il
diff e' stato prodotto; bilanciamento parentesi verificato su entrambi.

Le righe citate sotto come «:N» sono righe di `ds4-p4a/ds4_cuda.cu` DOPO
l'applicazione della patch, salvo dove marcate «base :N» (file attuale non
patchato) o «disegno :N» (blob del disegno).

## 1. Cosa e' stato costruito, e dove

| pezzo | dove (file patchato) |
|---|---|
| Sidecar globale `g_moe_drain_overlap4` (2 eventi per parita' + generazione armata + timestamp) e helper: requested/events_ready/create/destroy/outstanding/retire/poll/retire_at_claim/consumer_fence/consumer_sync_enter+exit | :36736-36956 |
| Distruzione eventi nella release (dopo la `cudaStreamSynchronize` dell'upload stream) | :36981-36984 |
| Creazione eventi nella prepare, SOLO a flag acceso; fallimento = log + niente overlap (fail-open sul bloccante) | :38613-38632 |
| `cuda_moe_drain_overlap4_arm` — record dell'evento sull'upload stream dopo l'ultimo publish + commit ottimistico (VALID + commit tiering) + invalidazione batch registro + pubblicazione sidecar | :39836-39908 |
| ENFORCE, drain finale: ramo `if constexpr (DOV)` che arma al posto del drain bloccante; else = percorso bloccante odierno invariato | :41491-41521 (arm :41502, batch :41506-41507) |
| Worker: quarto parametro DOV; poll dell'overlap nel loop idle; ritiro al claim; propagazione a enforce | :30569, :41568, :41607-41613, :41666-41673, :41909 |
| non-ENFORCE, drain del worker: ramo DOV gemello (arm :42226; ramo bloccante copiato riga per riga :42232-42281); l'istanza DOV=false esegue il testo ORIGINALE, token-identico (:42283-42321) | :42217-42322 |
| Consumer `routes_finish<G73, DOV>`: campionamento stallo attorno alla sync del resolver (:46932-46939 enter, :46949-46951 exit); fence §3.1 per split_mode==0 (:47168-47187); fence difensiva sull'uscita `fused split telemetry contract` (:47227-47244) | :46906+ |
| `routes_submit<G73, G132, DOV>` → passa DOV alla finish | :47259, :47281 |
| `routed_moe_launch_impl<G73, G132, DOV>`: propagazione a submit (:47577) e alla finish del ramo split (:48801); fence §3.2 del ramo split DOPO il blocco G132/kernel Fable e PRIMA della passata miss (:48923-48954) | :47358+ |
| Dispatch una-tantum in `cuda_g73_route_dispatch_init`: `DS4_CUDA_DRAIN_OVERLAP4=1` letto una volta, istanze `<...,DOV=true>` selezionate solo a flag acceso; una riga di log a flag acceso per la verifica binario/env | :49644-49716 |

Telemetria (requisito 5): `drain_overlap_ms` = intervallo ready→primo
`cudaStreamQuery(upload)==Success` osservato dal loop idle del worker
(:41607-41613 → :36863-36882, con ritiro di sicurezza al claim :41666-41673);
`gpu_stall_on_drain_ms` = porzione della sync del resolver trascorsa con un
overlap outstanding (:46932-46951 → :36934-36956). Entrambe alimentano i
contatori GIA' esistenti di drain3 (WP_DRAIN_OVERLAP_NS,
WP_GPU_STALL_ON_DRAIN_NS, base :4444-4445) sotto `DS4_CUDA_WORKER_PROFILE=1`.
A flag DOV spento le alimentazioni stanno solo in istanze non dispatchate:
restano 0 per costruzione, come oggi.

## 2. Composizione coi template esistenti

DOV e' un parametro AGGIUNTIVO con default `false`, mai una sostituzione:

- `cuda_moe_route_worker<G73, G132, SCOPED, DOV>` (SCOPED resta terzo);
- `cuda_moe_tiering_enforce_request<G73, G132, SCOPED, DOV>`;
- `routed_moe_launch_impl<G73, G132, DOV>`;
- `cuda_moe_gpu_resident_routes_submit<G73, G132, DOV>`;
- `cuda_moe_gpu_resident_routes_finish<G73, DOV>`.

`cuda_moe_tiering_finish_vram_reservations<SCOPED>` NON e' stata toccata
(zero diff nel suo corpo): il braccio armato vive ai due call-site, e a arm
fallito la si chiama identica a oggi. Il dispatch compone i tre assi
(g73/general × scoped × dov) a init; a flag spento le istanze selezionate
sono le STESSE di oggi. Il dispatch MTP resta cablato su
`routed_moe_launch_impl<false>` (= DOV=false, :49723-49725 invariate); i
percorsi Q1/IQ1 non passano dal dispatch e restano su istanze non-overlap
(§3.3 del disegno), con in piu' la guardia runtime descritta al punto 6.4.

Costo dichiarato: raddoppio delle istanze referenziate (worker 8→16, launch
impl 4→8, enforce 8→16, finish 2→4, submit 4→8) = piu' testo nel binario,
stessa classe di costo gia' pagata per G132 e SCOPED (disegno §2). Ogni riga
nuova sta dentro `if constexpr (DOV)`: nelle istanze false il ramo e' uno
statement scartato dal compilatore, non un ramo runtime (la lezione dei due
cadaveri).

## 3. I quattro invarianti e il meccanismo che li protegge

**I1 — Visibilita' di dati e puntatori.** Lo spigolo passa da host a device:
`cudaEventRecord(ready_event[gen&1], route_upload_stream)` accodato DOPO
l'ultimo publish della generazione (ENFORCE: dopo i flush demand/publish/
zerocopy, arm chiamato a :41502; non-ENFORCE: dopo il flush del publish
batch, :42226) e `cudaStreamWaitEvent(0, ...)` accodato PRIMA del primo
kernel che dereferenzia slot o `route_ptrs` in volo (fence :36903-36930;
siti: non-split :47178, split :48936, difensivo :47235). `route_ready_host`
torna a significare solo «route decise e accodate»; l'esecuzione dei
consumer e' gated dall'evento.

**I2 — Transazione slot e promozioni.** Il commit LOADING→VALID + commit
tiering diventa ottimistico SOLO dentro l'arm, DOPO il record riuscito
(:39884-39892). Nessun attore osserva un VALID con copia in volo: i kernel
consumer stanno dietro il waitEvent (I1), il riciclo degli slot dietro il
claim-gate (I3). Su QUALUNQUE fallimento (precondizioni, Peek con errore
pendente, record fallito) l'arm ritorna 0 e si esegue il percorso bloccante
attuale riga per riga: ENFORCE :41509-41514 → `finish_vram_reservations<SCOPED>`
invariata (refund + invalidate scoped/full come oggi); non-ENFORCE
:42232-42281 (copia verbatim del blocco odierno). Il drain anticipato
pre-SSD resta bloccante e non passa dall'arm (chiamata invariata :40777-40781:
e' un rollback, mai ottimistico).

**I3 — Lifetime dei buffer condivisi.** Il claim-gate e' INVARIATO
(:31048-31116, query del done-event :31068-31074). Con l'overlap,
`cudaEventQuery(done_event)==cudaSuccess` al claim di N+1 prova
transitivamente il completamento fisico di upload(N): il record del
done-event (ds4.c:12288-12293, invariato) e' accodato su stream 0 dopo i
kernel consumer, che stanno dopo il waitEvent. La catena e' fail-closed
anche nei rami storti: ds4.c registra il done-event SOLO se tutti i consumer
del layer sono stati accodati (`if (ok)`); se il consumer esce prima di
accodare il fence, il done-event non esiste → il claim successivo fallisce
chiuso → quarantena, nessun riuso di staging sotto copie in volo. L'unico
punto in cui un layer PROSEGUE dopo un NULL post-ready (il replay G73
dall'uscita `fused split telemetry contract`) riceve la fence difensiva
:47235-47243 (vedi 6.5). Il ritiro al claim (:41666-41673) consuma la stessa
prova per la telemetria.

**I4 — Esattezza del registro dei trasporti.** Con overlap armato il worker
non ha la prova del completamento al finish: il batch viene INVALIDATO
(`ds4_transport_h2d_batch_invalidate` + finish: ENFORCE :41506-41507,
non-ENFORCE :42229-42231), mai committato. Versione minima del disegno,
DICHIARATA con una riga una-tantum accanto al registro
(`[transport] drain_overlap4=minimal ...`, :39893-39900) e visibile in
`ledger_complete=0` nella riga `[transport]` esistente.

## 4. Il percorso d'errore

- **Fallimento SINCRONO dell'arm** (errore pendente al Peek, evento
  mancante, record fallito): ritorno 0 senza azzerare lo stato d'errore
  (Peek, non Get — :39867; su record fallito :39871-39880 si logga e NON si
  chiama `cudaGetLastError`): il percorso bloccante esegue la sua
  `cudaGetLastError`/sync e attribuisce il fallimento ESATTAMENTE come oggi
  → `route_failed_host` prima di ready, consumer al solito punto
  (:47133-47166), invalidazione dal percorso SCOPED se attivo (il fallback
  E' `finish_vram_reservations<SCOPED>`: requisito 4 soddisfatto per
  costruzione).
- **Errore ASINCRONO sull'H2D dopo l'arm** (§3.4 del disegno): l'errore
  sticky avvelena il contesto; lo stream con errore non completa l'evento,
  quindi i consumer dietro il waitEvent non eseguono mai su copie fallite
  (I1 regge il caso). L'errore emerge al confine successivo: record del
  done-event del consumer (base :31298-31341) o query del claim
  (:31068-31074) → fail-closed → quarantena — lo stesso percorso dei
  contesti avvelenati (IMA della lane). Il poll idle che lo incontra logga
  una volta e NON lo azzera (:36874-36881). Finestra di ritardo della
  diagnosi: una generazione, come da disegno.
- **Errore del waitEvent del consumer** (sincrono, contesto/handle rotto):
  log con sito e causa, poi lo stesso trattamento dei watchdog esistenti —
  `cancel_and_join` (che quiesce l'upload stream prima di ogni invalidate:
  mai invalidare con copie in volo) + `cuda_moe_expert_cache_invalidate`
  con sito dedicato `consumer-dov4-wait-event[-split]` + NULL/0
  (:47177-47186, :48934-48952, :47234-47243). Nel ramo split, prima del
  fail-closed viene cancellata la lane G132 se attiva (:48940-48944), come
  fanno gli altri error-path di quel blocco.
- **Nessun errore inghiottito**: gli unici `cudaGetLastError()` nuovi sono
  (a) nel ramo di fallimento della CREAZIONE eventi a init (:38622-38625),
  su un errore appena loggato, perche' non contamini il primo job; (b)
  nessun altro. Poll, arm e fence lasciano pendente cio' che trovano.

## 5. Rilocalizzazioni rispetto al disegno (blob `5688dcd3...` → base attuale `07d00271...`)

| oggetto | disegno | base attuale |
|---|---|---|
| Contratto publish-prima-del-drain (I1) | :40835-40837 | :41160-41162 (commento P.5a) |
| Drain ENFORCE + transazione slot (I2) | :39331-39356 | :39601-39653 (`finish_vram_reservations<SCOPED>`, ora templata dall'invalidate.patch) |
| Drain non-ENFORCE | :41541-41545 | :41866-41880 |
| Pubblicazione ready / failed | :41625 / :41594 | :41950 (:41499 all-hit G73) / :41919 |
| Claim-gate (I3) | :30953-31021 | :31048-31116 (query done-event :31068-31074) |
| Commento lifetime zero-copy | :40360-40368 | :40676-40694 |
| Registro trasporti (I4) | :27916-27963 / :27909-27914 | :28011-28059 / :28004-28009 |
| Loop idle del worker | :40937-40964 | :41262-41290 |
| Drain anticipato pre-SSD | :40137-40172 | :40439-40477 |
| Sync del resolver (stallo GPU) | :46188-46197 | :46508-46542 (`route_resolve_sync_seconds` :46522) |
| Check failed del consumer | :46385-46400 | :46714-46738 (ora con ramo scoped-consume) |
| Kernel Fable (ownership lane) | :48103 | :48440-48447 (`moe_g132_split_own_cpu_routes_kernel`, dentro il blocco G132 :48389-48456 aggiunto dal fix) |
| Passata miss del ramo split | «:48086 e seguenti» (coordinate pre-fix di lane_fable) | :48525-48584 (gate/up/mid miss, down miss, fused finish, sum); passata hit :48298-48331; finish del ramo split :48334-48337 |
| Dispatch init | :48796-48816 | :49135-49176 (gia' esteso da SCOPED) |
| `drain_completed` Q1/IQ1 | :50418, :51208, :51609, :51846 | :15871, :51211, :52001, :52402, :52639 (tutti dietro `cuda_g133_shared_policy_active()`) |
| Contatori WP_DRAIN_OVERLAP/STALL | «da creare» | GIA' presenti (drain3.patch): enum base :4444-4445, riga report :4885-4886 — drain4 li alimenta soltanto |

Slittamenti = lane_kernel + lane_econ + invalidate + drain3 applicati sopra
il blob del disegno. Nessun punto d'innesto e' risultato semanticamente
cambiato; l'unica novita' strutturale rilevante e' il blocco G132/Fable
(:48389-48456) fra la finish e la passata miss, che e' esattamente il punto
dove il disegno voleva il waitEvent del ramo split.

## 6. Punti dove il disegno taceva e ho deciso io (dichiarati)

1. **Nome del flag**: `DS4_CUDA_DRAIN_OVERLAP4` (dal mandato) e non
   `DS4_CUDA_DRAIN_OVERLAP` (disegno §2): evita che un env stantio dei due
   bracci morti armi il nuovo percorso per sbaglio.
2. **Arm ai call-site, `finish_vram_reservations` intatta**: il disegno
   metteva il DOV «al posto della coppia drain→VALID» senza fissare il
   confine di funzione; ho scelto la forma che lascia la funzione del drain
   bloccante a zero-diff e concentra il nuovo codice nei due siti.
3. **Duplicazione verbatim del blocco bloccante non-ENFORCE** dentro il ramo
   `if constexpr (DOV)` (:42232-42281): il prezzo di avere l'istanza
   DOV=false token-identica all'originale (il suo else esterno E' il testo
   originale, :42283-42321, indentazione compresa). Stessa scelta, in
   piccolo, per il drain ENFORCE (:41509-41520).
4. **Guardia runtime sulla policy condivisa G133**: l'arm rifiuta quando
   `cuda_g133_shared_policy_active()` (:39860-39865). Il disegno vietava
   Q1/IQ1 via dispatch, ma i consumatori di `drain_completed`
   (request-boundary, q1-0-mixed-entry, ...) leggono `route_completed_*`
   come prova di quiescenza: con un overlap armato quella implicazione
   cadrebbe. La policy e' stato di g_moe_tiering (non env-stabile a
   dispatch-init), quindi il check sta nell'arm: un ramo prevedibile che
   esiste solo nelle istanze DOV=true.
5. **Fence difensiva sull'uscita `fused split telemetry contract`**
   (:47227-47244): quel NULL post-ready con worker sano e armato prosegue,
   con G73, nel replay esatto che poi registra il done-event; senza fence il
   done-event non proverebbe piu' upload completo (buco di I3 che il disegno
   non copre). Fence best-effort prima del return.
6. **Fence del consumer: split_mode==0 dentro `routes_finish`, split 1/2 nel
   launch impl** dopo il blocco G132/Fable (:48923-48954): fedele a §3.1 +
   §3.2. Nota onesta: la passata hit e' accodata PRIMA della finish, quindi
   sta comunque davanti al fence in ordine di stream; il beneficio aggiuntivo
   del posizionamento §3.2 e' non serializzare il kernel Fable dietro le
   copie. Su fence fallita nel ramo split si cancella prima la lane G132
   se attiva.
7. **Creazione eventi fallita = fail-open bloccante** (:38613-38632), non
   bocciatura della prepare: log immediato + `drain_overlap_ms` fermo a 0 a
   flag acceso = degradazione visibile nel protocollo. In piu' una riga di
   log al dispatch quando DOV e' armato (:49651-49657) per la verifica
   binario/env chiesta dall'autopsia drain3x (caso «errore di
   configurazione/selezione binario»).
8. **Residuo OFF non templabile, dichiarato**: (a) la release chiama
   `cuda_moe_drain_overlap4_events_destroy()` incondizionata (:36984) — a
   flag spento e' un ciclo su due handle NULL in un percorso di teardown
   one-shot; (b) la prepare fa una getenv cachata (:38618) — stessa classe
   della getenv di SCOPED a init; (c) il sidecar sposta la .bss come
   qualunque ricompilazione (classe di perturbazione gia' accettata e
   coperta dal run di controllo a flag spenti del protocollo). Nessuna
   struct condivisa modificata; nessuna chiamata CUDA aggiunta su percorsi
   OFF; nessuna riga calda ristrutturata fuori dalle istanze DOV=true.
9. **Semantica di misura, ai margini**: `gpu_stall_on_drain_ms` usa il
   completamento stampato dal worker; se il worker non l'ha ancora stampato
   a fine sync, si conta l'intera sync (limite superiore onesto).
   `drain_overlap_ms` al ritiro-al-claim data il completamento all'istante
   del claim (ritardo massimo un quantum di SwitchToThread); dopo un
   cancel_and_join+respawn un singolo campione puo' risultare gonfiato — i
   log di cancel adiacenti lo rendono riconoscibile.
10. **Esposizione ereditata, non ampliata**: il quiesce di `cancel_and_join`
   e' gated su staged-KV (base :31157-31160) — vale gia' oggi per tutti i
   watchdog; i percorsi di fence fallita riusano quella semantica senza
   cambiarla. E con G73 la sync del resolver del layer successivo ora
   attende anche l'upload residuo: una tempesta di drain puo' emergere li'
   come deadline del resolver invece che come budget del guardiano bruciato
   nel worker — e' esattamente cio' che `gpu_stall_on_drain_ms` esiste per
   misurare, e il protocollo di DEADLOCK.md §7 (FIX-B attivo, ordine
   invertito, n≥3) resta la condizione di validita' di qualunque verdetto.

## 7. Cosa NON e' stato toccato (requisito 6)

Fix Fable del ramo split (il suo kernel resta prima del fence, :48440-48447
invariate); kernel row-parallel; join asincrono della lane (:48611-48624
invariate); invalidazione proporzionata SCOPED (tutti i suoi rami intatti;
drain4 vi si compone soltanto); ammissione/residenza/cache (l'arm tocca solo
il confine di consegna); Q1/IQ1 in ogni forma (nessun sito q1_0/iq1_s
modificato; guardia 6.4 in piu'); il drain anticipato pre-SSD; la riga
`[worker-prof]` (formato invariato, i campi esistono da drain3).

## 8. SHA-256

```
07d00271b4e6f6172b40d58859cbaeab552245da03fef25b185e5f6e4e033f9c  ds4-p4a/ds4_cuda.cu (base del diff, tree corrente)
f595ad3f0e760e0e5c6a236ec3b52a5d1929e366a2aa7e495fb61229b7daf63f  drain4.patch
```
