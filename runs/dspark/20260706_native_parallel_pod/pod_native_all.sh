#!/bin/bash
# Pod nativo parallelo (3090, Linux): M8-NATIVO (0011 basta qui?) + seconda coppia
# di validazione appaiata OFF/ON. Patch: 0001-0005 (=bee9eb3) + 0009/0010/0011.
set -u
OUT=/root/out_native_$(date +%H%M)
mkdir -p "$OUT"
PROG="$OUT/progress.log"
say() { echo "[$(date '+%F %T')] $*" >> "$PROG"; }
DS4DIR=/root/ds4
MODEL=/root/models/ds4-2bit.gguf
MTP=/root/models/ds4-mtp.gguf
P="Write a Python function that parses a CSV file and returns the sum of the second column. Include error handling and a short docstring."

say "SETUP start"
if [ ! -d "$DS4DIR" ]; then git clone -q https://github.com/antirez/ds4 "$DS4DIR"; fi
cd "$DS4DIR" && git checkout -q 80ebbc3
for p in 0001 0002 0003 0004 0005 0009 0010 0011; do
  f=(/root/patches/${p}-*.patch)
  if git apply --check "$f" 2>>"$PROG"; then git apply "$f"; say "patch $p OK";
  else say "patch $p FALLITA (check log)"; fi
done
make cuda CUDA_ARCH=sm_86 -j"$(nproc)" > "$OUT/build.log" 2>&1
say "build rc=$? $(ls -la ./ds4 2>/dev/null | awk '{print \$5}')"

say "DOWNLOAD modelli"
mkdir -p /root/models
[ -f "$MTP" ] || wget -q -c -O "$MTP" "https://huggingface.co/antirez/deepseek-v4-gguf/resolve/main/DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf"
[ -f "$MODEL" ] || wget -q -c -O "$MODEL" "https://huggingface.co/antirez/deepseek-v4-gguf/resolve/main/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf"
say "modelli: $(stat -c%s $MODEL) / $(stat -c%s $MTP) byte (attesi 86720111488 / 3807602400)"
[ "$(stat -c%s $MODEL)" = "86720111488" ] || { say "MODEL SIZE SBAGLIATA - STOP"; exit 1; }

SPEC="DS4_SPEX_STATS=1 DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1 DS4_MTP_CONF_LOG=1 DS4_MTP_TIMING=1"
BASE="DS4_SPEX_STATS=1"
run() { local n="$1"; shift; local e="$1"; shift
  local t0=$(date +%s)
  env $e timeout 2400 "$DS4DIR/ds4" -m "$MODEL" --cuda --ssd-streaming \
      --ssd-streaming-cache-experts 8GB -p "$P" -n 100 -c 2048 --temp 0 --nothink "$@" \
      > "$OUT/$n.log" 2>&1
  say "M8NAT $n rc=$? $(( $(date +%s)-t0 ))s $(tr -d '\0' < $OUT/$n.log | tr '\r' '\n' | grep -m1 'generation:') | cache: $(tr -d '\0' < $OUT/$n.log | tr '\r' '\n' | grep -m1 -oE 'cache disabled|= [0-9]+ experts')"
}
say "M8-NATIVO start (warmup + 2 coppie)"
run m8nat_warmup "$BASE"
run m8nat_base_r1 "$BASE"
run m8nat_spec2_r1 "$SPEC" --mtp "$MTP" --mtp-draft 2 --mtp-margin 0
run m8nat_base_r2 "$BASE"
run m8nat_spec2_r2 "$SPEC" --mtp "$MTP" --mtp-draft 2 --mtp-margin 0
run m8nat_spec4_r1 "$SPEC" --mtp "$MTP" --mtp-draft 4 --mtp-margin 0

say "EVAL appaiata OFF start"
env DS4_SPEX_STATS=1 timeout 10800 "$DS4DIR/ds4-eval" -m "$MODEL" --cuda --ssd-streaming \
    --ssd-streaming-cache-experts 8GB --questions 20 --tokens 384 --temp 0 --nothink \
    --plain --trace "$OUT/eval_off.trace" > "$OUT/eval_off.log" 2>&1
say "EVAL OFF rc=$? $(tr -d '\0' < $OUT/eval_off.log | tr '\r' '\n' | grep -E 'passed' | tail -1)"
say "EVAL appaiata ON start"
env DS4_SPEX_STATS=1 DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1 DS4_MTP_PROBE=1 timeout 10800 \
    "$DS4DIR/ds4-eval" -m "$MODEL" --cuda --ssd-streaming --ssd-streaming-cache-experts 8GB \
    --mtp "$MTP" --questions 20 --tokens 384 --temp 0 --nothink --plain \
    --trace "$OUT/eval_on.trace" > "$OUT/eval_on.log" 2>&1
say "EVAL ON rc=$? $(tr -d '\0' < $OUT/eval_on.log | tr '\r' '\n' | grep -E 'passed' | tail -1)"
say "NATIVO TUTTO FATTO"
echo DONE > "$OUT/NATIVE_DONE"
ln -sfn "$OUT" /root/out_native_latest
