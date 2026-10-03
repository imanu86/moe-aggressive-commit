"""Plain separate copy for the new cache-lending accounting fix; no Git or Daily writes."""
from pathlib import Path
import hashlib,json,shutil,subprocess
root=Path(__file__).resolve().parent/'fourhour_20261002'
src=root/'memory547-source'
if not src.exists(): shutil.copytree(root/'dynamic2-source',src,ignore=shutil.ignore_patterns('strata-main-alignment','__pycache__'))
for name in ('include/strata/prefill/prefill.hpp','src/prefill/prefill.cpp','src/program/generate.cpp'):
    if (src/name).read_bytes()!=(root/'dynamic2-source'/name).read_bytes(): raise RuntimeError('Existing source modified '+name)
diff=sorted((root/'github').glob('*_pr547.diff'))[-1]
subprocess.run(['git','apply','--no-index','--exclude=src/prefill/prefill.cpp','--check',str(diff)],cwd=src,check=True)
subprocess.run(['git','apply','--no-index','--exclude=src/prefill/prefill.cpp',str(diff)],cwd=src,check=True)
p=src/'src/prefill/prefill.cpp'; text=p.read_text(encoding='utf-8')
changes={
 'int64_t chunk) {\n    // the same allocation sequence as `init`, counted':'int64_t chunk, bool src) {\n    // Match carve: xn only for unfused GR, grs always, and source-dependent MoE layout.',
 'f(T * N); f(T * D); f(T * D); o.take<uint16_t>(T * D, ok); f(T * LR); o.take<uint16_t>(T * LR, ok);':'f(T * N); f(T * D);\n    if (gr_unfused()) f(T * D);\n    f(T * HC);\n    o.take<uint16_t>(T * D, ok); f(T * LR); o.take<uint16_t>(T * LR, ok);',
 'moe_set_bytes(T, g.n_expert, fused_layout(T, true))':'moe_set_bytes(T, g.n_expert, fused_layout(T, src))',
}
for old,new in changes.items():
    if text.count(old)!=1: raise RuntimeError('Unexpected prefill port '+old)
    text=text.replace(old,new)
p.write_text(text,encoding='utf-8',newline='\n')
changed=['include/strata/prefill/prefill.hpp','src/prefill/prefill.cpp','src/program/generate.cpp']
(root/'memory547-preparation.json').write_text(json.dumps({'upstream':'db4f91a1171d697928b0d2e1f50ef95e25559d4c','pr547':'4072b708e94d06cadee61a47df1930f22d313d86','base':'dynamic2, experimental dynamic default OFF','port':'Header/generate exact diff; prefill three exact replacements preserving all existing tc_sm75 allocations. Initial whole patch check failed at overlap, no partial writes.','diff_sha256':hashlib.sha256(diff.read_bytes()).hexdigest(),'files':{name:hashlib.sha256((src/name).read_bytes()).hexdigest() for name in changed},'daily_changed':False},indent=2),encoding='utf-8')
print('Prepared PR547 memory accounting, no mode or arithmetic changes')
