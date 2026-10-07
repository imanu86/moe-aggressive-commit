"""Sampled decode (temperature > 0) on the 131k bench prompts, one engine process per arm (7/10, Gumbel #1281).

    python samp_ab.py --name DET-samp-<arm> --build build-gumbel-59ae43d --temp 1.0 --n 20 [--env KEY=VALUE ...]
        [--add-opt=--pipeline-windows=2 ...]

Two unmeasured warm requests (L01 loads the 131k prefix, then L02), then n measured requests alternating L01/L02,
temperature `temp`, seed = 1000 + k (the same seeds in every arm), max 512 tokens, not forced.  Per request: decode
t/s, tokens, drafts accepted/offered.  Results in <name>/samp.jsonl; summary printed at the end.
"""
import argparse, importlib, json, statistics, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
K = HERE.parent / '20261004_routed_keep'
sys.path.insert(0, str(K))
import run_long as RL   # noqa: E402

RK, P0 = RL.RK, RL.P0
PREFIX, CONFIG, bounded, sha = RL.PREFIX, RL.CONFIG, RL.bounded, RL.sha
SERVE = Path(r'C:\Users\imanu\source\repos\Strata-wt\gumbel')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--build', required=True)
    ap.add_argument('--temp', type=float, required=True)
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--tokens', type=int, default=512)
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--add-opt', action='append', default=[])
    a = ap.parse_args()
    assert a.name.startswith('DET-')
    out = K / a.name
    assert not out.exists()
    cfg = json.loads(CONFIG.read_text())
    exe = K / a.build / 'strata.exe'
    pin = json.loads((exe.parent / 'build.json').read_text())
    assert pin['status'] == 'completed' and sha(exe) == pin['executable_sha256']
    helper = PREFIX.load_helper()
    tok, template, convert, _ = helper.tokenizer_and_template(cfg)
    for m in [m for m in sys.modules if m == 'serve' or m.startswith('serve.')]:
        del sys.modules[m]
    sys.path.insert(0, str(SERVE))
    server = importlib.import_module('serve.server')
    man, casi, prefissi, prompts = P0.carica_fixture()
    prompt = {}
    for cid in ('L01', 'L02'):
        pre = casi[cid]['prefisso_per_contesto']['ctx131k']
        msgs = [{'role': 'user', 'content': man['istruzione_contesto'] + prefissi[pre]},
                {'role': 'assistant', 'content': 'pronto'}, {'role': 'user', 'content': prompts[cid]}]
        m, tools, kw = convert({'messages': msgs, 'temperature': a.temp})
        prompt[cid] = tok.encode(template.render(m, tools, **kw), parse_special=True)
    args = PREFIX.replace_option(list(server.engine_args(cfg)), '--prompt-cache-file', None)
    for ov in a.add_opt:
        k, _, v = ov.partition('='); assert k.startswith('--'); args += [k, v] if _ else [k]
    args += ['--layer-split', '16', '--trim-stage-weights']
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1',
               CUDA_VISIBLE_DEVICES='1,0', STRATA_POOL_SPIN_US='100')
    for kv in a.env:
        k, v = kv.split('=', 1)
        assert k.startswith('STRATA_') or k.startswith('CUDA_')
        env[k] = v
    for _ in range(60):
        now = RK.snapshot()
        if not now['competing']:
            break
        time.sleep(10)
    assert not now['competing'], now['competing']
    out.mkdir()
    (out / 'plan.json').write_text(json.dumps(dict(build=a.build, temp=a.temp, n=a.n, tokens=a.tokens, args=args,
                                                   env={k: v for k, v in env.items() if k.startswith(('STRATA_', 'CUDA_'))},
                                                   executable_sha256=pin['executable_sha256']), indent=2) + '\n')
    jl = (out / 'samp.jsonl').open('a', encoding='utf-8')
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    owned, rows = {}, []
    try:
        bounded(engine.restart, 300, engine, owned, 'Startup deadline')
        plan = [('L01', -1, True), ('L02', -2, True)] + [(('L01', 'L02')[k % 2], k, False) for k in range(a.n)]
        for cid, k, warm in plan:
            emitted = []

            def gen():
                for t in engine.generate(prompt[cid], 64 if warm else a.tokens,
                                         dict(temperature=a.temp, seed=1000 + max(k, 0)), threading.Event()):
                    if t is not None:
                        emitted.append(int(t))
            bounded(gen, 900, engine, owned, f'request {k} deadline')
            last = dict(engine.last)
            tps = last['generated'] / last['decode_ms'] * 1000 if last.get('decode_ms') else None
            row = dict(k=k, case=cid, warm=warm, tps=tps, generated=last.get('generated'),
                       acc=last.get('drafts_accepted'), off=last.get('drafts_offered'))
            jl.write(json.dumps(row) + '\n'); jl.flush()
            if not warm:
                rows.append(row)
        for c in ('L01', 'L02'):
            v = [r for r in rows if r['case'] == c and r['tps']]
            tps = [r['tps'] for r in v]
            acc = sum(r['acc'] or 0 for r in v) / max(1, sum(r['off'] or 0 for r in v))
            tpw = sum(r['generated'] for r in v)
            print(f"{a.name} T={a.temp} {c}: n={len(v)} t/s media {statistics.mean(tps):.1f} "
                  f"(sd {statistics.pstdev(tps):.1f}) accettazione {100 * acc:.1f}% token {tpw}", flush=True)
    finally:
        jl.close()
        try:
            bounded(engine.close, 35, engine, owned, 'Cleanup deadline')
        except BaseException:
            pass
        PREFIX.terminate_owned(owned)


if __name__ == '__main__':
    import os
    LOCKS = RL.LOCKS
    while True:
        if not (LOCKS / 'build.lock').exists() and not (LOCKS / 'pause').exists():
            try:
                fd = os.open(LOCKS / 'bench.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, sys.argv[sys.argv.index('--name') + 1].encode())
                os.close(fd)
                break
            except FileExistsError:
                pass
        time.sleep(10)
    try:
        main()
    finally:
        (LOCKS / 'bench.lock').unlink(missing_ok=True)
