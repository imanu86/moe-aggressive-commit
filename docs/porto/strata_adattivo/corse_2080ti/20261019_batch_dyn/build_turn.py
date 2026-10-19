"""Compila una worktree con i passi di ../20261006_due_schede/build_lock.py, prendendo il TURNO del laboratorio.

    python build_turn.py <source dir> [--target strata] [--jobs 6]

Il 19/10 le code concatenano i bracci senza pause (bab.py di seq.py riprende bench.lock entro un secondo e non guarda
build.lock), quindi build_lock.py, che aspetta bench.lock libero, non trova mai il varco.  Qui: appena non c'e' pause, nessun
strata.exe gira e build.lock e' libero, prende bench.lock (O_EXCL, la GPU resta ferma per tutti durante la compilazione) e poi
build.lock; compila (stessi argomenti di cmake, priorita' sotto il normale) e rilascia entrambi.  Mai priorita' alta.
"""
import argparse, hashlib, os, subprocess, sys, time
from pathlib import Path

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
D = Path(r'D:\ds4_work\strata\Strata')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')

ap = argparse.ArgumentParser()
ap.add_argument('source')
ap.add_argument('--target', default='strata')
ap.add_argument('--jobs', type=int, default=6)
a = ap.parse_args()
SRC = Path(a.source).resolve()
BUILD = SRC / 'build-sm7586'


def engine_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True, errors='replace')
    return 'strata.exe' in r.stdout.lower()


def excl(p, text):
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, text.encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


t0 = time.time()
# prenotazione (come turno.py): build.lock, poi bench.lock appena il braccio in corso lo rilascia
while (LOCKS / 'pause').exists() or not excl(LOCKS / 'build.lock', str(SRC)):
    time.sleep(0.5)
while (LOCKS / 'pause').exists() or (LOCKS / 'bench.lock').exists() or engine_running() or         not excl(LOCKS / 'bench.lock', f'BUILD-{SRC.name}'):
    time.sleep(0.25)
print(f'turno preso dopo {time.time() - t0:.0f} s', flush=True)
try:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
    p = subprocess.run(f'cmd.exe /d /s /c "call "{VC / "Auxiliary/Build/vcvars64.bat"}" >nul && set"',
                       capture_output=True, text=True, encoding='cp1252', errors='replace', env=env,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    for line in p.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            k, v = line.split('=', 1)
            env[k] = v
    env = {k: v for k, v in env.items() if not k.upper().startswith('STRATA_')}
    env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')

    def run(cmd):
        r = subprocess.run([str(x) for x in cmd], env=env, capture_output=True, text=True, errors='replace',
                           creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        out = r.stdout + r.stderr
        errs = [l for l in out.splitlines() if 'error' in l.lower()]
        print('\n'.join(errs[:60]), flush=True)
        print('\n'.join(out.splitlines()[-25:]), '\nrc', r.returncode, flush=True)
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
    run([CM / 'CMake/bin/cmake.exe', '--build', BUILD, '--parallel', str(a.jobs), '--target', a.target])
    exe = BUILD / 'strata.exe'
    if exe.exists():
        print('sha256', hashlib.sha256(exe.read_bytes()).hexdigest(), flush=True)
finally:
    (LOCKS / 'build.lock').unlink(missing_ok=True)
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
    print(f'turno rilasciato, {time.time() - t0:.0f} s in tutto', flush=True)
