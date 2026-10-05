"""One bounded engine run: Daily elastic config, lab exe, optional STRATA_ROUTED_KEEP probe.

Purpose: calibrate how much routed-sum error (offline screen metric) the generated
text tolerates. Arm B zeroes decode router weights ranked >= keep (experts still
computed, so no speed claim); arm A is the same exe without the probe. Before each
run the machine state is compared with the first run's baseline and recorded.
Outputs are data; never execute model text.
"""
import argparse, json, subprocess, sys, threading, time
from pathlib import Path
import psutil

L = Path(__file__).resolve().parent
sys.path.insert(0, str(L.parent / '20261004_closed_cache'))
sys.path.insert(0, str(L.parents[4] / '.codex_runs' / '20261004_neuron_cache'))  # original helpers
from run_capture import PREFIX, CONFIG, bounded, sha, PROMPTS
from run_closed import fixture, oracle


def commit_free_gib():
    """Windows commit charge still available (GlobalMemoryStatusEx.ullAvailPageFile)."""
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 2**30


def wait_commit(need_gib=60.0, deadline_s=240):
    t0 = time.monotonic()
    while commit_free_gib() < need_gib and time.monotonic() - t0 < deadline_s:
        time.sleep(5)
    return round(commit_free_gib(), 1)


def snapshot():
    s = {'available_ram_gib': round(psutil.virtual_memory().available / 2**30, 1),
         'commit_free_gib': wait_commit()}
    try:
        used, util = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu',
                                              '--format=csv,noheader,nounits'], text=True, timeout=15).strip().split(', ')
        s.update(gpu_used_mib=int(used), gpu_util=int(util))
    except Exception as e:
        s['gpu_error'] = repr(e)
    names = {(p.info.get('name') or '').lower() for p in psutil.process_iter(['name'])}
    s['cgcontrol'] = 'cgcontrol.exe' in names
    s['competing'], _ = PREFIX.check_competing_processes()
    return s


