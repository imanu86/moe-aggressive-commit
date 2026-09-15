"""P10 cella 3 - legge una traccia nsys (.sqlite) e riporta, per il solo
`mul_mat_vec_q`, il tempo per famiglia di quanto: numero di lanci, tempo totale,
tempo MEDIANO per lancio. E' la grandezza che questa cella muove.

Il tempo per lancio non dipende da quanti forward ci sono nella finestra, quindi
il confronto prima/dopo e' valido anche se le due finestre non contengono lo
stesso numero di token.

Uso:
    python kernel_mmvq_p10.py --sqlite <file.sqlite> [--json-out log/x.json]
"""
import argparse
import json
import re
import sqlite3
import statistics
from pathlib import Path

TIPI = {
    0: "f32", 1: "f16", 8: "q8_0", 10: "q2_k", 11: "q3_k", 12: "q4_k", 13: "q5_k",
    14: "q6_k", 16: "iq2_xxs", 17: "iq2_xs", 18: "iq3_xxs", 19: "iq1_s", 20: "iq4_nl",
    21: "iq3_s", 22: "iq2_s", 23: "iq4_xs", 29: "iq1_m", 30: "bf16",
}


def tipo_ggml(dem):
    m = re.search(r"\(ggml_type\)(\d+)", dem or "")
    if m:
        return TIPI.get(int(m.group(1)), "tipo%s" % m.group(1))
    m = re.search(r"GGML_TYPE_([A-Z0-9_]+)", dem or "")
    if m:
        return m.group(1).lower()
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", required=True)
    ap.add_argument("--json-out")
    ap.add_argument("--etichetta", default="")
    a = ap.parse_args()

    con = sqlite3.connect(a.sqlite)
    cur = con.cursor()
    righe = list(cur.execute(
        "select ss.value, sd.value, k.start, k.end "
        "from CUPTI_ACTIVITY_KIND_KERNEL k "
        "join StringIds sd on sd.id = k.demangledName "
        "join StringIds ss on ss.id = k.shortName order by k.start"))
    con.close()

    per_tipo = {}
    tot_ns = 0
    for short, dem, s, e in righe:
        tot_ns += (e - s)
        if "mul_mat_vec_q" not in (short or "") and "mul_mat_vec_q" not in (dem or ""):
            continue
        t = tipo_ggml(dem)
        per_tipo.setdefault(t, []).append((e - s) / 1000.0)   # us

    fuori = {}
    for short, dem, s, e in righe:
        if "mul_mat_vec_q" in (short or "") or "mul_mat_vec_q" in (dem or ""):
            continue
        k = (short or "")[:40]
        d = fuori.setdefault(k, [0, 0.0])
        d[0] += 1
        d[1] += (e - s) / 1e6

    out = {"sqlite": a.sqlite, "etichetta": a.etichetta,
           "kernel_totali": len(righe), "tempo_kernel_ms": tot_ns / 1e6,
           "mul_mat_vec_q": {}}
    print("# %s" % a.sqlite)
    print("# kernel nella finestra: %d, tempo totale dei kernel %.1f ms" % (len(righe), tot_ns / 1e6))
    print("%-10s %8s %12s %12s %12s %12s" % ("tipo", "lanci", "totale ms", "mediana us", "media us", "minimo us"))
    for t, v in sorted(per_tipo.items(), key=lambda x: -sum(x[1])):
        v.sort()
        rec = {"lanci": len(v), "totale_ms": sum(v) / 1000.0,
               "mediana_us": statistics.median(v), "media_us": sum(v) / len(v),
               "minimo_us": v[0]}
        out["mul_mat_vec_q"][t] = rec
        print("%-10s %8d %12.3f %12.3f %12.3f %12.3f" %
              (t, rec["lanci"], rec["totale_ms"], rec["mediana_us"], rec["media_us"], rec["minimo_us"]))

    print("\n# primi kernel non-mmvq per tempo totale")
    for k, (n, ms) in sorted(fuori.items(), key=lambda x: -x[1][1])[:8]:
        print("  %-42s %6d lanci  %8.1f ms" % (k, n, ms))
    out["altri_kernel"] = {k: {"lanci": n, "totale_ms": ms}
                           for k, (n, ms) in sorted(fuori.items(), key=lambda x: -x[1][1])[:20]}

    if a.json_out:
        Path(a.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json_out).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
