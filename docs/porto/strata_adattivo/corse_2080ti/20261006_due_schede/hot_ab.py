"""A/B of Fable's hot levers inside ONE engine process (7/10): requests alternate without and with `lab=...`.

    python hot_ab.py --name DET-hot-1 --build build-fable-93be6e0 --lever MTP_PRIORITY:-1 --lever EARLY_L1:1 ...
        [--rounds 3] [--add-opt=--pipeline-windows=2 ...] [--env KEY=VALUE ...]

Same messages, forced ids (STRATA_FORCE_IDS) and forced windows (STRATA_FORCE_WINDOWS, remapped per request) as the
deterministic bench det_force.sh.  For each lever, `rounds` rounds; a round is L01 then L02, each case once per arm in
the order A B (even rounds) or B A (odd rounds).  Every measured request is preceded by a short warm request with the
same lab key on the same prompt (graph recapture and the arm's first window stay out of the measure).
Verdict per lever: the gain of B over the A of the same round and case; it passes when all pairs have the same sign and
the mean is > 1%.  Results are appended to <name>/hot_ab.jsonl as they come.
"""
import argparse, importlib, json, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
K = HERE.parent / '20261004_routed_keep'
sys.path.insert(0, str(K))
import run_long as RL   # noqa: E402  (RK, P0, PREFIX, CONFIG, bounded, sha, LOCKS)

