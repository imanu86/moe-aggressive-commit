"""Coda notturna 01/11/2026: 3080 Ti e 2080 Ti libere, 3060 con schermo e OktoCGControl.
Banco della comunita' (prompt freschi 4K/32K, 3 corse, T=0, 256 token) sotto bench.lock, porta 8105.
Un braccio fallito non ferma la coda. Non tocca Daily, bat o config della Daily.
Uso: coda_notte.py F1 | F2 ...   (fasi in FASI)."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

QUI = Path(__file__).resolve().parent
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
S = Path(r'D:\ds4_work\strata\Strata')
PY = S / '.venv/Scripts/python.exe'
BENCH = Path(r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py')
CFG = QUI.parent / '20261029_upsync0271' / 'strata-0271-pila-3080ti.json'
B0271 = QUI.parent / '20261004_routed_keep' / 'build-up0271pila-5fbc4784'
B029 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-b6ba3fa6'
DUE, TRE = '0,2', '0,2,1'   # PCI_BUS_ID: 0=3080 Ti, 1=3060, 2=2080 Ti


def freddi(n):
    """3060 (CUDA1) fuori dalla catena: tiene n esperti fissi tra quelli che le altre due non contengono.
    Niente --remote-expert-opt, che li farebbe ruotare. La 2080 Ti qui e' CUDA2, quindi il suo nucleo RAM passa a DEV2."""
    return {'_args': ['--split-device', '2', '--expert-cache-device1', str(n)], '_togli': ['--prompt-cache-file'],
            'STRATA_RAM_CORE_SLOTS_DEV1': None, 'STRATA_RAM_CORE_SLOTS_DEV2': '5500'}


def confronto(rip):
    """v0.2.9 e v0.2.7.1 alternate, stessa divisione, riserva 700/384."""
    return [(f'{n}{s}_{r}', b, s, DUE, 700, 384, {}) for r in rip for s in ('20', '18', '16', '22')
            for n, b in (('u', B029), ('p', B0271))]


SENZA_CATENA = {'_togli': ['--prompt-cache-file', '--pipeline-windows']}
PIENO = '4096,32768,128000'   # i tre bersagli del banco della comunita'
TUTTE = {'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8', 'STRATA_MMVQ_IL': None}
SPIN = {'STRATA_POOL_SPIN_US': None}
SM86 = {'STRATA_GU_SWIGLU': '1', 'STRATA_GR_UP75': '1', 'STRATA_CPU_IQ_ALL_EXACT1': '1'}

