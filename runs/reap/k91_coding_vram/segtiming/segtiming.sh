#!/bin/bash
# Timing SEGMENTATO via differencing: n=64/256/576 per config -> TTFT + t/s per segmento
# (1-64 cold-start/page-in, 65-256, 257+ steady-state). Stream separati.
set -u
BIN=/root/ds4-pace/ds4; MODEL=/root/models/ds4-2bit.gguf
MD=/root/knee/masks; OUT=/root/seg/out; mkdir -p $OUT
PROMPT=/root/knee/frontpage.txt
CACHE=400   # ~cache reale 12GB, cosi' il page-in/cold-start e' visibile
run() { # tag maskfile n
  local tag="$1" mf="$2" n="$3" env=""
  [ "$mf" != "none" ] && env="DS4_REAP_MASK_FILE=$MD/$mf"
  env $env $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold \
     --ssd-streaming-cache-experts $CACHE -c 2048 --nothink --temp 0 -n $n \
     --prompt-file $PROMPT > /dev/null 2> $OUT/${tag}_n${n}.diag
  local pf=$(grep -oE "prefill: *[0-9.]+ t/s" $OUT/${tag}_n${n}.diag | grep -oE "[0-9.]+" | tail -1)
  local ge=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/${tag}_n${n}.diag | grep -oE "[0-9.]+" | tail -1)
  echo "$tag n=$n prefill=$pf gen=$ge" | tee -a $OUT/summary.txt
}
echo "=== seg timing cache=$CACHE ===" > $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
   -c 512 --nothink --temp 0 -n 8 -p "hi" > /dev/null 2>&1  # warmup
for cfg in "full:none" "reapK8:reap_keepK_8.runtime.txt" "reapK32:reap_keepK_32.runtime.txt"; do
  tag="${cfg%%:*}"; mf="${cfg##*:}"
  for n in 64 256 576; do run "$tag" "$mf" "$n"; done
done
touch $OUT/DONE
echo "=== FATTO ===" | tee -a $OUT/summary.txt
