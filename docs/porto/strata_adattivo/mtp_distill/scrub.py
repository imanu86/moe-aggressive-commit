"""scrub.py - bonifica di segreti e dati personali PRIMA che un testo lasci il PC (usato da build_corpus.py).

Regola: si stampano solo CONTEGGI per tipo, mai i valori.  Ogni sostituzione lascia un segnaposto stabile
(`[REDACTED_<TIPO>]`) così il testo resta leggibile e tokenizzabile.

Copre: chiavi API note (OpenAI/Anthropic `sk-`, AWS `AKIA`, GitHub `ghp_/gho_/github_pat_`, Slack `xox*`, Google
`AIza`, RunPod `rpa_`, Supabase `sbp_`, Netlify `nfp_`, Hugging Face `hf_`, Telegram bot, Stripe `sk_live/pk_live`,
SendGrid `SG.`, Railway/UUID dopo una parola-chiave), JWT, `Bearer ...`, blocchi PEM di chiavi private, coppie
`key=value` / `key: value` / `"key": "value"` con parola-chiave (password, token, secret, api_key, ...), righe di file
`.env` (`NOME=valore`), stringhe ad alta entropia vicino a parole-chiave, connection string con password (`://user:pw@`),
e dati personali: IBAN, numeri di carta (Luhn), codice fiscale italiano, telefoni, email.
"""
from __future__ import annotations

import math
import re
from collections import Counter

# ------------------------------------------------------------------------------------------------ segreti
_KEY_WORDS = r"(?:api[_-]?key|apikey|access[_-]?key|secret(?:[_-]?key)?|client[_-]?secret|token|auth(?:orization)?|" \
             r"password|passwd|pwd|passphrase|private[_-]?key|credential[s]?|bearer|session[_-]?id|cookie|signature)"

SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("PEM", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("ANTHROPIC", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OPENAI", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}")),
    ("AWS", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GITHUB", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("SLACK", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("GOOGLE", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("RUNPOD", re.compile(r"\brpa_[A-Za-z0-9]{20,}\b")),
    ("SUPABASE", re.compile(r"\bsbp_[a-fA-F0-9]{30,}\b")),
    ("NETLIFY", re.compile(r"\bnfp_[A-Za-z0-9]{20,}\b")),
    ("HUGGINGFACE", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("STRIPE", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("SENDGRID", re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b")),
    ("TELEGRAM_BOT", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("BEARER", re.compile(r"(?i)\bbearer\s+(?!\[REDACTED)[A-Za-z0-9._~+/=-]{16,}")),
    ("URL_PASSWORD", re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s/:@]+:)([^\s@/]{3,})(@)")),
    # chiave = valore (anche fra virgolette, anche JSON, anche "export NOME=") quando la chiave e' una parola sensibile
    ("KEYVALUE", re.compile(
        r"(?i)(\b(?:export\s+)?[A-Za-z0-9_.-]*" + _KEY_WORDS + r"[A-Za-z0-9_.-]*\b\s*[\"']?\s*[:=]\s*[\"']?)"
        r"(?!\[REDACTED)([^\s\"',;}\]]{6,})")),
    # riga stile .env: NOME_IN_MAIUSCOLO=valore lungo (non un numero, non un percorso evidente)
    ("ENV_LINE", re.compile(r"(?m)^(\s*(?:export\s+)?[A-Z][A-Z0-9_]{2,}=)(?!\[REDACTED)([A-Za-z0-9+/=_.~:-]{16,})\s*$")),
]

_NEAR_KEY = re.compile(r"(?i)" + _KEY_WORDS)
_HIGH_ENTROPY_CAND = re.compile(r"\b[A-Za-z0-9+/_=-]{24,}\b")


def _entropy(s: str) -> float:
    c = Counter(s)
    n = len(s)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def _looks_like_secret_blob(s: str) -> bool:
    if len(s) < 24:
        return False
    classes = sum(bool(re.search(p, s)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]"))
    if classes < 2:
        return False
    if re.fullmatch(r"[0-9a-fA-F-]+", s) and len(s) in (32, 36, 40, 64):   # hash / uuid: segreto solo vicino a chiavi
        return True
    return _entropy(s) >= 3.8


# ------------------------------------------------------------------------------------------------ dati personali
PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?\b")),
    ("CODICE_FISCALE", re.compile(r"\b[A-Z]{6}\d{2}[A-EHLMPRST]\d{2}[A-Z]\d{3}[A-Z]\b")),
    ("PHONE", re.compile(r"(?<![\w/.-])(?:\+|00)\d{1,3}[ .-]?\(?\d{2,4}\)?[ .-]?\d{3,4}[ .-]?\d{3,4}(?![\w/.-])"
                         r"|(?<![\w/.-])3\d{2}[ .-]?\d{3}[ .-]?\d{3,4}(?![\w/.-])")),
    ("CARD", re.compile(r"(?<![\w/.-])(?:\d[ -]?){13,19}(?![\w/.-])")),
]


def _luhn_ok(digits: str) -> bool:
    s, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        s += d
        alt = not alt
    return s % 10 == 0


def _iban_ok(s: str) -> bool:
    s = s.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    moved = s[4:] + s[:4]
    num = "".join(str(int(ch, 36)) for ch in moved)
    return int(num) % 97 == 1


class Scrubber:
    """Applica le bonifiche e conta per tipo.  `scrub(text)` restituisce il testo pulito."""

    def __init__(self, pii: bool = True):
        self.counts: Counter = Counter()
        self.pii = pii

    def _sub(self, kind: str, pat: re.Pattern, text: str, repl) -> str:
        def f(m):
            self.counts[kind] += 1
            return repl(m)
        return pat.sub(f, text)

    def scrub(self, text: str) -> str:
        if not text or len(text) < 6:
            return text
        for kind, pat in SECRET_PATTERNS:
            if kind == "URL_PASSWORD":
                text = self._sub(kind, pat, text, lambda m: m.group(1) + "[REDACTED_PASSWORD]" + m.group(3))
            elif kind in ("KEYVALUE", "ENV_LINE"):
                text = self._sub(kind, pat, text, lambda m: m.group(1) + "[REDACTED_SECRET]")
            else:
                text = self._sub(kind, pat, text, lambda m, k=kind: f"[REDACTED_{k}]")
        # stringhe ad alta entropia entro 60 caratteri da una parola-chiave
        if _NEAR_KEY.search(text):
            def near(m):
                s = m.group(0)
                if s.startswith("[REDACTED") or not _looks_like_secret_blob(s):
                    return s
                lo, hi = max(0, m.start() - 60), m.start()
                if _NEAR_KEY.search(text, lo, hi) is None:
                    return s
                self.counts["HIGH_ENTROPY"] += 1
                return "[REDACTED_SECRET]"
            text = _HIGH_ENTROPY_CAND.sub(near, text)
        if self.pii:
            for kind, pat in PII_PATTERNS:
                if kind == "CARD":
                    def card(m):
                        digits = re.sub(r"\D", "", m.group(0))
                        if 13 <= len(digits) <= 19 and _luhn_ok(digits) and not digits.startswith("0"):
                            self.counts["CARD"] += 1
                            return "[REDACTED_CARD]"
                        return m.group(0)
                    text = pat.sub(card, text)
                elif kind == "IBAN":
                    def iban(m):
                        if _iban_ok(m.group(0)):
                            self.counts["IBAN"] += 1
                            return "[REDACTED_IBAN]"
                        return m.group(0)
                    text = pat.sub(iban, text)
                else:
                    text = self._sub(kind, pat, text, lambda m, k=kind: f"[REDACTED_{k}]")
        return text

    def scrub_obj(self, obj):
        """Bonifica ricorsiva di stringhe dentro dict/list (argomenti dei tool)."""
        if isinstance(obj, str):
            return self.scrub(obj)
        if isinstance(obj, list):
            return [self.scrub_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.scrub_obj(v) for k, v in obj.items()}
        return obj


if __name__ == "__main__":   # prova rapida, solo conteggi
    s = Scrubber()
    sample = ("token=abcDEF123456789012345 export OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz0123 "
              "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U "
              "mail: qualcuno@example.com tel +39 333 1234567 IBAN IT60X0542811101000000123456 carta 4111 1111 1111 1111 "
              "CF RSSMRA85T10A562S postgres://u:segreto@host/db RAILWAY_TOKEN=0123456789abcdef0123456789abcdef")
    out = s.scrub(sample)
    assert "sk-proj" not in out and "example.com" not in out and "4111" not in out
    print(dict(s.counts))
