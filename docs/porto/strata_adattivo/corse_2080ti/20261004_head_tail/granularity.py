"""How finely can down-projection work be skipped? Gate-first selection per token, groups of G neurons.

For each call: gate-first score |silu(g_i)|. Two policies at the same neuron budget (keep k):
  neuron  keep the top k*640 neurons; a group of G is skippable only if none of its neurons is kept
  group   rank groups of G by summed score and keep whole groups (k*640/G of them)
Reports the share of down work skipped and the routed-sum relative L2 (worst mean over layers).
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / '20261004_ngram_memory'))
import analyze_dynamic as AD
import trace_io

TOPK, FF = 10, 640


def main(lab, model, fork, text='code', layers=(1, 35, 36), keep=0.5):
    W = AD.Weights(Path(model), Path(fork))
    rows = trace_io.read_rows(Path(lab) / text / 'trace.snt')
    for G in (1, 4, 8, 16, 32, 64):
        res = []
        for layer in layers:
            X = np.stack([r['layers'][layer]['x'] for r in rows]).astype(np.float32)
            ids = np.stack([r['layers'][layer]['ids'] for r in rows])
            w = np.stack([r['layers'][layer]['weights'] for r in rows]).astype(np.float32)
            P = len(rows)
            full = np.zeros((P, TOPK, 2560), np.float32)
            errn = np.zeros((P, TOPK, 2560), np.float32)
            errg = np.zeros((P, TOPK, 2560), np.float32)
            skip_n, n_calls = 0.0, 0
            for e in np.unique(ids):
                pi, si = np.nonzero(ids == e)
                ex = W.expert(layer, int(e))
                x = X[pi]
                g, u = x @ ex['gate'].T, x @ ex['up'].T
                h = AD.silu(g) * u
                D = ex['down']
                full[pi, si] = h @ D.T
                s = np.abs(AD.silu(g))
                kn = int(round(keep * FF))
                keepn = np.zeros_like(h, bool)
                np.put_along_axis(keepn, np.argsort(-s, axis=1)[:, :kn], True, axis=1)
                errn[pi, si] = (h * ~keepn) @ D.T
                grp_active = keepn.reshape(len(pi), FF // G, G).any(axis=2)
                skip_n += float((~grp_active).mean(axis=1).sum()); n_calls += len(pi)
                gs = s.reshape(len(pi), FF // G, G).sum(axis=2)
                kg = kn // G
                keepg = np.zeros_like(gs, bool)
                np.put_along_axis(keepg, np.argsort(-gs, axis=1)[:, :kg], True, axis=1)
                keepg = np.repeat(keepg, G, axis=1)
                errg[pi, si] = (h * ~keepg) @ D.T
            R = np.einsum('pk,pkd->pd', w, full)
            rn = np.linalg.norm(R, axis=1)
            en = np.linalg.norm(np.einsum('pk,pkd->pd', w, errn), axis=1) / rn
            eg = np.linalg.norm(np.einsum('pk,pkd->pd', w, errg), axis=1) / rn
            res.append((skip_n / n_calls, en.mean(), eg.mean()))
        r = np.array(res)
        print(f'G={G:2}: lavoro down saltabile con selezione per neurone {100*r[:,0].mean():5.1f}% '
              f'(errore {100*r[:,1].max():.1f}%) | selezione per gruppi: salta {100*(1-keep):.0f}%, errore {100*r[:,2].max():.1f}%',
              flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:4])
