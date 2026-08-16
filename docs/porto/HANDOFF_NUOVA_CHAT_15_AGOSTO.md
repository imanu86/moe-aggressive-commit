# HANDOFF OPERATIVO PER NUOVA CHAT — PORTO DS4 + DSPARK — 15 AGOSTO 2026

## 0. Scopo e istruzione di lettura

Questo e' il punto di ripresa immediato dopo l'ultimo braccio decode e prima di
aprire una nuova chat con privilegi completi. Va letto integralmente prima di
modificare o compilare. Completa, senza sostituirli:

- `HANDOFF_13_AGOSTO.md` e `LEDGER_13_AGOSTO.md`;
- `HANDOFF_14_AGOSTO.md` e `LEDGER_14_AGOSTO.md`;
- `HANDOFF_15_AGOSTO.md` e `LEDGER_15_AGOSTO.md`.

Per risultati, errori, file e modifiche, l'ordine di autorita' e':

1. artifact e log reali;
2. sorgente e diff correnti;
3. questi documenti;
4. ricordi o riassunti della chat.

Obiettivo persistente: **DS4 + DSpark sul banco Porto ad almeno 20 token/s in
decode**, con output completo e coerente. L'obiettivo non e' concluso a 14, 16,
19 o 19,9 t/s. In parallelo il prefill lungo deve avanzare con leve macro, prima
verso 500 t/s e idealmente verso 1000 t/s, ma in questa ripresa la priorita'
immediata e' chiudere il disegno decode GPU-driven gia' iniziato.

## 1. Accesso, elevazione e controllo remoto

La task che materializza questo documento **ha avuto accesso pieno in scrittura**
a `D:\llama-overlap` e `D:\ds4_work`, ha compilato `llama-server` Release piu'
volte e ha creato processi benchmark/server reali. CIM risponde ancora. Al
momento dell'handoff non risulta un processo `llama-server` residuo.

Il controllo remoto dell'app e' invece diventato indisponibile dopo i riavvii
della chat/PC. Non confondere i due piani:

- filesystem/process creation erano funzionanti;
- il controllo remoto della UI/app e' perso per una ragione separata;
- una nuova task deve comunque verificare nuovamente i privilegi, senza fidarsi
  di questo paragrafo e senza mostrare popup di conferma.

Prima azione obbligatoria della nuova task:

1. create/delete di un file sonda univoco dentro `D:\llama-overlap`;
2. create/delete di un file sonda univoco dentro `D:\ds4_work`;
3. query CIM e avvio di un processo innocuo/nascosto;
4. se uno dei tre fallisce, fermarsi e dire che il cambio di privilegi non e'
   stato recepito. Non fingere di poter modificare/buildare.

## 2. Percorsi autorevoli

```text
runtime          D:\llama-overlap
artifact/run     D:\ds4_work\llama_run
documentazione   C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto
target DS4       C:\ds4-models\DS4-0731-IQ2XXS.gguf
draft DSpark     D:\ds4-models\DSpark-draft-Q2K.gguf
runner decode    C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\run_porto_short.ps1
artifact decode  C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs
```

Il runtime e' un worktree molto dirty, con grandi modifiche pregresse
dell'utente. Non usare `git reset --hard`, `git checkout --`, pulizie globali o
commit di file interi senza isolare gli hunk della leva corrente.

## 3. Regole sperimentali non negoziabili

1. Un solo B per leva.
2. Se il B e' chiaramente peggiore, scartarlo e leggere il codice; niente
   repliche consolatorie.
3. Se e' positivo o entro circa il 4% di varianza, fare tre run totali identici
   e usare la media.
4. Niente ABBA, sweep o combinazioni di leve non giustificate.
5. SHA non basta: verificare finitezza, completamento, coerenza del testo,
   errori, divergenze, p1/acceptance e contatori. CPU/GPU possono produrre SHA
   diversi legittimamente.
6. Aggiornare sempre Ledger/Handoff.
7. Prima di un commit chiedere esplicitamente l'approvazione dell'utente;
   commit circoscritto, nessuna modifica estranea, nessun push.
8. Evitare polling invasivo mentre vengono caricati oltre 80 GiB.
9. Prefill e decode sono fasi distinte; non applicare policy target-prefill al
   draft o al target-decode.
