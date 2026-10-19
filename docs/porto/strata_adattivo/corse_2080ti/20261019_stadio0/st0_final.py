"""Numeri derivati per MISURE_STADIO0: scomposizione della finestra di decode, pendenze per GiB e proiezioni, solo da dati misurati (+ modello della traccia).

    python st0_final.py
"""
import json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st0_report as R
import numpy as np

MIB_PER_SLOT = 1.43   # 1 GiB = 716 slot di esperti da 1,43 MiB (blob medio osservato: 3,40 GiB / 2438 slot)

FAMILIES = {
    '1138': ['S2B3a'], '1563': ['S3H2'], '1800': ['B2a', 'S2B2a', 'S3H1'],
    '2440 veloce': ['S2A2', 'S2A3'], '3100-3260': ['S3H3', 'S5X1', 'S5X2', 'S5H3b'],
}


def req_rows(names, labels=('L01', 'L02', 'L03')):
    rows = []
    for n in names:
        o = R.parse_run('DET-ST0-' + n if not n.startswith('DET') else n)
        for r in o['requests']:
            if r['label'] in labels and 's0_wait' in r and r.get('gen', 0) > 500:
                rows.append(r)
    return rows


def m(rows, k):
    v = [r[k] for r in rows if k in r]
    return st.mean(v) if v else float('nan')


def main():
    print('## scomposizione della finestra di decode (L01-L03, regime veloce), ms per finestra')
    print('| slot stadio 0 | n | ms/finestra | tok/fin | ms/token | stadio 0 (attesa GPU + pool/piano) | stadio 1 | resto (bozza, commit, ritardi) | quota stadio 0 | hit % | CPU esp./layer-fin |')
    print('|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|')
    tab = {}
    for fam, names in FAMILIES.items():
        rows = req_rows(names)
        if fam == '2440 veloce':
            rows = [r for r in rows if r['s0_wait'] < 14]
        if not rows:
            continue
        mw, tw = m(rows, 'ms_win'), m(rows, 'tok_win')
        s0, s0w, s0p, s1 = m(rows, 's0_ms'), m(rows, 's0_wait'), m(rows, 's0_pool'), m(rows, 's1_ms')
        tab[fam] = dict(ms_tok=mw / tw, pool=s0p, wait=s0w, s0=s0, s1=s1, mw=mw, tw=tw, cpu=m(rows, 'cpu_experts'), hit=m(rows, 'hit'))
        print(f"| {fam} | {len(rows)} | {mw:.1f} | {tw:.2f} | {mw / tw:.2f} | {s0:.1f} ({s0w:.1f} + {s0p:.1f}) | {s1:.1f} | {mw - s0 - s1:.1f} | {s0 / mw * 100:.0f}% | {m(rows, 'hit'):.1f} | {m(rows, 'cpu_experts'):.2f} |")
    # pendenze
    xs = {'1138': 1138, '1563': 1563, '1800': 1800, '2440 veloce': 2440, '3100-3260': 3200}
    pts = [(xs[k], tab[k]['ms_tok'], tab[k]['pool'], tab[k]['mw']) for k in xs if k in tab]
    x = np.array([p[0] for p in pts], float)
    for lab, idx in (('ms/token', 1), ('pool+piano stadio 0 (ms/finestra)', 2), ('ms/finestra', 3)):
        y = np.array([p[idx] for p in pts], float)
        b, a = np.polyfit(x, y, 1)
        print(f'\npendenza {lab}: {b * 1000:+.3f} per 1000 slot = {b * 1024 / MIB_PER_SLOT:+.3f} per GiB (intercetta {a:.2f}; fra {int(x.min())} e {int(x.max())} slot)')
    # proiezione con il modello della traccia (oracolo): CPU esperti/chiamata globali a S0 slot e pool previsto dalla relazione misurata pool~cpu
    cpu = np.array([tab[k]['cpu'] for k in xs if k in tab]); pool = np.array([tab[k]['pool'] for k in xs if k in tab])
    b, a = np.polyfit(cpu, pool, 1)
    print(f'\nrelazione misurata pool+piano stadio 0 = {a:.2f} + {b:.2f} x (esperti CPU per layer-finestra, globali)')
    orac = {3108: 1.32, 3260: 1.24, 4000: 0.95, 5000: 0.72, 6000: 0.61, 7000: 0.57, 8192: 0.57}
    stat = {3108: 2.23, 3260: 2.14, 4000: 1.70, 5000: 1.27, 6000: 0.99, 7000: 0.79, 8192: 0.57}
    print('| slot stadio 0 | CPU esp./chiamata (oracolo) | pool+piano previsto (ms/fin) | (profilo statico) | pool previsto |')
    print('|---:|---:|---:|---:|---:|')
    for s in orac:
        print(f'| {s} | {orac[s]:.2f} | {max(a + b * orac[s], 0.4):.1f} | {stat[s]:.2f} | {max(a + b * stat[s], 0.4):.1f} |')


if __name__ == '__main__':
    main()
