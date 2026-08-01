## Verdetto

**Verificato:** upstream è POSIX-only. Non esiste `src/platform`, non esiste un CMake nativo e non c’è alcun ramo Windows utile. L’unica condizione `_WIN32` upstream è un `#error` che dichiara esplicitamente POSIX-only nel quantizzatore: [gguf-tools/deepseek4-quantize.c:40](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/gguf-tools/deepseek4-quantize.c:40).

Quindi lo strato Windows è sostanzialmente tutto nostro e va portato per intero:

- i 10 file di `src/platform`/`src/win32`;
- le integrazioni Windows dentro `ds4.c`, `ds4_cuda.cu` e `ds4_server.c`;
- il CMake MSVC/nvcc;
- le sostituzioni POSIX necessarie nei nuovi moduli upstream.

La buona notizia è che il fork contiene già un’implementazione Windows matura di file overlapped, mapping, thread, path, RNG, console e Winsock. **Stima:** questo evita circa 3–5 giornate rispetto a rifare lo strato Win32 da zero. Non è però un cherry-pick automatico: upstream ha aggiunto `distributed`, `tp`, `ssd`, `web`, `agent`, `eval`, `layer_pack` e altre unità che il vecchio CMake non conosce.

## Perimetro verificato

- Fork: `646f3beb77732ca286e9bf9f38cf0d63d3ecc78a`
- Upstream: `54b36ed9ba42da31b24f2d1a5feb075c2475dbb1`
- Base comune: `8809b90a1e3247389d7652b565ab6772e036f1ea`
- Lo strato Windows/CMake fu introdotto nel fork da `bac7d8b`, 13 maggio.
- Nessuna compilazione e nessuna modifica eseguita.

Il working tree del fork non è pulito. In particolare [os_file.c](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.c) e [os_file.h](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.h) hanno modifiche non committate relative a `requested_max_chunk`/`os_pread_cancellable_max_chunk`. Le righe sotto si riferiscono al working tree attuale, non soltanto a `646f3be`.

# 1. Inventario del nostro strato di piattaforma

## File dedicati

| File | Funzione Windows |
|---|---|
| [os_file.h:14](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.h:14) | `os_file_t` è `HANDLE`; stato per I/O cancellabile con `OVERLAPPED` |
| [os_file.c:40](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.c:40) | apertura, duplicazione, positioned I/O, timeout e cancellazione |
| [os_mmap.h:8](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_mmap.h:8) | mapping Windows con `HANDLE mapping` |
| [os_mmap.c:43](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_mmap.c:43) | `CreateFileMappingW`/`MapViewOfFile`/`UnmapViewOfFile` |
| [os_thread.h:6](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_thread.h:6) | `SRWLOCK`, `CONDITION_VARIABLE`, `INIT_ONCE`, `HANDLE` |
| [os_thread.c:8](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_thread.c:8) | `_beginthreadex`, join/detach, once, CPU count |
| [os_clock.h:4](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_clock.h:4) | `QueryPerformanceCounter` al posto di `clock_gettime` |
| [os_console.h:6](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_console.h:6) | console UTF-8 e output non bufferizzato |
| [os_path.h:7](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_path.h:7) | UTF-8↔UTF-16, slash, path lunghi drive/UNC |
| [os_random.h:6](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_random.h:6) | `BCryptGenRandom` al posto di `/dev/urandom` |
| [win_dirent.h:4](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/win32/win_dirent.h:4) | `FindFirstFileW`/`FindNextFileW`/`FindClose` |

## Le tre righe richieste

Sono ancora presenti:

- [os_file.c:100](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.c:100): `CreateFileW`; i flag includono `FILE_FLAG_RANDOM_ACCESS | FILE_FLAG_OVERLAPPED` alle righe 105–107.
- [os_file.c:363](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.c:363): se lo stato è ancora `pending`, imposta `errno = EBUSY` e ritorna `-1`.
- [os_file.c:417](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/src/platform/os_file.c:417): `WaitForSingleObject(state->event, wait_ms)`.

## Copertura precisa di `os_file.c`

