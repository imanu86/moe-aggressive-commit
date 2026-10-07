"""BAB verdict (owner 7/10: one A per bench, ideally B A B). Usage: python bab_verdict.py A B1 [B2]
Prints per arm L01/L02 decode s and t/s, then gain of each B over A and of the B mean over A (on L01+L02).
"""
import re, sys
from pathlib import Path

K = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep')


def arm(n):
    s = (K / n / 'engine.log').read_text(encoding='utf-8', errors='replace')
    g = [int(x) / 1000 for x in re.findall(r'1024 generated in (\d+) ms', s)]
    w = re.findall(r'strata work: request \d \(forced\), (\d+) windows', s)
    return n, g, w


a, *bs = [arm(n) for n in sys.argv[1:]]
for n, g, w in [a, *bs]:
    print(f'{n:<18} L01 {g[0]:6.2f}s ({1024 / g[0]:5.1f} t/s)  L02 {g[1]:6.2f}s ({1024 / g[1]:5.1f} t/s)  finestre {"/".join(w)}')
ta = sum(a[1])
gains = [(ta - sum(b[1])) / ta * 100 for b in bs]
print('guadagno di ogni B su A (L01+L02) %:', [round(x, 1) for x in gains])
print(f'guadagno medio B su A: {sum(gains) / len(gains):.1f} %')
