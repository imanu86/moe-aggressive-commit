"""Replay di una traccia di lavoro reale (agenti/chat) contro un server Strata avviato da questo script.

La traccia (build_trace.py) ha per ogni richiesta: sessione, istante di invio, token di prompt/riusati/nuovi, token generati,
pensiero (tempo fra la fine della richiesta precedente della stessa sessione e l'invio della successiva = strumento + harness).
Il replay rigioca una FINESTRA della traccia:
  - stessi arrivi relativi: la prima richiesta di ogni sessione parte all'istante osservato (0 se era gia' in coda all'inizio
    della finestra); le successive partono quando la precedente della stessa sessione FINISCE nel replay, piu' il pensiero osservato
    (dipendenze reali: nel replay non si manda un turno prima che il precedente sia stato servito);
  - stesse dimensioni: prompt di P token, output di al piu' `out` token (max_tokens);
  - stessa struttura di prefissi: un prefisso di sistema comune a tutte le sessioni (SHARED_TOK token), poi una storia privata per
    sessione che cresce di turno in turno (prompt k = prompt k-1 + risposta k-1 + risultato di strumento); quando la traccia mostra
    un calo del prompt (compattazione o taglio) la sessione ricomincia da una conversazione nuova.
  Il TESTO e' sintetico (fixture del banco, mai prompt reali); la lunghezza in token e' regolata sul conteggio vero del server
  (usage.prompt_tokens) a ogni turno.  Il RIUSO non e' imposto: lo decide la cache del server (e la sua configurazione).
Prima del cronometro le conversazioni che erano gia' in corso all'inizio della finestra vengono lette una volta (riscaldamento,
max_tokens 1) nell'ordine in cui erano state servite, cosi' la cache parte da uno stato confrontabile con l'originale.

Misure: tempo totale per finire la finestra (dal via fino alla fine dell'ultima richiesta), TTFT per richiesta (invio -> primo
contenuto), attesa in coda (TTFT meno tempo di lettura del server), token letti/riusati, decode aggregato, carico CPU altrui.

    python ..\\20261006_due_schede\\bench_lock.py REPLAY-<tag> -- python -u replay_trace.py --tag T --exe X --extra "..." --env "K=V"
"""
import argparse, collections, json, os, re, shlex, socket, statistics as stt, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

D = Path(r'D:\ds4_work\strata\Strata')
K = H.parent / '20261004_routed_keep'
ap = argparse.ArgumentParser()
ap.add_argument('--trace', default=str(H / 'trace_dsh_20261016.json'))
ap.add_argument('--t0', type=float, default=3600.0, help='inizio finestra (s dall inizio del lavoro)')
ap.add_argument('--span', type=float, default=1800.0, help='durata finestra: richieste inviate prima di t0+span')
ap.add_argument('--exe', default=str(K / 'build-upsmain-d06429ee' / 'strata.exe'))
ap.add_argument('--serve', default=None, help='default: <exe dir>/source/serve')
ap.add_argument('--tag', required=True)
ap.add_argument('--extra', default='', help='argomenti motore; un opzione qui SOSTITUISCE quella del Daily')
ap.add_argument('--drop', default='', help='opzioni del Daily da togliere')
ap.add_argument('--env', default='', help='env del motore, "K=V K2=V2"')
ap.add_argument('--port', type=int, default=8102)
ap.add_argument('--think-scale', type=float, default=1.0)
ap.add_argument('--think-cap', type=float, default=120.0, help='tetto del pensiero (s): oltre e attesa di altri agenti, non strumento')
ap.add_argument('--shared-tok', type=int, default=9218)
ap.add_argument('--ratio', type=float, default=3.9, help='caratteri per token iniziali (poi corretti sul conteggio del server)')
ap.add_argument('--deadline', type=float, default=3600.0, help='s dal via oltre i quali si chiude (richieste non finite segnalate)')
ap.add_argument('--no-warm', action='store_true')
ap.add_argument('--dup', type=int, default=1, help='duplica ogni sessione N volte (testo privato diverso): N*4 agenti dalle 4 della traccia')
ap.add_argument('--dup-stagger', type=float, default=1.5, help='s di sfasamento fra le copie')
ap.add_argument('--dry', action='store_true', help='stampa il piano e basta (niente server, niente GPU)')
ap.add_argument('--config', default='strata-0143-daily.json', help='config del Daily (in D:/ds4_work/strata/Strata) da cui prendere args e env; 26/10: strata-026-daily.json o una copia con percorso assoluto')
ap.add_argument('--out-base', default=str(H), help='cartella che contiene replay_<tag> (default: questa; 26/10: 20261026_leve/corse)')
ap.add_argument('--save-text', action='store_true', help='salva in <corsa>/testi/<sessione>_<indice>.json il testo generato (mai il prompt)')
ap.add_argument('--only', default='', help='solo queste sessioni della traccia, es. A,B,C (26/10: i 3 sotto-agenti senza l orchestratore P)')
a = ap.parse_args()

