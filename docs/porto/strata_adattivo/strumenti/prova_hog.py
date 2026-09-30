"""Collaudo della cache elastica sotto pressione di VRAM (29/9/2026).

Avvia Strata (configurazione del confronto equo, riserva di avvio 1393), manda UNA richiesta lunga in streaming e,
dopo `--hog-at` secondi dal primo token, avvia `hog.exe` che occupa `--hog-mib` MiB di VRAM per `--hog-secs`
secondi, come un altro programma che si apre e poi si chiude. Stampa i token al secondo per finestre di 10 s (un
delta dello stream = un token) e le righe del motore sulla cache elastica. Con `--elastico no` e' il controllo:
lo stesso motore con la cache fissa.

Uso:  python prova_hog.py --elastico si|no [--hog-mib 2500] [--hog-at 20] [--hog-secs 60] [--max-tokens 4096]
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "strata_prova"))
import curva_strata as C  # noqa: E402

OUT = Path(r"D:\ds4_work\strata\prova_hog")
HOG = Path(r"D:\ds4_work\strata\hog.exe")
PROMPT = ("Scrivi un saggio lungo e dettagliato, in italiano, sulla storia dei calcolatori dal telaio di Jacquard "
          "alle GPU di oggi: almeno dodici sezioni, ognuna con esempi concreti, date e nomi.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elastico", choices=["si", "no"], required=True)
    ap.add_argument("--hog-mib", type=int, default=2500)
    ap.add_argument("--hog-at", type=float, default=20.0)
    ap.add_argument("--hog-secs", type=int, default=60)
    ap.add_argument("--max-tokens", type=int, default=4096)
    # 30/9: altro eseguibile (es. build-0129) e nome della corsa
    ap.add_argument("--exe", default=None)
    ap.add_argument("--nome", default=None)
    a = ap.parse_args()
    if a.exe:
        C.BASE["exe"] = a.exe
    OUT.mkdir(parents=True, exist_ok=True)
    nome = a.nome or f"hog_{a.elastico}"
    args = [x for x in C.BASE["args"]]
    i = args.index("--vram-reserve-mib")
    args[i + 1] = "1393"
    if a.elastico == "si":
        args.append("--elastic")
    C.ferma()
    time.sleep(5)
    cfg = dict(C.BASE, args=args, log=str(OUT / f"strata_{nome}.log"))
    cfg_path = C.S / f"prova_{nome}.json"
    cfg_path.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    env = dict(os.environ, STRATA_ELASTIC_TRACE="1")
    v0 = C.vram_mib()
    print(f"[{time.strftime('%H:%M:%S')}] {nome}: VRAM altri programmi {v0} MiB", flush=True)
    srv = subprocess.Popen([str(C.PY), str(C.S / "serve" / "server.py"), "--engine", "strata", "--config", str(cfg_path),
                            "--port", str(C.PORTA)], cwd=str(C.S), env=env,
                           stdout=open(OUT / f"server_{nome}.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    if not C.pronto():
        print("server non pronto", flush=True)
        C.ferma()
        return
    body = {"model": "strata", "messages": [{"role": "user", "content": PROMPT}], "max_tokens": a.max_tokens,
            "stream": True, "temperature": 0}
    req = urllib.request.Request(f"http://127.0.0.1:{C.PORTA}/v1/chat/completions",
                                 data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    stamps, hog_proc, t_first = [], None, None
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            linea = raw.decode("utf-8", errors="replace").strip()
            if not linea.startswith("data:") or linea[5:].strip() == "[DONE]":
                continue
            o = json.loads(linea[5:])
            for ch in o.get("choices", []):
                d = ch.get("delta", {})
                if d.get("content") or d.get("reasoning_content"):
                    now = time.time()
                    t_first = t_first or now
                    stamps.append(now - t_first)
                    if hog_proc is None and now - t_first >= a.hog_at:
                        hog_proc = subprocess.Popen([str(HOG), str(a.hog_mib), str(a.hog_secs)],
                                                    stdout=open(OUT / f"hog_{nome}.log", "w", encoding="utf-8"),
                                                    stderr=subprocess.STDOUT)
                        print(f"  hog avviato a {now - t_first:.1f} s: {a.hog_mib} MiB per {a.hog_secs} s", flush=True)
    if hog_proc is not None:
        hog_proc.wait(timeout=a.hog_secs + 60)
    fine = stamps[-1] if stamps else 0.0
    print(f"  {len(stamps)} delta in {fine:.1f} s", flush=True)
    finestre = []
    for w0 in range(0, int(fine) + 1, 10):
        n = sum(1 for s in stamps if w0 <= s < w0 + 10)
        finestre.append((w0, n / 10.0))
    print("  t/s per 10 s: " + "  ".join(f"{w0}s:{v:.1f}" for w0, v in finestre), flush=True)
    time.sleep(8)
    righe = [l.rstrip() for l in Path(cfg["log"]).read_text(encoding="utf-8", errors="replace").splitlines()
             if "strata elastic:" in l or "stall" in l or "no progress" in l or "hit rate" in l or "LOW" in l]
    for l in righe:
        print("  " + l[:200], flush=True)
    (OUT / f"riassunto_{nome}.json").write_text(json.dumps(
        {"elastico": a.elastico, "vram_altri_mib": v0, "hog_mib": a.hog_mib, "hog_at": a.hog_at,
         "hog_secs": a.hog_secs, "delta": len(stamps), "secondi": fine, "finestre_tps": finestre, "motore": righe},
        indent=1, ensure_ascii=False), encoding="utf-8")
    C.ferma()
    srv.wait(timeout=60)


if __name__ == "__main__":
    main()
