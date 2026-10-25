"""Banco della comunità (benchmark.py del report RTX 5090) sulla Daily 0.1.45, porta 8105, sotto bench.lock.
Stesso metodo dei 2x5060 Ti: prompt freschi 4K/32K/128K, 3 corse, greedy, 256 token, ragionamento off."""
import os, sys, time, json, subprocess, urllib.request
from pathlib import Path

LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
PAUSE = Path(r'D:\ds4_work\strata\lab_locks\pause')
S = Path(r'D:\ds4_work\strata\Strata')
OUT = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_banco_comunita') / sys.argv[1]
BENCH = Path(r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py')
OUT.mkdir(parents=True, exist_ok=True)
CFG = sys.argv[2] if len(sys.argv) > 2 else 'strata-0145-daily.json'
BLD = sys.argv[3] if len(sys.argv) > 3 else 'build-0145-daily'
c = json.loads((S / CFG).read_text(encoding='utf-8-sig'))
c['log'] = str(OUT / 'engine.log')
a = c['args']
if '--prompt-cache-file' in a:   # la 0.2.6 pura non ha l'opzione (25/10)
    pf = a.index('--prompt-cache-file'); a[pf + 1] = str(OUT / 'prefix.bin')
cfg = OUT / 'config.json'; cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')

while True:
    if not PAUSE.exists():
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, b'BANCO-COMUNITA'); os.close(fd); break
        except FileExistsError:
            pass
    time.sleep(1)
jump = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process JumpConnect | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum'], capture_output=True, text=True).stdout.strip()
(OUT / 'ambiente.txt').write_text(f'inizio {time.strftime("%H:%M")} jump_cpu_s {jump}\n', encoding='utf-8')
log = open(OUT / 'server.log', 'w', encoding='utf-8')
p = subprocess.Popen([str(S / '.venv/Scripts/python.exe'), str(S / (BLD + '/source/serve/server.py')), '--engine', 'strata',
                      '--config', str(cfg), '--host', '127.0.0.1', '--port', '8105'], stdout=log, stderr=subprocess.STDOUT)
try:
    t0 = time.time()
    while True:
        try:
            urllib.request.urlopen('http://127.0.0.1:8105/v1/models', timeout=5); break
        except Exception:
            if p.poll() is not None: raise SystemExit('server uscito')
            if time.time() - t0 > 900: raise SystemExit('avvio oltre 15 min')
            time.sleep(5)
    print('pronto in %.0f s' % (time.time() - t0), flush=True)
    subprocess.run([str(S / '.venv/Scripts/python.exe'), str(BENCH), '--root', str(S / (BLD + '/source')),
                    '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs', '--url', 'http://127.0.0.1:8105', '--out', str(OUT)], check=False)
finally:
    jump = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process JumpConnect | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum'], capture_output=True, text=True).stdout.strip()
    with open(OUT / 'ambiente.txt', 'a', encoding='utf-8') as f: f.write(f'fine {time.strftime("%H:%M")} jump_cpu_s {jump}\n')
    p.terminate(); time.sleep(5)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    LOCK.unlink(missing_ok=True)
    print('motore fermato, lock rilasciato', flush=True)
