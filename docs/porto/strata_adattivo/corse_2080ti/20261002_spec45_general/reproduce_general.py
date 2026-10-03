"""Paired spec 4/5/4 model check with complete oracles and bounded decode samples."""
from pathlib import Path
import collections
import hashlib
import json
import os
import re
import sys
import threading
import time

sys.path.insert(0, r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages')
ROOT=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'tools/sm75')]
import psutil
import validate_model as V
from serve.server import StrataEngine
from serve.frontend import ChatTemplate,OutputParser
from tools.strata_tokenizer import Tokenizer

OUT=Path(__file__).resolve().parent/'20261002_spec45_general_aba'
CFG=Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json')
SOURCE=Path(r'D:\ds4_work\strata\validazioni\20261002_quality_0136_aba_final')
cfg=json.loads(CFG.read_text(encoding='utf-8'))
base_args=json.loads((SOURCE/'plan.json').read_text(encoding='utf-8'))['args']
V.require(not OUT.exists(),'Existing output directory')
V.require(not any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name'])),'Another engine is active')
V.require(psutil.virtual_memory().available>16*2**30,'Insufficient initial RAM')
OUT.mkdir()
tp=Path(cfg['tokenizer'])
vocab=json.loads((tp/'vocab.json').read_text(encoding='utf-8'))
tokens=[None]*len(vocab)
for text,index in vocab.items(): tokens[index]=text
tok=Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
tpl=ChatTemplate(tp/'chat_template.jinja')
def encode(text):
    return tok.encode(tpl.render([{'role':'user','content':text}],enable_thinking=True,reasoning_effort='low'),parse_special=True)
gold={'north':'ARCO-731','south':'LUNA-482','west':'PORTO-916'}
fill=tok.encode(V.TEXTS['doc'][1],parse_special=False)
cases=[]
for name,text,expected in V.ANSWERS:
    cases.append({'name':name,'kind':'oracle','expected':expected,'ids':encode(text),'max_new':2048})
bench_question=('Write a detailed archive operations manual in 18 numbered sections, with examples, covering immutable revisions, '
                'record lookup, checksums, binary versus decimal units, crate inspection, safe migration, recovery, and daily reconciliation. '
                'Use the archive as your source and aim for at least 1600 words.')
for depth in (20000,131072):
    rendered=tpl.render([{'role':'user','content':'Read this archive. AUTH_RECORD lines are authoritative.\n__ARCHIVE__\n'
        'Return only JSON with keys north, south, west and their authoritative codes.'}],enable_thinking=True,reasoning_effort='low')
    left,right=rendered.split('__ARCHIVE__')
    left=tok.encode(left,parse_special=True); right=tok.encode(right,parse_special=True)
    records=[tok.encode('\nAUTH_RECORD '+key+'='+val+'\n',parse_special=False) for key,val in gold.items()]
    remaining=depth-len(left)-len(right)-sum(map(len,records))
    lengths=[remaining//10,remaining*4//10,remaining*4//10]
    lengths.append(remaining-sum(lengths))
    archive=[]
    for i,size in enumerate(lengths):
        archive+=(fill*(size//len(fill)+1))[:size]
        if i<3: archive+=records[i]
    ids=left+archive+right
    V.require(len(ids)==depth,'Fixture size differs')
    cases.append({'name':'records_'+str(depth),'kind':'oracle','expected':gold,'ids':ids,'max_new':2048})
    perf_right=tok.encode(tpl.render([{'role':'user','content':'Read this archive. AUTH_RECORD lines are authoritative.\n__ARCHIVE__\n'+bench_question}],
                                  enable_thinking=True,reasoning_effort='low').split('__ARCHIVE__')[1],parse_special=True)
    for repeat in (1,2):
        cases.append({'name':'decode_'+str(depth)+'_'+str(repeat),'kind':'bounded_throughput','ids':left+archive+perf_right,'max_new':1024})
for case in cases:
    V.write_json(OUT/(case['name']+'.ids.json'),case['ids'])
profile=Path(base_args[base_args.index('--expert-profile')+1])
plan={'protocol':'spec4 A1 / spec5 B / spec4 A2; same 0.1.36 executable',
      'thinking':True,'reasoning_effort':'low','sampling':{'temperature':0},
      'exe':cfg['exe'],'exe_sha256':V.sha(cfg['exe']),'config_sha256':V.sha(CFG),
      'expert_profile_sha256':V.sha(profile),'base_args':base_args,'deadline_seconds':1800,
      'cases':[{k:v for k,v in c.items() if k!='ids'}|{'prompt_tokens':len(c['ids']),'ids_sha256':V.sha(OUT/(c['name']+'.ids.json'))} for c in cases],
      'env_overrides':{'STRATA_IQ_MT_MIN':'1','STRATA_PARALLEL_INTERMEDIATE_QUANT':'0','STRATA_TRACE':'1','STRATA_DECODE_TIMING':'1','STRATA_WATCHDOG_S':'240'},
      'daily_changed':False,'artificial_load':False,
      'limits':'Limited oracle suite and two bounded samples per depth. Trace enabled identically. Not general model quality, elastic-daily SOTA, numerical logits parity, or 250k validation.'}
V.write_json(OUT/'plan.json',plan)
result={'plan':plan,'status':'running','arms':{}}
timer=threading.Timer(1800,lambda:os._exit(124)); timer.daemon=True; timer.start()
def save(): V.write_json(OUT/'results.json',result)
try:
    for label,spec in [('A1',4),('B',5),('A2',4)]:
        V.require(V.sha(profile)==plan['expert_profile_sha256'],'Expert profile changed')
        V.require(psutil.virtual_memory().available>16*2**30,'Insufficient RAM before loading')
        folder=OUT/label; folder.mkdir(); (folder/'cuda-cache').mkdir()
        args=V.set_arg(V.set_arg(base_args,'--spec',spec),'--mtp-max-t',spec)
        env=dict(os.environ); env.pop('STRATA_API_KEY',None); env.update(cfg.get('env',{}))
        env.pop('STRATA_DUMP_FIRST_LOGITS',None)
        env.update(plan['env_overrides']); env['CUDA_CACHE_PATH']=str(folder/'cuda-cache')
        env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
        engine=StrataEngine(cfg['exe'],args,cwd=str(folder),log=str(folder/'engine.log'),env=env,lazy=True)
        arm={'spec':spec,'records':[]}; result['arms'][label]=arm
        print('START',label,'spec',spec,flush=True)
        try:
            engine.restart(); arm['engine_info']=dict(engine.info)
            V.require(engine.info.get('spec')==spec and engine.info.get('mtp_max')==spec,'Incorrect actual speculation limit')
            V.require(engine.info.get('expert_slots')==6167,'Cache size changed')
            V.require(engine.info.get('context')==262144 and engine.info.get('kv_resident')==32768,'KV changed')
            V.require(engine.info.get('vram_free_mib',0)>=768,'Insufficient VRAM margin')
            print('READY',label,json.dumps(arm['engine_info']),flush=True); save()
            for case in cases:
                V.require(psutil.virtual_memory().available>8*2**30,'RAM fell below floor')
                logpath=folder/'engine.log'; offset=logpath.stat().st_size
                wall=time.monotonic()
                generated=[x for x in engine.generate(case['ids'],case['max_new'],{'temperature':0},threading.Event()) if x is not None]
                elapsed=time.monotonic()-wall
                body=tok.decode(generated)
                for stop in ('<|im_end|>','<|endoftext|>'): body=body.removesuffix(stop)
                parser=OutputParser(thinking=True); events=parser.feed(body)+parser.finish()
                content=''.join(x.text for x in events if x.kind=='content')
                reasoning=''.join(x.text for x in events if x.kind=='reasoning')
                with logpath.open('rb') as stream:
                    stream.seek(offset); log=stream.read().decode('utf-8',errors='replace')
                windows=collections.Counter(int(x) for x in re.findall(r'strata trace: window -?\d+ (\d+)',log))
                item={'name':case['name'],'kind':case['kind'],'content':content,'reasoning':reasoning,
                      'expected':case.get('expected'),'wall_s':elapsed,'window_T_histogram':dict(sorted(windows.items())),
                      **engine.last,'available_ram_gib':psutil.virtual_memory().available/2**30}
                item['decode_tps']=1000*item['generated']/item['decode_ms'] if item['decode_ms'] else 0
                item['acceptance_pct']=100*item.get('drafts_accepted',0)/item['drafts_offered'] if item.get('drafts_offered') else None
                if case['kind']=='oracle': item['pass']=V.evaluate_answer(content,item['finish'],case['expected'])
                else: item['sample_complete']=item['generated']==1024 and item['finish']=='length'
                arm['records'].append(item); save()
                print('CASE',label,case['name'],'PASS' if item.get('pass',item.get('sample_complete')) else 'FAIL',
                      'gen',item['generated'],'decode',round(item['decode_tps'],3),'drafts',str(item.get('drafts_accepted'))+'/'+str(item.get('drafts_offered')),
                      'windows',dict(windows),'finish',item['finish'],flush=True)
        finally: engine.close()
        print('STOPPED',label,flush=True)
    V.require(V.sha(CFG)==plan['config_sha256'],'Daily config changed')
    result['status']='completed'
    result['oracle_pass']=all(r['pass'] for a in result['arms'].values() for r in a['records'] if r['kind']=='oracle')
    result['throughput_samples_complete']=all(r['sample_complete'] for a in result['arms'].values() for r in a['records'] if r['kind']=='bounded_throughput')
    save(); print('GENERAL_COMPLETE','oracle_pass',result['oracle_pass'],'bounded_samples_complete',result['throughput_samples_complete'],flush=True)
except BaseException as error:
    result.update(status='failed',error=str(error)); save(); raise
finally: timer.cancel()
