"""Copia la build di lab/batch-dyn in ../20261004_routed_keep/build-batchdyn-<sha>/ (strata.exe, serve e tools della worktree,
strata-vision.exe dalla build multichat45 di riferimento) e scrive build.json.  Niente GPU.

    python pack_build.py
"""
import hashlib, json, shutil, subprocess
from pathlib import Path

WT = Path(r'C:\Users\imanu\source\repos\Strata-wt\batch-dyn')
K = Path(__file__).resolve().parent.parent / '20261004_routed_keep'
sha = subprocess.run(['git', '-C', str(WT), 'rev-parse', '--short=8', 'HEAD'], capture_output=True, text=True).stdout.strip()
dst = K / f'build-batchdyn-{sha}'
dst.mkdir(parents=True, exist_ok=True)
exe = WT / 'build-sm7586' / 'strata.exe'
shutil.copy2(exe, dst / 'strata.exe')
for dll in (WT / 'build-sm7586').glob('*.dll'):
    shutil.copy2(dll, dst / dll.name)
shutil.copy2(K / 'build-multichat45-e42d8af8' / 'strata-vision.exe', dst / 'strata-vision.exe')
for sub in ('serve', 'tools'):
    if (dst / 'source' / sub).exists():
        shutil.rmtree(dst / 'source' / sub)
    shutil.copytree(WT / sub, dst / 'source' / sub, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
h = hashlib.sha256((dst / 'strata.exe').read_bytes()).hexdigest()
(dst / 'build.json').write_text(json.dumps({
    'status': 'completed', 'executable_sha256': h,
    'note': f'lab/batch-dyn {sha} = lab/multichat45 (e42d8af8 + documenti) + STRATA_BATCH_DYNAMIC (opt-in). Compilato sm_75+86 con '
            'build_lock.py (19/10). strata-vision.exe copiato da build-multichat45-e42d8af8. Compilato si, installato no.'}, indent=2),
    encoding='utf-8')
print(dst, h)
