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
    ap.add_argument('--add-opt', action='append', default=[], help='--option=value appended (repeatable options)')
    ap.add_argument('--drop-opt', action='append', default=[], help='--option removed from the Daily args')
    ap.add_argument('--daily-exe', action='store_true', help="use the Daily config's own exe")
    ap.add_argument('--prefix-as-system', action='store_true',
                    help='instruction + 131k prefix as the SYSTEM message, then the case: the prefix ends at the first '
                         'turn boundary, the root checkpoint the prefix disk cache saves (not comparable with the '
                         'default user-turn layout)')
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
        if a.prefix_as_system:
            msgs = [{'role': 'system', 'content': man['istruzione_contesto'] + prefissi[pre]},
                    {'role': 'user', 'content': prompts[cid]}]
        else:
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
    for ov in a.add_opt:   # --option=value, or a bare --flag
        k, _, v = ov.partition('='); assert k.startswith('--'); args += [k, v] if _ else [k]
    for ov in a.drop_opt:
        assert ov.startswith('--') and ov in args; args = PREFIX.replace_option(args, ov, None)
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.pop('STRATA_TURNO_LOCK', None)   # run_long_turno: the lab's lock name, not an engine switch
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1')
    for kv in a.env:
        k, v = kv.split('=', 1)
        assert k.startswith('STRATA_') or k in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER', 'CUDA_DEVICE_MAX_CONNECTIONS')   # card order for a split
        env[k] = v
    base_path = L / 'state-baseline.json'
    now = RK.snapshot()
    diff = RK.compare(json.loads(base_path.read_text()), now)
    print(json.dumps({'run': a.name, 'state': now, 'state_diff': diff}, ensure_ascii=False), flush=True)
    assert not now['competing'], now['competing']
    assert now['commit_free_gib'] >= 52, f"Too little commit charge: {now['commit_free_gib']} GiB"
    out.mkdir()
    plan = dict(build=a.build, daily_exe=a.daily_exe, set_opt=a.set_opt, add_opt=a.add_opt, env_probe=a.env, mtp_dir=a.mtp_dir, args=args, tokens=a.tokens, state=now,
                state_diff=diff, prompt_tokens={c: len(i) for c, i in requests},
                executable_sha256=pin['executable_sha256'], daily_sha256=sha(Path(cfg['exe'])),
                config_sha256=sha(CONFIG), env={k: v for k, v in env.items() if k.startswith(('STRATA_', 'CUDA_'))})
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    result = dict(status='starting', requests=[])
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    started, owned = time.monotonic(), {}
    try:
        # 12/10: about one start in eight dies in the prompt path's init, before any work (the log stops after
        # "CUDA1 prompt path borrows", nvcuda64.dll 0xc0000409 at the same offset since 7/10 on every build; see
        # lab/hostgap docs/HOSTGAP.md).  Record the engine's exit code and start it once more on the same arm: nothing
        # has been measured yet, so the arm stays valid; the engine's log is appended, not replaced.
        for attempt in (1, 2):
            try:
                bounded(engine.restart, 300, engine, owned, 'Startup deadline')
                break
            except Exception as e:
                rc = getattr(getattr(engine, 'proc', None), 'returncode', None)
                result.setdefault('start_failures', []).append(dict(attempt=attempt, returncode=rc, error=repr(e)[:500]))
                if attempt == 2 or 'exited before it was ready' not in str(e):
                    raise
                print(f'retry avvio: the engine exited before it was ready (returncode {rc}), starting it again ({a.name})', flush=True)
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


LOCKS = Path(r'D:\ds4_work\strata\lab_locks')


