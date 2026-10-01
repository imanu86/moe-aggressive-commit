"""Unisce le patch validate 0.1.31/HC/vector/PR315 in un candidato daily isolato."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from compila_0131 import BASE, CUDA, VC, NINJA
from compila_pr315 import integrate_gr


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--hc',type=Path,required=True)
    ap.add_argument('--hc-logits',type=Path,required=True)
    ap.add_argument('--vector',type=Path,required=True)
    ap.add_argument('--pr315',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    base,hc,hcl,vec,pr=[p.resolve(strict=True) for p in [a.base,a.hc,a.hc_logits,a.vector,a.pr315]]
    out=a.out.resolve()
    sys.path.insert(0,str(BASE/'.venv/Lib/site-packages'))
    import psutil
    if any((p.info['name'] or '').lower() in ('strata.exe','llama-server.exe') for p in psutil.process_iter(['name'])):
        raise RuntimeError('Motore attivo: compilazione rinviata')
    out.mkdir(parents=True,exist_ok=False)
    source,build=out/'source',base/'build'
    shutil.copytree(hcl/'source',source)
    header='include/strata/kernels/fused_gr.hpp'; gr='src/kernels/cuda/fused_gr.cu'; verify='src/core/verify.cpp'
    changes={header:(pr/'source'/header).read_text(encoding='utf-8'),
             gr:integrate_gr((source/gr).read_text(encoding='utf-8'),(pr/'incoming'/gr).read_text(encoding='utf-8')),
             'src/kernels/cuda/dequant_bf16.cu':(vec/'dequant_bf16.cu').read_text(encoding='utf-8')}
    assert (source/'include/strata/core/tc_sm75.hpp').read_bytes()==(vec/'include/strata/core/tc_sm75.hpp').read_bytes()
    text=(source/verify).read_text(encoding='utf-8')
    anchor='    cudaGetDevice(&device_);'
    assert text.count(anchor)==1
    line=next(line for line in text.splitlines(True) if anchor in line)
    changes[verify]=text.replace(line,line+'    strata::kernels::fused_gr_check(); // PR315: once per card, bitwise gate\n')
    patch=''
    for name,after in changes.items():
        before=(source/name).read_text(encoding='utf-8')
        patch+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
        (source/name).write_text(after,encoding='utf-8')
    (out/'daily-combination.patch').write_text(patch,encoding='utf-8')
    env=dict(os.environ)
    if 'STRATA_API_KEY' in env:raise RuntimeError('Escludere STRATA_API_KEY')
    env.pop('STRATA_GR_V3',None);env.pop('STRATA_HC_V2',None)
    init=subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',capture_output=True,text=True,env=env,check=True)
    for line in init.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            key,value=line.split('=',1);env[key]=value
    env['PATH']=str(CUDA/'bin')+os.pathsep+env.get('Path',env.get('PATH',''))
    binary=VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64'
    result={'base':str(base),'hc':str(hc),'hc_logits':str(hcl),'vector':str(vec),'pr315':str(pr),'scope':'0.1.31 + nine local patches + HC/GDN FP16 + vector dequant + PR315 + opt-in logits','steps':[]}
    def run(name,command,shell=False):
        print(name,flush=True);start=time.monotonic()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            proc=subprocess.run(command if shell else list(map(str,command)),cwd=out,env=env,shell=shell,stdout=log,stderr=subprocess.STDOUT)
        result['steps'].append({'name':name,'exit':proc.returncode,'seconds':round(time.monotonic()-start,2)})
        (out/'build-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        if proc.returncode:raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))
    replacements={}
    for target in [r'CMakeFiles\strata_kernels.dir\src\kernels\cuda\fused_gr.cu.obj',r'CMakeFiles\strata_engine.dir\src\core\verify.cpp.obj']:
        command=subprocess.check_output([str(NINJA),'-C',str(build),'-t','commands',target]).decode().splitlines()[-1]
        assert ' -c ' in command and target in command
        command=command.replace(str(base/'source'),str(source)).replace((base/'source').as_posix(),source.as_posix())
        destination=out/target;destination.parent.mkdir(parents=True,exist_ok=True)
        replacements[target]=destination
        run('compile-'+destination.name,command,shell=True)
    replacements[r'CMakeFiles\strata_kernels.dir\src\kernels\cuda\dequant_bf16.cu.obj']=vec/'dequant_bf16.cu.obj'
    ninja=(build/'build.ninja').read_text(encoding='utf-8')
    for library in ['strata_kernels.lib','strata_engine.lib']:
        line=next(x for x in ninja.splitlines() if x.startswith('build '+library+':'))
        objects=line.split('Release ',1)[1].split(' ||',1)[0].split()
        rsp=out/(library+'.rsp')
        rsp.write_text('/nologo\n/out:"'+str(out/library)+'"\n'+'\n'.join('"'+str(replacements.get(x,build/x))+'"' for x in objects),encoding='utf-8')
        run('archive-'+library,[binary/'lib.exe','@'+str(rsp)])
    libs=[out/'strata_engine.lib',hc/'strata_prefill.lib',build/'strata_spec.lib',out/'strata_kernels.lib']
    libs += [build/x for x in ['strata_core.lib','strata_kernels_cpu.lib','ggml/src/ggml-cpu.lib','strata_mmq.lib','ggml/src/ggml-base.lib']]
    libs += [CUDA/'lib/x64'/(x+'.lib') for x in ['cudart','cuda','cublas','cublasLt','cudadevrt']]
    libs += [x+'.lib' for x in ['kernel32','user32','gdi32','winspool','shell32','ole32','oleaut32','uuid','comdlg32','advapi32']]
    run('link',[binary/'link.exe','/nologo','/machine:x64','/INCREMENTAL:NO','/subsystem:console','/DEBUG','/OPT:REF','/OPT:ICF','/MANIFEST:EMBED','/out:'+str(out/'strata.exe'),'/pdb:'+str(out/'strata.pdb'),hcl/r'CMakeFiles\strata.dir\src\program\generate.cpp.obj',*libs])
    parity=out/'hc_check.cpp'
    shutil.copy2(pr/'hc_check.cpp',parity)
    run('compile-hc-check',[binary/'cl.exe','/nologo','/std:c++20','/EHsc','/O2','/MD','/I'+str(source/'include'),parity,'/Fo:'+str(out/'hc_check.obj'),'/Fe:'+str(out/'hc_check.exe'),'/link',out/'strata_kernels.lib',build/'strata_core.lib',CUDA/'lib/x64/cudart.lib',CUDA/'lib/x64/cudadevrt.lib'])
    run('hc-check',[out/'hc_check.exe'])
    print((out/'hc-check.log').read_text(encoding='utf-8'),flush=True)
    result['exe_sha256']=hashlib.sha256((out/'strata.exe').read_bytes()).hexdigest()
    result['source_sha256']={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in changes}
    result['reused_objects_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [hc/'strata_prefill.lib',vec/'dequant_bf16.cu.obj',hcl/r'CMakeFiles\strata.dir\src\program\generate.cpp.obj']}
    (out/'build-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('DAILY_BUILD_OK',out,flush=True)


if __name__=='__main__':main()
