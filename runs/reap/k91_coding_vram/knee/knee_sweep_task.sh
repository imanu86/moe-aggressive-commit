#!/bin/bash
# Sweep keep-K generico per un TASK qualsiasi. Uso: knee_sweep_task.sh <task> <ngen>
# Legge /root/knee/<task>.txt, scrive /root/knee_<task>/out. Stream separati (stdout=testo).
set -u
TASK="${1:?task}"; NGEN="${2:-500}"
BIN=/root/ds4-pace/ds4
MODEL=/root/models/ds4-2bit.gguf
MD=/root/knee/masks
OUT=/root/knee_$TASK/out; mkdir -p $OUT
PROMPT=/root/knee/$TASK.txt
CACHE=1024
gen() {  # tag maskfile
  local tag="$1" mf="$2" env=""
  [ "$mf" != "none" ] && env="DS4_REAP_MASK_FILE=$MD/$mf"
  env $env $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold \
     --ssd-streaming-cache-experts $CACHE -c 2048 --nothink --temp 0 -n $NGEN \
     --prompt-file $PROMPT > $OUT/gen_$tag.txt 2> $OUT/gen_$tag.diag
  local ts=$(grep -oE "generation: *[0-9.]+ t/s" $OUT/gen_$tag.diag | grep -oE "[0-9.]+" | tail -1)
  printf "%-14s -> gen %s t/s\n" "$tag" "${ts:-NA}" | tee -a $OUT/summary.txt
}
probe() {  # tag maskfile
  local tag="$1" mf="$2"
  [ "$mf" = "none" ] && return 0
  DS4_REAP_MASK_FILE=$MD/$mf DS4_SPEX_TRACE_ROUTING=$OUT/route_$tag.csv \
    $BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
    -c 2048 --nothink --temp 0 -n 40 --prompt-file $PROMPT > /dev/null 2> $OUT/probe_$tag.diag
}
echo "=== task=$TASK ngen=$NGEN ===" > $OUT/summary.txt
$BIN -m $MODEL --cuda --ssd-streaming --ssd-streaming-cold --ssd-streaming-cache-experts $CACHE \
   -c 512 --nothink --temp 0 -n 8 -p "hi" > /dev/null 2>&1
gen full none
for K in 32 28 23 20 16 12 8; do
  gen reapK$K reap_keepK_$K.runtime.txt
  probe reapK$K reap_keepK_$K.runtime.txt
done
for K in 23 16; do
  gen randK$K random_keepK_${K}_seed0.runtime.txt
  probe randK$K random_keepK_${K}_seed0.runtime.txt
done
touch $OUT/DONE
echo "=== FATTO $TASK ===" | tee -a $OUT/summary.txt
