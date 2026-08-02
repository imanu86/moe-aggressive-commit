#!/usr/bin/env bash
# Incatena le onde dal lotto DA al lotto A, in gruppi di AMPIEZZA.
# Salta i lotti gia' fatti, cosi' e' riavviabile senza rifare lavoro.
#
#   ./pilota.sh 5 119 10
set -u
QUI=$(cd "$(dirname "$0")" && pwd)
DA=${1:-1}; A=${2:-119}; W=${3:-10}

n=$DA
while [ "$n" -le "$A" ]; do
  fine=$((n + W - 1))
  [ "$fine" -gt "$A" ] && fine=$A
  echo "=== onda $n-$fine  ($(date +%H:%M:%S)) ==="
  bash "$QUI/onda.sh" "$n" "$fine" 2>&1 | grep -E "righe|VUOTO|gia'" | tail -"$W"
  n=$((fine + 1))
done

fatte=$(ls -1 "$QUI/../../../ds4-port/lotti/SCHEDE_"*.tsv 2>/dev/null | wc -l)
echo "=== FINITO: $fatte schede su $A lotti ==="
