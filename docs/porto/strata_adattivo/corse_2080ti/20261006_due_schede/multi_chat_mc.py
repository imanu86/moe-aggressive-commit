"""Multi-chat bench (lab/multichat): ONE engine on the two-card split (as multi_chat.py: RTX 3060 stage 0, 2080 Ti
stage 1, --layer-split 16 --trim-stage-weights), streaming clients, 131k contexts as system prompts.

Scenarios (in this order, after warming context A and then B):
  serial : A-L01, A-L02, A-L03, B-L02, B-L03 one at a time       (the one-at-a-time reference)
  same2  : A-L01 + A-L02 at once                          same3 : A-L01 + A-L02 + A-L03 at once
  diff2  : A-L01 + B-L02 at once                          diff3 : A-L01 + A-L02 + B-L03 at once
Per chat: tokens, TTFT (send -> first content chunk, queue included), decode t/s after the first token, wall, the
engine's reused/read tokens.  Per scenario: aggregate t/s (all tokens / wall from the first send to the last end).
Text check per reply: distinct word 4-grams ratio (loops), non-printable share (garbage), equal to the serial reply.
Outputs are data; never execute model text.

    python bench_lock.py DET-mc-<name> -- python multi_chat_mc.py --tag T --exe X [--extra "..."] [--scen serial,same2]
"""
import argparse, json, os, shlex, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import banco_p0 as P0   # noqa: E402

D = Path(r'D:\ds4_work\strata\Strata')
ap = argparse.ArgumentParser()
ap.add_argument('--exe', default=str(H.parent / '20261004_routed_keep' / 'build-main-be4cf1c' / 'strata.exe'))
ap.add_argument('--serve', default=r'C:\Users\imanu\source\repos\Strata-2080Ti-core\serve')
ap.add_argument('--tag', required=True)
ap.add_argument('--extra', default='--batch 3 --batch-mtp', help='engine args after the split ones')
ap.add_argument('--base', default='--layer-split 16 --trim-stage-weights --pipeline-windows 2')
ap.add_argument('--scen', default='serial,same2,same3,diff2,diff3')
ap.add_argument('--maxt', type=int, default=384)
ap.add_argument('--port', type=int, default=8101)
ap.add_argument('--env', default='', help='extra engine env, "K=V K2=V2"')
a = ap.parse_args()

