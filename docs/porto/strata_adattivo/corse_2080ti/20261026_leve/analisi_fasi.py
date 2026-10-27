"""Analisi per fasi del replay a 3 agenti (27/10/2026): solo log e res.json esistenti, nessuna GPU, nessun strata.exe.

Per ogni corsa ricostruisce la linea del tempo dai tempi lato client di res.json (invio, primo contenuto, fine) e dal tempo di lettura
dichiarato dal server (prompt_ms = riga «strata serve: prompt ... read in X ms»):
    in coda   [invio, primo - lettura]      legge   [primo - lettura, primo]      scrive   [primo, fine]
Il log del motore NON ha un orario per riga (solo quello di avvio): l'ordine e le durate delle righe servono a controllare la ricostruzione
(le letture del server sono seriali: la lettura di una richiesta comincia dove finisce la precedente piu' ~0,5-0,9 s di ammissione).
Fasi: (a) legge >=1 e nessuno scrive; (b) scrivono >=2 e nessuno legge (b1: scrive uno solo); (c) legge >=1 e scrive >=1; (i) nessuno dei due.
Velocita' per fase: (T) token distribuiti in modo uniforme sull'intervallo di ogni richiesta (approssimata: pesa uguale in tutte le fasi);
(N) minimi quadrati non negativi sui token di ogni richiesta (una velocita' per classe), cosi' una fase lenta o ferma si vede;
(E) misure dirette del motore: righe «batch: read N tokens on a thread of its own ... decoded R rows meanwhile» (solo con PIPED_CONCURRENT),
«batch (pipelined ...): S group-steps, R rows in T ms», «the prompt was read in N parts, the slots decoding X ms between them» (gruppo seriale).

    python analisi_fasi.py > fasi_generato.md
"""
import itertools, json, re, statistics as st, sys
from pathlib import Path
import numpy as np

H = Path(__file__).resolve().parent
CORSE = H / 'corse'
OLD = H.parent / '20261019_replay'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else float('nan')


def carica(d):
    j = json.loads((d / 'res.json').read_text(encoding='utf-8'))
    out = []
    for r in j['res']:
        if not r.get('ok'):
            continue
        rd = (r.get('prompt_ms') or 0) / 1000
        f = r['t_first_rel']
        s = r['t_send_rel']
        out.append(dict(sid=r['sid'], k=r['k'], s=s, f=f, e=r['t_end_rel'], rd=min(rd, f - s), new=r['prompt'] - (r.get('cached') or 0),
                        out=r['out'], prompt=r['prompt']))
    return j, out


def carica_originale():
    t = json.loads((OLD / 'trace_dsh_20261016.json').read_text(encoding='utf-8'))['req']
    T0 = 3600.0
    out = []
    for r in t:
        if r['sid'] in 'ABC' and r['end'] > T0 and r['send'] < T0 + 1200:
            s = max(0.0, r['send'] - T0)
            f = r['first'] - T0
            rd = r['srv_read_ms'] / 1000
            out.append(dict(sid=r['sid'], k=r['k'], s=s, f=f, e=r['end'] - T0, rd=min(rd, f - s), new=r['new'], out=r['out'], prompt=r['P']))
    return out


def intervalli(q):
    a = max(q['s'], q['f'] - q['rd'])
    return (q['s'], a), (a, q['f']), (q['f'], q['e'])


def dentro(iv, t):
    return iv[0] <= t < iv[1]


def sweep(rs):
    T = max(q['e'] for q in rs)
    pts = sorted({0.0, T} | {x for q in rs for iv in intervalli(q) for x in iv})
    seg = []
    for a, b in zip(pts, pts[1:]):
        if b - a < 1e-9:
            continue
        m = (a + b) / 2
        nq = nr = nd = 0
        for q in rs:
            iq, ir, idd = intervalli(q)
            nq += dentro(iq, m)
            nr += dentro(ir, m)
            nd += dentro(idd, m)
        seg.append((a, b, nq, nr, nd))
    return T, seg


