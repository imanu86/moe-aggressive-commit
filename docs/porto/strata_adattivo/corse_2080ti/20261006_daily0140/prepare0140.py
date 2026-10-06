"""Daily 0.1.40-r1, passo 1: controlla i due checkout, crea il punto di ripristino, congela il sorgente provato e scrive la
configurazione proposta.

Il main del fork (worktree Strata-2080Ti-core, ramo main) deve essere pulito e uguale a origin/main; il checkout del Daily
(D:\\ds4_work\\strata\\Strata, main) pulito a parte i file non tracciati.  Il punto di ripristino contiene i bundle dei due
repository, la configurazione del Daily, il lancio sul desktop, i manifest sm75 del fork e tutti i file non tracciati del
Daily.  Il sorgente e' `git archive` del commit del fork: esattamente i file tracciati, niente dal working tree.

La configurazione proposta (strata-2080ti-sota.proposed.json, SOLO nella cartella della release) e' quella viva con
il solo percorso dell'eseguibile (build-0140-daily): niente --batch, niente altri argomenti; la configurazione viva non viene mai toccata da questo script.
Nessun comando git che cambia stato: solo lettura, bundle e archive.  Il confronto con origin/main usa `ls-remote`.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, time
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0140_20261006'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
D = Path(r'D:\ds4_work\strata\Strata')
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
UPSTREAM = '1735d6471df29b42c26170efaac1f1446a58640f'   # Niko1221/Strata v0.1.40
LABEL = '0.1.40-r1'
NEW_BUILD = D / 'build-0140-daily'
EXTRA_ARGS = []   # il Daily resta senza --batch (decisione dell'owner)


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, encoding='utf-8', errors='replace').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(obj):   # il formato della configurazione: indent 2, CRLF, senza BOM
    return (json.dumps(obj, indent=2, ensure_ascii=False) + '\n').replace('\n', '\r\n').encode('utf-8')


R.mkdir(exist_ok='--resume' in sys.argv)
for root in (P, D):
    print(root, git(root, 'status', '--short', '--branch').splitlines()[0], flush=True)
    assert git(root, 'branch', '--show-current') == 'main', root
    assert not git(root, 'diff', '--name-only') and not git(root, 'diff', '--cached', '--name-only'), root
assert not git(P, 'status', '--porcelain'), 'fork checkout not clean: ' + git(P, 'status', '--short')
head = git(P, 'rev-parse', 'HEAD')
remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/main'], cwd=P, text=True).split()[0]
assert remote == head, 'fork main not pushed (origin/main on the server is ' + remote + ')'
assert git(P, 'rev-parse', 'origin/main') == head, 'local origin/main ref differs from HEAD'
daily_head = git(D, 'rev-parse', 'HEAD')
assert subprocess.run(['git', 'merge-base', '--is-ancestor', daily_head, head], cwd=P).returncode == 0, 'Daily is not behind main'
assert subprocess.run(['git', 'merge-base', '--is-ancestor', UPSTREAM, head], cwd=P).returncode == 0, 'v0.1.40 not merged'
untracked = git(D, 'ls-files', '--others', '--exclude-standard').splitlines()

if not (R / 'recovery.json').exists():
    backup = Path(r'D:\ds4_work\strata\ripristini') / time.strftime('%Y%m%d_%H%M%S_daily0140')
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
                    how_to_restore='copy strata-2080ti-sota.json and the .bat from this folder back; the previous build '
                                   'folder is untouched')
    (R / 'recovery.json').write_text(json.dumps(recovery, indent=2) + '\n', encoding='utf-8')
    print('RECOVERY', backup, flush=True)

S = R / 'source'
if not S.exists():
    data = subprocess.check_output(['git', 'archive', '--format=tar', head], cwd=P)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(S)
files = {p.relative_to(S).as_posix(): sha(p) for p in sorted(S.rglob('*')) if p.is_file()}
assert not any((S / '.github/workflows').glob('*')) if (S / '.github/workflows').exists() else True
(R / 'preparation.json').write_text(json.dumps(dict(fork_head=head, upstream=UPSTREAM, version=LABEL, source_files=len(files),
                                                    files=files), indent=2) + '\n', encoding='utf-8')
print('SOURCE READY', head, len(files), 'files', flush=True)

# configurazione proposta: la viva con il solo exe cambiato, exe nella nuova cartella di build; la viva resta com'e'
rec = json.loads((R / 'recovery.json').read_text())
live_path = D / 'strata-2080ti-sota.json'
raw = live_path.read_bytes()
assert sha(live_path) == rec['cfg_sha256'], 'live config changed since the restore point'
live = json.loads(raw)
assert dump(live) == raw, 'live config formatting would change'
proposed = json.loads(raw)
args = proposed['args']
assert '--elastic' in args and '--prompt-cache-file' in args and '--ple-row-cache' in args
assert not any(a in args for a in ('--batch', '--batch-mtp', '--slots')), 'live config already has batch flags'
proposed['exe'] = str(NEW_BUILD / 'strata.exe')
args += EXTRA_ARGS
assert proposed['args'] == live['args'] and not EXTRA_ARGS
out = R / 'strata-2080ti-sota.proposed.json'
out.write_bytes(dump(proposed))
assert json.loads(out.read_bytes()) == proposed
print('PROPOSED CONFIG', out, sha(out), flush=True)
