#!/bin/bash
# 131k L01/L02: B = port/0139 (upstream 0.1.39 + fork), twice; then A = the Daily's own exe.  Whole arena registered.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for spec in "LP-port1|--build build-p0139" "LP-port2|--build build-p0139" "LP-daily|--daily-exe"; do
  n=${spec%%|*}; o=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-140
  timeout 3000 python -u run_long.py --name "$n" $o --env STRATA_ARENA_PIN_GIB=64 > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a -E "elastic: [+-]" "$n/engine.log" | tail -1 | cut -c1-150
  grep -a "strata decode timing" "$n/engine.log" | cut -c1-260
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s ttft %.0f s' % (q['case'], q['decode_tps'], q['ttft_s']) for q in r['requests']))"
done
