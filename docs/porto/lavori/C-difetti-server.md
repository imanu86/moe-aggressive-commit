# Verifica difetti server

- **LETTO NEL CODICE:** stato del rapporto: verifica completata in sola lettura, senza compilazione, server o benchmark.

- **LETTO NEL CODICE:** i due difetti sono confermati nel file reale `D:\llama-overlap\tools\server\server-context.cpp`.
- **LETTO NEL CODICE:** il sandbox di questo agente ha rifiutato l'edit del repository `D:\llama-overlap` perche' esterno all'unica radice scrivibile.
- **LETTO NEL CODICE:** durante la verifica il repository esterno e' avanzato al commit concorrente `04df9d1002458d3acc9b75eea04c6095e8904e3c`, che include entrambi i fix in `server-context.cpp`; il diff locale dei due file consentiti e' ora vuoto.
- **LETTO NEL CODICE:** questo agente non ha eseguito commit e non attribuisce a se' le righe entrate nel commit concorrente.
- **LETTO NEL CODICE:** il commit concorrente include 15 righe di diff in `server-context.cpp`: la logica funzionale e' minima, ma i commenti esplicativi aggiunti rendono il diff testuale piu' ampio della sola correzione.
- **LETTO NEL CODICE:** i commenti correnti a `tools/server/server-context.cpp:371-373` citano ancora le vecchie righe `:4154`, `:4201`, `:4197`; dopo il loro stesso inserimento le righe funzionali sono `:4167`, `:4214`, `:4210`.
- **LETTO NEL CODICE:** il commento corrente a `tools/server/server-context.cpp:2225` dice “Unico sito del repo”; la sezione 4 conferma numerose altre leve booleane presence-based. La frase e' vera soltanto se letta come “unico sito di `LLAMA_KV_RING` non uniformato”.

## 1) Difetto 1

- **LETTO NEL CODICE:** `spec_replay` e' dichiarato con valore iniziale `false` in `tools/server/server-context.cpp:202`.
- **LETTO NEL CODICE:** nel parent del commit concorrente, `reset()` puliva gli altri stati speculativi (`spec_draft`, `spec_i_batch`, `spec_ckpt`) a `tools/server/server-context.cpp:366-369`, ma non `spec_replay`; la versione corrente aggiunge l'azzeramento a riga 375.
- **LETTO NEL CODICE:** `release()` porta lo slot a `SLOT_STATE_IDLE` e chiama `reset()` a `tools/server/server-context.cpp:552-568`.
- **LETTO NEL CODICE:** una nuova richiesta viene assegnata allo stesso slot a `tools/server/server-context.cpp:1934-1938`, senza altre scritture di `spec_replay`.
- **LETTO NEL CODICE:** il ramo di ripristino dopo accettazione parziale contabilizza la verifica reale a riga 4160, conserva gli accettati in `spec_draft` a riga 4163, imposta `spec_replay = true` a riga 4167 e ritorna a riga 4188.
- **LETTO NEL CODICE:** al normale giro successivo, la guardia a righe 4210-4212 salta l'aggiornamento statistico quando `spec_replay` e' vero e solo dopo lo azzera a riga 4214.
- **LETTO NEL CODICE:** prima del fix, se lo slot veniva rilasciato fra le righe funzionali oggi numerate 4167 e 4214, `release() -> reset()` non azzerava il flag; la prima verifica speculativa della richiesta successiva incontrava quindi il flag residuo, saltava `update_spec_stats()` e poi lo azzerava.
- **LETTO NEL CODICE:** fix minimo: `spec_replay = false;` nel blocco speculativo di `reset()`, accanto alle pulizie di `spec_draft`, `spec_i_batch` e `spec_ckpt`.
- **LETTO NEL CODICE:** alla rilettura il fix e' presente a `tools/server/server-context.cpp:375`. La parte funzionale e' una sola assegnazione nel punto che gia' delimita la vita dello stato speculativo per slot.

## 2) Difetto 2

- **LETTO NEL CODICE:** nel parent del commit concorrente, `tools/server/server-context.cpp:2219` usava direttamente `if (getenv("LLAMA_KV_RING"))`; una variabile presente con valore `0` restituiva comunque un puntatore non nullo.
- **LETTO NEL CODICE:** dentro quel ramo, le vecchie righe 2220-2222 calcolavano SHA-256 sull'intero `generated_text` e scrivevano il log `[kv-ring-output]` per la risposta; nella versione corrente le stesse operazioni sono a righe 2233-2235.
- **LETTO NEL CODICE:** la convenzione booleana `v && *v && *v != '0'` compare in `ggml/src/ggml-cuda/ggml-cuda.cu:1435-1437`; per la stessa leva, la forma piu' stretta `gate && *gate && strcmp(gate, "0") != 0` compare in `ggml/src/ggml-cuda/kv-ring.cu:114-116` e in `src/llama-context.cpp:551-552`.
- **LETTO NEL CODICE:** fix minimo: salvare `getenv("LLAMA_KV_RING")` in un puntatore e richiedere puntatore non nullo, stringa non vuota e valore diverso da `0`, senza cambiare calcolo o log.
- **LETTO NEL CODICE:** alla rilettura il fix e' presente a `tools/server/server-context.cpp:2231-2232` nella forma `kv_ring_gate && *kv_ring_gate && *kv_ring_gate != '0'`.