10. L'utente ha chiesto leve grosse: non tornare a limare K, soglie, lane CPU o
    microflag da 0,1 t/s.

## 4. Protocollo benchmark: non cambiare la metrica

### Decode breve ufficiale

- runner autorevole: `run_porto_short.ps1`;
- prompt NeuraForge HTML di circa 68 token;
- completion 1.200 token;
- velocita' da riferire: riga `eval time`, non prompt-eval e non media mista;
- base e B devono usare lo stesso pacchetto env, modello, draft e seed;
- verificare `finish_reason`, numero token, contenuto HTML/testo, p1, draft
  acceptance e log errori;
- i warm-up o le fixture 64 non contano come B ufficiali.

### Decode qualita' lunga

- NeuraForge full, stop naturale circa 6.147 token;
- serve per la qualita' finale, non per sostituire il banco breve.

### Prefill lungo SOTA

- prompt reale circa 101.597 token;
- ctx richiesto 150.000, effettivo tipicamente 150.016;
- FASI=2;
- riportare separatamente `prompt eval` t/s e `eval` decode t/s;
- una fixture 20,7k o una completion di un token non e' una SOTA end-to-end.

## 5. Base decode autorevole

MASSA2 copy-all stable lanes, target 473 slot e draft 12:

```text
16,04 / 16,11 / 16,07 t/s
media 16,0733 t/s
p1 = .90025
cache hit target = 77,9%
miss/copie = 47.906 = 22,1%
output uguale e coerente
```

Env aggiuntive:

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

Conto del gap:

```text
base                 62,214 ms/token
obiettivo 20 t/s     50,000 ms/token
risparmio richiesto  12,214 ms/token
```

Copie correnti: 39,9217 esperti/token x 6,75 MiB = 0,263155 GiB/token. A
24,35 GiB/s il trasporto fisico e' 10,807 ms/token. Nascondendo perfino il 100%
del DMA si arriva conservativamente a 19,453 t/s: serve recuperare anche almeno
1,407 ms/token di gestione/calcolo. Questa e' la ragione per cui un'altra leva
di solo overlap non basta.

## 6. Stato prefill da non confondere con il decode

SOTA lunga corretta corrente, tre run full DS4+DSpark, prompt 101.597 + 64,
ctx150k, resident dense, packetizer0, layer staging1, HC scheduler storico,
FASI2, denseFA, UB2048:

```text
110,7004853 / 111,0927880 / 126,8021418 t/s
media prefill 116,1985 t/s
media decode breve 7,9492 t/s
p1 .61702
stesso output coerente e stesso SHA
```

Artifact:

```text
D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_resident*_f2_b2048.*
```

La misura 275,506 t/s era una fixture target-only 20.728 token con completion1:
utile come misura di motore, non certificata come SOTA full. Il profilo
`blk.*=CPU` ha prodotto hidden/KV non finiti e `markov_w1` con indice -1 anche
senza packetizer; non va rilanciato identico. Il blocco del PC durante quel test
e' registrato nel ledger.

Quando si tornera' al prefill, la direzione macro resta residenza virtuale
phase-aware e tail FFN realmente fuso, non wildcard CPU o solo staging. Ma la
nuova chat deve prima chiudere il disegno decode WIP descritto sotto.

## 7. Famiglie decode gia' chiuse: non rifarle

Queste famiglie sono state implementate e falsificate oppure chiuse da un
budget matematico insufficiente:

- `FORK_RIUSA_SLOT=1`: media 15,76;
- `SALTA_COPIA_PARITA=1`: 15,37;
- BANCA_B predittiva: 12,38 circa, poi rimossa;
- exact-demand mailbox/host H2D: deadlock al primo comando nel grafo reale;
- whole-FFN/shared overlap: 14,57 / 14,55;
- RCI read-compute-install direttamente da mapped: 14,97 ufficiale;
- super-op CPU manuale: fixture 12,60 e 11,40;
- lane B transiente multi-stream: capture unjoined, poi deadlock;
- lane B transiente single-stream: 11,37, stage 1,487 ms/ciclo e tail
  0,993 ms/ciclo;
