"""Tabella dei bracci da corse/*/summary.json: mediane prompt/decode, picco memoria per scheda."""
import csv, json, sys
from pathlib import Path
Q = Path(__file__).parent / 'corse'
def picco(d):
    m = {}
    try:
        for r in csv.reader(open(d / 'schede.csv', encoding='utf-8')):
            i = r[1].strip(); v = int(r[2].split()[0]); m[i] = max(m.get(i, 0), v)
    except Exception:
        pass
    return m
print('braccio | pr4K | dec4K | pr32K | dec32K | MiB 3080/3060/2080')
for d in sorted(Q.iterdir(), key=lambda p: (p / 'ambiente.txt').stat().st_mtime if (p / 'ambiente.txt').exists() else 0):
    try:
        s = json.loads((d / 'summary.json').read_text(encoding='utf-8'))
    except Exception:
        print(d.name, 'NESSUN RISULTATO'); continue
    f = lambda k, c: s.get(k, {}).get(c, {}).get('median', 0)
    m = picco(d)
    print(f"{d.name} | {f('4096','prefill_tok_s'):.0f} | {f('4096','decode_tok_s'):.1f} | {f('32768','prefill_tok_s'):.0f} | {f('32768','decode_tok_s'):.1f} | {m.get('0')}/{m.get('1')}/{m.get('2')}")
