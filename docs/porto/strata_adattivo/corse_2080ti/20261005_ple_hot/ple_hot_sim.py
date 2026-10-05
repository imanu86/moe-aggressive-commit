"""PLE hot rows (handoff 5/10 sera, §6.5): how many SSD row reads would a set of pinned hot rows save?

Offline, no engine: the engine's own row hash (ngram_rows: 16 heads, bigram 0-7, trigram 8-15, EOS/NULL cut) and
an exact copy of its row cache (PleReader's RowCache: 8 ways, round-robin per set, 1,048,576 rows).  Prefill
semantics as gather_batch: per 8192-token chunk, look up every row against the cache as it was at the chunk start,
read the missing rows (counted as rows and as distinct 4 KiB pages: the engine reads pages), then insert them.

Hot set = the K most frequent rows of a TRAINING corpus that does not contain the test text.  Arms per test:
  base        dynamic cache 1M rows (the Daily)
  hot+1M      K pinned rows + dynamic 1M     (RAM +K*90 B)
  hot+(1M-K)  K pinned rows + dynamic 1M-K   (same RAM as today)

    python ple_hot_sim.py            corpora from the repos below, tests from the P0 fixtures
"""
import gzip, json, sys, time
from collections import Counter
from pathlib import Path

import numpy as np

FORK = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
TOKDIR = Path(r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs\tokenizer')
FIX = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0\fixtures')
OUT = Path(__file__).resolve().parent

MULT = np.array([23703573157769, 20109073645365, 8052911324071], dtype=np.uint64)
VOCAB = np.array([20000003, 20000023, 20000033, 20000047, 20000059, 20000063, 20000069, 20000077,
                  20000081, 20000093, 20000107, 20000147, 20000153, 20000159, 20000161, 20000171], dtype=np.uint64)
OFFSET = np.array([0, 20000003, 40000026, 60000059, 80000106, 100000165, 120000228, 140000297,
                   160000374, 180000455, 200000548, 220000655, 240000802, 260000955, 280001114, 300001275], dtype=np.uint64)
EOS = 248044
ROW_BYTES, TABLE_OFF, PAGE = 90, 192, 4096
CACHE_ROWS, WAYS, CHUNK = 1 << 20, 8, 8192


def rows_of(tokens: np.ndarray) -> np.ndarray:
    """(n, 16) uint32 row indices, as ngram_rows with the stream's own predecessors (start of stream = NULL)."""
    t = tokens.astype(np.int64)
    p1 = np.concatenate([[-1], t[:-1]])
    p2 = np.concatenate([[-1, -1], t[:-2]])
    cut1 = (p1 < 0) | (p1 == EOS)
    c1 = np.where(cut1, EOS, p1)
    cut2 = cut1 | (p2 < 0) | (p2 == EOS)
    c2 = np.where(cut2, EOS, p2)
    with np.errstate(over='ignore'):
        m2 = (t.astype(np.uint64) * MULT[0]) ^ (c1.astype(np.uint64) * MULT[1])
        m3 = m2 ^ (c2.astype(np.uint64) * MULT[2])
    out = np.empty((len(t), 16), dtype=np.uint32)
    for h in range(8):
        out[:, h] = (m2 % VOCAB[h] + OFFSET[h]).astype(np.uint32)
        out[:, 8 + h] = (m3 % VOCAB[8 + h] + OFFSET[8 + h]).astype(np.uint32)
    return out


def set_of(rows: np.ndarray, sets: int) -> np.ndarray:
    with np.errstate(over='ignore'):
        x = rows.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)
    x ^= x >> np.uint64(29)
    return (x % np.uint64(sets)).astype(np.int64)


