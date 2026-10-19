"""Analisi della traccia di pipeline (STRATA_PIPELINE_TRACE) di una richiesta: quanta parte del periodo di finestra e' lo stadio 0.

    python pl_analyze.py traccia.trace [--scale 0.5 --scale 0.0]

Eventi (ms, evento, seq, x0, x1): L0 lancio dello stadio 0 (x1>=10 o 1: speculativo), F0 stadio 0 finito, L1/F1 stadio 1, V verdetto.
Per finestra verificata s (ultimo L0/F0 valido): S0 = F0-L0, S1 = F1-L1, esposizione dello stadio 0 E0 = max(0, F0 - V(s-1)) cioe' il tempo in cui
lo stadio 1 aspetta lo stadio 0 dopo il verdetto precedente.  Il tetto del guadagno (stadio 0 a costo zero) e' E0 medio / periodo.
Rigioco: per ogni finestra si conservano gli scarti osservati (anticipo del lancio, ritardo fra F0 e L1, coda F1->V) e si scala S0: periodo
risultante a S0*k (k=0: tetto; k=0,5: stadio 0 il doppio piu' veloce, ecc.).  Solo calcolo sulla traccia, niente supposizioni di parallelismo nuove.
"""
import argparse, collections, statistics as st, sys


def parse(path):
    reqs, cur = [], None
    for ln in open(path, encoding='utf-8', errors='replace'):
        if ln.startswith('#'):
            cur = []; reqs.append(cur); continue
        f = ln.split()
        if len(f) < 5:
            continue
        if cur is None:
            cur = []; reqs.append(cur)
        cur.append((float(f[0]), f[1], int(f[2]), int(f[3]), int(f[4])))
    return reqs


def windows(ev):
    W = collections.defaultdict(dict)
    for t, e, s, x0, x1 in ev:
        w = W[s]
        if e == 'L0':
            w['L0'] = t; w['spec'] = x1 >= 10 or (x1 == 1 and x0 >= 1 and False); w.pop('F0', None)
            w['T'] = x0
        elif e == 'F0' and 'F0' not in w:
            w['F0'] = t
        elif e == 'L1':
            w['L1'] = t
        elif e == 'F1':
            w['F1'] = t
        elif e == 'V':
            w['V'] = t; w['acc'] = x0
    return W


def analyse(ev, scales):
    W = windows(ev)
    seqs = sorted(s for s, w in W.items() if all(k in w for k in ('L0', 'F0', 'L1', 'F1', 'V')))
    rows = []
    prev = None
    for s in seqs:
        w = W[s]
        if prev is not None and s == prev + 1:
            v0 = W[prev]['V']
            rows.append(dict(s=s, S0=w['F0'] - w['L0'], S1=w['F1'] - w['L1'], E0=max(0.0, w['F0'] - v0), per=w['V'] - v0,
                             gap_l1=w['L1'] - max(w['F0'], v0), tail=w['V'] - w['F1'], lead=w['L0'] - v0,
                             spec=w['spec'], T=w.get('T', 0), Lbeforev=w['L0'] < v0))
        prev = s
    return rows, W


def replay(rows, W, k):
    """periodo medio con S0 scalato di k: L0 resta ancorato come osservato rispetto al suo riferimento (verdetto precedente o F0 precedente)."""
    seqs = [r['s'] for r in rows]
    V = {}
    F0 = {}
    p = rows[0]['s'] - 1
    V[p] = W[p]['V']; F0[p] = W[p]['F0']
    tot = 0.0
    for r in rows:
        s = r['s']
        w = W[s]
        # riferimento del lancio osservato: se partito prima del verdetto precedente, dietro il suo F0 (stadio 0 libero), altrimenti dopo V
        if w['L0'] < W[s - 1]['V']:
            L0 = F0[s - 1] + (w['L0'] - W[s - 1]['F0'])
        else:
            L0 = V[s - 1] + (w['L0'] - W[s - 1]['V'])
        F0[s] = L0 + (w['F0'] - w['L0']) * k
        L1 = max(F0[s], V[s - 1]) + r['gap_l1']
        V[s] = L1 + r['S1'] + r['tail']
    return (V[seqs[-1]] - V[p]) / len(seqs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trace')
    ap.add_argument('--scale', type=float, action='append', default=[0.0, 0.5, 0.75])
    ap.add_argument('--req', type=int, default=None)
    a = ap.parse_args()
    reqs = parse(a.trace)
    for i, ev in enumerate(reqs):
        if a.req is not None and i != a.req:
            continue
        rows, W = analyse(ev, a.scale)
        if len(rows) < 20:
            print(f'req {i}: {len(rows)} finestre consecutive, troppo poche'); continue
        m = lambda key: st.mean(r[key] for r in rows)
        per = m('per')
        nspec = sum(1 for r in rows if r['E0'] < 0.5)
        print(f'req {i}: {len(rows)} finestre, periodo {per:.2f} ms ({1000/per:.1f} fin/s) | S0 {m("S0"):.2f} S1 {m("S1"):.2f} ms | '
              f'E0 (stadio 0 esposto) {m("E0"):.2f} ms = {m("E0")/per*100:.1f}% del periodo; finestre con E0<0,5 ms (stadio 0 nascosto): {nspec/len(rows)*100:.0f}% | '
              f'gap F0/V->L1 {m("gap_l1"):.2f} coda F1->V {m("tail"):.2f}')
        base = replay(rows, W, 1.0)
        out = [f'  rigioco k=1,00: {base:.2f} ms (controllo, osservato {per:.2f})']
        for k in sorted(set(a.scale), reverse=True):
            p = replay(rows, W, k)
            out.append(f'k={k:.2f}: {p:.2f} ms ({(base - p) / base * 100:+.1f}% di tempo, {(base / p - 1) * 100:+.1f}% di velocita)')
        print('; '.join(out))


if __name__ == '__main__':
    main()
