"""Serial continuation; no concurrent engine or background build."""
import json,subprocess,sys
from pathlib import Path
L=Path(__file__).resolve().parent
runs=[('resident','ledger',512),('default','code',512),('resident','code',512),
      ('observe','ledger',512),('daily','ledger',512)]
for mode,task,tokens in runs:
    name=f'{mode}-{task}-v1'
    print('BEGIN',name,flush=True)
    r=subprocess.run([sys.executable,str(L/'run_closed.py'),'--mode',mode,'--task',task,'--tokens',str(tokens),
                      '--build','build-v5','--name',name,'--run'],cwd=L,timeout=410)
    if r.returncode:raise SystemExit(r.returncode)
    result=json.loads((L/name/'result.json').read_text())
    assert result['status']=='completed' and not result['remaining_owned']
    print('END',name,flush=True)
