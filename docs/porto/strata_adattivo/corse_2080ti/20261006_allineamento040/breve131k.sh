#!/bin/bash
# Short test of the 0.1.40 merge: 131k L01/L02 with the Daily config, B = merge (build-m040) first, then A = the Daily's
# own exe (0.1.39 r1). One run each.
export PATH=/usr/bin:/mingw64/bin:$PATH
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
cd "$D" || exit 1
for spec in "L040-B|--build build-m040" "L040-A|--daily-exe"; do
  n=${spec%%|*}; b=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s)[:110])"
  powershell -NoProfile -Command "\$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; '  pool kernel: {0:N2} GB paginato, {1:N2} GB non paginato' -f (\$m.PoolPagedBytes/1GB),(\$m.PoolNonpagedBytes/1GB)"
  timeout 3000 python -u run_long.py --name "$n" $b > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a "session is up" "$n/engine.log" | head -1 | cut -c1-120
  grep -a "strata decode timing" "$n/engine.log" | cut -c1-330
  grep -a "serve: prompt [0-9]" "$n/engine.log" | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
