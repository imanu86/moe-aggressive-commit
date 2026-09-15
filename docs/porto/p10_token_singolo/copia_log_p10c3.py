"""P10 cella 3 - raccoglie i log puliti delle corse (V2 di riferimento, V3, V3b) in
`docs/porto/p10_token_singolo/log/` e scrive la tabella di confronto.

Non copia mai la chiave API: gli argomenti del server vengono redatti.

Uso:
    python copia_log_p10c3.py
"""
import json
import re
import shutil
from pathlib import Path

RUN = Path(r"D:\ds4_work\banco_p0_run")
DEST = Path(__file__).resolve().parent / "log"

CORSE = [
    ("V2r1",   "20260915_162514_P10_p10_c2_v2_buchi_mtp_spento_r1"),
    ("V2r2",   "20260915_165455_P10_p10_c2_v2_buchi_mtp_spento_r2"),
    ("V3r1",   "20260915_173505_P10_p10_c3_v3_kernel_iq2s_mtp_spento_r1"),
    ("V3r2",   "20260915_180825_P10_p10_c3_v3_kernel_iq2s_mtp_spento_r2"),
    ("V3b",    "20260915_184154_P10_p10_c3_v3b_kernel_iq2s_e_iq4nl_mtp_spento_r1"),
    ("nsysV3", "20260915_181857_P10_p10_c3_dopo_v3"),
]
NUOVE = {"V3r1", "V3r2", "V3b", "nsysV3"}   # V2* e' gia' in log/ dalla cella 2


def reda(testo):
    testo = re.sub(r"(--api-key\s+)\S+", r"\1<REDATTA>", testo)
    return testo


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    tab = {}
    for eti, nome in CORSE:
        d = RUN / nome
        if not d.exists():
            print("manca:", d)
            continue

        r = d / "riepilogo.json"
        if r.exists():
            dati = json.loads(r.read_text(encoding="utf-8"))
            if eti in NUOVE:
                (DEST / ("p10c3_%s_riepilogo.json" % eti)).write_text(
                    json.dumps(dati, indent=1, ensure_ascii=False), encoding="utf-8")
            tab[eti] = dati
        if eti in NUOVE:
            for src, dst in [("riepilogo.txt", "p10c3_%s_riepilogo.txt" % eti),
                             ("results.jsonl", "p10c3_%s_results.jsonl" % eti)]:
                s = d / src
                if s.exists():
                    shutil.copy2(s, DEST / dst)
            cfg = d / "config.redacted.json"
            if cfg.exists():
                (DEST / ("p10c3_%s_args.redacted.txt" % eti)).write_text(
                    reda(cfg.read_text(encoding="utf-8")), encoding="utf-8")
            car = d / "carico.jsonl"
            if car.exists():
                ramd, vlib, clk, util, watt = [], [], [], [], []
                for l in car.open(encoding="utf-8"):
                    try:
                        x = json.loads(l)
                    except Exception:
                        continue
                    ramd.append(x["ram_disponibile_gb"])
                    vlib.append(x["vram_totale_mib"] - x["vram_usata_mib"])
                    clk.append(x["clock_sm_mhz"])
                    util.append(x["gpu_util_pct"])
                    watt.append(x["watt"])
                mini = {"ram_disponibile_gb_min": min(ramd), "vram_libera_mib_min": min(vlib),
                        "clock_sm_mhz_mediano": sorted(clk)[len(clk)//2],
                        "gpu_util_pct_mediano": sorted(util)[len(util)//2],
                        "watt_mediano": sorted(watt)[len(watt)//2],
                        "campioni": len(ramd)}
                (DEST / ("p10c3_%s_carico_minimi.json" % eti)).write_text(
                    json.dumps(mini, indent=1), encoding="utf-8")

    def msxtok(d):
        i = d["insieme_libero"] if "insieme_libero" in d else d["tutti_i_casi"]
        return i["tempo_generazione_s"] / i["token_accettati"] * 1000.0, i["tps_insieme"]

    righe = []
    for eti in ["V2r1", "V2r2", "V3r1", "V3r2", "V3b"]:
        if eti not in tab:
            continue
        ms, tps = msxtok(tab[eti])
        imp = tab[eti].get("impronte", {})
        righe.append({"corsa": eti, "ms_per_token": ms, "tps": tps, "impronte": imp})

    def media(pref):
        v = [r for r in righe if r["corsa"].startswith(pref) and r["corsa"] != "V3b"]
        if not v:
            return None
        return sum(x["ms_per_token"] for x in v)/len(v), sum(x["tps"] for x in v)/len(v)

    out = {"righe": righe, "media_V2": media("V2"), "media_V3": media("V3")}
    if out["media_V2"] and out["media_V3"]:
        out["delta_ms_per_token"] = out["media_V3"][0] - out["media_V2"][0]
        out["delta_tps"] = out["media_V3"][1] - out["media_V2"][1]
    (DEST / "p10c3_confronto_V2_V3.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    lin = ["| corsa | ms/token | t/s | impronte |", "|---|---:|---:|---|"]
    for r in righe:
        n = len(set(r["impronte"].values()))
        lin.append("| %s | %.3f | %.3f | %d/4 chiavi, %d valori distinti |"
                   % (r["corsa"], r["ms_per_token"], r["tps"], len(r["impronte"]), n))
    if out.get("delta_ms_per_token") is not None:
        lin.append("| **media V2** | **%.3f** | **%.3f** | |" % out["media_V2"])
        lin.append("| **media V3** | **%.3f** | **%.3f** | |" % out["media_V3"])
        lin.append("| **delta** | **%+.3f** | **%+.3f** | |" % (out["delta_ms_per_token"], out["delta_tps"]))
    (DEST / "p10c3_confronto_V2_V3.md").write_text("\n".join(lin) + "\n", encoding="utf-8")
    print("\n".join(lin))


if __name__ == "__main__":
    main()
