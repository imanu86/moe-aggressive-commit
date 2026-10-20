#!/bin/bash
# Passata unica: replay della finestra 3600-4800 s (3 agenti + orchestratore; --dup 2 = 8 agenti) sullo STESSO exe,
# B = config batch attuale + STRATA_PIPED_CONCURRENT=1, A = B + STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1.
# Uso: bash coda_replay_pu.sh [cartella build] [dup]   (senza cartella: l'ultima build-passata-* copiata)
H="$(cd "$(dirname "$0")" && pwd)"
R="$H/../20261019_replay"
L="$H/../20261006_due_schede/bench_lock.py"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
B="${1:-$(ls -dt "$K"/build-passata-* 2>/dev/null | head -1)}"
[ -f "$B/strata.exe" ] || { echo "build non trovata: $B (dare il nome, es. build-passata-5c97ab45)"; exit 1; }
EXE="$B/strata.exe"
DUP="${2:-1}"
echo "exe   : $EXE"
echo "stato : strata.exe vivi (il servizio agenti sulla 8100 li tiene, e tiene bench.lock: va fermato dall'owner):"
tasklist //FI "IMAGENAME eq strata.exe" //NH 2>/dev/null | grep -i strata || echo "  nessuno"
G="--batch 4 --batch-groups 2 --conversation-cache-mib 20480 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700"
cd "$R"
arm() { # tag env
  python -u "$L" "REPLAY-$1" -- python -u replay_trace.py --tag "pu-$1-d$DUP" --exe "$EXE" --t0 3600 --span 1200 --dup "$DUP" --extra "$G" --env "$2" > "$H/replay_pu-$1-d$DUP.run.log" 2>&1
}
arm b1 "STRATA_PIPED_CONCURRENT=1"
arm a1 "STRATA_PIPED_CONCURRENT=1 STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1"
arm b2 "STRATA_PIPED_CONCURRENT=1"