- nmax/soglie/K sweep storici;
- DSpark route predictor/BANCA_B;
- vecchio super-op prefill con aritmetica Dwarf Q8_K/Q8_0: -53,1% sulla RTX
  3060 rispetto agli MMVQ Q8_1 correnti.

Non riproporre una variante cosmetica di queste famiglie. In particolare:

- la base non legge un miss due volte dal PCIe: copia mapped->slab una volta e
  poi MMVQ legge dalla VRAM;
- i rendez-vous host o i secondi stream dentro il grafo reale hanno gia'
  fallito sotto WDDM;
- riscrivere i dot CPU perde blocking e scheduling del motore esistente;
- eliminare DSpark da solo ha un tetto circa 17,72 t/s;
- riottimizzare la lane CPU senza cambiare architettura non ha budget macro.

## 8. Ultimo braccio completato: `LLAMA_DSV4_DECODE_VRES`

### 8.1 Disegno

E' stato aggiunto un op GGML `GGML_OP_DSV4_MOE_DECODE`, default-off tramite
`LLAMA_DSV4_DECODE_VRES=1`:

1. router e AcceptMoE invariati;
2. op custom consuma `cur`, ID esatti, gate IQ2_XXS, up IQ2_XXS e down Q2_K;
3. output per route `[4096,n_routes,n_tokens]`;
4. pesi route, ordine e somma esterna restano invariati;
5. backend CUDA divide il grafo a ogni op MoE;
6. host prende lista/slot exact-demand, sincronizza, lancia H2D vere da alias
   host pinned su stream dedicato;
7. gate/up fusi applicano clamp DS4 e SwiGLU;
8. down usa Q8_1 normale.

La correttezza della fusione DS4 e' stata verificata. Il problema e'
orchestrativo, non un errore semantico del kernel.

### 8.2 Invariante importante: route `-1`

La partizione K=2 emette legittimamente una route fisica `-1` come sentinel per
il ramo non assegnato. I primi due tentativi K=2 abortivano con INT_MIN durante
il warm-up. Non era soltanto un problema di warm-up.

Correzione valida da preservare in qualsiasi nuovo op:

- mask class 3 per la route nulla;
- slot fisico sanitizzato a 0 solo per rendere gli accessi safe;
- `mid` azzerato, quindi down/output nullo;
- nessuna domanda/copia/installazione cache per quella route.

### 8.3 Risultati

| Braccio | Forma | t/s | p1 | Verdetto |
|---|---:|---:|---:|---|
| VRES K=0 fixture | 64 | 12,10 | .87805 | corretto |
| VRES K=0 ufficiale | 1.200 | 12,83 | .78025 | circa +8% sul GPU-only storico |
| VRES K=2 fixture r3 | 64 | 12,68 | .80952 | corretto, stesso SHA reference K=2 |
| VRES K=2 ufficiale | 1.200 | **14,03** | .87391 | **-12,7% dalla base, respinto** |

K=0 ufficiale:

```text
tag b_decode_vres_gpu_k0_t473_d12_b1
finish length, 1.200 token, 4.344 caratteri
SHA 2DCF97B640FE7879096E10DD49DE87891B11E6C010F0861EFC16C7A856EEE3CA
miss circa 49,5%
graphlet 24.510
H2D 1.161,63 GiB
sync 64.368,752 ms
```

K=2 ufficiale:

```text
tag b_decode_vres_k2_t473_d12_b1
14,03 t/s, 71,29 ms/token
p1 .87391
finish length, 1.200 token, 3.854 caratteri
SHA 71A1036F77DC3DB14CA9210CDF3181DE07D4249E0244601DBB2E9607FA2AE396
domanda 220.441
hit 172.282 = 78,2%
miss 48.159 = 21,8%
VRES graphlet 21.586
mancanti 47.463
copie H2D 142.389 = 312,87 GiB
sync 20.581,557 ms
partizioni 56.115
assegnazioni CPU 112.230
zero errori, divergenze o NaN
```

Nota: il contatore `sync` include l'attesa del segmento GPU precedente, quindi
non e' puro overhead host. Il verdetto non cambia: il confine host blocca la
composizione scheduler CPU/GPU. Il +8% K=0 e' reale, ma riaccendendo la lane CPU
la stessa architettura scende a 14,03. Nessuna replica perche' il B e'
chiaramente peggiore.

Artifact:

