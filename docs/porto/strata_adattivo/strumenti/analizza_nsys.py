"""Sequenza dei kernel di Strata per strato, da un profilo Nsight Systems esportato in SQLite, 30/9/2026.

I kernel dentro il grafo della finestra (--cuda-graph-trace=node) sono in CUPTI_ACTIVITY_KIND_KERNEL. Gli strati si
separano sui `wait_flag_ge_kernel` (la GPU aspetta il piano della CPU una volta per strato e gruppo). Stampa: quanto e'
occupata la GPU nella cattura (unione degli intervalli, non somma), i buchi fra un kernel e il successivo, e per un tratto
tipico (la mediana dei tratti fra due wait_flag) la sequenza dei kernel con durata e buco prima di ciascuno.
Uso:  python analizza_nsys.py FILE.sqlite
"""
import sqlite3
import statistics
import sys


def main():
    c = sqlite3.connect(sys.argv[1])
    cols = [r[1] for r in c.execute("pragma table_info(CUPTI_ACTIVITY_KIND_KERNEL)")]
    nome = "shortName" if "shortName" in cols else "demangledName"
    q = ("select k.start, k.end, k.streamId, s.value from CUPTI_ACTIVITY_KIND_KERNEL k "
         "join StringIds s on s.id = k.%s order by k.start" % nome)
    ks = [(a, b, st, n) for a, b, st, n in c.execute(q)]
    print("kernel: %d, colonne: %s" % (len(ks), ", ".join(cols[:12])))
    t0, t1 = ks[0][0], max(k[1] for k in ks)
    busy, cur_s, cur_e = 0, None, None
    for a, b, _, _ in ks:   # unione degli intervalli (i flussi possono sovrapporsi)
        if cur_e is None or a > cur_e:
            if cur_e is not None:
                busy += cur_e - cur_s
            cur_s, cur_e = a, b
        else:
            cur_e = max(cur_e, b)
    busy += cur_e - cur_s
    print("cattura %.1f ms, GPU occupata %.1f ms (%.0f%%)" % ((t1 - t0) / 1e6, busy / 1e6, 100.0 * busy / (t1 - t0)))
    # tratti fra due wait_flag consecutivi (uno strato o mezzo strato)
    idx = [i for i, k in enumerate(ks) if "wait_flag" in k[3]]
    tratti = [(idx[j], idx[j + 1]) for j in range(len(idx) - 1)]
    durate = [ks[e][0] - ks[s][0] for s, e in tratti]
    if not tratti:
        return
    med = statistics.median(durate)
    print("tratti fra wait_flag: %d, durata mediana %.1f us, kernel per tratto (mediana) %d" %
          (len(tratti), med / 1e3, statistics.median([e - s for s, e in tratti])))
    s, e = min(tratti, key=lambda t: abs((ks[t[1]][0] - ks[t[0]][0]) - med))
    print("tratto tipico: %.1f us" % ((ks[e][0] - ks[s][0]) / 1e3))
    prev_end = None
    lav = buchi = 0
    for a, b, st, n in ks[s:e + 1]:
        gap = (a - prev_end) / 1e3 if prev_end is not None else 0.0
        print("  %8.1f us buco %7.1f us  flusso %3d  %s" % ((b - a) / 1e3, gap, st, n[:90]))
        lav += b - a
        buchi += max(0.0, gap * 1e3)
        prev_end = b if prev_end is None else max(prev_end, b)
    print("nel tratto: lavoro %.1f us, buchi %.1f us" % (lav / 1e3, buchi / 1e3))


if __name__ == "__main__":
    main()
