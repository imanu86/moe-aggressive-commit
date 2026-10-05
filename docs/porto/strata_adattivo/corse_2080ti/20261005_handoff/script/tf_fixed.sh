#!/bin/bash
# Teacher forcing with a fixed expert placement (fixed cache, no adaptive swaps, fixed PCIe share): two runs of the
# same exe must give identical log-probs, so any difference between builds is the change itself.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
FIX="--drop-opt=--elastic --set-opt=--expert-cache=5000 --set-opt=--adapt-every=0 --set-opt=--pcie-frac=0.36"
for spec in "$@"; do
  n=${spec%%|*}; b=${spec#*|}
  for t in code explain; do
    python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)" 
    timeout 900 python -u run_keep.py --name "$n-$t" --arm A --task $t $b --teacher A-$t $FIX > "$n-$t.runlog" 2>&1
    echo "$n-$t rc=$?"
  done
done
