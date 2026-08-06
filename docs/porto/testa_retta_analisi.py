# LA RETTA DEL COSTO DEL DRAFT — tre punti comparabili, e il residuo che la falsifica
#
# Legge i tre log del braccio testa_retta_nmax.ps1 (n_max = 1, 2, 3 nella STESSA
# config: nothink + cache viva + server -lv 4) ed estrae, MISURATI e non derivati:
#   p1 e per_pos   <- "acc per pos" (verifica del bersaglio)
#   c_draft        <- dur(g)/calls delle spec-stats
#   colpi h        <- contatore della cache di QUELLA run
#   t/s            <- timings della risposta
#
# Poi fa tre cose che una sola run non puo' fare:
#   1. la RETTA c(posizioni) su tre punti, col RESIDUO -- se il residuo e' grande,
#      "fisso + marginale" e' il modello sbagliato (costo a gradini, per esempio).
#      Con DUE punti la retta esce sempre: e' l'errore che ha prodotto il
#      marginale negativo del 7/8 notte.
#   2. il CONTROLLO INCROCIATO del passo: il tempo per token misurato deve tornare
#      da (passo + c)/mlen coi pezzi misurati. Se non torna, la differenza e' la
#      CONTESA fra draft e cache -- una grandezza nuova, non un residuo.
#   3. il confronto con le soglie pre-registrate (SOTA 9,26; h di pareggio 21,7%
#      a n_max=2 e 18,1% a n_max=3).
import json, re, sys

DIR = r'D:\ds4_work\llama_run'
SOTA = 9.26
UNION = {1: 446, 2: 600, 3: 751}      # posizioni verificate = n_max+1; union dalla curva
MS_PER_ESPERTO = 0.2706               # 6,75 MiB / 24,35 GiB/s
PAVIMENTO = 69.0                      # 52,7 pavimento + 16,3 calcolo GPU

def leggi(k):
    d = {'k': k}
    try:
        log = open(rf'{DIR}\testa_retta_k{k}_server.log', encoding='utf-8', errors='replace').read()
    except FileNotFoundError:
        return None
    m = re.search(r'acc per pos = \(([^)]*)\)', log)
    if m:
        d['per_pos'] = [float(x) for x in m.group(1).split(',')]
    m = re.search(r'dur\(b,g,a\) = ([\d.]+), ([\d.]+), ([\d.]+)', log)
    n = re.search(r'#calls\(b,g,a\) =\s*(\d+)\s+(\d+)\s+(\d+)', log)
    if m and n:
        d['dur_g'], d['calls'] = float(m.group(2)), int(n.group(2))
        d['c'] = d['dur_g'] / d['calls']
    colpi = re.findall(r'domanda (\d+) \(colpi (\d+) = ([\d.]+)%', log)
    if colpi:
        d['domande'], d['h'] = int(colpi[-1][0]), float(colpi[-1][2]) / 100
    try:
        r = json.load(open(rf'{DIR}\testa_retta_k{k}.resp.json', encoding='utf-8-sig'))
        d['ts'] = r['timings']['predicted_per_second']
        d['tok'] = r['tokens_predicted']
        d['acc'] = (r['timings'].get('draft_n_accepted'), r['timings'].get('draft_n'))
    except Exception:
        pass
    return d

punti = [p for p in (leggi(k) for k in (1, 2, 3)) if p]
if not punti:
    sys.exit('nessun punto trovato')

print(f'{"n_max":>5} {"t/s":>6} {"p1":>6} {"per_pos":>22} {"mlen":>5} {"c_draft":>8} {"colpi h":>8}')
for p in punti:
    pp = p.get('per_pos', [])
    p['mlen'] = 1 + sum(pp)
    print(f'{p["k"]:>5} {p.get("ts",0):6.2f} {(pp[0] if pp else 0):6.3f} '
          f'{", ".join(f"{x:.3f}" for x in pp):>22} {p["mlen"]:5.3f} '
          f'{p.get("c",0):7.1f}m {p.get("h",0)*100:7.1f}%')

print()
print('CONTROLLO INCROCIATO — il token torna coi pezzi misurati?')
for p in punti:
    if 'c' not in p or 'h' not in p or 'ts' not in p:
        continue
    passo = PAVIMENTO + UNION[p['k']] * MS_PER_ESPERTO * (1 - p['h'])
    atteso = (passo + p['c']) / p['mlen']
    misurato = 1000 / p['ts']
    p['scarto'] = misurato - atteso
    print(f'  n_max={p["k"]}: passo {passo:6.1f} + c {p["c"]:5.1f} = {passo+p["c"]:6.1f} / {p["mlen"]:.3f} '
          f'= {atteso:6.1f} ms atteso contro {misurato:6.1f} misurato  -> scarto {p["scarto"]:+6.1f} ms'
          f'{"   <- CONTESA?" if abs(p["scarto"]) > 15 else ""}')

print()
print('LA RETTA c(posizioni) SU TRE PUNTI  (posizioni = n_max, cioe le bozze prodotte)')
usabili = [p for p in punti if 'c' in p]
if len(usabili) >= 3:
    xs = [p['k'] for p in usabili]
    ys = [p['c'] for p in usabili]
    n = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    den = sum((x-mx)**2 for x in xs)
    marg = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / den
    fisso = my - marg*mx
    res = [y - (fisso + marg*x) for x, y in zip(xs, ys)]
    print(f'  c(n) = {fisso:.1f} fisso + {marg:.1f} per posizione')
    print(f'  residui: {", ".join(f"{r:+.2f}" for r in res)}  (max |res| = {max(abs(r) for r in res):.2f} ms)')
    if marg < -0.5:
        print('  MARGINALE NEGATIVO -> il modello lineare e FALSIFICATO (o i punti non sono comparabili)')
    elif max(abs(r) for r in res) > 3:
        print('  RESIDUO GRANDE -> "fisso + marginale" e il modello sbagliato: costo a gradini?')
    else:
        print(f'  retta plausibile: il fisso e il {fisso/(fisso+marg)*100:.0f}% di una chiamata a n_max=1')
else:
    print(f'  solo {len(usabili)} punti con spec-stats: retta non calcolabile')

print()
print(f'CONTRO LE SOGLIE PRE-REGISTRATE (SOTA {SOTA}; pareggio h 21,7% a n_max=2, 18,1% a n_max=3)')
best = max((p for p in punti if 'ts' in p), key=lambda p: p['ts'], default=None)
for p in punti:
    if 'ts' not in p:
        continue
    print(f'  n_max={p["k"]}: {p["ts"]:5.2f} t/s = {p["ts"]/SOTA-1:+.1%} sulla SOTA')
if best:
    d = best['ts']/SOTA - 1
    print()
    print(f'  migliore: n_max={best["k"]} a {best["ts"]:.2f} ({d:+.1%})')
    print('  VERDETTO (criterio emendato): ' + (
        'supera la SOTA con margine -> seconda strada aperta' if d > 0.04 else
        'NON supera con margine fuori dal rumore -> ammortamento CHIUSO, la testa e la via'))
