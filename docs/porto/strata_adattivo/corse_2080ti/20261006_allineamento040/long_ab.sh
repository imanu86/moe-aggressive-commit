#!/bin/bash
# 131k L01/L02 on the Daily config, one run per arm, in the order given (B first).
#   bash long_ab.sh "NAME|run_long args" ["NAME|run_long args" ...]
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for spec in "$@"; do
  n=${spec%%|*}; b=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:110])"
  timeout 3000 python -u run_long.py --name "$n" $b > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a "strata decode timing" "$n/engine.log" | cut -c1-200
  grep -a "serve: prompt [0-9]" "$n/engine.log" | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
