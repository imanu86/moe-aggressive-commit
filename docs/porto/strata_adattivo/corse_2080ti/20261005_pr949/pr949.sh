#!/bin/bash
# PR 949 (--pool-tasks): fixed-placement identity (default 0 and 96 tasks) against TFX-enc, then 131k L01/L02:
# B = 96 tasks twice, 192 once, 48 once; then A = default (0: 3 per participating thread = 24 on 7 workers + host).
H=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261005_handoff/script
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
bash "$H/tf_fixed.sh" "TFX-pt0|--build build-pr949" "TFX-pt96|--build build-pr949 --set-opt=--pool-tasks=96"
cd "$D" || exit 1
for n in TFX-pt0 TFX-pt96; do
  for t in code explain; do
    python - "$n" "$t" <<'PY' | tee -a tf_fixed_pr949.txt
import sys
from pathlib import Path
n, t = sys.argv[1], sys.argv[2]
a = Path(f'{n}-{t}/logpos.tsv'); b = Path(f'TFX-enc-{t}/logpos.tsv')
if not a.is_file(): print(f'{n}-{t}: senza logpos'); sys.exit()
print(f'{n}-{t}: ' + ('identico bit per bit a TFX-enc' if a.read_bytes() == b.read_bytes() else 'DIVERSO da TFX-enc'))
PY
  done
  grep -a "CPU pool tasks" $n-code/engine.log | head -1 | cut -c1-160
done
CAND="--env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma"
for spec in "LPT96-a|96" "LPT96-b|96" "LPT192|192" "LPT48|48" "LPT24-default|0"; do
  n=${spec%%|*}; pt=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:110])"
  powershell -NoProfile -Command "\$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; '  pool kernel: {0:N2} GB paginato, {1:N2} GB non paginato' -f (\$m.PoolPagedBytes/1GB),(\$m.PoolNonpagedBytes/1GB)"
  timeout 3000 python -u run_long.py --name "$n" --build build-pr949 $CAND "--set-opt=--pool-tasks=$pt" > "$n.runlog" 2>&1
  echo "$n (pool-tasks $pt) rc=$?"
  grep -a "CPU pool tasks" "$n/engine.log" | head -1 | cut -c1-140
  grep -a "strata decode timing" "$n/engine.log" | cut -c1-330
  grep -a "serve: prompt [0-9]" "$n/engine.log" | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
