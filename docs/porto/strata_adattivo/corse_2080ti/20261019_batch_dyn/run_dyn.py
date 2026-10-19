"""Banco di lab/batch-dyn (STRATA_BATCH_DYNAMIC): una corsa per invocazione, sotto bench.lock (O_EXCL, preso e rilasciato qui).

    python run_dyn.py <tag> <config.json> <exe> [--env K=V ...] [--args "--opt v ..."] [--community] [--switch N]

- parte da <config.json> (sola lettura), sostituisce exe/log/prompt-cache-file, applica --args (un'opzione qui SOSTITUISCE quella
  della config) e --env, e avvia serve/server.py della build (porta 8106);
- --community: il benchmark della comunita' (prompt freschi 4K/32K/128K, greedy, 256 token) come community_bench.py;
- --switch N: N cicli del test di passaggio (1 chat, poi 3 chat insieme, attesa oltre STRATA_BATCH_IDLE_S, di nuovo 1 chat);
- campiona la VRAM libera delle due schede ogni secondo (vram.csv) e la CPU di JumpConnect (sessione 1) prima e dopo;
- ferma solo il proprio albero di processi (mai taskkill per nome: il Daily resta in pace).
Esce senza fare nulla se esiste lab_locks\\pause.
"""
import argparse, json, os, shlex, subprocess, sys, threading, time, urllib.request
from pathlib import Path

import psutil

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
S = Path(r'D:\ds4_work\strata\Strata')
H = Path(__file__).resolve().parent
BENCH = Path(r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py')
PORT = 8106

ap = argparse.ArgumentParser()
ap.add_argument('tag')
ap.add_argument('config')
ap.add_argument('exe')
ap.add_argument('--env', action='append', default=[])
ap.add_argument('--args', default='')
ap.add_argument('--community', action='store_true')
ap.add_argument('--switch', type=int, default=0)
ap.add_argument('--idle', type=float, default=30.0, help='STRATA_BATCH_IDLE_S atteso dal test di passaggio')
ap.add_argument('--conc', default='', help='es. 2,3,4: decode aggregato con N conversazioni insieme (prompt corti)')
a = ap.parse_args()

OUT = H / a.tag
OUT.mkdir(parents=True, exist_ok=True)
EXE = Path(a.exe)
BLD = EXE.parent


def split_opts(xs):
    out, i = [], 0
    while i < len(xs):
        if xs[i].startswith('--'):
            j = i + 1
            while j < len(xs) and not xs[j].startswith('--'):
                j += 1
            out.append(xs[i:j])
            i = j
        else:
            out[-1].append(xs[i])
            i += 1
    return out


c = json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
base = split_opts(c['args'])
extra = split_opts(shlex.split(a.args))
drop = {e[0] for e in extra}
c['args'] = [x for o in base if o[0] not in drop for x in o] + [x for o in extra for x in o]
if '--prompt-cache-file' in c['args']:
    c['args'][c['args'].index('--prompt-cache-file') + 1] = str(OUT / 'prefix.bin')
c['exe'], c['log'], c['port'] = str(EXE), str(OUT / 'engine.log'), PORT
if 'vision' in c:
    c['vision']['exe'] = str(BLD / 'strata-vision.exe')
for kv in a.env:
    k, v = kv.split('=', 1)
    c.setdefault('env', {})[k] = v
cfg = OUT / 'config.json'
cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')


def jump_cpu():
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
                        '(Get-Process JumpConnect -ErrorAction SilentlyContinue | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum'],
                       capture_output=True, text=True)
    return r.stdout.strip() or '0'


def http(path, body=None, timeout=30):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat(content, max_tokens=256):
    body = {'model': 'strata', 'messages': [{'role': 'user', 'content': content}], 'temperature': 0,
            'reasoning_effort': 'none', 'max_tokens': max_tokens, 'stream': True, 'stream_options': {'include_usage': True}}
    t0 = time.perf_counter()
    first, n, usage = None, 0, {}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=1800) as r:
        for line in r:
            if not line.startswith(b'data: '):
                continue
            p = line[6:].strip()
            if p == b'[DONE]':
                break
            ch = json.loads(p)
            if ch.get('usage'):
                usage = ch['usage']
            for cc in ch.get('choices', []):
                d = cc.get('delta', {})
                if (d.get('content') or '') + (d.get('reasoning_content') or ''):
                    n += 1
                    if first is None:
                        first = time.perf_counter() - t0
    el = time.perf_counter() - t0
    gen = usage.get('completion_tokens', n)
    return {'ttft_s': first, 'elapsed_s': el, 'gen': gen, 'prompt': usage.get('prompt_tokens'),
            'decode_tok_s': (gen - 1) / (el - first) if first is not None and el > first and gen > 1 else None}


FILLER = [f'def task_{i:05d}(value: int) -> int: return (value * {(i % 97) + 1} + {i}) % 100003' for i in range(12000)]


def fresh(tag, lines=100):
    return (f'Benchmark nonce: switch-{tag}-{time.time_ns()}.\nReview this synthetic Python module:\n' + '\n'.join(FILLER[:lines]) +
            '\n\nWrite a detailed explanation of the code above. Write at least 600 words.')


