# DSPARK-2fix — perché il drafter non consegnava, e il fix

Data: 2026-07-29. Tree bersaglio: `ds4-p4a` CORRENTE (dspark1 + logids + shared1 +
dspark2 + drain4fix applicati; preimage sha256 sotto). `dspark2fix.patch`: solo
`ds4-p4a/ds4.c`, 265 inserimenti / 48 rimozioni, tutti dentro codice dspark2 tranne
un inserimento puro (helper di submit) adiacente al blocco shared1 — nessuna riga di
shared1/dspark1/drain4/drain4fix/logids modificata. `git apply --check` PASS.
Niente build, niente server, D:\ non toccato.

## Risposte alle quattro domande

### 4 (per primo, come chiesto): NO, il drafter NON dipende dalla lane accesa

Il candidato è falsificato nel codice, su tre livelli:

- la pool g132 è creata **dal drafter stesso** a engine-open:
  `ds4_g132_lane_parallel_init()` è chiamata nel blocco del flag
  (ds4.c:21981 preimage, dentro `[nextn-cpu] ... enabled`); i worker della pool
  (n_threads-1) esistono e dormono sulla work_cond anche con
  `DS4_G132_CPU_LANE` spento;
- il thread del ciclo di draft è un thread DEDICATO per sessione
  (`os_thread_create` in `ds4_nextn_drafter_create`), non un worker della pool:
  esiste comunque;
- anche se la pool mancasse, lo shim degrada inline
  (`ds4_nextn_parallel_for`, preimage 6805-6813: submit fallita ⇒
  `fn(ctx, 0, n_rows)`): più lento, mai fermo.

**Il runner NON va cambiato**: la lane deve restare spenta (l'esclusione reciproca
a engine-open è deliberata: la pool ha un solo slot di submit). Il nuovo log
`[nextn-cpu] drafter worker online (g132 pool initialized=1 workers=N ...)` lo
certifica a ogni run.

### 1: stale vs late, e perché k_gen=0 in entrambi

In v1 (dspark2): `src=stale` = nessun job valido per (token, posizione) al take —
al ciclo 1 è FISIOLOGICO (il primo kick avviene solo a fine ciclo 1).
`src=late` = il job era GIUSTO (token e posizione predetti correttamente,
`job_first_pos == checkpoint.len-1`) ED era stato preso in carico dal worker
(`pub_seq == job_seq` ⇒ intake avvenuto), ma con 0 passi COMPLETATI al momento del
take: `k_gen` conta i forward completati e `draft_ms` viene scritto alla prima
pubblicazione. Quindi il ciclo 2 del log dice: kick OK, predizione OK, ancora OK,
worker sveglio e DENTRO il primo forward — non "mai partito" ma "mai arrivato in
fondo al passo 1 entro la finestra".

I due src finiscono nello stesso stato vuoto per la **trappola di riavvio di v1**:
ogni take a vuoto CONSUMAVA il job (ds4.c preimage 20146:
`if (d->job_seq != 0) d->job_consumed = true;`) e il cycle_end kickava un job
NUOVO; il worker abbandonava la catena al check tra i passi e ricominciava da zero.
Aggiungi che il primo passo di ogni catena paga il first-touch del mmap pageable
(≈820 MB: attn 113,8 + e/h_proj 35,7 + shexp 26,7 + 6 esperti Q4_K 85 + testa
562,6 — il modulo è NON registrato/NON pinnato by design, gate (a)) e che il
row-holdback richiede 2 passi completati per consegnare 1 draft: se il passo 1
costa ≳ la finestra (~266 ms), il sistema resta in restart perpetuo e non consegna
MAI, esattamente il pattern osservato. A regime caldo il passo stimato è 30-45 ms
e il difetto non si vede; a freddo (o con page cache sotto pressione a ctx 150k)
è fatale.

### 2: il kick avviene sul percorso giusto anche con --quality

