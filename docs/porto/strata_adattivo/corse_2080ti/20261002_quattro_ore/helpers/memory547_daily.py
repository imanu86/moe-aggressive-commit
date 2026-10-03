"""Operational elastic profile paired ring OFF / ON / OFF benchmark, no daily writes."""
from pathlib import Path
import json,os,subprocess,sys,time
BASE=Path(__file__).resolve().parent
ROOT=BASE/'fourhour_20261002'
RESEARCH=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
DAILY=Path(r'D:\ds4_work\strata\Strata')
state=json.loads((ROOT/'run-state.json').read_text())
report={'protocol':'baseline037 A1 / same source plus PR547 B / baseline037 A2, dynamic OFF throughout; explicit PCIe0.28, unchanged elastic KV profile; unchanged operational elastic configuration','arms':{},'status':'running'}
for label,ring in [('A1','0'),('B','0'),('A2','0')]:
    name='memory547_daily_'+label; folder=ROOT/name
    env=dict(os.environ);env.pop('STRATA_API_KEY',None)
    cache=ROOT/('cuda-cache-'+name); cache.mkdir(exist_ok=True)
    env.update(PYTHONDONTWRITEBYTECODE='1',STRATA_DECODE_TIMING='1',STRATA_SPLIT_TIMING='1',STRATA_MTP_BATCH_RING='0',STRATA_TOPK_DYNAMIC=ring,CUDA_CACHE_PATH=str(cache))
    args=[sys.executable,'-B','-u',str(RESEARCH/'docs/porto/strata_adattivo/strumenti/prova_kv262k.py'),
          '--nome',name,'--out',str(folder),'--exe',str(ROOT/('build-memory547/strata.exe' if label=='B' else 'build-dynamic2/strata.exe')),
          '--server-source',str(ROOT/('memory547-source' if label=='B' else 'dynamic2-source')),'--config-template',str(ROOT/'config-pcie028.json'),'--durata-max-s','900']
    print('START',name,'ring',ring,flush=True)
    p=subprocess.run(args,env=env,cwd=BASE,creationflags=subprocess.CREATE_NO_WINDOW)
    report['arms'][label]={'ring':ring,'exit':p.returncode,'result':json.loads((folder/'esito.json').read_text(encoding='utf-8')) if (folder/'esito.json').is_file() else None}
    (ROOT/'memory547_daily_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if p.returncode: raise RuntimeError('Arm failed '+name)
    print('STOPPED',name,flush=True)
report['status']='completed'
(ROOT/'memory547_daily_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('DAILY_RING_COMPLETE',flush=True)