```text
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\decode_vres_gpu_k0_fixture64_b1.*
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\b_decode_vres_gpu_k0_t473_d12_b1.*
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\decode_vres_k2_fixture64_b1.server.log
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\decode_vres_k2_fixture64_r2.server.log
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\decode_vres_k2_fixture64_r3.*
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\b_decode_vres_k2_t473_d12_b1.*
```

I primi due artifact K=2 sono tentativi abortiti e **non** risultati
prestazionali. Solo `r3` e il B 1.200 sono validi.

## 9. Diagnosi trasversale ottenuta dal prefill

Il lavoro prefill ha chiarito quali principi si trasferiscono al decode:

1. la residenza virtuale funziona solo se trasporto e calcolo sono una pipeline
   GPU-visible, non se l'host interrompe il grafo 43 volte;
2. i pesi vanno letti una volta per tile e consumati mentre sono in shared;
3. lo staging deve avere ownership e puntatori stabili, ma non deve obbligare un
   secondo stream se WDDM impedisce il progresso;
4. l'aritmetica Dwarf non va portata ciecamente: su Porto gli MMVQ Q8_1 correnti
   sono migliori dei port Q8_K/Q8_0;
5. il valore di DwarfStar e' soprattutto nello scheduling expert-major,
   tile-capable, nella fusione e nella residenza simulata;
6. per il decode il DMA fisico non basta: il kernel deve eliminare anche copia,
   rilettura/launch e gestione intermediaria;
7. CPU e GPU devono restare componibili dal scheduler. Il braccio K=0 non puo'
   essere promosso se distrugge il vantaggio K=2.

## 10. Disegno macro aperto: miss expert-tile GPU-driven

E' l'unico disegno ancora aperto con una direzione plausibile verso il salto
macro. Non e' prediction, non e' BANCA_B e non e' il vecchio RCI.

### 10.1 Semantica desiderata

Per ogni route/layer:

- hit A: calcolo dalla slab VRAM come oggi;
- vero miss: il kernel legge ogni blocco quantizzato dalla sorgente mapped una
  sola volta, in modo coalescente;
- lo stesso blocco entra in shared memory;
- dallo shared viene contemporaneamente copiato nello slot A deciso da MASSA2
  e consumato dal dot;
- gate e up condividono la quantizzazione Q8_1 di `cur` e fondono clamp/SwiGLU;
- down Q2_K fa lo stesso read/compute/install;
- nessun host sync, nessun mailbox, nessun `cudaMemcpyAsync` dinamico, nessun
  secondo stream, nessuna predizione;
- tutto resta catturabile nel CUDA graph e il scheduler puo' continuare a
  comporre la lane CPU K=2.

Differenza dal RCI bocciato: RCI leggeva mapped via SM per fare tutto il dot ma
non eliminava correttamente il costo rispetto al percorso base; il nuovo kernel
deve essere davvero expert-tile, con una sola lettura coalescente per blocco,
riuso shared immediato e installazione nello stesso pass. Il cancello deve
misurare il beneficio reale per layer, non assumerlo.

### 10.2 Primo cancello

Non attivare subito tutti i 43 layer. Aggiungere un gate di singolo layer
default-off, ad esempio layer appreso 3 o un layer centrale rappresentativo.
Il primo test e' una fixture 64, non il B 1.200.

Criteri obbligatori:

- output completo/coerente e finito;
- route IDs e pesi invariati;
- stesso ordine r0..r5;
- nessun accesso sulla route `-1`;
- hit/miss/vittime MASSA2 identici alla base;
- installazioni gate/up/down bilanciate;
- byte letti pari ai miss reali, nessun overfetch intera banca;
- graph capture/reuse ancora attiva;
- nessun host boundary e nessun nuovo stream;
- tempo del layer instrumentato dimostra una direzione che possa colmare il gap
  globale. Se e' solo un +5% locale senza percorso al 20, fermarsi e leggere il
  profilo.

Solo dopo:

1. estendere a tutti i layer;
2. fixture64 completa;
3. un solo B 1.200;
4. se >=19,5 t/s o comunque positivo/entro4% con direzione credibile, tre run
   totali identici;
5. se chiaramente peggiore, niente repliche.

## 11. Stato esatto del codice WIP: non compilato

