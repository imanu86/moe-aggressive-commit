from pathlib import Path
import hashlib,json,subprocess,urllib.request,zipfile
BASE=Path(__file__).resolve().parent
R=BASE/'checkpoint038_20261003'; R.mkdir(exist_ok=False)
SHA='99f3dbd0b21d1401b3769e0c0d963913607f380b'
archive=R/'upstream.zip'
with urllib.request.urlopen('https://codeload.github.com/Niko1221/Strata/zip/'+SHA,timeout=60) as response:
    archive.write_bytes(response.read())
source=R/'source'; source.mkdir()
z=zipfile.ZipFile(archive); prefix=z.namelist()[0].split('/')[0]+'/'
for name in z.namelist():
    if name.endswith('/') or not name.startswith(prefix): continue
    rel=Path(name[len(prefix):]); assert not rel.is_absolute() and '..' not in rel.parts
    if rel.as_posix().startswith('.github/workflows/'):continue
    target=source/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(name))
print((source/'AGENTS.md').read_text(),flush=True)
files=['include/strata/prefill/prefill.hpp','src/prefill/prefill.cpp','src/program/generate.cpp']
original=R/'original'; original.mkdir()
for rel in files:
    t=original/rel; t.parent.mkdir(parents=True,exist_ok=True); t.write_bytes((source/rel).read_bytes())
(R/'provenance.json').write_text(json.dumps({'upstream':SHA,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
    'plain_source_export':True,'original_files':{rel:hashlib.sha256((source/rel).read_bytes()).hexdigest() for rel in files}},indent=2))
print('SOURCE_READY',source,flush=True)
