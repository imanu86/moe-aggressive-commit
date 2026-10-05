#!/bin/bash
# PR 930 at 131k (L01/L02), r2 candidate config (adaptive elastic core, DMA), Daily config (PLE table on D:):
# B twice (build-pr930), then A (build-r2cand)
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
CAND="--env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma"
for spec in "L930-a|build-pr930" "L930-b|build-pr930" "L930-r2|build-r2cand"; do
  n=${spec%%|*}; b=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:110])"
  timeout 3000 python -u run_long.py --name "$n" --build $b $CAND > "$n.runlog" 2>&1
  echo "$n ($b) rc=$?"
  grep -a "strata decode timing" "$n/engine.log" | sed 's/ = verify.*draft/ ... draft/' | cut -c1-220
  grep -a "serve: prompt [0-9]\|waited" "$n/engine.log" | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
