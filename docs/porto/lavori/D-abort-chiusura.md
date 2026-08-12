# Diagnosi del crash di `llama-server.exe` alla chiusura

**LETTO NEL CODICE** — Stato: rapporto finale di diagnosi pura; nessuna modifica applicata al codice, al registro o alla configurazione di sistema.

**LETTO NEI LOG** — Data dell'analisi: 12 agosto 2026; finestra esaminata: 10–12 agosto 2026.

## Esito

- **LETTO NEI LOG** — La causa delle chiusure ordinate è identificata direttamente in otto minidump: la UCRT sta eseguendo come callback `atexit` `ggml_cuda_kv_ring_dump()`; questa chiama `ggml_cuda_set_device()`, `cudaGetDevice()` restituisce la stringa esatta `driver shutting down`, `CUDA_CHECK` entra in `ggml_cuda_error()` e `GGML_ABORT` chiama `abort()`.
- **LETTO NEL CODICE** — La callback tardiva nasce in `ggml/src/ggml-cuda/kv-ring.cu:157-177`: quando `LLAMA_KV_RING` è attivo, l'inizializzazione registra `atexit(ggml_cuda_kv_ring_free)` e poi `atexit(ggml_cuda_kv_ring_dump)`.
- **LETTO NEI LOG** — Il punto terminale `ucrtbase.dll+0xa527e` ha sottocodice fast-fail 7; `P9` degli eventi WER è `0000000000000007` e il record eccezione dei dump contiene lo stesso valore.
- **LETTO NEL CODICE** — `winnt.h:23048` definisce 7 come `FAST_FAIL_FATAL_APP_EXIT`; `winnt.h:23043` definisce invece 2 come `FAST_FAIL_STACK_COOKIE_CHECK_FAILURE`.
- **LETTO NEL CODICE** — `ggml/src/ggml.c:252-271` mostra che `ggml_abort()` chiama direttamente `abort()`; il disassemblato del binario caricato chiama la sua importazione UCRT `abort` subito prima del return address `ggml-base.dll+0x199f`.
- **LETTO NEI LOG** — Quindi, per i dump di chiusura, `0xc0000409` non segnala una corruzione dello stack: è l'esito intenzionale di `abort()` dopo un errore CUDA di runtime in unload.
- **LETTO NEI LOG** — Due dei dieci dump attualmente conservati non sono chiusure: sono abort durante inferenza per `cudaGraphLaunch(...): out of memory`. Condividono lo stesso terminale UCRT e lo stesso bucket della build, ma non la causa a monte.
- **IPOTESI** — Per le chiusure ordinate della build corrente la probabilità della causa KV-ring/`atexit` è superiore al 95%: è verificata in 8/8 dump di chiusura disponibili e tutti i log correlati terminano sulla medesima riga `ggml-cuda.cu:108`; i dump più vecchi sono già usciti dalla rotazione.

## Perimetro e riproducibilità dell'analisi

- **LETTO NEL CODICE** — Il sorgente letto è il working tree effettivo di `D:\llama-overlap`, HEAD `04df9d1002458d3acc9b75eea04c6095e8904e3c`.
- **LETTO NEL CODICE** — Il working tree contiene una modifica locale a `ggml/src/ggml-backend.cpp`; il diff modifica la sola strumentazione `GGML_SCHED_PROFILO` e non la logica di arresto del worker.
- **LETTO NEL CODICE** — Sono presenti numerosi file non tracciati di misura; nessuno è stato modificato o cancellato durante questa diagnosi.
- **LETTO NEL CODICE** — Il `ggml-cuda.dll` caricato nei dump ha timestamp PE `0x6a7bbfe6`, uguale al binario corrente in `build/bin`; il disassemblato contiene i numeri di riga e le stringhe del sorgente corrente usati per attribuire i frame.
- **LETTO NEI LOG** — Non sono stati trovati PDB, MAP o ILK utili e non risultano installati WinDbg/CDB; la catena è stata ricostruita in sola lettura dai record MINIDUMP, dalle tabelle PE/unwind, dalle importazioni e dal disassemblato.
- **LETTO NEL CODICE** — Non è stata compilata né eseguita alcuna build e non è stato avviato `llama-server.exe`.

## Verifica dei conteggi e correlazione temporale

| Data | Risultato della query diretta `Get-WinEvent` Event ID 1000 | Confronto con i conteggi forniti |
|---|---|---|
| 10 agosto | **LETTO NEI LOG** — 10 eventi `ucrtbase.dll / 0xc0000409 / +0xa527e` e 1 evento `llama.dll / 0xc0000005`; totale 11. | **LETTO NEI LOG** — Il valore fornito 11 è il totale di tutti i crash di `llama-server.exe`, non il solo gruppo UCRT. |
| 11 agosto | **LETTO NEI LOG** — 11 eventi UCRT identici e 3 eventi `cupti64_126.dll / 0xc0000005`; totale 14. | **LETTO NEI LOG** — Il valore fornito 14 è anche qui il totale di tutti i moduli. |
| 12 agosto, fino alle 11:32 | **LETTO NEI LOG** — 19 eventi UCRT identici, senza altri moduli nel periodo interrogato. | **LETTO NEI LOG** — Il valore fornito 12 era già superato al momento della verifica; un nuovo evento è apparso durante l'analisi. |

