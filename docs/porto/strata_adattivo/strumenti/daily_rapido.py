"""Daily (llama.cpp M2 di produzione) sul profilo `rapido`, nello stato attuale della macchina, 29/9/2026.

Lancia avvia_daily_lab.py (legge il bat del daily senza toccarlo, porta 18110, -c 139264 come Strata), aspetta il
server, registra lo stato al lancio, campiona ogni 10 s la CPU di tutti i processi (psutil, 100 = un core) mentre gira
il banco, poi ferma SOLO il server di laboratorio (pid.txt, verificato per nome e porta).
"""
import hashlib
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import psutil

PROVA = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_prova")
LAB = Path(r"D:\ds4_work\strata\ab_daily")
ETI = "daily_m2_rapido_carico"
PORTA = 18110
RUNTIME_DLL = Path(r"D:\ds4_work\bin_elastico_m2\llama.dll")


def nvsmi():
    r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True)
    u, g = (x.strip() for x in r.stdout.strip().split(","))
    return int(u), int(g)


def pronto(timeout=1200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % PORTA, timeout=5) as r:
                if r.status == 200:
                    return time.time() - t0
        except Exception:
            pass
        time.sleep(5)
    return None


def campiona(stop, out):
    procs = {}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            procs[p.pid] = p
        except Exception:
            pass
    with open(out, "w", encoding="utf-8") as f:
        while not stop.wait(10):
            riga = {"t": time.strftime("%H:%M:%S"), "proc": {}}
            for p in psutil.process_iter(["pid", "name"]):
                if p.pid not in procs:
                    try:
                        p.cpu_percent(None)
                        procs[p.pid] = p
                    except Exception:
                        pass
                    continue
                try:
                    c = procs[p.pid].cpu_percent(None)
                except Exception:
                    continue
                if c >= 5:
                    k = p.info["name"] or str(p.pid)
                    riga["proc"][k] = round(riga["proc"].get(k, 0) + c / 100.0, 2)
            riga["ram_disp_gb"] = round(psutil.virtual_memory().available / 2**30, 1)
            try:
                riga["vram_mib"], riga["gpu_pct"] = nvsmi()
            except Exception:
                pass
            f.write(json.dumps(riga) + "\n")
            f.flush()


def ferma():
    try:
        pid = int((LAB / "pid.txt").read_text().strip())
        p = psutil.Process(pid)
        cmd = " ".join(p.cmdline())
        if p.name().lower() == "llama-server.exe" and ("--port %d" % PORTA) in cmd:
            p.terminate()
            p.wait(60)
            print("server di laboratorio fermato (pid %d)" % pid, flush=True)
        else:
            print("pid.txt non e' il server di laboratorio: non fermo niente", flush=True)
    except Exception as e:
        print("ferma:", e, flush=True)


def main():
    # 30/9: --runtime DIR --etichetta NOME per provare un altro llama-server (es. D:\ds4_work\daily_sm75\runtime)
    global ETI
    runtime = None
    if "--runtime" in sys.argv:
        runtime = Path(sys.argv[sys.argv.index("--runtime") + 1])
    if "--etichetta" in sys.argv:
        ETI = sys.argv[sys.argv.index("--etichetta") + 1]
    dll = (runtime / "llama.dll") if runtime else RUNTIME_DLL
    vram0, gpu0 = nvsmi()
    stato = {"quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "runtime": "%s (llama.dll %s)"
             % (runtime or "bin_elastico_m2", hashlib.sha256(dll.read_bytes()).hexdigest()[:8]), "vram_usata_mib": vram0,
             "ram_disponibile_mb": int(psutil.virtual_memory().available / 2**20), "contesto": 139264,
             "cgcontrol": any((p.info["name"] or "").lower() == "cgcontrol.exe" for p in psutil.process_iter(["name"]))}
    (LAB / ("stato_al_lancio_%s.json" % ETI)).write_text(json.dumps(stato, indent=1), encoding="utf-8")
    print("stato al lancio:", json.dumps(stato), flush=True)
    srv = subprocess.Popen([sys.executable, str(PROVA / "avvia_daily_lab.py"), "--porta", str(PORTA), "--contesto",
                            "139264", "--etichetta", ETI] + (["--runtime", str(runtime)] if runtime else [])
                           + [x for i, a in enumerate(sys.argv) if a == "--env" for x in ("--env", sys.argv[i + 1])],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    stop = threading.Event()
    th = threading.Thread(target=campiona, args=(stop, LAB / ("cpu_%s.jsonl" % ETI)), daemon=True)
    th.start()
    try:
        s = pronto()
        if s is None:
            print("server non pronto in 20 minuti", flush=True)
            return 1
        print("[%s] server pronto in %.0f s; VRAM usata %d MiB" % (time.strftime("%H:%M:%S"), s, nvsmi()[0]), flush=True)
        r = subprocess.run([sys.executable, str(PROVA / "banco_strata.py"), "--motore", "llama", "--url",
                            "http://127.0.0.1:%d" % PORTA, "--profilo", "rapido", "--etichetta", ETI],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout[-6000:], flush=True)
        if r.returncode != 0:
            print("banco uscito con", r.returncode, r.stderr[-3000:], flush=True)
    finally:
        stop.set()
        ferma()
        try:
            srv.wait(60)
        except Exception:
            pass
    print("FINE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
