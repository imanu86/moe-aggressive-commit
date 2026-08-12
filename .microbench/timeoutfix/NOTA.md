# TIMEOUTFIX — chiusura dei quattro difetti del guardiano transiente (audit10/08_timeout.md)

Data: 2026-07-29. Base verificata: tree corrente post-rebuild 7821FFA5.
File toccato dalla patch: **solo `ds4-p4a/ds4_cuda.cu`** (os_file.c intatto, vedi B1).
Applicazione: `git apply .microbench/timeoutfix/timeoutfix.patch` dalla radice del repo.
`git apply --check` verificato pulito sul tree corrente; patch riapplicata end-to-end su
copia fresca del file di tree e confrontata per hash con la copia revisionata: identica.

## SHA-256

| Cosa | SHA-256 |
|---|---|
| `ds4-p4a/ds4_cuda.cu` PRIMA (tree corrente) | `f0dd5cfc6e001a61e818f8569e74e9ad07d536c55108418fef7851712224ba36` |
| `ds4-p4a/ds4_cuda.cu` DOPO la patch | `1c323a1eef8ee834b3f062e3e54e26b3beea43a6eb54942ede9f1c6467531c17` |
| `timeoutfix.patch` | `f0e1ed5c741d070bb2d4e92d1a231cb463210500209c1f4d262fbc14834710b0` |
| `ds4-p4a/src/platform/os_file.c` (NON toccato, riferimento) | `9687c44fe5d22ceed9f243b6c8aabb4b89ea5dded15307657b76bfc7a3d88fc1` |

NON compilato, nessun server avviato (vincolo di mandato). La verifica e' statica:
rilettura di ogni claim dell'audit sul codice + revisione riga-per-riga della patch.

---

## B1 (ALTA) — slot OVERLAPPED riusato dopo cancel >50 ms — VERIFICATO, CHIUSO

**Verifica del claim.** Tutto regge, con una precisazione sul trigger:
- `os_file.c:418-431` e `:433-443`: su `WAIT_TIMEOUT`/`WAIT_FAILED` il lettore emette
  `CancelIoEx`, aspetta il completamento del cancel solo 50 ms e, se non arriva,
  ritorna `-1` **lasciando `active=1` e l'OVERLAPPED pending**. Precisazione: con la
  chiamata transiente (`timeout_ms=UINT32_MAX`, os_file.c:410-416) questo ramo scatta
  quando il cancel del consumer viene osservato **al submit del chunk** (`wait_ms=0`,
  os_file.c:395-399/416) — cioe' quando il cancel cade tra due chunk — non a ogni wait.
  Il ramo POSIX equivalente e' os_file.c:510-519 (`aio_cancel` che resta `EINPROGRESS`
  esce con `active=1`).
- `os_file.c:317-327`: `os_pread_cancellable_reset` azzera SOLO `cancel_sequence`,
  non `active`. Confermato.
- `os_file.c:363-366`: la rilettura successiva trova `pending()!=0` → `EBUSY` → nel
  chiamante `got<0` con marcatori gia' azzerati (ds4_cuda.cu, fallback serve) → ritorno
  0 → `[transient-timeout] reason=fallback-unavailable fallback_skipped_reason=fallback-pread-failed`
  (log a ds4_cuda.cu:41768-41774). Confermato.
- Il commento storico a ds4_cuda.cu:31514-31517 («the cancellable call has returned …
  slot can be reset») e' falso per quei rami: confermato.
- Attenuante notato in verifica (non nell'audit): `os_pread_cancellable_pending()` a
  os_file.c:262-275 e' un poll attivo che *raccoglie* il completamento (GetOverlappedResult
  FALSE) e azzera `active` se l'I/O e' nel frattempo finito. La finestra e' quindi
  «cancel ancora incompleto AL MOMENTO della rilettura», piu' stretta di come letta
  nell'audit, ma reale: un singolo poll che vede `ERROR_IO_INCOMPLETE` basta a
  produrre l'abort.

