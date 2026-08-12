# Analisi di fattibilità: MTP, DSpark e SPEX sul substrato CPU

Data: 2026-07-29.  
Perimetro: analisi statica e aritmetica; nessuna build, nessun server, nessuna
modifica al runtime.

## Verdetto

L'idea A è fattibile **come pilota di prefetch a qualità invariata**, ma non con
uno dei tre motori preso così com'è:

- SPEX/SPX1 è già veloce abbastanza, ma predice il routing del **layer successivo
  dello stesso token**, non le 43 route del token successivo. Il suo anticipo è
  un layer, non 10-20 layer né un token.
- MTP può fornire il token draft, ma la “testa” è in realtà un mini-transformer
  MoE completo. Su CPU non esiste ancora il suo executor e il solo token draft
  non contiene le route dei 43 layer target.
- Il forward Q1 top-1 è la sola strada che può trasformare un token draft in una
  lista `(layer, expert)`. Con i numeri oggi disponibili il suo pavimento è
  circa **4,806 ms/layer**: sotto 5 ms nominali, ma senza margine. Aggiungendo il
  pavimento della testa MTP si arriva a **5,203 ms/layer equivalente**.

Quindi:

- nel regime pre-cliff da 5,1 ms/layer, MTP + forward Q1 top-1 **non prende
  anticipo**;
- nel regime post-cliff da 6,9 ms/layer può mantenere il passo e costruire circa
  10 layer di anticipo, ma non 20;
- il pilota da fare è un **route-forward CPU dedicato, approssimato e
  token-ahead**, con obiettivo p95 non superiore a 3,5 ms/layer per una finestra
  di 10 layer pre-cliff. Il kernel Q1 da 294 µs/expert è un componente
  sufficiente, non ancora il forward sufficiente.

L'idea B è più lontana. Il validatore e il batch layer-major esistono davvero,
ma:

1. manca un ingresso pubblico per una sequenza draft prodotta dalla CPU;
2. la MTP Q1_0 non supera il loader corrente;
3. la Q4_K non è “classe int8” e in campagna non ha prodotto un singolo draft
   utilizzabile;
4. per `k>2` esiste il batch generico, non un verificatore bit-exact equivalente
   al decode autoregressivo.

Ordine raccomandato: **T0 oracle/tracce → T1 prefetch-only → T2 commit N=2 →
solo dopo DSpark k>2**. Non conviene riaprire T2 prima che T1 abbia dimostrato
che il route-forward è puntuale e non genera traffico sprecato.

## Correzioni delle premesse

### Gli asset MTP non hanno le dimensioni/precisioni indicate

I file presenti oggi sono:

- `C:\ds4-models\DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf`:
  **3.807.602.400 byte**;
- `C:\ds4-models\DeepSeek-V4-Flash-MTP-Q1_0-Q8_0-F32.gguf`:
  **1.089.693.408 byte**.

Gli stessi numeri e hash sono nel ledger
(`reap-loop-ledger-main/docs/EXPERIMENTS_LEDGER.md:15942-15950`). Il file da
1,09 GB è Q1_0, non Q4K.

Q4_K non è int8. I tre stack routed della Q4K occupano 3.623.878.656 byte; nella
Q1_0 occupano 905.969.664 byte
(`EXPERIMENTS_LEDGER.md:15544-15555`). Che attention/shared siano Q8_0 non rende
la parte routed “classe int8”. L'evidenza Colibri citata nel mandato dice anzi
che, per il commit, servirà verosimilmente una parte routed realmente int8 o un
mix di precisione con accettazione misurata: nessuno dei due asset presenti
soddisfa oggi quella descrizione.

### “Mai caricati in campagna” è vero solo per l'esecuzione utile

