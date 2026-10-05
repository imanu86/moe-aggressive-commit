#!/bin/bash
# r2 candidate (merge v2 + exact Q2): fixed-placement identity, then 131k L01/L02 - B twice, then A (main + PLE diag)
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
SP="C:/Users/imanu/AppData/Local/Temp/claude/C--Users-imanu-source-repos-cgc-ia-pipeline/1085fc9c-fbfa-42ca-ab1f-57705ff33831/scratchpad"
cd "$D" || exit 1
bash "$SP/tf_fixed.sh" "TFX-r2|--build build-r2cand"
for t in code explain; do
  python - "$t" <<'PY' | tee -a tf_fixed_r2.txt
import sys
from pathlib import Path
t = sys.argv[1]
a = Path(f'TFX-r2-{t}/logpos.tsv'); b = Path(f'TFX-enc-{t}/logpos.tsv')
if not a.is_file(): print(f'{t}: TFX-r2 senza logpos'); sys.exit()
print(f'{t}: TFX-r2 ' + ('identico bit per bit a TFX-enc' if a.read_bytes() == b.read_bytes() else 'DIVERSO da TFX-enc'))
PY
  python analyze_tf.py TFX-r2-$t TFX-enc-$t 2>&1 | tail -1 | tee -a tf_fixed_r2.txt
done
CAND="--env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma"
for spec in "LR-r2a|build-r2cand" "LR-r2b|build-r2cand" "LR-cand|build-plediag"; do
  n=${spec%%|*}; b=${spec#*|}
  python -c "
from run_keep import snapshot; import json,time
for _ in range(40):
    s=snapshot()
    if not s['competing'] and s['commit_free_gib']>=58: break
    time.sleep(15)
print(json.dumps(s))" | cut -c1-100
  timeout 3000 python -u run_long.py --name "$n" --build $b $CAND > "$n.runlog" 2>&1
  echo "$n rc=$?"
  grep -a "strata decode timing" "$n/engine.log" | sed 's/ = verify.*draft/ ... draft/' | cut -c1-220
  grep -a "serve: prompt\|waited" "$n/engine.log" | cut -c1-200
  python -c "
import json; r=json.load(open('$n/result.json'))
print('  =>', r['status'], ' | '.join('%s %.1f t/s' % (q['case'], q['decode_tps']) for q in r['requests']))"
done
