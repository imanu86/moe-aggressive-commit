"""Summarize full and paired hybrid-block probe runs without starting GPU work."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dist(values):
    a = np.asarray(values, dtype=np.float64)
    assert len(a) and np.isfinite(a).all()
    return {'n': len(a), 'mean': float(a.mean()), 'median': float(np.median(a)),
            'p95': float(np.percentile(a, 95)), 'max': float(a.max()), 'min': float(a.min())}


def summarize(cases):
    times = {}
    for row in cases:
        by_name = {a['name']: a for a in row['arms']}
        for name, arm in by_name.items():
            rounds = np.asarray(arm['round_us'], dtype=np.float64)
            assert np.isfinite(rounds).all() and np.all(rounds > 0)
            times.setdefault(name, []).append(float(np.median(rounds)))
        baseline = by_name['gpu3_cpu7']; hybrid = by_name['gpu30_cpu70']
        assert baseline['gpu_active_weight_bytes'] == hybrid['gpu_active_weight_bytes'] == 3 * row['full_expert_bytes']
        assert baseline['cpu_active_weight_bytes'] == hybrid['cpu_active_weight_bytes'] == 7 * row['full_expert_bytes']
        assert row['pack_bitwise_inverse'] and row['cpu_split_l2'] < 1e-5 and row['gpu_split_l2'] < 1e-5
    base = np.asarray(times['gpu3_cpu7']); partial = np.asarray(times['gpu30_cpu70'])
    return {
        'cases': len(cases), 'case_median_latency_us': {name: dist(t) for name, t in times.items()},
        'hybrid_latency_reduction_vs_equal_weight_vram': float(1 - partial.sum() / base.sum()),
        'hybrid_faster_cases': int((partial < base).sum()),
        'per_case_latency_reduction_distribution': dist(1 - partial / base),
        'cpu_partition_relative_l2': dist([r['cpu_split_l2'] for r in cases]),
        'gpu_partition_relative_l2': dist([r['gpu_split_l2'] for r in cases]),
        'hybrid_vs_full_gpu_routed_relative_l2': dist([r['hybrid_vs_gpu_routed_l2'] for r in cases]),
        'full_cpu_vs_full_gpu_routed_relative_l2': dist([r['full_cpu_vs_gpu_routed_l2'] for r in cases]),
        'pack_and_inverse_check_us': dist([r['pack_and_inverse_check_us'] for r in cases]),
        'within_case_max_min_round_ratio': {name: dist([max(a['round_us']) / min(a['round_us'])
                                                     for r in cases for a in r['arms'] if a['name'] == name]) for name in times}
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lab', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    result = {'experiment': 'physical-64-neuron-blocks-gpu30-cpu70', 'date': '2026-10-04',
              'analyzer_sha256': sha(Path(__file__)), 'datasets': json.loads((a.lab / 'datasets.json').read_text()),
              'scope': 'Warm single-token expert microbenchmark. Real captured inputs and routing on four layers, three short prompts. Equal active weight bytes, not identical total CUDA allocations. No online cache, KV allocation, end-to-end generation, or t/s measured.',
              'timing': 'Median of repetitions within each case, then sum over matched cases. Positive reduction means lower hybrid latency. Timed input D2H, CPU quantization, GPU quantization, both compute paths, CPU reduction, partial-result H2D, GPU final merge and synchronization. Packing, weight upload and allocator setup excluded.',
              'runs': [], 'controls': []}
    for phase in ('v1', 'paired-v2'):
        all_cases = []
        for prompt in ('code', 'explain', 'reason'):
            folder = a.lab / f'{prompt}-{phase}'
            meta = json.loads((folder / 'result.json').read_text())
            assert meta['status'] == 'completed' and not meta['remaining_owned']
            assert sha(folder / 'results.jsonl') == meta['result_sha256']
            rows = [json.loads(line) for line in (folder / 'results.jsonl').read_text().splitlines()]
            header, cases = rows[0], rows[1:]
            assert len(cases) == header['cases'] == 40
            assert all(len(arm['round_us']) == header['rounds'] for row in cases for arm in row['arms'])
            data = {'prompt': prompt, 'phase': phase, 'metadata': meta, 'header': header,
                    'summary': summarize(cases), 'per_layer': {str(layer): summarize([r for r in cases if r['layer'] == layer])
                                                              for layer in (0, 1, 35, 36)}, 'cases': cases}
            result['runs'].append(data); all_cases.extend(cases)
            print(json.dumps({'prompt': prompt, 'phase': phase, 'summary': data['summary']}), flush=True)
        result['aggregate_' + phase] = summarize(all_cases)
    for name in ('smoke-v1', 'smoke-parallel-v2', 'pool-ff192-v2', 'pool-ff448-v2', 'pool-ff640-v2'):
        folder = a.lab / name
        meta = json.loads((folder / 'result.json').read_text())
        assert meta['status'] == 'completed' and not meta['remaining_owned']
        result['controls'].append({'name': name, 'metadata': meta, 'log': (folder / 'process.log').read_text()})
    with a.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')


if __name__ == '__main__':
    main()