RK, P0 = RL.RK, RL.P0
PREFIX, CONFIG, bounded, sha = RL.PREFIX, RL.CONFIG, RL.bounded, RL.sha
FORCE = HERE / 'force_ids'
FABLE_SERVE = Path(r'C:\Users\imanu\source\repos\Strata-wt\fable')
WARM_TOKENS = 48


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--build', required=True)
    ap.add_argument('--lever', action='append', required=True, help='NAME:VALUE[,NAME:VALUE] for the B arm')
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--tokens', type=int, default=1024)
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--add-opt', action='append', default=[])
    ap.add_argument('--switch', action='store_true', help='no warm requests, cases alternate (see the plan)')
    ap.add_argument('--ctx2', action='store_true',
                    help='with --switch: L02 on ANOTHER 131k context (aghi131k), not forced (greedy, the same work in '
                         'both arms when the lever keeps the bits); the two contexts park in the conversation cache')
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
    # the fork's server.py (it turns sampling["strata_lab"] into the request's lab= key)
    for m in [m for m in sys.modules if m == 'serve' or m.startswith('serve.')]:
        del sys.modules[m]
    sys.path.insert(0, str(FABLE_SERVE))
    server = importlib.import_module('serve.server')
    assert 'strata_lab' in Path(server.__file__).read_text(encoding='utf-8'), server.__file__
    man, casi, prefissi, prompts = P0.carica_fixture()
    prompt = {}
    for cid in ('L01', 'L02'):
        pre = 'aghi131k' if (a.ctx2 and cid == 'L02') else casi[cid]['prefisso_per_contesto']['ctx131k']
        msgs = [{'role': 'user', 'content': man['istruzione_contesto'] + prefissi[pre]},
                {'role': 'assistant', 'content': 'pronto'}, {'role': 'user', 'content': prompts[cid]}]
        m, tools, kw = convert({'messages': msgs, 'temperature': 0})
        prompt[cid] = tok.encode(template.render(m, tools, **kw), parse_special=True)
    # the request plan: (lever index, round, case, arm, warm?)
    plan = []
    if a.switch:
        # --switch (7/10, the prefill seed): no warm requests, every measured request follows the OTHER case, so each
        # one starts with the expert cache tuned to the other text; per case A B B A in each round (balanced), after
        # one unmeasured L02 that loads the 131k prefix
        if a.ctx2:
            plan.append((0, -1, 'L01', 'A', True))
        plan.append((0, -1, 'L02', 'A', True))
        for li in range(len(a.lever)):
            for r in range(a.rounds):
                for arm in ('A', 'B', 'B', 'A'):
                    plan += [(li, r, 'L01', arm, False), (li, r, 'L02', arm, False)]
    for li in range(len(a.lever) if not a.switch else 0):
        for r in range(a.rounds):
            for cid in ('L01', 'L02'):
                for arm in (('A', 'B') if r % 2 == 0 else ('B', 'A')):
                    plan += [(li, r, cid, arm, True), (li, r, cid, arm, False)]
    # forced ids: the k-th request takes its case's list; forced windows: the reference's request 0 (L01) / 1 (L02)
    # renumbered to k
    ref = {'L01': [], 'L02': []}
    for line in (FORCE / 'ref_def1_trace.txt').read_text().splitlines():
        p = line.split()
        if len(p) >= 5 and p[0] == 'W' and p[1] in ('0', '1'):
            ref['L01' if p[1] == '0' else 'L02'].append(p[2:])
    out.mkdir()
    win = out / 'force_windows.txt'
    with win.open('w') as f:
        for k, (_, _, cid, _, _) in enumerate(plan):
            for p in ref[cid]:
                f.write('W %d %s\n' % (k, ' '.join(p)))
    ids_env = ';'.join(str(FORCE / f'force_{cid}.txt') for (_, _, cid, _, _) in plan)
    args = PREFIX.replace_option(list(server.engine_args(cfg)), '--prompt-cache-file', None)
    for ov in a.add_opt:
        k, _, v = ov.partition('='); assert k.startswith('--'); args += [k, v] if _ else [k]
    args += ['--layer-split', '16', '--trim-stage-weights']
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1',
               CUDA_VISIBLE_DEVICES='1,0', STRATA_POOL_SPIN_US='100')
    if not a.ctx2:
        env.update(STRATA_FORCE_IDS=ids_env, STRATA_FORCE_WINDOWS=str(win),
                   STRATA_FORCE_TRACE=str(out / 'force_trace.txt'))
    for kv in a.env:
        k, v = kv.split('=', 1)
        assert k.startswith('STRATA_') or k.startswith('CUDA_')
        env[k] = v
    for _ in range(60):   # another agent's nvcc or engine: wait, up to 10 min
        now = RK.snapshot()
        if not now['competing']:
            break
        print('attendo:', now['competing'], flush=True)
        time.sleep(10)
    assert not now['competing'], now['competing']
    (out / 'plan.json').write_text(json.dumps(dict(build=a.build, levers=a.lever, rounds=a.rounds, args=args,
                                                   executable_sha256=pin['executable_sha256'], state=now,
                                                   env={k: v for k, v in env.items()
                                                        if k.startswith(('STRATA_', 'CUDA_')) and k != 'STRATA_FORCE_IDS'},
                                                   requests=len(plan)), indent=2) + '\n', encoding='utf-8')
    jl = (out / 'hot_ab.jsonl').open('a', encoding='utf-8')
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    owned = {}
    res = {}
    try:
        bounded(engine.restart, 300, engine, owned, 'Startup deadline')
        for k, (li, r, cid, arm, warm) in enumerate(plan):
            sampling = dict(temperature=0, seed=73)
            if arm == 'B':
                sampling['strata_lab'] = a.lever[li]
            emitted = []

            def gen():
                for token in engine.generate(prompt[cid], WARM_TOKENS if warm else a.tokens, sampling, threading.Event()):
                    if token is not None:
                        emitted.append(int(token))
            bounded(gen, 900, engine, owned, f'request {k} deadline')
            last = dict(engine.last)
            tps = last['generated'] / last['decode_ms'] * 1000 if last.get('decode_ms') else None
            row = dict(k=k, lever=a.lever[li], round=r, case=cid, arm=arm, warm=warm, tps=tps,
                       generated=last.get('generated'), reused=last.get('reused'), t=round(time.time()))
            jl.write(json.dumps(row) + '\n'); jl.flush()
            if not warm:
                res.setdefault(li, {}).setdefault((r, cid), {})[arm] = tps
                print(f"{a.lever[li]:24s} r{r} {cid} {arm} {tps:6.1f} t/s", flush=True)
        print('VERDETTO', flush=True)
        for li, pairs in res.items():
            g = [100 * (v['B'] / v['A'] - 1) for v in pairs.values() if v.get('A') and v.get('B')]
            g01 = [100 * (v['B'] / v['A'] - 1) for (r, c), v in pairs.items() if c == 'L01' and v.get('A') and v.get('B')]
            g02 = [100 * (v['B'] / v['A'] - 1) for (r, c), v in pairs.items() if c == 'L02' and v.get('A') and v.get('B')]
            mean = sum(g) / len(g) if g else 0
            ok = g and (all(x > 0 for x in g) or all(x < 0 for x in g)) and abs(mean) > 1
            print(f"{a.lever[li]:24s} L01 {['%+.1f' % x for x in g01]} L02 {['%+.1f' % x for x in g02]} "
                  f"media {mean:+.1f}% -> {'PASSA' if ok and mean > 0 else 'PEGGIORA' if ok else 'nel rumore'}",
                  flush=True)
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