- Errori Win32 → `errno`: righe 40–68.
- Validità/inizializzazione `HANDLE`: 70–85.
- Apertura UTF-16 overlapped: 88–120.
- `dup` → `DuplicateHandle`: 123–143.
- Riapertura sequenziale via `GetFinalPathNameByHandleW`/`CreateFileW`: 146–180.
- `fopen` → `_wfopen`: 183–201.
- Dimensione → `GetFileSizeEx`: 215–231.
- Stato cancellabile/evento: 234–259.
- Completamento → `GetOverlappedResult`: 262–286.
- Distruzione → `CancelIoEx` e attesa: 289–315.
- Reset/cancel: 317–348.
- `ReadFile` overlapped con timeout: 351–477.
- Controparte POSIX AIO: 478–539.
- Limite chunk, modifica locale corrente: 550–571.
- Lettura posizionale semplice: `SetFilePointerEx`+`ReadFile` contro `pread`, 574–603.
- Loop `os_pread`: 606–668.

## Altre sostituzioni POSIX già implementate nel fork

In [ds4.c](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4.c):

- `_fileno`/`_isatty`: 34–42.
- Page size → `GetSystemInfo`: 557.
- File stamp → `GetFileAttributesExA`: 6544.
- Affinità thread Windows: 11623.
- Instance lock → `CreateFileW`, `LockFileEx`, `SetEndOfFile`, `WriteFile`, `GetTempPathW`: 20578–20643.
- Sostituzione di `fmemopen` con file temporaneo: 22034–22088.
- `mlock` → `VirtualLock` e working-set adjustment: 22591–22672.
- Il modello usa `os_mmap_t`: 1129–1144; chiusura 1353–1360; warm 1373; apertura 1597–1622.

In [ds4_server.c](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_server.c):

- Winsock, `SOCKET`, `closesocket`, `WSAPoll`: 36–75.
- Stato atomico Windows: 86–111.
- `socklen_t`: 147.
- Console control handler: 166.
- PID/localtime: 217 e 225.
- Errori Winsock → `errno`: 232–254.
- `mkdir` → `CreateDirectoryW`: 257–268.
- `fseek` → `_fseeki64`: 282.
- `ftruncate` → `_chsize_s`: 290–306.
- Rename atomico → `MoveFileExW`: 310–323.
- `unlink` → `DeleteFileW`: 327–338.
- `rmdir` → `RemoveDirectoryW`: 343–354.
- `SO_EXCLUSIVEADDRUSE`, `ioctlsocket`, timeout Winsock: 8184–8232.
- `WSAStartup` e cleanup: 8546–8707.

In [ds4_cuda.cu](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/ds4_cuda.cu) il supporto è molto più invasivo:

- `Interlocked*` per gli atomici: 2379–2445.
- File e tracing con `HANDLE`/wide paths: 2859–3588.
- `VirtualAlloc`, `VirtualFree`, `VirtualLock`, working set: 3934–3954, 5230, 7172–13727, 36150–36211.
- Eventi e I/O overlapped: 6911, 9690, 12907–13727, 29902–35884, 39318–45570.
- QPC, `Sleep`, `SwitchToThread`, barriere: 30103–33055, 39071–39261, 40562–42364, 44363, 45570, 49645–50512, 56338–56344.
- Gestione differente del mapping modello: 17969–17983.

Il quantizzatore del fork è ancora dichiaratamente non portato: [deepseek4-quantize.c:38](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/gguf-tools/deepseek4-quantize.c:38).

## Indice completo dei condizionali Windows del fork

Escludendo directory generate `build-*`, ci sono **191 direttive condizionali Windows nel codice compilabile**:

- `ds4.c` — 34, 35, 134, 557, 6544, 11623, 20578, 20595, 22034, 22044, 22072, 22081, 22563, 22591, 22598, 22670.
- `ds4_server.c` — 36, 37, 86, 96, 105, 147, 166, 217, 225, 232, 257, 282, 290, 310, 327, 343, 363, 8184, 8197, 8215, 8232, 8546, 8567, 8580, 8620, 8644, 8707.
- `ds4_cuda.cu` — 24, 25, 1615, 2126, 2317, 2379, 2399, 2417, 2428, 2444, 2859, 2870, 2923, 3160, 3345, 3455, 3934, 3954, 5136, 5230, 6453, 6508, 6911, 7172, 7182, 7942, 8047, 8085, 9690, 10203, 10287, 10807, 10892, 10929, 10989, 11067, 11273, 11301, 11368, 12154, 12163, 12663, 12907, 13257, 13269, 13411, 13430, 13440, 13552, 13577, 13592, 13647, 13669, 13727, 17969, 17983, 29902, 30103, 30658, 31923, 32061, 32096, 32241, 32288, 32622, 32905, 33054, 35883, 36150, 36393, 39071, 39087, 39238, 39261, 39318, 39692, 40562, 40956, 41120, 41242, 41371, 41412, 41532, 42364, 42658, 43182, 44363, 44381, 45194, 45218, 45354, 45570, 46099, 47928, 49645, 50270, 50276, 50506, 50512, 56338, 56344.
- `src/platform/os_file.c` — 9, 40, 72, 81, 94, 129, 157, 184, 206, 220, 237, 251, 264, 291, 318, 330, 368, 558, 566, 582, 612.
- `src/platform/os_file.h` — 7, 8, 15, 22.
- `src/platform/os_mmap.c` — 8, 18, 43, 78, 93, 105.
- `src/platform/os_mmap.h` — 12.
- `src/platform/os_thread.c` — 1, 8.
- `src/platform/os_thread.h` — 6, 7.
- `src/platform/os_clock.h` — 4, 5.
- `src/platform/os_console.h` — 6, 7.
- `src/platform/os_path.h` — 7, 8.
- `src/platform/os_random.h` — 6, 7.
- `src/win32/win_dirent.h` — 4, 8.
- `gguf-tools/deepseek4-quantize.c` — 38.

In [docs/windows_cuda_port.md](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/docs/windows_cuda_port.md) compaiono inoltre nove `#ifdef` dentro esempi/documentazione: 133, 175, 234, 256, 355, 404, 440, 521, 548. Non sono direttive compilate.

Esistono anche probe Windows-only:

- [tools/os_layer_test.c:6](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/tools/os_layer_test.c:6), con test di file >4,5 GiB, mmap, pread concorrente, RNG e clock alle righe 71–113.
- [tools/mapviewoffile_register_probe_win.cpp:184](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/tools/mapviewoffile_register_probe_win.cpp:184).
- `g17_arena_probe.cu` e `g17_segmented_arena_probe.cu`, Windows-only.

# 2. Cosa ha upstream

## Strato di piattaforma

**Verificato: non ne ha uno.**

- Nessuna directory `src/platform`.
- Nessun `os_file`, `os_mmap`, `os_thread`, `os_path`, `os_clock`.
- Nessun CMake.
- Nessuna implementazione Windows in `ds4.c`, `ds4_cuda.cu`, `ds4_server.c` o nei nuovi moduli.
- Unica direttiva `_WIN32`: l’esplicito errore POSIX-only del quantizzatore.

## Apertura e lettura del modello

Upstream mantiene un file descriptor POSIX crudo:

- Include diretti `fcntl.h`, `pthread.h`, `sys/file.h`, `sys/mman.h`, `unistd.h`: [ds4.c:18](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:18)–41.
- `ds4_model` contiene `int fd`: [ds4.c:2071](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2071)–2085.
- Chiusura con `munmap` e `close`: [ds4.c:2306](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2306)–2313.
- Apertura con `open(path, O_RDONLY)`: [ds4.c:2433](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2433).
- Dimensione con `fstat`: 2437.
- Mapping con `mmap(..., MAP_SHARED/MAP_PRIVATE, fd, 0)`: [ds4.c:2452](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2452)–2458.
- Metadati e tensor data restano puntatori/offset nel mapping: 2340 e 2370.
- L’API GPU espone direttamente il file descriptor: [ds4_gpu.h:95](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_gpu.h:95)–100.
- Il descriptor viene consegnato al backend alle righe [ds4.c:55961](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:55961), 56295, 56312 e 56321.

