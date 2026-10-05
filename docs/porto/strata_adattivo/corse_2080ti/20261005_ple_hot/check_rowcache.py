"""Daily 0.1.39 r1 with the PLE table on D: and a 16M-row PLE cache: the launcher's server + config on port 8100 -
health, a complete JSON oracle, the PLE path in the engine log. Stops only the processes it started.
(Same method as 20261005_daily0139/check_installed0139.py.)
"""
import json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path

B = Path(__file__).resolve().parent
D = Path(r'D:\ds4_work\strata\Strata')
OUT = B / 'installed-startup'
OUT.mkdir(exist_ok=False)
sys.path[:0] = [str(D / 'build-0139-daily/source'), str(D / '.venv/Lib/site-packages'), str(D / 'tools/sm75')]
import psutil
import validate_model as V

S2_D = r'D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf'
cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
assert cfg['exe'] == str(D / 'build-0139-daily/strata.exe')
assert cfg['args'][cfg['args'].index('--ple-gguf') + 1] == S2_D
assert cfg['args'][cfg['args'].index('--ple-row-cache') + 1] == '16777216'
assert not any('strata' in (q.info['name'] or '').lower() for q in psutil.process_iter(['name']))
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 8100))
engine_log = Path(cfg['log'])
log_from = engine_log.stat().st_size if engine_log.exists() else 0
env = {k: v for k, v in os.environ.items() if k != 'STRATA_API_KEY'}
env['PYTHONDONTWRITEBYTECODE'] = '1'
server = D / 'build-0139-daily/source/serve/server.py'
cmd = [str(D / '.venv/Scripts/python.exe'), '-B', str(server), '--engine', 'strata', '--config', str(D / 'strata-2080ti-sota.json'),
       '--host', '127.0.0.1', '--port', '8100']
result = dict(status='running', exe_sha256=V.sha(Path(cfg['exe'])), server_sha256=V.sha(server),
              config_sha256=V.sha(D / 'strata-2080ti-sota.json'), port=8100, host='127.0.0.1',
              method='the launcher\'s paths, the installed shipping binary, loopback health, a JSON marker and the PLE path '
                     'in the engine log; own processes only')
p, owner, start = None, None, time.monotonic()


def save():
    (OUT / 'esito.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


def get(path, payload=None, timeout=3):
    req = urllib.request.Request('http://127.0.0.1:8100' + path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def new_engine_lines():
    if not engine_log.exists():
        return []
    with engine_log.open('rb') as f:
        f.seek(log_from if engine_log.stat().st_size >= log_from else 0)
        return f.read().decode('utf-8', 'replace').splitlines()


save()
try:
    with (OUT / 'server.log').open('w', encoding='utf-8') as log:
        p = subprocess.Popen(cmd, cwd=D, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        owner = psutil.Process(p.pid)
        while time.monotonic() - start < 240:
            assert p.poll() is None, 'server exited before ready'
            try:
                health = get('/health')
                result['health'] = health
                if health.get('status') == 'ok':
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise TimeoutError('Daily server startup deadline')
        assert result['health']['max_context'] == 262144
        result['startup_s'] = time.monotonic() - start
        result['metrics'] = get('/metrics')
        response = get('/v1/chat/completions', {'model': cfg['model_name'], 'messages': [
            {'role': 'user', 'content': 'Return only JSON with key marker and literal value DAILY-039-READY.'}],
            'max_tokens': 128, 'temperature': 0, 'chat_template_kwargs': {'enable_thinking': False}}, timeout=120)
        text = response['choices'][0]['message']['content']
        finish = response['choices'][0]['finish_reason']
        clean = text.strip()
        if clean.startswith('```json\n') and clean.endswith('\n```'):
            clean = clean[8:-4].strip()
        result['smoke'] = dict(content=text, finish=finish, usage=response.get('usage'),
                               oracle_pass=V.evaluate_answer(clean, finish, {'marker': 'DAILY-039-READY'}))
        assert result['smoke']['oracle_pass']
        lines = new_engine_lines()
        result['ple_lines'] = [s for s in lines if 'PLE on' in s or 'native dense' in s or 'ple io' in s][:6]
        assert any('PLE on' in s and S2_D in s for s in lines), 'engine log does not show the PLE table on D:'
        result.update(status='completed', elapsed_s=time.monotonic() - start)
        print('Daily 0.1.39 on 8100 with the PLE table on D: and the 16M row cache: health, JSON oracle and PLE path PASS', flush=True)
except BaseException as exc:
    result.update(status='failed', error=repr(exc), elapsed_s=time.monotonic() - start)
    try:
        result.setdefault('ple_lines', [s for s in new_engine_lines() if 'PLE' in s or 'native dense' in s][:6])
    except OSError:
        pass
    raise
finally:
    if p is not None:
        try:
            children = owner.children(recursive=True)
        except psutil.Error:
            children = []
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(timeout=5)
        for child in children:
            try:
                if child.is_running():
                    child.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(children, timeout=5)
        for child in alive:
            try:
                child.kill()
            except psutil.Error:
                pass
    result['owned_server_stopped'] = True
    save()
