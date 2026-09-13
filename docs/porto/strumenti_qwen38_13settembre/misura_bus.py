"""Corsa di banco con campionamento del traffico PCIe.

Per ogni richiesta: avvia `nvidia-smi dmon -s t`, lancia banco_http.py, ferma il
campionatore e riassume rxpci (byte che ENTRANO nella GPU, cioe' i pesi letti
dalla RAM). Serve a confrontare assetti diversi della bozza a parita' di forma.
"""
import argparse, json, pathlib, re, subprocess, sys, time

HERE = pathlib.Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument('--label', required=True)
ap.add_argument('--max-tokens', type=int, default=768)
ap.add_argument('--ctx-tokens', type=int, default=0)
ap.add_argument('--requests', type=int, default=2)
args = ap.parse_args()


def riassumi(path):
    rx = []
    for line in pathlib.Path(path).read_text(errors='replace').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        campi = line.split()
        # colonne: gpu rxpci txpci  (MB/s)
        for c in campi[1:3]:
            pass
        try:
            rx.append(float(campi[1]))
        except (ValueError, IndexError):
            continue
    rx = [v for v in rx if v >= 0]
    if not rx:
        return 'nessun campione'
    n = len(rx)
    t1, t2 = n // 3, 2 * n // 3
    med = lambda a: sum(a) / len(a) / 1000.0 if a else 0.0
    return (f'campioni {n} | medio {med(rx):.2f} GB/s | primo terzo {med(rx[:t1]):.2f} '
            f'| secondo {med(rx[t1:t2]):.2f} | terzo {med(rx[t2:]):.2f} | picco {max(rx)/1000.0:.2f}')


for i in range(1, args.requests + 1):
    dmon_out = HERE / f'dmon_{args.label}_{i}.txt'
    fh = open(dmon_out, 'w')
    dmon = subprocess.Popen(['nvidia-smi', 'dmon', '-s', 't', '-d', '1'], stdout=fh,
                            stderr=subprocess.STDOUT)
    time.sleep(1.0)
    cmd = [sys.executable, str(HERE / 'banco_http.py'),
           '--max-tokens', str(args.max_tokens), '--turns', '1', '--temperature', '0',
           '--ctx-tokens', str(args.ctx_tokens),
           '--label', f'{args.label}_r{i}']
    print(f'== richiesta {i}:', flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write('ERRORE banco:\n' + r.stderr[-2000:])
    dmon.terminate()
    try:
        dmon.wait(timeout=10)
    except subprocess.TimeoutExpired:
        dmon.kill()
    fh.close()
    print(f'   traffico richiesta {i}: {riassumi(dmon_out)}', flush=True)
