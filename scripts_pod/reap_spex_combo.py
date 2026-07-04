"""REAP + SPEX — cache a due tier. Budget B residenti = s esperti REAP-salient (static, sempre) + (B-s) Markov (dynamic).
Confronta: POP(freq statica) | REAP(saliency statica) | MARKOV(dyn) | HYBRID(reap-static + markov-dyn).
Fit su un corpus, eval su un altro (cross = caso SPEX). Uso: python reap_spex_combo.py FIT.npz EVAL.npz reap.json [B]
"""
import sys, json, numpy as np

def rec_scores(scores, Al1, B):
    idx = np.argpartition(-scores, B - 1, axis=1)[:, :B]; T, E = scores.shape
    m = np.zeros((T, E), bool); np.put_along_axis(m, idx, True, axis=1)
    return float(np.take_along_axis(m, Al1, axis=1).mean())

def rec_fixed(fixed, Al1, nexp):
    m = np.zeros(nexp, bool); m[fixed] = True
    return float(m[Al1].mean())

def rec_hybrid(reap_set, mk, Al1, nexp, Bdyn):
    mk2 = mk.copy(); mk2[:, reap_set] = -1e18                      # non ri-predire cio' che e' gia' residente
    idx = np.argpartition(-mk2, Bdyn - 1, axis=1)[:, :Bdyn]
    m = np.zeros((mk.shape[0], nexp), bool); m[:, reap_set] = True; np.put_along_axis(m, idx, True, axis=1)
    return float(np.take_along_axis(m, Al1, axis=1).mean())

def run(fit_p, eval_p, reap_p, B=32):
    Ef = np.load(fit_p)['experts'].astype(np.int64)
    dv = np.load(eval_p); Ev = dv['experts'].astype(np.int64); nexp = int(dv['n_experts'])
    reap = json.load(open(reap_p))['experts_by_mass_asc']         # ascendente -> top-salient in coda
    T, L, k = Ev.shape
    acc = {kk: [] for kk in ('pop', 'reap', 'markov', 'hybrid')}
    for l in range(L - 1):
        C = np.zeros((nexp, nexp)); Af, Af1 = Ef[:, l, :], Ef[:, l + 1, :]
        for c1 in range(k):
            for c2 in range(k): np.add.at(C, (Af[:, c1], Af1[:, c2]), 1.0)
        Ave, Ave1 = Ev[:, l, :], Ev[:, l + 1, :]
        pop = np.broadcast_to(C.sum(0), (Ave.shape[0], nexp)); mk = C[Ave].sum(1)
        reap_top = np.array(reap[str(l + 1)][-B:])
        acc['pop'].append(rec_scores(pop, Ave1, B))
        acc['markov'].append(rec_scores(mk, Ave1, B))
        acc['reap'].append(rec_fixed(reap_top, Ave1, nexp))
        acc['hybrid'].append(rec_hybrid(np.array(reap[str(l + 1)][-(B // 2):]), mk, Ave1, nexp, B // 2))
    r = {kk: np.mean(v) for kk, v in acc.items()}
    print(f"  FIT={fit_p.split('/')[-1]:26} EVAL={eval_p.split('/')[-1]:26} B={B}({100*B/nexp:.0f}%): "
          f"POP={r['pop']:.3f} REAP={r['reap']:.3f} MARKOV={r['markov']:.3f} HYBRID={r['hybrid']:.3f}")
    return r

if __name__ == '__main__':
    B = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    run(sys.argv[1], sys.argv[2], sys.argv[3], B)
