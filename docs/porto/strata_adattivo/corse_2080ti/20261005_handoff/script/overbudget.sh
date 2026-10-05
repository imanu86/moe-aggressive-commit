#!/bin/bash
# Fixed expert caches of growing size (no elastic, explicit --expert-cache: no post-write shrink), to find where the
# WDDM budget is crossed and decode collapses (paging to shared memory).  cap = free at sizing - reserve.
set -u
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for spec in "OB-auto|auto" "OB-r5260|5260" "OB-r4750|4750" "OB-r4240|4240" "OB-r3730|3730" "OB-r2700|2700"; do
  n=${spec%%|*}; r=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-140
  if [ "$r" = "auto" ]; then
    EX="--drop-opt=--elastic"
  else
    EX="--drop-opt=--elastic --set-opt=--expert-cache=9000 --set-opt=--vram-reserve-mib=$r"
  fi
  timeout 900 python -u run_keep.py --name "$n" --arm A --task code --build build-vram1 --env STRATA_ARENA_PIN_GIB=64 \
    --env STRATA_TRACE=1 $EX > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a -E "expert cache [0-9]+ slots|after a request|after the verifier" "$n/engine.log" | cut -c1-200
  L=$(grep -a "strata decode timing" "$n/engine.log" | tail -1)
  python -c "
import json,re; l=json.load(open('$n/result.json'))['last']; t='''$L'''
m=re.search(r'([0-9.]+) ms/window.*?GPU-reach wait ([0-9.]+).*?CPU ([0-9.]+)\].*?CPU experts ([0-9.]+).*?VRAM hits ([0-9.]+), PCIe ([0-9.]+)', t)
print('  =>', round(l['generated']/l['decode_ms']*1000,1), 't/s, win', m.group(1), 'gpuwait', m.group(2), 'cpu', m.group(3), 'cpuexp', m.group(4), 'vram', m.group(5), 'prefill', round(l['prompt_tokens']/l['prompt_ms']*1000), 't/s')" 2>&1 | tail -1
done
