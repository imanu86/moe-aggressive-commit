"""Publish only the already tested/installed shipping engine; no workflow or model."""
from pathlib import Path
import subprocess,hashlib,json,zipfile
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti');D=Path(r'D:\ds4_work\strata\Strata\build-0138-daily');GH=r'C:\Program Files\GitHub CLI\gh.exe'
TAG='v0.1.38-sm75-20261003-r1'
def git(*args):return subprocess.check_output(['git',*args],cwd=P,text=True,encoding='utf-8').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
print(git('branch','--show-current'),git('status','--short','--branch'),flush=True);assert git('branch','--show-current')=='main' and not git('status','--porcelain')
head=git('rev-parse','HEAD');manifest=json.loads((P/'docs/sm75/source-manifest.json').read_text());smoke=json.loads((R/'installed-startup/esito.json').read_text());assert smoke['status']=='completed'
exe_hash=sha(D/'strata.exe');assert exe_hash==manifest['validated_executable_sha256']==smoke['exe_sha256']
DEST=R/'release';DEST.mkdir(exist_ok=False);archive=DEST/'strata-sm75-0.1.38-20261003-windows-x64.zip'
runtime='''Strata0.1.38 SM75 Windows x64; modified22GB RTX2080Ti, Ryzen5800X/AVX2, CUDA12.6.
Requires CUDA12.6 runtime/cuBLAS on PATH and Microsoft Visual C++ x64 runtime.
Extract into engine/ of the matching fork checkout; use tools/sm75/configure.py
with your existing model/pack/MTP paths, then START-HERE.bat.
Profile generator enables automatic elastic cache and conservative tail checkpoints,
KV262144/int8/resident32768, reserve1393MiB; serial intermediate quantization.
The original checkpoint grid is removed. Wide top-k is pinned from PR603.
No model weights, credentials, QA instrumentation, PDB or workflow is included.
Stock11GB and multiGPU performance are unvalidated. Historical releases remain.
'''
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.write(D/'strata.exe','strata.exe')
    for name in ('LICENSE','CREDITS.md','docs/sm75/source-manifest.json','docs/sm75/validation.json'):z.write(P/name,Path(name).name)
    z.writestr('RUNTIME.md',runtime)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None and hashlib.sha256(z.read('strata.exe')).hexdigest()==exe_hash
sums=DEST/'SHA256SUMS.txt';sums.write_text(sha(archive)+'  '+archive.name+'\n'+exe_hash+'  strata.exe\n',encoding='utf-8')
notes=DEST/'RELEASE.md';notes.write_text(f'''Main aligned to upstream **0.1.38** (`99f3dbd`), retaining SM75 ports and automatic
elastic expert caching. The original checkpoint grid is removed; the optional
near-tail checkpoint from [PR614](https://github.com/Niko1221/Strata/pull/614) is
enabled by this fork's profile generator. Includes pinned wide top-k from
[PR603](https://github.com/Niko1221/Strata/pull/603), with its author credits.
Parallel intermediate quantization remains opt-in, serial in the profile.

Validated on modified **RTX2080Ti22GB**, Ryzen5800X/AVX2,96GB RAM, Windows,
CUDA12.6, IQ3_XXS, KV262144/int8/resident32768.

- Full SM75 build, six CTest checks,18 wide top-k prompt/decode parity cases,
  64 real-GGUF CPU quantization cases,118 upstream server mock tests.
- Fixed-placement old036/new038/old036 numerical comparison:2560 teacher rows
  per arm, logits bitwise, KL0, top-1 agreement100%, six recall oracles pass.
- Automatic elastic conversations at131072/250000 actual input tokens:
  six complete oracles pass,1024 generated tokens at each depth and new markers
  after long decode. Controlled PR603250k A/B/A and its limits are documented.
- Exact installed shipping executable/server startup passed; source and historical
  manifests preserved. This does not turn the historical grid failures into passes.

General model quality, stock11GB, multiGPU and physical DRAM bandwidth are not
validated. See [measurements and limits](https://github.com/imanu86/Strata-2080Ti/blob/{head}/docs/sm75/BENCHMARKS.md).
Executable SHA256: `{exe_hash}`.

ZIP contains exact tested/installed shipping engine, MIT notices, provenance and
validation. Requires CUDA12.6 runtime/cuBLAS and Microsoft VC++ x64 runtime;
supply existing weights separately. No QA hooks, credentials or workflow.
Previous releases remain available for rollback.
''',encoding='utf-8')
subprocess.run([GH,'release','create',TAG,str(archive),str(sums),'--repo','imanu86/Strata-2080Ti','--target',head,'--title','Strata0.1.38 SM75: wide top-k, elastic cache and conservative checkpoints','--notes-file',str(notes),'--latest'],check=True)
status={'url':'https://github.com/imanu86/Strata-2080Ti/releases/tag/'+TAG,'tag':TAG,'target_commit':head,'exe_sha256':exe_hash,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size}
(R/'release-publication.json').write_text(json.dumps(status,indent=2));print(json.dumps(status),flush=True)
