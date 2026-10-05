#!/bin/bash
# One Daily-config run with nvidia-smi sampled every 2 s: the whole card's VRAM in use vs what the engine sees free.
set -u
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
N=${1:-TR-smi-code}
rm -f "$N.samples"
(
  while true; do
    echo "$(date +%T) $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits)" >> "$N.samples"
    sleep 2
  done
) &
SMI=$!
sleep 4
timeout 900 python -u run_keep.py --name "$N" --arm A --task code --daily-exe --env STRATA_ARENA_PIN_GIB=64 \
  --env STRATA_TRACE=1 > "$N.runlog" 2>&1
echo "rc=$?"
sleep 4
kill "$SMI" 2>/dev/null
grep -a -E "expert cache auto|expert cache [0-9]+ slots|VRAM free with everything|elastic: \+|MiB free after the weights" "$N/engine.log" | cut -c1-150
echo "--- nvidia-smi MiB used over the run (count x value):"
awk '{print $2}' "$N.samples" | tr -d ',' | uniq -c | tr '\n' ' '
echo
