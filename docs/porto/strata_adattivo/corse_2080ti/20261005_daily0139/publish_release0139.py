"""Daily 0.1.39, step 7: publish exactly the tested and installed shipping engine (no model, no workflow)."""
import hashlib, json, shutil, subprocess, zipfile
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0139_20261005'
P = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core')
D = Path(r'D:\ds4_work\strata\Strata\build-0139-daily')
TAG = 'v0.1.39-sm75-20261005-r1'
GH = shutil.which('gh') or r'C:\Program Files\GitHub CLI\gh.exe'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=P, text=True, encoding='utf-8').strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


assert git('branch', '--show-current') == 'main' and not git('status', '--porcelain')
head = git('rev-parse', 'HEAD')
manifest = json.loads((P / 'docs/sm75/source-manifest.json').read_text())
smoke = json.loads((R / 'installed-startup/esito.json').read_text())
val = json.loads((R / 'validation-results.json').read_text())
assert smoke['status'] == 'completed'
exe_hash = sha(D / 'strata.exe')
assert exe_hash == manifest['validated_executable_sha256'] == smoke['exe_sha256']
DEST = R / 'release'
DEST.mkdir(exist_ok=False)
archive = DEST / 'strata-sm75-0.1.39-20261005-windows-x64.zip'
runtime = '''Strata 0.1.39 SM75 Windows x64; modified 22 GB RTX 2080 Ti, Ryzen 5800X/AVX2, CUDA 12.6.
Requires the CUDA 12.6 runtime/cuBLAS on PATH and the Microsoft Visual C++ x64 runtime.
Extract into engine/ of the matching fork checkout; use tools/sm75/configure.py with your existing
model/pack/MTP paths, then START-HERE.bat.
The profile keeps the automatic two-zone elastic expert cache (fixed core, rotating VMM tail),
conservative tail checkpoints, KV 262144/int8/resident 32768, reserve 1393 MiB.
Lab options (STRATA_PREFETCH_NEXT, STRATA_ELASTIC_CORE_ADAPT, STRATA_LOOKAHEAD_PROBE, STRATA_ROUTED_*,
STRATA_GATE_KEEP, STRATA_LOGPOS, STRATA_TRACE) are compiled in and off unless their variable is set.
No model weights, credentials, PDB or workflow are included. Stock 11 GB and multi-GPU are unvalidated.
'''
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.write(D / 'strata.exe', 'strata.exe')
    for name in ('LICENSE', 'CREDITS.md', 'docs/sm75/source-manifest.json', 'docs/sm75/validation.json'):
        z.write(P / name, Path(name).name)
    z.writestr('RUNTIME.md', runtime)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and hashlib.sha256(z.read('strata.exe')).hexdigest() == exe_hash
sums = DEST / 'SHA256SUMS.txt'
sums.write_text(sha(archive) + '  ' + archive.name + '\n' + exe_hash + '  strata.exe\n', encoding='utf-8')
notes = DEST / 'RELEASE.md'
notes.write_text(f'''Fork main aligned to upstream **0.1.39** (`{manifest['snapshot_upstream_commit'][:7]}`), keeping the SM75
ports, the automatic two-zone elastic expert cache (fork-only), wide top-k (PR603) and the near-tail checkpoint
(PR614).  New in the fork since 0.1.38 (all off by default): next-layer PCIe prefetch, swappable elastic core,
WDDM budget / NVML figures in `STRATA_TRACE`, CPU and GPU expert format benches.

Validated on a modified **RTX 2080 Ti 22 GB**, Ryzen 5800X/AVX2, 96 GB RAM, Windows, CUDA 12.6, IQ3_XXS,
KV 262144/int8/resident 32768, the Daily's own configuration:

{val['release_bullets']}

General model quality, stock 11 GB cards and multi-GPU are not validated.
Executable SHA256: `{exe_hash}`.

The ZIP holds the exact tested and installed shipping engine, MIT notices, provenance and validation.
Requires the CUDA 12.6 runtime/cuBLAS and the Microsoft VC++ x64 runtime; supply the weights separately.
Previous releases remain available for rollback.
''', encoding='utf-8')
subprocess.run([GH, 'release', 'create', TAG, str(archive), str(sums), '--repo', 'imanu86/Strata-2080Ti', '--target', head,
                '--title', 'Strata 0.1.39 SM75: upstream 0.1.39 with the elastic cache, +9-20% decode at 131k',
                '--notes-file', str(notes), '--latest'], check=True)
status = dict(url='https://github.com/imanu86/Strata-2080Ti/releases/tag/' + TAG, tag=TAG, target_commit=head,
              exe_sha256=exe_hash, archive_sha256=sha(archive), archive_bytes=archive.stat().st_size)
(R / 'release-publication.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
print(json.dumps(status), flush=True)
