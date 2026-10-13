"""13/10: what reads the disks while life 2 of a ttft_bench arm starts.  python monitor_avvio.py <tag>
Waits for ttft_<tag>/engine2.log, then every 5 s for 320 s: per-disk read/write MB/s and the top processes by I/O and
CPU; writes ttft_<tag>/monitor2.txt.  Read only (psutil)."""
import sys, time
from pathlib import Path
import psutil
H = Path(__file__).resolve().parent
out_dir = H / f'ttft_{sys.argv[1]}'
log = out_dir / 'engine2.log'
t0 = time.time()
while not log.exists():
    if time.time() - t0 > 3600:
        sys.exit('no life 2')
    time.sleep(1)
out = (out_dir / 'monitor2.txt').open('w', encoding='utf-8')
def snap():
    d = {}
    for p in psutil.process_iter(['name']):
        try:
            io = p.io_counters(); ct = p.cpu_times()
            d[p.pid] = (p.info['name'], io.read_bytes, io.write_bytes, ct.user + ct.system)
        except (psutil.Error, OSError):
            pass
    return d
pd, ps = psutil.disk_io_counters(perdisk=True), snap()
start = time.time()
while time.time() - start < 320:
    time.sleep(5)
    nd, ns = psutil.disk_io_counters(perdisk=True), snap()
    t = time.time() - start
    disks = ' '.join(f'{k} r{(nd[k].read_bytes - pd[k].read_bytes) / 5e6:.0f} w{(nd[k].write_bytes - pd[k].write_bytes) / 5e6:.0f}'
                     f' busy{(nd[k].busy_time - pd[k].busy_time) / 50 if hasattr(nd[k], "busy_time") else -1:.0f}%'
                     for k in nd if k in pd)
    rows = []
    for pid, (n, r, w, c) in ns.items():
        if pid in ps:
            _, r0, w0, c0 = ps[pid]
            rows.append(((r - r0) / 5e6, (w - w0) / 5e6, (c - c0) / 5, n, pid))
    top_io = sorted(rows, reverse=True)[:5]
    top_cpu = sorted(rows, key=lambda x: -x[2])[:5]
    out.write(f't={t:5.0f}s cpu{psutil.cpu_percent():.0f}% | {disks}\n')
    out.write('   io : ' + ', '.join(f'{n}({pid}) r{r:.0f} w{w:.0f}MB/s' for r, w, c, n, pid in top_io) + '\n')
    out.write('   cpu: ' + ', '.join(f'{n}({pid}) {c:.2f}' for r, w, c, n, pid in top_cpu) + '\n')
    out.flush()
    pd, ps = nd, ns
