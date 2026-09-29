"""Curva «esperti in VRAM -> velocita'» di Strata, 29/9/2026: stesso banco (profilo `curva`), cache di dimensione diversa.

Per ogni punto: scrive la configurazione (quella del confronto equo, strata-iq3_xxs-r1032.json, con gli argomenti
del punto al posto della riserva), avvia serve/server.py sulla 18120, aspetta /health, registra la VRAM degli altri
programmi prima del lancio e le righe del motore sulla cache, esegue banco_strata.py, spegne strata.exe e il server.
Un punto alla volta, in serie. Tutto sotto D:\\ds4_work\\strata\\curva; i risultati del banco in banco_run.

Uso:  python curva_strata.py [punto ...]     (senza argomenti: tutti i punti, nell'ordine)
"""
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
S = Path(r"D:\ds4_work\strata\Strata")
OUT = Path(r"D:\ds4_work\strata\curva")
PY = S / ".venv" / "Scripts" / "python.exe"
BASE = json.loads((S / "strata-iq3_xxs-r1032.json").read_text(encoding="utf-8-sig"))
PORTA = 18120

# punto -> argomenti che sostituiscono --expert-cache / --vram-reserve-mib della configurazione base
PUNTI = {
    "auto_r1032": ["--expert-cache", "auto", "--vram-reserve-mib", "1032"],
    "auto_r700": ["--expert-cache", "auto", "--vram-reserve-mib", "700"],
    "n1100_r1032": ["--expert-cache", "1100", "--vram-reserve-mib", "1032"],
    "n600_r1032": ["--expert-cache", "600", "--vram-reserve-mib", "1032"],
}


def vram_mib():
    o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True).stdout.strip()
    return int(o.split()[0])


def args_punto(extra):
    a, i = [], 0
    base = BASE["args"]
    while i < len(base):
        if base[i] in ("--expert-cache", "--vram-reserve-mib"):
            i += 2
            continue
        a.append(base[i])
        i += 1
    return a + extra


def ferma():
    for filtro in ('name="strata.exe"', 'name="python.exe" and commandline like "%serve\\\\server.py%--engine strata%"'):
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-CimInstance Win32_Process -Filter '{filtro}' | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                       capture_output=True)
    for _ in range(30):
        vivi = subprocess.run(["tasklist", "/FI", "IMAGENAME eq strata.exe", "/NH"], capture_output=True, text=True).stdout
        if "strata.exe" not in vivi:
            return
        time.sleep(2)


def pronto(timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scelti = sys.argv[1:] or list(PUNTI)
    riassunto = []
    for nome in scelti:
        ferma()
        time.sleep(5)
        cfg = dict(BASE, args=args_punto(PUNTI[nome]), log=str(OUT / f"strata_{nome}.log"))
        cfg_path = S / f"curva_{nome}.json"
        cfg_path.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        v0 = vram_mib()
        print(f"[{datetime.now():%H:%M:%S}] {nome}: VRAM altri programmi {v0} MiB, lancio", flush=True)
        srv = subprocess.Popen([str(PY), str(S / "serve" / "server.py"), "--engine", "strata", "--config", str(cfg_path),
                                "--port", str(PORTA)], cwd=str(S),
                               stdout=open(OUT / f"server_{nome}.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
        rec = {"punto": nome, "args": PUNTI[nome], "vram_altri_mib": v0}
        if not pronto():
            rec["errore"] = "server non pronto"
            print(f"  {nome}: server non pronto", flush=True)
        else:
            righe = [l.strip() for l in Path(cfg["log"]).read_text(encoding="utf-8", errors="replace").splitlines()
                     if "expert cache" in l or "VRAM free with everything" in l or "borrows" in l]
            rec["motore"] = righe
            for l in righe:
                print("  " + l, flush=True)
            b = subprocess.run([str(PY), str(HERE / "banco_strata.py"), "--profilo", "curva", "--url",
                                f"http://127.0.0.1:{PORTA}", "--etichetta", f"curva_{nome}",
                                "--nota", f"curva esperti->velocita', punto {nome}, VRAM altri {v0} MiB"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            for l in b.stdout.splitlines():
                if "@ctx" in l:
                    print(l, flush=True)
            corse = sorted(Path(r"D:\ds4_work\strata\banco_run").glob(f"*curva_{nome}_curva"))
            if corse:
                rec["corsa"] = corse[-1].name
                rec["riassunto"] = json.loads((corse[-1] / "riassunto.json").read_text(encoding="utf-8"))
        ferma()
        srv.wait(timeout=60)
        riassunto.append(rec)
        (OUT / "riassunto_curva.json").write_text(json.dumps(riassunto, indent=1, ensure_ascii=False), encoding="utf-8")
    print("FINE", flush=True)


if __name__ == "__main__":
    main()
