"""Istantanea della memoria dei processi strata.exe: working set, privata, regioni mappate per file (solo percorsi e dimensioni)."""
import collections, os, sys, psutil
tot = collections.Counter()
for p in psutil.process_iter(['name', 'pid']):
    if (p.info['name'] or '').lower() != 'strata.exe':
        continue
    mi = p.memory_info()
    print(f'pid {p.pid}: working set {mi.wset / 2**30:.2f} GiB, privata {mi.private / 2**30:.2f} GiB, vms {mi.vms / 2**30:.2f} GiB')
    try:
        for m in p.memory_maps(grouped=False):
            name = os.path.basename(m.path) if m.path and not m.path.startswith('[') else (m.path or '[anon]')
            if name.lower().endswith(('.dll', '.exe')) and 'strata' not in name.lower():
                name = '[dll]'
            tot[name] += m.rss
    except Exception as e:  # noqa: BLE001
        print('memory_maps non disponibile:', e)
for k, v in tot.most_common(10):
    print(f'  {k[:70]:70s} rss {v / 2**30:6.2f} GiB')
vm, sw = psutil.virtual_memory(), psutil.swap_memory()
print(f'sistema: totale {vm.total / 2**30:.1f}, disponibile {vm.available / 2**30:.1f}, swap usato {sw.used / 2**30:.1f} GiB')
