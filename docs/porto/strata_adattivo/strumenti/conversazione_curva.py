"""One real generated conversation: 20k initial prompt, ~1k user turns to 250k.

Uses the validated operative daily without changing it. No stress load, profiler,
automatic build, history truncation or model restart between requests.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request

CLONE = Path('D:/ds4_work/strata/Strata')
sys.path.insert(0, str(CLONE/'.venv/Lib/site-packages'))
import psutil

EXPECTED = 'f469e096e868e4579daaec71ceef63693790e300e7a4cc5b49a8853d075a1d34'
SYSTEM = ('Sei il collega tecnico in una revisione continuativa di Strata. Rispondi in italiano '
          'usando gli estratti e tutte le risposte precedenti. Distingui fatti osservabili e ipotesi; '
          'non inventare benchmark. Non eseguire strumenti. Preferisci 120-160 parole per risposta, '
          'concludi il ragionamento entro questo spazio senza elenchi lunghi. '
          'Ambiente fissato: RTX 2080 Ti modificata a 22 GB, Ryzen 7 5800X, 96 GB RAM; '
          'Strata 0.1.31 IQ3_XXS, KV massimo 262144, residenti 32768, cache esperti auto/elastica, '
          'MTP attivo. Questi parametri restano validi per l\'intera conversazione.')
QUESTIONS = [
    'Quale accesso alla memoria domina qui? Collega questo estratto al percorso discusso prima e proponi una misura utile.',
    'Quale invariante protegge la correttezza? Spiega un caso limite concreto e il test necessario prima di ottimizzare.',
    'Perche\' questa scelta puo\' comportarsi diversamente in prefill e decode? Confrontala con quanto abbiamo gia\' visto.',
    'Individua il compromesso fra cache, banda e lavoro ripetuto. Quale modifica merita una prova, senza promettere guadagni?',
    'Che cosa cambia quando il contesto cresce? Ricostruisci le dipendenze con le parti della conversazione precedenti.',
    'Scegli una sola verifica di parita\' numerica per questa parte e spiega cosa copre e cosa lascia aperto.',
    'Quale limite deriva da SM75 e quale dalla struttura del codice? Proponi una priorita\' compatibile con il nostro hardware.',
    'Cerca un rischio nella gestione dei buffer o degli indici; distingui un rischio potenziale da un difetto dimostrato.',
    'Confronta il nuovo estratto con la proposta della risposta precedente. La manterresti o la correggeresti? Motiva.',
    'Quali contatori servono per attribuire il tempo a questa fase? Spiega come evitare confronti fra carichi diversi.',
]
FIELDS = ['turn', 'prompt_tokens', 'user_tokens', 'reused_tokens', 'fresh_tokens',
          'output_tokens', 'engine_generated', 'prefill_ms', 'prefill_tps', 'decode_ms',
          'decode_tps', 'ttft_s', 'wall_s', 'finish', 'drafts_accepted', 'drafts_offered',
          'expert_hit_rate', 'expert_slots', 'gpu_temp_c', 'gpu_power_w', 'gpu_util_pct',
          'gpu_memory_mib', 'cpu_percent', 'ram_available_gib', 'local_tokens']


def write_json(path, data):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp.replace(path)


class SourceBank:
    def __init__(self, source):
        names = ['docs/DETAILS.md', 'docs/MULTI_GPU.md', 'docs/AMD_HIP.md']
        for pattern in ['include/**/*.hpp', 'src/prefill/*.cpp', 'src/kernels/cuda/*.cu',
                        'src/program/*.cpp', 'src/**/*.cpp', 'serve/*.py']:
            names += [p.relative_to(source).as_posix() for p in sorted(source.glob(pattern))]
        names = list(dict.fromkeys(n for n in names if (source/n).is_file()))
        pieces = ['\n\n=== FILE '+n+' ===\n'+(source/n).read_text(encoding='utf-8', errors='strict') for n in names]
        self.text = ''.join(pieces)
        self.pos = 0
        self.files = names

    def take(self, tok, target, head, tail, template=None, messages=None):
        # Tokenize only the new user turn. Full rendered context is counted initially
        # and near the endpoint; the server's usage is authoritative every turn.
        max_chars = 24000 if template and len(messages) > 1 else target*12
        lo, hi = 1, min(len(self.text)-self.pos, max_chars)
        if hi <= 0:
            raise RuntimeError('Unique source text exhausted; no filler repetition allowed')
        chosen = None
        while lo <= hi:
            mid = (lo+hi)//2
            content = head+self.text[self.pos:self.pos+mid]+tail
            encoded = (template.render(messages+[{'role': 'user', 'content': content}], enable_thinking=False)
                       if template else content)
            count = len(tok.encode(encoded, parse_special=True))
            if chosen is None or abs(count-target) < abs(chosen[0]-target):
                chosen = (count, mid, content)
            if abs(count-target) <= 4:
                break
            if count < target:
                lo = mid+1
            else:
                hi = mid-1
        count, consumed, content = chosen
        if abs(count-target) > 12:
            raise RuntimeError(f'Cannot size turn: target {target}, got {count}')
        self.pos += consumed
        return content, count


def stream(url, payload, timeout):
    req = urllib.request.Request(url+'/v1/chat/completions',
        data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
    begin = time.monotonic()
    content, reasoning, last, first = [], [], None, None
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            if not raw.startswith(b'data: '):
                continue
            data = raw[6:].strip()
            if data == b'[DONE]':
                break
            chunk = json.loads(data)
            if chunk.get('error'):
                raise RuntimeError(str(chunk['error']))
            for choice in chunk.get('choices', []):
                delta = choice.get('delta') or {}
                text = delta.get('content') or ''
                content.append(text)
                reasoning.append(delta.get('reasoning_content') or '')
                if text and first is None:
                    first = time.monotonic()-begin
            if 'usage' in chunk:
                last = chunk
    if last is None:
        raise RuntimeError('Streaming response has no final usage')
    return ''.join(content), ''.join(reasoning), last, first, time.monotonic()-begin


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--port', type=int, default=18120)
    ap.add_argument('--target', type=int, default=250000)
    ap.add_argument('--initial', type=int, default=20000)
    ap.add_argument('--step', type=int, default=1000)
    ap.add_argument('--max-output', type=int, default=512)
    ap.add_argument('--duration-limit-s', type=int, default=10800)
    a = ap.parse_args()
    if not 8192 <= a.initial < a.target <= 250000 or not 256 <= a.step <= 2048:
        ap.error('initial8192..target, target<=250000; step256..2048')
    if not 128 <= a.max_output <= 1024 or a.duration_limit_s <= 0:
        ap.error('max-output128..1024; positive duration')
    if 'STRATA_API_KEY' in os.environ:
        raise RuntimeError('Exclude STRATA_API_KEY in the calling lab shell; never read it')
    active = [p.info['name'] for p in psutil.process_iter(['name'])
              if (p.info['name'] or '').lower() in ('strata.exe', 'llama-server.exe')]
    if active:
        raise RuntimeError('An engine is already active; not stopping it: '+str(active))
    with socket.socket() as s:
        s.bind(('127.0.0.1', a.port))
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cfg = json.loads((CLONE/'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
    exe = Path(cfg['exe']).resolve(strict=True)
    assert hashlib.sha256(exe.read_bytes()).hexdigest() == EXPECTED
    assert '--elastic' in cfg['args']
    assert cfg['args'][cfg['args'].index('--max-context')+1] == '262144'
    source = exe.parent/'source'
    sys.path.insert(0, str(source/'tools'))
    sys.path.insert(0, str(source))
    import strata_tokenizer as ST
    from serve.frontend import ChatTemplate
    tokenizer = Path(cfg['tokenizer'])
    vocab = json.loads((tokenizer/'vocab.json').read_text(encoding='utf-8'))
    tokens = [None]*len(vocab)
    for text, i in vocab.items():
        tokens[i] = text
    tok = ST.Tokenizer(tokens, (tokenizer/'merges.txt').read_text(encoding='utf-8').split('\n'),
                       json.loads((tokenizer/'token_type.json').read_text(encoding='utf-8')))
    template = ChatTemplate(tokenizer/'chat_template.jinja')
    bank = SourceBank(source)
    messages = [{'role': 'system', 'content': SYSTEM}]
    initial_head = ('Apriamo una revisione tecnica del nostro Strata SM75. Ti passo il dossier iniziale '
                    'con documentazione e sorgenti reali. I prossimi messaggi porteranno altre parti '
                    'dello stesso progetto: ragioniamo insieme accumulando decisioni e verifiche.\n')
    tail = ('\nFine estratto. Parti da una sintesi delle dipendenze fra memoria, cache e calcolo. '
            'Scegli una priorita\' misurabile e un vincolo di correttezza; rispondi in 120-160 parole.')
    initial, initial_count = bank.take(tok, a.initial, initial_head, tail, template, messages)
    messages.append({'role': 'user', 'content': initial})
    cfg.update(cwd=str(out), log=str(out/'native.log'), host='127.0.0.1', port=a.port)
    # Keep the actual daily environment, excluding all inherited experimental overrides.
    env = {k: v for k, v in os.environ.items() if not k.startswith('STRATA_')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    cfg['env'] = {'STRATA_WATCHDOG_S': '240'}
    write_json(out/'config.json', cfg)
    bootstrap = out/'server_bootstrap.py'
    bootstrap.write_text('import sys,runpy\n'+
        f'sys.path.insert(0,{str(CLONE/".venv/Lib/site-packages")!r})\n'+
        f'runpy.run_path({str(source/"serve/server.py")!r},run_name="__main__")\n', encoding='utf-8')
    url = f'http://127.0.0.1:{a.port}'
    def get(path):
        with urllib.request.urlopen(url+path, timeout=10) as r:
            return json.load(r)
    started = time.monotonic()
    deadline = started+a.duration_limit_s
    rows = []
    result = {'status': 'starting', 'target_tokens': a.target, 'initial_target': a.initial,
              'user_step_target': a.step, 'max_output': a.max_output, 'kv_capacity': 262144,
              'kv_resident': 32768, 'elastic': True, 'exe_sha256': EXPECTED,
              'server_sha256': hashlib.sha256((source/'serve/server.py').read_bytes()).hexdigest(),
              'source_bank_sha256': hashlib.sha256(bank.text.encode()).hexdigest(),
              'source_bank_characters': len(bank.text), 'source_files': bank.files,
              'sampling': {'temperature': 0.6, 'top_p': 0.95, 'top_k': 20, 'min_p': 0.0},
              'thinking': False, 'artificial_load': False, 'history_truncated': False,
              'profiling': False, 'new_build': False, 'turns': 0, 'last_prompt_tokens': 0}
    write_json(out/'progress.json', result)
    server = None
    try:
        with (out/'server.log').open('w', encoding='utf-8') as log, \
             (out/'transcript.jsonl').open('w', encoding='utf-8') as transcript, \
             (out/'curve.csv').open('w', encoding='utf-8', newline='') as curve:
            writer = csv.DictWriter(curve, fieldnames=FIELDS)
            writer.writeheader()
            server = subprocess.Popen([sys.executable, '-B', '-u', str(bootstrap), '--engine', 'strata',
                '--config', str(out/'config.json'), '--host', '127.0.0.1', '--port', str(a.port)],
                cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            (out/'server.pid').write_text(str(server.pid))
            print('OUTPUT', out, 'INITIAL_LOCAL', initial_count, flush=True)
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Server exited during startup')
                try:
                    health = get('/health')
                    if health.get('status') == 'ok':
                        break
                except (OSError, ValueError):
                    pass
                if time.monotonic()-started > 600:
                    raise TimeoutError('Startup600s')
                time.sleep(2)
            assert health['max_context'] == 262144 and health.get('api_key') is False
            result.update(status='running', startup_s=round(time.monotonic()-started, 2), health=health,
                          initial_engine=get('/metrics')['engine'])
            write_json(out/'progress.json', result)
            print('READY', result['startup_s'], 's', flush=True)
            local_count = initial_count
            turn = 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Conversation duration limit')
                if (out/'STOP').exists():
                    result['status'] = 'stopped'
                    result['stop_reason'] = (out/'STOP').read_text(encoding='utf-8').strip() or 'stop_requested'
                    break
                turn += 1
                user_content = messages[-1]['content']
                user_tokens = len(tok.encode(user_content, parse_special=True))
                payload = {'model': 'strata', 'messages': messages, 'max_tokens': a.max_output,
                           **result['sampling'], 'stream': True, 'chat_template_kwargs': {'enable_thinking': False}}
                answer, reasoning, last, ttft, wall = stream(url, payload, min(1800, deadline-time.monotonic()))
                if not answer.strip() or reasoning:
                    raise RuntimeError('Empty content or unexpected thinking output')
                usage = last['usage']
                metrics = get('/metrics')
                request = max(metrics['requests'], key=lambda r: r['time'])
                assert request['prompt_tokens'] == usage['prompt_tokens']
                assert request['output_tokens'] == usage['completion_tokens']
                prompt = usage['prompt_tokens']
                reused = usage['prompt_tokens_details']['cached_tokens']
                if turn == 1:
                    assert prompt == initial_count and reused == 0
                if rows:
                    assert prompt > rows[-1]['prompt_tokens'], 'Context must grow without truncation'
                generated = request.get('engine_generated') or usage['completion_tokens']
                fresh = prompt-reused
                pms, dms = request['prompt_ms'], request['decode_ms']
                hardware = metrics.get('hardware') or {}
                timing = last.get('timings') or {}
                row = dict(turn=turn, prompt_tokens=prompt, user_tokens=user_tokens,
                    reused_tokens=reused, fresh_tokens=fresh, output_tokens=usage['completion_tokens'],
                    engine_generated=generated, prefill_ms=pms,
                    prefill_tps=fresh*1000/pms if pms else None, decode_ms=dms,
                    decode_tps=generated*1000/dms if dms else None, ttft_s=ttft, wall_s=wall,
                    finish=request['finish'], drafts_accepted=timing.get('draft_n_accepted'),
                    drafts_offered=timing.get('draft_n'), expert_hit_rate=request.get('hit_rate'),
                    expert_slots=metrics['engine'].get('expert_slots'), gpu_temp_c=hardware.get('gpu_temp'),
                    gpu_power_w=hardware.get('gpu_power'), gpu_util_pct=hardware.get('gpu_util'),
                    gpu_memory_mib=(hardware.get('gpu_mem_used') or 0)/2**20,
                    cpu_percent=psutil.cpu_percent(), ram_available_gib=psutil.virtual_memory().available/2**30,
                    local_tokens=local_count)
                writer.writerow(row)
                curve.flush()
                transcript.write(json.dumps({'turn': turn, 'user': user_content, 'assistant': answer,
                    'usage': usage, 'timings': timing, 'measurements': row,
                    'user_sha256': hashlib.sha256(user_content.encode()).hexdigest()}, ensure_ascii=False)+'\n')
                transcript.flush()
                rows.append(row)
                messages.append({'role': 'assistant', 'content': answer})
                result.update(turns=turn, last_prompt_tokens=prompt, last=row,
                              elapsed_s=round(time.monotonic()-started, 2), source_characters_consumed=bank.pos)
                write_json(out/'progress.json', result)
                print('TURN', turn, 'CTX', prompt, 'USER', user_tokens, 'NEW', fresh,
                      'REUSE', reused, 'OUT', usage['completion_tokens'],
                      'PREFILL', round(row['prefill_tps'], 2), 'DECODE', round(row['decode_tps'], 2),
                      'TTFT', round(ttft, 2) if ttft else None, 'FINISH', row['finish'], flush=True)
                if prompt >= a.target:
                    result['status'] = 'completed'
                    break
                followup = ('Proseguiamo la revisione, turno '+str(turn+1)+'. Nella risposta precedente hai scritto: '+
                            answer[:200].replace('\n', ' ')+'\nOra aggiungo un estratto nuovo dello stesso progetto.\n')
                question = QUESTIONS[turn%len(QUESTIONS)]
                if turn%20 == 0:
                    question += ' Richiama anche GPU/VRAM, capacita\' KV e residenti fissati nel dossier iniziale.'
                tail = '\nFine nuovo estratto. '+question+' Rispondi in 120-160 parole.'
                # Accurate final sizing includes assistant replies and chat-template overhead.
                near_end = prompt+generated+a.step+100 >= a.target
                if near_end:
                    next_content, local_count = bank.take(tok, a.target+8, followup, tail, template, messages)
                else:
                    next_content, _ = bank.take(tok, a.step, followup, tail)
                    local_count = None
                messages.append({'role': 'user', 'content': next_content})
    except Exception as exc:
        result.update(status='failed', error=repr(exc))
        raise
    finally:
        if server is not None and server.poll() is None:
            try:
                children = psutil.Process(server.pid).children(recursive=True)
            except psutil.Error:
                children = []
            server.terminate()
            for child in reversed(children):
                try:
                    child.terminate()
                except psutil.Error:
                    pass
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
            _, alive = psutil.wait_procs(children, timeout=5)
            for child in alive:
                try:
                    child.kill()
                except psutil.Error:
                    pass
        result['elapsed_s'] = round(time.monotonic()-started, 2)
        write_json(out/'progress.json', result)
        write_json(out/'result.json', result)
        print('RESULT', result['status'], 'TURNS', len(rows), 'CTX', result['last_prompt_tokens'], flush=True)


if __name__ == '__main__':
    main()
