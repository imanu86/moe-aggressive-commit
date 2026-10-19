"""Legge gli engine.log delle corse NN-braccio e stampa per braccio: mediana prompt/decode per target, finestre, ms/finestra, draft."""
import re, sys, statistics as st
from pathlib import Path
here = Path(__file__).resolve().parent
rx_w = re.compile(r'strata work: request \d+, (\d+) windows')
rx_p = re.compile(r'strata serve: prompt (\d+) tokens = .*? read in (\d+) ms \(([\d.]+) tok/s\), (\d+) generated in (\d+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)')
runs = {}
for d in sorted(here.glob('*-*')):
    if not d.is_dir() or not (d / 'engine.log').exists():
        continue
    tag, arm = d.name.split('-', 1)
    rows, w = [], None
    for line in (d / 'engine.log').read_text(encoding='utf-8', errors='replace').splitlines():
        m = rx_w.search(line)
        if m: w = int(m.group(1))
        m = rx_p.search(line)
        if m and int(m.group(1)) > 1000:
            T, pm, pt, g, dm, dt, a, b = m.groups()
            rows.append(dict(T=int(T), p=float(pt), d=float(dt), dms=int(dm), w=w, a=int(a), b=int(b)))
    amb = (d / 'ambiente.txt').read_text(encoding='utf-8', errors='replace').splitlines() if (d / 'ambiente.txt').exists() else []
    runs[d.name] = (arm, rows, amb)
if len(sys.argv) > 1 and sys.argv[1] == 'runs':
    for n, (arm, rows, amb) in runs.items():
        s = ' '.join(f"{r['T']//1024}K:{r['p']:.0f}/{r['d']:.1f}" for r in rows)
        print(f'{n:8s} {s}   {amb[0][:0]}')
    sys.exit()
arms = {}
for n, (arm, rows, amb) in runs.items():
    arms.setdefault(arm, []).extend(rows)
Ts = sorted({r['T'] for rows in arms.values() for r in rows})
print('braccio  n | ' + ' | '.join(f'{T//1024}K prompt/decode (ms/finestra, accept%)' for T in Ts))
for arm, rows in arms.items():
    out = []
    for T in Ts:
        x = [r for r in rows if r['T'] == T]
        if not x:
            out.append('-'); continue
        mw = st.mean(r['dms'] / r['w'] for r in x if r['w'])
        acc = 100 * sum(r['a'] for r in x) / max(1, sum(r['b'] for r in x))
        out.append(f"{st.median(r['p'] for r in x):.0f}/{st.median(r['d'] for r in x):.1f} (n{len(x)}, {mw:.1f}, {acc:.0f}%)")
    print(f'{arm:6s} {len(rows):3d} | ' + ' | '.join(out))
