"""TTFT bench (lab/ttft43): time to the first token in the owner's real use, one engine on the two-card split with
the 0.1.43 Daily config (strata-0143-daily.json, read only), a lab --prompt-cache-file in its own folder, a lab port.

Two clients as in real use, synthetic but realistic prompts (only upstream v0.1.43 public docs and sources, plus
generic instructions written here; no personal data):
  CC  : Claude Code over /v1/messages - system ~24k + 12 tools ~2k, first user message ~14k (project rules + files
        opened), then turns of tool_use / tool_result (~2.5k each).  Sessions cc1, cc2, cc3 share system and tools.
  DSH : over /v1/chat/completions - another system ~30k, user ~3k, turns of ~1.5k.
  side: Claude Code's helper call (a session title): small system, ~300 tokens.

Plan (one engine life, then a full restart of server and engine on the same prefix folder):
  life 1:  cc1_t1 (cold)   cc1_t2 (c: one turn more)   side1 (e)   cc1_t3 (e: the turn after the side call)
           dsh1_t1 (b, DSH cold)   cc2_t1 (b: new CC session after DSH)   dsh1_t2 (b)   12 s pause
           cc1_t4 (b: back to cc1)
           idle --idle s (an idle save may run), /unload (the engine exits, a write in flight ends), server stops
  life 2:  cc3_t1 (a: new CC session, prefix on disk)   dsh2_t1 (a: new DSH session)   cc1_t5 (d)   dsh1_t3 (d)
Per request: TTFT (send -> first content delta, server template and tokenization included), wall, prompt tokens,
cached tokens, and the engine's own lines for it (prompt ... read in, restored, miss, saved, PLE waits).
Text check: every reply is stored; the B arm's replies are compared with the A arm's by --compare.

    python bench_lock.py DET-ttft-<tag> -- python ttft_bench.py --tag <tag> --exe <strata.exe> [--serve <dir>]
           [--env "K=V K2=V2"] [--idle 25] [--compare <other tag>]
Outputs (data, never executed): ttft_<tag>/  results.json, summary.txt, engine1.log, engine2.log, server*.log, *.txt
"""
import argparse, hashlib, json, os, shlex, socket, subprocess, sys, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
D = Path(r'D:\ds4_work\strata\Strata')
REPO = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti')
SHA = '7695859a'   # upstream v0.1.43: public text only
DAILY_CFG = D / 'strata-0143-daily.json'
PREFIX_ROOT = Path(r'D:\ds4_work\strata\lab_prefix\ttft43')

ap = argparse.ArgumentParser()
ap.add_argument('--tag', required=True)
ap.add_argument('--exe', required=True)
ap.add_argument('--serve', default=str(D / 'build-0143-daily' / 'source' / 'serve'))
ap.add_argument('--env', default='', help='extra engine env, "K=V K2=V2"')
ap.add_argument('--args', default='', help='extra engine args appended to the Daily ones')
ap.add_argument('--set-opt', action='append', default=[], help='--option=value replacing a Daily arg')
ap.add_argument('--drop-opt', action='append', default=[], help='--option removed from the Daily args (with its value '
                'when the next arg is not an option)')
ap.add_argument('--server-env', default='', help='server process env, "K=V K2=V2" (e.g. STRATA_PROMPT_ENCODER=1)')
ap.add_argument('--port', type=int, default=8102)
ap.add_argument('--idle', type=float, default=25.0, help='idle seconds before the restart')
ap.add_argument('--maxt', type=int, default=24)
ap.add_argument('--compare', default=None, help='another tag: compare the replies')
ap.add_argument('--only-fixture', action='store_true', help='build and size the prompts, no engine')
a = ap.parse_args()
OUT = H / f'ttft_{a.tag}'


# ---------------------------------------------------------------- prompts
def git_text(path):
    return subprocess.run(['git', '-C', str(REPO), 'show', f'{SHA}:{path}'], capture_output=True,
                          check=True).stdout.decode('utf-8', 'replace').replace('\r\n', '\n')


