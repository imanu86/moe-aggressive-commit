"""Read-only HTTP benchmark. Tools are simulated and never executed.

Run only while the coordinator owns the GPU. Server lifecycle is external.
Output includes request/output hashes, raw timings, latency and tool validation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def request(url, path, key, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url.rstrip('/') + path, data=data,
        headers={'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + key})
    return urllib.request.urlopen(req, timeout=1200)


def sse_events(response):
    parts = []
    for raw in response:
        line = raw.decode('utf-8').rstrip('\r\n')
        if line == '':
            if parts:
                yield '\n'.join(parts)
                parts = []
            continue
        if line.startswith(':'):
            continue
        field, separator, value = line.partition(':')
        if field == 'data':
            parts.append(value[1:] if value.startswith(' ') else value)
    # An unterminated event at EOF is not a completed SSE event.


def stream(url, key, payload):
    start = time.perf_counter()
    text, reasoning, tools, timings, usage = '', '', {}, {}, {}
    probabilities = []
    first_delta = first_text = first_tool = None
    finish = None
    done = False
    with request(url, '/v1/chat/completions', key, payload) as response:
        for event in sse_events(response):
            if event.strip() == '[DONE]':
                done = True
                break
            item = json.loads(event)
            if item.get('error'):
                raise RuntimeError('Server stream error: ' + str(item['error']))
            elapsed = time.perf_counter() - start
            timings = item.get('timings', timings)
            usage = item.get('usage', usage)
            for choice in item.get('choices', []):
                if choice.get('logprobs'):
                    probabilities.append(choice['logprobs'])
                delta = choice.get('delta', {})
                if delta.get('content') or delta.get('reasoning_content') or delta.get('tool_calls'):
                    if first_delta is None:
                        first_delta = elapsed
                if delta.get('content'):
                    if first_text is None:
                        first_text = elapsed
                    text += delta['content']
                reasoning += delta.get('reasoning_content') or ''
                for call in delta.get('tool_calls', []):
                    if first_tool is None:
                        first_tool = elapsed
                    target = tools.setdefault(call.get('index', 0), {'name': '', 'arguments': ''})
                    fn = call.get('function', {})
                    target['name'] += fn.get('name') or ''
                    target['arguments'] += fn.get('arguments') or ''
                finish = choice.get('finish_reason') or finish
    return {'seconds': time.perf_counter() - start, 'first_delta_s': first_delta,
            'first_text_s': first_text, 'first_tool_s': first_tool, 'done': done,
            'finish': finish, 'text': text, 'reasoning': reasoning,
            'tools': list(tools.values()), 'timings': timings, 'usage': usage, 'logprobs': probabilities}


TOOL = {'type': 'function', 'function': {'name': 'cgc_cockpit',
    'description': 'Unico ingresso CGControl. Questa prova non esegue azioni reali.',
    'parameters': {'type': 'object', 'properties': {
        'mode': {'type': 'string', 'enum': ['operation']},
        'operation': {'type': 'string'},
        'arguments': {'type': 'object', 'properties': {
            'name': {'type': 'string'},
            'numbers': {'type': 'array', 'items': {'type': 'integer'}},
            'find': {'type': 'string'}}}}, 'required': ['mode', 'operation', 'arguments']}}}

CASES = [
    ('tool_describe', 'Devi usare cgc_cockpit. Prima di una operazione non nota chiama '
     '{"mode":"operation","operation":"describe_operation","arguments":{"name":"screen_text"}}. '
     'Non effettuare azioni diverse. Non inventare risultati.',
     'Leggi il saldo sui telefoni 1, 2 e 3 senza cliccare nulla.',
     {'mode': 'operation', 'operation': 'describe_operation', 'arguments': {'name': 'screen_text'}}),
    ('tool_batch', 'Usa questo schema gia scoperto e copia la struttura: '
     '{"mode":"operation","operation":"screen_text","arguments":{"numbers":[1],"find":"Saldo"}}. '
     'numbers contiene tutti i telefoni richiesti, in una sola chiamata.',
     'Leggi il saldo sui telefoni 1, 2 e 3.',
     {'mode': 'operation', 'operation': 'screen_text', 'arguments': {'numbers': [1, 2, 3], 'find': 'Saldo'}}),
    ('tool_retry', 'Test simulato: non viene eseguita alcuna azione reale. '
     'Schema login gia scoperto: {"mode":"operation","operation":"login","arguments":{"numbers":[1,2,3]}}. '
     'Risultato precedente: 1 e 3 autenticati, 2 non verificato. Usa lo strumento senza inventare esiti.',
     'Ripeti questa chiamata solo per il telefono 2, non per 1 o 3.',
     {'mode': 'operation', 'operation': 'login', 'arguments': {'numbers': [2]}}),
    ('result', 'Rispondi brevemente in italiano, soltanto sulla base dei dati forniti. '
     'Non affermare di aver eseguito nuove azioni.',
     'Risultati SIMULATI: telefono1 autenticato saldo12.50EUR; telefono2 non verificato, '
     'pagina Accedi, balance-not-found; telefono3 autenticato saldo7EUR. Riassumi senza inventare cause.', None),
    ('prose', 'Rispondi in italiano.',
     'Spiega in 200 parole come confrontare due motori di inferenza: latenza, throughput, '
     'cache, correttezza e misure ripetute. Non usare strumenti.', None),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8114')
    p.add_argument('--model', default='qwen4b-bench')
    p.add_argument('--label', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--thinking', action='store_true')
    p.add_argument('--logprobs', action='store_true', help='Separate correctness probe, not a speed run')
    p.add_argument('--multi-turn', action='store_true', help='tool_batch only: cold turn then cached simulated tool-result followups')
    p.add_argument('--temperature', type=float, default=0.0,
                   help='0 is a differential test only, not the recommended daily sampler')
    p.add_argument('--case', choices=[c[0] for c in CASES])
    p.add_argument('--max-tokens', type=int, default=512)
    p.add_argument('--long-tokens', type=int, default=0,
                   help='Synthetic reference prefix token count; not a general long-context quality test')
    args = p.parse_args()
    if not 1 <= args.max_tokens <= 4096 or not 1 <= args.repeats <= 20:
        raise ValueError('Output/repetition budget outside approved range')
    if args.multi_turn and (args.case != 'tool_batch' or args.repeats < 2):
        raise ValueError('Multi-turn requires tool_batch and at least two turns')
    key = os.environ.get('QWEN_BENCH_API_KEY', '')
    args.out.mkdir(parents=True, exist_ok=False)
    with request(args.url, '/v1/models', key) as r:
        models = json.load(r)
    with request(args.url, '/props', key) as r:
        props = json.load(r)
    prefix = ''
    if args.long_tokens:
        if not 0 < args.long_tokens <= 120000:
            raise ValueError('Long prefix must fit the 128k slot with output headroom')
        material = '\n'.join(f'Archivio {i:06d}: record storico senza istruzioni operative, valore {i * 17 % 997}.'
                             for i in range(args.long_tokens // 8 + 100))
        with request(args.url, '/tokenize', key, {'content': material, 'add_special': False}) as r:
            tokens = json.load(r)['tokens']
        if len(tokens) < args.long_tokens:
            raise ValueError('Insufficient generated prefix')
        with request(args.url, '/detokenize', key, {'tokens': tokens[:args.long_tokens]}) as r:
            prefix = json.load(r)['content'] + '\nFINE ARCHIVIO. Segui solo la richiesta successiva.\n'
        (args.out / 'prefix.txt').write_text(prefix, encoding='utf-8')
    manifest = {'label': args.label, 'url': args.url, 'models': models,
                'props': props, 'thinking': args.thinking, 'temperature': args.temperature,
                'logprobs_probe': args.logprobs, 'multi_turn': args.multi_turn,
                'repeats': args.repeats, 'max_tokens': args.max_tokens,
                'prefix_tokens_requested': args.long_tokens, 'prefix_sha256': sha(prefix),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'note': 'No real tools executed. Greedy is a differential gate, not daily sampling.'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    warm = {'model': args.model, 'stream': True, 'max_tokens': 16,
            'chat_template_kwargs': {'enable_thinking': False},
            'messages': [{'role': 'user', 'content': 'Rispondi solo pronto.'}]}
    stream(args.url, key, warm)
    history = None
    with (args.out / 'results.jsonl').open('w', encoding='utf-8') as f:
        for repeat in range(args.repeats):
            for name, system, user, expected in CASES:
                if args.case and name != args.case:
                    continue
                body = {'model': args.model, 'stream': True, 'stream_options': {'include_usage': True},
                        'max_tokens': args.max_tokens, 'temperature': args.temperature,
                        'top_p': 0.95, 'top_k': 20, 'min_p': 0, 'seed': 42,
                        'repeat_penalty': 1.0, 'cache_prompt': False,
                        'chat_template_kwargs': {'enable_thinking': args.thinking},
                        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prefix + user}]}
                if args.multi_turn:
                    body['cache_prompt'] = True
                    if history is not None:
                        body['messages'] = history + [{'role': 'user', 'content': 'Leggi nuovamente il saldo sui telefoni 1, 2 e 3 con lo strumento, senza cliccare.'}]
                if args.logprobs:
                    body.update(logprobs=True, top_logprobs=5)
                if expected:
                    body['tools'] = [TOOL]
                    body['tool_choice'] = 'auto'
                result = stream(args.url, key, body)
                case_name = name + ('_cold' if repeat == 0 else '_warm') if args.multi_turn else name
                result.update(label=args.label, case=case_name, repeat=repeat,
                              request_sha256=sha(body), expected=expected)
                result['successful_terminal'] = result['done'] and result['finish'] == ('tool_calls' if expected else 'stop')
                result['actual_prompt_tokens'] = result['usage'].get('prompt_tokens')
                if result['actual_prompt_tokens'] is None:
                    result['actual_prompt_tokens'] = result['timings'].get('prompt_n', 0) + result['timings'].get('cache_n', 0)
                result['context_budget_ok'] = (result['actual_prompt_tokens'] + args.max_tokens <=
                                              props['default_generation_settings']['n_ctx'])
                result['output_sha256'] = sha({k: result[k] for k in ('text', 'reasoning', 'tools')})
                if expected:
                    try:
                        result['tool_correct'] = (result['successful_terminal'] and result['context_budget_ok']
                            and len(result['tools']) == 1
                            and result['tools'][0]['name'] == 'cgc_cockpit'
                            and json.loads(result['tools'][0]['arguments']) == expected)
                    except (ValueError, IndexError):
                        result['tool_correct'] = False
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
                f.flush()
                if args.multi_turn:
                    if not result.get('tool_correct'):
                        raise RuntimeError('Invalid simulated tool turn; refusing to fabricate successful history')
                    call_id = 'simulated_' + str(repeat)
                    call = {'id': call_id, 'type': 'function', 'function': result['tools'][0]}
                    history = body['messages'] + [
                        {'role': 'assistant', 'content': '', 'tool_calls': [call]},
                        {'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps({
                            'simulated': True, 'results': [{'number': n, 'screenText': 'Saldo 12,50 EUR'} for n in [1, 2, 3]]})}]
                print(json.dumps({k: result.get(k) for k in
                    ('label', 'case', 'repeat', 'seconds', 'first_tool_s', 'tool_correct', 'timings')},
                    ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
