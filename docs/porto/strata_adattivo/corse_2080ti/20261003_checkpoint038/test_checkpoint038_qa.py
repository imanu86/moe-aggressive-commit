"""Unmeasured quality run: shipping A/B + identical server logits readout."""
from pathlib import Path
import os,sys,json,time,threading,shutil
R=Path(__file__).resolve().parent/'checkpoint038_20261003';S=R/'source';speed=R/'model-tests-r3'
sys.path[:0]=[str(S),r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np,psutil,validate_model as V
from serve.server import StrataEngine
from serve.frontend import OutputParser,ChatTemplate
out=R/'quality-tests-r3';out.mkdir(exist_ok=False)
cfg=json.loads(Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
measured=json.loads((speed/'results.json').read_text(encoding='utf-8'));assert measured['status']=='completed'
fresh=json.loads((speed/'fresh.ids.json').read_text());follow=json.loads((speed/'follow.ids.json').read_text());tail=json.loads((speed/'teacher_tail.ids.json').read_text())
tp=Path(cfg['tokenizer'])
from tools.strata_tokenizer import Tokenizer
vocab=json.loads((tp/'vocab.json').read_text(encoding='utf-8'));tokens=[None]*len(vocab)
for text,index in vocab.items():tokens[index]=text
tok=Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
warm=tok.encode(ChatTemplate(tp/'chat_template.jinja').render([{'role':'user','content':'Return only JSON with key ready and value true.'}],enable_thinking=False),parse_special=True)
rendered=ChatTemplate(tp/'chat_template.jinja').render([{'role':'user','content':'Read the archive. Only AUTH_RECORD lines define the requested codes.\n__ARCHIVE__\nReturn only JSON with keys north, south, west containing the codes.'}],enable_thinking=False)
right=tok.encode(rendered.split('__ARCHIVE__')[1],parse_special=True)
assert follow[-len(right):]==right
fill=tok.encode(V.TEXTS['doc'][1],parse_special=False)
grow=follow[:-len(right)]+(fill*(20000//len(fill)+1))[:20000]+right
branch=grow[:-len(right)]+tok.encode('\nTHIRD additional independent appendix.\n',parse_special=False)+right
for name,ids in [('grow',grow),('branch',branch)]:(out/(name+'.ids.json')).write_text(json.dumps(ids))
def decode(ids):
    body=tok.decode(ids)
    for token in ('<|im_end|>','<|endoftext|>'):body=body.removesuffix(token)
    p=OutputParser(thinking=False)
    return ''.join(x.text for x in p.feed(body)+p.finish() if x.kind=='content')
def oracle(text,finish):
    try:
        text=text.strip()
        if text.startswith('```json\n') and text.endswith('\n```'):text=text[8:-4].strip()
        return finish=='stop' and json.loads(text)==measured['plan']['expected']
    except ValueError:return False
result={'status':'running','test_readout_only':True,'rows_per_arm':64,'shipping_patch':str(R/'checkpoint-grid.patch'),'policy':V.POLICY,'warmup':'same unrelated 32-token-max request as timing; preceding QA attempts invalid due mixed Prefill ABI, preserved separately','arms':{}}
qa_build=json.loads((R/'qa-build.json').read_text(encoding='utf-8'))
assert all(x['both_translation_units_rebuilt'] for x in qa_build['qa_binaries'].values())
def save():(out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
def guard():
    assert time.monotonic()-started<2400,'QA deadline'
    assert psutil.virtual_memory().available>8*2**30,'RAM reserve'
started=time.monotonic();save()
assert not any('strata' in (p.info['name'] or '').lower() and (p.info['name'] or '').lower().endswith('.exe') for p in psutil.process_iter(['name']))
try:
    for chunk in measured['plan']['chunks']:
        for label,mode in [('A1','A'),('B1','B'),('A2','A')]:
            guard();name=f'chunk{chunk}_{label}';folder=out/name;folder.mkdir()
            env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
            env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(speed/'cuda-cache'),STRATA_WATCHDOG_S='240',STRATA_PARALLEL_INTERMEDIATE_QUANT='0',STRATA_TEST_FIRST_LOGITS=str(folder/'first.f32'))
            env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
            exe=R/f'strata-qa-{mode}.exe';args=V.set_arg(measured['plan']['args'],'--prefill',chunk)
            engine=StrataEngine(str(exe),args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
            arm={'exe_sha256':V.sha(exe),'requests':[]};result['arms'][name]=arm;save();print('QA START',name,flush=True)
            try:
                engine.restart();arm['info']=dict(engine.info)
                assert int(engine.info['expert_slots'])==5357 and int(engine.info['vram_free_mib'])>=1000
                list(engine.generate(warm,32,{'temperature':0},threading.Event()))
                for prompt_name,ids in [('fresh',fresh),('follow',follow)]:
                    guard();dump=folder/'first.f32';dump.unlink(missing_ok=True)
                    generated=[x for x in engine.generate(ids,128,{'temperature':0},threading.Event()) if x is not None]
                    row=np.fromfile(dump,dtype='<f4');assert row.size==len(tokens) and np.isfinite(row).all()
                    shutil.copy2(dump,folder/f'{prompt_name}-first.f32')
                    text=decode(generated);item={'name':prompt_name,'content':text,'output_ids':generated,**engine.last,'oracle_pass':oracle(text,engine.last['finish'])}
                    arm['requests'].append(item);save();assert item['oracle_pass']
                    if mode=='B' and prompt_name=='follow':assert item['reused']>=32768
                rows=[]
                for pos in range(64):
                    guard();dump=folder/'first.f32';dump.unlink(missing_ok=True)
                    list(engine.generate(follow+tail[:pos],1,{'temperature':0},threading.Event()))
                    row=np.fromfile(dump,dtype='<f4');assert row.size==len(tokens) and np.isfinite(row).all()
                    rows.append(row)
                    if (pos+1)%16==0:print('QA ROWS',name,pos+1,flush=True)
                raw=folder/'teacher.bin';np.asarray(rows,dtype='<f4').tofile(raw)
                arm['teacher']={'positions':64,'sha256':V.sha(raw)};arm['completed']=True;save()
                if mode=='B':
                    for prompt_name,ids,min_reuse in [('grow',grow,32768),('branch',branch,49152)]:
                        guard()
                        generated=[x for x in engine.generate(ids,128,{'temperature':0},threading.Event()) if x is not None]
                        text=decode(generated);item={'name':prompt_name,'content':text,'output_ids':generated,**engine.last,'oracle_pass':oracle(text,engine.last['finish'])}
                        arm['requests'].append(item);save()
                        assert item['oracle_pass'] and item['reused']>=min_reuse
                        print('QA RESUME',name,prompt_name,'reused',item['reused'],flush=True)
            finally:engine.close()
            print('QA STOPPED',name,flush=True)
    for mode in ('A','B'):
        guard();name='cache0_'+mode;folder=out/name;folder.mkdir()
        env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
        env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(speed/'cuda-cache'),STRATA_WATCHDOG_S='240',STRATA_PARALLEL_INTERMEDIATE_QUANT='0',STRATA_TEST_FIRST_LOGITS=str(folder/'first.f32'))
        env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
        args=V.set_arg(V.set_arg(measured['plan']['args'],'--prefill',1536),'--prompt-cache',0)
        exe=R/f'strata-qa-{mode}.exe';engine=StrataEngine(str(exe),args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
        arm={'exe_sha256':V.sha(exe),'requests':[]};result['arms'][name]=arm;save();print('QA START',name,flush=True)
        try:
            engine.restart();arm['info']=dict(engine.info);guard()
            list(engine.generate(warm,32,{'temperature':0},threading.Event()))
            generated=[x for x in engine.generate(fresh,128,{'temperature':0},threading.Event()) if x is not None]
            row=np.fromfile(folder/'first.f32',dtype='<f4');assert row.size==len(tokens) and np.isfinite(row).all()
            text=decode(generated);item={'name':'fresh','content':text,'output_ids':generated,**engine.last,'oracle_pass':oracle(text,engine.last['finish'])}
            arm['requests'].append(item);arm['completed']=True;save();assert item['oracle_pass'] and item['reused']==0
        finally:engine.close()
        print('QA STOPPED',name,flush=True)
    result['status']='completed'
except BaseException as e:
    result.update(status='failed',error=str(e));raise
finally:
    save();print('QA STATUS',result['status'],flush=True)
