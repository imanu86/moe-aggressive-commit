"""Daily 0.1.39, step 2: the shipping SM75 build from the frozen source, its parity checks and the server tests.

Same configuration as the 0.1.38 Daily (Release, sm_75, shared CUDA runtime, native experts, tests on, the Daily's
vendored llama.cpp at the pinned 3cf03257).  No QA variant: the teacher-forcing readout (STRATA_LOGPOS) is in main,
off unless its variable is set.  Each step's log is kept beside this script.
"""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0139_20261005'
S = R / 'source'
D = Path(r'D:\ds4_work\strata\Strata')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
GGUF = r'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'
JOBS = os.environ.get('BUILD0139_JOBS', '4')

env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
p = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"', capture_output=True,
                   text=True, encoding='cp1252', errors='replace', env=env, creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode == 0
for line in p.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k, v = line.split('=', 1); env[k] = v
env = {k: v for k, v in env.items() if not k.upper().startswith('STRATA_')}
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')
steps = {}


def run(cmd, name, cwd=R, timeout=5400):
    print(time.strftime('%H:%M:%S'), name, flush=True)
    t0 = time.monotonic()
    with (R / (name + '.log')).open('w', encoding='utf-8') as f:
        q = subprocess.run([str(x) for x in cmd], cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    steps[name] = dict(rc=q.returncode, seconds=round(time.monotonic() - t0, 1))
    if q.returncode:
        print((R / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-6000:])
    assert q.returncode == 0, name


cmake_text = (S / 'CMakeLists.txt').read_text(encoding='utf-8-sig')
targets = ['strata', 'qsa_topk_active_parity', 'gr_parity', 'gdn_parity', 'pool_quant_parity', 'router_dot_parity',
           'expert_cache_elastic_test', 'expert_cache_per_layer_test', 'expert_profile_save_test']
targets = [t for t in targets if f'add_executable({t} ' in cmake_text or f'add_executable({t}\n' in cmake_text or t == 'strata']
print('targets', targets, flush=True)
run([CM / 'CMake/bin/cmake.exe', '-S', S, '-B', R / 'build', '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
     f'-DCMAKE_MAKE_PROGRAM={CM / "Ninja/ninja.exe"}', f'-DCMAKE_CUDA_COMPILER={CUDA / "bin/nvcc.exe"}',
     '-DCMAKE_CUDA_ARCHITECTURES=75', '-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared',
     '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF', '-DSTRATA_BUILD_TESTS=ON', '-DSTRATA_PARITY_PROMPT_ATTN=ON',
     '-DSTRATA_NATIVE_EXPERTS=ON', f'-DSTRATA_GGML_DIR={(D / "third_party/llama.cpp").as_posix()}',
     '-DFETCHCONTENT_FULLY_DISCONNECTED=ON', f'-DPython3_EXECUTABLE={sys.executable}'], 'configure')
run([CM / 'CMake/bin/cmake.exe', '--build', R / 'build', '--parallel', JOBS, '--target', *targets], 'build')
exe = R / 'strata.exe'
shutil.copy2(R / 'build/strata.exe', exe)
tests = [t for t in targets if t not in ('strata', 'pool_quant_parity')]
run([CM / 'CMake/bin/ctest.exe', '--test-dir', R / 'build', '--output-on-failure', '-R', '^(' + '|'.join(tests) + ')'], 'ctest')
run([R / 'build/pool_quant_parity.exe', GGUF], 'pool-quant-parity')
code = ("import sys,runpy; sys.path.insert(0,r'D:\\ds4_work\\strata\\Strata\\.venv\\Lib\\site-packages'); "
        "sys.argv=['unittest','discover','-s','serve','-p','test_*.py','-t','.']; runpy.run_module('unittest',run_name='__main__')")
run([sys.executable, '-B', '-u', '-X', 'utf8', '-c', code], 'server-tests', cwd=S, timeout=900)
result = dict(fork_head=json.loads((R / 'preparation.json').read_text())['fork_head'],
              shipping_exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), targets=targets, steps=steps,
              configure='Release sm_75, CUDA 12.6 shared runtime, native experts, tests on, llama.cpp 3cf03257')
(R / 'build.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print('BUILD READY', result['shipping_exe_sha256'], flush=True)
