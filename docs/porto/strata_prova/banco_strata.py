"""Banco per Strata (github Niko1221/Strata) sulle STESSE fixture del banco P0, 28/9/2026.

Stessi messaggi di banco_p0.py (istruzione + prefisso come primo turno utente, "pronto", poi il caso), stesso budget
«screening» (1024 token per L01/L02), greedy (temperature 0: il server di Strata non manda chiavi di campionamento al
motore e il motore decodifica greedy). Differenza voluta: Strata usa la sua testa MTP (bozza fino a 3 token + prompt
lookup), come la usa chi lo installa. Nessuna chiave API (server solo su 127.0.0.1).

Misure per richiesta: lato client (TTFT del primo delta e del primo testo finale, fine dello stream, chunk, usage) e
lato motore da GET /metrics (prompt_ms, decode_ms, token generati, token riusati dalla cache della conversazione),
piu' la VRAM usata da nvidia-smi prima di ogni richiesta.

Uso:  python banco_strata.py --profilo tutto --etichetta iq3xxs_auto --out D:\\ds4_work\\strata\\banco_run
Profili: lungo_2 (L01/L02 a 32k), lungo_131k (L01/L02 a 131k), tutto (prima 32k poi 131k).
Con --motore llama misura il NOSTRO llama-server (daily in laboratorio, avvia_daily_lab.py) con gli stessi messaggi:
i numeri vengono dai `timings` dello stream (prompt_n/prompt_ms, predicted_n/predicted_ms, cache_n).
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "banco_p0"))
import banco_p0 as P0  # noqa: E402  (carica_fixture, RISCALDAMENTO: stesse fixture e stessi controlli SHA)

PROFILI = {
    "lungo_2": [("L01", "ctx32k"), ("L02", "ctx32k")],
    "lungo_131k": [("L01", "ctx131k"), ("L02", "ctx131k")],
    "tutto": [("L01", "ctx32k"), ("L02", "ctx32k"), ("L01", "ctx131k"), ("L02", "ctx131k")],
    # 28/9 notte, confronto equo e a regime: 8 casi di fila sullo stesso prefisso a 32k (la residenza impara),
    # il punto operativo a 131k, poi copia e rinomina di codice (dove bozza e prompt lookup rendono di piu')
    "regime": ([(i, "ctx32k") for i in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08")] +
               [("L01", "ctx131k"), ("L02", "ctx131k"), ("C01", "corto"), ("C02", "corto")]),
    # ripetizione dei soli casi di codice (copia/rinomina), per controllare se un risultato si ripete
    "codice": [("C01", "corto"), ("C02", "corto")],
    # contesto corto senza copia: separa «contesto corto» da «compito di copia»
    "corto": [("L01", "corto"), ("L06", "corto")],
    # isolamento di una leva di Strata (corsia CPU, bozza): gli stessi casi del regime, meno lunghi
    "isola": ([(i, "ctx32k") for i in ("L01", "L02", "L03", "L04")] +
              [("L01", "ctx131k"), ("L02", "ctx131k"), ("C01", "corto")]),
    # 29/9, curva esperti in VRAM -> velocita' (un punto per dimensione di cache)
    "curva": ([(i, "ctx32k") for i in ("L01", "L02", "L03", "L04")] + [("L01", "ctx131k"), ("L02", "ctx131k")]),
    # 29/9, F0: i prompt che ADDESTRANO il profilo degli esperti (mai usati nella misura) ...
    "addestra": ([("S%02d" % i, "corto") for i in range(1, 11)] + [(i, "corto") for i in ("L05", "L06", "L07", "L08")]),
    # 29/9, A/B rapido (macchina libera, ~3 minuti per motore): solo prompt corti, niente prefill lunghi
    "rapido": ([(i, "corto") for i in ("L01", "L02", "L03", "L04")] + [("C01", "corto")]),
    # ... e quelli che lo MISURANO (disgiunti dai precedenti)
    "f0": ([(i, "ctx32k") for i in ("L01", "L02", "L03", "L04")] + [("L01", "ctx131k"), ("L02", "ctx131k"),
                                                                    ("C01", "corto"), ("C02", "corto")]),
}
BLOCCHI = {  # per il riassunto: nome -> etichette
    "32k_tutti": ["L0%d@ctx32k" % i for i in range(1, 9)],
    "32k_regime_ultimi4": ["L0%d@ctx32k" % i for i in range(5, 9)],
    "32k_codice": ["L06@ctx32k", "L07@ctx32k", "L08@ctx32k"],
    "131k": ["L01@ctx131k", "L02@ctx131k"],
    "copia_rinomina": ["C01@corto", "C02@corto"],
}


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def vram_mib():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout.strip().split(",")
        return int(o[0]), int(o[1])
    except Exception:
        return None, None


def get_json(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat_stream(base, messaggi, max_tokens, timeout=10800):
    body = {"model": "strata", "messages": messaggi, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, "temperature": 0}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    t0 = time.perf_counter()
    contenuto, ragionamento = [], []
    t_primo = t_primo_testo = t_ultimo = None
    n_chunk, usage, fine, timings = 0, None, None, None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            linea = raw.decode("utf-8", errors="replace").strip()
            if not linea.startswith("data:"):
                continue
            d = linea[5:].strip()
            if d == "[DONE]":
                break
            o = json.loads(d)
            if o.get("usage"):
                usage = o["usage"]
            if o.get("timings"):
                timings = o["timings"]
            for ch in o.get("choices", []):
                if ch.get("finish_reason"):
                    fine = ch["finish_reason"]
                delta = ch.get("delta", {})
                c = delta.get("content") or ""
                rg = delta.get("reasoning_content") or ""
                if c or rg:
                    now = time.perf_counter()
                    t_primo = t_primo or now
                    t_ultimo = now
                    n_chunk += 1
                if c and t_primo_testo is None:
                    t_primo_testo = time.perf_counter()
                contenuto.append(c)
                ragionamento.append(rg)
    t_fine = time.perf_counter()
    return {"wall_s": t_fine - t0, "ttft_s": (t_primo - t0) if t_primo else None,
            "ttft_testo_s": (t_primo_testo - t0) if t_primo_testo else None,
            "stream_s": (t_ultimo - t_primo) if t_primo and t_ultimo else None,
            "chunk": n_chunk, "usage": usage, "fine": fine, "timings": timings,
            "content": "".join(contenuto), "reasoning_content": "".join(ragionamento)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18120")
    ap.add_argument("--profilo", default="tutto", choices=sorted(PROFILI))
    ap.add_argument("--etichetta", required=True)
    ap.add_argument("--out", default=r"D:\ds4_work\strata\banco_run")
    ap.add_argument("--nota", default="")
    ap.add_argument("--motore", choices=["strata", "llama"], default="strata")
    a = ap.parse_args()

    run = Path(a.out) / ("%s_%s_%s" % (datetime.now().strftime("%Y%m%d_%H%M%S"), a.etichetta, a.profilo))
    (run / "output").mkdir(parents=True, exist_ok=True)
    man, casi, prefissi, prompts = P0.carica_fixture()
    m0 = get_json(a.url + ("/metrics" if a.motore == "strata" else "/props"))
    (run / "metrics_avvio.json").write_text(json.dumps(m0, indent=1, ensure_ascii=False), encoding="utf-8")
    print("motore:", json.dumps(m0.get("engine") if a.motore == "strata" else m0.get("model_path"),
                                ensure_ascii=False)[:600], flush=True)

    righe = []

    def esegui(etichetta, messaggi, max_tokens, meta):
        v_prima = vram_mib()
        r = chat_stream(a.url, messaggi, max_tokens)
        if a.motore == "strata":
            m = get_json(a.url + "/metrics")
            ult = (m.get("requests") or [{}])[0]
        else:                       # llama-server: i timings dello stream, nella stessa forma
            tm = r["timings"] or {}
            ult = {"prompt_tokens": (tm.get("prompt_n") or 0) + (tm.get("cache_n") or 0), "reused": tm.get("cache_n"),
                   "output_tokens": tm.get("predicted_n"), "prompt_ms": tm.get("prompt_ms"),
                   "decode_ms": tm.get("predicted_ms"), "timings": tm}
        pms, dms = ult.get("prompt_ms"), ult.get("decode_ms")
        nuovi = (ult.get("prompt_tokens") or 0) - (ult.get("reused") or 0)
        rec = dict(meta, etichetta=etichetta, vram_prima_mib=v_prima[0],
                   wall_s=round(r["wall_s"], 3), ttft_s=r["ttft_s"] and round(r["ttft_s"], 3),
                   ttft_testo_s=r["ttft_testo_s"] and round(r["ttft_testo_s"], 3),
                   stream_s=r["stream_s"] and round(r["stream_s"], 3), chunk=r["chunk"], usage=r["usage"],
                   fine=r["fine"], motore=ult,
                   prefill_tps_motore=round(nuovi / (pms / 1000.0), 2) if pms and nuovi > 0 else None,
                   decode_tps_motore=round(ult["output_tokens"] / (dms / 1000.0), 3)
                   if dms and ult.get("output_tokens") else None,
                   impronta_sha256=sha(r["reasoning_content"] + r["content"]),
                   content_caratteri=len(r["content"]), reasoning_caratteri=len(r["reasoning_content"]))
        base = etichetta.replace("@", "_")
        (run / "output" / (base + ".content.txt")).write_text(r["content"], encoding="utf-8")
        (run / "output" / (base + ".reasoning.txt")).write_text(r["reasoning_content"], encoding="utf-8")
        with (run / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        righe.append(rec)
        print("  %-18s prompt %6s nuovi %6s  prefill %8s t/s  decode %7s t/s  out %5s  ttft %7.2f s  vram %s MiB  fine=%s"
              % (etichetta, ult.get("prompt_tokens"), nuovi, rec["prefill_tps_motore"], rec["decode_tps_motore"],
                 ult.get("output_tokens"), rec["ttft_s"] or -1, v_prima[0], r["fine"]), flush=True)

    for k in (1, 2):
        esegui("riscaldamento_%d" % k, [{"role": "user", "content": P0.RISCALDAMENTO[0]}], P0.RISCALDAMENTO[1],
               {"caso": "riscaldamento", "riscaldamento": True})
    for cid, ctx in PROFILI[a.profilo]:
        c = casi[cid]
        pre = c["prefisso_per_contesto"][ctx]
        messaggi = ([{"role": "user", "content": man["istruzione_contesto"] + prefissi[pre]},
                     {"role": "assistant", "content": "pronto"}] if pre else []) + \
                   [{"role": "user", "content": prompts[cid]}]
        esegui("%s@%s" % (cid, ctx), messaggi, c["budget_token"]["screening"],
               {"caso": cid, "contesto": ctx, "riscaldamento": False})

    utili = [r for r in righe if not r.get("riscaldamento")]
    tok = sum(r["motore"].get("output_tokens") or 0 for r in utili)
    sec = sum((r["motore"].get("decode_ms") or 0) for r in utili) / 1000.0
    def blocco(etichette):
        rr = [r for r in utili if r["etichetta"] in etichette]
        t = sum(r["motore"].get("output_tokens") or 0 for r in rr)
        s = sum((r["motore"].get("decode_ms") or 0) for r in rr) / 1000.0
        return {"casi": len(rr), "decode_tps": round(t / s, 3) if s else None}

    riass = {"corsa": run.name, "nota": a.nota, "decode_aggregato_tps": round(tok / sec, 3) if sec else None,
             "blocchi": {nome: blocco(et) for nome, et in BLOCCHI.items()
                         if any(r["etichetta"] in et for r in utili)},
             "per_caso": [{k: r[k] for k in ("etichetta", "prefill_tps_motore", "decode_tps_motore", "ttft_s",
                                              "vram_prima_mib", "fine")} for r in utili]}
    (run / "riassunto.json").write_text(json.dumps(riass, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(riass, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
