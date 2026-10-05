# read-only: folder sizes under given roots, two levels deep
import os, stat, sys, time
G = 1 << 30
def size(path):
    total = 0
    stack = [path]
    while stack:
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if getattr(st, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                        continue
                    if stat.S_ISDIR(st.st_mode): stack.append(e.path)
                    else: total += st.st_size
        except OSError:
            pass
    return total
for root in sys.argv[1:]:
    rows = []
    for e in os.scandir(root):
        if e.is_dir(follow_symlinks=False):
            s = size(e.path)
            sub = []
            if s >= 4 * G:
                for f in os.scandir(e.path):
                    if f.is_dir(follow_symlinks=False):
                        ss = size(f.path)
                        if ss >= 2 * G: sub.append((ss, f.name))
            rows.append((s, e.name, sorted(sub, reverse=True)[:8]))
    rows.sort(reverse=True)
    print(f'== {root}')
    for s, n, sub in rows:
        if s < 2 * G: continue
        print(f'{s/G:8.1f}  {n}')
        for ss, nn in sub: print(f'{ss/G:14.1f}    {nn}')
