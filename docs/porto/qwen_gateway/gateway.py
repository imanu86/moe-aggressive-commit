"""Gateway locale per Claude Code: proxy HTTPS (CONNECT) su 127.0.0.1.

Fase 1 — SOLO INOLTRO. Per `api.anthropic.com` termina il TLS col certificato locale (vedi
genera_ca.py), legge la richiesta, la inoltra INTATTA ad Anthropic (header, corpo, abbonamento
compreso) e rimanda la risposta cosi' com'e', in streaming. Ogni altro host passa come tunnel cieco,
senza essere aperto. Serve a verificare che l'app desktop onori HTTPS_PROXY + NODE_EXTRA_CA_CERTS e
a vedere quali richieste partono (modello, subagent si'/no) prima di scrivere l'instradamento.

Non registra MAI header di autenticazione ne' il contenuto dei messaggi: solo metadati.
Solo libreria standard. Avvio: python gateway.py [--porta 8787]
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path

CERT_DIR = Path(os.environ.get("USERPROFILE", ".")) / ".claude" / "qwen-gateway"
INTERCETTA = {"api.anthropic.com"}
LIMITE_TESTA = 1 << 20
SALTO = ("proxy-connection", "connection", "keep-alive")


class Registro:
    def __init__(self, cartella: Path):
        cartella.mkdir(parents=True, exist_ok=True)
        self.f = (cartella / f"gateway_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl").open("a", encoding="utf-8")

    def scrivi(self, **campi) -> None:
        campi = {"ora": datetime.now().strftime("%H:%M:%S.%f")[:-3], **campi}
        self.f.write(json.dumps(campi, ensure_ascii=False) + "\n")
        self.f.flush()


async def travasa(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int:
    n = 0
    try:
        while True:
            dati = await reader.read(65536)
            if not dati:
                break
            n += len(dati)
            writer.write(dati)
            await writer.drain()
    except (ConnectionError, ssl.SSLError, OSError, asyncio.IncompleteReadError):
        pass
    return n


def chiudi(*scrittori: asyncio.StreamWriter | None) -> None:
    for w in scrittori:
        if w is not None:
            try:
                w.close()
            except Exception:
                pass


async def leggi_testa(reader: asyncio.StreamReader) -> tuple[str, list[tuple[str, str]], bytes]:
    grezza = await reader.readuntil(b"\r\n\r\n")
    righe = grezza[:-4].split(b"\r\n")
    prima = righe[0].decode("latin-1")
    intest = []
    for r in righe[1:]:
        k, _, v = r.decode("latin-1").partition(":")
        intest.append((k.strip(), v.strip()))
    return prima, intest, grezza


def valore(intest: list[tuple[str, str]], nome: str) -> str | None:
    return next((v for k, v in intest if k.lower() == nome), None)


async def leggi_corpo(reader: asyncio.StreamReader, intest: list[tuple[str, str]]) -> bytes:
    if "chunked" in (valore(intest, "transfer-encoding") or "").lower():
        corpo = b""
        while True:
            riga = await reader.readuntil(b"\r\n")
            taglia = int(riga.split(b";")[0].strip() or b"0", 16)
            if taglia == 0:
                while (await reader.readuntil(b"\r\n")) != b"\r\n":  # eventuali trailer
                    pass
                return corpo
            corpo += await reader.readexactly(taglia)
            await reader.readexactly(2)
    n = int(valore(intest, "content-length") or 0)
    return await reader.readexactly(n) if n else b""


def metadati(percorso: str, intest: list[tuple[str, str]], corpo: bytes) -> dict:
    m: dict = {"agente": valore(intest, "x-claude-code-agent-id") is not None,
               "sessione": (valore(intest, "x-claude-code-session-id") or "")[:8] or None}
    if percorso.startswith("/v1/messages") and corpo[:1] == b"{":
        try:
            j = json.loads(corpo)
            m.update({"modello": j.get("model"), "stream": bool(j.get("stream")), "messaggi": len(j.get("messages", [])),
                      "tool": len(j.get("tools", []) or []), "max_tokens": j.get("max_tokens"),
                      "campi": sorted(k for k in j if k not in ("messages", "system", "tools", "model", "max_tokens", "stream"))})
        except ValueError:
            pass
    return m


async def inoltra(host: str, c_reader: asyncio.StreamReader, c_writer: asyncio.StreamWriter, reg: Registro) -> None:
    """Una richiesta per connessione: legge, inoltra intatta, rimanda la risposta in streaming, chiude."""
    u_writer = None
    t0 = time.perf_counter()
    try:
        prima, intest, _ = await leggi_testa(c_reader)
        metodo, percorso, _ = prima.split(" ", 2)
        aggiorna = valore(intest, "upgrade") is not None
        corpo = b"" if aggiorna else await leggi_corpo(c_reader, intest)
        info = {"host": host, "metodo": metodo, "percorso": percorso.split("?")[0], "byte_richiesta": len(corpo),
                **metadati(percorso, intest, corpo)}

        ctx = ssl.create_default_context()
        ctx.set_alpn_protocols(["http/1.1"])
        u_reader, u_writer = await asyncio.open_connection(host, 443, ssl=ctx, server_hostname=host, limit=LIMITE_TESTA)

        if aggiorna:  # websocket o simili: testa intatta, poi tubo in entrambe le direzioni
            u_writer.write((prima + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in intest) + "\r\n").encode("latin-1"))
            await u_writer.drain()
            reg.scrivi(**info, esito="upgrade")
            await asyncio.wait([asyncio.ensure_future(travasa(c_reader, u_writer)),
                                asyncio.ensure_future(travasa(u_reader, c_writer))], return_when=asyncio.FIRST_COMPLETED)
            return

        fuori = [(k, v) for k, v in intest if k.lower() not in SALTO and k.lower() not in ("transfer-encoding", "content-length")]
        if corpo or metodo in ("POST", "PUT", "PATCH"):
            fuori.append(("Content-Length", str(len(corpo))))
        fuori.append(("Connection", "close"))
        u_writer.write((prima + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in fuori) + "\r\n").encode("latin-1") + corpo)
        await u_writer.drain()

        r_prima, r_intest, _ = await leggi_testa(u_reader)
        ttfb = time.perf_counter() - t0
        r_fuori = [(k, v) for k, v in r_intest if k.lower() not in SALTO] + [("Connection", "close")]
        c_writer.write((r_prima + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in r_fuori) + "\r\n").encode("latin-1"))
        await c_writer.drain()
        n = await travasa(u_reader, c_writer)
        reg.scrivi(**info, status=int(r_prima.split(" ")[1]), ttfb_ms=round(ttfb * 1e3), totale_ms=round((time.perf_counter() - t0) * 1e3),
                   byte_risposta=n, tipo=valore(r_intest, "content-type"))
    except (asyncio.IncompleteReadError, ConnectionError, ssl.SSLError) as exc:
        reg.scrivi(host=host, esito="connessione chiusa", errore=type(exc).__name__)
    except Exception as exc:
        reg.scrivi(host=host, esito="ERRORE", errore=f"{type(exc).__name__}: {exc}")
        try:
            msg = json.dumps({"type": "error", "error": {"type": "api_error", "message": f"gateway locale: {type(exc).__name__}"}}).encode()
            c_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "
                           + str(len(msg)).encode() + b"\r\n\r\n" + msg)
            await c_writer.drain()
        except Exception:
            pass
    finally:
        chiudi(u_writer, c_writer)


def servi(tls_locale: ssl.SSLContext | None, reg: Registro):
    async def gestisci(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            prima, _, _ = await leggi_testa(reader)
            metodo, bersaglio, _ = prima.split(" ", 2)
            if metodo != "CONNECT":
                writer.write(b"HTTP/1.1 501 Not Implemented\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return chiudi(writer)
            host, _, porta = bersaglio.rpartition(":")
            if tls_locale is not None and host.lower() in INTERCETTA and porta == "443":
                writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                await writer.drain()
                await writer.start_tls(tls_locale)
                return await inoltra(host.lower(), reader, writer, reg)
            # tunnel cieco: il gateway non vede nulla di questo traffico
            try:
                u_reader, u_writer = await asyncio.open_connection(host, int(porta))
            except OSError:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return chiudi(writer)
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            await asyncio.wait([asyncio.ensure_future(travasa(reader, u_writer)),
                                asyncio.ensure_future(travasa(u_reader, writer))], return_when=asyncio.FIRST_COMPLETED)
            chiudi(u_writer, writer)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, ssl.SSLError, ValueError):
            chiudi(writer)
    return gestisci


async def main_async(args) -> None:
    reg = Registro(Path(args.log))
    tls = None
    if (CERT_DIR / "leaf.pem").exists():
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(CERT_DIR / "leaf.pem", CERT_DIR / "leaf.key")
        tls.set_alpn_protocols(["http/1.1"])
    srv = await asyncio.start_server(servi(tls, reg), "127.0.0.1", args.porta, limit=LIMITE_TESTA)
    reg.scrivi(evento="avvio", porta=args.porta, intercetta=sorted(INTERCETTA) if tls else [], fase="solo inoltro")
    print(f"gateway su 127.0.0.1:{args.porta} | intercetta: {sorted(INTERCETTA) if tls else 'niente (mancano i certificati)'}", flush=True)
    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8787)
    ap.add_argument("--log", default=r"D:\ds4_work\qwen_gateway_run\log_gateway")
    try:
        asyncio.run(main_async(ap.parse_args()))
    except KeyboardInterrupt:
        sys.exit(0)
