import json
from pathlib import Path

p = Path(r'D:\ds4_work\strata\Strata\strata-2080ti-sota.json')
cfg = json.loads(p.read_text(encoding='utf-8'))
i = cfg['args'].index('--mtp')
assert cfg['args'][i + 1] == r'D:\ds4_work\strata\Strata-data\mtp\rt', cfg['args'][i + 1]
raw = p.read_text(encoding='utf-8')
old = json.dumps(r'D:\ds4_work\strata\Strata-data\mtp\rt') + ','
new = json.dumps(r'D:\ds4_work\strata\Strata-data\mtp\rt_it48k') + ','
assert raw.count(old) == 1, raw.count(old)
p.write_bytes(raw.replace(old, new).encode('utf-8'))
cfg = json.loads(p.read_text(encoding='utf-8'))
print('mtp ->', cfg['args'][cfg['args'].index('--mtp') + 1])
