from pathlib import Path
import os
import subprocess
import sys

R = Path(__file__).resolve().parent
VERSION = '0136' if '--136' in sys.argv else '0135'
SOURCE = R/('candidate'+VERSION)
PY = sys.executable
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
CM = Path(r'C:\Users\imanu\AppData\Local\Programs\Python\Python312\Scripts')
env = dict(os.environ)
env.pop('STRATA_API_KEY', None)
init = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                      capture_output=True, text=True, encoding='cp1252', errors='replace',
                      env=env, creationflags=subprocess.CREATE_NO_WINDOW)
if init.returncode:
    raise RuntimeError('MSVC environment initialization failed')
for line in init.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k, v = line.split('=', 1)
        env[k] = v
env.pop('STRATA_API_KEY', None)

def run(args, name, timeout=1800):
    if VERSION == '0136':
        name = '0136-'+name
    print(name, flush=True)
    with (R / (name + '.log')).open('w', encoding='utf-8') as log:
        p = subprocess.run([str(x) for x in args], stdout=log, stderr=subprocess.STDOUT,
                           env=env, cwd=R, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    print(name, 'exit', p.returncode, flush=True)
    if p.returncode:
        print((R/(name+'.log')).read_text(encoding='utf-8', errors='replace')[-10000:])
        sys.exit(p.returncode)

B = R / ('build'+VERSION)
if '--topk-direct' in sys.argv:
    B.mkdir(exist_ok=True)
    run([CUDA/'bin/nvcc.exe', '-std=c++17', '-O3', '-arch=sm_75', '-D_WINDOWS',
         '-Xcompiler=/EHsc', '-I', R/'candidate0135/include',
         R/'candidate0135/src/kernels/cuda/qsa_select.cu',
         R/'candidate0135/src/kernels/qsa_topk_active_parity.cpp',
         '-o', B/'qsa_topk_active_parity.exe', '-cudart=shared'], 'direct-topk')
    sys.exit(0)
if '--gr-direct' in sys.argv:
    B.mkdir(exist_ok=True)
    run([CUDA/'bin/nvcc.exe', '-std=c++17', '-O3', '-arch=sm_75', '-D_WINDOWS',
         '-Xcompiler=/EHsc', '-I', R/'candidate0135/include',
         R/'candidate0135/src/kernels/cuda/gr.cu', R/'candidate0135/src/kernels/cuda/fused_gr.cu',
         R/'candidate0135/src/kernels/cuda/native_bf16.cu', R/'candidate0135/src/kernels/cuda/native_gr_norm.cu',
         R/'candidate0135/src/kernels/cuda/native_gr_postops.cu',
         R/'candidate0135/src/kernels/cuda/verify_kernels.cu',
         R/'candidate0135/src/kernels/gr_parity.cpp',
         '-o', B/'gr_parity.exe', '-cudart=shared'], 'direct-gr')
    sys.exit(0)
if '--pool-direct' in sys.argv:
    B.mkdir(exist_ok=True)
    CL = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe'
    GG = Path(r'D:\ds4_work\strata\Strata\third_party\llama.cpp\ggml')
    inputs = ['src/kernels/cpu/pool.cpp', 'src/kernels/cpu/native_expert.cpp',
              'src/kernels/cpu/expert_layout.cpp', 'src/kernels/cpu/pool_quant_parity.cpp',
              'src/kernels/cpu/expert.cpp','src/kernels/cpu/q2_avx2.cpp',
              'src/kernels/cpu/iq_avx512.cpp','src/kernels/cpu/iq_avx2.cpp','src/kernels/cpu/kq_avx2.cpp']
    objects = []
    for p in inputs:
        obj = B/(Path(p).stem+'.obj')
        arch = ['/arch:AVX512'] if Path(p).name in ('expert.cpp','iq_avx512.cpp') else ['/arch:AVX2'] if 'avx2.cpp' in p else []
        run([CL, '/nologo', '/std:c++20', '/O2', '/EHsc', '/MD', '/DSTRATA_NATIVE_EXPERTS=1', *arch,
             '/I'+str(R/'candidate0135/include'), '/I'+str(R/'candidate0135/third_party/ggml'),
             '/I'+str(GG/'include'), '/I'+str(GG/'src'), '/c', R/'candidate0135'/p, '/Fo'+str(obj)],
            'cpu-compile-'+Path(p).stem)
        objects.append(obj)
    libs = Path(r'D:\ds4_work\strata\Strata\build-0130')
    run([CL, '/nologo', '/MD', *objects, 'advapi32.lib',
         libs/'ggml/src/ggml-cpu.lib', libs/'ggml/src/ggml-base.lib',
         '/Fe'+str(B/'pool_quant_parity.exe')], 'cpu-link')
    sys.exit(0)
if '--syntax' in sys.argv:
    CL = VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe'
    for p in ['src/prefill/prefill.cpp','src/core/expert_cache.cpp','src/core/verify.cpp',
              'src/program/generate.cpp']:
        run([CL, '/nologo', '/std:c++20', '/EHsc', '/Zs', '/DSTRATA_NATIVE_EXPERTS=1', '/DSTRATA_VERSION="0.1.35"',
             '/I'+str(R/'candidate0135/include'), '/I'+str(CUDA/'include'),
             '/I'+str(R/'candidate0135/third_party/ggml'), R/'candidate0135'/p],
             'syntax-'+Path(p).stem)
    run([CUDA/'bin/nvcc.exe', '-std=c++17', '-O3', '-arch=sm_75', '-D_WINDOWS',
         '-Xcompiler=/EHsc', '-I', R/'candidate0135/include', '-c',
         R/'candidate0135/src/prefill/kernels.cu', '-o', B/'prefill-kernels.obj'], 'cuda-prefill-compile')
    run([CUDA/'bin/nvcc.exe', '-std=c++17', '-O3', '-arch=sm_75', '-D_WINDOWS',
         '-Xcompiler=/EHsc', '-I', R/'candidate0135/include', '-c',
         R/'candidate0135/src/kernels/cuda/dequant_bf16.cu', '-o', B/'dequant-bf16.obj'], 'cuda-dequant-compile')
    sys.exit(0)
if '--configure' in sys.argv:
    run([CM/'cmake.exe', '-S', SOURCE, '-B', B, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_MAKE_PROGRAM={CM / "ninja.exe"}',
         f'-DCMAKE_CUDA_COMPILER={CUDA / "bin/nvcc.exe"}', '-DCMAKE_CUDA_ARCHITECTURES=75',
         '-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared',
         '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF', '-DSTRATA_BUILD_TESTS=OFF',
         '-DSTRATA_PARITY_PROMPT_ATTN=ON', '-DSTRATA_NATIVE_EXPERTS=ON',
         '-DSTRATA_GGML_DIR=D:/ds4_work/strata/Strata/third_party/llama.cpp',
         '-DFETCHCONTENT_FULLY_DISCONNECTED=ON', f'-DPython3_EXECUTABLE={PY}'], 'configure')
targets = [x for x in sys.argv[1:] if not x.startswith('--')]
if targets:
    run([CM/'cmake.exe', '--build', B, '--parallel', '2', '--target', *targets], 'build-'+'-'.join(targets))
