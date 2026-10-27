"""Controllo della RAM nel tempo del passaggio a caldo (perdita di ~10 GiB a ciclo corretta in c4af6851, mai rimisurata).

    python run_ram.py <tag> <config.json> [--cicli 8] [--agenti 4] [--idle 10] [--out cartella]

Avvia il server della build indicata nella config (porta 8106, come run_dyn.py), campiona ogni 2 s la memoria privata e il working set
di strata.exe e la RAM disponibile del sistema (ram.csv), poi ripete N cicli: 1 chat da sola, <agenti> chat insieme (entrata nel
modo agenti), attesa oltre STRATA_BATCH_IDLE_S (uscita), 1 chat da sola.  Alla fine scrive ram_cicli.json e stampa, per ogni ciclo,
la memoria privata di strata.exe dopo l'uscita e la RAM disponibile; verdetto: la privata dopo l'ultimo ciclo non deve superare
quella dopo il primo di piu' di 1 GiB (la perdita vecchia era 10-15 GiB per ciclo).  STRATA_BATCH_IDLE_S = --idle (default 10 s,
per ciclare piu' in fretta: il passaggio e' lo stesso).  Prende il turno (bench.lock, O_EXCL) come run_dyn.py; esce se esiste
lab_locks\\pause.  Ferma solo il proprio albero di processi.
"""
import argparse, json, os, subprocess, sys, threading, time, urllib.request
from pathlib import Path

import psutil

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
S = Path(r'D:\ds4_work\strata\Strata')
H = Path(__file__).resolve().parent
PORT = 8106
ap = argparse.ArgumentParser()
ap.add_argument('tag')
ap.add_argument('config')
ap.add_argument('--cicli', type=int, default=8)
ap.add_argument('--agenti', type=int, default=4)
ap.add_argument('--idle', type=float, default=10.0)
ap.add_argument('--out', default=str(H / 'corse'))
a = ap.parse_args()
OUT = Path(a.out) / a.tag
OUT.mkdir(parents=True, exist_ok=True)

c = json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
EXE = Path(c['exe'])
BLD = EXE.parent
if '--prompt-cache-file' in c['args']:
    c['args'][c['args'].index('--prompt-cache-file') + 1] = str(OUT / 'prefix.bin')
c['log'], c['port'] = str(OUT / 'engine.log'), PORT
c.setdefault('env', {})['STRATA_BATCH_IDLE_S'] = str(int(a.idle))
cfg = OUT / 'config.json'
cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')


def http(path, timeout=30):
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}{path}', timeout=timeout) as r:
        return json.load(r)


def chat(content, max_tokens=256):
    body = {'model': 'strata', 'messages': [{'role': 'user', 'content': content}], 'temperature': 0,
            'reasoning_effort': 'none', 'max_tokens': max_tokens, 'stream': True, 'stream_options': {'include_usage': True}}
    t0 = time.perf_counter()
    first, usage = None, {}
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
                if first is None and (d.get('content') or '') + (d.get('reasoning_content') or ''):
                    first = time.perf_counter() - t0
    el = time.perf_counter() - t0
    gen = usage.get('completion_tokens', 0)
    return {'ttft_s': first, 'elapsed_s': el, 'gen': gen,
            'decode_tok_s': (gen - 1) / (el - first) if first is not None and el > first and gen > 1 else None}


FILLER = [f'def task_{i:05d}(value: int) -> int: return (value * {(i % 97) + 1} + {i}) % 100003' for i in range(12000)]


def fresh(tag, lines=100):
    return (f'Benchmark nonce: ram-{tag}-{time.time_ns()}.\nReview this synthetic Python module:\n' + '\n'.join(FILLER[:lines]) +
            '\n\nWrite a detailed explanation of the code above. Write at least 600 words.')


def strata_mem():
    priv = wset = 0
    for q in psutil.process_iter(['name']):
        if (q.info['name'] or '').lower() == 'strata.exe':
            try:
                m = q.memory_info()
                priv += getattr(m, 'private', m.rss)
                wset += m.rss
            except psutil.Error:
                pass
    return priv / 2**30, wset / 2**30


