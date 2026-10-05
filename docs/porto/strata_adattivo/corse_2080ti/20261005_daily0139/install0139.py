"""Daily 0.1.39, step 5: fast-forward the Daily checkout, freeze the tested engine and source, switch config+launcher.

Requires the fork main to carry the 0.1.39 manifest (step 4) and no Strata process running.  The old build-0138-daily
stays untouched; config and launcher are replaced atomically and restored from the restore point on any failure.
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0139_20261005'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
D = Path(r'D:\ds4_work\strata\Strata')
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
sys.path.insert(0, str(D / '.venv/Lib/site-packages'))
import psutil


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8', errors='replace').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


for root in (P, D):
    print(root, git(root, 'status', '--short', '--branch').splitlines()[0], flush=True)
    assert git(root, 'branch', '--show-current') == 'main'
assert not any((q.info['name'] or '').lower() == 'strata.exe' for q in psutil.process_iter(['name'])), 'a Strata engine is running'
rec = json.loads((R / 'recovery.json').read_text())
backup = Path(rec['backup'])
assert git(D, 'rev-parse', 'HEAD') == rec['old_daily_head']
assert not git(D, 'diff', '--name-only') and not git(D, 'diff', '--cached', '--name-only')
assert sha(D / 'strata-2080ti-sota.json') == rec['cfg_sha256'] and sha(BAT) == rec['launcher_sha256']
manifest = json.loads((P / 'docs/sm75/source-manifest.json').read_text())
exe = R / 'strata.exe'
assert manifest['snapshot_version'] == '0.1.39' and sha(exe) == manifest['validated_executable_sha256']
untracked = git(D, 'ls-files', '--others', '--exclude-standard').splitlines()
assert untracked == rec['untracked_preserved']
assert not set(untracked) & set(git(P, 'ls-files').splitlines())
target = D / 'build-0139-daily'
assert not target.exists()

subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=D, check=True)
head = git(P, 'rev-parse', 'HEAD')
assert git(D, 'rev-parse', 'origin/main') == head, 'push the manifest commit first'
subprocess.run(['git', 'merge', '--ff-only', 'origin/main'], cwd=D, check=True)
target.mkdir()
shutil.copy2(exe, target / 'strata.exe')
shutil.copytree(R / 'source', target / 'source')
shutil.copy2(P / 'docs/sm75/source-manifest.json', target / 'source-manifest.json')
assert sha(target / 'strata.exe') == manifest['validated_executable_sha256']
for rel, h in manifest['files'].items():
    assert sha(target / 'source' / rel) == h, rel

cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
assert cfg['exe'] == rec['old_daily_exe'] and '--elastic' in cfg['args']
cfg['exe'] = str(target / 'strata.exe')
text = BAT.read_text(encoding='utf-8')
assert 'build-0138-daily' in text
text = text.replace('build-0138-daily', 'build-0139-daily')
lines = text.splitlines()
for i, line in enumerate(lines):
    if line.startswith('rem Strata Daily ') and '0.1.38' in line:
        lines[i] = ('rem Strata Daily 5/10/2026: upstream 0.1.39 + SM75/elastica (nucleo fisso, coda VMM)/top-k603/tail614 '
                    '+ exact-small + QSA grouped-query + prefisso652; opzioni di laboratorio spente.')
    elif line.startswith('rem Misure e ripristino:'):
        lines[i] = ('rem Misure e ripristino: docs/porto/strata_adattivo/ALLINEAMENTO_0139_5_OTTOBRE.md. '
                    'Diagnostica (STRATA_TRACE, STRATA_DECODE_TIMING) disponibile ma spenta.')
text = '\n'.join(lines) + '\n'   # written below with newline='\r\n': CRLF on disk, as the launcher was
assert '0.1.39' in text and 'build-0138-daily' not in text
ctmp = D / 'strata-2080ti-sota.json.039.tmp'
btmp = BAT.with_suffix('.bat.039.tmp')
assert not ctmp.exists() and not btmp.exists()
ctmp.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
btmp.write_text(text, encoding='utf-8', newline='\r\n')
try:
    os.replace(ctmp, D / 'strata-2080ti-sota.json')
    os.replace(btmp, BAT)
    assert 'build-0139-daily' in BAT.read_text(encoding='utf-8')
    assert json.loads((D / 'strata-2080ti-sota.json').read_text())['exe'] == str(target / 'strata.exe')
    assert set(untracked) == set(git(D, 'ls-files', '--others', '--exclude-standard').splitlines())
except BaseException:
    shutil.copy2(backup / 'strata-2080ti-sota.json', D / 'strata-2080ti-sota.json')
    shutil.copy2(backup / BAT.name, BAT)
    raise
result = dict(backup=str(backup), daily_head=head, exe=str(target / 'strata.exe'), exe_sha256=sha(target / 'strata.exe'),
              server=str(target / 'source/serve/server.py'), server_sha256=sha(target / 'source/serve/server.py'),
              config_sha256=sha(D / 'strata-2080ti-sota.json'), launcher_sha256=sha(BAT),
              untracked_preserved=len(untracked), previous_build_kept=rec['old_daily_exe'])
(R / 'daily-installation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2), flush=True)