- **LETTO NEI LOG** — Tutti i 40 eventi UCRT dei tre giorni hanno versione UCRT `10.0.26100.8875`, offset `0xa527e`, codice `0xc0000409` e `P9=7`.
- **LETTO NEI LOG** — Il bucket `1415363239619437240` non è letteralmente unico per tutte le build dei tre giorni: appartiene alla build con `P3=6a7ad71c` e copre 9 eventi dell'11 agosto e tutti i 19 del 12; build precedenti del 10 e dell'11 hanno bucket diversi pur mantenendo UCRT, offset, codice e `P9` uguali.
- **LETTO NEI LOG** — La variazione del bucket segue il timestamp `P3` di `llama-server.exe`; non indica una diversa funzione UCRT.
- **LETTO NEI LOG** — Gli eventi WER della build corrente classificano il problema come `BEX64`, con `P4=ucrtbase.dll`, `P7=00000000000a527e`, `P8=c0000409`, `P9=0000000000000007`.

### Correlazioni rappresentative

- **LETTO NEI LOG** — `q_join.server.log:634-662` registra: server inattivo, `cleaning up before exit...`, breakdown `Host 75388 MiB`, dump della cache esperti e infine `ggml-cuda.cu:108: CUDA error`; l'Event 1000 segue alle 11:12:29 e il dump PID 15244 alle 11:12:32.
- **LETTO NEI LOG** — `q_rif.server.log:635-663` presenta la stessa sequenza; l'Event 1000 è alle 11:32:07 e il dump PID 10516 alle 11:32:10.
- **LETTO NEI LOG** — `k448.server.log:635-663`, `k512.server.log:637-665`, `r512.server.log:637-665`, `s512.server.log:634-662`, `q_dma.server.log:663-690` e `q_fu7.server.log:637-665` mostrano la stessa chiusura ordinata e sono entro 2,6–4,5 secondi dal rispettivo evento.
- **LETTO NEI LOG** — I manifesti di queste corse riportano tutti `LLAMA_KV_RING=1(E)`; la callback trovata nel dump è quindi coerente con la configurazione di ciascuna corsa.
- **LETTO NEI LOG** — `q_fu6.server.log:487-490` e `q_fu4.server.log:484-487` non contengono `cleaning up`: abortiscono durante `cudaGraphLaunch` con `CUDA error: out of memory`.
- **LETTO NEI LOG** — I dump PID 19056 e 4336 confermano per queste due corse il messaggio `out of memory` e un return address CUDA diverso da quello del KV ring.
- **LETTO NEI LOG** — Lo stesso offset e bucket UCRT sono dunque il terminale comune di `ggml_abort()->abort()`, non una firma sufficiente della causa CUDA a monte.

## 1. Cammino di uscita completo

### Entrypoint, segnale e arresto del servizio

1. **LETTO NEL CODICE** — `tools/server/main.cpp:1-4` contiene soltanto `main() -> llama_server(argc, argv)`.
2. **LETTO NEL CODICE** — `tools/server/server.cpp:291-310` costruisce i parametri, inizializza il singleton delle sessioni stream, analizza gli argomenti, chiama `llama_backend_init()` e poi entra in `llama_server(params,...)`.
3. **LETTO NEL CODICE** — `server.cpp:27-28,231-240` conserva un `shutdown_handler` statico e usa un `atomic_flag`: il primo interrupt invoca l'handler, il secondo chiama direttamente `exit(1)`.
4. **LETTO NEL CODICE** — `server.cpp:649-653` registra su Windows un `SetConsoleCtrlHandler` che gestisce soltanto `CTRL_C_EVENT`; per `CTRL_BREAK_EVENT`, `CTRL_CLOSE_EVENT`, `CTRL_LOGOFF_EVENT` e `CTRL_SHUTDOWN_EVENT` restituisce `FALSE`.
5. **LETTO NEL CODICE** — `server.cpp:634-637` imposta l'handler della modalità non-router a `ctx_server.terminate()`.
6. **LETTO NEL CODICE** — `server-context.cpp:4280-4287` inoltra `terminate()` a `queue_tasks.terminate()`.
7. **LETTO NEL CODICE** — `server-queue.cpp:119-146` pone `running=false`, notifica la condition variable e fa ritornare `start_loop()` sul thread principale.
8. **LETTO NEL CODICE** — `server.cpp:682-690` chiama quindi `clean_up()`, unisce il thread HTTP e l'eventuale monitor del processo figlio.
9. **LETTO NEL CODICE** — `server.cpp:597-604` mostra che `clean_up()` ferma e unisce il GC delle sessioni, ferma HTTP, ritermina la queue e chiama `llama_backend_free()`.
10. **LETTO NEL CODICE** — `src/llama.cpp:116-118` mostra che il nome `llama_backend_free()` è fuorviante per questo scopo: libera solo le tabelle di quantizzazione tramite `ggml_quantize_free()`; non distrugge contesti, backend, buffer o CUDA Runtime.
11. **LETTO NEL CODICE** — `server.cpp:693-699` stampa il breakdown mentre `ctx_server` è ancora vivo e poi ritorna; la distruzione del modello non avviene dentro `clean_up()`.