stop = threading.Event()
rows = []


def ram_sampler():
    with open(OUT / 'ram.csv', 'w', encoding='utf-8') as f:
        f.write('t,strata_private_gib,strata_wset_gib,ram_avail_gib,swap_used_gib\n')
        while not stop.wait(2.0):
            pv, ws = strata_mem()
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            row = (time.time(), pv, ws, vm.available / 2**30, sw.used / 2**30)
            rows.append(row)
            f.write(','.join(f'{x:.2f}' for x in row) + '\n')
            f.flush()


sys.path.insert(0, str(H.parent / '20261019_batch_dyn'))
import turno_lock  # noqa: E402
if not turno_lock.take(f'AUTO-RAM-{a.tag}'):
    sys.exit('pause: niente GPU')
print('lock preso', time.strftime('%H:%M:%S'), flush=True)
p = None
cicli = []
try:
    log = open(OUT / 'server.log', 'w', encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.Popen([str(S / '.venv/Scripts/python.exe'), '-B', str(BLD / 'source/serve/server.py'), '--engine', 'strata',
                          '--config', str(cfg), '--host', '127.0.0.1', '--port', str(PORT)], cwd=S, env=env, stdout=log,
                         stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    threading.Thread(target=ram_sampler, daemon=True).start()
    t0 = time.time()
    while True:
        try:
            http('/v1/models', timeout=5)
            break
        except Exception:
            if p.poll() is not None:
                raise SystemExit('server uscito')
            if time.time() - t0 > 900:
                raise SystemExit('avvio oltre 15 min')
            time.sleep(3)
    print(f'pronto in {time.time() - t0:.0f} s', flush=True)
    chat(fresh('warmup', 10), 16)          # la prima richiesta dell'avvio e' scartata
    time.sleep(a.idle + 8)
    for cyc in range(1, a.cicli + 1):
        r_pre = chat(fresh(f'c{cyc}-pre'))
        res = [None] * a.agenti
        def one(i):
            res[i] = chat(fresh(f'c{cyc}-ag{i}'))
        th = [threading.Thread(target=one, args=(i,)) for i in range(a.agenti)]
        tw = time.perf_counter()
        for i, t in enumerate(th):
            t.start()
            time.sleep(0.5)
        for t in th:
            t.join()
        wall = time.perf_counter() - tw
        pv_agenti, _ = strata_mem()
        time.sleep(a.idle + 10)            # oltre l'attesa: uscita dal modo agenti
        r_post = chat(fresh(f'c{cyc}-post'))
        time.sleep(3)
        pv, ws = strata_mem()
        vm = psutil.virtual_memory()
        row = {'ciclo': cyc, 'privata_agenti_gib': round(pv_agenti, 2), 'privata_dopo_gib': round(pv, 2), 'wset_dopo_gib': round(ws, 2),
               'ram_disponibile_gib': round(vm.available / 2**30, 2), 'wall_agenti_s': round(wall, 1),
               'decode_pre': r_pre['decode_tok_s'], 'decode_post': r_post['decode_tok_s'],
               'decode_agenti': [x['decode_tok_s'] for x in res], 'ttft_agenti': [x['ttft_s'] for x in res]}
        cicli.append(row)
        print('ciclo', json.dumps(row), flush=True)
        (OUT / 'ram_cicli.json').write_text(json.dumps(cicli, indent=1), encoding='utf-8')
finally:
    stop.set()
    if cicli:
        d = cicli[-1]['privata_dopo_gib'] - cicli[0]['privata_dopo_gib']
        print(f'privata dopo l\'uscita: ciclo 1 {cicli[0]["privata_dopo_gib"]} GiB, ciclo {len(cicli)} {cicli[-1]["privata_dopo_gib"]} GiB, '
              f'differenza {d:+.2f} GiB: {"OK (nessuna perdita)" if d <= 1.0 else "PERDITA"}', flush=True)
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
