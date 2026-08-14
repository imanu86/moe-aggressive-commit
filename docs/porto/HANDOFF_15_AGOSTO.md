# HANDOFF PORTO — 15 AGOSTO 2026

## 0. Obiettivo e carattere di questo handoff

Obiettivo persistente dell'utente: portare **DS4 + DSpark sul banco Porto ad almeno
20 token/s in decode**, mantenendo output corretto/coerente. In parallelo va
costruito un prefill realmente macro, con traguardo intermedio 500 t/s e ideale
verso 1000 t/s, senza confondere misure target-only o completion di un token con
una SOTA end-to-end.

Questo documento completa `HANDOFF_13_AGOSTO.md`, `LEDGER_13_AGOSTO.md`,
`HANDOFF_14_AGOSTO.md` e `LEDGER_14_AGOSTO.md`. Per numeri, errori e modifiche,
**log e codice correnti restano l'autorità**. La task sorgente era
`019ffc23-6976-7d83-aff4-ba9ede2a8822`; la continuazione che ha prodotto questo
file ha perso l'elevazione dopo il riavvio della chat e non può più scrivere in
`D:\llama-overlap` o `D:\ds4_work`.

## 1. Regole operative dell'utente

1. Un solo B per leva. Se chiaramente peggiore, scartarlo e leggere il codice.
2. Se positivo o entro circa il 4% di varianza, fare tre run totali identici e
   usare la media. Niente ABBA o sweep gratuiti.
3. SHA non basta: verificare completamento, coerenza, finitezza, errori,
   divergenze e acceptance. Differenze CPU/GPU possono cambiare SHA legittimamente.
4. Aggiornare sempre Ledger/Handoff e fare commit circoscritti, senza includere
   modifiche estranee del worktree e senza push.
5. Conservare il worktree molto dirty. Non usare reset/checkout distruttivi.
6. Controllare periodicamente upstream, fork e materiale DwarfStar locale prima
   di reinventare.
7. Prefill e decode sono fasi diverse; non usare una leva prefill-only nel draft
   o nel decode.
8. Evitare polling invasivo durante il caricamento degli oltre 80 GiB.
9. Privilegiare salti architetturali; non spendere ore in +5% seriali.
10. Un braccio che blocca l'intero PC è operativamente bocciato e non si rilancia
    identico.

## 2. Percorsi e modelli

- Runtime: `D:\llama-overlap`
- Artifact e run: `D:\ds4_work\llama_run`
- Documentazione: `C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto`
- Target: `C:\ds4-models\DS4-0731-IQ2XXS.gguf`
- Draft: `D:\ds4-models\DSpark-draft-Q2K.gguf`
- Runner corrente/intermedio:
  `C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\sota100k_ctx150k.ps1`

Prima azione della nuova task: verificare scrittura reale in `D:\llama-overlap`
e `D:\ds4_work` con create/delete di file sonda non confliggenti, e verificare
CIM/process creation. Non mostrare popup di autorizzazione. Se l'accesso non è
pieno, dichiararlo immediatamente e non fingere di poter modificare/buildare.

## 3. Base decode autorevole

Base breve MASSA2 copy-all stable lanes, target 473 slot + draft 12:

- 16,04 / 16,11 / 16,07 t/s
- media **16,0733 t/s**
- p1 = **0,90025**
- stesso output
- target cache hit 77,9%
- miss/copie 47.906 = 22,1%

Configurazione aggiuntiva della base:

```text
LLAMA_CACHE_BOZZA_SLOT=12
PORTO_SPEC_NMAX=2
PORTO_SPEC_CONF_MIN=0.8
LLAMA_OVERLAP_BATCH_MAX=3
LLAMA_SPEC_CONF_ESENTA_POS0=1
LLAMA_ACCEPTMOE=1
LLAMA_ACCEPTMOE_ESATTE=1
LLAMA_ACCEPTMOE_SOGLIA=0.75
LLAMA_ACCEPTMOE_COMPATTA=1
LLAMA_GRAPH_REUSE_PER_TAGLIA=1
LLAMA_CACHE_ESPERTI_MASSA=2
LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE=0
LLAMA_CACHE_ESPERTI_MASSA_CORSIE=0
```