### Thread e worker

- **LETTO NEL CODICE** — `server-stream.cpp:357-393` porta `running=false`, notifica, fa `join()` del thread GC e finalizza le sessioni prima di distruggerne mutex e condition variable.
- **LETTO NEL CODICE** — `server-http.cpp:440-452` avvia un thread di ascolto; `server.cpp:685-688` chiama prima `stop()` e poi `join()`.
- **LETTO NEL CODICE** — `server.cpp:676-690` conserva l'eventuale monitor del child in uno `std::thread` locale e lo unisce esplicitamente.
- **LETTO NEL CODICE** — `ggml-backend.cpp:824-925` definisce il worker overlap CPU con thread, mutex, condition variable, stato atomico e lavoro preso per valore.
- **LETTO NEL CODICE** — `ggml-backend.cpp:940-964` rende il join difensivo un no-op quando non vi è lavoro; l'arresto pone `abortito`, pubblica `FERMA`, notifica e chiama `th.join()`.
- **LETTO NEL CODICE** — `ggml-backend.cpp:2398-2413` chiama questo arresto prima di cancellare il worker e prima di liberare gli eventi dello scheduler.
- **LETTO NEL CODICE** — `ggml-backend.cpp:2436-2455,2528-2541` unisce inoltre il worker nei reset e nelle sincronizzazioni.
- **LETTO NEL CODICE** — `ggml-cpu/ggml-cpu.c:2711-2739` ferma il pool CPU, notifica e unisce tutti i worker secondari prima di distruggere mutex/condition e memoria del pool.
- **LETTO NEL CODICE** — `llama-context.h:386-387` inizializza a null i threadpool esterni e il server non chiama `llama_attach_threadpool()`; quando il piano CPU non ne riceve uno, `ggml-cpu.c:3266-3340,3350-3414` crea un pool transitorio e lo libera prima che il calcolo ritorni.
- **LETTO NEL CODICE** — `ggml-cpu/ggml-cpu.cpp:99-122` conserva l'eventuale threadpool come puntatore preso in prestito e il backend CPU non tenta una seconda free.
- **LETTO NEL CODICE** — `cache-esperti.cu:1770-1774` pone `ferma=true`, notifica e unisce/cancella il thread di servizio della cache prima di liberare eventi, stream e buffer.
- **LETTO NEL CODICE** — `common/log.h:48-60` e `common/log.cpp:373-385` documentano e implementano una scelta diversa per il logger: il singleton con thread è intenzionalmente lasciato allocato per evitare hang nel teardown DLL Windows.
- **LETTO NEI LOG** — La thread di eccezione dei dump ordinati ha nello stack la catena di ritorno di `main` e il dispatcher `atexit`; non è il worker overlap, il pool CPU, il servizio cache o un thread HTTP.

### Distruzione degli oggetti automatici

- **LETTO NEL CODICE** — Gli oggetti sono costruiti in `server.cpp:365-383` nell'ordine `ctx_server`, `ctx_http`, `child`, `routes`, `tools`, `models_routes`; dopo il return sono distrutti in ordine inverso, con `ctx_server` per ultimo.
- **LETTO NEL CODICE** — `server-context.cpp:1004-1009,1073-1087` fa eseguire al distruttore di `server_context_impl`: `spec.reset()`, `spec_init.reset()`, quindi `llama_init.reset()`, infine `mtmd_free()`.
- **LETTO NEL CODICE** — `common/speculative.cpp:2342-2349` dichiara modello draft prima del contesto draft; la distruzione inversa elimina prima il contesto e poi il modello.
- **LETTO NEL CODICE** — `common/common.cpp:1203-1216` usa lo stesso ordine per il target: samplers e LoRA, poi contesto, infine modello.
- **LETTO NEL CODICE** — `include/llama-cpp.h:11-28` collega le `unique_ptr` a `llama_free()` e `llama_model_free()`.
- **LETTO NEL CODICE** — `llama-context.cpp:588-606` esegue il corpo del distruttore e poi C++ distrugge i membri in ordine inverso rispetto a `llama-context.h`.
- **LETTO NEL CODICE** — In `llama-context.h:356,380-406`, i buffer di memoria/grafo/output più tardivi sono eliminati prima; la vector proprietaria `backends` alla riga 381 è distrutta prima dello scheduler dichiarato alla riga 356.
- **LETTO NEL CODICE** — `ggml/include/ggml-cpp.h:31-39` inoltra la distruzione delle `unique_ptr` a `ggml_backend_free`, `ggml_backend_buffer_free`, `ggml_backend_event_free` e `ggml_backend_sched_free`.
- **LETTO NEL CODICE** — `ggml-cuda.cu:3040-3044` distrugge ogni backend CUDA cancellandone il `ggml_backend_cuda_context`.
- **LETTO NEL CODICE** — `ggml-cuda.cu:648-668` attende che non vi siano catture di grafi, scarica la cache esperti, distrugge copy event, stream e handle cuBLAS.
- **LETTO NEL CODICE** — I pool CUDA sono membri a `common.cuh:1497-1506` e vengono distrutti automaticamente dopo il corpo del distruttore; i pool legacy selezionano il device e fanno `cudaFree` in `ggml-cuda.cu:385-400`.
- **LETTO NEL CODICE** — `llama-model.cpp:982-1005` conserva i buffer del modello in `pimpl->ctxs_bufs`; il pimpl è distrutto dopo il corpo di `llama_model::~llama_model()` a `llama-model.cpp:1031-1035`.
- **LETTO NEL CODICE** — Il buffer mappato zero-copy usa `cudaHostAlloc(...Mapped|Portable)` a `ggml-cuda.cu:1357-1403` e il suo deleter chiama `cudaFreeHost(ctx->host)` a `ggml-cuda.cu:1298-1301`.
- **LETTO NEI LOG** — `q_join.server.log:160,164-166` attribuisce al modello target 74 304 MiB `CUDA0_Mapped`, 7 383,67 MiB CUDA0 e 1 010 MiB CUDA_Host.
- **LETTO NEI LOG** — Il fatto che lo stack raggiunga il dispatcher `atexit` prova che i distruttori automatici del server, inclusi contesto e modello, sono già ritornati; un abort da `cudaFreeHost` sarebbe comparso prima e con un caller CUDA diverso.

