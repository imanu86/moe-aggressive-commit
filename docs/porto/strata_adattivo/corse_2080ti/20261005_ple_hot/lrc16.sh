#!/bin/bash
# PLE row cache 16M rows (1.4 GB) vs 1M (today), cold 131k L01/L02, r2 + #930, candidate config, PLE table on D::
# B twice, then A.  Same bytes read: only the row-cache hits and the SSD reads may change.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
CAND="--env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma"
for spec in "LRC16-a|16777216" "LRC16-b|16777216" "LRC1M|"; do
  n=${spec%%|*}; rc=${spec#*|}
  extra=()
  [ -n "$rc" ] && extra=("--set-opt=--ple-row-cache=$rc")
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:110])"
  timeout 3000 python -u run_long.py --name "$n" --build build-pr930 $CAND "${extra[@]}" > "$n.runlog" 2>&1
  echo "$n (row cache ${rc:-1048576}) rc=$?"
  grep -a "strata decode timing" "$n/engine.log" | sed 's/ = verify.*draft/ ... draft/' | cut -c1-220
  grep -a "decode PLE after\|serve: prompt [0-9]\|waited" "$n/engine.log" | cut -c1-300
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], 'startup %.0f s' % r.get('startup_s', 0), ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
