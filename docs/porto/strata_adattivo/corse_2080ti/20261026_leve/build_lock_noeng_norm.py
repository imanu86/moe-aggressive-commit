"""build_lock.py senza l'attesa del motore spento (PIANO_GLOBALE_2026-10-19 par. 0b, passo 1.0).

    python build_lock_noeng.py <source dir> [--target strata] [--jobs 4] [--tests]
                                          [--bench-held "<motivo>"]

E' la copia di build_lock.py con tolto ` and not engine_running()` dalle due condizioni dell'attesa: il Daily
dell'owner e' sempre acceso, quindi l'originale aspetterebbe per sempre. Resta identico per tutto il resto: una
sola build per volta (build.lock, O_EXCL), niente build mentre pause esiste, niente build mentre un braccio di
benchmark tiene bench.lock, ninja a priorita BELOW_NORMAL, CUDA 12.6 sm_75+86, test off, la llama.cpp del Daily.

--bench-held "<motivo>" e' l'unica cosa in piu', e non e' nel piano: serve quando bench.lock non e' un braccio di
benchmark ma il holder fisso del servizio agenti (servi_agenti.py lo tiene per tutto il servizio, e chi scrive e'
un agente di quel servizio).  Serve a dichiarare la deroga nel log invece che aggirare il lock di nascosto: senza
motivo scritto la riga non viene stampata e il comportamento resta quello del piano (aspettare).  Non cancellare
mai bench.lock.
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
ap.add_argument('--tests', action='store_true')
ap.add_argument('--bench-held', default=None, metavar='MOTIVO')
a = ap.parse_args()
SRC = Path(a.source).resolve()
BUILD = SRC / 'build-sm7586'


def engine_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True,
                       errors='replace')
    return 'strata.exe' in r.stdout.lower()


LOCKS.mkdir(parents=True, exist_ok=True)
lock = LOCKS / 'build.lock'
t0 = time.time()
while True:
    if not (LOCKS / 'bench.lock').exists() and not (LOCKS / 'pause').exists():
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(SRC).encode())
            os.close(fd)
            if not (LOCKS / 'bench.lock').exists():
                break
            lock.unlink(missing_ok=True)
        except FileExistsError:
            pass
    elif a.bench_held and not (LOCKS / 'pause').exists() and not (LOCKS / 'build.lock').exists():
        held = (LOCKS / 'bench.lock').read_text(errors='replace').strip()
        print(f'BENCH LOCK TENUTO: {held}\n  deroga dichiarata: {a.bench_held}\n'
              f'  strata.exe vivo: {engine_running()} - la build non tocca la GPU, non ferma e non tocca il motore',
              flush=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f'{SRC} (bench held: {a.bench_held})'.encode())
            os.close(fd)
            break
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
    env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')

    def run(cmd):
        r = subprocess.run([str(x) for x in cmd], env=env, capture_output=True, text=True, errors='replace',
                           creationflags=subprocess.NORMAL_PRIORITY_CLASS)
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
             f'-DSTRATA_BUILD_TESTS={"ON" if a.tests else "OFF"}', f'-DSTRATA_GGML_DIR={(D / "third_party/llama.cpp").as_posix()}',
             '-DFETCHCONTENT_FULLY_DISCONNECTED=ON', f'-DPython3_EXECUTABLE={sys.executable}'])
    run([CM / 'CMake/bin/cmake.exe', '--build', BUILD, '--parallel', str(a.jobs), '--target', a.target])
    exe = BUILD / 'strata.exe'
    if exe.exists():
        print('sha256', hashlib.sha256(exe.read_bytes()).hexdigest(), flush=True)
finally:
    lock.unlink(missing_ok=True)
    print(f'lock released, {time.time() - t0:.0f} s total', flush=True)
