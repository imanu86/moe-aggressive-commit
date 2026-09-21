"""Sonda di /v1/messages (formato Anthropic) sul llama-server locale.

Domanda: cosa accetta il fork di cio' che Claude Code manda davvero? Serve per sapere che cosa il
gateway deve ripulire prima di instradare verso Qwen le richieste destinate a Haiku.

Uso (staccato dalla shell di Claude): python sonda_messages.py --run [--braccio m1]
Esito in D:\\ds4_work\\qwen_gateway_run\\<data_ora>_sonda\\: STATO.txt, rapporto.json, runner.log.
"""
from __future__ import annotations
import argparse
import copy
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server_locale  # noqa: E402

OUT = Path(r"D:\ds4_work\qwen_gateway_run")
MODELLO = "claude-haiku-4-5-20251001"  # l'ID che Claude Code manderebbe: il server locale deve tollerarlo
BETA = "claude-code-20250219,interleaved-thinking-2025-05-14,context-management-2025-06-27,prompt-caching-scope-2026-01-05"

ATTRIBUZIONE = "x-anthropic-billing-header: cc_version=2.1.270.abc; cc_entrypoint=cli; cch=a5145;"
TOOL = {"name": "leggi_file", "description": "Legge un file di testo dal disco e ne restituisce il contenuto.",
        "input_schema": {"type": "object", "properties": {"percorso": {"type": "string", "description": "percorso assoluto"}},
                         "required": ["percorso"]}}

