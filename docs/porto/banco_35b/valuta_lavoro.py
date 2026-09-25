"""Valuta l'esito dei casi controllabili del profilo «lavoro» (25/9), secondo gli attesi di prepara_fixture.py.

C01/C02: frazione delle righe attese riprodotte identiche (>= 0,90), per C02 con bound_group -> gruppo_legato
e nessuna occorrenza residua; S01: JSON con esattamente le 4 chiavi e mib_per_token_lordi = 906,24 +- 0,05;
S02: JSON con "ripartizione" di tre interi che sommano 100 e trasferimento massimo; S06: la correzione attesa.
Uso: python valuta_lavoro.py CARTELLA [CARTELLA ...]
"""
import difflib
import json
import re
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "banco_p0" / "fixtures"
SORGENTE = (FIX / "moe-demand_20260914.cuh").read_text(encoding="utf-8").splitlines()


def codice(testo):
    m = re.search(r"```[^\n]*\n(.*?)```", testo, flags=re.S)
    return (m.group(1) if m else testo).splitlines()


def copia(testo, rinomina):
    """Il file e' ~4.000 token e il budget 1024: la copia non puo' finire. Si giudica la parte PRODOTTA:
    quota delle righe prodotte identiche al tratto corrispondente dell'atteso."""
    atteso = [r.replace("bound_group", "gruppo_legato") for r in SORGENTE] if rinomina else SORGENTE
    got = codice(testo)
    if got and got[-1].strip() and len(got) < len(atteso):
        got = got[:-1]  # l'ultima riga di una copia troncata e' di solito a meta'
    if not got:
        return False, "nessuna riga"
    sm = difflib.SequenceMatcher(a=atteso[:len(got) + 5], b=got, autojunk=False)
    uguali = sum(b.size for b in sm.get_matching_blocks())
    frazione = uguali / len(got)
    ok = frazione >= 0.90 and not (rinomina and "bound_group" in testo)
    extra = " (bound_group residuo)" if rinomina and "bound_group" in testo else ""
    return ok, f"{len(got)} righe, identiche {frazione:.0%}{extra}"


def json_puro(testo):
    t = testo.strip()
    try:
        return json.loads(t), ""
    except Exception:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if m:
            try:
                json.loads(m.group(0))
                return None, "JSON con testo intorno"
            except Exception:
                pass
        return None, "JSON non valido"


def s01(testo):
    o, err = json_puro(testo)
    if o is None:
        return False, err
    chiavi = ["strati", "esperti_attivi", "mib_per_esperto", "mib_per_token_lordi"]
    if sorted(o) != sorted(chiavi):
        return False, f"chiavi {sorted(o)}"
    ok = abs(float(o["mib_per_token_lordi"]) - 906.24) <= 0.05 and o["strati"] == 48 and o["esperti_attivi"] == 10
    return ok, f"mib_per_token_lordi={o['mib_per_token_lordi']}"


def s02(testo):
    o, err = json_puro(testo)
    if o is None:
        return False, err
    r = o.get("ripartizione") if isinstance(o, dict) else None
    if not isinstance(r, dict) or sorted(r) != ["calcolo", "coordinamento", "trasferimento"]:
        return False, f"struttura {o}"
    v = list(r.values())
    ok = all(isinstance(x, int) for x in v) and sum(v) == 100 and r["trasferimento"] == max(v)
    return ok, str(r)


def s06(testo):
    ok = any(a in testo for a in ("ultimo_uso[i] < ultimo_uso[migliore]", "ultimo_uso[i] <ultimo_uso[migliore]"))
    return ok, "correzione trovata" if ok else "correzione assente"


PROVE = {"C01": lambda t: copia(t, False), "C02": lambda t: copia(t, True), "S01": s01, "S02": s02, "S06": s06}

for cartella in map(Path, sys.argv[1:]):
    cfg = json.loads((cartella / "config.redacted.json").read_text(encoding="utf-8"))
    nome = cfg["preset"]["id"]
    esiti = []
    for l in (cartella / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        if r.get("riscaldamento") or r["caso"] not in PROVE:
            continue
        testo = (cartella / "output" / f"{r['caso']}_corto.content.txt").read_text(encoding="utf-8")
        ok, dettaglio = PROVE[r["caso"]](testo)
        tronco = " TRONCATO" if r.get("motivo_fine") == "length" else ""
        esiti.append(f"{r['caso']} {'OK' if ok else 'NO'} ({dettaglio}{tronco})")
    print(f"{nome:10s} " + " | ".join(esiti))
