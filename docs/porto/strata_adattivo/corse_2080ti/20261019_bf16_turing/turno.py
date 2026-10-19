"""19/10 (bf16-turing): prendere il turno in un laboratorio dove le code concatenano i bracci senza pause.

    python turno.py <nome> --hold -- <comando...>    bench.lock tenuto da noi per tutto il comando (microbanco)
    python turno.py <nome> --queue -- <comando...>   il comando prende bench.lock da sé (coda di run_long)

Prenotazione: build.lock (O_EXCL) fa aspettare il prossimo braccio delle altre code (run_long guarda build.lock prima di
bench.lock); appena il braccio in corso rilascia bench.lock e nessun strata.exe gira, --hold prende bench.lock (O_EXCL) e
rilascia build.lock; --queue rilascia build.lock e lancia subito la coda.  pause blocca tutto.  Mai priorità alta.
"""
import os, subprocess, sys, time
from pathlib import Path

L = Path(r'D:\ds4_work\strata\lab_locks')
name, mode = sys.argv[1], sys.argv[2]
cmd = sys.argv[sys.argv.index('--') + 1:]


def engine():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True, errors='replace')
    return 'strata.exe' in r.stdout.lower()


def excl(p, text):
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, text.encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


t0 = time.time()
while (L / 'pause').exists() or not excl(L / 'build.lock', f'turno {name}'):
    time.sleep(2)
print(f'turno prenotato dopo {time.time() - t0:.0f} s', flush=True)
held = False
try:
    while (L / 'bench.lock').exists() or (L / 'pause').exists() or engine():
        time.sleep(1)
    if mode == '--hold':
        while not excl(L / 'bench.lock', name):
            time.sleep(1)
        held = True
finally:
    (L / 'build.lock').unlink(missing_ok=True)
print(f'turno preso dopo {time.time() - t0:.0f} s', flush=True)
try:
    rc = subprocess.run(cmd).returncode
finally:
    if held:
        (L / 'bench.lock').unlink(missing_ok=True)
sys.exit(rc)
