# Porto PR upstream #1120 e #1122 sul fork Strata-2080Ti-core

Base: `Strata-2080Ti-core` `main` @ `3f85784`. Patch da applicare dalla radice del fork con `git apply <file>`.
Entrambe passano `git apply --check` su 3f85784 e si applicano in tutti e due gli ordini (1120 poi 1122, o il contrario).
Stato: **compilato no, installato no, provato no**. Il checkout del fork non è stato toccato.

| file | PR upstream (head) | file toccati | +/- |
|---|---|---|---|
| `pr1120.diff` | #1120 `202d4cc` (bsvinay, aperta) | MULTI_GPU.md, verify.hpp, verify_kernels.hpp, verify.cpp, verify_kernels.cu, generate.cpp | +312 / -28 |
| `pr1122.diff` | #1122 `ad4eaaa` (Hardin22, aperta) | DETAILS.md, MULTI_GPU.md, verify.cpp, generate.cpp | +254 / -67 |

## pr1120: STRATA_SPLIT_OVERLAP (passaggio tra blocchi sovrapposto)

**Cosa fa.** Con `--layer-split` su schede diverse e senza `--pipeline-windows`, ogni passaggio tra due blocchi ha una
parola «pronto» in memoria pinned mappata. Il grafo del blocco che scrive finisce con `handoff_publish` (carico con
store volatili, fence di sistema, l'ultimo blocco CUDA alza il flag). Il grafo del blocco che legge comincia con
`wait_handoff`, un'attesa limitata. `Verifier::run` cattura il grafo del blocco successivo sul proprio thread, poi lo
prepara e lo lancia (`prelaunch`) da un thread di appoggio mentre serve i layer del proprio blocco. Il blocco
precedente viene sincronizzato solo a catena finita. Dal percorso critico escono una sync e un lancio di grafo per
finestra. Le finestre batch restano seriali.

**Come si accende.** Variabili d'ambiente, tutte spente di default:
- `STRATA_SPLIT_OVERLAP=1` accende la funzione. Non vale con `--split-device 0` né con `--pipeline-windows` (in quel caso lo dice nel log e resta spenta). Il log di avvio mostra `one hand-off per window (overlapped: STRATA_SPLIT_OVERLAP=1)`.
- `STRATA_SPLIT_WAIT_MS` (default 30000, 0 = nessun limite) limita l'attesa lato GPU. Allo scadere la finestra fallisce con un errore esplicito.
- `STRATA_TEST_HANDOFF_DROP=N` è un hook di test: nella N-esima finestra il flag non viene alzato.

**Conflitti risolti** (4 hunk respinti su 3f85784):
1. `verify_kernels.hpp`: il fork ha `wait_flag_ge_stamped`, dal porto #1038. Ho aggiunto le dichiarazioni di `handoff_publish` e `wait_handoff` dopo di essa, senza toccarla.
2. `verify_kernels.cu`: upstream porta un suo `strata_now_ns()`, mentre il fork ha già `now_ns()` con le stesse sorgenti di clock (globaltimer, wall_clock64). Ho riusato `now_ns()` e messo i due kernel nello stesso namespace anonimo, dopo `wait_flag_ge_stamped_kernel`. Così non c'è un secondo helper duplicato.
3. `verify.cpp`, distruttore: il fork libera anche `la_*`, `pf_staging_`, `h_pred_` e `h_bal_`. Li ho tenuti tutti e ho aggiunto `hcount_d_`, `herr_h_` e `hdrop_h_`.
4. `verify.cpp`, `run()`:
   - `neuron_trace_->begin_run()` (sonda lab) resta in testa.
   - Il blocco di lancio, compreso l'azzeramento dei timbri `h_bal_` del #1038, è ora dentro `if (!pre)`.
   - In `prelaunch` ho aggiunto lo stesso azzeramento di `h_bal_` prima del lancio, che upstream non ha.
   - Nel ramo `chain` ho aggiunto, come nel percorso seriale, la sonda lab lookahead e `pcie_balance_window(steps, G)`.
   - La sonda lookahead è diventata una lambda locale `la_report` chiamata da entrambi i percorsi: stesso comportamento, nessuna duplicazione.

**Default bit-identico.** Senza la variabile i puntatori dei flag sono nulli: `record_window` cattura lo stesso grafo,
`pre` e `chain` valgono false, `handoff_failed()` restituisce false. Restano solo un `_mm_sfence()` in più in
`stage_inputs` e un puntatore nullo in più nel ciclo di `release_gpu_waits`, che non cambiano l'output.

**Cache elastica.** Le due cose possono convivere (la cache elastica richiede `pipeline_windows == 0`, come
l'overlap). La cache elastica sta sul blocco di CUDA0, cioè lo stadio 0, che non viene mai pre-lanciato: si
pre-lanciano solo gli stadi successivi. `elastic_step` gira al punto sicuro del decode, dopo che `ver.run` è tornato,
e a quel punto la catena ha già sincronizzato tutti i blocchi. Non vedo conflitti, ma la combinazione non è provata
né qui né upstream.

## pr1122: --adapt-async 1 insieme a --pipeline-windows 2

**Cosa fa.** Nella 0.1.40 il tier adattivo asincrono si spegne quando c'è `--pipeline-windows`. Con questa patch,
sotto `--pipeline-windows 2`, il thread del job fa solo lavoro host: scelta, copie di rimbalzo, spostamenti in RAM.
Le copie di ciascuna scheda le accoda il thread del loop nei «gap» di quella scheda, cioè quando nessuna finestra è in
volo su quello stadio: prima di ogni lancio, a ogni verdetto, e ogni 0,5 ms mentre un giro è aperto. Gli stati nuovi
sono `Pick` e `RamFence`. La tabella di residenza sul device viene caricata una volta sola, a loop svuotato
(`a_pl_settle`). Il loop seriale è rifattorizzato (`a_pick`/`a_back`, `a_from`/`a_in_one`) ma fa le stesse cose. Inoltre
il timeout di `Verifier::service`, con `STRATA_VERIFY_TRACE=1`, stampa `diag()` e `trace_dump()` come fa `run()`.

**Come si accende.** `--layer-split` su 2 schede, `--serve`, `--pipeline-windows 2`, `--resident-experts` (modalità
RAM residente), `--adapt-async 1`, buffer di scambio page-locked. `--pipeline-windows 1` continua a spegnere il tier
asincrono. Per il confronto, `STRATA_PIPELINE_DEBUG=1 STRATA_PIPELINE_ADAPT_ASYNC=0` tiene il tier bloccante accanto
alla pipeline.

**Conflitti.** Nessuno testuale: tutti i 19 hunk entrano con offset. Le zone toccate (tier asincrono, loop pipelined,
`service()`) non hanno modifiche del fork rispetto a upstream 82f46a8, e ho verificato che `AJob::idle()`,
`Verifier::in_flight()`, `ms_now`, `<functional>` e `ahomes[stadio]` esistono con lo stesso significato. Il diff è
rigenerato su 3f85784.

**Default bit-identico.** Senza `--adapt-async 1` `ajob` è nullo, e tutte le aggiunte nel loop pipelined sono sotto
`if (ajob)`. Il tier asincrono non è bit-esatto per costruzione (#876).

**Cache elastica.** Non c'è interazione possibile. La cache elastica richiede che non ci sia il complemento CPU
residente ed è rifiutata con `--pipeline-windows` tra GPU (`el_split_ok`, `el_on`). Il tier asincrono richiede invece
`--resident-experts`: le due cose si escludono.

## Da controllare in compilazione (coordinatore)

- `verify_kernels.cu`: nessuna ridefinizione di `now_ns` o di `strata_now_ns`. I due kernel nuovi devono stare nel namespace anonimo e i wrapper `wait_handoff` e `handoff_publish` in `strata::kernels`. `%globaltimer`, `atomicAdd` e `__threadfence_system` vanno bene su sm_75 e sm_86.
- `verify.cpp`:
  - `NextLaunch` è una struct locale con `std::thread` (`<thread>` è già incluso).
  - La lambda `la_report` usa `g`, `la_probe_`, `la_windows_` e `la_cnt_`.
  - `steps` e `G` devono essere visibili nel ramo `chain`.
  - Upstream ha compilato #1120 solo su Linux (ROCm, CUDA V100 e 5080). Nessun build MSVC è riportato.
- `generate.cpp` (1122): `std::function<bool(int)> a_pl_idle`, la lambda `adapt_tick(bool, bool = true)` con argomento di default (MSVC la accetta: upstream l'ha compilata con MSVC + CUDA 13.3) e `ms_now` definito prima del poll da 0,5 ms.
- Per il bit-identico: a parità di seed, confrontare a greedy l'output del binario patchato senza le variabili e quello di 3f85784.

## Rischi e cose da sapere prima delle corse

- **#1122 e lo stallo di #905.** Su 2x 3090 sotto Linux si piantava (`timed out at layer 44`) quando partiva un `nvidia-smi --query-gpu` subito dopo ogni richiesta. Era colpa dei rami di grafo di #904 più le query NVML, e upstream ha poi reso `STRATA_DF_BRANCH` opt-in. **Nel fork `STRATA_DF_BRANCH` è ancora acceso di default su CUDA** (verify.cpp:675). Nelle corse con 1122: niente monitor `nvidia-smi` in parallelo (es. `monitor3060.sh`), oppure un braccio con `STRATA_DF_BRANCH=0`.
- **#1120 su NVIDIA rende poco.** Il guadagno è soprattutto su HIP/RDNA3: una sync più un lancio di grafo costano poco su CUDA. Sulle 2x 5080 le differenze sono nel rumore, in entrambe le direzioni.
- **Le due funzioni si escludono.** #1120 si spegne da sola con `--pipeline-windows`. Le corse sono quindi due bracci separati:
  - (A) `--layer-split` + `STRATA_SPLIT_OVERLAP=1`, con `--elastic` ammesso;
  - (B) `--layer-split` + `--pipeline-windows 2` + `--resident-experts` + `--adapt-async 1`, senza cache elastica.
- **Windows/WDDM.** Il kernel `wait_handoff` gira sullo stadio ≥1, che nel nostro setup non è la scheda col display, per il tempo dello stadio 0 (decine di ms). Il limite di 30 s è solo un paracadute e il watchdog host di 20 s (#267) interviene prima.

## Numeri riportati upstream

**#1120**:
- 2x RX 7900 XTX (gfx1100, ROCm, Linux), Swift 1.5 IQ3_XXS 128K, split 0-25/26-47, risposte greedy da 512 token:
  - codice 53 → 69,6 tok/s;
  - prosa 45 → 57,8 tok/s;
  - nella doc, prima del limite sull'attesa: 70,1 e 55,9;
  - output greedy byte-identico con il flag a 0 e a 1.
- 4x V100 (sm_70), 4 stadi: +1,63% decode (85,93 → 87,33 tok/s), −0,73 ms per finestra.
- 2x RTX 5080 (CUDA): nel rumore. Su PIX 84,8/83,5 e 91,8/93,1; con 2 client 95,8 → 87,5. Su NODE 2 client 92,5 → 101,9.
- 2x RDNA4: nessun guadagno, output byte-identico.

**#1122**: RTX 4060 Ti (layer 0-19) + RTX 5080 (20-47), i9-14900KF, 32 GB, Windows 11. Swift 1.5 IQ3_XXS 160K, KV q4_0,
RAM residente, `--trim-stage-weights`, greedy, 5 prompt × 2 giri, decode in tok/s:

| configurazione | corsa 1 | corsa 2 |
|---|---|---|
| `--pipeline-windows 2` con tier bloccante | 93,5 | 94,1 |
| `--adapt-async 1` col loop seriale | 97,4 | 102,1 |
| tutti e due insieme | 110,2 | 111,3 |

Quindi +18% sulla sola pipeline e +11% sul solo async. Stress test (`STRATA_PIPELINE_FORCE_MISS=2 STRATA_PIPELINE_THETA=0`,
12 richieste da 1500 token): nessun timeout, 1552 giri, 105.435 esperti scambiati, ~40 ms per giro. Non c'è un
confronto esatto perché l'async non è bit-esatto.
