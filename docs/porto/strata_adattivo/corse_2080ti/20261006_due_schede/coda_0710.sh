#!/bin/bash
# 7/10 queue after DET-hot-2: the host-core stability check, then build lab/prefill-seed (first/last/last/first,
# 12 identical requests per process: the lever MTP_PRIORITY:1 is the default, so A and B are the same config).
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
cd $D || exit 1
python - <<'EOF'
import psutil, time
def busy():
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if (p.info['name'] or '').lower() == 'python.exe' and any('DET-hot-2' in c for c in p.info['cmdline'] or []):
                return True
        except Exception:
            pass
    return False
while busy():
    time.sleep(20)
EOF
O="--build build-fable-93be6e0 --rounds 3 --add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --lever MTP_PRIORITY:1"
for arm in first1:first last1:last last2:last first2:first; do
  n=${arm%%:*}; hc=${arm##*:}
  echo "== DET-stab-$n $(date +%H:%M)"
  timeout 3000 python -u hot_ab.py --name DET-stab-$n $O --add-opt=--host-core=$hc 2>&1 | grep -E 'Error|assert|Traceback' | head -5
done
echo "== build seed $(date +%H:%M)"
python -u build_lock.py /c/Users/imanu/source/repos/Strata-wt/seed 2>&1 | tail -6
if [ -f /c/Users/imanu/source/repos/Strata-wt/seed/build-sm7586/strata.exe ]; then
  S=$(git -C /c/Users/imanu/source/repos/Strata-wt/seed rev-parse --short HEAD)
  mkdir -p $K/build-seed-$S && cp /c/Users/imanu/source/repos/Strata-wt/seed/build-sm7586/strata.exe $K/build-seed-$S/
  H=$(sha256sum $K/build-seed-$S/strata.exe | cut -d' ' -f1)
  printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "lab/prefill-seed %s: seme della cache esperti dalla massa della prefill (STRATA_PREFILL_SEED, spento di default)"\n}\n' "$H" "$S" > $K/build-seed-$S/build.json
  echo "staged build-seed-$S"
fi
python - <<'EOF'
import json, statistics
from pathlib import Path
K = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep')
for n in ('first1', 'last1', 'last2', 'first2'):
    p = K / f'DET-stab-{n}' / 'hot_ab.jsonl'
    if not p.exists():
        print(n, 'mancante'); continue
    m = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    m = [r for r in m if not r['warm'] and r['tps']]
    for c in ('L01', 'L02'):
        v = [r['tps'] for r in m if r['case'] == c]
        med = statistics.median(v)
        slow = sum(1 for x in v if x < 0.92 * med)
        print(f'{n:7s} {c} n={len(v)} media {statistics.mean(v):.1f} mediana {med:.1f} min {min(v):.1f} lente {slow}')
EOF
