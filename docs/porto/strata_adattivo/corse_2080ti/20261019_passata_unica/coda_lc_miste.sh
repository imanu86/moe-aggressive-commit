#!/bin/bash
# Passata unica — banco «4 agenti a contesti misti» (2k, 8k, 30k, 90k di contesto; 1-4k token nuovi), B-A-B sullo STESSO exe.
#   B = config batch attuale + STRATA_PIPED_CONCURRENT=1
#   A = B + STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1
# Giri per braccio: 2 misti (2 lettori + 2 scrittori, ruoli scambiati) + 1 burst (4 letture insieme con 1 scrittore di
# supporto).  Criteri: tempo totale delle 4 letture, t/s di decode degli altri durante, token identici (parita`).
# Uso: bash coda_lc_miste.sh [cartella build]     (senza argomento: l'ultima build-passata-* trovata)
# Bracci: b1/b2 = base | a1 = pacco + finestra server (30 ms di default) | a2 = pacco SENZA finestra server
#   (STRATA_PACK_WAIT_MS=0: isola la sola leva del motore) | a3 = pacco con 2 slot di pacco (se la VRAM va a 0).
#   STRATA_PACK_CHUNK NON va acceso: l'agente 1 ha trovato che nel percorso concorrente il secondo chunk gira senza
#   prestito (F2 nel suo doc).  Braccio singolo o extra: ARMS="a2" bash coda_lc_miste.sh <cartella>
H="$(cd "$(dirname "$0")" && pwd)"
L="$H/../20261006_due_schede/bench_lock.py"
K="$(cd "$H/../20261004_routed_keep" && pwd -W)"
B="${1:-$(ls -dt "$K"/build-passata-* 2>/dev/null | head -1)}"
[ -f "$B/strata.exe" ] || { echo "build non trovata: $B (dare il nome, es. build-passata-5c97ab45)"; exit 1; }
EXE="$B/strata.exe"
G="--batch 4 --batch-groups 2 --conversation-cache-mib 20480 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700"
ARMS="${ARMS:-b1 a1 b2}"
echo "exe   : $EXE"
[ -f "$B/build.json" ] && python -c "import json,sys;c=json.load(open(sys.argv[1],encoding='utf-8'));print('build :',c['note']);print('sha256:',c['executable_sha256'][:16])" "$B/build.json"
echo "stato : lock GPU = $([ -f /d/ds4_work/strata/lab_locks/bench.lock ] && echo occupies || echo libero) | strata.exe vivi:"
tasklist //FI "IMAGENAME eq strata.exe" //NH 2>/dev/null | grep -i strata || echo "  nessuno"
echo "        (il servizio agenti sulla 8100 tiene bench.lock e un strata.exe: se resta, i bracci aspettano per sempre"
echo "         - va fermato dall'owner prima di partire, e riacceso dopo)"
cd "$H"
arm() { # tag env
  echo "== braccio $1 =="
  python -u "$L" "LCM-$1" -- python -u -X utf8 letture_miste.py --tag "m-$1" --exe "$EXE" --extra "$G" --env "$2" > "lc_m_$1.run.log" 2>&1
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
echo "verdetto: python pu_verdict.py $(echo $ARMS | sed -E 's/([^ ]+)/m-\1/g')"
