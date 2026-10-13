#!/bin/bash
# 13/10: braccio B (leve) ripetuto due volte (B2, B3) per misurare il riavvio con STRATA_CONV_DISK
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
PY=/d/ds4_work/strata/Strata/.venv/Scripts/python.exe
B=$K/build-ttft43-a2111f8b
for tag in B2 B3; do
  echo "== $tag $(date +%H:%M:%S)"
  python $D/bench_lock.py DET-ttft-$tag -- $PY -B $D/ttft_bench.py --tag $tag --exe $B/strata.exe --serve $B/source/serve --env "STRATA_PREFIX_DISK_MULTI=24 STRATA_CONV_DISK=10" --server-env STRATA_PROMPT_ENCODER=1 --compare A > $D/ttft_$tag.runlog 2>&1
  echo "$tag rc=$? $(date +%H:%M:%S)"
done
echo "== fine lazy $(date +%H:%M:%S)"