### Fase globale/statica: il punto guasto

1. **LETTO NEL CODICE** — `kv-ring.cu:157-177` inizializza il contatore globale `g_ring` e registra due callback `atexit`.
2. **LETTO NEL CODICE** — `kv-ring.cu:257-276` implementa il dump: acquisisce `g_mutex`, controlla `initialized`, chiama `ggml_cuda_set_device`, sincronizza e copia i contatori prima di stampare.
3. **LETTO NEI LOG** — Il frame nel dump è l'ingresso effettivo di `ggml_cuda_kv_ring_dump()`; il return address `ggml-cuda.dll+0x16ced1` cade subito dopo la chiamata a `ggml_cuda_set_device`.
4. **LETTO NEL CODICE** — Il disassemblato del blocco di errore passa la costante 115 a `ggml_cuda_error`, identificando `ggml-cuda.cu:115`: `CUDA_CHECK(cudaGetDevice(&current_device))`.
5. **LETTO NEI LOG** — Il quinto argomento di `ggml_cuda_error` punta a `cudart64_12.dll+0x63608`, che contiene `driver shutting down`.
6. **LETTO NEL CODICE** — L'header CUDA 12.6 installato, `driver_types.h:237`, definisce `cudaErrorCudartUnloading = 4`; la stringa osservata è coerente con il runtime in unload.
7. **LETTO NEL CODICE** — `ggml-cuda.cu:99-108` passa l'errore a `GGML_ABORT`; `ggml.c:252-271` stampa e chiama `abort()`.
8. **LETTO NEI LOG** — Il crash avviene quindi durante il teardown globale, dopo il teardown degli oggetti server, quando la CUDA Runtime ha già iniziato lo smontaggio.
9. **LETTO NEL CODICE** — Non esiste nel fork alcuna chiamata a `cudaDeviceReset`, `cudaThreadExit`, `cuDevicePrimaryCtxRelease` o equivalente.
10. **LETTO NEL CODICE** — `ggml-backend-reg.cpp:169-176` evita intenzionalmente di scaricare i backend dinamici e rilascia la proprietà degli handle; CUDA rimane demandata al teardown del processo/DLL.
11. **LETTO NEI LOG** — La risposta alla domanda “esistono statici distrutti dopo CUDA?” è sì: non un normale distruttore C++ del modello, ma le callback `atexit` che gestiscono lo stato globale KV ring sono eseguite quando CUDART risponde già `driver shutting down`.

### Ctrl+C, altri eventi console e `Stop-Process -Force`

- **LETTO NEL CODICE** — Un vero primo Ctrl+C percorre il cammino ordinato appena ricostruito e arriva al return di `main`, quindi alle callback `atexit`.
- **LETTO NEI LOG** — La presenza di `cleaning up before exit...`, del breakdown e dei dump cache nei log correlati prova che quelle corse hanno percorso la chiusura ordinata.
- **LETTO NEL CODICE** — Gli altri eventi console Windows non sono gestiti e non possono invocare `clean_up()` attraverso questo handler.
- **IPOTESI** — Un autentico `Stop-Process -Force` usa una terminazione forzata del processo, non genera `CTRL_C_EVENT` e non consente a codice utente, distruttori automatici o `atexit` di eseguire.
- **IPOTESI** — Perciò una terminazione realmente forzata non può produrre lo stack KV-ring/`atexit` trovato nei dump; se un comando `Stop-Process -Force` è temporalmente associato a uno di questi eventi, occorre distinguere un Ctrl+C precedente, un fallback del runner o un processo che era già entrato nel teardown.
- **LETTO NEI LOG** — I `.server.log` non registrano il comando esterno che ha causato lo stop; il modo di chiusura non è quindi attribuibile con certezza alla sola coppia timestamp/log.
- **LETTO NEL CODICE** — Il secondo Ctrl+C chiama `exit(1)` a `server.cpp:231-237`: salta i distruttori automatici ma esegue le callback di uscita della CRT; è un cammino diverso dal primo Ctrl+C e dal kill duro.
- **LETTO NEL CODICE** — Il sospetto iniziale “stesso teardown sia con Force sia con Ctrl+C” non è confermato dal codice: soltanto il primo Ctrl+C entra nel teardown ordinato osservato.

