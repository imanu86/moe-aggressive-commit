from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RESEARCH = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
TOOL = RESEARCH / 'docs/porto/strata_adattivo/strumenti/prova_kv262k.py'
DAILY = Path(r'D:\ds4_work\strata\Strata')
ARMS = {
    'daily0131': (DAILY/'build-0131-daily/strata.exe', DAILY/'build-0131-daily/source', '0'),
    'candidate0135_serial': (ROOT/'build0135/strata.exe', ROOT/'candidate0135', '0'),
    'candidate0135_parallel': (ROOT/'build0135/strata.exe', ROOT/'candidate0135', '1'),
    'candidate0136_serial': (ROOT/'build0136/strata.exe', ROOT/'candidate0136', '0'),
    'candidate0136_parallel': (ROOT/'build0136/strata.exe', ROOT/'candidate0136', '1'),
    'installed0136_startup': (DAILY/'build-0136-daily/strata.exe', DAILY/'build-0136-daily/source', '0'),
}
name = sys.argv[1]
exe, source, parallel = ARMS[name]
env = dict(os.environ)
env.pop('STRATA_API_KEY', None)
env['STRATA_PARALLEL_INTERMEDIATE_QUANT'] = parallel
env['PYTHONDONTWRITEBYTECODE'] = '1'
out = ROOT/'model-tests'/name
args = [sys.executable, '-B', '-u', '-X', 'utf8', str(TOOL), '--nome', name,
        '--out', str(out), '--exe', str(exe), '--server-source', str(source),
        '--topk-modo', 'active', '--durata-max-s', '1000']
if '--startup' in sys.argv:
    args.append('--solo-avvio')
if name == 'installed0136_startup':
    args.extend(['--config-template', str(DAILY/'strata-2080ti-sota.json')])
print('ARM', name, 'parallel_quant', parallel, flush=True)
result = subprocess.run(args, env=env, cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
print('ARM_EXIT', result.returncode, flush=True)
sys.exit(result.returncode)
