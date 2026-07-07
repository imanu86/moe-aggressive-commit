#!/bin/bash
# Adaptive-K via COPERTURA (SPEX): osserva W=50 wide UNA volta, poi per ogni COV% congela la
# coverage-mask (K auto-scelto per copertura) -> continua -> grada. Task-indipendente.
# Uso: coverage_sweep.sh <task> <ngen>   (task: frontpage|python|json)
set -u
TASK="${1:?task}"; NGEN="${2:-1000}"
BIN=/root/ds4-pace/ds4; MODEL=/root/models/ds4-2bit.gguf
OUT=/root/cov_$TASK/out; mkdir -p $OUT
PROMPT=/root/knee/$TASK.txt
CACHE=1024; W=50
echo "=== coverage sweep task=$TASK W=$W ===" > $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
   -c 512 --nothink --temp 0 -n 8 -p "hi" > /dev/null 2>&1
# FASE 1 (una volta): wide W token, trace con pesi
DS4_SPEX_TRACE_ROUTING=$OUT/route.csv DS4_SPEX_TRACE_ROUTING_WEIGHTS=1 \
  $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
  -c 2048 --nothink --temp 0 -n $W --prompt-file $PROMPT > $OUT/tw.txt 2> $OUT/p1.diag
cat $PROMPT $OUT/tw.txt > $OUT/p2prompt.txt
echo "fase1 wide fatta ($(wc -c < $OUT/tw.txt) byte)" | tee -a $OUT/summary.txt
n2=$((NGEN - W))
for COV in 80 85 90 95; do
  python3 /root/build_coverage_mask.py $OUT/route.csv $OUT/cov_$COV.txt $COV 2>&1 | tee -a $OUT/summary.txt
  # aderenza gate (probe breve trace ON)
  DS4_REAP_MASK_FILE=$OUT/cov_$COV.txt DS4_SPEX_TRACE_ROUTING=$OUT/adr_$COV.csv \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 2048 --nothink --temp 0 -n 32 --prompt-file $PROMPT > /dev/null 2> /dev/null
  DS4_REAP_MASK_FILE=$OUT/cov_$COV.txt \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 3072 --nothink --temp 0 -n $n2 --prompt-file $OUT/p2prompt.txt > $OUT/trest_$COV.txt 2> $OUT/p2_$COV.diag
  ts=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/p2_$COV.diag | grep -oE "[0-9.]+" | tail -1)
  cat $OUT/tw.txt $OUT/trest_$COV.txt > $OUT/deliverable_$COV.html
  printf "COV=%s t/s_frozen=%s\n" "$COV" "${ts:-NA}" | tee -a $OUT/summary.txt
done
touch $OUT/DONE
echo "=== FATTO $TASK ===" | tee -a $OUT/summary.txt
