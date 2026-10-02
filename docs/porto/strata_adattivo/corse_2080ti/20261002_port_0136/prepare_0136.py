from pathlib import Path
import io
import json
import shutil
import subprocess
import zipfile

R = Path(__file__).resolve().parent
REPO = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
BASE = R/'upstream0135'
LOCAL = R/'candidate0135'
UP = R/'upstream0136'
DEST = R/'candidate0136'
SHA = '36fa455e579b23a9c909c2c6fe1bddd9e51cb8ca'
if UP.exists() or DEST.exists():
    raise RuntimeError('Existing 0.1.36 export: inspect before repeating')
data = subprocess.run(['git', 'archive', '--format=zip', SHA], cwd=REPO, capture_output=True, check=True).stdout
with zipfile.ZipFile(io.BytesIO(data)) as z:
    for item in z.infolist():
        target = (UP/item.filename).resolve()
        if not target.is_relative_to(UP.resolve()):
            raise RuntimeError('Archive path escapes export')
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
shutil.copytree(UP, DEST)
conflicts = []
ports = []
TEMP = R/'merge0136'
TEMP.mkdir(exist_ok=True)
for p in sorted(LOCAL.rglob('*')):
    if not p.is_file():
        continue
    name = p.relative_to(LOCAL).as_posix()
    old = (BASE/name).read_bytes() if (BASE/name).exists() else b''
    new = p.read_bytes()
    if old.replace(b'\r\n', b'\n') == new.replace(b'\r\n', b'\n'):
        continue
    target = DEST/name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not (BASE/name).exists():
        if target.exists():
            raise RuntimeError('New local path also exists upstream: '+name)
        target.write_bytes(new)
    else:
        inputs = [new, old, (UP/name).read_bytes() if (UP/name).exists() else b'']
        files = []
        for idx, raw in enumerate(inputs):
            temp = TEMP/(str(idx)+'.txt')
            temp.write_bytes(raw.replace(b'\r\n', b'\n'))
            files.append(str(temp))
        result = subprocess.run(['git', 'merge-file', '-p', '--diff3', '-L', 'local-sm75', '-L', 'base0135', '-L', 'upstream0136', *files], capture_output=True)
        if result.returncode < 0 or result.returncode > 127:
            raise RuntimeError('merge-file failed: '+name)
        target.write_bytes(result.stdout)
        if result.returncode:
            conflicts.append(name)
    ports.append(name)
(R/'merge-report0136.json').write_text(json.dumps({'upstream':SHA, 'ported_paths':ports, 'conflicts':conflicts}, indent=2), encoding='utf-8')
print(json.dumps({'ported_paths':len(ports), 'conflicts':conflicts}, indent=2))
