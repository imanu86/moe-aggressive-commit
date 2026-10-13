"""Table of mc2 results: aggregate t/s per scenario (rows) and arm (columns); solo = mean decode t/s of a single chat.

    python tabella.py daily b4mtp b4g2 ...
"""
import json, sys
from pathlib import Path

H = Path(__file__).resolve().parent
arms = sys.argv[1:]
data = {}
order = []
for t in arms:
    p = H / f'mc2_{t}' / 'res.json'
    if not p.exists():
        continue
    r = json.loads(p.read_text(encoding='utf-8'))
    data[t] = r['scen']
    for sc in r['scen']:
        if sc not in order:
            order.append(sc)
cols = [t for t in arms if t in data]
print('| scenario | ' + ' | '.join(cols) + ' |')
print('|---|' + '---|' * len(cols))
for sc in order:
    cells = []
    for t in cols:
        v = data[t].get(sc)
        if v is None:
            cells.append('')
        elif sc.startswith('solo'):
            cells.append(f"{v['solo_dec']} (dec)")
        elif sc.startswith('pf'):
            ms = [x.get('ttft') for _, x in sorted(v['res'].items())]
            cells.append('/'.join(f'{m:.2f}' for m in ms if m is not None) + ' s')
        else:
            cells.append(f"{v['agg']:.1f}")
    print(f'| {sc} | ' + ' | '.join(cells) + ' |')
