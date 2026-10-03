from checkpoint_daily_common import *
import math,statistics,time
RUN=BASE/'checkpoint_daily_20261003/paired-r2'
for attempt in range(4):
    try:r=json.loads((RUN/'results.json').read_text(encoding='utf-8'));break
    except json.JSONDecodeError:
        if attempt==3:raise
        time.sleep(.1)
complete=r['status']=='completed';arms={k:a for k,a in r['arms'].items() if a.get('completed')}
def stats(xs):return {'count':len(xs),'median':statistics.median(xs),'min':min(xs),'max':max(xs),'all':xs} if xs else None
def score(a,b,targets):
    assert a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all()
    kl=[];same=[];na=[];nb=[]
    for pos in range(len(a)):
        pa,pb=V.logsoftmax(a[pos]),V.logsoftmax(b[pos]);target=targets[pos]
        na.append(-float(pa[target]));nb.append(-float(pb[target]))
        kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())));same.append(a[pos].argmax()==b[pos].argmax())
    return {'positions':len(a),'top1_agreement_pct':100*float(np.mean(same)),'kl_mean':float(np.mean(kl)),'kl_median':float(np.median(kl)),'kl_p99':float(np.percentile(kl,99)),'kl_max':float(np.max(kl)),'ppl_reference':math.exp(float(np.mean(na))),'ppl_candidate':math.exp(float(np.mean(nb))),'nll_delta_mean':float(np.mean(np.asarray(nb)-na)),'nll_deltas':[b-a for a,b in zip(na,nb)],'kl_values':kl,'same_top1':[bool(x) for x in same]}
def first_compare(a,b):
    aa=np.fromfile(a,dtype='<f4');bb=np.fromfile(b,dtype='<f4');assert aa.shape==bb.shape and aa.size==len(TOKENS)
    pa,pb=V.logsoftmax(aa),V.logsoftmax(bb)
    return {'bitwise':bool(np.array_equal(aa,bb)),'kl':max(0.,float((np.exp(pa)*(pa-pb)).sum())),'same_top1':bool(aa.argmax()==bb.argmax()),'max_logit_abs_delta':float(np.max(np.abs(aa-bb)))}
