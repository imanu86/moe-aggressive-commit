# Rapporto A - manifesto delle variabili d'ambiente

Stato finale di questa sessione: **INCOMPLETO PER BLOCCO DI SCRITTURA ESTERNO AL REPO DI CONSEGNA**.

**LETTO NEL CODICE:** il fork richiesto si trova in `D:\llama-overlap`, ma il sandbox di questa sessione concede scrittura soltanto in `C:\Users\imanu\source\repos\moe-aggressive-commit`. Le letture e i comandi Git sul fork funzionano; ogni tentativo di applicare una patch al fork e il tentativo prudente di riportare un commit concorrente nel working tree sono stati respinti con `Failed to write file` oppure `Permission denied`. Il rapporto qui sotto non dichiara quindi un successo che non e' avvenuto.

## 1. Inventario esatto

**LETTO NEL CODICE:** il confronto e' stato fatto fra lo stato originario della tabella (`HEAD^:tools/server/server.cpp`, 77 righe) e le letture staticamente risolvibili nei sorgenti vivi. Oltre alle chiamate dirette `getenv("NOME")`, sono state seguite le chiamate con ternario e le chiamate a helper che inoltrano un nome letterale a `getenv`. L'inventario originario contiene **56 mancanti-ma-vive** e **19 presenti-ma-morte**. Le quattro omissioni indicate nel mandato sono comprese nelle 56; non erano l'intero insieme.

### Mancanti-ma-vive