def classe(nr, nd):
    if nr >= 1 and nd == 0:
        return 'a'
    if nr == 0 and nd >= 2:
        return 'b2'
    if nr == 0 and nd == 1:
        return 'b1'
    if nr >= 1 and nd >= 1:
        return 'c'
    return 'i'


def nnls_piccolo(A, y):
    """minimi quadrati non negativi con pochissime incognite (prova tutti i sottoinsiemi); pesi relativi"""
    A = np.array(A, float)
    y = np.array(y, float)
    w = 1 / np.maximum(y, 1)
    A, y = A * w[:, None], y * w
    best = None
    n = A.shape[1]
    for k in range(1, n + 1):
        for sub in itertools.combinations(range(n), k):
            x, *_ = np.linalg.lstsq(A[:, sub], y, rcond=None)
            if (x < 0).any():
                continue
            full = np.zeros(n)
            full[list(sub)] = x
            res = float(np.sqrt(np.mean((A @ full - y) ** 2)))
            if best is None or res < best[1] - 1e-12:
                best = (full, res)
    return best


def nnls_w(A, y):
    """colonne con meno di 2 s di tempo totale sono troppo poco sostenute: velocita' non stimata (resta 0)"""
    if not A:
        return None
    M = np.array(A)
    ok = [i for i in range(M.shape[1]) if M[:, i].sum() >= 2.0]
    if not ok:
        return None
    x, res = nnls_piccolo(M[:, ok].tolist(), y)
    full = np.zeros(M.shape[1])
    full[ok] = x
    return full, res