## 3) Lista (a): stato per-richiesta/per-slot non azzerato

- **LETTO NEL CODICE:** la ricerca globale con `rg` ha incluso dichiarazioni `slot`/`session` e funzioni `reset()`/`release()` in tutto il repository, non soltanto il server.
- **IPOTESI:** gli altri nomi `slot` trovati fuori dal server appartengono a cache/arena/eventi GPU o a sessioni locali di tokenizzazione; non e' stato individuato in essi il ciclo riusabile `richiesta -> release/reset -> richiesta` di `server_slot`.
- **IPOTESI:** oltre ad A1 e A2 non e' stato confermato un altro trascinamento fra richieste applicative; l'esito negativo non equivale a una prova formale su ogni struttura generica del repository.

### A1 - `n_remaining` ereditato da una richiesta finita

- **LETTO NEL CODICE:** `n_remaining` e' stato dello slot dichiarato a `tools/server/server-context.cpp:216` e `reset()` (`tools/server/server-context.cpp:353-407`) non lo azzera.
- **LETTO NEL CODICE:** per una richiesta con limite, `has_budget()` aggiorna `n_remaining` a `tools/server/server-context.cpp:467-473`; se la richiesta finisce anticipatamente, puo' restare positivo.
- **LETTO NEL CODICE:** per la richiesta successiva illimitata, `has_budget()` ritorna a `tools/server/server-context.cpp:463-464` prima dell'assegnazione `n_remaining = -1` di riga 467.
- **LETTO NEL CODICE:** `get_n_draft_max()` usa ogni valore positivo residuo per limitare la bozza a `tools/server/server-context.cpp:507-508`; un residuo pari a 1 porta il massimo a 0 e disabilita la speculazione per la richiesta illimitata.
- **IPOTESI:** gravita' **media**: non altera il testo bersaglio, ma puo' ridurre o spegnere silenziosamente la decodifica speculativa e falsare `n_remain` diagnostico.
- **LETTO NEL CODICE:** solo report; nessuna correzione applicata.

### A2 - prompt vuoto espone contatori e tempi della richiesta precedente

- **LETTO NEL CODICE:** i campi `n_decoded`, `n_prompt_tokens_processed`, `t_prompt_processing` e `t_token_generation` sono dichiarati a `tools/server/server-context.cpp:215`, `:220`, `:322-323`; `reset()` (`:353-407`) non li azzera.
- **LETTO NEL CODICE:** nel percorso normale `n_prompt_tokens_processed` viene azzerato a riga 3481, `n_decoded` a riga 3695 e i tempi vengono ricalcolati a righe 3505, 4047 e 4051.
- **LETTO NEL CODICE:** il ramo del prompt vuoto passa invece prima da `print_timings()` e `send_final_response()` a `tools/server/server-context.cpp:3233-3238`.
- **LETTO NEL CODICE:** `send_final_response()` copia `get_timings()` e `n_decoded` a `tools/server/server-context.cpp:2246` e `:2251`; `get_timings()` legge proprio quei campi a `:574-586`.
- **LETTO NEL CODICE:** dopo una richiesta precedente sullo stesso slot, una risposta a prompt vuoto puo' quindi riportare contatori e tempi vecchi; sul primo uso, i valori hanno gli inizializzatori di dichiarazione.
- **IPOTESI:** gravita' **media** per correttezza di telemetria/API, **bassa** per la generazione perche' il ramo termina senza inferenza.
- **LETTO NEL CODICE:** solo report; nessuna correzione applicata.

### Esito degli altri oggetti di sessione

- **LETTO NEL CODICE:** `stream_session_manager::create_or_replace()` costruisce sempre una nuova `stream_session` a `tools/server/server-stream.cpp:277-296`.
- **LETTO NEL CODICE:** il costruttore inizializza buffer, contatori, flag e timestamp a `tools/server/server-stream.cpp:137-146`; non c'e' riuso tramite `reset()`/`release()`.
- **LETTO NEL CODICE:** nessun ulteriore trascinamento per-richiesta confermato in `server-stream.cpp`.

## 4) Lista (b): leve booleane `getenv()` senza confronto con `"0"`

- **LETTO NEL CODICE:** ricerca eseguita con `rg` su tutto `D:\llama-overlap`, inclusi file nascosti ed esclusa soltanto `.git`; sono stati poi riletti i siti C/C++ candidati per separare leve booleane da percorsi, numeri e stringhe.
- **LETTO NEL CODICE:** i casi sotto sono aggiuntivi rispetto a `LLAMA_KV_RING`; per ciascuno la condizione usa la sola presenza, quindi anche la stringa `"0"` produce il ramo indicato.
- **IPOTESI:** la gravita' misura la sorpresa di configurazione e l'effetto del ramo; molte leve upstream sono intenzionalmente presence-based, quindi l'elenco non afferma automaticamente che ciascuna sia un bug.

### Albero sorgente principale, fuori da `rif_dwarfstar`

