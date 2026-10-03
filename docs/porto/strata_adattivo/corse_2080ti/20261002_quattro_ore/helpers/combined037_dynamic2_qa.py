"""Combined aligned037/dynamic-topk paired gate with complete oracles and fixed reference next-token logits."""
from pathlib import Path
import json, math, os, re, sys, threading, time
sys.path.insert(0,r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages')
ROOT=Path(__file__).resolve().parent/'fourhour_20261002'
SOURCE=ROOT/'dynamic2-source'
sys.path[:0]=[str(SOURCE),str(SOURCE/'tools'),str(SOURCE/'tools/sm75')]
import numpy as np
import psutil
import validate_model as V
from serve.server import StrataEngine
from serve.frontend import ChatTemplate, OutputParser
from tools.strata_tokenizer import Tokenizer

OUT=ROOT/'combined037_dynamic2_qa'
CFG=Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json')
cfg=json.loads(CFG.read_text(encoding='utf-8'))
args=json.loads((Path(r'D:\ds4_work\strata\validazioni\20261002_quality_0136_aba_final')/'plan.json').read_text(encoding='utf-8'))['args']
args=V.set_arg(V.set_arg(args,'--pcie-frac','0.28'),'--spec',4)
V.require(not OUT.exists(),'Existing output directory')
V.require(not any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name'])),'Another engine is active')
OUT.mkdir()
tp=Path(cfg['tokenizer']); vocab=json.loads((tp/'vocab.json').read_text(encoding='utf-8'))
tokens=[None]*len(vocab)
for text,index in vocab.items(): tokens[index]=text
tok=Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
tpl=ChatTemplate(tp/'chat_template.jinja')
def encode(text): return tok.encode(tpl.render([{'role':'user','content':text}],enable_thinking=True,reasoning_effort='low'),parse_special=True)
def decode_body(ids):
    body=tok.decode(ids)
    for stop in ('<|im_end|>','<|endoftext|>'): body=body.removesuffix(stop)
    parser=OutputParser(thinking=True); events=parser.feed(body)+parser.finish()
    return ''.join(x.text for x in events if x.kind=='content'), ''.join(x.text for x in events if x.kind=='reasoning')
def answer(content,finish,expected):
    if finish!='stop': return False
    text=content.strip()
    if text.startswith('```json\n') and text.endswith('\n```'): text=text[8:-4].strip()
    try: return json.loads(text)==expected
    except (ValueError,TypeError): return False
gold={'north':'ARCO-731','south':'LUNA-482','west':'PORTO-916'}
fill=tok.encode(V.TEXTS['doc'][1],parse_special=False)
cases=[{'name':name,'ids':encode(text),'expected':expected,'max_new':2048,'kind':'oracle'} for name,text,expected in V.ANSWERS]
teachers={}
for depth in (20000,32768,65536,131072):
    rendered=tpl.render([{'role':'user','content':'Read this archive. AUTH_RECORD lines are authoritative.\n__ARCHIVE__\nReturn JSON with keys north, south, west and their authoritative codes.'}],enable_thinking=True,reasoning_effort='low')
    left,right=rendered.split('__ARCHIVE__'); left=tok.encode(left,parse_special=True); right=tok.encode(right,parse_special=True)
    records=[tok.encode('\nAUTH_RECORD '+key+'='+val+'\n',parse_special=False) for key,val in gold.items()]
    remaining=depth-len(left)-len(right)-sum(map(len,records)); sizes=[remaining//10,remaining*4//10,remaining*4//10]; sizes.append(remaining-sum(sizes))
    archive=[]
    for i,size in enumerate(sizes):
        archive+=(fill*(size//len(fill)+1))[:size]
        if i<3: archive+=records[i]
    ids=left+archive+right; V.require(len(ids)==depth,'Fixture length differs')
    cases.append({'name':'records_'+str(depth),'ids':ids,'expected':gold,'max_new':2048,'kind':'oracle'})
    # Score a fixed reference continuation; never append the sampled prediction.
    tail=tok.encode(V.TEXTS['doc'][1],parse_special=False)[:65]
    teachers[str(depth)]={'prefix':ids,'tail':tail}
    V.write_json(OUT/('records_'+str(depth)+'.ids.json'),ids)
    V.write_json(OUT/('teacher_'+str(depth)+'.ids.json'),tail)
candidate_exe=ROOT/'build-dynamic2/strata.exe'
reference_exe=Path('D:/ds4_work/strata/Strata/build-0136-daily/strata.exe')
plan={'protocol':'installed036 A1 / aligned037 dynamic ON B / installed036 A2; PCIe0.28 fixed laboratory quality','exe':str(candidate_exe),'exe_sha256':V.sha(candidate_exe),'reference_exe':str(reference_exe),'reference_sha256':V.sha(reference_exe),'args':args,
      'thinking':True,'reasoning_effort':'low','temperature':0,'kv_capacity':262144,'kv_resident':32768,'kv':'int8',
      'env_common':{'STRATA_IQ_MT_MIN':'1','STRATA_PARALLEL_INTERMEDIATE_QUANT':'0','STRATA_DECODE_TIMING':'1','STRATA_WATCHDOG_S':'240'},
      'oracle_policy':'Complete stopped answer, JSON parsed exactly after optional single json code fence; strict unfenced result recorded separately.',
      'teacher_rows_per_depth':64,'depths':[20000,32768,65536,131072],'artificial_load':False,'daily_changed':False,
      'limits':'Fixed cache laboratory quality gate; teacher rows probe the target, not full draft-logit equality or general model quality.'}
V.write_json(OUT/'plan.json',plan)
result={'plan':plan,'status':'running','arms':{}}
def save(): V.write_json(OUT/'results.json',result)
started=time.monotonic()
try:
    for label,ring in [('A1','0'),('B','1'),('A2','0')]:
        folder=OUT/label; folder.mkdir(); (folder/'cuda-cache').mkdir()
        env=dict(os.environ); env.pop('STRATA_API_KEY',None); env.update(cfg.get('env',{})); env.update(plan['env_common'])
        env.update(STRATA_MTP_BATCH_RING='0',STRATA_TOPK_DYNAMIC=ring,STRATA_DUMP_FIRST_LOGITS=str(folder/'first'),CUDA_CACHE_PATH=str(folder/'cuda-cache'),PYTHONDONTWRITEBYTECODE='1')
        env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
        engine=StrataEngine(str(candidate_exe if label=='B' else reference_exe),args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
        arm={'ring':ring,'records':[],'teacher':{}}; result['arms'][label]=arm
        print('START',label,'ring',ring,flush=True)
        try:
            engine.restart(); arm['info']=dict(engine.info)
            V.require(engine.info.get('expert_slots')==6167,'Cache differs')
            V.require(engine.info.get('context')==262144 and engine.info.get('kv_resident')==32768,'KV differs')
            print('READY',label,json.dumps(arm['info']),flush=True); save()
            for case in cases:
                V.require(time.monotonic()-started<2400,'Task deadline exceeded')
                V.require(psutil.virtual_memory().available>8*2**30,'RAM floor')
                ids=[x for x in engine.generate(case['ids'],case['max_new'],{'temperature':0},threading.Event()) if x is not None]
                content,reasoning=decode_body(ids)
                item={'name':case['name'],'content':content,'reasoning':reasoning,'expected':case['expected'],
                      'pass':answer(content,engine.last['finish'],case['expected']),
                      'strict_unfenced_pass':V.evaluate_answer(content,engine.last['finish'],case['expected']),**engine.last}
                arm['records'].append(item); save(); print('ANSWER',label,case['name'],item['pass'],'strict',item['strict_unfenced_pass'],engine.last['finish'],flush=True)
                depth=case['name'].removeprefix('records_')
                if depth in teachers:
                    teacher=teachers[depth]; prefix=teacher['prefix']; tail=teacher['tail']
                    rows=[]
                    for pos in range(64):
                        reference=prefix+tail[:pos]
                        raw=folder/('first.pos'+str(len(reference)-1)+'.f32')
                        if raw.exists(): raw.unlink()
                        generated=[x for x in engine.generate(reference,1,{'temperature':0},threading.Event()) if x is not None]
                        V.require(len(generated)==1 and raw.is_file(),'Missing teacher row')
                        row=np.fromfile(raw,dtype='<f4'); V.require(row.size==len(tokens) and bool(np.isfinite(row).all()),'Invalid logits')
                        rows.append(row); raw.unlink()
                    path=folder/('teacher_'+depth+'.bin'); np.asarray(rows,dtype='<f4').tofile(path)
                    arm['teacher'][depth]={'rows':64,'sha256':V.sha(path),'path':str(path)}; save()
                    print('TEACHER',label,depth,'finite',flush=True)
        finally: engine.close()
        print('STOPPED',label,flush=True)
    report={'teacher':{},'oracle_pass':all(r['pass'] for a in result['arms'].values() for r in a['records'])}
    for depth,teacher in teachers.items():
        arrays=[np.fromfile(OUT/label/('teacher_'+depth+'.bin'),dtype='<f4').reshape(64,len(tokens)) for label in ('A1','B','A2')]
        def score(other):
            kl=[]; same=[]; na=[]; nb=[]
            for i in range(64):
                pa,pb=V.logsoftmax(arrays[0][i]),V.logsoftmax(other[i])
                target=teacher['tail'][i]; na.append(-float(pa[target])); nb.append(-float(pb[target]))
                kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())))
                same.append(bool(arrays[0][i].argmax()==other[i].argmax()))
            delta=[b-a for a,b in zip(na,nb)]
            return {'positions':64,'top1_agreement_pct':100*float(np.mean(same)),
                    'kl_mean':float(np.mean(kl)),'kl_median':float(np.median(kl)),'kl_p99':float(np.percentile(kl,99)),
                    'kl_max':float(np.max(kl)),'ppl_reference':math.exp(float(np.mean(na))),
                    'ppl_candidate':math.exp(float(np.mean(nb))),'nll_delta_mean':float(np.mean(delta)),
                    'nll_deltas':delta,'kl_values':kl,'same_top1':same}
        candidate,repeat=score(arrays[1]),score(arrays[2])
        report['teacher'][depth]={'candidate':V.public_stats(candidate),'reference_repeat':V.public_stats(repeat),
            'bitwise_candidate':bool(np.array_equal(arrays[0],arrays[1])),'bitwise_repeat':bool(np.array_equal(arrays[0],arrays[2])),
            'gate':V.regression_gate(candidate,repeat)}
    report['pass']=report['oracle_pass'] and all(x['gate']['pass'] for x in report['teacher'].values())
    result.update(status='completed',report=report); save(); V.write_json(OUT/'comparison.json',report)
    print('RING_QA',report['pass'],json.dumps(report),flush=True)
except BaseException as error:
    result.update(status='failed',error=str(error)); save(); raise