Bracci già bocciati nel regime corrente:

- `FORK_RIUSA_SLOT=1`: 15,84 / 15,71 / 15,73, media 15,76.
- `SALTA_COPIA_PARITA=1`: unico B 15,37, p1 invariata.
- BANCA_B predittiva: implementazione sperimentale completamente rimossa; non
  riproporla senza nuova evidenza.
- DSpark route probe: completamente rimosso.

## 4. Base lunga corretta prima della nuova campagna

Run storico valido:

- ctx richiesto 150.000, effettivo 150.016
- prompt 101.676 + completion 2.048 = 103.724
- FASI=2, UB1024
- prefill **92,30 t/s**
- decode **9,69 t/s**
- p1 **0,76501**
- nessun errore/divergenza
- cache target 473→0 nel prefill, 0→473 nel decode
- output coerente, troncato per `length`
- artifact `D:\ds4_work\llama_run\ctx150k_mass2_stable_f2_b1024.*`

FASI1 con cache esperti presente era OOM a 7.169 prompt token; FASI2 ha liberato
3.194 MiB.

## 5. Nuova base lunga corretta, 14 agosto

Configurazione: DS4+DSpark completo, target densi residenti CUDA, routed mapped,
packetizer 0, staging layer-major 1, HC_FUSO=5 sul scheduler storico (nessun pin
CUDA forzato), FASI2, block-sparse 0, B=UB=2048, prompt 101.597, completion 64.

Tre run validi:

| Run | Prefill t/s | Decode t/s | p1 |
|---|---:|---:|---:|
| R1 | 110,7004853 | 7,770260 | 0,61702 |
| R2 | 111,0927880 | 7,774656 | 0,61702 |
| R3 | 126,8021418 | 8,302715 | 0,61702 |
| **media** | **116,1985** | **7,9492** | **0,61702** |

Tutti: prompt 101.597, completion 64, finish `length`, output 266 caratteri,
stesso SHA `D556C4C30669464AB3E05C7F3037348EC063DEFA5558ADD51C0BAE731B722C31`,
testo inglese coerente che riconosce il dump di codice, zero errori/divergenze.
Lo spread prefill è 13,86%: usare la media, non scegliere R3.

Artifact:

```text
D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_resident*_f2_b2048.*
```

Verdetto: **116,20 t/s è la SOTA lunga corretta attuale**, +25,9% sulla vecchia
92,30. Non è il risultato finale desiderato e non giustifica cinque ore di
lavoro; è il controllo che ha smascherato le false SOTA veloci.

Commit documentale già eseguito, senza push:

```text
f23589d docs(porto): record phase-safe 100k prefill baseline
```

## 6. La misura 275,506 t/s: reale come tempo, non certificata come inferenza

Base corta target-only, 20.728 token, ctx40k, completion 1, block-sparse + layer
staging, tre run: media **275,5064725 t/s**, tempo 75,235982 s.

Questo dato misura un motore prefill, ma non prova una SOTA DS4+DSpark corretta:

- era target-only;
- la completion era un solo token (`<`);
- DSpark non riceveva/consumava l'intera catena di hidden/KV;
- block-sparse non era stato validato generativamente a lungo;
- il profilo `blk.*=CPU` non era stato attraversato da un decode sano.

Non chiamarlo più SOTA end-to-end. Va conservato come upper bound/indizio di
throughput del profilo prefill.

## 7. Bracci lunghi veloci risultati contaminati

I tentativi full con wildcard target `blk\..*=CPU`, packetizer globale, staging e
varianti HC/block-sparse hanno dato:

