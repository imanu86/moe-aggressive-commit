"""Diagnostic comparison against two already-supported upstream chunk sizes."""
from pathlib import Path
import sys,json,math
sys.path[:0]=[r'D:\ds4_work\strata\Strata\.venv\Lib\site-packages',r'C:\Users\imanu\source\repos\Strata-2080Ti\tools\sm75']
import numpy as np,validate_model as V
R=Path(__file__).resolve().parent/'checkpoint038_20261003';Q=R/'quality-tests-r3'
tail=json.loads((R/'model-tests-r3/teacher_tail.ids.json').read_text())
def load(label):return np.fromfile(Q/label/'teacher.bin',dtype='<f4').reshape(64,-1)
def score(a,b):
    na,nb,kl,same=[],[],[],[]
    for pos in range(64):
        pa,pb=V.logsoftmax(a[pos]),V.logsoftmax(b[pos]);target=tail[pos]
        na.append(-float(pa[target]));nb.append(-float(pb[target]))
        kl.append(max(0.,float((np.exp(pa)*(pa-pb)).sum())));same.append(a[pos].argmax()==b[pos].argmax())
    return {'positions':64,'top1_agreement_pct':100*float(np.mean(same)),'kl_mean':float(np.mean(kl)),
            'kl_median':float(np.median(kl)),'kl_p99':float(np.percentile(kl,99)), 'kl_max':float(np.max(kl)),
            'ppl_reference':math.exp(float(np.mean(na))),'ppl_candidate':math.exp(float(np.mean(nb))),
            'nll_delta_mean':float(np.mean(np.asarray(nb)-na)),'nll_deltas':[b-a for a,b in zip(na,nb)],'kl_values':kl,'same_top1':[bool(x) for x in same]}
a,b,repeat=[load('chunk1536_'+label) for label in ('A1','B1','A2')]
c,r=score(a,b),score(a,repeat)
report={'original_1536_gate':V.regression_gate(c,r),'candidate_1536':V.public_stats(c),'repeat_1536':V.public_stats(r),
        'note':'Diagnostic supported-chunk control; does not overwrite or relax the original local gate'}
cross=Q/'chunk6144_A1/teacher.bin'
if cross.exists():report['upstream_only_1536_to_6144']=V.public_stats(score(a,load('chunk6144_A1')))
(R/'geometry-control.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
