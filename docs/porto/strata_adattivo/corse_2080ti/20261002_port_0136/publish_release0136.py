from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

R=Path(__file__).resolve().parent
P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
D=Path(r'D:\ds4_work\strata\Strata\build-0136-daily')
GH=r'C:\Program Files\GitHub CLI\gh.exe'
TAG='v0.1.36-sm75-20261002-r1'
HEAD='729eb4a14c0a102cf7a57149e8e3fd93a9d18a5f'
DEST=R/'release0136'
if DEST.exists():raise RuntimeError('Release preparation exists; inspect before repeating')
state=subprocess.check_output(['git','status','--short','--branch'],cwd=P,text=True)
branch=subprocess.check_output(['git','branch','--show-current'],cwd=P,text=True).strip()
print(branch,state,flush=True)
if branch!='main' or len(state.splitlines())!=1:raise RuntimeError('Publication checkout changed')
smoke=json.loads((R/'model-tests/installed0136_startup/esito.json').read_text())
if smoke['status']!='completed':raise RuntimeError('Installed startup incomplete')
exe_hash=hashlib.sha256((D/'strata.exe').read_bytes()).hexdigest()
manifest=json.loads((P/'docs/sm75/source-manifest.json').read_text())
if exe_hash!=manifest['validated_executable_sha256'] or exe_hash!=smoke['exe_sha256']:
    raise RuntimeError('Release differs from tested/installed engine')
DEST.mkdir()
runtime='''Strata0.1.36 SM75 Windows x64, tested on a modified22GB RTX2080Ti and Ryzen5800X/AVX2.
Requires CUDA12.6 runtime/cuBLAS on PATH and Microsoft Visual C++ x64 runtime.
Extract into engine/ of the matching fork checkout. Configure existing model/pack/MTP paths with
tools/sm75/configure.py, then run START-HERE.bat. No model weights or credentials are included.
KV262144/int8/resident32768, reserve1393MiB and automatic elastic expert caching describe the measured profile.
Parallel intermediate quantization stays off unless STRATA_PARALLEL_INTERMEDIATE_QUANT=1 is explicitly set.
The PDB corresponds to this executable for debugging. Stock11GB tuning and general model quality are unvalidated.
'''
archive=DEST/'strata-sm75-0.1.36-20261002-windows-x64.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    z.write(D/'strata.exe','strata.exe')
    z.write(D/'strata.pdb','strata.pdb')
    z.write(P/'LICENSE','LICENSE')
    z.write(P/'CREDITS.md','CREDITS.md')
    z.write(P/'docs/sm75/source-manifest.json','source-manifest.json')
    z.write(P/'docs/sm75/validation.json','validation.json')
    z.writestr('RUNTIME.md',runtime)
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None or hashlib.sha256(z.read('strata.exe')).hexdigest()!=exe_hash:
        raise RuntimeError('Release archive verification failed')
zip_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
sums=DEST/'SHA256SUMS.txt'
sums.write_text(zip_hash+'  '+archive.name+'\n'+exe_hash+'  strata.exe\n',encoding='utf-8')
body=f'''Main is aligned to upstream **0.1.36** (`36fa455`), preserving the validated Turing port:
elastic expert cache, HC/GDN FP16, vector dequantization and active-bound prefill top-k.
Includes the minimal pending-copy ordering from PR463; PR500 parallel intermediate quantization is **opt-in, default off**.
The upstream fused prefill requires SM80+ and cluster decode SM90+, so neither is enabled on Turing.

Measured on a **modified RTX2080Ti22GB**, Ryzen5800X/AVX2,96GB RAM, Windows/CUDA12.6,
IQ3_XXS, MTP, KV262144/int8/resident32768 and automatic elastic cache.

- Current serial daily: fresh **131248-token prefill972.68 tokens/s**, aggregate decode **40.123 tokens/s** across2x1024 outputs.
- Reference0.1.31 in the same session:974.05/41.255; parallel candidate970.60/40.272.
- Single sequential samples with varying desktop activity, elastic slots, outputs and MTP: **no causal speedup claimed**.
- Fresh full CMake SM75 engine build,16 bitwise top-k cases,64 real-GGUF CPU pool cases, HC parity with zero failures and100 server mock tests.
- Exact installed executable/server startup passed in40.72s with runtime capacity262144.
- General model quality and stock11GB hardware remain unvalidated. Historical250k retrieval belongs to the preserved0.1.31 engine; it was not repeated on this release.

Executable SHA256: `{exe_hash}`.

The ZIP contains the exact tested/installed engine, matching PDB, source manifest, validation, MIT notices and runtime requirements.
Extract it into `engine/` under this fork. Requires CUDA12.6 runtime/cuBLAS on PATH and Microsoft Visual C++ x64 runtime.
Supply existing model/pack paths with `tools/sm75/configure.py`, then run `START-HERE.bat`.
No model weights, credentials or workflow are included; GitHub Actions remains disabled.
The previous release is retained for rollback.

[Quick start](https://github.com/imanu86/Strata-2080Ti#readme) · [Measurements and limits](https://github.com/imanu86/Strata-2080Ti/blob/{HEAD}/docs/sm75/BENCHMARKS.md).
'''
notes=DEST/'RELEASE.md'
notes.write_text(body,encoding='utf-8')
subprocess.run([GH,'release','create',TAG,str(archive),str(sums),'--repo','imanu86/Strata-2080Ti',
               '--target',HEAD,'--title','Strata 0.1.36 SM75: upstream alignment and elastic daily',
               '--notes-file',str(notes),'--latest'],check=True)
status={'url':'https://github.com/imanu86/Strata-2080Ti/releases/tag/'+TAG,'tag':TAG,'target_commit':HEAD,
        'exe_sha256':exe_hash,'archive_sha256':zip_hash,'archive_bytes':archive.stat().st_size}
(R/'release-publication.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
print(json.dumps(status),flush=True)
