"""lab_run.py - esegue un comando pesante (GPU/CPU) sotto D:\\ds4_work\\strata\\lab_locks\\bench.lock (O_EXCL), con un tetto di
tempo, uccidendo prima i figli e poi il padre, e rilasciando sempre il lock.

    python lab_run.py --name mtp-smoke --max-min 30 [--wait-min 60] -- python capture_driver.py ...

Regole del lab (6/10, run_long.py): si aspetta finche' esistono build.lock o pause; bench.lock e' esclusivo; nel lock
si scrive chi lo tiene.  `closed` non ferma questo runner: il coordinatore ha autorizzato i lavori MTP del 12/10 (si
registra l'avviso nel log).  Niente strata.exe altrui in esecuzione: se ce n'e' uno, si aspetta.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

LOCKS = Path(r"D:\ds4_work\strata\lab_locks")


def other_strata_running() -> list[str]:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq strata.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    except Exception:
        return []
    return [line for line in out.splitlines() if line.lower().startswith('"strata.exe"')]


def kill_tree(p: subprocess.Popen):
    try:   # i figli prima del padre (taskkill /T parte dalle foglie)
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    except Exception:
        pass
    try:
        p.wait(timeout=30)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--max-min", type=float, required=True, help="tetto di tempo del comando")
    ap.add_argument("--wait-min", type=float, default=60.0, help="quanto aspettare il lock")
    ap.add_argument("--cwd", default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        print("nessun comando")
        return 2
    LOCKS.mkdir(parents=True, exist_ok=True)
    if (LOCKS / "closed").exists():
        print(f"avviso: lab_locks/closed presente ({(LOCKS / 'closed').read_text().strip()}); lavori MTP autorizzati dal coordinatore il 12/10", flush=True)
    t0 = time.time()
    fd = None
    while fd is None:
        if time.time() - t0 > a.wait_min * 60:
            print("lock non ottenuto entro il tempo: rinuncio")
            return 3
        busy = other_strata_running()
        if (LOCKS / "build.lock").exists() or (LOCKS / "pause").exists() or busy:
            time.sleep(10)
            continue
        try:
            fd = os.open(LOCKS / "bench.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            time.sleep(10)
    os.write(fd, f"{a.name} pid={os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')} max {a.max_min:g} min\n".encode())
    os.close(fd)
    print(f"lock preso dopo {time.time() - t0:.0f} s di attesa", flush=True)
    rc = -1
    p = None
    try:
        p = subprocess.Popen(cmd, cwd=a.cwd)
        try:
            rc = p.wait(timeout=a.max_min * 60)
        except subprocess.TimeoutExpired:
            print(f"tetto di {a.max_min:g} min raggiunto: uccido figli e padre", flush=True)
            kill_tree(p)
            rc = 124
    except KeyboardInterrupt:
        if p is not None:
            kill_tree(p)
        rc = 130
    finally:
        if p is not None and p.poll() is None:
            kill_tree(p)
        for _ in range(5):   # il motore puo' avere figli che chiudono i file con calma
            try:
                (LOCKS / "bench.lock").unlink()
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(1)
        print("lock rilasciato", flush=True)
    print(f"{a.name} rc={rc} in {(time.time() - t0) / 60:.1f} min", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
