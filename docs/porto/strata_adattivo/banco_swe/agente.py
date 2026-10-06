"""Banco SWE di casa, passo 3: l'agente e il voto.  Niente sandbox (scelta dell'utente, 6/10): il modello lavora in una
cartella su D: per caso, il prompt gli vieta il resto e una guardia blocca i comandi che escono dalla cartella o vanno in
rete.  Stile mini-SWE-agent: un blocco ```bash per risposta, eseguito con Git Bash nella cartella del repo, con il venv
del caso davanti nel PATH; si chiude con `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.

Il server: quello del Daily (build e config del Daily) su 127.0.0.1:8100, avviato e fermato da qui, con
--prompt-cache-file spostato in D:\\ds4_work\\swe_casa (il file operativo dell'utente non si tocca).

    python agente.py --cases ID [ID ...] | --n 3   --name corsa   [--effort none|low|medium|high] [--budget N]
                     [--temp 1.0 --top-p 0.95 --top-k 20] [--max-steps 40]

Per ogni caso: runs\\<corsa>\\<id>\\ traiettoria.jsonl, patch.diff, voto.json; riassunto in runs\\<corsa>\\riepilogo.json.
"""
import argparse, json, os, re, socket, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepara as P   # noqa: E402

DATA, CASI = P.DATA, P.CASI
D = Path(r'D:\ds4_work\strata\Strata')
BASH = r'C:\Program Files\Git\bin\bash.exe'
DONE = 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'

SYSTEM = """You are a software engineer fixing an issue in a Python repository. You work in a shell, one command at a time.

Rules:
- Your working directory is {repo}. Read and change ONLY files inside it. Never touch, list or delete anything outside
  it, never use absolute paths, never use `..` to leave it, no network access (no pip install, curl, git fetch/push).
- Do not change the existing tests unless the issue needs it; you may add a small script to reproduce the issue and
  delete it at the end.
- `python` is the project's environment (already installed). Edit files with python scripts or sed; keep changes
  minimal and focused on the issue.
- Use the `bash` tool for every command, one call per reply (it runs in a fresh Git Bash shell in the working
  directory; output is truncated to the first and last lines).
- When the fix is done, call the `submit` tool.
"""

TOOLS = [
    {'type': 'function', 'function': {
        'name': 'bash', 'description': 'Run one bash command in the working directory and return its output.',
        'parameters': {'type': 'object', 'properties': {'command': {'type': 'string', 'description': 'the command'}},
                       'required': ['command']}}},
    {'type': 'function', 'function': {
        'name': 'submit', 'description': 'Finish: the fix is complete.', 'parameters': {'type': 'object', 'properties': {}}}},
]

TASK = """<issue>
{issue}
</issue>

Fix the issue by changing the source code of the repository in your working directory."""

BLOCK = [
    (r'(^|[\s;&|(])(/[a-z]/|[a-zA-Z]:[\\/])', 'absolute path outside the working directory'),
    (r'(^|[\s;&|(<>=\'"])/(tmp|usr|etc|var|home|mnt|bin|opt|proc|dev|root|cygdrive|sys|lib)\b', 'absolute path outside the working directory'),
    (r'(^|[\s;&|(=])~|\$HOME|\$USERPROFILE|%USERPROFILE%', 'home directory'),
    (r'\.\.[\\/]\.\.|(^|[\s;&|(])\.\.([\\/]|\s|$)', 'leaving the working directory with ..'),
    (r'\b(curl|wget|ssh|scp|ftp|nc|Invoke-WebRequest)\b', 'network'),
    (r'\bpip\s+install\b|\buv\s+(pip|add|sync)\b|\bconda\b', 'package install (network)'),
    (r'\bgit\s+(push|fetch|pull|clone|remote|config\s+--global)\b', 'git network/global'),
    (r'\b(reg|sc|shutdown|format|diskpart|bcdedit|schtasks|net\s+user|takeown|icacls|cmd\s*/c\s*del)\b', 'system'),
    (r'\brm\s+-[a-z]*r[a-z]*f?\s+(/|\*|\.)?\s*($|[;&|])', 'recursive delete of the whole directory'),
]


