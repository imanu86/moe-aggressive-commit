"""Per-token neuron selection inside each routed expert (arm B, dynamic).

For every call the engine would first compute a cheap signal, keep the top
k*640 neurons by that signal, and compute up/down (or gate/down) only for them:
  gate     |silu(g_i)|                       gate rows read in full (CATS-like)
  gate_n   |silu(g_i)| * ||up_i|| * ||d_i||   same read, static weight norms
  up_n     |u_i| * ||d_i||                    up rows read in full (FloE-like)
  oracle   |h_i| * ||d_i||                    needs h: not realizable, ceiling
Optionally the top-r experts by router weight are computed in full.
x comes from the saved full-model traces (SNTv0001, layers 0/1/35/36); gate, up
and down are decoded from the GGUF in float32, so h is recomputed in Python and
checked against the replayed h. Errors: relative L2 of the routed expert sum
per (position, layer), the same screen as the static arm. No calibration is
used at all, so there is no train/test split to leak. Not t/s, not generation.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / '20261004_ngram_memory'))
import analyze_head_tail as AHT
import trace_io

HIDDEN, FF, TOPK = 2560, 640, 10
LAYERS = (0, 1, 35, 36)
TEXTS = ('code', 'explain', 'reason')
KEEPS = (0.3, 0.4, 0.5, 0.6, 0.7)
SCORES = ('gate', 'gate_n', 'up_n', 'oracle')
FULL_TOP = (0, 1, 2)
GU_BLOCK = {16: (256, 66), 17: (256, 74), 18: (256, 98)}


class Weights:
    def __init__(self, model, fork):
        sys.path.insert(0, str(fork / 'tools'))
        from gguf_reader import GGUFFile
        from gguf import quants, GGMLQuantizationType
        self.quants, self.Q = quants, GGMLQuantizationType
        paths = [model, model.with_name(model.name.replace('-00001-of-00002', '-00002-of-00002'))]
        self.src = {}
        for p in paths:
            gg = GGUFFile(p)
            for t in gg.tensors:
                for layer in LAYERS:
                    for nm in ('gate', 'up', 'down'):
                        if t.name == f'blk.{layer}.ffn_{nm}_exps.weight':
                            self.src[(layer, nm)] = (p, gg.data_start + t.offset, t.type_id)
        assert len(self.src) == 3 * len(LAYERS)

    def expert(self, layer, e):
        out = {}
        for nm in ('gate', 'up'):
            p, base, kind = self.src[(layer, nm)]
            blk, bb = GU_BLOCK[kind]
            rb = HIDDEN // blk * bb
            with p.open('rb') as f:
                f.seek(base + e * FF * rb)
                raw = np.frombuffer(f.read(FF * rb), np.uint8).reshape(FF, rb)
            out[nm] = self.quants.dequantize(raw, self.Q(kind)).astype(np.float32)
            out['gu_row_bytes'], out['gu_type'] = rb, kind
        p, base, kind = self.src[(layer, 'down')]
        size = HIDDEN * (FF // (32 if kind == 20 else 64)) * 18
        with p.open('rb') as f:
            f.seek(base + e * size)
            out['down'] = AHT.decode_down(f.read(size), kind)
        out['down_type'], out['down_bytes'] = kind, size
        return out


def silu(v):
    return v / (1.0 + np.exp(-v))


def run(args):
    lab, t0 = Path(args.lab), time.time()
    W = Weights(Path(args.model), Path(args.fork))
    results, checks, bytes_model = [], {}, {}
    for text in TEXTS:
        rows = trace_io.read_rows(lab / text / 'trace.snt')
        snr = AHT.load_text(lab, text)
        for layer in LAYERS:
            P = len(rows)
            X = np.stack([r['layers'][layer]['x'] for r in rows]).astype(np.float32)
            ids = np.stack([r['layers'][layer]['ids'] for r in rows])
            wts = np.stack([r['layers'][layer]['weights'] for r in rows]).astype(np.float32)
            pos = np.array([r['pos'] for r in rows])
            assert np.allclose(wts.sum(1), 1, atol=1e-4)
            rank = np.argsort(np.argsort(-wts, axis=1, kind='stable'), axis=1)
            # replayed h for the check, keyed by (pos, expert)
            sel = snr['layer'] == layer
            ref = {(int(p), int(e)): i for i, (p, e) in enumerate(zip(snr['pos'][sel], snr['expert'][sel]))}
            ref_h = snr['h'][sel]
            y = np.zeros((P, TOPK, HIDDEN), np.float32)
            drop = {(s, k): np.zeros((P, TOPK, HIDDEN), np.float32) for s in SCORES for k in KEEPS}
            hcheck, touched = [], {k: [] for k in KEEPS}
            geo = None
            for e in np.unique(ids):
                pi, si = np.nonzero(ids == e)
                w = W.expert(layer, int(e))
                geo = geo or (w['gu_row_bytes'], w['down_type'], w['down_bytes'])
                x = X[pi]
                g, u = x @ w['gate'].T, x @ w['up'].T
                h = silu(g) * u
                D = w['down']
                y[pi, si] = h @ D.T
                for j, p in enumerate(pos[pi]):
                    i = ref.get((int(p), int(e)))
                    if i is not None:
                        hcheck.append(np.linalg.norm(h[j] - ref_h[i]) / max(np.linalg.norm(ref_h[i]), 1e-30))
                dn = np.linalg.norm(D, axis=0)[None, :]
                un = np.linalg.norm(w['up'], axis=1)[None, :]
                sg = np.abs(silu(g))
                score = {'gate': sg, 'gate_n': sg * un * dn, 'up_n': np.abs(u) * dn, 'oracle': np.abs(h) * dn}
                for s in SCORES:
                    order = np.argsort(-score[s], axis=1, kind='stable')
                    for k in KEEPS:
                        m = np.ones_like(h, dtype=bool)
                        np.put_along_axis(m, order[:, :int(round(k * FF))], False, axis=1)
                        drop[(s, k)][pi, si] = (h * m) @ D.T
                        if s == 'gate':  # down blocks touched by a dynamic selection, original layout
                            blk = 32 if w['down_type'] == 20 else 64
                            kept = ~m
                            touched[k].append(kept.reshape(len(pi), FF // blk, blk).any(axis=2).mean(axis=1))
            hc = np.array(hcheck)
            checks[f'{text}:{layer}'] = {'h_py_vs_replay_p50': float(np.median(hc)),
                                         'h_py_vs_replay_p99': float(np.quantile(hc, 0.99)),
                                         'matched_calls': int(hc.size)}
            rb, dt, dbytes = geo
            full = 2 * FF * rb + dbytes
            bytes_model[layer] = {'gu_row_bytes': rb, 'down_type': dt, 'full_expert_bytes': full,
                                  'gate_share': FF * rb / full}
            routed = np.einsum('pk,pkd->pd', wts, y, dtype=np.float64)
            rn = np.linalg.norm(routed, axis=1)
            for (s, k), dv in drop.items():
                for r in FULL_TOP:
                    pruned = (rank >= r).astype(np.float32) * wts
                    err = np.einsum('pk,pkd->pd', pruned, dv, dtype=np.float64)
                    e = np.linalg.norm(err, axis=1) / rn
                    frac_full = r / TOPK
                    blocks = float(np.concatenate(touched[k]).mean())
                    results.append({'text': text, 'layer': layer, 'score': s, 'keep': k, 'full_top': r,
                                    'mean': float(e.mean()), 'p99': float(np.quantile(e, 0.99)),
                                    'max': float(e.max()),
                                    # bytes read per call relative to the full expert
                                    'bytes_transposed_down': frac_full + (1 - frac_full) *
                                        (FF * rb + k * FF * rb + k * dbytes) / full,
                                    'bytes_original_down': frac_full + (1 - frac_full) *
                                        (FF * rb + k * FF * rb + blocks * dbytes) / full,
                                    'down_blocks_touched': blocks})
            print(f'{text} L{layer}: h check p50 {checks[f"{text}:{layer}"]["h_py_vs_replay_p50"]:.2e} '
                  f'({hc.size} calls) {time.time()-t0:.0f}s', flush=True)
    Path(args.output).write_text(json.dumps({'protocol': __doc__, 'checks': checks, 'bytes': bytes_model,
                                             'results': results, 'elapsed_s': time.time() - t0}, indent=1))
    print('written', args.output)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lab', required=True)
    ap.add_argument('--fork', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--output', required=True)
    run(ap.parse_args())
