#!/bin/bash
# Test precisione: per una variante-modello misura DUE assi -
# A) QUALITA': full (no mask) sul task-HARD (todo-app), n=1300 -> grade L0-L3
# B) FIT/VELOCITA': segmentato (n=64/256/576, cache=400) su frontpage -> TTFT + t/s per segmento
# Uso: precision_test.sh <model.gguf> <tag>
set -u
MODEL="${1:?model}"; TAG="${2:?tag}"
BIN=/root/ds4-pace/ds4
OUT=/root/prec_$TAG/out; mkdir -p $OUT
HARD=/root/knee/frontpage_hard.txt
FP=/root/knee/frontpage.txt
echo "=== precisione $TAG ($MODEL) ===" > $OUT/summary.txt
# warmup
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts 512 \
   -c 512 --nothink --temp 0 -n 8 -p "hi" > /dev/null 2>&1
# A) QUALITA' sul task hard (full, no mask, cache generosa)
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts 1024 \
   -c 2048 --nothink --temp 0 -n 1300 --prompt-file $HARD > $OUT/quality_hard.txt 2> $OUT/quality_hard.diag
qt=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/quality_hard.diag | grep -oE "[0-9.]+" | tail -1)
echo "qualita' hard: gen $qt t/s (grade in locale)" | tee -a $OUT/summary.txt
# B) SEGMENTATO (full, cache=400) su frontpage
for n in 64 256 576; do
  $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts 400 \
     -c 2048 --nothink --temp 0 -n $n --prompt-file $FP > /dev/null 2> $OUT/seg_n${n}.diag
  pf=$(grep -oE "prefill: *[0-9.]+ t/s" $OUT/seg_n${n}.diag | grep -oE "[0-9.]+" | tail -1)
  ge=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/seg_n${n}.diag | grep -oE "[0-9.]+" | tail -1)
  echo "seg n=$n prefill=$pf gen=$ge" | tee -a $OUT/summary.txt
done
touch $OUT/DONE
echo "=== FATTO $TAG ===" | tee -a $OUT/summary.txt