La Q4K è stata aperta e dichiarata loaded; il probe ha poi fallito il draft
32 volte su 32 perché il dispatcher non serve quel formato
(`EXPERIMENTS_LEDGER.md:15854-15879`). È anche il modulo che, in un'altra prova,
ha prodotto circa 2.000 ms/token e ~1.094 sfratti/token
(`EXPERIMENTS_LEDGER.md:17343-17345`). La Q1_0 è stata aperta dal loader, ma ha
fallito prima della readiness con:

```
type 41 (q1_0), expected a routed expert quant type
```

(`EXPERIMENTS_LEDGER.md:16157-16178`). Il difetto è ancora nel sorgente
corrente: `tensor_is_routed_expert_type()` accetta IQ2_XXS, IQ1_S, Q2_K e Q4_K
ma omette Q1_0 (`ds4-p4a/ds4.c:2907-2912`), pur avendo Q1_0 nello switch dei
byte/blocco (`ds4-p4a/ds4.c:2914-2920`).

### La “testa MTP” non è una sola proiezione

Il binder richiede proiezioni HC, embedding/history projection, attention, un
router a 256 esperti, tre stack routed e lo shared expert
(`ds4-p4a/ds4.c:3629-3667`). È un 44° blocco MoE, coerente con la tempesta di
sfratti già misurata, non una matrice logits economica.

### Lo SPX1 trovato esiste, ma ha semantica next-layer

Artefatto:

```
runs/spex/spex_model/ds4flash_d2_nextlayer.spex
size   90.177.568 byte
SHA256 A86288C3A29BE97179230A3ED86EEBDCD7293AB33987ED7AA57850213325F3C7
```

Il runtime usa `ffn_norm` del layer `L`, seleziona lo slice SPX1 di `L` e marca
la previsione per `L+1` (`ds4-p4a/ds4.c:10279-10358`). La comparazione avviene
poi contro gli esperti reali di quel layer
(`ds4-p4a/ds4.c:10449-10486`). Dunque non è un predittore del token successivo.

Sul DS4 corrente, inoltre, la recall reale K6 è circa 31-32%, non la recall
0,83/0,96/0,99 del ledger E9. E9 è Qwen3-30B e non è trasferibile
(`EXPERIMENTS_LEDGER.md:115-124`). La misura DS4 online è 20.720/64.512 =
32,12% (`ds4-p4a/G13_SPEX_HIDDEN_DRY_RUN_RESULTS.md:106-115`); il profilo K1
ha recall 8,95% e precisione 53,70%
(`ds4-p4a/G15_SPEX_CAP_PROFILE_RESULTS.md:35-40`).

### `DS4_MTP_BATCH_VERIFY` non spegne tutta la speculazione

Il gate server è effettivamente:

```
temperature <= 0
mtp_draft_tokens > 1
DS4_MTP_SPEC_DISABLE assente
```

(`ds4-p4a/ds4_server.c:7484-7488`). Però
`DS4_MTP_BATCH_VERIFY` presente rende falso **solo**
`use_decode2_exact` (`ds4-p4a/ds4.c:21301-21310`) e devia sul batch generico
(`ds4-p4a/ds4.c:21406-21448`). È quindi l'interruttore di spegnimento del
verificatore exact N=2, non del validatore/speculatore nel suo complesso.

## 1. Ritmo

### A. SPEX hidden GPU

Il peso letto per score è:

```
4096 × 256 × 2 byte = 2.097.152 byte = 2 MiB/layer
43 × 2 MiB = 86 MiB residenti
```

La costruzione/allocation usa esattamente
`43 × 4096 × 256 × sizeof(uint16_t)` (`ds4-p4a/ds4.c:10186-10230`).

La migliore quota disponibile è l'A/B J23:

```
decode score/topK = 51,617 s / 160 token
decode baseline   = 50,543 s / 160 token
delta             = 1,074 s / 160 = 6,7125 ms/token
score eseguiti    = 42/token
quota osservata   = 6,7125 / 42 = 0,160 ms/layer predetto
```

