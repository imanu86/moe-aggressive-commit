"""misura_4agenti.py - misura reale del multichat sul log del motore della 8100.
    python misura_4agenti.py segna   -> salva posizione nel log e ora (inizio della finestra di misura)
    python misura_4agenti.py         -> riassume le richieste dal segno a ora (il log non ha l'ora per riga)
Per ogni richiesta: token di prompt, riusati, letti, ms di lettura, generati, ms di decode. Aggregati a muro sulla finestra."""
import json, re, sys, time
from pathlib import Path

LOG = Path(r'D:\ds4_work\strata\sota\strata_dyn_agenti.log')
STATO = Path(__file__).with_name('segno.json')
RX = re.compile(r'prompt (\d+) tokens = (\d+) reused \+ (\d+)(?: of \d+)? read in (\d+) ms.*?, (\d+) generated in (\d+) ms')

if sys.argv[1:] == ['segna']:
    STATO.write_text(json.dumps({'off': LOG.stat().st_size, 't': time.time()}))
    sys.exit('segnato')
s = json.loads(STATO.read_text())
with LOG.open('rb') as f:
    f.seek(s['off'])
    testo = f.read().decode('utf-8', errors='replace')
muro = time.time() - s['t']
R = [tuple(map(int, m.groups())) for m in RX.finditer(testo)]
W = [int(x) for x in re.findall(r'strata work: request \d+, .*?, (\d+) tokens;', testo)]
BR = re.findall(r'read (\d+) tokens on a thread of its own in (\d+) ms.*?decoded (\d+) rows meanwhile', testo)
modi = [l.strip()[-90:] for l in testo.splitlines() if 'batch-dyn' in l and 'modo' in l]
if not R:
    sys.exit(f'nessuna richiesta in {muro / 60:.1f} min')
tot = lambda i: sum(x[i] for x in R)
print(f'finestra {muro / 60:.1f} min | richieste {len(R)} | prompt {tot(0)} (riusati {tot(1)}, letti {tot(2)}) | generati {tot(4)}')
print(f'per richiesta: lettura {tot(2) / max(1, tot(3)) * 1000:.0f} tok/s, decode {tot(4) / max(1, tot(5)) * 1000:.1f} t/s')
print(f'AGGREGATO a muro: {tot(4) / muro:.1f} t/s generati, {tot(2) / muro:.0f} tok/s letti')
print(f'TOKEN GENERATI (righe work): {sum(W)} in {len(W)} richieste -> {sum(W) / muro:.1f} t/s aggregati a muro')
if BR: print(f'letture concorrenti: {len(BR)}, {sum(int(a) for a,b,c in BR)} token in {sum(int(b) for a,b,c in BR)/1000:.0f} s, decode degli altri durante: {sum(int(c) for a,b,c in BR)/max(1,sum(int(b) for a,b,c in BR))*1000:.1f} righe/s')
print(f'motore occupato (lettura+decode)/muro: {(tot(3) + tot(5)) / 10 / muro:.0f}% (>100% = richieste sovrapposte)')
print(f'prompt per richiesta: min {min(x[0] for x in R)} max {max(x[0] for x in R)} | passaggi di modo: {len(modi)}')