def simulate(rows: np.ndarray, cache_rows: int, hot: np.ndarray | None) -> dict:
    """rows: (n, 16).  Returns lookups, row misses (SSD rows) and distinct pages read."""
    sets = cache_rows // WAYS
    keys = np.full(sets * WAYS, 0xFFFFFFFF, dtype=np.uint32) if sets else None
    nxt = np.zeros(max(sets, 1), dtype=np.int64)
    lookups = misses = pages = 0
    for c0 in range(0, len(rows), CHUNK):
        r = rows[c0:c0 + CHUNK].reshape(-1)
        lookups += len(r)
        need = np.ones(len(r), dtype=bool)
        if hot is not None and len(hot):
            need &= ~np.isin(r, hot, assume_unique=False)
        if sets:
            s = set_of(r, sets)
            ways = keys.reshape(sets, WAYS)[s]                  # cache state at the chunk start
            need &= ~(ways == r[:, None]).any(axis=1)
        miss = np.unique(r[need])                              # in-batch duplicates read once
        misses += len(miss)
        if len(miss):
            off = TABLE_OFF + miss.astype(np.int64) * ROW_BYTES
            pg = np.unique(np.concatenate([off // PAGE, (off + ROW_BYTES - 1) // PAGE]))
            pages += len(pg)
        if sets and len(miss):
            # insert in the order the batch asked for them (first occurrence), round-robin inside the set
            first = r[need]
            _, idx = np.unique(first, return_index=True)
            order = first[np.sort(idx)]
            kl, nl = keys, nxt
            for row, sidx in zip(order.tolist(), set_of(order, sets).tolist()):
                base = sidx * WAYS
                w = int(nl[sidx])
                nl[sidx] = (w + 1) % WAYS
                kl[base + w] = row
    return dict(lookups=lookups, misses=misses, pages=pages, hit=1 - misses / max(lookups, 1))


def tokenizer():
    sys.path[:0] = [str(FORK / 'tools')]
    from strata_tokenizer import Tokenizer
    vocab = json.loads((TOKDIR / 'vocab.json').read_text(encoding='utf-8'))
    toks = [None] * len(vocab)
    for tk, i in vocab.items():
        toks[i] = tk
    return Tokenizer(toks, (TOKDIR / 'merges.txt').read_text(encoding='utf-8').splitlines(),
                     json.loads((TOKDIR / 'token_type.json').read_text(encoding='utf-8')))


def corpus_files() -> dict[str, list[Path]]:
    def pick(root, pats, skip=('\\build', '\\bin\\', '\\obj\\', '\\.git', 'node_modules', '_deps', '\\.vs\\',
                               '__pycache__', '\\worktrees', '\\.codex_runs', '\\corse_2080ti\\')):
        out = []
        for pat in pats:
            for p in Path(root).rglob(pat):
                s = str(p)
                if p.is_file() and not any(k in s for k in skip) and p.stat().st_size < 400_000:
                    out.append(p)
        return sorted(set(out))
    return {
        'strata': pick(FORK, ['src/**/*.cpp', 'src/**/*.cu', 'src/**/*.cuh', 'include/**/*.hpp', 'serve/*.py',
                              'tools/*.py', 'docs/*.md']),
        'cgc': pick(Path(r'C:\Users\imanu\source\repos\MultiPhoneControls'), ['*.cs', '*.md', '*.xaml']),
        'ricerca': pick(Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs'), ['*.md', '*.py']),
    }


def encode_files(tok, files, cap_tokens):
    ids, n = [], 0
    for p in files:
        try:
            text = p.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        e = tok.encode(text)
        ids.append(np.array(e, dtype=np.int32))
        n += len(e)
        if n >= cap_tokens:
            break
    return ids


def main():
    t0 = time.time()
    tests = {}
    tests['ctx131k (codice llama.cpp)'] = np.frombuffer(gzip.decompress((FIX / 'ids/ctx131k.ids.bin.gz').read_bytes()), dtype='<i4')
    short = [np.array(json.loads((FIX / f'ids/prompt_S{i:02d}.ids.json').read_text()), dtype=np.int32) for i in range(1, 11)]
    tok = tokenizer()
    files = corpus_files()
    print({k: len(v) for k, v in files.items()}, flush=True)
    enc = {}
    for k, fl in files.items():
        t1 = time.time()
        # every 5th file of each corpus is held out as a test of "the user's own material"
        train = [p for i, p in enumerate(fl) if i % 5]
        held = [p for i, p in enumerate(fl) if i % 5 == 0]
        enc[k] = (encode_files(tok, train, 6_000_000), encode_files(tok, held, 140_000))
        print(f'{k}: train {sum(map(len, enc[k][0]))} token, held-out {sum(map(len, enc[k][1]))} token '
              f'({time.time() - t1:.0f} s)', flush=True)
    for k in enc:
        tests[f'held-out {k}'] = np.concatenate(enc[k][1])[:131072]
    # training counts: per file streams (a file starts with NULL predecessors), all corpora together
    cnt = Counter()
    for k in enc:
        for a in enc[k][0]:
            if len(a):
                u, c = np.unique(rows_of(a).reshape(-1), return_counts=True)
                cnt.update(dict(zip(u.tolist(), c.tolist())))
    ranked = np.array([r for r, _ in cnt.most_common()], dtype=np.uint32)
    print(f'righe distinte nel corpus di addestramento: {len(ranked)}', flush=True)
    res = {'train_tokens': {k: int(sum(map(len, enc[k][0]))) for k in enc}, 'distinct_rows': int(len(ranked)), 'tests': {}}
    for name, toks in tests.items():
        rows = rows_of(toks)
        line = {'tokens': int(len(toks))}
        b = simulate(rows, CACHE_ROWS, None)
        line['base'] = b
        for K in (262144, 524288, 1048576, 2097152):
            hot = np.sort(ranked[:K])
            line[f'hot{K}+1M'] = simulate(rows, CACHE_ROWS, hot)
            line[f'hot{K}+(1M-K)'] = simulate(rows, max(CACHE_ROWS - K, 0), hot)
        res['tests'][name] = line
        print(f'\n{name}: {len(toks)} token, base {b["misses"]} righe / {b["pages"]} pagine (hit {b["hit"]:.1%})')
        for k, v in line.items():
            if k.startswith('hot'):
                print(f'  {k:18s} righe {v["misses"]:8d} ({v["misses"] / max(b["misses"], 1):.0%})  '
                      f'pagine {v["pages"]:8d} ({v["pages"] / max(b["pages"], 1):.0%})', flush=True)
    # short prompts: each a fresh process-lifetime cache would be too kind; one cache across all ten, in order
    s = np.concatenate(short)
    rows = rows_of(s)
    b = simulate(rows, CACHE_ROWS, None)
    print(f'\nS01-S10 in fila: {len(s)} token, base {b["misses"]} righe / {b["pages"]} pagine')
    for K in (262144, 1048576):
        v = simulate(rows, CACHE_ROWS, np.sort(ranked[:K]))
        print(f'  hot{K}+1M righe {v["misses"]} ({v["misses"] / max(b["misses"], 1):.0%}) pagine {v["pages"]}')
    (OUT / 'ple_hot_sim.json').write_text(json.dumps(res, indent=1) + '\n', encoding='utf-8')
    np.save(OUT / 'hot_rows_ranked_top2M.npy', ranked[:2097152])
    print(f'\nfatto in {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
