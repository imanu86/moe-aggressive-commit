"""Riassume le corse di st0_run.py: una riga per richiesta (lettura, decode, tempo per stadio per finestra, hit/miss, PLE) e il contesto della corsa.

    python st0_report.py RUN [RUN ...]   (nomi in D:\\ds4_work\\strata\\lab_st0\\runs; --json per l'uscita grezza)
Il tempo per stadio viene dalle righe 'strata serve: stage N' (cumulative dall'avvio: si fanno le differenze fra richieste) e da
'strata decode timing' (una per richiesta).  PLE bloccato = differenza del contatore 'blocked' nelle righe 'decode PLE before/after' + le attese
'the chunk at token N waited X ms for its PLE rows' della lettura.
"""
import json, re, statistics as st, sys
from pathlib import Path

RUNS = Path(r'D:\ds4_work\strata\lab_st0\runs')
R_PROMPT = re.compile(r'strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms \(([\d.]+) tok/s\), (\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of (\d+)')
R_DEC = re.compile(r'strata decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window = verify ([\d.]+) \(GPU-reach wait ([\d.]+) \+ per-layer host ([\d.]+) \[plan ([\d.]+) actq ([\d.]+) jobs ([\d.]+) CPU ([\d.]+)\] \+ stage ([\d.]+)\) \+ commit/emit ([\d.]+) \+ draft ([\d.]+); per layer-window: CPU experts ([\d.]+) \(([\d.]+) entries\), VRAM hits ([\d.]+), PCIe ([\d.]+)')
R_STAGE = re.compile(r'strata serve: stage (\d+): (\d+) windows; per window: wait for the GPU ([\d.]+) ms, pool \+ plan ([\d.]+) ms, host staging ([\d.]+) ms, commit ([\d.]+) ms')
R_HIT = re.compile(r'decode expert cache hit rate: ([\d.]+)% \((\d+) hits / (\d+) lookups\)(?:; (\d+) more read by the GPU)?')
R_BLOCK = re.compile(r'decode PLE (before|after): .*?blocked ([\d.]+) ms total')
R_WAIT = re.compile(r'the chunk at token (\d+) waited (\d+) ms for its PLE rows')
R_KV = re.compile(r'KV streaming: ([\d.]+)% of (\d+) block reads hit VRAM, ([\d.]+) MiB read from RAM')


