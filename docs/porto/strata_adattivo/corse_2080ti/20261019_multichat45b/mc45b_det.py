"""Banco di parita' e TTFT delle leve di lab/multichat45b (19/10): UN motore, avviato dalla config del Daily (solo lettura:
strata-0143-daily.json) con cache esperti FISSA (--expert-cache 1500, senza --elastic, --adapt-every 0, senza cache di
prompt/conversazione su disco ne' visione), richieste a temperatura 0 attraverso il server HTTP.

  python ..\\20261006_due_schede\\bench_lock.py DET-mc45b-<tag> -- python -u mc45b_det.py --tag T --exe X [--env "K=V ..."]

Richieste (stesso elenco in ogni braccio, testi distinti per non toccare nessuna cache di prefisso):
  w   warm-up (non misurata)
  s0..s2   prompt da ~300 token
  l0..l2   prompt da ~3000 token
Per ognuna: token di prompt, TTFT (invio -> primo chunk di contenuto), 96 token di uscita, sha1 del testo.  L'esito va in
mc45b_<tag>/res.json; il confronto fra bracci lo fa cmp_det.py.
"""
import argparse, hashlib, json, os, shlex, socket, subprocess, sys, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import banco_p0 as P0   # noqa: E402

D = Path(r'D:\ds4_work\strata\Strata')
ap = argparse.ArgumentParser()
ap.add_argument('--exe', required=True)
ap.add_argument('--tag', required=True)
ap.add_argument('--env', default='', help='env del motore, "K=V K2=V2"')
ap.add_argument('--extra', default='', help='opzioni del motore in coda')
ap.add_argument('--maxt', type=int, default=96)
ap.add_argument('--port', type=int, default=8102)
a = ap.parse_args()
SERVE = Path(a.exe).parent / 'source' / 'serve'
OUT = H / f'mc45b_{a.tag}'
OUT.mkdir(exist_ok=True)
_, _, prefissi, _ = P0.carica_fixture()
BASE = prefissi['ctx131k']
INSTR = 'Materiale di riferimento (codice e documenti di un progetto):\n\n'
Q = 'Riassumi in tre frasi il materiale qui sopra.'

# (nome, caratteri, offset): ~4 caratteri per token
REQS = [('w', 14000, 5003)]
REQS += [(f's{k}', 1100, 20011 + 17389 * k) for k in range(3)]
REQS += [(f'l{k}', 11500, 41017 + 23117 * k) for k in range(3)]

DROP = {'--elastic', '--prompt-cache', '--prompt-cache-file', '--conversation-cache-mib', '--conversation-cache-slots',
        '--vision', '--expert-cache'}


def split_opts(toks):
    out, cur = [], None
    for t in toks:
        if t.startswith('--'):
            cur = [t]
            out.append(cur)
        elif cur is not None:
            cur.append(t)
        else:
            raise SystemExit(f'bad arg {t}')
    return out


def http(path, timeout=10):
    with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{a.port}' + path), timeout=timeout) as r:
        return json.load(r)


cfg = json.loads((D / 'strata-0143-daily.json').read_text(encoding='utf-8-sig'))   # sola lettura
base = [o for o in split_opts(cfg['args']) if o[0] not in DROP]
base += [['--expert-cache', '1500'], ['--adapt-every', '0']] + split_opts(shlex.split(a.extra))
cfg['args'] = [x for o in base for x in o]
cfg.pop('vision', None)
cfg['log'], cfg['exe'], cfg['port'] = str(OUT / 'engine.log'), a.exe, a.port
env = cfg.setdefault('env', {})
for k in ('STRATA_PREFIX_DISK_MULTI', 'STRATA_CONV_DISK'):
    env.pop(k, None)
env['STRATA_DUMP_FIRST_LOGITS'] = str(OUT / 'fl')   # logits of each request's first window -> fl.<n> (n = request order)
for kv in shlex.split(a.env):
    k2, v2 = kv.split('=', 1)
    env[k2] = v2
cfg_path = OUT / 'config.json'
cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
model = cfg['model_name']


def ask(name, chars, off):
    body = dict(model=model, temperature=0, max_tokens=a.maxt, stream=True,
                messages=[dict(role='system', content=INSTR + BASE[off: off + chars]), dict(role='user', content=Q)],
                chat_template_kwargs=dict(enable_thinking=False))
    t0 = time.monotonic()
    first, parts, usage = None, [], {}
    req = urllib.request.Request(f'http://127.0.0.1:{a.port}/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            c = json.loads(data)
            if c.get('usage'):
                usage = c['usage']
            if not c.get('choices'):
                continue
            d = c['choices'][0].get('delta') or {}
            if d.get('content'):
                if first is None:
                    first = time.monotonic()
                parts.append(d['content'])
    end = time.monotonic()
    txt = ''.join(parts)
    (OUT / f'{name}.txt').write_text(txt, encoding='utf-8')
    return dict(name=name, prompt=usage.get('prompt_tokens'), out=usage.get('completion_tokens'),
                ttft=round((first or end) - t0, 3), wall=round(end - t0, 2),
                sha1=hashlib.sha1(txt.encode('utf-8')).hexdigest()[:16], head=txt[:70].replace('\n', ' '))


with socket.socket() as s:
    s.bind(('127.0.0.1', a.port))
penv = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(SERVE / 'server.py'), '--engine', 'strata',
                      '--config', str(cfg_path), '--host', '127.0.0.1', '--port', str(a.port)],
                     cwd=D, env=penv, stdout=(OUT / 'server.log').open('w', encoding='utf-8'), stderr=subprocess.STDOUT,
                     creationflags=subprocess.CREATE_NO_WINDOW)
def jump_cpu():
    try:
        import psutil
        return [round(p.cpu_times().user + p.cpu_times().system, 1) for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower().startswith('jumpconnect')]
    except Exception:   # noqa: BLE001
        return None


res = dict(tag=a.tag, exe=a.exe, env=a.env, extra=a.extra, reqs=[], jump_cpu_start=jump_cpu())
try:
    t0 = time.monotonic()
    while time.monotonic() - t0 < 1500:
        assert p.poll() is None, 'server exited'
        try:
            if http('/health').get('status') == 'ok':
                break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    else:
        raise TimeoutError('avvio')
    res['startup_s'] = round(time.monotonic() - t0)
    print(f'motore pronto in {res["startup_s"]} s', flush=True)
    for name, chars, off in REQS:
        r = ask(name, chars, off)
        res['reqs'].append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        (OUT / 'res.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
finally:
    res['jump_cpu_end'] = jump_cpu()
    (OUT / 'res.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    import psutil
    try:
        kids = psutil.Process(p.pid).children(recursive=True)
    except psutil.Error:
        kids = []
    p.terminate()
    try:
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
    for kd in kids:
        try:
            kd.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(kids, timeout=20)
    for kd in alive:
        try:
            kd.kill()
        except psutil.Error:
            pass
print('fine', a.tag, flush=True)