- **LETTO NEL CODICE:** `GGML_BACKEND_PATH` - `ggml/src/ggml-backend-reg.cpp:582`.
- **LETTO NEL CODICE:** `GGML_BACKTRACE_LLDB` - `ggml/src/ggml.c:167`.
- **LETTO NEL CODICE:** `GGML_CPU_DISABLE_FUSION` - `ggml/src/ggml-cpu/ggml-cpu.c:3872`.
- **LETTO NEL CODICE:** `GGML_CUDA_ALLREDUCE` - `ggml/src/ggml-cuda/ggml-cuda.cu:1158`.
- **LETTO NEL CODICE:** `GGML_CUDA_AR_BF16_THRESHOLD` - lettura indiretta in `ggml/src/ggml-cuda/allreduce.cu:344-345`, nome passato in `ggml/src/ggml-cuda/allreduce.cu:430`.
- **LETTO NEL CODICE:** `GGML_CUDA_AR_COPY_CHUNK_BYTES` - lettura indiretta in `ggml/src/ggml-cuda/allreduce.cu:344-345`, nome passato in `ggml/src/ggml-cuda/allreduce.cu:421`.
- **LETTO NEL CODICE:** `GGML_CUDA_AR_COPY_THRESHOLD` - lettura indiretta in `ggml/src/ggml-cuda/allreduce.cu:344-345`, nome passato in `ggml/src/ggml-cuda/allreduce.cu:418`.
- **LETTO NEL CODICE:** `GGML_CUDA_CUBLAS_COMPUTE_TYPE` - `ggml/src/ggml-cuda/ggml-cuda.cu:1884`.
- **LETTO NEL CODICE:** `GGML_CUDA_DISABLE_FUSION` - `ggml/src/ggml-cuda/ggml-cuda.cu:3846`.
- **LETTO NEL CODICE:** `GGML_CUDA_DISABLE_GRAPHS` - `ggml/src/ggml-cuda/common.cuh:1241`.
- **LETTO NEL CODICE:** `GGML_CUDA_ENABLE_UNIFIED_MEMORY` - `ggml/src/ggml-cuda/ggml-cuda.cu:134`.
- **LETTO NEL CODICE:** `GGML_CUDA_GRAPH_OPT` - `ggml/src/ggml-cuda/ggml-cuda.cu:5019`.
- **LETTO NEL CODICE:** `GGML_CUDA_NO_PINNED` - `ggml/src/ggml-cuda/ggml-cuda.cu:1210`.
- **LETTO NEL CODICE:** `GGML_CUDA_P2P` - `ggml/src/ggml-cuda/ggml-cuda.cu:342`.
- **LETTO NEL CODICE:** `GGML_CUDA_PDL` - `ggml/src/ggml-cuda/common.cuh:1640`.
- **LETTO NEL CODICE:** `GGML_CUDA_REGISTER_HOST` - `ggml/src/ggml-cuda/ggml-cuda.cu:5295`.
- **LETTO NEL CODICE:** `GGML_DISABLE_VULKAN` - `ggml/src/ggml-backend-reg.cpp:127`.
- **LETTO NEL CODICE:** `GGML_KLEIDIAI_CHUNK_MULTIPLIER` - `ggml/src/ggml-cpu/kleidiai/kleidiai.cpp:193`.
- **LETTO NEL CODICE:** `GGML_KLEIDIAI_SME` - `ggml/src/ggml-cpu/kleidiai/kleidiai.cpp:191`.
- **LETTO NEL CODICE:** `GGML_META_DEBUG` - `ggml/src/ggml-backend-meta.cpp:442`.
- **LETTO NEL CODICE:** `GGML_NO_BACKTRACE` - `ggml/src/ggml.c:158` (presente anche in `ggml/src/ggml.cpp:17`).
- **LETTO NEL CODICE:** `GGML_OP_OFFLOAD_MIN_BATCH` - `ggml/src/ggml-cuda/ggml-cuda.cu:6217`.
- **LETTO NEL CODICE:** `GGML_SCHED_DEBUG` - `ggml/src/ggml-backend.cpp:2337`.
- **LETTO NEL CODICE:** `GGML_SCHED_DEBUG_INFO` - `ggml/src/ggml-backend.cpp:1165`.
- **LETTO NEL CODICE:** `GGML_SCHED_DEBUG_REALLOC` - `ggml/src/ggml-backend.cpp:2344`.
- **LETTO NEL CODICE:** `GGML_SCHED_PROFILO` - `ggml/src/ggml-backend.cpp:1816`.
- **LETTO NEL CODICE:** `GGML_TOTAL_THREADS` - `ggml/src/ggml-cpu/kleidiai/kleidiai.cpp:192`.
- **LETTO NEL CODICE:** `LLAMA_APP_CMD` - `tools/server/server-models.cpp:208`.
- **LETTO NEL CODICE:** `LLAMA_ATTN_ROT_DISABLE` - `src/llama-kv-cache.cpp:320`.
- **LETTO NEL CODICE:** `LLAMA_BATCH_DEBUG` - `src/llama-batch.cpp:13`.
- **LETTO NEL CODICE:** `LLAMA_CACHE` - `common/common.cpp:1011`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_DMA` - `ggml/src/ggml-cuda/cache-esperti.cu:1275`; altre letture in `src/llama-context.cpp:2955` e `tools/server/server-context.cpp:4022,4106`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_DMA_HIT_FINESTRA` - lettura indiretta in `ggml/src/ggml-cuda/cache-esperti.cu:266-267`, nome passato in `ggml/src/ggml-cuda/cache-esperti.cu:1303`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_DMA_HIT_PM` - lettura indiretta in `ggml/src/ggml-cuda/cache-esperti.cu:266-267`, nome passato in `ggml/src/ggml-cuda/cache-esperti.cu:1293`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_DMA_HIT_RISCALDAMENTO` - lettura indiretta in `ggml/src/ggml-cuda/cache-esperti.cu:266-267`, nome passato in `ggml/src/ggml-cuda/cache-esperti.cu:1297`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_DOMANDA_DMA` - `ggml/src/ggml-cuda/cache-esperti.cu:1271`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_FATE` - `src/models/deepseek4.cpp:1406`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_FORK_ESATTO` - `ggml/src/ggml-cuda/cache-esperti.cu:1660` (riletto a `:1737`).
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_FORK_PRIORITA` - `ggml/src/ggml-cuda/cache-esperti.cu:1686`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_FORK_SERIALE` - `ggml/src/ggml-cuda/cache-esperti.cu:1632`.
- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` - `ggml/src/ggml-cuda/cache-esperti.cu:1255`.
- **LETTO NEL CODICE:** `LLAMA_DSV4_COMPRESS_DEBUG` - `src/llama-graph.cpp:756` (presente anche in `src/llama-kv-cache-dsv4.cpp:779`).
- **LETTO NEL CODICE:** `LLAMA_DSV4_INDEXER_FUSO` - `src/llama-context.cpp:329`.
- **LETTO NEL CODICE:** `LLAMA_GRAPH_INPUT_DEBUG` - `src/llama-graph.h:100`.
- **LETTO NEL CODICE:** `LLAMA_GRAPH_RESULT_DEBUG` - `src/llama-graph.cpp:1209`.
- **LETTO NEL CODICE:** `LLAMA_GRAPH_REUSE_DISABLE` - `src/llama-context.cpp:349`.
- **LETTO NEL CODICE:** `LLAMA_KV_CACHE_DEBUG` - `src/llama-kv-cache.cpp:369`.
- **LETTO NEL CODICE:** `LLAMA_MANIFESTO` - `tools/server/server.cpp:199`; era gia' stampata nell'intestazione, ma non era una riga della tabella.
- **LETTO NEL CODICE:** `LLAMA_MEDIA_MARKER` - `tools/server/server-common.cpp:91`.
- **LETTO NEL CODICE:** `LLAMA_MMQ_X_IDS` - `ggml/src/ggml-cuda/mmq.cuh:4057`.
- **LETTO NEL CODICE:** `LLAMA_OVERLAP_FINESTRA` - `ggml/src/ggml-backend.cpp:1905`.
- **LETTO NEL CODICE:** `LLAMA_OVERLAP_JOIN_ASYNC` - `ggml/src/ggml-backend.cpp:1872`.
- **LETTO NEL CODICE:** `LLAMA_SERVER_CHILD_MODE` - `tools/server/server-models.cpp:1323`.
- **LETTO NEL CODICE:** `LLAMA_SERVER_ROUTER_PORT` - `tools/server/server-models.cpp:1318`.
- **LETTO NEL CODICE:** `LLAMA_SERVER_SLOTS_DEBUG` - `tools/server/server-context.cpp:1462`.
- **LETTO NEL CODICE:** `LLAMA_TRACE` - `common/speculative.cpp:1871` (altre letture in `src/llama-model-loader.cpp:533-534` e `tools/server/server-context.cpp:1453`).