def parse_run(name):
    d = RUNS / name
    res = json.loads((d / 'res.json').read_text())
    plan = json.loads((d / 'plan.json').read_text())
    out = dict(name=name, status=res['status'], extra_mib=res.get('extra_mib'), startup_s=res.get('startup_s'), requests=[])
    slots = [l for l in res.get('startup_lines', []) if re.search(r'expert cache \d+ slots', l)]
    out['slots'] = [int(m.group(1)) for l in slots for m in [re.search(r'expert cache (\d+) slots', l)] if m]
    out['slots1'] = [int(m.group(1)) for l in res.get('startup_lines', []) for m in [re.search(r'CUDA1 runs layers [\d-]+, expert cache (\d+) slots', l)] if m]
    prev = {0: (0, 0.0), 1: (0, 0.0)}
    for rq in res['requests']:
        t = (d / f"{rq['label']}.log").read_text(errors='replace')
        row = dict(label=rq['label'], prompt_tokens=rq['prompt_tokens'])
        m = R_PROMPT.search(t)
        if m:
            n, reused, read, rms, rtps, gen, dms, dtps, acc, off = m.groups()
            row.update(reused=int(reused), read=int(read), read_s=float(rms) / 1000, read_tps=float(rtps), gen=int(gen),
                       dec_s=float(dms) / 1000, dec_tps=float(dtps), acc=f'{acc}/{off}')
        m = R_DEC.search(t)
        if m:
            g = [float(x) for x in m.groups()]
            row.update(win=int(g[0]), tok_win=g[2], ms_win=g[3], verify=g[4], gpu_wait=g[5], host=g[6], cpu_ms=g[10], commit=g[12], draft=g[13],
                       cpu_experts=g[14], vram_hits=g[16])
        for m in R_STAGE.finditer(t):
            s, w, wait, pool, stg, com = int(m.group(1)), int(m.group(2)), *[float(m.group(i)) for i in (3, 4, 5, 6)]
            pw, pcum = prev[s]
            if w > pw:
                inc_w = (wait + pool + stg + com) * w
                row[f's{s}_ms'] = round((inc_w - pcum) / (w - pw), 2)
                row[f's{s}_wait'] = round((wait * w - prev.get(('w', s), 0.0)) / (w - pw), 2)
                row[f's{s}_pool'] = round((pool * w - prev.get(('p', s), 0.0)) / (w - pw), 2)
                prev[s] = (w, inc_w); prev[('w', s)] = wait * w; prev[('p', s)] = pool * w
        m = R_HIT.search(t)
        if m:
            row['hit'] = float(m.group(1)); row['pcie_experts'] = int(m.group(4) or 0)
        b = {k: float(v) for k, v in (m.groups() for m in R_BLOCK.finditer(t))}
        if 'before' in b and 'after' in b:
            row['ple_blocked_dec_ms'] = round(b['after'] - b['before'])
        w = [int(x[1]) for x in R_WAIT.findall(t)]
        if w:
            row['ple_wait_ms'] = max(w)
        m = R_KV.search(t)
        if m:
            row['kv_hit'] = float(m.group(1))
        out['requests'].append(row)
    amb = json.loads((d / 'ambiente.json').read_text()) if (d / 'ambiente.json').exists() else []
    for rq, row in zip(res['requests'], out['requests']):   # VRAM usata e potenza della 3060 durante la richiesta
        if 't0' in rq:
            sm = [list(map(float, r['gpu'][0].split(', ')[1:5])) for r in amb if r.get('gpu') and rq['t0'] <= r['t'] <= rq['t1']]
            if sm:
                row['vram0'] = round(st.median(x[0] for x in sm)); row['pw0'] = round(st.median(x[3] for x in sm))
    g0 = [list(map(float, r['gpu'][0].split(', ')[1:5])) for r in amb if r.get('gpu')]
    if g0:
        busy = [x for x in g0 if x[1] >= 90]
        out['amb'] = dict(vram0_mib=round(st.median(x[0] for x in g0)), clk0_busy_med=round(st.median(x[2] for x in busy)) if busy else None,
                          pw0_busy_med=round(st.median(x[3] for x in busy), 1) if busy else None,
                          cpu_altri_med=round(st.median(r.get('cpu_altri', 0) for r in amb if 'cpu_altri' in r), 2))
    # utilizzo GPU per processo sulla 3060 (luid con memoria dedicata piu' vicina alla memoria usata da nvidia-smi indice 0)
    eng = [e for r in amb for e in r.get('engines', [])]
    if eng:
        mem = {}
        for e in eng:
            f = e.split('|')
            if f[0] == 'M' and len(f) > 2:
                mem.setdefault(f[1], []).append(float(f[2].replace(',', '.')))
        luid0 = None
        if mem and out.get('amb'):
            luid0 = min(mem, key=lambda l: abs(st.median(mem[l]) - out['amb']['vram0_mib']) if st.median(mem[l]) > 0 else 1e9)
        agg = {}
        n_samples = sum(1 for r in amb if r.get('engines'))
        for e in eng:
            f = e.split('|')
            if f[0] == 'E' and len(f) > 4 and f[2] == luid0:
                k = f'{f[1]}/{f[3]}'
                agg[k] = agg.get(k, 0.0) + float(f[4].replace(',', '.'))
        # i valori sono somme su 2 campioni per giro: media = somma / (2 * giri)
        out['gpu0_users'] = {k: round(v / (2 * max(n_samples, 1)), 1) for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:6]}
    out['jump'] = (res.get('jump_start'), res.get('jump_end'))
    return out


def fmt(rows):
    hdr = ['arm', 'slot0', 'req', 'letti', 'lettura s (tok/s)', 'decode t/s', 'ms/fin', 'tok/fin', 'st0 ms', 'st0 attesa GPU', 'st0 pool', 'st1 ms', 'hit%', 'cpu exp/layer', 'ple blocco ms', 'VRAM 3060', 'W 3060']
    print('| ' + ' | '.join(hdr) + ' |'); print('|' + '---|' * len(hdr))
    for o in rows:
        for r in o['requests']:
            print('| ' + ' | '.join(str(x) for x in [
                o['name'].replace('DET-ST0-', ''), '/'.join(map(str, o['slots'])), r['label'], r.get('read', ''),
                f"{r['read_s']:.1f} ({r['read_tps']:.0f})" if 'read_s' in r and r.get('read', 0) > 200 else '',
                f"{r['dec_tps']:.1f}" if r.get('gen', 0) > 100 else '', r.get('ms_win', ''), r.get('tok_win', ''), r.get('s0_ms', ''), r.get('s0_wait', ''),
                r.get('s0_pool', ''), r.get('s1_ms', ''), r.get('hit', ''), r.get('cpu_experts', ''),
                r.get('ple_blocked_dec_ms', r.get('ple_wait_ms', '')), r.get('vram0', ''), r.get('pw0', '')]) + ' |')


if __name__ == '__main__':
    names = [a for a in sys.argv[1:] if not a.startswith('--')]
    rows = [parse_run(n if n.startswith('DET-') else 'DET-ST0-' + n) for n in names]
    if '--json' in sys.argv:
        print(json.dumps(rows, indent=1))
    else:
        fmt(rows)
        for o in rows:
            print(f"{o['name']}: stato {o['status']}, avvio {o['startup_s']} s, slot stadio 1 {o['slots1']}, ambiente {o.get('amb')}, GPU 3060 per processo (% medio) {o.get('gpu0_users')}, Jump {o['jump']}")