def tokenizer():
    sys.path.insert(0, str(Path(a.serve).parent / 'tools'))
    import strata_tokenizer as ST
    cfg = json.loads(DAILY_CFG.read_text(encoding='utf-8-sig'))
    tp = Path(cfg['tokenizer'])
    vocab = json.loads((tp / 'vocab.json').read_text(encoding='utf-8'))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    return ST.Tokenizer(toks, (tp / 'merges.txt').read_text(encoding='utf-8').split('\n'),
                        json.loads((tp / 'token_type.json').read_text()))


TOK = None


def ntok(s):
    return len(TOK.encode(s))


def cut(text, want):
    """The first ~want tokens of text, cut at a line end."""
    probe = text[:40000]
    ratio = max(ntok(probe), 1) / max(len(probe), 1)
    n = min(len(text), int(want / ratio))
    for _ in range(4):
        got = ntok(text[:n])
        if abs(got - want) <= want * 0.02 or n >= len(text):
            break
        n = min(len(text), int(n * want / max(got, 1)))
    k = text.rfind('\n', 0, n)
    return text[:k if k > n * 0.9 else n]


CC_INSTR = """You are an interactive command line agent that helps users with software engineering tasks: fixing bugs,
adding features, refactoring, explaining code. Use the tools below to read and change files and to run commands.

# Tone and style
Be concise and direct. Explain non-trivial commands before running them. Prefer short answers; no preamble.
Never invent file contents: read a file before changing it. Keep changes minimal and in the style of the codebase.

# Doing tasks
1. Understand the request; search the codebase when the location is unknown.
2. Make a plan for multi-step work and keep it updated with the todo tool.
3. Implement, then verify with the project's own build and tests. Report what was verified and what was not.
4. Never commit unless asked. Never push to a remote unless asked.

# Tool usage policy
Call independent tools in parallel. Use the dedicated tools for reading, editing and searching files instead of
shell commands. Paths are absolute. When a tool fails, read the error and fix the cause instead of retrying blindly.

# Environment
Working directory: /work/strata (a git repository, branch main). Platform: linux. Shell: bash.
The project is an inference engine for mixture-of-experts language models on consumer GPUs, written in C++ and CUDA,
with a Python HTTP server in serve/. Its reference documentation follows.

# Reference documentation
"""
CC_RULES = """<system-reminder>
As you answer the user's questions, you can use the following context.
# Project instructions (checked into the codebase)
- Build with CMake and Ninja in Release; run the parity tests of any kernel you touch.
- Keep every engine switch opt-in behind an environment variable until it is measured.
- Commit messages: imperative, one subject line, a body explaining why. Small commits with explicit paths.
- The server in serve/ is Python 3.12 without third-party dependencies beyond the standard library.
- Benchmarks run one at a time; never start a second engine while one is running.
- Output must stay identical bit for bit unless the change says otherwise and says why.
- Logs go to stderr with the "strata" prefix; the user-facing protocol is on stdout.
# Current state
Git status: clean. Recent commits touch the prompt cache, the prefill and the server's streaming.
</system-reminder>
"""
TOOL_NAMES = [('Bash', 'Runs a shell command in a persistent session with an optional timeout.', {'command': 'string', 'timeout': 'integer', 'description': 'string'}),
              ('Read', 'Reads a file from the local filesystem, with optional line offset and limit.', {'file_path': 'string', 'offset': 'integer', 'limit': 'integer'}),
              ('Edit', 'Performs an exact string replacement in a file.', {'file_path': 'string', 'old_string': 'string', 'new_string': 'string', 'replace_all': 'boolean'}),
              ('Write', 'Writes a file, overwriting it if it exists.', {'file_path': 'string', 'content': 'string'}),
              ('Grep', 'Searches file contents with a regular expression.', {'pattern': 'string', 'path': 'string', 'glob': 'string', 'output_mode': 'string'}),
              ('Glob', 'Finds files by glob pattern, sorted by modification time.', {'pattern': 'string', 'path': 'string'}),
              ('TodoWrite', 'Creates and updates a structured task list for the session.', {'todos': 'array'}),
              ('WebFetch', 'Fetches a URL and answers a prompt about its content.', {'url': 'string', 'prompt': 'string'}),
              ('Task', 'Launches a sub-agent for a bounded, independent task.', {'description': 'string', 'prompt': 'string', 'subagent_type': 'string'}),
              ('NotebookEdit', 'Replaces, inserts or deletes a cell in a notebook.', {'notebook_path': 'string', 'cell_id': 'string', 'new_source': 'string'}),
              ('MultiEdit', 'Applies several exact replacements to one file atomically.', {'file_path': 'string', 'edits': 'array'}),
              ('LS', 'Lists the entries of a directory.', {'path': 'string', 'ignore': 'array'})]
