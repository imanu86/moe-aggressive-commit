"""Serial queue of engine runs that never overlaps builds or other engines and waits for Windows commit headroom.

Each spec: (runner, name, args). Before a run: wait (up to 60 min) until no compiler/linker/ninja/cmake and no
strata.exe is running and the commit charge has >= 58 GiB free. A run that fails with WinError 1455 is renamed
`<name>-failed-commit` and retried once. Output: one line per run.
"""
import json, subprocess, sys, time
from pathlib import Path
import psutil

L = Path(__file__).resolve().parent
sys.path.insert(0, str(L))
from run_keep import commit_free_gib

BUSY = ('nvcc', 'cl', 'link', 'ninja', 'cmake', 'cicc', 'ptxas', 'strata')


def busy():
    names = set()
    for p in psutil.process_iter(['name']):
        n = (p.info.get('name') or '').lower().removesuffix('.exe')
        if n in BUSY:
            names.add(n)
    return names


def wait_ready(deadline_s=3600):
    t0 = time.monotonic()
    while time.monotonic() - t0 < deadline_s:
        b = busy()
        c = commit_free_gib()
        if not b and c >= 58:
            time.sleep(20)                      # let a just-finished process release its memory
            if not busy() and commit_free_gib() >= 58:
                return True
        time.sleep(15)
    return False


def summary(name):
    r = json.loads((L / name / 'result.json').read_text(encoding='utf-8'))
    if 'requests' in r:
        return r['status'], [round(q['decode_tps'], 1) for q in r['requests']]
    last = r.get('last') or {}
    tps = last['generated'] / last['decode_ms'] * 1000 if last.get('decode_ms') else None
    return r['status'], round(tps, 1) if tps else None, r.get('error', '')[:120]


def run(runner, name, args):
    for attempt in (1, 2):
        if not wait_ready():
            print(f'{name}: macchina mai libera in 60 min, salto', flush=True)
            return
        p = subprocess.run([sys.executable, '-u', runner, '--name', name, *args], cwd=L, capture_output=True, text=True,
                           errors='replace', timeout=2400)
        failed_commit = '1455' in (p.stdout + p.stderr)
        if (L / name / 'result.json').exists() and not failed_commit:
            print(name, *summary(name), flush=True)
            return
        if (L / name).exists():
            (L / name).rename(L / f'{name}-failed-commit{attempt}' if failed_commit else L / f'{name}-failed{attempt}')
        print(f'{name}: fallito (tentativo {attempt}, commit={failed_commit}) {p.stderr[-200:]}', flush=True)
        if not failed_commit:
            return


if __name__ == '__main__':
    specs = json.loads(Path(sys.argv[1]).read_text())
    for runner, name, args in specs:
        run(runner, name, args)
    print('ORCHESTRA-DONE', flush=True)
