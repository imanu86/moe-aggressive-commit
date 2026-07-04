"""SPEX gate (LOCALE, VETTORIZZATO) — predicibilita CROSS-LAYER del next-expert al punto operativo SPEX.
SPEX tiene RESIDENTE un budget B di esperti (predetti dal layer L) e prefetcha. Recall = frazione dei k
attivi a L+1 gia' residenti. Tre predittori:
  RANDOM  = B a caso (per-token, seedato)  -> pavimento-caso VERO (~B/E, indipendente da E)
  STATIC  = B piu' popolari a L+1           -> sfrutta la concentrazione/marginale
  MARKOV  = B col punteggio co-occorrenza da L -> condizionamento cross-layer (segnale SPEX)
Guadagno: (STATIC-RANDOM)=concentrazione, (MARKOV-STATIC)=cross-layer, (MARKOV-RANDOM)=totale.
Uso: python markov_gate.py traces_*.npz
"""
import sys, numpy as np

def topB_recall(scores, Al1, B, k):
    """scores [T,E], Al1 [T,k]. Recall media = frazione dei k attivi che cadono nei top-B di scores."""
    idx = np.argpartition(-scores, B - 1, axis=1)[:, :B]          # [T,B] indici top-B (non ordinati)
    T, E = scores.shape
    mask = np.zeros((T, E), dtype=bool)
    np.put_along_axis(mask, idx, True, axis=1)
    return float(np.take_along_axis(mask, Al1, axis=1).mean())    # media su token e su k

def analyze(path, seed=0):
    d = np.load(path)
    E = d['experts'].astype(np.int64)   # [T, L, k]
    T, L, k = E.shape
    nexp = int(d['n_experts'])
    split = T // 2
    rng = np.random.default_rng(seed)
    budgets = [b for b in (k, 2 * k, 3 * k, 4 * k) if b <= nexp]
    MK = {B: [] for B in budgets}; ST = {B: [] for B in budgets}; RD = {B: [] for B in budgets}
    for l in range(L - 1):
        Al_tr, Al1_tr = E[:split, l, :], E[:split, l + 1, :]
        Al_te, Al1_te = E[split:, l, :], E[split:, l + 1, :]
        C = np.zeros((nexp, nexp), dtype=np.float64)
        for c1 in range(k):
            for c2 in range(k):
                np.add.at(C, (Al_tr[:, c1], Al1_tr[:, c2]), 1.0)
        mk_scores = C[Al_te].sum(1)                                # [n_te, E]  Markov
        st_scores = np.broadcast_to(C.sum(0), mk_scores.shape)     # [n_te, E]  popolarita (uguale per riga)
        rd_scores = rng.random(mk_scores.shape)                    # [n_te, E]  random per-token
        for B in budgets:
            MK[B].append(topB_recall(mk_scores, Al1_te, B, k))
            ST[B].append(topB_recall(st_scores, Al1_te, B, k))
            RD[B].append(topB_recall(rd_scores, Al1_te, B, k))
    print(f"\n{path}\n  T={T} L={L} k={k} E={nexp}  (recall = frazione dei k attivi a L+1 gia' residenti)")
    print(f"  {'budget':>18} | {'RANDOM':>7} {'STATIC':>7} {'MARKOV':>7} | {'conc(S-R)':>9} {'xlayer(M-S)':>11} {'tot(M-R)':>8}")
    for B in budgets:
        r, s, m = np.mean(RD[B]), np.mean(ST[B]), np.mean(MK[B])
        print(f"  {B:>3}/{nexp} ({100*B/nexp:4.0f}% res) | {r:7.3f} {s:7.3f} {m:7.3f} | {s-r:+9.3f} {m-s:+11.3f} {m-r:+8.3f}")
    return {'random': RD, 'static': ST, 'markov': MK, 'E': nexp, 'k': k}

if __name__ == '__main__':
    for p in sys.argv[1:]:
        analyze(p)
