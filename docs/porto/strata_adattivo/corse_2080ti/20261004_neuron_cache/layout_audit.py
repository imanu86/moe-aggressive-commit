"""CPU-only storage audit; selected masks are hypotheses, not measured activations.

Example: python layout_audit.py --layout /pack/native_experts.txt --out layout.json
No weights are read, no model is executed, and no inference speedup is inferred.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

H, FF = 2560, 640
# Verified against the Daily ggml structs: type -> (name, weights/block, bytes/block).
DOWN = {42: ('Q2_0', 64, 18), 20: ('IQ4_NL', 32, 18)}


def layers_from(path):
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    header = re.search(r'n_expert (\d+), total (\d+)', text)
    if not header:
        raise ValueError('Expected a native v3/v4 header with expert count and total bytes')
    experts, total = map(int, header.groups())
    layers = []
    offset = 0
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        layer, gu_type, d_type, start, blob = map(int, line.split()[:5])
        if d_type not in DOWN:
            raise ValueError(f'Unvalidated down type {d_type}; do not guess its layout')
        name, width, size = DOWN[d_type]
        assert layer == len(layers) and start == offset
        down = H * (FF // width) * size
        assert FF % width == 0 and (blob - down) % (2 * FF) == 0
        gu_row = (blob - down) // (2 * FF)
        assert gu_row > 0
        layers.append({'layer': layer, 'gu_type': gu_type, 'd_type': d_type,
                       'down_format': name, 'block_width': width, 'block_bytes': size,
                       'gu_row_bytes': gu_row, 'gate_bytes': gu_row * FF,
                       'up_bytes': gu_row * FF, 'down_bytes': down, 'blob_bytes': blob})
        offset += blob * experts
    assert len(layers) == 48 and experts == 512 and offset == total
    return layers, experts, total, hashlib.sha256(raw).hexdigest()


def footprint(layer, indices):
    assert len(set(indices)) == len(indices) and all(0 <= i < FF for i in indices)
    blocks = {i // layer['block_width'] for i in indices}
    gu = 2 * layer['gu_row_bytes'] * len(indices)
    down = len(blocks) * layer['block_bytes'] * H
    return {'kept_neurons': len(indices), 'down_blocks_touched': len(blocks),
            'down_block_fraction': len(blocks) / (FF // layer['block_width']),
            'gate_up_bytes': gu, 'down_bytes': down, 'weight_bytes': gu + down,
            'weight_fraction': (gu + down) / layer['blob_bytes']}


def top_abs_group_invariant():
    # Structural checks on synthetic vectors, NOT real model activations and
    # NOT a CUDA/kernel parity or model-quality test. Positions remain unchanged.
    cases = [[0.0] * FF, [(-1.0 if i % 2 else 1.0) for i in range(FF)],
             [math.sin(i * 0.713) * (1 + i % 29) for i in range(FF)],
             [float((i * 97) % 41 - 20) for i in range(FF)]]
    checked = 0
    for h in cases:
        for k in (1, 160, 320, 480, 640):
            selected = set(sorted(range(FF), key=lambda i: abs(h[i]), reverse=True)[:k])
            for start in range(0, FF, 32):
                group = range(start, start + 32)
                if not any(i in selected for i in group):
                    continue
                original = max(abs(h[i]) for i in group)
                masked = max(abs(h[i]) if i in selected else 0.0 for i in group)
                assert original == masked
                checked += 1
    return {'synthetic_vectors': len(cases), 'nonempty_groups_checked': checked,
            'result': 'Every nonempty original group preserves amax under exact top-|h| selection.',
            'scope': 'Mathematical/CPU structural check only. No arbitrary predictor, weighted ranking, compacted regrouping, GPU parity or quality claim.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--layout', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        ap.error('Output exists; preserve it and choose a new name')
    layers, experts, total, digest = layers_from(args.layout)
    rows = []
    for k in (160, 320, 480):
        masks = {'contiguous_from_zero': list(range(k)),
                 'evenly_dispersed': [(j * FF) // k for j in range(k)]}
        for pattern, indices in masks.items():
            measurements = [dict(layer=l['layer'], down_format=l['down_format'], **footprint(l, indices)) for l in layers]
            packed = sum(m['weight_bytes'] for m in measurements) * experts
            rows.append({'kept_fraction': k / FF, 'mask_pattern': pattern,
                         'total_weight_bytes_if_applied_to_every_expert': packed,
                         'fraction_of_all_expert_weights': packed / total,
                         'per_layer': measurements})
    for layer in layers:
        assert footprint(layer, [])['weight_bytes'] == 0
        assert footprint(layer, list(range(FF)))['weight_bytes'] == layer['blob_bytes']
    report = {
        'scope': 'Exact storage arithmetic for the observed pack layout under hypothetical neuron masks; not measured sparsity, transfer traffic, latency, quality, or a realizable whole-model cache budget.',
        'layout_sha256': digest, 'hidden': H, 'intermediate': FF, 'experts_per_layer': experts,
        'layers': layers, 'down_layer_counts': dict(Counter(l['down_format'] for l in layers)),
        'weight_bytes': {'total': total, **{role: sum(l[role + '_bytes'] for l in layers) * experts for role in ('gate', 'up', 'down')}},
        'assumptions': [
            'Only selected original gate/up rows and whole touched original down quantization blocks are retained.',
            'The 25%/75% contiguous masks are aligned to 32-wide activation groups but end halfway through a 64-wide Q2_0 block; that block is still counted in full.',
            'The same mask size/pattern is applied to every expert solely to normalize storage totals. Actual routing, overlap across candidates and reuse are not known.',
            'Predictor state, mappings, allocation alignment, scratch, cache churn and non-expert model weights are excluded.',
            'A new sparse-code or transposed format may avoid whole-block retention, but it must carry original scales or introduce requantization and needs a different cost model.',
            'No inference gain follows directly from the byte ratios; preparation and kernel costs must be measured.',
        ],
        'scenarios': rows, 'top_abs_original_group_check': top_abs_group_invariant(),
        'next_measurement': 'Capture real h, true router weights and expert outputs on CPU/VRAM/PCIe paths; compare error and mask unions on held-out future tokens before building a compact-cache kernel.'
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'total_expert_gib': total / 2**30, 'down_layer_counts': report['down_layer_counts'],
                      'scenarios': [{k: r[k] for k in ('kept_fraction', 'mask_pattern', 'fraction_of_all_expert_weights')} for r in rows],
                      'top_abs_original_group_check': report['top_abs_original_group_check']}, indent=2))


if __name__ == '__main__':
    main()
