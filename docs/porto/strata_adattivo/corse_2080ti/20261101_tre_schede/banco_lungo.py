"""Giro veloce a contesto lungo: una lettura da 128K (stesso prompt del banco della comunita') e poi turni brevi sulla stessa conversazione,
senza rileggere: ogni leva da' 7 misure di scrittura a contesto lungo in un minuto e mezzo. T=0, 256 token, come il banco.

    python banco_lungo.py --url http://127.0.0.1:8105 --out DIR --base RICHIESTA.json [--turni 6]
"""
import argparse, json, statistics, time, urllib.request
from pathlib import Path

ALTRO = 'Continue with the next section of the explanation. Write at least 600 words.'


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def turno(url, req):
    wire = urllib.request.Request(url + '/v1/chat/completions', data=json.dumps(req).encode(), headers={'Content-Type': 'application/json'})
    testo, primo, t0 = [], None, time.perf_counter()
    with urllib.request.urlopen(wire, timeout=1800) as r:
        for riga in r:
            if not riga.startswith(b'data: '):
                continue
            dato = riga[6:].strip()
            if dato == b'[DONE]':
                break
            for scelta in json.loads(dato).get('choices', []):
                d = scelta.get('delta', {})
                t = (d.get('content') or '') + (d.get('reasoning_content') or '')
                if t:
                    primo = primo if primo is not None else time.perf_counter() - t0
                    testo.append(t)
    e = get(url + '/metrics')['requests'][0]
    return ''.join(testo), primo, e


ap = argparse.ArgumentParser()
ap.add_argument('--url', default='http://127.0.0.1:8105')
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--base', type=Path, required=True)
ap.add_argument('--turni', type=int, default=6)
a = ap.parse_args()

base = json.loads(a.base.read_text(encoding='utf-8'))
righe = []
for i in range(a.turni + 1):
    testo, ttft, e = turno(a.url, base)
    nuovi = e['prompt_tokens'] - (e.get('reused') or 0)
    riga = {'turno': i, 'prompt_tokens': e['prompt_tokens'], 'riusati': e.get('reused') or 0, 'ttft_s': ttft, 'generati': e['engine_generated'],
            'lettura_tok_s': nuovi / (e['prompt_ms'] / 1000), 'scrittura_tok_s': e['engine_generated'] / (e['decode_ms'] / 1000)}
    print(json.dumps(riga), flush=True)
    righe.append(riga)
    (a.out / 'lungo.json').write_text(json.dumps(righe, indent=1) + '\n', encoding='utf-8')
    base['messages'] = base['messages'] + [{'role': 'assistant', 'content': testo}, {'role': 'user', 'content': ALTRO}]
s = [r['scrittura_tok_s'] for r in righe]
sommario = {'lettura_128k': righe[0]['lettura_tok_s'], 'scrittura_mediana': statistics.median(s), 'scrittura_min': min(s), 'scrittura_max': max(s),
            'ttft_turni': statistics.median(r['ttft_s'] for r in righe[1:])}
(a.out / 'sommario_lungo.json').write_text(json.dumps(sommario, indent=1) + '\n', encoding='utf-8')
print('sommario', json.dumps(sommario), flush=True)