L'ultimo build Release riuscito e' **precedente** agli ultimi edit del kernel
expert-tile. Il binario su disco rappresenta il vecchio VRES graphlet, non il
WIP corrente. Dopo gli edit descritti qui sotto non e' stata eseguita neppure
una build. Non lanciare il binario pensando di validare il sorgente corrente.

### 11.1 `ggml/src/ggml-cuda/mmvq.cu`

Sono stati aggiunti parzialmente:

- trait `dsv4_install_block` per IQ2_XXS e Q2_K;
- template kernel `mul_mat_vec_q_moe_installa<type, has_fusion>`;
- un blocco per due output-row/route e un warp per token;
- per mask miss class1: load `int4` mapped -> shared + slab, poi dot da shared;
- fusione gate/up con clamp DS4 e SwiGLU;
- host launcher `ggml_cuda_mul_mat_vec_q_miss_install_impl`;
- API pubbliche:
  - `ggml_cuda_mul_mat_vec_q_miss_install_dsv4_gate_up`;
  - `ggml_cuda_mul_mat_vec_q_miss_install_dsv4_down`.

Audit statico obbligatorio prima della build:

- sintassi `extern __shared__ __align__(16)` con nvcc/MSVC;
- istanziazione dei pointer array quando gate e' nullo sotto `if constexpr`;
- `fastmodulo`, stride di blocco e shared bytes;
- `grid.y <= 3` per i token decode;
- allineamento `int4`: IQ2 row 1056 B, Q2_K row 672 B, entrambi /16;
- correttezza di `__syncwarp` per warp-token;
- tipi/argomenti di `ggml_cuda_kernel_launch`;
- accumulo e rounding rispetto a MMVQ corrente;
- assenza di doppia installazione della stessa route duplicata.

### 11.2 `mmvq.cuh`

Contiene le dichiarazioni delle due API miss-install. Verificare firma/callsite
prima di compilare.

### 11.3 `cache-esperti.cu/.cuh`

Modifiche parziali:

- `ggml_cuda_cache_esperti_vres_requested()` risponde anche a
  `LLAMA_DSV4_DECODE_TILE_VRES`;
- dichiarazione/implementazione parziale di
  `ggml_cuda_cache_esperti_tile_prepare`;
- `tile_prepare` richiama la decisione esatta `kern_decidi`, costruisce la
  maschera, sanitizza la route nulla e aggiorna contatori esistenti.

Problema: l'env TILE riusa ancora lo stato/allocazioni del vecchio VRES
graphlet. Questo e' sbagliato. Il nuovo percorso non deve allocare stream H2D,
eventi/mailbox o stampare telemetria del graphlet respinto.

### 11.4 Wiring ancora mancante

- `src/llama-graph.cpp` legge ancora solo `LLAMA_DSV4_DECODE_VRES` nei due
  punti correnti;
- manca un flag/gate di singolo layer per TILE;
- il custom op CUDA usa ancora `vres_prepare` con H2D e wait;
- `ggml-cuda.cu` segmenta ancora il grafo attorno all'op e blocca l'host;
- restano helper `ggml_cuda_graph_view`, stream/eventi/allocazioni VRES e
  registro alias host costruiti per il braccio respinto;
- il nuovo kernel miss-install non e' chiamato;
- l'env TILE, nello stato attuale, **non esercita** il disegno desiderato.

Quindi: **non impostare `LLAMA_DSV4_DECODE_TILE_VRES=1` e non fare un run** prima
di aver completato/ripulito il wiring.

## 12. Simboli utili per ritrovare il WIP

Al momento dell'handoff:

```text
src/llama-graph.cpp:1890,2288
    LLAMA_DSV4_DECODE_VRES ancora vecchio gate

ggml/src/ggml-cuda/cache-esperti.cu:481
    LLAMA_DSV4_DECODE_TILE_VRES

ggml/src/ggml-cuda/cache-esperti.cu:4207
    ggml_cuda_cache_esperti_tile_prepare

ggml/src/ggml-cuda/cache-esperti.cu:5570
    telemetria vecchia VRES graphlet

ggml/src/ggml-cuda/ggml-cuda.cu:5417 e 5479-5499
    helper/segmentazione ggml_cuda_graph_view del graphlet respinto

ggml/src/ggml-cuda/mmvq.cu:2373,2385
    API miss-install gate/up e down
```

