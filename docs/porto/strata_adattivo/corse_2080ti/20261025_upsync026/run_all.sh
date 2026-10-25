#!/bin/bash
# Ordine B-A-B: Daily 0.1.43 r2, A (0.2.6 pura), B (0.2.6 + pila), Daily. Ogni corsa ~7-15 min. Il runner prende bench.lock da solo.
# Guardie: niente corsa se esiste lab_locks\pause o se gira un strata.exe (il runner a fine corsa fa taskkill /IM strata.exe: ucciderebbe il Daily).
# Non chiude Jump Desktop ne' OktoCGControl; priorita' normale. STRATA_NO_PRESET=1: niente tuning salvato del server.
H="$(cd "$(dirname "$0")" && pwd)"; BC=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti
R=$(cygpath -w $BC/20261004_routed_keep)
export STRATA_NO_PRESET=1
run() {  # tag config build
  [ -e /d/ds4_work/strata/lab_locks/pause ] && { echo "PAUSE: mi fermo"; exit 3; }
  tasklist //FI "IMAGENAME eq strata.exe" //NH | grep -qi strata.exe && { echo "strata.exe in vita: mi fermo"; exit 4; }
  echo "$(date +%H:%M) inizio $1 (Jump sessione 1: $(powershell -NoProfile -Command '(Get-Process JumpConnect | Where-Object SessionId -eq 1 | Measure-Object).Count') processi; OktoCGControl aperto)"
  python -u $BC/20261019_banco_comunita/community_bench.py "$1" "$2" "$3"
  echo "$(date +%H:%M) fine $1"
  { echo "Jump Desktop e OktoCGControl aperti durante la corsa (nota dell'agente, 25/10)"; } >> $BC/20261019_banco_comunita/$1/ambiente.txt
}
run up026-daily-1 'D:\ds4_work\strata\Strata\strata-0143-daily.json' 'D:\ds4_work\strata\Strata\build-0143-daily'
run up026-A-pura  "$(cygpath -w $H/config-A-pura-default.json)" "$R\build-up026-4b9e05a2"
run up026-B-pila  "$(cygpath -w $H/config-B-pila-daily.json)"   "$R\build-up026pila-ffe66174"
run up026-daily-2 'D:\ds4_work\strata\Strata\strata-0143-daily.json' 'D:\ds4_work\strata\Strata\build-0143-daily'
