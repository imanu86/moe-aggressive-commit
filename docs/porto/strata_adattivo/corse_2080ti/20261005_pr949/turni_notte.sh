#!/bin/bash
# Night of 5/10: final turn benchmark (HANDOFF_5_OTTOBRE_SERA §6.2). B first, then A.
# B = r2 candidate: build-pr949 (r2 + #930 + #949), adaptive elastic core, DMA, --pool-tasks 96.
# A = Daily r1 exe. Both read the Daily config (PLE table on D:, --ple-row-cache 16777216).
# Also the DMA endurance test (#31): a stuck engine shows as no progress in the run's engine.log.
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
pools() { powershell -NoProfile -Command "\$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; '  pool kernel: {0:N2} GB paginato, {1:N2} GB non paginato' -f (\$m.PoolPagedBytes/1GB),(\$m.PoolNonpagedBytes/1GB)"; }
for spec in "TURNI-r2|--build build-pr949 --env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma --set-opt=--pool-tasks=96" \
            "TURNI-daily|--daily-exe --env STRATA_ARENA_PIN_GIB=64"; do
  n=${spec%%|*}; args=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:120])"
  pools
  echo "$n start $(date +%H:%M)"
  timeout 21600 python -u run_turns.py --name "$n" $args > "$n.runlog" 2>&1
  echo "$n rc=$? end $(date +%H:%M)"
  tail -15 "$n.runlog" | cut -c1-240
  pools
done
