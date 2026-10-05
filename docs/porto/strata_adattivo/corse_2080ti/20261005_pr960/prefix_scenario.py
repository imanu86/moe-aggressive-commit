"""PR 960 vs our --prompt-cache-file: does a NEW chat with the same long system prompt reuse it after a request with
another start (a title request, a subagent), and after a server restart?

Runs the Daily's own frozen server (build-0139-daily) on 127.0.0.1:8100 with a COPY of the Daily config whose
--prompt-cache-file and log point into this folder (the operational prompt-prefix-v1.bin is never touched).
Scenario (temperature 0, 32 output tokens):
  A1  system S (~25k tokens) + question 1           new chat
  A2  A1 + answer + question 2                       same chat, next turn
  T   other short system + text                      a different start (title request)
  B1  system S + question 3                          a NEW chat with the same system prompt   <- the PR's case
  -- server restart --
  C1  system S + question 4                          a new chat after a restart (our file's case)
Reuse is read from the engine log lines `strata serve: prompt N tokens = R reused + M read`.
"""
import json, os, re, socket, subprocess, sys, time, urllib.request
from pathlib import Path

B = Path(__file__).resolve().parent
D = Path(r'D:\ds4_work\strata\Strata')
FIX = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0\fixtures')
OUT = B / ('scenario-' + time.strftime('%H%M%S'))
OUT.mkdir()
sys.path[:0] = [str(D / '.venv/Lib/site-packages')]
import psutil

cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
args = list(cfg['args'])
i = args.index('--prompt-cache-file')
args[i + 1] = str(OUT / 'prefix-test.bin')
cfg['args'], cfg['log'] = args, str(OUT / 'engine.log')
tmp_cfg = OUT / 'config.json'
tmp_cfg.write_text(json.dumps(cfg, indent=2), encoding='utf-8')

# ~25k-token system prompt: the start of the 32k fixture (C++ sources), like an agent's tool list + rules
S = 'You are a coding agent. Tools and repository context follow.\n\n' + (FIX / 'ctx32k.txt').read_text(encoding='utf-8')[:96000]
assert not any('strata' in (q.info['name'] or '').lower() for q in psutil.process_iter(['name']))


def start():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 8100))
    env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    log = (OUT / 'server.log').open('a', encoding='utf-8')
    p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(D / 'build-0139-daily/source/serve/server.py'),
                          '--engine', 'strata', '--config', str(tmp_cfg), '--host', '127.0.0.1', '--port', '8100'],
                         cwd=D, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 300:
        assert p.poll() is None, 'server exited'
        try:
            if get('/health').get('status') == 'ok':
                return p
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise TimeoutError('startup')


def stop(p):
    kids = psutil.Process(p.pid).children(recursive=True)
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
    for k in kids:
        try:
            k.terminate()
        except psutil.Error:
            pass
    psutil.wait_procs(kids, timeout=10)


def get(path, payload=None, timeout=5):
    req = urllib.request.Request('http://127.0.0.1:8100' + path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat(name, messages):
    n0 = len(serve_lines())
    t0 = time.monotonic()
    r = get('/v1/chat/completions', {'model': cfg['model_name'], 'messages': messages, 'max_tokens': 32, 'temperature': 0,
                                     'chat_template_kwargs': {'enable_thinking': False}}, timeout=600)
    wall = time.monotonic() - t0
    for _ in range(20):
        new = serve_lines()[n0:]
        if new:
            break
        time.sleep(0.5)
    m = re.search(r'prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms', new[-1] if new else '')
    row = dict(step=name, wall_s=round(wall, 2), answer=r['choices'][0]['message']['content'][:60])
    if m:
        row.update(prompt=int(m[1]), reused=int(m[2]), read=int(m[3]), prompt_ms=int(m[4]))
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row, r['choices'][0]['message']['content']


def serve_lines():
    p = Path(cfg['log'])
    return [s for s in p.read_text(encoding='utf-8', errors='replace').splitlines() if 'strata serve: prompt' in s] if p.exists() else []


rows = []
p = start()
try:
    sysm = {'role': 'system', 'content': S}
    r, a1 = chat('A1 nuova chat', [sysm, {'role': 'user', 'content': 'Which file defines the argument parser? One line.'}])
    rows.append(r)
    r, _ = chat('A2 turno 2', [sysm, {'role': 'user', 'content': 'Which file defines the argument parser? One line.'},
                               {'role': 'assistant', 'content': a1},
                               {'role': 'user', 'content': 'And which header declares it? One line.'}])
    rows.append(r)
    r, _ = chat('T inizio diverso', [{'role': 'system', 'content': 'Write a 5-word title for the conversation.'},
                                     {'role': 'user', 'content': 'We discussed the argument parser of a C++ project.'}])
    rows.append(r)
    r, _ = chat('B1 nuova chat, stesso system', [sysm, {'role': 'user', 'content': 'Name one function that parses flags. One line.'}])
    rows.append(r)
finally:
    stop(p)
time.sleep(3)
p = start()
try:
    r, _ = chat('C1 dopo il riavvio', [sysm, {'role': 'user', 'content': 'Name one struct used for parameters. One line.'}])
    rows.append(r)
finally:
    stop(p)
(OUT / 'esito.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
pf = OUT / 'prefix-test.bin'
print('file del prefisso:', pf.stat().st_size if pf.exists() else 'assente')
