"""Banco «letture corte concorrenti + scrittori» (passata unica, 19/10): il caso tipico dell'owner.

UN motore avviato dalla config del Daily (sola lettura: strata-0143-daily.json, senza --prompt-cache-file e --vision), exe e
argomenti/env dati, client in streaming via server HTTP.  Contesti R0..R7 come in mc2.py (prefisso comune ~32k + storia
privata 0-70k token a seme fisso), tutti scaldati prima del cronometro.

Scenario, per ogni giro (--rounds, default 2):
  - W scrittori (R4..) mandano un turno corto (~500 caratteri) con max_tokens --wmaxt (600) e decodificano;
  - dopo --lead s (4) N lettori (R0..R(N-1)) mandano INSIEME un turno con una coda nuova di 2-4k token (8-16k caratteri,
    lunghezza diversa per lettore), max_tokens --rmaxt (8): e' la lettura corta su una conversazione gia' in cache;
  - ogni turno successivo della stessa conversazione include le risposte precedenti (la storia cresce, la cache la tiene).
Misure per giro: wall delle letture (primo invio -> ultima fine) e TTFT per lettore, token nuovi letti; t/s degli scrittori
DURANTE la finestra delle letture (token ricevuti nella finestra / durata), prima e dopo; righe `strata pack:` /
`read ... on a thread` / `decoded N rows meanwhile` del motore.  Dopo i giri, parita': ogni lettore rimanda il suo ultimo
turno DA SOLO (temperature 0, --pmaxt token) e il testo si salva per il confronto fra bracci.  Carico CPU altrui e
JumpConnect (CPU che cresce = Jump Desktop connesso) campionati.  Output: cartella lc_<tag>/ con res.json, engine.log, testi.

    python ..\\20261006_due_schede\\bench_lock.py LC-<tag> -- python -u letture_concorrenti.py --tag T --exe X --extra "..." --env "..."
"""
import argparse, json, os, re, shlex, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import banco_p0 as P0   # noqa: E402

