"""Install the validated binary/source together; preserve old daily and all untracked work."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

R=Path(__file__).resolve().parent
P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
D=Path(r'D:\ds4_work\strata\Strata')
RESEARCH=Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit')
BAT=Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
SOURCE=R/'candidate0136'
EXE=R/'build0136/strata.exe'
OLD='ad4700d61852af3481c8c36a98e5411a76e167cc'
BACKUP=Path(r'D:\ds4_work\strata\ripristini')/time.strftime('%Y%m%d_%H%M%S_0136_main_daily')

def git(root,*args):
    return subprocess.run(['git',*args],cwd=root,check=True,text=True,encoding='utf-8',capture_output=True).stdout

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

for root in [P,D,RESEARCH]:
    print(str(root),git(root,'branch','--show-current').strip(),git(root,'status','--short','--branch'),flush=True)
if git(P,'branch','--show-current').strip()!='main' or git(D,'branch','--show-current').strip()!='main':
    raise RuntimeError('Operational checkouts must be main')
if git(D,'rev-parse','HEAD').strip()!=OLD or git(D,'diff','--name-only') or git(D,'diff','--cached','--name-only'):
    raise RuntimeError('Daily tracked work changed: inspect before installation')
manifest=json.loads((P/'docs/sm75/source-manifest.json').read_text(encoding='utf-8'))
if sha(EXE)!=manifest['validated_executable_sha256']:
    raise RuntimeError('Tested binary does not match published source manifest')
sysinfo=subprocess.check_output(['tasklist','/FO','CSV','/NH'],text=True,encoding='cp1252',errors='replace')
if any('"'+name+'"' in sysinfo.lower() for name in ['strata.exe','llama-server.exe']):
    raise RuntimeError('An engine is running; do not alter its install')
target=D/'build-0136-daily'
if target.exists(): raise RuntimeError('Daily 0.1.36 target already exists; inspect first')
untracked=git(D,'ls-files','--others','--exclude-standard').splitlines()
pubnames=set(git(P,'ls-files').splitlines())
if set(untracked)&pubnames:
    raise RuntimeError('Untracked daily files would collide with the new main')
BACKUP.mkdir(parents=True)
git(D,'bundle','create',str(BACKUP/'daily-before.bundle'),'--all')
metadata=[]
for name in untracked:
    src=D/name
    dst=BACKUP/'untracked'/name
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.suffix.lower()=='.dmp':
        os.link(src,dst)  # Same D: volume; preserve huge dumps without copying their data.
        mode='hardlink; source left untouched'
    else:
        shutil.copyfile(src,dst)
        mode='copy'
    metadata.append({'path':name,'bytes':src.stat().st_size,'backup':mode})
shutil.copyfile(D/'strata-2080ti-sota.json',BACKUP/'strata-2080ti-sota.json')
shutil.copyfile(BAT,BACKUP/BAT.name)
shutil.copytree(D/'build-0131-daily',BACKUP/'build-0131-daily')
(BACKUP/'untracked-manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
git(D,'fetch','origin','main')
head=git(P,'rev-parse','HEAD').strip()
if git(D,'rev-parse','origin/main').strip()!=head:
    raise RuntimeError('Publication main has not been pushed')
git(D,'merge','--ff-only','origin/main')
target.mkdir()
shutil.copyfile(EXE,target/'strata.exe')
shutil.copyfile(R/'build0136/strata.pdb',target/'strata.pdb')
shutil.copytree(SOURCE,target/'source')
shutil.copyfile(P/'docs/sm75/source-manifest.json',target/'source-manifest.json')
cfg=json.loads((D/'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
if cfg['args'][cfg['args'].index('--max-context')+1]!='262144' or '--elastic' not in cfg['args']:
    raise RuntimeError('Daily KV/elastic policy changed unexpectedly')
cfg['exe']=str(target/'strata.exe')
cfg.setdefault('env',{})['STRATA_PARALLEL_INTERMEDIATE_QUANT']='0'
(D/'strata-2080ti-sota.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
text=BAT.read_text(encoding='utf-8')
text=text.replace('build-0131-daily','build-0136-daily')
text=text.replace('0.1.31 + patch elastiche locali + HC/GDN FP16 + vector + PR315 + top-k attivo.',
                  '0.1.36 + port sm75/elastica + top-k attivo + ordinamento #463; quantizzazione seriale.')
text=text.replace('RISULTATI_TOPK_2_OTTOBRE.md','ALLINEAMENTO_0136_2_OTTOBRE.md')
BAT.write_text(text,encoding='utf-8',newline='\r\n')
LAUNCHERS=RESEARCH/'docs/porto/strata_adattivo/lanciatori'
shutil.copyfile(D/'strata-2080ti-sota.json',LAUNCHERS/'strata-2080ti-sota.json')
shutil.copyfile(BAT,LAUNCHERS/BAT.name)
if sha(target/'strata.exe')!=manifest['validated_executable_sha256'] or sha(target/'source/serve/server.py')!=sha(SOURCE/'serve/server.py'):
    raise RuntimeError('Installed engine/server mismatch')
if set(untracked)!=set(git(D,'ls-files','--others','--exclude-standard').splitlines()):
    raise RuntimeError('Untracked paths changed during integration')
result={'backup':str(BACKUP),'daily_head':head,'exe':str(target/'strata.exe'),'exe_sha256':sha(target/'strata.exe'),
        'server':str(target/'source/serve/server.py'),'server_sha256':sha(target/'source/serve/server.py'),
        'untracked_preserved':len(untracked),'kv_capacity':262144,'kv_resident':32768,'elastic':True,'parallel_quant':'0'}
(R/'daily-installation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