def analizza(rs):
    T, seg = sweep(rs)
    R = dict(T=T, n=len(rs), new=sum(q['new'] for q in rs), out=sum(q['out'] for q in rs))
    ttft = [q['f'] - q['s'] for q in rs]
    R['ttft_mean'] = st.mean(ttft)
    R['ttft_p90'] = pct(ttft, .9)
    R['qwait_mean'] = st.mean(max(0, q['f'] - q['s'] - q['rd']) for q in rs)
    tot = dict(inflight=0, served=0, dec=0, read=0, queue=0)
    nrmax = 0
    t_nr2 = 0
    for a, b, nq, nr, nd in seg:
        dt = b - a
        tot['inflight'] += (nq + nr + nd) * dt
        tot['served'] += (nr + nd) * dt
        tot['dec'] += nd * dt
        tot['read'] += nr * dt
        tot['queue'] += nq * dt
        nrmax = max(nrmax, nr)
        t_nr2 += dt if nr >= 2 else 0
    lg = [x for x in seg if x[1] - x[0] >= 0.3] or seg      # massimi solo su tratti di almeno 0,3 s (niente sbavature di ammissione)
    R['max_inflight'] = max(nq + nr + nd for _, _, nq, nr, nd in lg)
    R['max_served'] = max(nr + nd for _, _, _, nr, nd in lg)
    R['max_dec'] = max(nd for *_, nd in lg)
    R['max_read'] = nrmax
    R['t_read2'] = t_nr2
    for k, v in tot.items():
        R['mean_' + k] = v / T
    # fasi (metodo T)
    F = {c: dict(t=0.0, rt=0.0, gt=0.0, nd=0.0, nr=0.0, nq=0.0) for c in ('a', 'b1', 'b2', 'c', 'i')}
    for a, b, nq, nr, nd in seg:
        dt = b - a
        m = (a + b) / 2
        c = F[classe(nr, nd)]
        c['t'] += dt
        c['nd'] += nd * dt
        c['nr'] += nr * dt
        c['nq'] += nq * dt
        for q in rs:
            iq, ir, idd = intervalli(q)
            if dentro(ir, m) and ir[1] > ir[0]:
                c['rt'] += q['new'] / (ir[1] - ir[0]) * dt
            if dentro(idd, m) and idd[1] > idd[0]:
                c['gt'] += q['out'] / (idd[1] - idd[0]) * dt
    R['fasi'] = F
    # metodo N: scrittura (per agente) in classi S (1 scrive, nessuno legge), M (>=2 scrivono, nessuno legge), X (qualcuno legge)
    A, y = [], []
    Ar, yr = [], []
    for q in rs:
        _, ir, idd = intervalli(q)
        row = [0.0, 0.0, 0.0]
        rowr = [0.0, 0.0]
        for a, b, nq, nr, nd in seg:
            ov = max(0.0, min(b, idd[1]) - max(a, idd[0]))
            if ov > 0:
                row[2 if nr >= 1 else (1 if nd >= 2 else 0)] += ov
            ovr = max(0.0, min(b, ir[1]) - max(a, ir[0]))
            if ovr > 0:
                rowr[1 if nd >= 1 else 0] += ovr
        if q['e'] > q['f'] and q['out'] > 0:
            A.append(row)
            y.append(q['out'])
        if ir[1] > ir[0] and q['new'] > 50:
            Ar.append(rowr)
            yr.append(q['new'])
    R['_A'], R['_y'] = A, y
    R['nnls_w'] = nnls_w(A, y)
    R['nnls_r'] = nnls_piccolo(Ar, yr) if Ar else None

    def mean_nd(c):
        return F[c]['nd'] / F[c]['t'] if F[c]['t'] > 0 else 0.0
    R['ra'] = F['a']['rt'] / F['a']['t'] if F['a']['t'] >= 1 else None
    R['rc'] = F['c']['rt'] / F['c']['t'] if F['c']['t'] >= 1 else None
    x = R['nnls_w'][0] if R['nnls_w'] else None
    R['wb_agent'] = x[1] if x is not None and F['b2']['t'] >= 1 and x[1] > 0 else None
    R['wb_agg'] = x[1] * mean_nd('b2') if R['wb_agent'] is not None else None
    R['wb1'] = x[0] if x is not None and F['b1']['t'] >= 1 and x[0] > 0 else None
    R['wc_agent'] = x[2] if x is not None and F['c']['t'] >= 1 else None
    R['wc_agg'] = x[2] * mean_nd('c') if R['wc_agent'] is not None else None
    R['mnd'] = {c: mean_nd(c) for c in F}
    R['wbT'] = F['b2']['gt'] / F['b2']['t'] if F['b2']['t'] >= 1 else None
    R['wcT'] = F['c']['gt'] / F['c']['t'] if F['c']['t'] >= 1 else None
    R['tq'] = {c: F[c]['t'] for c in F}
    # sovrapposizione di ogni lettura con chi scrive (frazione di tempo con nd>=1)
    for q in rs:
        _, ir, _ = intervalli(q)
        L = ir[1] - ir[0]
        ov = sum(max(0.0, min(b, ir[1]) - max(a, ir[0])) for a, b, nq, nr, nd in seg if nd >= 1)
        q['ov_dec'] = ov / L if L > 0 else 0.0
    return R


def lettura_diretta(rs):
    """prefill misurato dal server per richiesta (new / prompt_ms), separato per quanto la lettura si sovrappone a chi scrive"""
    g = dict(puro=[0, 0.0], misto=[0, 0.0], parziale=[0, 0.0])
    for q in rs:
        if q['new'] < 50 or q['rd'] <= 0:
            continue
        k = 'puro' if q['ov_dec'] < 0.05 else ('misto' if q['ov_dec'] >= 0.5 else 'parziale')
        g[k][0] += q['new']
        g[k][1] += q['rd']
    return {k: (v[0], v[1], v[0] / v[1] if v[1] else float('nan')) for k, v in g.items()}


