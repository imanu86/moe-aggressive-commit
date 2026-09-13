"""Banco HTTP per il launcher Qwen38: primo token, decode, append di un secondo turno.

Misura quello che vede il harness (chat/completions in streaming), non chiamate native.
"""
import argparse, hashlib, json, pathlib, re, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument('--url', default='http://127.0.0.1:8100')
ap.add_argument('--ctx-tokens', type=int, default=0, help='token di contesto reale da anteporre')
ap.add_argument('--max-tokens', type=int, default=512)
ap.add_argument('--turns', type=int, default=2)
ap.add_argument('--label', default='run')
ap.add_argument('--temperature', type=float, default=None, help='se indicata viene inviata nella richiesta (0 = greedy)')
ap.add_argument('--out', default=str(pathlib.Path(__file__).with_name('banco_http.jsonl')))
args = ap.parse_args()

bat = pathlib.Path(r'C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat').read_text(errors='replace')
key = re.search(r'set "API_KEY=([^"]*)"', bat).group(1)
H = {'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + key}


def post(path, body, timeout=10800):
    req = urllib.request.Request(args.url + path, data=json.dumps(body).encode('utf-8'), headers=H)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


filler = ''
if args.ctx_tokens:
    src = pathlib.Path(r'C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source')
    parts, n = [], 0
    files = [p for p in src.rglob('*') if p.is_file() and p.suffix in ('.cpp', '.c', '.h', '.cu', '.cuh', '.py')
             and 'build' not in p.parts and p.stat().st_size < 400_000]
    for p in sorted(files):
        t = p.read_text(encoding='utf-8', errors='replace')
        parts.append(f'// ===== FILE {p.relative_to(src)} =====\n{t}')
        n += len(t)
        if n > args.ctx_tokens * 3.6:
            break
    filler = '\n'.join(parts)
    toks = post('/tokenize', {'content': filler})['tokens']
    if len(toks) > args.ctx_tokens:
        filler = post('/detokenize', {'tokens': toks[:args.ctx_tokens]})['content']
    print(f'contesto: {len(toks)} token disponibili, tagliati a {min(len(toks), args.ctx_tokens)}', flush=True)

questions = [
    "Spiega in italiano, in modo dettagliato e con esempi di codice C++, come funziona una cache LRU "
    "per gli esperti di un modello Mixture-of-Experts e quali sono i suoi limiti su una GPU da 12 GB.",
    "Ora riscrivi la stessa spiegazione come checklist operativa numerata di almeno venti punti, "
    "aggiungendo per ogni punto un paragrafo su come misurarne l'effetto sulla velocita' di generazione. "
    "Sii molto esteso.",
]
messages = []
if filler:
    messages.append({'role': 'user', 'content': 'Contesto di riferimento (codice sorgente):\n\n' + filler +
                     '\n\nLeggi il contesto e rispondi soltanto "pronto".'})
    messages.append({'role': 'assistant', 'content': 'pronto'})

results = []
for turn in range(args.turns):
    messages.append({'role': 'user', 'content': questions[turn % len(questions)]})
    body = {'messages': messages, 'max_tokens': args.max_tokens, 'stream': True,
            'stream_options': {'include_usage': True}, 'timings_per_token': False}
    if args.temperature is not None:
        body['temperature'] = args.temperature
    req = urllib.request.Request(args.url + '/v1/chat/completions', data=json.dumps(body).encode('utf-8'), headers=H)
    t0 = time.perf_counter(); t_first = None; n_chunks = 0; timings = None; content = []; reasoning = []
    with urllib.request.urlopen(req, timeout=10800) as r:
        for raw in r:
            line = raw.decode('utf-8', errors='replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            o = json.loads(data)
            if o.get('timings'):
                timings = o['timings']
            for ch in o.get('choices', []):
                d = ch.get('delta', {})
                piece = (d.get('content') or '') + (d.get('reasoning_content') or '')
                if piece:
                    if t_first is None:
                        t_first = time.perf_counter()
                    n_chunks += 1
                    content.append(d.get('content') or '')
                    reasoning.append(d.get('reasoning_content') or '')
    t_end = time.perf_counter()
    rec = {'label': args.label, 'turn': turn + 1, 'ctx_tokens_req': args.ctx_tokens,
           'wall_s': round(t_end - t0, 3), 'ttft_s': round((t_first or t_end) - t0, 3),
           'chunks': n_chunks, 'timings': timings}
    if timings:
        rec['prompt_n'] = timings.get('prompt_n'); rec['prompt_tps'] = round(timings.get('prompt_per_second', 0), 2)
        rec['gen_n'] = timings.get('predicted_n'); rec['gen_tps'] = round(timings.get('predicted_per_second', 0), 2)
        for k in ('draft_n', 'draft_n_accepted'):
            if k in timings:
                rec[k] = timings[k]
    # impronta del testo generato: serve a confrontare due assetti che DEVONO calcolare
    # la stessa cosa (per esempio sparse contro densa) e non solo a confrontarne i tempi.
    # il ragionamento arriva su reasoning_content: se si firma solo content, con
    # --reasoning on si finisce per firmare la stringa vuota.
    testo = ''.join(reasoning) + ''.join(content)
    rec['text_sha'] = hashlib.sha256(testo.encode('utf-8')).hexdigest()[:12]
    rec['text_len'] = len(testo)
    pathlib.Path(args.out).with_name(f'testo_{args.label}_t{turn + 1}.txt').write_text(testo, encoding='utf-8')
    print(json.dumps({k: v for k, v in rec.items() if k != 'timings'}), flush=True)
    results.append(rec)
    messages.append({'role': 'assistant', 'content': ''.join(content), 'reasoning_content': ''.join(reasoning)})

with open(args.out, 'a', encoding='utf-8') as f:
    for rec in results:
        f.write(json.dumps(rec) + '\n')
