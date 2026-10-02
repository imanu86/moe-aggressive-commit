"""Integrate the tested source tree on main, retaining published ancestry and historical evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

R=Path(__file__).resolve().parent
P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
C=R/'candidate0136'
BASE='36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca'
OLD='ad4700d61852af3481c8c36a98e5411a76e167cc'
BACKUP=R/('recovery-main-'+time.strftime('%Y%m%d_%H%M%S'))

def git(*args, capture=False):
    return subprocess.run(['git',*args],cwd=P,check=True,text=True,encoding='utf-8',capture_output=capture)

def write(name,text):
    (P/name).parent.mkdir(parents=True,exist_ok=True)
    (P/name).write_text(text,encoding='utf-8',newline='\n')

branch=git('branch','--show-current',capture=True).stdout.strip()
state=git('status','--short','--branch',capture=True).stdout
print(branch,state,flush=True)
if branch!='main' or git('rev-parse','HEAD',capture=True).stdout.strip()!=OLD or len(state.splitlines())!=1:
    raise RuntimeError('Publication main changed; inspect before integration')
arms={name:json.loads((R/'model-tests'/name/'esito.json').read_text(encoding='utf-8'))
      for name in ['daily0131','candidate0136_serial','candidate0136_parallel']}
if any(a['status']!='completed' for a in arms.values()):
    raise RuntimeError('Model validation incomplete')
exe=R/'build0136/strata.exe'
exe_hash=hashlib.sha256(exe.read_bytes()).hexdigest()
if any(arms[n]['exe_sha256']!=exe_hash for n in ['candidate0136_serial','candidate0136_parallel']):
    raise RuntimeError('Candidate binary changed since validation')
for name,marker in [('0136-topk-parity.log','PASS: 16'),('0136-gr-parity.log','gr_parity OK'),('0136-server-tests.log','Ran 100 tests')]:
    if marker not in (R/name).read_text(encoding='utf-8'):
        raise RuntimeError('Missing parity/server evidence')
BACKUP.mkdir()
git('bundle','create',str(BACKUP/'publication-before.bundle'),'--all')
shutil.copyfile(P/'docs/sm75/source-manifest.json',BACKUP/'source-manifest-0131.json')
shutil.copyfile(P/'docs/sm75/validation.json',BACKUP/'validation-0131.json')
(R/'integration-recovery.json').write_text(json.dumps({'publication_backup':str(BACKUP),'old_head':OLD,'upstream':BASE},indent=2),encoding='utf-8')
# The old fork deliberately replaced core files with the validated 0.1.31 snapshot despite 0.1.34 ancestry.
# Stitch upstream ancestry, then explicitly import the COMPLETE 0.1.36 tree plus the reviewed local port.
git('merge','--no-ff','--no-commit','-s','ours',BASE)
preserve={'README.md','START-HERE.bat','.gitignore','.gitattributes','AGENTS.md'}
for src in sorted(C.rglob('*')):
    if not src.is_file(): continue
    name=src.relative_to(C).as_posix()
    if name in preserve: continue
    if name.startswith('.github/workflows/'):
        raise RuntimeError('Unexpected workflow in candidate')
    dest=P/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,dest)
shutil.copyfile(BACKUP/'source-manifest-0131.json',P/'docs/sm75/source-manifest-0131.json')
shutil.copyfile(BACKUP/'validation-0131.json',P/'docs/sm75/validation-0131.json')
shutil.copyfile(C/'README.md',P/'docs/UPSTREAM_README.md')
bench=P/'docs/sm75/BENCHMARKS.md'
historical=bench.read_text(encoding='utf-8')
# The parameterized local bench now calls the upstream API; the separate active API was retired by this port.
topk=P/'tests/sm75/topk_active.cpp'
write('tests/sm75/topk_active.cpp',topk.read_text(encoding='utf-8').replace('qsa_block_topk_active(', 'qsa_block_topk('))
build=P/'tools/sm75/build.py'
write('tools/sm75/build.py',build.read_text(encoding='utf-8').replace("default='75;86'", "default='75'"))
validation={'date':'2026-10-02','upstream_commit':BASE,'version':'0.1.36','executable_sha256':exe_hash,
            'model_comparison':arms,'parallel_quant_default':'off; opt-in STRATA_PARALLEL_INTERMEDIATE_QUANT=1',
            'numerical':{'topk_bitwise_cases':16,'native_pool_bitwise_cases':64,'gr_failures':0,'server_mock_tests':100},
            'limitations':['One sequential baseline/serial/parallel comparison; elastic cache, MTP, outputs and other apps vary.',
                           'No causal speed improvement or general model quality claim.',
                           '250k retrieval belongs to the historical 0.1.31 binary; the new engine was exercised at 131k with KV262144.',
                           'Only the modified 22 GB Turing card and AVX2 machine were exercised.']}
write('docs/sm75/validation.json',json.dumps(validation,indent=2))
table='| Engine | Fresh 131k prefill t/s | Aggregate decode t/s | Initial elastic slots |\n|---|---:|---:|---:|\n'
labels={'daily0131':'0.1.31 reference','candidate0136_serial':'0.1.36 serial (daily)','candidate0136_parallel':'0.1.36 parallel quant (opt-in)'}
for n,a in arms.items():
    table+=f"| {labels[n]} | {a['summary']['per_caso'][0]['prefill_tps_motore']:.2f} | {a['summary']['decode_aggregato_tps']:.3f} | {a['initial_cache']['expert_slots']} |\n"
intro=f'''# Main aligned to upstream 0.1.36, 2 October 2026

Current source base: `{BASE}`. The tested SM75 executable SHA256 is
`{exe_hash}`. Windows, modified RTX2080Ti22GB, Ryzen5800X/AVX2, 96GB RAM,
CUDA12.6, IQ3_XXS, KV262144/int8/resident32768, reserve1393MiB, automatic elastic
cache, MTP. Two requests per arm: fresh131248 tokens, then131239 with131072
reused; 1024 output tokens each. No artificial saturation.

{table}
These are single sequential samples with real desktop activity, changing cache
and MTP acceptance. They do not establish a causal gain from either upstream
changes or parallel quantization. The daily keeps serial quantization; the
parallel implementation is available for explicit controlled comparisons.
16 top-k cases pass bitwise; the unchanged pool port retains 64 real-GGUF
serial/parallel cases; the CMake-built HC test has zero failures. All100 upstream
server mock tests pass. General model quality and a new250k retrieval are not
covered by this comparison. Historical 0.1.31 evidence follows, including its
separate top-k A/B/A and250k retrieval; those measurements do not describe the
new executable.

'''
write('docs/sm75/BENCHMARKS.md',intro+historical)
readme=(P/'README.md').read_text(encoding='utf-8')
readme=readme.replace('This release reproduces our tested **0.1.31 daily** with elastic expert caching,\nHC/GDN FP16, vector dequantization, PR315 and the prefill top-k active-block fix.\nUpstream history is retained; the source snapshot is pinned to the tested version.',
'''Main is aligned to upstream **0.1.36**, preserving our elastic expert cache,
HC/GDN FP16, vector dequantization and the Turing prefill top-k active bound.
The pending-copy ordering from PR463 is included. PR500's parallel intermediate
quantization is opt-in; serial remains the measured daily default.
Upstream history and the original0.1.31 provenance are retained.''')
readme=readme.replace('## Measured performance','## Current comparison\n\n'+table+'\nSingle samples with real desktop activity, elastic cache and varying MTP; no causal\nspeedup is claimed. See [current validation](docs/sm75/BENCHMARKS.md).\n\n## Historical 0.1.31 performance')
readme=readme.replace('No new CUDA build/GPU benchmark was run for publication. The release engine is\nthe previously tested binary; the manifest verifies its source snapshot.',
'''The0.1.36 engine was built and tested explicitly for the authorized kernel work.
Its source manifest and validation are separate from the preserved0.1.31 record.''')
write('README.md',readme)
patches=(P/'docs/sm75/PATCHES.md').read_text(encoding='utf-8')
patches=patches.replace('`qsa_block_topk_active`','`qsa_block_topk(..., active_blocks)`').replace('Only prefill calls the new API. Captured decode graphs keep the original API:', 'Only prefill supplies the active bound. Captured decode graphs omit it:')
write('docs/sm75/PATCHES.md',f'''# Current 0.1.36 port

Upstream `{BASE}` plus the preserved SM75/elastic port. Original snapshot hashes
remain in `source-manifest-0131.json`; current hashes are in `source-manifest.json`.
PR315 and asynchronous commit are now upstream implementations. CUDA active-bound
top-k is restricted to SM75; new upstream SM90+ cluster dispatch is retained.
PR463 contributes the minimal pending-copy wait before serve/CLI verification.
PR500 contributes parallel intermediate quantization, default off and enabled by
`STRATA_PARALLEL_INTERMEDIATE_QUANT=1`. Its quantizers match the serial/native
AVX2 paths. New upstream fused prefill requires SM80+, cluster decode SM90+;
neither fast path is enabled on Turing. No CH16/BPW/PR439 or workflow is imported.

Current executable SHA256: `{exe_hash}`.

## Historical 0.1.31 implementation and evidence

'''+patches)
builddoc=(P/'docs/sm75/BUILD.md').read_text(encoding='utf-8')
write('docs/sm75/BUILD.md','''# Current SM75 build

Current main is upstream0.1.36 plus the documented port. The complete fresh
CMake/Ninja Release build passed with CUDA12.6, MSVC14.44, native CPU experts,
shared CUDA runtime and architecture75. The builder now defaults to75.
100 server mock tests and the CMake-built top-k/HC checks pass. Historical
publication notes below refer to the original0.1.31 release. The original
manifest is preserved as `source-manifest-0131.json`; `check_source.py` verifies
the current source manifest. No automated workflow is installed.

'''+builddoc)
credits=(P/'CREDITS.md').read_text(encoding='utf-8')
credits=credits.replace('Source baseline: Strata **0.1.31**', 'Original published snapshot baseline: Strata **0.1.31**')
credits=credits.replace("The snapshot's older version is an explicit validation choice.", "That historical snapshot and its evidence remain available separately from current main.")
write('CREDITS.md',credits+f'''\nCurrent main source baseline: Strata0.1.36, `{BASE}`. The0.1.31 manifest remains
as historical provenance. Community [PR463](https://github.com/Niko1221/Strata/pull/463)
provides the pending-copy ordering correction and [PR500](https://github.com/Niko1221/Strata/pull/500)
the parallel intermediate quantization design; local integration adds opt-in
dispatch and the real-GGUF parity harness. Their published author history and
upstream licenses are preserved. No reported speedup from another machine is
claimed for this fork.\n''')
files={p.relative_to(C).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
       for p in sorted(C.rglob('*')) if p.is_file()}
manifest={'snapshot_upstream_commit':BASE,'snapshot_version':'0.1.36','validated_executable_sha256':exe_hash,
          'previous_manifest':'source-manifest-0131.json','files':files,
          'previous_manifest_sha256':hashlib.sha256((BACKUP/'source-manifest-0131.json').read_bytes()).hexdigest(),
          'publication_overrides':sorted(preserve & files.keys()),
          'meaning':'Current tested source export plus explicit publication overrides; original 0.1.31 provenance preserved separately.'}
write('docs/sm75/source-manifest.json',json.dumps(manifest,indent=2))
check=(P/'tools/sm75/check_source.py').read_text(encoding='utf-8')
check=check.replace("    overrides = set(manifest['publication_overrides'])", "    if 'previous_manifest_sha256' in manifest:\n        previous = ROOT/'docs/sm75'/manifest['previous_manifest']\n        if hashlib.sha256(previous.read_bytes()).hexdigest() != manifest['previous_manifest_sha256']:\n            raise SystemExit('Historical source manifest changed')\n    overrides = set(manifest['publication_overrides'])")
check=check.replace("print(f'SOURCE_OK {checked} files; tested daily snapshot preserved')", "print(f\"SOURCE_OK {checked} files; current {manifest['snapshot_version']}; original provenance preserved\")")
write('tools/sm75/check_source.py',check)
print('Prepared main integration; review/stage/commit/push separately',flush=True)
