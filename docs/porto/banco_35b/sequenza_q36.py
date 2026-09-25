"""Sequenza di blocchi del banco P0 per il 35B (25/9) e tabella riassuntiva.

Ogni blocco = un processo llama-server NUOVO (avvia_blocco.ps1), eseguiti UNO ALLA VOLTA, mai sovrapposti.
Uso:
  python sequenza_q36.py --blocco preset_Q36_B0_elastico_nomtp.json:fumo --blocco ...:lungo_2
  python sequenza_q36.py --solo-tabella CARTELLA [CARTELLA ...]
La tabella legge dalle cartelle delle corse: prefill e decode dai timing del server, accettazione della bozza,
impronta del testo, slot della cache elastica e numero di resize dal log del server, VRAM/RAM dal campionatore.
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# copia locale del lanciatore di banco_p0: stessa logica, guardia che ignora i nodi MSBuild fermi di Visual Studio
AVVIA = HERE / "avvia_blocco_q36.ps1"
ROOT = Path(r"D:\ds4_work\banco_35b_run")


def llama_vivi():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/NH"],
                         capture_output=True, text=True).stdout
    return "llama-server.exe" in out


def esegui_blocco(preset, profilo, nota, diario):
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(AVVIA),
           "-Preset", str(HERE / preset), "-Profilo", profilo, "-OutRoot", str(ROOT), "-Nota", nota]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL)
    testo = r.stdout + "\n" + r.stderr
    with diario.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {preset} {profilo} rc={r.returncode} {time.time() - t0:.0f} s =====\n{testo}\n")
    m = re.findall(r"^CARTELLA_CORSA=(.+)$", testo, flags=re.M)
    return (m[-1].strip() if m else None), r.returncode


def leggi_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))  # chiusura.json di PS 5.1 ha il BOM
    except Exception:
        return None


def elastico(cartella):
    """Slot della cache e resize dal log del server (stderr completo, poi server.log)."""
    info = {"slot_iniziali": None, "slot_finali": None, "resize": 0, "slot_min": None, "slot_max": None}
    for nome in ("server.stderr.txt", "server.log"):
        f = Path(cartella) / "log" / nome
        if not f.exists():
            continue
        slots = []
        for riga in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"MoE expert cache enabled: (\d+) layers x (\d+) slots", riga)
            if m and info["slot_iniziali"] is None:
                info["slot_iniziali"] = int(m.group(2))
            if '"event":"resize"' in riga:
                info["resize"] += 1
                m = re.search(r'"slots":(\d+)', riga)
                if m:
                    slots.append(int(m.group(1)))
        if slots or info["slot_iniziali"] is not None:
            if slots:
                info.update(slot_finali=slots[-1], slot_min=min(slots), slot_max=max(slots))
            break
    return info


def riassumi(cartelle):
    righe = []
    for c in cartelle:
        c = Path(c)
        man = leggi_json(c / "manifest.json") or {}
        cfg = leggi_json(c / "config.redacted.json") or {}
        preset = cfg.get("preset", {})
        chius = leggi_json(c / "log" / "chiusura.json") or {}
        el = elastico(c)
        carico = []
        f = c / "carico.jsonl"
        if f.exists():
            for l in f.read_text(encoding="utf-8").splitlines():
                try:
                    carico.append(json.loads(l))
                except Exception:
                    pass
        vram = [x["vram_usata_mib"] for x in carico if isinstance(x.get("vram_usata_mib"), (int, float))]
        ram = [x["ram_disponibile_gb"] for x in carico if isinstance(x.get("ram_disponibile_gb"), (int, float))]
        f = c / "results.jsonl"
        if not f.exists():
            continue
        for l in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            if r.get("riscaldamento"):
                continue
            dn, da = r.get("draft_n") or 0, r.get("draft_n_accepted") or 0
            righe.append({
                "braccio": preset.get("id"), "etichetta": preset.get("etichetta"), "profilo": man.get("profilo"),
                "caso": r.get("etichetta"), "prompt_n": r.get("prompt_n"), "cache_n": r.get("cache_n"),
                "prefill_tps": r.get("prompt_tps_server"), "decode_tps": r.get("gen_tps_server"),
                "pred_n": r.get("predicted_n"), "accettazione": round(da / dn, 3) if dn else None,
                "draft": f"{da}/{dn}" if dn else "",
                "sha12": (r.get("impronta_testo_sha256") or "")[:12], "fine": r.get("motivo_fine"),
                "slot_iniziali": el["slot_iniziali"], "slot_finali": el["slot_finali"], "resize": el["resize"],
                "vram_max_mib": max(vram) if vram else None, "ram_disp_min_gb": min(ram) if ram else None,
                "carico_s": chius.get("secondi_caricamento"), "cartella": str(c),
            })
    return righe


def tabella(righe):
    t = ["| braccio | profilo | caso | prompt | cache | prefill t/s | decode t/s | accett. | slot ini→fin (resize) "
         "| VRAM max | RAM min | carico s | impronta |",
         "|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|"]
    for r in righe:
        acc = "" if r["accettazione"] is None else f"{r['accettazione']:.1%}"
        slot = "" if r["slot_iniziali"] is None else f"{r['slot_iniziali']}→{r['slot_finali']} ({r['resize']})"
        pf = "" if r["prefill_tps"] is None else f"{r['prefill_tps']:.1f}"
        dc = "" if r["decode_tps"] is None else f"{r['decode_tps']:.2f}"
        t.append(f"| {r['braccio']} | {r['profilo']} | {r['caso']} | {r['prompt_n']} | {r['cache_n']} | {pf} | {dc} "
                 f"| {acc} | {slot} | {r['vram_max_mib']} | {r['ram_disp_min_gb']} | {r['carico_s']} | {r['sha12']} |")
    return "\n".join(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocco", action="append", default=[], help="preset.json:profilo")
    ap.add_argument("--nota", default="matrice Q36 25/9")
    ap.add_argument("--solo-tabella", nargs="*")
    args = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.solo_tabella:
        righe = riassumi(args.solo_tabella)
        print(tabella(righe))
        return
    diario = ROOT / f"sequenza_q36_{stamp}.log"
    cartelle = []
    for b in args.blocco:
        preset, profilo = b.rsplit(":", 1)
        attesa = 0
        while llama_vivi() and attesa < 120:
            time.sleep(5)
            attesa += 5
        if llama_vivi():
            print("ERRORE: un llama-server e' ancora vivo, mi fermo.", flush=True)
            break
        print(f"{datetime.now():%H:%M:%S} avvio {preset} {profilo}", flush=True)
        cartella, rc = esegui_blocco(preset, profilo, args.nota, diario)
        print(f"{datetime.now():%H:%M:%S} fine {preset} {profilo} rc={rc} -> {cartella}", flush=True)
        if cartella:
            cartelle.append(cartella)
        time.sleep(20)
    righe = riassumi(cartelle)
    (ROOT / f"sequenza_q36_{stamp}.json").write_text(json.dumps(righe, indent=1, ensure_ascii=False), encoding="utf-8")
    md = tabella(righe)
    (ROOT / f"sequenza_q36_{stamp}.md").write_text(md + "\n", encoding="utf-8")
    print(md, flush=True)


if __name__ == "__main__":
    main()
