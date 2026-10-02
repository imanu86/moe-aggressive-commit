"""Export cumulative conversation measurements and standalone SVG/PNG curves."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess


def aggregate(rows):
    fresh = sum(r['fresh_tokens'] for r in rows)
    generated = sum(r['engine_generated'] for r in rows)
    pms = sum(r['prefill_ms'] for r in rows)
    dms = sum(r['decode_ms'] for r in rows)
    return {'turns': len(rows), 'context_min': min(r['prompt_tokens'] for r in rows),
        'context_max': max(r['prompt_tokens'] for r in rows), 'fresh_tokens': fresh,
        'generated_tokens': generated, 'prefill_tps': fresh*1000/pms,
        'decode_tps': generated*1000/dms, 'ttft_mean_s': statistics.mean(r['ttft_s'] for r in rows),
        'wall_mean_s': statistics.mean(r['wall_s'] for r in rows),
        'drafts_accepted': sum(r.get('drafts_accepted') or 0 for r in rows),
        'drafts_offered': sum(r.get('drafts_offered') or 0 for r in rows)}


def enrich_native(rows, native, initial_slots):
    lookup = {r['prompt_tokens']: r for r in rows}
    current_slots, current = initial_slots, None
    for line in native.splitlines():
        m = re.search(r'strata elastic:.*?-> (\d+) slots', line)
        if m:
            current_slots = int(m[1])
        m = re.search(r'strata serve: prompt (\d+) tokens =', line)
        if m:
            current = lookup.get(int(m[1]))
            if current is not None:
                current['expert_slots_startup_reported'] = current['expert_slots']
                current['expert_slots'] = current_slots
        m = re.search(r'KV streaming: ([\d.]+)% of (\d+) block reads hit VRAM, ([\d.]+) MiB read from RAM', line)
        if m and current is not None:
            current.update(kv_vram_hit_pct=float(m[1]), kv_block_reads=int(m[2]), kv_ram_mib=float(m[3]))
    return rows


def plot(summary, rows, out, node, sharp):
    from reportlab.graphics.shapes import Drawing, String, Line, Circle
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics import renderSVG
    from reportlab.lib import colors
    drawing = Drawing(1200, 1020)
    dark, blue, gray = colors.HexColor('#173b66'), colors.HexColor('#84b4df'), colors.HexColor('#d8e2ec')
    drawing.add(String(48, 976, 'Strata SM75: one conversation from 20k to 250k', fontName='Helvetica-Bold', fontSize=23, fillColor=dark))
    drawing.add(String(48, 950, 'Modified RTX 2080 Ti 22 GB | KV 262144 / resident 32768 | elastic cache | MTP | IQ3_XXS', fontSize=13))
    drawing.add(String(48, 926, f"{len(rows)} generated replies; initial 20k, then approximately 1k user tokens; full history retained", fontSize=13))
    specs = [('decode_tps', 'Decode: engine generated tokens / native decode time', 654, 0),
             ('prefill_tps', 'Incremental prefill: new tokens only / native prompt time', 376, 0),
             ('ttft_s', 'Time to first visible token: HTTP + tokenization + prefill', 98, 0)]
    for key, title, y, minimum in specs:
        selected = rows[1:] if key == 'prefill_tps' else rows
        raw = [(r['prompt_tokens']/1000, r[key]) for r in selected]
        pooled = [(b['center_k'], b[key if key != 'ttft_s' else 'ttft_mean_s']) for b in summary['bins_10k']]
        high = max(v for _, v in raw)*1.15
        step = 10 if key == 'decode_tps' else (100 if key == 'prefill_tps' else max(1, math.ceil(high/6)))
        high = math.ceil(high/step)*step
        lp = LinePlot()
        lp.x, lp.y, lp.width, lp.height = 86, y, 1064, 190
        lp.data = [raw, pooled]
        lp.lines[0].strokeColor, lp.lines[0].strokeWidth = blue, 1
        lp.lines[1].strokeColor, lp.lines[1].strokeWidth = dark, 3
        lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 19, 251
        lp.xValueAxis.valueSteps = [20, 50, 100, 130, 160, 200, 250]
        lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = minimum, high
        lp.yValueAxis.valueSteps = list(range(minimum, int(high)+1, step))
        lp.xValueAxis.labels.fontSize = lp.yValueAxis.labels.fontSize = 11
        lp.yValueAxis.visibleGrid = 1
        lp.yValueAxis.gridStrokeColor = gray
        drawing.add(lp)
        drawing.add(String(86, y+220, title, fontName='Helvetica-Bold', fontSize=16, fillColor=dark))
        drawing.add(String(86, y-34, 'Actual prompt depth (thousands of tokens)', fontSize=11))
        x = 86+(135.164-19)/(251-19)*1064
        drawing.add(Line(x, y, x, y+190, strokeColor=colors.HexColor('#b4bac2'), strokeWidth=1, strokeDashArray=[3, 4]))
        if key == 'prefill_tps':
            drawing.add(String(86, y+199, f"Initial cold 20k prefill: {rows[0]['prefill_tps']:.2f} tokens/s (separate workload)", fontSize=11))
    drawing.add(Line(870, 914, 904, 914, strokeColor=blue, strokeWidth=1))
    drawing.add(String(912, 910, 'per turn', fontSize=11))
    drawing.add(Line(1015, 914, 1049, 914, strokeColor=dark, strokeWidth=3))
    drawing.add(String(1057, 910, '10k bins', fontSize=11))
    drawing.add(String(48, 28, '10k rates pool tokens/time. First turn excluded from pooled warm curve. Dashed: 135164 active-top-k limit.', fontSize=10))
    svg = out/'curve.svg'
    renderSVG.drawToFile(drawing, str(svg))
    if node and sharp:
        code = 'const sharp=require(process.argv[1]); sharp(process.argv[2],{density:144}).png().toFile(process.argv[3]).catch(e=>{console.error(e.message);process.exit(1);});'
        subprocess.run([str(node), '-e', code, str(sharp), str(svg), str(out/'curve.png')], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--node', type=Path)
    ap.add_argument('--sharp', type=Path)
    ap.add_argument('--allow-partial', action='store_true')
    a = ap.parse_args()
    result = json.loads((a.run/'result.json').read_text(encoding='utf-8'))
    if result['status'] != 'completed' and not a.allow_partial:
        raise RuntimeError('Run did not reach target; refuse a completed curve')
    transcript = [json.loads(s) for s in (a.run/'transcript.jsonl').read_text(encoding='utf-8').splitlines()]
    rows = [r['measurements'] for r in transcript]
    if not rows:
        raise RuntimeError('No completed requests')
    assert all(rows[i]['prompt_tokens'] < rows[i+1]['prompt_tokens'] for i in range(len(rows)-1))
    assert all(r['prompt_tokens']+r['output_tokens'] <= 262144 for r in rows)
    assert all(abs(r['user_tokens']-1000) <= 12 for r in rows[1:-1])
    assert all(r['reused_tokens'] > 0 for r in rows[1:])
    rows = enrich_native(rows, (a.run/'native.log').read_text(encoding='utf-8'), result['initial_engine']['expert_slots'])
    milestones = []
    for point in [20000, 50000, 80000, 100000, 130000, 160000, 200000, 230000, 250000]:
        selected = [r for r in rows[1:] if point-5000 <= r['prompt_tokens'] <= point+5000]
        if selected:
            milestones.append({'at_k': point//1000, **aggregate(selected)})
    bins = []
    for low in range(20000, 250000, 10000):
        selected = [r for r in rows[1:] if low <= r['prompt_tokens'] < low+10000]
        if selected:
            bins.append({'center_k': statistics.mean(r['prompt_tokens'] for r in selected)/1000, **aggregate(selected)})
    slots = [r['expert_slots'] for r in rows]
    temps = [r['gpu_temp_c'] for r in rows if r.get('gpu_temp_c') is not None]
    recalled = [{'turn': r['turn'], 'reply': r['assistant'],
                 'gpu_2080_mentioned': '2080' in r['assistant'],
                 'vram_22_mentioned': '22' in r['assistant'],
                 'kv_capacity_mentioned': re.search(r'262[., ]?144', r['assistant']) is not None,
                 'kv_resident_mentioned': re.search(r'32[., ]?768', r['assistant']) is not None}
                for r in transcript if (r['turn']-1)%20 == 0 and r['turn'] > 1]
    summary = {'status': result['status'], 'hardware': 'modified RTX 2080 Ti 22 GB, Ryzen 7 5800X, 96 GB RAM',
        'exe_sha256': result['exe_sha256'], 'server_sha256': result['server_sha256'],
        'source_bank_sha256': result['source_bank_sha256'], 'elapsed_s': result['elapsed_s'],
        'kv_capacity': 262144, 'kv_resident': 32768, 'elastic': True, 'sampling': result['sampling'],
        'history_truncated': False, 'turns': len(rows), 'context_min': rows[0]['prompt_tokens'],
        'context_max': rows[-1]['prompt_tokens'], 'generated_tokens': sum(r['output_tokens'] for r in rows),
        'finish_counts': {k: sum(r['finish']==k for r in rows) for k in sorted(set(r['finish'] for r in rows))},
        'initial_cold': rows[0], 'warm_all': aggregate(rows[1:]), 'milestones': milestones, 'bins_10k': bins,
        'expert_slots_min': min(slots), 'expert_slots_max': max(slots),
        'gpu_temp_min': min(temps) if temps else None, 'gpu_temp_max': max(temps) if temps else None,
        'last': rows[-1], 'recall_checks': recalled,
        'transcript_sha256': hashlib.sha256((a.run/'transcript.jsonl').read_bytes()).hexdigest(),
        'limitations': ['One retained conversation, different source text and generated replies at each depth.',
            'Incremental ~1k prefill differs from cold full-context prefill benchmarks.',
            'Decode rates depend on generated content, MTP acceptance, expert residency and normal desktop activity.',
            'Technical answer correctness not fully evaluated; recall mentions are limited checks.',
            'Native KV streaming counters are engine-reported; no physical DRAM GB/s measured.']}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (a.out/'curve.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    samples = [transcript[0], min(transcript, key=lambda r: abs(r['measurements']['prompt_tokens']-130000)), transcript[-1]]
    examples = [{'turn': r['turn'], 'context': r['measurements']['prompt_tokens'],
                 'question_tail': r['user'][-1200:], 'answer': r['assistant']} for r in samples]
    (a.out/'conversation-samples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    plot(summary, rows, a.out, a.node, a.sharp)
    lines = ['# Conversazione cumulativa 20k → 250k — 2 ottobre 2026', '',
        f"Daily f469, {len(rows)} turni, {summary['generated_tokens']} token generati; contesto reale {rows[0]['prompt_tokens']} → {rows[-1]['prompt_tokens']}.", '',
        'RTX2080Ti modificata a22GB, Ryzen7 5800X,96GB RAM. KV262144/int8/resident32768, cache auto/elastica, MTP, nessun carico artificiale.', '',
        'Dossier iniziale da20k con documentazione reale Strata, poi estratti nuovi da circa1000token per messaggio utente. Tutte le risposte effettive conservate nella cronologia, nessuna troncatura o riavvio intermedio.', '',
        f"Primo prefill freddo: **{rows[0]['prefill_tps']:.2f}t/s**, TTFT{rows[0]['ttft_s']:.2f}s. Le righe seguenti misurano il prefill incrementale e il decode.", '',
        '| Contesto circa | Turni nella finestra ±5k | Prefill incrementale t/s | Decode t/s | TTFT medio s |',
        '|---:|---:|---:|---:|---:|']
    for m in milestones:
        lines.append(f"|{m['at_k']}k|{m['turns']}|{m['prefill_tps']:.2f}|{m['decode_tps']:.2f}|{m['ttft_mean_s']:.2f}|")
    lines += ['', 'Velocita\' aggregate come somma token / somma tempi nativi; prima richiesta esclusa dalle finestre warm. TTFT misurato al primo contenuto visibile nel flusso HTTP.', '',
        f"Risposte terminate: {summary['finish_counts']}. Slot esperti effettivi: {min(slots)}–{max(slots)}, ricostruiti dal log nativo; la metrica engine riportava gli slot iniziali. Temperatura GPU: {summary['gpu_temp_min']}–{summary['gpu_temp_max']}°C.", '',
        '![Curva](curve.png)', '', 'CSV e summary JSON contengono ogni punto, MTP, riuso, cache, telemetria e limiti. Gli esempi sono risposte reali del modello; la correttezza tecnica generale non e\' stata valutata.', '',
        'Questa e\' una curva osservata durante una singola conversazione. Cambiano testo, accettazione MTP e cache. Il prefill da1k con riuso non e\' confrontabile direttamente col prefill freddo da131k/250k. Nessuna misura fisica GB/s DRAM.', '',
        'Tutti i processi di questa prova sono chiusi al termine della corsa. Nessuna modifica al daily o alla combinazione di kernel.']
    (a.out/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['status','turns','context_max','generated_tokens','finish_counts','milestones']}, indent=2))


if __name__ == '__main__':
    main()
