"""P0 — aggregazione delle corse del banco.

Regole del protocollo applicate qui, senza eccezioni:
  - il throughput di un insieme e' somma(token accettati) / somma(tempo di generazione),
    NON la media aritmetica dei t/s dei singoli casi;
  - l'unita' indipendente e' il PROCESSO/COPPIA: piu' richieste dello stesso server non
    sono prove indipendenti;
  - si calcola il rapporto per coppia, la mediana e un intervallo bootstrap al 95% sulle
    coppie, e si stampano anche i singoli valori;
  - copia/rinomina resta separata dalla risposta libera e non entra mai nella sua media;
  - le corse non valide vengono elencate, non silenziosamente escluse.

Uso:
  python aggrega.py --root D:\\ds4_work\\banco_p0_run
  python aggrega.py --coppia CART_A CART_B --coppia CART_A2 CART_B2
"""
import argparse
import json
import random
from pathlib import Path

INSIEMI = ["libero", "copia", "qualita", "prefill"]


def carica(cartella):
    c = Path(cartella)
    man = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
    righe = []
    f = c / "results.jsonl"
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                righe.append(json.loads(l))
    return {"cartella": str(c), "manifest": man, "righe": righe}


def tps_insieme(righe, insieme=None):
    sel = [r for r in righe
           if not r.get("riscaldamento") and r.get("valido")
           and (insieme is None or insieme in (r.get("insiemi") or []))]
    tok = sum((r.get("predicted_n") or 0) for r in sel)
    tempo = sum((r.get("predicted_ms") or 0) for r in sel) / 1000.0
    return {"n_casi": len(sel), "token": tok, "tempo_s": round(tempo, 3),
            "tps": round(tok / tempo, 4) if tempo > 0 else None}


def prefill_tps(righe):
    sel = [r for r in righe if not r.get("riscaldamento") and r.get("valido")
           and "prefill" in (r.get("insiemi") or [])]
    out = {}
    for r in sel:
        pn = r.get("prompt_n") or 0
        pms = r.get("prompt_ms") or 0
        out[r["etichetta"]] = {
            "prompt_n": pn, "cache_n": r.get("cache_n"), "prompt_ms": pms,
            "prompt_tps_integrale": round(pn / (pms / 1000.0), 2) if pms > 0 else None,
            "prompt_tps_server": r.get("prompt_tps_server"),
        }
    return out