Il kick vive in `ds4_nextn_cycle_end` (preimage 20201+), chiamato: sul take a
vuoto, sul free-check miss, e su OGNI esito di commit di
`ds4_session_eval_speculative_argmax`. Con l'assetto del run il server passa da lì:
ds4_server.c:7484-7488 richiede `temperature <= 0` (✓ temp=0), `mtp_draft_tokens>1`
(✓ --mtp-draft 8) e `DS4_MTP_SPEC_DISABLE` assente (✓). `--quality` cambia solo il
VERIFICATORE quando draft_n==2 (decode2-exact: commit corretti ma niente kick,
ANCHOR_NONE — preimage ~23528/23558 — il ciclo dopo si rialimenta da solo); con
k=7 consegnati si va sul batch verify che kicka. La prova che il kick funzionava è
nel log stesso: `cycle=2 src=late` richiede un job che ha predetto ESATTAMENTE il
token committato alla posizione giusta — kick, predizione argmax e intake tutti OK.

### 3: sì, mancava l'osservabilità — aggiunta, una riga per processo per veto

Nuovi log (tutti flag-on only):

- `[nextn-cpu] drafter worker online (g132 pool initialized=%d workers=%u; lane
  env not required)` — all'avvio del thread (risponde in-log alla domanda 4);
- `[nextn-cpu] first chain step done fwd=%.1f ms head=%.1f ms (first-touch
  page-in ... included)` — il PRIMO passo completato nel processo, col costo vero
  del freddo: è il discriminatore paging-vs-wedge. Se nel prossimo run questa riga
  NON appare mai ⇒ il worker è davvero incastrato dentro il passo 1 (wedge);
  se appare con ms alti ⇒ era/è paging;
- `[nextn-cpu] kick veto: anchor D2H read failed (kind=%d row=%u)` — una volta:
  un D2H d'ancora fallito non è più un no-kick silenzioso;
- `[nextn-draft] head argmax failed; chain aborted` — una volta;
- riga per ciclo estesa: `... rebase=%d inflight=%d ...` — `inflight` = passo che
  il worker sta calcolando al momento del take (0 = fermo): distingue "sta
  macinando il passo 1" da "non è mai partito" anche senza aspettare il one-shot;
- summary esteso: `kicks= pending= chain_steps= step_ms_avg= step_ms_max=` —
  il costo reale per passo su tutta la richiesta.

## Il fix di design: catena PERSISTENTE con re-base sui commit

La causa primaria (trappola di riavvio) è rimossa cambiando il contratto del
rendezvous (`ds4_nextn_drafter_take`):

- un job che COMBACIA con lo stream committato ma non ha ancora nulla di
  consegnabile resta IN CORSA (`src=pending`): non viene consumato e il ciclo NON
  kicka un job nuovo — il worker conserva la finestra successiva per finire;
- a ogni ciclo il take valida IL token appena committato contro la predizione
  della catena per quell'offset (offset 0 = token del kick, offset j = draft j);
  la validazione è induttiva: un token per ciclo, l'intero span risulta verificato.
  `job_take_expect` impone che i take siano CONTIGUI (un token committato fuori
  dal percorso speculativo, un rewind, un salto ⇒ job morto e finestra KV in
  reset);
- appena la catena SUPERA la frontiera committata, il take consegna la coda
  ri-basata (`drafts[] = pub_drafts[off..]`, `rebase=off` nel log) e da lì il
  flusso torna quello di dspark2 (free-check, batch verify intatto, kick alla
  fine). Il verificatore batch resta l'autorità di correttezza in ogni caso;
- invarianti conservati sotto re-base: il row-holdback vale per costruzione
  (coda ≤ pub_count − off ⇒ la riga KV dell'ultima posizione committabile esiste
  sempre); le righe mantenute dal trim al kick successivo sono solo su posizioni
  validate; morte fuori traiettoria ⇒ `needs_reset`, morte a coda esaurita su
  traiettoria giusta ⇒ nessun reset.

Effetto atteso sul run rotto: la prima catena assorbe il freddo attraverso più
cicli `pending` (invece di essere uccisa ogni 266 ms), poi consegna la coda; le
catene successive partono calde. Se anche così `k_delivered` resta 0, i nuovi
numeri (`step_ms_avg/max`, `inflight`, il one-shot del primo passo) dicono
esattamente dove muore.

