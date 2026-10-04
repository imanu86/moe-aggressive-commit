"""Bounded synthetic activation capture. No HTTP, Daily edits, or speed claims."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import struct
import threading
import time

import psutil

sys.dont_write_bytecode = True
LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
F = ROOT.parent / 'Strata-2080Ti'
D = Path(r'D:\ds4_work\strata\Strata')
CONFIG = D / 'strata-2080ti-sota.json'
EXE = LAB / 'build-v1' / 'strata.exe'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PREFIX = load('prefix_helpers', ROOT / '.codex_runs/20261004_prefix_disk/validate_prefix.py')


PROMPTS = [
    ('code', 'Write Python code for a small LRU cache with capacity 3, get, put and an eviction counter. '
     'Use OrderedDict. Include a deterministic test with keys A, B, C, A, D and explain each eviction. '
     'Return the code followed by a short explanation of why a cache hit changes recency.'),
    ('explain', 'Spiega in italiano, con esempi concreti, come funzionano memoria RAM, cache della CPU, '
     'VRAM e SSD durante una conversazione con un modello linguistico. Descrivi separatamente la lettura '
     'del prompt e la generazione, indicando che cosa viene riutilizzato. Non inventare misure di velocità.'),
    ('reason', 'A warehouse has three bins. Amber starts with 24 units, cobalt with 17, jade with 31. '
     'Transfer 6 units from amber to cobalt, sell 5 from jade, then add 9 new units to amber. '
     'Write a table showing each step and the final total. Explain which operations conserve the total '
     'and give Python code that verifies the calculation.'),
]


def trace_structure(path):
    assert path.is_file() and 40 < path.stat().st_size <= 230936104, 'Missing/empty/oversized trace'
    count = accepted = 0
    with path.open('rb') as f:
        assert f.read(8) == b'SNTv0001'
        assert struct.unpack('<4I4i', f.read(32)) == (2560, 640, 10, 4, 0, 1, 35, 36)
        while True:
            raw = f.read(24)
            if not raw:
                break
            assert len(raw) == 24, 'Truncated trace record header'
            t, keep, pos, serial = struct.unpack('<IIqQ', raw)
            assert 1 <= keep <= t <= 8 and pos >= 0 and serial > 0
            size = t * 4 + 4 * t * (2560 * 4 + 10 * 12 + 10 * 2560 * 4)
            assert len(f.read(size)) == size, 'Truncated trace payload'
            count += 1
            accepted += keep
    assert 1 <= count <= 64 and accepted > 0
    return {'windows': count, 'accepted_positions': accepted}


def bounded(fn, seconds, engine, owned, label):
    errors = []
    values = []
    def work():
        try:
            values.append(fn())
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    until = time.monotonic() + seconds
    while thread.is_alive():
        if engine.proc is not None:
            try:
                p = psutil.Process(engine.proc.pid)
                born = p.create_time()
                if p.pid in owned and abs(owned[p.pid] - born) >= .02:
                    raise RuntimeError('Engine PID was reused; refusing to acquire the replacement')
                owned.setdefault(p.pid, born)
                PREFIX.process_tree(p.pid, owned)
            except psutil.Error:
                pass
        if time.monotonic() >= until:
            PREFIX.terminate_owned(owned)
            thread.join(3)
            if thread.is_alive():
                engine._neuron_worker_stuck = True
            raise TimeoutError(label)
        thread.join(.2)
    if errors:
        raise errors[0]
    return values[0] if values else None


def main():
    global EXE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name', required=True)
    ap.add_argument('--prompt', type=int, choices=range(3), required=True)
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--build', default='build-v1')
    ap.add_argument('--daily-reference', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if not a.build.replace('-', '').replace('_', '').isalnum():
        ap.error('Use a simple build directory name')
    EXE = LAB / a.build / 'strata.exe'
    if not a.name.replace('-', '').replace('_', '').isalnum():
        ap.error('Use a simple output directory name')
    out = LAB / a.name
    if out.exists():
        ap.error('Output exists; preserve prior runs')
    cfg = json.loads(CONFIG.read_text())
    profile = Path(cfg['args'][cfg['args'].index('--expert-profile') + 1])
    assert sha(profile) == '8f59b4aa8873209dff11c11e37bcda9529a1335b724a1afeea37bf6388975baf'
    if a.daily_reference:
        if a.trace:
            ap.error('Daily reference cannot capture the new trace')
        EXE = Path(cfg['exe'])
    helper = PREFIX.load_helper()
    tokenizer, template, convert, _ = helper.tokenizer_and_template(cfg)
    from serve import server
    label, prompt = PROMPTS[a.prompt]
    body = {'messages': [{'role': 'system', 'content': 'You are a careful technical assistant.'},
                         {'role': 'user', 'content': prompt}], 'reasoning_effort': 'none'}
    messages, tools, kwargs = convert(body)
    rendered = template.render(messages, tools, **kwargs)
    ids = tokenizer.encode(rendered, parse_special=True)
    turn = tokenizer.encode('<|im_start|>', parse_special=True)
    assert len(turn) == 1
    args = PREFIX.fixed_args(server, cfg, turn[0], False, None)
    # Fixed placement; include PCIe and CPU misses for diagnostics. No elasticity/swaps.
    args = PREFIX.replace_option(args, '--pcie-frac', '0.25')
    args = PREFIX.replace_option(args, '--prompt-cache', '0')
    args.append('--no-spec-split')
    env = PREFIX.environment(cfg, out / 'first-logits')
    if a.trace:
        env['STRATA_NEURON_TRACE_FILE'] = str(out / 'trace.bin')
    plan = {'status': 'planned', 'prompt_kind': label, 'rendered_prompt': rendered,
            'prompt_ids': ids, 'prompt_tokens': len(ids), 'max_new_tokens': 64,
            'trace': a.trace, 'args': args,
            'profile_sha256': sha(profile),
            'placement_note': '3800 uniform max-blob slots become 5080 variable-size slots: 8442 MiB',
            'scope': 'Fixed-placement diagnostic capture, not a timing or quality benchmark',
            'daily_sha256': sha(Path(cfg['exe'])), 'config_sha256': sha(CONFIG)}
    plan['provenance'] = {str(p): sha(p) for p in [Path(__file__), Path(PREFIX.__file__),
                            Path(helper.__file__), Path(server.__file__),
                            D / 'build-0138-daily/source/serve/frontend.py',
                            D / 'build-0138-daily/source/tools/strata_tokenizer.py',
                            Path(cfg['args'][cfg['args'].index('--pack')+1]) / 'native_experts.txt']}
    plan['diagnostic_environment'] = {k: v for k, v in env.items()
                                    if k.startswith(('STRATA_', 'CUDA_'))}
    print(json.dumps({k: plan[k] for k in ('status', 'prompt_kind', 'prompt_tokens', 'trace')}), flush=True)
    if not a.run:
        return
    if not a.daily_reference:
        pin = json.loads((EXE.parent / 'result.json').read_text())
        assert pin['status'] == 'completed' and sha(EXE) == pin['executable_sha256']
        assert all(sha(F / p) == h for p, h in pin['source_files'].items()), 'Build source changed'
    competing, idle = PREFIX.check_competing_processes()
    assert not competing, competing
    assert psutil.virtual_memory().available > 12 * 1024**3, 'Insufficient free RAM'
    out.mkdir()
    (out / 'plan.json').write_bytes((json.dumps(plan, indent=2) + '\n').encode())
    owned = {}
    engine = server.StrataEngine(str(EXE), args, cwd=cfg['cwd'], log=str(out/'engine.log'), env=env, lazy=True)
    result = {'status': 'starting', 'executable_sha256': sha(EXE), 'idle_build_nodes': idle}
    started = time.monotonic()
    try:
        bounded(engine.restart, 180, engine, owned, 'Startup deadline')
        assert engine.alive()
        result['engine_info'] = dict(engine.info)
        info = result['engine_info']
        for key, expected in {'context': 262144, 'kv': 'int8', 'kv_resident': 32768,
                              'spec': 4, 'mtp_max': 4, 'pool_workers': 7,
                              'expert_slots': 5080, 'expert_cache_mib': 8442}.items():
            assert info.get(key) == expected, (key, info.get(key), expected)
        assert float(info['pcie_frac']) == .25
        result['startup_s'] = time.monotonic() - started
        emitted = []
        cancel = threading.Event()
        def generate():
            for token in engine.generate(ids, 64, {'temperature': 0, 'seed': 73}, cancel):
                if token is not None:
                    emitted.append(int(token))
        bounded(generate, 150, engine, owned, 'Generation deadline')
        assert emitted
        logits = list(out.glob('first-logits.pos*.f32'))
        assert len(logits) == 1 and logits[0].name == f'first-logits.pos{len(ids)-1}.f32'
        result.update(status='completed', generated_ids=emitted, text=tokenizer.decode(emitted),
                      last=dict(engine.last), first_logits=PREFIX.finite_logits(logits[0]))
    except BaseException as exc:
        result.update(status='failed', error=repr(exc))
        raise
    finally:
        try:
            if not getattr(engine, '_neuron_worker_stuck', False):
                bounded(engine.close, 45, engine, owned, 'Cleanup deadline')
        except BaseException as exc:
            result['close_error'] = repr(exc)
        result['cleanup_actions'] = PREFIX.terminate_owned(owned)
        remaining = []
        for pid, born in owned.items():
            try:
                p = psutil.Process(pid)
                if abs(p.create_time()-born) < .02 and p.is_running():
                    remaining.append(pid)
            except psutil.NoSuchProcess:
                pass
        result.update(remaining_owned=remaining, elapsed_s=time.monotonic()-started,
                      daily_unchanged=sha(Path(cfg['exe'])) == plan['daily_sha256'],
                      config_unchanged=sha(CONFIG) == plan['config_sha256'])
        if (out/'trace.bin').exists():
            result['trace'] = {'bytes': (out/'trace.bin').stat().st_size, 'sha256': sha(out/'trace.bin')}
        if a.trace:
            try:
                result['trace_structure'] = trace_structure(out/'trace.bin')
            except BaseException as exc:
                result.update(status='failed', trace_error=repr(exc))
        if remaining or not result['daily_unchanged'] or not result['config_unchanged']:
            result.update(status='failed', validation_error='Cleanup or Daily preservation failed')
        (out/'result.json').write_bytes((json.dumps(result, indent=2)+'\n').encode())
    assert result['status'] == 'completed', result
    assert not result['remaining_owned'] and result['daily_unchanged'] and result['config_unchanged']
    print('FINISHED', result['status'], len(result['generated_ids']), 'tokens', flush=True)


if __name__ == '__main__':
    main()