RE_THREAD = re.compile(r'batch: read (\d+) tokens on a thread of its own in (\d+) ms \(concurrent, to (\d+) of (\d+)\); the slots decoded (\d+) rows')
RE_PIPE = re.compile(r'batch \(pipelined, (\d+) groups of (\d+)\): (\d+) group-steps, (\d+) rows in (\d+) ms = ([\d.]+) rows/s')
RE_PARTS = re.compile(r'the prompt was read in (\d+) parts, the slots decoding (\d+) ms between them')
RE_WIN = re.compile(r'strata batch: (\d+) windows, avg ([\d.]+) rows, ([\d.]+) ms/window')
RE_SERVE = re.compile(r'serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\), (\d+) generated in (\d+) ms')


def log_motore(d, rs):
    L = (d / 'engine.log').read_text(encoding='utf-8', errors='replace').splitlines()
    ini = [i for i, ln in enumerate(L) if 'engine started:' in ln]
    if len(ini) > 1:      # 02_R3L: primo tentativo fallito, rilanciato nello stesso file di log
        L = L[ini[-1]:]
    prompts = {q['prompt'] for q in rs}
    th, pipe, parts, win, serve = [], [], [], [], []
    for ln in L:
        m = RE_THREAD.search(ln)
        if m:
            n, ms, to, of, rows = map(int, m.groups())
            th.append(dict(n=n, ms=ms, of=of, rows=rows, replay=of in prompts))
        m = RE_PIPE.search(ln)
        if m:
            pipe.append(tuple(float(x) for x in m.groups()))
        m = RE_PARTS.search(ln)
        if m:
            parts.append((int(m.group(1)), int(m.group(2))))
        m = RE_WIN.search(ln)
        if m:
            win.append(tuple(float(x) for x in m.groups()))
        m = RE_SERVE.search(ln)
        if m:
            serve.append(tuple(int(x) if '.' not in x else float(x) for x in m.groups()))
    return dict(th=th, pipe=pipe, parts=parts, win=win, serve=serve)


def tag_arm(name):
    return name.split('_', 1)[1] if '_' in name[:3] else name


def fmt(x, n=1):
    return 'n.d.' if x is None or (isinstance(x, float) and x != x) else f'{x:.{n}f}'


def riga_fasi(R):
    F = R['fasi']
    out = []
    for c, nome in (('a', '(a) solo letture'), ('b2', '(b) >=2 scrivono'), ('b1', '(b1) 1 scrive'), ('c', '(c) mista'), ('i', '(i) ferma')):
        f = F[c]
        t = f['t']
        if t < 1:
            out.append(f'| {nome} | {t:.1f} | {100 * t / R["T"]:.0f}% | - | - | - | - |')
            continue
        rd = f['rt'] / t
        wr = f['gt'] / t
        ndm = f['nd'] / t
        nrm = f['nr'] / t
        out.append(f'| {nome} | {t:.0f} | {100 * t / R["T"]:.0f}% | {fmt(nrm, 2)} | {fmt(ndm, 2)} | {fmt(rd, 0) if f["rt"] > 0 else "-"} | '
                   f'{fmt(wr, 1) if f["gt"] > 0 else "-"} ({fmt(wr / ndm, 1) if ndm > 0 and f["gt"] > 0 else "-"}/agente) |')
    return '\n'.join(out)


BUCK = [('<3K', 0, 3000), ('3-8K', 3000, 8000), ('8-16K', 8000, 16000), ('>50K', 50000, 10 ** 9)]


def per_taglia(rs):
    out = []
    for nome, lo, hi in BUCK:
        for lab, cond in (('senza scrittori', lambda q: q['ov_dec'] < 0.05), ('con scrittori', lambda q: q['ov_dec'] >= 0.5)):
            g = [q for q in rs if lo <= q['new'] < hi and q['rd'] > 0 and cond(q)]
            if g:
                out.append(f'{nome} {lab} ({len(g)}): {sum(q["new"] for q in g) / sum(q["rd"] for q in g):.0f} tok/s')
    return '; '.join(out)