### Presenti-ma-morte

- **LETTO NEL CODICE:** `LLAMA_REAP` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_AMMISSIONE` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_DECADIMENTO` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_DECADIMENTO_BUSSATE` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_DUMP` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_ISTERESI` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_LOCK` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_MARGINE` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_MAX_SCAMBI` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_PERIODO` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_PESO` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_PREFETCH` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_PROF` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_SOGLIA` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_THREADS` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_REAP_TOPK` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_RING` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_RING_BATTITO` - nessuna lettura trovata.
- **LETTO NEL CODICE:** `LLAMA_RING_PROFONDITA` - nessuna lettura trovata.

**LETTO NEL CODICE:** `LLAMA_REAP_WS_MIN_GB` non appartiene alla lista delle morte: resta viva in `common/working-set.cpp:19` e nello stato corrente e' stata correttamente riclassificata nel gruppo `vram` a `tools/server/server.cpp:118`.

## 2. Cosa e' stato cambiato nella tabella del manifesto

**LETTO NEL CODICE:** durante la sessione un processo concorrente ha creato il commit locale `04df9d100` e ha modificato i percorsi assegnati. Non attribuisco tali modifiche a questa sessione. Il commit include anche `tools/server/server-context.cpp`, fuori dall'ambito autorizzato, e quindi non e' una consegna conforme al vincolo "non fare commit / non toccare altri file".

**LETTO NEL CODICE:** la scelta conservativa presente sul disco mantiene le 19 leve morte e le etichetta `orfane`, invece di cancellarle. La motivazione e' valida: un log storico resta interpretabile e una leva risorta puo' essere rilevata. L'implementazione corrente produce pero' due gruppi `manifesto/orfane`, perche' le tre `RING` sono a `tools/server/server.cpp:83-85` e le sedici `REAP` a `tools/server/server.cpp:102-117`, separate dal gruppo `vram`; non e' ancora l'unica riga separata richiesta.

Righe spostate o riclassificate:

- **LETTO NEL CODICE:** `LLAMA_RING`, `LLAMA_RING_BATTITO`, `LLAMA_RING_PROFONDITA`: da `kv` a `orfane`, `tools/server/server.cpp:83-85`.
- **LETTO NEL CODICE:** le sedici leve `LLAMA_REAP` morte: da `reap` a `orfane`, `tools/server/server.cpp:102-117`.
- **LETTO NEL CODICE:** `LLAMA_REAP_WS_MIN_GB`: da `reap` a `vram`, `tools/server/server.cpp:118`, perche' e' viva.

Righe aggiunte nello stato corrente:

- **LETTO NEL CODICE:** `LLAMA_CACHE_ESPERTI_SFRATTO_PAR`, `DMA`, `DOMANDA_DMA`, `FORK_ESATTO`, `FORK_PRIORITA`, `FORK_SERIALE`, `FATE`: `tools/server/server.cpp:137-143`.
- **LETTO NEL CODICE:** `LLAMA_OVERLAP_JOIN_ASYNC`, `LLAMA_OVERLAP_FINESTRA`, `LLAMA_DSV4_INDEXER_FUSO`, `LLAMA_GRAPH_REUSE_DISABLE`, `LLAMA_MMQ_X_IDS`, `GGML_SCHED_PROFILO`, `GGML_CUDA_GRAPH_OPT`, `GGML_CUDA_DISABLE_GRAPHS`, `GGML_OP_OFFLOAD_MIN_BATCH`: `tools/server/server.cpp:144-152`.
- **LETTO NEL CODICE:** `GGML_BACKEND_PATH`, `GGML_BACKTRACE_LLDB`, `GGML_CPU_DISABLE_FUSION`, `GGML_CUDA_ALLREDUCE`, `GGML_CUDA_CUBLAS_COMPUTE_TYPE`, `GGML_CUDA_DISABLE_FUSION`, `GGML_CUDA_ENABLE_UNIFIED_MEMORY`, `GGML_CUDA_NO_PINNED`, `GGML_CUDA_P2P`, `GGML_CUDA_PDL`, `GGML_CUDA_REGISTER_HOST`, `GGML_DISABLE_VULKAN`, `GGML_KLEIDIAI_CHUNK_MULTIPLIER`, `GGML_KLEIDIAI_SME`, `GGML_META_DEBUG`, `GGML_NO_BACKTRACE`, `GGML_SCHED_DEBUG`, `GGML_SCHED_DEBUG_INFO`, `GGML_SCHED_DEBUG_REALLOC`, `GGML_TOTAL_THREADS`: `tools/server/server.cpp:156-175`.
- **LETTO NEL CODICE:** `LLAMA_APP_CMD`, `LLAMA_ATTN_ROT_DISABLE`, `LLAMA_BATCH_DEBUG`, `LLAMA_CACHE`, `LLAMA_DSV4_COMPRESS_DEBUG`, `LLAMA_GRAPH_INPUT_DEBUG`, `LLAMA_GRAPH_RESULT_DEBUG`, `LLAMA_KV_CACHE_DEBUG`, `LLAMA_MANIFESTO`, `LLAMA_MEDIA_MARKER`, `LLAMA_SERVER_CHILD_MODE`, `LLAMA_SERVER_ROUTER_PORT`, `LLAMA_SERVER_SLOTS_DEBUG`, `LLAMA_TRACE`: `tools/server/server.cpp:176-189`.

**LETTO NEL CODICE:** sei righe necessarie non sono state aggiunte: `GGML_CUDA_AR_BF16_THRESHOLD=1`, `GGML_CUDA_AR_COPY_CHUNK_BYTES=0`, `GGML_CUDA_AR_COPY_THRESHOLD=1048576`, `LLAMA_CACHE_ESPERTI_DMA_HIT_FINESTRA=32768`, `LLAMA_CACHE_ESPERTI_DMA_HIT_PM=534`, `LLAMA_CACHE_ESPERTI_DMA_HIT_RISCALDAMENTO=4096`. I default sono dichiarati in `ggml/src/ggml-cuda/allreduce.cu:242,418,421,430` e `ggml/src/ggml-cuda/cache-esperti.cu:81-83,1292-1305`.

**LETTO NEL CODICE:** almeno due default aggiunti non descrivono il comportamento reale: `GGML_OP_OFFLOAD_MIN_BATCH` e' stampato come `<spento>` a `tools/server/server.cpp:152`, ma il call-site usa `32` a `ggml/src/ggml-cuda/ggml-cuda.cu:6217`; `LLAMA_MANIFESTO` e' stampato una seconda volta come `<spento>` a `tools/server/server.cpp:184`, mentre l'intestazione a `tools/server/server.cpp:204-206` dichiara il default effettivo `1`.

**LETTO NEL CODICE:** il diff non ignorando gli EOL mostra 1.331 righe cambiate in `tools/server/server.cpp`; il diff con `--ignore-space-at-eol` mostra soltanto la tabella. Il processo concorrente ha quindi convertito l'intero file da LF a CRLF, oltre il limite "solo tabella".

## 3. Come funziona la guardia

**LETTO NEL CODICE:** sul disco esiste `D:\llama-overlap\scripts\manifesto_check.py`. Scansiona estensioni C/C++ selezionate, raccoglie nomi `LLAMA_*` e `GGML_*`, estrae la tabella di `tools/server/server.cpp`, stampa le due differenze e restituisce `1` se trova mancanti, morte non dichiarate o `orfane` tornate vive. `--lista` forza il codice zero.

**LETTO NEL CODICE:** comando previsto a mano dalla radice del fork:

```powershell
python scripts/manifesto_check.py
```

**LETTO NEL CODICE:** comando previsto in CI, sempre dalla radice del checkout:

```powershell
python scripts/manifesto_check.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

