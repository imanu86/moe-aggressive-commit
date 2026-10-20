"""Verdetto B-A-B dei banchi «passata unica» (letture_concorrenti.py e letture_miste.py): legge lc_<tag>/res.json.

    python pu_verdict.py m-b1 m-a1 m-b2        (tag come in coda_lc_miste.sh / coda_lc.sh: b1 a1 b2, m- o lc_)

Stampa, allineati per (tipo di giro, numero di giro): tempo totale delle letture, TTFT, token nuovi letti e t/s di
lettura, t/s degli scrittori durante le letture, lettura lato motore, righe `strata pack:`.  Poi la dispersione fra i
due bracci B, il guadagno di A su B, il giudizio per criterio (un effetto piu` piccolo della dispersione fra i B e`
«inconclusivo»).  Infine identita` dei token: confronto byte a byte dei testi di parita` e dei testi delle letture fra
i bracci, e confronto dei conteggi (prompt / cached / out per richiesta).  Niente GPU: legge file.
"""
import json
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
tags = []
for t in sys.argv[1:]:
    tags.append(t[3:] if t.startswith('lc_') else t)
if len(tags) < 3:
    sys.exit('serve B A B: python pu_verdict.py m-b1 m-a1 m-b2')
arms = []
for t in tags:
    d = next((H / f'lc_{c}' for c in (t, f'm-{t}') if (H / f'lc_{c}' / 'res.json').exists()), None)
    if d is None:
        sys.exit(f'manca lc_{t}/res.json (o lc_m-{t}/res.json) in {H}')
    arms.append((t, json.loads((d / 'res.json').read_text(encoding='utf-8')), d))


def rounds(res):
    out = {}
    for r in res.get('rounds', []):
        out[(r.get('kind', 'mixed'), r.get('round'))] = r
    return out


# (chiave, etichetta, lettore, ruolo): 'su' = guadagno se A e` piu` basso, 'giu'' = se piu` alto,
# 'uguale' = deve essere uguale fra bracci (altrimenti la corsa non e` confrontabile), 'presenza' = il pacco deve
# esserci solo nei bracci A
METRICS = [
    ('readers_wall', 'tempo totale letture s', lambda r: r.get('readers_wall'), 'su'),
    ('ttft_max', 'TTFT max s', lambda r: r.get('ttft_max'), 'su'),
    ('new_tokens_read', 'token nuovi letti', lambda r: r.get('new_tokens_read'), 'uguale'),
    ('read_tps_wall', 't/s lettura (muro)', lambda r: r.get('read_tps_wall'), 'giu'),
    ('writers_tps_during_reads', 't/s scrittori DURANTE', lambda r: r.get('writers_tps_during_reads'), 'giu'),
    ('engine_read_tokens', 'motore: token letti', lambda r: (r.get('engine') or {}).get('read_tokens'), 'uguale'),
    ('engine_read_ms', 'motore: ms di lettura', lambda r: (r.get('engine') or {}).get('read_ms'), 'su'),
    ('engine_read_tps', 'motore: t/s lettura', lambda r: (r.get('engine') or {}).get('read_tps'), 'giu'),
    ('conc_rows_s', 'motore: rows/s in lettura', lambda r: max([x.get('rows_s') for x in (r.get('engine') or {}).get('conc_reads') or []] or [None]), 'giu'),
    ('pack_lines', 'righe strata pack:', lambda r: len(r.get('pack_lines') or []), 'presenza'),
    ('gather_lines', 'finestre server (righe)', lambda r: len(r.get('gather_lines') or []), 'presenza'),
    # solo da leggere in tabella: quanto erano davvero sovrapposte le letture (un giro seriale non e` una passata unica)
    ('send_span', 'invii span s', lambda r: r.get('send_span'), 'info'),
    ('finish_span', 'fine letture span s', lambda r: r.get('finish_span'), 'info'),
    ('overlap_min_s', 'sovrapposizione min s', lambda r: r.get('overlap_min_s'), 'info'),
]

keys = sorted({k for _, res, _ in arms for k in rounds(res)})
print('== bracci ==')
for t, res, d in arms:
    print(f'  {t:8s} env={res.get("env")} exe={Path(res.get("exe")).parent.name} context={res.get("contexts") or "n/d"}')

print('\n== giri allineati ==')
for key in keys:
    rows = [rounds(res).get(key) for _, res, _ in arms]
    if any(r is None for r in rows):
        print(f'giro {key}: manca in qualche braccio - saltato')
        continue
    print(f'giro {key[0]}{key[1]}  ({rows[0].get("readers")}, lettori) scrittori {rows[0].get("writers")}')
    for name, label, get, _role in METRICS:
        vals = [get(r) for r in rows]
        txt = ' '.join(f'{v if v is not None else "-":>10}' for v in vals)
        print(f'   {label:28s} {txt}')

