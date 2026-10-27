"""Banco della comunita' (benchmark.py del report RTX 5090) su StrataFast, porta 8105, sotto bench.lock.
Uso: python sf_bench.py <tag> <L|0> [--targets 32768,65536,128000] [--runs 3] [--smoke]
L = valore di --prompt-split (0 = spento: il flag non c'e').  Config: strata-stratafast.json (accanto a questo file).
Stesso metodo del banco 4K/32K/128K: prompt freschi con nonce, greedy, 256 token, ragionamento off."""
import os, sys, time, json, subprocess, urllib.request, argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('tag'); ap.add_argument('split', type=int)
ap.add_argument('--targets', default='32768,65536,128000'); ap.add_argument('--runs', type=int, default=3)
ap.add_argument('--smoke', action='store_true'); ap.add_argument('--extra', default='')
a = ap.parse_args()

HERE = Path(__file__).resolve().parent
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
PAUSE = Path(r'D:\ds4_work\strata\lab_locks\pause')
S = Path(r'D:\ds4_work\strata\Strata')
SRC = HERE.parent / '20261004_routed_keep' / 'build-stratafast-dd0390fb' / 'source'
OUT = HERE / a.tag
OUT.mkdir(parents=True, exist_ok=True)
c = json.loads((HERE / 'strata-stratafast.json').read_text(encoding='utf-8'))
c['log'] = str(OUT / 'engine.log')
c['args'] += a.extra.split()
if a.split > 0:
    c['args'] += ['--prompt-split', str(a.split)]
cfg = OUT / 'config.json'; cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')

while True:
    if not PAUSE.exists():
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, b'STRATAFAST-' + a.tag.encode()); os.close(fd); break
        except FileExistsError:
            pass
    time.sleep(1)


def jump():
    return subprocess.run(['powershell', '-NoProfile', '-Command',
        '$p=Get-Process JumpConnect -ErrorAction SilentlyContinue | Where-Object SessionId -eq 1; if($p){($p|Measure-Object CPU -Sum).Sum}else{"assente"}'],
        capture_output=True, text=True).stdout.strip()


(OUT / 'ambiente.txt').write_text(f'inizio {time.strftime("%H:%M")} jump_cpu_s {jump()}\n', encoding='utf-8')
log = open(OUT / 'server.log', 'w', encoding='utf-8')
p = subprocess.Popen([str(S / '.venv/Scripts/python.exe'), str(SRC / 'serve/server.py'), '--engine', 'strata',
                      '--config', str(cfg), '--host', '127.0.0.1', '--port', '8105'], stdout=log, stderr=subprocess.STDOUT,
                     cwd=str(SRC))
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
    targets = '2048' if a.smoke else a.targets
    runs = '1' if a.smoke else str(a.runs)
    subprocess.run([str(S / '.venv/Scripts/python.exe'),
                    r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py',
                    '--root', str(SRC), '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs',
                    '--url', 'http://127.0.0.1:8105', '--out', str(OUT), '--targets', targets, '--runs', runs], check=False)
finally:
    with open(OUT / 'ambiente.txt', 'a', encoding='utf-8') as f: f.write(f'fine {time.strftime("%H:%M")} jump_cpu_s {jump()}\n')
    p.terminate(); time.sleep(5)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    LOCK.unlink(missing_ok=True)
    print('motore fermato, lock rilasciato', flush=True)