report={'status':r['status'],'completed_arms':len(arms),'instrumented_timing':True,'depths':{},'overall_pass':None,'limits':['one modified2080Ti22GB, IQ3_XXS, one retrieval fixture per context','three pairs, instrumented first-logit output, no uninstrumented SOTA claim','elastic/autocache change naturally; startup and resize events recorded','long decode output may reach1024-token budget; no answer correctness oracle for guide']}
for depth in r['plan']['contexts']:
    data={'performance':{},'quality':{},'geometry':{},'oracle_pass':True}
    paired=[i for i in range(1,4) if f'{depth}_A{i}' in arms and f'{depth}_B{i}' in arms]
    for mode in ('A','B'):
        selected=[a for a in arms.values() if a['depth']==depth and a['mode']==mode]
        data['oracle_pass'] &= all(x['oracle_pass'] for a in selected for x in a['requests'] if 'oracle_pass' in x)
        data['geometry'][mode]={'startup_expert_slots':[a['info']['expert_slots'] for a in selected],'events':{f'pair{a["pair"]}':a['chunk_events'] for a in selected},'startup_runtime_spec':[a['info']['spec'] for a in selected],'startup_mtp_max':[a['info']['mtp_max'] for a in selected],'startup_lookup':[a['info']['lookup'] for a in selected]}
        perf={}
        for name in ('fresh','branch','conversation','long_decode'):
            rows=[x for a in selected for x in a['requests'] if x['name']==name]
            perf[name]={'ttft_s':stats([x['ttft_s'] for x in rows]),'read_s':stats([x['prompt_ms']/1000 for x in rows]),'reused':stats([x['reused'] for x in rows]),'actual_prompt_tokens':stats([x['actual_input_tokens'] for x in rows]),'generated':stats([x['generated'] for x in rows]),'prefill_tps_read_only':stats([1000*x['prompt_read']/x['prompt_ms'] for x in rows if x['prompt_ms']>0])}
            if name=='long_decode':perf[name].update(decode_tps=stats([x['decode_tps'] for x in rows]),complete_answers=[x['complete_answer'] for x in rows])
        data['performance'][mode]=perf
    data['paired_performance']={}
    for name in ('fresh','branch','conversation','long_decode'):
        rows=[]
        for pair in paired:
            aa=next(x for x in arms[f'{depth}_A{pair}']['requests'] if x['name']==name);bb=next(x for x in arms[f'{depth}_B{pair}']['requests'] if x['name']==name)
            row={'pair':pair,'same_prompt':aa['prompt_sha256']==bb['prompt_sha256'],'ttft_savings_s':aa['ttft_s']-bb['ttft_s'],'ttft_reduction_pct':100*(1-bb['ttft_s']/aa['ttft_s']),'reused_delta':bb['reused']-aa['reused']}
            if name=='long_decode':row['decode_change_pct']=100*(bb['decode_tps']/aa['decode_tps']-1)
            rows.append(row)
        data['paired_performance'][name]=rows
    for corpus in r['plan']['teacher_corpora']:
        tail=json.loads((RUN/f'teacher-{corpus}.ids.json').read_text(encoding='utf-8'))[:64]
        arrays={name:np.fromfile(RUN/name/f'teacher-{corpus}.bin',dtype='<f4').reshape(64,-1) for name in arms if name.startswith(str(depth)+'_')}
        if not paired:continue
        a=np.concatenate([arrays[f'{depth}_A{i}'] for i in paired]);b=np.concatenate([arrays[f'{depth}_B{i}'] for i in paired]);candidate=score(a,b,tail*len(paired))
        q={'candidate':V.public_stats(candidate),'bitwise_candidate':bool(np.array_equal(a,b)),'paired_count':len(paired),'gate':None}
        refs=[i for i in (2,3) if f'{depth}_A1' in arrays and f'{depth}_A{i}' in arrays]
        if refs:
            ra=np.concatenate([arrays[f'{depth}_A1'] for i in refs]);rb=np.concatenate([arrays[f'{depth}_A{i}'] for i in refs]);repeat=score(ra,rb,tail*len(refs))
            q.update(reference_repeat=V.public_stats(repeat),bitwise_reference_repeat=bool(np.array_equal(ra,rb)),gate=V.regression_gate(candidate,repeat))
        data['quality'][corpus]=q
    data['first_logits']={}
    for name in ('fresh','branch','conversation'):
        candidates=[];repeats=[]
        for pair in paired:
            aa=next(x for x in arms[f'{depth}_A{pair}']['requests'] if x['name']==name);bb=next(x for x in arms[f'{depth}_B{pair}']['requests'] if x['name']==name)
            if aa['prompt_sha256']==bb['prompt_sha256']:candidates.append({'pair':pair,**first_compare(RUN/f'{depth}_A{pair}'/(name+'-first.f32'),RUN/f'{depth}_B{pair}'/(name+'-first.f32'))})
        for i in (2,3):
            if f'{depth}_A1' in arms and f'{depth}_A{i}' in arms:
                aa=next(x for x in arms[f'{depth}_A1']['requests'] if x['name']==name);bb=next(x for x in arms[f'{depth}_A{i}']['requests'] if x['name']==name)
                if aa['prompt_sha256']==bb['prompt_sha256']:repeats.append({'repeat':i,**first_compare(RUN/f'{depth}_A1'/(name+'-first.f32'),RUN/f'{depth}_A{i}'/(name+'-first.f32'))})
        limit=max(.01,3*max([x['kl'] for x in repeats],default=0))
        data['first_logits'][name]={'candidate':candidates,'reference_repeat':repeats,'kl_limit':limit,'pass':len(candidates)==3 and all(x['same_top1'] and x['kl']<=limit for x in candidates)}
    if len(paired)==3:
        data['numerical_pass']=all(x['gate'] and x['gate']['pass'] for x in data['quality'].values()) and all(data['first_logits'][name]['pass'] for name in ('fresh','branch'))
    else:data['numerical_pass']=None
    report['depths'][str(depth)]=data
if complete:
    assert len(arms)==12
    report['overall_pass']=all(x['oracle_pass'] and x['numerical_pass'] for x in report['depths'].values())
write(RUN/('comparison.json' if complete else 'comparison-partial.json'),report)
print(json.dumps({'status':report['status'],'completed_arms':len(arms),'overall_pass':report['overall_pass'],'depths':{d:{'numerical_pass':x['numerical_pass'],'oracle_pass':x['oracle_pass'],'paired_count':len(x['paired_performance']['fresh'])} for d,x in report['depths'].items()}},indent=2))
