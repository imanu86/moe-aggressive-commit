import json,subprocess,sys
from pathlib import Path
L=Path(__file__).resolve().parent
for mode in ['default','resident','drop']:
    name=f'{mode}-explain-v1';print('BEGIN',name,flush=True)
    r=subprocess.run([sys.executable,str(L/'run_extended.py'),'--mode',mode,'--task','explain','--tokens','512',
                      '--build','build-v5','--name',name,'--run'],cwd=L,timeout=410)
    if r.returncode:raise SystemExit(r.returncode)
    q=json.loads((L/name/'result.json').read_text());assert q['status']=='completed' and not q['remaining_owned']
    print('END',name,flush=True)
