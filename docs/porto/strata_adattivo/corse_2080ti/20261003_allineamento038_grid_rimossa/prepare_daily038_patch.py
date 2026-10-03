from pathlib import Path
import difflib,subprocess,json,hashlib
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';S=R/'source';U=B/'checkpoint038_20261003/source';parts=[];changed=[]
for p in sorted(S.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(S).as_posix();old=(U/rel).read_bytes() if (U/rel).is_file() else b'';new=p.read_bytes()
    if old==new:continue
    a=old.decode('utf-8').replace('\r\n','\n');z=new.decode('utf-8').replace('\r\n','\n')
    if a==z:continue
    changed.append(rel);parts.extend(difflib.unified_diff(a.splitlines(True),z.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
p=R/'038-sm75-elastica-tail-wide.patch';p.write_text(''.join(parts),encoding='utf-8',newline='\n')
subprocess.run(['git','apply','--no-index','--check',str(p)],cwd=U,check=True)
(R/'patch-provenance.json').write_text(json.dumps({'upstream':'99f3dbd0b21d1401b3769e0c0d963913607f380b','changed_paths':changed,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'original_elastic_author':'Claude Opus; local final038 guarded port','tail':'Codex PR614','wide':'asp345, Claude Opus5.5 PR603','SM75':'jklnvlink/community original HC/GDN/vector and local budget/CPU quant ports'},indent=2));print('Portable patch passes apply check; changed files',len(changed))
