"""Tempo di un'immagine nel Daily 0.1.45 (visione su CPU, 8 thread, 1024 token d'immagine): config copiata, porta 8104.

1. L'encoder da solo (server.Vision del Daily, stessi parametri della config): tempo per immagini sintetiche diverse (CPU, niente GPU).
2. Il server completo (server.py + motore): richiesta di solo testo e richieste con immagine (non in cache), max_tokens 4,
   temperatura 0: il tempo in piu' di una richiesta con immagine su una di solo testo e' il costo dell'immagine nel percorso reale.
Immagini sintetiche (grafici e testo generati qui, niente schermate dell'utente).  Si lancia dentro bench_lock.py.
"""
import base64, io, json, os, random, subprocess, sys, threading, time, urllib.request
from pathlib import Path

import psutil
from PIL import Image, ImageDraw, ImageFont

H = Path(__file__).resolve().parent
RUNS = Path(r'D:\ds4_work\strata\lab_st0\runs')
D = Path(r'D:\ds4_work\strata\Strata')
SRC = D / 'build-0145-daily' / 'source'
CONFIG = H / 'strata-0145-daily-st0.json'
OUT = RUNS / (sys.argv[1] if len(sys.argv) > 1 else 'DET-ST0-VIS')
PORT = 8104
sys.path[:0] = [str(SRC)]
sys.dont_write_bytecode = True
from serve import server  # noqa: E402


def jump_state():
    import ctypes
    rows = []
    for p in psutil.process_iter(['name', 'pid']):
        if (p.info['name'] or '').lower().startswith('jumpconnect'):
            try:
                ct = p.cpu_times(); sid = ctypes.c_ulong()
                ctypes.windll.kernel32.ProcessIdToSessionId(p.pid, ctypes.byref(sid))
                rows.append(dict(pid=p.pid, session=sid.value, cpu_s=round(ct.user + ct.system, 2)))
            except psutil.Error:
                pass
    return rows


def make_image(seed, w=1600, h=900):
    r = random.Random(seed)
    im = Image.new('RGB', (w, h), (r.randrange(200, 255), r.randrange(200, 255), r.randrange(200, 255)))
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('arial.ttf', 28)
    except OSError:
        f = ImageFont.load_default()
    for i in range(14):
        d.text((40, 30 + i * 52), f'Riga {i} seed {seed}: valore {r.randrange(10**6)} totale {r.random() * 1000:.2f}', fill=(10, 10, 10), font=f)
    for _ in range(40):
        x, y = r.randrange(w - 200), r.randrange(h - 200)
        d.rectangle([x, y, x + r.randrange(20, 200), y + r.randrange(20, 200)], outline=(r.randrange(256),) * 3, width=3)
    buf = io.BytesIO(); im.save(buf, 'PNG')
    return buf.getvalue()


def call(path, body, timeout=900):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    OUT.mkdir(parents=True)
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    res = dict(encoder=[], server=[], jump_start=jump_state())
    # 1. encoder da solo
    vc = dict(cfg['vision'])
    v = server.Vision(vc, log=open(OUT / 'vision_solo.log', 'w'), env=None, lazy=False)
    v.encode(make_image(0))   # riscaldamento (carica l'mmproj)
    for s in (1, 2, 3, 4):
        data = make_image(s)
        t = time.monotonic(); path, ntok = v.encode(data); dt = time.monotonic() - t
        res['encoder'].append(dict(seed=s, s=round(dt, 2), tokens=ntok, png_kb=len(data) // 1024))
        print('encoder', res['encoder'][-1], flush=True)
    v.close()
    # 2. server completo
    env = {k: val for k, val in os.environ.items() if k != 'STRATA_API_KEY'}
    p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(SRC / 'serve' / 'server.py'), '--engine', 'strata', '--config',
                          str(CONFIG), '--host', '127.0.0.1', '--port', str(PORT)], cwd=D, env=env,
                         stdout=open(OUT / 'server.log', 'w', encoding='utf-8'), stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        t0 = time.time()
        while time.time() - t0 < 600:
            assert p.poll() is None, 'server uscito'
            try:
                h = call('/health', None, timeout=3)
                if h.get('loaded'):
                    break
            except Exception:
                pass
            time.sleep(2)
        res['startup_s'] = round(time.time() - t0, 1)
        q = 'Descrivi in italiano cosa mostra questa immagine.'
        txt = 'Descrivi in italiano cosa mostra questa immagine. ' * 1

        def req(content, mt=4):
            t = time.monotonic()
            r = call('/v1/chat/completions', dict(model='x', temperature=0, max_tokens=mt, messages=[dict(role='user', content=content)],
                                                    chat_template_kwargs=dict(enable_thinking=False)))
            return round(time.monotonic() - t, 2), r.get('usage')
        # riscaldamento del percorso (grafi del motore)
        req('Rispondi con una parola: ciao.')
        for k in range(3):
            res['server'].append(dict(kind='testo', **dict(zip(('s', 'usage'), req(f'{txt} Variante {k}.')))))
            print(res['server'][-1], flush=True)
        for s in (11, 12, 13, 14):
            b64 = base64.b64encode(make_image(100 + s)).decode()
            r = dict(kind='immagine', seed=s, **dict(zip(('s', 'usage'), req([dict(type='text', text=q), dict(
                type='image_url', image_url=dict(url=f'data:image/png;base64,{b64}'))]))))
            res['server'].append(r); print(r, flush=True)
    finally:
        kids = []
        try:
            kids = psutil.Process(p.pid).children(recursive=True)
        except Exception:
            pass
        p.terminate()
        try:
            p.wait(timeout=40)
        except Exception:
            p.kill()
        for k in kids:
            try:
                k.kill()
            except Exception:
                pass
        res['jump_end'] = jump_state()
        (OUT / 'res.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