- sparse + staging + HC pin CUDA, UB12288: OOM;
- sparse + pin, UB8192: prefill 181,58 t/s, output gibberish, p1=0;
- dense + pin, UB8192: prefill 128,35 t/s, stesso gibberish, p1=0;
- pin HC rimosso completamente;
- dense HC0 UB8192: prefill completato, poi assert CPU `GET_ROWS_Q` al primo decode;
- dense HC scheduler UB8192: prefill 121,74, stesso assert;
- UB4096: prefill 132,65, stesso assert.

Il primo raw token dei run gibberish era `<think>`, poi degeneravano. Non basta
per certificare il KV: p1=0 e nessun draft accettato.

Il wildcard CPU spostava esattamente circa 6.846,95 MiB da CUDA0 a CPU:

- profilo residente valido: CPU modello ~1.010 MiB, CUDA0 ~7.383,67 MiB,
  decode graph 5/45 split;
- profilo CPU contaminato: CPU ~7.856,95 MiB, CUDA0 ~536,70 MiB,
  decode graph 295/893 split.

## 8. Patch phase-safe del packetizer e suo verdetto

È stata implementata, buildata e testata una patch default-off/phase-safe:

- `ggml/include/ggml-backend.h`: setter scheduler-local;
- `ggml/src/ggml-backend.cpp`: `offload_pacchetti` non più letto come decisione
  globale nei due punti operativi, ma appartenente allo scheduler;
- `src/llama-context.h/.cpp`: ownership draft conservata dal raw
  `params.ctx_other`; helper unico per scheduler normale e retry; target prefill
  ON, target decode OFF, DSpark sempre OFF; FASI draft disabilitato.

Nota cruciale: `cparams.ctx_other` non identifica DSpark Porto perché DSpark ha
embedding/output propri; va usato il raw `params.ctx_other` salvato prima.

Fixture full DS4+DSpark, 20.749 token + 64, ctx40k, UB12288, block-sparse,
staging, HC scheduler, wildcard CPU, packetizer richiesto 1:

- il log conferma `packetizer pesi host escluso (contesto draft)`;
- draft graph torna 6/8 split;
- target passa prefill→decode;
- al primo draft/decode: assert `ggml-cpu/ops.cpp GET_ROWS_Q`;
- nessuna completion e nessun t/s finale.

Artifact:

```text
D:\ds4_work\llama_run\sota_ctx40000_bsparse_stage_hc5_phasepkt_fixture20k_f2_b12288.*
```

Verdetto: il packetizer phase-safe **non ripara** hidden/KV già prodotti nel
prefill. Non fare repliche.

## 9. Diagnostica esatta `GET_ROWS_Q`

È stata aggiunta temporaneamente una stampa fail-fast in
`ggml/src/ggml-cpu/ops.cpp` prima dell'assert. La diagnostica deve essere rimossa
dopo aver registrato il risultato.

Fixture 6.720 token, packetizer 1:

```text
GET_ROWS_Q invalid index:
src0='markov_w1.weight'
src1='CPU#node_509#0'
dst='node_510'
i=0 i01=-1 ne01=129280
src1_ne=[1,1,1,1]
```

Artifact:

```text
D:\ds4_work\llama_run\sota_ctx12000_bsparse_stage_hc5_phasepkt_diag6k_f2_b8192.*
```

Catena codice verificata:

1. `src/models/dflash.cpp:299`: primo/secondo lookup di `markov_w1.weight`.
2. `dflash.cpp:323`: il secondo `prev` viene da `ggml_argmax(col)`.
3. `ggml/src/ggml-cuda/argmax.cu`: argmax parte da -1; se la colonna è tutta
   NaN/non-finita, resta -1.
4. Quindi non è un indice casuale/stale: il secondo passo Markov riceve logits
   non finite.
5. Il draft viene costruito prima del successivo target decode. DFlash ha già
   consumato gli hidden target e iniettato il proprio KV durante il prefill.