def bootstrap(valori, n=20000, seme=20260914):
    if not valori:
        return None
    rnd = random.Random(seme)
    k = len(valori)
    mediane = []
    for _ in range(n):
        campione = [valori[rnd.randrange(k)] for _ in range(k)]
        campione.sort()
        m = campione[k // 2] if k % 2 else (campione[k // 2 - 1] + campione[k // 2]) / 2.0
        mediane.append(m)
    mediane.sort()
    lo = mediane[int(0.025 * len(mediane))]
    hi = mediane[min(len(mediane) - 1, int(0.975 * len(mediane)))]
    return {"campioni": n, "limite_inferiore_95": round(lo, 4), "limite_superiore_95": round(hi, 4)}


def mediana(v):
    if not v:
        return None
    s = sorted(v)
    k = len(s)
    return s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="radice delle corse: le coppie si formano per replica")
    ap.add_argument("--coppia", nargs=2, action="append", default=[], metavar=("A", "B"))
    ap.add_argument("--insieme", default="libero", choices=INSIEMI)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    coppie = []
    invalide = []
    if args.root:
        corse = []
        for c in sorted(Path(args.root).iterdir()):
            if c.is_dir() and (c / "manifest.json").exists():
                d = carica(c)
                if not d["manifest"].get("valido", True):
                    invalide.append((str(c), d["manifest"].get("motivo_esclusione")))
                    continue
                corse.append(d)
        per_replica = {}
        for d in corse:
            k = d["manifest"]["replica"]
            per_replica.setdefault(k, {})[d["manifest"]["preset_id"]] = d
        for k in sorted(per_replica):
            g = per_replica[k]
            if "A" in g and "B" in g:
                coppie.append((g["A"], g["B"]))
            else:
                invalide.append((str(list(g.values())[0]["cartella"]),
                                 "replica %s senza controparte (presenti: %s)" % (k, sorted(g))))
    for a, b in args.coppia:
        coppie.append((carica(a), carica(b)))

    print("=== corse escluse o spaiate ===" if invalide else "=== nessuna corsa esclusa ===")
    for c, m in invalide:
        print("  %s  ->  %s" % (c, m))

    print("\n=== valori per corsa (insieme '%s') ===" % args.insieme)
    rapporti = []
    dettaglio = []
    for A, B in coppie:
        ta = tps_insieme(A["righe"], args.insieme)
        tb = tps_insieme(B["righe"], args.insieme)
        rap = None
        if ta["tps"] and tb["tps"]:
            rap = tb["tps"] / ta["tps"]
            rapporti.append(rap)
        print("  replica %-3s A=%-9s (%d casi, %d token, %.2f s)   B=%-9s   rapporto B/A=%s" % (
            A["manifest"]["replica"], ta["tps"], ta["n_casi"], ta["token"], ta["tempo_s"],
            tb["tps"], "n/d" if rap is None else "%.4f" % rap))
        dettaglio.append({
            "replica": A["manifest"]["replica"],
            "A": {"cartella": A["cartella"], **ta},
            "B": {"cartella": B["cartella"], **tb},
            "rapporto_B_su_A": rap,
            "insiemi_tutti": {i: {"A": tps_insieme(A["righe"], i), "B": tps_insieme(B["righe"], i)}
                              for i in INSIEMI},
            "prefill": {"A": prefill_tps(A["righe"]), "B": prefill_tps(B["righe"])},
            "impronte_uguali": [
                r["etichetta"] for r in A["righe"]
                if any(s["etichetta"] == r["etichetta"]
                       and s["impronta_testo_sha256"] == r["impronta_testo_sha256"]
                       for s in B["righe"])],
            "impronte_diverse": [
                r["etichetta"] for r in A["righe"]
                if any(s["etichetta"] == r["etichetta"]
                       and s["impronta_testo_sha256"] != r["impronta_testo_sha256"]
                       for s in B["righe"])],
        })

    ris = {"insieme": args.insieme, "n_coppie": len(coppie), "rapporti_per_coppia": rapporti,
           "mediana_rapporto": mediana(rapporti), "bootstrap_95_sulla_mediana": bootstrap(rapporti),
           "coppie": dettaglio, "escluse": invalide}
    print("\n=== sintesi ===")
    print("  coppie: %d" % len(coppie))
    print("  rapporti B/A: %s" % ["%.4f" % r for r in rapporti])
    print("  mediana: %s" % (None if ris["mediana_rapporto"] is None
                             else "%.4f" % ris["mediana_rapporto"]))
    print("  bootstrap 95%% sulla mediana: %s" % json.dumps(ris["bootstrap_95_sulla_mediana"]))
    if len(coppie) < 3:
        print("  ATTENZIONE: sotto le tre coppie l'intervallo non e' interpretabile; "
              "il protocollo chiede tre coppie in screening e cinque in conferma.")
    for i in INSIEMI:
        if i == args.insieme:
            continue
        va = [d["insiemi_tutti"][i]["A"]["tps"] for d in dettaglio
              if d["insiemi_tutti"][i]["A"]["tps"] is not None]
        vb = [d["insiemi_tutti"][i]["B"]["tps"] for d in dettaglio
              if d["insiemi_tutti"][i]["B"]["tps"] is not None]
        if va or vb:
            print("  (insieme separato '%s' - A: %s  B: %s)" % (
                i, ["%.2f" % x for x in va], ["%.2f" % x for x in vb]))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(ris, indent=1, ensure_ascii=False), encoding="utf-8")
        print("\nscritto %s" % args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
