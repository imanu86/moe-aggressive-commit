"""Costruisce la traccia del lavoro reale (DSH, 3 agenti + orchestratore su Strata) SOLO con tempi e conteggi.

Fonti: le sessioni DSH (%APPDATA%\\dsh-desktop\\harness\\sessions\\*\\<id>\\session.v4.jsonl.zstd, zstd multi-frame) danno per ogni
richiesta LLM l'istante di invio (step/start), il primo blocco, la fine e l'uso (inputTokens, cacheReadTokens, outputTokens);
il log del Daily (strata_0143_daily.log) non ha timestamp per richiesta ma, con il server seriale, le sue righe
`strata serve: prompt N tokens = R reused + W read in X ms ..., G generated in Y ms` escono nell'ordine di servizio: si abbinano
alle richieste DSH per (prompt, generati) e danno la durata lato server (lettura, decode).  Nessun contenuto viene scritto.

    python -I build_trace.py --log D:\\ds4_work\\strata\\sota\\strata_0143_daily.log --out trace_dsh_20261016.json ^
        --label P=session-1c512c --label A=41c81312 --label B=7ad02764 --label C=67383909 ^
        --from-ms 1792122495000 --to-ms 1792137100000
"""
import argparse, collections, datetime, glob, json, os, re, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dshread import lines