def stampa_run(nome, d_or_none, rs, j=None, d=None):
    R = analizza(rs)
    ld = lettura_diretta(rs)
    print(f'\n#### {nome}\n')
    print(f'makespan {R["T"]:.1f} s; {R["n"]} richieste; token nuovi letti {R["new"]:,}; token generati {R["out"]:,}; '
          f'TTFT medio {R["ttft_mean"]:.1f} s, p90 {R["ttft_p90"]:.1f} s; attesa in coda media {R["qwait_mean"]:.1f} s.'.replace(',', '.'))
    print(f'Agenti: in volo (coda+lettura+scrittura) medio {R["mean_inflight"]:.2f}, max {R["max_inflight"]}; serviti (legge o scrive) medio {R["mean_served"]:.2f}, '
          f'max {R["max_served"]}; in coda medio {R["mean_queue"]:.2f}; che scrivono medio {R["mean_dec"]:.2f}, max {R["max_dec"]}; '
          f'che leggono medio {R["mean_read"]:.2f}, max {R["max_read"]} (tempo con 2+ letture insieme: {R["t_read2"]:.1f} s).\n')
    print('| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |\n|---|---:|---:|---:|---:|---:|---:|')
    print(riga_fasi(R))
    nw, nr_ = R['nnls_w'], R['nnls_r']
    if nw:
        x, res = nw
        print(f'\nMetodo N, scrittura per agente: 1 solo scrive {x[0]:.1f} t/s; 2+ scrivono senza letture {x[1]:.1f} t/s; mentre qualcuno legge {x[2]:.1f} t/s (scarto relativo {res:.2f}).')
    print('Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: ' +
          '; '.join(f'{k} {v[0]:,} tok in {v[1]:.0f} s = {v[2]:.0f} tok/s'.replace(',', '.') for k, v in ld.items() if v[1] > 0))
    print('Lettura per taglia (token nuovi / tempo di lettura del server): ' + per_taglia(rs))
    if d is not None:
        E = log_motore(d, rs)
        th = [t for t in E['th'] if t['replay']]
        if th:
            pur = [t for t in th if t['rows'] == 0]
            mis = [t for t in th if t['rows'] > 0]
            byp = {q['prompt']: q for q in rs}
            tdec = sum(t['ms'] / 1000 * byp[t['of']]['ov_dec'] for t in mis if t['of'] in byp)
            print(f'Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: {sum(t["rows"] for t in mis)} righe in {tdec:.1f} s = '
                  f'{sum(t["rows"] for t in mis) / max(1e-9, tdec):.1f} righe/s (tempo dalla ricostruzione).')
            print(f'Motore, letture «su un thread proprio» ({len(th)}): senza righe nel frattempo {sum(t["n"] for t in pur)} tok in {sum(t["ms"] for t in pur) / 1000:.1f} s = '
                  f'{(sum(t["n"] for t in pur) / max(1e-9, sum(t["ms"] for t in pur) / 1000)):.0f} tok/s; con righe nel frattempo {sum(t["n"] for t in mis)} tok in '
                  f'{sum(t["ms"] for t in mis) / 1000:.1f} s = {(sum(t["n"] for t in mis) / max(1e-9, sum(t["ms"] for t in mis) / 1000)):.0f} tok/s, '
                  f'{sum(t["rows"] for t in mis)} righe = {sum(t["rows"] for t in mis) / max(1e-9, sum(t["ms"] for t in mis) / 1000):.1f} righe/s sul tempo intero delle letture.')
        if E['pipe']:
            print('Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): ' +
                  '; '.join(f'{int(p[0])}x{int(p[1])} {int(p[2])} passi {int(p[3])} righe {p[4] / 1000:.1f} s {p[5]:.1f}/s' for p in E['pipe']))
        if E['win']:
            wr = sum(w[0] * w[1] for w in E['win'])
            wt = sum(w[0] * w[2] for w in E['win']) / 1000
            print(f'Motore, gruppo seriale: finestre di sola scrittura {wr:.0f} righe in {wt:.1f} s = {wr / wt:.1f} righe/s, {wr / sum(w[0] for w in E["win"]):.2f} righe per finestra.')
        if E['parts']:
            print(f'Motore, gruppo seriale: {len(E["parts"])} letture spezzate, scrittori fermi tra le parti {sum(p[1] for p in E["parts"]) / 1000:.1f} s in tutto; '
                  f'finestre: ' + '; '.join(f'{int(w[0])} finestre, {w[1]:.2f} righe medie, {w[2]:.1f} ms = {w[1] / w[2] * 1000:.1f} righe/s' for w in E['win']))
    return R


