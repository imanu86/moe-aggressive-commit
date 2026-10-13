#!/bin/bash
# 13/10: riavvio lento con STRATA_CONV_DISK? bracci B (leve) e A (Daily) ripetuti con monitor_avvio.py sulla vita 2
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
PY=/d/ds4_work/strata/Strata/.venv/Scripts/python.exe
B=$K/build-ttft43-a2111f8b
DA=/d/ds4_work/strata/Strata/build-0143-daily
for tag in ${1:-B4 A2 B5}; do
  echo "== $tag $(date +%H:%M:%S)"
  $PY -B $D/monitor_avvio.py $tag > $D/monitor_$tag.out 2>&1 &
  case $tag in
    B*) python $D/bench_lock.py DET-ttft-$tag -- $PY -B $D/ttft_bench.py --tag $tag --exe $B/strata.exe --serve $B/source/serve --env "STRATA_PREFIX_DISK_MULTI=24 STRATA_CONV_DISK=10" --server-env STRATA_PROMPT_ENCODER=1 --compare A > $D/ttft_$tag.runlog 2>&1 ;;
    A*) python $D/bench_lock.py DET-ttft-$tag -- $PY -B $D/ttft_bench.py --tag $tag --exe $DA/strata.exe --serve $DA/source/serve --compare A > $D/ttft_$tag.runlog 2>&1 ;;
  esac
  echo "$tag rc=$? $(date +%H:%M:%S)"
  wait
done
echo "== fine avvio2 $(date +%H:%M:%S)"
