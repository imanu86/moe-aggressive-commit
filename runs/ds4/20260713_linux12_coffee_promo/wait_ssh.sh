#!/usr/bin/env bash
# Poll pod until SSH ports appear (or 20 min). Write endpoint to POD_SSH.txt.
set -u
RUNDIR="/c/Users/imanu/source/repos/moe-aggressive-commit/runs/ds4/20260713_linux12_coffee_promo"
export RUNPOD_API_KEY="$(tr -d '\r\n' < /c/Users/imanu/Desktop/Runapod.txt)"
POD_ID="$(cat $RUNDIR/POD_ID.txt)"
OUT="$RUNDIR/POD_SSH.txt"
LOG="$RUNDIR/wait_ssh.log"
DEADLINE=$(( $(date +%s) + 20*60 ))
log(){ echo "[$(date -u '+%H:%M:%SZ')] $*" | tee -a "$LOG"; }
log "waiting for SSH ports on pod=$POD_ID"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  resp=$(curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" "https://rest.runpod.io/v1/pods/$POD_ID" 2>/dev/null)
  parsed=$(echo "$resp" | python -c "
import sys,json
try:
  d=json.load(sys.stdin)
except Exception:
  print('PARSEFAIL'); sys.exit()
st=d.get('desiredStatus'); ip=d.get('publicIp'); pm=d.get('portMappings'); rt=d.get('runtime')
# portMappings like {'22':12345}
ssh=''
if pm and ip:
  p=pm.get('22') or pm.get(22)
  if p: ssh='%s:%s'%(ip,p)
print('STATUS=%s IP=%s PM=%s SSH=%s RT=%s'%(st,ip,pm,ssh,'yes' if rt else 'no'))
" 2>/dev/null)
  log "$parsed"
  ssh=$(echo "$parsed" | grep -oE 'SSH=[0-9.]+:[0-9]+' | cut -d= -f2)
  if [ -n "$ssh" ]; then
    echo "$ssh" > "$OUT"
    log "SSH READY: $ssh -> wrote $OUT"
    exit 0
  fi
  sleep 25
done
log "DEADLINE: no SSH after 20min"
exit 2
