"""Avvia il DAILY (runtime elastico M2) in laboratorio con la configurazione IDENTICA al lanciatore, 28/9/2026.

Legge `Desktop\\SERVER IA LOCALE\\Qwen - ADATTIVO M2 VRAM+RAM - senza MTP.bat` senza modificarlo: variabili d'ambiente
nell'ordine del bat (`set "X="` le toglie, come fa cmd) e argomenti di llama-server riga per riga. Cambiano solo:
host 127.0.0.1, porta di laboratorio, nessuna chiave API, log, slot e cartella di lavoro sotto D:\\ds4_work\\strata\\ab_daily.
Il monitor watch_mtp.ps1 del bat non viene avviato. La chiave del bat non viene letta.

Uso:  python avvia_daily_lab.py [--porta 18110] [--contesto 139264]   (resta in primo piano finche' il server gira)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BAT = Path(r"C:\Users\imanu\Desktop\SERVER IA LOCALE\Qwen - ADATTIVO M2 VRAM+RAM - senza MTP.bat")
LAB = Path(r"D:\ds4_work\strata\ab_daily")
SALTA_ENV = {"API_KEY", "HOST", "PORT", "D", "T", "STAMP"}


def leggi_bat():
    righe = BAT.read_bytes().decode("latin-1").splitlines()
    env = dict(os.environ)
    exe, args, dentro = None, [], False
    for r in righe:
        s = r.strip()
        m = re.match(r'^set "([^=]+)=(.*)"$', s)
        if m and not dentro:
            k, v = m.group(1), m.group(2)
            if k in SALTA_ENV:
                continue
            if v == "":
                env.pop(k, None)
            else:
                env[k] = v
            continue
        if not dentro and s.endswith("llama-server.exe\" ^"):
            exe = s[:-2].strip().strip('"')
            dentro = True
            continue
        if dentro:
            fine = not s.endswith("^")
            corpo = s[:-1].strip() if not fine else s
            # una riga puo' portare flag e valore insieme ("--tensor-split 1"): token separati, virgolette rispettate
            args += [t.strip('"') for t in re.findall(r'"[^"]*"|\S+', corpo)]
            if fine:
                break
    return exe, args, env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=18110)
    # 28/9: con gli altri programmi aperti il -c 262144 del bat non parte (cudaHostAlloc della KV mappata, 3264 MiB,
    # out of memory): per l'A/B con Strata si usa il suo stesso contesto massimo
    ap.add_argument("--contesto", type=int, default=None, help="sostituisce il valore di -c del bat")
    a = ap.parse_args()
    exe, args, env = leggi_bat()
    for d in ("logs", "slots", "ffcache"):
        (LAB / d).mkdir(parents=True, exist_ok=True)
    fuori, i = [], 0
    while i < len(args):
        x = args[i]
        if x == "--host":
            fuori += ["--host", "127.0.0.1"]; i += 2; continue
        if x == "--port":
            fuori += ["--port", str(a.porta)]; i += 2; continue
        if x == "--api-key":
            i += 2; continue
        if x == "--log-file":
            fuori += ["--log-file", str(LAB / "logs" / "daily_m2_lab.log")]; i += 2; continue
        if x == "--slot-save-path":
            fuori += ["--slot-save-path", str(LAB / "slots")]; i += 2; continue
        if x == "-c" and a.contesto:
            fuori += ["-c", str(a.contesto)]; i += 2; continue
        fuori.append(x); i += 1
    assert "%API_KEY%" not in fuori and "--api-key" not in fuori
    env_bat = {k: v for k, v in env.items() if k not in os.environ or os.environ[k] != v}
    (LAB / "comando.json").write_text(json.dumps({"bat": str(BAT), "exe": exe, "args": fuori, "env_dal_bat": env_bat},
                                                 indent=1, ensure_ascii=False), encoding="utf-8")
    print("exe:", exe)
    print("args:", " ".join(fuori))
    print("env dal bat:", len(env_bat), "variabili", flush=True)
    p = subprocess.Popen([exe] + fuori, cwd=str(LAB / "ffcache"), env=env,
                         stdout=open(LAB / "server_stdout.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    (LAB / "pid.txt").write_text(str(p.pid))
    print("pid", p.pid, flush=True)
    return p.wait()


if __name__ == "__main__":
    sys.exit(main())
