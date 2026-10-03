from pathlib import Path
import os,subprocess,shutil,json,hashlib
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';T=R/'topk-base-build';T.mkdir(exist_ok=False)
VC=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC');CM=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
env=dict(os.environ);env.pop('STRATA_API_KEY',None)
p=subprocess.run(f'cmd.exe /d /s /c "call "{VC/"Auxiliary/Build/vcvars64.bat"}" >nul && set"',capture_output=True,text=True,encoding='cp1252',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0
for line in p.stdout.splitlines():
    if '=' in line and not line.startswith('='):k,v=line.split('=',1);env[k]=v
deps=['strata_kernels.lib','strata_core.lib']
for rel in deps:shutil.copy2(R/'base-deps'/rel,T/rel)
rel='CMakeFiles/qsa_topk_parity.dir/src/kernels/qsa_topk_parity.cpp.obj';(T/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'build'/rel,T/rel)
cmds=subprocess.check_output([str(CM/'Ninja/ninja.exe'),'-C',str(R/'build'),'-t','commands','qsa_topk_parity'],text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW).splitlines()
cmd=next(c for c in cmds if '/out:qsa_topk_parity.exe' in c)
with (R/'build-topk-base.log').open('w',encoding='utf-8') as f:p=subprocess.run(cmd,cwd=T,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode==0,(R/'build-topk-base.log').read_text()
(R/'topk-base-build.json').write_text(json.dumps({'method':'same PR603 parity driver object linked against preserved pre603 aligned038 kernel/core libraries; compares actual SM75 active-bound baseline, no STRATA_TOPK_OLD override','sha256':{rel:hashlib.sha256((T/rel).read_bytes()).hexdigest() for rel in deps+['CMakeFiles/qsa_topk_parity.dir/src/kernels/qsa_topk_parity.cpp.obj','qsa_topk_parity.exe']}},indent=2));print('Fair baseline top-k driver ready')
