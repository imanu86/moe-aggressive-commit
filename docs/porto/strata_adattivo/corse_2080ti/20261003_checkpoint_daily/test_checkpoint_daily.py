"""Predeclared Daily cadence A/B, three interleaved pairs at 131k/250k.

Exact shipping Daily binary, auto cache/prefill and elasticity unchanged.
All runs carry identical first-logit diagnostics; overhead is included in
timings, so these are paired instrumented measurements, not a new SOTA claim.
"""
from checkpoint_daily_common import *
import time,datetime,subprocess,shutil,math
OUT=BASE/'checkpoint_daily_20261003'
assert json.loads((OUT/'probe/results.json').read_text(encoding='utf-8'))['status']=='completed'
RUN=OUT/'paired-r2';RUN.mkdir(exist_ok=False)
GOLD={'north':'ARCO-731','south':'LUNA-482','west':'PORTO-916'}
fill=TOK.encode(V.TEXTS['doc'][1],parse_special=False)
rendered=TPL.render([{'role':'user','content':'Read the archive. Only AUTH_RECORD lines define the requested codes.\n__ARCHIVE__\nReturn only JSON with keys north, south, west containing the codes.'}],enable_thinking=False)
left,right=rendered.split('__ARCHIVE__');left=TOK.encode(left,parse_special=True);right=TOK.encode(right,parse_special=True)
markers={name:TOK.encode('\n'+label+' additional archive appendix.\n',parse_special=False) for name,label in [('fresh','FIRST'),('branch','SECOND')]}
filler=(fill*(1024//len(fill)+1))[:1024]
records=[TOK.encode('\nAUTH_RECORD '+key+'='+value+'\n',parse_special=False) for key,value in GOLD.items()]
fixtures={}
for depth in (131072,250000):
    p_len=depth-len(markers['fresh'])-len(filler)-len(right)
    remain=p_len-len(left)-sum(map(len,records));sizes=[remain//10,remain*4//10,remain*4//10];sizes.append(remain-sum(sizes))
    prefix=list(left)
    for i,n in enumerate(sizes):
        prefix+=(fill*(n//len(fill)+1))[:n]
        if i<3:prefix+=records[i]
    assert len(prefix)==p_len
    f={name:prefix+marker+filler+right for name,marker in markers.items()}
    assert len(f['fresh'])==depth and max(map(len,f.values()))+1024+8<262144
    common=next((i for i,(a,b) in enumerate(zip(f['fresh'],f['branch'])) if a!=b),min(map(len,f.values())))
    f['common']=common;fixtures[depth]=f
    for name in ('fresh','branch'):write(RUN/f'{depth}-{name}.ids.json',f[name])
next_text=(V.TEXTS['doc'][1]*10)
next_ids=TOK.encode(next_text,parse_special=False)[:1000]
next_turn='\n'+TPL.render([{'role':'user','content':TOK.decode(next_ids)+'\nUsing only AUTH_RECORD entries earlier in this conversation, return only JSON with keys north, south, west and their codes.'}],enable_thinking=False)
next_turn=TOK.encode(next_turn,parse_special=True)
long_turn=TOK.encode('\n'+TPL.render([{'role':'user','content':'Write a long numbered practical guide for operating this archive safely. Cover preserving immutable records, checking identifiers, handling revisions, validating exports, units, and inspecting shipments. Give at least twenty detailed steps, with examples. Do not repeat the three secret codes.'}],enable_thinking=False),parse_special=True)
tails={name:TOK.encode(text,parse_special=False)[:65] for name,(_,text) in V.TEXTS.items()}
for name,tail in tails.items():assert len(tail)==65;write(RUN/f'teacher-{name}.ids.json',tail)
write(RUN/'next-turn.ids.json',next_turn);write(RUN/'long-turn.ids.json',long_turn)
plan={'exe_sha256':sha(CFG['exe']),'config_sha256':sha(DAILY/'strata-2080ti-sota.json'),'binary_version':'0.1.36 shipping Daily','contexts':[131072,250000],'pairs_per_context':3,'order':'A1/B1, B2/A2, A3/B3','baseline_every':16384,'candidate_every':8192,'args_original':CFG['args'],'elastic':True,'prefill':'auto unchanged; observed startup8192, changes logged','expected':GOLD,'fixtures':{str(d):{'fresh_tokens':len(f['fresh']),'branch_tokens':len(f['branch']),'common_tokens':f['common']} for d,f in fixtures.items()},'teacher_rows_per_corpus':64,'teacher_corpora':list(tails),'policy':V.POLICY,'max_new_recall':128,'max_new_long_decode':1024,'long_decode_is_not_an_answer_oracle':True,'artificial_pressure':False,'readout':'identical optional first-window dump enabled in all arms; overhead included in TTFT','daily_changed':False,'maximum_seconds':10800,'admission_vram_mib':500,'initial_attempt':'paired rejected before warmup/token generation at759MiB versus runner800MiB; retained; admission now follows actual Daily elastic500MiB contract, no quality threshold changed'}
write(RUN/'plan.json',plan)
result={'status':'running','plan':plan,'arms':{}}
stop=threading.Event();cancel=threading.Event();phase='startup';resource_failure=[]
started=time.monotonic()
def save():write(RUN/'results.json',result)
def guard():
    assert time.monotonic()-started<plan['maximum_seconds'],'test deadline'
    assert not resource_failure,resource_failure
    assert psutil.virtual_memory().available>8*2**30,'RAM reserve'
def monitor():
    known={}
    with (RUN/'resources.jsonl').open('w',encoding='utf-8') as log:
        while not stop.is_set():
            ram=psutil.virtual_memory().available/2**30
            row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':phase,'ram_available_gib':ram,'cpu_percent':psutil.cpu_percent(None),'disk':psutil.disk_io_counters()._asdict(),'processes':[]}
            if ram<8:resource_failure.append('RAM below8GiB');cancel.set()
            for p in psutil.process_iter(['pid','name']):
                if not p.pid:continue
                try:
                    pp=known.setdefault(p.pid,p);usage=pp.cpu_percent(None)
                    if usage>=5:row['processes'].append({'pid':p.pid,'name':p.info['name'],'cpu_one_core_percent':usage})
                except psutil.Error:pass
            try:row['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.free,temperature.gpu,clocks.sm,clocks.mem','--format=csv,noheader,nounits'],text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW).strip()
            except Exception as exc:row['gpu_error']=repr(exc)
            log.write(json.dumps(row)+'\n');log.flush();stop.wait(10)
def request(e,folder,name,prompt,max_new,expected=None):
    guard();assert len(prompt)+max_new+8<=262144
    clear_dump(folder);t0=time.perf_counter();first=None;generated=[]
    for token in e.generate(prompt,max_new,{'temperature':0},cancel):
        if token is not None:
            if first is None:first=time.perf_counter()-t0
            generated.append(token)
    guard();assert generated
    row=first_row(folder,len(prompt));row.tofile(folder/(name+'-first.f32'))
    text=decode(generated)
    item={'name':name,'ttft_s':first,'wall_s':time.perf_counter()-t0,'prompt_sha256':hashlib.sha256(np.asarray(prompt,dtype='<i8').tobytes()).hexdigest(),'actual_input_tokens':len(prompt),'output_ids':generated,'content':text,**e.last}
    if expected is not None:item['oracle_pass']=oracle(text,e.last['finish'],expected)
    else:item['complete_answer']=e.last['finish']=='stop';item['decode_tps']=1000*len(generated)/e.last['decode_ms'] if e.last['decode_ms']>0 else None
    print('REQUEST',phase,name,'prompt',len(prompt),'reused',item['reused'],'TTFT',round(first,3),'oracle',item.get('oracle_pass'),'generated',len(generated),flush=True)
    return item
ensure_free();save();thread=threading.Thread(target=monitor,daemon=True);thread.start()
try:
    for depth in plan['contexts']:
        for pair in range(1,4):
            for mode in (('A','B') if pair%2 else ('B','A')):
                guard();label=f'{depth}_{mode}{pair}';phase=label;folder=RUN/label;folder.mkdir()
                args=V.set_arg(CFG['args'],'--prompt-cache-every',plan['baseline_every'] if mode=='A' else plan['candidate_every'])
                arm={'mode':mode,'pair':pair,'depth':depth,'args':args,'requests':[],'teacher':{}};result['arms'][label]=arm;save()
                e=engine(folder,args,readout=True);print('START',label,flush=True)
                try:
                    e.restart();arm['info']=dict(e.info);save()
                    assert e.max_context==262144 and int(e.info['vram_free_mib'])>=plan['admission_vram_mib']
                    list(e.generate(WARM,32,{'temperature':0},cancel))
                    for name in ('fresh','branch'):
                        phase=label+'/'+name;item=request(e,folder,name,fixtures[depth][name],128,GOLD)
                        arm['requests'].append(item);save()
                        if name=='fresh':assert item['reused']==0
                    branch_generated=arm['requests'][-1]['output_ids']
                    conv=fixtures[depth]['branch']+branch_generated+next_turn
                    phase=label+'/conversation';item=request(e,folder,'conversation',conv,128,GOLD)
                    arm['requests'].append(item);save()
                    long_prompt=conv+item['output_ids']+long_turn
                    phase=label+'/long_decode';item=request(e,folder,'long_decode',long_prompt,1024)
                    arm['requests'].append(item);save()
                    for corpus,tail in tails.items():
                        phase=label+'/teacher-'+corpus;rows=[];reused=[]
                        for pos in range(64):
                            guard();prompt=fixtures[depth]['branch']+tail[:pos];clear_dump(folder)
                            list(e.generate(prompt,1,{'temperature':0},cancel))
                            rows.append(first_row(folder,len(prompt)));reused.append(e.last['reused'])
                            if (pos+1)%32==0:print('TEACHER',label,corpus,pos+1,flush=True)
                        raw=folder/f'teacher-{corpus}.bin';np.asarray(rows,dtype='<f4').tofile(raw)
                        arm['teacher'][corpus]={'positions':64,'sha256':sha(raw),'reused_min':min(reused),'reused_max':max(reused)};save()
                    arm['chunk_events']=chunk_events(folder/'engine.log');arm['completed']=True;save()
                finally:e.close()
                print('STOPPED',label,flush=True)
    result.update(status='completed',elapsed_s=time.monotonic()-started)
except BaseException as exc:
    result.update(status='failed',error=repr(exc),elapsed_s=time.monotonic()-started);raise
finally:
    stop.set();thread.join(timeout=12);save();print('STATUS',result['status'],flush=True)
