"""Repeat the isolated published PR delta without changing Daily or old evidence."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys, threading, time
sys.path.insert(0, r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages')
import psutil
BASE = Path(__file__).resolve().parent
OLD = BASE/'fourhour_20261002'
ROOT = BASE/'retest_pr512_20261003'
ROOT.mkdir(exist_ok=False)
ENV = dict(os.environ)
ENV.pop('STRATA_API_KEY', None)
for key in list(ENV):
    if key.startswith('STRATA_'): ENV.pop(key, None)
ENV.update(PYTHONDONTWRITEBYTECODE='1', CUDA_CACHE_PATH=str(ROOT/'cuda-cache'),
           STRATA_DECODE_TIMING='1', STRATA_SPLIT_TIMING='1')
ENV['PATH'] = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'+os.pathsep+ENV.get('PATH','')
if any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name'])):
    raise RuntimeError('An engine is already active')
(ROOT/'config.json').write_bytes((OLD/'config-pr512-fixed4000.json').read_bytes())
exe = OLD/'build-pr512/strata.exe'
assert hashlib.sha256(exe.read_bytes()).hexdigest() == '9933918a7f1e6dee2e55b41552df068e654169834c7d6e7679710330469b5207'
stop = threading.Event()
phase = 'idle'
def sample():
    known = {}
    with (ROOT/'resources.jsonl').open('w',encoding='utf-8') as out:
        while not stop.is_set():
            row = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'phase':phase,
                   'ram_available_gib':psutil.virtual_memory().available/2**30,
                   'cpu_percent':psutil.cpu_percent(None), 'cpu_per_core':psutil.cpu_percent(None,percpu=True),
                   'disk':psutil.disk_io_counters()._asdict(), 'processes':[]}
            for p in psutil.process_iter(['pid','name']):
                try:
                    obj=known.setdefault(p.pid,p); cpu=obj.cpu_percent(None)
                    if cpu>=5:
                        row['processes'].append({'pid':p.pid,'name':p.info['name'],'cpu_one_core_percent':cpu})
                except psutil.Error: pass
            try:
                row['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.free,temperature.gpu,clocks.sm,clocks.mem,power.draw','--format=csv,noheader,nounits'],text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW).strip()
            except Exception as e: row['gpu_error']=str(e)
            out.write(json.dumps(row)+'\n'); out.flush(); stop.wait(10)
sampler=threading.Thread(target=sample,daemon=True)
sampler.start()
report={'status':'running','upstream':'db4f91a1171d697928b0d2e1f50ef95e25559d4c',
        'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
        'shared_cuda_cache':True,'artificial_load':False,'arms':{}}
def save(): (ROOT/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
try:
    phase='idle_baseline'; print('IDLE_BASELINE 30s',flush=True); stop.wait(30)
    phase='parity'
    p=subprocess.run([str(OLD/'build-pr512/qsa_topk_active_parity.exe')],env=ENV,capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    (ROOT/'parity.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode or 'PASS: 16' not in p.stdout: raise RuntimeError('Parity failed')
    print('PARITY PASS: 16',flush=True)
    for label, mode in [('A1','capacity'),('B','active'),('A2','capacity')]:
        phase=label; folder=ROOT/label
        print('START',label,mode,flush=True)
        args=[sys.executable,'-B','-u',r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\strumenti\prova_kv262k.py',
              '--nome','retest_pr512_'+label,'--out',str(folder),'--exe',str(exe),
              '--server-source',str(OLD/'pr512-source037'),'--config-template',str(ROOT/'config.json'),
              '--topk-modo',mode,'--cache-fissa','4000','--durata-max-s','900']
        with (ROOT/(label+'-driver.log')).open('w',encoding='utf-8') as log:
            p=subprocess.run(args,env=ENV,cwd=BASE,stdout=log,stderr=subprocess.STDOUT,timeout=960,creationflags=subprocess.CREATE_NO_WINDOW)
        result=json.loads((folder/'esito.json').read_text()) if (folder/'esito.json').exists() else None
        report['arms'][label]={'mode':mode,'exit':p.returncode,'result':result}; save()
        print('FINISHED',label,p.returncode,result.get('summary') if result else None,flush=True)
        if p.returncode: raise RuntimeError('Arm failed '+label)
    report['status']='completed'
except Exception as e:
    report.update(status='failed',error=str(e)); raise
finally:
    stop.set(); sampler.join(timeout=12); save()
    print('STATUS',report['status'],flush=True)
