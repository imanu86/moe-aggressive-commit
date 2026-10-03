from pathlib import Path
import subprocess,sys,os,json,hashlib
R=Path(__file__).resolve().parent/'checkpoint038_20261003'
env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
env['PYTHONPATH']=r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages'+os.pathsep+str(R/'source')
env['PYTHONDONTWRITEBYTECODE']='1'
modules=['server','lifecycle','mcp','security','monitor','detok','structured','winjob']
with (R/'upstream-server-tests.log').open('w',encoding='utf-8') as log:
    p=subprocess.run([sys.executable,'-m','unittest']+['serve.test_'+name for name in modules],cwd=R/'source',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
print('UPSTREAM SERVER TESTS',p.returncode,flush=True)
print((R/'upstream-server-tests.log').read_text(encoding='utf-8',errors='replace')[-3000:])
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
daily={
    'exe':(r'D:\ds4_work\strata\Strata\build-0136-daily\strata.exe','c35505ca79b790bd37ed7073fcadd399dd30d1b88e85bb99a6eb24a52d945d0a'),
    'config':(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json','ccffa537cdb264f99317948c1c6f41ffbc1e5ce370cafb1ca8c0ca717e77e112'),
    'server':(r'D:\ds4_work\strata\Strata\build-0136-daily\source\serve\server.py','73f90f417e9207811fdc47e5e6240f69bbde0f61ff027b9e0d8cb7b7bb2f4d81'),
    'launcher':(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat','1103f2ffb7727aafe1754f964c1969a03c0838a659edfc5984b1f4afbd2bd2c4')}
result={'upstream_server_returncode':p.returncode,'daily':{key:{'sha256':sha(path),'unchanged':sha(path)==expected} for key,(path,expected) in daily.items()}}
for rel in ['include/strata/prefill/prefill.hpp','src/prefill/prefill.cpp','src/program/generate.cpp']:
    assert sha(R/'source'/rel)==sha(R/'shipping-candidate'/rel),'Shipping source not restored'
assert sha(R/'build/strata.exe')==sha(R/'strata-candidate.exe')
sys.path.insert(0,r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages')
import psutil
result.update(ram_available_gib=psutil.virtual_memory().available/2**30,strata_processes=[{'pid':p.pid,'name':p.info['name']} for p in psutil.process_iter(['name']) if 'strata' in (p.info['name'] or '').lower()])
result['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).strip()
(R/'final-state.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
assert p.returncode==0 and all(item['unchanged'] for item in result['daily'].values())
