"""Causal, frozen turn-local pruning pilot on saved full-model inputs.

Calibrate on the first 32 continuation input positions, evaluate the next 31.
Never use held-out h to select a mask. This is a local GPU output experiment,
not pruned generation, physical weight packing, or a throughput benchmark.
Requires numpy, psutil and the adjacent neuron-cache analyzers.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '20261004_neuron_cache'))
import analyze_probe100 as P
import analyze_trace as A

KEEPS = (576, 512, 480)
LAYERS = (0, 1, 35, 36)
MIN_OBSERVATIONS = 4
TRAIN = 32
CODEBOOK = np.array([-127, -104, -83, -65, -49, -35, -22, -10,
                     1, 13, 25, 38, 53, 69, 89, 113], dtype=np.float64)


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def decode(raw, kind):
    """Original IQ4_NL/Q2_0 blocks, float64 for the column-norm score."""
    b = np.frombuffer(raw, np.uint8).reshape(-1, 18)
    d = b[:, :2].copy().view('<f2').astype(np.float64)
    q = b[:, 2:]
    if kind == 20:
        values = np.concatenate((CODEBOOK[q & 15], CODEBOOK[q >> 4]), axis=1)
    elif kind == 42:
        values = ((q[:, :, None] >> np.array([0, 2, 4, 6], np.uint8)) & 3)
        values = values.reshape(-1, 64).astype(np.float64) - 1
    else:
        raise ValueError('unsupported down format')
    result = d * values
    assert np.isfinite(result).all()
    return result


def scalar_decode(raw, kind):
    out = []
    for at in range(0, len(raw), 18):
        d = struct.unpack_from('<e', raw, at)[0]
        q = raw[at+2:at+18]
        if kind == 42:
            out.extend(d * (((q[j//4] >> (2*(j % 4))) & 3) - 1) for j in range(64))
        else:
            out.extend(d * CODEBOOK[q[j] & 15] for j in range(16))
            out.extend(d * CODEBOOK[q[j] >> 4] for j in range(16))
    return np.array(out)


class Norms:
    def __init__(self, model, fork):
        sys.path.insert(0, str(fork / 'tools'))
        from gguf_reader import GGUFFile
        paths = [model, model.with_name(model.name.replace('-00001-of-00002', '-00002-of-00002'))]
        assert paths[0] != paths[1] and all(p.is_file() for p in paths)
        self.metadata = []
        self.sources = {}
        for path in paths:
            gg = GGUFFile(path)
            self.metadata.append({'name': path.name, 'size': path.stat().st_size,
                                  'mtime_ns': path.stat().st_mtime_ns,
                                  'header_sha256': hashlib.sha256(path.open('rb').read(gg.data_start)).hexdigest()})
            for layer in LAYERS:
                selected = [t for t in gg.tensors if t.name == f'blk.{layer}.ffn_down_exps.weight']
                if selected:
                    assert len(selected) == 1 and layer not in self.sources
                    t = selected[0]
                    assert t.shape == [640, 2560, 512] and t.type_id in (20, 42)
                    self.sources[layer] = (path, gg.data_start + t.offset, t.type_id)
        assert set(self.sources) == set(LAYERS)
        self.cache = {}
        self.hashes = {}
        self.checked = set()

    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        layer, expert = key
        path, base, kind = self.sources[layer]
        block = 32 if kind == 20 else 64
        size = 2560 * (640 // block) * 18
        with path.open('rb') as stream:
            stream.seek(base + expert * size)
            raw = stream.read(size)
        assert len(raw) == size
        values = decode(raw, kind).reshape(2560, 640)
        if kind not in self.checked:
            # Independent scalar bit unpacking on 16 evenly spaced real blocks.
            chunks = b''.join(raw[i*18:i*18+18] for i in np.linspace(0, size//18-1, 16, dtype=int))
            assert np.array_equal(decode(chunks, kind).ravel(), scalar_decode(chunks, kind))
            self.checked.add(kind)
        norm = np.sum(values * values, axis=0)
        assert np.all(norm > 0)
        self.cache[key] = norm
        self.hashes[f'{layer}:{expert}'] = hashlib.sha256(raw).hexdigest()
        return norm


def build_bank(training, norms, scorer):
    """The sole mask constructor receives calibration rows only."""
    grouped = collections.defaultdict(list)
    for row in training:
        grouped[(int(row['layer']), int(row['expert']))].append(row)
    bank = {}
    stats = {}
    for key, rows in sorted(grouped.items()):
        if len(rows) < MIN_OBSERVATIONS:
            continue
        h = np.array([r['h'] for r in rows], dtype=np.float64)
        w = np.array([r['weight'] for r in rows], dtype=np.float64)
        # Squared norm of each neuron's individual routed output contribution.
        # Cross-neuron cancellation is not modeled; this is a ranking heuristic.
        individual = (h * w[:, None]) ** 2 * norms.get(key)[None, :]
        score = np.mean(individual, axis=0) if scorer == 'mean' else np.max(individual, axis=0)
        order = np.argsort(-score, kind='stable')
        masks = np.zeros((3, 640), dtype=np.uint8)
        for j, keep in enumerate(KEEPS):
            masks[j, order[:keep]] = 1
        bank[key] = masks
        stats[f'{key[0]}:{key[1]}'] = {'observations': len(rows),
                                     'last_training_position': max(int(r['pos']) for r in rows)}
    assert bank
    return bank, stats


def write_bank(path, bank):
    with path.open('xb') as stream:
        stream.write(b'SNM10001' + struct.pack('<II', 640, len(bank)))
        for (layer, expert), masks in sorted(bank.items()):
            stream.write(struct.pack('<ii', layer, expert) + masks.tobytes())
    readback = P.read_bank(path)
    assert set(readback) == set(bank)
    assert all(np.array_equal(readback[k], bank[k]) for k in bank)


def summarize(data, bank, start):
    groups = collections.defaultdict(list)
    for row in data:
        if row['pos'] >= start:
            groups[(int(row['pos']), int(row['layer']))].append(row)
    curve = []
    covered_errors = [[], [], []]
    covered = 0
    calls = 0
    covered_mass = total_mass = 0.
    byte_full = 0
    byte_kept = np.zeros(3)
    nr_full = 0
    nr_kept = np.zeros(3)
    for (pos, layer), rows in sorted(groups.items()):
        assert len(rows) == 10 and len({int(r['expert']) for r in rows}) == 10
        full = np.zeros(2560)
        partial = np.zeros((3, 2560))
        layer_full = 0
        layer_kept = np.zeros(3)
        for row in rows:
            weight = float(row['weight'])
            full += weight * row['y'][1].astype(np.float64)
            partial += weight * row['y'][5:8].astype(np.float64)
            key = (layer, int(row['expert']))
            geo = A.geometry(int(row['gu']), int(row['down']))
            size = geo['full_expert_weight_bytes']
            kept = np.full(3, size, dtype=np.float64)
            calls += 1
            total_mass += abs(weight)
            if key in bank:
                assert row['cold'] == 0
                covered += 1
                covered_mass += abs(weight)
                for j in range(3):
                    kept[j] = A.mask_footprint(np.flatnonzero(bank[key][j]), geo)['weight_bytes']
                    covered_errors[j].append(A.rel_l2(row['y'][j+5], row['y'][1]))
            else:
                assert row['cold'] == 1
                assert all(np.array_equal(row['y'][j+5], row['y'][1]) for j in range(3))
            byte_full += size
            byte_kept += kept
            layer_full += size
            layer_kept += kept
            if row['tier'] != 1:
                nr_full += size
                nr_kept += kept
        errors = [A.rel_l2(partial[j], full) for j in range(3)]
        curve.append({'pos': pos, 'layer': layer, 'relative_l2': errors,
                      'ideal_weight_saving_fraction': (1-layer_kept/layer_full).tolist()})
    positions = sorted({row['pos'] for row in curve})
    assert positions == list(range(start, start+31)) and len(curve) == 124
    summary = []
    for j, keep in enumerate(KEEPS):
        errors = [r['relative_l2'][j] for r in curve]
        summary.append({'keep': keep, 'drop_fraction': 1-keep/640,
                        'routed_sum_relative_l2': A.distribution(errors),
                        'covered_expert_relative_l2': A.distribution(covered_errors[j]),
                        'ideal_all_tier_weight_saving_fraction': float(1-byte_kept[j]/byte_full),
                        'ideal_nonresident_weight_saving_fraction': float(1-nr_kept[j]/nr_full),
                        'layer_rows_above_5pct': sum(v > .05 for v in errors),
                        'layer_rows_above_10pct': sum(v > .10 for v in errors),
                        'first_8_relative_l2': A.distribution(errors[:32]),
                        'last_8_relative_l2': A.distribution(errors[-32:])})
    return {'positions': len(positions), 'layer_rows': len(curve), 'expert_calls': calls,
            'covered_calls': covered, 'covered_call_fraction': covered/calls,
            'covered_route_mass_fraction': covered_mass/total_mass,
            'summary': summary, 'curve': curve}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fork', type=Path, required=True)
    ap.add_argument('--lab', type=Path, required=True)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--replayer', type=Path, required=True)
    ap.add_argument('--replayer-sha256', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    assert P.sha(args.replayer) == args.replayer_sha256
    assert not [p.info for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()
                in ('strata.exe', 'neuron_trace_replay.exe', 'hybrid_expert_probe.exe')]
    assert psutil.disk_usage(str(args.lab)).free > 3*1024**3
    config = json.loads(args.config.read_text())
    model = Path(config['args'][config['args'].index('--native')+1])
    protected = [args.config, Path(config['exe'])]
    before = {str(p): P.sha(p) for p in protected}
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
    env['PATH'] = os.pathsep.join(config.get('lib_dirs', []) + [env.get('PATH', '')])
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    args.output.mkdir()
    state = {'status': 'running', 'training_positions': TRAIN,
             'minimum_training_observations': MIN_OBSERVATIONS, 'keeps': KEEPS,
             'scorers': ['mean', 'peak'], 'calibration_isolation': 'Only positions prefix..prefix+31 enter mask construction',
             'screening_rule': 'Consider a compact-kernel follow-up only if one fixed variant has routed mean <=3%, p99 <=10% and ideal weight saving >=3% in each of the three texts. This is an engineering screen, not a model-quality guarantee.',
             'protected_before': before, 'replayer_sha256': P.sha(args.replayer),
             'script_sha256': P.sha(Path(__file__)), 'runs': []}
    try:
        norms = Norms(model, args.fork)
        state['model'] = norms.metadata
        for name in ('code', 'explain', 'reason'):
            folder = args.lab / f'probe100-{name}-normal-v1'
            meta = json.loads((folder/'result.json').read_text())
            prefix = len(meta['prompt_ids'])
            baseline = P.records(folder/'c0-target.snr', b'SNRv0002')
            training = baseline[(baseline['pos'] >= prefix) & (baseline['pos'] < prefix+TRAIN)]
            assert len(training) == 32*4*10
            assert min(training['pos']) == prefix and max(training['pos']) == prefix+31
            for scorer in ('mean', 'peak'):
                began = time.monotonic()
                bank, stats = build_bank(training, norms, scorer)
                mask_seconds = time.monotonic()-began
                stem = f'{name}-{scorer}'
                masks = args.output/(stem+'.snm')
                replay = args.output/(stem+'.snr')
                write_bank(masks, bank)
                assert all(s['last_training_position'] < prefix+32 for s in stats.values())
                command = [str(args.replayer), str(folder/'target/trace.bin'), str(model), str(replay), str(masks)]
                began = time.monotonic()
                with (args.output/(stem+'.log')).open('xb') as log:
                    proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    try:
                        code = proc.wait(timeout=120)
                        assert code == 0, (stem, code)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.wait(timeout=15)
                wall = time.monotonic()-began
                data = P.records(replay, b'SNRv0002')
                assert len(data) == len(baseline) == 2560
                for field in ('serial', 'pos', 'layer', 'expert', 'tier', 'gu', 'down', 'weight', 'h'):
                    assert np.array_equal(data[field], baseline[field]), (stem, field)
                # Full reference and h are unchanged. Old oracle vectors 2..4
                # used a different standalone Q8 quantizer and are not compared.
                assert np.array_equal(data['y'][:, :2], baseline['y'][:, :2]), stem
                evaluation = summarize(data, bank, prefix+32)
                item = {'prompt': name, 'scorer': scorer, 'prefix_tokens': prefix,
                        'training_range_inclusive': [prefix, prefix+31],
                        'test_range_inclusive': [prefix+32, prefix+62],
                        'trained_experts': len(bank), 'training_stats': stats,
                        'mask_construction_including_cold_norms_s': mask_seconds,
                        'diagnostic_replay_wall_s': wall,
                        'trace_sha256': P.sha(folder/'target/trace.bin'),
                        'baseline_sha256': P.sha(folder/'c0-target.snr'),
                        'masks_sha256': P.sha(masks), 'output_sha256': P.sha(replay),
                        'controls': {'full_h_and_y0_to_y1_bitwise': True,
                                     'unseen_and_rare_experts_full_fallback_bitwise': True,
                                     'mask_roundtrip_bitwise': True}, 'evaluation': evaluation}
                state['runs'].append(item)
                print(json.dumps({'run': stem, 'covered': evaluation['covered_call_fraction'],
                                  'summary': evaluation['summary']}), flush=True)
        state['norm_source_hashes'] = norms.hashes
        state['down_decode_scalar_checks'] = sorted(norms.checked)
        state['status'] = 'completed'
    except BaseException as exc:
        state.update(status='failed', error=repr(exc))
        raise
    finally:
        state['protected_after'] = {str(p): P.sha(p) for p in protected}
        assert state['protected_after'] == before
        state['live_engines_after'] = [p.info for p in psutil.process_iter(['name','pid'])
                                      if (p.info['name'] or '').lower() in ('strata.exe', 'neuron_trace_replay.exe')]
        save(args.output/'measurements.json', state)


if __name__ == '__main__':
    main()
