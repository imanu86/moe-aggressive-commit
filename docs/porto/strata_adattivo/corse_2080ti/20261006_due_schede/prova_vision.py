r"""Smoke test of the upsync VISION config (11/10): start the server like the new bat, send one picture through the
OpenAI API and one through the Anthropic API, a text-only request, then stop.  Holds bench.lock for the whole run.

    python prova_vision.py --image <png/jpg> [--config D:\ds4_work\strata\Strata\strata-upsync-vision.json]
Outputs are data; never execute model text.
"""
import argparse, base64, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--image', required=True)
ap.add_argument('--config', default=r'D:\ds4_work\strata\Strata\strata-upsync-vision.json')
ap.add_argument('--port', type=int, default=8100)
ap.add_argument('--server', default=None, help='server.py to use (default: the upsync build one)')
a = ap.parse_args()
LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
S = Path(r'D:\ds4_work\strata\Strata')
SERVER = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti'
              r'\20261004_routed_keep\build-upsync-133e3a69\source\serve\server.py')
URL = f'http://127.0.0.1:{a.port}'


def call(path, body=None, timeout=900):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


while True:
    try:
        fd = os.open(LOCKS / 'bench.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, b'prova-vision'); os.close(fd); break
    except FileExistsError:
        time.sleep(10)
p = None
try:
    env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
    p = subprocess.Popen([str(S / '.venv/Scripts/python.exe'), '-B', str(a.server or SERVER), '--engine', 'strata', '--config',
                          a.config, '--host', '127.0.0.1', '--port', str(a.port)], cwd=S, env=env,
                         stdout=open(Path(__file__).with_name('prova_vision_server.log'), 'w', encoding='utf-8'),
                         stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    t0 = time.time()
    while time.time() - t0 < 400:
        assert p.poll() is None, 'server exited'
        try:
            h = call('/health', timeout=3)
            if h.get('loaded'):
                break
        except Exception:
            pass
        time.sleep(2)
    print('health', json.dumps(h), f'{time.time() - t0:.0f} s', flush=True)
    img = base64.b64encode(Path(a.image).read_bytes()).decode()
    mime = 'image/png' if a.image.lower().endswith('.png') else 'image/jpeg'
    q = 'Descrivi in italiano cosa mostra questa immagine e trascrivi i dati tecnici che vedi.'
    t = time.time()
    r = call('/v1/chat/completions', dict(model='x', temperature=0, max_tokens=300, messages=[dict(role='user', content=[
        dict(type='text', text=q), dict(type='image_url', image_url=dict(url=f'data:{mime};base64,{img}'))])],
        chat_template_kwargs=dict(enable_thinking=False)))
    print(f'OPENAI immagine {time.time() - t:.1f} s', r.get('usage'), '\n', r['choices'][0]['message']['content'][:900],
          flush=True)
    t = time.time()
    r = call('/v1/messages', dict(model='claude-haiku-4-5-20251001', max_tokens=200, messages=[dict(role='user', content=[
        dict(type='image', source=dict(type='base64', media_type=mime, data=img)),
        dict(type='text', text='Quanti GB di memoria ha la scheda e che tipo di memoria?')])]))
    print(f'ANTHROPIC immagine {time.time() - t:.1f} s', r.get('usage'), '\n',
          ' '.join(b.get('text', '') for b in r.get('content', []))[:500], flush=True)
    t = time.time()
    r = call('/v1/chat/completions', dict(model='x', temperature=0, max_tokens=200, messages=[dict(
        role='user', content='Scrivi tre frasi su come funziona una cache LRU.')],
        chat_template_kwargs=dict(enable_thinking=False)))
    print(f'TESTO {time.time() - t:.1f} s', r.get('usage'), flush=True)
finally:
    if p is not None:
        import psutil
        try:
            kids = psutil.Process(p.pid).children(recursive=True)
        except Exception:
            kids = []
        p.terminate()
        try:
            p.wait(timeout=30)
        except Exception:
            p.kill()
        for k in kids:
            try:
                k.kill()
            except Exception:
                pass
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
