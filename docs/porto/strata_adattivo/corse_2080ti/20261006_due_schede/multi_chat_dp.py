"""DATA PARALLEL (owner 7/10): two independent engines, one per card, each with the full model (no layer split, its own
MTP head), each serving its own chat.  Same 131k contexts and prompts as multi_chat.py.

Both engines read the experts through --mmap-experts, so the 43.8 GiB of expert files sit ONCE in the OS file cache and
both processes share them (two resident arenas would need ~80 GiB of private RAM).  Every request's text is checked.

Steps: start both engines (2080 Ti on :8101, 3060 on :8102); warm each with its own context (A on the 2080 Ti, B on the
3060), one at a time; then (1) the 2080 Ti chat alone, (2) the 3060 chat alone, (3) both at once.  Per chat: tokens,
wall s, TTFT (= the engine's prompt_ms; queue excluded), decode t/s from the engine's timings; plus the aggregate.
Outputs are data; never execute model text.

    python bench_lock.py DET-mc-dp -- python multi_chat_dp.py [--exe X] [--tag T] [--resident-2080]
"""
import argparse, json, os, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import banco_p0 as P0   # noqa: E402

D = Path(r'D:\ds4_work\strata\Strata')
ap = argparse.ArgumentParser()
ap.add_argument('--exe', default=str(H.parent / '20261004_routed_keep' / 'build-main-be4cf1c' / 'strata.exe'))
ap.add_argument('--serve', default=r'C:\Users\imanu\source\repos\Strata-2080Ti-core\serve')
ap.add_argument('--tag', default='dp')
ap.add_argument('--resident-2080', action='store_true', help='2080 Ti engine keeps the resident arena (no mmap)')
ap.add_argument('--maxt', type=int, default=512)
a = ap.parse_args()

os.environ['STRATA_POOL_SPIN_US'] = '100'
OUT = H / f'multi_chat_{a.tag}'
OUT.mkdir(exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
SYS_A = man['istruzione_contesto'] + prefissi['ctx131k']
SYS_B = man['istruzione_contesto'] + prefissi['aghi131k']


def http(port, path, payload=None, timeout=10):
    req = urllib.request.Request(f'http://127.0.0.1:{port}' + path,
                                 data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Server:
    def __init__(self, name, port, gpu, mmap):
        cfg = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))   # read only
        args = list(cfg['args'])
        k = args.index('--prompt-cache-file')
        del args[k:k + 2]
        if mmap:
            args.append('--mmap-experts')
        self.dir = OUT / name
        self.dir.mkdir(exist_ok=True)
        cfg['args'], cfg['log'], cfg['exe'], cfg['gpu'] = args, str(self.dir / 'engine.log'), a.exe, gpu
        self.cfg_path = self.dir / 'config.json'
        self.cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        self.model, self.port, self.name, self.p = cfg['model_name'], port, name, None

    def start(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', self.port))
        env = {k: v for k, v in os.environ.items() if k not in ('STRATA_API_KEY', 'CUDA_VISIBLE_DEVICES')}
        self.p = subprocess.Popen([str(D / '.venv/Scripts/python.exe'), '-B', str(Path(a.serve) / 'server.py'),
                                   '--engine', 'strata', '--config', str(self.cfg_path), '--host', '127.0.0.1',
                                   '--port', str(self.port)],
                                  cwd=D, env=env, stdout=(self.dir / 'server.log').open('w', encoding='utf-8'),
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)

    def wait(self):
        t0 = time.monotonic()
        while time.monotonic() - t0 < 600:
            assert self.p.poll() is None, f'{self.name}: server exited'
            try:
                if http(self.port, '/health').get('status') == 'ok':
                    print(f'{self.name} up in {time.monotonic() - t0:.0f} s', flush=True)
                    return
            except (OSError, ValueError):
                pass
            time.sleep(1)
        raise TimeoutError(self.name)

    def stop(self):
        import psutil
        if not self.p:
            return
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
        psutil.wait_procs(kids, timeout=20)


res = {}


def ask(key, srv, system, q, maxt):
    t0 = time.monotonic()
    try:
        r = http(srv.port, '/v1/chat/completions',
                 dict(model=srv.model, temperature=0, max_tokens=maxt,
                      messages=[dict(role='system', content=system), dict(role='user', content=q)],
                      chat_template_kwargs=dict(enable_thinking=False)), timeout=3600)
        u, tm = r.get('usage') or {}, r.get('timings') or {}
        s = time.monotonic() - t0
        txt = r['choices'][0]['message']['content'] or ''
        res[key] = dict(ok=True, eng=srv.name, s=round(s, 1), out=u.get('completion_tokens'),
                        prompt=u.get('prompt_tokens'), cache_n=tm.get('cache_n'), prompt_n=tm.get('prompt_n'),
                        ttft_s=round((tm.get('prompt_ms') or 0) / 1000, 1), decode_tps=tm.get('predicted_per_second'),
                        wall_tps=round((u.get('completion_tokens') or 0) / s, 1), head=txt[:120], tail=txt[-120:])
        (OUT / f'{key}.txt').write_text(txt, encoding='utf-8')
    except Exception as e:   # noqa: BLE001
        res[key] = dict(ok=False, eng=srv.name, s=round(time.monotonic() - t0, 1), err=repr(e)[:300])
    print(key, json.dumps(res[key], ensure_ascii=False), flush=True)


def ram():
    import psutil
    vm = psutil.virtual_memory()
    return f'RAM free {vm.available / 2**30:.1f} GiB'


big = Server('e2080', 8101, 1, mmap=not a.resident_2080)
small = Server('e3060', 8102, 0, mmap=True)
try:
    print(ram(), flush=True)
    big.start()
    big.wait()          # one at a time: the two loads do not fight over the disk
    small.start()
    small.wait()
    print('both up;', ram(), flush=True)
    ask('warmA_2080', big, SYS_A, 'Rispondi solo: pronto.', 8)
    ask('warmB_3060', small, SYS_B, 'Rispondi solo: pronto.', 8)
    print(ram(), flush=True)
    QA, QB = prompts['L01'], prompts['L02']
    ask('soloA_2080', big, SYS_A, QA, a.maxt)
    ask('soloB_3060', small, SYS_B, QB, a.maxt)
    t = time.monotonic()
    th = [threading.Thread(target=ask, args=('parA_2080', big, SYS_A, QA, a.maxt)),
          threading.Thread(target=ask, args=('parB_3060', small, SYS_B, QB, a.maxt))]
    for x in th:
        x.start()
    for x in th:
        x.join()
    wall = time.monotonic() - t
    tot = sum((res[k].get('out') or 0) for k in ('parA_2080', 'parB_3060'))
    print(f'2 chat in parallelo (una per motore): {tot} token in {wall:.1f} s = {tot / wall:.1f} t/s aggregati;'
          f' {ram()}', flush=True)
    for k in ('A', 'B'):
        so, pa = res.get(f'solo{k}_' + ('2080' if k == 'A' else '3060')), res.get(f'par{k}_' + ('2080' if k == 'A' else '3060'))
        if so and pa and so.get('ok') and pa.get('ok'):
            same = (OUT / f'solo{k}_{so["eng"][1:]}.txt').read_text(encoding='utf-8') == \
                   (OUT / f'par{k}_{pa["eng"][1:]}.txt').read_text(encoding='utf-8')
            print(f'{k}: testo solo == parallelo: {same}', flush=True)
    (OUT / 'res.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
finally:
    small.stop()
    big.stop()
