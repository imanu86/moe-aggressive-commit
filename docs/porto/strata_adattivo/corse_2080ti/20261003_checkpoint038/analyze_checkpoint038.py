from pathlib import Path
import json,math,statistics,sys
sys.path[:0]=[r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np
import validate_model as V
R=Path(__file__).resolve().parent/'checkpoint038_20261003/model-tests-r3'
Q=R.parent/'quality-tests-r3'
r=json.loads((R/'results.json').read_text(encoding='utf-8')); assert r['status']=='completed'
qa=json.loads((Q/'results.json').read_text(encoding='utf-8')); partial='--partial' in sys.argv
assert partial or qa['status']=='completed'
tail=json.loads((R/'teacher_tail.ids.json').read_text()); arms=r['arms']
report={'quality':{},'performance':{},'limitations':['single modified RTX2080Ti22GB','IQ3_XXS; one recall workload and fixed teacher corpus',
         'timing output is a complete short recall answer; no long-output decode speed claim','fixed cache; adaptation disabled; no artificial pressure']}
def stats(xs):return {'median':statistics.median(xs),'min':min(xs),'max':max(xs),'all':xs}
for chunk in r['plan']['chunks']:
    perf={}
    for mode in ('A','B'):
        rows=[arms[f'chunk{chunk}_{mode}{i}']['requests'] for i in range(1,4)]
        assert all(a['oracle_pass'] for row in rows for a in row)
        perf[mode]={'fresh_ttft_s':stats([row[0]['ttft_s'] for row in rows]),
                    'follow_ttft_s':stats([row[1]['ttft_s'] for row in rows]),
                    'fresh_reused':stats([row[0]['reused'] for row in rows]),
                    'follow_reused':stats([row[1]['reused'] for row in rows]),
                    'follow_read':stats([row[1]['prompt_tokens']-row[1]['reused'] for row in rows])}
    perf['follow_ttft_reduction_percent']=100*(1-perf['B']['follow_ttft_s']['median']/perf['A']['follow_ttft_s']['median'])
    perf['paired_follow_savings_s']=[arms[f'chunk{chunk}_A{i}']['requests'][1]['ttft_s']-arms[f'chunk{chunk}_B{i}']['requests'][1]['ttft_s'] for i in range(1,4)]
    report['performance'][str(chunk)]=perf
    arrays=[np.fromfile(Q/f'chunk{chunk}_{label}'/'teacher.bin',dtype='<f4').reshape(64,-1) for label in ('A1','B1','A2')]
    assert all(np.isfinite(x).all() for x in arrays)
    def score(other):
        kl=[];same=[];na=[];nb=[]
        for pos in range(64):
            pa,pb=V.logsoftmax(arrays[0][pos]),V.logsoftmax(other[pos]);target=tail[pos]
            na.append(-float(pa[target]));nb.append(-float(pb[target]))
            kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())));same.append(arrays[0][pos].argmax()==other[pos].argmax())
        return {'positions':64,'top1_agreement_pct':100*float(np.mean(same)),'kl_mean':float(np.mean(kl)),
                'kl_median':float(np.median(kl)),'kl_p99':float(np.percentile(kl,99)), 'kl_max':float(np.max(kl)),
                'ppl_reference':math.exp(float(np.mean(na))),'ppl_candidate':math.exp(float(np.mean(nb))),
                'nll_delta_mean':float(np.mean(np.asarray(nb)-na)),'nll_deltas':[b-a for a,b in zip(na,nb)],'kl_values':kl,'same_top1':[bool(x) for x in same]}
    candidate,repeat=score(arrays[1]),score(arrays[2])
    report['quality'][str(chunk)]={'candidate':V.public_stats(candidate),'reference_repeat':V.public_stats(repeat),
        'bitwise_candidate':bool(np.array_equal(arrays[0],arrays[1])),'bitwise_repeat':bool(np.array_equal(arrays[0],arrays[2])),
        'gate':V.regression_gate(candidate,repeat)}
    for prompt_name in ('fresh','follow'):
        rows=[np.fromfile(Q/f'chunk{chunk}_{label}'/f'{prompt_name}-first.f32',dtype='<f4') for label in ('A1','B1','A2')]
        pa,pb,pc=[V.logsoftmax(row) for row in rows]
        report['quality'][str(chunk)][f'{prompt_name}_first']={'kl_candidate':max(0.,float((np.exp(pa)*(pa-pb)).sum())),
            'kl_reference_repeat':max(0.,float((np.exp(pa)*(pa-pc)).sum())),
            'same_top1_candidate':bool(rows[0].argmax()==rows[1].argmax()),'same_top1_repeat':bool(rows[0].argmax()==rows[2].argmax())}
    first_rows=[report['quality'][str(chunk)][f'{name}_first'] for name in ('fresh','follow')]
    report['quality'][str(chunk)]['first_row_gate']={'description':'Additional first-output check: KL <= max(0.01,3*repeat), same top1',
        'pass':all(x['kl_candidate']<=max(.01,3*x['kl_reference_repeat']) and x['same_top1_candidate'] for x in first_rows)}
report['oracle_pass']=all(a['oracle_pass'] for arm in arms.values() for a in arm['requests'])
report['qa_oracle_pass']=all(a['oracle_pass'] for arm in qa['arms'].values() for a in arm['requests'])
if all((Q/f'cache0_{mode}'/'first.f32').exists() for mode in ('A','B')):
    disabled=[np.fromfile(Q/f'cache0_{mode}'/'first.f32',dtype='<f4') for mode in ('A','B')]
    report['cache0_bitwise']=bool(np.array_equal(disabled[0],disabled[1]))
else:report['cache0_bitwise']=None
report['pass']=report['oracle_pass'] and report['qa_oracle_pass'] and report['cache0_bitwise'] and all(x['gate']['pass'] and x['first_row_gate']['pass'] for x in report['quality'].values())
(R/('comparison-pending-cache0.json' if partial else 'comparison.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
