"""P7, cella 4 — raccoglie le corse del banco in una tabella.

Legge `riepilogo.json` e `carico.jsonl` di ogni cartella di corsa che porta
`P7-cella4` (o un elenco esplicito) e stampa ms/token, t/s, impronte e la RAM
LIBERA MINIMA della corsa. Sotto 4 GB la cella e' invalida (rischio R-RAM).

  python raccogli_c4.py                 # tutte le corse P7-cella4
  python raccogli_c4.py <cartella> ...  # solo quelle indicate
"""
import json
import sys
from pathlib import Path

RUNS = Path(r"D:\ds4_work\banco_p0_run")


def ram_min(cartella):
    f = cartella / "carico.jsonl"
    if not f.exists():
        return None
    v = []
    for riga in f.read_text(encoding="utf-8", errors="replace").splitlines():
        riga = riga.strip()
        if not riga:
            continue
        try:
            d = json.loads(riga)
        except Exception:
            continue
        r = d.get("ram_disponibile_gb")
        if isinstance(r, (int, float)):
            v.append(r)
    return min(v) if v else None


def main():
    if len(sys.argv) > 1:
        cartelle = [Path(a) if Path(a).is_absolute() else RUNS / a for a in sys.argv[1:]]
    else:
        cartelle = sorted(p for p in RUNS.iterdir() if p.is_dir() and "P7-cella4" in p.name)

    righe = []
    for c in cartelle:
        r = c / "riepilogo.json"
        if not r.exists():
            continue
        d = json.loads(r.read_text(encoding="utf-8"))
        tutti = d["tutti_i_casi_misurati"]
        # Una corsa fermata da un guasto puo' avere zero token accettati (S9):
        # resta valida come lettura dei contatori, non come misura di tempo.
        if not tutti.get("token_accettati"):
            print("%-9s %-38s  CORSA SENZA TOKEN ACCETTATI (non e' una misura di tempo)" %
                  (d["preset"], d["etichetta"][:38]))
            continue
        ms = 1000.0 * tutti["tempo_generazione_s"] / tutti["token_accettati"]
        righe.append({
            "corsa": c.name,
            "preset": d["preset"],
            "etichetta": d["etichetta"],
            "profilo": d["profilo"],
            "token": tutti["token_accettati"],
            "ms_token": round(ms, 3),
            "tps": tutti["tps_insieme"],
            "tps_libero": d["insieme_libero"]["tps_insieme"],
            "guasto": d["guasto"],
            "ram_libera_min_gb": ram_min(c),
            "impronte": d["impronte"],
        })

    print("%-9s %-38s %-12s %8s %9s %9s %9s  %s" %
          ("preset", "etichetta", "profilo", "token", "ms/token", "t/s", "RAMmin", "impronte L01/S01"))
    for r in righe:
        imp = r["impronte"]
        firma = "/".join((imp.get("L01@corto", "-")[:8], imp.get("S01@corto", "-")[:8]))
        print("%-9s %-38s %-12s %8d %9.3f %9.3f %9s  %s%s" %
              (r["preset"], r["etichetta"][:38], r["profilo"], r["token"], r["ms_token"], r["tps"],
               ("%.2f" % r["ram_libera_min_gb"]) if r["ram_libera_min_gb"] is not None else "?",
               firma, "" if not r["guasto"] else "  GUASTO: %s" % r["guasto"]))

    print()
    base = {r["preset"]: r["ms_token"] for r in righe}
    if "S0_p7" in base:
        rif = base["S0_p7"]
        print("riferimento spento S0 = %.3f ms/token" % rif)
        for r in righe:
            if r["preset"] == "S0_p7":
                continue
            n = 47 if "47strati" in r["etichetta"] else (8 if "8strati" in r["etichetta"] else 0)
            d = r["ms_token"] - rif
            if n:
                print("  %-9s %+7.3f ms/token su %2d strati = %6.1f us/strato" % (r["preset"], d, n, 1000.0 * d / n))
            else:
                print("  %-9s %+7.3f ms/token" % (r["preset"], d))

    out = Path(__file__).resolve().parent / "log" / "c4_tabella_celle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(righe, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("\nscritto", out)


if __name__ == "__main__":
    main()
