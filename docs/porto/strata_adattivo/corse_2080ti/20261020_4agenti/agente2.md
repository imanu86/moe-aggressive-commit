# Agente 2 — motore: generate.cpp + pacco C++ (run_packed / pk_prepare / pk_finish / pk_read / batch_read_piece)

2026-10-20. Worktree `Strata-wt\passata-unica`, branch `lab/passata-unica`, HEAD `5c97ab45` (= origin).
Compilato no, installato no, provato no, misurato no (la build è dell'agente 1).

## Esito principale

**Il bug noto è già corretto in HEAD (`4ee62d09`), e la mia verifica statica non ha trovato varianti residue.**
Nessuna modifica a `src/program/generate.cpp` in questo giro.

### Il bug com'era (faa52840) e dov'è chiuso ora

- In faa52840 il ramo `if (piped && pr_conc && req_imgs.empty())` (r.14698) finiva con `return true` (r.~14937)
  **prima** del blocco `piece_now` → `pk_read` (r.14986-14990): con `STRATA_PIPED_CONCURRENT=1` la lettura
  concorrente usciva senza mai impacchettare → 0 righe `strata pack:` in `pack3-conc` (r9).
- In HEAD: `pk_prepare` gira sul thread host prima del reader (r.14748), il reader chiama
  `sp.run_packed(pk_run.segs)` al posto di `sp.run` (r.14891), `pk_finish` gira dopo `reader.join()` +
  `pipe_drain()` (r.14947) **su ogni uscita** (il distruttore `ReadEnd` joina il reader anche per eccezione).
  `pk_read` (r.14581) resta il tre in fila per il percorso senza concorrenza.

### Verifica statica dell'invariante «una passata per layer, esperti letti una volta»

- `Prefill::run_packed` (`src/prefill/prefill.cpp:5237`): concatena i segmenti in UN flusso di token con
  `row_seg`/`row_pos` e chiama una sola `run()`.
- `run_impl` (prefill.cpp:2380+): il chunk T (righe di tutti i segmenti) attraversa il layer una volta sola;
  i `PackSub` (r.2680) sezionano il chunk solo per GDN/conv/K-V/attenzione per sessione (r.2941, 3154, 4955-5044);
  gli esperti MMQ del chunk sono ridequantizzati una volta per il flusso intero.
- Nel ramo concorrente: con `pk_on` la lettura intera `[a0,b0)` + tutti i segmenti BHINT vanno in UN
  `run_packed` (r.14891), il ciclo `for (q0…)` fa un solo giro (`q = b0`, r.14965), quindi 2-4 lettori =
  una passata di chunk per layer. Con `STRATA_PACK_CHUNK=N` la passata unica è per chunk di ~N token
  (pipeline dei due stadi), come da design.

### Controlli accessori (tutti a posto)

- **Doppio lend**: il giro esterno dà già `lend(to-at)` (generate.cpp:15279), `pk_prepare` ridà `lend(total)`
  (r.14501): lend è idempotente («its current loan already covers this → continue», r.14200; altrimenti
  refill_one + relayout). Nessun prestito doppio; `Cc = max(sp.chunk(),1)` (r.14750) segue l'eventuale relayout.
- **BYIELD con pk_on**: `stop_at_chunk = nullptr` (r.14880) e `q = b0` → il yield non è preso, come da design
  («the stop would land in the packed row stream»); la riga BYIELD consumata non produce un give-way fantasma
  (`q < b0` fa da guardia, r.14978).
- **Ciclo di vita callback**: `on_pack_rows` installato in `pk_prepare` solo dopo il lend riuscito;
  `pk_finish` lo azzera sempre prima di ogni altra cosa (r.14538-14539); `pk_drop_uncached` su ogni
  fallimento (lend, restore, read). Contratto segmento: `on_pack_rows(u.seg, …)` (prefill.cpp:5034) ↔
  `seg_plan[seg] → plans` con guardia `seg_plan[seg] >= plans.size()` (r.14521) — combacia.
- **bhint**: `pk_hint_add` (generate.cpp:11718) deduplica e limita la coda a `2·pks.size()+2`; le righe BHINT
  arrivate durante la finestra restano per la lettura successiva (limite noto, «Passi dopo»).
- `batch_read_piece` / `piped_read_piece` (include/strata/program/batch_read.hpp): aritmetica pura, testata in
  `tests/program/batch_read_test.cpp`; `piped → 0` è ciò che fa cadere la lettura nel ramo pacco. Il pack è
  saltato solo quando `planned` (layer split con piano) o con `STRATA_PIPED_READ_PIECE>0`: coerente col design.
- Equilibrio parentesi nei blocchi nuovi (14290-14600, 14739-14990) a posto; `SIZE_MAX` già usato nel file.

## File toccati

- Solo questo doc. `src/program/generate.cpp`, `src/prefill/prefill.cpp`,
  `include/strata/program/batch_read.hpp`: **nessuna modifica** (la correzione è già in `4ee62d09`).

## Comandi di misura pronti (per dopo la build dell'agente 1)

Build attesa: `python corse_2080ti/20261006_due_schede/build_lock_noeng.py C:\Users\imanu\source\repos\Strata-wt\passata-unica --jobs 4`
poi `copia_build.py … passata "patch 21 pack-concurrent, <sha8 HEAD>"` → `build-passata-<sha8>`.

1. Banco B-A-B: `bash corse_2080ti/20261019_passata_unica/coda_lc.sh build-passata-<sha8>`
   - verifica specifica del pezzo 2: righe `strata pack:` DEVONO comparire **solo in lc_a1**
     (braccio A = `STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1`) — sono la firma che il ramo
     concorrente ora chiama il pacco; se in a1 ce ne sono 0 mentre `read … on a thread of its own`
     c'è, il bug è ancora vivo:log in `lc_a1/engine.log`.
   - riga attesa: `strata pack: N tokens of this prompt read with K prompts sent ahead (M tokens: @parked:…)`
     con K fino a 3 (4 lettori = il proprio + 3 hint; i pack slot = STRATA_PACK_PREFILL).
2. Replay: `bash corse_2080ti/20261019_passata_unica/coda_replay_pu.sh build-passata-<sha8> 1` e `… 2`.
3. Se l'agente 1 vede errori di compilazione: il blocco è `pk_prepare`/`pk_finish`/`pk_read`
   (generate.cpp r.14290-14600) e il blocco `STRATA_PACK_CONCURRENT` nel ramo concorrente
   (r.14739-14990); `git diff faa52840 4ee62d09` lo mostra intero.
