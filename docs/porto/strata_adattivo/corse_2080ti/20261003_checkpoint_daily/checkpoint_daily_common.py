"""Read-only Daily engine helpers. All outputs stay in the task workspace."""
from pathlib import Path
import os,sys,json,threading,hashlib,re
BASE=Path(__file__).resolve().parent
DAILY=Path(r'D:\ds4_work\strata\Strata')
SOURCE=DAILY/'build-0136-daily/source'
sys.path[:0]=[str(SOURCE),r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np, psutil, validate_model as V
from serve.server import StrataEngine
from serve.frontend import ChatTemplate,OutputParser
from tools.strata_tokenizer import Tokenizer
CFG=json.loads((DAILY/'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
TP=Path(CFG['tokenizer']); VOCAB=json.loads((TP/'vocab.json').read_text(encoding='utf-8')); TOKENS=[None]*len(VOCAB)
for text,index in VOCAB.items(): TOKENS[index]=text
TOK=Tokenizer(TOKENS,(TP/'merges.txt').read_text(encoding='utf-8').split('\n'),json.loads((TP/'token_type.json').read_text(encoding='utf-8')))
TPL=ChatTemplate(TP/'chat_template.jinja')
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(path,value): Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
def ensure_free():
    engines=[p.info for p in psutil.process_iter(['pid','name']) if ('strata' in (p.info['name'] or '').lower() and (p.info['name'] or '').lower().endswith('.exe')) or (p.info['name'] or '').lower()=='llama-server.exe']
    assert not engines,engines
    assert psutil.virtual_memory().available>8*2**30
def env(folder,readout=False):
    e={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
    e.update(CFG.get('env',{}))
    e.update(PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(folder.parent/'cuda-cache'))
    if readout:e['STRATA_DUMP_FIRST_LOGITS']=str(folder/'first')
    e['PATH']=os.pathsep.join(CFG.get('lib_dirs',[])+[e.get('PATH','')])
    return e
def engine(folder,args=None,readout=False):
    assert sha(CFG['exe'])=='c35505ca79b790bd37ed7073fcadd399dd30d1b88e85bb99a6eb24a52d945d0a'
    return StrataEngine(CFG['exe'],list(CFG['args']) if args is None else args,cwd=str(folder),log=str(folder/'engine.log'),env=env(folder,readout),lazy=True)
def ids(text,thinking=False): return TOK.encode(TPL.render([{'role':'user','content':text}],enable_thinking=thinking),parse_special=True)
WARM=ids('Return only JSON with key ready and value true.')
def decode(generated):
    text=TOK.decode(generated)
    for special in ('<|im_end|>','<|endoftext|>'):text=text.removesuffix(special)
    p=OutputParser(thinking=False)
    return ''.join(x.text for x in p.feed(text)+p.finish() if x.kind=='content')
def oracle(text,finish,expected):
    try:
        text=text.strip()
        if text.startswith('```json\n') and text.endswith('\n```'):text=text[8:-4].strip()
        return finish=='stop' and json.loads(text)==expected
    except ValueError:return False
def first_row(folder,prompt_tokens):
    path=folder/f'first.pos{prompt_tokens-1}.f32'
    row=np.fromfile(path,dtype='<f4');assert row.size==len(TOKENS) and np.isfinite(row).all()
    return row
def clear_dump(folder):
    for path in folder.glob('first.pos*.f32'):path.unlink()
def chunk_events(log):
    text=Path(log).read_text(encoding='utf-8',errors='replace')
    return [line for line in text.splitlines() if ('prompt chunk' in line or ('elastic:' in line and ('slots' in line or 'VMM' in line)) or 'prefill auto' in line or 'prompt path borrows' in line)]