tr = json.loads(Path(a.trace).read_text(encoding='utf-8'))
REQ = tr['req']
T0, T1 = a.t0, a.t0 + a.span
bys = collections.defaultdict(list)
for r in REQ:
    bys[r['sid']].append(r)
for v in bys.values():
    v.sort(key=lambda r: r['send'])

# ------------------------------------------------------------------ piano
def extends(prev, cur):
    return prev is not None and cur['P'] >= prev['P'] + max(0, prev['out'] - 64)


plan = {}      # sid -> dict(warm=req|None, reqs=[...])
for sid, rs in bys.items():
    win = [r for r in rs if r['end'] > T0 and r['send'] < T1]
    if not win:
        continue
    i0 = rs.index(win[0])
    warm = rs[i0 - 1] if i0 > 0 and rs[i0 - 1]['end'] <= T0 else None
    if warm is not None and not extends(warm, win[0]):
        warm = None      # il primo turno della finestra ricomincia da zero: scaldare non serve
    plan[sid] = dict(warm=warm, reqs=win)
if a.only:
    plan = {k: v for k, v in plan.items() if k in set(a.only.split(','))}
    if not plan:
        raise SystemExit('--only: nessuna sessione della finestra corrisponde')


def orig_stats():
    rs = [r for v in plan.values() for r in v['reqs']]
    ends = max(r['end'] for r in rs) - T0
    tt = [r['first'] - max(r['send'], T0) for r in rs if r['first'] is not None and r['first'] > T0]
    sv = sum(r['srv_read_ms'] + r['srv_gen_ms'] for r in rs) / 1000
    return dict(requests=len(rs), makespan=ends, ttft_p50=pct(tt, .5), ttft_p90=pct(tt, .9), ttft_max=max(tt), ttft_mean=sum(tt) / len(tt),
                prompt=sum(r['P'] for r in rs), reused=sum(r['reused'] for r in rs), new=sum(r['new'] for r in rs),
                out=sum(r['out'] for r in rs), server_read_s=sum(r['srv_read_ms'] for r in rs) / 1000,
                server_gen_s=sum(r['srv_gen_ms'] for r in rs) / 1000, server_busy_s=sv)


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


OS = orig_stats()
NSESS0 = len(plan)
if a.dup > 1:
    for sid in list(plan):
        for d in range(2, a.dup + 1):
            nsid = f'{sid}{d}'
            plan[nsid] = dict(plan[sid], stagger=(d - 1) * a.dup_stagger)
            bys[nsid] = bys[sid]
print('FINESTRA', f'{T0:.0f}-{T1:.0f} s del lavoro:', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in OS.items()}, flush=True)
for sid, v in plan.items():
    w = v['warm']
    print(f'  {sid}: {len(v["reqs"])} richieste, warm {"P=%d" % w["P"] if w else "-"}, primo invio {max(0, v["reqs"][0]["send"] - T0):.0f} s, '
          f'P {v["reqs"][0]["P"]}..{max(r["P"] for r in v["reqs"])}, reset {sum(1 for p, c in zip(v["reqs"], v["reqs"][1:]) if not extends(p, c))}',
          flush=True)
if a.dry:
    sys.exit(0)

import banco_p0 as P0   # noqa: E402

