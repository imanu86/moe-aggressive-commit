"""Extended deep-context A/B/A QA, full frozen512/1024/1024-token corpora.

No guide generation precedes scoring: aligned fixed inputs are compared right
after the recall requests. Auto cache/prefill, elastic policy and sampling stay
unchanged. This is additional evidence, not a relabeling of the64-row failure.
"""
from checkpoint_daily_common import *
import time,subprocess,datetime,shutil
OUT=BASE/'checkpoint_daily_20261003';SPEED=OUT/'paired-r2'
main=json.loads((SPEED/'results.json').read_text(encoding='utf-8'))
assert main['status']=='completed'
RUN=OUT/'full-qa';RUN.mkdir(exist_ok=False)
texts={}
for name,(count,text) in V.TEXTS.items():
    texts[name]=TOK.encode(text*(count//64+2),parse_special=False)[:count]
    assert len(texts[name])==count
    write(RUN/f'{name}.ids.json',texts[name])
    (RUN/f'{name}.txt').write_text(TOK.decode(texts[name]),encoding='utf-8')
fixtures={d:{name:json.loads((SPEED/f'{d}-{name}.ids.json').read_text(encoding='utf-8')) for name in ('fresh','branch')} for d in main['plan']['contexts']}
plan={'binary_sha256':sha(CFG['exe']),'args_original':CFG['args'],'contexts':main['plan']['contexts'],'order':['A1','B','A2'],'baseline_every':16384,'candidate_every':8192,'texts':{n:{'input_tokens':len(x),'scored_positions':len(x)-1,'ids_sha256':sha(RUN/f'{n}.ids.json')} for n,x in texts.items()},'scored_positions_per_arm':2557,'policy':V.POLICY,'same_settings_as_daily':True,'elastic':True,'artificial_pressure':False,'teacher_method':'branch + ids[:pos+1], max_new1, prediction discarded; last unknown target excluded','initial_requests':'same unrelated warmup, fresh recall, branch recall; no guide/extra conversation before teacher scoring','prior_short_gate':'retained independently; full QA does not overwrite its verdict','maximum_seconds':7200,'admission_vram_mib':500}
write(RUN/'plan.json',plan)
result={'status':'running','plan':plan,'arms':{}}
started=time.monotonic();stop=threading.Event();cancel=threading.Event();phase='startup';position=0;resource_failure=[]
def save():write(RUN/'results.json',result)
def guard():
    assert time.monotonic()-started<plan['maximum_seconds'],'QA deadline'
    assert not resource_failure and psutil.virtual_memory().available>8*2**30,'RAM reserve'
def monitor():
    with (RUN/'resources.jsonl').open('w',encoding='utf-8') as log:
        while not stop.is_set():
            ram=psutil.virtual_memory().available/2**30
            row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':phase,'position':position,'ram_available_gib':ram,'cpu_percent':psutil.cpu_percent(None)}
            active=globals().get('e')
            row['prompt_progress']=getattr(active,'progress',None)
            row['prefill_tok_s_mean']=getattr(active,'prefill_tok_s_mean',None)
            if ram<8:resource_failure.append('RAM below8GiB');cancel.set()
            try:row['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.free,temperature.gpu,clocks.sm,clocks.mem','--format=csv,noheader,nounits'],text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW).strip()
            except Exception as exc:row['gpu_error']=repr(exc)
            log.write(json.dumps(row)+'\n');log.flush();stop.wait(10)
ensure_free();assert shutil.disk_usage(RUN).free>30*2**30,'Raw-logit disk reserve'
save();thread=threading.Thread(target=monitor,daemon=True);thread.start()
try:
    for depth in plan['contexts']:
        for label,mode in [('A1','A'),('B','B'),('A2','A')]:
            guard();name=f'{depth}_{label}';phase=name;position=0;folder=RUN/name;folder.mkdir()
            args=V.set_arg(CFG['args'],'--prompt-cache-every',plan['baseline_every'] if mode=='A' else plan['candidate_every'])
            arm={'mode':mode,'args':args,'requests':[],'teacher':{}};result['arms'][name]=arm;save()
            e=engine(folder,args,readout=True);print('FULL START',name,flush=True)
            try:
                e.restart();arm['info']=dict(e.info);save()
                assert e.max_context==262144 and int(e.info['vram_free_mib'])>=500
                list(e.generate(WARM,32,{'temperature':0},cancel))
                for request_name in ('fresh','branch'):
                    guard();prompt=fixtures[depth][request_name];clear_dump(folder)
                    generated=[];progress=[]
                    for token in e.generate(prompt,128,{'temperature':0},cancel):
                        if token is not None:generated.append(token)
                        elif e.progress and (not progress or progress[-1]!=list(e.progress)):progress.append(list(e.progress))
                    row=first_row(folder,len(prompt));row.tofile(folder/f'{request_name}-first.f32')
                    text=decode(generated);item={'name':request_name,'content':text,'output_ids':generated,'prefill_progress':progress,**e.last,'oracle_pass':oracle(text,e.last['finish'],main['plan']['expected'])}
                    arm['requests'].append(item);save();print('FULL RECALL',name,request_name,'oracle',item['oracle_pass'],flush=True)
                for corpus,ids in texts.items():
                    phase=name+'/'+corpus;raw=folder/f'{corpus}.logits.bin';reused=[]
                    with raw.open('wb') as f:
                        f.write(np.asarray([len(TOKENS),len(ids)],dtype='<i4').tobytes())
                        for pos in range(len(ids)):
                            guard();position=pos;prompt=fixtures[depth]['branch']+ids[:pos+1]
                            assert len(prompt)+9<262144;clear_dump(folder)
                            generated=[x for x in e.generate(prompt,1,{'temperature':0},cancel) if x is not None]
                            assert len(generated)==1 and e.last['prompt_tokens']==len(prompt)
                            row=first_row(folder,len(prompt));f.write(row.tobytes());reused.append(e.last['reused'])
                            if (pos+1)%128==0:print('FULL ROWS',name,corpus,pos+1,'/',len(ids),flush=True)
                    V.check_dump(raw,len(ids),len(TOKENS))
                    arm['teacher'][corpus]={'rows':len(ids),'scored_positions':len(ids)-1,'sha256':sha(raw),'reused_min':min(reused),'reused_max':max(reused)};save()
                arm['chunk_events']=chunk_events(folder/'engine.log');arm['completed']=True;save()
            finally:e.close()
            print('FULL STOPPED',name,flush=True)
    result.update(status='completed',elapsed_s=time.monotonic()-started)
except BaseException as exc:
    result.update(status='failed',error=repr(exc),elapsed_s=time.monotonic()-started);raise
finally:
    stop.set();thread.join(timeout=12);save();print('FULL STATUS',result['status'],flush=True)