## 2. Candidati all'abort del CRT, in ordine di probabilità

### 1. Callback `atexit` del KV ring contro CUDART in unload — molto alta, verificata

- **LETTO NEI LOG** — Evidenza richiesta: 8/8 dump di chiusura hanno `ggml_cuda_kv_ring_dump -> ggml_cuda_set_device -> cudaGetDevice -> driver shutting down -> ggml_cuda_error -> ggml_abort -> abort`.
- **LETTO NEL CODICE** — File/righe: `kv-ring.cu:157-177,257-276`; `ggml-cuda.cu:99-122`; `ggml.c:252-271`.
- **LETTO NEI LOG** — Conferma ulteriore: tutte le corse correlate hanno `LLAMA_KV_RING=1` e terminano a `ggml-cuda.cu:108`.
- **LETTO NEI LOG** — Non serve un altro dump per confermare questa causa sulla build corrente; un dump di una build corretta servirebbe invece a verificare la scomparsa del frame.

### 2. OOM durante `cudaGraphLaunch`, confuso dal bucket con una chiusura — verificato per 2/10 dump, ma non è teardown

- **LETTO NEI LOG** — File/righe: `q_fu6.server.log:487-490` e `q_fu4.server.log:484-487`.
- **LETTO NEI LOG** — I dump PID 19056 e 4336 contengono `out of memory` e un caller a `ggml-cuda.dll+0x1607db`, non `ggml_cuda_kv_ring_dump`.
- **LETTO NEL CODICE** — Il terminale resta `ggml_cuda_error:108 -> ggml_abort -> abort`, motivo per cui offset e bucket UCRT coincidono.
- **LETTO NEI LOG** — Per confermare eventuali altri casi basta classificare ogni nuovo dump per caller CUDA e messaggio, non per bucket UCRT.

### 3. Ordine `backends` prima di `sched` nel `llama_context` — rischio latente basso, non causa dei dump

- **LETTO NEL CODICE** — File/righe: `llama-context.h:356,380-406`; lo scheduler è dichiarato prima della vector backend e viene quindi distrutto dopo di essa.
- **LETTO NEL CODICE** — Lo scheduler conserva puntatori backend grezzi e il worker fino a `ggml_backend_sched_free()` (`ggml-backend.cpp:966-1035,2398-2434`).
- **LETTO NEL CODICE** — Il worker è unito correttamente quando finalmente lo scheduler è distrutto; a server inattivo non riceve nuovi lavori.
- **LETTO NEI LOG** — I dump non passano da worker o scheduler e avvengono più tardi, in `atexit`.
- **IPOTESI** — Probabilità come causa dei crash osservati: inferiore al 5%; resta un ordine fragile da correggere separatamente con `sched.reset()` prima della distruzione dei backend.
- **IPOTESI** — Per confermare un problema proprio di quest'ordine servirebbe un dump con thread worker attivo o un frame scheduler/evento durante la distruzione, assente nei dump esaminati.

### 4. Handler console statico con riferimenti pendenti — rischio latente molto basso, non osservato

- **LETTO NEL CODICE** — `shutdown_handler` è statico a `server.cpp:27`, le lambda catturano oggetti automatici per riferimento a `server.cpp:587-593,597-604,634-637` e l'handler non viene deregistrato o svuotato prima del return.
- **IPOTESI** — Un Ctrl+C tardivo nella stretta finestra successiva alla distruzione degli oggetti potrebbe dereferenziare stato scaduto.
- **LETTO NEI LOG** — Nessun dump mostra il console-handler thread o una violazione di accesso da questa lambda.
- **IPOTESI** — Per confermare servirebbe un dump con stack `console_ctrl_handler -> shutdown_handler` durante il teardown; probabilità per il difetto presente inferiore all'1%.

### 5. Worker cache esperti, doppia free o scrittura dopo distruzione — bassa e contraddetta dallo stack

- **LETTO NEL CODICE** — `cache-esperti.cu:1770-1832` ferma e unisce il servizio prima di liberare risorse e azzera i puntatori/lo stato.
- **LETTO NEL CODICE** — `cache-esperti.cu:1834-1845` stampa i contatori prima della free; questa sequenza compare nei log prima dell'abort tardivo.
- **LETTO NEL CODICE** — Molte free della cache non usano `CUDA_CHECK`; non possono chiamare direttamente `ggml_cuda_error()` sul loro valore di ritorno.
- **LETTO NEI LOG** — Il controllo CUDA che abortisce è invece identificato a `ggml-cuda.cu:115` dentro il successivo callback KV ring.
- **IPOTESI** — Una corruzione precedente non è matematicamente impossibile, ma non è necessaria per spiegare `cudaErrorCudartUnloading` ed è priva di evidenza nei dieci dump.

### 6. `std::thread` joinable, eccezione da distruttore, mutex distrutto, virtuale pura, heap/stack corruption — esclusi per i dump osservati

