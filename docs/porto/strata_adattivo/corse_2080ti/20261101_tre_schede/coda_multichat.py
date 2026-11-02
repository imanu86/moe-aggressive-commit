"""Multichat 01/11/2026: 3080 Ti + 2080 Ti libere (3060 con schermo e OktoCGControl). Replay DSH 3600+1200 s, sessioni A,B,C, come 29/10.
Tutte le corse: STRATA_ROUTE_PRIOR=0, PIPED_CONCURRENT=1, batch 4, cache conversazioni 18432 MiB / 16 posti.

    python coda_multichat.py <split> braccio[:dup] ...     (dup 2 = 6 agenti)
Output in corse_mc/replay_<NN>_<braccio>_s<split>[_6ag]. Sempre dietro bench_lock; a fine corsa strata.exe spento e lock tolto.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
K = CORSE / '20261004_routed_keep'
B0271, B029 = K / 'build-up0271pila-5fbc4784', K / 'build-up029pila-b6ba3fa6'
OUT = HERE / 'corse_mc'
G = '--batch 4 --conversation-cache-mib 18432 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700'
PC = 'STRATA_ROUTE_PRIOR=0 STRATA_PIPED_CONCURRENT=1'
COAL = PC + ' STRATA_COALESCE_PREFILL=4 STRATA_COALESCE_MIN_REQS=2 STRATA_COALESCE_BURST_MS=1000 STRATA_COALESCE_WAIT_MS=50'
ARMS = {
    'p': (B0271, PC),      # v0.2.7.1 + pila
    'u': (B029, PC),       # v0.2.9 + pila
    'c': (B029, COAL),     # v0.2.9 + lettura condivisa
}
cfg = OUT / 'cfg-due-schede.json'
OUT.mkdir(exist_ok=True)
c = json.loads((CORSE / '20261029_multichat' / 'cfg-up0271-3080ti.json').read_text(encoding='utf-8-sig'))
c['env'].update({'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'CUDA_VISIBLE_DEVICES': '0,2', 'STRATA_ROUTE_PRIOR': '0'})
cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')
split = sys.argv[1]
n = len([p for p in OUT.iterdir() if p.name.startswith('replay_')])
for spec in sys.argv[2:]:
    arm, _, dup = spec.partition(':')
    n += 1
    build, env = ARMS[arm]
    tag = f'{n:02d}_{arm}_s{split}' + (f'_{int(dup) * 3}ag' if dup else '')
    cmd = [sys.executable, '-u', str(CORSE / '20261006_due_schede' / 'bench_lock.py'), f'MULTICHAT-{tag}', '--',
           sys.executable, '-u', '-X', 'utf8', str(CORSE / '20261019_replay' / 'replay_trace.py'), '--tag', tag, '--t0', '3600', '--span', '1200',
           '--only', 'A,B,C', '--config', str(cfg), '--exe', str(build / 'strata.exe'),
           '--out-base', str(OUT), '--port', '8102', f'--extra={G} --layer-split {split}', '--env=' + env]
    if dup:
        cmd += ['--dup', dup]
    print(f'== {tag}: {env}', flush=True)
    rc = subprocess.run(cmd).returncode
    print(f'== {tag} uscita {rc}', flush=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    Path(r'D:\ds4_work\strata\lab_locks\bench.lock').unlink(missing_ok=True)
print('== multichat finita', flush=True)
