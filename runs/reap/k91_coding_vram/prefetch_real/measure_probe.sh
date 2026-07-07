#!/bin/bash
# t/s REALE segmentato: baseline / 0003(selection-continuity) / hidden-probe (K=6,16,23).
# Stesso binario ds4-probe (config via env). Full q2, cache=400 (12GB), n=64/256/576.
set -u
BIN=/root/ds4-probe/ds4; MODEL=/root/models/ds4-2bit.gguf
OUT=/root/measure/out; mkdir -p $OUT
FP=/root/knee/frontpage.txt; CACHE=400
run() { local tag="$1" ev="$2"; shift 2
  for n in "$@"; do
    env $ev $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold \
       --ssd-streaming-cache-experts $CACHE -c 2048 --nothink --temp 0 -n $n \
       --prompt-file $FP > /dev/null 2> $OUT/${tag}_n${n}.diag
    local ge=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/${tag}_n${n}.diag | grep -oE "[0-9.]+" | tail -1)
    echo "$tag n=$n gen=$ge" | tee -a $OUT/summary.txt
  done
}
echo "=== VERIFICA probe load + prefetch ===" > $OUT/summary.txt
DS4_SPEX_PREFETCH_NEXT_LAYER=1 DS4_SPEX_HIDDEN_FILE=/root/probe.spex DS4_SPEX_PREFETCH_PROFILE=1 \
  $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
  -c 512 --nothink --temp 0 -n 10 --prompt-file $FP > /dev/null 2> $OUT/verify.diag
grep -E "hidden-probe loaded|SPEX stage1 prefetch.*hidden" $OUT/verify.diag | head -3 | tee -a $OUT/summary.txt
echo "prefetch-events(hidden): $(grep -c "prefetch.*hidden" $OUT/verify.diag) / totali: $(grep -c "SPEX stage1 prefetch" $OUT/verify.diag)" | tee -a $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE -c 512 --nothink --temp 0 -n 8 -p hi > /dev/null 2>&1
echo "--- BASELINE ---" | tee -a $OUT/summary.txt;  run baseline "" 64 256 576
echo "--- 0003 selection-continuity ---" | tee -a $OUT/summary.txt; run pf0003 "DS4_SPEX_PREFETCH_NEXT_LAYER=1" 64 256 576
echo "--- HIDDEN-PROBE K=6 ---" | tee -a $OUT/summary.txt; run probeK6 "DS4_SPEX_PREFETCH_NEXT_LAYER=1 DS4_SPEX_HIDDEN_FILE=/root/probe.spex DS4_SPEX_HIDDEN_K=6" 64 256 576
echo "--- HIDDEN-PROBE K=16 ---" | tee -a $OUT/summary.txt; run probeK16 "DS4_SPEX_PREFETCH_NEXT_LAYER=1 DS4_SPEX_HIDDEN_FILE=/root/probe.spex DS4_SPEX_HIDDEN_K=16" 64 256
echo "--- HIDDEN-PROBE K=23 ---" | tee -a $OUT/summary.txt; run probeK23 "DS4_SPEX_PREFETCH_NEXT_LAYER=1 DS4_SPEX_HIDDEN_FILE=/root/probe.spex DS4_SPEX_HIDDEN_K=23" 64 256
touch $OUT/DONE; echo "=== FATTO ===" | tee -a $OUT/summary.txt
