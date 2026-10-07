"""Run any GPU command (teacher forcing, a short strata probe) holding the lab's exclusive bench.lock.

    python bench_lock.py <name> -- <command> [args...]

Waits for no build.lock and no other bench.lock (run_long.py arms take the same lock) and no strata.exe running,
then runs the command and releases the lock.  Exit code is the command's.
"""
import os, subprocess, sys, time
from pathlib import Path

LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
name = sys.argv[1]
cmd = sys.argv[sys.argv.index('--') + 1:]


def engine_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True,
                       errors='replace')
    return 'strata.exe' in r.stdout.lower()


LOCKS.mkdir(parents=True, exist_ok=True)
t0 = time.time()
while True:
    if not (LOCKS / 'build.lock').exists() and not (LOCKS / 'pause').exists() and not engine_running():
        try:
            fd = os.open(LOCKS / 'bench.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, name.encode())
            os.close(fd)
            break
        except FileExistsError:
            pass
    time.sleep(10)
print(f'bench lock taken after {time.time() - t0:.0f} s', flush=True)
try:
    rc = subprocess.run(cmd).returncode
finally:
    (LOCKS / 'bench.lock').unlink(missing_ok=True)
sys.exit(rc)
