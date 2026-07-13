# DS4 Windows / WDDM / GB10 Runtime Alternatives - 2026-07-13

Report consolidato per la task separata su porting DS4/Dwarf/SPEX e alternative
hardware/runtime per superare il tetto WDDM della memoria host pinned.

Regola di lettura:

- **MISURA LOCALE**: osservato su questa macchina o da log locali.
- **FONTE**: repository, PR, issue, documentazione ufficiale o README esterno.
- **IPOTESI**: deduzione tecnica da fonti/misure, da validare prima di trattarla
  come fatto operativo.

## Sintesi

Il percorso piu corto verso l'obiettivo tecnico ("maschera dinamica per turno"
circa 50 GiB e fetch RAM senza pedaggio `pread + staging + sync`, target 5-8
t/s) non e Windows/WDDM sulla macchina attuale.

- **MISURA LOCALE**: in WSL2 `cudaHostAlloc` arriva a 31 GiB e fallisce il
  target 50 GiB al blocco successivo. La copia H2D verificata dalla arena
  trattenuta sta intorno a 3.0 GiB/s sui test grandi.
- **FONTE**: Windows WDDM gestisce la memoria GPU tramite VidMm e impone una
  policy per cui la GPU puo usare al massimo meta della DRAM fisica come shared
  memory in un dato istante. Su 64 GiB fisici questo rende il tetto di circa
  32 GiB coerente con la misura locale.
- **FONTE**: NVIDIA documenta che su Windows nativo e WSL il supporto Unified
  Memory e limitato e la memoria pinned di sistema disponibile alle
  applicazioni e limitata.
- **MISURA LOCALE**: il probe CUDA nativo Windows e stato revisionato lato ABI,
  compilato e poi eseguito a GPU/WSL liberi. La matrice single 24/28/30/31 GiB
  passa; 32 GiB fallisce con `CUDA_ERROR_OUT_OF_MEMORY` da
  `cuMemHostAlloc(arena)`. Il test blocks 32 GiB step 1 GiB trattiene 31 GiB e
  fallisce sul blocco successivo. Quindi Windows nativo conserva il tetto
  pratico ~31 GiB.
