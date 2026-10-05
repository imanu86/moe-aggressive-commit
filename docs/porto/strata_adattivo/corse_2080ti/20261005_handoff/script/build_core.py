"""Configure + build strata.exe in the core-adapt worktree at below-normal priority; copy the exe into a pinned lab dir."""
import hashlib, json, os, shutil, subprocess, time
from pathlib import Path

W = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
B = W / 'build-sm75'
OUT = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-core1')
VC = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
CM = r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
NINJA = r'C:\Users\imanu\AppData\Local\Programs\Python\Python312\Scripts\ninja.exe'
CUDA = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6'
BELOW = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS, inherited by ninja/cl/nvcc

env = {k.upper(): v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
out = subprocess.run(f'cmd.exe /d /s /c "call "{VC}" >nul && set"', capture_output=True, text=True, encoding='cp1252',
                     errors='replace', env=env)
for line in out.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k, v = line.split('=', 1); env[k.upper()] = v
env['PATH'] = CUDA + r'\bin' + os.pathsep + env['PATH']
OUT.mkdir(parents=True, exist_ok=False)
t0 = time.monotonic()
with (OUT / 'build.log').open('wb') as log:
    cmds = [[CM, '-S', str(W), '-B', str(B), '-G', 'Ninja', f'-DCMAKE_MAKE_PROGRAM={NINJA}', '-DCMAKE_BUILD_TYPE=Release',
             '-DCMAKE_CUDA_ARCHITECTURES=75', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared', f'-DCMAKE_CUDA_COMPILER={CUDA}/bin/nvcc.exe',
             '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_NATIVE_EXPERTS=ON', '-DSTRATA_BUILD_CLOSED_PROBE=ON', '-DSTRATA_BUILD_CONVERSATION_TESTS=ON', '-DSTRATA_BUILD_NEURON_REPLAY=ON',
             '-DSTRATA_PARITY_POOL_QUANT=ON'],
            [CM, '--build', str(B), '--parallel', '8', '--target', 'strata']]
    for c in cmds:
        rc = subprocess.run(c, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=BELOW).returncode
        if rc:
            break
state = {'worktree': str(W), 'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=W, text=True).strip(),
         'diff': subprocess.check_output(['git', 'diff', '--stat'], cwd=W, text=True),
         'elapsed_s': time.monotonic() - t0, 'status': 'completed' if rc == 0 else f'failed rc={rc}'}
if rc == 0:
    shutil.copy2(B / 'strata.exe', OUT / 'strata.exe')
    state['executable_sha256'] = hashlib.sha256((OUT / 'strata.exe').read_bytes()).hexdigest()
(OUT / 'build.json').write_text(json.dumps(state, indent=2) + '\n')
print('FINISHED', state['status'], round(state['elapsed_s']))
