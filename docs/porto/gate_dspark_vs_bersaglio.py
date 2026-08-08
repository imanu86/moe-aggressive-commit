"""
DSpark instrada come il bersaglio? — misura OFFLINE, senza macchina.

L'idea (utente, 8/8): durante la bozza il proponente gira su CPU e il link PCIe
resta fermo ~26 ms, cioe' 97 esperti di staging gratuiti per ciclo. Per usarli
serve sapere QUALI esperti servira'. Se il router del proponente predicesse
quello del bersaglio, l'anticipo passerebbe da uno strato a un ciclo intero.

Invece di dumpare le route ed eseguire una correlazione (che vuole la macchina),
si confrontano i GATE: `ffn_gate_inp` e' la matrice [n_embd, n_expert] che
decide l'instradamento. Se il gate di DSpark blocco 0 e' quello del bersaglio
allo strato 41, le route coincidono PER COSTRUZIONE a parita' di stato nascosto.

`dflash.target_layers = [41, 42, 43]` suggerisce che i tre blocchi di DSpark
siano derivati da quegli strati, ma non lo dimostra: questo lo dimostra o lo
falsifica.

Esiti possibili:
  - gate IDENTICI          -> il proxy funziona per costruzione, si costruisce
  - gate CORRELATI         -> il proxy vale quanto la correlazione
  - gate SCORRELATI        -> l'idea del router-proxy e' morta, resta il gate
                              del bersaglio a L+1 (1 strato di anticipo, 71%)
"""

import sys, os
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
import gguf
import numpy as np

TGT = r'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
DFT = r'D:\ds4-models\DSpark-draft-Q2K.gguf'
STRATI_BERSAGLIO = [41, 42, 43]   # dflash.target_layers


def carica(path, nomi):
    """Legge SOLO i tensori richiesti, dequantizzando se serve."""
    r = gguf.GGUFReader(path, 'r')
    out = {}
    for t in r.tensors:
        if t.name in nomi:
            a = np.asarray(t.data)
            tipo = t.tensor_type
            if tipo not in (gguf.GGMLQuantizationType.F32, gguf.GGMLQuantizationType.F16):
                try:
                    a = gguf.quants.dequantize(a, tipo)
                except Exception as e:
                    print('   !! non dequantizzabile %s (%s): %s' % (t.name, tipo.name, e))
                    continue
            out[t.name] = (np.asarray(a, dtype=np.float32), tipo.name, [int(x) for x in t.shape])
    return out


print('=== tipi e forme dei gate ===')
nomi_t = ['blk.%d.ffn_gate_inp.weight' % L for L in STRATI_BERSAGLIO]
nomi_d = ['blk.%d.ffn_gate_inp.weight' % b for b in range(3)]

G_t = carica(TGT, set(nomi_t))
G_d = carica(DFT, set(nomi_d))

for n in nomi_t:
    if n in G_t:
        a, tp, sh = G_t[n]
        print('  bersaglio %-28s %-6s ne=%s' % (n, tp, sh))
for n in nomi_d:
    if n in G_d:
        a, tp, sh = G_d[n]
        print('  proponente %-27s %-6s ne=%s' % (n, tp, sh))

if not G_t or not G_d:
    print('\nMANCA UN GATE: non posso confrontare.')
    sys.exit(1)


def confronta(a, b):
    """Ritorna (uguali_bit, correlazione, frazione_segno_uguale)."""
    if a.shape != b.shape:
        return None, None, None
    ident = np.array_equal(a, b)
    x, y = a.ravel(), b.ravel()
    # correlazione di Pearson sull'intera matrice
    c = float(np.corrcoef(x, y)[0, 1])
    seg = float(np.mean(np.sign(x) == np.sign(y)))
    return ident, c, seg


print('\n=== confronto: ogni blocco del proponente contro ogni strato bersaglio ===')
print('   (correlazione ~1,0 = stesso gate; ~0,0 = indipendenti)')
righe = []
for b in range(3):
    nd = 'blk.%d.ffn_gate_inp.weight' % b
    if nd not in G_d:
        continue
    for L in STRATI_BERSAGLIO:
        nt = 'blk.%d.ffn_gate_inp.weight' % L
        if nt not in G_t:
            continue
        ident, c, seg = confronta(G_d[nd][0], G_t[nt][0])
        if c is None:
            print('  blocco %d vs strato %d: FORME DIVERSE %s contro %s'
                  % (b, L, G_d[nd][2], G_t[nt][2]))
            continue
        righe.append((b, L, ident, c, seg))
        print('  blocco %d vs strato %-2d :  identici=%-5s  corr=%+.4f  segno_uguale=%.3f'
              % (b, L, ident, c, seg))

print('\n=== metro di riferimento: due strati DIVERSI del bersaglio fra loro ===')
print('   (serve a sapere quanto vale una correlazione "alta" fra gate indipendenti)')
if len(G_t) >= 2:
    ks = sorted(G_t.keys())
    for i in range(len(ks) - 1):
        _, c, seg = confronta(G_t[ks[i]][0], G_t[ks[i + 1]][0])
        if c is not None:
            print('  %s vs %s :  corr=%+.4f  segno_uguale=%.3f' % (ks[i], ks[i + 1], c, seg))

print('\n=== VERDETTO ===')
if not righe:
    print('  nessun confronto possibile (forme diverse): il proponente non condivide')
    print('  la geometria del gate col bersaglio, quindi il proxy e MORTO.')
else:
    best = max(righe, key=lambda r: abs(r[3]))
    b, L, ident, c, seg = best
    print('  accoppiamento piu forte: blocco %d <-> strato %d, corr=%+.4f' % (b, L, c))
    if ident:
        print('  GATE IDENTICI: il proponente instrada come il bersaglio PER COSTRUZIONE.')
        print('  -> il router-proxy si puo costruire, e i 26 ms di bozza diventano')
        print('     97 esperti di staging con le route GIUSTE.')
    elif abs(c) > 0.7:
        print('  FORTEMENTE CORRELATI: il proxy vale, da verificare sulle route vere.')
    elif abs(c) > 0.25:
        print('  CORRELAZIONE DEBOLE: il proxy da un segnale, non una previsione.')
    else:
        print('  SCORRELATI: il router-proxy e MORTO. Resta il gate del bersaglio a')
        print('  L+1 sullo stato di L -- un solo strato di anticipo, 71% di colpi.')