def compare(base, now):
    diff = []
    if now['competing']:
        diff.append(f"processi in conflitto: {now['competing']}")
    if base.get('cgcontrol') != now.get('cgcontrol'):
        diff.append(f"CGControl {'acceso' if now.get('cgcontrol') else 'spento'} (base: {base.get('cgcontrol')})")
    if abs(now.get('gpu_used_mib', 0) - base.get('gpu_used_mib', 0)) > 1024:
        diff.append(f"VRAM occupata {now.get('gpu_used_mib')} MiB (base {base.get('gpu_used_mib')})")
    if abs(now['available_ram_gib'] - base['available_ram_gib']) > 8:
        diff.append(f"RAM libera {now['available_ram_gib']} GiB (base {base['available_ram_gib']})")
    return diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--arm', choices=['A', 'B'], required=True)
    ap.add_argument('--keep', type=int, default=0)
    ap.add_argument('--renorm', action='store_true')
    ap.add_argument('--task', choices=['ledger', 'code', 'explain'], required=True)
    ap.add_argument('--tokens', type=int, default=512)
    ap.add_argument('--build', default='build-v1')
    ap.add_argument('--teacher', default=None, help='arm-A run folder: force its prompt+answer, log per position')
    ap.add_argument('--min-w', type=float, default=0.0, help='STRATA_ROUTED_MIN_W (needs build-v2)')
    ap.add_argument('--min-keep', type=int, default=0, help='STRATA_ROUTED_MIN_KEEP (default 4 with --min-w)')
    ap.add_argument('--skip', action='store_true', help='STRATA_ROUTED_KEEP_SKIP=1: really skip zeroed experts')
    ap.add_argument('--miss-w', type=float, default=0.0, help='STRATA_ROUTED_MISS_W (needs build-v3)')
    ap.add_argument('--gate-keep', type=float, default=0.0, help='STRATA_GATE_KEEP fraction (needs build-v4)')
    ap.add_argument('--lookahead', action='store_true', help='STRATA_LOOKAHEAD_PROBE=1 (needs build-v5), any arm')
    ap.add_argument('--mtp-dir', default=None, help='alternative MTP pack folder (e.g. a draft-vocab candidate), any arm')
    ap.add_argument('--daily-exe', action='store_true', help="use the Daily config's own exe (arm A only)")
    ap.add_argument('--env', action='append', default=[], help='KEY=VALUE extra STRATA_ env (diagnostics), any arm')
    ap.add_argument('--set-opt', action='append', default=[], help='--option=value override of the Daily args')
    a = ap.parse_args()
    assert (a.arm == 'B') == (1 <= a.keep <= 9 or a.min_w > 0 or a.miss_w > 0 or a.gate_keep > 0)
    out = L / a.name
    assert not out.exists()
    cfg = json.loads(CONFIG.read_text())
    if a.daily_exe:
        assert a.arm == 'A'
        exe = Path(cfg['exe'])
        pin = {'status': 'completed', 'executable_sha256': sha(exe)}
    else:
        exe = L / a.build / 'strata.exe'
        pin = json.loads((exe.parent / 'build.json').read_text())
        assert pin['status'] == 'completed' and sha(exe) == pin['executable_sha256']
    helper = PREFIX.load_helper()
    tok, template, convert, _ = helper.tokenizer_and_template(cfg)
    from serve import server
    if a.task == 'explain':
        prompt, expected = PROMPTS[1][1], None
    else:
        prompt, expected = fixture(a.task)
    body = {'messages': [{'role': 'system', 'content': 'You are a careful technical assistant.'},
                         {'role': 'user', 'content': prompt}], 'reasoning_effort': 'none'}
    messages, tools, kw = convert(body)
    ids = tok.encode(template.render(messages, tools, **kw), parse_special=True)
    teacher_answer = []
    if a.teacher:
        t = json.loads((L / a.teacher / 'result.json').read_text(encoding='utf-8'))
        assert json.loads((L / a.teacher / 'plan.json').read_text(encoding='utf-8'))['prompt_ids'] == ids
        teacher_answer = t['generated_ids']
        ids = ids + teacher_answer
        a.tokens = 1
    # Daily elastic configuration; only the operational prompt-cache file is left out.
    args = PREFIX.replace_option(list(server.engine_args(cfg)), '--prompt-cache-file', None)
    if not a.teacher:
        args = PREFIX.replace_option(args, '--prompt-cache', '0')
    if a.mtp_dir:
        assert Path(a.mtp_dir, 'draft_vocab.bin').is_file() and Path(a.mtp_dir, 'dense.bin').is_file()
        args = PREFIX.replace_option(args, '--mtp', str(Path(a.mtp_dir).resolve()))
    if a.teacher:  # in-process prompt cache on: request 1 stores the prompt, request 2 reads only the answer fresh  # the answer is read through the verify windows (probe active), the prompt by the batched path
        args = PREFIX.replace_option(args, '--short-read', str(len(teacher_answer) + 8))
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1')
    if a.lookahead:
        env['STRATA_LOOKAHEAD_PROBE'] = '1'
    for kv in a.env:
        k, v = kv.split('=', 1); assert k.startswith('STRATA_'); env[k] = v
    for ov in a.set_opt:
        k, v = ov.split('=', 1); assert k.startswith('--'); args = PREFIX.replace_option(args, k, v)
    if a.teacher:
        env.update(STRATA_LOGPOS=str((out / 'logpos.tsv').resolve()), STRATA_LOGPOS_TOPK='20')
    if a.arm == 'B':
        if a.keep:
            env['STRATA_ROUTED_KEEP'] = str(a.keep)
        if a.min_w > 0:
            env['STRATA_ROUTED_MIN_W'] = f'{a.min_w:g}'
        if a.min_keep:
            env['STRATA_ROUTED_MIN_KEEP'] = str(a.min_keep)
        if a.skip:
            env['STRATA_ROUTED_KEEP_SKIP'] = '1'
        if a.miss_w > 0:
            env['STRATA_ROUTED_MISS_W'] = f'{a.miss_w:g}'
        if a.gate_keep > 0:
            env['STRATA_GATE_KEEP'] = f'{a.gate_keep:g}'
        if a.renorm:
            env['STRATA_ROUTED_KEEP_RENORM'] = '1'
    base_path = L / 'state-baseline.json'
    now = snapshot()
    if not base_path.exists():
        base_path.write_text(json.dumps(now, indent=2) + '\n')
    diff = compare(json.loads(base_path.read_text()), now)
    print(json.dumps({'run': a.name, 'state': now, 'state_diff': diff}, ensure_ascii=False), flush=True)
    assert not now['competing'], now['competing']
    assert psutil.virtual_memory().available > 16 * 2**30, 'Too little available RAM'
    assert now['commit_free_gib'] >= 52, f"Too little commit charge: {now['commit_free_gib']} GiB"
    out.mkdir()
    plan = dict(teacher=a.teacher, teacher_answer_tokens=len(teacher_answer), arm=a.arm, keep=a.keep,
                min_w=a.min_w, min_keep=a.min_keep, skip=a.skip, miss_w=a.miss_w, gate_keep=a.gate_keep, lookahead=a.lookahead, mtp_dir=a.mtp_dir, extra_env=a.env, set_opt=a.set_opt, build=a.build, renorm=a.renorm, task=a.task, args=args, prompt_ids=ids,
                prompt_tokens=len(ids), max_tokens=a.tokens, expected=expected,
                sampling=dict(temperature=0, seed=73), executable_sha256=pin['executable_sha256'],
                daily_sha256=sha(Path(cfg['exe'])), config_sha256=sha(CONFIG), state=now, state_diff=diff,
                env={k: v for k, v in env.items() if k.startswith(('STRATA_', 'CUDA_'))})
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    result = dict(status='starting')
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    started, owned, emitted = time.monotonic(), {}, []
    try:
        bounded(engine.restart, 300, engine, owned, 'Startup deadline')
        assert engine.alive()
        result['engine_info'] = dict(engine.info)
        result['startup_s'] = time.monotonic() - started
        req, first = time.monotonic(), []

        if a.teacher:
            prefix = ids[:len(ids) - len(teacher_answer)]
            bounded(lambda: list(engine.generate(prefix, 1, plan['sampling'], threading.Event())), 300, engine, owned,
                    'Teacher prefix deadline')
            result['teacher_prefix_last'] = dict(engine.last)
            req = time.monotonic()

        def gen():
            for token in engine.generate(ids, a.tokens, plan['sampling'], threading.Event()):
                if token is not None:
                    if not emitted:
                        first.append(time.monotonic())
                    emitted.append(int(token))
        bounded(gen, 300, engine, owned, 'Generation deadline')
        text = tok.decode(emitted)
        result.update(status='completed', generated_ids=emitted, text=text, last=dict(engine.last),
                      request_s=time.monotonic() - req, ttft_s=first[0] - req if first else None,
                      oracle=oracle(text, expected))
        (out / 'answer.txt').write_text(text, encoding='utf-8')
    except BaseException as e:
        result.update(status='failed', error=repr(e))
        raise
    finally:
        try:
            bounded(engine.close, 35, engine, owned, 'Cleanup deadline')
        except BaseException as e:
            result['close_error'] = repr(e)
        result['cleanup_actions'] = PREFIX.terminate_owned(owned)
        remaining = []
        for pid, born in owned.items():
            try:
                p = psutil.Process(pid)
                if abs(p.create_time() - born) < .02 and p.is_running():
                    remaining.append(pid)
            except psutil.NoSuchProcess:
                pass
        log = (out / 'engine.log').read_text(errors='replace') if (out / 'engine.log').exists() else ''
        result.update(remaining_owned=remaining, elapsed_s=time.monotonic() - started,
                      daily_unchanged=sha(Path(cfg['exe'])) == plan['daily_sha256'],
                      config_unchanged=sha(CONFIG) == plan['config_sha256'],
                      native_metrics=[s for s in log.splitlines() if any(
                          k in s for k in ('ROUTED_KEEP', 'ROUTED_MISS', 'GATE_KEEP', 'draft head', 'decode timing', 'strata serve:', 'expert-cache', 'elastic'))])
        (out / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: result.get(k) for k in ('status', 'last', 'ttft_s', 'oracle', 'native_metrics')},
                     ensure_ascii=False), flush=True)
    assert not remaining and result['daily_unchanged'] and result['config_unchanged']


if __name__ == '__main__':
    main()