**Chiusura (come indicato dall'audit).** In `cuda_moe_transient_timeout_fallback_serve`,
ramo `deadline_cancelled`: precondizione del ripiego = ack del cancel
(`os_pread_cancellable_pending()==0`) con **attesa bounded aggiuntiva di 1.0 s**
(poll di `pending()`, che e' anche il reaper), con uscite anticipate su
`route_worker_safe_leaked` («safe-leaked») e `route_stop` («route-stop»). Allo scadere:
`skipped_reason="cancel-ack-timeout"`, ritorno 0, **slot lasciato intatto** — mai
riusato. Il terminale resta quello odierno (abort della richiesta); il successivo
`cancel_and_join` quarantena lo slot pending col ramo che gia' possiede
(ds4_cuda.cu:31784-31798). Il fix e' nel chiamante, NON in os_file.c: azzerare
`active` nel reset sarebbe scorretto (il kernel possiede ancora buffer/OVERLAPPED).
Scelta del bound 1.0 s: i cancel si completano in ms; 1 s sta sotto la finestra di
grazia del consumer (stall 5 s default), e l'uscita su `route_stop` copre il caso di
finestre configurate piu' corte.

## B2 (ALTA) — data race su `route_transient_read_deadline` — VERIFICATO, CHIUSO

**Verifica del claim.** Regge integralmente:
- ds4_cuda.cu:29116: `double` ordinario in mezzo ad atomics. Scrittori: worker
  (publish 41660/41404, disarmo 31531, init/reset 37964/38855/39541); lettori
  concorrenti: consumer a 47908 e 47936 (ogni giro di poll), piu' 31825-31826 e 37718.
  Data race C++ formale, confermata.
- Il disarmo a 31531 ripubblica la **stessa** sequence (31532-31533): non e' un cambio
  di stato osservabile; il commento storico che la spacciava per pubblicazione valida
  era sbagliato. Confermato.
- Consumer: il ramo recovery (47943-47955) NON guarda `route_transient_read_bytes`;
  se continua a vedere la deadline scaduta, allo scadere della grazia fissa esegue
  `cancel_and_join` anche su un ripiego che avanza. Confermato. Il percorso
  progress-aware esiste solo dopo aver osservato deadline zero (47978-47992).

**Chiusura.** Pubblicazione atomica della transizione a fallback:
- campo → `std::atomic<double>` con `static_assert` su size/alignment/lock-free:
  **layout della struct invariato** (vincolo rispettato e provato a compile-time);
- disarmo pre-ripiego → `store(0.0, release)` (e' questa la pubblicazione);
- letture del consumer (47908, 47936) → `load(acquire)` per giro di poll: osservato
  0.0, il consumer esce dal ramo deadline-scaduta e passa al watchdog progress-aware
  gia' esistente, che e' esattamente il disegno inteso;
- gli altri siti (init/reset, teardown 37718, drain 31825) restano **testualmente
  identici**: su un atomic compilano come operazioni implicite seq_cst, corrette.
  In particolare la zona vietata :37707-37735 non e' toccata dalla patch.
Non ho aggiunto un contatore/versione: con l'atomic, transizione 0.0 + il ramo
progress-aware esistente coprono il caso; se il worker NON disarma mai (mai entrato
nel ripiego) il `cancel_and_join` allo scadere della grazia e' il comportamento
corretto, non un falso positivo — aggiungervi un check di progresso avrebbe mascherato
stalli veri.

## B3 (ALTA) — letture SSD_COLD→RAM fuori dal watchdog — VERIFICATO, CHIUSO

**Verifica del claim.** Regge integralmente:
- deadline creata all'ingresso enforce (41282-41286); PRIMA del percorso transiente il
  worker chiama `cuda_moe_tiering_load_to_ram` (41529 e retry a 41559, rami `!G73`);
  quella funzione legge gate/up/down con `cuda_pread_full` (36584/36592/36600) →
  `os_pread` senza deadline (6558-6560) → `GetOverlappedResult(..., TRUE)` bloccante
  (os_file.c:629-635). Confermato.
- Con `route_transient_read_sequence` non pubblicata il consumer classifica `starved`
  (47978-48016, ramo `!transient_active_now`) e chiama `cancel_and_join`; il cancel
  agisce su `route_transient_pread`, che la `os_pread` stack-local non osserva; join
  scaduto → `safe-leaked` permanente (31763-31780). Confermato.
- Variante osservata in verifica: se il ramo QD ha gia' pubblicato la sequence
  (41396-41408), il consumer classifica transiente ma il watchdog a progresso non
  vede byte nuovi durante la `os_pread` bloccante → stesso esito via
  `consumer-transient-stall`. Stessa radice: lettura non cancellabile e invisibile.

**Chiusura (riuso del percorso cancellabile transiente, come indicato).**
1. Il blocco storico di pubblicazione dello stato transiente (reset slot, azzeramenti,
   deadline, sequence, strumentazione DRAIN3) e' estratto verbatim in
   `cuda_moe_transient_read_publish_once(...)`, richiamato: nel punto storico del
   percorso transiente e PRIMA delle due `load_to_ram` del servizio route.
2. `cuda_moe_tiering_load_to_ram` accetta due parametri opzionali in coda
   (`transient_cache=NULL`, `transient_deadline=0.0`; nessun cambiamento per il
   chiamante di promozione a 37162). Con contesto transiente le tre letture passano da
   `cuda_moe_tiering_admission_pread` → `cuda_moe_transient_pread_chunked`: deadline
   assoluta per chunk, cancel del consumer onorato, progresso pubblicato in
   `route_transient_read_bytes` (alimenta il watchdog di stallo), contabilita'
   transport per byte realmente letti (niente doppia registrazione).
3. Composizione col recovery: se la deadline scade durante l'ammissione, il consumer
   cancella per il ripiego; la chunked ritorna -1, `load_to_ram` fallisce pulito
   (slot arena liberato, percorso di failure esistente), il servizio prosegue sul
   transiente che vede il marcatore di cancel e entra nel ripiego recuperabile
   (B1-fixato). L'expert viene servito; l'ammissione RAM e' semplicemente saltata.

**Conseguenze dichiarate sul percorso toccato** (non sono neutralita' violata: e' il
fix): le letture di ammissione ora compaiono in `g_transient_pread_calls/bytes`
(riga `[slow-token]`), nei contatori read del worker-prof e nel decode-trace; lo
slack DRAIN3 al primo ingresso transiente non include piu' il burn della load RAM
quando l'ammissione avviene per prima (ora sta DENTRO la finestra sorvegliata).

## B4 (MEDIA) — semantica di `deadline_exhausted` — VERIFICATO, CHIUSO

**Verifica del claim.** Regge: incremento solo al primo ingresso transiente con budget
gia' esaurito (41672-41683, per giunta solo con wprof attivo); le scadenze fra/dopo i
chunk ritornano -1 senza contare (31343-31350, 31419-31423); il campo stampato a
5039-5040 significava «budget gia' esaurito prima della prima pread transiente».

**Chiusura (semantica sistemata, non rinominato).** `WP_DEADLINE_EXHAUSTED` ora conta
le scadenze osservate dalle letture stesse, dentro `cuda_moe_transient_pread_chunked`:
(a) deadline scaduta al check pre-chunk (distinta dal cancel: condizione splittata,
stesso short-circuit di costo sul percorso caldo); (b) cancel-di-deadline del consumer
(`timeout_cancel_sequence` combaciante: il consumer cancella solo dopo aver osservato
la scadenza — 47941-47963); (c) deadline maturata dopo il chunk appena completato.
L'incremento al sito d'ingresso e' rimosso (quel caso ricade in (a) alla prima
chiamata: niente doppio conteggio; `deadline_slack_events/ns` invariati). Ogni chiamata
puo' incrementare al piu' una volta (ritorna al primo -1); i ripieghi (deadline 0.0,
marcatori azzerati) non contano. Semantica finale del campo stampato:
«numero di letture transiente terminate da scadenza della deadline». Resta sotto
wprof, com'era. Fuori perimetro dichiarato: le scadenze dentro il ramo QD
(`route-io-qd-timeout`) hanno gia' il loro terminale e non passano da questo contatore.

---

## Vincoli di mandato — conformita'

- **Sempre attivi, nessun flag nuovo**: B1/B2/B3/B4 sono correzioni incondizionate dei
  soli percorsi difettosi; a `TRANSIENT_TIMEOUT_RECOVERABLE=0` il ripiego resta
  inesistente com'oggi (B1 vive solo dentro il ripiego; B2/B3/B4 sono correttezza).
- **Neutralita' al byte su flag/percorsi non toccati**: promozione (37162) byte-identica
  (parametri default); ramo QD testualmente intatto; percorsi all-hit/RAM non passano
  da nessun sito modificato. Unica eccezione strutturale, motivata sopra: il tipo del
  campo deadline (B2) — stesso layout, stessi valori, ordering piu' forte anche nei
  siti freddi non annotati (init/reset/teardown), che restano testualmente identici.
- **Nessuna struct condivisa cambiata di layout**: provato con `static_assert`
  (size+alignment+lock-free) nel punto della dichiarazione.
- **Zone di altri agenti non toccate**: teardown/release :37707-37735 (nessun hunk;
  la lettura a 37718 resta testualmente identica e valida sull'atomic), ledger
  :28400-28700, budget host-pin :4017-4052 e :17281-17298, sharedcore/ds4.c — nessun
  hunk in quei range/file.
- **git apply --check pulito** sul tree corrente: verificato (e riapplicazione e2e
  con confronto hash).

## Residui dichiarati (fuori mandato, non patchati)

1. `cuda_moe_tiering_stage_observed_quant_cold_to_2bit_ram` (37162) continua a usare
   la `os_pread` bloccante: e' il percorso di promozione fuori dal servizio route;
   l'audit non lo indicava e portarlo sotto lo stesso slot cancellabile richiederebbe
   di provare chi lo esegue (lo slot transiente e' single-owner del route worker).
2. La deadline della richiesta resta `const` per tutta la richiesta (interferenza I1
   dell'audit, esplicitamente non classificata come B): dopo un ripiego, i miss
   successivi della stessa richiesta partono con budget gia' scaduto. Invariato.
3. Slot lasciato pending dopo `cancel-ack-timeout`: puo' far fallire con `pread` la
   richiesta successiva finche' il kernel non completa il cancel (il poll `pending()`
   della prossima pread lo raccoglie da solo appena completo). Identico al
   comportamento pre-patch nello stesso scenario; l'alternativa (riuso) e' il bug B1.
