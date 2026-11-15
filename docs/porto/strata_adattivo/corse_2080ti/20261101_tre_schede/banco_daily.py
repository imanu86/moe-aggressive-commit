"""Banco della comunita' (lettura e scrittura a 4K/32K/128K) su una configurazione del Daily, cosi' com'e', dietro bench.lock.
Stesso benchmark.py e stessi bersagli delle fasi FT3/FT4 di coda_notte.py, cosi' i numeri si confrontano con quelle e con i
risultati pubblicati della comunita'. Porta 8105, log del motore e config nella cartella della corsa, motore spento alla fine.

    python banco_daily.py <nome> <config del Daily> [modi]
modi, separati da virgola, nell'ordine dato (motore caricato una volta sola):
  comunita[:corse]  benchmark.py 4K/32K/128K (default, 3 corse)
  standard          `strata bench run` standard-v1 (docs/BENCHMARK_PROTOCOL.md) con la fase a 4 richieste: va per primo
                    (il protocollo vuole un motore appena caricato)
  rapido            tools/strata_bench.py, la suite rapida dei rapporti della comunita' (chat, 4K, 16K, agente) + --long 32K
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

QUI = Path(__file__).resolve().parent
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
PY = Path(r'D:\ds4_work\strata\Strata\.venv\Scripts\python.exe')
BENCH = Path(r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py')
PIENO = '4096,32768,128000'

nome, cfg_src = sys.argv[1], Path(sys.argv[2])
modi = (sys.argv[3] if len(sys.argv) > 3 else 'comunita:3').split(',')
SRC = Path(r'C:\Users\imanu\source\repos\Strata-wt\tappa4c')   # sorgenti della build del Daily (strata.py, bench/prompts/standard-v1)
out = QUI / 'corse' / nome
out.mkdir(parents=True, exist_ok=True)
c = json.loads(cfg_src.read_text(encoding='utf-8-sig'))
c['log'] = str(out / 'engine.log')
build = Path(c['exe']).parent
SRV = build / 'source' if (build / 'source').exists() else SRC   # pacchetto: source/ accanto all'exe; build di laboratorio: i sorgenti
(out / 'config.json').write_text(json.dumps(c, indent=1), encoding='utf-8')


def log(m):
    print(f'{time.strftime("%H:%M:%S")} {m}', flush=True)


while True:
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f'BANCO-DAILY-{nome}'.encode())
        os.close(fd)
        break
    except FileExistsError:
        time.sleep(2)
sonda = subprocess.Popen(['nvidia-smi', '--query-gpu=timestamp,index,memory.used,utilization.gpu,power.draw,temperature.gpu',
                          '--format=csv,noheader', '-l', '5', '-f', str(out / 'schede.csv')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
slog = open(out / 'server.log', 'w', encoding='utf-8')
env = dict(os.environ, STRATA_PROMPT_ENCODER='1')
p = subprocess.Popen([str(PY), str(SRV / 'serve/server.py'), '--engine', 'strata', '--config', str(out / 'config.json'),
                      '--host', '127.0.0.1', '--port', '8105'], stdout=slog, stderr=subprocess.STDOUT, env=env)
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
    rcs = []
    for modo in modi:
        tipo, _, n = modo.partition(':')
        if tipo == 'comunita':
            cmd, cwd = [str(PY), str(BENCH), '--root', str(SRV), '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs',
                        '--url', 'http://127.0.0.1:8105', '--out', str(out), '--targets', PIENO, '--runs', n or '3'], None
        elif tipo == 'standard':
            cmd, cwd = [str(PY), str(SRC / 'strata.py'), 'bench', 'run', '--url', 'http://127.0.0.1:8105', '--optional-concurrency',
                        '--track', 'custom', '--track-notes', f'OktoCGC Daily {nome}: 0.2.13.1 + pila + tappa 4c (9a610f59), due server di esperti',
                        '--quantization', 'IQ3_XXS (GSQ-RCO)', '--out', str(out / 'standard')], None
        elif tipo == 'rapido':
            cmd, cwd = [str(PY), str(SRC / 'tools' / 'strata_bench.py'), '--url', 'http://127.0.0.1:8105', '--config', str(out / 'config.json'), '--runs', n or '3', '--long',
                        '--out', str(out / 'rapido')], str(SRC)
        elif tipo == 'carico':   # carico:1-3-6 = tools/par_load.py w2 (prompt 1024, 256 scritti) a quelle chat insieme, 2 giri
            cmd, cwd = [str(PY), str(SRC / 'tools' / 'par_load.py'), 'http://127.0.0.1:8105', '--workload', 'w2', '--conc',
                        (n or '1-2-4').replace('-', ','), '--rounds', '2', '--warm-requests', '1', '--label', nome,
                        '--out', str(out / 'carico.json')], str(SRC)
        else:
            raise RuntimeError(f'modo sconosciuto {modo}')
        log(f'{nome}: {tipo} parte')
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5400)
        (out / f'banco_{tipo}.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
        log(f'{nome}: {tipo} rc={r.returncode}')
        rcs.append(f'{tipo}={r.returncode}')
    esito = 'finito ' + ' '.join(rcs)
except Exception as e:
    esito = f'fallito: {e}'
finally:
    p.terminate()
    time.sleep(5)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    sonda.terminate()
    slog.close()
    LOCK.unlink(missing_ok=True)
log(f'{nome}: {esito}')
if esito.startswith('finito'):
    (out / 'FATTO').write_text(esito, encoding='utf-8')
