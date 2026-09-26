"""Diagnostic node-trace comparison only; not an unprofiled speed benchmark."""
import json
import pathlib
import sqlite3
import statistics

lab = pathlib.Path(r'D:\ds4_work\qwen4b_kernel_lab')
root = pathlib.Path(r'D:\ds4_work\qwen4b_campaign')


def summarize(path):
    c = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    rows = c.execute('''
        SELECT s.value AS name,k.gridX,k.gridY,k.gridZ,k.blockX,k.blockY,k.blockZ,
               k.registersPerThread,k.staticSharedMemory,k.localMemoryPerThread,
               k.end-k.start AS ns
        FROM CUPTI_ACTIVITY_KIND_KERNEL k JOIN StringIds s ON s.id=k.demangledName
        WHERE s.value LIKE 'void mul_mat_vec_q<(ggml_type)12, (int)1, (bool)1%'
              AND k.gridX=9216 AND k.gridY=1 AND k.gridZ=1
    ''')
    groups = {}
    for r in rows:
        key = (r['name'],r['registersPerThread'],r['blockX'],r['blockY'],r['blockZ'])
        if key not in groups:
            groups[key] = {'name':r['name'], 'registers':r['registersPerThread'],
                           'grid':[r['gridX'],r['gridY'],r['gridZ']],
                           'block':[r['blockX'],r['blockY'],r['blockZ']],
                           'shared_bytes':r['staticSharedMemory'],
                           'local_bytes_per_thread':r['localMemoryPerThread'], 'samples':[]}
        groups[key]['samples'].append(r['ns'])
    out = []
    for row in groups.values():
        v = row.pop('samples')
        row.update(count=len(v), total_ns=sum(v),mean_ns=statistics.mean(v),median_ns=statistics.median(v),min_ns=min(v),max_ns=max(v))
        out.append(row)
    c.close()
    return out

result = {
    'original': summarize(root/'nsys_original/capture.sqlite'),
    'occ12_on': summarize(root/'nsys_occ12_on/capture.sqlite'),
    'interpretation': 'Instrumented diagnostic confirms dispatch/registers only. Different capture windows and node-trace overhead prevent promotion based on these times. Unprofiled OFF/ON/OFF failed performance gate.'
}
result['occ12_observed'] = any('(int)12>' in r['name'] for r in result['occ12_on'])
(lab/'evidence/occ12-profile-activation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
