"""Replay dei 3 agenti (../20261019_replay/replay_trace.py) sotto bench.lock, con la VRAM libera campionata ogni secondo.

    python run_replay_dyn.py <tag> -- <argomenti di replay_trace.py>

Il replay avvia e ferma da se' il proprio server (solo il proprio albero di processi).  Qui: lock (O_EXCL, come run_dyn.py), CPU di
JumpConnect prima e dopo, vram.csv in <tag>/.  Esce senza fare nulla se esiste lab_locks\\pause.
"""
import os, subprocess, sys, threading, time
from pathlib import Path

import psutil

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
H = Path(__file__).resolve().parent
R = H.parent / '20261019_replay'
tag = sys.argv[1]
rargs = sys.argv[sys.argv.index('--') + 1:]
OUT = H / tag
OUT.mkdir(parents=True, exist_ok=True)


def jump_cpu():
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
                        '(Get-Process JumpConnect -ErrorAction SilentlyContinue | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum'],
                       capture_output=True, text=True)
    return r.stdout.strip() or '0'


sys.path.insert(0, str(H))
import turno_lock  # noqa: E402
if not turno_lock.take(f'BATCHDYN-{tag}'):
    sys.exit('pause: niente GPU')
print('lock preso', time.strftime('%H:%M:%S'), flush=True)
amb = OUT / 'ambiente.txt'
amb.write_text(f'inizio {time.strftime("%H:%M:%S")} jump_cpu_s {jump_cpu()}\n', encoding='utf-8')
stop = threading.Event()


def vram_sampler():
    with open(OUT / 'vram.csv', 'w', encoding='utf-8') as f:
        f.write('t,gpu,free_mib,used_mib\n')
        while not stop.wait(1.0):
            r = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.free,memory.used', '--format=csv,noheader,nounits'],
                               capture_output=True, text=True)
            for line in r.stdout.strip().splitlines():
                f.write(f'{time.time():.1f},{line.replace(" ", "")}\n')
            f.flush()


threading.Thread(target=vram_sampler, daemon=True).start()
rc = 1
try:
    with open(OUT / 'replay.run.log', 'w', encoding='utf-8') as lf:
        rc = subprocess.run([sys.executable, '-u', str(R / 'replay_trace.py')] + rargs, cwd=R, stdout=lf,
                            stderr=subprocess.STDOUT).returncode
finally:
    stop.set()
    with open(amb, 'a', encoding='utf-8') as f:
        f.write(f'fine {time.strftime("%H:%M:%S")} jump_cpu_s {jump_cpu()} rc {rc}\n')
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
    print('lock rilasciato', time.strftime('%H:%M:%S'), 'rc', rc, flush=True)
sys.exit(rc)
