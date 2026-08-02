#!/usr/bin/env python3
"""LA CATENA. Cerchi una cosa, ti restituisce tutto cio' che scatena.

Per una VARIABILE:
    dove si legge, con quale semantica, sotto quali guardie, chi deve chiamare
    quella funzione perche' la lettura avvenga, cosa la lettura raggiunge, e
    -- la domanda che conta -- QUALI ALTRE VARIABILI vivono sui cammini che
    accende, perche' ognuna di quelle e' il prossimo collo di bottiglia.

Per una FUNZIONE:
    chi la chiama risalendo, cosa chiama scendendo, quali variabili legge il
    suo sottoalbero, e sotto quali condizioni ci si arriva.

Uso:
    python catena.py DS4_CUDA_Q8_F16_CACHE_MB
    python catena.py cuda_q8_f16_cache_has_budget
    python catena.py --trappole              tutte le semantiche di PRESENZA
    python catena.py --orfane                variabili lette e mai consumate
"""
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

QUI = Path(__file__).parent


class Mappa:
    def __init__(self):
        self.m = json.loads((QUI / 'mappa.json').read_text(encoding='utf-8'))
        g = QUI / 'guardie.json'
        self.g = json.loads(g.read_text(encoding='utf-8')) if g.exists() else {'siti': []}

        self.funzioni = defaultdict(list)
        for f in self.m['funzioni']:
            self.funzioni[f['nome']].append(f)

        self.chiama = defaultdict(set)       # f -> chi chiama f
        self.chiamata_da = defaultdict(set)  # f -> chi la chiama
        for c in self.m['chiamate']:
            self.chiama[c['da']].add(c['a'])
            self.chiamata_da[c['a']].add(c['da'])

        self.env_per_var = defaultdict(list)
        self.env_per_funzione = defaultdict(set)
        for l in self.m['letture_env']:
            self.env_per_var[l['variabile']].append(l)
            if l['funzione']:
                self.env_per_funzione[l['funzione']].add(l['variabile'])

        self.guardie_sito = {}
        for s in self.g['siti']:
            if s['tipo'] == 'env':
                self.guardie_sito[(s['file'], s['riga'])] = s['guardie']

        self.globali = defaultdict(set)
        for w in self.m['globali_scritte']:
            self.globali[w['funzione']].add(w['globale'])

    # ------------------------------------------------------------ chiusure
    def discendenti(self, nome, limite=6):
        visti, coda = {nome}, deque([(nome, 0)])
        ordine = []
        while coda:
            n, d = coda.popleft()
            if d >= limite:
                continue
            for succ in sorted(self.chiama.get(n, ())):
                if succ not in visti:
                    visti.add(succ)
                    ordine.append((succ, d + 1))
                    coda.append((succ, d + 1))
        return ordine

    def antenati(self, nome, limite=6):
        visti, coda = {nome}, deque([(nome, 0)])
        ordine = []
        while coda:
            n, d = coda.popleft()
            if d >= limite:
                continue
            for pre in sorted(self.chiamata_da.get(n, ())):
                if pre not in visti:
                    visti.add(pre)
                    ordine.append((pre, d + 1))
                    coda.append((pre, d + 1))
        return ordine

    # ------------------------------------------------------------- stampa
    def variabile(self, nome):
        siti = self.env_per_var.get(nome)
        if not siti:
            simili = [v for v in self.env_per_var if nome.upper() in v]
            print(f"  '{nome}' non e' letta da nessuna parte.")
            if simili:
                print("  forse cercavi:")
                for s in sorted(simili)[:12]:
                    print(f"    {s}")
            return

        print(f"\n{'=' * 78}\n{nome}\n{'=' * 78}")
        print(f"\nLETTA IN {len(siti)} PUNTI")
        funzioni_lettrici = set()
        for s in siti:
            g = self.guardie_sito.get((s['file'], s['riga']), [])
            marchio = {'PRESENZA': '  [TRAPPOLA: presenza, non valore]',
                       'ignoto': '  [semantica non decisa]'}.get(s['semantica'], '')
            print(f"\n  {s['file']}:{s['riga']}  in {s['funzione'] or '(fuori da funzione)'}")
            print(f"    letta con {s['come']}(), semantica {s['semantica']}{marchio}")
            if s.get('prova'):
                print(f"    prova: {s['prova']}")
            if g:
                print(f"    SI ARRIVA QUI SOLO SE ({len(g)} guardie):")
                for c in g:
                    print(f"      - {c[:110]}")
            else:
                print("    nessuna guardia: si legge sempre")
            if s['funzione']:
                funzioni_lettrici.add(s['funzione'])

        # chi deve chiamare, perche' la lettura avvenga
        print("\nPERCHE' LA LETTURA AVVENGA, QUALCUNO DEVE CHIAMARE")
        for f in sorted(funzioni_lettrici):
            su = self.antenati(f, limite=3)
            radici = [n for n, d in su if not self.chiamata_da.get(n)]
            print(f"\n  {f}()")
            diretti = sorted(self.chiamata_da.get(f, ()))[:8]
            if diretti:
                print(f"    chiamata da: {', '.join(diretti)}")
            else:
                print("    chiamata da: NESSUNO -- e' un punto d'ingresso o e' morta")
            if radici:
                print(f"    risalendo si arriva a: {', '.join(sorted(set(radici))[:6])}")

        # cosa accende, e con chi si incrocia
        print("\nCOSA ACCENDE (cammini raggiungibili dalle funzioni lettrici)")
        raggiunte = set()
        for f in funzioni_lettrici:
            raggiunte.update(n for n, _ in self.discendenti(f, limite=4))
        print(f"  {len(raggiunte)} funzioni raggiungibili")

        altre = defaultdict(set)
        for f in raggiunte:
            for v in self.env_per_funzione.get(f, ()):
                if v != nome:
                    altre[v].add(f)
        if altre:
            print(f"\nALTRE VARIABILI SUI CAMMINI CHE ACCENDE  ({len(altre)})")
            print("  ognuna di queste e' il prossimo collo di bottiglia possibile:")
            for v, dove in sorted(altre.items(), key=lambda x: -len(x[1])):
                sem = {s['semantica'] for s in self.env_per_var[v]}
                t = ' [PRESENZA]' if 'PRESENZA' in sem else ''
                print(f"    {v}{t}")
                print(f"        letta in {', '.join(sorted(dove)[:3])}")
        else:
            print("\n  nessun'altra variabile sui cammini che accende")

        glob = set()
        for f in raggiunte | funzioni_lettrici:
            glob.update(self.globali.get(f, ()))
        if glob:
            print(f"\nGLOBALI SCRITTE SU QUEI CAMMINI ({len(glob)})")
            print("  " + ', '.join(sorted(glob)[:24]))

    def funzione(self, nome):
        defs = self.funzioni.get(nome)
        if not defs:
            simili = [f for f in self.funzioni if nome.lower() in f.lower()]
            print(f"  '{nome}' non e' una funzione conosciuta.")
            for s in sorted(simili)[:14]:
                print(f"    {s}")
            return
        print(f"\n{'=' * 78}\n{nome}()\n{'=' * 78}")
        for d in defs:
            marchio = ' static' if d['statica'] else ''
            marchio += ' __global__' if d.get('kernel') else ''
            print(f"  {d['file']}:{d['riga']}-{d['riga_fine']}{marchio}")

        su = self.antenati(nome, limite=4)
        print(f"\nCHI LA CHIAMA, risalendo ({len(su)} funzioni)")
        per_liv = defaultdict(list)
        for n, d in su:
            per_liv[d].append(n)
        for d in sorted(per_liv)[:4]:
            print(f"  livello {d}: {', '.join(sorted(per_liv[d])[:10])}")

        giu = self.discendenti(nome, limite=3)
        print(f"\nCOSA CHIAMA, scendendo ({len(giu)} funzioni)")
        per_liv = defaultdict(list)
        for n, d in giu:
            per_liv[d].append(n)
        for d in sorted(per_liv)[:3]:
            print(f"  livello {d}: {', '.join(sorted(per_liv[d])[:10])}")

        var = set(self.env_per_funzione.get(nome, ()))
        for n, _ in giu:
            var.update(self.env_per_funzione.get(n, ()))
        if var:
            print(f"\nVARIABILI LETTE NEL SUO SOTTOALBERO ({len(var)})")
            for v in sorted(var):
                sem = {s['semantica'] for s in self.env_per_var[v]}
                print(f"    {v}{' [PRESENZA]' if 'PRESENZA' in sem else ''}")

    def trappole(self):
        pres = [l for l in self.m['letture_env'] if l['semantica'] == 'PRESENZA']
        per_var = defaultdict(list)
        for l in pres:
            per_var[l['variabile']].append(l)
        print(f"\n{len(per_var)} VARIABILI con almeno un sito a semantica di PRESENZA")
        print("  (metterle a 0 le ACCENDE invece di spegnerle)\n")
        for v, siti in sorted(per_var.items()):
            print(f"  {v}")
            for s in siti[:2]:
                print(f"      {s['file']}:{s['riga']}  {s['prova'] or ''}")

    def doppioni(self):
        """Chi fa la STESSA COSA di qualcun altro.

        Esiste perche' costruire guardando l'intorno minimo porta a duplicare
        cio' che c'e' gia' altrove: la nostra arena duplicava lo streaming SSD
        di upstream (-38%), il nostro route worker duplica il loro caricamento
        asincrono, la nostra cattura router rifa' un readback gia' fatto.

        Raggruppa per (categoria, frequenza, fase, effetto su VRAM) e mostra i
        gruppi con piu' occupanti: dentro quei gruppi si guarda se due
        meccanismi si contendono la stessa risorsa.

        Richiede che le schede siano state fuse (ricongiungi.py).
        """
        annotate = [f for f in self.m['funzioni'] if f.get('categoria')]
        if not annotate:
            print("  nessuna scheda fusa: esegui prima ricongiungi.py")
            return
        gruppi = defaultdict(list)
        for f in annotate:
            if f['frequenza'] in ('mai', 'avvio', 'ignoto'):
                continue          # i doppioni che contano sono sul cammino caldo
            if f['categoria'] in ('altro', 'parsing', 'test'):
                continue          # 'altro' e' un raccoglitore: un gruppo li' dentro
                                  # mette insieme cose che non c'entrano fra loro
            chiave = (f['categoria'], f['frequenza'], f['fase'], f['vram'])
            gruppi[chiave].append(f)

        print(f"\n  {len(annotate)} funzioni schedate, "
              f"{sum(len(v) for v in gruppi.values())} sul cammino caldo\n")
        print("  GRUPPI CHE FANNO LA STESSA COSA ALLA STESSA FREQUENZA")
        print("  (dentro un gruppo, due meccanismi possono contendersi la stessa risorsa)\n")
        for k, v in sorted(gruppi.items(), key=lambda x: -len(x[1])):
            if len(v) < 2:
                continue
            cat, fre, fas, vr = k
            print(f"  [{cat} / {fre} / {fas} / vram:{vr}]  {len(v)} funzioni")
            for f in sorted(v, key=lambda x: x['file'])[:8]:
                print(f"      {f['nome']:<46} {f['file']}:{f['riga']}")
                print(f"          {f.get('ruolo', '')[:96]}")
            if len(v) > 8:
                print(f"      (+{len(v) - 8} altre)")
            print()

    def orfane(self):
        morte = []
        for v, siti in self.env_per_var.items():
            f = {s['funzione'] for s in siti if s['funzione']}
            if not f:
                morte.append((v, 'letta fuori da qualunque funzione'))
                continue
            if not any(self.chiamata_da.get(x) for x in f):
                morte.append((v, f"letta solo in {', '.join(sorted(f)[:2])}, "
                                 "che nessuno chiama"))
        print(f"\n{len(morte)} VARIABILI SOSPETTE DI ESSERE INERTI\n")
        for v, perche in sorted(morte):
            print(f"  {v}\n      {perche}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    m = Mappa()
    q = sys.argv[1]
    if q == '--trappole':
        m.trappole()
    elif q == '--doppioni':
        m.doppioni()
    elif q == '--orfane':
        m.orfane()
    elif q.startswith('DS4_'):
        m.variabile(q)
    else:
        m.funzione(q)


if __name__ == '__main__':
    main()
