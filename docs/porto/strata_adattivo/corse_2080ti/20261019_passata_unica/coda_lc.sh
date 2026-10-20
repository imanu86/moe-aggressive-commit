#!/bin/bash
# Passata unica, passo 1: B-A-B sullo STESSO exe (build-passata-<sha>), 4 lettori (2-4k nuovi su R0..R3 in cache) + 2 scrittori.
#   B = config batch attuale + STRATA_PIPED_CONCURRENT=1
#   A = B + STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1
# Ogni braccio prende bench.lock (bench_lock.py). Uso: bash coda_lc.sh [cartella build]
#   senza argomento: l'ultima build-passata-* in 20261004_routed_keep (quella copiata dall'agente 1 con copia_build.py)
#   ARMS="b1" bash coda_lc.sh <cartella>  -> solo un braccio (ritorno)
# Bracci: b1/b2 = base | a1 = pacco + finestra server (30 ms) | a2 = pacco senza finestra (STRATA_PACK_WAIT_MS=0)
#   | a3 = pacco con 2 slot (se la VRAM va a 0).  STRATA_PACK_CHUNK non va acceso (F2 del doc agente1).
H="$(cd "$(dirname "$0")" && pwd)"
L="$H/../20261006_due_schede/bench_lock.py"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
B="${1:-$(ls -dt "$K"/build-passata-* 2>/dev/null | head -1)}"
[ -f "$B/strata.exe" ] || { echo "build non trovata: $B (dare il nome, es. build-passata-5c97ab45)"; exit 1; }
EXE="$B/strata.exe"
G="--batch 4 --batch-groups 2 --conversation-cache-mib 20480 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700"
echo "exe   : $EXE"
[ -f "$B/build.json" ] && python -c "import json,sys;c=json.load(open(sys.argv[1],encoding='utf-8'));print('build :',c['note']);print('sha256:',c['executable_sha256'][:16])" "$B/build.json"
echo "stato : strata.exe vivi (il servizio agenti sulla 8100 li tiene, e tiene bench.lock: va fermato dall'owner):"
tasklist //FI "IMAGENAME eq strata.exe" //NH 2>/dev/null | grep -i strata || echo "  nessuno"
ARMS="${ARMS:-b1 a1 b2}"
cd "$H"
arm() { # tag env
  echo "== braccio $1 =="
  python -u "$L" "LC-$1" -- python -u -X utf8 letture_concorrenti.py --tag "$1" --exe "$EXE" --extra "$G" --env "$2" > "lc_$1.run.log" 2>&1
  echo "  esito $1: $?"
}
for t in $ARMS; do
  case "$t" in
    b1|b2) arm "$t" "STRATA_PIPED_CONCURRENT=1" ;;
    a1)    arm "$t" "STRATA_PIPED_CONCURRENT=1 STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1" ;;
    a2)    arm "$t" "STRATA_PIPED_CONCURRENT=1 STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1 STRATA_PACK_WAIT_MS=0" ;;
    a3)    arm "$t" "STRATA_PIPED_CONCURRENT=1 STRATA_PACK_PREFILL=2 STRATA_PACK_CONCURRENT=1" ;;
    *) echo "braccio sconosciuto: $t"; exit 1 ;;
  esac
done
echo "verdetto: python pu_verdict.py $ARMS   (e parita': cmp lc_b1/par_*.txt lc_a1/par_*.txt)"
