"""Private diagnostic: identical follow prompt cold versus prior valid cached QA.

This isolates prior prompt checkpoint reuse, not expert-cache contents. No timing
or quality promotion is implied. Existing verified A/B binaries are unchanged.
"""
from pathlib import Path
import os, sys, json, time, threading, shutil, math
R=Path(__file__).resolve().parent/'checkpoint038_20261003'
S=R/'source'; speed=R/'model-tests-r3'; hot=R/'quality-tests-r3'
sys.path[:0]=[str(S),r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np, psutil, validate_model as V
from serve.server import StrataEngine
from serve.frontend import OutputParser, ChatTemplate
from tools.strata_tokenizer import Tokenizer
out=R/'cache-replay-diagnosis'; out.mkdir(exist_ok=False)
cfg=json.loads(Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
measured=json.loads((speed/'results.json').read_text(encoding='utf-8'))
qa=json.loads((hot/'results.json').read_text(encoding='utf-8'))
build=json.loads((R/'qa-build.json').read_text(encoding='utf-8'))
assert measured['status']==qa['status']=='completed'
assert all(x['both_translation_units_rebuilt'] for x in build['qa_binaries'].values())
follow=json.loads((speed/'follow.ids.json').read_text(encoding='utf-8'))
tail=json.loads((speed/'teacher_tail.ids.json').read_text(encoding='utf-8'))
tp=Path(cfg['tokenizer']); vocab=json.loads((tp/'vocab.json').read_text(encoding='utf-8'))
tokens=[None]*len(vocab)
for text,index in vocab.items(): tokens[index]=text
tok=Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
warm=tok.encode(ChatTemplate(tp/'chat_template.jinja').render([{'role':'user','content':'Return only JSON with key ready and value true.'}],enable_thinking=False),parse_special=True)
started=time.monotonic()
result={'status':'running','purpose':'cold versus cached same prompt, expert cache fixed; diagnostic only','prior_valid_qa':str(hot),'prompt_tokens':len(follow),'rows_per_arm':64,'arms':{}}
def save():
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
def guard():
    assert time.monotonic()-started<1800,'30-minute diagnostic deadline'
    assert psutil.virtual_memory().available>8*2**30,'RAM reserve'
def decode(ids):
    body=tok.decode(ids)
    for token in ('<|im_end|>','<|endoftext|>'): body=body.removesuffix(token)
    p=OutputParser(thinking=False)
    return ''.join(x.text for x in p.feed(body)+p.finish() if x.kind=='content')
def oracle(text,finish):
    try:
        text=text.strip()
        if text.startswith('```json\n') and text.endswith('\n```'): text=text[8:-4].strip()
        return finish=='stop' and json.loads(text)==measured['plan']['expected']
    except ValueError: return False
def compare(a,b,targets=None):
    assert a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all()
    if a.ndim==1: a=a[None,:]; b=b[None,:]
    kl=[]; na=[]; nb=[]
    for pos in range(len(a)):
        pa,pb=V.logsoftmax(a[pos]),V.logsoftmax(b[pos])
        kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())))
        if targets is not None:
            na.append(-float(pa[targets[pos]])); nb.append(-float(pb[targets[pos]]))
    r={'positions':len(a),'bitwise':bool(np.array_equal(a,b)), 'top1_agreement_pct':100*float(np.mean(a.argmax(axis=1)==b.argmax(axis=1))), 'max_logit_abs_delta':float(np.max(np.abs(a-b))), 'kl_mean':float(np.mean(kl)), 'kl_median':float(np.median(kl)), 'kl_p99':float(np.percentile(kl,99)), 'kl_max':float(max(kl))}
    if targets is not None:
        r.update(ppl_reference=math.exp(float(np.mean(na))),ppl_candidate=math.exp(float(np.mean(nb))),nll_delta_mean=float(np.mean(np.array(nb)-na)))
    return r
