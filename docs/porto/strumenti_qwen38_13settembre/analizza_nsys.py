"""Kernel GPU per forward a 1 riga (w1) contro 2 righe (w2) da un sqlite di nsys."""
import bisect, collections, re, sqlite3, sys

db = sqlite3.connect(sys.argv[1])
skip = int(sys.argv[2]) if len(sys.argv) > 2 else 4
tables = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
need = {"NVTX_EVENTS", "CUPTI_ACTIVITY_KIND_KERNEL", "StringIds"}
if not need <= tables:
    print("tabelle mancanti:", need - tables, "presenti:", sorted(tables)); sys.exit(1)
strings = dict(db.execute("select id, value from StringIds"))

ranges = collections.defaultdict(list)
for start, end, text, text_id in db.execute("select start, end, text, textId from NVTX_EVENTS where end is not null order by start"):
    label = text if text else strings.get(text_id)
    if label in ("w1", "w2", "w3"):
        ranges[label].append((start, end))
for k in ranges:
    ranges[k] = ranges[k][skip:]
print({k: len(v) for k, v in ranges.items()})

kcols = [r[1] for r in db.execute("pragma table_info(CUPTI_ACTIVITY_KIND_KERNEL)")]
name_col = "shortName" if "shortName" in kcols else "nameId"
kernels = list(db.execute(f"select start, end, {name_col} from CUPTI_ACTIVITY_KIND_KERNEL order by start"))
kstarts = [k[0] for k in kernels]
copies = []
if "CUPTI_ACTIVITY_KIND_MEMCPY" in tables:
    copies = list(db.execute("select start, end, bytes, copyKind from CUPTI_ACTIVITY_KIND_MEMCPY order by start"))
cstarts = [c[0] for c in copies]


def short(name_id):
    n = strings.get(name_id, str(name_id))
    n = re.sub(r"\(.*$", "", n)
    depth, out = 0, []
    for ch in n:
        if ch == "<":
            depth += 1
            if depth == 1:
                out.append("<>")
            continue
        if ch == ">":
            depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    s = "".join(out)
    return s[-70:]


stats = {}
for label, rs in ranges.items():
    per_name = collections.defaultdict(float)
    per_count = collections.defaultdict(int)
    wall = busy = h2d_ms = h2d_mb = d2h_ms = 0.0
    for start, end in rs:
        wall += (end - start) / 1e6
        i = bisect.bisect_left(kstarts, start)
        intervals = []
        while i < len(kernels) and kernels[i][0] < end:
            s, e, nid = kernels[i]
            per_name[short(nid)] += (e - s) / 1e6
            per_count[short(nid)] += 1
            intervals.append((s, min(e, end)))
            i += 1
        cur_s = cur_e = None
        for s, e in sorted(intervals):
            if cur_e is None or s > cur_e:
                if cur_e is not None:
                    busy += (cur_e - cur_s) / 1e6
                cur_s, cur_e = s, e
            else:
                cur_e = max(cur_e, e)
        if cur_e is not None:
            busy += (cur_e - cur_s) / 1e6
        j = bisect.bisect_left(cstarts, start)
        while j < len(copies) and copies[j][0] < end:
            s, e, b, kind = copies[j]
            if kind == 1:
                h2d_ms += (e - s) / 1e6; h2d_mb += b / 1048576
            elif kind == 2:
                d2h_ms += (e - s) / 1e6
            j += 1
    n = max(1, len(rs))
    stats[label] = {"n": len(rs), "wall": wall / n, "busy": busy / n, "h2d_ms": h2d_ms / n, "h2d_mb": h2d_mb / n,
                    "d2h_ms": d2h_ms / n, "names": {k: v / n for k, v in per_name.items()},
                    "counts": {k: c / n for k, c in per_count.items()}}
    st = stats[label]
    print(f"\n== {label}: {st['n']} forward | parete {st['wall']:.2f} ms | GPU occupata (unione kernel) {st['busy']:.2f} ms | "
          f"inattiva {st['wall'] - st['busy']:.2f} ms | H2D {st['h2d_ms']:.2f} ms {st['h2d_mb']:.1f} MiB | D2H {st['d2h_ms']:.2f} ms | "
          f"somma kernel {sum(st['names'].values()):.2f} ms")
    for k, v in sorted(st["names"].items(), key=lambda kv: -kv[1])[:22]:
        print(f"   {v:7.3f} ms  x{st['counts'][k]:6.1f}  {k}")

if "w1" in stats and "w2" in stats:
    a, b = stats["w1"], stats["w2"]
    print(f"\n== DIFFERENZA w2 - w1: parete {b['wall'] - a['wall']:+.2f} ms | occupata {b['busy'] - a['busy']:+.2f} | "
          f"inattiva {(b['wall'] - b['busy']) - (a['wall'] - a['busy']):+.2f} | H2D {b['h2d_ms'] - a['h2d_ms']:+.2f} ms "
          f"{b['h2d_mb'] - a['h2d_mb']:+.1f} MiB | somma kernel {sum(b['names'].values()) - sum(a['names'].values()):+.2f}")
    names = set(a["names"]) | set(b["names"])
    delta = sorted(((b["names"].get(k, 0) - a["names"].get(k, 0), k) for k in names), reverse=True)
    for d, k in delta[:25]:
        print(f"   {d:+7.3f} ms  ({a['names'].get(k, 0):6.3f} -> {b['names'].get(k, 0):6.3f})  x{a['counts'].get(k, 0):5.1f}->{b['counts'].get(k, 0):5.1f}  {k}")
