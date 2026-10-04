"""Head in VRAM, tail on CPU on demand: offline admission screen (arm B).

Each routed expert keeps its H most important neurons (the head, GPU resident).
The remaining 640-H neurons (the tail) stay in RAM and are computed on CPU only
when a per-call trigger fires; otherwise their contribution is skipped.

Inputs are saved full-model replays (SNRv0001: h[640] and router weight per
call, layers 0/1/35/36). Neuron order is static, built from calibration texts
only; the held-out text never influences the order (leave-one-text-out).
Errors are relative L2 of the routed expert sum per (position, layer), the same
screen as the turn-pruning pilot. Shared expert and residual are excluded, so
this is conservative with respect to the hidden state. Not a generation test,
not physical packing, not t/s.
"""
import argparse, collections, hashlib, json, struct, sys, time
from pathlib import Path

import numpy as np

HIDDEN, FF, TOPK = 2560, 640, 10
LAYERS = (0, 1, 35, 36)
TEXTS = ('code', 'explain', 'reason')
HEADS = (256, 320, 384, 448)          # multiples of 64: whole Q2_0 and IQ4_NL down blocks
ENTRY = np.dtype([('serial', '<u8'), ('pos', '<i8'), ('layer', '<i4'), ('expert', '<i4'),
                  ('tier', '<i4'), ('gu', '<i4'), ('down', '<i4'), ('cold', '<i4'), ('weight', '<f4'),
                  ('h', '<f4', (FF,)), ('y', '<f4', (8, HIDDEN))])
assert ENTRY.itemsize == 84524
CODEBOOK = np.array([-127, -104, -83, -65, -49, -35, -22, -10,
                     1, 13, 25, 38, 53, 69, 89, 113], dtype=np.float32)


def decode_down(raw, kind):
    b = np.frombuffer(raw, np.uint8).reshape(-1, 18)
    d = b[:, :2].copy().view('<f2').astype(np.float32)
    q = b[:, 2:]
    if kind == 20:
        v = np.concatenate((CODEBOOK[q & 15], CODEBOOK[q >> 4]), axis=1)
    elif kind == 42:
        v = ((q[:, :, None] >> np.array([0, 2, 4, 6], np.uint8)) & 3).reshape(-1, 64).astype(np.float32) - 1
    else:
        raise ValueError(kind)
    return (d * v).reshape(HIDDEN, FF)


