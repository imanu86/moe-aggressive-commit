"""Aggiunge UNA patch al registro stack/ di un worktree, riusando check_anchors.py (format-patch, ancore, INDEX/BLOCKS).
    python stack_add.py <worktree> <sha> <entry.json>
Non rigenera le altre patch (la pila su lab/multichat45b non e' ricostruibile da un range: i commit del pacco non sono voci)."""
import importlib.util, json, re, sys
from pathlib import Path

wt = Path(sys.argv[1]).resolve()
sha = sys.argv[2]
entry = json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('check_anchors', wt / 'stack' / 'check_anchors.py')
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)
m = ca.load_manifest()
if any(e['id'] == entry['id'] for e in m['patches']):
    m['patches'] = [e for e in m['patches'] if e['id'] != entry['id']]
full = ca.git(['rev-parse', sha], str(wt)).stdout.strip()
fname = f"{entry['id']}-{entry['name']}.patch"
entry['patch'] = fname
entry['commit'] = full
entry['title'] = ca.git(['log', '-1', '--format=%s', full], str(wt)).stdout.strip()
text = ca.git(['format-patch', '-1', '--stdout', '--no-stat', '--no-signature', '--zero-commit', full], str(wt)).stdout
text = re.sub(r'^From: .*$', 'From: Strata-2080Ti stack <stack@noreply.github.com>', text, count=1, flags=re.M)
(ca.HERE / fname).write_text(text, encoding='utf-8', newline='\n')
files, _ = ca.parse_patch(text)
anchors, n = [], 0
for f in files:
    if f['new'] or f['deleted']:
        n += 1
        anchors.append({'block': f"{entry['id']}-{n}", 'file': f['path'], 'symbol': '(new file)' if f['new'] else '(deleted file)',
                        'anchor': [], 'status_in_base': 'new-file' if f['new'] else 'deleted-file', 'hunk': 0})
        continue
    pre = ca.git(['show', f"{full}^:{f['path']}"], str(wt)).stdout.split('\n')
    for hi, h in enumerate(f['hunks'], 1):
        n += 1
        lines, st = ca.anchor_for(h, pre)
        anchors.append({'block': f"{entry['id']}-{n}", 'file': f['path'], 'symbol': h.symbol or '(file scope)',
                        'anchor': lines, 'status_in_base': st, 'hunk': hi})
entry['anchors'] = anchors
entry['files'] = [f['path'] for f in files]
m['patches'].append(entry)
m['stack_head'] = full
if 'intro_extra' in entry:
    extra = entry.pop('intro_extra')
    if extra not in m['intro']:
        m['intro'] = m['intro'].rstrip() + '\n\n' + extra
ca.save_manifest(m)
ca.INDEX.write_text(ca.render_index(m), encoding='utf-8', newline='\n')
ca.BLOCKS.write_text(ca.render_blocks(m), encoding='utf-8', newline='\n')
print(fname, len(anchors), 'insertion points;', sum(1 for a in anchors if a['status_in_base'] != 'unique'), 'not unique')
