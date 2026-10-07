"""Fork lab build for both cards: RTX 2080 Ti (sm_75) + RTX 3060 on Oculink (sm_86).

    python build_7586.py            configure (first time) and build strata into Strata-2080Ti-core/build-sm7586

Same configuration as the Daily's builds (Release, CUDA 12.6 shared runtime, native experts, the Daily's llama.cpp,
no network), CMAKE_CUDA_ARCHITECTURES "75;86", tests off.  Prints the tail of the output and the exe's sha256.
"""
import hashlib, os, subprocess, sys
from pathlib import Path

SRC = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
BUILD = SRC / 'build-sm7586'
D = Path(r'D:\ds4_work\strata\Strata')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')

env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
p = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"', capture_output=True,
                   text=True, encoding='cp1252', errors='replace', env=env, creationflags=subprocess.CREATE_NO_WINDOW)
for line in p.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k, v = line.split('=', 1)
        env[k] = v
env = {k: v for k, v in env.items() if not k.upper().startswith('STRATA_')}
env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')


def run(cmd):
    r = subprocess.run([str(x) for x in cmd], env=env, capture_output=True, text=True, errors='replace')
    print((r.stdout + r.stderr)[-3000:], 'rc', r.returncode, flush=True)
    if r.returncode:
        sys.exit(r.returncode)


if not (BUILD / 'CMakeCache.txt').exists():
    run([CM / 'CMake/bin/cmake.exe', '-S', SRC, '-B', BUILD, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
         f'-DCMAKE_MAKE_PROGRAM={CM / "Ninja/ninja.exe"}', f'-DCMAKE_CUDA_COMPILER={CUDA / "bin/nvcc.exe"}',
         '-DCMAKE_CUDA_ARCHITECTURES=75;86', '-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc',
         '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared', '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF',
         '-DSTRATA_BUILD_TESTS=OFF', '-DSTRATA_NATIVE_EXPERTS=ON',
         f'-DSTRATA_GGML_DIR={(D / "third_party/llama.cpp").as_posix()}', '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
         f'-DPython3_EXECUTABLE={sys.executable}'])
run([CM / 'CMake/bin/cmake.exe', '--build', BUILD, '--parallel', '1', '--target', 'strata'])
print('sha256', hashlib.sha256((BUILD / 'strata.exe').read_bytes()).hexdigest())
