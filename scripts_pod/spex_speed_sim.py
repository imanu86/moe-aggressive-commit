"""SPEX SPEED SIMULATOR — da recall a tok/s vs VRAM, per far girare un MoE grande su HW piccolo (RTX 3060 12GB).
Residenza a due tier: cache statica per-layer (r esperti/layer, i piu' popolari) + prefetch Markov (p) dal layer prec.
SPEX NON droppa: i miss vengono FETCHati (qualita' = base). L'unico costo e' il tempo di fetch -> tok/s.
Fit su un corpus, eval su un ALTRO (cross = uso reale). Uso: python spex_speed_sim.py FIT.npz EVAL.npz [expert_MB]
"""
import sys, numpy as np

def sim(fit, evl, expert_MB=9.5, base_vram=4.0, total_vram=12.0, compute_ms=25.0, p=8,
        r_list=(0, 1, 2, 4, 8, 16, 32),
        bws=((13.0, 'RAM~13'), (6.0, 'NVMe~6'), (3.5, 'NVMe~3.5'))):
    Ef = np.load(fit)['experts'].astype(np.int64)
    dv = np.load(evl); Ev = dv['experts'].astype(np.int64); nexp = int(dv['n_experts'])
    T, L, k = Ev.shape
    pops = [np.argsort(-np.bincount(Ef[:, l, :].ravel(), minlength=nexp)) for l in range(L)]
    Cs = []
    for l in range(L - 1):
        C = np.zeros((nexp, nexp)); Af, Af1 = Ef[:, l, :], Ef[:, l + 1, :]
        for c1 in range(k):
            for c2 in range(k): np.add.at(C, (Af[:, c1], Af1[:, c2]), 1.0)
        Cs.append(C)
    print(f"\nEVAL={evl.split('/')[-1]}  L={L} E={nexp} k={k} | expert={expert_MB}MB base={base_vram}GB "
          f"total_vram={total_vram}GB compute={compute_ms}ms prefetch_p={p}")
    print(f"  {'r/lay':>5} {'VRAM':>6} {'miss/lay':>8} {'fetch/tok':>10} |  tok/s serial/nascosto:  " +
          "  ".join(n for _, n in bws))
    for r in r_list:
        ml = []
        for l in range(1, L):
            static = pops[l][:r]
            mk = Cs[l - 1][Ev[:, l - 1, :]].sum(1)          # [T,E] score esperti layer l
            if r > 0: mk[:, static] = -1e18                 # non ri-prefetchare i residenti
            avail = np.zeros((T, nexp), bool)
            if r > 0: avail[:, static] = True
            if p > 0:
                pref = np.argpartition(-mk, p - 1, axis=1)[:, :p]
                np.put_along_axis(avail, pref, True, axis=1)
            hit = np.take_along_axis(avail, Ev[:, l, :], axis=1).sum(1)
            ml.append((k - hit).mean())
        miss = float(np.mean(ml))
        vram = base_vram + r * L * expert_MB / 1000.0 + p * expert_MB / 1000.0
        fetch_MB = miss * L * expert_MB
        fit_ok = "" if vram <= total_vram else "  (>VRAM!)"
        cells = []
        for b, _ in bws:
            fms = fetch_MB / b
            cells.append(f"{1000/(fms+compute_ms):5.1f}/{1000/max(fms, compute_ms):5.1f}")
        print(f"  {r:>5} {vram:>5.1f}G {miss:>8.2f} {fetch_MB:>8.0f}MB |  " + "   ".join(cells) + fit_ok)
    print("  (miss/lay = esperti da fetchare per layer; qualita' invariata; tok/s = serial/nascosto-dietro-compute)")

if __name__ == '__main__':
    eMB = float(sys.argv[3]) if len(sys.argv) > 3 else 9.5
    sim(sys.argv[1], sys.argv[2], expert_MB=eMB)
