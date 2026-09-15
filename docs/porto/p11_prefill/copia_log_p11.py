"""P11 - raccoglie i log puliti delle corse in docs/porto/p11_prefill/log/.

Per ogni corsa copia: riepilogo (json/txt), results.jsonl, gli argomenti redatti,
i minimi di carico (VRAM/RAM) e un ESTRATTO del log del server con le sole righe
che servono al giudizio (workspace, sparse FA, staging, errori CUDA).

Non copia mai la chiave API.

Uso:  python copia_log_p11.py <etichetta>=<nome_cartella_corsa> [...]
"""
import json
import re
import shutil
import sys
from pathlib import Path

RUN = Path(r"D:\ds4_work\banco_p0_run")
DEST = Path(__file__).resolve().parent / "log"

INTERESSANTI = re.compile(
    r"demand workspace|compute buffer size|sparse FA|qwen_prefetch|gdn|"
    r"CUDA error|out of memory|failed to allocate|alloc_tensor_range|"
    r"KV buffer size|model buffer size|n_batch|n_ubatch|n_ctx ", re.I)


def reda(testo):
    return re.sub(r"(--api-key\s+)\S+", r"\1<REDATTA>", testo)


def una(eti, nome):
    d = RUN / nome
    if not d.exists():
        print("manca:", d)
        return None
    DEST.mkdir(parents=True, exist_ok=True)
    dati = None
    r = d / "riepilogo.json"
    if r.exists():
        dati = json.loads(r.read_text(encoding="utf-8"))
        (DEST / ("p11_%s_riepilogo.json" % eti)).write_text(
            json.dumps(dati, indent=1, ensure_ascii=False), encoding="utf-8")
    for src, dst in [("riepilogo.txt", "p11_%s_riepilogo.txt" % eti),
                     ("results.jsonl", "p11_%s_results.jsonl" % eti)]:
        s = d / src
        if s.exists():
            shutil.copy2(s, DEST / dst)
    cfg = d / "config.redacted.json"
    if cfg.exists():
        (DEST / ("p11_%s_config.redacted.json" % eti)).write_text(
            reda(cfg.read_text(encoding="utf-8")), encoding="utf-8")
    car = d / "carico.jsonl"
    if car.exists():
        ramd, vlib, clk, util, watt = [], [], [], [], []
        for l in car.open(encoding="utf-8"):
            try:
                x = json.loads(l)
            except Exception:
                continue
            if x.get("ram_disponibile_gb") is None or x.get("vram_usata_mib") is None:
                continue
            ramd.append(x["ram_disponibile_gb"])
            vlib.append(x["vram_totale_mib"] - x["vram_usata_mib"])
            clk.append(x.get("clock_sm_mhz") or 0)
            util.append(x.get("gpu_util_pct") or 0)
            watt.append(x.get("watt") or 0)
        if ramd:
            mini = {"ram_disponibile_gb_min": min(ramd), "vram_libera_mib_min": round(min(vlib), 1),
                    "vram_libera_mib_mediana": round(sorted(vlib)[len(vlib) // 2], 1),
                    "clock_sm_mhz_mediano": sorted(clk)[len(clk) // 2],
                    "gpu_util_pct_mediano": sorted(util)[len(util) // 2],
                    "watt_mediano": sorted(watt)[len(watt) // 2], "campioni": len(ramd)}
            (DEST / ("p11_%s_carico_minimi.json" % eti)).write_text(
                json.dumps(mini, indent=1), encoding="utf-8")
    log = d / "log" / "server.log"
    if log.exists():
        righe = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines()
                 if INTERESSANTI.search(l)]
        (DEST / ("p11_%s_server_estratto.txt" % eti)).write_text(
            reda("\n".join(righe)) + "\n", encoding="utf-8")
    cl = d / "log" / "client.log"
    if cl.exists():
        (DEST / ("p11_%s_client.log" % eti)).write_text(
            reda(cl.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    ch = d / "log" / "chiusura.json"
    if ch.exists():
        shutil.copy2(ch, DEST / ("p11_%s_chiusura.json" % eti))
    print("raccolto", eti, "->", DEST)
    return dati


def main():
    for a in sys.argv[1:]:
        eti, _, nome = a.partition("=")
        una(eti, nome)


if __name__ == "__main__":
    main()
