"""Daily 0.1.39-r2, step 5 (ONLY WITH THE USER'S CONSENT): fast-forward the Daily checkout, freeze the tested engine and
source in build-0139r2-daily, switch config + launcher to the r2 configuration.

r2 configuration = the current Daily config (PLE table on D:, --ple-row-cache 16777216) plus
STRATA_ELASTIC_CORE_ADAPT=1 (env), --pcie-mode dma and --pool-tasks 96 (args).  build-0139-daily stays untouched;
config and launcher are replaced atomically and restored from the restore point on any failure.
Rollback afterwards: copy strata-2080ti-sota.json and the .bat from the restore point back.
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0139r2_20261006'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
D = Path(r'D:\ds4_work\strata\Strata')
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
sys.path.insert(0, str(D / '.venv/Lib/site-packages'))
import psutil


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8', errors='replace').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(obj):   # the config's own format: indent 2, CRLF, no BOM
    return (json.dumps(obj, indent=2, ensure_ascii=False) + '\n').replace('\n', '\r\n').encode('utf-8')


for root in (P, D):
    print(root, git(root, 'status', '--short', '--branch').splitlines()[0], flush=True)
    assert git(root, 'branch', '--show-current') == 'main'
assert not any((q.info['name'] or '').lower() == 'strata.exe' for q in psutil.process_iter(['name'])), 'a Strata engine is running'
rec = json.loads((R / 'recovery.json').read_text())
backup = Path(rec['backup'])
assert git(D, 'rev-parse', 'HEAD') == rec['old_daily_head']
assert not git(D, 'diff', '--name-only') and not git(D, 'diff', '--cached', '--name-only')
assert sha(D / 'strata-2080ti-sota.json') == rec['cfg_sha256'] and sha(BAT) == rec['launcher_sha256'], 'config or BAT changed since prepare'
manifest = json.loads((P / 'docs/sm75/source-manifest.json').read_text())
exe = R / 'strata.exe'
assert manifest['snapshot_version'] == '0.1.39-r2' and sha(exe) == manifest['validated_executable_sha256']
untracked = git(D, 'ls-files', '--others', '--exclude-standard').splitlines()
assert untracked == rec['untracked_preserved']
target = D / 'build-0139r2-daily'
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

raw = (D / 'strata-2080ti-sota.json').read_bytes()
cfg = json.loads(raw)
assert dump(cfg) == raw, 'config formatting would change'
assert cfg['exe'] == rec['old_daily_exe'] and cfg['exe'].endswith(r'build-0139-daily\strata.exe')
args = cfg['args']
assert '--elastic' in args and '--pcie-mode' not in args and '--pool-tasks' not in args and '--ple-row-cache' in args
cfg['exe'] = str(target / 'strata.exe')
args += ['--pcie-mode', 'dma', '--pool-tasks', '96']
cfg['env']['STRATA_ELASTIC_CORE_ADAPT'] = '1'

text = BAT.read_bytes().decode('ascii')
assert text.count('build-0139-daily') == 4   # the source line, the exe check (2) and the server path
text = text.replace('build-0139-daily', 'build-0139r2-daily')
lines = text.split('\r\n')
for i, line in enumerate(lines):
    if line.startswith('rem Strata Daily ') and '0.1.39' in line:
        lines[i] = ('rem Strata Daily 6/10/2026: 0.1.39-r2 = 0.1.39 + #904, Encapsulate, merge v2 #910, Q2_0 esatto, #930, '
                    '#949 (--pool-tasks 96), #965; nucleo elastico adattivo, DMA; tutto identico bit per bit a posizionamento fisso.')
    elif line.startswith('rem Misure e ripristino:'):
        lines[i] = ('rem Misure e ripristino: docs/porto/strata_adattivo/corse_2080ti/20261006_daily0139r2 e '
                    'HANDOFF_5_OTTOBRE_SERA.md; ripristino ' + str(backup) + '.')
text = '\r\n'.join(lines)
assert '0.1.39-r2' in text and 'build-0139-daily' not in text
ctmp = D / 'strata-2080ti-sota.json.r2.tmp'
btmp = BAT.with_suffix('.bat.r2.tmp')
assert not ctmp.exists() and not btmp.exists()
ctmp.write_bytes(dump(cfg))
btmp.write_bytes(text.encode('ascii'))
try:
    os.replace(ctmp, D / 'strata-2080ti-sota.json')
    os.replace(btmp, BAT)
    assert 'build-0139r2-daily' in BAT.read_text(encoding='ascii')
    assert json.loads((D / 'strata-2080ti-sota.json').read_bytes())['exe'] == str(target / 'strata.exe')
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
