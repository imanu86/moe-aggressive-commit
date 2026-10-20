"""misura_ov2.py - ferma il servizio agenti sulla 8100, esegue i comandi della «CODA 20 OTTOBRE» di CODA_MISURE.md
(blocchi 8-14), poi riaccende il servizio. NON tiene bench.lock: run_long.py e community_bench.py lo prendono da soli."""
import subprocess, time
from pathlib import Path

QUI = Path(__file__).resolve().parent
DUE = QUI.parent / '20261006_due_schede'
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
SERVI = QUI.parents[1] / 'servi_agenti.py'


def ps(cmd):
    return subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True).stdout


CODA = (QUI / 'CODA_MISURE.md').read_text(encoding='utf-8').splitlines()
i0 = next(i for i, l in enumerate(CODA) if l.startswith('# CODA 20 OTTOBRE'))
i1 = next(i for i, l in enumerate(CODA) if l.startswith('## 15.'))
PREF = ('bash det_force.sh', 'python bab_verdict.py', 'python ..' + chr(92) + '20261019_banco_comunita')
CMD = [l.strip() for l in CODA[i0:i1] if l.startswith(PREF)]

ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'servi_agenti|server.py' } | "
   "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
time.sleep(5)
subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
LOCK.unlink(missing_ok=True)
try:
    jump = ps("(Get-Process JumpConnect -ErrorAction SilentlyContinue | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum").strip()
    (QUI / 'misura_ov2.ambiente.txt').write_text('inizio ' + time.strftime('%H:%M') + ' jump_cpu_s ' + jump + '\n', encoding='utf-8')
    with open(QUI / 'misura_ov2.log', 'a', encoding='utf-8') as f:
        f.write(f'{len(CMD)} comandi\n')
        for n, c in enumerate(CMD):
            f.write(f'== {n} {time.strftime("%H:%M")} {c}\n'); f.flush()
            if c.startswith('bash'):
                r = subprocess.run(['bash', '-c', c], cwd=DUE, capture_output=True, text=True, encoding='utf-8', errors='replace')
            else:
                r = subprocess.run(c, cwd=DUE, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            f.write((r.stdout + r.stderr)[-3000:] + '\n'); f.flush()
finally:
    with open(QUI / 'misura_ov2.ambiente.txt', 'a', encoding='utf-8') as f:
        f.write('fine ' + time.strftime('%H:%M') + '\n')
    subprocess.Popen(['python', '-u', str(SERVI)], cwd=r'D:\ds4_work\strata\Strata',
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
