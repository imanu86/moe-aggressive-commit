#!/bin/bash
export PATH=/usr/local/cuda/bin:$PATH
S=/root/bstatus
echo "start" > $S
cd /root && rm -rf ds4-probe
git clone -q /root/ds4 ds4-probe 2>>/root/bp_err.log || { echo "clone_fail" > $S; exit 1; }
echo "cloned" > $S
cd ds4-probe && git checkout -q -f 80ebbc3 2>>/root/bp_err.log
echo "patching" > $S
for P in 0001-spex-stage0-cuda-stats 0002-spex-selected-upload-event 0003-spex-stage1-next-layer-prefetch 0004-spex-markov-loader-prefetch 0005-spex-routing-trace-capture 0006-spex-routing-trace-weights 0007-spex-trace-hidden 0011-reap-runtime-mask 0012-reap-sensor-s1 0013-reap-wrap 0014-pace-controller 0014e-pace-wrap-rename; do
  git apply /root/reap-loop/patches/ds4/$P.patch 2>>/root/bp_err.log || { echo "patchfail_$P" > $S; exit 1; }
done
cp /root/reap-loop/patches/ds4/ds4_spex_predict.c /root/reap-loop/patches/ds4/ds4_spex_predict.h .
python3 /root/apply_0015.py /root/ds4-probe/ds4.c 2>>/root/bp_err.log || { echo "applyfail" > $S; exit 1; }
echo "wiring_$(grep -c ds4_spex_hidden_get ds4.c)" > $S
echo "making" > $S
if make cuda CUDA_ARCH=sm_86 -j"$(nproc)" > /root/bp_make.log 2>&1; then
  touch /root/PROBE_BUILT; echo "BUILD_OK" > $S
else
  echo "buildfail" > $S
fi
