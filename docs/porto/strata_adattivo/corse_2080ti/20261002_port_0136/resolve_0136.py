from pathlib import Path
import json
import re

R=Path(__file__).resolve().parent
report=json.loads((R/'merge-report0136.json').read_text())
for name in report['conflicts']:
    p=R/'candidate0136'/name
    text=p.read_text(encoding='utf-8')
    pattern=r'^<<<<<<< local-sm75\n(.*?)^\|\|\|\|\|\|\| base0135\n(.*?)^=======\n(.*?)^>>>>>>> upstream0136\n'
    def resolve(m):
        local, base, upstream=m.groups()
        if name=='include/strata/kernels/qsa_select.hpp':
            if not upstream.startswith(base):
                raise RuntimeError('Unexpected header conflict')
            return local+upstream[len(base):]
        if base:
            raise RuntimeError('Expected independent insertions: '+name)
        return local+upstream
    text, count=re.subn(pattern, resolve, text, flags=re.S|re.M)
    if count!=1 or re.search(r'^<<<<<<<|^>>>>>>>|^\|\|\|\|\|\|\|',text,re.M):
        raise RuntimeError('Unresolved conflict: '+name)
    p.write_text(text,encoding='utf-8',newline='\n')
report['resolved_conflicts']=report.pop('conflicts')
report['conflicts']=[]
(R/'merge-report0136.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Resolved three independent insertions; upstream cluster/profile-save retained')