I numeri grezzi sono in `EXPERIMENTS_LEDGER.md:371`. È largamente sotto 5
ms/layer. Non è però un pilota token-ahead; concede solo il resto del layer `L`
per preparare `L+1`. La D2H/event chain ha già misurato un -2,8% con ring4
(`ds4-p4a/G14_SPEX_ASYNC_RING_RESULTS.md:75-80`).

Conclusione SPEX: **ritmo PASS, semantica FAIL per l'idea della finestra
token-ahead**. Può restare come segnale aggiuntivo/confidence gate, non come
motore principale.

### B. MTP head-only su CPU

Non esiste oggi un executor MTP CPU: `ds4_engine_has_mtp()`/draft tokens
escludono il backend CPU (`ds4-p4a/ds4.c:18498-18502`) e l'API pubblica espone
solo eval normale/speculativo, non eval MTP CPU
(`ds4-p4a/ds4.h:168-184`).

Si può però quotare un **pavimento**, non una misura. Nella MTP Q1_0:

```
routed attivi = 6 × 3.538.944 = 21.233.664 byte
resto MTP     = 1.089.693.408 - 905.969.664 = 183.723.744 byte
working read  ≈ 204.957.408 byte/draft
```

Audit0 implica:

```
banda CPU effettiva = 3.538.944 byte / 294,4 µs = 12,02 GB/s
pavimento MTP       = 204.957.408 / 12,02 GB/s = 17,05 ms/draft
```

Audit0 documenta sia 294,4 µs/expert sia 3.538.944 byte/expert
(`tools/audit0_microbench/results_cpu.md:6-24`,
`tools/audit0_microbench/results_cpu.md:48-62`). I 17,05 ms sono ottimistici:
ignorano overhead, formati Q8/F32 diversi, attention/KV, router, logits e jitter
Windows. Una prima soglia realistica è p95 **≤25 ms/draft**.

Spalmato sul token target:

```
17,05 / 43 = 0,397 ms/layer
```

ma questa divisione vale solo per il budget di pipeline. La testa produce un
token, non 43 route; da sola non promuove nulla.

### C. Forward approssimato Q1 top-1

Assumendo come dato il pavimento backbone full-precision di 194 ms/token e un
solo expert Q1 completo per layer:

```
expert Q1 = 43 × 0,2944 = 12,6592 ms/token
totale    = 194 + 12,6592 = 206,6592 ms/token
per layer = 206,6592 / 43 = 4,806 ms/layer
```

È nominalmente sotto 5 ms, ma il margine è solo:

```
5,1 - 4,806 = 0,294 ms/layer
43 × 0,294 = 12,6 ms/token
```

Quindi non arriva 10-20 layer avanti. Inoltre il codice corrente ha solo il
kernel expert Q1, non un backbone CPU approssimato Q1/top-1 completo.

### Combinazioni e anticipo reale

MTP CPU + route-forward Q1:

```
17,050 + 206,659 = 223,709 ms/token
223,709 / 43 = 5,203 ms/layer equivalente
```

Pre-cliff:

```
GPU target = 43 × 5,1 = 219,3 ms/token
pilota     = 223,7 ms/token
```

Il pilota perde circa 4,4 ms/token; non crea una finestra.

Post-cliff:

```
GPU target = 43 × 6,9 = 296,7 ms/token
anticipo   = 296,7 - 223,7 = 73,0 ms
73,0 / 6,9 = 10,6 layer
```

Per ottenere davvero una finestra `W`, includendo 17,05 ms di startup MTP, il
tempo route-forward `r` deve soddisfare:

```
43 × (GPU_layer - r) - 17,05 >= W × GPU_layer
```

Da cui:

| Regime | W=10 | W=20 |
|---|---:|---:|
| GPU 5,1 ms/layer | `r ≤ 3,52 ms/layer` | `r ≤ 2,33 ms/layer` |
| GPU 6,9 ms/layer | `r ≤ 4,90 ms/layer` | `r ≤ 3,29 ms/layer` |

