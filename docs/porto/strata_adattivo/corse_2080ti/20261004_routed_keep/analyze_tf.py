"""Teacher-forced fidelity: per-position argmax agreement and KL against the full-model arm.

Each run forced the same token sequence (prompt + arm A's greedy answer); the answer
positions went through the verify windows. Rows: pos, target, lp(target), top, lp(top),
top==target, lp(extra), lp(target w/o extra), then 20 'id:lp'. KL(A||X) is over A's
top 20 plus one bucket for the remaining mass (same recipe as upstream UNSLOTH_Q4.md).
"""
import json, math, sys
from pathlib import Path

L = Path(__file__).resolve().parent


def read(run):
    rows = {}
    for line in (L / run / 'logpos.tsv').read_text().splitlines():
        f = line.split('\t')
        top = [(int(x.split(':')[0]), float(x.split(':')[1])) for x in f[8:]]
        rows[int(f[0])] = dict(tgt=int(f[1]), top=int(f[3]), hit=f[5] == '1', topk=top)
    return rows


def kl(a, x):
    pa = {i: math.exp(lp) for i, lp in a}
    px = {i: math.exp(lp) for i, lp in x}
    ra, rx = max(1e-12, 1 - sum(pa.values())), None
    s, xin = 0.0, 0.0
    for i, p in pa.items():
        q = px.get(i)
        if q is None:  # outside X's top 20: bound it by X's smallest listed probability
            q = min(px.values())
        xin += q
        s += p * math.log(p / q)
    rx = max(1e-12, 1 - xin)
    return s + ra * math.log(ra / rx)


def compare(ref, run):
    A, X = read(ref), read(run)
    pos = sorted(set(A) & set(X))
    agree = sum(A[p]['top'] == X[p]['top'] for p in pos) / len(pos)
    hit = sum(X[p]['hit'] for p in pos) / len(pos)
    k = [kl(A[p]['topk'], X[p]['topk']) for p in pos]
    top5 = sum(len({i for i, _ in A[p]['topk'][:5]} & {i for i, _ in X[p]['topk'][:5]}) / 5 for p in pos) / len(pos)
    # decisive positions: A's top-1 leads its top-2 by >= 0.5 nats
    firm = [p for p in pos if A[p]['topk'][0][1] - A[p]['topk'][1][1] >= 0.5]
    firm_agree = sum(A[p]['top'] == X[p]['top'] for p in firm) / max(1, len(firm))
    return dict(positions=len(pos), argmax_vs_ref=agree, argmax_vs_teacher=hit, kl_mean=sum(k) / len(k),
                kl_p99=sorted(k)[int(0.99 * (len(k) - 1))], top5_overlap=top5,
                firm_positions=len(firm), firm_argmax_vs_ref=firm_agree)


if __name__ == '__main__':
    ref, runs = sys.argv[1], sys.argv[2:]
    out = {}
    for r in runs:
        out[r] = compare(ref, r)
        c = out[r]
        print(f"{r:24} vs {ref:16} pos {c['positions']:4} argmax {100*c['argmax_vs_ref']:5.1f}% "
              f"(teacher {100*c['argmax_vs_teacher']:5.1f}%) firm {100*c['firm_argmax_vs_ref']:5.1f}% of {c['firm_positions']} "
              f"top5 {100*c['top5_overlap']:5.1f}% KL {c['kl_mean']:.4f} p99 {c['kl_p99']:.3f}")
    print(json.dumps(out))
