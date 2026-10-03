"""Fast-forward actual Daily main, freeze tested source, atomically switch launcher/config."""
from pathlib import Path
import sys,os,subprocess,json,hashlib,shutil
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti');D=Path(r'D:\ds4_work\strata\Strata');BAT=Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
sys.path.insert(0,str(D/'.venv/Lib/site-packages'));import psutil
def git(root,*args):return subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8',errors='replace').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for root in (P,D):print(root,git(root,'branch','--show-current'),git(root,'status','--short','--branch'),flush=True);assert git(root,'branch','--show-current')=='main'
assert not any((p.info['name'] or '').lower().startswith('strata') and (p.info['name'] or '').lower().endswith('.exe') for p in psutil.process_iter(['name']))
rec=json.loads((R/'recovery.json').read_text());backup=Path(rec['backup']);assert git(D,'rev-parse','HEAD')==rec['old_head'] and not git(D,'diff','--name-only') and not git(D,'diff','--cached','--name-only')
assert sha(D/'strata-2080ti-sota.json')==rec['cfg_sha256'] and sha(BAT)==rec['launcher_sha256']
manifest=json.loads((P/'docs/sm75/source-manifest.json').read_text());exe=R/'strata-wide.exe';assert sha(exe)==manifest['validated_executable_sha256']
untracked=git(D,'ls-files','--others','--exclude-standard').splitlines();assert untracked==rec['untracked_preserved']
assert not set(untracked)&set(git(P,'ls-files').splitlines())
target=D/'build-0138-daily';assert not target.exists()
subprocess.run(['git','fetch','origin','main'],cwd=D,check=True);head=git(P,'rev-parse','HEAD');assert git(D,'rev-parse','origin/main')==head
subprocess.run(['git','merge','--ff-only','origin/main'],cwd=D,check=True)
target.mkdir();shutil.copy2(exe,target/'strata.exe');shutil.copytree(R/'source',target/'source');shutil.copy2(P/'docs/sm75/source-manifest.json',target/'source-manifest.json')
assert sha(target/'strata.exe')==manifest['validated_executable_sha256']
for rel,h in manifest['files'].items():assert sha(target/'source'/rel)==h,rel
cfg=json.loads((D/'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'));assert cfg['args'][cfg['args'].index('--max-context')+1]=='262144' and '--elastic' in cfg['args']
cfg['exe']=str(target/'strata.exe');assert '--prompt-cache-tail' not in cfg['args'];cfg['args']+=['--prompt-cache-tail','--prompt-cache-every','16384'];cfg.setdefault('env',{})['STRATA_PARALLEL_INTERMEDIATE_QUANT']='0'
text=BAT.read_text(encoding='utf-8').replace('build-0136-daily','build-0138-daily');text=text.replace('Strata daily validata il 2/10/2026: 0.1.36 + port sm75/elastica + top-k attivo + ordinamento #463; quantizzazione seriale.','Strata daily validata il 3/10/2026: 0.1.38 + sm75/elastica + top-k #603 + checkpoint tail #614; grid rimossa, quantizzazione seriale.');text=text.replace('ALLINEAMENTO_0136_2_OTTOBRE.md','ALLINEAMENTO_0138_GRID_RIMOSSA_3_OTTOBRE.md')
ctmp=D/'strata-2080ti-sota.json.038.tmp';btmp=BAT.with_suffix('.bat.038.tmp');assert not ctmp.exists() and not btmp.exists();ctmp.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8');btmp.write_text(text,encoding='utf-8',newline='\r\n')
try:
    os.replace(ctmp,D/'strata-2080ti-sota.json');os.replace(btmp,BAT)
    assert 'build-0138-daily' in BAT.read_text() and '--prompt-cache-tail' in json.loads((D/'strata-2080ti-sota.json').read_text())['args']
    assert set(untracked)==set(git(D,'ls-files','--others','--exclude-standard').splitlines())
except BaseException:
    shutil.copy2(backup/'strata-2080ti-sota.json',D/'strata-2080ti-sota.json');shutil.copy2(backup/BAT.name,BAT);raise
result={'backup':str(backup),'daily_head':head,'exe':str(target/'strata.exe'),'exe_sha256':sha(target/'strata.exe'),'server':str(target/'source/serve/server.py'),'server_sha256':sha(target/'source/serve/server.py'),'config_sha256':sha(D/'strata-2080ti-sota.json'),'launcher_sha256':sha(BAT),'untracked_preserved':len(untracked),'kv_capacity':262144,'kv_resident':32768,'elastic':True,'checkpoint_every':16384,'checkpoint_tail':True,'grid_present':False,'parallel_quant':'0','old_daily_build_retained':str(D/'build-0136-daily')}
(R/'daily-installation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