Questa è una differenza strutturale: non basta implementare `open` su Windows. Va riportata anche l’ABI `os_file_t`/`os_mmap_t` attraverso modello, core e backend CUDA.

# 3. Sistema di build

## CMake del fork

[CMakeLists.txt:1](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/CMakeLists.txt:1) configura C, C++ e CUDA, C11/C++17, `find_package(CUDAToolkit)` e architettura CUDA configurabile.

Costruisce:

- `ds4_platform`: 14–32.
- `ds4_cuda`: 34–40.
- `ds4_bake`: 42–43.
- libreria statica `ds4`: 45–49.
- `ds4-server`: 51–57.
- `moe_gate_bench`: 59–65.
- `iq1_s_bench`: 67–73.
- `q1_0_bench`: 75–81.
- `inspect`: 83–89.
- `ppl`: 116–122.
- `ds4_bake_test`: [tests/CMakeLists.txt:12](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-p4a/tests/CMakeLists.txt:12).

Su Windows:

- definisce `_WIN32_WINNT=0x0601`;
- collega `bcrypt` e `ws2_32`;
- usa opzioni MSVC/nvcc;
- **non costruisce intenzionalmente il CLI `ds4`**, righe 106–114;
- non costruisce `ds4_test`, escluso su Windows in `tests/CMakeLists.txt:1–10`.

`build-native/CMakeCache.txt` mostra una configurazione Ninja con `cl.exe`, `nvcc` e architettura CUDA 452. È solo evidenza di configurazione preesistente: non ho eseguito build.

## Makefile upstream

Il Makefile upstream costruisce più superficie applicativa:

- core include `ds4_distributed.o`, `ds4_tp.o`, `ds4_ssd.o`, `ds4_cuda.o`, `ds4_layer_pack.o`: [Makefile:38](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/Makefile:38)–39.
- target principali: 50.
- `cuda-spark`: [Makefile:116](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/Makefile:116)–118.
- `cuda-generic`: 119–120.
- test shell CUDA: 122–128.
- ROCm: 130–137.
- eseguibili `ds4`, `ds4-server`, `ds4-bench`, `ds4-eval`, `ds4-agent`: 139–152.
- regole per i nuovi moduli: 168–205.
- test: 258–400.

Rispetto al CMake del fork, upstream aggiunge almeno:

- `ds4_distributed.c`
- `ds4_tp.c`
- `ds4_ssd.c`
- `ds4_layer_pack.c`
- `ds4_help.c`
- `ds4_kvstore.c`
- `ds4_gpu_args.c`
- `ds4_web.c`
- `ds4_agent.c`
- `ds4_eval.c`

Viceversa, il CMake del fork ha target specifici assenti dal Makefile upstream: `moe_gate_bench`, `iq1_s_bench`, `q1_0_bench`, `inspect`, `ppl` e `ds4_bake_test`.

## Usabilità del Makefile su Windows

**Verificato: non è usabile nativamente con MSVC/nvcc senza riscrittura.**

Motivi concreti:

- `uname`: riga 2.
- Flag GCC/Clang: 13–17.
- `-pthread`: 31–47.
- Path `/usr/local/cuda`: 31–47.
- Librerie con path `sbsa-linux`.
- Condizionali e comandi shell POSIX.
- `rm -f` nel target `clean`: 404–405.
- Il target `all` non-Darwin non equivale direttamente a una build Windows: riga 101.

La strada corretta per Windows nativo è estendere/sostituire con CMake, includendo il nuovo grafo sorgenti upstream. Il CMake attuale del fork non è sufficiente senza aggiornamento.

# 4. Trappole upstream

Classificazione:

- **Alta:** cambia ABI, modello di I/O/thread/processo o blocca il target minimo.
- **Media:** adattamento localizzato ma non una semplice macro.
- **Bassa:** wrapper meccanico, hint eliminabile o backend non Windows.

## `pread` / `pwrite`

`pwrite`: **zero occorrenze**.

`pread` reali:

- [ds4_cuda.cu:1550](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:1550) — lettura staged CUDA del modello. **Alta**.
- [ds4.c:18349](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:18349) — page-in/streaming dal modello. **Alta**.
- [ds4.c:47573](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:47573) — lettura dell’instance-lock. **Media**, il fork ha già la sostituzione.
- [ds4_metal.m:10848](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_metal.m:10848) — **bassa per il target CUDA Windows**, alta per un eventuale Metal port.
- [rocm/ds4_rocm_runtime.cuh:5393](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/rocm/ds4_rocm_runtime.cuh:5393) — fuori dal target CUDA Windows.

## `mmap` / `munmap` / `madvise`

Core:

- [ds4.c:2310](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2310) `munmap` — **alta**.
- [ds4.c:2453](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2453) `mmap` del modello — **alta**.
- `posix_madvise`: 2328, 3067, 17547, 18309, 54260 — **bassa/media**; su Windows il fork già tratta warm/cold come no-op.

Altri moduli:

- [ds4_ssd.c:149](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_ssd.c:149), 190, 207 — mapping anonimo e lock di memoria per simulazione SSD. **Media**.
- [ds4_cuda.cu:1468](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:1468) — solo `posix_madvise`, **bassa**.
- [ds4_metal.m:11466](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_metal.m:11466) — fuori dal target.
- [rocm/ds4_rocm_runtime.cuh:5304](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/rocm/ds4_rocm_runtime.cuh:5304) — fuori dal target.

## `open` / `O_DIRECT`

- [ds4.c:2433](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:2433) — modello, **alta**.
- [ds4.c:47563](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:47563) — instance lock, **media**.
- [ds4_cuda.cu:3747](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:3747) — reopen diretto; `O_DIRECT` alle righe 1565, 3743, 3747. È protetto da `__linux__ && O_DIRECT`, quindi **non è di per sé un blocker Windows**.
- [ds4_server.c:97](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_server.c:97) — `/dev/urandom`, **bassa**, già coperto da `BCryptGenRandom`.
- [ds4_agent.c:7606](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_agent.c:7606) — `/dev/null` nel processo figlio, **alta se si costruisce agent**.
- [ds4_web.c:321](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_web.c:321), 1046 — RNG/process launch POSIX, **alta se si costruisce web**.
- ROCm: 1952, 5408, 6257, 6261; fuori dal target CUDA.

## `pthread_*`

Sono **848 riferimenti diretti** nei sorgenti di produzione:

| File | Riferimenti | Impatto |
|---|---:|---|
| `ds4.c` | 90 | **Alta**, core |
| `ds4_distributed.c` | 233 | **Alta** se incluso, ed è in `CORE_OBJS` |
| `ds4_server.c` | 244 | **Alta**, server |
| `ds4_tp.c` | 11 | **Alta** perché incluso nel core upstream |
| `ds4_agent.c` | 135 | Alta solo se si costruisce agent |
| `ds4_eval.c` | 10 | Media/opzionale |
| `ds4_metal.m` | 86 | Fuori dal target |
| ROCm runtime | 39 | Fuori dal target |

Per il minimo Windows CUDA server, `ds4.c + distributed + server + tp` contengono **578 riferimenti**. Non sono tutti 578 interventi distinti, perché molte chiamate possono essere sostituite tramite typedef/wrapper, ma mostrano che `os_thread` deve diventare l’API comune, non una correzione locale.

Linee esatte del sottoinsieme Windows/CUDA obbligatorio:

- `ds4.c`: 953, 1769–1772, 1793, 1795, 1798, 1807, 1819, 1822, 1824, 1833, 1850–1852, 1861, 1870, 1873–1882, 1896, 1902, 1907, 1915, 1917, 1919, 3780, 17601, 17604, 17859, 17935, 17960, 18671, 18690, 18699, 18720, 18727, 18885, 18904, 18913, 18934, 18941, 20973–21096, 21120–21355.
- `ds4_distributed.c`: 241, 274, 292–324, 389, 426–461, 1883–2336, 3120–3338, 3583–3749, 4096–4320, 5447–5830, 6283–6434, 6571–7151, 7445–7965.
- `ds4_server.c`: 8133–8715, 8753, 8998–9054, 9287–9629, 9832–9941, 10240–10950, 11612–11614, 12087–13129, 15418–16015, 16709–16823.
- `ds4_tp.c`: 149, 724, 922, 969, 1018, 1023, 1036, 1043, 1057, 1064, 1070.