Comando di orientamento:

```powershell
rg -n "LLAMA_DSV4_DECODE_(VRES|TILE_VRES)|tile_prepare|miss_install_dsv4|VRES graphlet|ggml_cuda_graph_view" `
  D:\llama-overlap\src D:\llama-overlap\ggml --glob '!build/**'
```

## 13. Ordine di ripresa consigliato

1. Verificare accesso/CIM/process creation.
2. Leggere integralmente i quattro HANDOFF/LEDGER 13-15 e questo file.
3. Controllare che non ci siano processi `llama-server` residui.
4. Fare `git status --short` e salvare un diff ristretto dei file WIP; nessun
   reset globale.
5. Auditare il kernel parziale `mmvq.cu` senza build.
6. Separare il nuovo TILE dal vecchio VRES:
   - env/stato indipendente;
   - niente stream/eventi/host alias;
   - niente segmentazione del grafo;
   - nessuna allocazione H2D VRES;
   - mantenere solo l'op GGML e la semantica route/output utile.
7. Collegare `tile_prepare` nel normale stream compute/capture.
8. Eseguire per gate/up:
   - hit masked dalla slab;
   - miss read/compute/install expert-tile;
   - fusione clamp/SwiGLU;
   - route nulla azzerata.
9. Eseguire per down:
   - hit masked dalla slab;
   - miss read/compute/install Q2_K;
   - pesi e somma esterni invariati.
10. Aggiungere gate singolo-layer e telemetria minima non invasiva.
11. `git diff --check` solo sui propri hunk.
12. Reconfigure se necessario e build Release.
13. Fixture64 singolo-layer.
14. Fixture64 all-layer.
15. Solo se corretta e con budget macro, un B ufficiale 1.200.
16. Regole replica del paragrafo 3.
17. Registrare tutto in Ledger/Handoff.
18. Rimuovere il vecchio VRES graphlet respinto e ogni diagnostica temporanea.
19. Chiedere approvazione prima di un commit runtime/documentale circoscritto;
    nessun push.

## 14. Build Release

Comando usato con successo nella task precedente:

```powershell
$portoVs = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat'
$portoCmake = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$portoCmd = 'call "' + $portoVs + '" -arch=x64 -host_arch=x64 && "' + $portoCmake + '" --build build --config Release --target llama-server -j 12'
& cmd.exe /d /s /c $portoCmd
```

I file CUDA nuovi `dsv4-moe.cu` e `dsv4-shared-hc.cu` entrano tramite glob e
possono richiedere reconfigure, ma sono materiale prefill untracked e non vanno
confusi col decode TILE. Se il linker/build coinvolge quei file, capire prima
se sono gia' nella configurazione; non cancellarli.

## 15. Worktree corrente e ownership

Tracked modificati al momento dell'handoff:

```text
common/speculative.cpp
ggml/include/ggml-backend.h
ggml/include/ggml.h
ggml/src/ggml-backend-meta.cpp
ggml/src/ggml-backend.cpp
ggml/src/ggml-cpu/ggml-cpu.c
ggml/src/ggml-cpu/ggml-cpu.cpp
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

Untracked importanti da preservare:

```text
ggml/src/ggml-cuda/dsv4-moe.cu/.cuh
ggml/src/ggml-cuda/dsv4-shared-hc.cu/.cuh
audit/*
molti artifact benchmark e patch locali
```

Il diff totale e' enorme e mescola lavoro di molte sessioni. Non usare la lista
dei file come prova di ownership. Per la leva corrente isolare i simboli VRES,
TILE, op `DSV4_MOE_DECODE` e i nuovi hunk MMVQ.

Nel repository documentale esiste una modifica user-owned da preservare:

```text
docs/porto/dopo_il_riavvio.ps1
```

Questo handoff e l'aggiornamento Ledger/Handoff sono modifiche documentali della
sessione corrente. Non includere lo script nel loro eventuale commit.

## 16. Cosa rimuovere e cosa riusare dal VRES respinto

Riusare solo:

- op GGML e dipendenze reali dei pesi;
- forma output per-route;
- router/AcceptMoE/weights/sum invariati;
- fusione clamp/SwiGLU gia' verificata;
- maschere hit/miss/null e gestione route `-1`;
- telemetria minima per IDs, miss e installazioni.

