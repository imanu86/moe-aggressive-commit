"""Copia la build di lab/multichat45b nella cartella dei binari del lab: build-multichat45b-<sha>\ con build.json, strata-vision.exe,
source\serve e source\tools.   python finish_build.py <worktree>   (stampa il percorso dell'exe)"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

WT = Path(sys.argv[1])
K = Path(__file__).resolve().parents[1] / '20261004_routed_keep'
sha = subprocess.run(['git', '-C', str(WT), 'rev-parse', '--short=8', 'HEAD'], capture_output=True, text=True).stdout.strip()
dest = K / f'build-multichat45b-{sha}'
(dest / 'source').mkdir(parents=True, exist_ok=True)
exe = WT / 'build-sm7586' / 'strata.exe'
shutil.copy2(exe, dest / 'strata.exe')
shutil.copy2(K / 'build-upsmain-d06429ee' / 'strata-vision.exe', dest / 'strata-vision.exe')
for d in ('serve', 'tools'):
    shutil.copytree(WT / d, dest / 'source' / d, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
h = hashlib.sha256(exe.read_bytes()).hexdigest()
(dest / 'build.json').write_text(json.dumps({
    'status': 'completed', 'executable_sha256': h,
    'note': f'lab/multichat45b {sha} = lab/multichat45 34cf6351 + upstream #3095 STRATA_PW_WITH_BATCH, #3104 STRATA_PF_FUSED_NATIVE_SM75 (con STRATA_PF_FUSED=1 STRATA_PF_FUSED_SM75=1), '
            '#2774 STRATA_PF_DIRETTO=1 (opt-in qui); sibnick K37 non portato (gia in 0.1.45, 653f0113). Tutto opt-in. Compilato sm_75+86 con build_lock.py (19/10). '
            'strata-vision.exe copiato da build-upsmain-d06429ee. Compilato si, installato no.'}, indent=2), encoding='utf-8')
print(dest / 'strata.exe')
