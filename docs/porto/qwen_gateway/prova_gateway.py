"""Prova del gateway SENZA toccare Claude Code: due richieste fatte da Python attraverso il proxy.

1. https://api.anthropic.com/v1/models senza credenziali, fidandosi SOLO della CA locale: ci si aspetta
   il 401 vero di Anthropic (= il TLS e' stato aperto col nostro certificato e la richiesta e' arrivata a loro).
2. https://example.com/ con le CA di sistema: ci si aspetta 200 (= tunnel cieco, non intercettato).
"""
from __future__ import annotations
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROXY = "http://127.0.0.1:8787"
CA = Path(os.environ["USERPROFILE"]) / ".claude" / "qwen-gateway" / "ca.pem"


def apri(url: str, ctx: ssl.SSLContext):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": PROXY}), urllib.request.HTTPSHandler(context=ctx))
    try:
        with opener.open(urllib.request.Request(url, headers={"anthropic-version": "2023-06-01"}), timeout=30) as r:
            return r.status, r.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode("utf-8", "replace")


solo_locale = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
solo_locale.load_verify_locations(CA)
print("1) api.anthropic.com via CA locale :", *apri("https://api.anthropic.com/v1/models", solo_locale))
print("2) example.com via CA di sistema    :", *[str(x)[:80] for x in apri("https://example.com/", ssl.create_default_context())])
try:
    apri("https://example.com/", solo_locale)
    print("3) ERRORE: example.com accettato con la sola CA locale")
    sys.exit(1)
except Exception as exc:
    print("3) example.com con la sola CA locale: rifiutato come atteso (", type(exc).__name__, ")")