def guard(cmd):
    for pat, why in BLOCK:
        if re.search(pat, cmd):
            return why
    return None


def get(path, payload=None, timeout=10):
    req = urllib.request.Request('http://127.0.0.1:8100' + path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Server:
    def __init__(self, out, exe=None, source=None, extra=()):
        """exe/source: a lab engine and the serve/ folder that matches it (default: the Daily's); extra: engine args
        appended to the Daily's (e.g. --batch 2 --batch-mtp)."""
        cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
        args = list(cfg['args'])
        args[args.index('--prompt-cache-file') + 1] = str(DATA / 'prefix-swe.bin')
        cfg['args'], cfg['log'] = args + list(extra), str(out / 'engine.log')
        if exe:
            cfg['exe'] = str(exe)
        self.server_py = Path(source) / 'server.py' if source else D / 'build-0139-daily/source/serve/server.py'
        self.cfg_path = out / 'config.json'
        self.cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        self.model, self.out, self.p = cfg['model_name'], out, None

    def __enter__(self):
        import psutil
        assert not any('strata' in (q.info['name'] or '').lower() for q in psutil.process_iter(['name'])), 'a Strata engine is running'
        with socket.socket() as s:
            s.bind(('127.0.0.1', 8100))
        env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
        self.p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(self.server_py),
                                   '--engine', 'strata', '--config', str(self.cfg_path), '--host', '127.0.0.1', '--port', '8100'],
                                  cwd=D, env=env, stdout=(self.out / 'server.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 300:
            assert self.p.poll() is None, 'server exited'
            try:
                if get('/health').get('status') == 'ok':
                    return self
            except (OSError, ValueError):
                pass
            time.sleep(1)
        raise TimeoutError('server startup')

    def __exit__(self, *exc):
        import psutil
        kids = psutil.Process(self.p.pid).children(recursive=True)
        self.p.terminate()
        try:
            self.p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.p.kill()
        for k in kids:
            try:
                k.terminate()
            except psutil.Error:
                pass
        psutil.wait_procs(kids, timeout=20)


def sh(cmd, repo, venv, timeout=180):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               PATH=str(venv / 'Scripts') + os.pathsep + os.environ.get('PATH', ''), VIRTUAL_ENV=str(venv))
    env.pop('PYTHONPATH', None)
    try:
        p = subprocess.run([BASH, '-c', cmd], cwd=repo, env=env, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 124, f'(the command did not finish in {timeout} s and was stopped)'


def clip(text, head=4000, tail=3000):
    return text if len(text) <= head + tail else text[:head] + f'\n... ({len(text) - head - tail} characters cut) ...\n' + text[-tail:]


def baseline(case_dir, rec):
    """The repo at base_commit plus the environment edits, committed locally so the model's patch is `git diff HEAD`."""
    P.reset(case_dir, rec['base_commit'])
    env_patch = (case_dir / 'env.patch').read_text(encoding='utf-8')
    if env_patch.strip():
        P.apply(case_dir, env_patch, 'env-baseline')
    P.git('-c', 'user.email=banco@locale', '-c', 'user.name=banco', 'commit', '-q', '--allow-empty', '-am', 'env',
          cwd=case_dir / 'repo')


def model_patch(case_dir):
    P.git('add', '-A', cwd=case_dir / 'repo')
    return P.git('diff', '--cached', 'HEAD', cwd=case_dir / 'repo')


def grade(case_dir, rec, inst, patch):
    P.reset(case_dir, rec['base_commit'])
    env_patch = (case_dir / 'env.patch').read_text(encoding='utf-8')
    if env_patch.strip():
        P.apply(case_dir, env_patch, 'env-grade')
    if patch.strip():
        try:
            P.apply(case_dir, patch, 'model')
        except RuntimeError as e:
            return dict(resolved=False, why='patch does not apply: ' + str(e)[:300])
    P.apply(case_dir, inst['test_patch'], 'test-grade')
    status, rc, sec = P.run_tests(case_dir, inst, rec['spec'], case_dir / 'venv' / 'Scripts' / 'python.exe', 'tests-model')
    f2p_ok = [t for t in rec['fail_to_pass'] if status.get(t) == 'PASSED']
    p2p_bad = [t for t in rec['p2p_ok'] if status.get(t) != 'PASSED']
    P.reset(case_dir, rec['base_commit'])
    return dict(resolved=len(f2p_ok) == len(rec['fail_to_pass']) and not p2p_bad, f2p_ok=len(f2p_ok),
                f2p_total=len(rec['fail_to_pass']), p2p_broken=p2p_bad[:20], test_seconds=round(sec, 1))


def solve(srv, a, rec, inst, out):
    case_dir = CASI / rec['instance_id']
    repo, venv = case_dir / 'repo', case_dir / 'venv'
    baseline(case_dir, rec)
    messages = [{'role': 'system', 'content': SYSTEM.format(repo=str(repo), done=DONE)},
                {'role': 'user', 'content': TASK.format(issue=inst['problem_statement'])}]
    body = {'model': srv.model, 'max_tokens': a.max_tokens, 'temperature': a.temp, 'seed': 73, 'tools': TOOLS}
    for k, v in (('top_p', a.top_p), ('top_k', a.top_k)):
        if v is not None:
            body[k] = v
    if a.effort == 'none':
        body['chat_template_kwargs'] = {'enable_thinking': False}
    elif a.effort:
        body['reasoning_effort'] = a.effort
    if a.budget:
        body['reasoning_budget_tokens'] = a.budget
    traj = (out / 'traiettoria.jsonl').open('w', encoding='utf-8')
    stats = dict(steps=0, prompt_tokens=0, completion_tokens=0, blocked=0, format_errors=0, model_seconds=0.0,
                 shell_seconds=0.0, ended='max_steps')
    t_case = time.monotonic()
    for step in range(a.max_steps):
        if time.monotonic() - t_case > a.max_minutes * 60:
            stats['ended'] = 'time'
            break
        t0 = time.monotonic()
        try:
            r = get('/v1/chat/completions', dict(body, messages=messages), timeout=3600)
        except Exception as e:   # the server failing is a run failure, not a model answer
            stats['ended'] = f'server error: {e!r}'[:300]
            break
        stats['model_seconds'] += time.monotonic() - t0
        msg = r['choices'][0]['message']
        content = msg.get('content') or ''
        usage = r.get('usage') or {}
        stats['prompt_tokens'] += usage.get('prompt_tokens', 0)
        stats['completion_tokens'] += usage.get('completion_tokens', 0)
        stats['steps'] = step + 1
        calls = msg.get('tool_calls') or []
        rec_step = dict(step=step + 1, seconds=round(time.monotonic() - t0, 1), usage=usage,
                        finish=r['choices'][0].get('finish_reason'), reasoning_chars=len(msg.get('reasoning_content') or ''),
                        content=content, tool_calls=calls)
        call_id, cmd, submit = None, None, False
        if calls:
            c0 = calls[0]
            call_id, fn = c0.get('id') or f'call_{step}', c0.get('function') or {}
            try:
                fargs = json.loads(fn.get('arguments') or '{}')
            except ValueError:
                fargs = {}
            if fn.get('name') == 'submit':
                submit = True
            elif fn.get('name') == 'bash':
                cmd = str(fargs.get('command') or '').strip()
            messages.append({'role': 'assistant', 'content': content,
                             'tool_calls': [dict(c0, id=call_id)]})
        else:
            messages.append({'role': 'assistant', 'content': content})
            blocks = re.findall(r'```(?:bash|sh)?\s*\n(.*?)```', content, re.S)   # fallback: a fenced command
            if len(blocks) == 1:
                cmd = blocks[0].strip()
                submit = DONE in cmd and len(cmd.splitlines()) == 1
        if submit:
            stats['ended'] = 'submitted'
            traj.write(json.dumps(rec_step, ensure_ascii=False) + '\n')
            break
        if not cmd:
            stats['format_errors'] += 1
            obs = 'No command: call the `bash` tool with one command, or `submit` when the fix is done.'
        else:
            why = guard(cmd)
            if why:
                stats['blocked'] += 1
                obs = f'BLOCKED ({why}): stay inside the working directory, no network, no system commands.'
            else:
                t1 = time.monotonic()
                rc, output = sh(cmd, repo, venv)
                stats['shell_seconds'] += time.monotonic() - t1
                obs = f'<returncode>{rc}</returncode>\n<output>\n{clip(output)}\n</output>'
            rec_step['command'] = cmd
        rec_step['observation'] = obs[:20000]
        traj.write(json.dumps(rec_step, ensure_ascii=False) + '\n')
        traj.flush()
        if call_id:
            messages.append({'role': 'tool', 'tool_call_id': call_id, 'content': obs})
        else:
            messages.append({'role': 'user', 'content': obs})
    traj.close()
    patch = model_patch(case_dir)
    (out / 'patch.diff').write_text(patch, encoding='utf-8', newline='\n')
    stats['minutes'] = round((time.monotonic() - t_case) / 60, 2)
    stats['model_seconds'] = round(stats['model_seconds'], 1)
    stats['shell_seconds'] = round(stats['shell_seconds'], 1)
    vote = grade(case_dir, rec, inst, patch)
    res = dict(instance_id=rec['instance_id'], **stats, **vote)
    (out / 'voto.json').write_text(json.dumps(res, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--cases', nargs='*')
    ap.add_argument('--n', type=int, default=0)
    ap.add_argument('--effort', choices=['none', 'low', 'medium', 'high'], default=None)
    ap.add_argument('--budget', type=int, default=0)
    ap.add_argument('--temp', type=float, default=1.0)
    ap.add_argument('--top-p', type=float, default=0.95)
    ap.add_argument('--top-k', type=int, default=20)
    ap.add_argument('--max-steps', type=int, default=40)
    ap.add_argument('--max-tokens', type=int, default=16384)
    ap.add_argument('--max-minutes', type=float, default=60)
    a = ap.parse_args()
    usable = json.loads((DATA / 'casi_utilizzabili.json').read_text(encoding='utf-8'))
    ids = a.cases or usable[:a.n]
    assert ids and all(i in usable for i in ids), 'unknown or unusable case'
    insts = {json.loads(l)['instance_id']: json.loads(l) for l in (DATA / 'swe_bench_verified.jsonl').read_text(encoding='utf-8').splitlines()}
    run_dir = DATA / 'runs' / a.name
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / 'impostazioni.json').write_text(json.dumps(vars(a), indent=1) + '\n', encoding='utf-8')
    results = []
    with Server(run_dir) as srv:
        for i in ids:
            rec = json.loads((CASI / i / 'caso.json').read_text(encoding='utf-8'))
            out = run_dir / i
            out.mkdir()
            try:
                r = solve(srv, a, rec, insts[i], out)
            except Exception as e:
                r = dict(instance_id=i, resolved=False, error=repr(e)[:500])
            results.append(r)
            print(f"{i}: risolto={r.get('resolved')} passi={r.get('steps')} min={r.get('minutes')} "
                  f"token={r.get('completion_tokens')} fine={r.get('ended')} bloccati={r.get('blocked')}", flush=True)
    ok = sum(1 for r in results if r.get('resolved'))
    summary = dict(settings=vars(a), resolved=ok, total=len(results),
                   minutes=round(sum(r.get('minutes') or 0 for r in results), 1), results=results)
    (run_dir / 'riepilogo.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'risolti {ok}/{len(results)} in {summary["minutes"]} min')


if __name__ == '__main__':
    main()