# Campi che Claude Code aggiunge verso un modello che crede un Claude corrente.
CAMPI_EXTRA = {
    "thinking_adaptive": {"thinking": {"type": "adaptive"}},
    "thinking_enabled": {"thinking": {"type": "enabled", "budget_tokens": 1024}},
    "output_config": {"output_config": {"effort": "medium"}},
    "context_management": {"context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]}},
    "metadata": {"metadata": {"user_id": "user_sonda_account__session_0000"}},
    "tool_defer_loading": {"tools": [{**TOOL, "defer_loading": True}]},
    "tool_strict": {"tools": [{**TOOL, "strict": True}]},
    "tool_cache_control": {"tools": [{**TOOL, "cache_control": {"type": "ephemeral"}}]},
    "system_blocchi_cache": {"system": [{"type": "text", "text": ATTRIBUZIONE},
                                        {"type": "text", "text": "Sei un assistente conciso.",
                                         "cache_control": {"type": "ephemeral", "ttl": "1h"}}]},
    "messaggio_blocchi_cache": {"messages": [{"role": "user", "content": [
        {"type": "text", "text": "Rispondi solo con la parola: ok", "cache_control": {"type": "ephemeral"}}]}]},
    "system_a_meta_conversazione": {"messages": [{"role": "user", "content": "Rispondi solo con la parola: ok"},
                                                 {"role": "system", "content": "Promemoria: rispondi in italiano."},
                                                 {"role": "user", "content": "Procedi."}]},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--braccio", default="m1", choices=sorted(server_locale.B.BRACCI))
    args = ap.parse_args()
    if not args.run:
        print("A secco: nessun server avviato. Usa --run. Campi in prova:", ", ".join(CAMPI_EXTRA))
        return 0
    run = OUT / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_sonda_" + args.braccio)
    run.mkdir(parents=True)
    flog = (run / "runner.log").open("w", encoding="utf-8")

    def log(msg: str) -> None:
        flog.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        flog.flush()

    def stato(msg: str) -> None:
        (run / "STATO.txt").write_text(msg + "\n", encoding="utf-8")
        log("STATO " + msg)

    rapporto: dict = {"braccio": args.braccio, "modello_richiesto": MODELLO, "prove": {}}
    errore = None
    try:
        stato("avvio del server")
        with server_locale.server(args.braccio, run, log) as (base, key):
            intest = {"Content-Type": "application/json", "x-api-key": key, "Authorization": "Bearer " + key,
                      "anthropic-version": "2023-06-01", "anthropic-beta": BETA,
                      "x-claude-code-session-id": "sonda", "x-claude-code-agent-id": "agente-sonda"}

            def chiama(percorso: str, corpo: dict | None, metodo: str = "POST", timeout: float = 600):
                dati = json.dumps(corpo).encode("utf-8") if corpo is not None else None
                req = urllib.request.Request(base + percorso, data=dati, method=metodo, headers=intest)
                t0 = time.perf_counter()
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as r:
                        testo = r.read().decode("utf-8", "replace")
                        return r.status, dict(r.headers), testo, time.perf_counter() - t0
                except urllib.error.HTTPError as e:
                    return e.code, dict(e.headers), e.read().decode("utf-8", "replace"), time.perf_counter() - t0

            base_corpo = {"model": MODELLO, "max_tokens": 512,
                          "messages": [{"role": "user", "content": "Rispondi solo con la parola: ok"}]}

            # 1) minimo, senza stream
            stato("prova 1: minimo senza stream")
            st, hd, tx, dt = chiama("/v1/messages?beta=true", base_corpo)
            j = json.loads(tx) if st == 200 else {}
            rapporto["prove"]["minimo"] = {"status": st, "secondi": round(dt, 2), "modello_risposto": j.get("model"),
                                           "tipi_blocchi": [b.get("type") for b in j.get("content", [])],
                                           "blocchi": j.get("content"), "stop_reason": j.get("stop_reason"),
                                           "usage": j.get("usage"), "errore": tx[:600] if st != 200 else None,
                                           "content_type": hd.get("Content-Type")}
            log(f"minimo: {st} in {dt:.1f}s")

            # 2) stream: sequenza degli eventi, ping, tempo al primo byte
            stato("prova 2: stream")
            req = urllib.request.Request(base + "/v1/messages?beta=true", method="POST", headers=intest,
                                         data=json.dumps({**base_corpo, "stream": True}).encode("utf-8"))
            t0 = time.perf_counter()
            eventi, primo, grezzo = [], None, []
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    ct = r.headers.get("Content-Type")
                    for riga in r:
                        if primo is None:
                            primo = time.perf_counter() - t0
                        s = riga.decode("utf-8", "replace").rstrip("\r\n")
                        if len(grezzo) < 40:
                            grezzo.append(s[:300])
                        if s.startswith("event:"):
                            eventi.append(s[6:].strip())
                rapporto["prove"]["stream"] = {"status": 200, "content_type": ct, "primo_byte_s": round(primo or -1, 2),
                                               "totale_s": round(time.perf_counter() - t0, 2),
                                               "sequenza_eventi": _comprimi(eventi), "ha_ping": "ping" in eventi,
                                               "prime_righe": grezzo}
            except urllib.error.HTTPError as e:
                rapporto["prove"]["stream"] = {"status": e.code, "errore": e.read().decode("utf-8", "replace")[:600]}
            log(f"stream: eventi {_comprimi(eventi)}")

            # 3) un campo extra alla volta sopra il corpo minimo
            rapporto["prove"]["campi"] = {}
            for nome, extra in CAMPI_EXTRA.items():
                stato(f"prova 3: campo {nome}")
                corpo = copy.deepcopy(base_corpo)
                corpo.update(copy.deepcopy(extra))
                st, _, tx, dt = chiama("/v1/messages?beta=true", corpo)
                j = json.loads(tx) if st == 200 else {}
                rapporto["prove"]["campi"][nome] = {
                    "status": st, "secondi": round(dt, 2),
                    "tipi_blocchi": [b.get("type") for b in j.get("content", [])] if st == 200 else None,
                    "firma_thinking": next((bool(b.get("signature")) for b in j.get("content", []) if b.get("type") == "thinking"), None),
                    "usage": j.get("usage"), "errore": tx[:500] if st != 200 else None}
                log(f"campo {nome}: {st} in {dt:.1f}s")

            # 4) giro completo di tool use
            stato("prova 4: tool use")
            corpo = {"model": MODELLO, "max_tokens": 1024, "tools": [TOOL],
                     "messages": [{"role": "user", "content": "Usa lo strumento leggi_file per leggere C:\\prova\\note.txt e dimmi cosa contiene."}]}
            st, _, tx, dt = chiama("/v1/messages?beta=true", corpo)
            esito = {"status": st, "secondi": round(dt, 2), "errore": tx[:500] if st != 200 else None}
            if st == 200:
                j = json.loads(tx)
                uso = next((b for b in j.get("content", []) if b.get("type") == "tool_use"), None)
                esito.update({"stop_reason": j.get("stop_reason"), "tipi_blocchi": [b.get("type") for b in j["content"]],
                              "tool_use": uso})
                if uso:
                    corpo["messages"] += [{"role": "assistant", "content": j["content"]},
                                          {"role": "user", "content": [{"type": "tool_result", "tool_use_id": uso["id"],
                                                                        "content": "Comprare il pane. Chiamare Mario alle 18."}]}]
                    st2, _, tx2, dt2 = chiama("/v1/messages?beta=true", corpo)
                    j2 = json.loads(tx2) if st2 == 200 else {}
                    esito["secondo_giro"] = {"status": st2, "secondi": round(dt2, 2), "stop_reason": j2.get("stop_reason"),
                                             "testo": " ".join(b.get("text", "") for b in j2.get("content", []) if b.get("type") == "text")[:400],
                                             "errore": tx2[:500] if st2 != 200 else None}
            rapporto["prove"]["tool_use"] = esito
            log(f"tool use: {st}")

            # 5) endpoint accessori
            stato("prova 5: endpoint accessori")
            st, _, tx, _ = chiama("/v1/messages/count_tokens", {"model": MODELLO, "messages": base_corpo["messages"]})
            rapporto["prove"]["count_tokens"] = {"status": st, "risposta": tx[:300]}
            st, _, tx, _ = chiama("/v1/models", None, metodo="GET")
            rapporto["prove"]["models"] = {"status": st, "risposta": tx[:400]}
    except BaseException as exc:
        errore = f"{type(exc).__name__}: {exc}"
        log("ERRORE " + errore)
    finally:
        rapporto["errore"] = errore
        (run / "rapporto.json").write_text(json.dumps(rapporto, indent=1, ensure_ascii=False), encoding="utf-8")
        stato(("FINE errore: " + errore) if errore else "FINE ok")
        flog.close()
    return 1 if errore else 0


def _comprimi(eventi: list[str]) -> str:
    out, prec, n = [], None, 0
    for e in eventi + [None]:
        if e == prec:
            n += 1
            continue
        if prec is not None:
            out.append(prec if n == 1 else f"{prec}x{n}")
        prec, n = e, 1
    return " ".join(out)


if __name__ == "__main__":
    sys.exit(main())
