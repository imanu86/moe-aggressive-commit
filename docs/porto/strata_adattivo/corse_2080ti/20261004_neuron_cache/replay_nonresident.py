"""Replay frozen 3-for-10 masks, with full/zero controls, on recorded inputs.

No generation server, no speed benchmark, no physical compact weight layout.
The diagnostic executable still reads complete original expert blobs.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import struct
import subprocess
import time

import numpy as np
import psutil

import analyze_probe100 as P
import analyze_trace as A


def errors(data, start, horizon):
    groups = collections.defaultdict(list)
    for row in data:
        if start <= row['pos'] < start + horizon:
            groups[(int(row['pos']), int(row['layer']))].append(row)
    values = []; nr_values = []; floor = []
    by_layer = collections.defaultdict(list)
    for (_, layer), rows in groups.items():
        assert len(rows) == 10
        full = np.zeros(2560); reduced = np.zeros(2560); grouped = np.zeros(2560)
        nr = np.zeros(2560); nr_reduced = np.zeros(2560)
        for row in rows:
            w = float(row['weight'])
            original = w * row['y'][1].astype(np.float64)
            partial = w * row['y'][5].astype(np.float64)
            full += original; reduced += partial
            grouped += w * row['y'][0].astype(np.float64)
            if row['tier'] != 1:
                nr += original; nr_reduced += partial
        value = A.rel_l2(reduced, full)
        values.append(value); by_layer[layer].append(value)
        floor.append(A.rel_l2(full, grouped))
        if np.any(nr):
            nr_values.append(A.rel_l2(nr_reduced, nr))
    return {'positions': horizon, 'routed_sum_relative_l2': A.distribution(values),
            'nonresident_sum_relative_l2': A.distribution(nr_values),
            'same_full_mmvg_vs_grouped_floor': A.distribution(floor),
            'per_layer_routed_sum_relative_l2': {str(k): A.distribution(v) for k, v in by_layer.items()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis', type=Path, required=True)
    ap.add_argument('--lab', type=Path, required=True)
    ap.add_argument('--replayer', type=Path, required=True)
    ap.add_argument('--replayer-sha256', required=True)
    ap.add_argument('--config', type=Path, required=True, help='Read only: native model path, environment and CUDA DLL dirs')
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()
    assert P.sha(args.replayer) == args.replayer_sha256
    competing = [p.info for p in psutil.process_iter(['pid', 'name'])
                 if (p.info['name'] or '').lower() in ('strata.exe', 'neuron_trace_replay.exe')]
    assert not competing, competing
    assert psutil.disk_usage(str(args.lab.resolve())).free > 2 * 1024 ** 3
    source = json.loads(args.analysis.read_text(encoding='utf-8'))
    config = json.loads(args.config.read_text(encoding='utf-8'))
    model = Path(config['args'][config['args'].index('--native') + 1])
    env = dict(os.environ)
    for key, value in config.get('env', {}).items():
        env[key] = str(value)
    env['PATH'] = os.pathsep.join(config.get('lib_dirs', []) + [env.get('PATH', '')])
    out = args.output_dir.resolve(); out.mkdir()
    result = {'status': 'running', 'scope': 'Local GPU output replay only, original full expert weights loaded; no end-to-end quality or speed claim',
              'analysis_sha256': P.sha(args.analysis), 'script_sha256': P.sha(Path(__file__)),
              'replayer_sha256': P.sha(args.replayer), 'config_sha256': P.sha(args.config),
              'model': {'name': model.name, 'size': model.stat().st_size, 'mtime_ns': model.stat().st_mtime_ns},
              'runs': [], 'remaining_owned': []}
    try:
        for run in source['runs']:
            name = run['prompt']; start = run['prefix_tokens']
            mask_path = out / (name + '.snm'); replay_path = out / (name + '.snr')
            bank = {}
            for layer in run['candidate_trained_three_for_ten']['per_layer']:
                for expert in layer['experts']:
                    mask = np.zeros(640, dtype=np.uint8); mask[expert['indices']] = 1
                    bank[(layer['layer'], expert['expert'])] = mask
            assert len(bank) == 40
            with mask_path.open('xb') as f:
                f.write(b'SNM10001' + struct.pack('<II', 640, len(bank)))
                for (layer, expert), mask in sorted(bank.items()):
                    f.write(struct.pack('<ii', layer, expert))
                    f.write(mask.tobytes() + bytes([1]) * 640 + bytes(640))
            folder = args.lab / f'probe100-{name}-normal-v1'
            trace = folder / 'target/trace.bin'
            command = [str(args.replayer.resolve()), str(trace.resolve()), str(model), str(replay_path), str(mask_path)]
            began = time.monotonic()
            with (out / (name + '.log')).open('xb') as log:
                proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    code = proc.wait(timeout=90)
                    assert code == 0, (name, code)
                finally:
                    if proc.poll() is None:
                        proc.kill(); proc.wait(timeout=15)
                    if proc.poll() is None:
                        result['remaining_owned'].append(proc.pid)
            wall = time.monotonic() - began
            data = P.records(replay_path, b'SNRv0002')
            old = P.records(folder / 'c0-target.snr', b'SNRv0002')
            assert len(data) == len(old) == 2560
            for field in ('serial', 'pos', 'layer', 'expert', 'tier', 'gu', 'down', 'weight', 'h'):
                assert np.array_equal(data[field], old[field]), (name, field)
            assert np.array_equal(data['y'][:, :5], old['y'][:, :5]), name
            selected = 0
            for row in data:
                key = (int(row['layer']), int(row['expert']))
                assert np.array_equal(row['y'][6], row['y'][1])
                if key in bank:
                    assert row['tier'] != 1 and row['cold'] == 0
                    assert np.array_equal(row['y'][7], np.zeros(2560))
                    selected += 1
                else:
                    assert row['cold'] == 1
                    assert np.array_equal(row['y'][5], row['y'][1])
                    assert np.array_equal(row['y'][7], row['y'][1])
            item = {'prompt': name, 'prefix_tokens': start, 'diagnostic_wall_s': wall,
                    'mask_sha256': P.sha(mask_path), 'trace_sha256': P.sha(trace),
                    'output_sha256': P.sha(replay_path), 'entries': len(data),
                    'masked_entries_including_last_prompt_input': selected,
                    'controls': {'original_h_and_full_outputs_bitwise': True,
                                 'full_mask_bitwise': True, 'zero_mask_exact': True,
                                 'missing_expert_full_fallback_bitwise': True, 'resident_unchanged': True},
                    'first_10': errors(data, start, 10), 'first_20': errors(data, start, 20),
                    'all_63': errors(data, start, 63)}
            result['runs'].append(item)
            print(json.dumps(item), flush=True)
        result['status'] = 'completed'
    except BaseException as exc:
        result.update(status='failed', error=repr(exc))
        raise
    finally:
        P.save(out / 'result.json', result)


if __name__ == '__main__':
    main()
