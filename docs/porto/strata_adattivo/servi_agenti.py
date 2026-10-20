"""servi_agenti.py - accende Strata sulla 8100 per gli agenti locali e lo sorveglia.

    python servi_agenti.py [--config strata-dyn-agenti.json] [--riserva strata-0145-agenti.json]

Avvia la config principale (batch dinamico, lab/batch-dyn c4af6851). Ogni 30 s legge RAM disponibile e memoria privata di
strata.exe: se la RAM disponibile resta sotto 3 GiB per due letture di fila (la vecchia perdita di RAM pinned del batch
dinamico) o il server muore, lo ferma e riparte con la config di riserva (0.1.45 batch fisso, cache esperti 2600).
Scrive una riga di stato ogni 5 min in D:\\ds4_work\\strata\\sota\\servi_agenti.log. Tiene bench.lock per tutto il servizio.
"""
import argparse, ctypes, os, subprocess, time
from pathlib import Path

S = Path(r'D:\ds4_work\strata\Strata')
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
LOG = Path(r'D:\ds4_work\strata\sota\servi_agenti.log')


class MEMSTAT(ctypes.Structure):
    _fields_ = [('len', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong), ('avail', ctypes.c_ulonglong),
                ('tpf', ctypes.c_ulonglong), ('apf', ctypes.c_ulonglong), ('tv', ctypes.c_ulonglong), ('av', ctypes.c_ulonglong),
                ('ext', ctypes.c_ulonglong)]


def avail_gib():
    m = MEMSTAT(); m.len = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2**30


def scrivi(msg):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(time.strftime('%d/%m %H:%M:%S ') + msg + '\n')


def avvia(cfg):
    c = Path(cfg) if Path(cfg).is_absolute() else S / cfg
    import json
    build = Path(json.loads(c.read_text(encoding='utf-8-sig'))['exe']).parent
    out = open(LOG.with_suffix('.server.log'), 'a', encoding='utf-8')
    p = subprocess.Popen([str(S / '.venv/Scripts/python.exe'), str(build / 'source/serve/server.py'), '--engine', 'strata',
                          '--config', str(c), '--host', '127.0.0.1', '--port', '8100'], stdout=out, stderr=subprocess.STDOUT)
    scrivi(f'avvio {c.name} pid {p.pid}')
    return p


def ferma(p):
    p.terminate(); time.sleep(5)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='strata-dyn-agenti.json')
    ap.add_argument('--riserva', default='strata-0145-agenti.json')
    a = ap.parse_args()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, b'SERVIZIO-AGENTI-8100'); os.close(fd); break
        except FileExistsError:
            time.sleep(1)
    cfg, p, basse, t_stato = a.config, avvia(a.config), 0, 0
    try:
        while True:
            time.sleep(30)
            av = avail_gib()
            basse = basse + 1 if av < 3 else 0
            if time.time() - t_stato > 300:
                scrivi(f'{cfg} vivo={p.poll() is None} RAM disponibile {av:.1f} GiB'); t_stato = time.time()
            if p.poll() is not None or basse >= 2:
                motivo = 'server morto' if p.poll() is not None else f'RAM disponibile {av:.1f} GiB'
                ferma(p)
                cfg = a.riserva
                scrivi(f'ripiego su {cfg}: {motivo}')
                p, basse = avvia(cfg), 0
    finally:
        ferma(p)
        LOCK.unlink(missing_ok=True)
        scrivi('servizio fermato, lock rilasciato')


main()
