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
Misura (agente 4, braccia B-A-B; l'agente 1 non lancia corse GPU):
`bash corse_2080ti/20261019_passata_unica/coda_lc.sh build-passata-<sha8>`
`bash corse_2080ti/20261019_passata_unica/coda_replay_pu.sh build-passata-<sha8> 1`

## Ricompilazioni

Max 3 build (1 già partita). Controllo `git log` ogni ~20 min; build incrementale su `build-sm7586` (ninja), quindi
veloce. Ogni build: log in questa cartella `buildN_<sha8>.log` con `rc` e `sha256` dell'exe.
