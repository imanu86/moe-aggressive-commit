"""Matched chunk control: checkpoint interval equals native prefill chunk 6144.

Read the same frozen prompts on verified A/B engines. This does not validate the
original 1536/6144 patch or certify model quality beyond the measured workload.
"""
from pathlib import Path
import os,sys,json,time,threading,shutil,math
R=Path(__file__).resolve().parent/'checkpoint038_20261003'; S=R/'source'; speed=R/'model-tests-r3'
sys.path[:0]=[str(S),r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np,psutil,validate_model as V
from serve.server import StrataEngine
from serve.frontend import ChatTemplate,OutputParser
from tools.strata_tokenizer import Tokenizer
out=R/'aligned-chunk-control'; out.mkdir(exist_ok=False)
cfg=json.loads(Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
m=json.loads((speed/'results.json').read_text(encoding='utf-8'))
qa=json.loads((R/'quality-tests-r3/results.json').read_text(encoding='utf-8'))
assert m['status']==qa['status']=='completed'
ids={k:json.loads((speed/(v+'.ids.json')).read_text(encoding='utf-8')) for k,v in [('fresh','fresh'),('follow','follow'),('tail','teacher_tail')]}
tp=Path(cfg['tokenizer']); vocab=json.loads((tp/'vocab.json').read_text(encoding='utf-8'));tokens=[None]*len(vocab)
for text,i in vocab.items(): tokens[i]=text
tok=Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
warm=tok.encode(ChatTemplate(tp/'chat_template.jinja').render([{'role':'user','content':'Return only JSON with key ready and value true.'}],enable_thinking=False),parse_special=True)
result={'status':'running','purpose':'configuration control, prefill 6144 and checkpoint cadence 6144 preserve reference chunk geometry','arms':{},'timing_is_single_run_diagnostic':True,'no_elastic':True}
started=time.monotonic()
def save(): (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
def guard():
    assert time.monotonic()-started<900 and psutil.virtual_memory().available>8*2**30
def decode(generated):
    text=tok.decode(generated)
    for special in ('<|im_end|>','<|endoftext|>'): text=text.removesuffix(special)
    p=OutputParser(thinking=False)
    return ''.join(x.text for x in p.feed(text)+p.finish() if x.kind=='content')
def oracle(text,finish):
    try:
        text=text.strip()
        if text.startswith('```json\n') and text.endswith('\n```'): text=text[8:-4].strip()
        return finish=='stop' and json.loads(text)==m['plan']['expected']
    except ValueError: return False
save()
assert not any('strata' in (p.info['name'] or '').lower() and (p.info['name'] or '').lower().endswith('.exe') for p in psutil.process_iter(['name']))
try:
    for mode in ('A','B'):
        guard();folder=out/mode;folder.mkdir();exe=R/f'strata-qa-{mode}.exe'
        assert V.sha(exe)==qa['arms'][f'chunk1536_{mode}1']['exe_sha256']
        args=V.set_arg(V.set_arg(m['plan']['args'],'--prefill',6144),'--prompt-cache-every',6144)
        env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
        env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(speed/'cuda-cache'),STRATA_WATCHDOG_S='240',STRATA_PARALLEL_INTERMEDIATE_QUANT='0',STRATA_TEST_FIRST_LOGITS=str(folder/'first.f32'))
        env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
        e=StrataEngine(str(exe),args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
        arm={'exe_sha256':V.sha(exe),'args':args,'requests':[]};result['arms'][mode]=arm;save();print('ALIGNED START',mode,flush=True)
        try:
            e.restart();arm['info']=dict(e.info)
            assert int(e.info['expert_slots'])==5357 and int(e.info['context'])==262144 and int(e.info['vram_free_mib'])>=1000
            list(e.generate(warm,32,{'temperature':0},threading.Event()))
            for prompt in ('fresh','follow'):
                guard();dump=folder/'first.f32';dump.unlink(missing_ok=True)
                generated=[x for x in e.generate(ids[prompt],128,{'temperature':0},threading.Event()) if x is not None]
                row=np.fromfile(dump,dtype='<f4');assert row.size==len(tokens) and np.isfinite(row).all()
                shutil.copy2(dump,folder/f'{prompt}-first.f32')
                text=decode(generated);item={'name':prompt,'content':text,'output_ids':generated,**e.last,'oracle_pass':oracle(text,e.last['finish'])}
                arm['requests'].append(item);save();assert item['oracle_pass']
                assert item['reused']==(0 if prompt=='fresh' else 30720)
                print('ALIGNED REQUEST',mode,prompt,'reused',item['reused'],flush=True)
            rows=[]
            for pos in range(64):
                guard();dump=folder/'first.f32';dump.unlink(missing_ok=True)
                list(e.generate(ids['follow']+ids['tail'][:pos],1,{'temperature':0},threading.Event()))
                row=np.fromfile(dump,dtype='<f4');assert row.size==len(tokens) and np.isfinite(row).all();rows.append(row)
                if (pos+1)%16==0: print('ALIGNED ROWS',mode,pos+1,flush=True)
            raw=folder/'teacher.bin';np.asarray(rows,dtype='<f4').tofile(raw);arm.update(teacher_sha256=V.sha(raw),completed=True);save()
        finally: e.close()
        print('ALIGNED STOPPED',mode,flush=True)
    result['comparison']={}
    for label,file in [('fresh','fresh-first.f32'),('follow','follow-first.f32'),('teacher','teacher.bin')]:
        a,b=[np.fromfile(out/mode/file,dtype='<f4').reshape(-1,len(tokens)) for mode in ('A','B')]
        kl=[]
        for ar,br in zip(a,b):
            pa,pb=V.logsoftmax(ar),V.logsoftmax(br);kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())))
        result['comparison'][label]={'positions':len(a),'bitwise':bool(np.array_equal(a,b)),'kl_mean':float(np.mean(kl)),'kl_p99':float(np.percentile(kl,99)),'top1_agreement_pct':100*float(np.mean(a.argmax(axis=1)==b.argmax(axis=1))),'max_logit_abs_delta':float(np.max(np.abs(a-b)))}
    result['versus_original_baseline6144']={}
    for mode in ('A','B'):
        result['versus_original_baseline6144'][mode]={}
        for label,file in [('fresh','fresh-first.f32'),('follow','follow-first.f32'),('teacher','teacher.bin')]:
            ref=R/'quality-tests-r3/chunk6144_A1'/file
            a,b=[np.fromfile(p,dtype='<f4').reshape(-1,len(tokens)) for p in (ref,out/mode/file)]
            kl=[]
            for ar,br in zip(a,b):
                pa,pb=V.logsoftmax(ar),V.logsoftmax(br);kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())))
            result['versus_original_baseline6144'][mode][label]={'positions':len(a),'bitwise':bool(np.array_equal(a,b)),'kl_mean':float(np.mean(kl)),'kl_p99':float(np.percentile(kl,99)),'top1_agreement_pct':100*float(np.mean(a.argmax(axis=1)==b.argmax(axis=1))),'max_logit_abs_delta':float(np.max(np.abs(a-b)))}
    result.update(status='completed',elapsed_s=time.monotonic()-started)
except BaseException as exc:
    result.update(status='failed',error=repr(exc));raise
finally: save();print('ALIGNED STATUS',result['status'],flush=True)
