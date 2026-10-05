"""Daily 0.1.39-r2, step 4: the fork's sm75 manifest and validation record for the tested engine (commit + push to main).

The 0.1.39 manifest and validation are kept as *-0139.json; the 2026-10-05 lab manifests become historical (hashes
recorded).  check_source.py reads source-manifest.json first again.  Files changed after the frozen source (these docs and
check_source.py) are publication overrides, as in 0.1.38.
"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0139r2_20261006'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
DOCS = P / 'docs/sm75'
CO = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=P, text=True, encoding='utf-8', errors='replace').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


assert git('branch', '--show-current') == 'main' and not git('status', '--porcelain'), git('status', '--short')
prep = json.loads((R / 'preparation.json').read_text())
build = json.loads((R / 'build.json').read_text())
val = json.loads((R / 'validation-results.json').read_text())
assert git('rev-parse', 'HEAD') == prep['fork_head'] == build['fork_head']
assert sha(R / 'strata.exe') == build['shipping_exe_sha256']

old = json.loads((DOCS / 'source-manifest.json').read_text())
assert old['snapshot_version'] == '0.1.39'
shutil.copyfile(DOCS / 'source-manifest.json', DOCS / 'source-manifest-0139.json')
shutil.copyfile(DOCS / 'validation.json', DOCS / 'validation-0139.json')
historical = {n: sha(DOCS / n) for n in ('r2cand949-20261005.json', 'r2cand930-20261005.json', 'r2cand-20261005.json',
                                         'ple-diag-20261005.json', 'gpu-904-enc-20261005.json', 'kernel-1tok-20261005.json',
                                         'source-manifest-0138.json', 'closed-cache-20261004.json', 'turn-pruning-20261004.json', 'hybrid-blocks-20261004.json',
                                         'neuron-probe100-20261004.json', 'neuron-trace-20261004.json', 'release-20261004.json',
                                         'source-manifest-0131.json', 'source-manifest-0136.json') if (DOCS / n).is_file()}
overrides = ['docs/sm75/source-manifest.json', 'docs/sm75/validation.json', 'docs/sm75/source-manifest-0139.json',
             'docs/sm75/validation-0139.json', 'docs/sm75/VALIDATION.md', 'tools/sm75/check_source.py']
manifest = dict(snapshot_upstream_commit=prep['upstream'], snapshot_version='0.1.39-r2', fork_commit=prep['fork_head'],
                validated_executable_sha256=build['shipping_exe_sha256'], previous_manifest='source-manifest-0139.json',
                previous_manifest_sha256=sha(DOCS / 'source-manifest-0139.json'), historical_manifests=historical,
                publication_overrides=overrides, dependency_ggml_commit='3cf03257f219afbe7334045ff7c6a06ac68c627d',
                meaning='complete tested source export (git archive of fork_commit) with explicit publication overrides; '
                        'no workflow; old source manifests preserved',
                files=prep['files'])
(DOCS / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
validation = dict(date='2026-10-06', upstream_commit=prep['upstream'], version='0.1.39-r2', fork_commit=prep['fork_head'],
                  executable_sha256=build['shipping_exe_sha256'], build=build['steps'], **val)
(DOCS / 'validation.json').write_text(json.dumps(validation, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')

cs = P / 'tools/sm75/check_source.py'
text = cs.read_text(encoding='utf-8')
old_list = ("        ROOT / 'docs/sm75' / name for name in (\n            'r2cand949-20261005.json',")
assert text.count(old_list) == 1
text = text.replace(old_list, "        ROOT / 'docs/sm75' / name for name in (\n            'source-manifest.json', 'r2cand949-20261005.json',")
cs.write_text(text, encoding='utf-8', newline='\n')

vm = DOCS / 'VALIDATION.md'
vm.write_text(vm.read_text(encoding='utf-8').rstrip('\n') + '\n\n' + val['markdown'] + '\n', encoding='utf-8', newline='\n')
chk = subprocess.run([sys.executable, str(cs)], cwd=P, capture_output=True, text=True)
print(chk.stdout, chk.stderr)
assert chk.returncode == 0 and 'current 0.1.39-r2' in chk.stdout
paths = ['docs/sm75/source-manifest.json', 'docs/sm75/validation.json', 'docs/sm75/source-manifest-0139.json',
         'docs/sm75/validation-0139.json', 'docs/sm75/VALIDATION.md', 'tools/sm75/check_source.py']
subprocess.run(['git', 'add', '--', *paths], cwd=P, check=True)
msg = ('OPUS-DEPLOY-Registra manifest e validazione del Daily 0.1.39-r2\n\n'
       f"Sorgente congelata {prep['fork_head'][:8]} (r2: #904, Encapsulate, #910, Q2_0 esatto, #930, #949, #965), eseguibile shipping "
       f"{build['shipping_exe_sha256'][:12]}; manifest 0.1.39 conservato come -0139, manifest del 5/10 storici, check_source legge "
       'prima source-manifest.json.\n\n' + CO + '\n')
subprocess.run(['git', 'commit', '-q', '-F', '-'], cwd=P, input=msg, text=True, check=True)
git('fetch', '-q', 'origin')
assert not git('log', '--oneline', 'HEAD..origin/main'), 'origin/main moved'
subprocess.run(['git', 'push', '-q', 'origin', 'main'], cwd=P, check=True)
print('MANIFEST COMMITTED', git('rev-parse', 'HEAD'), flush=True)