def switch_test(n):
    rows = []
    for cyc in range(1, n + 1):
        r = chat(fresh(f'c{cyc}-solo-pre')); r.update(phase='solo-prima', cycle=cyc, t=time.time()); rows.append(r)
        print('switch', json.dumps(r), flush=True)
        res = [None] * 3
        def one(i):
            res[i] = chat(fresh(f'c{cyc}-agent{i}'))
        th = [threading.Thread(target=one, args=(i,)) for i in range(3)]
        t0 = time.perf_counter()
        for i, t in enumerate(th):
            t.start(); time.sleep(0.5)
        for t in th:
            t.join()
        wall = time.perf_counter() - t0
        for i, r in enumerate(res):
            r.update(phase='agenti', cycle=cyc, agent=i, wall_s=wall, t=time.time()); rows.append(r)
            print('switch', json.dumps(r), flush=True)
        time.sleep(a.idle + 10)
        r = chat(fresh(f'c{cyc}-solo-post')); r.update(phase='solo-dopo', cycle=cyc, t=time.time()); rows.append(r)
        print('switch', json.dumps(r), flush=True)
        (OUT / 'switch.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    return rows


def conc_test(ns):
    """N conversazioni insieme con prompt corti (~600 token, diversi) e 384 token: l'aggregato in decode = token generati da
    tutte / tempo dal primo token dell'ultima a partire alla fine della prima a finire (finestra in cui decodificano tutte)."""
    rows = []
    for n in ns:
        for rep in (1, 2):
            res = [None] * n
            starts = [None] * n
            def one(i):
                starts[i] = time.perf_counter()
                res[i] = chat(fresh(f'conc{n}-{rep}-{i}', lines=20), max_tokens=384)
                res[i]['t_start'] = starts[i]
                res[i]['t_end'] = time.perf_counter()
            th = [threading.Thread(target=one, args=(i,)) for i in range(n)]
            t0 = time.perf_counter()
            for t in th:
                t.start()
            for t in th:
                t.join()
            wall = time.perf_counter() - t0
            first_all = max(r['t_start'] + r['ttft_s'] for r in res)
            end_first = min(r['t_end'] for r in res)
            gen = sum(r['gen'] for r in res)
            # token generati da tutte nella finestra comune, stimati dal ritmo di ciascuna
            overlap = max(end_first - first_all, 1e-3)
            agg_overlap = sum(r['decode_tok_s'] or 0 for r in res) if end_first > first_all else None
            row = {'n': n, 'rep': rep, 'wall_s': wall, 'gen': gen, 'agg_wall_tok_s': gen / wall,
                   'per_conv_decode_tok_s': [r['decode_tok_s'] for r in res], 'sum_decode_tok_s': agg_overlap,
                   'ttft_s': [r['ttft_s'] for r in res], 'overlap_s': overlap}
            rows.append(row)
            print('conc', json.dumps(row), flush=True)
            (OUT / 'conc.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
            time.sleep(3)
    return rows


sys.path.insert(0, str(H))
import turno_lock  # noqa: E402
if not turno_lock.take(f'BATCHDYN-{a.tag}'):
    sys.exit('pause: niente GPU')
print('lock preso', time.strftime('%H:%M:%S'), flush=True)
amb = OUT / 'ambiente.txt'
amb.write_text(f'inizio {time.strftime("%H:%M:%S")} jump_cpu_s {jump_cpu()}\n', encoding='utf-8')
stop = threading.Event()


def vram_sampler():
    with open(OUT / 'vram.csv', 'w', encoding='utf-8') as f:
        f.write('t,gpu,free_mib,used_mib\n')
        while not stop.wait(1.0):
            r = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.free,memory.used', '--format=csv,noheader,nounits'],
                               capture_output=True, text=True)
            for line in r.stdout.strip().splitlines():
                f.write(f'{time.time():.1f},{line.replace(" ", "")}\n')
            f.flush()


p = None
try:
    log = open(OUT / 'server.log', 'w', encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.Popen([str(S / '.venv/Scripts/python.exe'), '-B', str(BLD / 'source/serve/server.py'), '--engine', 'strata',
                          '--config', str(cfg), '--host', '127.0.0.1', '--port', str(PORT)], cwd=S, env=env, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    threading.Thread(target=vram_sampler, daemon=True).start()
    t0 = time.time()
    while True:
        try:
            http('/v1/models', timeout=5); break
        except Exception:
            if p.poll() is not None:
                raise SystemExit('server uscito')
            if time.time() - t0 > 900:
                raise SystemExit('avvio oltre 15 min')
            time.sleep(3)
    print(f'pronto in {time.time() - t0:.0f} s', flush=True)
    with open(amb, 'a', encoding='utf-8') as f:
        f.write(f'pronto in {time.time() - t0:.0f} s\n')
    if a.community:
        subprocess.run([str(S / '.venv/Scripts/python.exe'), str(BENCH), '--root', str(BLD / 'source'),
                        '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs', '--url', f'http://127.0.0.1:{PORT}',
                        '--out', str(OUT)], check=False)
    if a.conc:
        conc_test([int(x) for x in a.conc.split(',')])
    if a.switch:
        switch_test(a.switch)
finally:
    stop.set()
    with open(amb, 'a', encoding='utf-8') as f:
        f.write(f'fine {time.strftime("%H:%M:%S")} jump_cpu_s {jump_cpu()}\n')
    if p is not None:
        try:
            kids = psutil.Process(p.pid).children(recursive=True)
        except psutil.Error:
            kids = []
        p.terminate()
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
        for k in kids:
            try:
                k.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(kids, timeout=20)
        for k in alive:
            try:
                k.kill()
            except psutil.Error:
                pass
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
    print('motore fermato, lock rilasciato', time.strftime('%H:%M:%S'), flush=True)