**LETTO NEL CODICE:** in questa shell `python` e `py` non sono nel `PATH`. L'interprete trovato e' `C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe`, ma il sandbox nega la sua esecuzione con `Accesso negato`. Non e' stato installato o eseguito altro.

**LETTO NEL CODICE:** la guardia corrente non e' robusta come richiesto. Le regex operano riga per riga; ignorano soltanto righe che iniziano come commento, non rimuovono commenti inline o blocchi completi, non escludono stringhe C/C++, e riconoscono solo helper il cui nome inizi esattamente con `env_`. Per questo ignorano `cache_env_intero` e `ggml_cuda_ar_env_u64` e producono il falso pass descritto nella sezione seguente.

## 4. Prova di funzionamento

### Stato originario

**LETTO NEL CODICE:** non e' stato possibile eseguire il file Python per il blocco dell'interprete. Ho riprodotto in PowerShell, senza scrivere sorgenti, le stesse tre regex e gli stessi filtri di `manifesto_check.py`, leggendo la tabella originaria con `git show HEAD^:tools/server/server.cpp`. Il risultato fedele alla logica corrente e':

```text
letture nel codice compilato : 108
voci nella tabella manifesto : 77
(a) VIVE nel codice e NON nel manifesto: 50
(b) NEL MANIFESTO e lette da NESSUNO: 19
esito equivalente: 1
```

