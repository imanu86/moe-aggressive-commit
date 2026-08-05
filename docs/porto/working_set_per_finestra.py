import os, numpy as np
D = r'D:\ds4_work\dump'
idx = {}
for l in open(os.path.join(D,'INDICE.tsv')):
    p = l.rstrip('\n').split('\t')
    if p[0]=='file': continue
    idx.setdefault(p[1], []).append((int(p[2]), p[0], p[3], [int(x) for x in p[4:8]]))
def leggi(n):
    pz=[]
    for _, f, tipo, ne in sorted(idx[n]):
        dt = np.float32 if tipo=='f32' else np.int32
        d = np.fromfile(os.path.join(D,f), dtype=dt); a,b = ne[0],ne[1]
        if d.size==a*b: pz.append(d.reshape(b,a))
        else:
            s=(d.size-a)//(b-1); pz.append(np.stack([d[t*s:t*s+a] for t in range(b)]))
    return np.concatenate(pz,axis=0)
V = {L: leggi(f'ffn_moe_topk-{L}') for L in range(43) if f'ffn_moe_topk-{L}' in idx}
T = min(v.shape[0] for v in V.values())
MIB = 6.75
print(f'{"finestra":>9} {"distinti TOTALI":>16} {"GiB":>7} {"NUOVI per token":>16} {"GiB/token":>10}')
for W in (1, 2, 4, 8, 16, 32, 64, 128):
    dist, nuovi = [], []
    for t0 in range(0, T-W, max(W,1)):
        s = set()
        for L in V:
            s |= set((L<<16)|int(e) for e in V[L][t0:t0+W].ravel())
        dist.append(len(s))
    # nuovi: quanti (strato,esperto) del token t non sono apparsi nei W precedenti
    for t in range(W, min(T, 400)):
        prec = set()
        for L in V:
            prec |= set((L<<16)|int(e) for e in V[L][t-W:t].ravel())
        ora = set()
        for L in V:
            ora |= set((L<<16)|int(e) for e in V[L][t].ravel())
        nuovi.append(len(ora - prec))
    dm, nm = np.mean(dist), np.mean(nuovi)
    print(f'{W:9d} {dm:16.0f} {dm*MIB/1024:7.2f} {nm:16.0f} {nm*MIB/1024:10.3f}')
