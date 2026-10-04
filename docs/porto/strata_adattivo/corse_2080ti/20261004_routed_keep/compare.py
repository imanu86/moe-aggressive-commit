"""Compare probe runs with full-model references (same prompts, temperature 0, seed 73)."""
import collections, json, sys
from pathlib import Path

L = Path(__file__).resolve().parent
CLOSED = L.parent / '20261004_closed_cache'
# full-model references: own arm A when present, else the Oct 4 closed-cache controls
REFS = {'ledger': ['A-ledger', CLOSED / 'default-ledger-v1'], 'code': ['A-code', CLOSED / 'default-code-v1'],
        'explain': ['A-explain', CLOSED / 'default-explain-v1']}


def load(d):
    return json.loads((Path(d) / 'result.json').read_text(encoding='utf-8'))


def longest_repeat(ids, n=4):
    """Longest run of consecutive identical n-grams (a loop indicator)."""
    best = run = 0
    for i in range(n, len(ids) - n + 1, 1):
        run = run + 1 if ids[i:i + n] == ids[i - n:i] else 0
        best = max(best, run)
    return best


def main(names):
    for name in names:
        task = name.rsplit('-', 1)[1]
        b = load(L / name)
        refs = [r if isinstance(r, Path) else L / r for r in REFS[task]]
        ref = next(r for r in refs if (r / 'result.json').exists())
        a = load(ref)
        x, y = a['generated_ids'], b['generated_ids']
        n = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
        same = sum(p == q for p, q in zip(x, y))
        last = b.get('last') or {}
        tps = last['generated'] / last['decode_ms'] * 1000 if last.get('decode_ms') else None
        print(f"{name:22} ref={ref.name:20} len {len(x):3}/{len(y):3} first_diff {n:3} "
              f"identical {'YES' if x == y else 'no ':3} oracle {str((b.get('oracle') or {}).get('passed')):5} "
              f"loop4 {longest_repeat(y):3} t/s {tps and round(tps, 1)}")


if __name__ == '__main__':
    main(sys.argv[1:])
