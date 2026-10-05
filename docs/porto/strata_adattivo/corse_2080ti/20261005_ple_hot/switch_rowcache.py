"""Daily 0.1.39 r1: PLE row cache 16,777,216 rows (1.4 GB of RAM) instead of the default 1,048,576.

The rows read are the same bytes (output unchanged); a larger cache keeps the rows of the material the server has
already seen, so later prompts of the same project read fewer rows from the SSD (simulation: 50-55% left after
~2M tokens of the project, RESULTS.md "Righe PLE in RAM").  Cold 131k check first (LRC16-*).

Restore point first (config, BAT, sha256); rollback = copy the two files back.
"""
import hashlib, json, shutil, time
from pathlib import Path

D = Path(r'D:\ds4_work\strata\Strata')
CFG = D / 'strata-2080ti-sota.json'
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
ROWS = '16777216'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def dump(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + '\n').replace('\n', '\r\n').encode('utf-8')


raw = CFG.read_bytes()
cfg = json.loads(raw)
assert dump(cfg) == raw, 'config formatting would change: stop'
args = cfg['args']
assert '--ple-row-cache' not in args, 'already set'
i = args.index('--native-dense-gguf')
assert args[i + 2] == '--native-dense-gguf'

stamp = time.strftime('%Y%m%d_%H%M%S')
rp = Path(r'D:\ds4_work\strata\ripristini') / f'{stamp}_ple_rowcache'
rp.mkdir()
shutil.copy2(CFG, rp / CFG.name)
shutil.copy2(BAT, rp / BAT.name)
(rp / 'RIPRISTINO.txt').write_bytes((
    'Ripristino del cambio "cache di righe PLE 16M" (5/10/2026 sera)\r\n'
    f'config {CFG.name} sha256 {sha(CFG)}\r\n'
    f'BAT {BAT.name} sha256 {sha(BAT)}\r\n'
    f'Per tornare indietro: copiare i due file sopra i loro originali ({CFG} e {BAT}).\r\n').encode('utf-8'))

args[i + 4:i + 4] = ['--ple-row-cache', ROWS]   # right after the two --native-dense-gguf pairs
CFG.write_bytes(dump(cfg))

bat = BAT.read_bytes()
anchor = b'rem Cache esperti auto/elastica'
line = (f'rem Cache di righe PLE {ROWS} righe (1,4 GB di RAM, 5/10 sera): tiene le righe gia\' lette nella sessione; '
        f'ripristino in {rp}.\r\n').encode('ascii')
assert bat.count(anchor) == 1 and line not in bat
k = bat.index(anchor)
BAT.write_bytes(bat[:k] + line + bat[k:])

print(json.dumps({'restore_point': str(rp), 'config_sha256': sha(CFG), 'bat_sha256': sha(BAT),
                  'ple_row_cache': ROWS}, indent=2))
