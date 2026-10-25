"""Genera le due config del 25/10 dalla copia del Daily 0.1.43 (il file del Daily non si tocca).
  A (0.2.6 pura, default per due schede): via --elastic e --prompt-cache-file (nostre), via tutte le STRATA_*; resta CUDA_VISIBLE_DEVICES.
  B (0.2.6 + pila): config del Daily, exe nuovi; via le env inerti (NODECUT, TOPK_GRID, B6_HEAD_MINB, QFUSE_HC: nessun effetto su CUDA),
     aggiunta STRATA_HC16_SM75=1 (il Daily 0.1.43 aveva hc16 di serie; sulla pila e' opt-in, patch 18)."""
import json, sys
from pathlib import Path
SRC = Path(r'D:\ds4_work\strata\Strata\strata-0143-daily.json')
HERE = Path(__file__).parent
ROOT = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep')
A_DIR, B_DIR = sys.argv[1], sys.argv[2]   # nomi delle cartelle build-up026-<sha>, build-up026pila-<sha>

def base(d):
    c = json.loads(SRC.read_text(encoding='utf-8-sig'))
    c['exe'] = str(ROOT / d / 'strata.exe')
    c['vision']['exe'] = str(ROOT / d / 'strata-vision.exe')
    return c

a = base(A_DIR)
args = a['args']
args.remove('--elastic')
i = args.index('--prompt-cache-file'); del args[i:i + 2]
a['env'] = {k: v for k, v in a['env'].items() if not k.startswith('STRATA_')}
(HERE / 'config-A-pura-default.json').write_text(json.dumps(a, indent=1), encoding='utf-8')

b = base(B_DIR)
for k in ('STRATA_NODECUT', 'STRATA_TOPK_GRID', 'STRATA_B6_HEAD_MINB', 'STRATA_QFUSE_HC'):
    b['env'].pop(k)
b['env']['STRATA_HC16_SM75'] = '1'
(HERE / 'config-B-pila-daily.json').write_text(json.dumps(b, indent=1), encoding='utf-8')
print('ok')
