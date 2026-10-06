"""Pure upstream 0.1.40 (tag v0.1.40, exported with git archive - no checkout, no branch) built with the Daily's
configuration (Release, sm_75, CUDA 12.6 shared runtime, native experts, llama.cpp of the Daily) and staged as
20261004_routed_keep/build-up0140: the reference that tells upstream's own numeric changes from the merge's.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, time
from pathlib import Path

B = Path(__file__).resolve().parent
REPO = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
SRC = Path(r'D:\ds4_work\strata\src_up0140')
BUILD = Path(r'D:\ds4_work\strata\build_up0140')
K = B.parent / '20261004_routed_keep'
D = Path(r'D:\ds4_work\strata\Strata')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
TAG = 'v0.1.40'

env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
p = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"', capture_output=True,
                   text=True, encoding='cp1252', errors='replace', env=env, creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode == 0
for line in p.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k, v = line.split('=', 1)
        env[k] = v
env = {k: v for k, v in env.items() if not k.upper().startswith('STRATA_')}
env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')


def run(cmd, name, timeout=5400):
    print(time.strftime('%H:%M:%S'), name, flush=True)
    with (B / (name + '.log')).open('w', encoding='utf-8') as f:
        q = subprocess.run([str(x) for x in cmd], cwd=B, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    if q.returncode:
        print((B / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-6000:])
    assert q.returncode == 0, name


commit = subprocess.check_output(['git', 'rev-parse', TAG + '^{commit}'], cwd=REPO, text=True).strip()
if not SRC.exists():
    tar = subprocess.check_output(['git', '-c', 'core.autocrlf=false', 'archive', '--format=tar', TAG], cwd=REPO)
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(SRC, filter='tar')
run([CM / 'CMake/bin/cmake.exe', '-S', SRC, '-B', BUILD, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
     f'-DCMAKE_MAKE_PROGRAM={CM / "Ninja/ninja.exe"}', f'-DCMAKE_CUDA_COMPILER={CUDA / "bin/nvcc.exe"}',
     '-DCMAKE_CUDA_ARCHITECTURES=75', '-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared',
     '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF', '-DSTRATA_BUILD_TESTS=OFF', '-DSTRATA_NATIVE_EXPERTS=ON',
     f'-DSTRATA_GGML_DIR={(D / "third_party/llama.cpp").as_posix()}', '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
     f'-DPython3_EXECUTABLE={sys.executable}'], 'configure_up0140')
run([CM / 'CMake/bin/cmake.exe', '--build', BUILD, '--parallel', '8', '--target', 'strata'], 'build_up0140')
dst = K / 'build-up0140'
dst.mkdir(exist_ok=True)
shutil.copy2(BUILD / 'strata.exe', dst / 'strata.exe')
h = hashlib.sha256((dst / 'strata.exe').read_bytes()).hexdigest()
(dst / 'build.json').write_text(json.dumps(dict(status='completed', executable_sha256=h,
                                                note=f'pure upstream 0.1.40 {commit[:8]} (git archive), build of 20261006_allineamento040'),
                                           indent=2) + '\n', encoding='utf-8')
print('READY up0140', h[:12], flush=True)