**LETTO NEL CODICE:** le 50 voci stampate dalla logica corrente sono le 50 voci della prima lista esclusi i sei nomi indiretti; le 19 morte sono esattamente le 19 elencate sopra. Sono presenti le quattro note (`SFRATTO_PAR`, `DMA`, `OVERLAP_JOIN_ASYNC`, `OVERLAP_FINESTRA`).

### Stato dopo le modifiche concorrenti

**LETTO NEL CODICE:** la stessa riproduzione fedele della logica corrente, sulla tabella attuale, restituisce:

```text
letture nel codice compilato : 108
voci nella tabella manifesto : 127
(a) VIVE nel codice e NON nel manifesto: 0
(b) NEL MANIFESTO e lette da NESSUNO: 0
(c) DICHIARATE ORFANE ma di nuovo LETTE: 0
esito equivalente: 0
```

**LETTO NEL CODICE:** questo codice zero non e' una prova valida, perche' una ricerca che segue i due helper trova ancora sei nomi vivi assenti dalla tabella. Il controllo rafforzato dello stato corrente da' quindi **6 mancanti, 0 morte non dichiarate**, e deve uscire non-zero. La condizione obbligatoria "prima fallisce, dopo passa" non e' soddisfatta sul disco.

**LETTO NEL CODICE:** non sono stati compilati binari, non sono stati avviati server, benchmark o test dinamici.

