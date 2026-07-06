#!/bin/bash
# PROBE 0013 (mandato SPEX-main): (a) meccanismo accounting, (b) numero pulito
# cache-on vs cache-off A PARITA' di --mtp. 3060 daily, dir timestampata.
set -u
OUT=/root/out_probe_$(date +%H%M%S)
mkdir -p "$OUT"; ln -sfn "$OUT" /root/out_probe_latest
PROG="$OUT/progress.log"
say() { echo "[$(date '+%F %T')] $*" >> "$PROG"; }
DS4=/root/ds4-dspark/ds4
MODEL=/root/models/ds4-2bit.gguf
MTP=/root/models/ds4-mtp.gguf
P="Write a Python function that parses a CSV file and returns the sum of the second column. Include error handling and a short docstring."
CACHE=250   # config daily-like, reserve DEFAULT (niente RESERVE_GB: variabile unica = registrazione)

grab() { tr -d '\0' < "$1" | tr '\r' '\n' | grep -E 'available|cache budget|= [0-9]+ experts|registered|HOST_STATICS|generation:' | head -8; }
run() { local n="$1"; shift; local e="$1"; shift; local ntok="$1"; shift
  local t0=$(date +%s)
  env DS4_SPEX_STATS=1 $e timeout 1200 "$DS4" -m "$MODEL" --cuda --ssd-streaming \
      --ssd-streaming-cache-experts $CACHE -p "$P" -n $ntok -c 2048 --temp 0 --nothink "$@" \
      > "$OUT/$n.log" 2>&1
  say "PROBE $n rc=$? $(( $(date +%s)-t0 ))s"
  grab "$OUT/$n.log" | sed 's/^/    /' >> "$PROG"
}

say "PROBE-A meccanismo (init-only, -n 8)"
run a1_nomtp "" 8
run a2_mtp_reg "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1" 8 --mtp "$MTP" --mtp-draft 1
run a3_mtp_noreg "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1 DS4_MTP_NO_REGISTER=1" 8 --mtp "$MTP" --mtp-draft 1

say "PROBE-B numero pulito (draft-1 inerte su entrambi, -n 100, warmup+2rep/lato)"
run b_warmup "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1" 30 --mtp "$MTP" --mtp-draft 1
run b_reg_r1 "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1" 100 --mtp "$MTP" --mtp-draft 1
run b_noreg_r1 "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1 DS4_MTP_NO_REGISTER=1" 100 --mtp "$MTP" --mtp-draft 1
run b_reg_r2 "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1" 100 --mtp "$MTP" --mtp-draft 1
run b_noreg_r2 "DS4_MTP_STREAMING=1 DS4_MTP_HOST_STATICS=1 DS4_MTP_NO_REGISTER=1" 100 --mtp "$MTP" --mtp-draft 1

say "PROBE DONE"
echo DONE > "$OUT/PROBE_DONE"
