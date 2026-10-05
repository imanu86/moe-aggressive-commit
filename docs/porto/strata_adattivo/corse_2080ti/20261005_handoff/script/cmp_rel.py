# read-only: compare each scratchpad/rel-<sha> copy with promo-platform's commit <sha> (blob hashes)
import hashlib, os, subprocess, sys

S = sys.argv[1]
G = 'C:/Users/imanu/source/repos/promo-platform'
LP = r'\\?' + '\\' + os.path.abspath(S).replace('/', '\\')   # long paths
SKIP = {'node_modules', '.next', '.netlify'}


def blob(b):
    return hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest()


tot_same = tot_diff = tot_extra = tot_missing = 0
changed = []
for d in sorted(os.listdir(LP)):
    if not d.startswith('rel-'):
        continue
    sha = d[4:].split('-')[0]
    tree = {}
    out = subprocess.run(['git', '-C', G, 'ls-tree', '-r', sha], capture_output=True, text=True,
                         encoding='utf-8').stdout
    for line in out.splitlines():
        meta, path = line.split('\t', 1)
        tree[path] = meta.split()[2]
    root = os.path.join(LP, d)
    same = diff = extra = 0
    extras, diffs, seen = [], [], set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [x for x in dn if x not in SKIP]
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace('\\', '/')
            if rel in ('tsconfig.tsbuildinfo', 'next-env.d.ts'):
                continue
            seen.add(rel)
            if rel not in tree:
                extra += 1
                extras.append(rel)
                continue
            b = open(p, 'rb').read()
            if blob(b) == tree[rel] or blob(b.replace(b'\r\n', b'\n')) == tree[rel]:
                same += 1
            else:
                diff += 1
                diffs.append(rel)
    missing = len([k for k in tree if k not in seen])
    tot_same += same
    tot_diff += diff
    tot_extra += extra
    tot_missing += missing
    if diff or extra:
        changed.append((d, diff, extra, diffs[:3], extras[:4]))
print(f'72 copie: file uguali al commit {tot_same}, diversi {tot_diff}, in piu {tot_extra}, '
      f'del commit mancanti {tot_missing}')
for c in changed[:15]:
    print(' ', c)
print('copie con differenze:', len(changed))
