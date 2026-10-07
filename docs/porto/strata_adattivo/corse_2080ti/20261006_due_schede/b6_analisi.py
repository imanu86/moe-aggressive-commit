"""B6: reads STRATA_SPEC_LOG files (one 'W ...' line per decode window of the serve loop) and prints
  - the cost of a window by its size (round ms: mean by T and a least-squares line),
  - the drafter's calibration: acceptance of draft j (given the drafts before it held) by depth and probability bin,
    from the drafts verified and from the first draft held back (decided when every draft before it held),
  - an offline replay of window-size rules on the same windows (only sizes <= the drafter's chain + 1 whose
    outcome the log decides), in tokens per ms.

    python b6_analisi.py <spec.log> [...]

Line: W p T T_mtp a emit kind verify commit draft round held_hit n p0 p1 ...  (kind 0 mtp, 1 lookup, 2 chain, 3 first)
"""
import sys
from collections import defaultdict


def load(paths):
    reqs, cur = [], None
    for path in paths:
        for line in open(path, encoding='utf8', errors='replace'):
            f = line.split()
            if not f or f[0] != 'W':
                continue
            p, T, Tm, a, emit, kind = (int(x) for x in f[1:7])
            ver, com, dra, rnd = (float(x) for x in f[7:11])
            held, n = int(f[11]), int(f[12])
            probs = [float(x) for x in f[13:13 + n]]
            if kind == 3 or cur is None:
                cur = []
                reqs.append(cur)
            cur.append(dict(p=p, T=T, a=a, emit=emit, kind=kind, ver=ver, com=com, dra=dra, rnd=rnd, held=held,
                            probs=probs))
    return reqs


def line_fit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - b * mx, b


