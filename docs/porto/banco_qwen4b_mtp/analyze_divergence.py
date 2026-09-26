"""CPU-only comparison of completed clean campaign rows; no network/inference."""
import json,pathlib
root=pathlib.Path(r'D:\ds4_work\qwen4b_campaign')
out=pathlib.Path(r'D:\ds4_work\qwen4b_mtp_lab\divergence-analysis.json')
def rows(label):
 p=root/f'clean_{label}'/'bench'/'results.jsonl'
 return {(r['case'],r['repeat']):r for line in p.read_text(encoding='utf-8').splitlines() if (r:=json.loads(line))}
def diff(a,b):
 i=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
 return {'first_different_char_zero_based':i,'common_prefix_chars':i,'prefix_tail':a[max(0,i-120):i],
         'baseline_next':a[i:i+180],'variant_next':b[i:i+180], 'baseline_chars':len(a),'variant_chars':len(b)}
b=rows('original_b');report={}
for label in ('original_a','rebuild','mtp1','mtp2','mtp3'):
 rs=rows(label); checks=[]
 for key,r in rs.items():
  if key not in b:continue
  base=b[key];c={'case':key[0],'repeat':key[1],'same_request':base['request_sha256']==r['request_sha256'],
    'same_output':base['output_sha256']==r['output_sha256'],'baseline_predicted':base['timings']['predicted_n'],
    'variant_predicted':r['timings']['predicted_n'],'drafted':r['timings'].get('draft_n'),
    'accepted':r['timings'].get('draft_n_accepted')}
  if base['text']!=r['text']:c['text_difference']=diff(base['text'],r['text'])
  checks.append(c)
 report[label]=checks
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{'same':sum(x['same_output'] for x in v),'total':len(v),'first_difference':next((x for x in v if not x['same_output']),None)} for k,v in report.items()},ensure_ascii=False,indent=2))
