# Agente 1 — build e correttezza (20/10/2026, dalle 05:56)

 Stato mio (aggiornato 06:32): **compilato sì, installato no, provato solo `--version`/`--help` (niente GPU), misurato no**.
Build 1 `rc 0` in 624 s, exe sha256 `2490f2832c28ef6aec64946f72808180adb0cac0a4839556580fedf70c709e03`.
Copia pronta per le misure: **`corse_2080ti/20261004_routed_keep/build-passata-e29c8065/`** (155 target, sm_75+86 Release;
`strata.exe` + `strata-vision.exe` dal Daily + `source/serve`, `source/tools`; `strata --version` → `strata 0.1.45`).
L'HEAD del worktree è `e29c8065` (solo `serve/`, nessun C++ cambiato): il C++ della copia è quello di `5c97ab45`.
GPU mai toccata, `strata.exe` della 8100 mai fermato, `bench.lock` mai cancellato (deroga dichiarata nel log build).

## Cosa ho fatto

1. `git branch --show-current` = `lab/passata-unica`, HEAD = `5c97ab45`, worktree pulito (un solo file sporco:
   `serve/server.py`, edits dell'agente 3 — non toccato).
2. Build 1 lanciata con lo script giusto:
   `python -u build_lock_noeng.py 'C:/Users/imanu/source/repos/Strata-wt/passata-unica' --jobs 6 --bench-held "servizio agenti 8100 ..."`
   - il bench.lock è tenuto fisso da `servi_agenti.py` («SERVIZIO-AGENTI-8100»): senza `--bench-held` la build
     aspetti per sempre; la deroga è scritta nel log, il lock non è stato toccato.
   - log: `build1b_5c97ab45.log` in questa cartella. Configure completo (sm_75+86, Release, tests off,
     llama.cpp del Daily) ok in 42 s, `rc 0`; `cmake --build` in corso su `build-sm7586\strata.exe`.
   - primo tentativo fallito (rc 1, nessun danno): bash mangiava le barre del path Windows; passarlo tra
     virgolette con `/`.
3. `build-sm7586` è coperto da `.gitignore:12 build*/` → non sporca `git status` degli altri agenti.
4. Nota per chi userà la copia: `copia_build.py` copia anche `source\serve` e `source\tools` dallo stato del
   worktree all'istante della copia → se l'agente 3 ha `server.py` a metà, la copia è quella a metà.
   Usare l'exe; la copia di `serve/` va dichiarata come snapshot.

## Correttezza — `STRATA_PACK_CONCURRENT` spento non cambia nulla (verificato a mano sul diff)

Diff unico: `git diff faa52840 4ee62d09 -- src/program/generate.cpp` (+124/-65, un solo file). Con l'interruttore
spento i percorsi nuovi non vengono mai presi:

| punto del percorso nuovo | perché è spento-invariante |
|---|---|
| `pack_conc` (r.14744-14748) | `getenv("STRATA_PACK_CONCURRENT")` nullo → `false` → `pk_prepare` non chiamato in `read_part` → `pk_run.active` resta false |
| `pk_on` (r.14749) | false → `Cc = C` (righe 14755-14756 identiche a prima, `reserve_prefill(C)`/`reserve_uploads(C)`) |
| `sp.stop_at_chunk` (r.14885) | ramo `else` = la lambda di prima, identica |
| thread lettore (r.14890-14895) | ramo `else` = `force_chunk` + `sp.run(ids+q0, b0-q0, q0)` come prima |
| `pk_finish` (r.14947) | chiamata solo `if (pk_on)`; la riga dopo (`drained`) è la stessa logica di prima, solo estratta in `const bool drained` |
| `q = !pk_on && ...` (r.14953) | con `pk_on` false è l'espressione originale |
| `pk_read` (r.14573-14583) | ora chiama `pk_prepare` + `run_packed` + `pk_finish` in fila: stesse decisioni, stessi valori di `packed` su tutti i rami (`plans.empty()`, `segs.size()==1`, `lend` failed, `run_packed` failed) |
| guardie RAII tolte (`DropUncached`, `ClearPackRows`) | sostituite da `pk_drop_uncached()` e dallo `on_pack_rows = nullptr` di `pk_finish`, chiamati su tutti i rami che prima le facevano scattare (vedi eccezione F1) |

Nessun altro file toccato dalla leva (verificato: `PACK_CONCURRENT` compare solo in `generate.cpp`,
`docs/MULTICHAT.md`, `stack/INDEX.md`, `stack/BLOCKS.md`).

## Segnalazioni per l'agente 2 (generate.cpp è suo: non ho modificato nulla)

**F1 — perdita delle guardie sul ramo di errore (riga 14755).** In `read_part`:
`if (pack_conc && ... && !pk_prepare(...))` ha già fatto `lend(...)`, ha riscritto gli slot di pacco e ha installato
`last_sp.on_pack_rows = [&](...){ ... pk_run ... }` (r.14489). Subito dopo,
`if (use_mtp && !mtp.reserve_prefill(Cc, e)) return false;` esce **senza** `pk_finish` e senza `pk_drop_uncached`:
resta installato un callback che cattura `pk_run` per riferimento. `pk_run` è dichiarato dentro il `for (;;)` di
smistamento (dichiarazione r.14305-14314, il `for (;;)` è a r.12611): all'iterazione dopo è un oggetto nuovo, e
`on_pack_rows` ancora installato sul Prefill punta a memoria morta (e vale anche per un prefill ordinario — è
esattamente il caso che il commento dell'originale `ClearPackRows` chiamava esplicitamente «do not leave a callback
referencing this request installed for the next request or for an ordinary prefill»). Stesso rischio se
`std::thread` (r.14834 o 14887) lancia `std::system_error` prima del `pk_finish` di r.14947.
Fix minimo che suggerisco a lui: `pk_finish(false, 0)` (o `pk_run.active=false; last_sp.on_pack_rows=nullptr;
pk_drop_uncached();`) prima di ogni `return false` fra `pk_prepare` e il `pk_finish` del round.

**F2 — `lend` e `STRATA_PACK_CHUNK>0`.** `pk_prepare` presta `min(total, pk_chunk)` una sola volta (r.14501), e nel
percorso concorrente non c'è il `lend(to - at, ...)` del percorso a pezzi (r.15279): con `STRATA_PACK_CHUNK=N` il
secondo chunk del pacco gira senza prestito nuovo. Default `pk_chunk = 0` (un solo pezzo) → non tocca le corse
previste; da non accendere nel banco B-A-B.

**F3 — una riga di log persa.** Con `pk_on` e `drained` false si esce con `batch_fatal` dopo `pk_finish(false,...)`:
nessuna riga `strata pack:` (voluto: il log si stampa solo `if (ok)`), però le slot restano senza checkpoint e
nessuna riga dice perché. Utile per leggere i log del banco: se non compare `strata pack:` può essere un drain
fallito, non solo «niente da impacchettare».

## Comandi pronti (dopo di me)

Build copiata (eseguita da me, esito sotto nel file): `corse_2080ti/20261004_routed_keep/build-passata-<sha8>/`.
Misura (agente 4, braccia B-A-B; l'agente 1 non lancia corse GPU) — nome di build reale da usare:
`bash corse_2080ti/20261019_passata_unica/coda_lc.sh build-passata-e29c8065`
`bash corse_2080ti/20261019_passata_unica/coda_replay_pu.sh build-passata-e29c8065 1`
Exe diretto se un runner lo chiede:
`corse_2080ti\20261004_routed_keep\build-passata-e29c8065\strata.exe` (sha256 `2490f283…`, 0.1.45, sm_75+86).
Braccio A = `STRATA_PACK_PREFILL=3 STRATA_PIPED_CONCURRENT=1 STRATA_PACK_CONCURRENT=1`; non accendere
`STRATA_PACK_CHUNK` finché F2 non è sistemata.

## Secondo giro di correttezza — `serve/server.py` dell'agente 3 (`e29c8065`)

Prove eseguite da me (solo CPU, niente GPU): `python -m unittest serve.test_pack_gather` → **8/8 ok**;
`serve.test_pack_hint serve.test_admit_order serve.test_control_cancel serve.test_parallel serve.test_prometheus`
→ **47/47 ok**. Lettura del diff reale (`git diff --ignore-cr-at-eol 5c97ab45 e29c8065 -- serve/server.py`:
67+/8-): con `STRATA_PACK_CONCURRENT` spento `PACK_CONCURRENT=false`, `PACK_WAIT_MS=0`, `_pack_gather` esce subito
senza toccare nulla e il conteggio in `_pack_hint` non parte → percorso di rilascio invariato (il `pack=` passato a
`_take_control` serve solo a chiamare `_pack_gather`, che con l'interruttore spento torna 0).

Segnalazioni per l'agente 3 (non ho toccato i suoi file):
- **CRLF su tutto `serve/server.py`**: il commit è a CRLF, il file prima era LF → il diff segna 14457 righe cambiate
  (67 reali). `copia_build.py`/`stack_add.py` e la patch 21 ne escono gonfie. Da ri-normalizzare a LF.
- **P1**: la finestra (default 30 ms) viene scontata **dentro** `_take_control`, dopo il `ctl_epoch += 1` e mentre
  `self.ctl` è tenuto: chi legge per primo paga 30 ms di TTFT prima di mandare il proprio prompt. È il costo scritto
  nel design, ma va misurato come TTFT del primo lettore, non solo come aggregato.
- **P2**: `self.pack_pending` viene azzerato solo in `_pack_gather`; gli `_pack_hint` arrivati quando nessuno tiene
  `self.ctl` restano contati e possono far chiudere una finestra successiva in anticipo (`base >= slots`).
- **P3**: `pack=embeddings is None` è vero anche per le ripartenze del percorso solo (3 punti del diff): una lettura
  corta (gli ultimi token di una già impacchettata) paga comunque la finestra.

## Lettura di `Prefill::run_packed` per l'agente 2 (src/prefill/prefill.cpp:5237-5263)

- `run_packed` mette tutti i segmenti in un `Pack` locale (`pack_ = &p`, guardia `Unpack` che lo azzera su tutti gli
  stage) e poi chiama **`run(...)`**, che in fondo chiama **`drain_pipeline()`** (prefill.cpp:5276-5285): nel percorso
  concorrente il drain del prefill avviene sul thread del lettore mentre il thread host pompa le finestre. Da
  verificare da lui che i due drain (prefill e `pipe_drain` delle finestre, generate.cpp:14946) non si aspettino a
  vicenda.
- Il prestito è `lend(total)` dove `total` = prompt proprio + token degli altri (r.14501): nel braccio A gli slot in
  decode non trovano gli esperti prestati e li calcolano su CPU come fra i pezzi → **il t/s degli scrittori nel ramo
  A va letto come parte del verdetto**, non come rumore.

## Build 2 (`--tests --target all`): fallita per un motivo vecchio, estraneo alla leva

`build2_tests_e29c8065.log`: `rc 1` in 35 s. Errore: `src/kernels/hc_persist_parity.cpp(55,56): error C3861:
'unsetenv' / 'setenv' identificatore non trovato` — MSVC non ha `unsetenv` e quel file include solo `<cstdlib>`.
Non è la leva (la leva tocca solo `src/program/generate.cpp`, che compila): nella stessa condizione si trovano anche
`src/core/arch_defaults_test.cpp`, `src/core/conversation_file_test.cpp`, `src/kernels/decode_cluster_parity.cpp` →
**la build `--tests` di questo branch non è mai girata su Windows**. Non l'ho corretto: bruciava l'ultimo slot di
build e i file non sono miei. Da fare se serve un check C++ su CPU: una piccola shim MSVC (`_putenv_s` / `_unsetenv`)
in quei 3-4 sorgenti di test.
Verificato dopo: `build-sm7586\strata.exe` **non è stato ricompilato** (sha256 ancora `2490f283…`) → la copia
`build-passata-e29c8065` resta valida. Attenzione però: il `CMakeCache` di `build-sm7586` ora ha
`STRATA_BUILD_TESTS=ON`; la prossima build senza `--tests` lo riporta a OFF.

## Check CPU-only eseguiti (niente GPU, niente slot build)

- `tests/program/batch_read_test.cpp` compilato a parte (`cl /std:c++17`, header-only) e eseguito: **`batch_read_test: ok`**
  → le regole di `batch_read_piece`, `piped_read_piece`, `concurrent_read_off`, `piped_read_lead_in` (le funzioni che
  il percorso concorrente usa) passano col codice della leva in posto.
- `git apply --check --reverse stack/21-pack-concurrent.patch` sull'HEAD: **ok** → la patch registrata nel `stack/`
  è esattamente il codice del worktree. Se l'agente 2 committa C++, la 21 va rigenerata
  (`20261019_passata_unica/stack_add.py <worktree> <sha> entry21.json`) prima di chiamarla verificata.
- `strata.exe --version` → `strata 0.1.45`; `--help` ok.

## Ricompilazioni

**3 build di mandato: 1 usata (ok), 2 usata (fallita per i test, exe intatto), 1 rimasta** per il C++ dell'agente 2.
Giro di build: `python -u build_lock_noeng.py 'C:/Users/imanu/source/repos/Strata-wt/passata-unica' --jobs 6
--bench-held "servizio agenti 8100: bench.lock tenuto da servi_agenti.py"` (incrementale su `build-sm7586`, ~2-4 min
dopo la prima), poi `python -u copia_build.py 'C:/Users/imanu/source/repos/Strata-wt/passata-unica' passata "<nota>"`
→ `build-passata-<sha8>`; `copia_build.py` **rifiuta il lavoro se il worktree ha file non committati** (a 06:29 ha
bloccato finché l'agente 3 non ha committato `serve/server.py`: coordinate i commit).
Controllo `git log` ogni ~20 min. Nessun C++ nuovo è arrivato fino alle 07:4x:HEAD resta `e29c8065`.
