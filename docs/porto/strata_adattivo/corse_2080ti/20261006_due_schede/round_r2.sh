#!/bin/bash
# After round S: pruning A/B (owner 6/10), then build the prefix-disk-cache port (machine idle), then control + prefix arms.
#   R2-hardin / R2-hardin2: old binary of the 17:0x reference (62.7/53.6) - machine or binary?
#   R2-base: build-stage (per-stage timing).  R2-pfx1 writes the 131k split prefix file, R2-pfx2 must read it (L01 prefill ~s).
export PATH=/usr/bin:/mingw64/bin:$PATH
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
D=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_due_schede
while [ ! -f $K/S-ref2/result.json ] || tasklist //FI "IMAGENAME eq strata.exe" | grep -qi strata; do sleep 30; done
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-stage --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
M="--env STRATA_ROUTED_MISS_W=0.08 --env STRATA_ROUTED_KEEP_SKIP=1"
echo "potatura start $(date +%H:%M:%S)"
bash "$L/long_ab_run.sh" "P-miss1|$I $M" "P-base1|$I" "P-miss2|$I $M" "P-base2|$I"
echo "build start $(date +%H:%M:%S)"
python $D/b7586_full.py > $D/build_pfx.log 2>&1; rc=$?
echo "build rc $rc $(date +%H:%M:%S)"; tail -3 $D/build_pfx.log
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
C="--env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100"
ARMS=("R2-hardin|--build build-hardin $C" "R2-base|--build build-stage $C")
if [ $rc -eq 0 ]; then
  mkdir -p $K/build-pfx && cp /c/Users/imanu/source/repos/Strata-2080Ti-core/build-sm7586/strata.exe $K/build-pfx/
  H=$(sha256sum $K/build-pfx/strata.exe | cut -d' ' -f1)
  printf '{\n "status": "completed",\n "executable_sha256": "%s",\n "note": "fork d2f0d52 + stage timing + split commit async opt-in + prefix disk cache with layer split (working tree)"\n}\n' $H > $K/build-pfx/build.json
  rm -f /d/ds4_work/strata/lab_prefix/split131k.bin
  P="--add-opt=--prompt-cache-file=D:/ds4_work/strata/lab_prefix/split131k.bin"
  ARMS+=("R2-pfx1|--build build-pfx $C $P" "R2-pfx2|--build build-pfx $C $P")
fi
ARMS+=("R2-hardin2|--build build-hardin $C")
bash "$L/long_ab_run.sh" "${ARMS[@]}"
for n in R2-pfx1 R2-pfx2; do echo "== $n"; grep -a "prefix disk cache\|serve: prompt [0-9]" $K/$n/engine.log | cut -c1-220; done