Rimuovere o disattivare integralmente nel nuovo path:

- segmentazione host del grafo;
- helper `ggml_cuda_graph_view` se non usato altrove;
- mailbox/alias host dedicati al VRES;
- stream H2D, wait ed eventi del graphlet;
- `cudaMemcpyHostToDevice` per exact-demand dinamico;
- contatori/log che attribuiscono TILE al vecchio VRES;
- fallback silenzioso che potrebbe eseguire il vecchio percorso con env TILE.

Il flag vecchio deve restare default-off e, dopo aver trasferito gli elementi
utili, va rimosso insieme al codice respinto. Prima della rimozione verificare
che nessun hunk condiviso appartenga a MASSA2 o ad altre modifiche utente.

## 17. Cancello matematico per non perdere altre ore

Il B corrente deve recuperare 12,214 ms/token dalla base. Un risultato da 17 o
18 t/s puo' essere un sottocancello utile, ma non va scambiato per la trave.

Tabella di riferimento:

```text
16,0733 t/s = 62,214 ms/token
18,0    t/s = 55,556 ms/token  (risparmio 6,658)
19,0    t/s = 52,632 ms/token  (risparmio 9,582)
19,5    t/s = 51,282 ms/token  (risparmio 10,932)
20,0    t/s = 50,000 ms/token  (risparmio 12,214)
```

Il prossimo B ufficiale deve quindi mostrare almeno una direzione molto vicina
a 19,5, oppure una telemetria credibile che identifichi l'ultimo costo residuo
ortogonale. Se fa 16,5 con molta complessita', non aggiungere altre tre leve:
scartare e leggere il profilo.

## 18. Dopo il salto decode: come tornare al prefill

Una volta chiuso/promosso il decode TILE:

1. riprendere la fixture full residente sana;
2. discriminare block-sparse con densi residenti, packetizer0, UB2048/4096 e
   completion >=32;
