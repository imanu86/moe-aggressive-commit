"""Three interleaved pairs per chunk, complete recall oracles and fixed teacher logits."""
from pathlib import Path
import datetime,hashlib,json,math,os,statistics,subprocess,sys,threading,time
BASE=Path(__file__).resolve().parent; R=BASE/'checkpoint038_20261003'; S=R/'source'
sys.path[:0]=[str(S),r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np, psutil
import validate_model as V
from serve.server import StrataEngine
from serve.frontend import ChatTemplate,OutputParser
from tools.strata_tokenizer import Tokenizer
OUT=R/'model-tests-r3'; OUT.mkdir(exist_ok=False)
cfg=json.loads(Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
tp=Path(cfg['tokenizer']); vocab=json.loads((tp/'vocab.json').read_text(encoding='utf-8')); tokens=[None]*len(vocab)
for text,index in vocab.items():tokens[index]=text
tok=Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
tpl=ChatTemplate(tp/'chat_template.jinja')
rendered=tpl.render([{'role':'user','content':'Read the archive. Only AUTH_RECORD lines define the requested codes.\n__ARCHIVE__\nReturn only JSON with keys north, south, west containing the codes.'}],enable_thinking=False)
left,right=rendered.split('__ARCHIVE__'); left=tok.encode(left,parse_special=True); right=tok.encode(right,parse_special=True)
gold={'north':'ARCO-731','south':'LUNA-482','west':'PORTO-916'}
fill=tok.encode(V.TEXTS['doc'][1],parse_special=False)
records=[tok.encode('\nAUTH_RECORD '+k+'='+v+'\n',parse_special=False) for k,v in gold.items()]
remaining=32768-len(left)-sum(map(len,records)); sizes=[remaining//10,remaining*4//10,remaining*4//10];sizes.append(remaining-sum(sizes))
prefix=list(left)
for i,size in enumerate(sizes):
    prefix+=(fill*(size//len(fill)+1))[:size]
    if i<3:prefix+=records[i]
assert len(prefix)==32768
filler=(fill*(1024//len(fill)+1))[:1024]
fresh=prefix+tok.encode('\nFIRST additional archive appendix.\n',parse_special=False)+filler+right
follow=prefix+tok.encode('\nSECOND independent appendix.\n',parse_special=False)+filler+right
common=0
for aa,bb in zip(fresh,follow):
    if aa!=bb:break
    common+=1
assert 32768<=common<32800
tail=tok.encode(V.TEXTS['doc'][1],parse_special=False)[:65]
for name,ids in [('fresh',fresh),('follow',follow),('teacher_tail',tail)]: (OUT/(name+'.ids.json')).write_text(json.dumps(ids))
args=[x for x in cfg['args'] if x!='--elastic']
for key,val in [('--expert-cache',4000),('--spec',4),('--pcie-frac',0.28),('--suffix-draft',0),('--adapt-swaps',0),('--conversation-cache-mib',0),('--prompt-cache',6),('--prompt-cache-every',16384)]:args=V.set_arg(args,key,val)
plan={'upstream':'99f3dbd0b21d1401b3769e0c0d963913607f380b','chunks':[1536,6144],'pairs_each':3,'args':args,
      'fresh_prompt_tokens':len(fresh),'follow_prompt_tokens':len(follow),'common_tokens':common,'expected':gold,
      'teacher_rows':0,'teacher_pairs':'separate QA binaries with identical test-only server readout; original speed binaries unchanged',
      'quality_policy':V.POLICY,'artificial_load':False,'daily_changed':False,
      'scope':'single modified RTX2080Ti22GB; KV262144/int8/resident32768; benchmark fixture and teacher corpus',
      'candidate_reuse_min':32768,'maximum_total_seconds':3600}
result={'status':'running','plan':plan,'arms':{}};stop=threading.Event();phase='startup'
def save(): (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
def monitor():
    known={}
    with (OUT/'resources.jsonl').open('w',encoding='utf-8') as log:
        while not stop.is_set():
            row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':phase,'ram_available_gib':psutil.virtual_memory().available/2**30,'cpu_percent':psutil.cpu_percent(None),'disk':psutil.disk_io_counters()._asdict(),'processes':[]}
            for p in psutil.process_iter(['pid','name']):
                if p.pid==0:continue
                try:
                    obj=known.setdefault(p.pid,p);cpu=obj.cpu_percent(None)
                    if cpu>=5:row['processes'].append({'pid':p.pid,'name':p.info['name'],'cpu_one_core_percent':cpu})
                except psutil.Error:pass
            try:row['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.free,temperature.gpu,clocks.sm,clocks.mem','--format=csv,noheader,nounits'],text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW).strip()
            except Exception as e:row['gpu_error']=str(e)
            log.write(json.dumps(row)+'\n');log.flush();stop.wait(10)
def decode(ids):
    body=tok.decode(ids)
    for token in ('<|im_end|>','<|endoftext|>'):body=body.removesuffix(token)
    p=OutputParser(thinking=False); ev=p.feed(body)+p.finish()
    return ''.join(x.text for x in ev if x.kind=='content')
def oracle(text,finish):
    try:
        cleaned=text.strip()
        if cleaned.startswith('```json\n') and cleaned.endswith('\n```'):cleaned=cleaned[8:-4].strip()
        return finish=='stop' and json.loads(cleaned)==gold
    except ValueError:return False
assert not any((p.info['name'] or '').lower() in ('strata.exe','strata-baseline.exe','llama-server.exe') for p in psutil.process_iter(['name']))
thread=threading.Thread(target=monitor,daemon=True);thread.start();started=time.monotonic();save()
try:
    for chunk in plan['chunks']:
        for pair in range(1,4):
            # Alternate pair order to reduce systematic warming and drift.
            for mode in (['A','B'] if pair%2 else ['B','A']):
                label=f'chunk{chunk}_{mode}{pair}';folder=OUT/label;folder.mkdir();phase=label
                env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
                env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(OUT/'cuda-cache'),STRATA_WATCHDOG_S='240',STRATA_PARALLEL_INTERMEDIATE_QUANT='0',STRATA_DECODE_TIMING='1',STRATA_SPLIT_TIMING='1')
                env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
                teacher=False
                if teacher:env['STRATA_DUMP_FIRST_LOGITS']=str(folder/'first.f32')
                exe=R/'strata-baseline.exe' if mode=='A' else R/'build/strata.exe'
                current_args=V.set_arg(args,'--prefill',chunk)
                engine=StrataEngine(str(exe),current_args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
                arm={'mode':mode,'pair':pair,'chunk':chunk,'exe_sha256':V.sha(exe),'requests':[],'teacher':None}
                result['arms'][label]=arm;save();print('START',label,flush=True)
                try:
                    engine.restart();arm['info']=dict(engine.info)
                    assert int(engine.info['expert_slots'])==5357 and engine.max_context==262144
                    assert int(engine.info['vram_free_mib'])>=1000
                    # Same warm-up, unrelated to the archive's prefix.
                    warm=tok.encode(tpl.render([{'role':'user','content':'Return only JSON with key ready and value true.'}],enable_thinking=False),parse_special=True)
                    list(engine.generate(warm,32,{'temperature':0},threading.Event()))
                    for name,ids in [('fresh',fresh),('follow',follow)]:
                        assert time.monotonic()-started<plan['maximum_total_seconds']
                        assert psutil.virtual_memory().available>8*2**30
                        t0=time.perf_counter();first=None;out=[]
                        for token in engine.generate(ids,128,{'temperature':0},threading.Event()):
                            if token is not None:
                                if first is None:first=time.perf_counter()-t0
                                out.append(token)
                        text=decode(out);item={'name':name,'ttft_s':first,'wall_s':time.perf_counter()-t0,'output_ids':out,'content':text,**engine.last}
                        item['oracle_pass']=oracle(text,engine.last['finish']);arm['requests'].append(item);save()
                        print('RESULT',label,name,'reuse',engine.last.get('reused'),'ttft',round(first or 0,3),'oracle',item['oracle_pass'],flush=True)
                        assert item['oracle_pass'],'Incomplete or incorrect recall answer'
                        if mode=='B' and name=='follow':assert engine.last.get('reused',0)>=32768,'Grid did not improve checkpoint reuse'
                    if teacher:
                        rows=[]
                        for pos in range(64):
                            generated=list(engine.generate(follow+tail[:pos],1,{'temperature':0},threading.Event()))
                            row=np.fromfile(folder/'first.f32',dtype='<f4')
                            assert row.size==len(tokens) and np.isfinite(row).all()
                            rows.append(row)
                        raw=folder/'teacher.bin';np.asarray(rows,dtype='<f4').tofile(raw)
                        arm['teacher']={'positions':64,'sha256':V.sha(raw)};save();print('TEACHER',label,'finite64',flush=True)
                finally:engine.close()
                arm['completed']=True;save();print('STOPPED',label,flush=True)
    result['status']='completed'
except BaseException as e:
    result.update(status='failed',error=str(e));raise
finally:
    stop.set();thread.join(timeout=12);save();print('STATUS',result['status'],flush=True)
