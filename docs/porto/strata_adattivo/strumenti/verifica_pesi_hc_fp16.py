"""Verifica rappresentabilita' FP16 delle matrici HC/GDN BF16 nel pack locale."""
import argparse
import json
from pathlib import Path
import sys

from compila_0131 import BASE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    import numpy as np
    rows = []
    for line in (a.pack / "index.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"): continue
        f = line.split()
        if not (".hc_" in f[0] and any(p in f[0] for p in ("_down.", "_up.", "_inject.")) or
                ".ssm_alpha." in f[0] or ".ssm_beta." in f[0]): continue
        if int(f[2]) != 4: raise RuntimeError("Tensor non BF16: " + f[0])
        names = {0: "dense.bin", 1: "embd.bin", 2: "experts.bin", 3: "extra.bin"}
        raw = np.memmap(a.pack / names[int(f[1])], dtype="<u2", mode="r", offset=int(f[3]), shape=(int(f[4])//2,))
        values = (raw.astype(np.uint32) << 16).view(np.float32)
        with np.errstate(over="ignore", invalid="ignore"):
            rounded = values.astype(np.float16).astype(np.float32)
        abs_values = np.abs(values)
        rows.append({"name": f[0], "values": int(values.size), "not_exact": int(np.count_nonzero(values != rounded)),
                     "nonfinite_source": int(np.count_nonzero(~np.isfinite(values))),
                     "nonfinite_fp16": int(np.count_nonzero(~np.isfinite(rounded))),
                     "max_abs": float(np.max(abs_values)),
                     "max_abs_conversion_error": float(np.max(np.abs(values-rounded)))})
        del raw, values, rounded
    if not rows: raise RuntimeError("Nessuna matrice HC/GDN trovata")
    result = {"pack": str(a.pack), "matrices": len(rows), "values": sum(r["values"] for r in rows),
              "not_exact": sum(r["not_exact"] for r in rows), "nonfinite_fp16": sum(r["nonfinite_fp16"] for r in rows),
              "max_abs": max(r["max_abs"] for r in rows), "rows": rows}
    a.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)


if __name__ == "__main__": main()