def main():
    reqs = load(sys.argv[1:])
    for ri, ws in enumerate(reqs):
        ws = [w for w in ws if w['kind'] != 3]
        mtp = [w for w in ws if w['kind'] == 0]
        print(f'== request {ri}: {len(ws)} windows ({len(mtp)} plain MTP), '
              f'{sum(w["emit"] for w in ws)} tokens in {sum(w["rnd"] for w in ws):.0f} ms '
              f'-> {sum(w["emit"] for w in ws) / max(1e-9, sum(w["rnd"] for w in ws)) * 1000:.1f} t/s')
        byT = defaultdict(list)
        for w in mtp:
            byT[w['T']].append(w)
        for T in sorted(byT):
            g = byT[T]
            k = len(g)
            print(f'  T={T}: {k:4d} windows  round {sum(w["rnd"] for w in g) / k:6.2f} ms  (verify '
                  f'{sum(w["ver"] for w in g) / k:6.2f} commit {sum(w["com"] for w in g) / k:5.2f} draft '
                  f'{sum(w["dra"] for w in g) / k:5.2f})  tokens {sum(w["a"] + 1 for w in g) / k:.2f}')
        if len(byT) > 1:
            c0, c1 = line_fit([w['T'] for w in mtp], [w['rnd'] for w in mtp])
            v0, v1 = line_fit([w['T'] for w in mtp], [w['ver'] for w in mtp])
            print(f'  round ms = {c0:.2f} + {c1:.2f} * T   (verify {v0:.2f} + {v1:.2f} * T)')
    allw = [w for ws in reqs for w in ws if w['kind'] == 0]
    # calibration: draft j tested iff a >= j (j < T-1), accepted iff a > j; held back j = T-1 decided iff a == T-1
    cal = defaultdict(lambda: [0, 0])
    for w in allw:
        T, a, pr = w['T'], w['a'], w['probs']
        for j in range(T - 1):
            if a >= j and j < len(pr):
                c = cal[(min(j, 3), min(int(pr[j] * 10), 9))]
                c[0] += a > j
                c[1] += 1
        if w['held'] >= 0 and T - 1 < len(pr):
            c = cal[(min(T - 1, 3), min(int(pr[T - 1] * 10), 9))]
            c[0] += w['held']
            c[1] += 1
    print('== calibration: acceptance by depth and draft probability (rate/n)')
    for d in range(4):
        print(f'  depth {d}: ' + ' '.join(f'{b / 10:.1f}:{cal[(d, b)][0] / cal[(d, b)][1]:.2f}/{cal[(d, b)][1]}'
                                          for b in range(10) if cal[(d, b)][1]))

    def q(d, p):
        c = cal[(min(d, 3), min(int(p * 10), 9))]
        return (c[0] + 4 * p) / (c[1] + 4)

    # replay: a rule maps (probs) -> t; a window's outcome at size t is decided when t <= T (tokens 1 + min(a, t-1))
    # or t == T + 1 with the held-back verdict known (tokens 1 + a + held) or a < T - 1 (tokens 1 + a)
    for ri, ws in enumerate(reqs):
        mtp = [w for w in ws if w['kind'] == 0]
        if not mtp:
            continue
        c0, c1 = line_fit([w['T'] for w in mtp], [w['rnd'] for w in mtp])
        cost = lambda t: c0 + c1 * t
        base_tok = sum(w['a'] + 1 for w in mtp)
        base_ms = sum(cost(w['T']) for w in mtp)
        R = base_tok / base_ms

        def replay(rule):
            tok = ms = 0.0
            undecided = 0
            for w in mtp:
                t = rule(w['probs'])
                T, a = w['T'], w['a']
                if t <= T:
                    tk = 1 + min(a, t - 1)
                elif t == T + 1 and (a < T - 1 or w['held'] >= 0):
                    tk = 1 + a + (w['held'] if a == T - 1 else 0)
                else:
                    undecided += 1
                    t, tk = T, a + 1
                tok += tk
                ms += cost(t)
            return tok / ms, tok / len(mtp), ms / len(mtp), undecided

        def minp(th, S=4):
            def r(pr):
                t = 1
                while t < S and t - 1 < len(pr) and pr[t - 1] >= th:
                    t += 1
                return t
            return r

        def cumr(th, S=4):
            def r(pr):
                t, P = 1, 1.0
                while t < S and t - 1 < len(pr):
                    P *= pr[t - 1]
                    if P < th:
                        break
                    t += 1
                return t
            return r

        def dink(scale, S=4):
            def r(pr):
                best, bt, E, P = 1 - scale * R * cost(1), 1, 1.0, 1.0
                for t in range(2, min(S, len(pr) + 1) + 1):
                    P *= q(t - 2, pr[t - 2])
                    E += P
                    v = E - scale * R * cost(t)
                    if v > best:
                        best, bt = v, t
                return bt
            return r

        print(f'== replay request {ri} (cost {c0:.2f} + {c1:.2f} T ms, R {R * 1000:.1f} t/s at the logged sizes)')
        for name, rule in [('min_p 0.5', minp(0.5)), ('min_p 0.6', minp(0.6)), ('min_p 0.65', minp(0.65)),
                           ('min_p 0.7', minp(0.7)), ('min_p 0.8', minp(0.8)), ('cum 0.4', cumr(0.4)),
                           ('cum 0.5', cumr(0.5)), ('cum 0.6', cumr(0.6)), ('dinkelbach x1', dink(1.0)),
                           ('dinkelbach x1.2', dink(1.2)), ('dinkelbach x0.8', dink(0.8)), ('T=1 always', lambda pr: 1),
                           ('oracle (bound)', None)]:
            if rule is None:
                tok = sum(1 + w['a'] + (w['held'] == 1) for w in mtp)
                ms = sum(cost(w['a'] + 1 + (w['held'] == 1)) for w in mtp)
                print(f'  {name:16s} {tok / ms * 1000:6.1f} t/s  {tok / len(mtp):.2f} tok/window  {ms / len(mtp):.2f} ms/window')
                continue
            r, tw, mw, und = replay(rule)
            print(f'  {name:16s} {r * 1000:6.1f} t/s  {tw:.2f} tok/window  {mw:.2f} ms/window  undecided {und}')


if __name__ == '__main__':
    main()