TOOL_POLICY = (" Usage notes: the path must be absolute. Prefer this tool over the equivalent shell command. Results longer "
               "than 30000 characters are truncated. When several independent calls are needed, send them in one "
               "message so they run in parallel. Report failures with the error text. Never use it to read secrets or "
               "files outside the working directory unless the user asked. ")
DSH_INSTR = """Sei l'assistente operativo di un gruppo di sviluppo. Rispondi in italiano, in modo breve e concreto.
Lavori su un motore di inferenza per modelli a esperti su schede grafiche di fascia consumer: conosci la sua
documentazione (sotto), i comandi di build e i parametri di avvio. Quando una domanda riguarda una configurazione,
indica il parametro esatto e il suo effetto; quando riguarda un errore, la causa probabile e il controllo da fare.
Non inventare numeri: se una misura non c'e' nella documentazione, dillo. Niente preamboli, niente elenchi lunghi.

# Documentazione di riferimento
"""
SIDE_SYS = ("Analyze the conversation below and write a title for it: 3 to 7 words, sentence case, no quotes, no "
            "trailing punctuation. Reply with the title only.")
NO_TOOLS = 'Rispondi in una o due frasi, senza usare strumenti.'


def build_fixture():
    global TOK
    TOK = tokenizer()
    details = git_text('docs/DETAILS.md')
    tools = []
    for name, what, props in TOOL_NAMES:
        desc = what + TOOL_POLICY * 3
        tools.append({'name': name, 'description': desc,
                      'input_schema': {'type': 'object', 'additionalProperties': False,
                                       'required': list(props)[:1],
                                       'properties': {k: {'type': v, 'description': f'The {k.replace("_", " ")} of the call.'}
                                                      for k, v in props.items()}}})
    cc_system = CC_INSTR + cut(details, 23500)
    srcs = ['src/core/conversation_file.cpp', 'src/core/session.cpp', 'src/core/expert_cache.cpp',
            'src/core/pinned.cu', 'src/kernels/cpu/pool.cpp', 'src/core/mtp.cpp', 'src/ngram/ple_reader.cpp',
            'src/core/native_dense.cpp', 'src/core/remote_experts.cpp', 'src/core/conversation_state.cpp',
            'src/core/weights.cpp', 'src/kernels/ngram.cpp']
    S = {p: git_text(p) for p in srcs}

    def opened(files, each):
        return ''.join(f'\n<file path="/work/strata/{p}">\n{cut(S[p], each)}\n</file>\n' for p in files)

    sessions = {
        'cc1': (srcs[0:3], 'Why does a restored conversation sometimes miss the prefix on disk? Find the check that '
                           'rejects it and explain it.'),
        'cc2': (srcs[3:6], 'Where is pinned host memory allocated for the expert cache, and how is it given back?'),
        'cc3': (srcs[6:9], 'Explain how the PLE rows are read from disk and where the reader waits.'),
    }
    cc = {}
    for s, (files, q) in sessions.items():
        cc[s] = CC_RULES + '\nThese are the files I have open:\n' + opened(files, 4100) + '\n' + q
    turns = []   # cc turns 2..5: a tool_use then its tool_result
    for k, p in enumerate(srcs[9:12] + srcs[2:3]):
        turns.append({'say': f'Let me read {p} to follow the call path.', 'path': p,
                      'result': cut(S[p], 2500), 'ask': f'{NO_TOOLS} What does this file add to the answer? ({k + 2})'})
    dsh_doc = git_text('docs/INTEL.md') + '\n\n' + git_text('docs/AMD_HIP.md') + '\n\n' + git_text('docs/MULTI_GPU.md')
    dsh_system = DSH_INSTR + cut(dsh_doc, 29500)
    serve = git_text('serve/frontend.py')
    dsh_users = [
        'Ho questo estratto del server e un errore 400 sui messaggi con immagini. Dove nasce?\n\n' + cut(serve, 3000),
        'Stesso server, altra domanda: come vengono convertiti i blocchi tool_result?\n\n' + cut(serve[60000:], 3000),
    ]
    dsh_turns = [cut(serve[20000:], 1500) + '\n\nE in questo pezzo cosa cambia?',
                 cut(serve[35000:], 1500) + '\n\nUltima cosa: questo pezzo e\' coperto dai test?']
    side_user = ('Conversation so far:\nuser: ' + sessions['cc1'][1] + '\nassistant: I read conversation_file.cpp, '
                 'session.cpp and expert_cache.cpp; the restore validates the identity, the token prefix and the '
                 'geometry before any upload, and a changed prefix length is reported as a miss.\n'
                 'user: ok, and what about the second card?')
    fx = dict(sha=SHA, tools=tools, cc_system=cc_system, cc=cc, turns=turns, dsh_system=dsh_system, dsh_users=dsh_users,
              dsh_turns=dsh_turns, side_user=side_user)
    sizes = dict(cc_system=ntok(cc_system), tools=ntok(json.dumps(tools)), **{f'{s}_user': ntok(t) for s, t in cc.items()},
                 cc_turn=[ntok(t['result']) for t in turns], dsh_system=ntok(dsh_system),
                 dsh_users=[ntok(t) for t in dsh_users], dsh_turns=[ntok(t) for t in dsh_turns], side=ntok(side_user))
    fx['sizes'] = sizes
    return fx