def main():
    runs = sorted(p for p in CORSE.iterdir() if p.name.startswith('replay_'))
    rid = {}
    print('# Dati generati da analisi_fasi.py (non editare a mano)\n')
    tabella = []
    for p in runs:
        j, rs = carica(p)
        nome = p.name.replace('replay_', '')
        R = stampa_run(nome, p, rs, j, p)
        rid[nome] = (R, rs, j, p)
    print('\n#### ORIGINALE (sessione vera, tratto 3600-4800 s, solo A,B,C)\n')
    ro = carica_originale()
    Ro = stampa_run('ORIGINALE', None, ro)
    rid['ORIGINALE'] = (Ro, ro, None, None)
    for nm in ('c1-daily', 'c1b-daily', 'c2-g2cc', 'c2b-g2cc', 'q1-b4-8ag'):
        j, rs = carica(OLD / f'replay_{nm}')
        R = stampa_run('19/10 ' + nm, None, rs, j, OLD / f'replay_{nm}')
        rid['19/10 ' + nm] = (R, rs, j, OLD / f'replay_{nm}')
    rid['R0 (4 corse: 05,07,09,11)'] = (pool(rid, ['05_R0', '07_R0', '09_R0', '11_R0']), None, None, None)
    rid['R3L (6 corse: 02,04,18,20,22,24)'] = (pool(rid, ['02_R3L', '04_R3L', '18_R3L', '20_R3L', '22_R3L', '24_R3L']), None, None, None)
    riepilogo(rid)
    tabelle_fasi(rid)
    tabella_grande(rid)
    stima_seriale(rid)


def stima_seriale(rid):
    """S (stima, NON misura): server seriale (FIFO) con la stessa cache grande delle corse batch. Piano e pensiero (invio - fine precedente della
    stessa sessione) presi dalla corsa 06_R3; servizio = a + new/b (retta adattata sulle 4 corse R0) + out / (velocita' di scrittura singola R0)."""
    X, Y, O, Tm = [], [], 0, 0.0
    for n in ('05_R0', '07_R0', '09_R0', '11_R0'):
        for q in rid[n][1]:
            X.append(q['new'])
            Y.append(q['rd'])
            O += q['out']
            Tm += q['e'] - q['f']
    b, a = np.polyfit(X, Y, 1)
    wr = O / Tm
    print()
    print('## Stima S: server seriale con la cache grande (nessuna corsa lo ha misurato)')
    print()
    print(f'Lettura singola adattata sulle 4 corse R0: tempo = {a:.2f} s + token/{1 / b:.0f} tok/s; scrittura singola R0 {wr:.1f} t/s. '
          f'Piano e pensiero della corsa 06_R3; stesso numero di token nuovi di 06_R3 (cache come R3).')
    print()
    for ref in ('06_R3', '08_R2', '02_R3L', '24_R3L'):
        rs = sorted(rid[ref][1], key=lambda q: q['s'])
        by = {}
        for q in rs:
            by.setdefault(q['sid'], []).append(q)
        nxt = {}
        for sid, v in by.items():
            v.sort(key=lambda q: q['k'])
            for i, q in enumerate(v):
                q['think'] = max(0.0, q['s'] - v[i - 1]['e']) if i else 0.0
        ready = {sid: (0.0, 0) for sid in by}
        t_srv, tt, end = 0.0, [], 0.0
        while any(i < len(by[s_]) for s_, (_, i) in ready.items()):
            cand = [(rt, sid) for sid, (rt, i) in ready.items() if i < len(by[sid])]
            rt, sid = min(cand)
            i = ready[sid][1]
            q = by[sid][i]
            start = max(t_srv, rt)
            rd = a + b * q['new']
            first = start + rd
            fin = first + q['out'] / wr
            tt.append(first - rt)
            t_srv = fin
            end = fin
            ready[sid] = (fin + (by[sid][i + 1]['think'] if i + 1 < len(by[sid]) else 0), i + 1)
        print(f'- piano di {ref}: tempo per finire {end:.0f} s (misurato in quella corsa: {rid[ref][0]["T"]:.0f} s); TTFT medio {st.mean(tt):.1f} s, p90 {pct(tt, .9):.1f} s '
              f'(misurati: {rid[ref][0]["ttft_mean"]:.1f} / {rid[ref][0]["ttft_p90"]:.1f}).')


