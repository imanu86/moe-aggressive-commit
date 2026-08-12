# DSPARK-2 — gate del caricamento, ciclo di draft k=7 su CPU, innesto nel batch-verify

Data: 2026-07-29. Tree bersaglio: `ds4-p4a`. Pezzi 3-5 di `.microbench/pilot/DSPARK.md`,
sopra i pezzi 1-2 di `.microbench/dspark1/` (già applicati al tree).

## Esito

`dspark2.patch` tocca solo `ds4-p4a/ds4.c`: 750 inserimenti, 11 rimozioni (11 righe
sostituite, nessuna cancellata di semantica). Niente modifiche a `ds4_cuda.cu`,
`ds4_server.c`, `ds4_cli.c` o header. `git apply --check` PASS sul tree corrente.
Non compilato, nessun server avviato, `D:\` mai scritto (mai letto, in effetti).

Tutto è dietro `DS4_NEXTN_CPU_DRAFTER=1` (default 0). A flag spento il nuovo codice
eseguito è: una `getenv` a engine-open, un AND booleano su un campo engine nel probe
MTP per token, un test booleano in testa a `eval_speculative`, e check `s->nextn ==
NULL` (sempre veri) in invalidate/rewind/free e nei due hook ledger. Nessun kernel,
nessun thread, nessuna allocazione, nessun percorso caldo alterato.

## Pezzo 3 — i due gate del caricamento

### (a) Dispatcher CUDA "zero-silenzioso" → modulo in RAM, servito al forward CPU

Stato di fatto (verificato sul tree): il loader NON carica mai il modulo MTP in VRAM.
`model_open(&e->mtp_model, ...)` (ds4.c:21386) lo mmappa in RAM host e il percorso GPU
lo streamma per-chiamata dalla mappa; l'unico impegno lato CUDA è
`ds4_gpu_set_mtp_model_map_range` (chiamata a ds4.c:21518), che fa `cudaHostRegister`
dell'intera finestra tensori (~3,6 GiB pinned + device pointer zero-copy,
`g_mtp_model_registered_*` in ds4_cuda.cu:1090-1096, release a 3715). A morire coi
routed Q4_K è il dispatcher: `routed_moe_launch_impl` (ds4_cuda.cu:47515) accetta solo
IQ2/Q2, IQ1_S, Q1_0 e ritorna 0 su Q4_K (predicato a **ds4_cuda.cu:47595-47600**) →
"mtp probe draft failed" a ogni token. Il ramo MTP di `ds4_gpu_routed_moe_one_tensor`
instrada su `routed_moe_launch_impl<false>`: stesso predicato, stesso esito.

Il gate del patch, con `DS4_NEXTN_CPU_DRAFTER=1` (engine-open):

- richiede `--mtp` e backend GPU, ed è **mutuamente esclusivo con
  `DS4_G132_CPU_LANE=1`** (fail-closed: la lane pool ha uno slot di submit singolo);
- inizializza una-tantum la G132 lane pool (`ds4_g132_lane_parallel_init`);
- **salta la registrazione secondaria CUDA**: il modulo resta mmap host pageable
  (niente 3,6 GiB pinned, niente VRAM, log `[nextn-cpu] secondary CUDA map
  registration skipped`);
- spegne il probe draft GPU in `ds4_session_eval_internal` (`mtp_should_draft &&=
  !e->nextn_cpu_drafter`): il dispatcher zero-silenzioso non viene mai più raggiunto
  dal percorso MTP;
- alza `e->mtp_draft_tokens` a `max(attuale, 2, DS4_NEXTN_DRAFT_K)` così il server
  ingaggia il percorso speculativo senza dover coordinare `--mtp-draft`.

I tensori GPU piccoli del graph MTP (mtp_embed/state_hc/raw_cache, pochi MB) restano
allocati come oggi: `metal_graph_eval_mtp_draft*` ha i null-guard e comunque non viene
più chiamato sotto flag.

### (b) Predicato del loader che rifiuta il Q1_0 — NON toccato, solo documentato

`tensor_is_routed_expert_type` (**ds4.c:3040-3045**) include IQ2_XXS, IQ1_S, Q2_K,
Q4_K e **omette Q1_0 (type 41)**; `tensor_expect_routed_expert` (ds4.c:3074-3088)
esce con "expected a routed expert quant type" via `mtp_weights_validate_layout`
dentro `mtp_weights_bind` (ds4.c:3762). In più, anche correggendo il predicato, la
route Q1_0 dalla mappa MTP resta fail-closed nel selected loader (analisi AS citata
dal dossier). Il Q1_0 resta fuori come da mandato: rischio qualità (cosine 0,798-0,793
vs Q4K) non superato. Il patch non tocca nulla qui.

## Pezzo 4 — il ciclo di draft k=7 su CPU, sovrapposto

### Pipeline

Il verify si ingaggia solo a `temperature<=0` (ds4_server.c:7484-7486, righe
verificate: la condizione attuale è esattamente `temperature <= 0.0f &&
ds4_engine_mtp_draft_tokens(s->engine) > 1 && !DS4_MTP_SPEC_DISABLE`), dove
`ds4_session_sample` è `sample_argmax`. Quindi **alla fine di ogni ciclo speculativo
il prossimo token vero è già determinato**: lì (`ds4_nextn_cycle_end`) il patch fa il
kick del ciclo successivo con:

- ancora = HC backbone della frontiera committata (D2H 64 KB, stessa classe del ponte
  lane misurato): `g->cur_hc` dopo un decode a un token, oppure la riga
  `commit_drafts-1` di `g->batch_cur_hc` dopo un batch-verify;
- token = `argmax(s->logits)` (il token che il server campionerà);
- posizione, ultima posizione valida della KV, eos, flag di reset.

Il worker (un thread per sessione, creato a `ds4_session_create` sotto flag) genera
fino a k draft autoregressivi col forward dei pezzi 1-2
(`ds4_mtp_cpu_forward_nextn_q4_k`): passo j consuma il token alla posizione p (prima
il token vero, poi il draft precedente) con lo stato HC del passo precedente e RoPE p,
ed emette il draft per p+1 — lo stesso contratto della ricorsione GPU
(`metal_graph_eval_mtp_draft_from_hc`, ds4.c:16784). Il ciclo si sovrappone al decode
GPU del token corrente e allo streaming del server; al rendezvous successivo
(`ds4_nextn_drafter_take`, chiamato dentro `eval_speculative` subito dopo l'eval del
token vero) si prende **quello che c'è, mai attesa**: k effettivo = min(pronti,
draft_cap). Un job pendente è valido solo se ha predetto esattamente quel token a
quella posizione; altrimenti viene consumato e la finestra KV marcata per reset.

`DS4_NEXTN_DRAFT_K` (default 7) è clampato a 16, il k del verificatore
(`drafts[16]`, ds4.c:22677); al call-site vale anche il clamp esistente su
`draft_cap` (budget, ctx, accepted_cap).

### KV del modulo su CPU: holdback di riga e riconciliazione

La cache CPU del modulo (dspark1) è una finestra **scorrevole** (`kv_cache_push_raw`,
ds4.c:8162: memmove di una riga quando piena), non un ring col contatore come la GPU.
Perché l'attenzione resti coerente le righe devono essere posizioni contigue che
finiscono all'ultima posizione processata. Il patch quindi:

- **row-holdback**: il draft i è consegnabile solo quando il passo i+1 ha scritto la
  riga KV della sua posizione di commit; il worker esegue un passo extra oltre k
  (riempi-riga, il suo draft non viene mai consegnato). Così un full-accept non lascia
  MAI un buco in finestra. Eccezione: un draft EOS è terminale per la richiesta ed è
  consegnabile subito;
- **riconciliazione worker-side**: le mutazioni KV stanno TUTTE sul thread worker. Al
  job successivo il worker droppa le righe oltre la posizione committata
  (`n_raw -= drop`) o resetta la finestra su qualunque discontinuità (rewind,
  invalidate, predizione sbagliata, salto di prefill, drop > n_raw). Il decode thread
  non tocca mai la KV.

### Pool: i worker della lane, senza corse

Il ciclo gira nei worker della **G132 lane pool esistente**. Due vincoli rispettati:

1. la pool globale del processo ha un solo slot fn/ctx/done e "does not support
   concurrent submitters" (commento G132 in ds4.c): il thread drafter **pinna il suo
   `g_parallel_depth` thread-local a 1**, così ogni helper esistente riusato dal
   forward (attn Q8, shared, e/h_proj, router) esegue inline invece di submittare a
   `g_pool`;
2. i kernel pesanti di proprietà dspark1/2 — routed Q4_K (3 call-site dspark1) e la
   testa vocab — passano dal nuovo shim `ds4_nextn_parallel_for`, che sui thread
   drafter serializza su un mutex dedicato e submitta alla G132 pool; su ogni altro
   thread è byte-identico a `ds4_parallel_for`. La mutua esclusione col lane vero
   (`DS4_G132_CPU_LANE=1`) è imposta a engine-open.

Costo atteso per passo (stime dossier, da misurare): denso Q8 inline seriale
~15-22 ms + routed Q4_K su pool ~2-3 ms + testa ~13-20 ms ≈ 30-45 ms → in una
finestra di ~250-300 ms il take tipico è k_eff 4-7. La leva di ottimizzazione ovvia
(portare anche il denso sulla pool) è documentata, non tirata: richiederebbe di
toccare helper condivisi col backbone CPU.

### Testa LM su CPU (deviazione motivata dal dossier)

DSPARK.md:203-206 consiglia la testa su GPU (~2 ms). Dal thread worker non è
percorribile senza rischiare corse sull'unico command-context GPU (begin/end_commands
sono del decode thread). La testa è quindi la coda esatta di
`metal_graph_encode_output_head_mtp` replicata su CPU: `head_hidden` (già passato per
HC head + `mtp.0.norm` nel forward dspark1) × matrice output Q8_0 del base (562,6 MB,
riusa `matvec_q8_0_worker` sulla lane pool) + top-2 in un passaggio (greedy draft +
margine). È la riga "tutto CPU" della tabella del dossier (DSPARK.md:93-94); il costo
reale lo dice la telemetria.

## Pezzo 5 — collegamento al verificatore batch

I k draft entrano nel percorso esistente al posto della coppia (probe GPU + catena
from_hc): in `ds4_session_eval_speculative_argmax` (ds4.c:22634), sotto flag,
`drafts[]`/`draft_n` vengono dal take; il ciclo di drafting GPU è saltato
(`for (; !nextn_cpu && ...)`). **La semantica del verify è intatta**: free-check di
`drafts[0]` contro `argmax(s->logits)` (invariato), margin gate (il margine top-2
arriva dal worker invece che da `logits_top2(s->mtp_logits)`), decode2-exact,
`metal_graph_verify_suffix_tops` (ds4.c:17655), commit/replay/rollback: tutti
invariati. `DS4_MTP_KEEP_ACCEPTED`/`mtp_n_raw` (ds4.c:22712, 22719) restano al loro
posto e sotto flag sono inerti (la cache MTP GPU non viene più letta); la
contabilità equivalente su stato CPU è la riconciliazione worker-side del pezzo 4.

A ogni esito di commit c'è un solo hook (`ds4_nextn_cycle_end`): telemetria + kick del
ciclo successivo con l'ancora giusta per quel percorso (cur_hc per margin-skip,
replay e fallback sequenziale; riga batch per full/partial/prefix-1; nessun kick sui
percorsi decode2-exact strict, che tengono gli stati HC in view locali — il ciclo
dopo si auto-rialimenta dal proprio eval).

### Telemetria

Per ciclo (stderr, solo a flag acceso):

```
ds4: [nextn-draft] cycle=N src=live|late|stale k_gen=G k_delivered=D k_accepted=A draft_ms=T accept_pos=1,1,0,-,-,-,-
```

`k_gen` = passi completati dal worker al momento del take; `late` = catena giusta ma
non pronta; `stale` = job per una traiettoria non presa. A fine richiesta (hook in
`ds4_session_vram_ledger_request_end`, che il server chiama già a 7742):

```
ds4: [nextn-draft] summary cycles=... k_gen=... k_delivered=... k_accepted=... draft_ms_avg=...
ds4: [nextn-draft] summary pos=i offered=... accepted=... rate=...   (per i=1..k)
```

`rate` per posizione è l'accettazione media condizionale per posizione — il numero
che chiude il buco T0.3 del dossier, stavolta live.

## Flag

| Flag | Default | Effetto |
|---|---|---|
| `DS4_NEXTN_CPU_DRAFTER` | 0 | 1 = drafter NextN su CPU: modulo in RAM, probe GPU spento, ciclo async + innesto verify |
| `DS4_NEXTN_DRAFT_K` | 7 | draft per ciclo, clamp 1..16 (k del verificatore) |

Invarianti richiesti dal runtime: `--mtp <gguf>` presente, backend GPU,
`DS4_G132_CPU_LANE` non attivo. `DS4_MTP_SPEC_DISABLE=1` continua a spegnere tutto il
percorso speculativo (drafter incluso, che resta idle).

## Correzioni/osservazioni su dossier e dspark1 (punti toccati)

1. **DSPARK.md:210-211** ("sostituire le due chiamate di drafting GPU ... la
   contabilità KEEP_ACCEPTED/mtp_n_raw migra su stato CPU"): migrare la contabilità
   *letteralmente* avrebbe portato con sé un artefatto del percorso GPU: su
   full-accept `DS4_MTP_KEEP_ACCEPTED(draft_n)` marca valide `base+draft_n` righe ma
   la catena ne ha scritte `base+draft_n-1` (`from_hc` scrive la riga della posizione
   del token in ingresso e incrementa a ds4.c:16893; il probe è già contato in
   `mtp_base_raw` a ds4.c:22712) → la riga dell'ultima posizione accettata resta
   slot stale del ring, dentro la finestra del ciclo dopo. Sul ring GPU è
   un'approssimazione tollerata; sulla cache CPU *scorrevole* di dspark1 sarebbe un
   buco strutturale (le righe devono essere contigue). Per questo la versione CPU usa
   row-holdback + passo riempi-riga invece del contatore. Non è un blocco: è una
   deviazione deliberata, documentata qui, e l'artefatto GPU resta intatto perché quel
   percorso non è toccato.
2. **DSPARK.md:203-206** (testa su GPU): non percorribile dal worker senza un lock sul
   command-context che il mandato vieta di introdurre sul percorso caldo; scelta la
   riga "tutto CPU" della stessa tabella. Leva futura, non un difetto.
3. **DSPARK.md sez. 3 / contratto del primo draft**: il primo passo pipelined ancora
   su (HC@ultimo committato, token successivo) — la coppia "token corrente + hidden
   dell'ultimo forward" descritta dal dossier stesso — mentre il probe GPU usa la
   coppia stessa-posizione (HC@p, token@p). È un draft[0] con conditioning "classe
   pos-2": l'accettazione per posizione della telemetria è il misuratore. Nessun
   numero del dossier viene invalidato.
4. **dspark1/NOTA.md** ("Rollback della lunghezza KV dopo verifica e gestione
   accepted-prefix restano fuori mandato"): coperti qui; il decremento `n_raw` è
   legittimo sulla cache scorrevole solo per le righe più nuove, ed è esattamente
   l'unico caso usato (drop della coda rifiutata). Dopo uno slide le righe più
   vecchie sono perse: la finestra può risultare temporaneamente < 128 dopo un drop —
   effetto benigno (SWA più corta per un ciclo), documentato.
5. **Riga approssimata su take-in-ritardo**: se il take arriva prima dell'intake del
   worker (job giusto ma mai partito) e il ciclo committa solo il token vero, può
   restare in finestra al più una riga di traiettoria rifiutata del ciclo precedente
   (stessa classe dell'artefatto GPU del punto 1); ogni discontinuità più seria forza
   il reset.

## Hunk a rischio per il cantiere parallelo (shared1)

Durante la stesura il tree è cambiato sotto i piedi: le modifiche di
`.microbench/shared1/` (ds4.c +~750 righe: accelerator cache ~1860-2060,
instrumentazione print_vec_stats nei kernel Q4_K ~7160-7550, blocco spex_cpu_observe
~10100-10800, encode_decode_layer ~12700-13000) risultano **applicate** al tree.
`dspark2.patch` è generato e verificato **sopra** quel tree: la preimage sotto è
l'unica valida. Hunk dspark2 con contesto vicino a zone shared1 (righe preimage):

- 6778 (shim), 6838/6926/6996 (swap dei 3 call-site Q4_K dspark1): funzioni adiacenti
  all'instrumentazione shared1 a 7160+, nessuna riga di contesto condivisa;
- 9804 (blocco drafter): ~290 righe prima del blocco spex_cpu_observe di shared1;
- tutti gli altri (18332, 19731+, 21398+, 21514, 21555, 22145+, 22573, 22634-23250)
  sono fuori dalle zone shared1.

Se shared1 venisse rigenerato o riapplicato, va riapplicato PRIMA di dspark2 (l'ordine
con cui è nata questa preimage).

## Limiti dichiarati

- `DS4_MTP_FULL_LOGITS` e `DS4_MTP_PROBE` non hanno equivalente sotto flag (il probe
  GPU è spento by design; `mtp_logits` non viene scritto). `DS4_MTP_CONF_LOG` logga
  con margine/top dal worker.
- Percorsi decode2-exact (strict/quality): commit corretti, ma nessun kick (un ciclo
  senza speculazione dopo ciascuno; il flusso si auto-ripristina).
- Prima catena dopo il load: la matrice output (562,6 MB) e il modulo (3,6 GiB) si
  paginano da SSD alla prima passata — warm-up, poi restano in page cache.
- Multi-sessione: i submit drafter sono serializzati da un mutex globale; due sessioni
  in decode simultaneo si spartiscono la lane pool (caso non previsto dal protocollo a
  1 richiesta, ma safe by construction).
- Nessun numero di velocità/accettazione dichiarato: build e run sono fuori mandato;
  la telemetria [nextn-draft] è lo strumento di misura previsto.

## Verifiche eseguite

- `git apply --check .microbench/dspark2/dspark2.patch`: PASS, exit 0, sul tree
  corrente (post shared1).
- `git apply --numstat`: `750  11  ds4-p4a/ds4.c` (unico file).
- Bilanciamento `{} () []` sul file patchato (copia in scratchpad, commenti/stringhe
  esclusi): OK su tutte e tre le coppie.
- Conteggi simboli: 11 call-site `ds4_nextn_cycle_end` (tutti gli esiti di commit),
  take/kick/create/destroy/head/worker ognuno def+uso, 3 swap `ds4_nextn_parallel_for`
  nei kernel dspark1, 8 usi `nextn_cpu_drafter`.
- ds4_server.c:7479/7484-7486 verificati contro il tree corrente (coincidono col
  dossier); nessuna modifica al server.
- Nessuna compilazione, nessun server, `D:\` non toccato.

## SHA-256

Preimage richiesta da `git apply --check` (tree corrente, con dspark1 + logids +
shared1 applicati):

```text
ds4-p4a/ds4.c
8b0e32cac4d2cb3f4a7184d3e7f8423cb2919127487e2643c303751c1c67cdd3
```

Artefatto patch:

```text
.microbench/dspark2/dspark2.patch
531189e06e5051cd3adf6ad1eed4a954967e637fb8684cb991a2e59fac5ad4e6
```
