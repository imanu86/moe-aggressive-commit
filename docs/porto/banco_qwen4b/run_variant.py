"""Exclusive GPU variant runner. Never stops an existing server or changes the daily.

Coordinator stops the daily explicitly and restores it after the campaign.
All child handles and outputs belong to this one variant; no real tools execute.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
MODEL = Path(r'D:\models\qwen35-4b\Qwen3.5-4B-Q4_K_M.gguf')


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bin', type=Path, default=Path(r'D:\ds4_work\bin_q36m3'))
    p.add_argument('--draft', type=Path)
    p.add_argument('--draft-max', type=int, default=1)
    p.add_argument('--label', required=True)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--port', type=int, default=8114)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--max-tokens', type=int, default=512)
    p.add_argument('--temperature', type=float, default=0)
    p.add_argument('--long-tokens', type=int, default=0)
    p.add_argument('--thinking', action='store_true')
    p.add_argument('--logprobs', action='store_true')
    p.add_argument('--multi-turn', action='store_true')
    p.add_argument('--case')
    p.add_argument('--q4k-occ12', action='store_true', help='Opt-in isolated CUDA candidate only')
    args = p.parse_args()
    running = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq llama-server.exe', '/NH'],
                             capture_output=True, text=True, check=True)
    if 'llama-server.exe' in running.stdout.lower():
        raise RuntimeError('Existing llama-server detected; refusing to stop or overlap it')
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', args.port)) == 0:
            raise RuntimeError('Port already occupied')
    args.out.mkdir(parents=True, exist_ok=False)
    slots = args.out / 'slots'
    slots.mkdir()
    command = [str(args.bin / 'llama-server.exe'), '-m', str(MODEL), '--alias', 'qwen4b-bench',
               '-ngl', '99', '-fit', 'off', '-fa', 'on', '--no-mmap',
               '-ctk', 'q8_0', '-ctv', 'q8_0', '-b', '2048', '-ub', '512', '-t', '16',
               '-c', '131072', '-np', '1', '--jinja', '--reasoning', 'on', '--no-reasoning-preserve',
               '--temp', '0.6', '--top-p', '0.95', '--top-k', '20', '--min-p', '0',
               '--repeat-penalty', '1', '--no-context-shift', '--cache-ram', '0', '-ctxcp', '8',
               '--slot-save-path', str(slots), '--host', '127.0.0.1', '--port', str(args.port),
               '--metrics', '--log-file', str(args.out / 'server.log'), '-lv', '3']
    if args.draft:
        if not args.draft.is_file():
            raise FileNotFoundError(args.draft)
        if args.draft_max not in (1, 2, 3, 4, 6, 8):
            raise ValueError('Approved draft lengths: 1/2/3 and user-requested tool sweep 4/6/8')
        command += ['-md', str(args.draft), '--spec-type', 'draft-mtp', '-ngld', '99',
                    '-ctkd', 'q8_0', '-ctvd', 'q8_0', '--spec-draft-n-max', str(args.draft_max),
                    '--spec-draft-n-min', '1', '--spec-draft-p-min', '0']
    env = os.environ.copy()
    # Do not inherit unrelated experimental tunables or daily credentials.
    for k in list(env):
        if k.startswith(('LLAMA_', 'GGML_', 'QWEN', 'SPEC_')):
            env.pop(k)
    settings = {'GGML_SCHED_ASYNC_INPUTS': '1', 'GGML_CUDA_GRAPH_COMPAT_CACHE': '1',
                'GGML_CUDA_MMVQ_OCCUPANCY': '1'}
    if args.q4k_occ12:
        settings['GGML_CUDA_QWEN4B_Q4K_OCC12'] = '1'
    env.update(settings)
    hashes = {f.name: file_sha(f) for f in args.bin.iterdir() if f.suffix in ('.exe', '.dll')}
    manifest = {'command': command, 'env': settings, 'runtime_sha256': hashes,
                'model_sha256': file_sha(MODEL),
                'draft_sha256': file_sha(args.draft) if args.draft else None}
    (args.out / 'runtime.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    url = f'http://127.0.0.1:{args.port}'
    server = None
    try:
        with (args.out / 'stdout.log').open('wb') as out, (args.out / 'stderr.log').open('wb') as err:
            server = subprocess.Popen(command, cwd=args.out, env=env, stdout=out, stderr=err)
            (args.out / 'pid.txt').write_text(str(server.pid), encoding='ascii')
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f'Server exited {server.returncode}; inspect stderr.log')
                try:
                    with urllib.request.urlopen(url + '/health', timeout=2) as r:
                        if json.load(r).get('status') == 'ok':
                            break
                except (OSError, ValueError):
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError('Server health timeout')
                time.sleep(1)
            with (args.out / 'gpu-start.txt').open('w') as f:
                subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.free,clocks.sm,clocks.mem,power.draw',
                                '--format=csv'], stdout=f, check=True)
            bench = [sys.executable, str(HERE / 'bench_http.py'), '--url', url,
                     '--label', args.label, '--out', str(args.out / 'bench'),
                     '--repeats', str(args.repeats), '--max-tokens', str(args.max_tokens),
                     '--temperature', str(args.temperature), '--long-tokens', str(args.long_tokens)]
            if args.thinking:
                bench += ['--thinking']
            if args.case:
                bench += ['--case', args.case]
            if args.logprobs:
                bench += ['--logprobs']
            if args.multi_turn:
                bench += ['--multi-turn']
            subprocess.run(bench, env=env, check=True)
            with urllib.request.urlopen(url + '/metrics', timeout=5) as r:
                (args.out / 'metrics.txt').write_bytes(r.read())
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=20)
        (args.out / 'shutdown.json').write_text(json.dumps({
            'pid': server.pid if server else None,
            'returncode': server.returncode if server else None,
            'stopped': server is None or server.poll() is not None}), encoding='utf-8')


if __name__ == '__main__':
    main()
