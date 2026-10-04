"""CPU-only audit of nonresident experts and a hypothetical 3-for-10 pack.

Consumes existing GPU replays, starts no model, and constructs no packed weights.
Masks use candidate activations only; target activations are evaluation data.
Hidden activation energy is NOT output accuracy. Byte figures exclude runtime
alignment/allocator overhead and are estimates for the original quant blocks.
"""
import argparse
import collections
import itertools
import json
from pathlib import Path

import numpy as np

import analyze_probe100 as P
import analyze_trace as A


def ratio(num, den):
    return float(num / den) if den else None


def footprint(mask, geo):
    item = A.mask_footprint(np.flatnonzero(mask), geo)
    # Same explicit index estimate used by the previous candidate-bank audit.
    item['index_bytes_estimate'] = 16 + 2 * item['selected_neurons'] + 2 * item['down_blocks_touched']
    item['bytes_with_indices_estimate'] = item['weight_bytes'] + item['index_bytes_estimate']
    return item


def budget_mask(score, geo, budget):
    """Deterministic marginal energy/byte greedy, not an optimal knapsack solver."""
    mask = np.zeros(640, dtype=bool)
    width = geo['down_block_width']
    blocks = np.zeros(640 // width, dtype=bool)
    used = 16
    neuron_block = np.arange(640) // width
    while True:
        costs = 2 * geo['gu_row_bytes'] + 2 + (~blocks[neuron_block]) * (18 * 2560 + 2)
        fits = (~mask) & (used + costs <= budget)
        if not fits.any():
            break
        values = np.where(fits, score / costs, -1.)
        index = int(np.argmax(values))
        used += int(costs[index])
        mask[index] = True
        blocks[neuron_block[index]] = True
    assert footprint(mask, geo)['bytes_with_indices_estimate'] == used <= budget
    return mask


def self_checks():
    # Independent full-layout totals, plus shared-down-block accounting.
    for gu, down, full in ((17, 20, 1868800), (16, 42, 1305600),
                           (18, 20, 2176000), (18, 42, 1715200)):
        geo = A.geometry(gu, down)
        assert A.mask_footprint(np.arange(640), geo)['weight_bytes'] == full
        first = A.mask_footprint(np.array([0]), geo)['weight_bytes']
        adjacent = A.mask_footprint(np.array([0, 1]), geo)['weight_bytes']
        other = A.mask_footprint(np.array([0, geo['down_block_width']]), geo)['weight_bytes']
        assert adjacent - first == 2 * geo['gu_row_bytes']
        assert other - adjacent == 18 * 2560
        mask = budget_mask(np.ones(640), geo, 3 * full // 10)
        assert 0 < mask.sum() < 640
        assert np.array_equal(mask, budget_mask(np.ones(640), geo, 3 * full // 10))
    a = np.zeros(640, dtype=bool); a[:160] = True
    b = np.zeros(640, dtype=bool); b[160:320] = True
    assert (a & a).sum() / 160 == 1 and (a & b).sum() / 160 == 0
    return 'passed: four full byte totals, quant block sharing, budget, determinism, overlap'


def evaluate_pack(rows, packs):
    """Full fallback for every unseen/non-packed identity; resident rows unchanged."""
    count = covered = 0; mass = covered_mass = 0.
    full_bytes = all_bytes = saved_bytes = 0
    energy = kept_energy = 0.; per_call = []
    for row in rows:
        geo = A.geometry(int(row['gu']), int(row['down']))
        all_bytes += geo['full_expert_weight_bytes']
        if row['tier'] == 1:
            continue
        count += 1; w = abs(float(row['weight'])); mass += w
        full_bytes += geo['full_expert_weight_bytes']
        key = (int(row['layer']), int(row['expert']))
        if key not in packs:
            continue
        covered += 1; covered_mass += w
        saved_bytes += geo['full_expert_weight_bytes'] - footprint(packs[key], geo)['bytes_with_indices_estimate']
        h2 = row['h'].astype(np.float64) ** 2
        total = float(h2.sum()); kept = float(h2[packs[key]].sum())
        energy += w ** 2 * total; kept_energy += w ** 2 * kept
        per_call.append(ratio(kept, total))
    return {'positions': len(set(rows['pos'])), 'nonresident_calls': count,
            'nonresident_calls_covered': covered,
            'nonresident_call_fraction_covered': ratio(covered, count),
            'nonresident_route_mass_fraction_covered': ratio(covered_mass, mass),
            'covered_hidden_energy_fraction_weighted_h2': ratio(kept_energy, energy),
            'covered_hidden_energy_fraction_per_call': A.distribution(per_call),
            'ideal_nonresident_weight_read_saving_fraction': ratio(saved_bytes, full_bytes),
            'ideal_all_tier_weight_read_saving_fraction': ratio(saved_bytes, all_bytes)}


def analyze_run(root, kind):
    run = root / f'probe100-{kind}-normal-v1'
    cycle = json.loads((run / 'cycle-0.json').read_text(encoding='utf-8'))
    start = cycle['prefix_tokens']
    sources = [{'path': str((run / name).relative_to(root)).replace('\\', '/'),
                'sha256': P.sha(run / name)} for name in ('cycle-0.json', 'c0-masks.snm')]

    def read(path, version):
        data = P.records(path, version)
        sources.append({'path': str(path.relative_to(root)).replace('\\', '/'),
                        'sha256': P.sha(path), 'records': len(data)})
        return data

    target = read(run / 'c0-target.snr', b'SNRv0002')
    target = target[target['pos'] >= start]  # Exclude last prompt input.
    assert len(target) == 63 * 4 * 10
    assert set(target['layer']) == set(A.LAYERS)
    assert np.all((target['tier'] >= 0) & (target['tier'] <= 2))
    assert set(target['pos']) == set(range(start, start + 63))
    geos = {}
    candidates = {}
    for branch in range(10):
        data = read(run / f'c0-candidate-{branch}.snr', b'SNRv0001')
        for row in data:
            if row['pos'] < start:
                continue
            key = (int(row['layer']), int(row['expert']))
            geo = A.geometry(int(row['gu']), int(row['down']))
            assert key not in geos or geos[key] == geo
            geos[key] = geo
            entry = candidates.setdefault(key, {'score': np.zeros(640), 'mass': 0., 'calls': 0, 'tiers': set()})
            weight = abs(float(row['weight']))
            entry['score'] += weight ** 2 * row['h'].astype(np.float64) ** 2
            entry['mass'] += weight
            entry['calls'] += 1
            entry['tiers'].add(int(row['tier']))
    assert sum(e['calls'] for e in candidates.values()) == 4000
    nr_keys = {key for key, e in candidates.items() if 1 not in e['tiers']}
    mixed = [list(key) for key, e in candidates.items() if 1 in e['tiers'] and len(e['tiers']) > 1]
    packs = {}; pack_details = []
    for layer in A.LAYERS:
        ranked = sorted((key for key in nr_keys if key[0] == layer),
                        key=lambda key: (-candidates[key]['mass'], key))
        assert len(ranked) >= 10
        selected = ranked[:10]
        geo = geos[selected[0]]
        assert all(geos[key] == geo for key in selected)
        details = []
        for key in selected:
            mask = budget_mask(candidates[key]['score'], geo, 3 * geo['full_expert_weight_bytes'] // 10)
            packs[key] = mask
            details.append({'expert': key[1], 'candidate_calls': candidates[key]['calls'],
                            'candidate_route_mass': candidates[key]['mass'],
                            'indices': np.flatnonzero(mask).tolist(), **footprint(mask, geo)})
        size = sum(item['bytes_with_indices_estimate'] for item in details)
        limit = 3 * geo['full_expert_weight_bytes']
        assert size <= limit
        pack_details.append({'layer': layer, 'candidate_nonresident_identities': len(ranked),
                             'full_expert_bytes': geo['full_expert_weight_bytes'],
                             'pack_limit_bytes': limit, 'pack_bytes_estimate': size,
                             'equivalent_full_experts': size / geo['full_expert_weight_bytes'],
                             'experts': details})

    bank = P.read_bank(run / 'c0-masks.snm')
    union_bytes = union_full = 0
    for key in nr_keys:
        assert key in bank
        union_bytes += footprint(bank[key][0].astype(bool), geos[key])['bytes_with_indices_estimate']
        union_full += geos[key]['full_expert_weight_bytes']

    tier_counts = collections.Counter(); tier_mass = collections.Counter()
    oracle_bytes = nr_full = 0
    total_mass = 0.
    oracle_errors = []; oracle_nr_errors = []; oracle_energy = []
    per_expert = collections.defaultdict(list)
    groups = collections.defaultdict(list)
    for row in target:
        tier = int(row['tier']); key = (int(row['layer']), int(row['expert']))
        w = abs(float(row['weight'])); geo = A.geometry(int(row['gu']), int(row['down']))
        tier_counts[tier] += 1; tier_mass[tier] += w; total_mass += w
        groups[(int(row['pos']), key[0])].append(row)
        if tier == 1:
            continue
        nr_full += geo['full_expert_weight_bytes']
        h2 = row['h'].astype(np.float64) ** 2
        mask = np.zeros(640, dtype=bool); mask[A.selected(row['h'], 160)] = True
        per_expert[key].append(mask)
        oracle_bytes += footprint(mask, geo)['bytes_with_indices_estimate']
        oracle_energy.append(ratio(h2[mask].sum(), h2.sum()))
    for rows in groups.values():
        assert len(rows) == 10 and len({int(r['expert']) for r in rows}) == 10
        full = np.zeros(2560); approximate = np.zeros(2560)
        nr = np.zeros(2560); nr_approx = np.zeros(2560)
        for row in rows:
            w = float(row['weight']); original = w * row['y'][0].astype(np.float64)
            reduced = w * row['y'][2].astype(np.float64) if row['tier'] != 1 else original
            full += original; approximate += reduced
            if row['tier'] != 1:
                nr += original; nr_approx += reduced
        oracle_errors.append(A.rel_l2(approximate, full))
        if np.any(nr):
            oracle_nr_errors.append(A.rel_l2(nr_approx, nr))

    stats = {
        'prompt': kind, 'prefix_tokens': start, 'target_input_positions': 63,
        'tier_calls': {A.TIERS[t]: tier_counts[t] for t in range(3)},
        'tier_route_mass_fraction': {A.TIERS[t]: tier_mass[t] / total_mass for t in range(3)},
        'nonresident_unique_layer_experts': len(per_expert),
        'mixed_residency_candidate_keys': mixed,
        'candidate_union_top160_nonresident_fraction_with_indices': ratio(union_bytes, union_full),
        'oracle_current_top160': {
            'nonresident_weight_fraction_with_indices': ratio(oracle_bytes, nr_full),
            'hidden_energy_fraction_per_call': A.distribution(oracle_energy),
            'gpu_local_routed_sum_error_resident_unchanged': A.distribution(oracle_errors),
            'gpu_local_nonresident_sum_error': A.distribution(oracle_nr_errors)},
        'candidate_trained_three_for_ten': {
            'selection': 'top ten never-VRAM candidate identities per layer by route mass; equal byte budgets; marginal weighted-h2/byte greedy',
            'per_layer': pack_details,
            'first_10_positions': evaluate_pack(target[target['pos'] < start + 10], packs),
            'first_20_positions': evaluate_pack(target[target['pos'] < start + 20], packs),
            'all_63_positions': evaluate_pack(target, packs),
            'packed_output_error': None,
            'packed_output_error_status': 'not replayed; h energy is not output quality; no runtime pack exists'},
        'sources': sources,
    }
    return stats, per_expert


def recurrence(histories):
    out = []
    for (name_a, a), (name_b, b) in itertools.combinations(histories.items(), 2):
        matched = []
        for key in sorted(a.keys() & b.keys()):
            if min(len(a[key]), len(b[key])) < 2:
                continue
            aa = np.stack(a[key]).astype(np.float64)
            bb = np.stack(b[key]).astype(np.float64)
            # Equal expert weighting. All pairs avoid short/long gap confounding
            # of a consecutive-only comparison; token distributions still differ.
            wa = (np.sum(aa @ aa.T) - len(aa) * 160) / (len(aa) * (len(aa) - 1) * 160)
            wb = (np.sum(bb @ bb.T) - len(bb) * 160) / (len(bb) * (len(bb) - 1) * 160)
            cross = float(np.mean(aa @ bb.T) / 160)
            matched.append({'layer': key[0], 'expert': key[1], 'calls_a': len(aa), 'calls_b': len(bb),
                            'within_a_mean_overlap': float(wa), 'within_b_mean_overlap': float(wb),
                            'cross_mean_overlap': cross, 'within_minus_cross': float((wa + wb) / 2 - cross)})
        out.append({'prompts': [name_a, name_b], 'matched_experts': len(matched),
                    'within_mean_overlap': A.distribution([(r['within_a_mean_overlap'] + r['within_b_mean_overlap']) / 2 for r in matched]),
                    'cross_mean_overlap': A.distribution([r['cross_mean_overlap'] for r in matched]),
                    'within_minus_cross': A.distribution([r['within_minus_cross'] for r in matched]),
                    'per_expert': matched})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'experiment': 'nonresident-three-for-ten-cpu-audit', 'date': '2026-10-04',
              'self_checks': self_checks(), 'analyzer_sha256': P.sha(Path(__file__)),
              'scope': 'Three cycle-0 candidate sets (300 positions), 189 actual continuation inputs, four layers 0/1/35/36; short prefixes 85-102 tokens, KV capacity 262144/resident32768; same recorded normalpages+8GiB-pin configuration as probe100.',
              'limits': ['One text per genre cannot establish theme specialization or deep-context stability.',
                         'Original execution tier is recorded online; all h and y here are GPU local replay.',
                         'No online compressed generation, physical pack, latency improvement, or answer-quality claim.',
                         '3-for-10 uses ten identities PER LAYER, not ten simultaneous active experts or a whole-model 3-expert budget.',
                         'Byte estimate includes index estimates but excludes runtime alignment, allocator overhead and rebuilding cost.',
                         'Original-quant-block greedy mask is a heuristic, not a compressibility bound.'], 'runs': []}
    histories = {}
    for kind in ('code', 'explain', 'reason'):
        stats, history = analyze_run(args.lab, kind)
        result['runs'].append(stats); histories[kind] = history
        print(json.dumps({'prompt': kind, 'tiers': stats['tier_calls'],
                          'pack': {k: v for k, v in stats['candidate_trained_three_for_ten'].items() if k != 'per_layer'}}, allow_nan=False), flush=True)
    result['matched_nonresident_top160_recurrence'] = recurrence(histories)
    P.save(args.output, result)


if __name__ == '__main__':
    main()
