"""Bisezione 0.1.45 vs 0.1.43: una corsa = un braccio. uso: python -u bab.py <tag> <braccio> [--targets 4096,32768] [--runs 3]
Copia di community_bench.py (stesso metodo, porta 8105, bench.lock) con bracci definiti qui; non modifica i json/build del Daily."""
import os, sys, time, json, subprocess, urllib.request
from pathlib import Path

LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
PAUSE = Path(r'D:\ds4_work\strata\lab_locks\pause')
S = Path(r'D:\ds4_work\strata\Strata')
HERE = Path(__file__).resolve().parent
BENCH = Path(r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py')
B0143 = (S / 'strata-0143-daily.json', S / 'build-0143-daily')
N0145 = (HERE.parent / 'strata-0145-nobatch.json', S / 'build-0145-daily')
HCB = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-upsmain-d9a26384')
CONV_SMALL = ('6144', '2')
# bracci che cambiano solo argomenti sul 0.1.45 nobatch: nome -> {opzione: valore}
ARGSET = {'R': {'--vram-reserve-mib': '1905', '--vram-reserve-later-mib': '700'},        # riserve VRAM del Daily 0.1.45 (VERSIONE.txt)
          'R2': {'--vram-reserve-mib': '1600', '--vram-reserve-later-mib': '900'}}       # valori suggeriti dai warning del motore


def arm(n):
    """-> (json base, build dir, env da aggiungere, env da togliere, override cache conversazioni)"""
    if n == 'B':
        return B0143 + ({}, [], None)
    if n == 'Bx':                                    # braccio 3 al contrario: la 0.1.43 senza le leve lab/struct-a (NODECUT, TOPK_GRID, B6_HEAD_MINB)
        return B0143 + ({}, ['STRATA_NODECUT', 'STRATA_TOPK_GRID', 'STRATA_B6_HEAD_MINB', 'STRATA_QFUSE_HC'], None)
    cfg, bld = N0145
    env, drop, conv = {}, [], None
    if n in ARGSET:
        return cfg, bld, env, drop, conv
    if n == 'N':
        pass
    elif n == 'P':                                   # braccio 1
        env['STRATA_PIPED_CONCURRENT'] = '0'
    elif n == 'G':                                   # NAN_GUARD (#1892, acceso in 0.1.45) spento
        env['STRATA_NAN_GUARD'] = '0'
    elif n == 'S':                                   # braccio 2
        drop.append('STRATA_P2_FLUSH_NOSWITCH')
    elif n == 'V':                                   # differenza di argomenti: cache conversazioni 6144/2 come la 0.1.43
        conv = CONV_SMALL
    elif n == 'C':                                   # P + S + V insieme
        env['STRATA_PIPED_CONCURRENT'] = '0'; drop.append('STRATA_P2_FLUSH_NOSWITCH'); conv = CONV_SMALL
    elif n in ('H', 'H0'):                           # braccio 5: build upstream 0.1.45 + hc16
        bld = HCB
        if n == 'H':
            env['STRATA_HC16_SM75'] = '1'
    elif n == 'HC':                                  # build hc16 + P + S + V
        bld = HCB; env['STRATA_HC16_SM75'] = '1'; env['STRATA_PIPED_CONCURRENT'] = '0'
        drop.append('STRATA_P2_FLUSH_NOSWITCH'); conv = CONV_SMALL
    else:
        raise SystemExit('braccio sconosciuto ' + n)
    return cfg, bld, env, drop, conv


def ps(cmd):
    return subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True).stdout.strip()


def cpu_idle():
    return '/'.join(ps("(Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 3).CounterSamples | % { [math]::Round($_.CookedValue,1) }").split())


def jumpcpu():
    return ps('(Get-Process JumpConnect | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum')


def gpustat():
    return subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu', '--format=csv,noheader'],
                          capture_output=True, text=True).stdout.replace('\n', ' | ')


def main():
    tag, name = sys.argv[1], sys.argv[2]
    targets, runs = '4096,32768', '3'
    if '--targets' in sys.argv:
        targets = sys.argv[sys.argv.index('--targets') + 1]
    if '--runs' in sys.argv:
        runs = sys.argv[sys.argv.index('--runs') + 1]
    OUT = HERE / f'{tag}-{name}'
    OUT.mkdir(parents=True, exist_ok=True)
    cfgp, bld, env, drop, conv = arm(name)
    c = json.loads(Path(cfgp).read_text(encoding='utf-8-sig'))
    c['exe'] = str(Path(bld) / 'strata.exe')
    c['log'] = str(OUT / 'engine.log')
    a = c['args']
    a[a.index('--prompt-cache-file') + 1] = str(OUT / 'prefix.bin')
    if conv:
        a[a.index('--conversation-cache-mib') + 1] = conv[0]
        a[a.index('--conversation-cache-slots') + 1] = conv[1]
    for k, v in ARGSET.get(name, {}).items():
        a[a.index(k) + 1] = v
    c['env'].update(env)
    for k in drop:
        c['env'].pop(k, None)
    cfg = OUT / 'config.json'
    cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')
    while True:
        if not PAUSE.exists():
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, b'BANCO-COMUNITA-BISEZIONE')
                os.close(fd)
                break
            except FileExistsError:
                pass
        time.sleep(0.5)
    try:
        amb = f'inizio {time.strftime("%H:%M")} braccio {name} build {Path(bld).name} jump_cpu_s {jumpcpu()} cpu_idle_% {cpu_idle()} gpu {gpustat()}\n'
        (OUT / 'ambiente.txt').write_text(amb, encoding='utf-8')
        senv = dict(os.environ)
        senv['STRATA_PROMPT_ENCODER'] = '1'   # come la bat della 0.1.43 (nella 0.1.45 e' incondizionato)
        log = open(OUT / 'server.log', 'w', encoding='utf-8')
        py = str(S / '.venv/Scripts/python.exe')
        p = subprocess.Popen([py, str(Path(bld) / 'source/serve/server.py'), '--engine', 'strata', '--config', str(cfg),
                              '--host', '127.0.0.1', '--port', '8105'], stdout=log, stderr=subprocess.STDOUT, env=senv)
        try:
            t0 = time.time()
            while True:
                try:
                    urllib.request.urlopen('http://127.0.0.1:8105/v1/models', timeout=5)
                    break
                except Exception:
                    if p.poll() is not None:
                        raise SystemExit('server uscito')
                    if time.time() - t0 > 900:
                        raise SystemExit('avvio oltre 15 min')
                    time.sleep(5)
            print('pronto in %.0f s' % (time.time() - t0), flush=True)
            subprocess.run([py, str(BENCH), '--root', str(Path(bld) / 'source'), '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs',
                            '--url', 'http://127.0.0.1:8105', '--out', str(OUT), '--targets', targets, '--runs', runs], check=False)
        finally:
            with open(OUT / 'ambiente.txt', 'a', encoding='utf-8') as f:
                f.write(f'fine {time.strftime("%H:%M")} jump_cpu_s {jumpcpu()} gpu {gpustat()}\n')
            p.terminate()
            time.sleep(5)
            subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    finally:
        LOCK.unlink(missing_ok=True)
        print('motore fermato, lock rilasciato', flush=True)


main()
