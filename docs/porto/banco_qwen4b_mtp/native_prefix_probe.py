"""Explicitly opt-in private-server inference probe. NOT executed by extraction child.
Capture native token IDs, compare on CPU, then one-token cold teacher-forced probes.
This API does not expose logits of internal speculative verification/rollback.
"""
import argparse,json,os,pathlib,urllib.parse,urllib.request

SYSTEM='Rispondi in italiano.'
USER='Spiega in 200 parole come confrontare due motori di inferenza: latenza, throughput, cache, correttezza e misure ripetute. Non usare strumenti.'

def call(args,path,body):
 if not args.allow_inference:raise ValueError('Requires --allow-inference; parent owns GPU scheduling')
 u=urllib.parse.urlparse(args.url)
 if u.hostname not in ('localhost','127.0.0.1') or u.port in (None,8100,8104):raise ValueError('Only explicit private loopback lab ports; refuse daily ports8100/8104')
 headers={'Content-Type':'application/json'}
 key=os.environ.get('QWEN_BENCH_API_KEY','')
 if key:headers['Authorization']='Bearer '+key
 req=urllib.request.Request(args.url.rstrip('/')+path,data=json.dumps(body).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)

def save(path,data):
 with pathlib.Path(path).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','compare','prefix'])
 p.add_argument('--url',default='http://127.0.0.1:8114');p.add_argument('--allow-inference',action='store_true')
 p.add_argument('--reference');p.add_argument('--variant');p.add_argument('--out',required=True);p.add_argument('--position',type=int)
 a=p.parse_args()
 if a.mode=='capture':
  chat={'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':USER}],
        'chat_template_kwargs':{'enable_thinking':False}}
  formatted=call(a,'/apply-template',chat)['prompt']
  if isinstance(formatted,str):prompt=call(a,'/tokenize',{'content':formatted,'add_special':True,'parse_special':True})['tokens']
  else:prompt=formatted
  request={'prompt':prompt,'n_predict':512,'stream':False,'return_tokens':True,
           'temperature':0,'top_p':0.95,'top_k':20,'min_p':0,'seed':42,
           'repeat_penalty':1.0,'cache_prompt':False}
  reply=call(a,'/completion',request)
  if not reply.get('tokens'):raise ValueError('Native token IDs missing')
  save(a.out,{'mode':'capture','chat':chat,'formatted_prompt':formatted,'prompt_tokens':prompt,
              'generation_tokens':reply['tokens'],'request':request,'response':reply})
 elif a.mode=='compare':
  b=json.loads(pathlib.Path(a.reference).read_text(encoding='utf-8'))
  v=json.loads(pathlib.Path(a.variant).read_text(encoding='utf-8'))
  if b['prompt_tokens']!=v['prompt_tokens']:raise ValueError('Prompt token mismatch')
  x,y=b['generation_tokens'],v['generation_tokens']
  j=next((i for i,(c,d) in enumerate(zip(x,y)) if c!=d),min(len(x),len(y)))
  result={'equal':x==y,'first_different_generation_token_zero_based':j,
          'baseline_token':x[j] if j<len(x) else None,'variant_token':y[j] if j<len(y) else None,
          'baseline_count':len(x),'variant_count':len(y)}
  save(a.out,result);print(json.dumps(result))
 else:
  ref=json.loads(pathlib.Path(a.reference).read_text(encoding='utf-8'))
  j=a.position
  if j is None or not 0<=j<len(ref['generation_tokens']):raise ValueError('Valid --position required')
  prompt=ref['prompt_tokens']+ref['generation_tokens'][:j]
  # n_predict1 forces get_n_draft_max<=0: meaningful ordinary-target probabilities,
  # not TODO/placeholder probabilities from speculative multi-token output.
  request={'prompt':prompt,'n_predict':1,'stream':False,'return_tokens':True,'temperature':-1,
           'samplers':['temperature'],'n_probs':10,'post_sampling_probs':False,'seed':42,
           'cache_prompt':False,'repeat_penalty':1.0,'id_slot':0}
  reply=call(a,'/completion',request)
  if reply.get('timings',{}).get('draft_n',0):raise ValueError('Unexpected speculation in one-token probe')
  save(a.out,{'mode':'prefix','position':j,'prompt_token_count':len(prompt),'reference_token':ref['generation_tokens'][j],
              'request':request,'response':reply,
              'limitation':'Cold prefill; does NOT inspect internal batched verification or dirty rollback state'})
if __name__=='__main__':main()
