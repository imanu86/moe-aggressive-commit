"""P9 - client della corsa profilata: stessa sequenza del banco P0 profilo `lungo_131k`,
con due finestre di cattura nsys aperte DENTRO il decode (una per caso).

Perche' un client dedicato e non `banco_p0.py`: la cattura va aperta quando il prefill
e' finito e il decode e' in regime, cioe' al PRIMO delta SSE della risposta. Solo il
client sa quando accade. Le richieste sono costruite con le stesse fixture congelate e
gli stessi parametri del banco (greedy, seed 1234, budget 1024, cache_prompt come il
profilo `lungo_131k`), quindi le IMPRONTE devono coincidere con quelle di P8 R0.

Questa corsa e' DIAGNOSTICA: i suoi ms/token sono misurati col profilatore attaccato e
non sono un benchmark. Il riferimento senza profilatore e' P8 R0 (37,906 ms/token).
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BANCO = Path(r"C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0")
sys.path.insert(0, str(BANCO))
import banco_p0 as B  # noqa: E402


def stream_chat(url, key, messaggi, max_tokens, cache_prompt, seed, temperature,
                on_first_delta=None, timeout=10800):
    """Copia di B.Server.chat_stream con un aggancio al primo delta."""
    body = {"messages": messaggi, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, "temperature": temperature,
            "seed": seed, "cache_prompt": cache_prompt, "timings_per_token": False}
    dati = json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = {"Content-Type": "application/json; charset=utf-8",
         "Authorization": "Bearer " + key}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=dati, headers=h)
    t0 = time.perf_counter()
    contenuto, ragionamento = [], []
    t_primo = None
    timings = usage = motivo = None
    n_chunk = 0
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            linea = raw.decode("utf-8", errors="replace").strip()
            if not linea.startswith("data:"):
                continue
            d = linea[5:].strip()
            if d == "[DONE]":
                break
            o = json.loads(d)
            if o.get("timings"):
                timings = o["timings"]
            if o.get("usage"):
                usage = o["usage"]
            for ch in o.get("choices", []):
                if ch.get("finish_reason"):
                    motivo = ch["finish_reason"]
                delta = ch.get("delta", {})
                c = delta.get("content") or ""
                rg = delta.get("reasoning_content") or ""
                if (c or rg):
                    if t_primo is None:
                        t_primo = time.perf_counter()
                        if on_first_delta:
                            on_first_delta()
                    n_chunk += 1
                contenuto.append(c)
                ragionamento.append(rg)
    t1 = time.perf_counter()
    return {"wall_s": t1 - t0,
            "ttft_primo_delta_s": (t_primo - t0) if t_primo else None,
            "chunk_sse": n_chunk, "timings": timings, "usage": usage,
            "motivo_fine": motivo,
            "content": "".join(contenuto), "reasoning_content": "".join(ragionamento)}


class Cattura:
    """Apre e chiude una finestra nsys nella sessione gia' avviata da `nsys launch`."""

    def __init__(self, nsys, sessione, out_dir, attesa_s, finestra_s, diario):
        self.nsys = nsys
        self.sessione = sessione
        self.out_dir = Path(out_dir)
        self.attesa_s = attesa_s
        self.finestra_s = finestra_s
        self.diario = diario
        self.eventi = []

    def _cmd(self, argv):
        t = time.time()
        p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        return {"argv": argv[1:], "t": round(t, 3), "durata_s": round(time.time() - t, 3),
                "rc": p.returncode, "out": (p.stdout or "")[-400:], "err": (p.stderr or "")[-400:]}

    def apri_dopo(self, etichetta):
        """Thread: aspetta `attesa_s`, apre la cattura, la chiude dopo `finestra_s`."""
        def corpo():
            time.sleep(self.attesa_s)
            out = str(self.out_dir / ("p9_%s" % etichetta))
            a = self._cmd([self.nsys, "start", "--session=" + self.sessione,
                           "-o", out, "--force-overwrite=true"])
            self.diario("    cattura APERTA  %s rc=%s (%.2fs)" % (etichetta, a["rc"], a["durata_s"]))
            time.sleep(self.finestra_s)
            b = self._cmd([self.nsys, "stop", "--session=" + self.sessione])
            self.diario("    cattura CHIUSA  %s rc=%s (%.2fs)" % (etichetta, b["rc"], b["durata_s"]))
            self.eventi.append({"etichetta": etichetta, "output": out + ".nsys-rep",
                                "start": a, "stop": b})
        th = threading.Thread(target=corpo, daemon=True)
        th.start()
        return th


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--preset", required=True)
    ap.add_argument("--out", required=True, help="cartella della corsa")
    ap.add_argument("--nsys", required=True)
    ap.add_argument("--sessione", required=True)
    ap.add_argument("--profila", default="L01,L02", help="quali casi profilare")
    ap.add_argument("--attesa-s", type=float, default=8.0)
    ap.add_argument("--finestra-s", type=float, default=4.0)
    ap.add_argument("--pid-server", type=int, default=0)
    ap.add_argument("--log-server", default=None)
    args = ap.parse_args()

    preset = json.loads(Path(args.preset).read_text(encoding="utf-8"))
    key = B.chiave_api()
    run = Path(args.out)
    (run / "output").mkdir(parents=True, exist_ok=True)
    (run / "log").mkdir(parents=True, exist_ok=True)
    (run / "nsys").mkdir(parents=True, exist_ok=True)
    diario_f = (run / "log" / "client.log").open("w", encoding="utf-8")

    def eco(m):
        print(m, flush=True)
        diario_f.write(m + "\n")
        diario_f.flush()

    eco("corsa P9 profilata: %s" % run.name)
    eco("preset %s (%s) url %s" % (preset["id"], preset["etichetta"], args.url))
    man, casi, prefissi, prompts = B.carica_fixture()
    eco("fixture: %d casi, prefissi %s" % (man["totale_casi"], ", ".join(man["prefissi"])))

    sonda = B.Sonda(run / "carico.jsonl", args.pid_server or None)
    sonda.start()

    cat = Cattura(args.nsys, args.sessione, run / "nsys", args.attesa_s, args.finestra_s, eco)
    da_profilare = set(x.strip() for x in args.profila.split(",") if x.strip())
    risultati = []
    thread_cat = []

    def esegui(etichetta, messaggi, max_tokens, cache_prompt, meta, profila=False):
        sonda.etichetta = etichetta
        hook = (lambda: thread_cat.append(cat.apri_dopo(etichetta))) if profila else None
        t0 = time.time()
        r = stream_chat(args.url, key, messaggi, max_tokens, cache_prompt,
                        preset["campionamento"]["seed"], preset["campionamento"]["temperature"],
                        on_first_delta=hook)
        tm = r["timings"] or {}
        testo = r["reasoning_content"] + r["content"]
        rec = dict(meta)
        rec.update({"etichetta": etichetta, "inizio_iso": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
                    "profilata": profila, "cache_prompt": cache_prompt, "max_tokens": max_tokens,
                    "wall_http_s": round(r["wall_s"], 4),
                    "ttft_primo_delta_s": None if r["ttft_primo_delta_s"] is None else round(r["ttft_primo_delta_s"], 4),
                    "timings_server": tm, "usage": r["usage"], "motivo_fine": r["motivo_fine"],
                    "impronta_testo_sha256": B.sha(testo),
                    "content_caratteri": len(r["content"]), "reasoning_caratteri": len(r["reasoning_content"])})
        base = etichetta.replace("@", "_")
        (run / "output" / (base + ".content.txt")).write_text(r["content"], encoding="utf-8")
        (run / "output" / (base + ".reasoning.txt")).write_text(r["reasoning_content"], encoding="utf-8")
        risultati.append(rec)
        with (run / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        eco("  %-20s wall %8.2fs  prompt_n %-7s cache_n %-7s pred %-5s  ms/tok %-8s sha %s%s" % (
            etichetta, rec["wall_http_s"], tm.get("prompt_n"), tm.get("cache_n"),
            tm.get("predicted_n"),
            None if tm.get("predicted_per_token_ms") is None else round(tm["predicted_per_token_ms"], 3),
            rec["impronta_testo_sha256"][:16], "  [PROFILATA]" if profila else ""))
        return rec

    guasto = None
    try:
        for k in (1, 2):
            esegui("riscaldamento_%d" % k, [{"role": "user", "content": B.RISCALDAMENTO[0]}],
                   B.RISCALDAMENTO[1], False, {"caso": "riscaldamento", "riscaldamento": True, "indice": k})
        visti = set()
        for i, (cid, ctx) in enumerate(B.PROFILI["lungo_131k"], 1):
            c = casi[cid]
            pre = c["prefisso_per_contesto"].get(ctx)
            messaggi = []
            primo = pre is not None and pre not in visti
            if pre:
                messaggi.append({"role": "user", "content": man["istruzione_contesto"] + prefissi[pre]})
                messaggi.append({"role": "assistant", "content": "pronto"})
                visti.add(pre)
            messaggi.append({"role": "user", "content": prompts[cid]})
            esegui("%s@%s" % (cid, ctx), messaggi, c["budget_token"]["screening"],
                   not (primo or pre is None),
                   {"caso": cid, "contesto": ctx, "prefisso": pre, "primo_uso_prefisso": primo,
                    "riscaldamento": False, "indice": i},
                   profila=(cid in da_profilare))
    except Exception as exc:
        guasto = {"tipo": exc.__class__.__name__, "messaggio": str(exc)[:500]}
        eco("GUASTO: %s" % json.dumps(guasto, ensure_ascii=False))

    for th in thread_cat:
        th.join(timeout=120)
    sonda.stop.set()
    sonda.join(timeout=10)

    if args.log_server and Path(args.log_server).exists():
        try:
            testo = Path(args.log_server).read_text(encoding="utf-8", errors="replace")
            (run / "log" / "server.log").write_text(testo.replace(key, "<REDATTA>"), encoding="utf-8")
        except Exception as exc:
            eco("ATTENZIONE: log del server non copiato: %r" % (exc,))

    # minimi di RAM e VRAM libera, come chiede il protocollo
    ram = []
    vram = []
    for l in (run / "carico.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(l)
        except Exception:
            continue
        if d.get("ram_disponibile_gb") is not None:
            ram.append(d["ram_disponibile_gb"])
        if d.get("vram_usata_mib") is not None and d.get("vram_totale_mib"):
            vram.append(d["vram_totale_mib"] - d["vram_usata_mib"])
    riep = {"corsa": run.name, "preset": preset["id"], "guasto": guasto,
            "catture": cat.eventi,
            "ram_disponibile_min_gb": min(ram) if ram else None,
            "vram_libera_min_mib": min(vram) if vram else None,
            "impronte": {r["etichetta"]: r["impronta_testo_sha256"][:16] for r in risultati},
            "ms_per_token_sotto_profilatore": {
                r["etichetta"]: (r["timings_server"] or {}).get("predicted_per_token_ms")
                for r in risultati if not r.get("riscaldamento")}}
    (run / "riepilogo.json").write_text(json.dumps(riep, indent=1, ensure_ascii=False), encoding="utf-8")
    eco("")
    eco(json.dumps(riep, indent=1, ensure_ascii=False))
    diario_f.close()
    print("CARTELLA_CORSA=%s" % run)
    return 0 if guasto is None else 2


if __name__ == "__main__":
    sys.exit(main())
