import sys, glob, os, collections, re, json

for p in (r'D:/llama-vision-upstream/gguf-py', r'D:/llama-subtract/gguf-py'):
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break
from gguf import GGUFReader
from gguf.constants import GGMLQuantizationType

S = os.path.dirname(os.path.abspath(__file__))
files = sorted(glob.glob(r'C:/ds4-models/Vision-Exp-GGUF/*.gguf'))
print('files:')
for f in files:
    print('   %-90s %d B  %.3f GiB' % (f, os.path.getsize(f), os.path.getsize(f) / 2**30))

agg = collections.defaultdict(lambda: [0, 0, 0])  # (file-kind, pattern, type) -> [n_tensors, n_elements, n_bytes]
for f in files:
    kind = 'mmproj' if 'mmproj' in os.path.basename(f).lower() else 'llm'
    r = GGUFReader(f, 'r')
    for t in r.tensors:
        g = re.sub(r'(?<=\.)\d+(?=\.)', '#', t.name)
        ty = GGMLQuantizationType(int(t.tensor_type)).name
        a = agg[(kind, g, ty)]
        a[0] += 1
        a[1] += int(t.n_elements)
        a[2] += int(t.n_bytes)

rows = []
tot = collections.defaultdict(lambda: [0, 0])
for (kind, g, ty), (n, ne, nb) in sorted(agg.items()):
    rows.append(dict(kind=kind, pattern=g, type=ty, n=n, n_elements=ne, n_bytes=nb, bpw=nb * 8 / ne))
    tot[kind][0] += ne
    tot[kind][1] += nb
    print('%-6s %-45s %-8s n=%4d  params=%14d  %9.3f GiB  bpw=%.4f' % (kind, g, ty, n, ne, nb / 2**30, nb * 8 / ne))
for k, (ne, nb) in tot.items():
    print('TOTAL %-6s params=%d (%.2fB)  bytes=%d  %.3f GiB  %.3f GB  bpw=%.4f' % (k, ne, ne / 1e9, nb, nb / 2**30, nb / 1e9, nb * 8 / ne))
json.dump(rows, open(os.path.join(S, 'gguf_ref_rows.json'), 'w'), indent=1)