# ---------------------------------------------------------------- requests
CC_REPLY = ('I checked the restore path: the image is validated against the engine identity, the token prefix and '
            'the session geometry before anything is uploaded.')
DSH_REPLY = ('Il punto e\' la conversione dei blocchi: il controllo dei tipi avviene prima del rendering del template, '
             'quindi un blocco non previsto produce un 400 con il nome del campo.')


def cc_body(fx, s, upto):
    """Claude Code session s at turn upto (1 = the first request)."""
    msgs = [{'role': 'user', 'content': [{'type': 'text', 'text': fx['cc'][s]}]}]
    for k in range(upto - 1):
        t = fx['turns'][k]
        tid = f'toolu_{s}_{k + 2:02d}'
        msgs.append({'role': 'assistant', 'content': [{'type': 'text', 'text': (CC_REPLY + ' ' if k else '') + t['say']},
                                                      {'type': 'tool_use', 'id': tid, 'name': 'Read',
                                                       'input': {'file_path': '/work/strata/' + t['path']}}]})
        msgs.append({'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': tid, 'content': t['result']},
                                                 {'type': 'text', 'text': t['ask']}]})
    if upto == 1:
        msgs[0]['content'][0]['text'] += '\n\n' + NO_TOOLS
    return {'model': 'x', 'max_tokens': a.maxt, 'temperature': 0, 'stream': True, 'thinking': {'type': 'disabled'},
            'system': [{'type': 'text', 'text': fx['cc_system']}], 'tools': fx['tools'], 'messages': msgs}


