"""P11 - serie della workspace CUDA e cadenza dei blocchi di prefill.

Per ogni corsa stampa: profondita' kv al momento della riserva, dimensione della
workspace riservata, e i secondi trascorsi dalla riserva precedente (cioe' quanto
e' costato quel tratto di prompt). Serve a vedere DOVE il costo cresce e dove la
VRAM finisce.

Uso:  python serie_workspace_p11.py <file_log_o_estratto> [...]
"""
import re
import sys
from pathlib import Path


def secondi(tstamp):
    # formato del log: mm.ss.mmm.uuu  (minuti.secondi.millisecondi.microsecondi)
    p = tstamp.split(".")
    if len(p) < 2:
        return None
    try:
        return int(p[0]) * 60 + int(p[1]) + int(p[2]) / 1000.0
    except ValueError:
        return None


def main():
    for f in sys.argv[1:]:
        righe = Path(f).read_text(encoding="utf-8", errors="replace").splitlines()
        print("== %s" % Path(f).name)
        prec = None
        for i, l in enumerate(righe):
            m = re.search(r"demand workspace tokens=(\d+) kv=(\d+)", l)
            if not m:
                continue
            ws = None
            for j in range(i + 1, min(i + 4, len(righe))):
                b = re.search(r"CUDA0 compute buffer size\s*=\s*([0-9.]+)", righe[j])
                if b:
                    ws = float(b.group(1))
                    break
            t = secondi(l.split()[0])
            d = (t - prec) if (prec is not None and t is not None) else None
            if int(m.group(1)) >= 512:
                print("   t=%8.1fs  tokens=%-5s kv=%-7s  ws=%8s MiB   tratto=%s" % (
                    t or -1, m.group(1), m.group(2), ws,
                    ("%.1f s" % d) if d else "-"))
                prec = t
        for l in righe:
            if re.search(r"CUDA error|out of memory|failed to allocate|qwen_prefetch", l):
                print("   ! " + l.strip())


if __name__ == "__main__":
    main()
