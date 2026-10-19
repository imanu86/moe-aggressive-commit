"""Aggrega le corse DET-ST0-* per regime della 3060 e per slot dello stadio 0.

    python st0_agg.py [prefisso...]     (default: tutte le DET-ST0-S*)
Regime di una richiesta di decode a 131K: 'veloce' se l'attesa della GPU dello stadio 0 e' < 14 ms per finestra (la 3060 lavora da sola),
'lento' altrimenti (la 3060 e' contesa o pagina).  Prefill e letture corte si leggono per slot e per dimensione del chunk.
"""
import json, re, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st0_report as R


def med(v):
    v = [x for x in v if x is not None]
    return round(st.median(v), 2) if v else None


def mean(v):
    v = [x for x in v if x is not None]
    return round(st.mean(v), 2) if v else None


def main():
    pref = sys.argv[1:] or ['DET-ST0-S']
    names = sorted(p.name for p in R.RUNS.iterdir() if any(p.name.startswith(x) for x in pref) and (p / 'res.json').exists())
    runs = []
    for n in names:
        try:
            o = R.parse_run(n)
        except Exception as e:   # noqa
            print('salto', n, repr(e)[:100]); continue
        if o['status'] != 'completed' or 'routing' in n.lower():
            continue
        free = None
        runs.append(o)
    print(f'{len(runs)} corse')
    # decode: una riga per richiesta L0x (>100 token generati)
    rows = []
    for o in runs:
        slots = o['slots'][0] if o['slots'] else None
        for r in o['requests']:
            if r.get('gen', 0) > 500 and 's0_wait' in r:
                rows.append(dict(run=o['name'].replace('DET-ST0-', ''), slots=slots, label=r['label'], tps=r['dec_tps'], ms_win=r['ms_win'], s0=r['s0_ms'],
                                 s0w=r['s0_wait'], s0p=r['s0_pool'], s1=r['s1_ms'], hit=r.get('hit'), tokwin=r['tok_win'], vram=r.get('vram0'),
                                 fast=r['s0_wait'] < 14, draft=r.get('draft'), commit=r.get('commit'), cpu_exp=r.get('cpu_experts')))
    bins = [(0, 800, '<800'), (800, 1300, '~1100'), (1300, 1700, '~1560'), (1700, 2100, '~1800'), (2100, 3000, '~2440 (base auto)'), (3000, 99999, '~3100-3260 (esplicito)')]
    print('\n## decode a 131K per slot e regime (L01..L04 per corsa; tok/fin diverso per richiesta: confrontare ms/finestra e ms per token)')
    print('| slot stadio 0 | regime | n | t/s | ms/finestra | st0 tot | st0 attesa GPU | st0 pool+piano | st1 tot | hit % | CPU esp./layer-fin | tok/fin | ms/token |')
    print('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for lo, hi, lab in bins:
        for fast in (True, False):
            g = [r for r in rows if r['slots'] and lo <= r['slots'] < hi and r['fast'] == fast]
            if not g:
                continue
            print(f"| {lab} | {'veloce' if fast else 'lento'} | {len(g)} | {mean([r['tps'] for r in g])} | {mean([r['ms_win'] for r in g])} | {mean([r['s0'] for r in g])} | "
                  f"{mean([r['s0w'] for r in g])} | {mean([r['s0p'] for r in g])} | {mean([r['s1'] for r in g])} | {mean([r['hit'] for r in g])} | {mean([r['cpu_exp'] for r in g])} | "
                  f"{mean([r['tokwin'] for r in g])} | {mean([r['ms_win'] / r['tokwin'] for r in g])} |")
    print('\n## frequenza del regime lento (decode a 131K)')
    for lo, hi, lab in bins:
        g = [r for r in rows if r['slots'] and lo <= r['slots'] < hi]
        if g:
            print(f"- {lab}: {sum(1 for r in g if not r['fast'])} lente su {len(g)}")
    # prefill
    print('\n## prefill: lettura a 131K (L01, a freddo) e letture corte da ~5K, per slot')
    print('| corsa | slot | chunk | VRAM libera dopo il carico | L01 lettura s (tok/s) | corte 5K: s (mediana) | regime decode L01 |')
    print('|---|---:|---:|---|---|---|---|')
    for o in runs:
        l01 = next((r for r in o['requests'] if r['label'] == 'L01' and 'read_s' in r), None)
        sh = [r['read_s'] for r in o['requests'] if r['label'].startswith('short') and 'read_s' in r]
        d = next((r for r in rows if r['run'] == o['name'].replace('DET-ST0-', '') and r['label'] == 'L01'), None)
        chunk = ''
        try:
            lg = (R.RUNS / o['name'] / 'engine.log').read_text(errors='replace')
            m = re.search(r'prompt chunk auto: (\d+) tokens', lg); chunk = m.group(1) if m else ''
            m = re.search(r'strata serve: (\d+) MiB of VRAM free with everything loaded', lg); free = m.group(1) if m else ''
        except OSError:
            free = ''
        if l01:
            print(f"| {o['name'].replace('DET-ST0-', '')} | {o['slots'][0] if o['slots'] else ''} | {chunk} | {free} MiB | {l01['read_s']:.0f} ({l01['read_tps']:.0f}) | "
                  f"{med(sh)} | {'veloce' if d and d['fast'] else 'lento'} |")
    print('\n## per corsa: decode medio dei L02-L04 (t/s) e dispersione')
    for o in runs:
        d = [r for r in rows if r['run'] == o['name'].replace('DET-ST0-', '')]
        if d:
            print(f"- {o['name'].replace('DET-ST0-', '')}: slot {o['slots'][0] if o['slots'] else ''}, VRAM 3060 {d[0]['vram']} MiB, t/s " + ', '.join(f"{r['label']} {r['tps']:.1f}{'' if r['fast'] else '*'}" for r in d))


if __name__ == '__main__':
    main()
