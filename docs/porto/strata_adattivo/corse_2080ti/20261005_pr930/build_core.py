"""Build targets of the fork's lab build (Strata-2080Ti-core/build-sm75, Release, sm_75, tests on).

    python build_core.py <target> [<target> ...]
"""
import os, subprocess, sys

VC = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
CM = r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
BUILD = r'C:\Users\imanu\source\repos\Strata-2080Ti-core\build-sm75'
env = {k.upper(): v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
out = subprocess.run(f'cmd.exe /d /s /c "call "{VC}" >nul && set"', capture_output=True, text=True, encoding='cp1252',
                     errors='replace', env=env)
for line in out.stdout.splitlines():
    if '=' in line and not line.startswith('='):
        k, v = line.split('=', 1)
        env[k.upper()] = v
env['PATH'] = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin' + os.pathsep + env['PATH']
r = subprocess.run([CM, '--build', BUILD, '--parallel', '8', '--target', *sys.argv[1:]], env=env, capture_output=True,
                   text=True, errors='replace')
print(r.stdout[-2500:], r.stderr[-1200:], 'rc', r.returncode)
sys.exit(r.returncode)
