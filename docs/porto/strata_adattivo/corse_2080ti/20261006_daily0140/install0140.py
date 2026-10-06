"""Daily 0.1.40-r1, passo 5 (SOLO CON IL CONSENSO DELL'UTENTE, a server fermo): porta avanti il checkout del Daily, congela
motore e sorgente provati in build-0140-daily, passa configurazione e lancio alla configurazione 0.1.40-r1.

Configurazione 0.1.40-r1 = quella viva del Daily (tabella PLE su D:, --ple-row-cache 16777216, --elastic, prefisso su disco
--prompt-cache-file ...) INVARIATA, senza --batch, con il solo eseguibile in build-0140-daily.  E' il file preparato da
prepare0140.py (daily0140_20261006/strata-2080ti-sota.proposed.json): lo script lo riconfronta con la configurazione viva
(stesso contenuto, solo il percorso dell'exe) prima di installarlo.  La configurazione viva precedente viene copiata
nel punto di ripristino (strata-2080ti-sota.json.prima-install-0140) oltre alla copia di prepare.  build-0139-daily non si tocca.

Prerequisito: i 5 file di manifest-out/docs/sm75 (vedi manifest-out/COME-APPLICARE.txt) devono essere gia' committati e
pushati nel fork; il manifest pubblicato deve coincidere con quello della cartella.  Il Daily avanza in fast-forward fino
a quel commit (che differisce dal commit provato solo per i file docs/sm75).
Con --check-only esegue solo i controlli di sola lettura e si ferma prima di scrivere qualsiasi cosa.
Ripristino dopo l'installazione: copiare strata-2080ti-sota.json e il .bat dal punto di ripristino.
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0140_20261006'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
D = Path(r'D:\ds4_work\strata\Strata')
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
LABEL = '0.1.40-r1'
sys.path.insert(0, str(D / '.venv/Lib/site-packages'))
import psutil


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8', errors='replace').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(obj):   # il formato della configurazione: indent 2, CRLF, senza BOM
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
OUTM = R / 'manifest-out/docs/sm75'
manifest = json.loads((OUTM / 'source-manifest.json').read_text())
published = P / 'docs/sm75/source-manifest.json'
assert sha(published) == sha(OUTM / 'source-manifest.json'), 'apply and push manifest-out first (COME-APPLICARE.txt)'
exe = R / 'strata.exe'
assert manifest['snapshot_version'] == LABEL and sha(exe) == manifest['validated_executable_sha256']
head = git(P, 'rev-parse', 'HEAD')
fork_commit = manifest['fork_commit']
assert subprocess.run(['git', 'merge-base', '--is-ancestor', fork_commit, head], cwd=P).returncode == 0
changed = set(git(P, 'diff', '--name-only', fork_commit, head).splitlines())
assert changed <= set(manifest['publication_overrides']), 'main moved beyond the manifest files: ' + str(sorted(changed))
untracked = git(D, 'ls-files', '--others', '--exclude-standard').splitlines()
assert untracked == rec['untracked_preserved']
target = D / 'build-0140-daily'
assert not target.exists()
check = json.loads((R / 'check.json').read_text())
assert check['status'].startswith('ok') and check['fork_head'] == fork_commit

raw = (D / 'strata-2080ti-sota.json').read_bytes()
cfg = json.loads(raw)
assert dump(cfg) == raw, 'config formatting would change'
assert cfg['exe'] == rec['old_daily_exe'] and cfg['exe'].endswith(r'build-0139-daily\strata.exe')
args = cfg['args']
assert '--elastic' in args and '--prompt-cache-file' in args and '--ple-row-cache' in args
assert not any(a in args for a in ('--batch', '--batch-mtp', '--slots'))
cfg['exe'] = str(target / 'strata.exe')
proposed_file = R / 'strata-2080ti-sota.proposed.json'
assert cfg == json.loads(proposed_file.read_bytes()) and dump(cfg) == proposed_file.read_bytes(), 'proposed config differs from live (exe only)'

text = BAT.read_bytes().decode('ascii')
assert text.count('build-0139-daily') == 4   # the source line, the exe check (2) and the server path
text = text.replace('build-0139-daily', 'build-0140-daily')
lines = text.split('\r\n')
done = set()
for i, line in enumerate(lines):
    if line.startswith('rem Strata Daily ') and '0.1.39' in line:
        lines[i] = ('rem Strata Daily 6/10/2026: eseguibile upstream 0.1.40 + SM75/elastica (prefisso su disco fino a 64K token 96e2cdc, '
                    'cache elastica che riprova un arena piu piccola df97358); stessa configurazione del Daily 0.1.39, senza --batch.')
        done.add('daily')
    elif line.startswith('rem Misure e ripristino:'):
        lines[i] = ('rem Misure e ripristino: docs/porto/strata_adattivo/corse_2080ti/20261006_daily0140; ripristino ' + str(backup) + '.')
        done.add('misure')
text = '\r\n'.join(lines)
assert done == {'daily', 'misure'} and '0.1.40' in text and 'build-0139-daily' not in text and text.count('build-0140-daily') == 4
if '--check-only' in sys.argv:
    print('CHECK-ONLY: all read-only checks passed; nothing written', flush=True)
    sys.exit(0)

subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=D, check=True)
assert git(D, 'rev-parse', 'origin/main') == head, 'push the manifest commit first'
subprocess.run(['git', 'merge', '--ff-only', 'origin/main'], cwd=D, check=True)
target.mkdir()
shutil.copy2(exe, target / 'strata.exe')
shutil.copytree(R / 'source', target / 'source')
shutil.copy2(OUTM / 'source-manifest.json', target / 'source-manifest.json')
assert sha(target / 'strata.exe') == manifest['validated_executable_sha256']
for rel, h in manifest['files'].items():
    assert sha(target / 'source' / rel) == h, rel

ctmp = D / 'strata-2080ti-sota.json.0140.tmp'
btmp = BAT.with_suffix('.bat.0140.tmp')
assert not ctmp.exists() and not btmp.exists()
shutil.copyfile(D / 'strata-2080ti-sota.json', backup / 'strata-2080ti-sota.json.prima-install-0140')   # the config being replaced
assert sha(backup / 'strata-2080ti-sota.json.prima-install-0140') == rec['cfg_sha256']
ctmp.write_bytes(dump(cfg))
btmp.write_bytes(text.encode('ascii'))
try:
    os.replace(ctmp, D / 'strata-2080ti-sota.json')
    os.replace(btmp, BAT)
    assert 'build-0140-daily' in BAT.read_text(encoding='ascii')
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