if __name__ == '__main__':
    # 6/10: lab builds (build_lock.py) and benchmark arms take turns.  An arm waits while a build holds build.lock,
    # then holds bench.lock for its whole run; a build waits while bench.lock exists.
    # bench.lock is exclusive (O_EXCL): arms from different queues or agents never overlap either.
    import os
    LOCKS.mkdir(parents=True, exist_ok=True)
    arm_name = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else 'arm'
    # 6/10 sera: while lab_locks\closed exists only the coordinator's deterministic bench (DET-*) may run
    if (LOCKS / 'closed').exists() and not arm_name.startswith('DET-'):
        sys.exit(f'lab closed by the coordinator ({(LOCKS / "closed").read_text().strip()}): arm {arm_name} not run')
    # 19/10 (bf16-turing, run_long_turno.py): the queue already holds bench.lock under the name in STRATA_TURNO_LOCK
    # (turno.py --hold): the arm runs inside that turn and leaves the lock to the queue
    turno = os.environ.get('STRATA_TURNO_LOCK', '')
    held = bool(turno) and (LOCKS / 'bench.lock').exists() and (LOCKS / 'bench.lock').read_text(errors='replace').strip() == turno
    if turno and not held:
        sys.exit(f'STRATA_TURNO_LOCK={turno} but bench.lock is not ours')
    while not held:
        if not (LOCKS / 'build.lock').exists() and not (LOCKS / 'pause').exists():
            try:
                fd = os.open(LOCKS / 'bench.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, (sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else 'arm').encode())
                os.close(fd)
                break
            except FileExistsError:
                pass
        time.sleep(10)
    # 6/10: what else the machine did during the arm (other agents write to disk, use CPU): every 5 s the CPU used
    # outside strata.exe (in cores) and the read/write MB/s per physical disk, kept in <arm>/ambiente.json
    amb, stop = [], threading.Event()

    def sampler():
        last = psutil.disk_io_counters(perdisk=True)
        lt = time.time()
        while not stop.wait(5):
            try:
                now_io, t = psutil.disk_io_counters(perdisk=True), time.time()
                dt = max(t - lt, 1e-3)
                tot = psutil.cpu_percent(interval=None) * psutil.cpu_count() / 100
                engines = [p for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() == 'strata.exe']
                for p in engines:   # 6/10: other agents take ~6 of 16 threads; HIGH priority while lab_locks\prio_high exists
                    try:
                        if not (LOCKS / 'prio_high').exists():
                            break
                        if p.nice() != psutil.HIGH_PRIORITY_CLASS:
                            p.nice(psutil.HIGH_PRIORITY_CLASS)
                    except Exception:
                        pass
                eng = sum(p.cpu_percent(interval=None) for p in engines) / 100
                disks = {d: [round((now_io[d].read_bytes - last[d].read_bytes) / dt / 1e6, 1),
                             round((now_io[d].write_bytes - last[d].write_bytes) / dt / 1e6, 1)]
                         for d in now_io if d in last}
                row = dict(t=round(t), cpu_altri=round(max(tot - eng, 0), 2), cpu_strata=round(eng, 2),
                           disk_mbs_rw=disks)
                # 6/10 notte: every 15 s, who holds dedicated VRAM (MB per process and adapter, > 100 MB): the
                # elastic 3060 cache shrinks when the desktop grows, and this says which process grew
                if len(amb) % 3 == 0:
                    import subprocess
                    ps = ("$c=Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage' -EA SilentlyContinue;"
                          "$c.CounterSamples|?{$_.CookedValue -gt 100MB}|%{$n=$_.InstanceName;"
                          "$i=if($n -match 'pid_(\\d+)'){[int]$matches[1]}else{0};"
                          "$l=if($n -match 'luid_0x[0-9a-f]+_(0x[0-9a-f]+)'){$matches[1]}else{''};"
                          "$p=(Get-Process -Id $i -EA SilentlyContinue).ProcessName;"
                          "'{0}|{1}|{2}' -f $p,$l,[math]::Round($_.CookedValue/1MB)}")
                    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True,
                                         text=True, timeout=20, creationflags=0x08000000).stdout
                    row['vram_mb'] = [ln.strip() for ln in out.splitlines() if ln.strip()]
                    # 7/10: temperature, clocks, power and throttle reasons per card (owner: watch the heat)
                    smi = subprocess.run(['nvidia-smi', '--query-gpu=index,temperature.gpu,clocks.sm,clocks.mem,'
                                          'power.draw,pstate,clocks_throttle_reasons.active',
                                          '--format=csv,noheader,nounits'], capture_output=True, text=True,
                                         timeout=10, creationflags=0x08000000).stdout
                    row['gpu'] = [ln.strip() for ln in smi.splitlines() if ln.strip()]
                amb.append(row)
                last, lt = now_io, t
            except Exception as e:   # sampling never fails the arm
                amb.append(dict(t=round(time.time()), err=str(e)[:80]))

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    try:
        main()
    finally:
        stop.set()
        if not held:
            (LOCKS / 'bench.lock').unlink(missing_ok=True)
        try:
            n = sys.argv[sys.argv.index('--name') + 1]
            if (L / n).is_dir():
                (L / n / 'ambiente.json').write_text(json.dumps(amb) + '\n', encoding='utf-8')
        except Exception:
            pass
