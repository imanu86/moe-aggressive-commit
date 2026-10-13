"""Markdown table of TTFT bench arms side by side: per request the TTFT (s), and from the engine's lines what was
reused and how (RAM, the system turn's file, a conversation file) and how many tokens were read.

    python ttft_tabella.py A B C
"""
import json, re, sys
from pathlib import Path

H = Path(__file__).resolve().parent
arms = sys.argv[1:]
res = {t: json.loads((H / f'ttft_{t}' / 'results.json').read_text(encoding='utf-8')) for t in arms}


def how(r):
    lines = r.get('engine') or []
    pl = next((l for l in lines if 'strata serve: prompt ' in l and ' tokens = ' in l), '')
    m = re.search(r'prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms', pl)
    src = []
    if any('conversation disk cache: hit' in l for l in lines):
        src.append('file conv.')
    elif any('prefix disk cache: restored' in l for l in lines):
        src.append('file prefisso')
    elif any('conversation cache: restored' in l for l in lines):
        src.append('RAM parcheggiata')
    if any('miss' in l and 'disk cache' in l for l in lines):
        src.append('miss disco')
    if m:
        n, reused, read, ms = map(int, m.groups())
        return n, reused, read, ms, '+'.join(src) or ('RAM viva' if reused else '-')
    return None, None, None, None, '+'.join(src)


names = [r['name'] for r in res[arms[0]]['requests']]
cases = {r['name']: r['case'] for r in res[arms[0]]['requests']}
print('| richiesta | caso | prompt | ' + ' | '.join(f'{t} TTFT s | {t} riuso / letti' for t in arms) + ' |')
print('|---|---|---|' + '---|---|' * len(arms))
for nm in names:
    row = [nm, cases[nm]]
    first = True
    for t in arms:
        r = next((x for x in res[t]['requests'] if x['name'] == nm), None)
        n, reused, read, ms, src = how(r) if r else (None,) * 5
        if first:
            row.append(f'{n:,}'.replace(',', '.') if n else '?')
            first = False
        row += [f'{r["ttft"]:.2f}'.replace('.', ',') if r and r.get('ttft') is not None else 'errore',
                f'{reused} ({src}) / {read}' if n else (src or '?')]
    print('| ' + ' | '.join(row) + ' |')
for t in arms:
    lv = res[t]['lives']
    print(f'\n{t}: avvio {lv["1"]["startup_s"] if "1" in lv else lv[1]["startup_s"]} s / '
          f'{lv["2"]["startup_s"] if "2" in lv else lv[2]["startup_s"]} s; exe {res[t]["exe_sha256"][:12]}; '
          f'env {res[t]["env"]!r}; server env {res[t].get("server_env")!r}; file {res[t].get("prefix_files")}')
    if res[t].get('same_text_as'):
        same = res[t]['same_text_as']
        print(f'  testo uguale: {sum(same.values())}/{len(same)}; diversi: {[k for k, v in same.items() if not v]}')