## 10. Discriminatore packetizer 0 interrotto dal blocco del PC, ma log conclusivo

Braccio: 6.720 token richiesti, ctx12k, UB8192, block-sparse 1, staging 1,
HC scheduler, wildcard CPU invariata, **packetizer 0**, max 8.

Il PC è diventato completamente inutilizzabile; la chat è stata riavviata e la
richiesta HTTP non ha scritto il riassunto finale. Il log server è però completo
fino all'assert:

- prompt elaborato: 6.716 token;
- prefill: **259,39 t/s** (25,89 s);
- transizione decode completata;
- stesso identico `markov_w1.weight`, `i01=-1`;
- nessun processo llama residuo.

Artifact:

```text
D:\ds4_work\llama_run\sota_ctx12000_bsparse_stage_hc5_placementcpu_pkt0_diag6k_f2_b8192.server.log
D:\ds4_work\llama_run\sota100k_ctx150k_bsparse_stage_hc5_placementcpu_pkt0_diag6k.summary.txt
```

Verdetto forte:

- il packetizer è **assolto come causa necessaria** della corruzione;
- il profilo senza packetizer può essere molto veloce (259,39 t/s) ma produce
  comunque hidden/KV draft non finiti;
- restano da separare placement wildcard CPU e block-sparse; staging storico era
  già stato validato generativamente stage-vs-no-stage su 6.698+32, build963;
- la configurazione identica non va rilanciata: ha bloccato l'intero PC.

## 11. Prossimo discriminatore prefill corretto e meno rischioso

Per riprendere lo studio prefill, non ripetere `blk.*=CPU`. Isolare prima
block-sparse usando il profilo residente già sano:

```text
DS4+DSpark full
target dense resident (BlockDenseCpu=0)
GGML_SCHED_OFFLOAD_PACCHETTI=0
layer staging=1
HC_FUSO=5 scheduler storico, nessun pin
FASI2
BlockSparse=1 (unica differenza dalla fixture/base residente)
ctx ~12k, prompt ~6,7k, completion >=32 o 64
UB conservativo 2048/4096, non 8192
GGML_CUDA_GRAPH_STATS=0 per evitare migliaia di righe
```

Criterio:

- output coerente, finito, p1 non collassata, zero NaN/assert: block-sparse
  assolto; il colpevole è il placement misto `blk.*=CPU`/scheduler split;
- stesso `argmax=-1`: ritirare block-sparse e costruire un verifier
  bitmap-vs-dense multi-ubatch prima di correggerlo.

Se block-sparse è sano, la strada macro prefill non è il wildcard CPU. Serve una
vera residenza virtuale phase-aware:

- backing pageable/mmap;
- piccolo staging VRAM layer-major;
- copie H2D esplicite tramite host pointer, non alias UVA/device;
- doppia parità/eventi solo dopo preflight memoria;
- DSpark separato e mai investito dalle policy target;
- evitare nuovo `CUDA0_Mapped`: il pin base è già ~76,3 GiB.

## 12. Audit prefill macro e super-op

Inventario denso target CUDA0 7.383,67 MiB:

- attention 4.660,125 MiB;
- shared expert 1.096,5 MiB;
- compressori+indexer 929,295 MiB;
- output+norm 536,578 MiB;
- resto ~161 MiB.

Routed experts 74.304 MiB CUDA0_Mapped; embedding F16 ~1.010 MiB CUDA_Host.
Staging attention/shared/compressori layer-major potrebbe liberare ~6,345 GiB
netti (~6,7 con output) aggiungendo ~6,53 GiB PCIe per passata, solo +9% sui
72,56 GiB routed. Non usare nuovo mapped pin.

Con base prefill 275,506, il target 500 richiede 41,456 s contro 75,236 s:
risparmio 33,780 s. Anche azzerare routed MMQ + copia non basta; serve recuperare
almeno ~9,67 s fuori dal routed. Il prossimo vero macro non può essere solo
overlap/staging: deve fondere il tail FFN completo.

