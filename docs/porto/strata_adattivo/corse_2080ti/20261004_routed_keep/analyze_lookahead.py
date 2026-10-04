"""Per-layer accuracy of the layer-ahead routing prediction (STRATA_LOOKAHEAD_PROBE) from engine logs.

Each LOOKAHEAD line is cumulative: per layer `tokens,hit@10,hit@20,nonresident,nonresident_hit@20`, where the
prediction for layer l is the top-20 of router(l) applied to layer l-1's MoE input, and hit@k counts real top-10
experts found among the first k predicted. Non-resident = not in the VRAM expert cache when routed.
"""
import sys
from pathlib import Path


def last_counts(log):
    line = [s for s in Path(log).read_text(errors='replace').splitlines() if s.startswith('LOOKAHEAD windows=')][-1]
    parts = line.split()
    windows = int(parts[1].split('=')[1])
    out = {}
    for p in parts[2:]:
        l, v = p.split(':')
        out[int(l)] = [int(x) for x in v.split(',')]
    return windows, out


def main(runs):
    for run in runs:
        windows, c = last_counts(Path(run) / 'engine.log')
        rows = [(l, *v) for l, v in sorted(c.items()) if v[0] > 0]
        tot = [sum(r[i] for r in rows) for i in range(1, 6)]
        print(f'== {run}: {windows} finestre')
        print(f'   tutti gli strati: top-10 {100*tot[1]/(10*tot[0]):.1f}%  top-20 {100*tot[2]/(10*tot[0]):.1f}%  '
              f'non residenti {100*tot[3]/(10*tot[0]):.1f}% degli esperti, coperti dal top-20 {100*tot[4]/max(1,tot[3]):.1f}%')
        for lo, hi in ((1, 8), (8, 16), (16, 24), (24, 32), (32, 40), (40, 48)):
            sel = [r for r in rows if lo <= r[0] < hi]
            if not sel:
                continue
            s = [sum(r[i] for r in sel) for i in range(1, 6)]
            print(f'   strati {lo:2}-{hi-1:2}: top-10 {100*s[1]/(10*s[0]):5.1f}%  top-20 {100*s[2]/(10*s[0]):5.1f}%  '
                  f'non residenti {100*s[3]/(10*s[0]):5.1f}%  coperti {100*s[4]/max(1,s[3]):5.1f}%')


if __name__ == '__main__':
    main(sys.argv[1:])
