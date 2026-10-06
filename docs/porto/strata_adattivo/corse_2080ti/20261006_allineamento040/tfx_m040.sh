#!/bin/bash
# Merge upstream v0.1.40: fixed-placement teacher forcing (code, explain) against TFX-enc (Daily config)
export PATH=/usr/bin:/mingw64/bin:$PATH
H=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261005_handoff/script
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
bash "$H/tf_fixed.sh" "TFX-m040|--build build-m040"
cd "$D" || exit 1
for t in code explain; do
  python - "$t" <<'PY' | tee -a tf_fixed_m040.txt
import sys
from pathlib import Path
t = sys.argv[1]
a = Path(f'TFX-m040-{t}/logpos.tsv'); b = Path(f'TFX-enc-{t}/logpos.tsv')
if not a.is_file(): print(f'{t}: TFX-m040 senza logpos'); sys.exit()
print(f'{t}: TFX-m040 ' + ('identico bit per bit a TFX-enc' if a.read_bytes() == b.read_bytes() else 'DIVERSO da TFX-enc'))
PY
  python analyze_tf.py TFX-m040-$t TFX-enc-$t 2>&1 | tail -1 | tee -a tf_fixed_m040.txt
done
