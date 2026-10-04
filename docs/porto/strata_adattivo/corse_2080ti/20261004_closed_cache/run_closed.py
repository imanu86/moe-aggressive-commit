"""Bounded, serial fixed-cache test. Outputs are data; never execute model code."""
import argparse, hashlib, json, os, re, subprocess, sys, threading, time
from pathlib import Path
import psutil
L=Path(__file__).resolve().parent
sys.path.insert(0,str(L.parent/'20261004_neuron_cache'))
from run_capture import PREFIX, CONFIG, F, bounded, sha, PROMPTS

def fixture(task):
    if task=='smoke': return PROMPTS[2][1],None
    if task=='ledger':
        rows=[]
        for i in range(1,41):
            rows.append(dict(id=f'R{i:02}',start=80+3*i,received=i%7+2,sold=i%5+1,
                             aisle=f'A{i%6}',owner=f'unit-{i%9}',state='audited'))
        prompt=('This is a synthetic stock ledger. Every row is independent. All amounts are integers. '
                'The ending quantity is start + received - sold. Use these exact records, not outside knowledge.\n'+
                '\n'.join(json.dumps(r,separators=(',',':')) for r in rows)+
                '\nReturn only JSON: {"rows":[{"id":"R01","end":N}, ... through R12],"total":N}. '
                'Report exactly the first twelve rows, in order. Total is the sum of their ending quantities. '
                'Do not include rows R13 to R40. Do not add explanations or Markdown.')
        out=[dict(id=r['id'],end=r['start']+r['received']-r['sold']) for r in rows[:12]]
        return prompt,dict(rows=out,total=sum(r['end'] for r in out))
    if task=='code':
        refs=[]
        for i in range(1,31):
            refs.append(f'Cache note {i:02}: capacity is 3 entries; keys are case sensitive. '
                'A hit moves its key to the newest position. A miss leaves order unchanged. '
                'A put of an existing key updates its value and moves it to newest. '
                'A put of a new key at capacity evicts exactly the oldest key. '
                'Keys in a reported state must be ordered from oldest to newest.')
        ops=[('put','A'),('put','B'),('put','C'),('get','A'),('put','D'),('get','B'),
             ('put','C'),('put','E'),('get','D'),('put','F'),('get','C'),('put','D')]
        order=[];ev=[];states=[]
        for op,key in ops:
            if key in order: order.remove(key);order.append(key)
            elif op=='put':
                if len(order)==3:ev.append(order.pop(0))
                order.append(key)
            states.append(list(order))
        prompt=('Trace this LRU cache exactly. Reference notes:\n'+'\n'.join(refs)+
                '\nOperations, beginning with an empty cache:\n'+json.dumps(ops)+
                '\nReturn only JSON with keys states (the oldest-to-newest key array after each of the 12 operations), '
                'evicted (keys in eviction order), and eviction_count. No code, Markdown or explanation.')
        return prompt,dict(states=states,evicted=ev,eviction_count=len(ev))
    raise ValueError(task)

