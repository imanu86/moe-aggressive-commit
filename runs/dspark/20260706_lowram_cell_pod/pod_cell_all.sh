#!/bin/bash
# CELLA MANCANTE matrice M8: nativo DISK-BOUND (cgroup memory.max=46.6G del container;
# punto A = finestra cache ~46G, punto B = hog 30G -> finestra ~16G, regime consumer).
# Stack 0009+0010+0011, stesso prompt/config della matrice. DS4_SPEX_STATS=1 ovunque.
set -u
OUT=/root/out_cell_$(date +%H%M%S)
mkdir -p "$OUT"; ln -sfn "$OUT" /root/out_cell_latest
PROG="$OUT/progress.log"
say() { echo "[$(date '+%F %T')] $*" >> "$PROG"; }
DS4DIR=/root/ds4
MODEL=/root/models/ds4-2bit.gguf
MTP=/root/models/ds4-mtp.gguf
P="Write a Python function that parses a CSV file and returns the sum of the second column. Include error handling and a short docstring."

say "CELL setup start; memory.max=$(cat /sys/fs/cgroup/memory.max)"
if [ ! -d "$DS4DIR" ]; then git clone -q https://github.com/antirez/ds4 "$DS4DIR"; fi
cd "$DS4DIR" && git checkout -q 80ebbc3
for p in 0001 0002 0003 0004 0005 0009 0010 0011; do
  f=(/root/patches/${p}-*.patch)
  git apply --check "$f" 2>>"$PROG" && git apply "$f" && say "patch $p OK" || say "patch $p FALLITA"
done
make cuda CUDA_ARCH=sm_86 -j"$(nproc)" > "$OUT/build.log" 2>&1
say "build rc=$?"
mkdir -p /root/models
[ -f "$MTP" ] || wget -q -c -O "$MTP" "https://huggingface.co/antirez/deepseek-v4-gguf/resolve/main/DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf"
[ -f "$MODEL" ] || wget -q -c -O "$MODEL" "https://huggingface.co/antirez/deepseek-v4-gguf/resolve/main/DeepSeek-V4-Flash-IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf"
[ "$(stat -c%s $MODEL)" = "86720111488" ] || { say "MODEL SIZE SBAGLIATA - STOP"; exit 1; }
say "modelli ok"

SPEC="DS4_SPEX_STATS=1 DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1 DS4_MTP_CONF_LOG=1 DS4_MTP_TIMING=1"
BASE="DS4_SPEX_STATS=1"
run() { local n="$1"; shift; local e="$1"; shift
  local t0=$(date +%s)
  env $e timeout 2400 "$DS4DIR/ds4" -m "$MODEL" --cuda --ssd-streaming \
      --ssd-streaming-cache-experts 8GB -p "$P" -n 100 -c 2048 --temp 0 --nothink "$@" \
      > "$OUT/$n.log" 2>&1
  say "CELL $n rc=$? $(( $(date +%s)-t0 ))s $(tr -d '\0' < $OUT/$n.log | tr '\r' '\n' | grep -m1 'generation:') mem.cur=$(( $(cat /sys/fs/cgroup/memory.current)/1073741824 ))G"
}
punto() { # A|B
  local tag="$1"
  say "PUNTO $tag: warmup (scartata) + 2 rep per config"
  run "${tag}_warmup" "$BASE"
  run "${tag}_base_r1" "$BASE"
  run "${tag}_spec2_r1" "$SPEC" --mtp "$MTP" --mtp-draft 2 --mtp-margin 0
  run "${tag}_base_r2" "$BASE"
  run "${tag}_spec2_r2" "$SPEC" --mtp "$MTP" --mtp-draft 2 --mtp-margin 0
  run "${tag}_spec4_r1" "$SPEC" --mtp "$MTP" --mtp-draft 4 --mtp-margin 0
  run "${tag}_spec4_r2" "$SPEC" --mtp "$MTP" --mtp-draft 4 --mtp-margin 0
}

say "PUNTO A: finestra cache ~46G (no hog), disk-bound (modello 87G > cap 46.6G)"
punto A

say "PUNTO B: avvio hog 30G -> finestra ~16G (regime consumer 3060-like)"
python3 - << 'PYEOF' > "$OUT/hog.log" 2>&1 &
import time
GB = 1 << 30
b = bytearray(30 * GB)
for i in range(0, len(b), 4096):
    b[i] = 1
print("HOG 30G attivo", flush=True)
time.sleep(86400)
PYEOF
HOGPID=$!
sleep 90
say "hog: $(grep -c 'attivo' $OUT/hog.log 2>/dev/null) mem.cur=$(( $(cat /sys/fs/cgroup/memory.current)/1073741824 ))G"
punto B
kill $HOGPID 2>/dev/null
say "CELLA COMPLETA"
echo DONE > "$OUT/CELL_DONE"
