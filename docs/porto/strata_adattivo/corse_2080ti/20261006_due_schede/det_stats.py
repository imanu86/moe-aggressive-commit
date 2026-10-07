"""Per-run timings of DET arms and their spread (max-min, CV), L01 and L02 apart.

    python det_stats.py DET-a DET-b [...]
"""
import json, re, statistics, sys
from pathlib import Path

K = Path(__file__).resolve().parents[1] / '20261004_routed_keep'
rows = {'L01': [], 'L02': []}
for name in sys.argv[1:]:
    d = K / name
    if not (d / 'result.json').exists():
        print(name, 'no result'); continue
    res = json.loads((d / 'result.json').read_text())
    log = (d / 'engine.log').read_text(errors='replace').splitlines()
    timing = [l for l in log if l.startswith('strata decode timing')]
    st0 = [l for l in log if l.startswith('strata decode stage 0')]
    st1 = [l for l in log if l.startswith('strata decode stage 1')]
    work = [l for l in log if l.startswith('strata work')]
    amb = None
    if (d / 'ambiente.json').exists():
        try:
            a = json.loads((d / 'ambiente.json').read_text())
            vals = [x['cpu_altri'] for x in a if 'cpu_altri' in x]
            amb = sum(vals) / len(vals) if vals else None
        except Exception:
            pass
    print('==', name, '' if amb is None else 'cpu_altri mean %.2f cores' % amb)
    for i, q in enumerate(res['requests']):
        last = q['last']
        dec_s = last.get('decode_ms', 0) / 1000.0
        tps = q['decode_tps']
        msw = re.search(r'([\d.]+) ms/window', timing[i]).group(1) if i < len(timing) else '?'
        rows[q['case']].append(tps)
        print(f"  {q['case']}: decode {dec_s:.2f} s, {tps:.2f} t/s, {msw} ms/window")
        if i < len(st0): print('    ', st0[i][:150])
        if i < len(st1): print('    ', st1[i][:150])
        if i < len(work): print('    ', work[i][:260])
for c, v in rows.items():
    if len(v) >= 2:
        m = statistics.mean(v)
        print(f'{c}: n={len(v)} mean {m:.2f} t/s, max-min {max(v) - min(v):.2f} t/s ({100 * (max(v) - min(v)) / m:.1f}%), '
              f'CV {100 * statistics.stdev(v) / m:.2f}%')