- **LETTO NEL CODICE** — I thread server, overlap, CPU e cache hanno cammini di stop/join espliciti riportati sopra.
- **LETTO NEL CODICE** — `server-queue.cpp:266-304` contiene due `std::terminate()` per una response queue fermata mentre un HTTP reader aspetta, ma `clean_up()` non chiama `queue_results.terminate()` e nessun dump passa da queste righe.
- **LETTO NEI LOG** — Lo stack osservato contiene una chiamata diretta a `abort` da `ggml_abort`, non `std::terminate`, `_purecall`, `invalid_parameter` o un unwinder C++.
- **LETTO NEI LOG** — `ggml_cuda_kv_ring_dump` ha già acquisito `g_mutex` prima di fallire in CUDA; non sta tentando un `lock_guard` su quel mutex già distrutto.
- **LETTO NEI LOG** — `P9=7` esclude il sottocodice stack-cookie 2; non vi sono `0xc0000374`, frame heap manager o frame `__security_check_cookie`.
- **LETTO NEI LOG** — Per i crash ordinati queste categorie hanno probabilità pratica prossima a zero; restano categorie generiche per futuri dump con stack diverso.

## 3. Che cosa rappresenta `ucrtbase.dll+0xa527e`

- **LETTO NEI LOG** — L'offset è identico in tutti i 40 eventi UCRT interrogati.
- **LETTO NEL CODICE** — Nel binario `ggml-base.dll`, `ggml_abort` chiama l'entry della Import Address Table `abort` a RVA `0x1999`; il return address nei dump è RVA `0x199f`.
- **LETTO NEI LOG** — Il record eccezione è `0xc0000409`, non continuabile, con un parametro uguale a 7.
- **LETTO NEL CODICE** — Il valore 7 è `FAST_FAIL_FATAL_APP_EXIT`; il valore del controllo cookie è 2.
- **LETTO NEL CODICE** — Classificazione verificata: `abort()` della UCRT che termina con fast-fail fatal-app-exit.
- **LETTO NEI LOG** — Classificazioni escluse dallo stack: `std::terminate`, virtuale pura, `invalid_parameter_handler`, `__security_check_cookie` e fast-fail heap corruption.
- **IPOTESI** — `std::terminate` può in generale finire anch'esso in `abort` e quindi nello stesso offset terminale, ma non è presente nella catena di questi dump.
- **LETTO NEI LOG** — Il nome simbolico interno della funzione a `ucrtbase+0xa527e` non è stato risolto con simboli Microsoft locali; non viene inventato.
- **LETTO NEL CODICE** — La semantica è comunque più ristretta del solo nome interno: chiamante importato `abort` più `FAST_FAIL_FATAL_APP_EXIT` verificano `abort/fatal exit`, non una violazione di accesso.

## 4. Crash dump e registro WER

### Stato

- **LETTO NEI LOG** — `C:\Users\imanu\AppData\Local\CrashDumps` esiste e contiene dieci dump `llama-server.exe.<pid>.dmp`.
- **LETTO NEI LOG** — I file attualmente conservati vanno dalle 08:47:30 alle 11:32:10 del 12 agosto; la creazione di PID 10516 ha fatto uscire dalla rotazione il precedente dump più vecchio.
- **LETTO NEI LOG** — Le dimensioni sono 128,37–134,22 MiB; totale conservato 1 358 184 008 byte, cioè 1 295,27 MiB.
- **LETTO NEI LOG** — Otto dump sono chiusure KV-ring/`driver shutting down`; due sono OOM attivi.
- **LETTO NEI LOG** — Tra Event ID 1000 e il successivo Event ID 1001 WER, su undici eventi recenti, trascorrono 2,765–3,611 secondi, media 3,184 secondi.
- **LETTO NEI LOG** — Gli Event ID 1001 indicano anche i dump temporanei WER e la rispettiva cartella `C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_llama-server.exe_...`.

### Registro letto in sola lettura

- **LETTO NEI LOG** — `HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps` esiste, ma al livello radice non espone `DumpFolder`, `DumpType` o `DumpCount`.
- **LETTO NEI LOG** — Sotto HKLM non esiste una chiave `llama-server.exe`; le sole sottochiavi presenti sono dedicate a programmi NVIDIA.
- **LETTO NEI LOG** — Gli scope consueti `HKCU:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps` e le varianti `WOW6432Node` risultano assenti.
- **LETTO NEI LOG** — I dump sono comunque attivi e utilizzabili; il meccanismo che li abilita non è ricavabile dalle chiavi richieste e non viene attribuito senza evidenza.
- **LETTO NEI LOG** — Nessun valore del registro è stato creato o modificato.

### Comando condizionale per abilitarli se in futuro fossero assenti — non eseguito

- **IPOTESI** — Questo comando PowerShell, da console elevata, abilita dump mini per la sola applicazione e ne conserva dieci; `DumpType=1` è preferito qui perché un full dump potrebbe avvicinarsi alle decine di GiB del processo:

```powershell
$werKey = 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\llama-server.exe'
New-Item -Path $werKey -Force | Out-Null
New-ItemProperty -Path $werKey -Name DumpFolder -PropertyType ExpandString -Value '%LOCALAPPDATA%\CrashDumps' -Force | Out-Null
New-ItemProperty -Path $werKey -Name DumpType   -PropertyType DWord -Value 1  -Force | Out-Null
New-ItemProperty -Path $werKey -Name DumpCount  -PropertyType DWord -Value 10 -Force | Out-Null
```

