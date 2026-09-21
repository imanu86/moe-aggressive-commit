"""Prova dell'instradamento Haiku -> server locale attraverso il gateway, SENZA credenziali Anthropic.

  python prova_rotta.py [--porta 8788]

Manda ad https://api.anthropic.com/v1/messages (via proxy, fidandosi della sola CA locale) una richiesta
con modello Haiku fatta come quelle di Claude Code: system a blocchi, un `role: system` a meta'
conversazione, campi extra, un tool vero e uno «lato server» senza input_schema. Se la rotta locale
funziona risponde Qwen; se si ricade su Anthropic arriva il 401 (non ci sono credenziali): entrambe le
uscite sono informative. Poi la stessa cosa con un modello NON Haiku: deve arrivare il 401 di Anthropic.
"""
from __future__ import annotations
import argparse
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

CA = Path(os.environ["USERPROFILE"]) / ".claude" / "qwen-gateway" / "ca.pem"
HAIKU = "claude-haiku-4-5-20251001"


def corpo(modello: str, stream: bool) -> dict:
    return {"model": modello, "max_tokens": 400, "stream": stream,
            "system": [{"type": "text", "text": "x-anthropic-billing-header: cc_version=2.1.270.abc; cc_entrypoint=cli; cch=a5145;"},
                       {"type": "text", "text": "Sei un assistente conciso.", "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Ciao.", "cache_control": {"type": "ephemeral"}}]},
                         {"role": "assistant", "content": [{"type": "text", "text": "Ciao! Dimmi pure."}]},
                         {"role": "system", "content": "Promemoria: rispondi in italiano e in una sola riga."},
                         {"role": "user", "content": "Quanto fa 17 per 3? Rispondi solo col numero."}],
            "tools": [{"name": "leggi_file", "description": "Legge un file.", "defer_loading": False,
                       "input_schema": {"type": "object", "properties": {"percorso": {"type": "string"}}, "required": ["percorso"]}},
                      {"type": "tool_search_tool_regex_20251119", "name": "tool_search"}],
            "thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}, "metadata": {"user_id": "prova"},
            "context_management": {"edits": []}, "diagnostics": {"x": 1}}


def chiama(porta: int, modello: str, stream: bool):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(CA)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": f"http://127.0.0.1:{porta}"}),
                                         urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request("https://api.anthropic.com/v1/messages?beta=true", method="POST",
                                 data=json.dumps(corpo(modello, stream)).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01",
                                          "anthropic-beta": "claude-code-20250219", "x-claude-code-session-id": "prova-rotta"})
    t0 = time.perf_counter()
    try:
        with opener.open(req, timeout=600) as r:
            if not stream:
                return r.status, json.loads(r.read()), time.perf_counter() - t0
            eventi, modello_visto, testo = [], None, ""
            for riga in r:
                s = riga.decode("utf-8", "replace").strip()
                if s.startswith("event:"):
                    eventi.append(s[6:].strip())
                elif s.startswith("data:"):
                    j = json.loads(s[5:])
                    if j.get("type") == "message_start":
                        modello_visto = j["message"].get("model")
                    if j.get("type") == "content_block_delta" and j["delta"].get("type") == "text_delta":
                        testo += j["delta"]["text"]
            return r.status, {"eventi": len(eventi), "ping": eventi.count("ping"), "modello": modello_visto, "testo": testo,
                              "chiusura": eventi[-1] if eventi else None}, time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(200).decode("utf-8", "replace"), time.perf_counter() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8788)
    a = ap.parse_args()
    for nome, modello, stream in (("Haiku in stream    ", HAIKU, True), ("Haiku senza stream ", HAIKU, False),
                                  ("NON Haiku (Sonnet) ", "claude-sonnet-5", True)):
        st, esito, dt = chiama(a.porta, modello, stream)
        if isinstance(esito, dict) and "content" in esito:
            esito = {"modello": esito.get("model"), "testo": " ".join(b.get("text", "") for b in esito["content"] if b.get("type") == "text"),
                     "stop": esito.get("stop_reason"), "usage": esito.get("usage")}
        print(f"{nome}: {st} in {dt:5.1f}s -> {esito}")
