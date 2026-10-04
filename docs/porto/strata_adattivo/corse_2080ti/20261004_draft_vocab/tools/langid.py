"""Minimal stopword-based language id and secret screen shared by the corpus scripts (local text only, no downloads)."""
from __future__ import annotations

import re

IT = set("""il lo la i gli le un uno una di a da in con su per tra fra e ed o ma se che chi cui non più come quando dove
perché perche anche sono è e' era sarà essere stato stata hanno ha abbiamo questo questa questi queste quello quella
nel nella nei nelle sul sulla dal dalla dei delle degli del della al alla agli alle ci mi ti si vi ne già solo
molto tutto tutti tutte ogni dopo prima senza sia fare viene può puo deve devono tra cosa così cosi""".split())
EN = set("""the of and to in is that for it with as was on be by at this are from or an which you not have has but
we they their there been were will can would should more than also into over use used using when where what""".split())

WORD = re.compile(r"[A-Za-zÀ-ÿ']+")

SECRET_NAME = re.compile(r"(\.env|secret|credential|password|passwd|token|api[_-]?key|\.pfx|\.pem|\.key|id_rsa|private)",
                         re.I)
SECRET_BODY = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[abp]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|"
    r"(?i:(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{16,}))"
)


def lang_scores(text: str) -> tuple[float, float, int]:
    """(italian stopword share, english stopword share, words) over the first 200k characters."""
    words = [w.lower() for w in WORD.findall(text[:200_000])]
    if not words:
        return 0.0, 0.0, 0
    it = sum(1 for w in words if w in IT)
    en = sum(1 for w in words if w in EN)
    return it / len(words), en / len(words), len(words)


def classify(text: str) -> str:
    it, en, n = lang_scores(text)
    if n < 80:
        return "short"
    if it >= 0.20 and it > 1.3 * en:
        return "it"
    if en >= 0.12 and en > 1.3 * it:
        return "en"
    return "other"


def looks_secret(path: str, text: str) -> bool:
    return bool(SECRET_NAME.search(path)) or bool(SECRET_BODY.search(text))
