#!/bin/bash
# Warmup-length sweep (Approach A, no PACE): osserva-wide W token -> congela session-mask
# keep-K dalla massa-gate -> continua dal prefisso con mask congelata -> concatena e grada.
# Misura t/s_wide (fase1) e t/s_frozen (fase2 = steady-state mascherato).
set -u
BIN=/root/ds4-pace/ds4
MODEL=/root/models/ds4-2bit.gguf
OUT=/root/warm/out; mkdir -p $OUT
PROMPT=/root/warm/frontpage.txt
CACHE=1024
NTOTAL=1000
K=23
clean() { grep -v '^ds4:' "$1"; }   # toglie le righe diagnostiche, resta il testo generato

echo "=== warmup ===" > $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
   -c 512 --nothink --temp 0 -n 8 -p "hello" > $OUT/warm.log 2>&1

for W in 30 50 80 110 130 150; do
  echo "=== W=$W ===" | tee -a $OUT/summary.txt
  # FASE 1: wide (no mask), n=W, trace routing ON
  DS4_SPEX_TRACE_ROUTING=$OUT/route_W$W.csv \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 2048 --nothink --temp 0 -n $W --prompt-file $PROMPT > $OUT/p1_W$W.log 2>&1
  ts1=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/p1_W$W.log | grep -oE "[0-9.]+" | tail -1)
  clean $OUT/p1_W$W.log > $OUT/tw_W$W.txt
  # session-mask dalla massa osservata
  python3 /root/build_session_mask.py $OUT/route_W$W.csv $OUT/sess_W$W.txt $K 2>&1 | tee -a $OUT/summary.txt
  # prompt fase2 = prompt originale + prefisso wide T_W
  cat $PROMPT $OUT/tw_W$W.txt > $OUT/p2prompt_W$W.txt
  # FASE 2: mask CONGELATA, continua dal prefisso, trace OFF
  n2=$((NTOTAL - W))
  DS4_REAP_MASK_FILE=$OUT/sess_W$W.txt \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 3072 --nothink --temp 0 -n $n2 --prompt-file $OUT/p2prompt_W$W.txt > $OUT/p2_W$W.log 2>&1
  ts2=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/p2_W$W.log | grep -oE "[0-9.]+" | tail -1)
  hit2=$(grep -oE "hit_rate=[0-9.]+" $OUT/p2_W$W.log | grep -oE "[0-9.]+" | tail -1)
  # deliverable = T_W (wide) + T_rest (frozen)
  clean $OUT/p2_W$W.log > $OUT/trest_W$W.txt
  cat $OUT/tw_W$W.txt $OUT/trest_W$W.txt > $OUT/deliverable_W$W.html
  # aderenza fase2 (probe breve trace ON con la stessa mask)
  DS4_REAP_MASK_FILE=$OUT/sess_W$W.txt DS4_SPEX_TRACE_ROUTING=$OUT/adr_W$W.csv \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 2048 --nothink --temp 0 -n 32 --prompt-file $PROMPT > /dev/null 2>&1
  printf "W=%-4s t/s_wide=%s t/s_frozen=%s hit_frozen=%s\n" "$W" "${ts1:-NA}" "${ts2:-NA}" "${hit2:-NA}" | tee -a $OUT/summary.txt
done
touch $OUT/WARM_DONE
echo "=== FATTO ===" | tee -a $OUT/summary.txt
