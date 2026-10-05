"""Configure/build/test the port/0139 tree in its own build dir (never the lab or Daily ones).

usage: build_0139.py configure | build [targets...] | ctest [ctest args...] | run <exe> [args...]
Every step first waits (30 s polls, up to 30 min) until no strata.exe runs on this machine.
"""
import os, subprocess, sys, time

SRC = r'C:\Users\imanu\source\repos\Strata-2080Ti'
BUILD = r'C:\Users\imanu\source\repos\Strata-2080Ti\build-sm75-0139'
VC = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
CM_DIR = r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin'
CM = os.path.join(CM_DIR, 'cmake.exe')
CT = os.path.join(CM_DIR, 'ctest.exe')
CUDA_BIN = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'
NINJA = r'C:\Users\imanu\AppData\Local\Programs\Python\Python312\Scripts\ninja.exe'
BELOW = 0x00004000   # BELOW_NORMAL_PRIORITY_CLASS (inherited by ninja, cl, nvcc)
GGML = 'D:/ds4_work/strata/Strata/third_party/llama.cpp'   # read only, as the lab build


def strata_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True,
                       errors='replace')
    return 'strata.exe' in r.stdout.lower()


def commit_free_gib():
    import ctypes

    class M(ctypes.Structure):
        _fields_ = [('l', ctypes.c_ulong), ('ld', ctypes.c_ulong), ('tp', ctypes.c_ulonglong),
                    ('ap', ctypes.c_ulonglong), ('tf', ctypes.c_ulonglong), ('af', ctypes.c_ulonglong),
                    ('tv', ctypes.c_ulonglong), ('av', ctypes.c_ulonglong), ('ae', ctypes.c_ulonglong)]
    m = M()
    m.l = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.af / 2 ** 30


def wait_idle():
    t0 = time.time()
    while True:
        busy, free = strata_running(), commit_free_gib()
        if not busy and free >= 60:
            print(f'idle: no strata.exe, commit free {free:.1f} GiB', flush=True)
            return
        if time.time() - t0 > 30 * 60:
            print(f'not idle after 30 min (strata.exe={busy}, commit free {free:.1f} GiB): giving up', flush=True)
            sys.exit(3)
        print(f'waiting 30 s (strata.exe={busy}, commit free {free:.1f} GiB)', flush=True)
        time.sleep(30)


def env():
    e = {k.upper(): v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
    out = subprocess.run(f'cmd.exe /d /s /c "call "{VC}" >nul && set"', capture_output=True, text=True,
                         encoding='cp1252', errors='replace', env=e)
    for line in out.stdout.splitlines():
        if '=' in line and not line.startswith('='):
            k, v = line.split('=', 1)
            e[k.upper()] = v
    e['PATH'] = CUDA_BIN + os.pathsep + e['PATH']
    return e


def run(cmd, e, log=None):
    print('>', ' '.join(cmd), flush=True)
    if log:
        with open(log, 'w', encoding='utf-8', errors='replace') as f:
            r = subprocess.run(cmd, env=e, stdout=f, stderr=subprocess.STDOUT, text=True, errors='replace',
                               creationflags=BELOW)
    else:
        r = subprocess.run(cmd, env=e, creationflags=BELOW)
    print('rc', r.returncode, flush=True)
    return r.returncode


def main():
    step = sys.argv[1]
    wait_idle()
    e = env()
    if step == 'configure':
        os.makedirs(BUILD, exist_ok=True)
        return run([CM, '-S', SRC, '-B', BUILD, '-G', 'Ninja', f'-DCMAKE_MAKE_PROGRAM={NINJA}',
                    '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CUDA_ARCHITECTURES=75', '-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared',
                    f'-DCMAKE_CUDA_COMPILER={CUDA_BIN}/nvcc.exe'.replace('\\', '/'),
                    '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_ENABLE_HIP=OFF', '-DSTRATA_NATIVE_EXPERTS=ON',
                    '-DSTRATA_BUILD_TESTS=' + os.environ.get('TESTS', 'OFF'), '-DSTRATA_BUILD_CLOSED_PROBE=ON', '-DSTRATA_BUILD_NEURON_REPLAY=ON',
                    '-DSTRATA_BUILD_CONVERSATION_TESTS=ON', '-DSTRATA_PARITY_POOL_QUANT=ON',
                    f'-DSTRATA_GGML_DIR={GGML}', f'-DSTRATA_PLE_FIXTURE_DIR={SRC}/bench/micro'.replace('\\', '/')],
                   e, os.path.join(BUILD, '..', 'build-sm75-0139-configure.log') if False else None)
    if step == 'build':
        targets = sys.argv[2:]
        cmd = [CM, '--build', BUILD, '--parallel', os.environ.get('JOBS', '8')]
        if targets:
            cmd += ['--target', *targets]
        cmd += ['--', '-k', '0']
        return run(cmd, e, os.path.join(BUILD, 'build.log'))
    if step == 'ctest':
        return run([CT, '--test-dir', BUILD, '--output-on-failure', *sys.argv[2:]], e,
                   os.path.join(BUILD, 'ctest.log'))
    if step == 'run':
        exe = sys.argv[2]
        if not os.path.isabs(exe):
            exe = os.path.join(BUILD, exe)
        return run([exe, *sys.argv[3:]], e)
    print('unknown step', step)
    return 2


if __name__ == '__main__':
    sys.exit(main())

