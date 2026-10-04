"""Summarize actual recorded runs, including failures and imperfect answers."""
import json,re
from pathlib import Path
L=Path(__file__).resolve().parent
rows=[]
for p in sorted(L.glob('*/result.json')):
    r=json.loads(p.read_text());q=p.parent/'plan.json'
    if not q.exists():continue
    plan=json.loads(q.read_text());last=r.get('last',{})
    row=dict(run=p.parent.name,mode=plan['mode'],task=plan['task'],status=r['status'],
             prompt_tokens=plan['prompt_tokens'],tokens=last.get('generated'),
             tps=last.get('generated',0)*1000/last['decode_ms'] if last.get('decode_ms') else None,
             prompt_ms=last.get('prompt_ms'),ttft_s=r.get('ttft_s'),request_s=r.get('request_s'),
             acceptance=last.get('drafts_accepted',0)/last['drafts_offered'] if last.get('drafts_offered') else None,
             quality_pass=r.get('oracle',{}).get('passed'),
             process_cores_after_first=r.get('after_first_cpu_s',0)/r['after_first_s'] if r.get('after_first_s') else None,
             cleanup=not r['remaining_owned'],preserved=r['daily_unchanged'] and r['config_unchanged'])
    row['refills']=[s for s in r.get('native_metrics',[]) if s.startswith('CLOSED_REFILL')]
    row['done']=[s for s in r.get('native_metrics',[]) if s.startswith('CLOSED_DONE')]
    rows.append(row)
print(json.dumps(rows,indent=2))
(L/'summary.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
