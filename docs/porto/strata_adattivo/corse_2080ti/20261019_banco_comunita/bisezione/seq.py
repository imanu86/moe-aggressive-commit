"""python -u seq.py 01 B,N,B,N,B [--targets ..] -> corse tag NN-braccio, una alla volta, in sequenza."""
import subprocess, sys
from pathlib import Path
pref, arms = sys.argv[1], sys.argv[2].split(',')
extra = sys.argv[3:]
here = Path(__file__).resolve().parent
for i, a in enumerate(arms, 1):
    print(f'=== {pref}{i:02d}-{a}', flush=True)
    subprocess.run([sys.executable, '-u', str(here / 'bab.py'), f'{pref}{i:02d}', a] + extra, check=False)
