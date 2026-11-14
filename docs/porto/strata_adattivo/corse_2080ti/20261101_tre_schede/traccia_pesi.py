"""14/11: traccia del router con i pesi veri (--dump-routing, motore a domanda singola, non --serve) per la stima della maschera.
Config del Daily senza le opzioni del servizio, dei server e delle bozze; solo la 2080 Ti. Dietro bench.lock."""
import json, os, subprocess, time
from pathlib import Path

QUI = Path(__file__).resolve().parent
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
c = json.loads(Path(r'D:\ds4_work\strata\Strata\strata-02131-4c-daily-schermo3060.json').read_text(encoding='utf-8'))
a, out, i = c['args'], [], 0
due = {'--prompt-cache', '--prompt-cache-every', '--conversation-cache-mib', '--conversation-cache-slots', '--peer-device',
       '--peer-reserve-mib', '--lookup-max-t', '--kv-resident'}
uno = {'--prompt-cache-tail', '--vision'}
while i < len(a):
    if a[i] in due: i += 2
    elif a[i] in uno: i += 1
    else: out.append(a[i]); i += 1
out += ['--max-context', '16384', '--tokens-file', str(QUI / 'prompt_ids.txt'), '--max-new', '3000', '--dump-routing', str(QUI / 'routing_pesi.bin')]
# --max-context compare due volte: l'ultima vince? per sicurezza tolgo la prima
k = out.index('--max-context'); del out[k:k + 2]
env = dict(os.environ)
env.update(c['env'])
for k in [k for k in env if k.startswith('STRATA_PEER') or k.startswith('STRATA_EP_SPLIT')]:
    env.pop(k)
env['CUDA_VISIBLE_DEVICES'] = '2'
env['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
while True:
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, b'TRACCIA-PESI'); os.close(fd); break
    except FileExistsError:
        time.sleep(2)
try:
    (QUI / 'comando.txt').write_text(' '.join(out), encoding='utf-8')
    t0 = time.time()
    with open(QUI / 'motore.log', 'w', encoding='utf-8') as f:
        r = subprocess.run([c['exe']] + out, env=env, cwd=c['cwd'], stdout=f, stderr=subprocess.STDOUT, timeout=3600)
    print(f'motore uscito rc={r.returncode} in {time.time() - t0:.0f} s', flush=True)
finally:
    LOCK.unlink(missing_ok=True)
print('== coda finita', flush=True)