## `usleep`, `nanosleep`, `clock_gettime`

Tutte le occorrenze di produzione:

- `ds4.c`: [1192](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:1192) `clock_gettime`; 1666 `nanosleep`.
- `ds4_cuda.cu`: [1303](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_cuda.cu:1303) `clock_gettime`.
- `ds4_server.c`: 8129, 10880 `clock_gettime`.
- `ds4_distributed.c`: 549 `clock_gettime`; 1450 `nanosleep`.
- `ds4_tp.c`: 192 `clock_gettime`; 323 `usleep`.
- `ds4_kvstore.c`: 136 `clock_gettime`.
- `ds4_agent.c`: 546, 1283 `clock_gettime`; 4717 `nanosleep`; 7878 `usleep`.
- `ds4_eval.c`: 1419, 1428, 1430 `clock_gettime`; 1850, 3612, 3959 `usleep`; 4074 `nanosleep`.
- `ds4_cli.c`: 168 `nanosleep`; 303 `clock_gettime`.
- `ds4_bench.c`: 65 `clock_gettime`; 528 `nanosleep`.
- `ds4_web.c`: 127 `clock_gettime`; 146 `usleep`.
- `ds4_metal.m`: 1226 `clock_gettime`; 8452 `usleep`.
- ROCm runtime: 5237 `clock_gettime`.

**Invasività bassa/media:** il fork ha già `os_clock`, ma manca un wrapper comune completo per sleep/deadline. Sono comunque errori di compilazione diretti sotto MSVC se non sostituiti.

## `dlopen`

Soltanto [ds4_tp.c:585](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_tp.c:585)–591: due `dlopen`, `dlsym` e `dlclose` per `librdma.dylib`.

Il codice è dietro `DS4_TP_HAVE_VERBS`, definito nel percorso Apple quando gli header richiesti esistono. **Bassa per Windows CUDA:** va lasciato escluso. Un eventuale port richiederebbe `LoadLibrary`/`GetProcAddress`.

## Path POSIX hardcoded

Occorrenze runtime rilevanti:

- [ds4.c:47486](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4.c:47486): `/proc/self/oom_score_adj`, Linux-specific; **bassa**, va escluso.
- `ds4.c:47561`: `/tmp/ds4.lock`; **media/alta**, il fork ha già `GetTempPathW`.
- `ds4.c:49579`: payload/sessione temporanea; **media**.
- `ds4_cuda.cu:3746`: `/proc/self/fd/%d`; Linux/O_DIRECT guarded, **bassa**.
- [ds4_kvstore.c:340](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_kvstore.c:340)–365: join e scansione directory usando sempre `'/'`; **media**, soprattutto per drive/UNC e `mkdir`.
- [ds4_distributed.c:6864](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_distributed.c:6864)–6870: `/tmp` e `mkstemp`; **media**.
- `ds4_agent.c`: slash/cache directory 3983–4002; `/tmp` 7295 e 7577; `/dev/null` 7606; `/bin/sh` 7619. **Alta** per il target agent, perché si combina con `fork`/`exec`.
- `ds4_web.c`: join directory 161–164; `/dev/urandom` 321; path Chrome POSIX 967–978; `/usr/bin/open` 1032/1054; `/dev/null` 1046; `%s/.ds4/browser` 1331. **Alta** per web.
- `ds4_tp.c:585`: `/usr/lib/librdma.dylib`, feature-gated.
- `gguf-tools/deepseek4-quantize.c:108–117`: join con `'/'`; tool attualmente POSIX-only.
- ROCm 6260: `/proc/self/fd/%d`; fuori dal target.

## Altri blocker non presenti nell’elenco iniziale

I nuovi moduli includono direttamente header POSIX:

