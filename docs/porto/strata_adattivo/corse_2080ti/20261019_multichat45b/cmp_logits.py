"""Confronta i logit del primo token di ogni richiesta (fl.<n>) fra bracci di mc45b_det.py:
    python cmp_logits.py <controllo> <braccio> [...]     bit a bit?, max|d|, KL(controllo||braccio), argmax uguale"""
import sys
from pathlib import Path
import numpy as np

H = Path(__file__).resolve().parent
NAMES = ['w', 's0', 's1', 's2', 'l0', 'l1', 'l2']


def lg(t, n):
    f = H / f'mc45b_{t}' / f'fl.{n}'
    return np.fromfile(f, dtype=np.float32) if f.exists() else None


def lsm(x):
    x = x.astype(np.float64)
    m = x.max()
    return x - m - np.log(np.exp(x - m).sum())


ctl = sys.argv[1]
for t in sys.argv[2:]:
    print(f'{t} contro {ctl}')
    for n, nm in enumerate(NAMES):
        a, b = lg(ctl, n), lg(t, n)
        if a is None or b is None:
            print(f'  {nm}: manca')
            continue
        la, lb = lsm(a), lsm(b)
        kl = float((np.exp(la) * (la - lb)).sum())
        print(f'  {nm}: bit a bit {np.array_equal(a, b)}  max|d| {float(np.abs(a - b).max()):.5f}  KL {kl:.3e}  argmax {int(a.argmax()) == int(b.argmax())}')
