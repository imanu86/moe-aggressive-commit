#!/bin/bash
# 6/10: the repetition loops of the night turn benchmark came with greedy decoding inside the thinking. Same turns on
# the r2 (same arm as TURNI-r2), one run each: (1) thinking off, greedy; (2) thinking on with the sampling the model
# file itself recommends (GGUF general.sampling.*: temp 1.0, top_p 0.95, top_k 20).
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
R2="--build build-pr949 --env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma --set-opt=--pool-tasks=96"
pools() { powershell -NoProfile -Command "\$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; '  pool kernel: {0:N2} GB paginato, {1:N2} GB non paginato' -f (\$m.PoolPagedBytes/1GB),(\$m.PoolNonpagedBytes/1GB)"; }
for spec in "TURNI-r2-nothink|--no-think" "TURNI-r2-temp|--temp 1.0 --top-p 0.95 --top-k 20"; do
  n=${spec%%|*}; extra=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:120])"
  pools
  echo "$n start $(date +%H:%M)"
  timeout 14400 python -u run_turns.py --name "$n" $R2 $extra > "$n.runlog" 2>&1
  echo "$n rc=$? end $(date +%H:%M)"
  grep -a '"turn"' "$n.runlog" | cut -c1-200
  pools
done
