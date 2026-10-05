"""PLE hot rows, second pass: where is the ceiling?  Same corpora, cache and tests as ple_hot_sim.py.

- larger pinned sets (4M, 8M rows = 360/720 MB, and every row the training corpus ever touched);
- the base misses split by head kind (bigram heads 0-7, trigram heads 8-15) and by whether the training corpus
  touched the row at all (the most any profile from this corpus could save).
"""
import time
from collections import Counter

import numpy as np

import ple_hot_sim as S


def main():
    t0 = time.time()
    tok = S.tokenizer()
    files = S.corpus_files()
    train, tests = [], {}
    for k, fl in files.items():
        tr = S.encode_files(tok, [p for i, p in enumerate(fl) if i % 5], 6_000_000)
        ho = S.encode_files(tok, [p for i, p in enumerate(fl) if i % 5 == 0], 140_000)
        train += tr
        tests[f'held-out {k}'] = np.concatenate(ho)[:131072]
    import gzip
    tests['ctx131k'] = np.frombuffer(gzip.decompress((S.FIX / 'ids/ctx131k.ids.bin.gz').read_bytes()), dtype='<i4')
    cnt = Counter()
    for a in train:
        if len(a):
            u, c = np.unique(S.rows_of(a).reshape(-1), return_counts=True)
            cnt.update(dict(zip(u.tolist(), c.tolist())))
    ranked = np.array([r for r, _ in cnt.most_common()], dtype=np.uint32)
    seen = np.sort(ranked)
    once = int(sum(1 for v in cnt.values() if v == 1))
    print(f'addestramento: {sum(map(len, train))} token, {len(ranked)} righe distinte, {once} viste una volta sola',
          flush=True)
    for name, toks in tests.items():
        rows = S.rows_of(toks)
        b = S.simulate(rows, S.CACHE_ROWS, None)
        line = [f'{name}: base {b["misses"]}']
        for K in (4 << 20, 8 << 20):
            v = S.simulate(rows, S.CACHE_ROWS, np.sort(ranked[:K]))
            line.append(f'hot{K >> 20}M {v["misses"] / b["misses"]:.0%}')
        v = S.simulate(rows, S.CACHE_ROWS, seen)
        line.append(f'tutte le {len(seen) >> 20}M viste {v["misses"] / b["misses"]:.0%}')
        print('  '.join(line), flush=True)
        # the base misses (first-time rows of the stream, in-batch duplicates once) by head kind
        flat = rows.reshape(-1)
        head = np.tile(np.arange(16), len(rows))
        _, first = np.unique(flat, return_index=True)
        fr, fh = flat[first], head[first]
        in_train = np.isin(fr, seen)
        for kind, sel in (('bigramma', fh < 8), ('trigramma', fh >= 8)):
            print(f'    righe nuove {kind}: {int(sel.sum())}, di cui nel corpus {int((sel & in_train).sum())} '
                  f'({(sel & in_train).sum() / max(sel.sum(), 1):.0%})', flush=True)
    print(f'fatto in {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