Nel tree esistono quattro file nuovi/untracked e plumbing correlato:

```text
ggml/src/ggml-cuda/dsv4-moe.cu/.cuh
ggml/src/ggml-cuda/dsv4-shared-hc.cu/.cuh
```

Il port v2 contiene quant Q8_K, IQ2_XXS gate/up expert-tile, Q2_K down,
route-sort, somma ordinata, e shared Q8_0 + HC batch. Le correzioni già applicate:

- niente grid.y > 65.535 a UB12288;
- mid non pesato; route weight dopo down;
- somma r0..5 ordinata, niente atomic finali;
- `selected` deve essere reso contiguo;
- pesi devono essere vere dipendenze GGML, non pointer in op_params;
- shared HC adattato batch, non copiato dal path decode monoriga DwarfStar.

Il super-op v1 è già stato bocciato su fixture 6.698 target-only:
A 194,8275 vs B 91,3253 (-53,1%), output coerente. Non rifarlo.
Il v2 non è certificato e non è la priorità immediata: prima correggere/ritirare
il percorso prefill che produce NaN nel grafo full.

## 13. Stato del worktree runtime da preservare

`D:\llama-overlap` è molto dirty con modifiche pregresse dell'utente. Al momento
dell'handoff risultavano modificati, fra gli altri:

```text
common/speculative.cpp
ggml/include/ggml-backend.h
ggml/include/ggml.h
ggml/src/ggml-backend-meta.cpp
ggml/src/ggml-backend.cpp
ggml/src/ggml-cpu/ggml-cpu.c
ggml/src/ggml-cpu/ggml-cpu.cpp
ggml/src/ggml-cpu/ops.cpp                 # diagnostica temporanea GET_ROWS_Q
ggml/src/ggml-cuda/cache-esperti.cu/.cuh
ggml/src/ggml-cuda/common.cuh
ggml/src/ggml-cuda/ggml-cuda.cu
ggml/src/ggml-cuda/mmvq.cu/.cuh
ggml/src/ggml-cuda/topk-moe.cu/.cuh
ggml/src/ggml.c
src/llama-context.cpp/.h
src/llama-graph.cpp/.h
src/llama-kv-cache-dsv4.cpp/.h
src/llama-model.cpp
src/models/deepseek4.cpp
tools/llama-bench/llama-bench.cpp
tools/server/server.cpp
```

Non assumere che tutto sia di questa sessione. Isolare sempre hunks specifici.

Pulizia immediata raccomandata nella nuova task:

1. rimuovere solo la diagnostica `GET_ROWS_Q invalid index` da `ops.cpp`;
2. auditare la patch phase-safe nei quattro file e decidere se mantenerla
   default-off per il futuro o rimuoverla; non committare l'intero
   `ggml-backend.cpp`, che contiene molti hunks preesistenti;
3. non toccare i quattro `dsv4-*` finché non si sceglie di riprendere v2;
4. `git diff --check` ristretto ai propri hunks;
5. build Release dopo la pulizia.

## 14. Perché il decode è ancora lontano da 20 t/s

Base 16,0733 t/s = **62,214 ms/token**. Obiettivo 20 = 50,000 ms/token.
Risparmio necessario: **12,214 ms/token**.

Miss target:

- 39,9217 esperti copiati/token;
- 6,75 MiB/esperto;
- 269,471 MiB = 0,263155 GiB/token;
- a 24,35 GiB/s: **10,807 ms/token** di solo trasporto.

Quindi anche nascondendo il 100% del DMA, tetto conservativo:

```text
62,214 - 10,807 = 51,407 ms/token = 19,453 t/s
```

Servono almeno altri **1,407 ms/token** di gestione, e realisticamente
1,8–3,2 ms/token includendo confini graphlet.

