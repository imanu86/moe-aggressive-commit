#!/bin/bash
# Sweep keep-K -> ginocchio funzionale. Per ogni config: generazione FRONTPAGE (trace OFF,
# timing pulito) + probe aderenza (trace ON, n=40, gate pruned=0). Mask STATICA da tok0.
# cache=400 (~ cache reale su 12GB, cosi' il t/s e' rappresentativo del target edge).
set -u
BIN=/root/ds4-pace/ds4
MODEL=/root/models/ds4-2bit.gguf
MD=/root/knee/masks
OUT=/root/knee/out; mkdir -p $OUT
PROMPT=/root/knee/frontpage.txt
CACHE=1024
NGEN=1000
gen() {  # tag  maskfile("none" per full)
  local tag="$1" mf="$2" env=""
  [ "$mf" != "none" ] && env="DS4_REAP_MASK_FILE=$MD/$mf"
  env $env $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold \
     --ssd-streaming-cache-experts $CACHE -c 2048 --nothink --temp 0 -n $NGEN \
     --prompt-file $PROMPT > $OUT/gen_$tag.log 2>&1
  local ts=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/gen_$tag.log | grep -oE "[0-9.]+" | tail -1)
  local hit=$(grep -oE "hit_rate=[0-9.]+" $OUT/gen_$tag.log | grep -oE "[0-9.]+" | tail -1)
  printf "%-14s cache=%s -> gen %s t/s  hit=%s\n" "$tag" "$CACHE" "${ts:-NA}" "${hit:-NA}" | tee -a $OUT/summary.txt
}
probe() {  # tag maskfile: aderenza trace-on n=40
  local tag="$1" mf="$2"
  [ "$mf" = "none" ] && return 0
  DS4_REAP_MASK_FILE=$MD/$mf DS4_SPEX_TRACE_ROUTING=$OUT/route_$tag.csv \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold \
    --ssd-streaming-cache-experts $CACHE -c 2048 --nothink --temp 0 -n 40 \
    --prompt-file $PROMPT > $OUT/probe_$tag.log 2>&1
}
echo "=== warmup ===" | tee $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
   -c 512 --nothink --temp 0 -n 8 -p "hello" > $OUT/warm.log 2>&1
echo "  ok"
# ordine ruotato: baseline, poi K decrescente reap, poi random ai K vicini al ginocchio
echo "=== BASELINE full ===" | tee -a $OUT/summary.txt
gen full none
for K in 32 28 23 20 16 12 8; do
  echo "=== REAP keep-$K ===" | tee -a $OUT/summary.txt
  gen reapK$K reap_keepK_$K.runtime.txt
  probe reapK$K reap_keepK_$K.runtime.txt
done
for K in 23 20 16 12; do
  echo "=== RANDOM keep-$K (controllo) ===" | tee -a $OUT/summary.txt
  gen randK$K random_keepK_${K}_seed0.runtime.txt
  probe randK$K random_keepK_${K}_seed0.runtime.txt
done
touch $OUT/KNEE_DONE
echo "=== FATTO ===" | tee -a $OUT/summary.txt