OUT = Path(a.out_base) / f'replay_{a.tag}'
OUT.mkdir(parents=True, exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
POOL = prefissi['ctx131k'] + prefissi['aghi131k']
INSTR = 'Materiale di riferimento (codice e documenti di un progetto):\n\n'
def tool_q(outtok):
    """Domanda finale: chiede una risposta lunga quanto l'originale (il server non ha min_tokens: il modello si ferma presto)."""
    return ("Questo e' l'output dello strumento che hai chiamato. Analizzalo in relazione al materiale e decidi il passo "
            f"successivo, spiegando nel dettaglio perche'. Rispondi in modo esteso, circa {max(10, int(outtok * 0.7))} parole.")
ratio = [a.ratio]
cursor = collections.Counter()
SIDX = {s: i for i, s in enumerate(sorted(plan))}


def piece(sid, ntok):
    """Testo sintetico di ~ntok token, preso in sequenza dal pool a partire da un offset per sessione (mai lo stesso testo fra sessioni)."""
    n = max(8, int(ntok * ratio[0]))
    st = ((SIDX[sid] * 262144 if a.dup == 1 else SIDX[sid] * (len(POOL) // len(SIDX)) + 7777) + cursor[sid]) % len(POOL)
    cursor[sid] += n
    pool2 = POOL + POOL
    return pool2[st: st + n]


SHARED = INSTR + (POOL[-int(a.shared_tok * 3.9):])


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
        cfg = json.loads((D / a.config).read_text(encoding='utf-8-sig'))   # SOLA LETTURA (a.config assoluto vince su D)
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
        self.args = cfg['args']
        self.serve = Path(a.serve) if a.serve else Path(a.exe).parent / 'source' / 'serve'

    def __enter__(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', a.port))
        env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
        for kv in shlex.split(a.env):   # il server legge STRATA_PACK_CONCURRENT / STRATA_PACK_WAIT_MS solo dal suo ambiente (come con un .bat)
            env[kv.split('=', 1)[0]] = kv.split('=', 1)[1]
        env['PYTHONIOENCODING'] = 'utf-8'
        self.p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(self.serve / 'server.py'),
                                   '--engine', 'strata', '--config', str(self.cfg_path), '--host', '127.0.0.1',
                                   '--port', str(a.port)],
                                  cwd=D, env=env, stdout=(OUT / 'server.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)   # priorita' normale
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1500:
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
        try:
            _, alive = psutil.wait_procs(kids, timeout=20)
        except psutil.Error:   # 26/10: AccessDenied su un figlio già in chiusura fermava tutta la coda
            alive = kids
        for kd in alive:
            try:
                kd.kill()
            except psutil.Error:
                pass
        subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
        subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)


class MemSampler(threading.Thread):
    """Memoria ogni 3 s: working set e privata dei processi strata.exe, RAM disponibile e swap del sistema."""
    def __init__(self):
        super().__init__(daemon=True)
        self.halt = threading.Event()
        self.rows = []

    def run(self):
        import psutil
        while not self.halt.wait(3.0):
            ws = pv = 0
            for q in psutil.process_iter(['name']):
                try:
                    if (q.info['name'] or '').lower() == 'strata.exe':
                        mi = q.memory_info()
                        ws += mi.wset
                        pv += getattr(mi, 'private', mi.vms)
                except psutil.Error:
                    pass
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            self.rows.append((time.monotonic(), ws / 2**30, pv / 2**30, vm.available / 2**30, sw.used / 2**30, vm.total / 2**30))


class LoadSampler(threading.Thread):
    """Carico CPU (% della macchina) degli ALTRI processi, ogni 2 s: sistema meno strata/python del banco; OktoCGControl a parte."""
    def __init__(self):
        super().__init__(daemon=True)
        self.halt = threading.Event()
        self.vals, self.okto = [], []
        self.byname = collections.Counter()

    def run(self):
        import psutil
        mine = {'strata.exe', 'python.exe', 'pythonw.exe', 'system idle process'}      # l'idle NON e' carico altrui
        procs = {}
        while not self.halt.wait(2.0):
            tot = ok = 0.0
            for q in psutil.process_iter(['name']):
                try:
                    pr = procs.setdefault(q.pid, q)
                    c = pr.cpu_percent(None)
                    nm = (q.info['name'] or '').lower()
                    if nm.startswith('oktocg') or nm.startswith('cgcontrol'):
                        ok += c
                    elif nm not in mine:
                        tot += c
                        self.byname[nm] += c * 2.0 / psutil.cpu_count()      # percento-secondi della macchina
                except psutil.Error:
                    pass
            self.vals.append(tot / psutil.cpu_count())
            self.okto.append(ok / psutil.cpu_count())


def chat(model, msgs, maxt, rec):
    body = dict(model=model, temperature=0, max_tokens=maxt, stream=True, messages=msgs,
                chat_template_kwargs=dict(enable_thinking=False))
    t0 = time.monotonic()
    first, parts, last = None, [], None
    finish, tcalls = None, {}      # motivo di fine e chiamate a strumenti (--save-text)
    rec['t_send'] = t0

    def add_tool_calls(lst, key):
        for j, tc in enumerate(lst or []):
            slot = tcalls.setdefault(tc.get('index', j) if key == 'delta' else j, dict(id=None, name='', arguments=''))
            slot['id'] = tc.get('id') or slot['id']
            fn = tc.get('function') or {}
            slot['name'] += fn.get('name') or ''
            slot['arguments'] += fn.get('arguments') or ''
    try:
        req = urllib.request.Request(f'http://127.0.0.1:{a.port}/v1/chat/completions', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=7200) as r:
            streaming = 'text/event-stream' in (r.headers.get('Content-Type') or '')
            if not streaming:
                # risposta intera (non in streaming): un solo JSON
                c = json.loads(r.read().decode('utf-8', 'replace'))
                ch = (c.get('choices') or [{}])[0]
                m = ch.get('message') or {}
                if m.get('content'):
                    first = time.monotonic()
                    parts.append(m['content'])
                finish = ch.get('finish_reason')
                add_tool_calls(m.get('tool_calls'), 'message')
                if c.get('usage'):
                    last = c
            for raw in (r if streaming else []):
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
                if c['choices'][0].get('finish_reason'):
                    finish = c['choices'][0]['finish_reason']
                add_tool_calls(d.get('tool_calls'), 'delta')
                if d.get('content'):
                    if first is None:
                        first = time.monotonic()
                    parts.append(d['content'])
                if c.get('usage'):
                    last = c
        end = time.monotonic()
        u, tm = (last or {}).get('usage') or {}, (last or {}).get('timings') or {}
        rec.update(ok=True, t_first=first or end, t_end=end, out=u.get('completion_tokens') or 0, prompt=u.get('prompt_tokens'),
                   cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens'), prompt_ms=tm.get('prompt_ms'),
                   text=''.join(parts), finish=finish, tool_calls=[tcalls[k] for k in sorted(tcalls)])
    except Exception as e:   # noqa: BLE001
        rec.update(ok=False, t_end=time.monotonic(), err=repr(e)[:300], text='')
    return rec


class Conv:
    """Conversazione sintetica di una sessione."""
    def __init__(self, sid):
        self.sid = sid
        self.msgs = None
        self.prompt = 0       # token di prompt contati dal server all'ultimo turno
        self.out = 0
        self.last_text = ''

    def fresh(self, ptok, outtok):
        priv = max(64, ptok - a.shared_tok - 40)
        self.msgs = [dict(role='system', content=SHARED), dict(role='user', content=piece(self.sid, priv) + '\n\n' + tool_q(outtok))]

    def extend(self, ntok, outtok):
        self.msgs = self.msgs + [dict(role='assistant', content=self.last_text or '(nessuna risposta)'),
                                 dict(role='user', content='OUTPUT DELLO STRUMENTO:\n' + piece(self.sid, max(16, ntok)) + '\n\n' + tool_q(outtok))]

    def chars(self):
        return sum(len(m['content']) for m in self.msgs)


def do_request(model, conv, rec, maxt):
    rec['msgs_chars'] = conv.chars()
    chat(model, conv.msgs, maxt, rec)
    if rec.get('ok') and rec.get('prompt'):
        if rec['prompt'] > 20000:
            ratio[0] = 0.5 * ratio[0] + 0.5 * (rec['msgs_chars'] / rec['prompt'])
        conv.prompt, conv.out, conv.last_text = rec['prompt'], rec['out'], rec['text']
    return rec


def save_text(sid, r, rec):
    """--save-text: <corsa>/testi/<sessione>_<indice>.json con il testo generato; il prompt NON si salva (dati di sessioni reali)."""
    try:
        d = OUT / 'testi'
        d.mkdir(exist_ok=True)
        doc = dict(sessione=sid, indice=r['k'], token_generati=rec.get('out'), bersaglio=r['out'], motivo_fine=rec.get('finish'),
                   ok=bool(rec.get('ok')), testo=rec.get('text') or '')
        if rec.get('err'):
            doc['errore'] = rec['err']
        if rec.get('tool_calls'):
            doc['chiamate_strumenti'] = rec['tool_calls']
        (d / f'{sid}_{r["k"]}.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    except Exception as e:   # noqa: BLE001  - il salvataggio non deve fermare la corsa
        print(f'  save-text {sid}#{r["k"]} fallito: {e!r}', flush=True)


def log_size():
    try:
        return (OUT / 'engine.log').stat().st_size
    except OSError:
        return 0


def log_since(off):
    try:
        with (OUT / 'engine.log').open('rb') as f:
            f.seek(off)
            return f.read().decode('utf-8', 'replace').splitlines()
    except OSError:
        return []


RX = re.compile(r'strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+)(?: of (\d+))? read in (\d+) ms .*?, (\d+) generated in (\d+) ms')
res, convs = [], {}
allres = dict(tag=a.tag, exe=a.exe, extra=a.extra, env=a.env, window=[T0, T1], original=OS, args=None)
with Server() as srv:
    allres['args'] = srv.args
    mem = MemSampler()
    mem.start()
    # ---- riscaldamento: nell'ordine di servizio originale
    ws = sorted([(v['warm']['end'], sid, v['warm']) for sid, v in plan.items() if v['warm'] and not a.no_warm])
    for _, sid, w in ws:
        c = convs[sid] = Conv(sid)
        c.fresh(w['P'], w['out'])
        rec = {}
        t = time.monotonic()
        do_request(srv.model, c, rec, 1)
        print(f'warm {sid}: target {w["P"]} prompt {rec.get("prompt")} cached {rec.get("cached")} in {time.monotonic() - t:.0f} s {rec.get("err", "")}', flush=True)
        c.out = w['out']
        c.prompt = rec.get('prompt') or w['P']
        c.last_text = piece(sid, w['out'])      # la risposta "originale" del turno scaldato: sintetica della stessa lunghezza
        c.warm_target = w['P']
    off = log_size()
    smp = LoadSampler()
    smp.start()
    T_START = time.monotonic()
    done_evt = threading.Event()

    def agent(sid, v):
        conv = convs.get(sid) or Conv(sid)
        convs[sid] = conv
        prev = v['warm']
        first_arrival = max(0.0, v['reqs'][0]['send'] - T0) + v.get('stagger', 0.0)
        wait = T_START + first_arrival - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        for i, r in enumerate(v['reqs']):
            if i > 0:
                think = min(r['think'] if r['think'] is not None else 0.0, a.think_cap) * a.think_scale
                time.sleep(max(0.0, think))
            warm_ok = conv.msgs is not None
            if warm_ok and extends(prev, r):
                if prev is v['warm'] and i == 0:
                    ntok = r['P'] - prev['P'] - prev['out']
                else:
                    ntok = r['P'] - conv.prompt - conv.out
                conv.extend(ntok, r['out'])
            else:
                conv.fresh(r['P'], r['out'])
            rec = dict(sid=sid, k=r['k'], P_target=r['P'], out_target=r['out'], reused_orig=r['reused'], planned=(first_arrival if i == 0 else None))
            do_request(srv.model, conv, rec, max(1, r['out']))
            rec['t_send_rel'] = rec['t_send'] - T_START
            rec['t_first_rel'] = (rec.get('t_first') or rec['t_end']) - T_START
            rec['t_end_rel'] = rec['t_end'] - T_START
            res.append(rec)
            if a.save_text:
                save_text(sid, r, rec)
            if not rec.get('ok'):
                print(f'  {sid}#{r["k"]} ERRORE {rec.get("err")}', flush=True)
            else:
                print(f'  {sid}#{r["k"]}: send {rec["t_send_rel"]:6.0f} ttft {rec["t_first_rel"] - rec["t_send_rel"]:6.1f} end {rec["t_end_rel"]:6.0f} '
                      f'prompt {rec["prompt"]}/{r["P"]} cached {rec["cached"]} out {rec["out"]}/{r["out"]}', flush=True)
            prev = r

    th = [threading.Thread(target=agent, args=(sid, v), daemon=True) for sid, v in plan.items()]
    for x in th:
        x.start()
    while time.monotonic() - T_START < a.deadline and any(x.is_alive() for x in th):
        time.sleep(1)
    unfinished = [x for x in th if x.is_alive()]
    smp.halt.set()
    mem.halt.set()
    lines = log_since(off)

wall = max((r['t_end_rel'] for r in res if r.get('ok')), default=0)
ok = [r for r in res if r.get('ok')]
tt = [r['t_first_rel'] - r['t_send_rel'] for r in ok]
srv = [(int(m.group(5)), int(m.group(6)), int(m.group(7)), int(m.group(3)), int(m.group(2))) for ln in lines for m in [RX.search(ln)] if m]
qw = [max(0.0, (r['t_first_rel'] - r['t_send_rel']) - (r.get('prompt_ms') or 0) / 1000) for r in ok]
summ = dict(requests_planned=OS['requests'], requests_ok=len(ok), failed=len(res) - len(ok),
            unfinished_agents=len(unfinished), makespan=wall,
            ttft_p50=pct(tt, .5), ttft_p90=pct(tt, .9), ttft_max=max(tt) if tt else None, ttft_mean=sum(tt) / len(tt) if tt else None,
            queue_wait_mean=sum(qw) / len(qw) if qw else None, queue_wait_sum=sum(qw),
            prompt=sum(r['prompt'] or 0 for r in ok), reused=sum(r['cached'] or 0 for r in ok),
            new=sum((r['prompt'] or 0) - (r['cached'] or 0) for r in ok), out=sum(r['out'] for r in ok), out_target=sum(r['out_target'] for r in ok),
            server_read_s=sum(s[0] for s in srv) / 1000, server_gen_s=sum(s[2] for s in srv) / 1000, server_read_tok=sum(s[3] for s in srv),
            server_gen_tok=sum(s[1] for s in srv), server_log_requests=len(srv),
            cpu_other_mean=sum(smp.vals) / max(1, len(smp.vals)), cpu_other_p90=pct(smp.vals, .9), cpu_okto_mean=sum(smp.okto) / max(1, len(smp.okto)),
            mem_strata_wset_max_gib=max((r[1] for r in mem.rows), default=None), mem_strata_private_max_gib=max((r[2] for r in mem.rows), default=None),
            mem_avail_min_gib=min((r[3] for r in mem.rows), default=None), mem_swap_used_max_gib=max((r[4] for r in mem.rows), default=None),
            mem_total_gib=mem.rows[0][5] if mem.rows else None, agents=len(plan),
            cpu_other_top=[(k, round(v / max(1.0, wall), 1)) for k, v in smp.byname.most_common(5)])
summ['disturbed'] = bool(summ['cpu_other_mean'] > 30 or (summ['cpu_other_p90'] or 0) > 30)
summ['server_busy_frac'] = (summ['server_read_s'] + summ['server_gen_s']) / wall if wall else None
summ['reuse_frac'] = summ['reused'] / summ['prompt'] if summ['prompt'] else None
summ['orig_reuse_frac'] = OS['reused'] / OS['prompt']
allres['summary'] = summ
allres['res'] = [{k: v for k, v in r.items() if k not in ('text', 'tool_calls')} for r in res]      # niente testo: solo numeri
allres['engine_log'] = [ln[:300] for ln in lines if any(k in ln for k in ('strata batch', 'gave back', 'on a thread', 'pipelined', 'the prompt was read'))][:200]
(OUT / 'res.json').write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding='utf-8')
print('RIASSUNTO', json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in summ.items()}, ensure_ascii=False), flush=True)
print('ORIGINALE', json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in OS.items()}, ensure_ascii=False), flush=True)
print('fine', a.tag, flush=True)
