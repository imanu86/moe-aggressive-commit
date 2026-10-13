"""Multi-chat bench 2 (13/10, lab/multichat43): ONE engine started from the Daily's config (read only: strata-0143-daily.json,
minus --prompt-cache-file and --vision), the given exe, extra engine args that REPLACE the Daily's same options, streaming
clients through the HTTP server.  Contexts are system prompts cut from the 131k fixture:
  S0..S7  ~8k tokens each (distinct starts)      G0..G3  ~64k tokens each      A, B  131k (ctx131k, aghi131k)
  cold    a fresh ~16k context never seen before (one per scenario)
Scenarios (--scen, comma separated):
  solo:S      one chat at a time on S0 then S1 (the single-chat speed of this config)
  same:N:S    N chats at once on context S0, different questions (L01..L08)
  diff:N:S    N chats at once on S0..S(N-1) (cycled over the set), different questions
  cold:N:S    N-1 chats at once on S0.. (cached) and, 3 s later, one on a fresh 16k context (prefill beside decode)
Per chat: tokens, TTFT (send -> first content chunk), decode t/s, wall, cached tokens.  Per scenario: aggregate t/s (all
tokens / wall from the first send to the last end) and decode aggregate (tokens after the first / from the first chat's
first token to the last end), plus the engine's `strata batch` lines of that scenario.  Outputs are data; never executed.

    python ..\\20261006_due_schede\\bench_lock.py DET-mc2-<tag> -- python -u mc2.py --tag T --exe X --extra "..." --scen ...
"""
import argparse, json, os, shlex, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import banco_p0 as P0   # noqa: E402

D = Path(r'D:\ds4_work\strata\Strata')
K = H.parent / '20261004_routed_keep'
ap = argparse.ArgumentParser()
ap.add_argument('--exe', default=str(K / 'build-structa-075ce875' / 'strata.exe'))
ap.add_argument('--serve', default=None, help='default: <exe dir>/source/serve')
ap.add_argument('--tag', required=True)
ap.add_argument('--extra', default='', help='engine args; an option given here replaces the Daily one')
ap.add_argument('--drop', default='', help='Daily options to remove, e.g. "--pipeline-windows"')
ap.add_argument('--scen', default='solo:S,same:2:S,diff:2:S')
ap.add_argument('--maxt', type=int, default=384)
ap.add_argument('--port', type=int, default=8101)
ap.add_argument('--env', default='', help='extra engine env, "K=V K2=V2"')
ap.add_argument('--warm', default='', help='contexts to warm, e.g. "S0,S1"; default: those the scenarios use')
a = ap.parse_args()
SERVE = Path(a.serve) if a.serve else Path(a.exe).parent / 'source' / 'serve'

