"""Fase 2 del gateway: le richieste destinate a Haiku vanno al llama-server locale.

La rotta esiste solo se `%USERPROFILE%\\.claude\\qwen-gateway\\locale.json` c'e' e il server risponde:
    {"base": "http://127.0.0.1:8113", "chiave": "...", "instrada": "tutti" | "subagent"}
Se manca, se il server e' giu' o se risponde con un errore PRIMA che al client sia arrivato
qualcosa, si ricade su Anthropic con la richiesta originale intatta (il vero Haiku).

Cosa cambia sulla rotta locale (dalla sonda del 21/9):
  - `role: system` a meta' conversazione -> turno utente (il template Jinja lo rifiuta);
  - campi e blocchi che un modello locale non capisce vengono tolti; i tool senza `input_schema`
    (tool lato server) o con `defer_loading` pure;
  - il token OAuth dell'abbonamento NON viene mai mandato al server locale;
  - durante il prefill llama-server tace: ogni 10 s il gateway manda un evento `ping`, altrimenti
    Claude Code abortisce dopo 180 s di silenzio;
  - `model` nella risposta torna a essere l'ID richiesto (il server mette il percorso del GGUF).
"""
from __future__ import annotations
import asyncio
import json
import os
import time
import urllib.parse
from pathlib import Path

LOCALE = Path(os.environ.get("USERPROFILE", ".")) / ".claude" / "qwen-gateway" / "locale.json"
TENUTI = ("model", "messages", "system", "tools", "tool_choice", "max_tokens", "stream", "temperature", "top_p",
          "top_k", "stop_sequences", "thinking")
BLOCCHI = {"text", "image", "tool_use", "tool_result", "thinking"}
PING = b'event: ping\ndata: {"type": "ping"}\n\n'
TESTA_SSE = b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n"
ATTESA_TESTA = 15  # secondi concessi al server locale per rispondere prima di impegnarsi col client


def _blocchi(contenuto) -> list[dict]:
    if isinstance(contenuto, str):
        return [{"type": "text", "text": contenuto}] if contenuto else []
    out = []
    for b in contenuto or []:
        if not isinstance(b, dict) or b.get("type") not in BLOCCHI:
            continue
        b = {k: v for k, v in b.items() if k != "cache_control"}
        if b["type"] == "tool_result" and isinstance(b.get("content"), list):
            b["content"] = [{k: v for k, v in x.items() if k != "cache_control"} for x in b["content"]
                            if isinstance(x, dict) and x.get("type") in ("text", "image")]
        out.append(b)
    return out


def pulisci(j: dict) -> dict:
    out = {k: j[k] for k in TENUTI if k in j}
    if isinstance(out.get("system"), list):
        out["system"] = [{"type": "text", "text": b.get("text", "")} for b in out["system"] if isinstance(b, dict) and b.get("type") == "text"]
    messaggi: list[dict] = []
    for m in j.get("messages", []):
        ruolo, blocchi = m.get("role"), _blocchi(m.get("content"))
        if ruolo == "system":
            testo = "\n".join(b.get("text", "") for b in blocchi if b["type"] == "text")
            ruolo, blocchi = "user", [{"type": "text", "text": f"<system-reminder>\n{testo}\n</system-reminder>"}]
        if not blocchi:
            continue
        if messaggi and messaggi[-1]["role"] == ruolo:
            messaggi[-1]["content"] += blocchi
        else:
            messaggi.append({"role": ruolo, "content": blocchi})
    out["messages"] = messaggi
    if "tools" in out:
        out["tools"] = [{k: t[k] for k in ("name", "description", "input_schema") if k in t}
                        for t in out["tools"] or [] if isinstance(t, dict) and "input_schema" in t and not t.get("defer_loading")]
        if not out["tools"]:
            out.pop("tools")
            out.pop("tool_choice", None)
    return out


async def destinazione(metodo: str, percorso: str, info: dict) -> dict | None:
    if metodo != "POST" or percorso.split("?")[0] != "/v1/messages" or "haiku" not in (info.get("modello") or "").lower():
        return None
    try:
        d = json.loads(LOCALE.read_text(encoding="utf-8"))
        u = urllib.parse.urlsplit(d["base"])
    except (OSError, ValueError, KeyError):
        return None
    if d.get("instrada", "tutti") == "subagent" and not info.get("agente"):
        return None
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(u.hostname, u.port), 0.5)
        w.close()
    except (OSError, asyncio.TimeoutError):
        return None
    return d