- [ds4_distributed.c:18](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_distributed.c:18)–38: socket, networking, pthread.
- [ds4_server.c:16](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_server.c:16)–40.
- [ds4_tp.c:12](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_tp.c:12)–28.
- [ds4_agent.c:9](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_agent.c:9)–31: `dirent`, `fnmatch`, `poll`, `regex`, `signal`, `ioctl`, `wait`, processi.
- [ds4_web.c:3](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_web.c:3)–23: networking e process launch.
- [ds4_kvstore.c:12](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_kvstore.c:12)–23.
- [ds4_ssd.c:9](C:/Users/imanu/source/repos/moe-aggressive-commit/ds4-port/ds4_ssd.c:9)–10.

Particolarmente invasivi:

- Instance locking con `flock`, `ftruncate`, `dprintf`: `ds4.c:47563–47598`.
- `fork`/`exec` dell’agent: `ds4_agent.c:7577–7624`.
- Browser launcher con `fork`/`exec`: `ds4_web.c:1039–1060`.
- Socket POSIX in server, distributed, TP e web: richiedono Winsock; il fork copre il vecchio server, non questi nuovi moduli.

# 5. Ordine di lavoro

## Ordine tecnico verificato dalle dipendenze

1. **Definire il target minimo della tranche.**  
   Decidere esplicitamente se `distributed`, `tp`, `agent`, `eval` e `web` sono esclusi/stubbati per il primo `ds4-server.exe` single-GPU. Upstream oggi mette `distributed` e `tp` in `CORE_OBJS`, quindi non spariscono da soli.

2. **Portare lo strato di piattaforma completo.**  
   Prima `os_file`, `os_mmap`, `os_thread`, `os_clock`, `os_path`, `os_random`, `os_console`, `win_dirent`. Tutto il resto dipende da questi tipi e primitive.

3. **Portare l’ABI modello/file nel core e nel backend GPU.**  
   Sostituire `int fd`/mapping crudo upstream con `os_file_t`/`os_mmap_t`; riconciliare `ds4_gpu_set_model_fd*` con l’API del fork. Questo è il primo cambiamento strutturale indispensabile.

4. **Aggiornare CMake al nuovo grafo upstream.**  
   MSVC/nvcc, architetture, librerie `ws2_32`/`bcrypt`, nuovi sorgenti e feature gates. Il Makefile non è una base Windows valida.

5. **Portare thread, clock e sincronizzazione del percorso minimo.**  
   Prima `ds4.c` e `ds4_cuda.cu`; poi server. Usare `os_thread` sistematicamente.

6. **Portare il server Winsock e filesystem.**  
   Riapplicare le sostituzioni già presenti nel fork alla versione upstream del server.

7. **Integrare l’I/O CUDA overlapped/cancellabile.**  
   `ReadFile` overlapped, timeout, cancel, chunking e lifetime dell’evento. È codice già disponibile, ma va applicato dopo aver stabilizzato tipi e ABI.

8. **Solo dopo:** distributed/TP reali, agent, web, eval, quantizzatore e parità completa dei test.

## Stime, non fatti verificati

- **Risparmio dal riuso del fork:** circa **3–5 giornate** rispetto a un port Windows greenfield.
- **7–10 giornate “compila e linka”**: plausibile ma stretta soltanto per un target deliberatamente minimo, single-GPU CUDA, con `distributed`/`tp` disabilitati o stubbati e senza agent/web/eval.
- Considerando la divergenza upstream, pianificherei più prudentemente **8–12 giornate** per quel minimo.
- Se “compila e linka” significa parità con tutti gli eseguibili e moduli del Makefile upstream, la stima sale a circa **12–18 giornate**, prima della validazione funzionale.
- Le **18–25 giornate** complessive per “compila e gira single-GPU” restano credibili solo mantenendo ristretto il primo perimetro. Non coprono comodamente la piena parità di distributed/TP/agent/web.

In sintesi: il primo blocco non è soltanto “aggiungere CMake”. È **portare lo strato Win32 del fork, riallineare l’ABI file/mmap del modello e togliere dal grafo iniziale i nuovi moduli POSIX non necessari al single-GPU**. Senza queste tre decisioni, la tranche 7–10 giorni non è pianificabile.

Codex session ID: 019fbc41-c24a-7a20-989a-2c999a6ed8d1
Resume in Codex: codex resume 019fbc41-c24a-7a20-989a-2c999a6ed8d1