# nome, build, split, schede, riserva stadio 0, riserva stadi dopo, env in piu'
FASI = {
    'F1': [
        ('d16_r1393', B0271, '16', DUE, 1393, 384, {}),
        ('d16_r700', B0271, '16', DUE, 700, 384, {}),
        ('d18_r700', B0271, '18', DUE, 700, 384, {}),
        ('d20_r700', B0271, '20', DUE, 700, 384, {}),
        ('d22_r700', B0271, '22', DUE, 700, 384, {}),
        ('d16_r700_b', B0271, '16', DUE, 700, 384, {}),
    ],
    'F2': confronto('ab'),
    'F3': [
        ('t20_44', B0271, '20,44', TRE, 700, 384, {}),
        ('t20_42', B0271, '20,42', TRE, 700, 384, {}),
    ],
    'F4': [   # 384 non basta al secondo verificatore sullo stadio di mezzo
        ('t20_44_l1000', B0271, '20,44', TRE, 700, 1000, {}),
        ('t20_42_l1000', B0271, '20,42', TRE, 700, 1000, {}),
    ],
    'F5': [(f'h20_{n}', B0271, '20', '0,1,2', 700, 384, freddi(n)) for n in (1000, 2000, 4000)],
    'F7': [   # gli esperti freddi spengono catena doppia e nucleo RAM: paragone a due schede senza catena, poi di nuovo con la 3060
        ('n20_a', B0271, '20', DUE, 700, 384, {'_togli': ['--prompt-cache-file', '--pipeline-windows']}),
        ('f20_2000_b', B0271, '20', '0,1,2', 700, 384, freddi(2000)),
        ('n20_b', B0271, '20', DUE, 700, 384, {'_togli': ['--prompt-cache-file', '--pipeline-windows']}),
        ('f20_3000', B0271, '20', '0,1,2', 700, 384, freddi(3000)),
    ],
    'F8': [   # 02/11, OktoCGControl chiuso: stesse build delle corse col programma aperto, a coppie alternate
        ('oku20_a', B029, '20', DUE, 700, 384, {}),
        ('okp20_a', B0271, '20', DUE, 700, 384, {}),
        ('okn20_a', B0271, '20', DUE, 700, 384, SENZA_CATENA),
        ('okf20_2000_a', B0271, '20', '0,1,2', 700, 384, freddi(2000)),
        ('okf20_4000_a', B0271, '20', '0,1,2', 700, 384, freddi(4000)),
        ('oku20_b', B029, '20', DUE, 700, 384, {}),
        ('okp20_b', B0271, '20', DUE, 700, 384, {}),
        ('okn20_b', B0271, '20', DUE, 700, 384, SENZA_CATENA),
        ('okf20_2000_b', B0271, '20', '0,1,2', 700, 384, freddi(2000)),
        ('okt20_44', B0271, '20,44', TRE, 700, 1000, {}),
    ],
    'F9': [   # prompt grandi: l'uso vero parte da 30K. 128K = stesso prompt del banco 19/10; la vecchia configurazione e' split 16 con riserva 1393
        (f'g{n}_{r}', b, s, DUE, r0, 384, {'_targets': '64000,128000'}) for r in 'ab' for n, b, s, r0 in
        (('16_vecchia', B0271, '16', 1393), ('20u', B029, '20', 700), ('22u', B029, '22', 700), ('24u', B029, '24', 700))
    ],
    'F10': [   # leve della 2080 Ti mai misurate qui (#2197, #4962), banco comunita' completo, a coppie alternate col riferimento
        (f'L{n}_{r}', B029, '20', DUE, 700, 384, {'_targets': PIENO, **e}) for r in 'ab' for n, e in (
            ('base', {}),
            ('il', {'STRATA_MMVQ_IL': None}),
            ('sm75', {'STRATA_SM75_PERF': '1'}),
            ('sm75m8', {'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8'}),
            ('tutte', {'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8', 'STRATA_MMVQ_IL': None}))
    ],
    'F11': [   # divisioni e vecchia configurazione sul banco completo
        (f'D{n}_{r}', b, s, DUE, r0, 384, {'_targets': PIENO}) for r in 'ab' for n, b, s, r0 in
        (('16vecchia', B0271, '16', 1393), ('22u', B029, '22', 700), ('24u', B029, '24', 700))
    ],
    'F12': [('Ptempi', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, 'STRATA_DECODE_TIMING': '1', 'STRATA_VERIFY_PROFILE': '1'})] + [
        # dall'analisi di Fable: lavoratori CPU col valore normale, e i tre interruttori sm_86 che con due architetture il motore non applica
        (f'M{n}_{r}', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, **e}) for r in 'ab' for n, e in (
            ('rif', {}),
            ('spin', SPIN),
            ('sm86', SM86),
            ('spin86', {**SPIN, **SM86}))
    ],
    'F13': [('Z24tutte_a', B029, '24', DUE, 700, 384, {'_targets': PIENO, **TUTTE})],
    'F6': [(f'f20_{n}', B0271, '20', '0,1,2', 700, 384, freddi(n)) for n in (1000, 2000, 4000)] +
          [('p20_senzaprefisso', B0271, '20', DUE, 700, 384, {'_togli': ['--prompt-cache-file']})],
}


def log(m):
    r = f'{time.strftime("%d/%m %H:%M:%S")} {m}'
    print(r, flush=True)
    with open(QUI / 'coda.log', 'a', encoding='utf-8') as f:
        f.write(r + '\n')


def ambiente():
    q = ("$o=@{}; foreach($n in 'CGControl','JumpConnect','dwm'){$p=Get-Process $n -ErrorAction SilentlyContinue;"
         "$o[$n]=[math]::Round(($p|Measure-Object CPU -Sum).Sum,1)};"
         # Win32_VideoController resta indietro dopo un cambio di risoluzione: si legge il desktop (01/11)
         "Add-Type 'using System;using System.Runtime.InteropServices;public class G{[DllImport(\"user32.dll\")]public static extern IntPtr GetDC(IntPtr h);"
         "[DllImport(\"gdi32.dll\")]public static extern int GetDeviceCaps(IntPtr d,int i);[DllImport(\"user32.dll\")]public static extern bool SetProcessDPIAware();}';"
         "[G]::SetProcessDPIAware()|Out-Null;$d=[G]::GetDC([IntPtr]::Zero);"
         "$o['schermo']=\"$([G]::GetDeviceCaps($d,118))x$([G]::GetDeviceCaps($d,117))\";"
         "$o|ConvertTo-Json -Compress")
    return subprocess.run(['powershell', '-NoProfile', '-Command', q], capture_output=True, text=True).stdout.strip()


