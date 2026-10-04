"""Rebuild causal masks and repeat the largest-error case with full/zero controls."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import time

import numpy as np
import psutil

import measure as M


def self_check():
    raw = struct.pack('<e', 2.) + bytes([228]*16)
    assert np.array_equal(M.decode(raw, 42).ravel(), np.tile([-2., 0., 2., 4.], 16))
    raw = struct.pack('<e', .5) + bytes(range(16))
    assert np.array_equal(M.decode(raw, 20).ravel(), np.r_[.5*M.CODEBOOK, np.repeat(-63.5, 16)])
    rows = np.zeros(5, dtype=M.P.ENTRY)
    rows['layer'] = 0; rows['expert'] = 1; rows['weight'] = 1
    rows['h'] = np.arange(1, 641); rows['pos'] = np.arange(5)
    rows[-1]['expert'] = 2

    class Norms:
        def get(self, key):
            x = np.ones(640); x[0] = 1e10
            return x

    for scorer in ('mean', 'peak'):
        bank, stats = M.build_bank(rows, Norms(), scorer)
        assert list(bank) == [(0, 1)] and stats['0:1']['observations'] == 4
        masks = bank[(0, 1)]
        assert np.array_equal(masks.sum(axis=1), M.KEEPS)
        assert np.all(masks[:, 0])  # Small h, large downstream contribution.
        assert np.all(masks[2] <= masks[1]) and np.all(masks[1] <= masks[0])
    return True


def independent_summary(data, bank, first, count):
    """Separate aggregation, including in-sample calibration error for diagnosis."""
    result = []
    for j in range(3):
        errors = []
        for pos in range(first, first+count):
            for layer in M.LAYERS:
                rows = data[(data['pos'] == pos) & (data['layer'] == layer)]
                assert len(rows) == 10
                weights = rows['weight'].astype(np.float64)
                full = np.einsum('i,ij->j', weights, rows['y'][:, 1].astype(np.float64))
                partial = np.einsum('i,ij->j', weights, rows['y'][:, 5+j].astype(np.float64))
                errors.append(float(np.linalg.norm(partial-full)/np.linalg.norm(full)))
        result.append(M.A.distribution(errors))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('fork', 'lab', 'config', 'replayer', 'run', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    a = ap.parse_args()
    a.output.mkdir()
    source = json.loads((a.run/'measurements.json').read_text())
    assert source['status'] == 'completed' and M.P.sha(a.replayer) == source['replayer_sha256']
    assert not [p.info for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()
                in ('strata.exe', 'neuron_trace_replay.exe', 'hybrid_expert_probe.exe')]
    config = json.loads(a.config.read_text())
    model = Path(config['args'][config['args'].index('--native')+1])
    norms = M.Norms(model, a.fork)
    state = {'status': 'running', 'measurement_sha256': M.P.sha(a.run/'measurements.json'),
             'script_sha256': M.P.sha(Path(__file__)), 'self_checks': self_check(), 'runs': []}
    try:
        for item in source['runs']:
            name, scorer, prefix = item['prompt'], item['scorer'], item['prefix_tokens']
            folder = a.lab/f'probe100-{name}-normal-v1'
            baseline = M.P.records(folder/'c0-target.snr', b'SNRv0002')
            training = baseline[(baseline['pos'] >= prefix) & (baseline['pos'] < prefix+32)]
            bank, stats = M.build_bank(training, norms, scorer)
            existing = M.P.read_bank(a.run/f'{name}-{scorer}.snm')
            assert set(bank) == set(existing) and stats == item['training_stats']
            assert all(np.array_equal(bank[k], existing[k]) for k in bank)
            data = M.P.records(a.run/f'{name}-{scorer}.snr', b'SNRv0002')
            check = independent_summary(data, bank, prefix+32, 31)
            for j in range(3):
                for metric in ('mean', 'median', 'p95', 'p99', 'max'):
                    assert abs(check[j][metric]-item['evaluation']['summary'][j]['routed_sum_relative_l2'][metric]) < 1e-12
            state['runs'].append({'prompt': name, 'scorer': scorer, 'masks_reproduced': True,
                                  'independent_heldout_metrics_match': True,
                                  'in_sample_calibration_error': independent_summary(data, bank, prefix, 32)})

        # Repeat reason/mean (the largest 10% tail), all four format pairs.
        # Control-bank keys may include held-out experts, but those keys retain all
        # neurons in the pruning arm, exactly as the original missing-key fallback.
        original = M.P.records(a.run/'reason-mean.snr', b'SNRv0002')
        learned = M.P.read_bank(a.run/'reason-mean.snm')
        bank = {}
        for row in original:
            key = (int(row['layer']), int(row['expert']))
            masks = np.ones((3, 640), np.uint8)
            masks[0] = learned[key][0] if key in learned else 1
            masks[2] = 0
            bank[key] = masks
        masks = a.output/'controls.snm'; replay = a.output/'controls.snr'
        M.write_bank(masks, bank)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
        env['PATH'] = os.pathsep.join(config.get('lib_dirs', [])+[env.get('PATH', '')])
        command = [str(a.replayer), str(a.lab/'probe100-reason-normal-v1/target/trace.bin'),
                   str(model), str(replay), str(masks)]
        began = time.monotonic()
        with (a.output/'controls.log').open('xb') as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                assert proc.wait(timeout=120) == 0
            finally:
                if proc.poll() is None:
                    proc.kill(); proc.wait(timeout=15)
        repeated = M.P.records(replay, b'SNRv0002')
        assert len(repeated) == len(original)
        for field in ('serial', 'pos', 'layer', 'expert', 'tier', 'gu', 'down', 'weight', 'h'):
            assert np.array_equal(repeated[field], original[field]), field
        assert np.array_equal(repeated['y'][:, :6], original['y'][:, :6])
        assert np.array_equal(repeated['y'][:, 6], repeated['y'][:, 1])
        assert np.count_nonzero(repeated['y'][:, 7]) == 0
        state['gpu_controls'] = {'entries': len(repeated), 'diagnostic_wall_s': time.monotonic()-began,
                                 'pruning_repeat_bitwise': True, 'full_mask_bitwise': True,
                                 'zero_mask_exact': True, 'formats': sorted(set(zip(map(int,repeated['gu']),map(int,repeated['down'])))),
                                 'output_sha256': M.P.sha(replay), 'mask_sha256': M.P.sha(masks)}
        state['status'] = 'completed'
    except BaseException as exc:
        state.update(status='failed', error=repr(exc)); raise
    finally:
        state['live_engines_after'] = [p.info for p in psutil.process_iter(['name', 'pid'])
                                      if (p.info['name'] or '').lower() in ('strata.exe', 'neuron_trace_replay.exe')]
        M.save(a.output/'verification.json', state)
    print('VERIFIED masks, independent metrics, scalar formats, repeat/full/zero GPU controls', flush=True)


if __name__ == '__main__':
    main()
