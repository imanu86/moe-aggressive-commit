"""Exploratory second stage: update response memory only after full fallback.

Declared after the first frozen-code nearest-neighbor result was inspected.
Thresholds are input-relative residuals, not bounds on model/output error.
Every reuse excludes current/future truth from prediction and memory updates.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import time
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import analyze as A
from trace_io import LAYERS, sha


def run(rows, full, n, method, guard, verify=False):
    raw = collections.defaultdict(lambda: collections.deque(maxlen=A.CAP))
    for row in rows[:A.TRAIN]:
        for layer, d in row['layers'].items():
            for i, expert in enumerate(d['ids']):
                raw[A.key(full,row['pos'],n,layer,expert)].append((row['pos'], d['x'], d['gpu'][i]))
    memories = {}
    errors = []; covered = []; hits = total = candidates = l1_rejections = 0
    residuals = []; candidate_errors = []; cache_reads = saved = full_bytes = 0
    per_layer = {l: {'errors': [], 'covered': [], 'hits': 0, 'calls': 0} for l in LAYERS}
    worst = []
    for row in rows[A.TRAIN:]:
        for layer, d in row['layers'].items():
            delta_sum = np.zeros(2560)
            ref = d['weights'].astype(np.float64) @ d['gpu'].astype(np.float64)
            for i, expert in enumerate(d['ids']):
                k = A.key(full, row['pos'], n, layer, expert)
                previous = raw.get(k)
                use = False; prediction = None
                total += 1; full_bytes += A.FULL_BYTES[layer]; per_layer[layer]['calls'] += 1
                if previous:
                    assert max(v[0] for v in previous) < row['pos'], 'future/current input leaked into memory'
                    candidates += 1
                    if k not in memories:
                        memories[k] = A.Memory([v[1] for v in previous], [v[2] for v in previous])
                    mem = memories[k]
                    prediction, residual, l1, valid = mem.predict(d['x'], method)
                    if verify:
                        # Independent matrix solve, no cached inverse or predict method.
                        x = d['x'].astype(np.float64)
                        xs = np.asarray([v[1] for v in previous], dtype=np.float64)
                        ys = np.asarray([v[2] for v in previous], dtype=np.float64)
                        if method == 'nearest':
                            ix = int(np.argmin(np.sum((xs-x)**2,axis=1)))
                            check = ys[ix]; check_res = np.linalg.norm(xs[ix]-x)/np.linalg.norm(x); check_l1 = 1.
                        else:
                            dx = (xs[:-1]-xs[-1]).T; dy = ys[:-1]-ys[-1]
                            g = dx.T@dx; lam = .001*max(float(np.trace(g)/max(1,len(xs)-1)), 1.e-12)
                            c = np.linalg.solve(g+lam*np.eye(len(xs)-1), dx.T@(x-xs[-1]))
                            check = ys[-1]+c@dy
                            check_res = np.linalg.norm(x-xs[-1]-dx@c)/np.linalg.norm(x)
                            check_l1 = abs(1-c.sum())+np.abs(c).sum()
                        assert np.allclose(check,prediction,rtol=1.e-8,atol=1.e-9)
                        assert np.isclose(check_res,residual,rtol=1.e-9,atol=1.e-10)
                        assert np.isclose(check_l1,l1,rtol=1.e-9,atol=1.e-10)
                    cache_reads += mem.n*2560*4 + (mem.n**2*4 if method == 'affine' else 0)
                    use = valid and residual <= guard
                    residuals.append(residual); l1_rejections += not valid
                    # Truth is accessed for diagnostics only after the decision.
                    error = float(np.linalg.norm(prediction-d['gpu'][i])/np.linalg.norm(d['gpu'][i].astype(np.float64)))
                    candidate_errors.append(error)
                if use:
                    hits += 1; saved += A.FULL_BYTES[layer]; per_layer[layer]['hits'] += 1
                    cache_reads += (1 if method=='nearest' else memories[k].n)*2560*4
                    covered.append(error); per_layer[layer]['covered'].append(error)
                    delta_sum += float(d['weights'][i])*(prediction-d['gpu'][i])
                    # Crucial: a hit neither evaluates nor inserts the current true y.
                else:
                    raw[k].append((row['pos'], d['x'], d['gpu'][i]))
                    memories.pop(k, None)
            err = float(np.linalg.norm(delta_sum)/np.linalg.norm(ref))
            errors.append(err); per_layer[layer]['errors'].append(err)
            if err > .1: worst.append({'pos': row['pos'], 'layer': layer, 'relative_l2': err})
    end = sum(len(v) for v in raw.values())
    result = {'n': n, 'method': method, 'guard': guard, 'calls': total, 'candidate_calls': candidates,
              'reused_calls': hits, 'reused_fraction': hits/total, 'full_fallback_calls': total-hits,
              'input_residual': A.dist(residuals), 'candidate_expert_relative_l2': A.dist(candidate_errors),
              'covered_expert_relative_l2': A.dist(covered), 'routed_relative_l2': A.dist(errors),
              'ideal_skipped_weight_bytes': saved, 'ideal_skipped_fraction': saved/full_bytes,
              'estimated_fp32_cache_read_bytes': cache_reads,
              'ideal_net_read_saving_fraction': (saved-cache_reads)/full_bytes,
              'coefficient_l1_rejections': l1_rejections, 'end_cache_exemplars': end,
              'end_fp32_xy_bytes': end*2560*8, 'layer_rows_above_10pct': len(worst),
              'worst_layer_rows': sorted(worst,key=lambda r:-r['relative_l2'])[:8],
              'independent_prediction_checks': verify, 'layers': {}}
    for layer, s in per_layer.items():
        result['layers'][str(layer)] = {'reused_fraction': s['hits']/s['calls'],
            'routed_relative_l2': A.dist(s['errors']), 'covered_expert_relative_l2': A.dist(s['covered'])}
    result['passes_local_screen'] = (result['routed_relative_l2']['mean'] <= .03
        and result['routed_relative_l2']['p99'] <= .10 and result['ideal_skipped_fraction'] >= .03)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); assert not args.out.exists(); args.out.mkdir(parents=True)
    plan = {'scope': __doc__, 'keys_n': [2,3], 'methods': ['nearest','affine'],
            'guards': [.1,.2,.3], 'initial_inputs': 128, 'max_exemplars_per_key':16,
            'update': 'only after full fallback; no current exact output inserted on a cache hit',
            'screen': 'same mean<=3%, P99<=10%, ideal skipped weight bytes>=3% in all three texts',
            'script_sha256': sha(Path(__file__)), 'analyzer_sha256': sha(Path(A.__file__))}
    A.save(args.out/'plan.json', plan)
    started=time.monotonic(); results={'plan':plan,'texts':{}}
    for label in ('code','explain','reason'):
        _,rows,full,_=A.load_case(args.data/label)
        policies=[]
        for n in (2,3):
            for method in ('nearest','affine'):
                for guard in (.1,.2,.3):
                    p=run(rows,full,n,method,guard,verify=(n==2 and guard==.2))
                    policies.append(p)
                    print('ADAPTIVE',label,n,method,guard,'reuse',round(100*p['reused_fraction'],3),
                          'mean',round(100*p['routed_relative_l2']['mean'],3),
                          'p99',round(100*p['routed_relative_l2']['p99'],3),flush=True)
        results['texts'][label]={'policies':policies}
    common=[]
    for p in results['texts']['code']['policies']:
        matches=[next(q for q in results['texts'][l]['policies']
                    if (q['n'],q['method'],q['guard'])==(p['n'],p['method'],p['guard'])) for l in results['texts']]
        if all(q['passes_local_screen'] for q in matches): common.append({k:p[k] for k in ('n','method','guard')})
    results.update(policies_passing_all_three_texts=common,elapsed_cpu_s=time.monotonic()-started)
    A.save(args.out/'measurements.json',results)
    print('ADAPTIVE_OK',len(common),'common policies pass',round(results['elapsed_cpu_s'],2),'s',flush=True)


if __name__=='__main__': main()
