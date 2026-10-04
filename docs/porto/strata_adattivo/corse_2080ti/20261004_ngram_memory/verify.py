"""Independent small-matrix calculation, causal split and GPU-repeat checks."""
import argparse
import collections
import json
import os
from pathlib import Path
import subprocess
import time

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import analyze as A
from trace_io import sha, read_rows


def independent(rows, full, n, method, guard):
    # Separate predictor and reducer; no call to Memory/build_memory/evaluate.
    history = collections.defaultdict(list)
    for row in rows[:128]:
        suffix = tuple(full[row['pos']-n+1:row['pos']+1]) if n else ()
        for layer, d in row['layers'].items():
            for i, expert in enumerate(d['ids']):
                history[layer, int(expert), suffix].append((d['x'].astype(np.float64), d['gpu'][i].astype(np.float64)))
    total_hits = candidates = 0; errors = []; covered = []; total_bytes = 0; skipped = 0
    for row in rows[128:]:
        suffix = tuple(full[row['pos']-n+1:row['pos']+1]) if n else ()
        for layer, d in row['layers'].items():
            target = np.zeros(2560); approx = np.zeros(2560)
            for i, expert in enumerate(d['ids']):
                y = d['gpu'][i].astype(np.float64); x = d['x'].astype(np.float64)
                prediction = y.copy(); total_bytes += A.FULL_BYTES[layer]
                vals = history.get((layer, int(expert), suffix))
                if vals:
                    candidates += 1
                    xs = np.array([v[0] for v in vals[-16:]])
                    ys = np.array([v[1] for v in vals[-16:]])
                    if method == 'nearest':
                        distances = np.sum((xs-x)**2, axis=1)
                        which = int(np.argmin(distances))
                        out = ys[which]; residual = float(np.sqrt(distances[which]/np.sum(x*x))); l1 = 1.
                    else:
                        offsets = (xs[:-1]-xs[-1]).T
                        delta = x-xs[-1]
                        gram = offsets.T@offsets
                        lam = .001*max(float(np.trace(gram)/max(1,len(xs)-1)), 1.e-12)
                        c = np.linalg.solve(gram+lam*np.eye(len(xs)-1), offsets.T@delta)
                        coef = np.r_[c, 1-c.sum()]
                        out = coef@ys
                        residual = float(np.linalg.norm(delta-offsets@c)/np.linalg.norm(x))
                        l1 = float(np.abs(coef).sum())
                    if l1 <= 4 and (guard is None or residual <= guard):
                        prediction = out; total_hits += 1; skipped += A.FULL_BYTES[layer]
                        covered.append(float(np.linalg.norm(out-y)/np.linalg.norm(y)))
                target += float(d['weights'][i])*y
                approx += float(d['weights'][i])*prediction
            errors.append(float(np.linalg.norm(approx-target)/np.linalg.norm(target)))
    return {'hits': total_hits, 'candidates': candidates, 'routed': A.dist(errors),
            'covered': A.dist(covered), 'skipped_fraction': skipped/total_bytes}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--measurements', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--replayer', type=Path, required=True)
    ap.add_argument('--model', type=Path, required=True)
    a = ap.parse_args(); a.out = a.out.resolve(); assert not a.out.exists(); a.out.mkdir(parents=True)
    started = time.monotonic(); report = {'status': 'running', 'checks': [], 'verifier_sha256': sha(Path(__file__))}
    measurements = json.loads(a.measurements.read_text())
    # Re-run one identical physical GPU chunk after all capture/replay processes exit.
    src = sorted((a.data/'code/chunks').glob('*.snt'))[0].resolve()
    expected = src.with_suffix('.snr')
    dest = a.out/'repeated-code-chunk.snr'
    assert sha(a.replayer) == '64b55b1bef1b4ef4528ab8be9d7cc7f4465ed878e40ddf3b60bd00667d7a970c'
    env = {k: v for k,v in os.environ.items() if not k.startswith(('STRATA_', 'CUDA_', 'HIP_'))}
    env['PATH'] = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin' + os.pathsep + env['PATH']
    with (a.out/'repeat.log').open('xb') as log:
        result = subprocess.run([str(a.replayer.resolve()), str(src), str(a.model.resolve()), str(dest)],
            env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=180)
    assert result.returncode == 0
    assert sha(dest) == sha(expected), 'repeated GPU replay was not bitwise equal'
    report['checks'].append({'name': 'repeat_GPU_full_chunk_all_fields_bitwise', 'pass': True,
                            'entries': (dest.stat().st_size-40)//A.ENTRY.itemsize,
                            'sha256': sha(dest), 'input_sha256': sha(src)})
    for label in ('code', 'explain', 'reason'):
        meta, rows, full, _ = A.load_case(a.data/label)
        for n, method, guard in ((1, 'nearest', .10), (2, 'nearest', None), (2, 'affine', None), (3, 'affine', .05)):
            actual = independent(rows, full, n, method, guard)
            expected = next(p for p in measurements['texts'][label]['policies'] if (p['n'],p['method'],p['guard']) == (n,method,guard))
            assert actual['hits'] == expected['reused_calls'] and actual['candidates'] == expected['candidate_calls']
            assert actual['skipped_fraction'] == expected['ideal_skipped_fraction']
            for ref, got in ((expected['routed_relative_l2'], actual['routed']), (expected['covered_expert_relative_l2'], actual['covered'])):
                assert ref['count'] == got['count']
                for k in ('mean','median','p95','p99','max'):
                    if ref[k] is None: assert got[k] is None
                    else: assert np.isclose(ref[k], got[k], rtol=1.e-9, atol=1.e-10), (label,n,method,k,ref[k],got[k])
            report['checks'].append({'name': 'independent_prediction_and_routed_reduction', 'text': label,
                                    'n': n, 'method': method, 'guard': guard, 'pass': True})
        # Rebuild from supplied training slice after corrupting every held-out output.
        bank = A.build_memory(rows[:128], full, 2)
        fingerprint = {k: (v.x.copy(), v.y.copy()) for k,v in bank.items()}
        for row in rows[128:]:
            for d in row['layers'].values(): d['gpu'][:] = np.nan
        rebuilt = A.build_memory(rows[:128], full, 2)
        assert fingerprint.keys() == rebuilt.keys()
        for k,v in rebuilt.items():
            assert np.array_equal(v.x, fingerprint[k][0]) and np.array_equal(v.y, fingerprint[k][1])
            assert np.isfinite(v.predict(v.x[-1], 'affine')[0]).all()
        report['checks'].append({'name': 'held_out_output_corruption_does_not_change_memory', 'text': label, 'pass': True})
    report.update(status='completed', elapsed_s=time.monotonic()-started,
                  measurements_sha256=sha(a.measurements), remaining_owned=[])
    A.save(a.out/'verification.json', report)
    print('NGRAM_VERIFICATION_OK', len(report['checks']), 'checks', round(report['elapsed_s'],2), 's', flush=True)


if __name__ == '__main__':
    main()
