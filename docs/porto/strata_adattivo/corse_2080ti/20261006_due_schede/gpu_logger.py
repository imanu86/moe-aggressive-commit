r"""Light GPU/VRAM logger for the Strata engine on the two cards (11/10): finds what the 3060 does when decode slows.

    python gpu_logger.py --out D:\ds4_work\strata\lab_runs\gpulog-<tag> [--engine-log D:\ds4_work\strata\sota\strata_sota.log]
        [--every 1.0]

Writes, until Ctrl-C:
- gpu.csv: every `every` s, per card: time, index, pstate, SM/mem clock, power, util, mem used/total, PCIe gen/width,
  throttle reasons (one nvidia-smi process kept open with -lms, read line by line: no file buffering);
- wddm.csv: every `every` s, per adapter (LUID): dedicated and shared usage of the adapter and of strata.exe
  (Windows "GPU Adapter Memory" / "GPU Process Memory" counters, through one long-lived PowerShell);
- engine.csv: each new line of the engine log that matters (prompt/decode, elastic, expert cache, KV), stamped with the
  time it appeared, so a request can be matched to what the cards and Windows did at that moment.
Cheap: two helper processes, ~1% of one core.  Outputs are data.
"""
import argparse, csv, os, subprocess, threading, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--engine-log', default=r'D:\ds4_work\strata\sota\strata_sota.log')
ap.add_argument('--every', type=float, default=1.0)
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
stop = threading.Event()
NOW = lambda: time.strftime('%Y-%m-%d %H:%M:%S') + f'.{int(time.time() * 1000) % 1000:03d}'


def nvsmi():
    q = ('index,pstate,clocks.sm,clocks.mem,power.draw,utilization.gpu,memory.used,memory.total,'
         'pcie.link.gen.current,pcie.link.width.current,clocks_throttle_reasons.active')
    p = subprocess.Popen(['nvidia-smi', f'--query-gpu={q}', '--format=csv,noheader,nounits',
                          f'-lms={int(a.every * 1000)}'], stdout=subprocess.PIPE, text=True,
                         creationflags=0x08000000)
    with (out / 'gpu.csv').open('a', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time'] + q.split(','))
        for line in p.stdout:
            if stop.is_set():
                break
            w.writerow([NOW()] + [x.strip() for x in line.split(',')])
            f.flush()
    p.kill()


PS = r'''
$ErrorActionPreference = 'SilentlyContinue'
while ($true) {
  $s = (Get-Process strata -EA SilentlyContinue | Select-Object -First 1).Id
  $c = @('\GPU Adapter Memory(*)\Dedicated Usage','\GPU Adapter Memory(*)\Shared Usage')
  if ($s) { $c += "\GPU Process Memory(pid_$($s)_*)\Dedicated Usage"; $c += "\GPU Process Memory(pid_$($s)_*)\Shared Usage" }
  $r = Get-Counter $c -EA SilentlyContinue
  foreach ($x in $r.CounterSamples) {
    $l = if ($x.InstanceName -match 'luid_0x[0-9a-f]+_(0x[0-9a-f]+)') { $matches[1] } else { '' }
    $who = if ($x.Path -match 'gpu process memory') { 'strata' } else { 'adapter' }
    $k = if ($x.Path -match 'dedicated') { 'dedicated' } else { 'shared' }
    '{0};{1};{2};{3}' -f $l, $who, $k, [math]::Round($x.CookedValue / 1MB)
  }
  'END'
  Start-Sleep -Milliseconds INTERVAL
}
'''


def wddm():
    p = subprocess.Popen(['powershell', '-NoProfile', '-Command',
                          PS.replace('INTERVAL', str(int(a.every * 1000)))],
                         stdout=subprocess.PIPE, text=True, creationflags=0x08000000)
    with (out / 'wddm.csv').open('a', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time', 'luid', 'who', 'kind', 'mib'])
        t = NOW()
        for line in p.stdout:
            if stop.is_set():
                break
            line = line.strip()
            if line == 'END':
                f.flush()
                t = NOW()
                continue
            parts = line.split(';')
            if len(parts) == 4:
                w.writerow([t] + parts)
    p.kill()


KEYS = ('strata serve: prompt', 'strata elastic', 'expert cache', 'KV streaming', 'decode timing', 'engine started',
        'watchdog', 'error', 'ERR')


def engine():
    path = Path(a.engine_log)
    while not path.exists() and not stop.is_set():
        time.sleep(2)
    with path.open('r', encoding='utf-8', errors='replace') as src, \
            (out / 'engine.csv').open('a', newline='', encoding='utf-8') as f:
        src.seek(0, os.SEEK_END)
        w = csv.writer(f)
        w.writerow(['time', 'line'])
        while not stop.is_set():
            line = src.readline()
            if not line:
                time.sleep(0.2)
                continue
            if any(k in line for k in KEYS):
                w.writerow([NOW(), line.rstrip()[:400]])
                f.flush()


ths = [threading.Thread(target=fn, daemon=True) for fn in (nvsmi, wddm, engine)]
for t in ths:
    t.start()
print('logging in', out, '- Ctrl-C to stop', flush=True)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    stop.set()
