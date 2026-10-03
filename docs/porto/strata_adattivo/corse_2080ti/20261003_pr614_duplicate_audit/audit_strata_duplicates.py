from pathlib import Path
import json,subprocess,concurrent.futures,datetime,hashlib,base64,threading,re,sys
BASE=Path(__file__).resolve().parent;OUT=BASE/'duplicate-audit-20261003';OUT.mkdir(exist_ok='--resume' in sys.argv)
GH=r'C:\Program Files\GitHub CLI\gh.exe'
def api(endpoint):
    p=subprocess.run([GH,'api',endpoint],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:raise RuntimeError(p.stderr.strip()[:350])
    return json.loads(p.stdout)
decoder=json.JSONDecoder();rest=(BASE/'strata-fork-scan-current.json').read_text(encoding='utf-8-sig').strip();forks=[]
while rest:
    page,n=decoder.raw_decode(rest);forks.extend(page);rest=rest[n:].lstrip()
forks=[f for f in forks if f['full_name'].lower()!='imanu86/strata-2080ti']
meta={'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'All listed public forks default heads plus relevant upstream PR heads. Private/unlisted branches and unpublished work cannot be excluded.','listed_public_forks':len(forks),'heads':[],'errors':[],'sources':[]}
if '--resume' in sys.argv:meta=json.loads((OUT/'audit.json').read_text());meta['sources']=[]
def save():(OUT/'audit.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
def gethead(f):
    name=f['full_name'];d=api(f'repos/{name}/commits/{f["default_branch"]}')
    return {'repository':name,'branch':f['default_branch'],'sha':d['sha'],'message':d['commit']['message'],'date':d['commit']['committer']['date'],'url':d['html_url']}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    done={h['repository'] for h in meta['heads']}|{e['repository'] for e in meta['errors'] if e['stage']=='head'}
    jobs={pool.submit(gethead,f):f['full_name'] for f in forks if f['full_name'] not in done}
    for future in concurrent.futures.as_completed(jobs):
        try:meta['heads'].append(future.result())
        except Exception as e:meta['errors'].append({'stage':'head','repository':jobs[future],'error':repr(e)})
        if (len(meta['heads'])+len(meta['errors']))%50==0:save();print('FORK HEADS',len(meta['heads']),'errors',len(meta['errors']),flush=True)
up=api('repos/Niko1221/Strata/commits/main');meta['upstream_head']=up['sha'];meta['heads'].append({'repository':'Niko1221/Strata','branch':'main','sha':up['sha'],'url':up['html_url']})
for n in (37,563,378,65,203,62):
    d=json.loads((BASE/f'strata-scan-{n}.json').read_text(encoding='utf-8-sig'))
    meta['heads'].append({'repository':d['head']['repo']['full_name'],'branch':d['head']['ref'],'sha':d['head']['sha'],'pr':n,'url':d['html_url']})
unique={}
for h in meta['heads']:unique.setdefault(h['sha'],h)
meta['unique_heads']=len(unique);print('UNIQUE HEADS',len(unique),flush=True);save()
paths=('src/program/generate.cpp','src/core/expert_cache.cpp')
patterns={
 'tail_flag':r'prompt.cache.tail|pp_tail_saved|tail_checkpoint',
 'near_tail_checkpoint':r'(?:tail|end|remaining|near).{0,60}checkpoint|checkpoint.{0,60}(?:tail|end|remaining|near)',
 'elastic_flag':r'--elastic|open_sized_elastic|elastic_period',
 'vmm_cache':r'cuMemAddressReserve|cuMemCreate|cuMemMap|expert.cache.release',
 'kv_grow':r'kv.grow|kvg_start',
}
def inspect(h):
    source_rows=[]
    for path in paths:
        try:
            d=api(f'repos/{h["repository"]}/contents/{path}?ref={h["sha"]}')
            raw=base64.b64decode(d['content']);text=raw.decode('utf-8',errors='replace')
            digest=hashlib.sha256(raw).hexdigest();target=OUT/'source-blobs'/(h['sha']+'.'+path.replace('/','_'));target.write_bytes(raw)
            matches={key:[{'line':i+1,'text':line[:450]} for i,line in enumerate(text.splitlines()) if re.search(pattern,line,re.I)] for key,pattern in patterns.items()}
            source_rows.append({'head':h,'path':path,'blob':d['sha'],'sha256':digest,'matches':matches})
        except Exception as e:source_rows.append({'head':h,'path':path,'error':repr(e)})
    return source_rows
(OUT/'source-blobs').mkdir(exist_ok=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    jobs=[pool.submit(inspect,h) for h in unique.values()]
    for i,future in enumerate(concurrent.futures.as_completed(jobs),1):
        meta['sources'].extend(future.result())
        if i%10==0:save();print('SOURCE HEADS',i,'/',len(unique),flush=True)
meta['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();meta['status']='completed';save()
for r in meta['sources']:
    if 'matches' in r and any(r['matches'][key] for key in ('tail_flag','elastic_flag','vmm_cache')):
        print('MATCH',r['head']['repository'],r['head'].get('pr'),r['path'],{k:len(v) for k,v in r['matches'].items()},flush=True)
print('AUDIT COMPLETE',len(meta['heads']),len(meta['sources']),'head errors',len(meta['errors']),flush=True)