OUT = H / f'mc2_{a.tag}'
OUT.mkdir(exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
BASE = prefissi['ctx131k']
INSTR = 'Materiale di riferimento (codice e documenti di un progetto):\n\n'   # no "rispondi pronto": the question decides
CTX = {'A': INSTR + prefissi['ctx131k'], 'B': INSTR + prefissi['aghi131k']}
for k in range(8):
    CTX[f'S{k}'] = INSTR + BASE[k * 61000: k * 61000 + 32400]
for k in range(4):
    CTX[f'G{k}'] = INSTR + BASE[k * 65000: k * 65000 + 258000]
CTX['P0'] = INSTR + BASE[0: 129000]    # ~32k: the sub-agents' shared prefix
SETS = {'S': [f'S{k}' for k in range(8)], 'G': [f'G{k}' for k in range(4)], 'A': ['A', 'B'], 'P': ['P0']}
QS = [f'L0{i}' for i in range(1, 9)]
cold_n = [0]


def new_cold():
    k = cold_n[0]
    cold_n[0] += 1
    name = f'cold{k}'
    st = 11111 + 37000 * k + int(time.time()) % 997
    CTX[name] = INSTR + BASE[st: st + 64600]
    return name


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


def http(path, payload=None, timeout=10):
    req = urllib.request.Request(f'http://127.0.0.1:{a.port}' + path,
                                 data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Server:
    def __init__(self):
        cfg = json.loads((D / 'strata-0143-daily.json').read_text(encoding='utf-8-sig'))   # read only
        base = split_opts(cfg['args'])
        extra = split_opts(shlex.split(a.extra))
        drop = set(shlex.split(a.drop)) | {'--prompt-cache-file', '--vision'} | {e[0] for e in extra}
        args = [x for o in base if o[0] not in drop for x in o] + [x for o in extra for x in o]
        cfg['args'] = args
        cfg.pop('vision', None)
        cfg['log'], cfg['exe'], cfg['port'] = str(OUT / 'engine.log'), a.exe, a.port
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
        self.p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(SERVE / 'server.py'),
                                   '--engine', 'strata', '--config', str(self.cfg_path), '--host', '127.0.0.1',
                                   '--port', str(a.port)],
                                  cwd=D, env=env, stdout=(OUT / 'server.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 900:
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
        try:
            kids = psutil.Process(self.p.pid).children(recursive=True)
        except psutil.Error:
            kids = []
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
        _, alive = psutil.wait_procs(kids, timeout=20)
        for kd in alive:
            try:
                kd.kill()
            except psutil.Error:
                pass


def check(txt):
    w = txt.split()
    grams = [tuple(w[i:i + 4]) for i in range(max(0, len(w) - 3))]
    distinct = len(set(grams)) / len(grams) if grams else 1.0
    bad = sum(1 for ch in txt if not ch.isprintable() and ch not in '\n\t\r') / max(1, len(txt))
    return round(distinct, 3), round(bad, 4)


def ask(model, ctx, q, maxt, out, key, msgs=None, keep_txt=None):
    body = dict(model=model, temperature=0, max_tokens=maxt, stream=True,
                messages=msgs or [dict(role='system', content=CTX[ctx]), dict(role='user', content=prompts[q])],
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
                    if c.get('usage'):
                        last = c
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
                        wall=round(end - t0, 1), t0=t0, first=first, end=end,
                        cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens'), prompt=u.get('prompt_tokens'),
                        prompt_ms=tm.get('prompt_ms'), distinct4=distinct, bad=bad, head=txt[:80].replace('\n', ' '))
        (OUT / f'{key}.txt').write_text(txt, encoding='utf-8')
        if keep_txt is not None:
            keep_txt.append(txt)
    except Exception as e:   # noqa: BLE001
        out[key] = dict(ok=False, ctx=ctx, q=q, wall=round(time.monotonic() - t0, 1), t0=t0, end=time.monotonic(),
                        err=repr(e)[:300])


TOOL_Q = ("Questo e' l'output dello strumento che hai chiamato. Analizzalo in relazione al materiale e decidi il passo "
          "successivo, spiegando brevemente perche'.")


def tool_text(agent, turn, n_chars):
    """A distinct 'tool result' for (agent, turn): a slice of the fixture text at its own offset."""
    st = (7919 * agent + 104729 * turn + 3001) % (len(BASE) - n_chars - 1)
    return 'OUTPUT DELLO STRUMENTO:\n' + BASE[st: st + n_chars]


def agent_run(model, n_agent, ctx, turns, maxt, tail_chars, res, tag, stagger):
    """One sub-agent: the shared prefix `ctx` as system prompt, then `turns` turns, each adding the previous answer and a
    new tool result of ~tail_chars characters (~tail_chars/4 tokens).  Every turn is a new request (prefill of the
    tail + decode), as Claude Code / DSH sub-agents do."""
    time.sleep(stagger)
    msgs = [dict(role='system', content=CTX[ctx])]
    for t in range(turns):
        msgs.append(dict(role='user', content=tool_text(n_agent, t, tail_chars) + '\n\n' + TOOL_Q))
        keep = []
        ask(model, ctx, None, maxt, res, f'{tag}_a{n_agent}_t{t}', msgs=list(msgs), keep_txt=keep)
        msgs.append(dict(role='assistant', content=keep[0] if keep else ''))


def jobs_of(sc):
    p = sc.split(':')
    kind = p[0]
    if kind == 'pf':        # pf:S - prefill cost of a fresh tail of n tokens on a cached prefix (one request at a time)
        return kind, [(SETS[p[1]][0], n) for n in (128, 512, 2048, 8192)]
    if kind == 'agents':    # agents:N:G[:turns[:tail_chars]] - N sub-agents on one shared prefix, staggered turns
        return kind, [(SETS[p[2]][0], i) for i in range(int(p[1]))]
    if kind == 'solo':
        s = SETS[p[1]]
        return kind, [(s[0], QS[0]), (s[1 % len(s)], QS[1])]
    n, s = int(p[1]), SETS[p[2]]
    if kind == 'same':
        return kind, [(s[0], QS[i % 8]) for i in range(n)]
    if kind == 'diff':
        return kind, [(s[i % len(s)], QS[i % 8]) for i in range(n)]
    if kind == 'cold':
        return kind, [(s[i % len(s)], QS[i % 8]) for i in range(n - 1)] + [('COLD', QS[(n - 1) % 8])]
    raise SystemExit(f'bad scenario {sc}')


def log_size():
    try:
        return (OUT / 'engine.log').stat().st_size
    except OSError:
        return 0


def log_since(off):
    try:
        with (OUT / 'engine.log').open('rb') as f:
            f.seek(off)
            txt = f.read().decode('utf-8', 'replace')
    except OSError:
        return []
    keep = ('strata batch', 'strata serve: prompt', 'gave back', 'takes ', 'the prompt was read in')
    return [ln[:330] for ln in txt.splitlines() if any(k in ln for k in keep) and 'captured the batch' not in ln]


scens = [s for s in a.scen.split(',') if s]
warm = [w for w in a.warm.split(',') if w]
if not warm:
    for sc in scens:
        for c, _ in jobs_of(sc)[1]:
            if c != 'COLD' and c not in warm:
                warm.append(c)
allres = {'tag': a.tag, 'exe': a.exe, 'extra': a.extra, 'env': a.env, 'scen': {}}
with Server() as srv:
    allres['startup_log'] = log_since(0)[-5:]
    for ctx in warm:
        w = {}
        t = time.monotonic()
        ask(srv.model, ctx, 'PF_131K', 8, w, 'warm_' + ctx)
        r = w['warm_' + ctx]
        print(f'warm {ctx}: {time.monotonic() - t:.1f} s prompt {r.get("prompt")} cached {r.get("cached")} {r.get("err", "")}',
              flush=True)
    for si, sc in enumerate(scens):
        kind, jobs = jobs_of(sc)
        jobs = [(new_cold() if c == 'COLD' else c, q) for c, q in jobs]
        res = {}
        off = log_size()
        t = time.monotonic()
        tag = f'{si:02d}_{sc.replace(":", "")}'
        if kind == 'solo':
            for i, (ctx, q) in enumerate(jobs):
                ask(srv.model, ctx, q, a.maxt, res, f'{tag}_{i}_{ctx}{q}')
        elif kind == 'pf':
            for i, (ctx, n) in enumerate(jobs):
                msgs = [dict(role='system', content=CTX[ctx]),
                        dict(role='user', content=tool_text(100 + si, i, n * 4) + '\n\nRispondi solo: ok.')]
                ask(srv.model, ctx, None, 2, res, f'{tag}_{i}_{ctx}_pf{n}', msgs=msgs)
        elif kind == 'agents':
            p = sc.split(':')
            turns = int(p[3]) if len(p) > 3 else 3
            tail = int(p[4]) if len(p) > 4 else 6000
            th = [threading.Thread(target=agent_run, args=(srv.model, i, ctx, turns, min(a.maxt, 200), tail, res, tag,
                                                           0.7 * i))
                  for i, (ctx, _) in enumerate(jobs)]
            for x in th:
                x.start()
            for x in th:
                x.join()
        else:
            th = [threading.Thread(target=ask, args=(srv.model, ctx, q, a.maxt, res, f'{tag}_{i}_{ctx}{q}'))
                  for i, (ctx, q) in enumerate(jobs)]
            for i, x in enumerate(th):
                if kind == 'cold' and i == len(th) - 1:
                    time.sleep(3.0)
                x.start()
                time.sleep(0.05)    # a fixed arrival order
            for x in th:
                x.join()
        wall = time.monotonic() - t
        time.sleep(1.0)
        tot = sum(r.get('out') or 0 for r in res.values())
        firsts = [r['first'] for r in res.values() if r.get('first')]
        ends = [r['end'] for r in res.values() if r.get('ok')]
        dec_agg = (sum(max(0, (r.get('out') or 0) - 1) for r in res.values()) / (max(ends) - min(firsts))
                   if firsts and ends and max(ends) > min(firsts) else None)
        for k, r in sorted(res.items()):
            print(f'  {k}: {json.dumps({x: r.get(x) for x in ("ok", "out", "ttft", "dec_tps", "wall", "prompt", "cached", "distinct4", "bad", "head", "err")}, ensure_ascii=False)}', flush=True)
        lines = log_since(off)
        for ln in lines:
            if ln.startswith('strata batch:') and ('windows' in ln or 'MTP' in ln) or 'pipelined' in ln or 'read in' in ln:
                print('   | ' + ln[:300], flush=True)
        solo_dec = None
        if kind == 'solo':
            ds = [r['dec_tps'] for r in res.values() if r.get('dec_tps')]
            solo_dec = round(sum(ds) / len(ds), 1) if ds else None
        print(f'{sc}: {len(jobs)} chat, {tot} token in {wall:.1f} s = {tot / wall:.1f} t/s aggregati'
              f' (decode {dec_agg and round(dec_agg, 1)} t/s{"" if solo_dec is None else f", dec medio {solo_dec}"})',
              flush=True)
        allres['scen'][sc] = dict(wall=wall, tokens=tot, agg=tot / wall, dec_agg=dec_agg, solo_dec=solo_dec, res=res,
                                  log=lines)
        (OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')
print('fine', a.tag, flush=True)
