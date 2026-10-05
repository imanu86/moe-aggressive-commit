"""Lab manifest for the fork after a source change, so tools/sm75/check_source.py keeps passing.

Run from the fork root (C:\\Users\\imanu\\source\\repos\\Strata-2080Ti-core) AFTER committing the source change:

    python make_lab_manifest.py <previous>.json <new>.json <version-label> "<meaning>" file1 [file2 ...]

It copies the previous manifest, records the previous one's sha256 (and keeps the older historical ones), adds both
manifest names to publication_overrides, re-hashes the listed files (new files are added), and puts <new>.json first
in check_source.py's list.  Then: python tools/sm75/check_source.py -> SOURCE_OK; commit both files
(OPUS-DEPLOY-Registra il manifest di laboratorio ...) and push.  Writes bytes (LF), never text mode: on Windows
Path.write_text turns LF into CRLF.
"""
import hashlib
import json
import sys
from pathlib import Path

R = Path('.')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if len(sys.argv) < 6:
        raise SystemExit(__doc__)
    prev_name, new_name, version, meaning, files = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
    prev_path = R / 'docs/sm75' / prev_name
    prev = json.loads(prev_path.read_text(encoding='utf-8'))
    m = dict(prev)
    m['snapshot_version'] = version
    hist = dict(prev.get('historical_manifests', {}))
    if 'previous_manifest' in prev and prev['previous_manifest'] != 'source-manifest.json':
        hist[prev['previous_manifest']] = sha(R / 'docs/sm75' / prev['previous_manifest'])
    m['historical_manifests'] = hist
    m['previous_manifest'] = prev_name
    m['previous_manifest_sha256'] = sha(prev_path)
    ov = set(prev['publication_overrides'])
    ov.update({'docs/sm75/' + prev_name, 'docs/sm75/' + new_name})
    m['publication_overrides'] = sorted(ov)
    m['meaning'] = meaning
    table = dict(prev['files'])
    for f in files:
        table[f] = sha(R / f)
    m['files'] = dict(sorted(table.items()))
    (R / 'docs/sm75' / new_name).write_bytes((json.dumps(m, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    cs = R / 'tools/sm75/check_source.py'
    s = cs.read_bytes().decode('utf-8')
    old = f"'{prev_name}', "
    if s.count(old) < 1:
        raise SystemExit(f'{prev_name} not found in check_source.py')
    s = s.replace(old, f"'{new_name}', {old}", 1)
    cs.write_bytes(s.encode('utf-8'))
    print('ok:', new_name)


if __name__ == '__main__':
    main()
