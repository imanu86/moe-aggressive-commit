"""Elastic-cache PR resubmitted on the new upstream main (branch contrib/elastic-core-040, worktree
C:\\Users\\imanu\\source\\repos\\Strata-elastic-pr): build strata and the cache tests in this folder's build dir
(Release, sm_75, the Daily's llama.cpp), run the cache CTests, stage the exe as 20261004_routed_keep/build-epr040.
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent
W = Path(r'C:\Users\imanu\source\repos\Strata-elastic-pr')
BUILD = B / 'build'
K = B.parent / '20261004_routed_keep'
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


def run(cmd, name):
    with (B / (name + '.log')).open('w', encoding='utf-8') as f:
        r = subprocess.run([str(x) for x in cmd], cwd=B, env=env, stdout=f, stderr=subprocess.STDOUT)
    tail = (B / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-2500:]
    print(name, 'rc', r.returncode, flush=True)
    if r.returncode:
        print(tail)
        sys.exit(r.returncode)
    return tail


head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=W, text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=W, text=True).strip()
tests = ['expert_cache_elastic_test', 'expert_cache_per_layer_test', 'expert_profile_save_test', 'expert_cache_segmented_test']
run([CM / 'CMake/bin/cmake.exe', '-S', W, '-B', BUILD, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
     f'-DCMAKE_MAKE_PROGRAM={CM / "Ninja/ninja.exe"}', f'-DCMAKE_CUDA_COMPILER={CUDA / "bin/nvcc.exe"}',
     '-DCMAKE_CUDA_ARCHITECTURES=75', '-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared',
     '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF', '-DSTRATA_BUILD_TESTS=ON', '-DSTRATA_NATIVE_EXPERTS=ON',
     f'-DSTRATA_GGML_DIR={(D / "third_party/llama.cpp").as_posix()}', '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
     f'-DPython3_EXECUTABLE={sys.executable}'], 'configure040')
run([CM / 'CMake/bin/cmake.exe', '--build', BUILD, '--parallel', '8', '--target', 'strata', *tests], 'build040')
print(run([CM / 'CMake/bin/ctest.exe', '--test-dir', BUILD, '--output-on-failure', '-R', '^(' + '|'.join(tests) + ')$'],
          'ctest040')[-700:])
dst = K / 'build-epr040'
dst.mkdir(exist_ok=True)
shutil.copy2(BUILD / 'strata.exe', dst / 'strata.exe')
h = hashlib.sha256((dst / 'strata.exe').read_bytes()).hexdigest()
(dst / 'build.json').write_text(json.dumps(dict(status='completed', executable_sha256=h,
                                                note=f'contrib/elastic-core-040 {head[:8]} (upstream main 82f46a8 + --elastic)'),
                                           indent=2) + '\n', encoding='utf-8')
print('READY', head[:8], h[:12])
