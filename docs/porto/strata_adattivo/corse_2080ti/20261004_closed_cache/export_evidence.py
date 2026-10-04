"""Copy bounded test artifacts and verify preservation, only after engines exit."""
import hashlib,json,shutil,subprocess
from pathlib import Path
import psutil
L=Path(__file__).resolve().parent;R=L.parents[1];F=R.parent/'Strata-2080Ti'
DEST=R/'docs/porto/strata_adattivo/corse_2080ti/20261004_closed_cache'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not DEST.exists(),'Preserve existing publication'
active=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('strata.exe','neuron_trace_replay.exe','closed_router_parity.exe')]
assert not active,active
pins=json.loads((R/'docs/porto/strata_adattivo/corse_2080ti/20261004_ngram_memory/final-state.json').read_text())['protected_files']
assert all(sha(Path(p))==h for p,h in pins.items())
build=json.loads((L/'build-v5/result.json').read_text());assert build['status']=='completed'
assert all(sha(F/p)==h for p,h in build['source_files'].items())
DEST.mkdir(parents=True)
for name in ['run_closed.py','run_extended.py','build_closed.py','run_matrix.py','run_prose.py','analyze.py','export_evidence.py','summary.json']:
    shutil.copy2(L/name,DEST/name)
helpers=DEST/'local_helpers';helpers.mkdir()
for src in [L.parent/'20261004_neuron_cache/run_capture.py',L.parent/'20261004_prefix_disk/validate_prefix.py',L.parent/'20261004_decode_real/profile_decode_v2.py']:
    shutil.copy2(src,helpers/src.name)
save(DEST/'build.json',build)
shutil.copy2(L/'build-v5/build.log',DEST/'build-log.txt')
saved=[]
for p in sorted(L.glob('*/result.json')):
    if not (p.parent/'plan.json').exists():continue
    result=json.loads(p.read_text());assert not result['remaining_owned'] and result['daily_unchanged'] and result['config_unchanged']
    d=DEST/p.parent.name;d.mkdir();saved.append(p.parent.name)
    for name in ['plan.json','result.json','answer.txt','engine.log']:
        src=p.parent/name
        if src.is_file():shutil.copy2(src,d/('engine-log.txt' if name=='engine.log' else name))
same={}
base=json.loads((L/'default-ledger-v1/result.json').read_text())['generated_ids']
for name in ['observe-ledger-v1','daily-ledger-v1','daily-ledger-v2']:
    p=L/name/'result.json'
    if p.exists():same[name]=json.loads(p.read_text())['generated_ids']==base
assert all(same.values())
save(DEST/'verification.json',dict(router_cuda_cases=87,router_parity_sha256=sha(L/'build-v5/closed_router_parity.exe'),
     parity_note='v4 passed 87 cases; v5 parity executable is byte-identical. v5 changes only the driver exchange-buffer guard.',
     baseline_output_ids_equal=same,protected_files=pins,all_test_processes_exited=True,
     available_ram_gib=psutil.virtual_memory().available/1024**3,
     gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,memory.total,utilization.gpu','--format=csv,noheader'],text=True).strip(),
     tests=saved,daily_and_release_promoted=False,
     initial_faults=['First CUDA harness had an unordered pageable upload to a nonblocking stream. Fixed synchronization and reran 87 cases.',
       'First engine smoke failed before READY because exchange buffers were requested from the unused file source. Guarded by complement_ready; all inference runs use v5.']))
print('EXPORTED',str(DEST),len(saved),'runs')
