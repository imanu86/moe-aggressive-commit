"""Copy measured summaries and check the final local state; no engines launched."""
import json
from pathlib import Path
import subprocess
import psutil
from trace_io import sha
from analyze import save

DEST = Path(__file__).resolve().parent
ROOT = DEST.parents[4]
RUNS = ROOT/'.codex_runs'
SOURCES = {
    'capture-results.json': RUNS/'20261004_ngram_memory_v2/capture-results.json',
    'frozen-measurements.json': RUNS/'20261004_ngram_analysis_v1/measurements.json',
    'adaptive-measurements.json': RUNS/'20261004_ngram_adaptive_v1/measurements.json',
    'verification.json': RUNS/'20261004_ngram_verify_v1/verification.json',
    'initial-failed-start.json': RUNS/'20261004_ngram_memory_v1/capture-results.json',
}


def main():
    capture = json.loads(SOURCES['capture-results.json'].read_text())
    assert capture['status'] == 'completed' and not capture['remaining_owned'] and capture['protected_files_unchanged']
    verification = json.loads(SOURCES['verification.json'].read_text())
    assert verification['status'] == 'completed'
    pins = capture['protected_files_before']
    assert all(sha(Path(p)) == h for p,h in pins.items())
    active = []
    for proc in psutil.process_iter(['pid','name']):
        if (proc.info['name'] or '').lower() in ('strata.exe','neuron_trace_replay.exe'):
            active.append(proc.info)
    assert not active, active
    for name, source in SOURCES.items():
        with (DEST/name).open('xb') as target: target.write(source.read_bytes())
        assert sha(DEST/name) == sha(source)
    state = {'no_running_strata_or_replayer': True, 'protected_files_unchanged': True,
             'protected_files': pins, 'available_ram_gib': psutil.virtual_memory().available/1024**3,
             'gpu': subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,memory.total,utilization.gpu',
                                           '--format=csv,noheader'], text=True).strip(),
             'fork_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent/'Strata-2080Ti',text=True).strip(),
             'fork_status': subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent/'Strata-2080Ti',text=True).strip(),
             'public_evidence_sha256': {name: sha(DEST/name) for name in SOURCES},
             'all_gpu_work_completed': True,
             'daily_config_launcher_and_public_zip': 'unchanged',
             'large_raw_traces_replays_and_scalar_audits': 'retained locally under .codex_runs, not bundled'}
    save(DEST/'final-state.json',state)
    print('NGRAM_EVIDENCE_OK')


if __name__=='__main__': main()
