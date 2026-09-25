"""P0 — client del banco A/B. Presuppone un server GIA' avviato da avvia_blocco.ps1.

Cosa garantisce:
  - fixture congelate lette da fixtures_manifest.json: nessun testo rigenerato al volo;
  - streaming SSE con UTF-8 esplicito in invio e in ricezione (l'invio ISO-8859 corrompe
    i prompt: regola di metodo);
  - TTFT del PRIMO delta e TTFT del PRIMO testo finale visibile, separati;
  - timing originale del server conservato per intero, piu' il confronto con l'orologio
    della richiesta (la differenza e' registrata, non nascosta);
  - impronta SHA256 di reasoning_content + content: in greedy e' un oracolo;
  - campionamento di CPU/GPU/clock/temperature/VRAM/RAM durante tutta la corsa;
  - una cartella per corsa con manifest, config redatta, prompt, risultati, output e log.

Uso tipico (lo fa avvia_blocco.ps1):
  python banco_p0.py --preset preset_A.json --profilo fumo --replica 1 --out D:\\ds4_work\\banco_p0_run
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE.parent / "banco_p0" / "fixtures"  # copia locale (25/9): fixture condivise, sola lettura
BAT_PROD = Path(r"C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat")

# Sequenze in ORDINE FISSO. La coppia A/B esegue la stessa sequenza identica.
PROFILI = {
    # prova end-to-end degli schemi: non e' un benchmark
    "fumo": [("L01", "corto"), ("S01", "corto")],
    # screening del protocollo: 8 liberi x 2 contesti, copia/rinomina, qualita', prefill
    "screening": (
        [(i, "corto") for i in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08")] +
        [(i, "ctx32k") for i in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08")] +
        [("C01", "corto"), ("C02", "corto")] +
        [(i, "corto") for i in ("S01", "S02", "S03", "S04", "S05",
                                "S06", "S07", "S08", "S09", "S10")] +
        [("PF_32K", "ctx32k"), ("PF_131K", "ctx131k")] +
        [("Q_AGO_05", "aghi131k"), ("Q_AGO_25", "aghi131k"), ("Q_AGO_50", "aghi131k"),
         ("Q_AGO_75", "aghi131k"), ("Q_AGO_95", "aghi131k"), ("Q_TEC", "aghi131k")]
    ),
    "solo_libero": ([(i, "corto") for i in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08")] +
                    [(i, "ctx32k") for i in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08")]),
    "solo_prefill": [("PF_32K", "ctx32k"), ("PF_131K", "ctx131k")],
    # 15/9, decisione utente: solo il contesto lungo, due casi liberi a 32k (corsa breve, ~8 min)
    "lungo_2": [("L01", "ctx32k"), ("L02", "ctx32k")],
    # 15/9, punto operativo dell'utente: contesto ~100k+, KV 250k. Un solo prefill freddo a 131k, poi due decode
    "lungo_131k": [("L01", "ctx131k"), ("L02", "ctx131k")],
    # P11 (15/9): SOLO il prefill freddo a 131k. Una richiesta, risposta brevissima (64 token):
    # il tempo della corsa e' quasi tutto prefill, quindi una cella costa ~9 minuti invece di ~12.
    "prefill_131k": [("PF_131K", "ctx131k")],
    # P11 (15/9): cancello di qualita' del candidato finale. Il primo caso paga il prefill freddo
    # del prefisso aghi131k, i cinque successivi riusano la cache del prompt.
    # 25/9, 35B e Ling: il lavoro dell'utente (codice, JSON, copia/rinomina), tutto a contesto corto
    "lavoro": [(i, "corto") for i in ("C01", "C02", "S01", "S02", "S06", "L06", "L07")],
    "aghi_131k": [("Q_AGO_05", "aghi131k"), ("Q_AGO_25", "aghi131k"), ("Q_AGO_50", "aghi131k"),
                  ("Q_AGO_75", "aghi131k"), ("Q_AGO_95", "aghi131k"), ("Q_TEC", "aghi131k")],
}

RISCALDAMENTO = ("Rispondi con una sola parola: pronto.", 8)


# --------------------------------------------------------------------- utilita'
def chiave_api():
    return re.search(r'set "API_KEY=([^"]*)"', BAT_PROD.read_text(errors="replace")).group(1)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def redigi(testo, segreto):
    return testo.replace(segreto, "<REDATTA>") if segreto else testo


# ------------------------------------------------------------ controllo carico
class Sonda(threading.Thread):
    """Campiona CPU/GPU/clock/temperature/VRAM/RAM. Serve a giudicare se la macchina
    era quieta, non a misurare le prestazioni: non e' un profiler."""

    QUERY = ("utilization.gpu,utilization.memory,clocks.sm,clocks.mem,temperature.gpu,"
             "memory.used,memory.total,power.draw")

    def __init__(self, out_path, pid_server, intervallo=2.0):
        super().__init__(daemon=True)
        self.out = Path(out_path)
        self.pid = pid_server
        self.intervallo = intervallo
        self.stop = threading.Event()
        self.etichetta = "avvio"
        self.n = 0
        try:
            import psutil
            self.psutil = psutil
            self.proc = psutil.Process(pid_server) if pid_server else None
            if self.proc:
                self.proc.cpu_percent(None)
            psutil.cpu_percent(None)
        except Exception:
            self.psutil = None
            self.proc = None

    def _gpu(self):
        try:
            p = subprocess.run(["nvidia-smi", "--query-gpu=" + self.QUERY,
                                "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=15)
            v = [x.strip() for x in (p.stdout or "").strip().split(",")]
            nomi = ["gpu_util_pct", "gpu_mem_util_pct", "clock_sm_mhz", "clock_mem_mhz",
                    "temp_c", "vram_usata_mib", "vram_totale_mib", "watt"]
            out = {}
            for k, s in zip(nomi, v):
                try:
                    out[k] = float(s)
                except ValueError:
                    out[k] = None
            return out
        except Exception as exc:
            return {"errore": repr(exc)}

    def run(self):
        with self.out.open("a", encoding="utf-8") as f:
            while not self.stop.is_set():
                r = {"t": round(time.time(), 3), "iso": datetime.now().isoformat(timespec="seconds"),
                     "etichetta": self.etichetta}
                r.update(self._gpu())
                if self.psutil:
                    vm = self.psutil.virtual_memory()
                    r["cpu_pct_totale"] = self.psutil.cpu_percent(None)
                    r["ram_usata_gb"] = round(vm.used / (1 << 30), 2)
                    r["ram_disponibile_gb"] = round(vm.available / (1 << 30), 2)
                    if self.proc is not None:
                        try:
                            r["server_cpu_pct"] = self.proc.cpu_percent(None)
                            mi = self.proc.memory_info()
                            r["server_rss_gb"] = round(mi.rss / (1 << 30), 2)
                        except Exception:
                            r["server_vivo"] = False
                f.write(json.dumps(r) + "\n")
                f.flush()
                self.n += 1
                self.stop.wait(self.intervallo)


# ------------------------------------------------------------------- richieste
class Server:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.key = key
        self.h = {"Content-Type": "application/json; charset=utf-8",
                  "Authorization": "Bearer " + key}

    def get(self, path, timeout=20):
        req = urllib.request.Request(self.url + path, headers=self.h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def chat_stream(self, messaggi, max_tokens, cache_prompt, seed, temperature, timeout=10800):
        body = {"messages": messaggi, "max_tokens": max_tokens, "stream": True,
                "stream_options": {"include_usage": True}, "temperature": temperature,
                "seed": seed, "cache_prompt": cache_prompt, "timings_per_token": False}
        dati = json.dumps(body, ensure_ascii=False).encode("utf-8")  # UTF-8 ESPLICITO
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=dati, headers=self.h)
        t0 = time.perf_counter()
        contenuto, ragionamento = [], []
        t_primo_delta = t_primo_testo = None
        n_chunk = 0
        timings = None
        usage = None
        motivo_fine = None
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
                        motivo_fine = ch["finish_reason"]
                    delta = ch.get("delta", {})
                    c = delta.get("content") or ""
                    rg = delta.get("reasoning_content") or ""
                    if (c or rg):
                        if t_primo_delta is None:
                            t_primo_delta = time.perf_counter()
                        n_chunk += 1
                    if c and t_primo_testo is None:
                        t_primo_testo = time.perf_counter()
                    contenuto.append(c)
                    ragionamento.append(rg)
        t_fine = time.perf_counter()
        return {
            "wall_s": t_fine - t0,
            "ttft_primo_delta_s": (t_primo_delta - t0) if t_primo_delta else None,
            "ttft_primo_testo_finale_s": (t_primo_testo - t0) if t_primo_testo else None,
            "chunk_sse": n_chunk,
            "timings": timings, "usage": usage, "motivo_fine": motivo_fine,
            "content": "".join(contenuto), "reasoning_content": "".join(ragionamento),
        }


# ----------------------------------------------------------------------- corsa
def carica_fixture():
    man = json.loads((FIX / "fixtures_manifest.json").read_text(encoding="utf-8"))
    casi = {c["id"]: c for c in man["casi"]}
    prefissi = {}
    for nome, info in man["prefissi"].items():
        prefissi[nome] = (FIX / info["file"]).read_text(encoding="utf-8")
        assert sha(prefissi[nome]) == info["sha256_testo"], "fixture %s modificata!" % nome
    prompts = {}
    for cid, c in casi.items():
        t = (FIX / "prompts" / c["prompt_file"]).read_text(encoding="utf-8")
        assert sha(t) == c["prompt_sha256"], "prompt %s modificato!" % cid
        prompts[cid] = t
    return man, casi, prefissi, prompts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", required=True)
    ap.add_argument("--profilo", default="fumo", choices=sorted(PROFILI))
    ap.add_argument("--replica", type=int, default=1)
    ap.add_argument("--budget", default="screening", choices=["screening", "conferma"])
    ap.add_argument("--out", default=r"D:\ds4_work\banco_p0_run")
    ap.add_argument("--url", default=None)
    ap.add_argument("--pid-server", type=int, default=0)
    ap.add_argument("--log-server", default=None)
    ap.add_argument("--nota", default="")
    args = ap.parse_args()

    preset = json.loads(Path(args.preset).read_text(encoding="utf-8"))
    url = args.url or "http://%s:%d" % (preset["host"], preset["porta"])
    key = chiave_api()
    srv = Server(url, key)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_run = "%s_%s_%s_r%d" % (stamp, preset["fase"], preset["etichetta"], args.replica)
    run = Path(args.out) / nome_run
    (run / "output").mkdir(parents=True, exist_ok=True)
    (run / "log").mkdir(parents=True, exist_ok=True)
    diario = (run / "log" / "client.log").open("w", encoding="utf-8")

    def eco(msg):
        print(msg, flush=True)
        diario.write(msg + "\n")
        diario.flush()

    eco("corsa: %s" % nome_run)
    eco("preset %s (%s), profilo %s, url %s" % (preset["id"], preset["etichetta"], args.profilo, url))

    man, casi, prefissi, prompts = carica_fixture()
    eco("fixture: %d casi, prefissi %s" % (man["totale_casi"], ", ".join(man["prefissi"])))

    sonda = Sonda(run / "carico.jsonl", args.pid_server or None)
    sonda.start()

    props = None
    try:
        props = srv.get("/props")
    except Exception as exc:
        eco("ATTENZIONE: /props non leggibile: %r" % (exc,))

    config_redatta = {
        "preset": preset,
        "url": url,
        "api_key": "<REDATTA>",
        "profilo": args.profilo, "replica": args.replica, "budget": args.budget,
        "nota": args.nota,
        "props_server": props,
        "fixtures_manifest_sha256": sha((FIX / "fixtures_manifest.json").read_text(encoding="utf-8")),
    }
    if "args" in config_redatta["preset"]:
        config_redatta["preset"]["args"] = [
            "<REDATTA>" if a == key else a for a in preset["args"]]
    (run / "config.redacted.json").write_text(
        json.dumps(config_redatta, indent=1, ensure_ascii=False), encoding="utf-8")

    sequenza = PROFILI[args.profilo]
    prompts_usati = {}
    for cid, ctx in sequenza:
        c = casi[cid]
        pre = c["prefisso_per_contesto"].get(ctx)
        prompts_usati["%s@%s" % (cid, ctx)] = {
            "caso": cid, "contesto": ctx, "prefisso": pre,
            "prompt_sha256": c["prompt_sha256"], "prompt_n_token": c["prompt_n_token"],
            "prefisso_sha256": man["prefissi"][pre]["sha256_testo"] if pre else None,
            "prefisso_n_token": man["prefissi"][pre]["n_token_riverificato"] if pre else 0,
            "budget_token": c["budget_token"][args.budget],
            "insiemi": c["insiemi"], "sottotipo": c["sottotipo"],
        }
    (run / "prompts.json").write_text(json.dumps(
        {"riscaldamento": {"testo": RISCALDAMENTO[0], "max_tokens": RISCALDAMENTO[1],
                           "sha256": sha(RISCALDAMENTO[0]), "ripetizioni": 2},
         "sequenza": ["%s@%s" % t for t in sequenza],
         "dettaglio": prompts_usati}, indent=1, ensure_ascii=False), encoding="utf-8")

    risultati = []
    guasto = None
    prefissi_visti = set()
    ris_path = run / "results.jsonl"
    temperature = preset["campionamento"]["temperature"]
    seed = preset["campionamento"]["seed"]

    def registra(rec):
        risultati.append(rec)
        with ris_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def esegui(etichetta, messaggi, max_tokens, cache_prompt, meta):
        sonda.etichetta = etichetta
        t_inizio = time.time()
        r = srv.chat_stream(messaggi, max_tokens, cache_prompt, seed, temperature)
        tm = r["timings"] or {}
        testo = r["reasoning_content"] + r["content"]
        # Il timing del server include davvero tutto? Confronto con l'orologio della richiesta.
        somma_server_ms = (tm.get("prompt_ms") or 0) + (tm.get("predicted_ms") or 0)
        rec = dict(meta)
        rec.update({
            "etichetta": etichetta,
            "inizio_iso": datetime.fromtimestamp(t_inizio).isoformat(timespec="seconds"),
            "cache_prompt": cache_prompt, "max_tokens": max_tokens,
            "temperature": temperature, "seed": seed,
            "wall_http_s": round(r["wall_s"], 4),
            "ttft_primo_delta_s": None if r["ttft_primo_delta_s"] is None else round(r["ttft_primo_delta_s"], 4),
            "ttft_primo_testo_finale_s": None if r["ttft_primo_testo_finale_s"] is None
            else round(r["ttft_primo_testo_finale_s"], 4),
            "chunk_sse": r["chunk_sse"],
            "motivo_fine": r["motivo_fine"],
            "usage": r["usage"],
            "timings_server": tm,
            "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"),
            "predicted_n": tm.get("predicted_n"),
            "prompt_ms": tm.get("prompt_ms"), "predicted_ms": tm.get("predicted_ms"),
            "prompt_tps_server": tm.get("prompt_per_second"),
            "gen_tps_server": tm.get("predicted_per_second"),
            "draft_n": tm.get("draft_n"), "draft_n_accepted": tm.get("draft_n_accepted"),
            "somma_timing_server_ms": round(somma_server_ms, 3),
            "scarto_orologio_meno_server_ms": round(r["wall_s"] * 1000.0 - somma_server_ms, 3),
            "scarto_relativo_pct": None if somma_server_ms <= 0 else
            round((r["wall_s"] * 1000.0 - somma_server_ms) / somma_server_ms * 100.0, 3),
            "content_caratteri": len(r["content"]),
            "reasoning_caratteri": len(r["reasoning_content"]),
            "impronta_testo_sha256": sha(testo),
            "impronta_solo_content_sha256": sha(r["content"]),
            "troncato_dal_budget": bool(r["motivo_fine"] == "length"),
            "valido": True, "motivo_esclusione": None,
        })
        base = etichetta.replace("@", "_")
        (run / "output" / (base + ".content.txt")).write_text(r["content"], encoding="utf-8")
        (run / "output" / (base + ".reasoning.txt")).write_text(r["reasoning_content"], encoding="utf-8")
        registra(rec)
        eco("  %-22s wall %7.2fs  ttft %6.2f/%-6s  prompt_n %-7s cache_n %-7s pred %-5s "
            "gen %-7s sha %s  fine=%s" % (
                etichetta, rec["wall_http_s"], rec["ttft_primo_delta_s"] or -1,
                ("%.2f" % rec["ttft_primo_testo_finale_s"]) if rec["ttft_primo_testo_finale_s"] else "-",
                rec["prompt_n"], rec["cache_n"], rec["predicted_n"],
                rec["gen_tps_server"], rec["impronta_testo_sha256"][:12], rec["motivo_fine"]))
        return rec

    try:
        # --- due riscaldamenti IDENTICI, esclusi dalle metriche ----------------
        for k in (1, 2):
            esegui("riscaldamento_%d" % k,
                   [{"role": "user", "content": RISCALDAMENTO[0]}], RISCALDAMENTO[1], False,
                   {"caso": "riscaldamento", "contesto": "corto", "prefisso": None,
                    "insiemi": [], "sottotipo": "riscaldamento", "riscaldamento": True,
                    "indice": k})
        imp = [r["impronta_testo_sha256"] for r in risultati if r.get("riscaldamento")]
        eco("  riscaldamenti identici fra loro: %s" % (imp[0] == imp[1]))

        # --- sequenza delle fixture, ordine fisso -----------------------------
        for i, (cid, ctx) in enumerate(sequenza, 1):
            c = casi[cid]
            pre = c["prefisso_per_contesto"].get(ctx)
            messaggi = []
            primo_uso = pre is not None and pre not in prefissi_visti
            if pre:
                messaggi.append({"role": "user",
                                 "content": man["istruzione_contesto"] + prefissi[pre]})
                messaggi.append({"role": "assistant", "content": "pronto"})
                prefissi_visti.add(pre)
            messaggi.append({"role": "user", "content": prompts[cid]})
            # prefill FREDDO al primo uso di un prefisso; dopo si riusa il prefisso
            cache_prompt = not (primo_uso or pre is None)
            esegui("%s@%s" % (cid, ctx), messaggi, c["budget_token"][args.budget], cache_prompt,
                   {"caso": cid, "contesto": ctx, "prefisso": pre,
                    "primo_uso_prefisso": primo_uso, "insiemi": c["insiemi"],
                    "sottotipo": c["sottotipo"], "riscaldamento": False, "indice": i,
                    "atteso": c.get("atteso"), "rubrica": c.get("rubrica")})
    except KeyboardInterrupt:
        guasto = {"tipo": "interruzione_manuale"}
    except Exception as exc:
        guasto = {"tipo": exc.__class__.__name__, "messaggio": redigi(str(exc), key),
                  "ultimo_completato": risultati[-1]["etichetta"] if risultati else None,
                  "quando": datetime.now().isoformat(timespec="seconds")}
        eco("GUASTO: %s" % json.dumps(guasto, ensure_ascii=False))

    sonda.stop.set()
    sonda.join(timeout=10)

    if args.log_server and Path(args.log_server).exists():
        try:
            testo_log = Path(args.log_server).read_text(encoding="utf-8", errors="replace")
            (run / "log" / "server.log").write_text(redigi(testo_log, key), encoding="utf-8")
            eco("log del server copiato e ripulito dalla chiave")
        except Exception as exc:
            eco("ATTENZIONE: log del server non copiato: %r" % (exc,))

    utili = [r for r in risultati if not r.get("riscaldamento") and r["valido"]]
    liberi = [r for r in utili if "libero" in r.get("insiemi", [])]

    def aggrega(gruppo):
        tok = sum((r["predicted_n"] or 0) for r in gruppo)
        tempo = sum((r["predicted_ms"] or 0) for r in gruppo) / 1000.0
        return {"n_casi": len(gruppo), "token_accettati": tok,
                "tempo_generazione_s": round(tempo, 3),
                "tps_insieme": round(tok / tempo, 3) if tempo > 0 else None}

    scarti = [r["scarto_relativo_pct"] for r in utili if r.get("scarto_relativo_pct") is not None]
    riepilogo = {
        "corsa": nome_run, "preset": preset["id"], "etichetta": preset["etichetta"],
        "profilo": args.profilo, "replica": args.replica, "budget": args.budget,
        "n_richieste": len(risultati), "n_riscaldamenti": 2,
        "guasto": guasto,
        "insieme_libero": aggrega(liberi),
        "tutti_i_casi_misurati": aggrega(utili),
        "scarto_orologio_vs_timing_server_pct": {
            "min": round(min(scarti), 3) if scarti else None,
            "max": round(max(scarti), 3) if scarti else None,
            "mediano": round(sorted(scarti)[len(scarti) // 2], 3) if scarti else None,
            "lettura": "lo scarto e' il tempo HTTP che il timing del server NON contiene "
                       "(coda, template, rete locale, serializzazione). Va dichiarato: "
                       "i t/s del server non sono i t/s visti dal client.",
        },
        "impronte": {r["etichetta"]: r["impronta_testo_sha256"][:16] for r in risultati},
        "campioni_carico": sonda.n,
    }
    (run / "riepilogo.json").write_text(json.dumps(riepilogo, indent=1, ensure_ascii=False),
                                        encoding="utf-8")
    manifest = {
        "fase": "P0", "corsa": nome_run, "creato": datetime.now().isoformat(timespec="seconds"),
        "preset_file": str(Path(args.preset).resolve()),
        "preset_sha256": sha(Path(args.preset).read_text(encoding="utf-8")),
        "preset_id": preset["id"], "variante": preset["etichetta"], "replica": args.replica,
        "profilo": args.profilo, "budget": args.budget,
        "fixtures_manifest_sha256": config_redatta["fixtures_manifest_sha256"],
        "snapshot_riferimento": r"D:\ds4_work\p0_snapshot_20260914\manifest_p0.json",
        "file": {p.name: {"bytes": p.stat().st_size} for p in sorted(run.rglob("*")) if p.is_file()},
        "valido": guasto is None,
        "motivo_esclusione": None if guasto is None else "guasto durante la corsa",
        "nota": args.nota,
    }
    (run / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    if guasto:
        (run / "failure.json").write_text(json.dumps(guasto, indent=1, ensure_ascii=False),
                                          encoding="utf-8")

    righe = ["corsa %s" % nome_run,
             "preset %s / %s, profilo %s, replica %d" % (preset["id"], preset["etichetta"],
                                                         args.profilo, args.replica),
             "richieste: %d (2 riscaldamenti esclusi)" % len(risultati),
             "insieme libero: %s" % json.dumps(riepilogo["insieme_libero"]),
             "tutti i casi: %s" % json.dumps(riepilogo["tutti_i_casi_misurati"]),
             "scarto orologio-timing server (%%): %s" % json.dumps(
                 {k: v for k, v in riepilogo["scarto_orologio_vs_timing_server_pct"].items()
                  if k != "lettura"}),
             "campioni di carico: %d" % sonda.n,
             "guasto: %s" % ("nessuno" if guasto is None else json.dumps(guasto, ensure_ascii=False)),
             "", "impronte:"]
    for k, v in riepilogo["impronte"].items():
        righe.append("  %-24s %s" % (k, v))
    (run / "riepilogo.txt").write_text("\n".join(righe) + "\n", encoding="utf-8")

    eco("")
    eco("\n".join(righe))
    diario.close()
    print("CARTELLA_CORSA=%s" % run)
    return 0 if guasto is None else 2


if __name__ == "__main__":
    sys.exit(main())