DSpark costa ~14,26 ms/ciclo, pari a ~5,776 ms/output-token. Anche azzerandolo
interamente il tetto sarebbe ~17,72 t/s. DSpark staging da solo non è la trave.

## 15. Disegno decode macro da attaccare subito

Il prossimo braccio decode non deve essere BANCA_B predittiva né un'altra leva
da 5%. Il candidato è un singolo flag default-off, concettualmente:

```text
LLAMA_EXACT_DEMAND_DMA=1
```

Macro-pipeline per ogni layer:

1. graphlet router/classificatore e ramo già residente;
2. piccola lista esatta dei miss trasferita al host;
3. H2D copy-engine degli esperti esatti verso destinazioni stabili della slab;
4. evento `upload_ready`;
5. graphlet MMVQ della coda mancante;
6. decisione cache + join fusi/ridotti per recuperare anche almeno 1,4 ms/token
   di gestione oltre al DMA.

Perché serve il confine host: su sm86 non esiste una memcpy copy-engine dinamica
lanciabile dal device; i nodi memcpy dei CUDA graph hanno indirizzi statici.
Il current `kern_fj_copia` resta graph-compatible perché copia da
CUDA0_Mapped tramite SM, non tramite copy engine.

Rischio: 43 confini router/ciclo possono costare ~0,35–1,74 ms/token assumendo
20–100 microsecondi ciascuno. Quindi il prototipo deve dimostrare il budget prima
di un B lungo.

Cancello strumentato prima del full benchmark:

- zero overfetch rispetto ai miss reali;
- H2D byte esatti e copy-engine realmente usato;
- graph reuse dei graphlet ancora attivo;
- overhead totale dei 43 confini < ~1 ms/token;
- decisione/classificazione/join risparmiano abbastanza da portare il guadagno
  totale ad almeno 12,214 ms/token;
- output identico/coerente, stessa selezione/pesi/ordine, zero NaN/OOB;
- se il cancello matematico non passa, niente run 1.200 token.

Pattern locali DwarfStar da riusare: commit/materiale `78f50cb` e `5633856`,
metadata per parità, `upload_ready`, `compute_done`, ownership persistente e
fallback fail-closed. Non portare ciecamente le wave generiche G38/G39: DwarfStar
ha mostrato che senza kernel expert-tile restano peggiori della production.

## 16. DSpark virtual residency: utile ma seconda leva

`blk.1/2` DSpark oggi sono CPU e non arrivano al dispatcher CUDA standard. Il
normale offload copierebbe l'intera banca ~2.224 MiB/layer. Disegno possibile:

- buft host-pageable dedicato CUDA-logical;
- riuso slab draft 12 slot = ~104,263 MiB;
- piccolo ring pinned 2×9.110.640 B = ~17,377 MiB;
- router/top-k prima, shared expert espanso per creare finestra;
- pack+H2D e join al primo MMID routed;
- guardie `np=1`, `n_tokens<=2`, DFlash, quanti esatti, fallback immediato;
- nessun secondo slab da 104 MiB: il margine VRAM osservato è troppo stretto.

È conoscenza trasversale dal prefill, ma da sola non porta a 20. Tenerla dopo il
cancello target exact-demand DMA oppure integrarla solo se il macro budget richiede
un secondo risparmio ortogonale.

## 17. Ordine operativo per la nuova task

1. Verificare pieno accesso e process creation; stop immediato se manca.
2. Leggere integralmente HANDOFF/LEDGER 13, 14 e questo file.
3. Incrociare i log citati con codice/diff corrente.
4. Non rilanciare la configurazione CPU/UB8192 che ha bloccato il PC.
5. Rimuovere la diagnostica temporanea; build pulita.
6. Aggiornare Ledger/Handoff e fare commit documentale circoscritto, no push.
7. Spostarsi **subito sul decode macro**: audit e prototipo strumentato
   `EXACT_DEMAND_DMA` con budget dei confini e della gestione.
