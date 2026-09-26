"""Diagnostic-only Nsight capture. Never use instrumented timings as speed results.

Requires coordinator-owned idle GPU and no existing llama-server. Stops only its
own uniquely tagged server. The coordinator restores the daily separately.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

from bench_http import stream

NSYS = Path(r'C:\Program Files\NVIDIA Corporation\Nsight Systems 2024.5.1\target-windows-x64\nsys.exe')


def tagged_pids():
    command = "Get-CimInstance Win32_Process -Filter \"name='llama-server.exe'\" | Where-Object { $_.CommandLine -like '*qwen4b-nsys-private*' } | Select-Object -ExpandProperty ProcessId"
    r = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command],
                       capture_output=True, text=True, check=True)
    return [int(line.strip()) for line in r.stdout.splitlines() if line.strip().isdigit()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--bin', type=Path, default=Path(r'D:\ds4_work\bin_q36m3'))
    p.add_argument('--q4k-occ12', action='store_true')
    p.add_argument('--duration', type=int, default=20)
    p.add_argument('--delay', type=int, default=10)
    p.add_argument('--max-tokens', type=int, default=2048)
    args = p.parse_args()
    existing = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq llama-server.exe', '/NH'],
                              capture_output=True, text=True, check=True)
    if 'llama-server.exe' in existing.stdout.lower():
        raise RuntimeError('Existing server: coordinator must stop it first')
    args.out.mkdir(parents=True, exist_ok=False)
    server_args = [str(args.bin / 'llama-server.exe'),
        '-m', r'D:\models\qwen35-4b\Qwen3.5-4B-Q4_K_M.gguf', '--alias', 'qwen4b-nsys-private',
        '-ngl', '99', '-fit', 'off', '-fa', 'on', '--no-mmap', '-ctk', 'q8_0', '-ctv', 'q8_0',
        '-b', '2048', '-ub', '512', '-t', '16', '-c', '131072', '-np', '1', '--jinja',
        '--reasoning', 'on', '--no-reasoning-preserve', '--no-context-shift', '--cache-ram', '0',
        '-ctxcp', '8', '--host', '127.0.0.1', '--port', '8115']
    command = [str(NSYS), 'profile', '--trace=cuda,nvtx', '--sample=none', '--cpuctxsw=none',
               '--cuda-graph-trace=node', '--delay=' + str(args.delay), '--duration=' + str(args.duration), '--kill=false',
               '--output=' + str(args.out / 'capture')] + server_args
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(('LLAMA_', 'GGML_', 'QWEN', 'SPEC_')):
            env.pop(key)
    env.update(GGML_SCHED_ASYNC_INPUTS='1', GGML_CUDA_GRAPH_COMPAT_CACHE='1', GGML_CUDA_MMVQ_OCCUPANCY='1')
    if args.q4k_occ12:
        env['GGML_CUDA_QWEN4B_Q4K_OCC12'] = '1'
    (args.out / 'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    (args.out / 'environment.json').write_text(json.dumps({k: v for k, v in env.items() if k.startswith('GGML_')}, indent=2), encoding='utf-8')
    profiler = None
    try:
        with (args.out / 'profile.log').open('wb') as log:
            profiler = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=args.out)
            deadline = time.monotonic() + 90
            while True:
                if profiler.poll() is not None:
                    raise RuntimeError('Profiler exited before server was ready')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8115/health', timeout=2) as r:
                        if json.load(r).get('status') == 'ok':
                            break
                except (OSError, ValueError):
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError('Profile server health timeout')
                time.sleep(1)
            pids = tagged_pids()
            if len(pids) != 1:
                raise RuntimeError('Could not uniquely identify profile server')
            (args.out / 'server_pid.txt').write_text(str(pids[0]), encoding='ascii')
            payload = {'model': 'qwen4b-nsys-private', 'stream': True, 'max_tokens': args.max_tokens,
                       'temperature': 0, 'cache_prompt': False,
                       'chat_template_kwargs': {'enable_thinking': False},
                       'messages': [{'role': 'user', 'content':
                         'Scrivi una guida tecnica dettagliata di almeno 1500 parole sui benchmark GPU, '
                         'discutendo memoria, kernel, latenza, throughput, verifica numerica e riproducibilita.'}]}
            result = stream('http://127.0.0.1:8115', '', payload)
            (args.out / 'instrumented_request.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            # Fixed capture duration may outlast a short response; continue generating only while active.
            if profiler.poll() is None:
                result = stream('http://127.0.0.1:8115', '', payload)
                (args.out / 'instrumented_request2.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            profiler.wait(timeout=180)
            if profiler.returncode:
                raise RuntimeError('Profiler failed: ' + str(profiler.returncode))
    finally:
        for pid in tagged_pids():
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], stdout=subprocess.DEVNULL, check=False)
        if profiler is not None and profiler.poll() is None:
            profiler.terminate()
            profiler.wait(timeout=20)
        (args.out / 'shutdown.json').write_text(json.dumps({'remaining_tagged_pids': tagged_pids()}), encoding='utf-8')


if __name__ == '__main__':
    main()
