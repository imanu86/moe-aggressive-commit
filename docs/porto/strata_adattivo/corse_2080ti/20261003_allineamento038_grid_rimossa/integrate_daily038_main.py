"""Import the complete tested038 export on main; retain ancestry and old evidence."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,re,statistics
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';S=R/'source';P=Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
UP='99f3dbd0b21d1401b3769e0c0d963913607f380b';OLD='2c394674ed933a817741506b0b35e370f4d45c21'
def git(*args):return subprocess.check_output(['git',*args],cwd=P,text=True,encoding='utf-8',errors='replace').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(rel,text):
    p=P/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8',newline='\n')
print(git('branch','--show-current'),git('status','--short','--branch'),flush=True)
assert git('branch','--show-current')=='main' and git('rev-parse','HEAD')==OLD and not git('status','--porcelain')
parity=json.loads((R/'parity-r1/results.json').read_text());dialogue=json.loads((R/'dialogue-r1/results.json').read_text());build=json.loads((R/'build-wide.json').read_text());speed=json.loads((R/'speed-summary.json').read_text())
assert parity['status']=='completed' and parity['gate_pass'] and parity['oracle_pass']
assert dialogue['status']=='completed' and dialogue['long_decode_pass'] and dialogue['oracle_pass']
assert speed['completed'] and speed['oracle_pass'] and speed['long_decode_pass'] and speed['first_logits_bitwise']
exe=R/'strata-wide.exe';assert sha(exe)==build['shipping_exe_sha256'];assert sha(S/'src/program/generate.cpp')==build['shipping_generate_sha256']
for rel,h in build['source_files'].items():assert sha(S/rel)==h,rel
assert 'align_every' not in (S/'src/program/generate.cpp').read_text()
assert 'qsa_topk_parity: PASS' in (R/'topk-wide-selftest.log').read_text()
assert '100% tests passed' in (R/'ctest-wide.log').read_text() and 'PASS: 64' in (R/'pool-quant-wide.log').read_text()
assert 'Ran 118 tests' in (R/'server-tests.log').read_text() and '\nOK\n' in (R/'server-tests.log').read_text()
rec=json.loads((R/'recovery.json').read_text());backup=Path(rec['backup']);assert (backup/'fork-main-before.bundle').exists()
previous=(P/'docs/sm75/source-manifest.json').read_bytes();previous_validation=(P/'docs/sm75/validation.json').read_bytes()
assert git('rev-parse','6ba96984ac8a5f019edd84d7a83c278e6a1d363d^{commit}')=='6ba96984ac8a5f019edd84d7a83c278e6a1d363d'
subprocess.run(['git','merge','--no-ff','--no-commit','-s','ours',UP,'6ba96984ac8a5f019edd84d7a83c278e6a1d363d'],cwd=P,check=True)
preserve={'README.md','START-HERE.bat','.gitignore','.gitattributes','AGENTS.md'};imported=[]
for src in sorted(S.rglob('*')):
    if not src.is_file():continue
    rel=src.relative_to(S).as_posix();assert not rel.startswith('.github/workflows/')
    if rel in preserve:continue
    dest=P/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);imported.append(rel)
(P/'docs/sm75/source-manifest-0136.json').write_bytes(previous);(P/'docs/sm75/validation-0136.json').write_bytes(previous_validation)
shutil.copyfile(S/'README.md',P/'docs/UPSTREAM_README.md')
cfg=P/'tools/sm75/configure.py';text=cfg.read_text(encoding='utf-8');needle="'--kv-resident', str(a.kv_resident), '--vram-reserve-mib', str(a.reserve_mib), '--elastic']"
assert text.count(needle)==1;text=text.replace(needle,"'--kv-resident', str(a.kv_resident), '--vram-reserve-mib', str(a.reserve_mib), '--elastic',\n        '--prompt-cache-tail', '--prompt-cache-every', '16384']")
text=text.replace("'env': {'STRATA_WATCHDOG_S': '240'}","'env': {'STRATA_WATCHDOG_S': '240', 'STRATA_PARALLEL_INTERMEDIATE_QUANT': '0'}");write('tools/sm75/configure.py',text)
performance_table='| Actual fresh input | Fresh prefill t/s | Long decode t/s | Output tokens |\n|---|---:|---:|---:|\n'
for depth in (131072,250000):
    fresh=next(x for x in dialogue['requests'] if x['name']==f'{depth}-fresh');long=next(x for x in dialogue['requests'] if x['name']==f'{depth}-long')
    performance_table+=f"| {depth} | {fresh['prompt_read']*1000/fresh['prompt_ms']:.2f} | {long['generated']*1000/long['decode_ms']:.3f} | {long['generated']} |\n"
samples=speed['timing']['250000-fresh']['arms'];tps=[x['prompt_read']*1000/x['prompt_ms'] for x in samples];baseline=statistics.mean([tps[0],tps[2]]);gain=(tps[1]/baseline-1)*100;spread=abs(tps[0]-tps[2])/baseline*100
current=f'''# Validated0.1.38 SM75 source, 3 October2026

Upstream main `{UP}`, automatic elastic expert cache, SM75 HC/GDN FP16 and vector
dequantization ports, serial intermediate quantization, conservative optional
`--prompt-cache-tail` ([PR614](https://github.com/Niko1221/Strata/pull/614)), and wide
top-k ([PR603](https://github.com/Niko1221/Strata/pull/603), exact pinned source).
The old checkpoint grid is removed, including its chunk-boundary overrides.
The old failed grid comparisons remain in the research record; this replacement
does not turn those failures into passes.

Full fresh CMake/Ninja Release build, CUDA12.6/MSVC14.44, architecture75.
Six CTest checks pass; native CPU quantization64 cases bitwise; wide top-k18 cases,
continuous scores, ties and equal scores, prompt/decode through524288 cells;
118 upstream server mock tests pass. A fixed-placement old036/new038/old036
model comparison has2560 teacher rows (2557 scored positions) per arm, finite
logits, six complete recall oracles, and all local numerical gates pass.
Separate Daily auto/elastic conversations at131072 and250000 input tokens pass
six oracles, with1024 generated tokens at each depth and a new marker afterwards.

Controlled PR603 comparison at250000 actual tokens: same038 source,5357 expert
slots,8192 prefill chunk, spec4, KV262144/int8/resident32768, resize disabled by
real long policy intervals. A/B/A repeated baseline; first logits are bitwise
identical and every complete recall/marker oracle passes. Detailed timings and
the distinction from the automatic Daily profile are in `validation.json`.

Only the modified22GB RTX2080Ti, Ryzen5800X/AVX2 and96GB RAM were exercised.
No artificial system saturation, general quality score, physical DRAM-bandwidth
measurement, stock11GB or multiGPU performance claim.
Executable SHA256: `{sha(exe)}`. Previous manifests and validation remain intact.

{performance_table}
Single automatic-profile samples: initial6339 expert slots, runtime spec6,
MTPmax4/lookup3/PCIe0.36. They do not establish a causal gain against old036.
Controlled PR603250k prefill A/B/A: {tps[0]:.2f}/{tps[1]:.2f}/{tps[2]:.2f}t/s,
{gain:+.2f}% relative to the baseline mean, reference spread{spread:.2f}%.
This fixed5357slot/8192chunk/spec4 profile has MTPmax0/lookup0/PCIe0.28;
keep it distinct from the automatic Daily profile above. Only one A/B/A.

'''
validation={'date':'2026-10-03','upstream_commit':UP,'version':'0.1.38','executable_sha256':sha(exe),'grid_removed':True,'checkpoint_tail':True,'pr603':json.loads((R/'pr603-provenance.json').read_text()),'paired_numerical':parity,'daily_dialogue':dialogue,'controlled_topk_250k':speed,'kernel_bench':json.loads((R/'topk-bench-r1/results.json').read_text()),'numerical':{'ctest_checks':6,'wide_topk_cases':18,'native_quant_cases':64,'upstream_server_mock_tests':118},'limitations':['Modified22GB SM75 only; no broad model quality score','Automatic Daily cache placement and MTP vary; controlled kernel comparison uses a fixed profile','Original failed grid comparisons are preserved; old036 measurements are historical','No stock11GB or multiGPU validation']}
write('docs/sm75/validation.json',json.dumps(validation,indent=2))
for rel in ('docs/sm75/BENCHMARKS.md','docs/sm75/PATCHES.md','docs/sm75/BUILD.md'):
    old=(P/rel).read_text(encoding='utf-8');write(rel,current+'## Historical records (their original versions and limits apply)\n\n'+old)
readme=(P/'README.md').read_text(encoding='utf-8');a=readme.index('Main is aligned');z=readme.index('[Credits]',a)
readme=readme[:a]+'''Main is aligned to upstream **0.1.38**, preserving the automatic elastic expert
cache and validated Turing ports. The original checkpoint grid has been removed;
the conservative tail checkpoint is optional in the engine and enabled by this
fork's profile generator. The pinned wide top-k from PR603 is included after
SM75 parity and model validation. Serial intermediate quantization remains the
profile default. Historical0.1.31 and0.1.36 evidence is preserved separately.
'''+readme[z:]
readme=readme.replace('## Current comparison','## Current0.1.38 validation\n\nSix CTest checks,18 wide top-k cases,64 CPU quantization cases and118 server\ntests pass. Paired model regression and real conversations at131k/250k pass;\nsee [current evidence and limits](docs/sm75/BENCHMARKS.md). KV capacity is262144.\n\n## Historical0.1.36 comparison')
readme=readme.replace('## Historical0.1.36 comparison',performance_table+'\nSingle automatic-profile samples; cache/MTP vary. The separately controlled\nPR603250k A/B/A and numerical parity are documented in the evidence above.\n\n## Historical0.1.36 comparison')
readme=readme.replace('The0.1.36 engine was built and tested explicitly for the authorized kernel work.\nIts source manifest and validation are separate from the preserved0.1.31 record.','The current0.1.38 engine was built and validated for this integration.\nCurrent and historical source manifests/validation remain separate.')
readme=readme.replace('The original decode API/captured graphs are unchanged.','The wide fallback from PR603 also accelerates long selections and decode;\n  selected IDs pass parity against the upstream reference.')
write('README.md',readme)
credits=(P/'CREDITS.md').read_text(encoding='utf-8');write('CREDITS.md',credits+f'''\nCurrent0.1.38 integration: upstream `{UP}`. Original elastic expert-cache design
by Claude Opus; Codex port/guards and validation. Tail checkpoint: Codex,
[PR614](https://github.com/Niko1221/Strata/pull/614). Wide top-k: Chanyeong Lim
(asp345), co-authored by Claude Opus5.5, [PR603](https://github.com/Niko1221/Strata/pull/603),
head6ba96984ac8a5f019edd84d7a83c278e6a1d363d. Their work is credited explicitly;
the old grid is now historical and is absent from the operative source.\n''')
files={p.relative_to(S).as_posix():sha(p) for p in sorted(S.rglob('*')) if p.is_file()}
manifest={'snapshot_upstream_commit':UP,'snapshot_version':'0.1.38','validated_executable_sha256':sha(exe),'previous_manifest':'source-manifest-0136.json','previous_manifest_sha256':hashlib.sha256(previous).hexdigest(),'files':files,'publication_overrides':sorted(preserve & files.keys()),'dependency_ggml_commit':'3cf03257f219afbe7334045ff7c6a06ac68c627d','meaning':'complete tested source export with explicit publication overrides; no workflow; old source manifests preserved'}
write('docs/sm75/source-manifest.json',json.dumps(manifest,indent=2))
extra=['README.md','CREDITS.md','docs/UPSTREAM_README.md','tools/sm75/configure.py','docs/sm75/BENCHMARKS.md','docs/sm75/PATCHES.md','docs/sm75/BUILD.md','docs/sm75/validation.json','docs/sm75/source-manifest.json','docs/sm75/source-manifest-0136.json','docs/sm75/validation-0136.json']
paths=sorted(set(imported+extra));pathfile=R/'stage-main.paths';pathfile.write_bytes(b''.join(x.encode('utf-8')+b'\0' for x in paths))
subprocess.run([sys.executable,'-B',str(P/'tools/sm75/check_source.py')],cwd=P,check=True)
subprocess.run(['git','add','--pathspec-from-file='+str(pathfile),'--pathspec-file-nul'],cwd=P,check=True)
assert not git('-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--check','--cached'), 'whitespace errors'
(R/'main-prepared.json').write_text(json.dumps({'upstream':UP,'old_head':OLD,'staged_paths':paths,'exe_sha256':sha(exe)},indent=2))
print('Complete tested main source prepared/staged; commit and push next',flush=True)
