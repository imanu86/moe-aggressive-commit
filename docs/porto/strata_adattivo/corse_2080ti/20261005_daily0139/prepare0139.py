"""Daily 0.1.39, step 1: check both checkouts, take the restore point, freeze the tested source.

Fork main (the Strata-2080Ti-core worktree, branch main) must be clean at HEAD; the Daily checkout
(D:\\ds4_work\\strata\\Strata, main) clean apart from its untracked files.  The restore point holds bundles of both
repositories, the Daily config, the desktop launcher, the fork's sm75 manifests and every untracked Daily file.
The source is `git archive` of the fork commit: exactly the tracked files, nothing from the working tree.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, time
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0139_20261005'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
D = Path(r'D:\ds4_work\strata\Strata')
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
UPSTREAM = '6f32ec070f23ced9f50e704d854d775da52591ab'   # Niko1221/Strata v0.1.39


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8', errors='replace').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


R.mkdir(exist_ok='--resume' in sys.argv)
for root in (P, D):
    print(root, git(root, 'status', '--short', '--branch').splitlines()[0], flush=True)
    assert git(root, 'branch', '--show-current') == 'main', root
    assert not git(root, 'diff', '--name-only') and not git(root, 'diff', '--cached', '--name-only'), root
head = git(P, 'rev-parse', 'HEAD')
git(P, 'fetch', '-q', 'origin')
assert git(P, 'rev-parse', 'origin/main') == head, 'fork main not pushed'
daily_head = git(D, 'rev-parse', 'HEAD')
assert subprocess.run(['git', 'merge-base', '--is-ancestor', daily_head, head], cwd=P).returncode == 0, 'Daily is not behind main'
assert subprocess.run(['git', 'merge-base', '--is-ancestor', UPSTREAM, head], cwd=P).returncode == 0, 'v0.1.39 not merged'
untracked = git(D, 'ls-files', '--others', '--exclude-standard').splitlines()

if not (R / 'recovery.json').exists():
    backup = Path(r'D:\ds4_work\strata\ripristini') / time.strftime('%Y%m%d_%H%M%S_allineamento039')
    backup.mkdir(parents=True, exist_ok=False)
    git(P, 'bundle', 'create', str(backup / 'fork-main-before.bundle'), '--all')
    git(D, 'bundle', 'create', str(backup / 'daily-main-before.bundle'), '--all')
    for p in (D / 'strata-2080ti-sota.json', BAT, P / 'docs/sm75/source-manifest.json', P / 'docs/sm75/validation.json'):
        shutil.copyfile(p, backup / p.name)
    for name in untracked:
        src, dest = D / name, backup / 'untracked' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == '.dmp':
            os.link(src, dest)
        else:
            shutil.copyfile(src, dest)
    cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
    recovery = dict(backup=str(backup), fork_head=head, old_daily_head=daily_head, upstream=UPSTREAM,
                    untracked_preserved=untracked, old_daily_exe=cfg['exe'], old_daily_exe_sha256=sha(cfg['exe']),
                    cfg_sha256=sha(D / 'strata-2080ti-sota.json'), launcher_sha256=sha(BAT),
                    how_to_restore='copy strata-2080ti-sota.json and the .bat from this folder back; build-0138-daily is untouched')
    (R / 'recovery.json').write_text(json.dumps(recovery, indent=2) + '\n', encoding='utf-8')
    print('RECOVERY', backup, flush=True)

S = R / 'source'
if not S.exists():
    data = subprocess.check_output(['git', 'archive', '--format=tar', head], cwd=P)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(S)
files = {p.relative_to(S).as_posix(): sha(p) for p in sorted(S.rglob('*')) if p.is_file()}
assert not any((S / '.github/workflows').glob('*')) if (S / '.github/workflows').exists() else True
(R / 'preparation.json').write_text(json.dumps(dict(fork_head=head, upstream=UPSTREAM, source_files=len(files),
                                                    files=files), indent=2) + '\n', encoding='utf-8')
print('SOURCE READY', head, len(files), 'files', flush=True)