3. non riattivare `blk.*=CPU` wildcard;
4. usare backing pageable/mmap + piccolo staging VRAM, senza nuovo
   `CUDA0_Mapped` (pin base gia' ~76,3 GiB);
5. separare completamente DSpark dalle policy target;
6. portare dal decode il principio expert-tile read-once/compute/install;
7. per 500 t/s non basta azzerare copia+routed MMQ: serve fondere anche shared,
   add, HC e launch/materializzazioni del tail FFN;
8. validare sempre full DS4+DSpark e non solo target-only completion1.

## 19. Prompt minimo da dare alla nuova chat

```text
Lavora su D:\llama-overlap e D:\ds4_work per portare DS4+DSpark Porto a
20 t/s decode corretto. Prima verifica scrittura piena e CIM/process creation;
se manca, fermati. Leggi integralmente HANDOFF_NUOVA_CHAT_15_AGOSTO.md e i
HANDOFF/LEDGER 13-15 in
C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto.

Il percorso GPU-driven miss expert-tile read/compute/install e' stato completato,
compilato e falsificato: 10,15 t/s sulla fixture layer 3 e 10,45 t/s all-layer,
con output bit-identico alla reference e installazioni deduplicate. Non
rilanciarlo e non tentare varianti locali dello stesso mapped read SM/UVA; il
traffico misurato e' circa 25,15 GiB per 64 token e il tetto end-to-end e'
circa 4,10 GiB/s, incompatibile con 20 t/s.

Base autorevole 16,0733 t/s; ultimo VRES K2 14,03 respinto; K0 aveva +8% ma
rompeva la composizione CPU/GPU. Non rifare exact-DMA, BANCA_B, RCI mapped,
whole-FFN, super-op CPU, lane transiente o TILE GPU-driven. Il prossimo macro
deve ridurre/evitare i byte di miss, non spostare ancora il coordinamento sul
device. Worktree molto dirty: preserva gli hunk utente, aggiorna Ledger/Handoff,
chiedi approvazione prima di un commit, nessun push.
```

## 20. Stato finale di questo handoff

- Nessun run in corso.
- CIM funzionante.
- Accesso pieno era funzionante in questa task.
- Controllo remoto app perso per causa separata/non diagnosticata.
- Vecchio VRES graphlet: corretto ma prestazionalmente respinto a K=2.
- Nuovo TILE expert-driven: compilato, corretto nelle fixture ma respinto a
  10,45 t/s all-layer; niente B 1.200.
- Nessun commit runtime della leva fallita; codice sperimentale default-off nel
  dirty worktree.
- Documentazione aggiornata; commit documentale non eseguito in attesa di
  approvazione esplicita.
- Obiettivo ancora aperto: **20 t/s decode medio su tre run corretti**.

## 21. Addendum della ripresa: TILE completato e falsificato

La ripresa del 15 agosto ha verificato nuovamente scrittura reale in
`D:\llama-overlap` e `D:\ds4_work`, CIM/process creation e assenza di processi
llama residui. Il current tree era piu' avanti di quanto descritto sopra: il
vecchio VRES graphlet/segmentazione host era gia' assente e il custom op
`GGML_OP_DSV4_MOE_DECODE` con flag default-off
`LLAMA_DSV4_DECODE_TILE_VRES=1` era gia' presente.

L'audit prima del run ha trovato e corretto questi punti:

- miss duplicati tra token speculativi: `kern_decidi` deduplicava la lista, ma
  la maschera classificava anche le route successive come miss; il kernel
  originale avrebbe quindi riletto e scritto lo stesso expert tile in
  concorrenza. Il compute/install ora itera la lista device dei soli miss unici,
  carica ogni row-group una volta e lo condivide tra i token che lo usano;
- il flag TILE non viene piu' ereditato dalla cache bozza DSpark;
- allocazioni TILE fail-closed con rilascio delle parziali;
- telemetria estesa a chiamate, classi route, miss unici e installazioni separate
  gate/up/down.

Build Release `llama-server` riuscita. SHA-256 del binario CUDA testato:

```text
ggml-cuda.dll
8592E4BAD25761C95EF661F15699DA4665AC0C636EC29C90A6929FA5E7AD402F
```

Fixture ufficiali con il runner breve autorevole:

| Braccio | Decode | p1 | Telemetria | Correttezza |
|---|---:|---:|---|---|
| TILE solo layer 3 | **10,15 t/s** | .77273 | 32 chiamate; 99 miss-route, 87 unici; install 87/87/87 | `length`, 64 token, SHA reference K=2 |
| TILE tutti i layer | **10,45 t/s** | .80952 | 1.376 chiamate; 4.174 miss-route, 3.815 unici; install 3.815/3.815/3.815 | `length`, 64 token, SHA reference K=2, zero errori/divergenze |

SHA output di entrambe le fixture e della reference
`decode_vres_k2_fixture64_r3`:

```text
E23927D45A1AAC205727E96ACF4D13F9E3040AE3186415915DE0948B23C4A663
```

Artifact:

```text
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\decode_tile_layer3_fixture64_20260815_b1.*
C:\Users\imanu\Documents\Codex\2026-08-13\c-users-imanu-source-repos-moe\work\runs\decode_tile_all_fixture64_20260815_b1.*
```

Verdetto: **TILE respinto senza B 1.200**. Il full path legge 3.815 expert tile
da 6,75 MiB, circa 25,15 GiB, in 6,127 s di decode: anche attribuendo tutto il
tempo al traffico si ottengono soltanto circa 4,10 GiB/s. Per completare 64
token a 20 t/s gli stessi byte richiederebbero almeno 7,86 GiB/s prima del
compute. La lettura SM/UVA e' quindi il limite strutturale; la rimozione globale
dei confini host non lo compensa. Non spendere tempo in varianti locali di
griglia, numero warp o coalescenza dello stesso GPU-driven mapped read.

Stato al termine dell'addendum:

- nessun processo llama in corso;
- TILE resta sperimentale e default-off nel dirty worktree; nessun commit;
- vecchio VRES graphlet assente dal sorgente corrente;
- base decode autorevole invariata a **16,0733 t/s**;
- obiettivo **20 t/s medio su tre run corretti** ancora non raggiunto;
- la famiglia decode exact-demand/mapped e' ora chiusa anche nella variante
  GPU-driven senza host sync. Il prossimo candidato deve ridurre i byte di miss
  o evitare il traffico, non soltanto spostarne il coordinamento sul device.