Il Q1 top-1 stimato (4,806) passa solo W10 post-cliff. La combinazione con
margine, oggi, è dunque: **MTP token draft + route-forward più aggressivo del
Q1/full-backbone stimato, con target p95 3,5 ms/layer; SPEX opzionale come
confidence, non in serie sul cammino**.

## 2. Tetto del guadagno e tracce ID

### Tracce non recuperate

Non ho trovato le righe ID J17/J31. Ricerca read-only effettuata in:

- `D:\ds4_work` (incluso
  `D:\ds4_work\capture_alllayer_clone\g7_runs`): presenti telemetrie runtime,
  non JSONL con `selected`/`compact_ids`;
- `C:\Users\imanu\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\ds4-win-work`;
- `C:\Users\imanu\source\repos\reap-loop`, incluse le worktree `.claude`;
- `C:\Users\imanu\Documents\Codex`;
- vecchio `/root` WSL: non verificabile, perché su questa macchina non è
  installata alcuna distribuzione WSL.

Il ledger dice che J17 era
`/root/ds4_tiering_observe_html160_ids.jsonl`, 2,4 MB
(`EXPERIMENTS_LEDGER.md:365`), e riporta solo gli aggregati. J31 riporta due
tracce da 6.923 righe, ma non i loro path
(`EXPERIMENTS_LEDGER.md:379`). Senza le sequenze non è possibile inventare
l'overlap `t → t+1`.

### Quello che gli aggregati consentono già di dire

J17:

```
cap128 hit = 0,0000
cap258 hit = 0,3396
cap512 hit = 0,5927
```

J31:

```
cap258 hit = 0,3413 / 0,3450
cap512 hit = 0,6099 / 0,6139
```

(`EXPERIMENTS_LEDGER.md:365,379`).

Quindi la premessa “l'overlap t/t+1 è già sfruttato da LRU” non vale
automaticamente a 140 slot. La stessa chiave `(layer,expert)` viene riusata
solo dopo aver attraversato gli altri 42 layer; con `43 × 6 = 258` richieste
fra due cicli, cap128 misura zero hit e cap140 è ancora sotto un ciclo completo.
L'overlap raw può essere alto e tuttavia essere stato sfrattato prima del token
successivo.

### Oracle perfetto a 140 slot

Una finestra perfetta di 20 layer entra:

```
20 × 6 = 120 slot futuri
+ 6 slot del layer corrente = 126
margine = 140 - 126 = 14 slot
```

Il massimo teorico conservando il layer corrente è W22:

```
22 × 6 + 6 = 138 ≤ 140
23 × 6 + 6 = 144 > 140
```

Con previsione perfetta, promozione conclusa entro la deadline e slot
prefetchabili, l'**hit-at-demand oracle è 100%** dopo il priming per W10 e W20.
Questo non significa zero byte: il costo steady-state è il numero di nuove
chiavi che entrano in coda alla finestra.

Il priming lordo vale:

```
W10: 60 × 7.077.888 = 424.673.280 byte = 405 MiB
W20: 120 × 7.077.888 = 849.346.560 byte = 810 MiB
```

Ogni avanzamento di layer richiede al massimo:

```
6 × 6,75 MiB = 40,5 MiB/layer
```

Al ritmo pre-cliff:

```
40,5 MiB / 5,1 ms = 7,94 GiB/s = 8,33 GB/s circa
```

Il registro trasporti ha visto 6.795 MB/s quando il tubo lavora
(`EXPERIMENTS_LEDGER.md:17314-17316`): senza overlap/reuse non basta; serve
almeno:

```
1 - 6,795 / 8,33 = 18,4% di byte evitati
```

oppure una pipeline H2D più vicina ai ~25 GB/s fisici. Post-cliff:

```
40,5 MiB / 6,9 ms = 5,87 GiB/s = 6,16 GB/s
```

e il tubo misurato può teoricamente tenere il passo.

Il guadagno conservativo massimo è rimuovere il delta post/pre:

```
post = 43 × 6,9 = 296,7 ms/token
pre  = 43 × 5,1 = 219,3 ms/token
delta nascosto = 77,4 ms/token
speedup = 296,7 / 219,3 = 1,353×
```

cioè circa -26% di latenza / +35% t/s. È un tetto conservativo perché i 5,1
ms/layer pre-cliff contengono ancora trasporto; non è lecito promettere di più
senza la traccia e una scomposizione contemporanea.

### Run minimo mancante

Serve un solo run greedy rappresentativo:

```
temperature=0
completion_tokens=160
DS4_EXPERT_TIERING=observe
DS4_EXPERT_TIERING_LOG=<nuovo jsonl>
DS4_EXPERT_TIERING_LOG_IDS=1   # LOG_IDS=1 nel vecchio harness
SPEX/prefetch/mask che alterano il confronto = off
```

Gate di completezza: **6.923 righe = 43 × 161**, con `selected_len=6`,
`compact_ids` validi e chiave token/layer. La strumentazione storica è descritta
in `EXPERIMENTS_LEDGER.md:364-365`, ma il simbolo
`DS4_EXPERT_TIERING_LOG_IDS` non è più presente nel sorgente `ds4-p4a`
corrente: la ricerca nel repo lo trova solo nei ledger. Il run minimo richiede
quindi il vecchio binario/commit J16 oppure il ripristino futuro di quel logger;
non basta impostare oggi la variabile.

T0 deve calcolare, senza runtime mutato:

```
overlap(t,t+1) =
  Σ |E[t,layer] ∩ E[t+1,layer]| / (6 × coppie token-layer)

oracle_hit_W =
  domande presenti e ready nella finestra / domande totali

new_bytes_W =
  Σ nuove (layer,expert) × 7.077.888
```

e separare sempre:

- route del token draft quando il token è corretto;
- route del token draft quando il token è sbagliato;
- hit che LRU140 avrebbe comunque dato;
- nuovi hit realmente attribuibili alla finestra.

Un token draft sbagliato **non “rivela” per definizione** gli esperti del token
vero: mantiene il prefisso, ma cambia embedding e hidden successivi. La qualità
resta sicura perché il token vero è GPU; la precisione di prefetch è però un
dato da misurare, non una proprietà.

## 3. Innesto nel percorso VRAM

### Stato attuale

`vram_promotions` è un contatore, non una coda o un'API
(`ds4-p4a/ds4_cuda.cu:28385`, incrementi
`ds4-p4a/ds4_cuda.cu:39380-39402`). La promozione nasce dentro il route worker
da una richiesta reale del layer corrente: solo se `have_ram` viene chiamato
`cuda_moe_tiering_pick_vram_slot()`
(`ds4-p4a/ds4_cuda.cu:41005-41028`).

`pick_vram_slot()` applica min-frequency, admission gate, budget G133 e scelta
del victim (`ds4-p4a/ds4_cuda.cu:39363-39425`). Non esiste in `ds4_gpu.h`/API
pubblica un ingresso `(layer,expert)` esterno.

Lo SPEX funzionale non è già quell'ingresso:

- accetta solo `DS4_SPEX_PREFETCH_K=1`
  (`ds4-p4a/ds4.c:10160-10165`);
- crea una coda/slab privata a due slot;
- è esplicitamente disabilitato se la resident expert cache è richiesta
  (`ds4-p4a/ds4.c:10239-10263`);
- al consumo copia lo slab nella compact gather, non pubblica una promozione
  tiering (`ds4-p4a/ds4_cuda.cu:44619-44638`,
  `ds4-p4a/ds4_cuda.cu:44850-44868`).

### Può ricevere la lista senza cambiare politica?

**No, non letteralmente.** Anticipare l'ammissione di una chiave mai domandata
è già un cambiamento della politica di admission/tempo. Si può però preservare
la parte importante della politica:

1. nuova intent queue con
   `(epoch, decode_seq, layer, expert, deadline, confidence)`;
