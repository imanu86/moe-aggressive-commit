#!/bin/bash
# one 131k L01/L02 on main + PLE diagnostics, the candidate configuration (core adapt on, DMA)
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for n in LX-diag1; do
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-100
  timeout 3000 python -u run_long.py --name "$n" --build build-plediag --env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a "ple io\|waited\|serve: prompt" "$n/engine.log" | cut -c1-400
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
