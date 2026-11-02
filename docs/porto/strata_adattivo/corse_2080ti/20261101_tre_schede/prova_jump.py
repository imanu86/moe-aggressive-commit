"""Prova 02/11/2026: scrittura continua mentre l'owner si collega con Jump.
v0.2.9, due schede, divisione 20, tutte le leve della 2080 Ti, dietro bench.lock, porta 8105. Una riga al secondo in corse_jump/<nome>/secondi.csv:
ora, token nel secondo, CPU di JumpConnect (core), uso della 3060. Finisce dopo i minuti chiesti o quando compare il file STOP nella cartella.

    python prova_jump.py <nome> [minuti]
"""
import csv, json, os, subprocess, sys, threading, time, urllib.request
from pathlib import Path

import psutil

QUI = Path(__file__).resolve().parent
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
PY = Path(r'D:\ds4_work\strata\Strata\.venv\Scripts\python.exe')
CFG = QUI.parent / '20261029_upsync0271' / 'strata-0271-pila-3080ti.json'
B = QUI.parent / '20261004_routed_keep' / 'build-up029pila-b6ba3fa6'
nome, minuti = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 15
OUT = QUI / 'corse_jump' / nome
OUT.mkdir(parents=True, exist_ok=True)
STOP = OUT / 'STOP'

c = json.loads(CFG.read_text(encoding='utf-8-sig'))
a = c['args']
a[a.index('--layer-split') + 1] = '20'
a[a.index('--vram-reserve-mib') + 1] = '700'
a[a.index('--vram-reserve-later-mib') + 1] = '384'
i = a.index('--prompt-cache-file')
del a[i:i + 2]
c['exe'] = str(B / 'strata.exe')
c['vision']['exe'] = str(B / 'strata-vision.exe')
c['log'] = str(OUT / 'engine.log')
c['env'].update({'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'CUDA_VISIBLE_DEVICES': '0,2', 'STRATA_ROUTE_PRIOR': '0',
                 'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8'})
c['env'].pop('STRATA_MMVQ_IL', None)
(OUT / 'config.json').write_text(json.dumps(c, indent=1), encoding='utf-8')

fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
os.write(fd, b'PROVA-JUMP')
os.close(fd)
slog = open(OUT / 'server.log', 'w', encoding='utf-8')
srv = subprocess.Popen([str(PY), str(B / 'source/serve/server.py'), '--engine', 'strata', '--config', str(OUT / 'config.json'),
                        '--host', '127.0.0.1', '--port', '8105'], stdout=slog, stderr=subprocess.STDOUT)
conta = [0]
fine = threading.Event()


def jump_cpu():
    t = 0.0
    for p in psutil.process_iter(['name']):
        try:
            if (p.info['name'] or '').lower().startswith('jump'):
                x = p.cpu_times()
                t += x.user + x.system
        except psutil.Error:
            pass
    return t


def registra():
    with open(OUT / 'secondi.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['ora', 'token', 'jump_core', 'uso_3060'])
        prima, pj, n = 0, jump_cpu(), 0
        u = ''
        while not fine.is_set():
            time.sleep(1)
            n += 1
            ora, j = conta[0], jump_cpu()
            if n % 5 == 0:
                r = subprocess.run(['nvidia-smi', '-i', '1', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                                   capture_output=True, text=True)
                u = r.stdout.strip()
            w.writerow([time.strftime('%H:%M:%S'), ora - prima, round(j - pj, 2), u])
            f.flush()
            prima, pj = ora, j


TESTO = ('Scrivi in italiano un manuale tecnico lunghissimo e dettagliato sulla progettazione di un compilatore: analisi lessicale, '
         'sintattica, semantica, rappresentazioni intermedie, ottimizzazioni e generazione del codice, con esempi di codice per ogni capitolo.')


def richiesta():
    d = json.dumps({'model': 'strata', 'stream': True, 'max_tokens': 3000, 'temperature': 0,
                    'stream_options': {'include_usage': False}, 'messages': [{'role': 'user', 'content': TESTO}]}).encode()
    q = urllib.request.Request('http://127.0.0.1:8105/v1/chat/completions', d, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(q, timeout=900) as r:
        for riga in r:
            if riga.startswith(b'data: ') and b'"delta"' in riga:
                conta[0] += 1
            if STOP.exists():
                return


try:
    t0 = time.time()
    while True:
        try:
            urllib.request.urlopen('http://127.0.0.1:8105/v1/models', timeout=5)
            break
        except Exception:
            if srv.poll() is not None or time.time() - t0 > 900:
                raise RuntimeError('motore non partito')
            time.sleep(3)
    print('PRONTO', flush=True)
    th = threading.Thread(target=registra, daemon=True)
    th.start()
    t1 = time.time()
    while time.time() - t1 < minuti * 60 and not STOP.exists():
        richiesta()
    fine.set()
    th.join(3)
finally:
    srv.terminate()
    time.sleep(5)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    slog.close()
    LOCK.unlink(missing_ok=True)
print('FINITO', flush=True)
