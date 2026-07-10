# patches/ — nota di servizio: la serie canonica vive in reap-loop

**La serie canonica delle patch runtime ds4 è `reap-loop/patches/ds4/`** (repo
`C:\Users\imanu\source\repos\reap-loop`): vedi il `patches/README.md` lì per la mappa completa
numero-per-numero, gli hash e le regole. Questa directory contiene snapshot storici e materiale
specifico delle arene moe. Stato verificato il 2026-07-10.

Cosa c'è qui (branch `main` / `cascade-memory/harness`, identici su `patches/`):

- `ds4/0001..0008` — copie identiche alle canoniche di reap-loop (stessi hash).
- `ds4/0009`, `ds4/0010` — **revisioni divergenti** (hash 57ce10ce / d135f38e): stessi hunk delle
  canoniche ma line-ending CRLF e author `dspark-track <imanu86@gmail.com>`. **Non applicarle**:
  usare le copie canoniche di reap-loop (b69b9738 / f741a526, LF, author neutro).
- `ds4/archive/2026-07-04-stall-instrumentation-uncommitted.patch` (ad71e31b) — storico, fuori serie.
- `ds4/ds4_spex_predict.c|.h`, `ds4/upstream-pr497-single-token-selected-load.diff` — supporto,
  identici a reap-loop.

Branch:

- `reap/k91-coding-vram`: aggiunge `0011-reap-runtime-mask` / `0012-reap-sensor-s1` (copie identiche
  alle canoniche di reap-loop) e `0015-spex-hidden-probe-wiring.apply.py` (924007a4): script Python
  di wiring per il ds4.c del worktree k91, non una patch di serie — il numero 0015 collide con due
  patch canoniche in reap-loop.
- `dspark/mtp-spec-dec`: serie parallela MTP/spec-dec con **numerazione in collisione**:
  `0011-dspark-mtp-host-statics` e `0012-dspark-mtp-no-register-diagnostic` non c'entrano con le
  0011/0012 REAP. Si applicano solo nell'arena dspark.

Regola: le nuove patch runtime ds4 nascono in `reap-loop/patches/ds4/` col prossimo numero libero
(0019+), mai riusando numeri già presi.
