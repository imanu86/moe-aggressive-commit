"""Confronto dei bracci di mc45b_det.py: per ogni richiesta sha1 del testo contro il controllo e TTFT.
    python cmp_det.py <controllo> <braccio> [<braccio>...]    (tag = nome dopo mc45b_)"""
import json, statistics, sys
from pathlib import Path

H = Path(__file__).resolve().parent


def load(t):
    return json.loads((H / f'mc45b_{t}' / 'res.json').read_text(encoding='utf-8'))


ctl = load(sys.argv[1])
cm = {r['name']: r for r in ctl['reqs']}
for t in sys.argv[1:]:
    r = load(t)
    rm = {x['name']: x for x in r['reqs']}
    row = []
    for cls in ('s', 'l'):
        names = [n for n in rm if n.startswith(cls)]
        tt = [rm[n]['ttft'] for n in names]
        pr = [rm[n]['prompt'] for n in names]
        same = sum(1 for n in names if n in cm and cm[n]['sha1'] == rm[n]['sha1'])
        row.append(f"{cls}: prompt {pr} ttft {tt} med {statistics.median(tt):.3f}s testo uguale al controllo {same}/{len(names)}")
    print(f"{t:14s} env=[{r['env']}] avvio {r.get('startup_s')} s\n   " + "\n   ".join(row))