| Leva e sito | Effetto | Gravita' |
|---|---|---|
| **LETTO NEL CODICE:** compatibilita' `LLAMA_ARG_NO_*`, `common/arg.cpp:133-136` (rilevata anche a `:152-156`) | **LETTO NEL CODICE:** la presenza forza il valore falso dell'opzione corrispondente; `LLAMA_ARG_NO_X=0` la disabilita comunque. | **IPOTESI:** bassa-media, sorpresa di configurazione CLI. |
| **LETTO NEL CODICE:** `NO_COLOR`, `common/common.cpp:1117-1120` | **LETTO NEL CODICE:** ogni valore non vuoto, incluso `0`, disabilita i colori del terminale. | **IPOTESI:** bassa; e' la semantica standard di `NO_COLOR`. |
| **LETTO NEL CODICE:** `LLAMA_TRACE`, `common/speculative.cpp:1871` | **LETTO NEL CODICE:** rende verboso il modulo speculativo n-gram anche con `LLAMA_TRACE=0`. | **IPOTESI:** bassa, log e piccolo overhead. |
| **LETTO NEL CODICE:** `GGML_NO_BACKTRACE`, `ggml/src/ggml.c:158-160` e `ggml/src/ggml.cpp:17-19` | **LETTO NEL CODICE:** sopprime il backtrace anche con valore `0`. | **IPOTESI:** bassa-media, diagnostica persa sui crash. |
| **LETTO NEL CODICE:** `GGML_BACKTRACE_LLDB`, `ggml/src/ggml.c:167-168` | **LETTO NEL CODICE:** seleziona il cammino LLDB anche con valore `0`. | **IPOTESI:** media su macOS, perche' il commento segnala possibili problemi di attach/Terminal. |
| **LETTO NEL CODICE:** `GGML_RPC_DEBUG`, `ggml/src/ggml-rpc/ggml-rpc.cpp:21-24` e `ggml/src/ggml-rpc/transport.cpp:39-42` | **LETTO NEL CODICE:** abilita i log RPC di debug. | **IPOTESI:** bassa, rumore e overhead di log. |
| **LETTO NEL CODICE:** `GGML_DISABLE_VULKAN`, `ggml/src/ggml-backend-reg.cpp:127-130` | **LETTO NEL CODICE:** impedisce la registrazione del backend Vulkan. | **IPOTESI:** media-alta, backend richiesto non disponibile per un `=0`. |
| **LETTO NEL CODICE:** `GGML_CANN_NO_PINNED`, `ggml/src/ggml-cann/ggml-cann.cpp:1693-1694,2811` | **LETTO NEL CODICE:** disabilita l'allocazione host pinned e dichiara assente la relativa capacita'. | **IPOTESI:** media, prestazioni/trasferimenti host-device. |
| **LETTO NEL CODICE:** `GGML_SYCL_NO_PINNED`, `ggml/src/ggml-sycl/common.cpp:27-28` e `ggml/src/ggml-sycl/ggml-sycl.cpp:5538` | **LETTO NEL CODICE:** disabilita memoria host pinned e la capacita' esposta. | **IPOTESI:** media, prestazioni/trasferimenti. |
| **LETTO NEL CODICE:** `GGML_CUDA_DISABLE_GRAPHS`, `ggml/src/ggml-cuda/common.cuh:1241-1242` | **LETTO NEL CODICE:** disabilita i CUDA graph. | **IPOTESI:** media, regressione prestazionale silenziosa. **Bonificato 18/8 (A VALORE, LEDGER_18_AGOSTO.md).** |
| **LETTO NEL CODICE:** `GGML_CUDA_ENABLE_UNIFIED_MEMORY`, `ggml/src/ggml-cuda/ggml-cuda.cu:134-135,5438-5439` | **LETTO NEL CODICE:** usa allocazioni managed e forza la classificazione UMA. | **IPOTESI:** media-alta, politica di memoria e prestazioni cambiano materialmente. |
| **LETTO NEL CODICE:** `GGML_CUDA_P2P`, `ggml/src/ggml-cuda/ggml-cuda.cu:342-350,560` | **LETTO NEL CODICE:** abilita peer access CUDA e il relativo accesso VMM. | **IPOTESI:** media, topologia/trasferimenti multi-GPU. |
| **LETTO NEL CODICE:** `GGML_CUDA_NO_PINNED`, `ggml/src/ggml-cuda/ggml-cuda.cu:1210-1212,5476` | **LETTO NEL CODICE:** disabilita l'host allocator pinned e la capacita' riportata. | **IPOTESI:** media, prestazioni/trasferimenti. |
| **LETTO NEL CODICE:** `GGML_CUDA_REGISTER_HOST`, `ggml/src/ggml-cuda/ggml-cuda.cu:5295-5297,5318-5320` | **LETTO NEL CODICE:** abilita registrazione e deregistrazione CUDA dei buffer host. | **IPOTESI:** media, cambia gestione memoria host. |
| **LETTO NEL CODICE:** `GGML_METAL_FUSION_DISABLE` e `GGML_METAL_CONCURRENCY_DISABLE`, `ggml/src/ggml-metal/ggml-metal-context.m:136-137` | **LETTO NEL CODICE:** disabilitano rispettivamente fusioni e concorrenza Metal. | **IPOTESI:** media, prestazioni. |
| **LETTO NEL CODICE:** `GGML_METAL_GRAPH_OPTIMIZE_DISABLE`, `ggml/src/ggml-metal/ggml-metal-context.m:151-152` | **LETTO NEL CODICE:** disabilita l'ottimizzazione del grafo Metal. | **IPOTESI:** media, prestazioni. |
| **LETTO NEL CODICE:** `GGML_METAL_BF16_DISABLE`, `GGML_METAL_TENSOR_DISABLE`, `GGML_METAL_TENSOR_ENABLE`, `ggml/src/ggml-metal/ggml-metal-device.m:704-721` | **LETTO NEL CODICE:** forzano la disponibilita' dei percorsi BF16/Tensor nella direzione indicata dal nome. | **IPOTESI:** media-alta, scelta kernel e compatibilita' numerica/hardware. |
| **LETTO NEL CODICE:** `GGML_METAL_NO_RESIDENCY`, `ggml/src/ggml-metal/ggml-metal-device.m:829` | **LETTO NEL CODICE:** disabilita i residency set. | **IPOTESI:** media, gestione memoria Metal. |
| **LETTO NEL CODICE:** `GGML_METAL_SHARED_BUFFERS_DISABLE` e `GGML_METAL_SHARED_BUFFERS_ENABLE`, `ggml/src/ggml-metal/ggml-metal-device.m:837-841` | **LETTO NEL CODICE:** forzano in direzioni opposte l'uso dei buffer condivisi. | **IPOTESI:** media, politica memoria/prestazioni. |
| **LETTO NEL CODICE:** `GGML_OPENCL_ADRENO_XMEM_GEMM`, `ggml/src/ggml-opencl/ggml-opencl.cpp:5341-5342` | **LETTO NEL CODICE:** abilita il kernel xmem GEMM su Adreno. | **IPOTESI:** media, selezione kernel. |
| **LETTO NEL CODICE:** `GGML_OPENCL_ADRENO_USE_LARGE_BUFFER`, `ggml/src/ggml-opencl/ggml-opencl.cpp:5346-5347` | **LETTO NEL CODICE:** abilita il percorso large-buffer su Adreno. | **IPOTESI:** media, allocazione/prestazioni. |
| **LETTO NEL CODICE:** `GGML_OPENCL_DISABLE_FUSION`, `ggml/src/ggml-opencl/ggml-opencl.cpp:5425` | **LETTO NEL CODICE:** disabilita le fusioni OpenCL. | **IPOTESI:** media, prestazioni. |
| **LETTO NEL CODICE:** `GGML_REMOTING_USE_APIR_CAPSET`, `ggml/src/ggml-virtgpu/virtgpu.cpp:180` | **LETTO NEL CODICE:** abilita il capset APIR del backend virtgpu. | **IPOTESI:** media, cambia protocollo/capacita' del backend. |
| **LETTO NEL CODICE:** `GGML_VK_PREFER_HOST_MEMORY`, `GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM`, `GGML_VK_ALLOW_SYSMEM_FALLBACK`, `GGML_VK_DISABLE_GRAPH_OPTIMIZE`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:5772-5782` | **LETTO NEL CODICE:** forzano le omonime politiche di memoria e ottimizzazione Vulkan. | **IPOTESI:** media, memoria/prestazioni. |
| **LETTO NEL CODICE:** `GGML_VK_DISABLE_COOPMAT`, `GGML_VK_DISABLE_COOPMAT2`, `GGML_VK_DISABLE_COOPMAT2_DECODE_VECTOR`, `GGML_VK_DISABLE_INTEGER_DOT_PRODUCT`, `GGML_VK_DISABLE_BFLOAT16`, `GGML_VK_DISABLE_DOT2`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:5814-5842` e `:6635-6660` | **LETTO NEL CODICE:** disabilitano le estensioni/capacita' Vulkan indicate, anche con valore `0`. | **IPOTESI:** media-alta, selezione kernel e prestazioni; possibile perdita di un percorso hardware. |
| **LETTO NEL CODICE:** `GGML_VK_ENABLE_MEMORY_PRIORITY`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:5845-5847` | **LETTO NEL CODICE:** abilita la priorita' memoria Vulkan. | **IPOTESI:** media, politica memoria. |
| **LETTO NEL CODICE:** `GGML_VK_DISABLE_ASYNC`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:5926-5928` | **LETTO NEL CODICE:** disabilita il percorso asincrono Vulkan. | **IPOTESI:** media, prestazioni. |
| **LETTO NEL CODICE:** `GGML_VK_DISABLE_F16`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6012-6014,6666-6667` | **LETTO NEL CODICE:** forza la disabilitazione FP16. | **IPOTESI:** media-alta, scelta kernel e prestazioni. |
| **LETTO NEL CODICE:** `GGML_VK_ALLOW_GRAPHICS_QUEUE`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6030-6031` | **LETTO NEL CODICE:** permette di selezionare una coda grafica per il compute. | **IPOTESI:** media, scheduling/prestazioni. |
| **LETTO NEL CODICE:** `GGML_VK_DISABLE_MULTI_ADD`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6204-6206` | **LETTO NEL CODICE:** disabilita il kernel multi-add. | **IPOTESI:** media, prestazioni. |
| **LETTO NEL CODICE:** `GGML_VK_ASYNC_USE_TRANSFER_QUEUE`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6563-6565` | **LETTO NEL CODICE:** forza la transfer queue per il percorso asincrono. | **IPOTESI:** media, scheduling. |
| **LETTO NEL CODICE:** `GGML_VK_DISABLE_FUSION`, `GGML_VK_DISABLE_MMVQ`, `GGML_VK_FORCE_MMVQ`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6584,6593-6596` | **LETTO NEL CODICE:** disabilitano le fusioni o forzano/disabilitano MMVQ. | **IPOTESI:** media, scelta kernel/prestazioni. |
| **LETTO NEL CODICE:** `GGML_VK_DEBUG_MARKERS`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6850` | **LETTO NEL CODICE:** abilita i marker di debug Vulkan quando l'estensione esiste. | **IPOTESI:** bassa, diagnostica/overhead. |
| **LETTO NEL CODICE:** `GGML_VK_PERF_LOGGER`, `GGML_VK_PERF_LOGGER_CONCURRENT`, `GGML_VK_SYNC_LOGGER`, `GGML_VK_MEMORY_LOGGER`, `ggml/src/ggml-vulkan/ggml-vulkan.cpp:6899-6902` | **LETTO NEL CODICE:** abilitano i rispettivi logger Vulkan. | **IPOTESI:** bassa-media, log e sincronizzazioni diagnostiche. |
| **LETTO NEL CODICE:** `LLAMA_TRACE`, `tools/quantize/quantize.cpp:214-239` | **LETTO NEL CODICE:** esegue diagnostica aggiuntiva e stampa i dati di quantizzazione anche con `0`. | **IPOTESI:** bassa, solo strumento e overhead diagnostico. |
| **LETTO NEL CODICE:** `LLAMA_SKIP_TESTS_SLOW_ON_EMULATOR`, `tests/test-json-schema-to-grammar.cpp:1569-1572` | **LETTO NEL CODICE:** salta i test lenti anche con `0`. | **IPOTESI:** media per CI, perche' riduce la copertura. |
| **LETTO NEL CODICE:** `LLAMA_PYTHON_AVAILABLE`, `tests/test-json-schema-to-grammar.cpp:1514,1572` | **LETTO NEL CODICE:** dichiara Python disponibile e avvia i test Python senza validare il valore. | **IPOTESI:** bassa-media, possibile test fallito o diagnostica falsa. |
| **LETTO NEL CODICE:** `LLAMA_NODE_AVAILABLE`, `tests/test-json-schema-to-grammar.cpp:1513` | **LETTO NEL CODICE:** stampa disponibilita' vera con `0`; in questo file il sito osservato e' diagnostico. | **IPOTESI:** bassa. |
| **LETTO NEL CODICE:** `TEST_GRAMMAR_PARSER_PRINT_ALL`, `tests/test-grammar-parser.cpp:72-75` | **LETTO NEL CODICE:** stampa tutti i casi e ritorna. | **IPOTESI:** bassa, solo test. |
| **LETTO NEL CODICE:** `MTMD_DEBUG_EMBEDDINGS`, `tools/mtmd/clip.cpp:224` | **LETTO NEL CODICE:** abilita il dump/debug degli embedding multimodali. | **IPOTESI:** bassa-media, output e overhead. |
| **LETTO NEL CODICE:** `MTMD_DEBUG_GRAPH`, `tools/mtmd/mtmd-cli.cpp:157-160` | **LETTO NEL CODICE:** installa la callback di debug del grafo multimodale. | **IPOTESI:** bassa-media, overhead diagnostico. |
| **LETTO NEL CODICE:** `LLAMA_DEBUG_JINJA`, `tools/parser/debug-template-parser.cpp:369-370` | **LETTO NEL CODICE:** abilita il debug Jinja. | **IPOTESI:** bassa, strumento diagnostico. |

