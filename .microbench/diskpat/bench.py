# Misura DIRETTA del disco con lo schema di accesso REALE del runtime:
# letture da 768 KB a offset sparsi sul file del modello (86,7 GB), variando il
# numero di letture in volo. Nessuna deduzione: si cronometra il tempo speso
# nelle read e si dividono i byte per QUEL tempo.
#
# Perche' 768 KB: e' la dimensione media misurata nel runtime (86,4 GB / 109.836
# chiamate). Perche' offset sparsi su tutto il file: il working set degli expert
# e' sparso e il file (86,7 GB) eccede la RAM (64 GB), quindi la page cache non
# puo' servirli tutti — stesso regime del decode.
import os, sys, time, threading, random

PATH = r"C:\ds4-models\ds4-2bit.gguf"
BLOCK = 768 * 1024
PER_THREAD = 250          # letture per thread per livello
LEVELS = [1, 2, 4, 8]

size = os.path.getsize(PATH)
print("file: %s  (%.1f GB)  blocco=%d KB  letture/thread=%d" % (PATH, size/1e9, BLOCK//1024, PER_THREAD))
print()

def worker(seed, out, idx):
    rnd = random.Random(seed)
    fd = os.open(PATH, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    n = 0
    t_read = 0.0
    try:
        for _ in range(PER_THREAD):
            off = rnd.randrange(0, max(size - BLOCK, 1))
            off -= off % 4096
            t0 = time.perf_counter()
            os.lseek(fd, off, os.SEEK_SET)
            b = os.read(fd, BLOCK)
            t_read += time.perf_counter() - t0
            n += len(b)
    finally:
        os.close(fd)
    out[idx] = (n, t_read)

print("%-8s %12s %12s %14s %12s" % ("thread", "MB letti", "wall (s)", "MB/s aggreg.", "ms/lettura"))
base = None
for nt in LEVELS:
    out = [None] * nt
    ths = [threading.Thread(target=worker, args=(1000 + nt * 100 + i, out, i)) for i in range(nt)]
    t0 = time.perf_counter()
    for t in ths: t.start()
    for t in ths: t.join()
    wall = time.perf_counter() - t0
    tot_b = sum(o[0] for o in out if o)
    tot_t = sum(o[1] for o in out if o)
    mbps = tot_b / 1e6 / wall
    per_read_ms = tot_t * 1000 / (nt * PER_THREAD)
    if base is None: base = mbps
    print("%-8d %12.0f %12.2f %14.0f %12.2f   (%+.0f%% vs 1 thread)" %
          (nt, tot_b/1e6, wall, mbps, per_read_ms, (mbps - base) / base * 100))

print()
print("LETTURA: se la banda NON sale coi thread, il dispositivo e' al limite con questo")
print("schema e la leva e' ridurre i byte. Se sale, il limite e' nel nostro percorso.")
