from checkpoint_daily_common import *
import math
RUN=BASE/'checkpoint_daily_20261003/full-qa'
r=json.loads((RUN/'results.json').read_text(encoding='utf-8'))
complete=r['status']=='completed'
report={'status':r['status'],'completed_arms':sum(bool(x.get('completed')) for x in r['arms'].values()),'scored_positions_per_arm':2557,'depths':{},'overall_pass':None,'prior_short_verdict_preserved':True}
def merge(objs):
    n=sum(x['positions'] for x in objs)
    result={'positions':n,'ppl_reference':math.exp(sum(x['positions']*math.log(x['ppl_reference']) for x in objs)/n),'ppl_candidate':math.exp(sum(x['positions']*math.log(x['ppl_candidate']) for x in objs)/n)}
    for key in ('nll_deltas','kl_values','same_top1'):result[key]=[v for obj in objs for v in obj[key]]
    result.update(top1_agreement_pct=100*float(np.mean(result['same_top1'])),kl_mean=float(np.mean(result['kl_values'])),kl_median=float(np.median(result['kl_values'])),kl_p99=float(np.percentile(result['kl_values'],99)),kl_max=float(max(result['kl_values'])),nll_delta_mean=float(np.mean(result['nll_deltas'])))
    return result
def first(a,b):
    aa,bb=[np.fromfile(p,dtype='<f4') for p in (a,b)];assert aa.shape==bb.shape and aa.size==len(TOKENS)
    pa,pb=V.logsoftmax(aa),V.logsoftmax(bb)
    return {'bitwise':bool(np.array_equal(aa,bb)),'kl':max(0.,float((np.exp(pa)*(pa-pb)).sum())),'same_top1':bool(aa.argmax()==bb.argmax())}
for depth in r['plan']['contexts']:
    names=[f'{depth}_{label}' for label in ('A1','B','A2')]
    if not all(name in r['arms'] and r['arms'][name].get('completed') for name in names):continue
    data={'corpora':{},'first_logits':{},'oracle_pass':all(x['oracle_pass'] for name in names for x in r['arms'][name]['requests'])}
    candidates=[];repeats=[]
    for corpus in r['plan']['texts']:
        ids=json.loads((RUN/f'{corpus}.ids.json').read_text(encoding='utf-8'))
        matrices=[V.check_dump(RUN/name/f'{corpus}.logits.bin',len(ids),len(TOKENS)) for name in names]
        candidate=V.paired_stats(matrices[0],matrices[1],ids);repeat=V.paired_stats(matrices[0],matrices[2],ids)
        candidates.append(candidate);repeats.append(repeat)
        data['corpora'][corpus]={'candidate':V.public_stats(candidate),'reference_repeat':V.public_stats(repeat),'gate':V.regression_gate(candidate,repeat),'bitwise_candidate':bool(np.array_equal(matrices[0],matrices[1])),'bitwise_reference_repeat':bool(np.array_equal(matrices[0],matrices[2]))}
        print('FULL SCORE',depth,corpus,'positions',candidate['positions'],'gate',data['corpora'][corpus]['gate']['pass'],flush=True)
    candidate=merge(candidates);repeat=merge(repeats)
    data['aggregate']={'candidate':V.public_stats(candidate),'reference_repeat':V.public_stats(repeat),'gate':V.regression_gate(candidate,repeat)}
    for prompt in ('fresh','branch'):
        candidate=first(RUN/names[0]/f'{prompt}-first.f32',RUN/names[1]/f'{prompt}-first.f32')
        repeat=first(RUN/names[0]/f'{prompt}-first.f32',RUN/names[2]/f'{prompt}-first.f32')
        limit=max(.01,3*repeat['kl'])
        data['first_logits'][prompt]={'candidate':candidate,'reference_repeat':repeat,'kl_limit':limit,'pass':candidate['same_top1'] and candidate['kl']<=limit}
    data['numerical_pass']=data['aggregate']['gate']['pass'] and all(x['gate']['pass'] for x in data['corpora'].values()) and all(x['pass'] for x in data['first_logits'].values())
    data['pass']=data['oracle_pass'] and data['numerical_pass'];report['depths'][str(depth)]=data
if complete:
    assert len(report['depths'])==2 and report['completed_arms']==6
    report['overall_pass']=all(x['pass'] for x in report['depths'].values())
write(RUN/('comparison.json' if complete else 'comparison-partial.json'),report)
print(json.dumps({'status':report['status'],'completed_arms':report['completed_arms'],'overall_pass':report['overall_pass'],'depths':{d:{'pass':x['pass'],'numerical_pass':x['numerical_pass'],'oracle_pass':x['oracle_pass'],'corpora':{n:y['gate']['pass'] for n,y in x['corpora'].items()}} for d,x in report['depths'].items()}},indent=2))
