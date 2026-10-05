"""Are two GGUFs' experts the same weights?  Row cosine and relative error of dequantized expert matrices.

Reference: our IQ3_XXS GSQ-RCO model (local, full). Others: the slice GGUFs from hf_slice.py.
If a variant stored its experts in another basis (a rotation, a permutation) the cosine would collapse to ~0;
same base weights at different bit widths give ~0.9+.
"""
import sys
import numpy as np
from gguf import GGMLQuantizationType as Q
from gguf.quants import dequantize

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from hf_slice import parse, QS

NAMES = {16: 'IQ2_XXS', 17: 'IQ2_XS', 18: 'IQ3_XXS', 20: 'IQ4_NL', 21: 'IQ3_S', 22: 'IQ2_S', 23: 'IQ4_XS', 42: 'Q2_0', 8: 'Q8_0'}
E = 8


def open_gguf(path):
    with open(path, 'rb') as f:
        head = f.read(64 << 20)
    _, _, tens, start = parse(head)
    return path, {t['name']: dict(t, abs=start + t['off']) for t in tens}


def q2_0(raw, rows, cols):
    b = raw.reshape(rows, cols // 64, 18)
    d = b[:, :, :2].copy().view(np.float16).astype(np.float32)          # (rows, nb, 1)
    c = b[:, :, 2:]
    codes = np.stack([(c >> (2 * k)) & 3 for k in range(4)], axis=-1).reshape(rows, cols // 64, 64)
    return (d * (codes.astype(np.float32) - 1.0)).reshape(rows, cols)


def expert(g, name, e):
    path, tens = g
    t = tens[name]
    blk, tsz = QS[t['type']]
    cols, rows = t['ne'][0], t['ne'][1]
    rb = cols // blk * tsz
    with open(path, 'rb') as f:
        f.seek(t['abs'] + e * rows * rb)
        raw = np.frombuffer(f.read(rows * rb), dtype=np.uint8).reshape(rows, rb)
    if t['type'] == 42:
        return q2_0(raw, rows, cols), t['type']
    return dequantize(raw, Q(t['type'])).reshape(rows, cols).astype(np.float32), t['type']


def main():
    ours = open_gguf(r'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf')
    others = {'ISTA IQ3_S': open_gguf(r'C:\Users\imanu\Downloads\strata_slices\iq3s_L0-1-35_e48.gguf'),
              'unsloth UD-IQ4_XS': open_gguf(r'C:\Users\imanu\Downloads\strata_slices\udiq4xs_L0-1-35_e48.gguf')}
    print(f'{"tensore":30s} {"nostro":8s} {"altro":22s} {"tipo":8s} {"cos riga":>9s} {"err rel":>8s}')
    for L in (0, 1, 35):
        for role in ('gate', 'up', 'down'):
            name = f'blk.{L}.ffn_{role}_exps.weight'
            for label, g in others.items():
                cs, er = [], []
                for e in range(E):
                    a, ta = expert(ours, name, e)
                    b, tb = expert(g, name, e)
                    num = (a * b).sum(1)
                    cs.append(np.median(num / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-30)))
                    er.append(np.linalg.norm(a - b) / np.linalg.norm(b))
                print(f'{name:30s} {NAMES.get(ta, ta):8s} {label:22s} {NAMES.get(tb, tb):8s} {np.mean(cs):9.4f} {np.mean(er):8.3f}',
                      flush=True)
    # the two downloads against each other, layer 35 (both IQ3_S gate/up)
    a_, b_ = others['ISTA IQ3_S'], others['unsloth UD-IQ4_XS']
    for role in ('gate', 'up', 'down'):
        name = f'blk.35.ffn_{role}_exps.weight'
        cs = []
        for e in range(E):
            a, _ = expert(a_, name, e); b, _ = expert(b_, name, e)
            cs.append(np.median((a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-30)))
        print(f'{name:30s} ISTA IQ3_S vs unsloth IQ3_S: cos riga {np.mean(cs):.4f}')


if __name__ == '__main__':
    main()
