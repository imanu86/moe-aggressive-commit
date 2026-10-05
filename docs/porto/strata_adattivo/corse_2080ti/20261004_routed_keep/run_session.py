"""A long session: one engine process, a sequence of requests, per-request decode speed and expert-cache hit rate.

Purpose: see how the adaptive tier (and STRATA_ELASTIC_CORE_ADAPT) converges over a session, the Daily's real
regime, instead of fresh processes per request. Tasks repeat in rounds (code, ledger, explain); in-process
prompt cache off so every request reads its prompt.
"""
import argparse, json, re, sys, threading, time
from pathlib import Path

L = Path(__file__).resolve().parent
sys.path.insert(0, str(L))
import run_keep as RK
from run_closed import fixture

PREFIX, CONFIG, bounded, sha, PROMPTS = RK.PREFIX, RK.CONFIG, RK.bounded, RK.sha, RK.PROMPTS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--build', default='build-core1')
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--tokens', type=int, default=384)
    ap.add_argument('--set-opt', action='append', default=[], help='--option=value override of the Daily args')
    ap.add_argument('--drop-opt', action='append', default=[], help='--option removed from the Daily args')
    a = ap.parse_args()
    out = L / a.name
    assert not out.exists()
    cfg = json.loads(CONFIG.read_text())
    exe = L / a.build / 'strata.exe'
    pin = json.loads((exe.parent / 'build.json').read_text())
    assert pin['status'] == 'completed' and sha(exe) == pin['executable_sha256']
    tok, template, convert, _ = PREFIX.load_helper().tokenizer_and_template(cfg)
    from serve import server
    reqs = []
    for t in ('code', 'ledger', 'explain'):
        prompt = PROMPTS[1][1] if t == 'explain' else fixture(t)[0]
        body = {'messages': [{'role': 'system', 'content': 'You are a careful technical assistant.'},
                             {'role': 'user', 'content': prompt}], 'reasoning_effort': 'none'}
        m, tools, kw = convert(body)
        reqs.append((t, tok.encode(template.render(m, tools, **kw), parse_special=True)))
    args = PREFIX.replace_option(list(server.engine_args(cfg)), '--prompt-cache-file', None)
    args = PREFIX.replace_option(args, '--prompt-cache', '0')
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1')
    for kv in a.env:
        k, v = kv.split('=', 1); assert k.startswith('STRATA_'); env[k] = v
    for ov in a.set_opt:
        k, v = ov.split('=', 1); assert k.startswith('--'); args = PREFIX.replace_option(args, k, v)
    for ov in a.drop_opt:
        assert ov.startswith('--') and ov in args; args = PREFIX.replace_option(args, ov, None)
    now = RK.snapshot()
    assert not now['competing'] and now['commit_free_gib'] >= 52, now
    out.mkdir()
    (out / 'plan.json').write_text(json.dumps(dict(build=a.build, env_extra=a.env, args=args, rounds=a.rounds,
                                                   tokens=a.tokens, state=now), indent=2) + '\n')
    result = dict(status='starting', requests=[])
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    owned = {}
    try:
        bounded(engine.restart, 300, engine, owned, 'Startup deadline')
        for r in range(a.rounds):
            for t, ids in reqs:
                emitted = []

                def gen():
                    for token in engine.generate(ids, a.tokens, dict(temperature=0, seed=73), threading.Event()):
                        if token is not None:
                            emitted.append(int(token))
                bounded(gen, 600, engine, owned, f'{t} deadline')
                last = dict(engine.last)
                hit = last['hits'] / last['lookups'] if last.get('lookups') else None
                rec = dict(round=r, task=t, generated=last['generated'], decode_tps=last['generated'] / last['decode_ms'] * 1000,
                           hit_rate=hit, drafts=(last.get('drafts_accepted'), last.get('drafts_offered')))
                result['requests'].append(rec)
                print(json.dumps(rec), flush=True)
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
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
