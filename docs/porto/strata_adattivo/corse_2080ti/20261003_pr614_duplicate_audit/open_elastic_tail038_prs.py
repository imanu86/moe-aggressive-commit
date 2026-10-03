"""Run only after the human explicitly authorizes the named PR branches.

An isolated index prepares each focused commit; the operational main checkout
and its real index remain untouched. No worktree or detached checkout is used.
"""
from pathlib import Path
import os,subprocess,json,hashlib,sys
assert '--authorized' in sys.argv,'Requires actual user authorization for the named branches, not just filesystem access'
BASE=Path(__file__).resolve().parent;REPO=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti');GH=r'C:\Program Files\GitHub CLI\gh.exe'
UP='99f3dbd0b21d1401b3769e0c0d963913607f380b'
def run(args,env=None,binary=False):
    p=subprocess.run(args,cwd=REPO,env=env,capture_output=True,text=not binary)
    if p.returncode:raise RuntimeError((p.stderr or p.stdout))
    return p.stdout if binary else p.stdout.strip()
def git(*a,env=None,binary=False):return run(['git',*a],env,binary)
initial={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'status':git('status','--short','--branch')}
assert initial['branch']=='main' and not git('status','--porcelain'),initial
assert git('rev-parse',UP)==UP
assert run([GH,'api','repos/Niko1221/Strata/commits/main','--jq','.sha'])==UP,'Base moved; re-evaluate before opening'
items=[
 ('codex/cuda-elastic-cache-038','elastic038_20261003','elastic.patch','adaptation.json','OPUS-CACHE-Porta la cache elastica CUDA su upstream 0.1.38','elastic038-pr-body.md','cache: add optional CUDA VMM elastic expert cache'),
 ('codex/prompt-cache-tail-038','checkpoint-tail038_20261003','checkpoint-tail.patch','preparation.json','GPT6-CACHE-Salva un checkpoint opzionale vicino alla fine del prompt','checkpoint-tail038-pr-body.md','serve: optionally checkpoint an existing chunk near the prompt tail')]
if '--tail-only' in sys.argv:items=[item for item in items if item[0]=='codex/prompt-cache-tail-038']
journal={'upstream':UP,'initial_checkout':initial,'items':[]}
def save():(BASE/'elastic-tail-pr-publication.json').write_text(json.dumps(journal,indent=2),encoding='utf-8')
save()
for branch,lab,patch,meta,message,body,title in items:
    assert git('branch','--show-current')=='main'
    print(git('status','--short','--branch'),flush=True)
    # Fail safely if a previous attempt created a ref; inspect its journal first.
    assert not run(['git','for-each-ref','--format=%(refname)','refs/heads/'+branch]),branch
    existing=json.loads(run([GH,'pr','list','--repo','Niko1221/Strata','--state','all','--head',branch,'--json','number,url']))
    assert not existing,existing
    index=BASE/(branch.replace('/','-')+'.index');assert not index.exists(),index
    env=dict(os.environ,GIT_INDEX_FILE=str(index));source=BASE/lab
    git('read-tree',UP,env=env)
    git('-c','core.autocrlf=false','apply','--cached',str(source/patch),env=env)
    paths=set(git('diff','--cached','--name-only',UP,env=env).splitlines())
    metadata=json.loads((source/meta).read_text());expected=metadata.get('files')
    if lab.startswith('checkpoint'):expected=metadata.get('files',metadata.get('source_hashes'))
    assert isinstance(expected,dict),metadata
    assert paths==set(expected),(paths,expected)
    for path,want in expected.items():
        data=git('show',':'+path,env=env,binary=True)
        assert hashlib.sha256(data).hexdigest()==want,path
    tree=git('write-tree',env=env)
    trailer='Co-Authored-By: Codex <noreply@openai.com>'
    if branch=='codex/cuda-elastic-cache-038':trailer='Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n'+trailer
    msg=BASE/(branch.replace('/','-')+'.commit.txt');msg.write_text(message+'\n\n'+trailer+'\n',encoding='utf-8',newline='\n')
    commit=git('commit-tree',tree,'-p',UP,'-F',str(msg),env=env)
    item={'branch':branch,'tree':tree,'commit':commit,'paths':sorted(paths),'phase':'commit_prepared'};journal['items'].append(item);save()
    git('update-ref','--create-reflog','refs/heads/'+branch,commit,'0'*40)
    # Push immediately after publishing the local commit ref.
    git('push','origin','refs/heads/'+branch+':refs/heads/'+branch)
    item['phase']='pushed';save()
    url=run([GH,'pr','create','--repo','Niko1221/Strata','--base','main','--head','imanu86:'+branch,'--title',title,'--body-file',str(BASE/body)])
    assert url.startswith('https://github.com/Niko1221/Strata/pull/'),url
    item.update(phase='pr_created',url=url);save();print('PR_CREATED',url,flush=True)
    final={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'status':git('status','--short','--branch')}
    assert final==initial,(initial,final)
print('Ready PRs created. Attach each URL to this task before finishing.',flush=True)
