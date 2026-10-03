from pathlib import Path
import os, subprocess, sys

ROOT=Path(__file__).resolve().parent/'fourhour_20261002'
SOURCE=ROOT/'candidate-source'
BUILD=ROOT/'build'
KERNELS='--kernels' in sys.argv
if KERNELS:
    SOURCE=ROOT/'kernel-source'
    BUILD=ROOT/'build-kernels'
SHARED='--shared' in sys.argv
if SHARED:
    SOURCE=ROOT/'shared-source'
    BUILD=ROOT/'build-shared'
V037='--037' in sys.argv
if V037:
    SOURCE=ROOT/'source037'
    BUILD=ROOT/'build037'
PR512='--pr512' in sys.argv
if PR512:
    SOURCE=ROOT/'pr512-source037'
    BUILD=ROOT/'build-pr512'
DYNAMIC='--dynamic' in sys.argv
if DYNAMIC:
    SOURCE=ROOT/'dynamic-source'
    BUILD=ROOT/'build-dynamic'
DYNAMIC2='--dynamic2' in sys.argv
if DYNAMIC2:
    SOURCE=ROOT/'dynamic2-source'
    BUILD=ROOT/'build-dynamic2'
MEMORY547='--memory547' in sys.argv
if MEMORY547:
    SOURCE=ROOT/'memory547-source'
    BUILD=ROOT/'build-memory547'
VC=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CUDA=Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
CM=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
env=dict(os.environ); env.pop('STRATA_API_KEY',None)
init=subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',capture_output=True,text=True,encoding='cp1252',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW)
if init.returncode: raise RuntimeError('MSVC environment initialization failed')
for line in init.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k,v=line.split('=',1); env[k]=v
env.pop('STRATA_API_KEY',None)
env['PYTHONDONTWRITEBYTECODE']='1'
def run(args,name):
    if KERNELS: name+='-kernels'
    if SHARED: name+='-shared'
    if V037: name+='-037'
    if PR512: name+='-pr512'
    if DYNAMIC: name+='-dynamic'
    if DYNAMIC2: name+='-dynamic2'
    if MEMORY547: name+='-memory547'
    print(name,flush=True)
    with (ROOT/(name+'.log')).open('w',encoding='utf-8') as log:
        p=subprocess.run([str(x) for x in args],stdout=log,stderr=subprocess.STDOUT,env=env,cwd=ROOT,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW)
    print(name,'exit',p.returncode,flush=True)
    if p.returncode:
        print((ROOT/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-10000:]); sys.exit(p.returncode)
if '--configure' in sys.argv:
    run([CM/'CMake/bin/cmake.exe','-S',SOURCE,'-B',BUILD,'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_MAKE_PROGRAM={CM/"Ninja/ninja.exe"}',f'-DCMAKE_CUDA_COMPILER={CUDA/"bin/nvcc.exe"}','-DCMAKE_CUDA_ARCHITECTURES=75','-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc','-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared','-DSTRATA_ENABLE_CUDA=ON','-DSTRATA_ENABLE_HIP=OFF',f'-DSTRATA_BUILD_TESTS={"ON" if PR512 else "OFF"}','-DSTRATA_PARITY_PROMPT_ATTN=ON','-DSTRATA_NATIVE_EXPERTS=ON','-DSTRATA_GGML_DIR=D:/ds4_work/strata/Strata/third_party/llama.cpp','-DFETCHCONTENT_FULLY_DISCONNECTED=ON',f'-DPython3_EXECUTABLE={sys.executable}'],'configure')
targets=[x for x in sys.argv[1:] if not x.startswith('--')]
if targets: run([CM/'CMake/bin/cmake.exe','--build',BUILD,'--parallel','2','--target',*targets],'build-'+'-'.join(targets))
