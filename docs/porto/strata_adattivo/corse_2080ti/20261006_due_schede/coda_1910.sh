#!/bin/bash
# 11/10 sera: micro-bench della catena fusa (Fable), poi B-A-B del nucleo RAM e della catena fusa.
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
K=$D/../20261004_routed_keep
CF=/c/Users/imanu/source/repos/Strata-wt/chainfuse/build-sm7586
W="STRATA_FORCE_WINDOWS=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede\force_ids\ref_def1_trace.txt"
P="--add-opt=--pipeline-windows=2 --add-opt=--vram-reserve-later-mib=384 --add-opt=--host-core=last"
E="--env STRATA_VRAM_FREE=device --env STRATA_ROUTE_TAIL_SKIP=0 --env STRATA_MMVQ_IL=0 --env STRATA_B6_MMVQ_ROWS=1 --env STRATA_ATTN_DAILY=1"

echo "== micro-bench catena $(date +%H:%M)"
cd $D && python -u bench_lock.py chainbench -- "$(cygpath -w $CF/chain_step_bench.exe)" --device 1 --iters 200 --vb 16 --graph > $D/chain_step_bench_e6b33daa.txt 2>&1
echo "rc=$?"; tail -25 $D/chain_step_bench_e6b33daa.txt

# build della catena in scena
S=$K/build-chainfuse-e6b33daa
mkdir -p $S && cp $CF/strata.exe $S/ && printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "lab/chainfuse e6b33daa (Fable): STRATA_CHAIN_FUSE2=1 fusioni della catena MTP"\n}\n' "$(sha256sum $S/strata.exe | cut -d' ' -f1)" > $S/build.json

echo "== nucleo RAM $(date +%H:%M)"
for arm in b1 a b2; do
  X=""; case $arm in b*) X="--env STRATA_RAM_CORE=1 --env STRATA_RAM_CORE_SLOTS_DEV1=5500";; esac
  bash $D/det_force.sh DET-coreram-$arm build-coreram-e1755272 --env "$W" $P $E $X >/dev/null 2>&1
done
(cd $K && python $D/bab_verdict.py DET-coreram-a DET-coreram-b1 DET-coreram-b2)
for a in a b1; do echo "-- $a"; grep -ah "strata ram core\|decode expert cache hit rate" $K/DET-coreram-$a/engine.log | tail -3 | cut -c1-260; done

if grep -q "^rc=0" <(echo "rc=$(grep -c DIFFERENT $D/chain_step_bench_e6b33daa.txt | sed 's/^0$/0/')"); then :; fi
if ! grep -qi "different\|mismatch\|FAIL" $D/chain_step_bench_e6b33daa.txt; then
  echo "== catena fusa $(date +%H:%M)"
  for arm in b1 a b2; do
    X=""; case $arm in b*) X="--env STRATA_CHAIN_FUSE2=1 --env STRATA_CHAIN_FUSE2_VB=16";; esac
    bash $D/det_force.sh DET-chainfuse-$arm build-chainfuse-e6b33daa --env "$W" $P $E $X >/dev/null 2>&1
  done
  (cd $K && python $D/bab_verdict.py DET-chainfuse-a DET-chainfuse-b1 DET-chainfuse-b2)
  for a in a b1; do grep -ah "accepted [0-9]* of [0-9]*" $K/DET-chainfuse-$a/engine.log | grep -o "accepted [0-9]* of [0-9]*" | tr '\n' ' '; echo "($a)"; done
else
  echo "== catena fusa NON provata nel motore: il micro-bench segnala differenze"
fi
