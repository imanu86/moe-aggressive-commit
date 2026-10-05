# read-only: sizes of C:\ folders (depth <= 4) and files >= 1 GB; no reparse points followed
import os, stat, sys, time, json
ROOT = 'C:/'
t0 = time.time()
dir_size = {}
big = []
def walk(path, depth, parents):
    try:
        it = os.scandir(path)
    except OSError:
        return 0
    total = 0
    with it:
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if getattr(st, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                continue
            if stat.S_ISDIR(st.st_mode):
                total += walk(e.path, depth + 1, parents)
            else:
                total += st.st_size
                if st.st_size >= 1 << 30:
                    big.append((st.st_size, e.path, st.st_mtime))
    if depth <= 4:
        dir_size[path] = total
    return total
walk(ROOT, 0, [])
big.sort(reverse=True)
out = {'seconds': round(time.time() - t0), 'dirs': sorted(dir_size.items(), key=lambda kv: -kv[1])[:150],
       'big': [(s, p, time.strftime('%Y-%m-%d', time.localtime(m))) for s, p, m in big[:80]]}
json.dump(out, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('done', out['seconds'], 's,', len(big), 'files >= 1 GB')