def dsh_body(fx, s, upto):
    first = fx['dsh_users'][0 if s == 'dsh1' else 1]
    msgs = [{'role': 'system', 'content': fx['dsh_system']}, {'role': 'user', 'content': first}]
    for k in range(upto - 1):
        msgs += [{'role': 'assistant', 'content': DSH_REPLY}, {'role': 'user', 'content': fx['dsh_turns'][k]}]
    return {'model': 'x', 'max_tokens': a.maxt, 'temperature': 0, 'stream': True,
            'chat_template_kwargs': {'enable_thinking': False}, 'messages': msgs}


def side_body(fx):
    return {'model': 'x', 'max_tokens': a.maxt, 'temperature': 0, 'stream': True, 'thinking': {'type': 'disabled'},
            'system': [{'type': 'text', 'text': SIDE_SYS}], 'messages': [{'role': 'user', 'content': fx['side_user']}]}


def stream(path, body, timeout=900):
    """POST and read the SSE stream: (ttft_s, wall_s, text, usage)."""
    req = urllib.request.Request(f'http://127.0.0.1:{a.port}{path}', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.monotonic()
    first, parts, usage = None, [], {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            c = json.loads(data)
            if path == '/v1/messages':
                if c.get('type') == 'content_block_delta':
                    d = c.get('delta') or {}
                    piece = d.get('text') or d.get('partial_json') or d.get('thinking') or ''
                    if piece and first is None:
                        first = time.monotonic()
                    if d.get('text'):
                        parts.append(d['text'])
                elif c.get('type') == 'message_start':
                    usage.update((c.get('message') or {}).get('usage') or {})
                elif c.get('type') == 'message_delta':
                    usage.update(c.get('usage') or {})
            else:
                if c.get('usage'):
                    usage.update(c['usage'])
                    usage['timings'] = c.get('timings')
                for ch in c.get('choices') or []:
                    d = ch.get('delta') or {}
                    piece = d.get('content') or d.get('reasoning_content') or ''
                    if piece and first is None:
                        first = time.monotonic()
                    if d.get('content'):
                        parts.append(d['content'])
    end = time.monotonic()
    return (first or end) - t0, end - t0, ''.join(parts), usage


# ---------------------------------------------------------------- server
def http(path, payload=None, timeout=10):
    req = urllib.request.Request(f'http://127.0.0.1:{a.port}' + path,
                                 data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'}, method='GET' if payload is None else 'POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Server:
    def __init__(self, life, prefix_file):
        cfg = json.loads(DAILY_CFG.read_text(encoding='utf-8-sig'))   # read only
        args = list(cfg['args'])
        k = args.index('--prompt-cache-file')
        args[k + 1] = str(prefix_file)
        if '--vision' in args:   # the CPU image encoder is not on the text path
            args.remove('--vision')
        cfg.pop('vision', None)
        for ov in a.set_opt:
            k2, v2 = ov.split('=', 1)
            args[args.index(k2) + 1] = v2
        for k2 in a.drop_opt:
            i = args.index(k2)
            del args[i:i + (2 if i + 1 < len(args) and not args[i + 1].startswith('--') else 1)]
        cfg['args'] = args + shlex.split(a.args)
        cfg['exe'], cfg['log'] = a.exe, str(OUT / f'engine{life}.log')
        for kv in shlex.split(a.env):
            k2, v2 = kv.split('=', 1)
            cfg.setdefault('env', {})[k2] = v2
        self.cfg = cfg
        self.cfg_path = OUT / f'config{life}.json'
        self.cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        self.life, self.p = life, None

    def __enter__(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', a.port))
        env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY' and not k.upper().startswith('STRATA_')}
        for kv in shlex.split(a.server_env):
            k2, v2 = kv.split('=', 1)
            env[k2] = v2
        t0 = time.monotonic()
        self.p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(Path(a.serve) / 'server.py'),
                                   '--engine', 'strata', '--config', str(self.cfg_path), '--host', '127.0.0.1',
                                   '--port', str(a.port)],
                                  cwd=D, env=env, stdout=(OUT / f'server{self.life}.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        while time.monotonic() - t0 < 600:
            assert self.p.poll() is None, 'server exited'
            try:
                h = http('/health')
                if h.get('status') == 'ok' and h.get('loaded'):
                    self.startup_s = time.monotonic() - t0
                    print(f'life {self.life}: engine up in {self.startup_s:.0f} s', flush=True)
                    return self
            except (OSError, ValueError):
                pass
            time.sleep(1)
        raise TimeoutError('server startup')

    def __exit__(self, *exc):
        import psutil
        try:
            print('unload:', http('/unload', {}, timeout=120), flush=True)   # the engine exits on its own
        except Exception as e:   # noqa: BLE001
            print('unload failed:', repr(e)[:200], flush=True)
        kids = psutil.Process(self.p.pid).children(recursive=True)
        self.p.terminate()
        try:
            self.p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.p.kill()
        for kd in kids:
            try:
                kd.terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(kids, timeout=30)


def log_lines(life, start):
    p = OUT / f'engine{life}.log'
    if not p.exists():
        return [], start
    b = p.read_bytes()
    keys = ('strata serve: prompt ', 'prefix disk cache', 'conversation cache', 'PLE rows', 'waited',
            'restored', 'checkpoint', 'ple io', 'ttft')
    lines = [l for l in b[start:].decode('utf-8', 'replace').splitlines() if any(k in l for k in keys)]
    return [l[:300] for l in lines], len(b)


PLAN = [  # (life, name, case, client, session, turn)
    (1, 'cc1_t1', 'freddo', 'cc', 'cc1', 1), (1, 'cc1_t2', 'c', 'cc', 'cc1', 2), (1, 'side1', 'e', 'side', '', 0),
    (1, 'cc1_t3', 'e-dopo', 'cc', 'cc1', 3), (1, 'dsh1_t1', 'b-freddo', 'dsh', 'dsh1', 1),
    (1, 'cc2_t1', 'b', 'cc', 'cc2', 1), (1, 'dsh1_t2', 'b', 'dsh', 'dsh1', 2), (1, 'idle12', 'pausa', 'idle', '', 12),
    (1, 'cc1_t4', 'b', 'cc', 'cc1', 4),
    (2, 'cc3_t1', 'a', 'cc', 'cc3', 1), (2, 'dsh2_t1', 'a', 'dsh', 'dsh2', 1), (2, 'cc1_t5', 'd', 'cc', 'cc1', 5),
    (2, 'dsh1_t3', 'd', 'dsh', 'dsh1', 3),
]


def main():
    fx_path = H / 'ttft_fixture.json'
    if fx_path.exists():
        fx = json.loads(fx_path.read_text(encoding='utf-8'))
    else:
        fx = build_fixture()
        fx_path.write_text(json.dumps(fx, ensure_ascii=False), encoding='utf-8')
    print('fixture sizes', json.dumps(fx['sizes']), 'sha256', sha(fx_path)[:16], flush=True)
    if a.only_fixture:
        return
    OUT.mkdir(exist_ok=False)
    pdir = PREFIX_ROOT / a.tag
    pdir.mkdir(parents=True, exist_ok=False)   # a fresh folder: nothing on disk before life 1
    prefix_file = pdir / 'prefix.bin'
    build = Path(a.exe).parent / 'build.json'
    res = dict(tag=a.tag, exe=a.exe, exe_sha256=sha(a.exe), build=json.loads(build.read_text()) if build.exists() else None,
               serve=a.serve, env=a.env, args=a.args, set_opt=a.set_opt, drop_opt=a.drop_opt, server_env=a.server_env, fixture_sha256=sha(fx_path), maxt=a.maxt, idle=a.idle,
               prefix_file=str(prefix_file), started=time.strftime('%Y-%m-%d %H:%M:%S'), lives={}, requests=[])
    for life in (1, 2):
        with Server(life, prefix_file) as srv:
            res['lives'][life] = dict(startup_s=round(srv.startup_s, 1), env=srv.cfg.get('env'), args=srv.cfg['args'])
            pos = log_lines(life, 0)[1]
            for lf, name, case, client, s, turn in PLAN:
                if lf != life:
                    continue
                if client == 'idle':   # a pause between clients, as in real use (an idle save may run in it)
                    time.sleep(turn)
                    lines, pos = log_lines(life, pos)
                    res['lives'][life].setdefault('pauses', {})[name] = lines
                    for l in lines:
                        print('   pausa  ', l[:200], flush=True)
                    continue
                if client == 'cc':
                    path, body = '/v1/messages', cc_body(fx, s, turn)
                elif client == 'dsh':
                    path, body = '/v1/chat/completions', dsh_body(fx, s, turn)
                else:
                    path, body = '/v1/messages', side_body(fx)
                try:
                    ttft, wall, txt, usage = stream(path, body)
                    ok, err = True, None
                except Exception as e:   # noqa: BLE001
                    ttft = wall = None; txt, usage, ok, err = '', {}, False, repr(e)[:300]
                time.sleep(1.0)   # the engine's last lines of this request
                lines, pos = log_lines(life, pos)
                (OUT / f'{name}.txt').write_text(txt, encoding='utf-8')
                r = dict(life=life, name=name, case=case, ok=ok, err=err, ttft=ttft and round(ttft, 2),
                         wall=wall and round(wall, 2), usage=usage, text_head=txt[:80].replace('\n', ' '), engine=lines)
                res['requests'].append(r)
                pl = next((l for l in lines if 'strata serve: prompt ' in l and ' tokens = ' in l), '')
                print(f'{name:8s} {case:8s} ttft {r["ttft"]} s  {pl[13:140]}', flush=True)
                for l in lines:
                    if 'prefix disk cache' in l or 'conversation cache: restored' in l or 'waited' in l:
                        print('          ', l[:200], flush=True)
            if life == 1:
                time.sleep(a.idle)   # idle: what an idle save does happens here
                lines, pos = log_lines(life, pos)
                res['lives'][life]['idle_lines'] = lines
        res['lives'][life]['shutdown_tail'] = log_lines(life, 0)[0][-6:]
    res['ended'] = time.strftime('%Y-%m-%d %H:%M:%S')
    res['prefix_files'] = sorted((p.name, p.stat().st_size) for p in pdir.iterdir())
    if a.compare:
        other = H / f'ttft_{a.compare}'
        res['same_text_as'] = {r['name']: ((other / f'{r["name"]}.txt').exists() and
                                           (other / f'{r["name"]}.txt').read_text(encoding='utf-8') ==
                                           (OUT / f'{r["name"]}.txt').read_text(encoding='utf-8'))
                               for r in res['requests']}
    (OUT / 'results.json').write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    rows = [f'{r["name"]:8s} {r["case"]:8s} ttft {r["ttft"]} s wall {r["wall"]} s prompt '
            f'{r["usage"].get("input_tokens") or r["usage"].get("prompt_tokens")} cached '
            f'{r["usage"].get("cache_read_input_tokens") or (r["usage"].get("prompt_tokens_details") or {}).get("cached_tokens")}'
            for r in res['requests']]
    (OUT / 'summary.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    print('\n'.join(rows), flush=True)
    if a.compare:
        print('same text as', a.compare, json.dumps(res['same_text_as']), flush=True)


if __name__ == '__main__':
    main()