### Sottalbero di riferimento `rif_dwarfstar`

- **LETTO NEL CODICE:** `git ls-files` include tre file sotto `rif_dwarfstar`, quindi il grep globale li deve considerare.
- **LETTO NEL CODICE:** nessun riferimento a `rif_dwarfstar`, `ds4.c` o `ds4_cuda.cu` e' stato trovato nei `CMakeLists.txt`/`cmake` e negli alberi `ggml`, `src`, `tools`; questi siti non risultano nel grafo di build corrente.
- **IPOTESI:** gravita' comune delle voci seguenti: **informativa nel binario corrente**, **media se il sorgente di riferimento viene compilato separatamente**, salvo i soli interruttori di test/abort che diventano **alta**.
- **IPOTESI:** effetto comune applicato a ciascuna voce: una leva positiva seleziona/abilita il percorso nominato; una leva `NO_`/`DISABLE_` lo disabilita; `PROFILE`/`STATS`/`LOG`/`VERBOSE`/`DEBUG`/`TRACE`/`TIMING` abilita diagnostica. In tutti i siti elencati **LETTO NEL CODICE** il test e' sulla presenza e non sul valore, quindi `0` ha lo stesso effetto della presenza.

#### Diagnostica, profiling e log

- **LETTO NEL CODICE:** `DS4_DECODE_PROFILE_DETAIL` - `rif_dwarfstar/ds4.c:6775,6880,8640`.
- **LETTO NEL CODICE:** `DS4_PREFILL_PROFILE_DETAIL` - `rif_dwarfstar/ds4.c:7086,8291`; `DS4_PREFILL_PROFILE_TOKEN` - `rif_dwarfstar/ds4.c:8598`.
- **LETTO NEL CODICE:** `DS4_METAL_DECODE_STAGE_PROFILE` - `rif_dwarfstar/ds4.c:11184`; `DS4_METAL_INDEXER_STAGE_PROFILE` - `:11343,13378`; `DS4_METAL_LAYER_STAGE_PROFILE` - `:13379,14699`; `DS4_METAL_Q_STAGE_PROFILE` - `:13380`.
- **LETTO NEL CODICE:** `DS4_METAL_GRAPH_TOKEN_PROFILE` - `rif_dwarfstar/ds4.c:14967`; `DS4_METAL_GRAPH_PREFILL_SPLIT_PROFILE` - `:15425`; `DS4_METAL_GRAPH_PREFILL_PROFILE` - `:15433,15744`.
- **LETTO NEL CODICE:** `DS4_METAL_GRAPH_TRACE_LAYERS` - `rif_dwarfstar/ds4.c:12868`; `DS4_METAL_GRAPH_TRACE_CACHE` - `:16334`; `DS4_METAL_GRAPH_TRACE_COMP` - `:16335`.
- **LETTO NEL CODICE:** `DS4_METAL_MEMORY_REPORT` - `rif_dwarfstar/ds4.c:16291,17689`; `DS4_TRACE_TOP` - `:17550,17693`; `DS4_TOKEN_TIMING` - `:17582,17694`.
- **LETTO NEL CODICE:** `DS4_MTP_PROBE` - `rif_dwarfstar/ds4.c:20839,20879`; `DS4_MTP_TIMING` - `:20953`; `DS4_MTP_CONF_LOG` - `:20954`; `DS4_MTP_SPEC_LOG` - `:20970,21152,21405,21422,21475`; `DS4_MTP_FULL_LOGITS` - `:20875,20956`; `DS4_MTP_EXACT_REPLAY` - `:21174`.
- **LETTO NEL CODICE:** `DS4_CUDA_WEIGHT_CACHE_VERBOSE` - `rif_dwarfstar/ds4_cuda.cu:3031,3051,3092,3177,3367,3418,5069,6984,7062,7226,7318,15765,15769,37889`; `DS4_CUDA_MODEL_COPY_VERBOSE` - `:7399`.
- **LETTO NEL CODICE:** `DS4_IQ1_S_PROFILE` - `rif_dwarfstar/ds4_cuda.cu:6555,6928,37195,43859`; `DS4_IQ1_MIXED_DEBUG` - `:39718,41248,41593`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_CACHE_STATS` - `rif_dwarfstar/ds4_cuda.cu:27628`; `DS4_CUDA_MOE_ROUTE_PROFILE` - `:36804`; `DS4_CUDA_PREFILL_UNION_STATS` - `:36806,40713`; `DS4_CUDA_SEL_PROFILE` - `:37328`; `DS4_CUDA_MOE_PROFILE` - `:39650,40026`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_DIRECT_CACHE_STATS` - `rif_dwarfstar/ds4_cuda.cu:37796`; `DS4_CUDA_MOE_MIXED_DIRECT_STATS` - `:37847`.
- **LETTO NEL CODICE:** `DS4_NESTED_RESIDUAL_VERIFY_RECONSTRUCTION` - `rif_dwarfstar/ds4_cuda.cu:6083,36071,36499`.

