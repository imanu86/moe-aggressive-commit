from pathlib import Path
import datetime, hashlib, json, statistics
R=Path(__file__).resolve().parent/'retest_pr512_20261003'
report=json.loads((R/'comparison.json').read_text())
assert report['status']=='completed'
resources=[json.loads(x) for x in (R/'resources.jsonl').read_text().splitlines()]
for r in resources:
    r['epoch']=datetime.datetime.fromisoformat(r['utc']).timestamp()
    if 'gpu' in r: r['gpu_values']=[float(x.strip()) for x in r['gpu'].split(',')]
    r['other_cpu_percent']=sum(p['cpu_one_core_percent'] for p in r['processes'] if p['pid']!=0 and p['name'].lower()!='strata.exe')/len(r['cpu_per_core'])
summary={'status':'completed','exe_sha256':report['exe_sha256'],'base':report['upstream'],'arms':{},
         'limits':['single completed A/B/A','modified RTX 2080 Ti 22 GB; not stock 11 GB',
                   '0.1.37 plus published PR512 delta, not full 0.1.38',
                   'fixed requested4000/effective5357 cache isolates dispatch; not elastic Daily',
                   'no full-model numerical quality oracle in this timed corpus',
                   'resource monitor cannot reconstruct causes of previous runs']}
def stats(values):
    return {'min':min(values),'median':statistics.median(values),'max':max(values)} if values else None
for label, arm in report['arms'].items():
    result=arm['result']; assert arm['exit']==0 and result['status']=='completed'
    cache=result['initial_cache']; assert cache['expert_slots']==5357
    files=list((R/label/'banco').glob('*/results.jsonl')); assert len(files)==1
    rows=[json.loads(x) for x in files[0].read_text().splitlines()]
    rows=[x for x in rows if not x.get('riscaldamento')]; assert len(rows)==2
    fresh=rows[0]; follow=rows[1]
    assert fresh['usage']['prompt_tokens']==131248 and follow['usage']['prompt_tokens']==131239
    assert all(x['motore']['output_tokens']==1024 and x['fine']=='length' for x in rows)
    # serve/server.py stores history.time = started, not the end of generation.
    begin=fresh['motore']['time']
    pf_end=begin+fresh['motore']['prompt_ms']/1000
    samples=[x for x in resources if x['phase']==label and begin<=x['epoch']<=pf_end]
    assert len(samples)>=10, 'Prefill resource window did not match the request'
    summary['arms'][label]={'dispatch':arm['mode'],'prefill_tps':fresh['prefill_tps_motore'],
        'ttft_s':fresh['ttft_s'],'decode_tps':result['summary']['decode_aggregato_tps'],
        'initial_cache':cache,'fresh_prompt_tokens':131248,'reused_prompt_tokens':131072,
        'prefill_resource_samples':len(samples),'prefill_start_utc':datetime.datetime.fromtimestamp(begin,datetime.timezone.utc).isoformat(),
        'prefill_end_utc':datetime.datetime.fromtimestamp(pf_end,datetime.timezone.utc).isoformat(),
        'ram_available_gib':stats([x['ram_available_gib'] for x in samples]),
        'cpu_percent':stats([x['cpu_percent'] for x in samples]),
        'other_cpu_percent_including_test_drivers':stats([x['other_cpu_percent'] for x in samples]),
        'gpu_util_percent':stats([x['gpu_values'][0] for x in samples if 'gpu_values' in x]),
        'gpu_free_mib':stats([x['gpu_values'][3] for x in samples if 'gpu_values' in x]),
        'gpu_temp_c':stats([x['gpu_values'][4] for x in samples if 'gpu_values' in x]),
        'gpu_sm_mhz':stats([x['gpu_values'][5] for x in samples if 'gpu_values' in x]),
        'gpu_mem_mhz':stats([x['gpu_values'][6] for x in samples if 'gpu_values' in x])}
    rates=[]
    for old,new in zip(resources,resources[1:]):
        if old['phase']==label and new['phase']==label and begin<=old['epoch']<new['epoch']<=pf_end:
            rates.append((new['disk']['read_bytes']-old['disk']['read_bytes'])/(new['epoch']-old['epoch'])/2**20)
    summary['arms'][label]['aggregate_disk_read_mib_s']=stats(rates)
a1=summary['arms']['A1']; a2=summary['arms']['A2']; b=summary['arms']['B']
mean=(a1['prefill_tps']+a2['prefill_tps'])/2
summary.update(reference_mean_prefill_tps=mean,reference_spread_percent=100*abs(a1['prefill_tps']-a2['prefill_tps'])/mean,
    active_gain_percent=100*(b['prefill_tps']/mean-1),ttft_saved_s=(a1['ttft_s']+a2['ttft_s'])/2-b['ttft_s'])
summary['stable_reference']=summary['reference_spread_percent']<=3
summary['positive_prefill']=summary['stable_reference'] and summary['active_gain_percent']>=3
summary['parity_pass']= 'PASS: 16' in (R/'parity.log').read_text()
(R/'analysis.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