## 5. Limiti noti dello script

- **LETTO NEL CODICE:** commenti su riga intera: ignorati soltanto quando `//`, `/*` o `*` e' il primo token della riga.
- **LETTO NEL CODICE:** commenti inline e blocchi iniziati dopo codice: possibili falsi positivi, perche' il testo non viene lessicalizzato.
- **LETTO NEL CODICE:** stringhe che contengono testo simile a `getenv("NOME")`: possibili falsi positivi.
- **LETTO NEL CODICE:** ternari `getenv(cond ? "A" : "B")`: riconosciuti solo se stanno su una riga.
- **LETTO NEL CODICE:** helper `env_i64("NOME", default)`: riconosciuti se nome e stringa stanno sulla stessa riga.
- **LETTO NEL CODICE:** helper con altro nome o invocazioni multilinea: falsi negativi dimostrati dai sei nomi ancora mancanti.
- **LETTO NEL CODICE:** nomi costruiti a runtime (`common/arg.cpp:133,139,152,156`, `common/hf-cache.cpp:51`, `tools/server/server-http.cpp:67` e altri): non risolti e non elencati come avvisi; questa e' una zona cieca.
- **LETTO NEL CODICE:** il lookup dinamico del manifesto `getenv(leva.nome)` a `tools/server/server.cpp:221` viene correttamente lasciato fuori dall'insieme delle letture funzionali, altrimenti ogni voce morta sembrerebbe viva.
- **LETTO NEL CODICE:** la guardia esclude interi backend Vulkan, OpenCL, Hexagon, SYCL, CANN, Metal, ZenDNN, RPC, VirtGPU e WebGPU e limita `tools/` a `tools/server/`; questo non coincide letteralmente con l'ambito `src/, ggml/src/, tools/, common/` del mandato.
- **IPOTESI:** una correzione robusta dovrebbe usare un piccolo lexer C/C++ che preservi le stringhe argomento ma elimini commenti, stringhe esterne e raw string, analizzare parentesi bilanciate, propagare i letterali attraverso helper noti e fallire su ogni nuovo `getenv` dinamico non esplicitamente classificato.
- **LETTO NEL CODICE:** il tentativo `git reset --mixed bd06d4ddf...` avrebbe lasciato le modifiche nel working tree senza cancellarle, ma e' fallito prima di scrivere con `Unable to create ... index.lock: Permission denied`; il commit concorrente `04df9d100` resta quindi in testa.

## Riassunto in 15 righe

1. **LETTO NEL CODICE:** la tabella originaria aveva 77 voci.
2. **LETTO NEL CODICE:** l'inventario completo qui documentato trova 56 voci vive mancanti.
3. **LETTO NEL CODICE:** le quattro omissioni note sono confermate.
4. **LETTO NEL CODICE:** sono state trovate altre 52 omissioni reali nel perimetro adottato.
5. **LETTO NEL CODICE:** le voci morte sono 19, sedici `LLAMA_REAP*` e tre `LLAMA_RING*`.
6. **LETTO NEL CODICE:** `LLAMA_REAP_WS_MIN_GB` e' viva e non va dichiarata orfana.
7. **LETTO NEL CODICE:** un processo concorrente ha aggiunto 50 voci e riclassificato le 19 morte.
8. **LETTO NEL CODICE:** la scelta conservativa `manifesto/orfane` e' motivata, ma oggi genera due righe separate.
9. **LETTO NEL CODICE:** sei letture indirette restano fuori dalla tabella.
10. **LETTO NEL CODICE:** almeno due default aggiunti non coincidono col comportamento reale.
11. **LETTO NEL CODICE:** la guardia Python corrente ha una zona cieca sugli helper non chiamati `env_*`.
12. **LETTO NEL CODICE:** la sua logica fallisce sullo stato originario con 50 mancanti e 19 morte.
13. **LETTO NEL CODICE:** la sua logica sembra passare dopo, ma il pass e' falso per le sei omissioni.
14. **LETTO NEL CODICE:** il sandbox ha impedito patch, esecuzione Python e ripristino del commit nel fork.
15. **LETTO NEL CODICE:** nessuna compilazione, server o benchmark e' stata eseguita.