2. nessun incremento artificiale di frequency/mass;
3. stesso `pick_vram_slot()` per eligibility, budget e victim;
4. pubblicazione atomica solo dopo read/H2D completo;
5. intent stale/late scartato senza attesa del decode;
6. domanda reale che manca usa il percorso transiente invariato.

Se si vuole il 100% oracle anche al primo tocco, occorre un bypass di
min-frequency: quello è esplicitamente una nuova policy
“prefetch lease/JIT”, anche se riusa esattamente trasporto, slot e victim
selector.

### Dove vive il pilota

Non nel worker G132. Il worker corrente è il consumer della route esatta e
chiude la richiesta che il layer target sta aspettando
(`ds4-p4a/ds4_cuda.cu:41449-41486`). Il ledger ha già dimostrato che mettere
calcolo CPU su quel cammino costa circa 1 ms/route/layer
(`EXPERIMENTS_LEDGER.md:18095-18104`).

Architettura consigliata:

- **thread CPU producer dedicato** per MTP/route-forward, con pool fisso di
  4 thread per il kernel Q1 e uno scheduler leggero;
- intent queue separata, bounded e keyed;
- riuso del route/tiering worker e del suo upload stream come consumer finale,
  oppure un uploader dedicato che consegna reservation complete al tiering;
- mai attendere il producer dal decode; su ritardo, fallback corrente.

Il vecchio SPEX CPU probe è un buon stampo di lifecycle: thread, condvar, ring
D2H e coda bounded (`ds4-p4a/ds4.c:9678-9703`,
`ds4-p4a/ds4.c:9761-9825`). Non è però un route-forward: calcola solo gate/up e
SwiGLU checksum, senza down/residuo/backbone
(`ds4-p4a/ds4.c:9714-9758`).

## 4. Livello B: draft CPU, validatore e DSpark

### Cosa c'è già

Il ciclo corrente:

1. esegue un token target normale;
2. consegna sempre quel token;
3. usa `s->mtp_draft_token` se `mtp_draft_valid`;
4. confronta gratis il primo draft con i logits target appena prodotti;
5. genera ricorsivamente fino a 16 draft;
6. verifica la suffix in batch o con l'exact N=2.

Riferimenti:

- primo token target e gate MTP:
  `ds4-p4a/ds4.c:21157-21181`;
- first-draft exact-accept gratis:
  `ds4-p4a/ds4.c:21201-21212`;
- drafting ricorsivo:
  `ds4-p4a/ds4.c:21227-21250`;
- cap engine 16:
  `ds4-p4a/ds4.c:19711-19712`;
- buffer `drafts[16]` e server `toks[17]`:
  `ds4-p4a/ds4.c:21179-21181`,
  `ds4-p4a/ds4_server.c:7479-7494`;
- `spec_logits` ha 16 righe:
  `ds4-p4a/ds4.c:11027-11039`.

Il batch DSpark è sostanziale, non nominale. Per `n_tokens=k`:

- il verificatore esegue tutti i layer una volta in ordine layer-major
  (`ds4-p4a/ds4.c:16147-16228`);
- il router produce `k × 6` selezioni
  (`ds4-p4a/ds4.c:15020-15075`);
- selected-load deduplica tutte le `6k` richieste in un'unione compatta
  (`ds4-p4a/ds4_cuda.cu:44129-44135`,
  `ds4-p4a/ds4_cuda.cu:44330-44348`).

Quindi gli esperti caricati per layer sono:

```
U(k) = |E1 ∪ E2 ∪ ... ∪ Ek|, con 6 ≤ U(k) ≤ min(6k,256)
```

Non è automaticamente “staffetta / k”. Se le route sono disgiunte,
`U(k)=6k`: si ammortizzano i 43 rendez-vous e parte dell'orchestrazione, non i
byte. Per k=2 e overlap normalizzato `o=|E1∩E2|/6`:

```
U(2) = 12 - 6o
esperti/token full-accept = U(2)/2 = 6 - 3o
risparmio byte vs 6/token = o/2
```