save()
assert not any('strata' in (p.info['name'] or '').lower() and (p.info['name'] or '').lower().endswith('.exe') for p in psutil.process_iter(['name']))
try:
    for chunk in (1536,6144):
        for mode in ('A','B'):
            guard(); name=f'chunk{chunk}_{mode}'; folder=out/name; folder.mkdir()
            prior=hot/f'chunk{chunk}_{mode}1'; exe=R/f'strata-qa-{mode}.exe'
            assert V.sha(exe)==qa['arms'][f'chunk{chunk}_{mode}1']['exe_sha256']
            args=V.set_arg(measured['plan']['args'],'--prefill',chunk)
            env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
            env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(speed/'cuda-cache'),STRATA_WATCHDOG_S='240',STRATA_PARALLEL_INTERMEDIATE_QUANT='0',STRATA_TEST_FIRST_LOGITS=str(folder/'first.f32'))
            env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
            engine=StrataEngine(str(exe),args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
            arm={'exe_sha256':V.sha(exe),'args':args}; result['arms'][name]=arm; save()
            print('COLD START',name,flush=True)
            try:
                engine.restart(); arm['info']=dict(engine.info)
                assert int(engine.info['expert_slots'])==5357 and int(engine.info['context'])==262144 and int(engine.info['vram_free_mib'])>=1000
                list(engine.generate(warm,32,{'temperature':0},threading.Event()))
                dump=folder/'first.f32'; dump.unlink(missing_ok=True); guard()
                generated=[x for x in engine.generate(follow,128,{'temperature':0},threading.Event()) if x is not None]
                row=np.fromfile(dump,dtype='<f4'); assert row.size==len(tokens) and np.isfinite(row).all()
                shutil.copy2(dump,folder/'cold-follow-first.f32')
                text=decode(generated)
                arm['request']={'content':text,'output_ids':generated,**engine.last,'oracle_pass':oracle(text,engine.last['finish'])}
                save(); assert arm['request']['oracle_pass'] and arm['request']['reused']==0
                arm['first_cold_vs_hot']=compare(np.fromfile(prior/'follow-first.f32',dtype='<f4'),row)
                save(); print('COLD FIRST',name,json.dumps(arm['first_cold_vs_hot']),flush=True)
                rows=[]
                for pos in range(64):
                    guard(); dump.unlink(missing_ok=True)
                    list(engine.generate(follow+tail[:pos],1,{'temperature':0},threading.Event()))
                    row=np.fromfile(dump,dtype='<f4'); assert row.size==len(tokens) and np.isfinite(row).all()
                    rows.append(row)
                    if (pos+1)%16==0: print('COLD ROWS',name,pos+1,flush=True)
                raw=folder/'teacher.bin'; arr=np.asarray(rows,dtype='<f4'); arr.tofile(raw)
                arm['teacher_sha256']=V.sha(raw)
                arm['teacher_cold_history_vs_hot_history']=compare(np.fromfile(prior/'teacher.bin',dtype='<f4').reshape(64,-1),arr,tail)
                arm['completed']=True; save()
                print('COLD COMPARE',name,json.dumps(arm['teacher_cold_history_vs_hot_history']),flush=True)
            finally: engine.close()
            print('COLD STOPPED',name,flush=True)
    result['cross_engine_cold']={}
    for chunk in (1536,6144):
        aa=out/f'chunk{chunk}_A'; bb=out/f'chunk{chunk}_B'
        result['cross_engine_cold'][str(chunk)]={'first':compare(np.fromfile(aa/'cold-follow-first.f32',dtype='<f4'),np.fromfile(bb/'cold-follow-first.f32',dtype='<f4')), 'teacher':compare(np.fromfile(aa/'teacher.bin',dtype='<f4').reshape(64,-1),np.fromfile(bb/'teacher.bin',dtype='<f4').reshape(64,-1),tail)}
    result.update(status='completed',elapsed_s=time.monotonic()-started)
except BaseException as e:
    result.update(status='failed',error=repr(e)); raise
finally:
    save(); print('COLD STATUS',result['status'],flush=True)
