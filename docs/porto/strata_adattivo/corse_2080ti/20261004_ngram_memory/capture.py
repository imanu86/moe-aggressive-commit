"""Capture three longer natural continuations, then replay experts on one GPU.

Uses the existing pinned local capture helper. Does not modify Daily, build,
publish, start HTTP, or run concurrent engines. Timings are diagnostic only.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import psutil
from trace_io import read_rows, split_trace, sha

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[5]
FORK = ROOT.parent / 'Strata-2080Ti'
OLD = ROOT / '.codex_runs/20261004_neuron_cache'
DAILY = Path(r'D:\ds4_work\strata\Strata')
EXE = OLD / 'build-probe100-v2/strata.exe'
REPLAY = ROOT / '.codex_runs/20261004_turn_pruning_build/build-v1/neuron_trace_replay.exe'


def save(path, obj):
    with path.open('xb') as stream:
        stream.write((json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--tokens', type=int, default=512)
    a = ap.parse_args()
    a.out = a.out.resolve()
    assert 256 <= a.tokens <= 512
    assert not a.out.exists()
    a.out.mkdir(parents=True)
    sys.path.insert(0, str(OLD))
    import run_capture as C
    P = C.PREFIX
    cfg = json.loads(C.CONFIG.read_text())
    build = json.loads((EXE.parent / 'result.json').read_text())
    assert sha(EXE) == build['executable_sha256'] == 'dd92a8980567c403be5f3ae31e24bbc97850c30b06f3f164e8afbb80d7e90a3a'
    assert sha(REPLAY) == '64b55b1bef1b4ef4528ab8be9d7cc7f4465ed878e40ddf3b60bd00667d7a970c'
    # The immutable old engine is intentionally reused. Current source differences
    # since that build are diagnostic replay/hybrid tools; record, do not hide them.
    differences = {p: sha(FORK/p) for p, h in build['source_files'].items() if sha(FORK/p) != h}
    helper = P.load_helper()
    tok, template, convert, _ = helper.tokenizer_and_template(cfg)
    from serve import server
    competing, idle = P.check_competing_processes()
    assert not competing, competing
    assert psutil.virtual_memory().available > 16*1024**3
    assert psutil.disk_usage(str(a.out)).free > 12*1024**3
    launcher = Path(r'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat')
    pins = {str(p): sha(p) for p in (Path(cfg['exe']), C.CONFIG, launcher)}
    state = {'status': 'running', 'tokens_requested_per_text': a.tokens,
             'hardware': {'gpu': 'modified RTX 2080 Ti 22 GB', 'cpu': 'Ryzen 5800X', 'ram_gib': 96},
             'engine_sha256': sha(EXE), 'engine_build_source_commit': build['source_commit'],
             'current_source_differences_from_engine_build': differences,
             'replayer_sha256': sha(REPLAY), 'protected_files_before': pins,
             'runner_sha256': sha(Path(__file__)), 'reader_sha256': sha(Path(__file__).with_name('trace_io.py')),
             'helpers': {str(p): sha(p) for p in (Path(C.__file__), Path(P.__file__), Path(helper.__file__), Path(server.__file__))},
             'captures': [], 'replays': []}
    save(a.out/'plan.json', state)
    owned = {}; engine = None; began = time.monotonic()
    try:
        for index, (label, prompt) in enumerate(C.PROMPTS):
            folder = a.out/label; folder.mkdir()
            body = {'messages': [{'role': 'system', 'content': 'You are a careful technical assistant.'},
                                 {'role': 'user', 'content': prompt}], 'reasoning_effort': 'none'}
            messages, tools, kwargs = convert(body)
            rendered = template.render(messages, tools, **kwargs)
            ids = tok.encode(rendered, parse_special=True)
            args = P.fixed_args(server, cfg, tok.encode('<|im_start|>', parse_special=True)[0], False, None)
            args = P.replace_option(args, '--pcie-frac', '0.25')
            args = P.replace_option(args, '--prompt-cache', '0')
            args.append('--no-spec-split')
            env = P.environment(cfg, folder/'unused-logits')
            env.pop('STRATA_DUMP_FIRST_LOGITS', None)
            env.update(STRATA_NEURON_TRACE_FILE=str(folder/'trace.snt'), STRATA_NEURON_TRACE_WINDOWS='512',
                       STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8')
            engine = server.StrataEngine(str(EXE), args, cwd=cfg['cwd'], log=str(folder/'engine.log'), env=env, lazy=True)
            started = time.monotonic()
            C.bounded(engine.restart, 180, engine, owned, label+' startup')
            assert engine.alive()
            for key, expected in {'context': 262144, 'kv': 'int8', 'kv_resident': 32768, 'spec': 4,
                                  'mtp_max': 4, 'pool_workers': 7, 'expert_slots': 5080, 'expert_cache_mib': 8442}.items():
                assert engine.info.get(key) == expected, (key, engine.info.get(key), expected)
            emitted = []
            def generate():
                for token in engine.generate(ids, a.tokens, {'temperature': 0, 'seed': 73}, threading.Event()):
                    if token is not None:
                        emitted.append(int(token))
            C.bounded(generate, 240, engine, owned, label+' generation')
            info, last = dict(engine.info), dict(engine.last)
            C.bounded(engine.close, 45, engine, owned, label+' close')
            engine = None
            rows = read_rows(folder/'trace.snt')
            full = ids + emitted
            assert [r['pos'] for r in rows] == list(range(len(ids)-1, len(ids)+len(emitted)-1))
            assert all(r['token'] == full[r['pos']] for r in rows)
            assert len(rows) >= 192, 'too few rows for the prespecified 128-input calibration'
            meta = {'label': label, 'prompt_ids': ids, 'generated_ids': emitted, 'rendered_prompt': rendered,
                    'generated_text': tok.decode(emitted), 'accepted_inputs': len(rows), 'engine_info': info,
                    'engine_last': last, 'args': args, 'elapsed_diagnostic_s': time.monotonic()-started,
                    'environment': {k: v for k, v in env.items() if k.startswith(('STRATA_', 'CUDA_'))},
                    'trace_sha256': sha(folder/'trace.snt')}
            save(folder/'capture.json', meta); state['captures'].append(meta)
            print('CAPTURE', label, len(rows), 'inputs', round(meta['elapsed_diagnostic_s'], 2), 's', flush=True)
        # All online engines have exited before offline GPU work starts.
        for meta in state['captures']:
            folder = a.out/meta['label']
            chunks = split_trace(folder/'trace.snt', folder/'chunks')
            for chunk in chunks:
                output = chunk.with_suffix('.snr')
                env = P.environment(cfg, folder/'unused-logits'); env.pop('STRATA_DUMP_FIRST_LOGITS', None)
                started = time.monotonic()
                with chunk.with_suffix('.log').open('xb') as log:
                    proc = subprocess.Popen([str(REPLAY), str(chunk), cfg['args'][cfg['args'].index('--native')+1], str(output)],
                                            cwd=a.out, env=env, stdout=log, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    owned[proc.pid] = psutil.Process(proc.pid).create_time()
                    proc.wait(timeout=180)
                assert proc.returncode == 0, chunk.with_suffix('.log').read_text()
                record = {'label': meta['label'], 'chunk': chunk.name, 'input_sha256': sha(chunk),
                          'output_sha256': sha(output), 'bytes': output.stat().st_size,
                          'elapsed_diagnostic_s': time.monotonic()-started}
                state['replays'].append(record)
                print('REPLAY', meta['label'], chunk.name, round(record['elapsed_diagnostic_s'], 2), 's', flush=True)
        state['status'] = 'completed'
    except BaseException as exc:
        state.update(status='failed', error=repr(exc))
        raise
    finally:
        if engine is not None and not getattr(engine, '_neuron_worker_stuck', False):
            try:
                C.bounded(engine.close, 45, engine, owned, 'final close')
            except BaseException as exc:
                state['close_error'] = repr(exc)
        state['cleanup_actions'] = P.terminate_owned(owned)
        remaining = []
        for pid, born in owned.items():
            try:
                proc = psutil.Process(pid)
                if abs(proc.create_time()-born) < .02 and proc.is_running(): remaining.append(pid)
            except psutil.NoSuchProcess:
                pass
        state['remaining_owned'] = remaining
        state['protected_files_unchanged'] = all(sha(Path(p)) == h for p, h in pins.items())
        state['elapsed_s'] = time.monotonic()-began
        if remaining or not state['protected_files_unchanged']: state['status'] = 'failed'
        save(a.out/'capture-results.json', state)
    assert state['status'] == 'completed'
    print('CAPTURE_AND_REPLAY_OK', round(state['elapsed_s'], 2), flush=True)


if __name__ == '__main__':
    main()
