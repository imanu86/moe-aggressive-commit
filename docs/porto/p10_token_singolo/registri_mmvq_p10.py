"""P10 cella 3 - legge l'oggetto compilato di `mmvq.cu` e riporta, per ogni istanza
di `mul_mat_vec_q` a ncols_dst = 1, i registri per thread, la memoria condivisa e
quanti blocchi da 128 thread restano residenti su un SM di sm_86 (65536 registri,
102400 B di shared, massimo 16 blocchi e 1536 thread).

E' la misura della causa trovata in questa cella: l'istanza iq2_s con la fusione
gate+up e small_k usa 110 registri e resta a 4 blocchi per SM (33% di occupazione).

Uso:
    python registri_mmvq_p10.py --obj D:\\ds4_work\\p8_work\\build\\ggml\\src\\ggml-cuda\\CMakeFiles\\ggml-cuda.dir\\mmvq.cu.obj
"""
import argparse
import re
import subprocess
from pathlib import Path

CUDA = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin")
TIPI = {8: "q8_0", 10: "q2_k", 11: "q3_k", 12: "q4_k", 13: "q5_k", 14: "q6_k",
        16: "iq2_xxs", 17: "iq2_xs", 18: "iq3_xxs", 19: "iq1_s", 20: "iq4_nl",
        21: "iq3_s", 22: "iq2_s", 23: "iq4_xs", 29: "iq1_m"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", required=True)
    ap.add_argument("--solo", default="", help="filtra per tipo, es. iq2_s,iq4_nl,q6_k")
    a = ap.parse_args()

    t = subprocess.run([str(CUDA / "cuobjdump.exe"), "-res-usage", a.obj],
                       capture_output=True, text=True, errors="replace").stdout
    b = re.findall(r"Function\s+(\S+):\s*\n\s*REG:(\d+)\s+STACK:(\d+)\s+SHARED:(\d+)\s+LOCAL:(\d+)", t)
    if not b:
        raise SystemExit("nessuna funzione trovata in %s" % a.obj)
    dem = subprocess.run([str(CUDA / "cu++filt.exe")], input="\n".join(x[0] for x in b),
                         capture_output=True, text=True).stdout.strip().split("\n")

    filtro = [s.strip() for s in a.solo.split(",") if s.strip()]
    righe = set()
    for (n, reg, st, sh, loc), d in zip(b, dem):
        m = re.search(r"mul_mat_vec_q<\(ggml_type\)(\d+), \(int\)(\d+), \(bool\)(\d), \(bool\)(\d),"
                      r" \(bool\)(\d), \(bool\)(\d)(?:, \(int\)(\d+))?>", d)
        if not m:
            continue
        ty, nc, fus, sk = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        mb = int(m.group(7)) if m.group(7) else 1
        if nc != 1 or ty not in TIPI:
            continue
        if filtro and TIPI[ty] not in filtro:
            continue
        reg, sh, loc = int(reg), int(sh), int(loc)
        th = 128                                   # nwarps = 4 a ncols_dst = 1
        per_blocco = ((reg + 7)//8)*8*th
        bl = min(65536//per_blocco if per_blocco else 16, (102400//sh) if sh else 16, 16, 1536//th)
        righe.add((TIPI[ty], "fus" if fus == "1" else "-", "small_k" if sk == "1" else "-",
                   mb, reg, sh, loc, bl, bl*th, round(100.0*bl*th/1536.0, 1)))

    print("%-9s %-4s %-8s %7s %5s %7s %6s %5s %6s %8s" %
          ("tipo", "fus", "small_k", "min_blk", "REG", "SHARED", "LOCAL", "b/SM", "th/SM", "occup.%"))
    for r in sorted(righe):
        print("%-9s %-4s %-8s %7d %5d %7d %6d %5d %6d %8.1f" % r)


if __name__ == "__main__":
    main()