## Secondo fix (latente, non la causa di QUESTO run): un solo mutex per la pool

Nel tree corrente la pool g132 ha DUE submitter possibili: il worker
`[shared-cpu]` di shared1 (ds4.c:11318/11323, serializzato sul SUO
`g_shared1_pool_mutex`, 11198-11204) e il drafter dspark2 (che in v1 usava un
mutex PRIVATO). Due mutex diversi = nessuna esclusione reciproca = pool a slot
singolo corrotta (generation/done incrociati, submitter in attesa infinita) la
prima volta che `DS4_CPU_SHARED_EXPERT=1` e `DS4_NEXTN_CPU_DRAFTER=1` girano
insieme. NON è la causa del run osservato (shared1 era dormiente: il gate
`ds4_shared1_env_requested`, ds4.c:1810-1813, richiede l'env e il log
`[shared-cpu] armed` non c'era), ma era una bomba innescata per il primo batch
combinato. Fix: il drafter ora submitta via `ds4_nextn_g132_submit` (definita
accanto al blocco shared1), che serializza sullo STESSO `g_shared1_pool_mutex`
usando la once-init di shared1 — zero righe di shared1 toccate, ordine di
armamento indifferente. Il mutex privato di v1 è rimosso.

## Telemetria: formato aggiornato

```
ds4: [nextn-draft] cycle=N src=live|pending|stale|dead k_gen=G k_delivered=D
     k_accepted=A rebase=R inflight=S draft_ms=T accept_pos=1,1,0,-,-,-,-
ds4: [nextn-draft] summary cycles=... k_gen=... k_delivered=... k_accepted=...
     kicks=... pending=... chain_steps=... step_ms_avg=... step_ms_max=...
     draft_ms_avg=...
ds4: [nextn-draft] summary pos=i offered=... accepted=... rate=...
```

`src`: `live` consegna; `pending` catena giusta ancora in corsa (niente kick);
`stale` nessun job utilizzabile / traiettoria divergente (reset + kick);
`dead` catena conclusa senza coda utile su traiettoria giusta (kick, no reset).

## Hunk del patch (righe preimage)

6788 (shim: mutex condiviso + guardie NO_GPU), 9907/9933 (campi struct),
9995-10102 (worker: online/first-step/head-fail/inflight/pub_done/stats),
11203 (+`ds4_nextn_g132_submit`, inserimento puro dopo
`ds4_shared1_pool_mutex_init` — unico hunk con contesto shared1, nessuna riga
shared1 modificata), 20119 (take ri-scritto), 20189 (kick: `job_checked`,
`job_take_expect`, contatore, veto log), 20208/20219 (cycle_end: src/rebase/
inflight/pending), 20244 (request begin/end: reset + summary esteso),
23319 (call-site take: firma + pending ⇒ ANCHOR_NONE).

## Verifiche eseguite

- `git apply --check .microbench/dspark2fix/dspark2fix.patch`: PASS sul tree
  corrente; `--numstat`: `265  48  ds4-p4a/ds4.c` (unico file).
- Bilanciamento `{} () []` sul file patchato: OK.
- Zero residui dei simboli rimossi (`cycle_stale`, mutex privato v1).
- drain4fix verificata: tocca solo `ds4_cuda.cu` — nessuna interazione coi miei
  hunk; il predicato zero-silenzioso resta a ds4_cuda.cu:47595-47600 nel tree
  corrente.
- Nessuna compilazione, nessun server.

## SHA-256

Preimage (tree corrente al momento della consegna):

```text
ds4-p4a/ds4.c
c603f9527e816092e7446da971346f479d599ae8b6725a65ede47e2b510515a2
```

Artefatto patch:

```text
.microbench/dspark2fix/dspark2fix.patch
391323556c437bf0cd7a6b42092a24ef8ae378301debcc6627b5c69a753b707b
```
