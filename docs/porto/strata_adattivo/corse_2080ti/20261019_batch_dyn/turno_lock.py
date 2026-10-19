"""Il turno del laboratorio come turno.py di 20261019_bf16_turing: prenotazione con build.lock (O_EXCL; le code che guardano
build.lock aspettano), poi bench.lock (O_EXCL) appena il braccio in corso lo rilascia e nessun strata.exe gira, poi build.lock
torna libero.  pause ferma tutto (prima di prendere bench.lock).  Ritorna True col bench.lock tenuto, False con pause."""
import os, time
from pathlib import Path

import psutil

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')


def _excl(p, text):
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, text.encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _engine():
    return any((q.info['name'] or '').lower() == 'strata.exe' for q in psutil.process_iter(['name']))


def take(name):
    while not _excl(LOCKS / 'build.lock', f'turno {name}'):
        if (LOCKS / 'pause').exists():
            return False
        time.sleep(1)
    try:
        while True:
            if (LOCKS / 'pause').exists():
                return False
            if not (LOCKS / 'bench.lock').exists() and not _engine() and _excl(LOCKS / 'bench.lock', name):
                return True
            time.sleep(0.5)
    finally:
        (LOCKS / 'build.lock').unlink(missing_ok=True)


def release():
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