#### Memoria, cache, copie e prefetch

- **LETTO NEL CODICE:** `DS4_CUDA_EMBED_ROW_STAGING` - `rif_dwarfstar/ds4.c:1714` e `rif_dwarfstar/ds4_cuda.cu:19896,19937`.
- **LETTO NEL CODICE:** `DS4_CUDA_DIRECT_MODEL` - `rif_dwarfstar/ds4.c:1813` e `rif_dwarfstar/ds4_cuda.cu:2974-2975,7335`; `DS4_CUDA_NO_MODEL_COPY` - `rif_dwarfstar/ds4_cuda.cu:7334`; `DS4_CUDA_NO_MODEL_PREFETCH` - `:5132`.
- **LETTO NEL CODICE:** `DS4_CUDA_COPY_MODEL` - `rif_dwarfstar/ds4_cuda.cu:5133`; `DS4_CUDA_COPY_MODEL_CHUNKED` - `:15704,15716,15720`; `DS4_CUDA_MODEL_PREFETCH_SYNC` - `:5192`; `DS4_CUDA_KEEP_MODEL_PAGES` - `:5226,5244`; `DS4_CUDA_NO_DIRECT_IO` - `:15754`.
- **LETTO NEL CODICE:** `DS4_CUDA_WEIGHT_CACHE` - `rif_dwarfstar/ds4_cuda.cu:2970,5134,7336`; `DS4_CUDA_WEIGHT_PRELOAD` - `:2971,5135,7337`; `DS4_CUDA_NO_FD_CACHE` - `:3000`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_Q8_F16_CACHE` - `rif_dwarfstar/ds4_cuda.cu:3263`; `DS4_CUDA_Q8_F16_ALL` - `:3265,3304`; `DS4_CUDA_Q8_F16_PRELOAD` - `rif_dwarfstar/ds4.c:1820`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_ATTENTION_OUTPUT_F16_CACHE` - `rif_dwarfstar/ds4_cuda.cu:3271`; `DS4_CUDA_NO_ATTN_Q_B_F16_CACHE` - `:3274,3285`; `DS4_CUDA_ATTENTION_OUTPUT_PRELOAD` - `:3303`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_Q8_F32_CACHE` - `rif_dwarfstar/ds4_cuda.cu:3311`; `DS4_CUDA_Q8_F32_ALL` - `:3312`; `DS4_CUDA_ATTN_Q_B_F32_CACHE` - `:3314`; `DS4_CUDA_Q8_F32_LARGE` - `:3316`; `DS4_CUDA_Q8_F32_PRELOAD` - `rif_dwarfstar/ds4.c:1821` e `rif_dwarfstar/ds4_cuda.cu:16260`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_DIRECT_CACHE_HITS` - `rif_dwarfstar/ds4_cuda.cu:37613`; `DS4_Q1_0_SELECTED_LOAD` - `:38583,39555`; `DS4_CUDA_MOE_NO_SELECTED_LOAD` - `rif_dwarfstar/ds4.c:1720,10043` e `rif_dwarfstar/ds4_cuda.cu:35864,39537,39556,39579,39602,39647,39817`.
- **LETTO NEL CODICE:** `DS4_IQ1_S_PACKED_H2D` - `rif_dwarfstar/ds4_cuda.cu:37127`; `DS4_IQ1_MIXED_GPU_PLAN` - `:43862`; `DS4_IQ1_MIXED_NO_MAIN_SYNC` - `:43860`.

