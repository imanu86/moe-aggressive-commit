#!/usr/bin/env bash
# Lancia un'onda di agenti Codex sui lotti indicati, in parallelo.
#
#   ./onda.sh 1 10        lotti dal 1 al 10
#   ./onda.sh 11 20
#
# Ogni agente scrive `lotti/SCHEDE_NNN.tsv` dentro la radice del worktree, che e'
# l'unico posto in cui il sandbox lo lascia scrivere.
set -u
R=/c/Users/imanu/source/repos/moe-aggressive-commit/ds4-port
DA=${1:?primo lotto}
A=${2:?ultimo lotto}

pids=()
for n in $(seq -w "$DA" "$A"); do
  n=$(printf "%03d" "$((10#$n))")
  m="$R/lotti/lotto_$n.md"
  [ -f "$m" ] || { echo "  lotto $n: manca il mandato"; continue; }
  [ -s "$R/lotti/SCHEDE_$n.tsv" ] && { echo "  lotto $n: gia' fatto"; continue; }

  {
    printf 'Leggi il mandato in lotti/lotto_%s.md e ESEGUILO.\n' "$n"
    printf 'Scrivi il risultato in lotti/SCHEDE_%s.tsv (percorso relativo alla radice).\n\n' "$n"
    cat "$m"
  } | codex exec -C "$R" -s workspace-write - > "/tmp/onda_$n.log" 2>&1 &
  pids+=($!)
  echo "  lotto $n avviato (pid $!)"
done

echo "  --- ${#pids[@]} agenti in volo, attendo ---"
for p in "${pids[@]}"; do wait "$p"; done

echo "  --- esito ---"
for n in $(seq -w "$DA" "$A"); do
  n=$(printf "%03d" "$((10#$n))")
  f="$R/lotti/SCHEDE_$n.tsv"
  if [ -s "$f" ]; then
    printf "  %s  %3s righe\n" "$n" "$(wc -l < "$f")"
  else
    printf "  %s  VUOTO\n" "$n"
  fi
done