D = Path(r'D:\ds4_work\strata\Strata')
K = H.parent / '20261004_routed_keep'
ap = argparse.ArgumentParser()
ap.add_argument('--exe', required=True)
ap.add_argument('--serve', default=None, help='default: <exe dir>/source/serve')
ap.add_argument('--tag', required=True)
ap.add_argument('--extra', default='', help='argomenti motore; un opzione qui SOSTITUISCE quella del Daily')
ap.add_argument('--drop', default='')
ap.add_argument('--env', default='', help='env del motore, "K=V K2=V2"')
ap.add_argument('--port', type=int, default=8104)
ap.add_argument('--readers', type=int, default=4)
ap.add_argument('--writers', type=int, default=2)
ap.add_argument('--rounds', type=int, default=2)
ap.add_argument('--lead', type=float, default=4.0, help='s fra la partenza degli scrittori e quella dei lettori')
ap.add_argument('--tails', default='2000,2700,3400,4000', help='token nuovi per lettore (ciclici)')
ap.add_argument('--rmaxt', type=int, default=8)
ap.add_argument('--wmaxt', type=int, default=600)
ap.add_argument('--pmaxt', type=int, default=64, help='token della ripetizione da soli (parita)')
a = ap.parse_args()
SERVE = Path(a.serve) if a.serve else Path(a.exe).parent / 'source' / 'serve'
OUT = H / f'lc_{a.tag}'
OUT.mkdir(exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
BASE = prefissi['ctx131k']
INSTR = 'Materiale di riferimento (codice e documenti di un progetto):\n\n'
import random as _rnd
_rr = _rnd.Random(20261018)
_BB = BASE + BASE
CTX = {}
for _k in range(8):
    _priv = _rr.randint(0, 70000) * 4
    _off = (140000 + _k * 47000) % len(BASE)
    CTX[f'R{_k}'] = INSTR + BASE[0: 129000] + f"\n\n[Storia privata dell'agente {_k}]\n" + _BB[_off: _off + _priv]
TOOL_Q = ("Questo e' l'output dello strumento che hai chiamato. Analizzalo in relazione al materiale e decidi il passo "
          "successivo, spiegando brevemente perche'.")
assert a.readers + a.writers <= 8


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
        cfg = json.loads((D / 'strata-0143-daily.json').read_text(encoding='utf-8-sig'))   # sola lettura
        base = split_opts(cfg['args'])
        extra = split_opts(shlex.split(a.extra))
        drop = set(shlex.split(a.drop)) | {'--prompt-cache-file', '--vision'} | {e[0] for e in extra}
        cfg['args'] = [x for o in base if o[0] not in drop for x in o] + [x for o in extra for x in o]
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


def ask(model, msgs, maxt, out, key):
    """Una richiesta in streaming; `ticks` = (istante, token cumulati) a ogni chunk di contenuto (per il t/s in finestra)."""
    body = dict(model=model, temperature=0, max_tokens=maxt, stream=True, messages=msgs,
                chat_template_kwargs=dict(enable_thinking=False))
    t0 = time.monotonic()
    first, parts, last, ticks = None, [], None, []
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
                    ticks.append((time.monotonic(), len(parts)))   # un chunk ~ un token (contenuto, non pensiero)
                if c.get('usage'):
                    last = c
        end = time.monotonic()
        txt = ''.join(parts)
        u, tm = (last or {}).get('usage') or {}, (last or {}).get('timings') or {}
        n = u.get('completion_tokens') or 0
        ttft = (first or end) - t0
        dec = (n - 1) / (end - first) if first and n > 1 and end > first else None
        out[key] = dict(ok=True, out=n, ttft=round(ttft, 2), dec_tps=dec and round(dec, 1), wall=round(end - t0, 1),
                        t0=t0, first=first, end=end, ticks=ticks, chunks=len(parts),
                        cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens'), prompt=u.get('prompt_tokens'),
                        prompt_ms=tm.get('prompt_ms'), head=txt[:80].replace('\n', ' '), txt=txt)
        (OUT / f'{key}.txt').write_text(txt, encoding='utf-8')
    except Exception as e:   # noqa: BLE001
        out[key] = dict(ok=False, wall=round(time.monotonic() - t0, 1), t0=t0, end=time.monotonic(), err=repr(e)[:300], ticks=[])


def tool_text(agent, turn, n_chars):
    st = (7919 * agent + 104729 * turn + 3001) % (len(BASE) - n_chars - 1)
    return 'OUTPUT DELLO STRUMENTO:\n' + BASE[st: st + n_chars]


class LoadSampler(threading.Thread):
    """Carico CPU degli altri processi ogni 2 s, e la CPU di JumpConnect (Jump Desktop) a inizio e fine."""
    def __init__(self):
        super().__init__(daemon=True)
        self.halt = threading.Event()
        self.vals = []
        self.jump = []

    def run(self):
        import psutil
        mine = {'strata.exe', 'python.exe', 'pythonw.exe'}
        procs = {}
        while not self.halt.wait(2.0):
            tot, jc = 0.0, 0.0
            for q in psutil.process_iter(['name']):
                try:
                    pr = procs.setdefault(q.pid, q)
                    c = pr.cpu_percent(None)
                    nm = (q.info['name'] or '').lower()
                    if nm not in mine:
                        tot += c
                    if nm.startswith('jumpconnect'):
                        ct = pr.cpu_times()
                        jc += ct.user + ct.system
                except psutil.Error:
                    pass
            self.vals.append(tot / psutil.cpu_count())
            self.jump.append(jc)


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


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
    keep = ('strata pack', 'strata batch: read', 'decoded', 'gave back', 'strata serve: prompt', 'VRAM', 'vram', 'free')
    return [ln[:330] for ln in txt.splitlines() if any(k in ln for k in keep) and 'captured the batch' not in ln]


def tokens_in(ticks, t_a, t_b):
    """Token (chunk di contenuto) ricevuti nell'intervallo [t_a, t_b]."""
    lo = sum(1 for t, _ in ticks if t < t_a)
    hi = sum(1 for t, _ in ticks if t <= t_b)
    return hi - lo


tails = [int(x) for x in a.tails.split(',')]
readers = [f'R{i}' for i in range(a.readers)]
writers = [f'R{a.readers + i}' for i in range(a.writers)]
hist = {c: [dict(role='system', content=CTX[c])] for c in readers + writers}
allres = dict(tag=a.tag, exe=a.exe, extra=a.extra, env=a.env, readers=readers, writers=writers, tails=tails, rounds=[])
smp = LoadSampler()
with Server() as srv:
    allres['startup_log'] = log_since(0)[-8:]
    for ctx in readers + writers:    # riscaldamento: ogni contesto letto una volta (max_tokens 8), uno alla volta
        w = {}
        t = time.monotonic()
        ask(srv.model, hist[ctx] + [dict(role='user', content=prompts['PF_131K'])], 8, w, 'warm_' + ctx)
        r = w['warm_' + ctx]
        print(f'warm {ctx}: {time.monotonic() - t:.1f} s prompt {r.get("prompt")} cached {r.get("cached")} {r.get("err", "")}', flush=True)
    smp.start()
    for rd in range(a.rounds):
        off = log_size()
        res = {}
        # scrittori: turno corto, risposta lunga
        wth = []
        for wi, c in enumerate(writers):
            hist[c].append(dict(role='user', content=tool_text(100 + wi, rd, 500) + '\n\n' + TOOL_Q))
            th = threading.Thread(target=ask, args=(srv.model, list(hist[c]), a.wmaxt, res, f'r{rd}_w{wi}_{c}'))
            wth.append(th)
            th.start()
            time.sleep(0.05)
        time.sleep(a.lead)
        # lettori: INSIEME, coda nuova di 2-4k token
        t_rd0 = time.monotonic()
        rth = []
        for ri, c in enumerate(readers):
            n_tok = tails[(ri + rd * len(readers)) % len(tails)]
            hist[c].append(dict(role='user', content=tool_text(ri, rd, n_tok * 4) + '\n\n' + TOOL_Q))
            th = threading.Thread(target=ask, args=(srv.model, list(hist[c]), a.rmaxt, res, f'r{rd}_r{ri}_{c}'))
            rth.append(th)
            th.start()
            time.sleep(0.05)
        for th in rth:
            th.join()
        t_rd1 = time.monotonic()
        for th in wth:
            th.join()
        for wi, c in enumerate(writers):
            r = res[f'r{rd}_w{wi}_{c}']
            hist[c].append(dict(role='assistant', content=r.get('txt', '')))
        for ri, c in enumerate(readers):
            r = res[f'r{rd}_r{ri}_{c}']
            hist[c].append(dict(role='assistant', content=r.get('txt', '')))
        lines = log_since(off)
        rr = [res[f'r{rd}_r{ri}_{c}'] for ri, c in enumerate(readers)]
        ww = [res[f'r{rd}_w{wi}_{c}'] for wi, c in enumerate(writers)]
        okr = [r for r in rr if r.get('ok')]
        rd_wall = max(r['end'] for r in rr) - min(r['t0'] for r in rr)
        new_tok = sum(max(0, (r.get('prompt') or 0) - (r.get('cached') or 0)) for r in okr)
        win_tok = sum(tokens_in(r['ticks'], t_rd0, t_rd1) for r in ww)
        w_t0 = min(r['t0'] for r in ww)
        w_end = max(r['end'] for r in ww)
        before_tok = sum(tokens_in(r['ticks'], w_t0, t_rd0) for r in ww)
        after_tok = sum(tokens_in(r['ticks'], t_rd1, w_end) for r in ww)
        summ = dict(round=rd, readers_wall=round(rd_wall, 2), ttft=[r.get('ttft') for r in rr],
                    ttft_p50=pct([r['ttft'] for r in okr], 0.5), ttft_max=max([r['ttft'] for r in okr] or [None]),
                    new_tokens_read=new_tok, read_tps_wall=round(new_tok / max(1e-9, rd_wall), 0),
                    prompt=[r.get('prompt') for r in rr], cached=[r.get('cached') for r in rr],
                    writers_tps_during_reads=round(win_tok / max(1e-9, t_rd1 - t_rd0), 1),
                    writers_tps_before=round(before_tok / max(1e-9, t_rd0 - w_t0), 1),
                    writers_tps_after=round(after_tok / max(1e-9, w_end - t_rd1), 1) if w_end > t_rd1 + 1 else None,
                    writers_dec_tps=[r.get('dec_tps') for r in ww], writers_out=[r.get('out') for r in ww],
                    errors=[r.get('err') for r in rr + ww if not r.get('ok')],
                    pack_lines=[ln for ln in lines if 'strata pack:' in ln],
                    read_lines=[ln for ln in lines if 'on a thread of its own' in ln or 'decoded' in ln][:12])
        print(f'giro {rd}: letture {len(rr)} in {rd_wall:.2f} s (TTFT {summ["ttft"]}, nuovi {new_tok} tok = {summ["read_tps_wall"]:.0f} t/s); '
              f'scrittori {summ["writers_tps_during_reads"]} t/s durante le letture, {summ["writers_tps_before"]} prima, '
              f'{summ["writers_tps_after"]} dopo; dec {summ["writers_dec_tps"]}', flush=True)
        for ln in summ['pack_lines'] + summ['read_lines']:
            print('   | ' + ln[:300], flush=True)
        for k, r in sorted(res.items()):
            r.pop('ticks', None)
            r.pop('txt', None)
        summ['res'] = res
        allres['rounds'].append(summ)
        (OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')
        time.sleep(2.0)
    # parita': l'ultimo turno di ogni lettore rimandato DA SOLO (stessa conversazione, piu' token), uno alla volta
    par = {}
    for ri, c in enumerate(readers):
        msgs = hist[c][:-1]     # senza la risposta da 8 token: lo stesso prompt dell'ultima lettura
        ask(srv.model, msgs, a.pmaxt, par, f'par_r{ri}_{c}')
        r = par[f'par_r{ri}_{c}']
        print(f'parita {c}: ttft {r.get("ttft")} cached {r.get("cached")} out {r.get("out")} head {r.get("head")!r}', flush=True)
        r.pop('ticks', None)
        r.pop('txt', None)
    allres['parity'] = par
    smp.halt.set()
    smp.join(timeout=5)
    jump = smp.jump
    allres['load_other'] = dict(mean=round(sum(smp.vals) / max(1, len(smp.vals)), 1), p90=round(pct(smp.vals, 0.9) or 0, 1), n=len(smp.vals))
    allres['jumpconnect_cpu_s'] = dict(start=jump[0] if jump else None, end=jump[-1] if jump else None,
                                       connected=bool(jump) and (jump[-1] - jump[0]) > 2.0)
    (OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')
print('carico altrui', allres['load_other'], 'JumpConnect', allres['jumpconnect_cpu_s'], flush=True)
print('fine', a.tag, flush=True)