- **FONTE**: il fork Windows CUDA concreto esiste:
  [`hawkli-1994/ds4-win:codex/windows-cuda`](https://github.com/hawkli-1994/ds4-win/tree/codex/windows-cuda),
  PR [`hawkli-1994/ds4-win#2`](https://github.com/hawkli-1994/ds4-win/pull/2),
  workflow [`Windows CUDA` run 25801727530](https://github.com/hawkli-1994/ds4-win/actions/runs/25801727530)
  verde. Stato reale: compila `ds4_server.exe`, ma e una PR draft,
  conflittuale e non risulta provata con modello reale.
- **FONTE**: per eliminare davvero staging/pin su NVIDIA, la strada piu pulita
  e un sistema Linux con HMM/ATS, in particolare DGX Spark/GB10. La PR upstream
  [`antirez/ds4#158`](https://github.com/antirez/ds4/pull/158) corregge proprio
  il path HMM su GB10/NVLink-C2C e riporta 13.81 t/s su DGX Spark con modello
  80.76 GiB, usando file page cache reclaimable invece di copie device-private.

Raccomandazione operativa:

1. Considerare chiusa la pista "Windows nativo aggira WDDM": su questa macchina
   non aggira il tetto host pinned.
2. Per arrivare piu in fretta a 50 GiB dinamici, spostare la sperimentazione su
   Linux bare metal/dual boot o pod Linux, dove non c'e il budget WDDM.
3. Se e accettabile cambiare hardware, DGX Spark/GB10 e la strada architetturale
   migliore: 128 GB unified coherent memory e path HMM/ATS gia identificato in
   DS4.

## Stato locale e vincoli

Hardware dichiarato:

- Ryzen 7 5800X
- ASUS PRIME B550M-A WIFI II
- 64 GB DDR4
- RTX 3060 12 GB

Repo:

- Repo report: `C:\Users\imanu\source\repos\moe-aggressive-commit`
- Area test DS4/probe: `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy`
- Sessione storica recuperata:
  `C:\Users\imanu\.codex\sessions\2026\07\07\rollout-2026-07-07T11-30-08-019f3be9-d8c0-7c51-89bf-1e5505b83d0e.jsonl`

Stato worktree:

- **MISURA LOCALE**: `moe-aggressive-commit` era su
  `cascade-memory/harness...origin/cascade-memory/harness`, con un file
  untracked preesistente `1{print`.
- **MISURA LOCALE**: `reap-loop` era su
  `spex-predictive-mask-study-2026-07-12...origin/spex-predictive-mask-study-2026-07-12`
  con molti artefatti untracked in `runs/ds4/20260712_v2_zerocopy`.
- Non ho creato cloni duplicati dei repo.
- Non ho interrotto processi DS4.
- Non ho committato.

## Coordinamento risorse tra task

Aggiornamento coordinamento 2026-07-13:

- Questa task e stata rinominata **"Porting DS4 / DGX Spark - NO GPU heavy"**.
- Ho notificato la task principale `DS4 study`
  (`019f3be9-d8c0-7c51-89bf-1e5505b83d0e`) che non usero GPU/WSL, non fermero
  `ds4-server`, non liberero memoria e non eseguiro probe finche non dichiara
  esplicitamente le risorse libere.
- Ho notificato le task parallele owner di file in `reap-loop`:
  - `Catalog DS4 runtime levers`: non tocco `docs/DS4_LEVE_CATALOG.md`.
  - `Prepare controlled A/B harness`: non tocco
    `runs/ds4/20260712_v2_zerocopy/scripts/run_0050_controlled_ab.sh` ne
    `AB_PROTOCOL.md`.
  - `Design patch 0051 arena`: non tocco
    `docs/DESIGN_0051_DYNAMIC_ARENA.md`.
- Il lock operativo corrente e:
  - **GPU + WSL + server DS4**: assegnati alla task principale.
  - **Questa task**: solo ricerca/report docs-only e comandi leggeri di
    ispezione; nessun test CUDA pesante.
  - **Matrice Windows nativa 24/28/30/31/32 GiB**: eseguita dopo rilascio
    esplicito GPU/WSL; 31 GiB PASS, 32 GiB FAIL con
    `CUDA_ERROR_OUT_OF_MEMORY`.

## Port Windows CUDA recuperato dalla sessione storica

La richiesta prioritaria era recuperare il port/fork Windows nativo gia trovato
in passato, non fermarsi a "si puo fare".

Risultato:

- **FONTE/MISURA LOCALE SU SESSIONE**: nella sessione storica, intorno alla
  linea 30997, era stato identificato
  [`hawkli-1994/ds4-win`](https://github.com/hawkli-1994/ds4-win), branch
  [`codex/windows-cuda`](https://github.com/hawkli-1994/ds4-win/tree/codex/windows-cuda).
- **FONTE**: PR corrente:
  [`[codex] Implement Windows CUDA port`](https://github.com/hawkli-1994/ds4-win/pull/2).
- **FONTE**: ultimo commit del branch:
  [`2fba7fe4d77b4a917ccca353d2d898c4abe9a817`](https://github.com/hawkli-1994/ds4-win/commit/2fba7fe4d77b4a917ccca353d2d898c4abe9a817),
  "Improve CUDA model allocation failure diagnostics".
- **FONTE**: workflow CI:
  [`Windows CUDA` run 25801727530](https://github.com/hawkli-1994/ds4-win/actions/runs/25801727530),
  job [`Build ds4_server.exe`](https://github.com/hawkli-1994/ds4-win/actions/runs/25801727530/job/75793336535),
  conclusione success, completato il 2026-05-13.
- **FONTE**: la PR e `OPEN`, `draft`, `mergeable=CONFLICTING`,
  `mergeStateStatus=DIRTY`.

Contenuto tecnico del port:

- CMake/MSVC per Windows CUDA.
- Link Winsock/BCrypt.
- Astrazione file/mmap/thread/clock/random/path in `src/platform`.
- Modifiche a `ds4.c`, `ds4_cuda.cu`, `ds4_server.c`, `ds4_gpu.h`.
- Workflow `.github/workflows/windows-cuda.yml` che installa CUDA 12.6.3 e
  produce `ds4_server.exe`.

Stato reale:

- **FONTE**: la CI compila.
- **FONTE/MISURA DA SESSIONE**: il PR body dichiara validazioni Linux (`make cpu`,
  `./ds4-server --help`, `git diff --check`) e dice che il build
  Windows/MSVC/CUDA non era stato eseguito localmente dal suo autore in quella
  fase.
- **IPOTESI**: e una base valida per non riscrivere lo strato Win32, ma non e
  una soluzione pronta per l'obiettivo memoria. Va rebaseato su upstream
  corrente e provato con il modello reale.

## Probe CUDA nativo Windows

File ricevuti:

- `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\tools\cuda_pinned_arena_probe_win.cpp`
- `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\tools\run_pinned_arena_probe_win.ps1`

### Revisione ABI manuale CUDA

**MISURA LOCALE**: il sorgente dichiara manualmente un sottoinsieme della CUDA
Driver API e carica `System32\nvcuda.dll` con `LoadLibraryW/GetProcAddress`.

Controlli buoni nel sorgente:

- `_WIN64` obbligatorio.
- `CUDAAPI __stdcall`.
- `CUresult=int`, `CUdevice=int`.
- `CUcontext` e `CUstream` come puntatori opachi.
- `CUdeviceptr_v1=unsigned int`, `CUdeviceptr_v2=unsigned long long`.
- `static_assert` su size x64: puntatori 8 byte, `CUresult` e `CUdevice` 4 byte,
  `CUdeviceptr_v2` 8 byte.
- Risoluzione coerente della famiglia v2:
  `cuMemAlloc_v2`, `cuMemFree_v2`, `cuMemcpyHtoDAsync_v2`, `cuMemcpyDtoH_v2`.
  Se la famiglia v2 non e completa, fallback legacy v1 all-or-nothing.
- `cuCtxCreate_v2` preferito a `cuCtxCreate`; `cuCtxDestroy_v2` preferito.
- `cuStreamDestroy_v2` preferito.

**FONTE**: la documentazione CUDA Driver API definisce `CUcontext` come puntatore
opaco e `CUdevice` come `int`; per `CUdeviceptr` dichiara un intero unsigned con
dimensione uguale alla dimensione del puntatore sul target:
<https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__TYPES.html>.

**FONTE**: `cuMemHostRegister` registra una memoria host per CUDA, page-locka e
mappa l'intervallo, ma NVIDIA avverte che page-lockare troppa memoria degrada il
sistema e va usato con parsimonia:
<https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__MEM.html>.

**MISURA LOCALE**: su `C:\Windows\System32\nvcuda.dll` locale sono esportati:

- `cuCtxCreate`, `cuCtxCreate_v2`, `cuCtxCreate_v3`, `cuCtxCreate_v4`
- `cuCtxDestroy`, `cuCtxDestroy_v2`
- `cuMemAlloc`, `cuMemAlloc_v2`, `cuMemFree`, `cuMemFree_v2`
- `cuMemcpyHtoDAsync`, `cuMemcpyHtoDAsync_v2`
- `cuMemcpyDtoH`, `cuMemcpyDtoH_v2`
- `cuMemHostAlloc`, `cuMemFreeHost`
- `cuStreamDestroy`, `cuStreamDestroy_v2`

Conclusione ABI:

- **MISURA LOCALE**: su questa macchina il probe usera
  `context_v2;device_memory_v2;stream_destroy_v2`.
- **IPOTESI**: l'ABI manuale e ragionevole per x64 e coerente con gli export
  reali. Il warning MinGW su cast `FARPROC` -> function pointer e atteso per
  `GetProcAddress`, non indica mismatch di firma da solo.

### Build

Tentativo MSVC:

- **MISURA LOCALE**: `cl.exe` trovato in Visual Studio 2022 Community, ma
  l'installazione locale manca di header/lib runtime (`excpt.h`,
  `vcruntime.h`, `msvcrt.lib`). Il runner PowerShell fallisce con:
  `windows.h(171): fatal error C1083: cannot open include file: 'excpt.h'`.
- Artefatti falliti:
  `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arena_probe_win\probe_20260713_061235_win_blocks_0p25g.build.stdout.txt`

Build riuscito via MinGW cross-compiler da WSL:

```text
x86_64-w64-mingw32-g++ -std=c++17 -O2 -Wall -Wextra -static -static-libgcc -static-libstdc++ -o '/mnt/c/Users/imanu/source/repos/reap-loop/runs/ds4/20260712_v2_zerocopy/arena_probe_win/probe_20260713_061915_win_mingw.exe' '/mnt/c/Users/imanu/source/repos/reap-loop/runs/ds4/20260712_v2_zerocopy/tools/cuda_pinned_arena_probe_win.cpp'
```

Artefatti:

- Eseguibile:
  `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arena_probe_win\probe_20260713_061915_win_mingw.exe`
- Comando:
  `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arena_probe_win\probe_20260713_061915_win_mingw.build.command.txt`
- Build stderr:
  `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arena_probe_win\probe_20260713_061915_win_mingw.build.stderr.txt`

### Matrice Windows nativa 24/28/30/31/32 GiB

Primo stato 2026-07-13 mattina:

- **MISURA LOCALE**: al primo controllo Windows aveva circa 1.04 GiB di RAM
  fisica libera e la GPU era quasi tutta occupata da un `ds4-server` WSL attivo.
- Decisione corretta in quel momento: nessun probe lanciato per non interferire
  con la task principale.

Esecuzione dopo rilascio GPU/WSL:

- **MISURA LOCALE**: prima della matrice, RTX 3060 libera:
  `NVIDIA GeForce RTX 3060, driver 596.21, 562 MiB / 12288 MiB, util 0%`.
- **MISURA LOCALE**: RAM fisica disponibile via
  `Microsoft.VisualBasic.Devices.ComputerInfo`: 52.65 GiB disponibili su
  63.89 GiB totali.
- **MISURA LOCALE**: nessun processo `ds4-server`, `wsl`, `wslhost` o
  `vmmemWSL` visibile da `Get-Process`.

Comando base usato per la matrice single:

```powershell
C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arena_probe_win\probe_20260713_061915_win_mingw.exe --mode single --target-gib <N> --step-gib 1 --staging-mib 16 --reserve-gib 8 --device 0
```

Log salvati in:

```text
C:\Users\imanu\Documents\Codex\2026-07-13\studio-separato-porting-ds4-dwarf-spex\work\native_win_probe_20260713_090803
```

Risultati:

| Log | Mode | Target | Esito | Allocato | Errore | Note |
| --- | --- | ---: | --- | ---: | --- | --- |
| `probe_win_single_24g.log` | single | 24 GiB | PASS | 24 GiB | - | arena retained, materializzazione per pagina, staging 16 MiB, DMA/checksum OK |
| `probe_win_single_28g.log` | single | 28 GiB | PASS | 28 GiB | - | target raggiunto |
| `probe_win_single_30g.log` | single | 30 GiB | PASS | 30 GiB | - | target raggiunto |
| `probe_win_single_31g.log` | single | 31 GiB | PASS | 31 GiB | - | target raggiunto |
| `probe_win_single_32g.log` | single | 32 GiB | FAIL | 0 GiB | `CUDA_ERROR_OUT_OF_MEMORY` da `cuMemHostAlloc(arena)` | non e guard RAM: prima del tentativo c'erano ~52.54 GiB disponibili |
| `probe_win_blocks_32g_step1g.log` | blocks | 32 GiB | FAIL controllato | 31 GiB | `CUDA_ERROR_OUT_OF_MEMORY` sul blocco successivo | 31 blocchi da 1 GiB trattenuti; staging 16 MiB e DMA/checksum OK sui 31 GiB |

Dettagli chiave:

- **MISURA LOCALE**: ABI driver usata dal probe:
  `context_v2;device_memory_v2;stream_destroy_v2`.
- **MISURA LOCALE**: il test `single 32 GiB` fallisce immediatamente su
  `cuMemHostAlloc(arena)` con `cuda_code=2`, `CUDA_ERROR_OUT_OF_MEMORY`, pur
  avendo piu di 52 GiB RAM disponibili.
- **MISURA LOCALE**: il test `blocks 32 GiB step 1 GiB` alloca e materializza
  31 GiB, poi fallisce sul blocco successivo con lo stesso errore CUDA. Il
  probe mantiene i 31 GiB, alloca lo staging pinned da 16 MiB, esegue H2D/D2H e
  verifica checksum prima del cleanup.
- **MISURA LOCALE**: dopo cleanup, la macchina e tornata a circa 50.08 GiB RAM
  disponibile e `nvidia-smi` mostrava 518 MiB / 12288 MiB, util 0%.

Conclusione:

- **MISURA LOCALE**: CUDA nativo Windows conserva il tetto pratico gia visto in
  WSL/WDDM: 31 GiB host pinned passano, 32 GiB fallisce con
  `CUDA_ERROR_OUT_OF_MEMORY`.
- **FONTE + MISURA**: il comportamento e coerente con la policy WDDM/VidMm della
  shared system memory descritta da Microsoft e con la limitazione pinned memory
  documentata da NVIDIA per Windows/WSL.
- **NON PIU IPOTESI**: su questa macchina, Windows nativo CUDA non sblocca una
  arena host-pinned da ~50 GiB.

## Misure WSL2 gia presenti

I log in `arena_probe` sono WSL/Linux, non il nuovo probe Windows nativo:

- runner `*.runner.sh`
- build con `/usr/local/cuda-12.8/bin/nvcc`
- Runtime API `cudaHostAlloc`

Tabella riassuntiva da `summary` JSONL:

| Log | Mode | Requested | Allocated | Status | Copy GiB/s | Note |
| --- | --- | ---: | ---: | --- | ---: | --- |
| `probe_20260713_074806_single_hostalloc_24g.jsonl` | single | 24 GiB | 24 GiB | success | 2.971581 | copy verified |
| `probe_20260713_074901_single_hostalloc_28g.jsonl` | single | 28 GiB | 28 GiB | success | 3.028627 | copy verified |
| `probe_20260713_075005_single_hostalloc_30g.jsonl` | single | 30 GiB | 30 GiB | success | 3.018815 | copy verified |
| `probe_20260713_075118_single_hostalloc_31g.jsonl` | single | 31 GiB | 31 GiB | success | 3.024387 | copy verified |
| `probe_20260713_072839_blocks_hostalloc_50g.jsonl` | blocks | 50 GiB | 31 GiB | failed | 3.040073 | `cudaHostAlloc` OOM at next 1 GiB block |

Percorso log:

`C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arena_probe`

Conclusione:

- **MISURA LOCALE**: su WSL2 con 64 GiB fisici, il massimo utile osservato e
  31 GiB pinned/trattenuti. Il target 50 GiB non passa.
- **MISURA LOCALE**: l'H2D diretto dalla arena pinned verificata e circa
  3.0 GiB/s nei test grandi.
- **IPOTESI**: una maschera da 50 GiB host-pinned non e raggiungibile su questa
  configurazione WSL/WDDM senza cambiare runtime o hardware.

## Ricognizione DS4/Dwarf/SPEX e correlati

### Upstream `antirez/ds4`

- URL: <https://github.com/antirez/ds4>
- **FONTE**: repository attivo, non archiviato.
- **FONTE**: descrizione GitHub al momento della ricognizione: "DeepSeek 4
  Flash and PRO local inference engine for Metal, CUDA and ROCm".

PR/issue rilevanti:

| Link | Stato | Rilevanza |
| --- | --- | --- |
| [`antirez/ds4#158`](https://github.com/antirez/ds4/pull/158) | OPEN, conflicting | Fix HMM per GB10/NVLink-C2C. Evita copie device-private quando `cudaHostRegister` non supportato e usa `cudaMemPrefetchAsync` sul full mmap. Riporta 13.81 t/s su DGX Spark. |
| [`antirez/ds4#349`](https://github.com/antirez/ds4/pull/349) | OPEN, conflicting | CUDA SSD streaming. Benchmark rapido su GB10 con cache esperti 8GB: prefill ~30-32 t/s, decode ~2.1 t/s. Utile ma sotto target 5-8 t/s per decode se usato come capacity mode. |
| [`antirez/ds4#153`](https://github.com/antirez/ds4/pull/153) | OPEN, conflicting | CUDA partial weight cache opt-in per GPU da 24GB: direct baseline 1.66 tok/s, cache 8GB 6.93 tok/s, 10GB 7.77 tok/s. Non supera WDDM, ma e una leva concreta per tenere hot dense weights in VRAM. |
| [`antirez/ds4#187`](https://github.com/antirez/ds4/pull/187) | OPEN, conflicting | Fast CUDA backend: mmq/mmvq, CUDA Driver VMM per layout pesi, weight-server VMM e MTP CUDA. Migliora performance su Linux/Blackwell, ma non e un bypass del budget WDDM host-pinned. |
| [`antirez/ds4#243`](https://github.com/antirez/ds4/pull/243) | OPEN, conflicting | KV/comp-cache turbo3/turbo4 e HISA. Riduce KV a lungo contesto, soprattutto su unified memory; non riduce il requisito di residency/pinning dei pesi MoE. |
| [`antirez/ds4#317`](https://github.com/antirez/ds4/pull/317) | OPEN, conflicting | Limita fallback CUDA distributed al layer span assegnato. Corregge il caso DGX Spark/Q4 dove il worker provava ad accedere/registrare il full GGUF invece di ~78 GiB. |
| [`antirez/ds4#435`](https://github.com/antirez/ds4/pull/435) | OPEN draft, mergeable | Generalizza router-select CUDA per DeepSeek V4 PRO su GB10 (384 experts, scale 2.5). Fix modello/architettura, non memory transport. |
| [`antirez/ds4#121`](https://github.com/antirez/ds4/pull/121) | OPEN, conflicting | Skip ordered F16 matmul su Blackwell: riportato +18.2% gen su Jetson Thor, +4.8% su GB10. Performance kernel, non memoria. |
| [`antirez/ds4#110`](https://github.com/antirez/ds4/pull/110) | CLOSED | Ottimizzazioni prefill GB10 (~20%): device tensors, `cudaMemsetAsync`, MoE down path. Utile come storico performance Spark, non soluzione residency. |
| [`antirez/ds4#512`](https://github.com/antirez/ds4/pull/512) | OPEN draft, mergeable | Windows nativo ROCm per AMD Strix Halo/gfx1151, Windows 11, ROCm 7.1, modello 80.76 GiB, ~15-16 t/s generation. Non aiuta RTX 3060 CUDA ma dimostra valore di unified RAM. |
| [`antirez/ds4#362`](https://github.com/antirez/ds4/pull/362) | OPEN | Windows AMD HIP SDK ROCm + MinGW CPU build per gfx1151 e fix >2 GiB. Non CUDA/NVIDIA. |
| [`antirez/ds4#407`](https://github.com/antirez/ds4/pull/407) | OPEN, conflicting | ROCm Strix Halo distributed/unified memory: copia solo span assegnati e gestisce span non contigui. Confronto utile, ma backend AMD. |
| [`antirez/ds4#461`](https://github.com/antirez/ds4/pull/461) | OPEN, mergeable | ROCm discrete GPU memory management: host-mapped expert fallback, free-reserve tunable. Utile come pattern di overflow, non applicabile a CUDA/WDDM locale. |
| [`antirez/ds4#320`](https://github.com/antirez/ds4/pull/320) | CLOSED, conflicting | Bugfix ROCm: con chunked copy evita `cudaHostRegister` del full mmap, altrimenti il `DONTNEED` non libera RAM. Importante come lezione: registrare tutto puo distruggere la strategia chunked. |
| [`antirez/ds4#497`](https://github.com/antirez/ds4/pull/497) | OPEN | CUDA selected load per streaming single-token FFN batch. Rilevante a streaming CUDA, non al tetto WDDM. |
| [`antirez/ds4#508`](https://github.com/antirez/ds4/pull/508) | OPEN | CPU SSD streaming per routed experts. Concettualmente utile per cache, non elimina host pinned/GPU path. |
| [`antirez/ds4#518`](https://github.com/antirez/ds4/pull/518) | CLOSED | Fix CUDA multi-model/MTP mapping: evita scorciatoie registered/owned su mappe straniere dopo fallimento `cudaHostRegister` base. Correttezza, non capacity. |
| [`antirez/ds4#109`](https://github.com/antirez/ds4/pull/109) | OPEN | Note Jetson Thor CUDA (`sm_110`). Documentazione, non runtime memory fix. |
| [`antirez/ds4#293`](https://github.com/antirez/ds4/issues/293) | OPEN | DGX Spark distributed worker host-registers whole GGUF, Q4 OOM. Segnala che su GB10 il dettaglio di host-register/layer-slice conta davvero. |
| [`antirez/ds4#183`](https://github.com/antirez/ds4/issues/183) | CLOSED | Misure GB10 vs Jetson Thor: GB10 gen ~14.20 t/s a 2k ctx, ~11.88 t/s a 65k; Thor ~7.77 -> 6.02 t/s. |

Branch upstream:

- **FONTE**: l'API GitHub mostra tre branch upstream al momento della
  ricognizione: `main` (`80ebbc396aee40eedc1d829222f3362d10fa4c6c`),
  `responses-api` (`acb40bf59791a340fe4d38705b88f1016bb321d4`) e
  `glm5.2` (`bd89932c4a0029a911b9f0f0a82688a4bbf69208`).
- **IPOTESI**: le piste runtime/hardware importanti non vivono su branch
  upstream separati; stanno in PR/fork.

Ricerche mirate:

- **FONTE**: ricerche GitHub su PR `DirectStorage`, `GPUDirect`, `GDS`,
  `cuFile` nel repo `antirez/ds4` non hanno restituito PR attive o chiuse
  rilevanti.
- **FONTE**: ricerche su issue `WDDM`, `Windows CUDA`, `native Windows`,
  `cudaHostRegister`, `cudaHostAlloc`, `pinned`, `GPUDirect`, `GDS`, `cuFile`
  non hanno trovato issue DS4 oltre ai casi gia tracciati via PR/issue sopra.
- **IPOTESI**: al momento non esiste una pista DS4 concreta basata su
  DirectStorage/GDS/cuFile da portare sulla RTX 3060 Windows.

### `hawkli-1994/ds4-win`

Gia trattato sopra. E il fork Windows CUDA concreto:

- <https://github.com/hawkli-1994/ds4-win>
- <https://github.com/hawkli-1994/ds4-win/tree/codex/windows-cuda>
- <https://github.com/hawkli-1994/ds4-win/pull/2>
- <https://github.com/hawkli-1994/ds4-win/actions/runs/25801727530>

Valutazione:

- **FONTE**: compila `ds4_server.exe` in CI Windows CUDA.
- **IPOTESI**: utile come base porting Win32/CMake, non come soluzione memoria.
- **NON MISURA**: non abbiamo un run modello reale su RTX 3060 Windows nativo.

### DGX Spark / GB10 / ARM64 / Jetson

#### `antirez/ds4#158` HMM GB10

Link:

- PR: <https://github.com/antirez/ds4/pull/158>
- Commit: <https://github.com/antirez/ds4/pull/158/commits/75c458da489ec2c543121da118601966e68d2727>

Stato:

- OPEN
- `mergeable=CONFLICTING`
- `mergeStateStatus=DIRTY`
- 8 linee in `ds4_cuda.cu`

Contenuto:

- Quando `cudaHostRegister()` restituisce `cudaErrorNotSupported` su GB10,
  chiama il path gia esistente `cuda_model_prefetch_range()`.
- Il path usa `cudaMemPrefetchAsync` sul full mmap e imposta
  `g_model_hmm_direct=1`.
- `cuda_model_range_is_cached()` ritorna cached quando HMM diretto e attivo,
  evitando copie per-range `cudaMalloc + cudaMemcpy`.

Risultati riportati dall'autore PR:

- Hardware DGX Spark GB10, SM_121, 128 GB unified LPDDR5x, NVLink-C2C.
- Modello 80.76 GiB.
- Prima: processo `nvidia-smi` ~87,992 MiB per copie device-private.
- Dopo: modello in file page cache reclaimable, processo ~26,000 MiB,
  GPU util 94%, throughput 13.81 t/s.

Valutazione:

- **FONTE**: e il candidato piu vicino all'obiettivo "no staging/pread/sync" su
  hardware coherent.
- **IPOTESI**: da cherry-pickare/rebaseare se si usa GB10 o un sistema ATS/HMM
  equivalente.

#### `antirez/ds4#317` span cover per CUDA distributed

Link:

- PR: <https://github.com/antirez/ds4/pull/317>
- Commit: <https://github.com/antirez/ds4/commit/d20da6c4389c30f8c0fb3fc331ff767ca1620a1a>

Stato:

- OPEN
- `mergeable=CONFLICTING`
- `mergeStateStatus=DIRTY`
- 83 insertions / 11 deletions in `ds4_cuda.cu`

Contenuto:

- Introduce `g_model_span_cover_offset/end` e `g_model_span_only`.
- Fa passare i fallback diretti/full-map solo se il range richiesto cade nello
  span cover assegnato al worker.
- Evita che un worker `--layers 21:output` tratti come accessibile l'intero
  GGUF Q4 da ~150 GiB quando il suo span reale e circa 78 GiB.

Valutazione:

- **FONTE**: e un fix preciso per issue `#293` su DGX Spark distributed.
- **IPOTESI**: non serve alla macchina RTX 3060/WSL come bypass WDDM, ma e
  molto rilevante se il percorso scelto diventa DGX Spark o pod Linux
  distributed con modelli Q4/profilo multi-worker.

#### CUDA/Blackwell performance PRs

Rilevanti per GB10/Blackwell, ma da non confondere con la soluzione memoria:

- [`antirez/ds4#121`](https://github.com/antirez/ds4/pull/121): skip ordered
  F16 matmul su Blackwell; riporta generazione media +18.2% su Jetson Thor e
  +4.8% su DGX Spark/GB10. Performance kernel.
- [`antirez/ds4#110`](https://github.com/antirez/ds4/pull/110): closed;
  riporta ~20% prefill improvement su GB10 usando device tensors,
  `cudaMemsetAsync` e path MoE down diverso. Performance kernel/storico.
- [`antirez/ds4#435`](https://github.com/antirez/ds4/pull/435): draft aperto;
  generalizza router-select CUDA per DeepSeek V4 PRO su GB10. Serve per far
  partire PRO, non per risolvere host-pinned/shared memory.
- [`antirez/ds4#187`](https://github.com/antirez/ds4/pull/187): grande PR CUDA
  con mmq/mmvq, CUDA Driver VMM per layout pesi e weight-server VMM. Utile su
  Linux/Blackwell per throughput e sharing fra processi; il VMM qui e driver
  VMM per allocazioni device, non un modo di superare VidMm/WDDM su Windows.

#### CUDA partial cache e selected-load

- [`antirez/ds4#153`](https://github.com/antirez/ds4/pull/153) riporta, su GPU
  24GB RTX 4090-class, direct-model decode da 1.66 tok/s a 6.93 tok/s con 8GB
  di partial weight cache e 7.77 tok/s con 10GB. Questo e molto vicino al
  target 5-8 t/s come idea di hot dense cache, ma il test e su 24GB VRAM e non
  risolve il bisogno di 50 GiB host-resident/pinned sulla 3060.
- [`antirez/ds4#497`](https://github.com/antirez/ds4/pull/497) corregge il
  selected-load CUDA per FFN batch a singolo token con MTP/streaming. Utile per
  evitare fallback OOM nel path streaming, non per creare una arena grande.
- [`antirez/ds4#508`](https://github.com/antirez/ds4/pull/508) e CPU SSD
  streaming per routed experts, soprattutto per macOS CPU safety. Come modello
  concettuale conferma che bounded residency aiuta; non e la strada CUDA zero
  copy.

#### `vu2lid/ds4-thor-docker`

Link: <https://github.com/vu2lid/ds4-thor-docker>

Stato:

- Repository packaging, non fork codice DS4.
- Descrizione: Docker packaging per `antirez/ds4` su NVIDIA aarch64 unified
  memory, testato su Jetson AGX Thor `sm_110`, CUDA 13, Ubuntu 24.04.
- Dice che dovrebbe funzionare su DGX Spark/GB10 impostando `DS4_CUDA_ARCH`,
  ma Spark non testato li.

Note operative importanti dal README:

- Q2/Q2-Q4 (~81-91 GB) possono girare fully resident su 128 GB Thor.
- SSD streaming su internal NVMe e riportato intorno a ~1 t/s, circa 8x piu
  lento, quindi non interattivo.
- `DS4_CUDA_HOST_REGISTER_PLAIN=1` evita un hang/wedge GPU/GSP in certe
  condizioni di host registration.
- Il repo non include DS4 ne pesi, solo Dockerfile/compose/build/docs.

Valutazione:

- **FONTE**: conferma che unified-memory ARM64 puo rendere residenti i pesi.
- **NON MISURA LOCALE**: i numeri Thor/packaging non sono stati riprodotti qui.
- **IPOTESI**: utile come runbook operativo, non come patch runtime.

#### `yuhai-china/ds4-spark`

Link: <https://github.com/yuhai-china/ds4-spark>

Stato:

- Non marcato come fork GitHub, ma contiene codice DS4 completo.
- README dice "DwarfStar", supporto CUDA / DGX Spark, `make cuda-spark`.
- Ultimi commit sono su Markov/HC speculative decoding, non sul collo di
  bottiglia WDDM/pinned.
- Albero include `ds4.c`, `ds4_cuda.cu`, Makefile con `cuda-spark`.

Valutazione:

- **FONTE**: e un adattamento DS4-like con focus DSpark/speculative.
- **MISURA DI RICOGNIZIONE**: nelle ricerche sui file principali non e emerso
  DirectStorage, GDS, o una patch diversa di `cudaHostRegister` rispetto a DS4.
- **IPOTESI**: interessante per speed/speculation, non per superare WDDM o
  eliminare staging su RTX 3060.

#### Ricette vLLM/DSpark su 2x DGX Spark

Esempi:

- <https://github.com/tonyd2wild/DeepSeek-v4-Flash-DSpark-1M-NVFP4-KV-2x-DGX-Spark>
- <https://github.com/drowzeys/DeepSeek-V4-Flash-DSpark-Abliterated-Uncensored-1M-57toks>
- <https://github.com/0rand/DeepSeek-v4-DSpark-Aidendle94-GB10-ServingStack>

Valutazione:

- **FONTE**: sono ricette/overlay/serving stack vLLM/DSpark, spesso TP=2 su due
  DGX Spark, non fork del runtime C DS4 per la path memoria.
- **FONTE**: riportano numeri elevati, anche 50-60 t/s o piu, ma su vLLM
  DSpark spec-decode, NVFP4 KV e due nodi GB10.
- **IPOTESI**: utili se l'obiettivo diventa servire DeepSeek V4 Flash su
  infrastruttura DGX Spark, ma non trasferibili alla RTX 3060/WDDM ne alla
  modifica DS4 zero-copy locale.

#### Fork recenti DS4 senza clone locale

Ho interrogato l'API GitHub `forks?sort=newest&per_page=100` e ordinato
localmente per `pushed_at`, senza creare cloni.

Fork/branch notevoli:

| Fork | Stato ricognizione | Rilevanza |
| --- | --- | --- |
| [`redhunt07/ds4-DSpark-GB10`](https://github.com/redhunt07/ds4-DSpark-GB10) | Fork di `antirez/ds4`, branch `main` ahead 13 commit, pushed 2026-07-13. README: operativo su DGX Spark/GB10, DSpark embedded, profilo fast ~17.6 generated tok/s dichiarati. | DSpark/GB10 runtime fork interessante. Non e una soluzione WDDM; richiede Linux ARM64/GB10/unified memory. |
| [`ljt019/ds4`](https://github.com/ljt019/ds4/tree/cuda-transient-f16-gemm) | Default branch `cuda-transient-f16-gemm`, ahead 1 commit (`ca7a2983a182`). Commit: transient F16 dequant + cuBLAS per prefill Q8_0, misurato su RTX PRO 6000 Blackwell: prefill 410.9 -> 995.7 -> 1651.8 t/s, decode circa invariato. | Performance prefill su Blackwell/discrete; non capacity/memory transport. |
| [`0xfunboy/ds4-multicuda`](https://github.com/0xfunboy/ds4-multicuda) | Fork ahead 9 commit. Aggiunge `--cuda-devices`, split esperti multi-GPU in-process e launcher; README commit riporta 2x RTX 3090: prefill +40%, cold-cache gen +28%, warm-cache decode 1.8 -> 2.8 t/s. | Interessante per multi-GPU Linux. Non supera il tetto WDDM/pinned su singola 3060 e resta sotto 5-8 t/s nei numeri dichiarati. |
| [`amplogik/ds4`](https://github.com/amplogik/ds4/tree/rocm-discrete-rdna3) | Branch `rocm-discrete-rdna3`, ahead 3 commit. Ricette discrete AMD RDNA3/ROCm, 4x24GB full residency ~22 t/s dichiarati, free-reserve tunable. | Alternativa ROCm/discrete AMD, non CUDA/NVIDIA locale. |
| [`Rekonquest/ds4`](https://github.com/Rekonquest/ds4) | Fork ahead 6 commit con workspace Rust sperimentale `ds4-rust`, backend Arc/Vulkan notes. | Sperimentale/pre-1.0. Non evidenzia soluzione per pinned/WDDM. |

Risultato:

- **FONTE**: nessuno dei fork recenti sopra e un port Windows CUDA migliore del
  fork `hawkli-1994/ds4-win`.
- **FONTE**: i fork migliori per throughput puntano a Linux/GB10/Blackwell,
  multi-GPU CUDA o ROCm, non a DirectStorage/GDS su Windows.
- **IPOTESI**: per la macchina locale la parte trasferibile e concettuale
  (partial hot cache, selected-load corretto, multi-GPU eventuale), non un
  pacchetto pronto che elimini il limite host pinned.

### SPEX nel repo locale

SPEX, nel materiale locale, e una leva software predittiva per expert prefetch,
non un runtime/hardware alternativo.

Fonti locali:

- `docs/BUILD_TUTTO_DENTRO_SPEC.md` dichiara SPEX gia cablato nel tree
  `spex/trace-ext` a commit `7a93e3b`, con patch 0001-0007 applicate.
- Lo stesso documento dice che SPEX si accende con `DS4_SPEX_MARKOV_FILE`,
  richiede `--ssd-streaming`, e deve essere verificato con output byte-identico
  ON vs OFF perche predice il loading, non il gating.
- `docs/CONFIDENCE_CASCADE_MEMORY.md` posiziona SPEX come prefetch predittivo
  degli expert; REAP/cascade agisce sull'asse working-set/memoria.
- I log locali in
  `C:\Users\imanu\source\repos\reap-loop\runs\ds4\20260712_v2_zerocopy\arm_off`
  mostrano statistiche SPEX (`hit_rate=0.3695`, `copy_ms_per_batch=27.054`,
  `sync_ms_per_batch=1.687`) nel contesto del lavoro DS4 corrente.

Valutazione:

- **MISURA LOCALE**: esistono log SPEX/runtime locali, ma sono parte dei test
  DS4 principali e non li ho rieseguiti in questa task per rispettare il lock.
- **FONTE**: SPEX e gia una leva in-tree secondo la documentazione locale.
- **IPOTESI**: SPEX puo ridurre miss, random read e copy/sync se il predittore
  e buono; non aumenta la quantita di memoria host pinnabile sotto WDDM.
- **NON DEDURRE**: un buon recall SPEX non implica automaticamente 5-8 t/s se
  il miss path resta `pread + staging + sync` e la arena host-pinned non supera
  ~31 GiB.

### DirectStorage, GPUDirect Storage, memory mapping, zero-copy

Risultato della ricognizione DS4:

- Non ho trovato un fork DS4 attuale con DirectStorage.
- Non ho trovato un fork DS4 attuale con GPUDirect Storage.
- Non ho trovato PR DS4 con `cuFile`/GDS.
- `antirez/ds4#349` e il candidato CUDA SSD streaming, ma usa selected-load e
  overlap, non GDS; benchmark GB10 decode ~2.1 t/s con 8GB expert cache.

Fonti esterne:

- **FONTE**: NVIDIA GPUDirect Storage crea un path diretto storage -> GPU e
  evita bounce buffer CPU, ma NVIDIA dice che GDS e supportato su Linux x86-64 e
  non su Windows:
  <https://developer.nvidia.com/gpudirect-storage>.
- **FONTE**: Microsoft DirectStorage per Windows/GDK mantiene staging buffers
  per flussi non compressi/compressi e custom decompression; non e equivalente
  a GDS per far leggere direttamente a CUDA da NVMe:
  <https://github.com/microsoft/DirectStorage/blob/main/Docs/DeveloperGuidance.md>.

Valutazione:

- **IPOTESI**: DirectStorage non risolve il collo `pread + staging + sync` di
  DS4 CUDA su Windows per RTX 3060.
- **IPOTESI**: GDS potrebbe essere utile su pod/Linux bare metal con hardware e
  filesystem supportati, ma non e la prima leva sulla macchina Windows attuale.

## Fonti architetturali

### WDDM / WSL

- **FONTE**: Microsoft DirectX blog spiega che VidMm gestisce VRAM e DRAM
  condivisa per la GPU; la shared memory e normale system memory e Windows
  permette alla GPU di usare solo meta della memoria fisica in un dato istante:
  <https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/>.
- **FONTE**: NVIDIA CUDA on WSL dichiara:
  - WSL usa il driver Windows e `libcuda.so` stubbed.
  - Full Managed Memory non e disponibile su Windows nativo e quindi WSL2 non
    la supporta.
  - Concurrent CPU/GPU access non e supportato.
  - La disponibilita di pinned system memory e limitata.
  Fonte: <https://docs.nvidia.com/cuda/wsl-user-guide/index.html>.

### CUDA HMM / ATS / mapped memory

- **FONTE**: CUDA Programming Guide dice che su Linux con HMM o ATS tutta la
  memoria allocata dal sistema e managed memory; su Windows e Tegra la unified
  memory ha limitazioni:
  <https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/understanding-memory.html>.
- **FONTE**: su Grace Hopper/Grace Blackwell con NVLink-C2C e ATS, la GPU puo
  usare host page tables e il sistema ha full unified memory con hardware
  coherence.
- **FONTE**: su Windows le allocazioni managed devono essere esplicite e non
  c'e la stessa full unified system memory.

### DGX Spark hardware

- **FONTE**: DGX Spark ha Grace Blackwell integrato GPU+CPU, 20-core Arm,
  128 GB unified system memory, LPDDR5x 273 GB/s e supporto a modelli fino a
  200B (405B dual Spark):
  <https://docs.nvidia.com/dgx/dgx-spark/hardware.html>.

## Matrice decisionale

| Strada | Fattibilita | Memoria realmente pinnabile/residente | Modifiche DS4 necessarie | Rischio | Costo | Prestazione attesa | Giudizio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WSL2 attuale su RTX 3060/64GB | Gia funziona | **MISURA**: `cudaHostAlloc` 31 GiB ok, 50 GiB fallisce a 31 GiB. | Dynamic arena non basta se richiede 50 GiB pinned; servono streaming/cache migliori. | Basso per continuare, alto per target 50 GiB. | Zero. | **MISURA**: H2D ~3.0 GiB/s da arena pinned grande; decode target non garantito. | Non raggiunge obiettivo 50 GiB. |
| Windows CUDA nativo su RTX 3060 | Probe compilato ed eseguito; porting DS4 base esiste | **MISURA**: single 24/28/30/31 GiB PASS; single 32 GiB FAIL; blocks 32 GiB trattiene 31 GiB e fallisce sul blocco successivo. | Rebase `hawkli` solo se serve un binario Windows per altri motivi; per 50 GiB pinned non basta. | Alto per obiettivo memoria: WDDM confermato. | Zero hardware, tempo alto non giustificato per 50 GiB. | **MISURA**: non supera il tetto WSL/WDDM; throughput DS4 reale non misurato perche capacity gia bocciata. | Pista chiusa per obiettivo 50 GiB. |
| Linux bare metal / dual boot locale | Fattibile se si installa Linux | **IPOTESI**: niente cap WDDM; HMM possibile se driver/kernel/GPU lo espongono, altrimenti pinned slabs oltre 31 GiB da misurare. | Implementare probe/arena Linux: rilevare HMM attributes, mmap+prefetch oppure pinned ring overlap. | Medio: install/driver, possibile bandwidth PCIe limitante. | Basso. | Potenziale 5-8 t/s se overlap e cache esperti riducono miss; da misurare. | Percorso corto a basso costo. |
| Linux CUDA locale con hot/partial cache | Codice candidato esiste in PR/fork, non testato qui | **IPOTESI**: niente WDDM, ma RTX 3060 ha solo 12GB VRAM; partial cache #153 e stata misurata su 24GB. | Portare idee #153/#497/SPEX su branch locale, dimensionare hot dense cache sotto 12GB, mantenere arena dinamica RAM. | Medio-alto: performance dipende da miss path e VRAM. | Basso. | #153 riporta 6.93-7.77 t/s su 24GB; su 12GB e una ipotesi da misurare, non un trasferimento diretto. | Possibile leva locale, non soluzione garantita. |
| Pod Linux GPU | Alta se si affitta nodo adatto | Dipende da hardware; su H100/A100 grande VRAM o sistemi HMM/GDS niente WDDM. | Portare harness/probe DS4, misurare arena/fetch; nessun Win32. | Medio-basso, ma ambiente diverso dal PC. | Orario cloud. | Buono per validare target rapidamente; non prova RTX 3060 locale. | Ottimo per validazione veloce. |
| DGX Spark / GB10 | Alta se hardware disponibile | **FONTE**: 128GB unified coherent; PR #158 tiene modello 80.76 GiB in file page cache reclaimable. | Rebase/cherry-pick #158, validare CUDA Spark, forse integrare dynamic mask sopra HMM direct. | Medio: PR conflittuale, hardware nuovo. | Alto. | **FONTE**: DS4 GB10 ~13.8-14.2 t/s decode a contesti moderati; Thor ~6-8 t/s. | Miglior soluzione architetturale. |
| CUDA multi-GPU Linux | Fork dimostrativi esistono | Somma VRAM/PCIe/P2P, non host pinned 50GB su singola GPU. | Adottare/fondere `0xfunboy/ds4-multicuda` o equivalente; risolvere correctness e cache policy. | Alto: fork sperimentale, topologia PCIe critica. | Medio-alto se servono GPU aggiuntive. | **FONTE fork**: 2x RTX 3090 warm decode 1.8 -> 2.8 t/s; sotto target locale. | Non e il percorso corto per 5-8 t/s su questa macchina. |
| Windows AMD Strix Halo ROCm | Fattibile solo cambiando hardware | **FONTE**: 96/128GB unified RAM, PR #512 carica modello 80.76 GiB; non e NVIDIA. | Usare PR #512/#362, non CUDA; niente RTX 3060. | Medio. | Alto. | **FONTE**: ~15-16 t/s generation su Windows ROCm Strix Halo. | Alternativa hardware valida, fuori path RTX. |
| DSpark/vLLM 2x DGX Spark | Fattibile con due Spark e stack vLLM | Usa memory/KV stack vLLM, non DS4 C arena. | Non e port DS4; migrazione applicativa. | Medio-alto: stack complesso. | Molto alto. | **FONTE**: ricette riportano 50-60 t/s+ su due nodi, ma non misure locali. | Alternativa prodotto, non soluzione DS4 locale. |

## Percorso consigliato

### Stato del probe Windows nativo

Il dubbio operativo e chiuso:

- **MISURA LOCALE**: Windows nativo CUDA passa 31 GiB host pinned e fallisce a
  32 GiB con `CUDA_ERROR_OUT_OF_MEMORY`.
- **MISURA LOCALE**: in modalita blocks, 32 GiB target step 1 GiB trattiene
  31 GiB e fallisce sul blocco successivo; quindi non e solo un limite del
  singolo blocco da 32 GiB.
- **CONCLUSIONE**: non investire nel port Windows CUDA come via per arrivare a
  una arena host pinned da circa 50 GiB. Il fork `hawkli-1994/ds4-win` resta
  utile solo se serve una build Windows per esperimenti non legati al tetto
  memoria.

### Percorso tecnico piu corto verso 5-8 t/s

1. Preparare Linux bare metal/dual boot o un pod Linux con GPU NVIDIA.
2. Portare il probe/arena Linux fuori da WSL e misurare:
   - `cudaHostAlloc` single/blocks 32/40/50 GiB;
   - `cudaHostRegister` su `mmap` file-backed;
   - attributi CUDA `cudaDevAttrPageableMemoryAccess` e
     `cudaDevAttrPageableMemoryAccessUsesHostPageTables`;
   - eventuale `nvidia-smi -q | grep Addressing`.
3. Se HMM/ATS e disponibile:
   - evitare pin massivo;
   - usare `mmap` + `cudaMemPrefetchAsync`/advise quando utile;
   - prototipare DS4 sul modello di `antirez/ds4#158`.
4. Se HMM/ATS non e disponibile:
   - usare arena pinned dinamica piu piccola del working set totale;
   - prefetch asincrono e double/triple buffering;
   - sovrapporre fetch e compute;
   - misurare miss rate SPEX/maschera per capire se 5-8 t/s e realistico su
     PCIe/RTX 3060.

### Percorso hardware pulito

Se si accetta hardware nuovo o remoto:

- DGX Spark/GB10: usare DS4 upstream con patch #158 rebaseata. E il path piu
  coerente con "arena grande dinamica" perche la memoria e unified/coherent e
  non WDDM-pinned.
- Strix Halo ROCm: PR #512 mostra che Windows nativo con unified RAM AMD puo
  funzionare bene, ma e una migrazione di hardware/backend, non un fix CUDA.

## Cose da non confondere

- "Compila su Windows" non significa "supera il tetto WDDM".
- DirectStorage non e GPUDirect Storage.
- SSD streaming non e zero-copy: puo ridurre RAM residente ma puo crollare a
  ~1-2 t/s su questi workload se il miss path e troppo frequente.
- SPEX/prefetch predittivo puo ridurre miss, ma non aumenta il budget host
  pinned imposto da WDDM.
- CUDA Driver VMM in `antirez/ds4#187` migliora layout/share delle allocazioni
  device su Linux; non e la stessa cosa del Virtual Memory Manager WDDM e non
  dimostra un bypass della shared-memory policy Windows.
- DSpark/vLLM su due DGX Spark non e DS4 C locale su RTX 3060.
- `cudaHostRegister`/`cudaHostAlloc` non aggirano per magia VidMm/WDDM su
  Windows/WSL.
- Le misure GB10/Thor di PR/issue/README sono fonti esterne, non misure locali.

## Link principali

Port Windows CUDA:

- <https://github.com/hawkli-1994/ds4-win>
- <https://github.com/hawkli-1994/ds4-win/tree/codex/windows-cuda>
- <https://github.com/hawkli-1994/ds4-win/pull/2>
- <https://github.com/hawkli-1994/ds4-win/actions/runs/25801727530>

DS4 upstream:

- <https://github.com/antirez/ds4>
- <https://github.com/antirez/ds4/pull/158>
- <https://github.com/antirez/ds4/pull/349>
- <https://github.com/antirez/ds4/pull/153>
- <https://github.com/antirez/ds4/pull/187>
- <https://github.com/antirez/ds4/pull/243>
- <https://github.com/antirez/ds4/pull/317>
- <https://github.com/antirez/ds4/pull/435>
- <https://github.com/antirez/ds4/pull/121>
- <https://github.com/antirez/ds4/pull/110>
- <https://github.com/antirez/ds4/pull/512>
- <https://github.com/antirez/ds4/pull/362>
- <https://github.com/antirez/ds4/pull/407>
- <https://github.com/antirez/ds4/pull/461>
- <https://github.com/antirez/ds4/pull/320>
- <https://github.com/antirez/ds4/pull/497>
- <https://github.com/antirez/ds4/pull/508>
- <https://github.com/antirez/ds4/pull/518>
- <https://github.com/antirez/ds4/issues/183>
- <https://github.com/antirez/ds4/issues/293>

GB10/Thor/DSpark:

- <https://github.com/vu2lid/ds4-thor-docker>
- <https://github.com/yuhai-china/ds4-spark>
- <https://github.com/redhunt07/ds4-DSpark-GB10>
- <https://github.com/ljt019/ds4/tree/cuda-transient-f16-gemm>
- <https://github.com/0xfunboy/ds4-multicuda>
- <https://github.com/amplogik/ds4/tree/rocm-discrete-rdna3>
- <https://github.com/Rekonquest/ds4>
- <https://github.com/tonyd2wild/DeepSeek-v4-Flash-DSpark-1M-NVFP4-KV-2x-DGX-Spark>
- <https://github.com/drowzeys/DeepSeek-V4-Flash-DSpark-Abliterated-Uncensored-1M-57toks>
- <https://github.com/0rand/DeepSeek-v4-DSpark-Aidendle94-GB10-ServingStack>

Documentazione:

- <https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/>
- <https://docs.nvidia.com/cuda/wsl-user-guide/index.html>
- <https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/understanding-memory.html>
- <https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__TYPES.html>
- <https://docs.nvidia.com/cuda/cuda-driver-api/group__CUDA__MEM.html>
- <https://developer.nvidia.com/gpudirect-storage>
- <https://github.com/microsoft/DirectStorage/blob/main/Docs/DeveloperGuidance.md>
- <https://docs.nvidia.com/dgx/dgx-spark/hardware.html>
