#!/usr/bin/env python3
"""Estrae il grafo del runtime DS4: funzioni, chiamate, variabili d'ambiente, globali.

Deterministico. Nessuna inferenza: o il simbolo c'e' nel testo o non c'e'.
Cio' che non riesce a decidere lo dichiara in `incerti` invece di indovinare.

Uso:  python estrai.py <radice> <uscita.json>
"""
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- pulizia

def spoglia(testo):
    """Sostituisce commenti e stringhe con spazi, conservando righe e colonne.

    Serve perche' altrimenti un `getenv("X")` dentro un commento diventa una
    lettura vera, e una graffa dentro una stringa sfasa tutto il conteggio.
    Le stringhe le teniamo altrove (servono per i nomi delle variabili), qui
    interessa solo che non disturbino il parsing strutturale.
    """
    fuori = []
    i, n = 0, len(testo)
    stato = None  # None | 'riga' | 'blocco' | 'str' | 'chr'
    while i < n:
        c = testo[i]
        due = testo[i:i+2]
        if stato is None:
            if due == '//':
                stato = 'riga'; fuori.append('  '); i += 2; continue
            if due == '/*':
                stato = 'blocco'; fuori.append('  '); i += 2; continue
            if c == '"':
                stato = 'str'; fuori.append(' '); i += 1; continue
            if c == "'":
                stato = 'chr'; fuori.append(' '); i += 1; continue
            fuori.append(c); i += 1; continue
        if stato == 'riga':
            if c == '\n':
                stato = None; fuori.append('\n')
            else:
                fuori.append(' ')
            i += 1; continue
        if stato == 'blocco':
            if due == '*/':
                stato = None; fuori.append('  '); i += 2; continue
            fuori.append('\n' if c == '\n' else ' '); i += 1; continue
        # dentro una stringa o un carattere
        if c == '\\' and i + 1 < n:
            fuori.append('  '); i += 2; continue
        if (stato == 'str' and c == '"') or (stato == 'chr' and c == "'"):
            stato = None
        fuori.append('\n' if c == '\n' else ' ')
        i += 1
    return ''.join(fuori)


# ------------------------------------------------------- definizioni di funzione

# Una definizione inizia a colonna 0 (stile del progetto), ha un nome seguito da
# parentesi, e la sua lista di argomenti si chiude prima di una graffa aperta.
INIZIO_DEF = re.compile(
    r'^(?!\s)'                                   # colonna 0
    r'(?P<pre>(?:[A-Za-z_][\w:*&<>,\s]*?\s+|\*+\s*)*?)'
    r'(?P<nome>[A-Za-z_]\w*)\s*\('
)

# righe che sembrano definizioni ma non lo sono
NON_FUNZIONI = {
    'if', 'for', 'while', 'switch', 'return', 'sizeof', 'else', 'do',
    'defined', 'static_assert', 'typedef', 'struct', 'union', 'enum',
    'case', 'goto', 'catch', 'template',
}

QUALIFICATORI = re.compile(
    r'\b(static|extern|inline|__global__|__device__|__host__|__forceinline__|'
    r'const|unsigned|signed|struct|enum|union|volatile|constexpr|explicit)\b')