#### Scelta di kernel e algoritmi

- **LETTO NEL CODICE:** `DS4_ROUTED_TOKEN_PARALLEL` e `DS4_NO_ROUTED_TOKEN_PARALLEL` - `rif_dwarfstar/ds4.c:7102-7103`; `DS4_PARALLEL_ATTN_ROWS` e `DS4_NO_PARALLEL_ATTN_ROWS` - `:8369,8372`; `DS4_NO_BATCHED_ROPE` - `:8386`.
- **LETTO NEL CODICE:** `DS4_NO_BATCHED_ATTN`, `DS4_BATCHED_FFN`, `DS4_PARALLEL_FFN`, `DS4_NO_SHARED_BATCH_FFN` - `rif_dwarfstar/ds4.c:8878-8881`.
- **LETTO NEL CODICE:** `DS4_METAL_DISABLE_SHARED_GATE_UP_SWIGLU_FUSION` - `rif_dwarfstar/ds4.c:11787`; `DS4_METAL_NO_PREFILL_KERNEL_WARMUP` - `:13256`; `DS4_METAL_GRAPH_TEACHER_FORCE` - `:12871`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_Q8_DP4A` - `rif_dwarfstar/ds4_cuda.cu:3298`; `DS4_CUDA_NO_TF32` - `:7470,16283`; `DS4_CUDA_NO_Q8_BATCH_WARP` - `:21599`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_INDEXER_DIRECT_ONE` - `rif_dwarfstar/ds4_cuda.cu:21210`; `DS4_CUDA_NO_INDEXER_WMMA` - `:21220`; `DS4_CUDA_NO_INDEXED_HEADS8` - `:23033`; `DS4_CUDA_INDEXED_TWOPASS` - `:23035`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_TOPK1024` - `rif_dwarfstar/ds4_cuda.cu:21403`; `DS4_CUDA_NO_TOPK2048` - `:21410,21417,21423`; `DS4_CUDA_NO_TOPK_CHUNKED` - `:21424`.
- **LETTO NEL CODICE:** `DS4_CUDA_SERIAL_F16_MATMUL` - `rif_dwarfstar/ds4_cuda.cu:21771,21840`; `DS4_CUDA_SERIAL_ROUTER` - `:21776,21841`; `DS4_CUDA_NO_ORDERED_F16_MATMUL` - `:21781,21842`; `DS4_CUDA_NO_F16_PAIR_MATMUL` - `:21839`.
- **LETTO NEL CODICE:** `DS4_CUDA_DISABLE_QKV_RMS_FUSED` - `rif_dwarfstar/ds4_cuda.cu:21969`; `DS4_CUDA_DISABLE_SHARED_GATE_UP_PAIR` - `:23496`; `DS4_CUDA_DISABLE_HC_SPLIT_NORM_FUSED` - `:44259`; `DS4_CUDA_DISABLE_Q8_HC_EXPAND_FUSED` - `:44403,44435`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_WINDOW_ATTENTION` - `rif_dwarfstar/ds4_cuda.cu:22664,22709,22865,22888,23126`; `DS4_CUDA_WINDOW_ATTENTION` - `:22710,22889,23127`; `DS4_CUDA_NO_CUBLAS_ATTENTION` - `:22726,23143`; `DS4_CUDA_NO_CUBLAS_ATTENTION_OUTPUT_A` - `:23328`.
- **LETTO NEL CODICE:** `DS4_CUDA_NO_WARP_ROUTER_SELECT` - `rif_dwarfstar/ds4_cuda.cu:23565,23614`; `DS4_CUDA_NO_PARALLEL_ROUTER_SELECT` - `:23566,23572,23615,23630`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_MIXED_DIRECT` - `rif_dwarfstar/ds4_cuda.cu:37604`; `DS4_CUDA_MOE_NO_DECODE_LUT_GATE` - `:37609,38996,39015,40070`; `DS4_CUDA_MOE_NO_DIRECT_DOWN_SUM6` - `:37610,38997,39016,40089`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_TILE4` - `rif_dwarfstar/ds4_cuda.cu:40050`; `DS4_CUDA_MOE_WRITE_GATE_UP` - `:40051`; `DS4_CUDA_MOE_NO_EXPERT_TILES` - `:40049`; `DS4_CUDA_MOE_NO_P2` - `:40052`; `DS4_CUDA_MOE_ATOMIC_DOWN` e `DS4_CUDA_MOE_NO_ATOMIC_DOWN` - `:40054-40055`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_GATE_ROW128`, `DS4_CUDA_MOE_GATE_ROW256`, `DS4_CUDA_MOE_GATE_ROW512`, `DS4_CUDA_MOE_GATE_ROW2048` - `rif_dwarfstar/ds4_cuda.cu:40057-40059,40072-40073`; varianti `NO_GATE_ROW128`, `NO_GATE_ROW256`, `NO_GATE_ROW2048` - `:40061-40063`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_DOWN_ROW64`, `DOWN_ROW128`, `DOWN_ROW256`, `DOWN_ROW512`, `DOWN_ROW1024`, `DOWN_ROW2048` - `rif_dwarfstar/ds4_cuda.cu:40075-40081`; varianti `NO_DOWN_ROW64`, `NO_DOWN_ROW128`, `NO_DOWN_ROW256`, `NO_DOWN_ROW2048` - `:40083-40086`.
- **LETTO NEL CODICE:** `DS4_CUDA_MOE_NO_DOWN_TILE16` - `rif_dwarfstar/ds4_cuda.cu:40065`; `DS4_CUDA_MOE_NO_DOWN_BLOCK16` - `:40067`.

