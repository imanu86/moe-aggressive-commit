from pathlib import Path
import sys,os,json,subprocess,shutil,hashlib,difflib
BASE=Path(__file__).resolve().parent;R=BASE/'daily038_alignment_20261003';S=R/'source';wide='--wide' in sys.argv;label='wide' if wide else 'base'
VC=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC');CM=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake');CUDA=Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
env=dict(os.environ);env.pop('STRATA_API_KEY',None)
p=subprocess.run(f'cmd.exe /d /s /c "call "{VC/"Auxiliary/Build/vcvars64.bat"}" >nul && set"',capture_output=True,text=True,encoding='cp1252',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0
for line in p.stdout.splitlines():
    if '=' in line and not line.startswith('='):k,v=line.split('=',1);env[k]=v
env.pop('STRATA_API_KEY',None);env['PYTHONDONTWRITEBYTECODE']='1';env['PATH']=str(CUDA/'bin')+os.pathsep+env.get('PATH','')
def run(cmd,name,cwd=R):
    print(name,flush=True)
    with (R/(name+'.log')).open('w',encoding='utf-8') as f:p=subprocess.run([str(x) for x in cmd],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:print((R/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-7000:])
    assert p.returncode==0,name
if not wide:
    run([CM/'CMake/bin/cmake.exe','-S',S,'-B',R/'build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_MAKE_PROGRAM={CM/"Ninja/ninja.exe"}',f'-DCMAKE_CUDA_COMPILER={CUDA/"bin/nvcc.exe"}','-DCMAKE_CUDA_ARCHITECTURES=75','-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc','-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared','-DSTRATA_ENABLE_CUDA=ON','-DSTRATA_ENABLE_HIP=OFF','-DSTRATA_BUILD_TESTS=ON','-DSTRATA_PARITY_PROMPT_ATTN=ON','-DSTRATA_NATIVE_EXPERTS=ON','-DSTRATA_GGML_DIR=D:/ds4_work/strata/Strata/third_party/llama.cpp','-DFETCHCONTENT_FULLY_DISCONNECTED=ON',f'-DPython3_EXECUTABLE={sys.executable}'],'configure-base')
targets=['strata','qsa_topk_active_parity','gr_parity','gdn_parity','pool_quant_parity','expert_cache_elastic_test','expert_cache_per_layer_test','expert_profile_save_test']
if wide:targets.append('qsa_topk_parity')
run([CM/'CMake/bin/cmake.exe','--build',R/'build','--parallel','2','--target',*targets],'build-'+label)
exe=R/('strata-'+label+'.exe');assert not exe.exists();shutil.copy2(R/'build/strata.exe',exe)
run([CM/'CMake/bin/ctest.exe','--test-dir',R/'build','--output-on-failure','-R','^(qsa_topk_active_parity|gr_parity|gdn_parity|expert_cache_elastic_test|expert_cache_per_layer_test|expert_profile_save_test)$'],'ctest-'+label)
if wide:run([R/'build/qsa_topk_parity.exe','--selftest'],'topk-wide-selftest')
run([R/'build/pool_quant_parity.exe',r'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'],'pool-quant-'+label)
p=S/'src/program/generate.cpp';before=p.read_text(encoding='utf-8');old=(BASE/'checkpoint038_20261003/qa-readout-A.patch').read_text(encoding='utf-8');hook='\n'.join(l[1:] for l in old.splitlines() if l.startswith('+') and not l.startswith('+++'))+'\n'
needle='                first_window = false;\n                bool eos = false;';assert before.count(needle)==1;after=before.replace(needle,hook+needle)
(R/('qa-readout-'+label+'.patch')).write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/src/program/generate.cpp',tofile='b/src/program/generate.cpp')),encoding='utf-8',newline='\n')
try:
    p.write_text(after,encoding='utf-8',newline='\n');run([CM/'CMake/bin/cmake.exe','--build',R/'build','--parallel','2','--target','strata'],'build-qa-'+label)
    qa=R/('strata-qa-'+label+'.exe');shutil.copy2(R/'build/strata.exe',qa)
    (R/('build-'+label+'.json')).write_text(json.dumps({'shipping_exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'qa_exe_sha256':hashlib.sha256(qa.read_bytes()).hexdigest(),'common_readout':True,'source_files':{p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in S.rglob('*') if p.is_file() and p.name!='generate.cpp'},'shipping_generate_sha256':hashlib.sha256(before.encode()).hexdigest()},indent=2))
finally:p.write_text(before,encoding='utf-8',newline='\n');shutil.copy2(exe,R/'build/strata.exe')
print('BUILD READY',label,flush=True)