def trova_funzioni(spoglio, grezzo, percorso):
    """Restituisce le funzioni con il loro intervallo di righe.

    Il corpo si delimita contando le graffe sul testo spoglio, cosi' le graffe
    dentro stringhe e commenti non falsano il conteggio.
    """
    funzioni = []
    incerti = []
    inizi_riga = [0]
    for m in re.finditer(r'\n', spoglio):
        inizi_riga.append(m.end())

    def riga_di(pos):
        lo, hi = 0, len(inizi_riga) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if inizi_riga[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for m in re.finditer(r'(?m)' + INIZIO_DEF.pattern, spoglio):
        nome = m.group('nome')
        if nome in NON_FUNZIONI:
            continue
        pre = m.group('pre').strip()
        # senza tipo di ritorno non e' una definizione (e' una chiamata a colonna 0
        # o una macro); l'unica eccezione sono i costruttori C++, che qui non usiamo
        if not pre:
            continue

        # trova la parentesi che chiude gli argomenti
        i = m.end() - 1
        prof, fine_args = 0, None
        while i < len(spoglio):
            if spoglio[i] == '(':
                prof += 1
            elif spoglio[i] == ')':
                prof -= 1
                if prof == 0:
                    fine_args = i
                    break
            i += 1
        if fine_args is None:
            continue

        # dopo gli argomenti: una graffa = definizione, un punto e virgola =
        # dichiarazione. In mezzo puo' esserci `const`, `noexcept`, attributi.
        coda = spoglio[fine_args + 1: fine_args + 200]
        mg = re.match(r'[\s\w:\(\)]*?\{', coda)
        if not mg:
            continue
        apertura = fine_args + 1 + mg.end() - 1

        # conta le graffe fino alla chiusura
        prof, j = 0, apertura
        while j < len(spoglio):
            if spoglio[j] == '{':
                prof += 1
            elif spoglio[j] == '}':
                prof -= 1
                if prof == 0:
                    break
            j += 1
        if prof != 0:
            incerti.append({'file': percorso, 'riga': riga_di(m.start()),
                            'nome': nome, 'motivo': 'graffe non bilanciate'})
            continue

        funzioni.append({
            'nome': nome,
            'file': percorso,
            'riga': riga_di(m.start()),
            'riga_fine': riga_di(j),
            'statica': bool(re.search(r'\bstatic\b', pre)),
            'kernel': '__global__' in pre,
            'inizio_corpo': apertura,
            'fine_corpo': j,
        })
    return funzioni, incerti


# ------------------------------------------------------------------ letture env

LETTURA_ENV = re.compile(r'(?P<come>\w+)\s*\(\s*"(?P<nome>DS4_[A-Z0-9_]+)"')
ENV_NUDA = re.compile(r'getenv\s*\(\s*"(?P<nome>DS4_[A-Z0-9_]+)"\s*\)')

# le forme che rivelano una semantica di PRESENZA invece che di VALORE
PRESENZA = [
    (re.compile(r'getenv\s*\([^)]*\)\s*!=\s*NULL'), 'getenv != NULL'),
    (re.compile(r'getenv\s*\([^)]*\)\s*!=\s*nullptr'), 'getenv != nullptr'),
    (re.compile(r'\w+\s*&&\s*\w+\s*\[\s*0\s*\]'), 'var && var[0]'),
    (re.compile(r'if\s*\(\s*getenv\s*\('), 'if (getenv(...))'),
]


def analizza(radice, uscita):
    radice = Path(radice)
    esclusi = ('build', 'build-verify', '.git', 'gguf-tools', 'tests')
    file_sorgente = []
    for est in ('*.c', '*.cu', '*.cpp', '*.h', '*.hpp', '*.cuh'):
        for p in radice.rglob(est):
            rel = p.relative_to(radice).as_posix()
            if any(rel.startswith(e + '/') or rel == e for e in esclusi):
                continue
            file_sorgente.append((p, rel))

    tutte_funzioni, incerti, testi = [], [], {}
    for p, rel in sorted(file_sorgente, key=lambda x: x[1]):
        try:
            grezzo = p.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        spoglio = spoglia(grezzo)
        testi[rel] = (grezzo, spoglio)
        f, inc = trova_funzioni(spoglio, grezzo, rel)
        tutte_funzioni.extend(f)
        incerti.extend(inc)

    per_nome = {}
    for f in tutte_funzioni:
        per_nome.setdefault(f['nome'], []).append(f)
    noti = set(per_nome)

    # ------------------------------------------------ chiamate, env, gate
    chiamate, letture, globali_scritte = [], [], []
    CHIAMATA = re.compile(r'\b([A-Za-z_]\w*)\s*\(')

    for f in tutte_funzioni:
        grezzo, spoglio = testi[f['file']]
        corpo_sp = spoglio[f['inizio_corpo']:f['fine_corpo']]
        # per le stringhe (nomi di variabili) serve il testo grezzo
        righe = grezzo.splitlines()
        corpo_gr = '\n'.join(righe[f['riga'] - 1: f['riga_fine']])

        visti = set()
        for m in CHIAMATA.finditer(corpo_sp):
            n = m.group(1)
            if n in NON_FUNZIONI or n == f['nome'] or n in visti:
                continue
            if n in noti:
                visti.add(n)
                chiamate.append({'da': f['nome'], 'da_file': f['file'], 'a': n})

        for m in LETTURA_ENV.finditer(corpo_gr):
            come, nome = m.group('come'), m.group('nome')
            riga = f['riga'] + corpo_gr[:m.start()].count('\n')
            finestra = corpo_gr[max(0, m.start() - 200): m.start() + 300]
            semantica = 'VALORE'
            prova = None
            if come == 'getenv':
                semantica = 'ignoto'
                for rx, etichetta in PRESENZA:
                    if rx.search(finestra):
                        semantica, prova = 'PRESENZA', etichetta
                        break
            elif come.startswith(('parse_', 'cuda_parse_', 'cuda_env_flag')):
                semantica = 'VALIDATA'
            letture.append({'variabile': nome, 'file': f['file'], 'riga': riga,
                            'funzione': f['nome'], 'come': come,
                            'semantica': semantica, 'prova': prova})

        for m in re.finditer(r'\b(g_[A-Za-z_]\w*)\s*=(?!=)', corpo_sp):
            globali_scritte.append({'globale': m.group(1), 'funzione': f['nome'],
                                    'file': f['file']})

    # letture env fuori da qualunque funzione (inizializzatori, lambda static)
    dentro = {(l['file'], l['riga']) for l in letture}
    for rel, (grezzo, _) in testi.items():
        for m in LETTURA_ENV.finditer(grezzo):
            riga = grezzo[:m.start()].count('\n') + 1
            if (rel, riga) in dentro:
                continue
            letture.append({'variabile': m.group('nome'), 'file': rel, 'riga': riga,
                            'funzione': None, 'come': m.group('come'),
                            'semantica': 'ignoto', 'prova': 'fuori da funzione'})

    dati = {
        'radice': str(radice),
        'file': len(testi),
        'funzioni': [{k: v for k, v in f.items()
                      if k not in ('inizio_corpo', 'fine_corpo')}
                     for f in tutte_funzioni],
        'chiamate': chiamate,
        'letture_env': letture,
        'globali_scritte': globali_scritte,
        'incerti': incerti,
        'duplicati': {n: len(v) for n, v in per_nome.items() if len(v) > 1},
    }
    Path(uscita).write_text(json.dumps(dati, indent=1), encoding='utf-8')

    var = {l['variabile'] for l in letture}
    print(f"  file analizzati    {len(testi)}")
    print(f"  funzioni           {len(tutte_funzioni)}")
    print(f"  archi di chiamata  {len(chiamate)}")
    print(f"  variabili DS4_*    {len(var)}  in {len(letture)} siti di lettura")
    print(f"  globali scritte    {len({g['globale'] for g in globali_scritte})}")
    print(f"  incerti            {len(incerti)}")
    pres = [l for l in letture if l['semantica'] == 'PRESENZA']
    ign = [l for l in letture if l['semantica'] == 'ignoto']
    print(f"  -> semantica di PRESENZA (trappole): {len(pres)}")
    print(f"  -> semantica non decisa:             {len(ign)}")


if __name__ == '__main__':
    analizza(sys.argv[1], sys.argv[2])
