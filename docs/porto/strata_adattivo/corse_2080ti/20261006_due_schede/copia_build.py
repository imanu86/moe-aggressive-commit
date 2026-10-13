"""Copy a worktree's lab build into 20261004_routed_keep/build-<name>-<sha8>/ beside its sources, as the bench arms want:
strata.exe (from <worktree>/build-sm7586), build.json (status, sha256, note), source/serve and source/tools at the
worktree's HEAD (git archive: exactly the committed files), strata-vision.exe copied from the Daily build.

    python copia_build.py <worktree> <name> "<note>"
"""
import hashlib, io, json, shutil, subprocess, sys, tarfile
from pathlib import Path

wt, name, note = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
K = Path(__file__).resolve().parent.parent / '20261004_routed_keep'
DAILY = Path(r'D:\ds4_work\strata\Strata\build-0143-daily')
sha8 = subprocess.run(['git', '-C', str(wt), 'rev-parse', '--short=8', 'HEAD'], capture_output=True, text=True,
                      check=True).stdout.strip()
if subprocess.run(['git', '-C', str(wt), 'status', '--porcelain', '--untracked-files=no'], capture_output=True,
                  text=True).stdout.strip():
    sys.exit('the worktree has uncommitted changes: commit first, the build must match a sha')
out = K / f'build-{name}-{sha8}'
out.mkdir(exist_ok=False)
exe = wt / 'build-sm7586' / 'strata.exe'
shutil.copy2(exe, out / 'strata.exe')
shutil.copy2(DAILY / 'strata-vision.exe', out / 'strata-vision.exe')
tar = subprocess.run(['git', '-C', str(wt), 'archive', '--format=tar', 'HEAD', 'serve', 'tools'], capture_output=True,
                     check=True).stdout
with tarfile.open(fileobj=io.BytesIO(tar)) as t:
    t.extractall(out / 'source', filter='data')
digest = hashlib.sha256((out / 'strata.exe').read_bytes()).hexdigest()
(out / 'build.json').write_text(json.dumps({'status': 'completed', 'executable_sha256': digest,
                                            'note': f'{note} (worktree {wt}, HEAD {sha8}; strata-vision.exe dal Daily '
                                                    f'build-0143-daily)'}, indent=2, ensure_ascii=False) + '\n',
                                encoding='utf-8')
print(out, digest)
