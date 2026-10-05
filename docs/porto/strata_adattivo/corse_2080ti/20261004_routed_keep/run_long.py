"""131k decode A/B on the P0 bench fixtures (L01 then L02 at ctx131k), one engine process per arm.

Same messages as docs/porto/strata_prova/banco_strata.py (instruction + 131k prefix as the first user turn,
"pronto", then the case), 1024 tokens, temperature 0, server-default reasoning. L01 reads the whole prompt
(batched prefill); L02 reuses the 131,072-token prefix from the in-process prompt cache. Daily elastic config
minus the operational prompt-cache file; lab probes only through the arm's environment.
"""
import argparse, json, sys, threading, time
from pathlib import Path
import psutil

L = Path(__file__).resolve().parent
sys.path.insert(0, str(L))
sys.path.insert(0, str(L.parents[2] / 'banco_p0'))
import run_keep as RK  # snapshot/compare/commit wait, PREFIX/CONFIG/bounded/sha
import banco_p0 as P0

PREFIX, CONFIG, bounded, sha = RK.PREFIX, RK.CONFIG, RK.bounded, RK.sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--build', default='build-v5')
    ap.add_argument('--env', action='append', default=[], help='KEY=VALUE lab probe for this arm')
    ap.add_argument('--mtp-dir', default=None)
    ap.add_argument('--tokens', type=int, default=1024)
    ap.add_argument('--set-opt', action='append', default=[], help='--option=value override of the Daily args')
    ap.add_argument('--daily-exe', action='store_true', help="use the Daily config's own exe")
    a = ap.parse_args()
    out = L / a.name
    assert not out.exists()
    cfg = json.loads(CONFIG.read_text())
    if a.daily_exe:
        exe = Path(cfg['exe']); pin = {'status': 'completed', 'executable_sha256': sha(exe)}
    else:
        exe = L / a.build / 'strata.exe'
        pin = json.loads((exe.parent / 'build.json').read_text())
        assert pin['status'] == 'completed' and sha(exe) == pin['executable_sha256']
    helper = PREFIX.load_helper()
    tok, template, convert, _ = helper.tokenizer_and_template(cfg)
    from serve import server
    man, casi, prefissi, prompts = P0.carica_fixture()
    requests = []
    for cid in ('L01', 'L02'):
        c = casi[cid]
        pre = c['prefisso_per_contesto']['ctx131k']
        msgs = [{'role': 'user', 'content': man['istruzione_contesto'] + prefissi[pre]},
                {'role': 'assistant', 'content': 'pronto'}, {'role': 'user', 'content': prompts[cid]}]
        m, tools, kw = convert({'messages': msgs, 'temperature': 0})
        requests.append((cid, tok.encode(template.render(m, tools, **kw), parse_special=True)))
    args = PREFIX.replace_option(list(server.engine_args(cfg)), '--prompt-cache-file', None)
    if a.mtp_dir:
        assert Path(a.mtp_dir, 'draft_vocab.bin').is_file()
        args = PREFIX.replace_option(args, '--mtp', str(Path(a.mtp_dir).resolve()))
    for ov in a.set_opt:
        k, v = ov.split('=', 1); assert k.startswith('--'); args = PREFIX.replace_option(args, k, v)
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1')
    for kv in a.env:
        k, v = kv.split('=', 1)
        assert k.startswith('STRATA_')
        env[k] = v
    base_path = L / 'state-baseline.json'
    now = RK.snapshot()
    diff = RK.compare(json.loads(base_path.read_text()), now)
    print(json.dumps({'run': a.name, 'state': now, 'state_diff': diff}, ensure_ascii=False), flush=True)
    assert not now['competing'], now['competing']
    assert now['commit_free_gib'] >= 52, f"Too little commit charge: {now['commit_free_gib']} GiB"
    out.mkdir()
    plan = dict(build=a.build, daily_exe=a.daily_exe, set_opt=a.set_opt, env_probe=a.env, mtp_dir=a.mtp_dir, args=args, tokens=a.tokens, state=now,
                state_diff=diff, prompt_tokens={c: len(i) for c, i in requests},
                executable_sha256=pin['executable_sha256'], daily_sha256=sha(Path(cfg['exe'])),
                config_sha256=sha(CONFIG), env={k: v for k, v in env.items() if k.startswith(('STRATA_', 'CUDA_'))})
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    result = dict(status='starting', requests=[])
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    started, owned = time.monotonic(), {}
    try:
        bounded(engine.restart, 300, engine, owned, 'Startup deadline')
        result['startup_s'] = time.monotonic() - started
        for cid, ids in requests:
            emitted, first = [], []
            t0 = time.monotonic()

            def gen():
                for token in engine.generate(ids, a.tokens, dict(temperature=0, seed=73), threading.Event()):
                    if token is not None:
                        if not emitted:
                            first.append(time.monotonic())
                        emitted.append(int(token))
            bounded(gen, 900, engine, owned, f'{cid} deadline')
            last = dict(engine.last)
            result['requests'].append(dict(case=cid, generated_ids=emitted, last=last, ttft_s=first[0] - t0 if first else None,
                                           decode_tps=last['generated'] / last['decode_ms'] * 1000 if last.get('decode_ms') else None))
            (out / f'{cid}.txt').write_text(tok.decode(emitted), encoding='utf-8')
            print(json.dumps({'case': cid, 'decode_tps': result['requests'][-1]['decode_tps'], 'prompt_ms': last.get('prompt_ms'),
                              'reused': last.get('reused'), 'drafts': (last.get('drafts_accepted'), last.get('drafts_offered'))}),
                  flush=True)
        result['status'] = 'completed'
    except BaseException as e:
        result.update(status='failed', error=repr(e))
        raise
    finally:
        try:
            bounded(engine.close, 35, engine, owned, 'Cleanup deadline')
        except BaseException as e:
            result['close_error'] = repr(e)
        result['cleanup_actions'] = PREFIX.terminate_owned(owned)
        log = (out / 'engine.log').read_text(errors='replace') if (out / 'engine.log').exists() else ''
        result['native_metrics'] = [s for s in log.splitlines() if any(
            k in s for k in ('ROUTED', 'GATE_KEEP', 'decode timing', 'strata serve:', 'draft head', 'elastic'))]
        result['daily_unchanged'] = sha(Path(cfg['exe'])) == plan['daily_sha256']
        (out / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
