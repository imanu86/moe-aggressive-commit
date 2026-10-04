"""Incremental lab build of strata.exe with the STRATA_ROUTED_KEEP probe; immutable output folder."""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

F = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
B = F / 'build-sm75-547-msvc'
L = Path(__file__).resolve().parent
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
git = lambda *a: subprocess.check_output(['git', *a], cwd=F, text=True).strip()


def main(name):
    out = L / name
    assert not out.exists() and git('branch', '--show-current') == 'main'
    out.mkdir()
    env = {k.upper(): v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
    setup = subprocess.run(f'cmd.exe /d /s /c "call "{VC}" >nul && set"', capture_output=True, text=True,
                           encoding='cp1252', errors='replace', env=env, timeout=60)
    assert setup.returncode == 0
    for line in setup.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            k, v = line.split('=', 1); env[k.upper()] = v
    env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')
    state = {'source_commit': git('rev-parse', 'HEAD'), 'diff': git('diff', '--stat'),
             'diff_sha256': hashlib.sha256(git('diff').encode()).hexdigest()}
    t0 = time.monotonic()
    with (out / 'build.log').open('wb') as log:
        rc = subprocess.run([str(CM), '--build', str(B), '--parallel', '4', '--target', 'strata'],
                            env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    state['elapsed_s'] = time.monotonic() - t0
    state['status'] = 'completed' if rc == 0 else f'failed rc={rc}'
    if rc == 0:
        shutil.copy2(B / 'strata.exe', out / 'strata.exe')
        state['executable_sha256'] = sha(out / 'strata.exe')
    (out / 'build.json').write_text(json.dumps(state, indent=2) + '\n')
    print('FINISHED', state['status'], round(state['elapsed_s'], 1))


if __name__ == '__main__':
    main(sys.argv[1])
