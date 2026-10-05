#!/bin/bash
# PLE table (shard 2) on D: (SATA) vs C: (NVMe, DRAM-less) - r2 candidate config, 131k L01/L02: B twice, then A
# Usage: ple_d.sh [suffix]   (run names LPD-d1<suffix>, LPD-d2<suffix>, LPD-c<suffix>)
# --ple-gguf alone fails ("native dense: duplicate split shard number"): the engine lists every shard beside
# --native (shard 2 in Downloads) and appends --ple-gguf. With --native-dense-gguf given explicitly (shard 1 +
# the D: copy of shard 2) the list is not built and the D: copy is the only shard 2 that is read.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
S1='C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'
PLE_D='D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf'
X=${1:-}
cd "$D" || exit 1
CAND="--env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma"
for spec in "LPD-d1$X|D" "LPD-d2$X|D" "LPD-c$X|C"; do
  n=${spec%%|*}; where=${spec#*|}
  extra=()
  [ "$where" = D ] && extra=("--set-opt=--ple-gguf=$PLE_D" "--add-opt=--native-dense-gguf=$S1" "--add-opt=--native-dense-gguf=$PLE_D")
  python -c "
from run_keep import snapshot; import json,time,shutil
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
c=shutil.disk_usage('C:/')
print(json.dumps(s)[:100], '| C: free %.1f GB (%.1f%%)' % (c.free/1e9, 100*c.free/c.total))"
  timeout 3000 python -u run_long.py --name "$n" --build build-r2cand $CAND "${extra[@]}" > "$n.runlog" 2>&1
  rc=$?
  echo "$n ($where) rc=$rc"
  if [ $rc -ne 0 ] && [ "$where" = D ]; then tail -3 "$n.runlog"; echo "B fallita: A saltata"; exit 1; fi
  grep -a "PLE on" "$n/engine.log" | cut -c1-200
  grep -a "strata decode timing" "$n/engine.log" | sed 's/ = verify.*draft/ ... draft/' | cut -c1-220
  grep -a "decode PLE after\|serve: prompt [0-9]\|waited" "$n/engine.log" | cut -c1-330
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], 'startup %.0f s' % r.get('startup_s', 0), ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