class Down:
    def __init__(self, model, fork):
        sys.path.insert(0, str(fork / 'tools'))
        from gguf_reader import GGUFFile
        paths = [model, model.with_name(model.name.replace('-00001-of-00002', '-00002-of-00002'))]
        self.src = {}
        for p in paths:
            gg = GGUFFile(p)
            for layer in LAYERS:
                for t in gg.tensors:
                    if t.name == f'blk.{layer}.ffn_down_exps.weight':
                        assert t.shape == [FF, HIDDEN, 512] and t.type_id in (20, 42)
                        self.src[layer] = (p, gg.data_start + t.offset, t.type_id)
        assert set(self.src) == set(LAYERS)

    def layer(self, layer, experts):
        p, base, kind = self.src[layer]
        size = HIDDEN * (FF // (32 if kind == 20 else 64)) * 18
        out = {}
        with p.open('rb') as f:
            for e in sorted(experts):
                f.seek(base + int(e) * size)
                raw = f.read(size)
                assert len(raw) == size
                out[int(e)] = decode_down(raw, kind)
        return out, kind


def load_text(lab, text):
    files = sorted((lab / text / 'chunks').glob('chunk-*.snr'))
    assert files, text
    parts = []
    for path in files:
        with path.open('rb') as f:
            assert f.read(8) == b'SNRv0001'
            assert struct.unpack('<4I4i', f.read(32)) == (HIDDEN, FF, TOPK, 4, *LAYERS)
        n = (path.stat().st_size - 40) // ENTRY.itemsize
        arr = np.memmap(path, mode='r', dtype=ENTRY, offset=40, shape=(n,))
        parts.append({k: np.array(arr[k]) for k in ('pos', 'layer', 'expert', 'weight', 'h')}
                     | {'y0': np.array(arr['y'][:, 0, :])})
    cat = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    key = cat['pos'] * 100000 + cat['layer'] * 1000 + cat['expert']
    _, first = np.unique(key, return_index=True)
    first.sort()
    out = {k: v[first] for k, v in cat.items()}
    out['dropped_duplicates'] = int(len(key) - len(first))
    return out


def orders_from(calib, down, layer):
    """Static per-expert neuron order from calibration calls only (most important first)."""
    sel = calib['layer'] == layer
    experts, h, w = calib['expert'][sel], calib['h'][sel].astype(np.float64), calib['weight'][sel].astype(np.float64)
    energy, absval, count = {}, {}, collections.Counter(experts.tolist())
    for e in np.unique(experts):
        m = experts == e
        cn = np.linalg.norm(down[int(e)], axis=0).astype(np.float64)
        wh = w[m, None] * h[m]
        energy[int(e)] = np.argsort(-(np.mean(wh * wh, axis=0) * cn * cn), kind='stable')
        absval[int(e)] = np.argsort(-(np.mean(np.abs(wh), axis=0) * cn), kind='stable')
    return {'energy': energy, 'abs': absval}, count


def run(args):
    lab, fork, model = Path(args.lab), Path(args.fork), Path(args.model)
    t0 = time.time()
    data = {t: load_text(lab, t) for t in TEXTS}
    meta = {t: {'calls': int(len(d['pos'])), 'positions': int(len(np.unique(d['pos']))),
                'dropped_duplicates': d['dropped_duplicates']} for t, d in data.items()}
    print('loaded', meta, f'{time.time()-t0:.1f}s', flush=True)
    downs = Down(model, fork)
    results, checks = [], {}
    for layer in LAYERS:
        used = set()
        for d in data.values():
            used |= set(d['expert'][d['layer'] == layer].tolist())
        down, kind = downs.layer(layer, used)
        print(f'layer {layer}: {len(used)} experts decoded (down type {kind})', flush=True)
        for held in TEXTS:
            calib = {k: np.concatenate([data[t][k] for t in TEXTS if t != held])
                     for k in ('layer', 'expert', 'weight', 'h')}
            orders, count = orders_from(calib, down, layer)
            d = data[held]
            sel = np.nonzero(d['layer'] == layer)[0]
            pos, ex, w, h = d['pos'][sel], d['expert'][sel], d['weight'][sel], d['h'][sel]
            # group = (position) inside this layer; every group must hold the 10 routed calls
            upos, grp = np.unique(pos, return_inverse=True)
            sizes = np.bincount(grp)
            assert np.all(sizes == TOPK), (held, layer, collections.Counter(sizes.tolist()))
            wsum = np.bincount(grp, weights=w)
            assert np.allclose(wsum, 1.0, atol=1e-4), (held, layer, wsum.min(), wsum.max())
            # rank inside the group by router weight (0 = largest)
            rank = np.empty(len(sel), np.int64)
            for g in range(len(upos)):
                idx = np.nonzero(grp == g)[0]
                rank[idx[np.argsort(-w[idx], kind='stable')]] = np.arange(TOPK)
            n = len(sel)
            y = np.zeros((n, HIDDEN), np.float32)
            tails = {}  # (order, H) -> [n, HIDDEN] weighted tail contribution
            covered = np.array([int(e) in orders['energy'] for e in ex])
            fallback = {int(e): np.argsort(-np.linalg.norm(down[int(e)], axis=0), kind='stable') for e in np.unique(ex)}
            for e in np.unique(ex):
                m = np.nonzero(ex == e)[0]
                D = down[int(e)]
                hm = h[m]
                y[m] = hm @ D.T
                for oname in ('energy', 'abs', 'downnorm', 'oracle'):
                    for H in HEADS:
                        if oname == 'oracle':  # per-call ideal: current |h_i|*||d_i||, not realizable
                            score = np.abs(hm) * np.linalg.norm(D, axis=0)[None, :]
                            tailmask = np.zeros_like(hm, dtype=bool)
                            np.put_along_axis(tailmask, np.argsort(-score, axis=1, kind='stable')[:, H:], True, axis=1)
                            t = (hm * tailmask) @ D.T
                        else:
                            order = orders.get(oname, {}).get(int(e), fallback[int(e)]) if oname != 'downnorm' else fallback[int(e)]
                            tail = order[H:]
                            t = hm[:, tail] @ D[:, tail].T
                        tails.setdefault((oname, H), np.zeros((n, HIDDEN), np.float32))[m] = t * w[m, None]
            # sanity: python down projection vs replay grouped output
            rel = np.linalg.norm(y - d['y0'][sel], axis=1) / np.maximum(np.linalg.norm(d['y0'][sel], axis=1), 1e-30)
            checks[f'{held}:{layer}'] = {'py_vs_replay_rel_l2_p50': float(np.median(rel)),
                                         'py_vs_replay_rel_l2_max': float(rel.max()),
                                         'calls': n, 'positions': int(len(upos)),
                                         'calls_with_calibrated_order': float(covered.mean())}
            # reorder calls as [position, rank] so group sums are plain reshapes
            G = len(upos)
            perm = np.lexsort((rank, grp))
            assert np.array_equal(grp[perm], np.repeat(np.arange(G), TOPK))
            w3, rank3 = w[perm].reshape(G, TOPK), rank[perm].reshape(G, TOPK)
            routed = (y[perm] * w[perm, None]).reshape(G, TOPK, HIDDEN).sum(axis=1, dtype=np.float64)
            rnorm = np.linalg.norm(routed, axis=1)
            for (oname, H), t in tails.items():
                t3 = t[perm].reshape(G, TOPK, HIDDEN)
                tnorm = np.linalg.norm(t3, axis=2)
                triggers = {'none': np.zeros((G, TOPK), bool)}
                for k in (1, 2, 3):
                    triggers[f'rank<{k}'] = rank3 < k
                for tau in (0.10, 0.15, 0.20):
                    triggers[f'w>={tau:.2f}'] = w3 >= tau
                # oracle trigger with the rank<2 budget: compute the two largest weighted tails
                orank = np.argsort(np.argsort(-tnorm, axis=1, kind='stable'), axis=1)
                triggers['oracle2'] = orank < 2
                for tname, computed in triggers.items():
                    err = np.einsum('gk,gkd->gd', (~computed).astype(np.float32), t3, dtype=np.float64)
                    e = np.linalg.norm(err, axis=1) / rnorm
                    results.append({'held_out': held, 'layer': layer, 'order': oname, 'head': H,
                                    'trigger': tname, 'tail_calls_computed': float(computed.mean()),
                                    'mean': float(e.mean()), 'p99': float(np.quantile(e, 0.99)),
                                    'max': float(e.max())})
            print(f'  {held} layer {layer}: {n} calls, cov {covered.mean():.2f}, '
                  f'check p50 {checks[f"{held}:{layer}"]["py_vs_replay_rel_l2_p50"]:.2e} {time.time()-t0:.0f}s', flush=True)
        del down
    out = {'protocol': __doc__, 'heads': HEADS, 'layers': LAYERS, 'texts': meta, 'checks': checks,
           'results': results, 'elapsed_s': time.time() - t0}
    Path(args.output).write_text(json.dumps(out, indent=1))
    print('written', args.output)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lab', required=True, help='.codex_runs/20261004_ngram_memory_v2')
    ap.add_argument('--fork', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--output', required=True)
    run(ap.parse_args())