8. In parallelo, se si usano agenti, assegnare a uno solo l'audit prefill
   residente+block-sparse; nessun run concorrente con il decode.
9. Tornare al prefill quando il prototipo decode è in build/audit o dopo il primo
   cancello: isolare block-sparse col profilo residente e poi progettare vera
   residenza virtuale, non wildcard `blk.*=CPU`.
10. Non chiudere l'obiettivo a un risultato intermedio: successo solo con
    DS4+DSpark >=20 t/s medio su tre run, output corretto/coerente.

## 18. Aggiornamento: exact-demand H2D esterno falsificato e rimosso

Il prototipo `LLAMA_CACHE_ESPERTI_EXACT_DMA=1` e' stato implementato nel runtime,
compilato e portato fino al warm-up target, ma **non ha mai raggiunto una
richiesta di inferenza**. Non conta quindi come B prestazionale e non va
riproposto nella stessa forma.

Disegno provato:

- `kern_decidi` e la lista esatta del FORK invariati;
- mailbox mapped device->host con `(strato, esperto, slot A)`;
- thread host dedicato;
- vere H2D dalle alias host pinned di `CUDA0_Mapped` verso la slab A;
- copy stream ad alta priorita';
- prima versione con kernel-spin/segnale, poi memops64 del command processor;
- CUDA graph target disabilitati nell'ultima versione, DSpark invariato.

Correzioni statiche emerse prima/durante il cancello:

1. gli strati a zero miss saltano legittimamente sequenze mailbox;
2. `n_strati=64` e' capienza della tabella cache, non numero blocchi DS4; le
   terne reali sono `blk.0..42`;
3. il servizio deve essere pronto prima del warm-up;
4. `cudaStreamQuery` non e' un flush WDDM sufficiente;
5. RTX 3060/driver Porto espongono memops64 (`attr122=1`) ma non la vecchia
   capability32 (`attr92=0`).

Due microtest isolati sono riusciti:

- `wait64` su uno stream e `write64` su un altro;
- `wait64` concorrente con `cuMemcpyHtoDAsync` di 8 MiB + `write64`, stesso
  contesto, entrambi i thread completati con codice 0.

Nel grafo reale, invece, tutte le varianti si fermano al **primo comando**:

```text
cache-esperti: EXACT_DMA primo comando host seq=1 strato=0 miss=8
```

La variante kernel-spin scadeva con `unspecified launch failure`; la variante
memops64, anche con sole Driver API calde e CUDA graph target spenti, restava
bloccata senza avanzare oltre `seq=1`. Il ciclo nasce quindi dallo scheduling e
dalle dipendenze multi-stream del grafo reale, non dalla disponibilita' del
primitivo CUDA in isolamento. Ogni processo bloccato e' stato terminato subito;
nessun output o numero t/s e' stato prodotto.

Artifact diagnostici:

```text
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\exactdma_smoke64_*.server.log
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\exactdma_memops64_smoke64_b1.server.log
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\exactdma_driver_smoke64_b1.server.log
```

Il codice `EXACT_DMA`, incluse alias host, mailbox, thread, memops, telemetria e
gate graph, e' stato rimosso integralmente. Ricerca repo-wide senza risultati e
build Release `llama-server` verde dopo la rimozione.

### Nuova direzione decode macro

Il prossimo braccio non deve inserire il host nel mezzo del grafo. Usare un
**super-op FFN decode interamente GPU**, riusando scheduling expert-tile
DwarfStar per IQ2_XXS gate/up + Q2_K down e la cache A MASSA2 corrente. Obiettivi
del primo sottocancello: una sola quantizzazione input, gate+up fusi, SwiGLU
senza materializzare gate/up, down e somma route ordinata, meno lanci e meno
gestione; trasporto miss inizialmente invariato sul FORK SM. Solo dopo aver
dimostrato correttezza e un risparmio macro si valuta un confine graphlet host
esplicito, non un callback/rendez-vous interno al grafo monolitico.
