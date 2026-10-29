"""Multichat sulla build v0.2.7.1 + pila (29/10/2026). Replay DSH, tratto 3600+1200 s, sessioni A,B,C, prima richiesta di ogni avvio scartata.
Tutte le corse: STRATA_ROUTE_PRIOR=0, 3080 Ti stadio 0 (cfg-up0271-3080ti.json), priorita' normale.

    python coda_multichat.py R0 P PC            # 3 agenti
    python coda_multichat.py R0:2 P:2           # 6 agenti (--dup 2)
Output in corse/replay_<NN>_<braccio>[_6ag].  Sempre dietro bench_lock; a fine corsa strata.exe spento e lock tolto.
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
BUILD = CORSE / '20261004_routed_keep' / 'build-up0271pila-5fbc4784'
G = '--conversation-cache-mib 18432 --conversation-cache-slots 16'
R4 = '--vram-reserve-mib 1905 --vram-reserve-later-mib 700'
ROUTE = 'STRATA_ROUTE_PRIOR=0'
ARMS = {
    'R0': ('', ROUTE),
    'P': (f'--batch 4 {G} {R4}', ROUTE),
    'PC': (f'--batch 4 {G} {R4}', ROUTE + ' STRATA_PIPED_CONCURRENT=1'),
}
(HERE / 'corse').mkdir(exist_ok=True)
n = len([p for p in (HERE / 'corse').iterdir() if p.name.startswith('replay_')])
for spec in sys.argv[1:]:
    arm, _, dup = spec.partition(':')
    n += 1
    extra, env = ARMS[arm]
    tag = f'{n:02d}_{arm}' + (f'_{int(dup) * 3}ag' if dup else '')
    cmd = [sys.executable, '-u', str(CORSE / '20261006_due_schede' / 'bench_lock.py'), f'MULTICHAT-{tag}', '--',
           sys.executable, '-u', '-X', 'utf8', str(CORSE / '20261019_replay' / 'replay_trace.py'), '--tag', tag, '--t0', '3600', '--span', '1200',
           '--only', 'A,B,C', '--config', str(HERE / 'cfg-up0271-3080ti.json'), '--exe', str(BUILD / 'strata.exe'),
           '--out-base', str(HERE / 'corse'), '--port', '8102', '--extra=' + extra, '--env=' + env]
    if dup:
        cmd += ['--dup', dup]
    print(f'== {tag}: {extra!r} {env}', flush=True)
    rc = subprocess.run(cmd).returncode
    print(f'== {tag} uscita {rc}', flush=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    Path(r'D:\ds4_work\strata\lab_locks\bench.lock').unlink(missing_ok=True)
