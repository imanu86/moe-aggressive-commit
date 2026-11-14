"""Quota del peso del router sugli esperti fuori dalle schede: profilo (ordine di residenza) + traccia --dump-routing."""
import struct, sys, numpy as np
prof = open(r'D:\ds4_work\strata\Strata\data\expert-profile.bin', 'rb').read()
ver, nl, ne, slots, n = struct.unpack_from('<5I', prof, 4)
rank = np.full((nl, ne), 10**9)
for i in range(n):
    l, e = struct.unpack_from('<HH', prof, 24 + 4 * i); rank[l, e] = i
for path in sys.argv[1:]:
    b = open(path, 'rb').read(); off = 0; L = []; E = []; W = []; K = None
    while off + 8 <= len(b):
        l, k = struct.unpack_from('<ii', b, off); off += 8
        ids = struct.unpack_from('<%di' % k, b, off); off += 4 * k
        w = struct.unpack_from('<%df' % k, b, off); off += 4 * k
        L += [l] * k; E += ids; W += w; K = k
    L, E, W = np.array(L), np.array(E), np.array(W)
    ok = np.isfinite(W); print("  pesi validi", round(100*ok.mean(),1), "%"); W = np.where(ok, W, 0); r = rank[L, E]; tot = W.sum(); toks = len(W) // K
    print(f'{path}: {toks} righe token-strato, k={K}')
    for N in (13323, 17491, 19565, 22000):
        fuori = r >= N
        print(f'  primi {N} sulle schede ({100*N/nl/ne:.0f}%): peso fuori {100*W[fuori].sum()/tot:.2f}%, scelte fuori {100*fuori.mean():.2f}%, '
              f'token-strato con almeno uno fuori {100*fuori.reshape(-1,K).any(1).mean():.1f}%')
    fu = (r >= 19565).reshape(-1, K)
    print('  scelte fuori per posizione nella lista del router (1..10):', ' '.join(f'{100*x:.1f}' for x in fu.mean(0)))
