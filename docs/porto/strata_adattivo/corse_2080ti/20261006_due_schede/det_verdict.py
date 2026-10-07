"""Verdict of a deterministic A/B (forced ids + forced windows) by the rule written before the data.

    python det_verdict.py A1,A2,A3 B1,B2,B3     (A = reference arms, B = candidate arms, paired in order)

Per arm: L01/L02 decode seconds and t/s, the "strata work" windows (must be identical), CPU used by other processes.
Rule: B passes if it is faster in all 3 pairs on L01 AND on L02, and the mean paired gain on L01+L02 decode time
is > 2.7 %.
"""
import json, re, statistics as st, sys
from pathlib import Path

K = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep')


def arm(n):
    s = (K / n / 'engine.log').read_text(encoding='utf-8', errors='replace')
    gen = [int(x) / 1000 for x in re.findall(r'1024 generated in (\d+) ms', s)]
    work = re.findall(r'strata work: request \d \(forced\), (\d+) windows', s)
    cpu = None
    f = K / n / 'ambiente.json'
    if f.exists():
        a = [x['cpu_altri'] for x in json.loads(f.read_text()) if 'cpu_altri' in x]
        cpu = st.mean(a) if a else None
    return dict(name=n, l01=gen[0] if gen else None, l02=gen[1] if len(gen) > 1 else None, work=work, cpu=cpu)


A = [arm(n) for n in sys.argv[1].split(',')]
B = [arm(n) for n in sys.argv[2].split(',')]
for r in A + B:
    l01, l02 = r['l01'], r['l02']
    print(f"{r['name']:<16} L01 {l01:6.2f}s ({1024 / l01:5.1f} t/s)  L02 {l02:6.2f}s ({1024 / l02:5.1f} t/s)  "
          f"finestre {'/'.join(r['work'])}  cpu altri {r['cpu'] if r['cpu'] is None else round(r['cpu'], 2)}")
pairs = list(zip(A, B))
g01 = [(a['l01'] - b['l01']) / a['l01'] * 100 for a, b in pairs]
g02 = [(a['l02'] - b['l02']) / a['l02'] * 100 for a, b in pairs]
gt = [((a['l01'] + a['l02']) - (b['l01'] + b['l02'])) / (a['l01'] + a['l02']) * 100 for a, b in pairs]
same_work = len({tuple(r['work']) for r in A + B}) == 1
print('guadagno per coppia L01 %:', [round(x, 1) for x in g01])
print('guadagno per coppia L02 %:', [round(x, 1) for x in g02])
print('guadagno per coppia L01+L02 %:', [round(x, 1) for x in gt], ' media %.1f' % st.mean(gt))
ok = all(x > 0 for x in g01) and all(x > 0 for x in g02) and st.mean(gt) > 2.7
print('lavoro identico in tutte le corse:', same_work)
print('VERDETTO:', 'PASSA' if ok else 'NON PASSA')
