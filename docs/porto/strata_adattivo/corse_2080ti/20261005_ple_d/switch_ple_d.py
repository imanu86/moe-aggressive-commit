"""Daily 0.1.39 r1: PLE table (shard 2) read from the verified copy on D: instead of C:\\Users\\imanu\\Downloads.

C: (Lexar EQ790, DRAM-less NVMe) stalls the 131k prefill 2-4x; the D: copy passed the A/B (20261004_routed_keep,
RESULTS.md "Tabella PLE su D:"). --ple-gguf alone fails ("duplicate split shard number": the engine lists every shard
beside --native), so the dense shards are given explicitly: shard 1 from Downloads, shard 2 from D:.

Restore point first (config, BAT, sha256); rollback = copy the two files back.
"""
import hashlib, json, shutil, time
from pathlib import Path

D = Path(r'D:\ds4_work\strata\Strata')
CFG = D / 'strata-2080ti-sota.json'
BAT = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
S1 = r'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'
S2_C = r'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf'
S2_D = r'D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf'
S2_SHA = '316B46F3A2DBD68C900F43136AB9449F9DCC3725DFD8C794847C204BC161E113'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest().upper()


def dump(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + '\n').replace('\n', '\r\n').encode('utf-8')


raw = CFG.read_bytes()
cfg = json.loads(raw)
assert dump(cfg) == raw, 'config formatting would change: stop'
args = cfg['args']
assert '--native-dense-gguf' not in args, 'already switched'
i = args.index('--ple-gguf')
assert args[i + 1] == S2_C and args[args.index('--native') + 1] == S1
assert Path(S2_D).stat().st_size == Path(S2_C).stat().st_size
assert sha(S2_D) == S2_SHA, 'D: copy differs'

stamp = time.strftime('%Y%m%d_%H%M%S')
rp = Path(r'D:\ds4_work\strata\ripristini') / f'{stamp}_ple_d'
rp.mkdir()
shutil.copy2(CFG, rp / CFG.name)
shutil.copy2(BAT, rp / BAT.name)
(rp / 'RIPRISTINO.txt').write_bytes((
    'Ripristino del cambio "tabella PLE su D:" (5/10/2026 sera)\r\n'
    f'config {CFG.name} sha256 {sha(CFG)}\r\n'
    f'BAT {BAT.name} sha256 {sha(BAT)}\r\n'
    f'Per tornare indietro: copiare i due file sopra i loro originali ({CFG} e {BAT}).\r\n').encode('utf-8'))

args[i + 1] = S2_D
args[i + 2:i + 2] = ['--native-dense-gguf', S1, '--native-dense-gguf', S2_D]
CFG.write_bytes(dump(cfg))

bat = BAT.read_bytes()
anchor = b'rem Cache esperti auto/elastica'
line = (f'rem Tabella PLE (shard 2) letta da {S2_D} (5/10 sera: su C: il prefill a 131k andava in stallo); '
        f'ripristino in {rp}.\r\n').encode('ascii')
assert bat.count(anchor) == 1 and line not in bat
k = bat.index(anchor)
BAT.write_bytes(bat[:k] + line + bat[k:])

print(json.dumps({'restore_point': str(rp), 'config_sha256': sha(CFG), 'bat_sha256': sha(BAT),
                  'ple_gguf': S2_D, 'native_dense_gguf': [S1, S2_D]}, indent=2))