Serve dunque la stessa traccia T0 anche per quantificare DSpark.

### Cosa manca per iniettare un draft CPU

L'API pubblica non ha `submit_drafts`; espone solo
`ds4_session_eval_speculative_argmax()` (`ds4-p4a/ds4.h:173-177`). Il draft
viene scritto internamente soltanto dopo
`metal_graph_eval_mtp_draft()` GPU
(`ds4-p4a/ds4.c:21078-21118`).

Occorrono:

1. API/queue per una sequenza di token draft con
   `session generation`, posizione prefix, lunghezza e provenance;
2. invalidazione su rewrite/rewind/reset;
3. percorso che alimenti direttamente `drafts[]`, senza fingere validi
   `mtp_state_hc` e `mtp_n_raw`;
4. per drafting ricorsivo, la CPU deve produrre già i `k` token; il target
   verifier necessita i token, non lo stato hidden MTP;
5. telemetria `drafted`, first-miss, verified, committed, fallback e tempo per
   fase. La visibilità di `spec_trace.patch` è già incorporata nelle righe
   exact correnti (`ds4-p4a/ds4.c:21334-21343`), ma non è stata rigirata in una
   campagna conclusiva.

Prima ancora, la Q1_0 MTP deve superare il tipo-loader e ottenere un executor
CPU completo. Non basta collegare il kernel routed audit0.

### Che cosa manca per k>2

Il contenitore e il batch generico supportano già k fino a 16. Mancano invece:

- un drafter CPU capace di produrre k token abbastanza in fretta;
- un exact verifier k>2. Il commento corrente ammette che il batch può cambiare
  l'argmax per differenze numeriche rispetto al decode
  (`ds4-p4a/ds4.c:21301-21307`);
- partial-commit/frontier k>2 validato end-to-end. Il codice forza lo snapshot
  per `draft_n>2` (`ds4-p4a/ds4.c:21421-21435`), ma questo prova plumbing, non
  equivalenza;
- misure `U(k)`, accettazione per posizione e token committati per passata;
- un criterio per scegliere k dinamicamente: fermarsi quando probabilità di
  accettazione marginale o union-load marginale non pagano più.

Il primo traguardo T2 deve restare N=2. Solo dopo exactness e speedup N=2 ha
senso aprire k=3/4; k=16 è capacità massima, non un punto operativo.

## 5. Piano a stadi e criteri di morte

### T0 — offline/oracle, zero rischio

Input:

- nuova traccia ID greedy 160 token completa;
- output del drafter MTP per gli stessi prefix;
- route-forward CPU sul token draft;
- distinzione token draft corretto/sbagliato;
- simulazione LRU140 e oracle W10/W20.

Metriche:

- overlap raw `t/t+1`;
- hit LRU140;
- oracle hit-at-demand W10/W20;
- recall/precision delle route draft;
- `new_bytes`, `wasted_bytes`, `late-equivalent`;
- union ratio DSpark `U(k)/(6k)` per k=2,3,4.

**Morte T0**:

- traccia incompleta o non riproducibile: diverso numero di righe/hash;
- oracle W10 copre meno dell'80% dei miss-byte LRU140: la finestra non ha un
  tetto utile;
- route-forward reale ha precisione <85% o recall@6 <80%: troppo traffico
  sprecato e troppi fallback sincroni;
- p95 route-forward >3,52 ms/layer nel regime pre-cliff: impossibile costruire
  10 layer di anticipo includendo il pavimento MTP;
- per DSpark k=2, dedup byte <10% (`U(2)/(12)>0,90`) e nessuna riduzione
  misurabile dell'orchestrazione: batch non ammortizza abbastanza.

T0 non deve essere ucciso perché MTP token-accept è basso: per T1 conta la
route recall anche sui token draft sbagliati.

### T1 — solo prefetch, dietro flag

Contratto:

- GPU/router/token target sempre autoritativi;
- intent queue bounded, nessuna attesa decode;
- fallback esistente su miss/late/stale;
- output greedy bit-identico;
- flag off con contatori e percorso neutrali.

Progressione:

1. replay oracle delle route vere, per provare solo innesto e deadline;
2. route-forward CPU su token oracle;
3. token MTP + route-forward;
4. solo dopo, confidence/SPEX fusion.

**Morte T1**:

- un solo mismatch di token/hash, route pointer errato o fallback non exact;
- `ready_at_use <80%`, `late >5%` o precisione delle promozioni utili <85%;
- byte file/H2D > baseline di oltre 10% dopo il warmup;
- evict_backbone o cache invalidations > baseline di oltre 5%;
- p95 producer >3,52 ms/layer pre-cliff oppure >4,90 ms/layer post-cliff per
  W10;
- throughput post-cliff non migliora almeno del 10% in A/B/B/A `n≥3`, a
  output identico;
- regressione pre-cliff >3%, anche se post-cliff migliora;
- coda non bounded, crescita di RAM/page fault o starvation dei worker target.

Il precedente K1 SPEX è il controllo negativo da non ripetere: su Cyber64
1,5167 → 0,6933 t/s (-54,29%), con 76,1 GB letti e circa 44% di byte inutili
(`ds4-p4a/G16_SPEX_K1_PREFETCH_RESULTS.md:116-140`). Dimostra che “stessi byte
dei transienti” è vero solo per previsioni utili; il prefetch sbagliato aggiunge
byte.

### T2 — commit N=2, poi DSpark k>2

Prerequisiti:

- MTP CPU p95 ≤25 ms/draft;
- asset di precisione con accettazione misurata; Q4K/Q1_0 non vanno chiamati
  int8;
- ingresso draft CPU generazionale;
- `spec_trace` rigirato e tutte le uscite classificate;
- exact N=2 come riferimento.

**Morte T2/N=2**:

- qualunque divergenza dal flusso greedy target su almeno 10.000 posizioni;
- first-draft acceptance <20% o media token consegnati/ciclo <1,25;
- fallback sequentiale per errore >0; il normale partial accept è ammesso e va
  contato separatamente;
- snapshot+verify+replay annulla il guadagno: t/s <+10% rispetto a T1/control
  in `n≥3`;
- nuova tempesta di residency: evict/token >1,05× T1;
- modulo MTP aggiunge più del 10% ai byte routed target.

Passaggio a k>2 solo se N=2 supera tutti i gate.

**Morte DSpark k>2**:

- batch row-top differisce dal decode exact anche una volta nel gate strict;
- accettazione marginale della posizione k <10%;
- `U(k)/(6k) >0,90` e riduzione dei rendez-vous non produce almeno +10% t/s;
- token committati/passata non crescono rispetto a N=2;
- partial accept richiede replay tale da riportare byte/tempo al baseline;
- qualunque peggioramento qualità/output non coperto da exact fallback.

## Decisione operativa

Aprire il filone, ma con un nome preciso: **token-ahead route pilot**, non
“riaccendere SPEX” né “MTP head-only”.

Il primo esperimento utile non è caricare di nuovo la MTP su GPU. È:

1. recuperare/generare la traccia ID 160 token;
2. misurare overlap e oracle W10/W20 a cap140;
3. costruire offline il route-forward Q1 top-1 e misurarne p50/p95;
4. continuare solo se p95 ≤3,52 ms/layer e route precision ≥85%;
5. innestare T1 con producer dedicato e tiering JIT;
6. lasciare T2 spento finché T1 non supera +10% t/s con byte e output sotto
   controllo.

Il substrato CPU ha rimosso il vecchio “non funziona nulla su CPU”. Non ha
rimosso i due vincoli causali rimasti: serve conoscere il token prima di
forwardarne le route, e serve un forward pilota sostanzialmente più veloce del
target per costruire una finestra. Sono questi, non il kernel expert, i gate
veri della riapertura.
