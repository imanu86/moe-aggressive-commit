"""(copia di 20261019_multichat45b/bench_fast.py) Come bench_lock.py ma con sondaggio ogni 0,2 s: il sondaggio da 10 s perdeva ogni volta contro la coda dei replay, che
riprende il lock nell'istante in cui lo libera.  Stessi controlli di bench_lock.py: niente build.lock, niente pause, niente strata.exe.
    python bench_fast.py <nome> -- <comando>"""
import os, subprocess, sys, time
from pathlib import Path

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
name = sys.argv[1]
cmd = sys.argv[sys.argv.index('--') + 1:]


def engine_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True, errors='replace')
    return 'strata.exe' in r.stdout.lower()


t0 = time.time()
while True:
    if not any((LOCKS / n).exists() for n in ('build.lock', 'pause', 'bench.lock')):
        try:
            fd = os.open(LOCKS / 'bench.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, name.encode())
            os.close(fd)
            if not engine_running():
                break
            (LOCKS / 'bench.lock').unlink(missing_ok=True)
        except FileExistsError:
            pass
    time.sleep(0.2)
print(f'bench lock taken after {time.time() - t0:.0f} s', flush=True)
try:
    rc = subprocess.run(cmd).returncode
finally:
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
sys.exit(rc)
