"""Isolated upstream037 + published PR512, capacity/active/capacity. No Daily writes."""
from pathlib import Path
import json, os, subprocess, sys
BASE=Path(__file__).resolve().parent
ROOT=BASE/'fourhour_20261002'
RESEARCH=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
cfg=json.loads((ROOT/'config-pcie028.json').read_text())
cfg['args']=[a for a in cfg['args'] if a!='--elastic']
cfg['args'][cfg['args'].index('--expert-cache')+1]='4600'
cfg_path=ROOT/'config-pr512-fixed.json'
if cfg_path.exists(): raise RuntimeError('Existing config')
cfg_path.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
report={'protocol':'pure upstream037 plus published four-file PR512; same executable capacity A1 / active B / capacity A2; fixed requested4600 effective profile6167; no elasticity; PCIe0.28; KV262144/int8/resident32768','status':'running','arms':{}}
for label,mode in [('A1','capacity'),('B','active'),('A2','capacity')]:
    env=dict(os.environ); env.pop('STRATA_API_KEY',None)
    cache=ROOT/('cuda-cache-pr512-'+label); cache.mkdir(exist_ok=True)
    env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(cache),STRATA_DECODE_TIMING='1',STRATA_SPLIT_TIMING='1')
    name='pr512_037_'+label; folder=ROOT/name
    args=[sys.executable,'-B','-u',str(RESEARCH/'docs/porto/strata_adattivo/strumenti/prova_kv262k.py'),
          '--nome',name,'--out',str(folder),'--exe',str(ROOT/'build-pr512/strata.exe'),
          '--server-source',str(ROOT/'pr512-source037'),'--config-template',str(cfg_path),
          '--topk-modo',mode,'--cache-fissa','4600','--durata-max-s','750']
    print('START',label,mode,flush=True)
    p=subprocess.run(args,env=env,cwd=BASE,creationflags=subprocess.CREATE_NO_WINDOW)
    report['arms'][label]={'mode':mode,'exit':p.returncode,'result':json.loads((folder/'esito.json').read_text()) if (folder/'esito.json').exists() else None}
    (ROOT/'pr512_037_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if p.returncode: raise RuntimeError('Arm failed '+label)
report['status']='completed'
(ROOT/'pr512_037_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PR512_ISOLATED_COMPLETE',flush=True)
