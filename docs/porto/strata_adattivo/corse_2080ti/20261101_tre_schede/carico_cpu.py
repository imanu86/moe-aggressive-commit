"""Carico CPU per le prove sotto carico: N processi a priorita' normale che girano a vuoto, come agenti che compilano.
Si fermano quando esce il processo che li ha lanciati o appare il file STOP accanto allo script.

    python carico_cpu.py 6
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

STOP = Path(__file__).resolve().parent / 'STOP_CARICO'


def gira():
    x = 0
    while True:
        for _ in range(2_000_000):
            x = (x * 31 + 7) & 0xFFFFFFFF
        if STOP.exists():
            return


if __name__ == '__main__':
    STOP.unlink(missing_ok=True)
    pp = [mp.Process(target=gira, daemon=True) for _ in range(int(sys.argv[1]))]
    for p in pp:
        p.start()
    print(f'carico acceso: {len(pp)} processi', flush=True)
    while not STOP.exists():
        time.sleep(2)
    for p in pp:
        p.join(5)
    STOP.unlink(missing_ok=True)
    print('carico spento', flush=True)