b0, b1 = arms[0][0], arms[-1][0]
print(f'\n== verdetto (B = {b0} e {b1}, A = {", ".join(t for t, _, _ in arms[1:-1])}) ==')
for key in keys:
    rs = [rounds(res).get(key) for _, res, _ in arms]
    if any(r is None for r in rs):
        continue
    print(f'giro {key[0]}{key[1]}:')
    for name, label, get, role in METRICS:
        vb0, vb1 = get(rs[0]), get(rs[-1])
        if vb0 is None or vb1 is None:
            continue
        if role == 'info' or (name not in rs[0] and name not in rs[-1]):   # info, o metric non prodotto da questo script
            continue
        disp = abs(vb1 - vb0)
        for i in range(1, len(arms) - 1):
            va = get(rs[i])
            if va is None:
                continue
            if role == 'uguale':
                ok = len({vb0, vb1, va}) == 1
                verdict = 'confrontabile' if ok else 'CORSA NON CONFRONTABILE (valori diversi fra bracci)'
                print(f'   {label:28s} B {vb0:>9} / {vb1:>9} | A {va:>9} -> {verdict}')
                continue
            if role == 'presenza':
                if vb0 or vb1:
                    verdict = 'il pacco compare ANCHE in B: bracci sporchi'
                elif va:
                    verdict = f'attivo nel A ({va} righe)'
                else:
                    verdict = 'NON ATTIVO nel A: la leva non e` mai scattata'
                print(f'   {label:28s} B {vb0:>9} / {vb1:>9} | A {va:>9} -> {verdict}')
                continue
            d = (vb0 - va) if role == 'su' else (va - vb0)
            verdict = 'inconclusivo' if abs(d) <= disp else ('guadagno' if d > 0 else 'PERDITA')
            pct_txt = f' ({100.0 * d / max(1e-9, (vb0 + vb1) / 2.0):+.1f}%)' if vb0 or vb1 else ''
            print(f'   {label:28s} B {vb0:>9} / {vb1:>9} (disp {disp:6.2f}) | A {va:>9} -> {d:+8.2f}{pct_txt}  {verdict}')

print('\n== righe pack dei bracci A ==')
for t, res, _ in arms:
    lines = [ln for r in res.get('rounds', []) for ln in (r.get('pack_lines') or [])]
    print(f'  {t}: {len(lines)}')
    for ln in lines[:6]:
        print('    | ' + ln[:280])

print('\n== token identici ==')
par_keys = sorted({k for _, res, _ in arms for k in (res.get('parity') or {})})
for k in par_keys:
    txts = []
    for t, _, d in arms:
        f = d / f'{k}.txt'
        txts.append(f.read_bytes() if f.exists() else None)
    ref = txts[0]
    marks = []
    for (t, _, _), x in zip(arms, txts):
        if x is None:
            marks.append(f'{t}: MANCANTE')
        elif x == ref:
            marks.append(f'{t}: identici ({len(x)} B)')
        else:
            i = next((i for i, (p, q) in enumerate(zip(ref, x)) if p != q), min(len(ref), len(x)))
            marks.append(f'{t}: diverso al byte {i} (len {len(x)} vs {len(ref)})')
    print(f'  {k}: ' + ' | '.join(marks))

for key in keys:
    rks = sorted({k for _, res, _ in arms for k in (rounds(res).get(key, {}).get('res') or {})
                  if '_r_' in k or k.endswith('_r') or '_w_' in k})
    if not rks:
        continue
    print(f'  letture giro {key[0]}{key[1]}:')
    for k in rks:
        outs = []
        for t, res, d in arms:
            r = (rounds(res).get(key, {}).get('res') or {}).get(k) or {}
            f = d / f'{k}.txt'
            b = f.read_bytes() if f.exists() else b''
            outs.append((t, r.get('out'), r.get('prompt'), r.get('cached'), len(b)))
        same_txt = len({o[4] for o in outs}) == 1 and all(o[4] for o in outs)
        same_n = len({(o[1], o[2], o[3]) for o in outs}) == 1
        print(f'    {k:26s} ' + ' '.join(f'{o[0]}:out {o[1]}/p {o[2]}/c {o[3]}' for o in outs) +
              f'  {"conteggi identici" if same_n else "CONTEGGI DIVERSI"}{" testi identici" if same_txt else ""}')

print('\n== muro aggregato ==')
for t, res, _ in arms:
    print(f'  {t}: {json.dumps(res.get("mix_wall") or {k: res.get(k) for k in ()}, ensure_ascii=False)}')
    if res.get('load_other'):
        print(f'      carico altrui {res["load_other"]} | JumpConnect {res.get("jumpconnect_cpu_s")}')
