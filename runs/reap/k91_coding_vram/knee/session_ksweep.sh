#!/bin/bash
# K-sweep SESSION-LEARNED: osserva W=50 wide UNA volta, poi congela session-mask keep-K per
# vari K -> continua -> grada. Vede se il session-learning crea un ginocchio graduale sul
# frontpage (dove il cold-static collassava a ogni K). Stream separati.
set -u
BIN=/root/ds4-pace/ds4
MODEL=/root/models/ds4-2bit.gguf
OUT=/root/sk/out; mkdir -p $OUT
PROMPT=/root/warm/frontpage.txt
CACHE=1024; NTOTAL=1000; W=50
echo "=== session K-sweep, W=$W ===" > $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
   -c 512 --nothink --temp 0 -n 8 -p "hi" > /dev/null 2>&1
# FASE 1 (una sola volta): wide W token, trace con pesi
DS4_SPEX_TRACE_ROUTING=$OUT/route.csv DS4_SPEX_TRACE_ROUTING_WEIGHTS=1 \
  $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
  -c 2048 --nothink --temp 0 -n $W --prompt-file $PROMPT > $OUT/tw.txt 2> $OUT/p1.diag
cat $PROMPT $OUT/tw.txt > $OUT/p2prompt.txt
echo "fase1 wide fatta ($(wc -c < $OUT/tw.txt) byte)" | tee -a $OUT/summary.txt
n2=$((NTOTAL - W))
for K in 32 23 16 12 8; do
  python3 /root/build_session_mask.py $OUT/route.csv $OUT/sess_K$K.txt $K 2>&1 | tee -a $OUT/summary.txt
  DS4_REAP_MASK_FILE=$OUT/sess_K$K.txt \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 3072 --nothink --temp 0 -n $n2 --prompt-file $OUT/p2prompt.txt > $OUT/trest_K$K.txt 2> $OUT/p2_K$K.diag
  ts=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/p2_K$K.diag | grep -oE "[0-9.]+" | tail -1)
  cat $OUT/tw.txt $OUT/trest_K$K.txt > $OUT/deliverable_K$K.html
  printf "K=%-3s t/s_frozen=%s\n" "$K" "${ts:-NA}" | tee -a $OUT/summary.txt
done
touch $OUT/DONE
echo "=== FATTO ===" | tee -a $OUT/summary.txt