os.environ['CUDA_VISIBLE_DEVICES'] = '1,0'
os.environ['STRATA_POOL_SPIN_US'] = '100'
OUT = H / f'mc_{a.tag}'
OUT.mkdir(exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
CTX = {'A': man['istruzione_contesto'] + prefissi['ctx131k'], 'B': man['istruzione_contesto'] + prefissi['aghi131k']}


def http(path, payload=None, timeout=10):
    req = urllib.request.Request(f'http://127.0.0.1:{a.port}' + path,
                                 data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Server:
    def __init__(self):
        cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))   # read only
        args = list(cfg['args'])
        k = args.index('--prompt-cache-file')
        del args[k:k + 2]
        cfg['args'] = args + shlex.split(a.base) + shlex.split(a.extra)
        cfg['log'], cfg['exe'] = str(OUT / 'engine.log'), a.exe
        for kv in shlex.split(a.env):
            k2, v2 = kv.split('=', 1)
            cfg.setdefault('env', {})[k2] = v2
        self.cfg_path = OUT / 'config.json'
        self.cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        self.model, self.p = cfg['model_name'], None

    def __enter__(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', a.port))
        env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
        self.p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(Path(a.serve) / 'server.py'),
                                   '--engine', 'strata', '--config', str(self.cfg_path), '--host', '127.0.0.1',
                                   '--port', str(a.port)],
                                  cwd=D, env=env, stdout=(OUT / 'server.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 600:
            assert self.p.poll() is None, 'server exited'
            try:
                if http('/health').get('status') == 'ok':
                    print(f'engine up in {time.monotonic() - t0:.0f} s', flush=True)
                    return self
            except (OSError, ValueError):
                pass
            time.sleep(1)
        raise TimeoutError('server startup')

    def __exit__(self, *exc):
        import psutil
        kids = psutil.Process(self.p.pid).children(recursive=True)
        self.p.terminate()
        try:
            self.p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.p.kill()
        for kd in kids:
            try:
                kd.terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(kids, timeout=20)


def check(txt):
    w = txt.split()
    grams = [tuple(w[i:i + 4]) for i in range(max(0, len(w) - 3))]
    distinct = len(set(grams)) / len(grams) if grams else 1.0
    bad = sum(1 for ch in txt if not ch.isprintable() and ch not in '\n\t\r') / max(1, len(txt))
    return round(distinct, 3), round(bad, 4)


def ask(model, ctx, q, maxt, out, key):
    body = dict(model=model, temperature=0, max_tokens=maxt, stream=True,
                messages=[dict(role='system', content=CTX[ctx]), dict(role='user', content=prompts[q])],
                chat_template_kwargs=dict(enable_thinking=False))
    t0 = time.monotonic()
    first, parts, last = None, [], None
    try:
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
                if not c.get('choices'):
                    continue
                d = c['choices'][0].get('delta') or {}
                if d.get('content'):
                    if first is None:
                        first = time.monotonic()
                    parts.append(d['content'])
                if c.get('usage'):
                    last = c
        end = time.monotonic()
        txt = ''.join(parts)
        u, tm = (last or {}).get('usage') or {}, (last or {}).get('timings') or {}
        n = u.get('completion_tokens') or 0
        ttft = (first or end) - t0
        dec = (n - 1) / (end - first) if first and n > 1 and end > first else None
        distinct, bad = check(txt)
        out[key] = dict(ok=True, ctx=ctx, q=q, out=n, ttft=round(ttft, 2), dec_tps=dec and round(dec, 1),
                        wall=round(end - t0, 1), t0=t0, end=end, cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens'),
                        prompt_ms=tm.get('prompt_ms'), distinct4=distinct, bad=bad, head=txt[:90].replace('\n', ' '))
        (OUT / f'{key}.txt').write_text(txt, encoding='utf-8')
    except Exception as e:   # noqa: BLE001
        out[key] = dict(ok=False, ctx=ctx, q=q, wall=round(time.monotonic() - t0, 1), t0=t0, end=time.monotonic(),
                        err=repr(e)[:300])


SCEN = {
    'serial': [('A', 'L01'), ('A', 'L02'), ('A', 'L03'), ('B', 'L02'), ('B', 'L03')],
    'same2': [('A', 'L01'), ('A', 'L02')],
    'same3': [('A', 'L01'), ('A', 'L02'), ('A', 'L03')],
    'diff2': [('A', 'L01'), ('B', 'L02')],
    'diff3': [('A', 'L01'), ('A', 'L02'), ('B', 'L03')],
}
allres = {}
SER = [c + q for c, q in SCEN['serial']]
with Server() as srv:
    for ctx in ('A', 'B'):
        w = {}
        t = time.monotonic()
        body_q = 'PF_131K'
        ask(srv.model, ctx, body_q, 8, w, 'warm' + ctx)
        print(f'warm {ctx}: {time.monotonic() - t:.1f} s {json.dumps({k: (v.get("out"), v.get("cached"), v.get("head")) for k, v in w.items()}, ensure_ascii=False)}', flush=True)
    for sc in a.scen.split(','):
        res = {}
        jobs = SCEN[sc]
        t = time.monotonic()
        if sc == 'serial':
            for i, (ctx, q) in enumerate(jobs):
                ask(srv.model, ctx, q, a.maxt, res, f'{sc}_{i}_{ctx}{q}')
        else:
            th = [threading.Thread(target=ask, args=(srv.model, ctx, q, a.maxt, res, f'{sc}_{i}_{ctx}{q}'))
                  for i, (ctx, q) in enumerate(jobs)]
            for x in th:
                x.start()
                time.sleep(0.05)    # a fixed arrival order
            for x in th:
                x.join()
        wall = time.monotonic() - t
        tot = sum(r.get('out') or 0 for r in res.values())
        for k, r in sorted(res.items()):
            same = None
            if sc != 'serial' and r.get('ok'):
                ref = OUT / f'serial_{SER.index(r["ctx"] + r["q"])}_{r["ctx"]}{r["q"]}.txt' \
                    if (r['ctx'] + r['q']) in SER else None
                if ref is not None and ref.exists():
                    a_txt, b_txt = ref.read_text(encoding='utf-8'), (OUT / f'{k}.txt').read_text(encoding='utf-8')
                    same = a_txt == b_txt or next((i for i, (x, y) in enumerate(zip(a_txt, b_txt)) if x != y), min(len(a_txt), len(b_txt)))
            r['same_as_serial'] = same
            print(f'  {k}: {json.dumps({x: r.get(x) for x in ("ok", "out", "ttft", "dec_tps", "wall", "cached", "distinct4", "bad", "same_as_serial", "head", "err")}, ensure_ascii=False)}', flush=True)
        print(f'{sc}: {len(jobs)} chat, {tot} token in {wall:.1f} s = {tot / wall:.1f} t/s aggregati', flush=True)
        allres[sc] = dict(wall=wall, tokens=tot, res=res)
        (OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')