def ferma():
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)


def braccio(nome, build, split, schede, r0, r1, env):
    out = QUI / 'corse' / nome
    if (out / 'FATTO').exists():
        log(f'{nome}: gia fatto, salto')
        return
    out.mkdir(parents=True, exist_ok=True)
    c = json.loads(CFG.read_text(encoding='utf-8-sig'))
    a = c['args']
    a[a.index('--layer-split') + 1] = split
    a[a.index('--vram-reserve-mib') + 1] = str(r0)
    a[a.index('--vram-reserve-later-mib') + 1] = str(r1)
    a[a.index('--prompt-cache-file') + 1] = str(out / 'prefix.bin')
    c['exe'] = str(build / 'strata.exe')
    c['vision']['exe'] = str(build / 'strata-vision.exe')
    c['log'] = str(out / 'engine.log')
    c['env'].update({'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'CUDA_VISIBLE_DEVICES': schede, 'STRATA_ROUTE_PRIOR': '0'})
    env = dict(env)
    bersagli = env.pop('_targets', '4096,32768')
    a += env.pop('_args', [])
    for k in env.pop('_togli', []):
        i = a.index(k)
        del a[i:i + 2]
    for k, v in env.items():
        if v is None:
            c['env'].pop(k, None)
        else:
            c['env'][k] = v
    (out / 'config.json').write_text(json.dumps(c, indent=1), encoding='utf-8')
    (out / 'ambiente.txt').write_text(f'inizio {time.strftime("%H:%M")} {ambiente()}\n', encoding='utf-8')
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, b'CODA-NOTTE')
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(2)
    sonda = subprocess.Popen(['nvidia-smi', '--query-gpu=timestamp,index,memory.used,utilization.gpu,power.draw,temperature.gpu',
                              '--format=csv,noheader', '-l', '5', '-f', str(out / 'schede.csv')],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    riser = subprocess.Popen(['nvidia-smi', 'dmon', '-i', '1', '-s', 't', '-d', '2', '-o', 'T', '-f', str(out / 'riser.csv')],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # traffico sul riser della 3060
    slog = open(out / 'server.log', 'w', encoding='utf-8')
    p = subprocess.Popen([str(PY), str(build / 'source/serve/server.py'), '--engine', 'strata', '--config', str(out / 'config.json'),
                          '--host', '127.0.0.1', '--port', '8105'], stdout=slog, stderr=subprocess.STDOUT)
    esito = 'fallito'
    try:
        t0 = time.time()
        while True:
            try:
                urllib.request.urlopen('http://127.0.0.1:8105/v1/models', timeout=5)
                break
            except Exception:
                if p.poll() is not None:
                    raise RuntimeError('server uscito')
                if time.time() - t0 > 900:
                    raise RuntimeError('avvio oltre 15 min')
                time.sleep(5)
        log(f'{nome}: pronto in {time.time() - t0:.0f} s')
        r = subprocess.run([str(PY), str(BENCH), '--root', str(build / 'source'), '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs',
                            '--url', 'http://127.0.0.1:8105', '--out', str(out), '--targets', bersagli],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3000)
        (out / 'banco.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
        esito = f'finito rc={r.returncode}'
    except Exception as e:
        esito = f'fallito: {e}'
    finally:
        with open(out / 'ambiente.txt', 'a', encoding='utf-8') as f:
            f.write(f'fine {time.strftime("%H:%M")} {ambiente()}\n')
        p.terminate()
        time.sleep(5)
        ferma()
        sonda.terminate()
        riser.terminate()
        slog.close()
        LOCK.unlink(missing_ok=True)
        (out / 'prefix.bin').unlink(missing_ok=True)
        time.sleep(10)
    log(f'{nome}: {esito}')
    if esito.startswith('finito'):
        (out / 'FATTO').write_text(esito, encoding='utf-8')


for fase in sys.argv[1:]:
    log(f'--- fase {fase}')
    for b in FASI[fase]:
        braccio(*b)
log('coda finita')
