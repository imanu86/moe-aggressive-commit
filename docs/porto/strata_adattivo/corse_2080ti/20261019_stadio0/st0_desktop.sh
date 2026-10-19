#!/bin/bash
# Costo di OktoCGControl sulla 3060: due braccia (Daily com'e' e cache esplicita) con l'app APERTA o CHIUSA, stesso protocollo delle altre corse.
# Serve l'owner: chiudere/aprire OktoCGControl fra una chiamata e l'altra (non lo fa lo script).  Schema B-A-B: aperta, chiusa, aperta.
#   bash st0_desktop.sh aperta   |   bash st0_desktop.sh chiusa     (ripetere aperta/chiusa/aperta; il numero d'ordine e' il secondo argomento)
export PATH=/usr/bin:/mingw64/bin:$PATH
H="$(cd "$(dirname "$0")" && pwd)"
stato=$1; n=${2:-1}
running=$(tasklist | grep -c -i "CGControl.exe")
if [ "$stato" = "chiusa" ] && [ "$running" != "0" ]; then echo "OktoCGControl e' ancora aperta: chiuderla (lo fa l'owner)"; exit 2; fi
if [ "$stato" = "aperta" ] && [ "$running" = "0" ]; then echo "OktoCGControl non e' aperta: aprirla (lo fa l'owner)"; exit 2; fi
cd "$H"
for arm in "auto:" "expl:--set-opt=--expert-cache=2000"; do
  tag=${arm%%:*}; opt=${arm#*:}
  python -u "$H/st0_lock.py" "DET-ST0-D-$stato$n-$tag" -- python -u -B st0_run.py --name "DET-ST0-D-$stato$n-$tag" --gpu-engine --short-n 2 --decodes 3 $opt > "runlog_D_${stato}${n}_${tag}.txt" 2>&1
done
