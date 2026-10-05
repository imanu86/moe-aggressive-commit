#!/bin/bash
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for spec in "SC-auto1|" "SC-c116a|--set-opt=--expert-cache=9000 --set-opt=--vram-reserve-mib=3730" "SC-c116b|--set-opt=--expert-cache=9000 --set-opt=--vram-reserve-mib=3730" "SC-auto2|"; do
  n=${spec%%|*}; o=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-140
  timeout 2400 python -u run_session.py --name "$n" --build build-vram1 --env STRATA_ARENA_PIN_GIB=64 --env STRATA_TRACE=1 $o > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a -E "expert cache [0-9]+ slots|elastic: [+-]" "$n/engine.log" | tail -2 | cut -c1-160
  grep -a "after a request" "$n/engine.log" | tail -1 | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
q=r['requests']; tps=[x['decode_tps'] for x in q]; hit=[x['hit_rate'] for x in q if x['hit_rate']]
print('  =>', r['status'], 'decode t/s', [round(t,1) for t in tps], 'mean', round(sum(tps)/len(tps),1), 'hit', round(sum(hit)/len(hit),3))"
done