def tabelle_fasi(rid):
    print()
    print('## Tabella per fasi (T = token uniformi nell intervallo; N = minimi quadrati; tempi in s, medie di corsa)')
    print()
    print('| braccio | (a) s | (a) lettura tok/s | (b) s | (b) scrittori | (b) agg. T / N | (b) per agente T | (b1) s | (b1) t/s | (c) s | (c) scrittori | (c) lettura tok/s | (c) scrittura agg. T / N | (c) per agente T | (i) s |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for nome in ('R0 (4 corse: 05,07,09,11)', '10_R1', '08_R2', '06_R3', 'R3L (6 corse: 02,04,18,20,22,24)', '03_L1', '19_L2', '21_L3', '23_L4', 'ORIGINALE'):
        R = rid[nome][0]
        F = R['F'] if 'F' in R else R['fasi']
        def g(c, k):
            return F[c][k]
        def r_(c):
            return g(c, 'rt') / g(c, 't') if g(c, 't') >= 1 else None
        def w_(c):
            return g(c, 'gt') / g(c, 't') if g(c, 't') >= 1 else None
        def nd_(c):
            return g(c, 'nd') / g(c, 't') if g(c, 't') >= 1 else None
        wbT, wcT = w_('b2'), w_('c')
        pa = lambda c: f'{g(c, "t"):.0f}'
        print(f'| {nome} | {pa("a")} | {fmt(r_("a"), 0)} | {pa("b2")} | {fmt(nd_("b2"), 2)} | {fmt(wbT, 0)} / {fmt(R.get("wb_agg"), 0)} | '
              f'{fmt(wbT / nd_("b2") if wbT else None, 1)} | {pa("b1")} | {fmt(w_("b1"), 0)} | {pa("c")} | {fmt(nd_("c"), 2)} | {fmt(r_("c"), 0)} | '
              f'{fmt(wcT, 0)} / {fmt(R.get("wc_agg"), 0)} | {fmt(wcT / nd_("c") if wcT else None, 1)} | {pa("i")} |')


def tabella_grande(rid):
    print()
    print('## La stessa lettura grande (C#22: 77.619 token nuovi) in ogni corsa')
    print()
    print('| corsa | lettura s | tok/s | quota di tempo con qualcuno che scrive |')
    print('|---|---:|---:|---:|')
    for k, v in rid.items():
        if v[1] is None or k.startswith('19/10') or k == 'ORIGINALE':
            continue
        for q in v[1]:
            if q['sid'] == 'C' and q['k'] == 22:
                print(f'| {k} | {q["rd"]:.1f} | {q["new"] / q["rd"]:.0f} | {100 * q["ov_dec"]:.0f}% |')


def pool(rid, names):
    Rs = [rid[n][0] for n in names]
    P = dict(T=st.mean(r['T'] for r in Rs), ttft_mean=st.mean(r['ttft_mean'] for r in Rs), ttft_p90=st.mean(r['ttft_p90'] for r in Rs))
    for k in ('mean_inflight', 'mean_served', 'mean_dec', 'new', 'out'):
        P[k] = st.mean(r[k] for r in Rs)
    for k in ('max_inflight', 'max_served', 'max_dec'):
        P[k] = max(r[k] for r in Rs)
    F = {c: {k: sum(r['fasi'][c][k] for r in Rs) for k in ('t', 'rt', 'gt', 'nd')} for c in ('a', 'b1', 'b2', 'c', 'i')}
    P['tq'] = {c: F[c]['t'] / len(Rs) for c in F}
    P['ra'] = F['a']['rt'] / F['a']['t'] if F['a']['t'] >= 1 else None
    P['rc'] = F['c']['rt'] / F['c']['t'] if F['c']['t'] >= 1 else None
    nw = nnls_w([a for r in Rs for a in r['_A']], [v for r in Rs for v in r['_y']])
    x = nw[0] if nw else None
    nd = {c: F[c]['nd'] / F[c]['t'] if F[c]['t'] > 0 else 0 for c in F}
    P['wb_agent'] = x[1] if x is not None and F['b2']['t'] >= 1 and x[1] > 0 else None
    P['wb_agg'] = x[1] * nd['b2'] if P['wb_agent'] is not None else None
    P['wb1'] = x[0] if x is not None and F['b1']['t'] >= 1 and x[0] > 0 else None
    P['wc_agent'] = x[2] if x is not None and F['c']['t'] >= 1 else None
    P['wc_agg'] = x[2] * nd['c'] if P['wc_agent'] is not None else None
    P['mnd'] = nd
    P['F'] = {c: {k: v / len(Rs) for k, v in F[c].items()} for c in F}
    P['wbT'] = F['b2']['gt'] / F['b2']['t'] if F['b2']['t'] >= 1 else None
    P['wcT'] = F['c']['gt'] / F['c']['t'] if F['c']['t'] >= 1 else None
    P['nnls_res'] = nw[1] if nw else None
    return P


def riepilogo(rid):
    print('\n## Riepilogo (una riga per corsa)\n')
    print('| corsa | makespan s | TTFT medio / p90 s | in volo medio (max) | serviti medi (max) | scrivono medi (max) | token nuovi letti | token generati | '
          '(a) lettura tok/s | (b) scrittura agg. t/s: T / N (N per agente) | (c) lettura tok/s | (c) scrittura agg. t/s: T / N (N per agente) | quota a / b / c / ferma |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for k, (R, rs, j, p) in rid.items():
        q = R['tq']
        tt = R['T']
        wb = f'{fmt(R["wbT"], 0)} / {R["wb_agg"]:.0f} ({R["wb_agent"]:.1f})' if R['wb_agg'] is not None else (f'{fmt(R["wbT"], 0)} / -' if R.get('wbT') else '-')
        wc = f'{fmt(R["wcT"], 0)} / {R["wc_agg"]:.0f} ({R["wc_agent"]:.1f})' if R['wc_agg'] is not None else '-'
        print(f'| {k} | {R["T"]:.0f} | {R["ttft_mean"]:.1f} / {R["ttft_p90"]:.1f} | {R["mean_inflight"]:.2f} ({R["max_inflight"]}) | '
              f'{R["mean_served"]:.2f} ({R["max_served"]}) | {R["mean_dec"]:.2f} ({R["max_dec"]}) | {R["new"]:,.0f} | {R["out"]:,.0f} | '
              f'{fmt(R["ra"], 0)} | {wb} | {fmt(R["rc"], 0)} | {wc} | '
              f'{100 * q["a"] / tt:.0f} / {100 * (q["b1"] + q["b2"]) / tt:.0f} / {100 * q["c"] / tt:.0f} / {100 * q["i"] / tt:.0f} |'.replace(',', '.'))


if __name__ == '__main__':
    main()
