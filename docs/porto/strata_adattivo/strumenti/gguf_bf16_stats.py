"""Statistiche dei tensori BF16 di un GGUF (sola lettura, campionata): quanto perde la conversione BF16 -> FP16
senza scala (come STRATA_BF16_TC) e con una scala potenza di due per tensore o per riga."""
import struct, sys, re, collections
import numpy as np

SAMPLE = 1 << 20   # elementi letti al massimo per tensore

def rd(f, fmt):
    s = struct.calcsize('<' + fmt)
    return struct.unpack('<' + fmt, f.read(s))

def rstr(f):
    (n,) = rd(f, 'Q')
    return f.read(n).decode('utf-8', 'replace')

def rval(f, t):
    if t == 8: return rstr(f)
    if t == 9:
        (at, n) = rd(f, 'IQ')
        return [rval(f, at) for _ in range(n)]
    fmt = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}[t]
    return rd(f, fmt)[0]

def tensors(path):
    with open(path, 'rb') as f:
        assert f.read(4) == b'GGUF'
        (ver, nt, nkv) = rd(f, 'IQQ')
        align = 32
        for _ in range(nkv):
            k = rstr(f); (t,) = rd(f, 'I'); v = rval(f, t)
            if k == 'general.alignment': align = v
        out = []
        for _ in range(nt):
            name = rstr(f); (nd,) = rd(f, 'I'); dims = rd(f, 'Q' * nd); (ty, off) = rd(f, 'IQ')
            out.append((name, dims, ty, off))
        base = (f.tell() + align - 1) // align * align
    return [(n, d, t, base + o, path) for (n, d, t, o) in out]

def f16_err(w, scale_mode):
    """w float32 2-D [rows, cols]; returns (rel L2 err, frac subnormal, frac flushed, frac overflow)"""
    a = np.abs(w)
    if scale_mode == 'none':
        s = np.ones((w.shape[0], 1), np.float32)
    elif scale_mode == 'tensor':
        m = a.max()
        e = np.floor(np.log2(m)) if m > 0 else 0
        s = np.full((w.shape[0], 1), 2.0 ** (14 - e), np.float32)
    else:  # row
        m = a.max(axis=1, keepdims=True); m[m == 0] = 1
        s = (2.0 ** (14 - np.floor(np.log2(m)))).astype(np.float32)
    ws = w * s
    h = np.clip(ws, -65504, 65504).astype(np.float16).astype(np.float32) / s
    err = np.linalg.norm(h - w) / max(np.linalg.norm(w), 1e-30)
    aws = np.abs(ws)
    nz = aws > 0
    sub = np.mean((aws < 2.0 ** -14) & nz); flush = np.mean((aws < 2.0 ** -25) & nz); ovf = np.mean(aws > 65504)
    return err, sub, flush, ovf

def main(paths):
    allt = []
    for p in paths: allt += tensors(p)
    bf = [t for t in allt if t[2] == 30]
    types = collections.Counter(t[2] for t in allt)
    print('tensori', len(allt), 'tipi', dict(types))
    groups = collections.defaultdict(list)
    for (n, d, ty, off, p) in bf:
        key = re.sub(r'blk\.\d+\.', 'blk.N.', n)
        groups[key].append((n, d, off, p))
    print(f"{'gruppo':42s} {'n':>3s} {'forma':>16s} {'MB tot':>8s} {'max|w|':>9s} {'mediana':>9s} | "
          f"{'err none':>9s} {'sub%':>6s} {'flush%':>7s} | {'err tens':>9s} | {'err riga':>9s}")
    for key in sorted(groups):
        g = groups[key]
        n, d, off, p = g[len(g) // 2]   # un layer centrale come campione
        cols = d[0]; rows = int(np.prod(d[1:])) if len(d) > 1 else 1
        tot = sum(int(np.prod(x[1])) for x in g) * 2 / 1e6
        take_rows = max(1, min(rows, SAMPLE // cols))
        # righe distribuite: un blocco all'inizio, uno a metà
        with open(p, 'rb') as f:
            parts = []
            for r0 in sorted(set([0, max(0, rows // 2 - take_rows // 2)])):
                nr = min(take_rows // 2 or 1, rows - r0)
                f.seek(off + r0 * cols * 2)
                parts.append(np.frombuffer(f.read(nr * cols * 2), dtype=np.uint16).reshape(nr, cols))
        u = np.concatenate(parts)
        w = (u.astype(np.uint32) << 16).view(np.float32)
        a = np.abs(w)
        e0 = f16_err(w, 'none'); e1 = f16_err(w, 'tensor'); e2 = f16_err(w, 'row')
        print(f"{key:42s} {len(g):3d} {str(tuple(d)):>16s} {tot:8.1f} {a.max():9.3g} {np.median(a):9.3g} | "
              f"{e0[0]:9.2e} {100*e0[1]:6.2f} {100*e0[2]:7.3f} | {e1[0]:9.2e} | {e2[0]:9.2e}")

if __name__ == '__main__':
    main(sys.argv[1:])
