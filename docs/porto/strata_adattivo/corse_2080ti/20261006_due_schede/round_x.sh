#!/bin/bash
# Prefix disk cache with layer split (build-pfx): the 131k prefix as the system message, so it is the root.
# X-pfx1 reads 131k and must save the file; X-pfx2 must restore it from disk at L01 (seconds, not ~80 s).
export PATH=/usr/bin:/mingw64/bin:$PATH
while tasklist //FI "PID eq 3220" | grep -qi bash || tasklist //FI "IMAGENAME eq strata.exe" | grep -qi strata; do sleep 20; done
rm -f /d/ds4_work/strata/lab_prefix/split131k.bin
L=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261006_allineamento040
I="--build build-pfx --prefix-as-system --env CUDA_VISIBLE_DEVICES=1,0 --add-opt=--layer-split=16 --add-opt=--trim-stage-weights --env STRATA_POOL_SPIN_US=100 --add-opt=--prompt-cache-file=D:/ds4_work/strata/lab_prefix/split131k.bin"
bash "$L/long_ab_run.sh" "X-pfx1|$I" "X-pfx2|$I"
K=/c/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep
for n in X-pfx1 X-pfx2; do echo "== $n"; grep -a "prefix disk cache\|serve: prompt [0-9]" $K/$n/engine.log | cut -c1-220; done
ls -la /d/ds4_work/strata/lab_prefix/
