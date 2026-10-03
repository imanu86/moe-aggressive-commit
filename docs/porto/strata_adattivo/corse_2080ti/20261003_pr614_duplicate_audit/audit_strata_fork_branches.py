from pathlib import Path
import json,subprocess,concurrent.futures,base64,hashlib,re,datetime
BASE=Path(__file__).resolve().parent;OUT=BASE/'duplicate-audit-20261003';GH=r'C:\Program Files\GitHub CLI\gh.exe'
meta=json.loads((OUT/'audit.json').read_text());repositories=sorted({h['repository'] for h in meta['heads'] if 'pr' not in h})
result={'scope':'All public branch heads returned by the API for readable listed fork repositories and upstream. Public default heads already audited separately.','repositories':len(repositories),'branches':[],'errors':[],'sources':[]}
def save():(OUT/'branch-audit.json').write_text(json.dumps(result,indent=2))
def api(endpoint,pages=False):
    cmd=[GH,'api',endpoint]+(['--paginate'] if pages else [])
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:raise RuntimeError(p.stderr.strip()[:250])
    if not pages:return json.loads(p.stdout)
    decoder=json.JSONDecoder();rest=p.stdout.strip();out=[]
    while rest:a,n=decoder.raw_decode(rest);out.extend(a);rest=rest[n:].lstrip()
    return out
def branches(repo):return [{'repository':repo,'branch':b['name'],'sha':b['commit']['sha']} for b in api(f'repos/{repo}/branches?per_page=100',True)]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    jobs={pool.submit(branches,repo):repo for repo in repositories}
    for i,f in enumerate(concurrent.futures.as_completed(jobs),1):
        try:result['branches'].extend(f.result())
        except Exception as e:result['errors'].append({'repository':jobs[f],'error':repr(e)})
        if i%100==0:save();print('BRANCH REPOS',i,'/',len(repositories),flush=True)
known={r['head']['sha'] for r in meta['sources'] if 'error' not in r};unique={}
for h in result['branches']:
    if h['sha'] not in known:unique.setdefault(h['sha'],h)
result['additional_unique_heads']=len(unique);print('ADDITIONAL HEADS',len(unique),flush=True);save()
def inspect(h):
    rows=[]
    for path in ('src/program/generate.cpp','src/core/expert_cache.cpp'):
        try:
            d=api(f'repos/{h["repository"]}/contents/{path}?ref={h["sha"]}');raw=base64.b64decode(d['content']);text=raw.decode('utf-8',errors='replace')
            target=OUT/'source-blobs'/(h['sha']+'.'+path.replace('/','_'));target.write_bytes(raw)
            matches={k:[{'line':i+1,'text':s[:400]} for i,s in enumerate(text.splitlines()) if re.search(p,s,re.I)] for k,p in {'tail_flag':'prompt.cache.tail|pp_tail_saved|tail_checkpoint','vmm':'cuMemAddressReserve|cuMemCreate|cuMemMap','elastic':'--elastic|open_sized_elastic|elastic_period','near_tail':'(?:tail|end|remaining|near).{0,60}checkpoint|checkpoint.{0,60}(?:tail|end|remaining|near)'}.items()}
            rows.append({'head':h,'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'matches':matches})
        except Exception as e:rows.append({'head':h,'path':path,'error':repr(e)})
    return rows
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    jobs=[pool.submit(inspect,h) for h in unique.values()]
    for i,f in enumerate(concurrent.futures.as_completed(jobs),1):
        result['sources'].extend(f.result())
        if i%20==0:save();print('BRANCH SOURCES',i,'/',len(unique),flush=True)
result.update(status='completed',finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
for r in result['sources']:
    if 'matches' in r and (r['matches']['tail_flag'] or r['matches']['elastic']):print('MATCH',r['head'],r['path'],r['matches'],flush=True)
print('BRANCH AUDIT COMPLETE',len(result['branches']),'heads',len(unique),'new unique; errors',len(result['errors']),flush=True)