ap = argparse.ArgumentParser()
ap.add_argument('--log', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--label', action='append', required=True, help='ETICHETTA=prefisso id sessione (la prima e l\'orchestratore)')
ap.add_argument('--from-ms', type=int, default=0, help='escludi richieste inviate prima (epoch ms)')
ap.add_argument('--to-ms', type=int, default=10**15)
a = ap.parse_args()
root = os.path.expandvars(r'%APPDATA%\dsh-desktop\harness\sessions')


def extract(prefix):
    p = [x for x in glob.glob(root + '/*/*/session.v4.jsonl.zstd') if prefix in x][0]
    ev = list(lines(p))[1:]
    steps = {}
    for r in ev:
        t, d = r['type'], r.get('data') or {}
        k = (d.get('turn'), d.get('step'))
        if t == 'step/start':
            steps.setdefault(k, {})['send'] = r['time']
        elif t == 'assistant/message':
            s = steps.setdefault(k, {})
            cs = [x for x in d['stream'] if x.get('type') == 'chunk']
            bs = [x['time'] for x in cs if x['chunk'].get('type') == 'block-start']
            fin = [x['time'] for x in cs if x['chunk'].get('type') == 'finish']
            u = d.get('usage') or {}
            s.update(first=bs[0] if bs else None, end=fin[-1] if fin else r['time'], inp=u.get('inputTokens'),
                     cache=u.get('cacheReadTokens') or 0, out=u.get('outputTokens'),
                     provider=(d['message'].get('source') or {}).get('provider'))
        elif t == 'tool/call':
            s = steps.setdefault(k, {})
            s['tools'] = s.get('tools', 0) + 1
        elif t == 'assistant/attempt':
            s = steps.setdefault(k, {})
            s['attempts'] = s.get('attempts', 0) + 1
    return [s for s in steps.values() if s.get('inp') is not None and s.get('send')]


# --- log del Daily: segmento del motore che contiene la finestra
txt = open(a.log, encoding='utf-8', errors='replace').read().splitlines()
starts = [(i, datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S').timestamp() * 1000)
          for i, l in enumerate(txt) for m in [re.match(r'\[strata\] (\S+ \S+) engine started', l)] if m]
reqs = {lab: extract(pre) for lab, pre in (x.split('=', 1) for x in a.label)}
allt = [r['send'] for rs in reqs.values() for r in rs if a.from_ms <= r['send'] <= a.to_ms]
t_min = min(allt)
seg = [s for s in starts if s[1] <= t_min][-1]
nxt = [s for s in starts if s[0] > seg[0]]
lo, hi = seg[0], (nxt[0][0] if nxt else len(txt))
rx = re.compile(r'strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+)(?: of (\d+))? read in (\d+) ms .*?, (\d+) generated in (\d+) ms')
E = []
for i in range(lo, hi):
    m = rx.search(txt[i])
    if m:
        p, r, rd, of, rms, g, gms = (int(x) if x else None for x in m.groups())
        E.append(dict(line=i + 1, prompt=p, reused=r, read=rd, read_ms=rms, gen=g, gen_ms=gms, cancelled='(cancelled)' in txt[i]))
byp = collections.defaultdict(list)
for i, e in enumerate(E):
    byp[(e['prompt'], e['gen'])].append(i)
used, T = set(), []
for lab, rs in reqs.items():
    for r in rs:
        if not (a.from_ms <= r['send'] <= a.to_ms):
            continue
        r['sid'] = lab
        T.append(r)
T.sort(key=lambda r: r['end'])
for r in T:
    for j in byp.get((r['inp'] + r['cache'], r['out']), []):
        if j not in used:
            r['eng'] = j
            used.add(j)
            break
miss = [r for r in T if 'eng' not in r]
t0 = min(r['send'] for r in T)
out = []
last = {}
for r in sorted(T, key=lambda r: r['send']):
    if 'eng' not in r:
        continue
    e = E[r['eng']]
    prev = last.get(r['sid'])
    out.append(dict(sid=r['sid'], k=sum(1 for o in out if o['sid'] == r['sid']), send=round((r['send'] - t0) / 1000, 2),
                    first=round((r['first'] - t0) / 1000, 2) if r.get('first') else None, end=round((r['end'] - t0) / 1000, 2),
                    P=r['inp'] + r['cache'], reused=r['cache'], new=r['inp'], out=r['out'], tools=r.get('tools', 0),
                    think=round((r['send'] - prev['end']) / 1000, 2) if prev else None, timeouts=r.get('attempts', 0),
                    srv_read_ms=e['read_ms'], srv_gen_ms=e['gen_ms'], eng=r['eng'], provider=r.get('provider')))
    last[r['sid']] = r
meta = dict(t0_epoch_ms=t0, log_segment_start_line=lo + 1, engine_entries=len(E), requests=len(out), unmatched=len(miss),
            labels=dict(x.split('=', 1) for x in a.label))
json.dump(dict(meta=meta, req=out), open(a.out, 'w'), indent=1)

# --- riassunto (solo conteggi e tempi)
wall = max(o['end'] for o in out)
rd = sum(o['srv_read_ms'] for o in out) / 1000
gn = sum(o['srv_gen_ms'] for o in out) / 1000
bys = collections.defaultdict(list)
for o in out:
    bys[o['sid']].append(o)
print(f'richieste {len(out)} (non abbinate {len(miss)}), lavoro {wall:.0f} s = {wall / 3600:.2f} h')
for s, rs in bys.items():
    print(f'  {s}: {len(rs)} richieste, prompt {sum(r["P"] for r in rs)}, riusati {sum(r["reused"] for r in rs)}, nuovi {sum(r["new"] for r in rs)}, '
          f'generati {sum(r["out"] for r in rs)}')
print(f'server: lettura {rd:.0f} s, decode {gn:.0f} s, occupato {(rd + gn) / wall:.1%} del lavoro; lettura = {rd / (rd + gn):.1%} del tempo servito')
order = sorted(out, key=lambda o: o['eng'])
sw = sum(1 for x, y in zip(order, order[1:]) if x['sid'] != y['sid'])
print(f'passaggi di sessione consecutivi nel server: {sw} su {len(order) - 1}')
ttft = [o['first'] - o['send'] for o in out if o['first'] is not None]
qw = [max(0.0, o['first'] - o['send'] - o['srv_read_ms'] / 1000) for o in out if o['first'] is not None]
pc = lambda v, q: sorted(v)[min(len(v) - 1, int(q * len(v)))]
print(f'TTFT p50/p90/max {pc(ttft, .5):.0f}/{pc(ttft, .9):.0f}/{max(ttft):.0f} s; attesa in coda (TTFT - lettura) media {st.mean(qw):.0f} s, somma {sum(qw):.0f} s')
ev = sorted([(o['send'], 1) for o in out] + [(o['end'], -1) for o in out])
cur, last_t, tm = 0, ev[0][0], collections.Counter()
for t, dv in ev:
    tm[cur] += t - last_t
    last_t = t
    cur += dv
tot = sum(tm.values())
print('richieste in volo (invio -> fine), % del tempo:', {k: round(100 * v / tot, 1) for k, v in sorted(tm.items())})
