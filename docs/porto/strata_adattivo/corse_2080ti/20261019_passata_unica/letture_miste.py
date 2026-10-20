"""Banco «4 agenti a contesti misti, letture e scritture in contemporanea» (passata unica, 20/10).

UN motore avviato dalla config del Daily (sola lettura: strata-0143-daily.json, senza --prompt-cache-file e --vision),
exe/argomenti/env dati, client in streaming via server HTTP.  4 conversazioni con contesti di lunghezze diverse
(default 2k, 8k, 30k, 90k token, tagliati dal prefisso ctx131k + una storia privata a seme fisso), scaldate una alla
volta prima del cronometro; i token reali di ogni contesto sono letti dal `prompt_tokens` della scaldata.

Giri, per ogni braccio:
  misti (--rounds): `--split` agenti mandano INSIEME una lettura (1-4k token nuovi, max_tokens --rmaxt) mentre gli altri
    scrivono (turno corto ~500 caratteri, max_tokens --wmaxt); i ruoli si scambiano a ogni giro;
  burst (--burst): TUTTE e 4 le letture insieme, con --side scrittori di supporto (contesto 2k, --smaxt token) partiti
    --lead s prima - cosi` il t/s di decode «degli altri durante» esiste anche nel burst.
Criteri per giro: `readers_wall` (primo invio -> ultima fine delle letture), TTFT per lettore, token nuovi letti e t/s
di lettura, t/s degli scrittori DURANTE la finestra delle letture (e prima/dopo, dai chunk ricevuti), e le righe del
motore nella finestra: `prompt N tokens = R reused + L read in X ms` (lettura lato motore), `read N tokens on a thread
of its own ... the slots decoded M rows meanwhile` (decode degli altri durante la lettura), `strata pack: ...` /
`gave back ...` (il pacco).  Poi parita`: l'ultimo turno di lettura di ogni agente rimandato DA SOLO (temperature 0,
--pmaxt token): i testi si confrontano fra bracci (token identici).  Carico CPU altrui e JumpConnect campionati.
Output: cartella lc_<tag>/ con res.json, engine.log, un .txt per ogni risposta.

    python ..\\20261006_due_schede\\bench_lock.py LC-<tag> -- python -u -X utf8 letture_miste.py --tag T --exe X --extra "..." --env "..."
"""
import argparse, json, os, re, shlex, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import banco_p0 as P0   # noqa: E402

