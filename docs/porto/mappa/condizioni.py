#!/usr/bin/env python3
"""Le guardie: per ogni riga di codice, cosa deve essere vero perche' ci si arrivi.

Non e' l'elenco degli `if`. E' la CATENA di condizioni che racchiude ogni sito
interessante (lettura di variabile, chiamata, scrittura di globale), piu' le
guardie di uscita anticipata -- che in questo codice sono il modo normale di
spegnere una funzione intera:

    static void fai_qualcosa(void) {
        if (!abilitato()) return;      <-- da qui in poi tutto il corpo e' guardato
        ...

Uso:  python condizioni.py <radice> <mappa.json> <uscita.json>
"""
import json
import re
import sys
from pathlib import Path

from estrai import spoglia, trova_funzioni, NON_FUNZIONI

USCITE = re.compile(r'^\s*(return|goto|continue|break|abort|exit)\b')
CONTROLLO = re.compile(r'\b(if|while|for|switch)\s*\(')


def _righe_di(testo):
    inizi = [0]
    for m in re.finditer(r'\n', testo):
        inizi.append(m.end())
    return inizi


def _riga(inizi, pos):
    lo, hi = 0, len(inizi) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if inizi[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def _chiudi_parentesi(t, i):
    """i punta a '('; restituisce la posizione della ')' che la chiude."""
    prof = 0
    while i < len(t):
        if t[i] == '(':
            prof += 1
        elif t[i] == ')':
            prof -= 1
            if prof == 0:
                return i
        i += 1
    return None


def _chiudi_graffa(t, i):
    prof = 0
    while i < len(t):
        if t[i] == '{':
            prof += 1
        elif t[i] == '}':
            prof -= 1
            if prof == 0:
                return i
        i += 1
    return None


def normalizza(cond):
    return re.sub(r'\s+', ' ', cond).strip()


def scomponi(cond):
    """Spezza una condizione nei suoi operandi di primo livello.

    `a && (b || c)` -> [('&&', 'a'), ('&&', '(b || c)')]
    Serve perche' un operando falso in una catena `&&` e' *la* precondizione
    mancante, e va potuto cercare da solo.
    """
    pezzi, buf, prof, op = [], [], 0, '&&'
    i = 0
    while i < len(cond):
        c = cond[i]
        if c == '(':
            prof += 1
        elif c == ')':
            prof -= 1
        if prof == 0 and cond[i:i+2] in ('&&', '||'):
            pezzi.append((op, normalizza(''.join(buf))))
            op = cond[i:i+2]
            buf = []
            i += 2
            continue
        buf.append(c)
        i += 1
    resto = normalizza(''.join(buf))
    if resto:
        pezzi.append((op, resto))
    return [p for p in pezzi if p[1]]


def guardie_di_funzione(corpo, base_pos):
    """Costruisce (posizione -> catena di guardie) per un corpo di funzione.

    Restituisce una lista ordinata di eventi (posizione, guardie_attive) da cui
    si ricava la catena di qualunque punto per ricerca binaria.
    """
    eventi = []          # (pos, tuple(guardie))
    pila = []            # [(prof_graffa, testo_guardia, negata)]
    permanenti = []      # guardie da uscita anticipata: valgono fino a fine scope
    prof = 0
    i, n = 0, len(corpo)

    def istantanea(pos):
        att = [g[1] for g in pila] + [p[1] for p in permanenti if p[0] <= prof]
        eventi.append((pos, tuple(att)))

    istantanea(0)
    while i < n:
        c = corpo[i]
        if c == '{':
            prof += 1
            i += 1
            continue
        if c == '}':
            prof -= 1
            while pila and pila[-1][0] >= prof:
                pila.pop()
            permanenti[:] = [p for p in permanenti if p[0] <= prof]
            istantanea(i)
            i += 1
            continue

        m = CONTROLLO.match(corpo, i) or (
            CONTROLLO.search(corpo, i, i + 1) if False else None)
        if not m:
            # cerca la prossima parola chiave di controllo a partire da qui
            m2 = CONTROLLO.search(corpo, i)
            if not m2:
                break
            # salta al match, ma continua a contare le graffe nel mezzo
            salto = corpo[i:m2.start()]
            prof += salto.count('{') - salto.count('}')
            while pila and pila[-1][0] >= prof:
                pila.pop()
            i = m2.start()
            continue

        parola = m.group(1)
        apri = corpo.index('(', m.start())
        chiudi = _chiudi_parentesi(corpo, apri)
        if chiudi is None:
            break
        cond = normalizza(corpo[apri + 1:chiudi])
        if parola == 'for':
            cond = f'ciclo for: {cond}'
        elif parola == 'switch':
            cond = f'switch su {cond}'

        dopo = corpo[chiudi + 1:]
        mg = re.match(r'\s*\{', dopo)
        if mg:
            # blocco con graffe: la guardia vale per tutto il blocco
            pila.append((prof, cond, False))
            istantanea(chiudi)
            i = chiudi + 1 + mg.end() - 1
            prof += 1
            i += 1
            continue

        # niente graffe: guardia di una sola istruzione
        ms = re.match(r'\s*([^;{]*;)', dopo)
        if ms and parola == 'if' and USCITE.match(ms.group(1)):
            # USCITA ANTICIPATA: da qui in poi vale la NEGAZIONE della condizione
            permanenti.append((prof, f'NON ({cond})'))
            istantanea(chiudi)
        i = chiudi + 1
    eventi.sort(key=lambda e: e[0])
    return eventi


def catena(eventi, pos):
    lo, hi, best = 0, len(eventi) - 1, ()
    while lo <= hi:
        mid = (lo + hi) // 2
        if eventi[mid][0] <= pos:
            best = eventi[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return list(best)


LETTURA_ENV = re.compile(r'(?P<come>\w+)\s*\(\s*"(?P<nome>DS4_[A-Z0-9_]+)"')


def analizza(radice, mappa_json, uscita):
    radice = Path(radice)
    mappa = json.loads(Path(mappa_json).read_text(encoding='utf-8'))
    noti = {f['nome'] for f in mappa['funzioni']}

    esclusi = ('build', 'build-verify', '.git', 'gguf-tools', 'tests')
    siti, condizioni_tutte = [], {}
    n_guardie = 0

    file_sorgente = []
    for est in ('*.c', '*.cu', '*.cpp', '*.h', '*.hpp', '*.cuh'):
        for p in radice.rglob(est):
            rel = p.relative_to(radice).as_posix()
            if any(rel.startswith(e + '/') or rel == e for e in esclusi):
                continue
            file_sorgente.append((p, rel))

    for p, rel in sorted(file_sorgente, key=lambda x: x[1]):
        grezzo = p.read_text(encoding='utf-8', errors='replace')
        spoglio = spoglia(grezzo)
        inizi = _righe_di(grezzo)
        funzioni, _ = trova_funzioni(spoglio, grezzo, rel)

        for f in funzioni:
            a, b = f['inizio_corpo'], f['fine_corpo']
            corpo_sp = spoglio[a:b]
            corpo_gr = grezzo[a:b]
            eventi = guardie_di_funzione(corpo_sp, a)
            n_guardie += sum(len(e[1]) for e in eventi[:1]) + len(eventi)

            for m in LETTURA_ENV.finditer(corpo_gr):
                g = catena(eventi, m.start())
                siti.append({
                    'tipo': 'env',
                    'nome': m.group('nome'),
                    'come': m.group('come'),
                    'file': rel,
                    'riga': _riga(inizi, a + m.start()),
                    'funzione': f['nome'],
                    'guardie': g,
                    'operandi': [o for cond in g for o in scomponi(cond)],
                })

            for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', corpo_sp):
                nome = m.group(1)
                if nome in NON_FUNZIONI or nome == f['nome'] or nome not in noti:
                    continue
                g = catena(eventi, m.start())
                if not g:
                    continue      # le chiamate incondizionate non ci interessano
                siti.append({
                    'tipo': 'chiamata',
                    'nome': nome,
                    'file': rel,
                    'riga': _riga(inizi, a + m.start()),
                    'funzione': f['nome'],
                    'guardie': g,
                })

            for _, g in eventi:
                for cond in g:
                    condizioni_tutte[cond] = condizioni_tutte.get(cond, 0) + 1

    dati = {
        'siti': siti,
        'condizioni_frequenti': sorted(condizioni_tutte.items(),
                                       key=lambda x: -x[1])[:200],
        'condizioni_distinte': len(condizioni_tutte),
    }
    Path(uscita).write_text(json.dumps(dati, indent=1), encoding='utf-8')

    env = [s for s in siti if s['tipo'] == 'env']
    guardati = [s for s in env if s['guardie']]
    print(f"  siti totali con guardie   {len(siti)}")
    print(f"  letture env               {len(env)}  di cui GUARDATE {len(guardati)}")
    print(f"  condizioni distinte       {len(condizioni_tutte)}")
    prof = sorted((len(s['guardie']) for s in env), reverse=True)[:1]
    if prof:
        print(f"  catena di guardie piu' profonda su una lettura env: {prof[0]}")


if __name__ == '__main__':
    analizza(sys.argv[1], sys.argv[2], sys.argv[3])
