"""Tasso di hit per stadio dalla traccia di instradamento (--dump-routing) di una corsa di decode a 131K.

    python routing_stage0.py routing.bin PROFILE.bin [--split 16] [--s1 9145] [--slots 2200,2800,3526,3874,4176,5000,6000,7000,7900,8192]

Record = int32 layer, int32 k, k int32 id, k float32 peso (una riga per token e per layer).  Un gruppo = run di righe consecutive con lo stesso layer
(una chiamata del pool per quel layer e finestra).  Per lo stadio 0 (layer < split) si prova una cache statica fatta dei primi S accoppiamenti
(layer, esperto) del profilo con layer < split (e' il modo in cui il motore riempie la scheda, esclusa l'adattamento), e come confronto il migliore
possibile sulla traccia stessa (oracolo statico, limite alto).  Misura: quota di (token, esperto) serviti dalla VRAM e esperti distinti mancanti per
chiamata di layer (quelli che costano un trasferimento o un calcolo sulla CPU).  Lo stadio 1 e' fissato a --s1 slot (il suo 9 145 reale).
"""
import argparse, sys
import numpy as np

NL, NE = 48, 512


def load(path):
    raw = np.fromfile(path, dtype=np.int32)
    k = int(raw[1]); rec = 2 + 2 * k
    raw = raw[: (len(raw) // rec) * rec].reshape(-1, rec)
    return raw[:, 0].copy(), raw[:, 2:2 + k].copy(), k


def profile(path):
    with open(path, 'rb') as f:
        assert f.read(4) == b'STRP'
        hdr = np.frombuffer(f.read(20), dtype=np.uint32)
        n = int(hdr[4])
        return np.frombuffer(f.read(4 * n), dtype=np.uint16).reshape(-1, 2).astype(np.int64)


def evaluate(layer, ids, gid, mask_rows, resident):
    """-> (quota hit entries, esperti distinti mancanti per chiamata, chiamate) sulle righe in mask_rows."""
    L = layer[mask_rows]; I = ids[mask_rows]; G = gid[mask_rows]
    hit = resident[L[:, None], I]
    ent = I.size
    # distinti per gruppo: chiave (gruppo, esperto), vale la prima occorrenza
    key = G[:, None].astype(np.int64) * NE + I
    flat = key.ravel(); miss_flat = (~hit).ravel()
    uk, idx = np.unique(flat, return_index=True)
    dist_miss = int(miss_flat[idx].sum())
    ngroups = len(np.unique(G))
    return hit.sum() / ent, dist_miss / max(ngroups, 1), ngroups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trace'); ap.add_argument('profile')
    ap.add_argument('--split', type=int, default=16)
    ap.add_argument('--s1-real', type=int, default=7554)
    ap.add_argument('--s1', type=int, default=9145)
    ap.add_argument('--slots', default='1500,2200,2800,3526,3874,4176,5000,6000,7000,7900,8192')
    a = ap.parse_args()
    layer, ids, k = load(a.trace)
    chg = np.flatnonzero(np.diff(layer) != 0) + 1
    gid = np.zeros(len(layer), np.int64)
    gid[chg] = 1
    gid = np.cumsum(gid)
    rows0 = layer < a.split
    rows1 = ~rows0
    print(f'righe {len(layer)}, k {k}, chiamate di layer {gid[-1] + 1}, righe stadio 0 {rows0.sum()} ({rows0.mean() * 100:.1f}%)')
    prof = profile(a.profile)
    # popolarita' sulla traccia (oracolo)
    cnt = np.zeros((NL, NE))
    np.add.at(cnt, (np.repeat(layer, k), ids.ravel()), 1.0)
    # stadio 1 fisso
    p1 = prof[prof[:, 0] >= a.split][:a.s1]
    r1 = np.zeros((NL, NE), bool); r1[p1[:, 0], p1[:, 1]] = True
    h1, m1, g1 = evaluate(layer, ids, gid, rows1, r1)
    print(f'stadio 1 ({a.s1} slot, profilo): hit {h1 * 100:.2f}%, esperti distinti mancanti per chiamata {m1:.3f}')
    print('| slot stadio 0 | profilo statico: hit % | mancanti/chiamata | oracolo (traccia): hit % | mancanti/chiamata |')
    print('|---:|---:|---:|---:|---:|')
    p0 = prof[prof[:, 0] < a.split]
    c0 = cnt.copy(); c0[a.split:] = -1
    order = np.argsort(-c0.ravel(), kind='stable')
    out = []
    for S in [int(x) for x in a.slots.split(',')]:
        r0 = np.zeros((NL, NE), bool); r0[p0[:S, 0], p0[:S, 1]] = True
        h, m, g = evaluate(layer, ids, gid, rows0, r0)
        ro = np.zeros((NL, NE), bool); ro.ravel()[order[:S]] = True
        ho, mo, _ = evaluate(layer, ids, gid, rows0, ro)
        out.append((S, h, m, ho, mo))
        print(f'| {S} | {h * 100:.2f} | {m:.3f} | {ho * 100:.2f} | {mo:.3f} |')
    # stadio 1 con l'oracolo (cache = i 7554 esperti piu' usati dalla traccia fra i layer >= split) e previsione globale per confronto col motore
    c1 = cnt.copy(); c1[:a.split] = -1
    o1 = np.argsort(-c1.ravel(), kind='stable')
    r1o = np.zeros((NL, NE), bool); r1o.ravel()[o1[:a.s1_real]] = True
    h1o, m1o, _ = evaluate(layer, ids, gid, rows1, r1o)
    print(f'stadio 1 oracolo a {a.s1_real} slot: hit {h1o * 100:.2f}%, mancanti/chiamata {m1o:.3f}')
    print('| slot stadio 0 | previsione CPU esperti/chiamata (globale, oracolo + oracolo) | idem profilo statico stadio 0 + oracolo stadio 1 |')
    print('|---:|---:|---:|')
    for S, h, m, ho, mo in out:
        print(f'| {S} | {(16 * mo + 32 * m1o) / 48:.2f} | {(16 * m + 32 * m1o) / 48:.2f} |')
    # quota stadio 0 nel totale e hit complessivo con stadio 0 a 3874 (confronto col dato del motore)
    print(f'nota: stadio 0 = {rows0.mean() * 100:.1f}% delle righe; hit complessivo con stadio 0 a 3874 slot e stadio 1 a {a.s1}: '
          f'{(rows0.mean() * [o for o in out if o[0] == 3874][0][1] + (1 - rows0.mean()) * h1) * 100 if any(o[0] == 3874 for o in out) else float("nan"):.2f}%')


if __name__ == '__main__':
    main()