- **LETTO NEI LOG** — Il comando non è necessario nello stato attuale, perché i dump esistono già, e non è stato eseguito.

## 5. Costo del rilascio non ordinato con circa 74 GiB pinned

### Chiusura ordinata che poi abortisce in `atexit`

- **LETTO NEI LOG** — Il breakdown a `q_join.server.log:635-637` è stampato prima della distruzione e mostra ancora 75 388 MiB host del target.
- **LETTO NEL CODICE** — Dopo il return, `server_context` distrugge contesti e modelli; il modello possiede il buffer mappato e il deleter esegue `cudaFreeHost`.
- **LETTO NEI LOG** — Il dump avviene solo dopo questi distruttori, nel dispatcher `atexit`; quindi il crash tardivo osservato non lascia al sistema il rilascio dei 74 304 MiB del modello target.
- **LETTO NEL CODICE** — Il residuo `g_ring.counters` è soltanto `COUNTER_COUNT*sizeof(uint64_t)` allocato a `kv-ring.cu:169-175`, non decine di GiB.
- **LETTO NEI LOG** — Il costo concreto misurato del difetto ordinato è: exit anomalo/BEX64, circa 3,18 secondi di gestione WER, 128–134 MiB scritti per dump, 1,295 GiB trattenuti dalla rotazione e perdita del profilo finale KV ring.
- **IPOTESI** — Non è solo estetica perché altera il codice d'uscita e l'automazione, genera I/O e rumore diagnostico e può nascondere abort reali come gli OOM dietro lo stesso bucket.
- **IPOTESI** — Non emerge però un rischio concreto di perdita permanente dei 74 GiB o di contesto CUDA orfano per il percorso ordinato già catturato.

### OOM attivo, secondo Ctrl+C o kill duro

- **LETTO NEI LOG** — Nei due OOM l'abort avviene durante l'inferenza, prima di `clean_up` e dei distruttori; in questi casi i grandi buffer risultano ancora posseduti dal processo.
- **LETTO NEL CODICE** — Il secondo Ctrl+C chiama `exit(1)` e salta i distruttori automatici; un kill duro li salta per definizione del percorso esterno.
- **IPOTESI** — Alla morte del processo Windows e il driver CUDA recuperano address space, page lock/pinned mappings, handle, allocazioni device e primary context; non è attesa una perdita permanente attraversando più processi.
- **IPOTESI** — Il rischio realistico è transitorio: pressione RAM non paginabile fino al completamento della terminazione, latenza del driver, breve indisponibilità della VRAM/pinned quota, log non flushati e possibile fallimento di una nuova corsa avviata troppo presto.
- **IPOTESI** — Un driver difettoso potrebbe amplificare il costo, ma non vi è nei log esaminati evidenza di reset GPU, TDR, memoria rimasta occupata dopo la morte del processo o riavvio necessario.
- **LETTO NEI LOG** — La risposta complessiva è quindi: difetto operativo reale ma a basso rischio persistente; per la chiusura ordinata il grosso è già liberato, per abort attivo/Force il rilascio è demandato al sistema.

## Correzione proposta per il candidato migliore — descritta, non applicata

- **LETTO NEL CODICE** — La regola violata è localizzata: una callback `atexit` non deve iniziare nuovo lavoro CUDA quando l'ordine di unload tra DLL/UCRT/CUDART non è più controllabile.
- **IPOTESI** — La correzione raccomandata è rimuovere entrambe le registrazioni `atexit` e rendere `dump+free` del KV ring un'operazione idempotente, non fatale, invocata durante la distruzione dell'ultimo `ggml_backend_cuda_context`, quando CUDART è ancora operativo.
- **IPOTESI** — Il contatore degli `ggml_backend_cuda_context` evita di scaricare il ring quando viene distrutto il solo contesto draft mentre il target è ancora vivo.
- **IPOTESI** — Gli errori delle API CUDA nel cleanup devono essere loggati e non passati a `CUDA_CHECK/GGML_ABORT`; in caso di runtime già in unload, il processo deve lasciare il residuo al driver senza trasformare una chiusura in crash.
- **IPOTESI** — Come hardening separato, `llama_context::~llama_context()` dovrebbe fare `sched.reset()` prima che la vector `backends` venga distrutta, così il worker e gli eventi muoiono mentre i backend puntati sono ancora vivi.
- **LETTO NEL CODICE** — Lo sketch seguente è intenzionalmente illustrativo e non è stato applicato:

```diff
diff --git a/ggml/src/ggml-cuda/kv-ring.cu b/ggml/src/ggml-cuda/kv-ring.cu
@@ void ggml_cuda_kv_ring_init(int device) {
     g_ring.initialized = true;
-    atexit(ggml_cuda_kv_ring_free);
-    atexit(ggml_cuda_kv_ring_dump);
+    // Nessuna API CUDA da atexit/DLL detach.
+    // L'ultimo ggml_backend_cuda_context chiama shutdown esplicito.
 }

+void ggml_cuda_kv_ring_shutdown_noexcept() noexcept {
+    std::lock_guard<std::mutex> lock(g_mutex);
+    if (!g_ring.initialized) {
+        return;
+    }
+    // Versione reale: sincronizza/copia/stampa/libera controllando ogni
+    // cudaError_t; durante il cleanup logga gli errori, non usa CUDA_CHECK.
+    kv_ring_dump_and_free_best_effort(g_ring);
+    g_ring = {};
+}

diff --git a/ggml/src/ggml-cuda/ggml-cuda.cu b/ggml/src/ggml-cuda/ggml-cuda.cu
+static std::atomic<unsigned> g_live_cuda_contexts{0};

@@ ggml_backend_cuda_context::~ggml_backend_cuda_context() {
     ggml_cuda_cache_esperti_runtime_libera(cache_esperti);
     cache_esperti = nullptr;
+    if (g_live_cuda_contexts.fetch_sub(1, std::memory_order_acq_rel) == 1) {
+        ggml_cuda_kv_ring_shutdown_noexcept();
+    }
     // poi eventi, stream, cuBLAS e pool
 }

@@ ggml_backend_t ggml_backend_cuda_init(int device) {
     ggml_backend_t cuda_backend = new ggml_backend { /* ... */ };
+    g_live_cuda_contexts.fetch_add(1, std::memory_order_release);
     return cuda_backend;
 }

diff --git a/src/llama-context.cpp b/src/llama-context.cpp
@@ llama_context::~llama_context() {
     ggml_opt_free(opt_ctx);
+    sched.reset(); // stop/join worker ed eventi prima della vector backends
 }
```

- **IPOTESI** — La verifica minima di una futura correzione richiede: una corsa con `LLAMA_KV_RING=1`, primo Ctrl+C, exit code 0, presenza del profilo KV-ring o di un warning non fatale, assenza di Event 1000/1001 e assenza di un nuovo dump.
- **IPOTESI** — Una seconda verifica deve coprire target+draft e ricreazione del contesto, per assicurare che il contatore “ultimo backend” non liberi prematuramente il ring.
- **IPOTESI** — Nessuna di queste verifiche è stata eseguita, in rispetto del divieto di build e avvio.

## Limiti

- **LETTO NEI LOG** — La rotazione conserva dieci dump; gli eventi più vecchi dei tre giorni non hanno più un dump locale disponibile e non possono ricevere la stessa attribuzione di stack individuale.
- **LETTO NEI LOG** — I log delle corse non registrano se lo stop esterno sia Ctrl+C, `Stop-Process` o un fallback; la conclusione sul kill duro deriva dal cammino di codice, non da una marcatura nel log.
- **LETTO NEI LOG** — Gli otto dump ordinati e i log recenti appartengono alla build `P3=6a7ad71c`; build precedenti hanno bucket diversi.
- **LETTO NEL CODICE** — L'assenza di simboli UCRT impedisce di assegnare un nome Microsoft interno a `+0xa527e`; chiamante importato e sottocodice fast-fail rendono però verificata la classificazione `abort/fatal exit`.
- **IPOTESI** — Non si afferma che ogni Event ID 1000 dei tre giorni abbia la causa KV ring: i due OOM dimostrano che il terminale UCRT comune può aggregare cause CUDA diverse.

## Riassunto finale — 15 righe

1. **LETTO NEI LOG** — Otto dump di chiusura mostrano `ggml_cuda_kv_ring_dump -> cudaGetDevice -> driver shutting down -> GGML_ABORT`.
2. **LETTO NEL CODICE** — Il KV ring registra `dump` e `free` con `atexit` in `kv-ring.cu:176-177`.
3. **LETTO NEI LOG** — La callback gira quando CUDART è già in unload; questo è il difetto primario.
4. **LETTO NEL CODICE** — `ggml_abort()` chiama direttamente l'import UCRT `abort()`.
5. **LETTO NEI LOG** — `0xc0000409` ha sottocodice 7, `FAST_FAIL_FATAL_APP_EXIT`, non stack-cookie.
6. **LETTO NEI LOG** — Due dump con lo stesso terminale sono OOM attivi, non crash di chiusura.
7. **LETTO NEL CODICE** — Il primo Ctrl+C termina la queue, ferma HTTP/GC e unisce i thread prima del return.
8. **LETTO NEL CODICE** — Il worker overlap e i pool CPU/cache hanno stop e join espliciti.
9. **LETTO NEL CODICE** — Lo scheduler viene però distrutto dopo i backend: rischio latente, non causa dei dump.
10. **LETTO NEL CODICE** — Solo `CTRL_C_EVENT` è gestito; gli altri eventi console saltano `clean_up`.
11. **IPOTESI** — Un vero `Stop-Process -Force` salta anche `atexit` e non può produrre lo stack osservato.
12. **LETTO NEI LOG** — Sono disponibili dieci dump, 1 295,27 MiB totali; HKLM non ha una regola llama specifica.
13. **LETTO NEI LOG** — Nel crash ordinato i 74 304 MiB mapped sono già passati dai distruttori prima di `atexit`.
14. **IPOTESI** — Il costo è soprattutto exit anomalo, circa 3,18 s WER e I/O; il leak persistente è improbabile.
15. **IPOTESI** — La correzione è togliere CUDA da `atexit` e fare shutdown KV-ring non fatale nell'ultimo contesto CUDA.
