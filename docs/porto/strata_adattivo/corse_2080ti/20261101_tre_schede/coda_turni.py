"""Prova a piu' turni 02/11/2026: una sola conversazione che cresce da 29K a 97K (+13-14K a turno), 6 turni, sessione A della traccia DSH.
Due schede, stessa configurazione del banco (niente batch), pensiero azzerato. Testo sintetico della fixture, stessi turni in ogni corsa.

    python coda_turni.py <nome:build:split:riserva> ...      (build p = 0.2.7.1, u = 0.2.9)
Output in corse_turni/replay_<nome>. Sempre dietro bench_lock; a fine corsa strata.exe spento e lock tolto.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
K = CORSE / '20261004_routed_keep'
BUILD = {'p': K / 'build-up0271pila-5fbc4784', 'u': K / 'build-up029pila-b6ba3fa6'}
BASE = CORSE / '20261029_upsync0271' / 'strata-0271-pila-3080ti.json'
OUT = HERE / 'corse_turni'
OUT.mkdir(exist_ok=True)
for spec in sys.argv[1:]:
    nome, b, split, r0 = spec.split(':')
    build = BUILD[b]
    if (OUT / f'replay_{nome}' / 'res.json').exists():
        print(f'== {nome}: gia fatto, salto', flush=True)
        continue
    c = json.loads(BASE.read_text(encoding='utf-8-sig'))
    a = c['args']
    i = a.index('--prompt-cache-file')
    del a[i:i + 2]
    c['exe'] = str(build / 'strata.exe')
    c['vision']['exe'] = str(build / 'strata-vision.exe')
    c['env'].update({'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'CUDA_VISIBLE_DEVICES': '0,2', 'STRATA_ROUTE_PRIOR': '0'})
    cfg = OUT / f'cfg-{nome}.json'
    cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')
    extra = f'--layer-split {split} --vram-reserve-mib {r0} --vram-reserve-later-mib 384'
    cmd = [sys.executable, '-u', str(CORSE / '20261006_due_schede' / 'bench_lock.py'), f'TURNI-{nome}', '--',
           sys.executable, '-u', '-X', 'utf8', str(CORSE / '20261019_replay' / 'replay_trace.py'), '--tag', nome, '--t0', '80', '--span', '640',
           '--only', 'A', '--think-scale', '0', '--config', str(cfg), '--exe', str(build / 'strata.exe'),
           '--out-base', str(OUT), '--port', '8102', f'--extra={extra}', '--env=STRATA_ROUTE_PRIOR=0']
    print(f'== {nome}: {extra}', flush=True)
    rc = subprocess.run(cmd).returncode
    print(f'== {nome} uscita {rc}', flush=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    Path(r'D:\ds4_work\strata\lab_locks\bench.lock').unlink(missing_ok=True)
print('== turni finiti', flush=True)