#### Controlli MTP e test

- **LETTO NEL CODICE:** `DS4_MTP_STRICT` abilita la modalita' stretta a `rif_dwarfstar/ds4.c:20945`; `DS4_MTP_CAPTURE_PREFIX1` abilita la cattura a `:21173`; `DS4_MTP_FORCE_SNAPSHOT` forza lo snapshot a `:21178`.
- **LETTO NEL CODICE:** `DS4_MTP_BATCH_VERIFY` e' un'eccezione al rubric del nome: a `rif_dwarfstar/ds4.c:21072` la sua presenza rende falsa `can_batch_verify`, quindi `DS4_MTP_BATCH_VERIFY=0` disabilita la verifica batch.
- **LETTO NEL CODICE:** `DS4_CUDA_DYNAMIC_ARENA_TEST_ABORT` - `rif_dwarfstar/ds4.c:20330`.
- **IPOTESI:** `DS4_CUDA_DYNAMIC_ARENA_TEST_ABORT=0` ha gravita' **alta se il riferimento viene eseguito**, perche' la sola presenza abilita un abort di test.

#### Controlli dinamici per nome

- **LETTO NEL CODICE:** `rif_dwarfstar/ds4_cuda.cu:1561` tratta come attiva ogni variabile della lista di incompatibilita' G73 quando `getenv(name)` e' non nullo; anche una voce impostata a `0` puo' quindi far rifiutare la configurazione.
- **IPOTESI:** gravita' **media se il riferimento viene compilato**, per falso errore di configurazione.
- **LETTO NEL CODICE:** `rif_dwarfstar/ds4_cuda.cu:39602-39604` considera `DS4_CUDA_PREFILL_WAVES` presente anche se vale `0` e rifiuta il trasporto selected-load richiesto dal nested residual.
- **IPOTESI:** gravita' **media se il riferimento viene compilato**, per falso errore di configurazione.
- **LETTO NEL CODICE:** `rif_dwarfstar/ds4_cuda.cu:2022-2024` considera presenti le variabili dipendenti di `DS4_EXPERT_RECOVERY_TRACE` anche se valgono `0`, e fallisce se la leva principale non e' impostata.
- **IPOTESI:** gravita' **media se il riferimento viene compilato**, per falso errore di configurazione.