D = Path(r'D:\ds4_work\strata\Strata')
ap = argparse.ArgumentParser()
ap.add_argument('--exe', required=True)
ap.add_argument('--serve', default=None, help='default: <exe dir>/source/serve')
ap.add_argument('--tag', required=True)
ap.add_argument('--extra', default='', help='argomenti motore; un opzione qui SOSTITUISCE quella del Daily')
ap.add_argument('--drop', default='')
ap.add_argument('--env', default='', help='env del motore, "K=V K2=V2"')
ap.add_argument('--port', type=int, default=8105)
ap.add_argument('--ctx', default='2000,8000,30000,90000', help='token di contesto per agente')
ap.add_argument('--tails', default='1000,2000,3000,4000', help='token nuovi a ogni lettura, per agente')
ap.add_argument('--split', type=int, default=2, help='lettori nei giri misti (gli altri scrivono)')
ap.add_argument('--rounds', type=int, default=2, help='giri misti (ruoli scambiati a ogni giro)')
ap.add_argument('--burst', type=int, default=1, help='giri finali con TUTTE le letture insieme')
ap.add_argument('--side', type=int, default=1, help='scrittori di supporto (contesto 2k) nei giri burst')
ap.add_argument('--side-ctx', type=int, default=2000)
ap.add_argument('--lead', type=float, default=4.0, help='s fra la partenza degli scrittori e quella dei lettori')
ap.add_argument('--rmaxt', type=int, default=8, help='token di risposta di una lettura')
ap.add_argument('--wmaxt', type=int, default=400, help='token di uno scrittore nel giro misto')
ap.add_argument('--smaxt', type=int, default=600, help='token dello scrittore di supporto')
ap.add_argument('--pmaxt', type=int, default=64, help='token della ripetizione da soli (parita)')
ap.add_argument('--dry', action='store_true', help='stampa contesti e programma dei giri e chiude (niente server, niente GPU)')
a = ap.parse_args()
SERVE = Path(a.serve) if a.serve else Path(a.exe).parent / 'source' / 'serve'
OUT = H / f'lc_{a.tag}'
OUT.mkdir(exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
BASE = prefissi['ctx131k']
CPT = 4.04          # caratteri per token del prefisso ctx131k (529521 caratteri = 131k token)
INSTR = 'Materiale di riferimento (codice e documenti di un progetto):\n\n'
TOOL_Q = ("Questo e' l'output dello strumento che hai chiamato. Analizzalo in relazione al materiale e decidi il passo "
          "successivo, spiegando brevemente perche'.")

ctx_tok = [int(x) for x in a.ctx.split(',')]
tail_tok = [int(x) for x in a.tails.split(',')]
assert len(ctx_tok) == len(tail_tok) == 4, 'un contesto e una coda per ciascuno dei 4 agenti'
assert 0 < a.split < 4


def make_ctx(i, target_tok, off_mul):
    """Contesto di ~target_tok token: prefisso comune tagliato + storia privata a seme fisso (offset diversi per agente)."""
    n = int(target_tok * CPT)
    half = n // 2
    off = (90000 + i * 61000 * off_mul) % max(1, len(BASE) - half - 1)
    return INSTR + BASE[0:half] + f"\n\n[Storia privata dell'agente {i}]\n" + BASE[off: off + (n - half)]


AG = [f'A{t // 1000}k' for t in ctx_tok]
CTX = {AG[i]: make_ctx(i, ctx_tok[i], 1) for i in range(4)}
SIDES = [f'S{i}' for i in range(a.side)]
for i, s in enumerate(SIDES):
    CTX[s] = make_ctx(20 + i, a.side_ctx, 1)
ALL = AG + SIDES
assert a.side <= 2, 'gli slot di conversazione bastano per 4 agenti + 2 scrittori di supporto'


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
                    ticks.append((time.monotonic(), len(parts)))
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
    st = (7919 * agent + 104729 * turn + 3001) % max(1, len(BASE) - n_chars - 1)
    return 'OUTPUT DELLO STRUMENTO:\n' + BASE[st: st + n_chars]


class LoadSampler(threading.Thread):
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


def log_slice(off, name='engine.log'):
    try:
        with (OUT / name).open('rb') as f:
            f.seek(off)
            return f.read().decode('utf-8', 'replace')
    except OSError:
        return ''


def log_size(name='engine.log'):
    try:
        return (OUT / name).stat().st_size
    except OSError:
        return 0


KEEP = ('strata pack', 'strata batch: read', 'gave back', 'VRAM', 'vram', 'free')
RX_REQ = re.compile(r'prompt (\d+) tokens = (\d+) reused \+ (\d+)(?: of \d+)? read in (\d+) ms.*?, (\d+) generated in (\d+) ms')
RX_CONC = re.compile(r'read (\d+) tokens on a thread of its own in (\d+) ms.*?decoded (\d+) rows meanwhile \(([\d.]+) rows/s')
RX_PACK = re.compile(r'strata pack: (\d+) tokens of this prompt read with (\d+) prompts? sent ahead \((\d+) tokens')


def eng_summary(raw):
    """Lato motore, dalla finestra: letture (token letti / ms), righe del pacco, decode concorrente delle finestre."""
    rq = [tuple(map(int, m.groups())) for m in RX_REQ.finditer(raw)]
    cc = [tuple(map(float, m.groups())) for m in RX_CONC.finditer(raw)]
    pk = [tuple(map(int, m.groups())) for m in RX_PACK.finditer(raw)]
    return dict(requests=len(rq),
                read_tokens=sum(x[2] for x in rq), read_ms=sum(x[3] for x in rq),
                read_tps=round(sum(x[2] for x in rq) / max(1e-9, sum(x[3] for x in rq) / 1000.0), 0),
                gen=sum(x[4] for x in rq), gen_ms=sum(x[5] for x in rq),
                gen_tps=round(sum(x[4] for x in rq) / max(1e-9, sum(x[5] for x in rq) / 1000.0), 1),
                per_request=[dict(prompt=x[0], reused=x[1], read=x[2], read_ms=x[3], gen=x[4], gen_ms=x[5]) for x in rq],
                conc_reads=[dict(read=int(x[0]), ms=int(x[1]), rows=int(x[2]), rows_s=x[3]) for x in cc],
                pack=[dict(own=a_, kept=b_, ahead=c_) for a_, b_, c_ in pk],
                gave_back=len(re.findall(r'gave back \d+ tokens read ahead', raw)))


def log_lines(raw):
    return [ln[:330] for ln in raw.splitlines() if any(k in ln for k in KEEP) and 'captured the batch' not in ln]


def tokens_in(ticks, t_a, t_b):
    lo = sum(1 for t, _ in ticks if t < t_a)
    hi = sum(1 for t, _ in ticks if t <= t_b)
    return hi - lo


def launch(model, msgs, maxt, res, key, threads, sleep=0.05):
    th = threading.Thread(target=ask, args=(model, list(msgs), maxt, res, key))
    threads.append(th)
    th.start()
    time.sleep(sleep)


hist = {c: [dict(role='system', content=CTX[c])] for c in ALL}
last_read = {c: None for c in AG}      # messaggio dell'ultima lettura di ogni agente (per la parita`)
allres = dict(tag=a.tag, exe=a.exe, extra=a.extra, env=a.env, agents=AG, side=SIDES, ctx_tok=ctx_tok,
              tail_tok=tail_tok, split=a.split, rounds=[])
smp = LoadSampler()
plan = []
for rd in range(a.rounds):
    rd_readers = AG[:a.split] if rd % 2 == 0 else AG[a.split:]
    plan.append(('mixed', rd, rd_readers, [c for c in AG if c not in rd_readers], SIDES[:0]))
for b in range(a.burst):
    plan.append(('burst', a.rounds + b, AG, [], SIDES))

if a.dry:     # niente server, niente GPU: stampa contesti e programma dei giri
    print(f'exe {a.exe}\nenv {a.env}\nport {a.port}\nagenti {AG} + scrittori di supporto {SIDES}')
    for c in ALL:
        print(f'  contesto {c}: {len(CTX[c])} caratteri =~ {round(len(CTX[c]) / CPT)} token')
    for kind, rd, readers, writers, sides in plan:
        new = {c: tail_tok[AG.index(c)] for c in readers}
        mt = {**{c: a.wmaxt for c in writers}, **{c: a.smaxt for c in sides}}
        print(f'  {kind}{rd}: lettori {readers} (nuovi {new} token, max_tokens {a.rmaxt}) | scrittori '
              f'{writers + sides} (max_tokens {mt}) | lettori inviati a +{a.lead:.0f} s dagli scrittori')
    print(f'poi ogni giro: readers_wall, ttft, t/s scrittori durante, righe pack; e parita` da sola a {a.pmaxt} token')
    sys.exit(0)

with Server() as srv:
    allres['startup_log'] = log_lines(log_slice(0))[-8:]
    # riscaldamento: ogni contesto letto una volta (max_tokens 8), uno alla volta; da qui i token reali del contesto
    ctxinfo = {}
    for c in AG + SIDES:
        w = {}
        t = time.monotonic()
        ask(srv.model, hist[c] + [dict(role='user', content=TOOL_Q)], 8, w, 'warm_' + c)
        r = w['warm_' + c]
        chars = sum(len(m['content']) for m in hist[c]) + len(TOOL_Q)
        pt = r.get('prompt') or 0
        r['cpt'] = round(chars / pt, 3) if pt else None
        r['ctx_target'] = ctx_tok[AG.index(c)] if c in AG else a.side_ctx
        ctxinfo[c] = dict(target=r['ctx_target'], prompt=pt, cached=r.get('cached'), cpt=r['cpt'],
                          warm_s=round(time.monotonic() - t, 1))
        allres['contexts'] = ctxinfo
        print(f'warm {c}: {time.monotonic() - t:.1f} s prompt {pt} cached {r.get("cached")} '
              f'(target {r["ctx_target"]}, {r["cpt"]} car/token) {r.get("err", "")}', flush=True)
        if r.get('err'):
            raise SystemExit(f'warming {c} failed: {r["err"]}')
    smp.start()
    for kind, rd, readers, writers, sides in plan:
        off, soff = log_size(), log_size('server.log')
        res = {}
        wt = []
        for si, c in enumerate(writers + sides):
            mt = a.wmaxt if c in writers else a.smaxt
            hist[c].append(dict(role='user', content=tool_text(100 + si, rd, 500) + '\n\n' + TOOL_Q))
            launch(srv.model, hist[c], mt, res, f'{kind}{rd}_w_{c}', wt)
        time.sleep(a.lead)
        t_rd0 = time.monotonic()
        rt = []
        for ri, c in enumerate(readers):
            n_tok = tail_tok[AG.index(c)]
            msgs = hist[c] + [dict(role='user', content=tool_text(AG.index(c), rd, int(n_tok * CPT)) + '\n\n' + TOOL_Q)]
            last_read[c] = msgs
            launch(srv.model, msgs, a.rmaxt, res, f'{kind}{rd}_r_{c}', rt)
        for th in rt:
            th.join()
        t_rd1 = time.monotonic()
        for th in wt:
            th.join()
        for c in writers + sides:
            hist[c].append(dict(role='assistant', content=res[f'{kind}{rd}_w_{c}'].get('txt', '')))
        for c in readers:
            hist[c].append(dict(role='assistant', content=res[f'{kind}{rd}_r_{c}'].get('txt', '')))
        raw = log_slice(off)
        srvraw = log_slice(soff, 'server.log')      # riga `[strata] pack:` dell'agente 3: quanti prompt raccolti nella finestra
        rr = [res[f'{kind}{rd}_r_{c}'] for c in readers]
        ww = [res[f'{kind}{rd}_w_{c}'] for c in writers + sides]
        okr = [r for r in rr if r.get('ok')]
        okw = [r for r in ww if r.get('ok')]
        rd_wall = max(r['end'] for r in rr) - min(r['t0'] for r in rr)
        new_tok = sum(max(0, (r.get('prompt') or 0) - (r.get('cached') or 0)) for r in okr)
        w_t0 = min([r['t0'] for r in okw], default=t_rd0)
        w_end = max([r['end'] for r in okw], default=t_rd1)
        win_tok = sum(tokens_in(r['ticks'], t_rd0, t_rd1) for r in okw)
        before_tok = sum(tokens_in(r['ticks'], w_t0, t_rd0) for r in okw)
        after_tok = sum(tokens_in(r['ticks'], t_rd1, w_end) for r in okw)
        summ = dict(kind=kind, round=rd, readers=readers, writers=writers + sides,
                    readers_wall=round(rd_wall, 2),
                    # validita` del giro: se gli invii sono davvero sovrapposti (altrimenti non e` una passata insieme)
                    send_span=round(max(r['t0'] for r in rr) - min(r['t0'] for r in rr), 2),
                    finish_span=round(max(r['end'] for r in rr) - min(r['end'] for r in rr), 2),
                    overlap_min_s=round(min(min(r['end'] for r in rr) - max(x['t0'] for x in rr), default=0), 2),
                    ttft=[r.get('ttft') for r in rr], ttft_p50=pct([r['ttft'] for r in okr], 0.5),
                    ttft_max=max([r['ttft'] for r in okr] or [None]),
                    new_tokens_read=new_tok, read_tps_wall=round(new_tok / max(1e-9, rd_wall), 0),
                    prompt={c: res[f'{kind}{rd}_r_{c}'].get('prompt') for c in readers},
                    cached={c: res[f'{kind}{rd}_r_{c}'].get('cached') for c in readers},
                    writers_tps_during_reads=round(win_tok / max(1e-9, t_rd1 - t_rd0), 1),
                    writers_tps_before=round(before_tok / max(1e-9, t_rd0 - w_t0), 1) if t_rd0 > w_t0 else None,
                    writers_tps_after=round(after_tok / max(1e-9, w_end - t_rd1), 1) if w_end > t_rd1 + 1 else None,
                    writers_dec_tps=[r.get('dec_tps') for r in ww], writers_out=[r.get('out') for r in ww],
                    engine=eng_summary(raw),
                    errors=[r.get('err') for r in rr + ww if not r.get('ok')],
                    pack_lines=[ln for ln in log_lines(raw) if 'strata pack' in ln][:10],
                    gather_lines=[ln[:300] for ln in srvraw.splitlines() if 'pack:' in ln and 'sent ahead' in ln][:10])
        print(f'{kind} {rd}: letture {len(rr)} in {rd_wall:.2f} s (TTFT {summ["ttft"]}, nuovi {new_tok} tok = '
              f'{summ["read_tps_wall"]:.0f} t/s); scrittori {summ["writers_tps_during_reads"]} t/s durante, '
              f'{summ["writers_tps_before"]} prima, {summ["writers_tps_after"]} dopo; motore {summ["engine"]["read_tps"]} '
              f'tok/s letti, {len(summ["pack_lines"])} righe pack, {len(summ["gather_lines"])} finestre server', flush=True)
        for ln in summ['pack_lines'] + summ['gather_lines']:
            print('   | ' + ln[:300], flush=True)
        for k2, r in sorted(res.items()):
            r.pop('ticks', None)
            r.pop('txt', None)
        summ['res'] = res
        allres['rounds'].append(summ)
        (OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')
        time.sleep(2.0)

    # parita`: l'ultima lettura di ogni agente, rimandata DA SOLO (stessa conversazione, piu` token)
    par = {}
    for c in AG:
        if last_read[c] is None:
            continue
        ask(srv.model, last_read[c], a.pmaxt, par, f'par_{c}')
        r = par[f'par_{c}']
        print(f'parita {c}: ttft {r.get("ttft")} cached {r.get("cached")} out {r.get("out")} head {r.get("head")!r}',
              flush=True)
        r.pop('ticks', None)
        r.pop('txt', None)
    allres['parity'] = par
    smp.halt.set()
    smp.join(timeout=5)
    jump = smp.jump
    allres['load_other'] = dict(mean=round(sum(smp.vals) / max(1, len(smp.vals)), 1),
                                p90=round(pct(smp.vals, 0.9) or 0, 1), n=len(smp.vals))
    allres['jumpconnect_cpu_s'] = dict(start=jump[0] if jump else None, end=jump[-1] if jump else None,
                                       connected=bool(jump) and (jump[-1] - jump[0]) > 2.0)
    allres['mix_wall'] = dict(
        burst_walls=[r['readers_wall'] for r in allres['rounds'] if r['kind'] == 'burst'],
        mixed_walls=[r['readers_wall'] for r in allres['rounds'] if r['kind'] == 'mixed'],
        read_tokens_total=sum(r['new_tokens_read'] for r in allres['rounds']),
        engine_read_tokens=sum(r['engine']['read_tokens'] for r in allres['rounds']),
        engine_read_ms=sum(r['engine']['read_ms'] for r in allres['rounds']),
        pack_lines=sum(len(r['pack_lines']) for r in allres['rounds']),
        gather_lines=sum(len(r['gather_lines']) for r in allres['rounds']),
        conc_rows_s=[x['rows_s'] for r in allres['rounds'] for x in r['engine']['conc_reads']],
    )
    (OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')

print('carico altrui', allres['load_other'], 'JumpConnect', allres['jumpconnect_cpu_s'], flush=True)
print('mix', allres['mix_wall'], flush=True)
print('fine', a.tag, flush=True)
