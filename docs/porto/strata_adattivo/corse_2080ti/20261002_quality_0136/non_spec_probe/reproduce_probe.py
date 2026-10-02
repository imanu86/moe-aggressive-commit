"""Targeted follow-up of a failed oracle; original A/B/A verdict is preserved."""
from pathlib import Path
import hashlib
import json
import os
import sys
import threading

ROOT = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
sys.path[:0] = [str(ROOT),str(ROOT/'tools'),str(ROOT/'tools/sm75')]
import psutil
import validate_model as V
from serve.server import StrataEngine
from serve.frontend import ChatTemplate, OutputParser
from tools.strata_tokenizer import Tokenizer

SOURCE = Path(r'D:\ds4_work\strata\validazioni\20261002_quality_0136_aba_final')
OUT = SOURCE.parent/'20261002_quality_0136_non_spec_probe'
original = json.loads((SOURCE/'results.json').read_text(encoding='utf-8'))
V.require(original['status']=='completed','Wait for the A/B/A run to finish')
V.require(not any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe')
                 for p in psutil.process_iter(['name'])),'Another engine is active')
cfg_path = Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json')
cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
args = list(original['plan']['args'])
args = V.set_arg(args,'--spec',2)
args = V.set_arg(args,'--mtp-max-t',1)
cfg['args']=args
tp = Path(cfg['tokenizer'])
vocab = json.loads((tp/'vocab.json').read_text(encoding='utf-8'))
tokens = [None]*len(vocab)
for token,index in vocab.items(): tokens[index]=token
tok = Tokenizer(tokens,(tp/'merges.txt').read_text(encoding='utf-8').split('\n'),
                json.loads((tp/'token_type.json').read_text(encoding='utf-8')))
tpl = ChatTemplate(tp/'chat_template.jinja')
name,question,expected = next(x for x in V.ANSWERS if x[0]=='weighted_sum')
V.require(not OUT.exists(),'Existing probe output')
OUT.mkdir()
report = {'purpose':'Follow up the original arithmetic failure without changing that verdict',
          'exe_sha256':V.sha(cfg['exe']),'config_sha256':V.sha(cfg_path),
          'args':args,'env_overrides':{'STRATA_IQ_MT_MIN':'1','STRATA_PARALLEL_INTERMEDIATE_QUANT':'0'},
          'question':question,'expected':expected,'modes':['no_reasoning','reasoning'],
          'records':[],'status':'running','original_gate_modified':False}
V.write_json(OUT/'plan.json',report)
env = dict(os.environ); env.pop('STRATA_API_KEY',None)
env.update(cfg.get('env',{}))
env.update(STRATA_IQ_MT_MIN='1',STRATA_PARALLEL_INTERMEDIATE_QUANT='0',STRATA_WATCHDOG_S='240')
env.pop('STRATA_DUMP_FIRST_LOGITS',None)
env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
engine = StrataEngine(cfg['exe'],args,cwd=str(OUT),log=str(OUT/'engine.log'),env=env,lazy=True)
timer = threading.Timer(600,lambda:os._exit(124)); timer.daemon=True; timer.start()
try:
    V.require(psutil.virtual_memory().available>16*2**30,'Insufficient RAM')
    engine.restart()
    report['engine_info']=dict(engine.info)
    V.require(engine.info.get('vram_free_mib',0)>=768,'Insufficient VRAM margin')
    for thinking in (False,True):
        template_options = {'enable_thinking':thinking}
        if thinking:
            template_options['reasoning_effort']='low'
        prompt = tpl.render([{'role':'user','content':question}],**template_options)
        ids = tok.encode(prompt,parse_special=True)
        generated = [x for x in engine.generate(ids,2048 if thinking else 256,{'temperature':0},threading.Event()) if x is not None]
        body = tok.decode(generated)
        for stop in ('<|im_end|>','<|endoftext|>'): body=body.removesuffix(stop)
        parser = OutputParser(thinking=thinking)
        events = parser.feed(body)+parser.finish()
        content = ''.join(x.text for x in events if x.kind=='content')
        reasoning = ''.join(x.text for x in events if x.kind=='reasoning')
        record = {'thinking':thinking,'content':content,'reasoning':reasoning,**engine.last,
                  'pass':V.evaluate_answer(content,engine.last['finish'],expected)}
        report['records'].append(record)
        V.write_json(OUT/'results.json',report)
        print('PROBE',thinking,'PASS' if record['pass'] else 'FAIL',engine.last['finish'],repr(content),flush=True)
    report['status']='completed'
finally:
    engine.close(); timer.cancel()
    V.write_json(OUT/'results.json',report)
print('Probe complete; original failed oracle remains recorded.',flush=True)
