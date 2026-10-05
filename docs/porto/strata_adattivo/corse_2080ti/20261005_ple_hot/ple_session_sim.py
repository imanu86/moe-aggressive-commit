"""PLE rows, third pass: a larger DYNAMIC row cache (--ple-row-cache, an existing option) in a warm session.

A Daily server lives for hours: before a prompt it has already read other material of the same project.  Session =
the project's training files (up to `history` tokens, in order, each file its own stream) then the held-out 131k
test.  Arms: dynamic cache 1M (today), 4M, 16M rows (95 MB, 360 MB, 1.4 GB), cold (no history) and warm.
"""
import time

import numpy as np

import ple_hot_sim as S


def run(history_rows, test_rows, cache_rows):
    """Warm the cache with history (counted apart), then measure the test.  Same chunk semantics as simulate()."""
    sets = cache_rows // S.WAYS
    keys = np.full(sets * S.WAYS, 0xFFFFFFFF, dtype=np.uint32)
    nxt = np.zeros(sets, dtype=np.int64)

    def feed(rows):
        misses = 0
        for c0 in range(0, len(rows), S.CHUNK):
            r = rows[c0:c0 + S.CHUNK].reshape(-1)
            s = S.set_of(r, sets)
            need = ~(keys.reshape(sets, S.WAYS)[s] == r[:, None]).any(axis=1)
            first = r[need]
            _, idx = np.unique(first, return_index=True)
            order = first[np.sort(idx)]
            misses += len(order)
            for row, sidx in zip(order.tolist(), S.set_of(order, sets).tolist()):
                w = int(nxt[sidx])
                nxt[sidx] = (w + 1) % S.WAYS
                keys[sidx * S.WAYS + w] = row
        return misses

    for h in history_rows:
        feed(h)
    return feed(test_rows)


def main():
    t0 = time.time()
    tok = S.tokenizer()
    files = S.corpus_files()
    for k, fl in files.items():
        hist = S.encode_files(tok, [p for i, p in enumerate(fl) if i % 5], 2_000_000)
        test = np.concatenate(S.encode_files(tok, [p for i, p in enumerate(fl) if i % 5 == 0], 140_000))[:131072]
        hist_rows = [S.rows_of(a) for a in hist if len(a)]
        test_rows = S.rows_of(test)
        base = run([], test_rows, S.CACHE_ROWS)
        out = [f'{k}: storia {sum(map(len, hist))} token; freddo 1M {base}']
        for cr in (1 << 20, 4 << 20, 16 << 20):
            m = run(hist_rows, test_rows, cr)
            out.append(f'caldo {cr >> 20}M {m} ({m / base:.0%})')
        print('  '.join(out), f'[{time.time() - t0:.0f} s]', flush=True)


if __name__ == '__main__':
    main()
