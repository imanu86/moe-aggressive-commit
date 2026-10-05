#!/bin/bash
# 131k L01/L02 (run_long.py), Daily config with the whole arena registered: auto expert cache vs an ~11.6 GiB start
# (explicit --expert-cache sized by --vram-reserve-mib 3730; the elastic cache stays on).  B, B, then A.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
C116="--set-opt=--expert-cache=9000 --set-opt=--vram-reserve-mib=3730"
for spec in "LB-c116a|$C116" "LB-c116b|$C116" "LB-auto|"; do
  n=${spec%%|*}; o=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-140
  timeout 3000 python -u run_long.py --name "$n" --build build-vram1 --env STRATA_ARENA_PIN_GIB=64 --env STRATA_TRACE=1 $o \
    > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a -E "expert cache [0-9]+ slots|elastic: [+-]" "$n/engine.log" | tail -2 | cut -c1-150
  grep -a "after a request" "$n/engine.log" | tail -1 | cut -c1-200
  grep -a "strata decode timing" "$n/engine.log" | cut -c1-330
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s ttft %.0f s' % (q['case'], q['decode_tps'], q['ttft_s']) for q in r['requests']))"
done
