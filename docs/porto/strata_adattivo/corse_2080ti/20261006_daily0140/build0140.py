"""Daily 0.1.40-r1, passo 2: la build SM75 shipping dal sorgente congelato.

Stessa configurazione del Daily 0.1.39-r2 (Release, sm_75, runtime CUDA condiviso, esperti nativi, test attivi, llama.cpp
del Daily al commit 3cf03257).  Nessuna variante QA.  A differenza della r2 si compilano TUTTI i target (cosi' il
CTest completo di check0140.py ha tutti gli eseguibili, compresi quelli nuovi della 0.1.40); i test girano in
check0140.py.  Il log di ogni passo resta accanto a questo script.
"""
import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0140_20261006'
S = R / 'source'
D = Path(r'D:\ds4_work\strata\Strata')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
JOBS = os.environ.get('BUILD0140_JOBS', '6')

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


def run(cmd, name, cwd=R, timeout=3600, fatal=True):
    print(time.strftime('%H:%M:%S'), name, flush=True)
    t0 = time.monotonic()
    with (R / (name + '.log')).open('w', encoding='utf-8') as f:
        q = subprocess.run([str(x) for x in cmd], cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    steps[name] = dict(rc=q.returncode, seconds=round(time.monotonic() - t0, 1))
    if q.returncode:
        print((R / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-6000:])
    assert q.returncode == 0 or not fatal, name


prep = json.loads((R / 'preparation.json').read_text())
assert not (S / '.github/workflows').exists() or not any((S / '.github/workflows').glob('*'))
run([CM / 'CMake/bin/cmake.exe', '-S', S, '-B', R / 'build', '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
     f'-DCMAKE_MAKE_PROGRAM={CM / "Ninja/ninja.exe"}', f'-DCMAKE_CUDA_COMPILER={CUDA / "bin/nvcc.exe"}',
     '-DCMAKE_CUDA_ARCHITECTURES=75', '-DCMAKE_CUDA_FLAGS=-D_WINDOWS -Xcompiler=/EHsc', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared',
     '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF', '-DSTRATA_BUILD_TESTS=ON', '-DSTRATA_PARITY_PROMPT_ATTN=ON',
     '-DSTRATA_NATIVE_EXPERTS=ON', f'-DSTRATA_GGML_DIR={(D / "third_party/llama.cpp").as_posix()}',
     '-DFETCHCONTENT_FULLY_DISCONNECTED=ON', f'-DPython3_EXECUTABLE={sys.executable}'], 'configure')
run([CM / 'CMake/bin/ctest.exe', '--test-dir', R / 'build', '-N'], 'ctest-list')
registered = re.findall(r'^\s*Test\s+#\d+:\s*(\S+)', (R / 'ctest-list.log').read_text(encoding='utf-8', errors='replace'), re.M)
print('registered ctest tests:', len(registered), flush=True)
run([CM / 'CMake/bin/cmake.exe', '--build', R / 'build', '--parallel', JOBS], 'build', timeout=3300)
exe = R / 'strata.exe'
shutil.copy2(R / 'build/strata.exe', exe)
result = dict(fork_head=prep['fork_head'], upstream=prep['upstream'], version=prep['version'],
              shipping_exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(), ctest_registered=len(registered), steps=steps,
              configure='Release sm_75, CUDA 12.6 shared runtime, native experts, tests on, all targets, llama.cpp 3cf03257')
(R / 'build.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print('BUILD READY', result['shipping_exe_sha256'], flush=True)
