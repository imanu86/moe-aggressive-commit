"""CPU-only lab builds beside build_lock.py, taking the same build.lock: strata-vision (encoder on the CPU) or llama-quantize.

    python build_lock_cpu.py <strata source dir> --project vision|quantize [--jobs 6]

vision:   <source>/tools/vision -> <source>/build-vision-cpu, target strata-vision, STRATA_VISION_CUDA=OFF,
          STRATA_PORTABLE=OFF (this PC's ISA, as setup.py builds it), the Daily's llama.cpp (same pinned commit).
quantize: the Daily's llama.cpp -> <source>/build-llama-cpu, target llama-quantize, no CUDA, no server/tests/examples.

Waits until bench.lock and pause do not exist and no strata.exe runs, then holds build.lock (O_EXCL) while it builds,
at below-normal priority.  Out-of-source: nothing is written into the Daily's llama.cpp folder.
"""
import argparse, hashlib, os, subprocess, sys, time
from pathlib import Path

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
LLAMA = Path(r'D:\ds4_work\strata\Strata\third_party\llama.cpp')
VC = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')

ap = argparse.ArgumentParser()
ap.add_argument('source')
ap.add_argument('--project', choices=['vision', 'quantize'], required=True)
ap.add_argument('--jobs', type=int, default=6)
a = ap.parse_args()
SRC = Path(a.source).resolve()
if a.project == 'vision':
    CSRC, BUILD, TARGET = SRC / 'tools' / 'vision', SRC / 'build-vision-cpu', 'strata-vision'
    DEFS = [f'-DLLAMA_DIR={LLAMA.as_posix()}', '-DSTRATA_VISION_CUDA=OFF', '-DSTRATA_PORTABLE=OFF']
    OUT = BUILD / 'bin' / 'strata-vision.exe'
else:
    CSRC, BUILD, TARGET = LLAMA, SRC / 'build-llama-cpu', 'llama-quantize'
    DEFS = ['-DGGML_CUDA=OFF', '-DGGML_NATIVE=ON', '-DBUILD_SHARED_LIBS=OFF', '-DLLAMA_BUILD_TESTS=OFF',
            '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_SERVER=OFF', '-DLLAMA_BUILD_APP=OFF', '-DLLAMA_BUILD_UI=OFF',
            '-DLLAMA_OPENSSL=OFF', '-DLLAMA_CURL=OFF']
    OUT = BUILD / 'bin' / 'llama-quantize.exe'


def engine_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True,
                       errors='replace')
    return 'strata.exe' in r.stdout.lower()


LOCKS.mkdir(parents=True, exist_ok=True)
lock = LOCKS / 'build.lock'
t0 = time.time()
while True:
    if not (LOCKS / 'bench.lock').exists() and not (LOCKS / 'pause').exists() and not engine_running():
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f'{SRC} {a.project}'.encode())
            os.close(fd)
            if not (LOCKS / 'bench.lock').exists() and not (LOCKS / 'pause').exists() and not engine_running():
                break
            lock.unlink(missing_ok=True)
        except FileExistsError:
            pass
    time.sleep(10)
print(f'lock taken after {time.time() - t0:.0f} s', flush=True)
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
        run([CM / 'CMake/bin/cmake.exe', '-S', CSRC, '-B', BUILD, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             f'-DCMAKE_MAKE_PROGRAM={CM / "Ninja/ninja.exe"}', *DEFS])
    run([CM / 'CMake/bin/cmake.exe', '--build', BUILD, '--parallel', str(a.jobs), '--target', TARGET])
    if OUT.exists():
        print('exe', OUT, 'sha256', hashlib.sha256(OUT.read_bytes()).hexdigest(), flush=True)
finally:
    lock.unlink(missing_ok=True)
    print(f'lock released, {time.time() - t0:.0f} s total', flush=True)
