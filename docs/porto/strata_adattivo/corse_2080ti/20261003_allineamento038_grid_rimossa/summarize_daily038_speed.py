from pathlib import Path
import json,sys,statistics,hashlib
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';sys.path.insert(0,r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages');import numpy as np
arms={n:json.loads((R/'speed-r1'/n/'results.json').read_text()) for n in ('A1','B','A2')}
assert all(a['status']=='completed' for a in arms.values())
for key in ('context','kv','kv_resident','expert_slots','spec','mtp_max','lookup','pcie_frac','conversation_cache_mib'):
    assert len({str(a['startup_info'][key]) for a in arms.values()})==1,key
assert all(a['plan']['args']==arms['A1']['plan']['args'] for a in arms.values())
bitwise={};outputs={};timing={}
for req in arms['A1']['requests']:
    name=req['name'];rows=[np.fromfile(R/'speed-r1'/n/f'{name}-first.f32',dtype='<f4') for n in ('A1','B','A2')]
    assert all(np.isfinite(x).all() for x in rows)
    bitwise[name]=bool(np.array_equal(rows[0],rows[1]) and np.array_equal(rows[0],rows[2]))
    requests=[next(x for x in arms[n]['requests'] if x['name']==name) for n in ('A1','B','A2')]
    outputs[name]=len({tuple(x['output_ids']) for x in requests})==1
    base=statistics.mean([requests[0]['ttft_s'],requests[2]['ttft_s']]);spread=abs(requests[0]['ttft_s']-requests[2]['ttft_s'])/base*100
    timing[name]={'A1_ttft_s':requests[0]['ttft_s'],'B_ttft_s':requests[1]['ttft_s'],'A2_ttft_s':requests[2]['ttft_s'],'baseline_mean_ttft_s':base,'candidate_ttft_change_pct':(requests[1]['ttft_s']/base-1)*100,'reference_spread_pct':spread,'arms':[{k:v for k,v in x.items() if k not in ('content','output_ids')} for x in requests]}
result={'completed':True,'oracle_pass':all(a['oracle_pass'] for a in arms.values()),'long_decode_pass':all(a['long_decode_pass'] for a in arms.values()),'first_logits_bitwise':all(bitwise.values()),'first_logits_by_request':bitwise,'all_output_ids_equal':all(outputs.values()),'outputs_by_request':outputs,'timing':timing,'arms':arms,'limits':'One controlled A/B/A on modified22GB SM75 at250k, same5357slot/8192chunk/spec4 settings and long disabled resize policy; actual Daily uses auto cache/chunk and adaptive MTP defaults. No physical bandwidth or general model quality claim.'}
(R/'speed-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('arms','timing')},indent=2));print(json.dumps({n:{k:v for k,v in x.items() if k!='arms'} for n,x in timing.items()},indent=2))
assert result['oracle_pass'] and result['long_decode_pass'] and result['first_logits_bitwise']
