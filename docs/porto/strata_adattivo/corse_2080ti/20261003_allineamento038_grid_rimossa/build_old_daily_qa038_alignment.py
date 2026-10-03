from pathlib import Path
import os,sys,subprocess,shutil,json,hashlib
BASE=Path(__file__).resolve().parent;R=BASE/'daily038_alignment_20261003';S=R/'old-daily-source';B=R/'old-qa-build';OB=BASE/'build0136';OS=BASE/'candidate0136'
daily=Path(r'D:\ds4_work\strata\Strata\build-0136-daily\source')
assert (daily/'src/program/generate.cpp').read_bytes()==(OS/'src/program/generate.cpp').read_bytes()
S.mkdir(exist_ok=True)
for directory in ('include','src'):shutil.copytree(daily/directory,S/directory,dirs_exist_ok=True)
B.mkdir(exist_ok=False)
VC=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC');CM=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
env=dict(os.environ);env.pop('STRATA_API_KEY',None)
p=subprocess.run(f'cmd.exe /d /s /c "call "{VC/"Auxiliary/Build/vcvars64.bat"}" >nul && set"',capture_output=True,text=True,encoding='cp1252',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0
for line in p.stdout.splitlines():
    if '=' in line and not line.startswith('='):k,v=line.split('=',1);env[k]=v
env.pop('STRATA_API_KEY',None)
deps=['strata_engine.lib','strata_prefill.lib','strata_kernels.lib','strata_core.lib','strata_kernels_cpu.lib','strata_spec.lib','strata_mmq.lib','ggml/src/ggml-cpu.lib','ggml/src/ggml-base.lib']
meta={'dependencies':{},'source_sha256':hashlib.sha256((S/'src/program/generate.cpp').read_bytes()).hexdigest(),'method':'original0136 generate TU only plus identical common readout; unchanged original libraries copied read-only'}
for rel in deps:
    target=B/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OB/rel,target);meta['dependencies'][rel]=hashlib.sha256(target.read_bytes()).hexdigest()
(B/'CMakeFiles/strata.dir/src/program').mkdir(parents=True,exist_ok=True)
cmds=subprocess.check_output([str(CM/'Ninja/ninja.exe'),'-C',str(OB),'-t','commands','strata'],text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW).splitlines()
selected=[next(c for c in cmds if '/FoCMakeFiles\\strata.dir\\src\\program\\generate.cpp.obj' in c),next(c for c in cmds if '/out:strata.exe' in c)]
selected=[c.replace(str(OS),str(S)) for c in selected];meta['commands']=selected
p=S/'src/program/generate.cpp';before=p.read_text(encoding='utf-8');old=(BASE/'checkpoint038_20261003/qa-readout-A.patch').read_text(encoding='utf-8');hook='\n'.join(l[1:] for l in old.splitlines() if l.startswith('+') and not l.startswith('+++'))+'\n'
needle='                first_window = false;\n                bool eos = false;';assert before.count(needle)==1;p.write_text(before.replace(needle,hook+needle),encoding='utf-8',newline='\n')
try:
    for i,c in enumerate(selected):
        with (R/f'old-qa-build-{i}.log').open('w',encoding='utf-8') as f:status=subprocess.run(c,cwd=B,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        assert status.returncode==0,(R/f'old-qa-build-{i}.log').read_text(encoding='utf-8',errors='replace')[-5000:]
    exe=R/'strata-qa-old-daily.exe';shutil.copy2(B/'strata.exe',exe);meta['qa_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
finally:p.write_text(before,encoding='utf-8',newline='\n')
(R/'old-qa-build.json').write_text(json.dumps(meta,indent=2));print('Old Daily QA ready',flush=True)
