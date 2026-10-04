"""Decode speed of the interleaved free-generation runs (S-*), from result.json and the engine log."""
import json, re, statistics, sys
from collections import defaultdict
from pathlib import Path

L = Path(__file__).resolve().parent
TIMING = re.compile(r'decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window.*'
                    r'CPU ([\d.]+)\].*CPU experts ([\d.]+) \(([\d.]+) entries\), VRAM hits ([\d.]+), PCIe ([\d.]+)')


def row(d):
    r = json.loads((d / 'result.json').read_text(encoding='utf-8'))
    p = json.loads((d / 'plan.json').read_text(encoding='utf-8'))
    last = r['last']
    m = next((TIMING.search(s) for s in r['native_metrics'] if 'decode timing' in s), None)
    out = dict(name=d.name, tps=last['generated'] / last['decode_ms'] * 1000, gen=last['generated'],
               acc=last['drafts_accepted'] / max(1, last['drafts_offered']), gpu_used=p['state'].get('gpu_used_mib'))
    if m:
        out.update(ms_window=float(m[4]), tok_window=float(m[3]), cpu_ms=float(m[5]), cpu_experts=float(m[6]),
                   cpu_entries=float(m[7]), vram=float(m[8]), pcie=float(m[9]))
    return out


def main():
    groups = defaultdict(list)
    for d in sorted(L.glob('S-*')):
        if (d / 'result.json').exists():
            x = row(d)
            parts = d.name.split('-')
            arm, task = ('A' if re.fullmatch(r'A\d+', parts[1]) else parts[1]), parts[-1]
            groups[(task, arm)].append(x)
            print(f"{x['name']:18} {x['tps']:6.2f} t/s  {x.get('ms_window', 0):6.1f} ms/win  {x.get('tok_window', 0):.2f} tok/win  "
                  f"CPU {x.get('cpu_ms', 0):5.1f} ms  CPU exp {x.get('cpu_experts', 0):5.2f} VRAM {x.get('vram', 0):5.2f} "
                  f"PCIe {x.get('pcie', 0):4.2f}  acc {100*x['acc']:.0f}%  GPU altri {x['gpu_used']} MiB")
    print()
    for task in sorted({t for t, _ in groups}):
        base = statistics.mean(x['tps'] for x in groups[(task, 'A')]) if groups[(task, 'A')] else None
        basew = statistics.mean(x['ms_window'] / x['tok_window'] for x in groups[(task, 'A')]) if base else None
        for arm in ('A', 'W06', 'W07', 'M08', 'M10'):
            xs = groups.get((task, arm))
            if not xs:
                continue
            tps = statistics.mean(x['tps'] for x in xs)
            mpt = statistics.mean(x['ms_window'] / x['tok_window'] for x in xs)
            print(f"{task:8} {arm:4} n={len(xs)}  {tps:6.2f} t/s ({100*(tps/base-1):+5.1f}%)  "
                  f"{mpt:5.1f} ms/token ({100*(basew/mpt-1):+5.1f}% per token)  "
                  f"esperti/token-layer {statistics.mean(x['cpu_entries'] + x['vram'] + x['pcie'] for x in xs) / statistics.mean(x['tok_window'] for x in xs):.2f}")


if __name__ == '__main__':
    main()
