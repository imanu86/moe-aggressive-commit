from pathlib import Path
import subprocess,shutil,json,hashlib
B=Path(__file__).resolve().parent;R=B/'daily038_alignment_20261003';S=R/'source'
assert (R/'build-base.json').exists()
shutil.copytree(S,R/'source-base')
shutil.copytree(R/'build',R/'base-deps',ignore=shutil.ignore_patterns('*.obj','*.exe','*.pdb','*.log','CMakeFiles','Testing','.ninja*'))
patch=R/'pr603.patch';data=patch.read_text(encoding='utf-8-sig');patch.write_text(data,encoding='utf-8',newline='\n')
for flag in ('--check',''):
    cmd=['git','apply','--whitespace=nowarn']+([flag] if flag else [])+[str(patch)]
    p=subprocess.run(cmd,cwd=S,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
(R/'pr603-provenance.json').write_text(json.dumps({'url':'https://github.com/Niko1221/Strata/pull/603','head':'6ba96984ac8a5f019edd84d7a83c278e6a1d363d','base':'99f3dbd0b21d1401b3769e0c0d963913607f380b','author':'Chanyeong Lim / asp345','coauthor':'Claude Opus 5.5','patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest()},indent=2))
print('Wide source prepared; base source and libraries preserved')
