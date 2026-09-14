"""P7 - lettura di una corsa del banco P0 con la speculazione ACCESA.

Estrae quello che il protocollo della cella chiede e NON deduce niente che non sia
scritto nei risultati:
  - t/s dell'insieme libero = somma(token accettati) / somma(tempo di generazione),
    separato per contesto (corto / ctx32k);
  - ms per token accettato (l'inverso, in chiaro, perche' la soglia di Codex e' 20 ms);
  - conteggi della bozza (`draft_n`, `draft_n_accepted` dai timings del server) quando
    il server li espone: token abbozzati, accettati, accettazione, token per passata;
  - casi finiti per `length` con testo vuoto (controllo D15);
  - picchi VRAM/RAM dalla sonda di carico;
  - confronto delle impronte SHA256 con una corsa di riferimento.

Uso:
  python analizza_p7.py --corsa <cartella> [--riferimento <cartella>] [--json-out f.json]
"""
import argparse
import json
from pathlib import Path


def carica(cartella):
    c = Path(cartella)
    righe = []
    f = c / "results.jsonl"
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                righe.append(json.loads(l))
    return c, righe


def utili(righe, contesto=None):
    return [r for r in righe
            if not r.get("riscaldamento") and r.get("valido")
            and "libero" in (r.get("insiemi") or [])
            and (contesto is None or r.get("contesto") == contesto)]


def aggrega(sel):
    tok = sum((r.get("predicted_n") or 0) for r in sel)
    ms = sum((r.get("predicted_ms") or 0) for r in sel)
    d_n = sum((r.get("draft_n") or 0) for r in sel)
    d_acc = sum((r.get("draft_n_accepted") or 0) for r in sel)
    out = {
        "n_casi": len(sel),
        "token_accettati": tok,
        "tempo_generazione_s": round(ms / 1000.0, 3),
        "tps": round(tok / (ms / 1000.0), 4) if ms > 0 else None,
        "ms_per_token_accettato": round(ms / tok, 4) if tok else None,
        "draft_n_totale": d_n if d_n else None,
        "draft_n_accettati": d_acc if d_n else None,
        "accettazione": round(d_acc / d_n, 4) if d_n else None,
    }
    if d_n:
        # una passata = una verifica del bersaglio. Con bozza di lunghezza L e
        # n_passate = draft_n / L, i token accettati per passata sono tok/n_passate.
        out["nota_passate"] = ("token abbozzati e accettati sommati sulle richieste; "
                               "i token per passata si ricavano dividendo per il numero "
                               "di verifiche, che il server non espone direttamente")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corsa", required=True)
    ap.add_argument("--riferimento", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    c, righe = carica(args.corsa)
    ris = {"corsa": c.name, "cartella": str(c)}

    sel = utili(righe)
    ris["libero_totale"] = aggrega(sel)
    for ctx in ("corto", "ctx32k"):
        ris["libero_" + ctx] = aggrega(utili(righe, ctx))

    # --- per richiesta ------------------------------------------------------
    per_caso = []
    for r in sel:
        d_n = r.get("draft_n")
        per_caso.append({
            "etichetta": r["etichetta"],
            "predicted_n": r.get("predicted_n"),
            "predicted_ms": r.get("predicted_ms"),
            "tps": r.get("gen_tps_server"),
            "draft_n": d_n,
            "draft_n_accepted": r.get("draft_n_accepted"),
            "accettazione": (round(r["draft_n_accepted"] / d_n, 4)
                             if d_n else None),
            "motivo_fine": r.get("motivo_fine"),
            "content_caratteri": r.get("content_caratteri"),
            "reasoning_caratteri": r.get("reasoning_caratteri"),
            "impronta": r.get("impronta_testo_sha256", "")[:16],
        })
    ris["per_caso"] = per_caso

    # --- D15: finito per budget con testo vuoto -----------------------------
    ris["d15_length_con_testo_vuoto"] = [
        r["etichetta"] for r in sel
        if r.get("motivo_fine") == "length"
        and (r.get("content_caratteri") or 0) + (r.get("reasoning_caratteri") or 0) == 0]
    ris["finiti_per_budget"] = [r["etichetta"] for r in sel if r.get("motivo_fine") == "length"]
    ris["content_vuoto_ma_ragionamento_pieno"] = [
        r["etichetta"] for r in sel
        if (r.get("content_caratteri") or 0) == 0 and (r.get("reasoning_caratteri") or 0) > 0]

    # --- carico: picchi -----------------------------------------------------
    carico = c / "carico.jsonl"
    if carico.exists():
        vram, ram, gpu = [], [], []
        for l in carico.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            d = json.loads(l)
            if d.get("vram_usata_mib") is not None:
                vram.append(d["vram_usata_mib"])
            if d.get("ram_usata_gb") is not None:
                ram.append(d["ram_usata_gb"])
            if d.get("gpu_util_pct") is not None:
                gpu.append(d["gpu_util_pct"])
        ris["picchi"] = {
            "vram_max_mib": max(vram) if vram else None,
            "vram_totale_mib": None,
            "ram_usata_max_gb": max(ram) if ram else None,
            "gpu_util_medio_pct": round(sum(gpu) / len(gpu), 1) if gpu else None,
            "campioni": len(vram),
        }

    # --- impronte contro il riferimento ------------------------------------
    if args.riferimento:
        _, rif = carica(args.riferimento)
        imp_rif = {r["etichetta"]: r["impronta_testo_sha256"] for r in rif}
        uguali, diverse, assenti = [], [], []
        for r in righe:
            e = r["etichetta"]
            if e not in imp_rif:
                assenti.append(e)
            elif imp_rif[e] == r["impronta_testo_sha256"]:
                uguali.append(e)
            else:
                diverse.append(e)
        ris["impronte"] = {
            "riferimento": str(Path(args.riferimento).name),
            "n_uguali": len(uguali), "n_diverse": len(diverse),
            "uguali": uguali, "diverse": diverse, "non_confrontabili": assenti,
        }

    print(json.dumps(ris, indent=1, ensure_ascii=False))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(ris, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
