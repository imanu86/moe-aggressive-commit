"""misura_ov.py - ferma il servizio agenti sulla 8100, esegue i passi 1-6 di CODA_MISURE.md (Obiettivo 1), poi riaccende il servizio.
Tiene bench.lock per tutta la coda. Esiti: bab_*.txt accanto a questo file."""
import os, subprocess, time
from pathlib import Path

QUI = Path(__file__).resolve().parent
DUE = QUI.parent / '20261006_due_schede'
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
SERVI = QUI.parents[1] / 'servi_agenti.py'
B = 'build-overlap-bc2e87a0'


def ps(cmd):
    return subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True).stdout


# 1. ferma il servizio: prima il guardiano (python servi_agenti.py), poi server e motore
ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'servi_agenti|server.py' } | "
   "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
time.sleep(5)
subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
LOCK.unlink(missing_ok=True)
# run_long.py prende bench.lock da solo per ogni braccio: qui NON va tenuto (19/10: tenerlo ha bloccato ogni braccio 50 min)

PASSI = [
    ('A0', [['DET-ov-A0', B], ['DET-ov-A0b', B]], ['DET-ov-A0', 'DET-ov-A0b']),
    ('nsw', [['DET-ov-nsw-A1', B], ['DET-ov-nsw-B1', B, '--env', 'STRATA_P2_FLUSH_NOSWITCH=1'], ['DET-ov-nsw-A2', B]],
     ['DET-ov-nsw-B1', 'DET-ov-nsw-A1', 'DET-ov-nsw-A2']),
    ('stg', [['DET-ov-stg-A1', B], ['DET-ov-stg-B1', B, '--env', 'STRATA_MTP_STAGE0=1'], ['DET-ov-stg-A2', B]],
     ['DET-ov-stg-B1', 'DET-ov-stg-A1', 'DET-ov-stg-A2']),
    ('minp', [['DET-ov-minp-A1', B], ['DET-ov-minp-B1', B, '--set-opt=--spec-min-p=0.70'], ['DET-ov-minp-A2', B]],
     ['DET-ov-minp-B1', 'DET-ov-minp-A1', 'DET-ov-minp-A2']),
    ('top2', [['DET-ov-top2', B, '--env', 'STRATA_OV_TOP2_STAT=1', '--env', 'STRATA_DECODE_TIMING=1']], None),
    ('prio', [['DET-ov-prio-A1', B], ['DET-ov-prio-B1', B, '--env', 'STRATA_OV_CHAIN_PRIO=1'], ['DET-ov-prio-A2', B]],
     ['DET-ov-prio-B1', 'DET-ov-prio-A1', 'DET-ov-prio-A2']),
]
try:
    jump = ps("(Get-Process JumpConnect -ErrorAction SilentlyContinue | Where-Object SessionId -eq 1 | Measure-Object CPU -Sum).Sum").strip()
    (QUI / 'misura_ov.ambiente.txt').write_text(f'inizio {time.strftime("%H:%M")} jump_cpu_s {jump}\n', encoding='utf-8')
    for nome, corse, bab in PASSI:
        for c in corse:
            with open(QUI / f'misura_ov.{c[0]}.log', 'w', encoding='utf-8') as f:
                subprocess.run(['bash', 'det_force.sh'] + c, cwd=DUE, stdout=f, stderr=subprocess.STDOUT)
        if bab:
            r = subprocess.run(['python', 'bab_verdict.py'] + bab, cwd=DUE, capture_output=True, text=True, encoding='utf-8', errors='replace')
            (QUI / f'bab_{nome}.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
finally:
    with open(QUI / 'misura_ov.ambiente.txt', 'a', encoding='utf-8') as f:
        f.write(f'fine {time.strftime("%H:%M")}\n')
    # 2. riaccende il servizio agenti (staccato)
    subprocess.Popen(['python', '-u', str(SERVI)], cwd=r'D:\ds4_work\strata\Strata',
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
