#!/bin/bash
# 131k L01/L02 on the installed Daily exe (build-ship139), whole arena: MTP drafting variants first (B), the Daily's
# --spec 4 --spec-min-p 0.5 last (A).  Greedy, so the output is the same; the figure is tokens per window.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for spec in "LM-p03|--set-opt=--spec-min-p=0.3" "LM-s6p03|--set-opt=--spec=6 --set-opt=--spec-min-p=0.3" "LM-p02|--set-opt=--spec-min-p=0.2" "LM-daily|"; do
  n=${spec%%|*}; o=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-100
  timeout 3000 python -u run_long.py --name "$n" --build build-ship139 --env STRATA_ARENA_PIN_GIB=64 $o > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a "strata decode timing" "$n/engine.log" | sed 's/ = verify.*draft/ ... draft/' | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s acc %s' % (q['case'], q['decode_tps'], (q['last'].get('drafts_accepted'), q['last'].get('drafts_offered'))) for q in r['requests']))"
done
