"""Sentinella delle prove notturne (11/11/2026): una lettura dello stato, niente azioni.

    python sentinella.py

Stampa OK oppure una riga ANOMALIA per ciascun problema: coda morta senza «coda finita», motore che non parte da troppo,
server.log fermo mentre il motore gira, «no progress» nel motore della corsa in corso, lucchetti rimasti senza padrone,
campionatori nvidia-smi orfani. Chi la legge decide cosa fare (fermare, pulire, rilanciare).
"""
import datetime as dt
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
QUI = Path(__file__).resolve().parent
LOG = QUI / 'coda.log'
CORSE = QUI / 'corse'
LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
ADESSO = dt.datetime.now()


def processi():
    ps = ("Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId)`t$($_.Name)`t$($_.CreationDate.ToString('s'))`t$($_.CommandLine)\" }")
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    r = []
    for line in out.splitlines():
        p = line.split('\t', 3)
        if len(p) == 4:
            r.append((int(p[0]), p[1], dt.datetime.fromisoformat(p[2]), p[3]))
    return r


def eta_min(t):
    return (ADESSO - t).total_seconds() / 60


P = processi()
code = [p for p in P if p[1].lower().startswith('python') and ('coda_notte' in p[3] or 'coda_multichat' in p[3] or 'replay_trace' in p[3])]
motore = [p for p in P if p[1].lower() == 'strata.exe']
build = [p for p in P if p[1].lower() in ('ninja.exe', 'cmake.exe', 'cl.exe', 'nvcc.exe') or 'build_lock' in p[3]]
smi = [p for p in P if p[1].lower() == 'nvidia-smi.exe' and ('-l 5' in p[3] or 'dmon' in p[3])]
anom = []

righe = LOG.read_text(encoding='utf-8', errors='replace').splitlines() if LOG.exists() else []
ultima = righe[-1] if righe else ''
try:
    t_ultima = dt.datetime.strptime(f'{ADESSO.year}/' + ultima[:14], '%Y/%d/%m %H:%M:%S')
except ValueError:
    t_ultima = None
finita = 'coda finita' in ultima
print(f'{ADESSO:%d/%m %H:%M} coda: {"viva" if code else "assente"} | motore: {len(motore)} | compilazione: {"si" if build else "no"} | ultima riga: {ultima[:90]}')

if not finita and not code and righe:
    anom.append(f'coda morta senza «coda finita» (ultima riga: {ultima[:80]})')

if motore:
    m = min(motore, key=lambda p: p[2])
    corse = sorted([d for d in CORSE.iterdir() if d.is_dir()], key=lambda d: d.stat().st_mtime)
    cur = corse[-1] if corse else None
    if cur is not None:
        sl, el = cur / 'server.log', cur / 'engine.log'
        if sl.exists():
            last = sl.read_text(encoding='utf-8', errors='replace').splitlines()[-1:] or ['']
            fermo = eta_min(dt.datetime.fromtimestamp(sl.stat().st_mtime))
            if 'still starting' in last[0] and eta_min(m[2]) > 12:
                anom.append(f'{cur.name}: il motore non parte da {eta_min(m[2]):.0f} min')
            elif fermo > 10:
                anom.append(f'{cur.name}: server.log fermo da {fermo:.0f} min col motore acceso')
        if el.exists() and 'no progress for' in el.read_text(encoding='utf-8', errors='replace'):
            anom.append(f'{cur.name}: il motore ha segnalato «no progress» (blocco)')
    if not code and eta_min(m[2]) > 5:
        anom.append(f'motore acceso da {eta_min(m[2]):.0f} min senza nessuna coda')

for nome in ('bench.lock', 'build.lock'):
    f = LOCKS / nome
    if f.exists() and not code and not build and not motore:
        anom.append(f'{nome} rimasto senza padrone (da {eta_min(dt.datetime.fromtimestamp(f.stat().st_mtime)):.0f} min)')
if smi and not code:
    anom.append(f'{len(smi)} campionatori nvidia-smi orfani')
if t_ultima and not finita and code and not motore and not build and eta_min(t_ultima) > 15:
    anom.append(f'coda viva ma ferma da {eta_min(t_ultima):.0f} min senza motore (lucchetto?)')

print('OK' if not anom else '\n'.join('ANOMALIA: ' + a for a in anom))
