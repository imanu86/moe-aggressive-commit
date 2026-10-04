"""Frozen, causal n-gram response memory. CPU only; no model or weights loaded.

The affine predictor interpolates complete nonlinear expert responses. It is
not an exact Wb cache for each linear projection. Reference outputs are never
passed to prediction/selection, and the cache is never updated on held-out data.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import sys
import time

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
from trace_io import LAYERS, read_rows, sha

sys.dont_write_bytecode = True
TRAIN = 128
CAP = 16
RIDGE = .001
GUARDS = (None, .01, .03, .05, .10)
L1_CAP = 4.
FULL_BYTES = {0: 1868800, 1: 1305600, 35: 2176000, 36: 1715200}
FORMATS = {0: (17, 20), 1: (16, 42), 35: (18, 20), 36: (18, 42)}
ENTRY = np.dtype([('serial', '<u8'), ('pos', '<i8'), ('layer', '<i4'), ('expert', '<i4'),
    ('tier', '<i4'), ('gu', '<i4'), ('down', '<i4'), ('cold', '<i4'), ('weight', '<f4'),
    ('h', '<f4', (640,)), ('y', '<f4', (8, 2560))])
assert ENTRY.itemsize == 84524


def save(path, value):
    with Path(path).open('xb') as f:
        f.write((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode())


def dist(values):
    x = np.asarray(values, dtype=np.float64)
    assert np.isfinite(x).all()
    if not len(x):
        return {'count': 0, 'mean': None, 'median': None, 'p95': None, 'p99': None, 'max': None}
    return {'count': len(x), 'mean': float(x.mean()), 'median': float(np.median(x)),
            'p95': float(np.percentile(x, 95)), 'p99': float(np.percentile(x, 99)), 'max': float(x.max())}


class Memory:
    """Only calibration x/y enter construction; query accepts current x alone."""
    def __init__(self, xs, ys):
        self.x = np.asarray(xs, dtype=np.float64)
        self.y = np.asarray(ys, dtype=np.float64)
        self.n = len(xs)
        self.dx = self.x[:-1] - self.x[-1]
        self.dy = self.y[:-1] - self.y[-1]
        gram = self.dx @ self.dx.T
        scale = float(np.trace(gram) / max(1, self.n-1))
        self.reg = RIDGE * max(scale, 1.e-12)
        self.gram = gram
        self.inverse = np.linalg.inv(gram + self.reg*np.eye(self.n-1)) if self.n > 1 else None

    def predict(self, x, method):
        x = np.asarray(x, dtype=np.float64)
        norm = float(np.linalg.norm(x))
        assert norm > 0
        if method == 'nearest':
            residuals = np.linalg.norm(self.x-x, axis=1) / norm
            i = int(np.argmin(residuals))
            return self.y[i].copy(), float(residuals[i]), 1., True
        assert method == 'affine'
        delta = x-self.x[-1]
        if self.n == 1:
            return self.y[-1].copy(), float(np.linalg.norm(delta)/norm), 1., True
        coeff = self.inverse @ (self.dx @ delta)
        residual = float(np.linalg.norm(delta-coeff@self.dx)/norm)
        l1 = float(abs(1-coeff.sum())+np.abs(coeff).sum())
        prediction = self.y[-1] + coeff@self.dy
        assert np.isfinite(prediction).all() and np.isfinite(residual) and np.isfinite(l1)
        return prediction, residual, l1, l1 <= L1_CAP


def key(full, pos, n, layer, expert):
    assert n == 0 or pos+1 >= n
    return (layer, int(expert), tuple(full[pos-n+1:pos+1]) if n else ())


def load_case(folder):
    meta = json.loads((folder/'capture.json').read_text())
    rows = read_rows(folder/'trace.snt')
    assert sha(folder/'trace.snt') == meta['trace_sha256']
    full = meta['prompt_ids'] + meta['generated_ids']
    assert len(rows) == meta['accepted_inputs'] and len(rows) > TRAIN
    assert all(full[row['pos']] == row['token'] for row in rows)
    indexed = {r['pos']: r for r in rows}
    filled = set(); backend = collections.defaultdict(list); formats = set(); sources = []
    for path in sorted((folder/'chunks').glob('*.snr')):
        with path.open('rb') as stream:
            header = stream.read(40)
        from trace_io import HEADER
        assert header == b'SNRv0001'+HEADER[8:]
        assert (path.stat().st_size-40) % ENTRY.itemsize == 0
        arr = np.memmap(path, mode='r', offset=40, dtype=ENTRY)
        assert np.isfinite(arr['y'][:, 0]).all()
        for r in arr:
            pos, layer, expert = int(r['pos']), int(r['layer']), int(r['expert'])
            assert (pos, layer, expert) not in filled
            filled.add((pos, layer, expert))
            row = indexed[pos]; data = row['layers'][layer]
            assert int(r['serial']) == row['serial']
            i = list(data['ids']).index(expert)
            assert r['weight'].tobytes() == data['weights'][i].tobytes()
            assert int(r['tier']) == int(data['tiers'][i])
            assert (int(r['gu']), int(r['down'])) == FORMATS[layer]
            formats.add(FORMATS[layer])
            if 'gpu' not in data:
                data['gpu'] = np.empty_like(data['parts'])
            y = r['y'][0]
            data['gpu'][i] = y
            den = np.linalg.norm(y.astype(np.float64))
            assert den > 0
            backend[int(r['tier'])].append(float(np.linalg.norm(data['parts'][i].astype(np.float64)-y)/den))
        sources.append({'file': path.name, 'sha256': sha(path), 'entries': len(arr)})
    assert len(filled) == len(rows)*40 and formats == set(FORMATS.values())
    return meta, rows, full, {'replays': sources, 'original_backend_vs_gpu_relative_l2':
                           {str(k): dist(v) for k, v in sorted(backend.items())}}


def build_memory(rows, full, n):
    raw = collections.defaultdict(lambda: collections.deque(maxlen=CAP))
    for row in rows:
        for layer, d in row['layers'].items():
            for i, expert in enumerate(d['ids']):
                raw[key(full, row['pos'], n, layer, expert)].append((d['x'], d['gpu'][i]))
    return {k: Memory([v[0] for v in vals], [v[1] for v in vals]) for k, vals in raw.items()}


def evaluate(rows, full, bank, n, method):
    stats = {g: {'routed': [], 'covered': [], 'layers': {l: {'routed': [], 'covered': [], 'hits': 0,
             'candidate_calls': 0, 'scan_bytes': 0, 'saved_bytes': 0, 'response_bytes': 0} for l in LAYERS},
             'hits': 0, 'saved_bytes': 0, 'scan_bytes': 0, 'response_bytes': 0} for g in GUARDS}
    candidate_errors = []; residuals = []; candidate_counts = 0; rejected_l1 = 0
    # Scalar audit samples make checking the input guard possible without storing
    # a second copy of every 2560-element prediction.
    audit = []
    for row in rows:
        for layer, d in row['layers'].items():
            ref = d['weights'].astype(np.float64) @ d['gpu'].astype(np.float64)
            ref_norm = float(np.linalg.norm(ref)); assert ref_norm > 0
            differences = {g: np.zeros(2560) for g in GUARDS}
            for i, expert in enumerate(d['ids']):
                memory = bank.get(key(full, row['pos'], n, layer, expert))
                if memory is None:
                    continue
                prediction, residual, l1, valid = memory.predict(d['x'], method)
                delta = prediction-d['gpu'][i]
                error = float(np.linalg.norm(delta)/np.linalg.norm(d['gpu'][i].astype(np.float64)))
                candidate_counts += 1; candidate_errors.append(error); residuals.append(residual)
                rejected_l1 += not valid
                audit.append((row['pos'], layer, int(expert), residual, l1, error, memory.n))
                # Hypothetical FP32 implementation: keys and common output writes
                # omitted; every hit scans X, accepted hits also read Y. Gram work
                # is not a measured kernel and this is not a bandwidth benchmark.
                scan = memory.n*2560*4 + (memory.n**2*4 if method == 'affine' else 0)
                response = (1 if method == 'nearest' else memory.n)*2560*4
                for guard, s in stats.items():
                    ls = s['layers'][layer]
                    ls['candidate_calls'] += 1
                    s['scan_bytes'] += scan; ls['scan_bytes'] += scan
                    if valid and (guard is None or residual <= guard):
                        differences[guard] += float(d['weights'][i])*delta
                        s['covered'].append(error); ls['covered'].append(error)
                        s['hits'] += 1; ls['hits'] += 1
                        s['saved_bytes'] += FULL_BYTES[layer]; ls['saved_bytes'] += FULL_BYTES[layer]
                        s['response_bytes'] += response; ls['response_bytes'] += response
            for guard, s in stats.items():
                error = float(np.linalg.norm(differences[guard])/ref_norm)
                s['routed'].append(error); s['layers'][layer]['routed'].append(error)
    total_bytes = len(rows)*10*sum(FULL_BYTES.values())
    result = []
    for guard, s in stats.items():
        summary = {'n': n, 'method': method, 'guard': guard, 'held_out_inputs': len(rows),
                   'calls': len(rows)*40, 'reused_calls': s['hits'], 'reused_fraction': s['hits']/(len(rows)*40),
                   'candidate_calls': candidate_counts, 'candidate_fraction': candidate_counts/(len(rows)*40),
                   'coefficient_l1_rejections': rejected_l1, 'routed_relative_l2': dist(s['routed']),
                   'covered_expert_relative_l2': dist(s['covered']), 'ideal_skipped_weight_bytes': s['saved_bytes'],
                   'baseline_weight_bytes': total_bytes, 'ideal_skipped_fraction': s['saved_bytes']/total_bytes,
                   'estimated_fp32_cache_read_bytes': s['scan_bytes']+s['response_bytes'],
                   'ideal_net_read_saving_fraction': (s['saved_bytes']-s['scan_bytes']-s['response_bytes'])/total_bytes,
                   'layers': {}}
        for layer, ls in s['layers'].items():
            denom = len(rows)*10*FULL_BYTES[layer]
            summary['layers'][str(layer)] = {'reused_calls': ls['hits'], 'reused_fraction': ls['hits']/(len(rows)*10),
                'candidate_calls': ls['candidate_calls'], 'routed_relative_l2': dist(ls['routed']),
                'covered_expert_relative_l2': dist(ls['covered']),
                'ideal_skipped_fraction': ls['saved_bytes']/denom,
                'ideal_net_read_saving_fraction': (ls['saved_bytes']-ls['scan_bytes']-ls['response_bytes'])/denom}
        summary['passes_local_screen'] = (summary['routed_relative_l2']['mean'] <= .03
            and summary['routed_relative_l2']['p99'] <= .10 and summary['ideal_skipped_fraction'] >= .03)
        result.append(summary)
    return result, {'candidate_error': dist(candidate_errors), 'input_residual': dist(residuals), 'audit': audit}


def controls():
    rng = np.random.default_rng(20261004)
    x = rng.normal(size=(8, 32)); y = rng.normal(size=(8, 24))
    bank = Memory(x, y)
    assert np.array_equal(bank.predict(x[2], 'nearest')[0], y[2])
    assert np.array_equal(bank.predict(x[-1], 'affine')[0], y[-1])
    assert bank.predict(x[-1], 'affine')[1] == 0
    pred = bank.predict(x[2], 'nearest')[0]
    future_y = rng.normal(size=24)  # held-out truth is intentionally not an API input
    future_y *= 999
    assert np.array_equal(pred, bank.predict(x[2], 'nearest')[0])
    linear = rng.normal(size=(32, 24)); offset = rng.normal(size=24)
    linear_bank = Memory(x, x@linear+offset)
    query = .3*x[0]+.7*x[-1]
    prediction, residual, l1, valid = linear_bank.predict(query, 'affine')
    rel = float(np.linalg.norm(prediction-(query@linear+offset))/np.linalg.norm(query@linear+offset))
    assert valid and residual < .01 and rel < .01
    # Repeated token key with unrelated internal context must not pass a tight guard.
    one = Memory([[1., 0.]], [[2., 0.]])
    assert one.predict([0., 1.], 'nearest')[1] > .10
    assert one.predict([0., 1.], 'affine')[1] > .10
    duplicate = Memory(np.repeat(x[-1:], 16, axis=0), np.repeat(y[-1:], 16, axis=0))
    assert np.array_equal(duplicate.predict(x[-1], 'affine')[0], y[-1])
    # Calibration deque must evict old rows, never read beyond the supplied prefix.
    deque = collections.deque(range(20), maxlen=CAP)
    assert list(deque) == list(range(4, 20))
    return {'duplicate_input_nearest_bitwise': True, 'duplicate_anchor_affine_bitwise': True,
            'rank_deficient_basis': True, 'context_collision_rejected': True,
            'predictor_has_no_current_output_argument': True, 'future_output_perturbation': True,
            'known_affine_map_relative_l2': rel, 'known_affine_map_input_residual': residual}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(); assert not a.out.exists(); a.out.mkdir(parents=True)
    capture = json.loads((a.data/'capture-results.json').read_text())
    assert capture['status'] == 'completed' and capture['protected_files_unchanged'] and not capture['remaining_owned']
    started = time.monotonic(); report = {'schema': 1, 'scope': __doc__, 'calibration_inputs': TRAIN,
        'max_exemplars_per_key': CAP, 'ridge_fraction': RIDGE, 'l1_cap': L1_CAP,
        'protocol_sha256': sha(Path(__file__).with_name('protocol.json')), 'capture_sha256': sha(a.data/'capture-results.json'),
        'analyzer_sha256': sha(Path(__file__)), 'reader_sha256': sha(Path(__file__).with_name('trace_io.py')),
        'controls': controls(), 'texts': {}}
    for label in ('code', 'explain', 'reason'):
        meta, rows, full, provenance = load_case(a.data/label)
        train, test = rows[:TRAIN], rows[TRAIN:]
        assert max(r['pos'] for r in train) < min(r['pos'] for r in test)
        case = {'prompt_tokens': len(meta['prompt_ids']), 'generated_tokens': len(meta['generated_ids']),
                'training_position_range': [train[0]['pos'], train[-1]['pos']],
                'held_out_position_range': [test[0]['pos'], test[-1]['pos']],
                'train_inputs': len(train), 'held_out_inputs': len(test), 'provenance': provenance,
                'recurrence': {}, 'memory': {}, 'policies': []}
        for n in (0, 1, 2, 3):
            if n:
                seen = set(); recurrent = 0
                for row in rows:
                    k = tuple(full[row['pos']-n+1:row['pos']+1]); recurrent += k in seen; seen.add(k)
                frozen = {tuple(full[r['pos']-n+1:r['pos']+1]) for r in train}
                hits = sum(tuple(full[r['pos']-n+1:r['pos']+1]) in frozen for r in test)
                case['recurrence'][str(n)] = {'total_repeat_inputs': recurrent,
                    'held_out_ngram_in_calibration': hits, 'held_out_fraction': hits/len(test)}
            bank = build_memory(train, full, n)
            count = sum(b.n for b in bank.values())
            case['memory'][str(n)] = {'keys': len(bank), 'exemplars': count,
                 'exemplars_per_key': dist([b.n for b in bank.values()]),
                 'fp32_x_and_y_bytes': count*2560*4*2,
                 'fp32_gram_bytes': sum(b.n*b.n*4 for b in bank.values())}
            for method in ('nearest', 'affine'):
                summaries, diagnostics = evaluate(test, full, bank, n, method)
                case['policies'].extend(summaries)
                audit = np.asarray(diagnostics.pop('audit'), dtype=np.float64).reshape(-1, 7)
                path = a.out/f'{label}-n{n}-{method}-audit.npz'
                np.savez_compressed(path, columns=np.array(['pos', 'layer', 'expert', 'input_residual', 'coefficient_l1', 'expert_error', 'exemplars']), rows=audit)
                case.setdefault('diagnostics', {})[f'n{n}-{method}'] = {**diagnostics, 'audit_sha256': sha(path)}
                print('ANALYZED', label, 'n', n, method, 'candidates', summaries[0]['candidate_calls'], flush=True)
        report['texts'][label] = case
    common = []
    for p in report['texts']['code']['policies']:
        candidates = [next(v for v in report['texts'][label]['policies']
            if (v['n'], v['method'], v['guard']) == (p['n'], p['method'], p['guard'])) for label in ('code','explain','reason')]
        if all(v['passes_local_screen'] for v in candidates):
            common.append({k: p[k] for k in ('n','method','guard')})
    report['policies_passing_all_three_texts'] = common
    report['elapsed_cpu_s'] = time.monotonic()-started
    save(a.out/'measurements.json', report)
    print('NGRAM_ANALYSIS_OK', len(common), 'common policies pass', round(report['elapsed_cpu_s'],2), 's', flush=True)


if __name__ == '__main__':
    main()
