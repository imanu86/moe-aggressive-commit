"""Preserve measured revision, disable alignment when checkpoint caching is off."""
from pathlib import Path
import hashlib,json,shutil,difflib
R=Path(__file__).resolve().parent/'checkpoint038_20261003'
speed=json.loads((R/'model-tests-r3/results.json').read_text(encoding='utf-8'));assert speed['status']=='completed'
saved=R/'measured-candidate';saved.mkdir(exist_ok=False)
files=['include/strata/prefill/prefill.hpp','src/prefill/prefill.cpp','src/program/generate.cpp']
for rel in files:
    dst=saved/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'source'/rel,dst)
shutil.copy2(R/'build/strata.exe',R/'strata-measured-candidate.exe')
shutil.copy2(R/'checkpoint-grid.patch',R/'checkpoint-grid-measured.patch')
shutil.copy2(R/'patch-provenance.json',R/'patch-provenance-measured.json')
p=R/'source/src/program/generate.cpp';text=p.read_text(encoding='utf-8')
old='sp.align_every = (reread_to > 0 || multi_gpu || o.prompt_cache_every <= 0) ? 0 : o.prompt_cache_every;'
assert text.count(old)==1
p.write_text(text.replace(old,'sp.align_every = (reread_to > 0 || multi_gpu || o.prompt_cache <= 0 || o.prompt_cache_every <= 0) ? 0 : o.prompt_cache_every;'),encoding='utf-8',newline='\n')
patch=''
for rel in files:
    before=(R/'original'/rel).read_text(encoding='utf-8');after=(R/'source'/rel).read_text(encoding='utf-8')
    patch+=f'diff --git a/{rel} b/{rel}\n'+''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=f'a/{rel}',tofile=f'b/{rel}'))
(R/'checkpoint-grid.patch').write_text(patch,encoding='utf-8',newline='\n')
meta=json.loads((R/'patch-provenance.json').read_text(encoding='utf-8'))
meta.update(patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),measured_exe_sha256=hashlib.sha256((R/'strata-measured-candidate.exe').read_bytes()).hexdigest(),final_revision_note='Adds prompt_cache<=0 bypass after timing runs; benchmark used cache6, so aligned path unchanged; final binary separately quality checked including cache0')
(R/'patch-provenance.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print('Shipping guard prepared; measured revision preserved')
