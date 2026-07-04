"""SPEX gate CROSS-DISTRIBUTION — il caso vero: cache/predittore costruito su un corpus, valutato su un ALTRO.
Se lo STATIC crolla cross-distribution ma il MARKOV regge -> la cache statica NON trasferisce, serve il dinamico (SPEX).
Fit su A (tutti i token), eval su B (tutti i token) -> nessun leakage (corpora diversi).
Uso: python markov_gate_cross.py FIT.npz EVAL.npz
"""
import sys, numpy as np

def topB_recall(scores, Al1, B):
    idx = np.argpartition(-scores, B - 1, axis=1)[:, :B]
    T, E = scores.shape
    m = np.zeros((T, E), bool); np.put_along_axis(m, idx, True, axis=1)
    return float(np.take_along_axis(m, Al1, axis=1).mean())

def cross(fit_path, eval_path):
    Ef = np.load(fit_path)['experts'].astype(np.int64)
    dv = np.load(eval_path); Ev = dv['experts'].astype(np.int64); nexp = int(dv['n_experts'])
    T, L, k = Ev.shape
    budgets = [k, 2 * k, 4 * k]  # 6%, 12.5%, 25% su 128
    MK = {B: [] for B in budgets}; ST = {B: [] for B in budgets}
    for l in range(L - 1):
        C = np.zeros((nexp, nexp), dtype=np.float64)                    # co-occorrenza dal corpus FIT
        Af, Af1 = Ef[:, l, :], Ef[:, l + 1, :]
        for c1 in range(k):
            for c2 in range(k):
                np.add.at(C, (Af[:, c1], Af1[:, c2]), 1.0)
        Ave, Ave1 = Ev[:, l, :], Ev[:, l + 1, :]                        # valuta sul corpus EVAL
        mk = C[Ave].sum(1)                                              # Markov: condiziona su L (eval)
        st = np.broadcast_to(C.sum(0), mk.shape)                        # Static: popolarita del FIT
        for B in budgets:
            MK[B].append(topB_recall(mk, Ave1, B)); ST[B].append(topB_recall(st, Ave1, B))
    fn = fit_path.split('/')[-1]; en = eval_path.split('/')[-1]
    print(f"\nFIT={fn}  ->  EVAL={en}   (E={nexp}, k={k})")
    print(f"  {'budget':>16} | {'STATIC':>7} {'MARKOV':>7} | {'M-S':>7}")
    for B in budgets:
        s, m = np.mean(ST[B]), np.mean(MK[B])
        print(f"  {B:>3}/{nexp} ({100*B/nexp:4.0f}%) | {s:7.3f} {m:7.3f} | {m-s:+7.3f}")

if __name__ == '__main__':
    cross(sys.argv[1], sys.argv[2])