def _modello_nell_evento(evento: bytes, modello: str) -> bytes:
    righe = evento.split(b"\n")
    for i, r in enumerate(righe):
        if r.startswith(b"data:"):
            try:
                j = json.loads(r[5:])
                if j.get("type") == "message_start":
                    j["message"]["model"] = modello
                    righe[i] = b"data: " + json.dumps(j, ensure_ascii=False).encode("utf-8")
            except (ValueError, KeyError, TypeError):
                pass
    return b"\n".join(righe)


async def servi(dest: dict, corpo: bytes, info: dict, c_writer: asyncio.StreamWriter, reg, t0: float) -> bool:
    """True = il client ha avuto la sua risposta dalla rotta locale. False = nulla e' stato scritto: ricadere."""
    try:
        import aiohttp
    except ImportError:
        return False
    try:
        richiesta = json.loads(corpo)
        pulita = pulisci(richiesta)
    except (ValueError, TypeError, AttributeError) as exc:
        reg.scrivi(**info, esito="locale: corpo non leggibile, ricado", errore=type(exc).__name__)
        return False
    stream, modello = bool(pulita.get("stream")), richiesta.get("model")
    intest = {"Authorization": "Bearer " + dest["chiave"], "x-api-key": dest["chiave"], "anthropic-version": "2023-06-01"}
    impegnato, n_ping, n_byte, ttfb = False, 0, 0, None

    async def ping() -> None:
        nonlocal n_ping
        c_writer.write(PING)
        await c_writer.drain()
        n_ping += 1

    async def errore_sse(msg: str) -> None:
        c_writer.write(b"event: error\ndata: " + json.dumps({"type": "error", "error": {"type": "api_error", "message": msg}}).encode() + b"\n\n")
        await c_writer.drain()

    sessione = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=3))
    try:
        compito = asyncio.ensure_future(sessione.post(dest["base"].rstrip("/") + "/v1/messages", json=pulita, headers=intest))
        while True:
            fatto, _ = await asyncio.wait({compito}, timeout=10 if impegnato else ATTESA_TESTA)
            if fatto:
                break
            if stream:  # il server sta facendo il prefill senza aver ancora risposto: ci si impegna e si pinga
                if not impegnato:
                    c_writer.write(TESTA_SSE)
                    impegnato = True
                await ping()
        try:
            r = compito.result()
        except Exception as exc:
            reg.scrivi(**info, esito="locale: connessione fallita", errore=type(exc).__name__, ricaduta=not impegnato)
            if impegnato:
                await errore_sse("server locale non raggiungibile")
            return impegnato
        if r.status != 200:
            testo = (await r.text())[:200].replace("\n", " ")
            reg.scrivi(**info, esito=f"locale: status {r.status}", errore=testo, ricaduta=not impegnato)
            if impegnato:
                await errore_sse(f"server locale: status {r.status}")
            return impegnato

        if not stream:
            j = json.loads(await r.read())
            j["model"] = modello
            dati = json.dumps(j, ensure_ascii=False).encode("utf-8")
            impegnato = True
            c_writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "
                           + str(len(dati)).encode() + b"\r\n\r\n" + dati)
            await c_writer.drain()
            reg.scrivi(**info, esito="LOCALE", status=200, totale_ms=round((time.perf_counter() - t0) * 1e3), usage=j.get("usage"))
            return True

        if not impegnato:
            c_writer.write(TESTA_SSE)
            impegnato = True
        testa, fine_evento = b"", True
        primo_evento = True
        while True:
            try:
                pezzo = await asyncio.wait_for(r.content.readany(), 10)
            except asyncio.TimeoutError:
                if fine_evento:
                    await ping()
                continue
            if not pezzo:
                break
            if ttfb is None:
                ttfb = time.perf_counter() - t0
            if primo_evento:
                testa += pezzo
                sep = b"\r\n\r\n" if b"\r\n\r\n" in testa else b"\n\n"
                if sep not in testa:
                    continue
                evento, _, resto = testa.partition(sep)
                pezzo = _modello_nell_evento(evento.replace(b"\r\n", b"\n"), modello) + b"\n\n" + resto
                primo_evento = False
            c_writer.write(pezzo)
            await c_writer.drain()
            n_byte += len(pezzo)
            fine_evento = pezzo.endswith(b"\n\n")
        reg.scrivi(**info, esito="LOCALE", status=200, ttfb_ms=round((ttfb or 0) * 1e3),
                   totale_ms=round((time.perf_counter() - t0) * 1e3), byte_risposta=n_byte, ping=n_ping,
                   messaggi_locali=len(pulita["messages"]), tool_locali=len(pulita.get("tools", [])))
        return True
    except Exception as exc:  # qualunque guasto: se al client non e' arrivato nulla si ricade su Anthropic
        reg.scrivi(**info, esito="locale: interrotta", errore=type(exc).__name__, ping=n_ping, ricaduta=not impegnato)
        return impegnato
    finally:
        await sessione.close()
