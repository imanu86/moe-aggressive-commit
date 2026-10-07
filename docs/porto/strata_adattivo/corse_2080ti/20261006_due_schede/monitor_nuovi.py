"""One line per arm that finishes after this monitor starts (any agent's arm): t/s, ms/window, tokens/window, text.

    python monitor_nuovi.py [PREFIX ...]     (only arms whose name starts with one of the prefixes; default all)
Runs until killed.  Uses monitor_giri's arm_line.
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import monitor_giri as M   # noqa: E402  (its main loop only runs with arms on argv; guarded below)

prefixes = tuple(sys.argv[1:])
start = time.time()
seen = set()
while True:
    for d in M.K.iterdir():
        r = d / 'result.json'
        if d.name in seen or not r.exists() or r.stat().st_mtime < start:
            continue
        if prefixes and not d.name.startswith(prefixes):
            continue
        seen.add(d.name)
        line = M.arm_line(d.name)
        s = (d / 'engine.log').read_text(encoding='utf-8', errors='replace') if (d / 'engine.log').exists() else ''
        import re
        tpw = re.findall(r'([0-9.]+) tokens/window', s)
        print(time.strftime('%H:%M'), line, ('tok/fin ' + '/'.join(tpw)) if tpw else '', flush=True)
    time.sleep(30)
