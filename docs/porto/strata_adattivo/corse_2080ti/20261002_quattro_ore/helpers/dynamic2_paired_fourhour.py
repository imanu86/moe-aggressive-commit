"""Same-process OFF/ON pairs; actual elastic cache, greedy held-out throughput fixtures."""
from pathlib import Path
import datetime,json,os,statistics,sys,threading,time
sys.path.insert(0,r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages')
BASE=Path(__file__).resolve().parent;R=BASE/'fourhour_20261002';SOURCE=R/'dynamic2-source'
sys.path[:0]=[str(SOURCE),str(SOURCE/'tools/sm75')]
import psutil
import validate_model as V
from serve.server import StrataEngine
OUT=R/'dynamic2-paired';V.require(not OUT.exists(),'Existing output')
V.require(not any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name'])),'Engine active')
OUT.mkdir();(OUT/'cuda-cache').mkdir()
cfg=json.loads((R/'config-pcie028.json').read_text());exe=R/'build-dynamic2/strata.exe'
fixtures={str(d):json.loads((BASE/'20261002_spec45_general_aba'/('decode_'+str(d)+'_1.ids.json')).read_text()) for d in [20000,131072]}
deadline=datetime.datetime.fromisoformat(json.loads((R/'run-state.json').read_text())['deadline_utc'])
plan={'protocol':'same captured graphs in one process; OFF/ON four interleaved pairs per depth; greedy held-out fixture',
      'contexts':{k:len(v) for k,v in fixtures.items()},'args':cfg['args'],'exe_sha256':V.sha(exe),'server_sha256':V.sha(SOURCE/'serve/server.py'),
      'tokens_per_sample':1024,'minimum_gain_pct':3,'artificial_load':False,'daily_modified':False,
      'control':'strata_tune.topk_dynamic=0|1; synchronized request boundary, both GPU guards retained',
      'limitations':'Bounded throughput, not complete-answer quality. Elastic membership can change across requests.'}
result={'status':'running','plan':plan,'records':[],'by_depth':{}};V.write_json(OUT/'plan.json',plan)
env=dict(os.environ);env.pop('STRATA_API_KEY',None);env.update(cfg.get('env',{}))
env.update(STRATA_TOPK_DYNAMIC='1',STRATA_TOPK_DYNAMIC_TRACE='1',STRATA_MTP_BATCH_RING='0',STRATA_DECODE_TIMING='1',STRATA_SPLIT_TIMING='1',PYTHONDONTWRITEBYTECODE='1',CUDA_CACHE_PATH=str(OUT/'cuda-cache'))
env['PATH']=os.pathsep.join(cfg.get('lib_dirs',[])+[env.get('PATH','')])
engine=StrataEngine(str(exe),cfg['args'],cwd=str(OUT),log=str(OUT/'engine.log'),env=env,lazy=True)
def save():V.write_json(OUT/'results.json',result)
def measure(depth,mode,phase):
    V.require((deadline-datetime.datetime.now(datetime.timezone.utc)).total_seconds()>60,'Four-hour deadline')
    V.require(psutil.virtual_memory().available>8*2**30,'RAM floor')
    ids=[x for x in engine.generate(fixtures[depth],1024,{'temperature':0,'strata_tune':{'topk_dynamic':mode,'pcie_frac':.28,'spec_min_p':.5}},threading.Event()) if x is not None]
    item={'depth':depth,'dynamic':mode,'phase':phase,**engine.last,'tokens':ids}
    V.require(item['generated']==1024 and item['finish']=='length','Incomplete throughput sample')
    item['decode_tps']=1000*item['generated']/item['decode_ms'];result['records'].append(item);save()
    print('PAIRED',depth,phase,'dynamic',mode,'tps',round(item['decode_tps'],3),flush=True)
    return item
try:
    engine.restart();result['info']=dict(engine.info);save()
    for depth in fixtures:
        measure(depth,0,'warmup')
        pairs=[]
        for repeat in range(4):
            a=measure(depth,0,'pair'+str(repeat)+'_off');b=measure(depth,1,'pair'+str(repeat)+'_on')
            pairs.append({'reference_tps':a['decode_tps'],'candidate_tps':b['decode_tps'],'gain_pct':100*(b['decode_tps']/a['decode_tps']-1),'tokens_identical':a['tokens']==b['tokens']})
        aa=[x['reference_tps'] for x in pairs];bb=[x['candidate_tps'] for x in pairs]
        ma,mb=statistics.median(aa),statistics.median(bb)
        result['by_depth'][depth]={'pairs':pairs,'median_reference_tps':ma,'median_candidate_tps':mb,'median_rate_gain_pct':100*(mb/ma-1),
                                 'median_paired_gain_pct':statistics.median(x['gain_pct'] for x in pairs),'reference_spread_pct':100*(max(aa)-min(aa))/ma,
                                 'all_pairs_positive':all(x['gain_pct']>0 for x in pairs),'passes_speed_threshold':mb>=ma*1.03}
        save();print('DEPTH_PAIRED_COMPLETE',depth,json.dumps(result['by_depth'][depth]),flush=True)
    text=(OUT/'engine.log').read_text(errors='replace')
    trace={str(m):text.count('strata topk dynamic request: '+str(m)) for m in [0,1]}
    V.require(trace['0']>=10 and trace['1']>=8,'Native mode-switch activation not demonstrated')
    result.update(status='completed',native_mode_trace=trace,quality_validation_pending=True);save()
    print('DYNAMIC_PAIRED_COMPLETE',flush=True)
except BaseException as e:result.update(status='failed',error=str(e));save();raise
finally:engine.close()