def oracle(text,expected):
    if expected is None:return dict(passed=None,note='Manual smoke only')
    s=text.strip()
    if s.startswith('```'):s=re.sub(r'^```(?:json)?\s*','',s);s=re.sub(r'\s*```$','',s)
    s=re.sub(r'<\|[^>]+\|>','',s).strip()
    try:
        got=json.loads(s);return dict(passed=got==expected,expected=expected,actual=got)
    except ValueError as e:return dict(passed=False,expected=expected,error=str(e))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True)
    ap.add_argument('--mode',choices=['daily','default','observe','resident','drop'],required=True)
    ap.add_argument('--task',choices=['smoke','ledger','code'],required=True)
    ap.add_argument('--tokens',type=int,default=512);ap.add_argument('--build',default='build-v1')
    ap.add_argument('--min-p',type=float,default=None);ap.add_argument('--run',action='store_true');a=ap.parse_args()
    assert a.name.replace('-','').replace('_','').isalnum() and 1<=a.tokens<=1024
    out=(L/a.name).resolve();assert not out.exists()
    cfg=json.loads(CONFIG.read_text());exe=Path(cfg['exe']) if a.mode=='daily' else L/a.build/'strata.exe'
    helper=PREFIX.load_helper();tok,template,convert,_=helper.tokenizer_and_template(cfg)
    from serve import server
    prompt,expected=fixture(a.task)
    body={'messages':[{'role':'system','content':'You are a careful technical assistant.'},{'role':'user','content':prompt}],
          'reasoning_effort':'none'}
    messages,tools,kw=convert(body);rendered=template.render(messages,tools,**kw);ids=tok.encode(rendered,parse_special=True)
    args=PREFIX.fixed_args(server,cfg,tok.encode('<|im_start|>',parse_special=True)[0],False,None)
    args=PREFIX.replace_option(args,'--pcie-frac','0.25');args=PREFIX.replace_option(args,'--prompt-cache','0')
    if a.min_p is not None:args=PREFIX.replace_option(args,'--spec-min-p',str(a.min_p))
    args.append('--no-spec-split')
    env=PREFIX.environment(cfg,out/'unused');env.pop('STRATA_DUMP_FIRST_LOGITS',None)
    env.update(STRATA_NO_LARGEPAGES='1',STRATA_ARENA_PIN_GIB='8',STRATA_DECODE_TIMING='1')
    if a.mode in ('observe','resident','drop'):env['STRATA_CLOSED_ROUTING']=a.mode
    # Equal device planning for both arms; observer hooks alone can then be checked.
    env['STRATA_VERIFY_DEVICE_PLAN']='1'
    plan=dict(mode=a.mode,task=a.task,args=args,prompt_ids=ids,prompt_tokens=len(ids),rendered_prompt=rendered,
              max_tokens=a.tokens,expected=expected,sampling=dict(temperature=0,seed=73),
              executable_sha256=sha(exe),daily_sha256=sha(Path(cfg['exe'])),config_sha256=sha(CONFIG),
              env={k:v for k,v in env.items() if k.startswith(('STRATA_','CUDA_'))},runner_sha256=sha(Path(__file__)))
    print(json.dumps(dict(mode=a.mode,task=a.task,prompt_tokens=len(ids),max_tokens=a.tokens)),flush=True)
    if not a.run:return
    if a.mode!='daily':
        pin=json.loads((exe.parent/'result.json').read_text());assert pin['status']=='completed'
        assert sha(exe)==pin['executable_sha256'];assert all(sha(F/p)==h for p,h in pin['source_files'].items()),'Changed source'
    competing,idle=PREFIX.check_competing_processes();assert not competing,competing
    assert psutil.virtual_memory().available>16*1024**3,'Too little available RAM'
    out.mkdir();(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    result=dict(status='starting',idle_nodes=idle,system_start=dict(available_ram=psutil.virtual_memory().available))
    try:result['gpu_before']=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader'],text=True,timeout=15).strip()
    except Exception as e:result['gpu_before_error']=repr(e)
    engine=server.StrataEngine(str(exe),args,cwd=cfg['cwd'],log=str(out/'engine.log'),env=env,lazy=True)
    started=time.monotonic();owned={};emitted=[]
    try:
        bounded(engine.restart,180,engine,owned,'Startup deadline')
        assert engine.alive();result['engine_info']=dict(engine.info);info=engine.info
        for k,v in dict(context=262144,kv='int8',kv_resident=32768,spec=4,mtp_max=4,pool_workers=7,expert_slots=5080,expert_cache_mib=8442).items():assert info.get(k)==v,(k,info.get(k),v)
        result['startup_s']=time.monotonic()-started
        req=time.monotonic();first=[];proc=psutil.Process(engine.proc.pid);cpu0=sum(proc.cpu_times()[:2])
        def gen():
            for token in engine.generate(ids,a.tokens,plan['sampling'],threading.Event()):
                if token is not None:
                    if not emitted:first.extend([time.monotonic(),sum(proc.cpu_times()[:2])])
                    emitted.append(int(token))
        bounded(gen,180,engine,owned,'Generation deadline')
        end=time.monotonic();cpu1=sum(proc.cpu_times()[:2])
        text=tok.decode(emitted)
        result.update(status='completed',generated_ids=emitted,text=text,last=dict(engine.last),request_s=end-req,
                      ttft_s=first[0]-req if first else None,request_cpu_s=cpu1-cpu0,
                      after_first_cpu_s=cpu1-first[1] if first else None,
                      after_first_s=end-first[0] if first else None,oracle=oracle(text,expected))
        (out/'answer.txt').write_text(text,encoding='utf-8')
    except BaseException as e:result.update(status='failed',error=repr(e));raise
    finally:
        try:
            if not getattr(engine,'_neuron_worker_stuck',False):bounded(engine.close,35,engine,owned,'Cleanup deadline')
        except BaseException as e:result['close_error']=repr(e)
        result['cleanup_actions']=PREFIX.terminate_owned(owned)
        remaining=[]
        for pid,born in owned.items():
            try:
                p=psutil.Process(pid)
                if abs(p.create_time()-born)<.02 and p.is_running():remaining.append(pid)
            except psutil.NoSuchProcess:pass
        result.update(remaining_owned=remaining,elapsed_s=time.monotonic()-started,
                      daily_unchanged=sha(Path(cfg['exe']))==plan['daily_sha256'],config_unchanged=sha(CONFIG)==plan['config_sha256'])
        log=(out/'engine.log').read_text(errors='replace') if (out/'engine.log').exists() else ''
        result['native_metrics']=[s for s in log.splitlines() if any(k in s for k in ['CLOSED_','decode timing','decode:','drafts','expert-cache:','prefill stats'])]
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ['status','last','ttft_s','after_first_cpu_s','after_first_s','oracle','native_metrics']}),flush=True)
    assert not remaining and result['daily_unchanged'] and result['config_unchanged']
if __name__=='__main__':main()
