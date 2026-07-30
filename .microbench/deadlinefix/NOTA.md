# DEADLINEFIX — deadline transiente adattiva, senza kill del route worker

Data: 2026-07-30. Base: tree corrente post-timeoutfix + fd0fix.
Applicazione: `git apply .microbench/deadlinefix/deadlinefix.patch`.
Patch: solo `ds4-p4a/ds4_cuda.cu`. Nessuna compilazione e nessun server avviato.

## SHA-256

| Oggetto | SHA-256 |
|---|---|
| `ds4-p4a/ds4_cuda.cu` prima | `f96582e583ef531dd4102b38134223ff674e77c2b0a37bfd64f3509cbc4e8f37` |
| `ds4-p4a/ds4_cuda.cu` dopo `git apply` | `1e5d1bbbca2940a453b64f49885e2782f0de3f018f9e382f31a75ba8477da3af` |
| `deadlinefix.patch` | `73d41af8e0549e0975f0cb74356db51da4556bbb77f1cb7cf15a35958c2794d7` |

`git apply --check` è pulito sul tree corrente. La patch è stata inoltre applicata
end-to-end a una copia fresca: il contenuto risultante, normalizzati i soli EOL, è
identico alla copia revisionata; l'hash “dopo” sopra è quello dei byte realmente
prodotti da `git apply` sul file CRLF corrente.

## Flag e policy

Tutto il nuovo comportamento è dietro
`DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE=1` (default spento). L'adaptive implica il
recovery transiente anche se `DS4_CUDA_TRANSIENT_TIMEOUT_RECOVERABLE` non è stato
impostato; con il nuovo flag spento il recovery e il watchdog storici restano
testualmente nei loro rami originali.

La lease di una lettura è:

`clamp(base_s + requested_MiB * per_mb_s, floor_s, cap_s)`.

- `base_s`: valore di `DS4_G133_TRANSIENT_IO_TIMEOUT_S`;
- `per_mb_s`: `DS4_CUDA_TRANSIENT_DEADLINE_PER_MB_S`, default `0.050`;
- `floor_s`: `DS4_CUDA_TRANSIENT_DEADLINE_FLOOR_S`, default `base_s`;
- `cap_s`: `DS4_CUDA_TRANSIENT_DEADLINE_CAP_S`, default
  `max(5.0, floor_s)`; un cap sotto il floor viene alzato al floor.

La policy completa viene loggata una volta come `[transient-deadline] adaptive=1`.
Con la taratura di collaudo `base=0.25`, floor e cap predefiniti sono 0.25 s e
5.0 s: una slice paga base + byte; un expert intero da 6.75 MiB riceve circa
0.588 s quando la sua dimensione è usata per la pubblicazione iniziale, mentre
ogni tensore e ogni gruppo QD ricevono la lease dei propri byte effettivi.

## Rinnovo e chiusura di I1

`cuda_moe_transient_pread_chunked` crea una lease nuova a ogni lettura, quindi la
`const transient_request_deadline` non viene più riusata come budget già scaduto
sui miss successivi. Dopo ogni chunk completato pubblica prima
`route_transient_read_bytes`, poi rinnova atomicamente la deadline in proporzione
ai byte restanti; a tensore completo la disarma. Il consumer continua a usare il
ramo progress-aware esistente: osservato un aumento dei byte, riallinea
`last_read_progress`/`wait_deadline` alla lease pubblicata dal worker.

Lo stesso protocollo copre le letture di ammissione e QD4. QD4 calcola la lease
sulla somma degli span ancora richiesti e la rinnova sui completamenti; se scade,
drena tutti gli OVERLAPPED e passa al percorso sincrono per-expert, invece di
rendere il timeout terminale.

## Gerarchia di recovery e backoff

Con adaptive attivo:

1. scadenza senza progresso: breve grace della sola lettura corrente; nessun
   `route_stop`, join o invalidate;
2. il worker aspetta l'ack dell'eventuale cancel, fa 10 ms di backoff e ritenta
   soltanto i tensori non completi con una lease nuova;
3. se anche il retry scade, fa 25 ms di backoff e rilegge i soli tensori non
   completi col medesimo percorso cancellabile ma senza deadline;
4. solo dopo 5 s senza byte nel fallback il consumer cancella la singola pread.
   Rimane sullo stesso `sequence` finché il worker pubblica `ready/failed`.

Nei rami adaptive `consumer-transient-deadline`, `consumer-transient-stall` e
`consumer-starved` non chiamano più `cuda_moe_route_worker_cancel_and_join` e non
invalidano la cache. Il kill resta disponibile per perdita reale del worker
(`route_stop`/`route_worker_failed`), corruzione di mailbox, teardown e altri
terminali di integrità: non è più una reazione a una lettura lenta.

## Invarianti dei byte pubblicati

- Retry chunked: prima del riuso dello slot si esige
  `os_pread_cancellable_pending()==0`; OVERLAPPED e buffer non sono mai riusati
  mentre il kernel li possiede. Le parti incomplete vengono sovrascritte nello
  staging non pubblicato.
- Fallback senza deadline: usa gli stessi offset, dimensioni e staging del
  percorso esatto; H2D/publish restano dopo il completamento di gate/up/down.
- QD4: `cancel_pending` attende e raccoglie ogni I/O prima che la rilettura
  sincrona possa sovrascrivere lo staging.
- Cancel finale: il consumer non restituisce né riusa la mailbox; aspetta la
  pubblicazione terminale del worker. Quindi nessun caso rende leggibili byte
  parziali o non pubblicati.

## Diagnosi causale e `deadline_exhausted`

La riga finale `[transient-deadline]` espone tre contatori mutuamente esclusivi,
classificati una sola volta per sequence:

- `slow_io`: deadline osservata con pread/QD marcata in volo;
- `cpu_contention`: deadline senza I/O in volo, oppure worker non ancora
  pubblicato/schedulato;
- `eviction_storm`: precede le altre due se ci sono almeno 4 sfratti del model
  cache dalla precedente richiesta route.

Sono esposti anche `read_retries`, `no_deadline_fallbacks` e
`final_read_cancels`; `worker_kills_for_slow_read` è dichiarato sempre zero.
`deadline_exhausted` conserva la semantica corretta di timeoutfix: conta letture
terminate dalla deadline. Un chunk che completa e rinnova la lease non lo
incrementa; pre-check scaduto, cancel di deadline e timeout QD adattivo sì.

## Neutralità e perimetro

A flag spento: nessuna policy viene inizializzata o loggata; deadline, valori
atomici, byte letti/pubblicati, recovery storico, terminali e log restano quelli
del tree corrente. Non è stato aggiunto né modificato alcun campo di struct.
Nessun hunk tocca allocatore range 8481–9200, teardown/ledger, host-pin budget,
precheck route worker, nextnfix o indexerzc.

## Criterio di accettazione

Collaudo obbligatorio (non eseguito per vincolo): con
`DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE=1`,
`DS4_G133_TRANSIENT_IO_TIMEOUT_S=0.25`, NextN `PIN=2`, `K=5`, il braccio deve
superare il token 3 senza restart/kill del route worker e senza
`cache-invalidate site=consumer-starved`. La riga finale deve mostrare
`worker_kills_for_slow_read=0`; eventuali lease scadute devono risultare in uno
dei tre contatori causali.
