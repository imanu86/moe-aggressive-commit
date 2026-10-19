"""Misure sullo stadio 0 (19/10): un braccio = un processo del motore Daily 0.1.45 (config copiata, exe del Daily in sola lettura).

Sequenza di un braccio: avvio, riscaldamento (~1K), tre letture fresche da ~5K (prefill corto), L01 a 131K (prefill lungo +
decode 1024), L02 a 131K (prefisso in cache, decode 1024).  Opzioni di laboratorio:
  --extra-mib N   toglie N MiB di VRAM allo stadio 0 (riserva del motore +N e riserva dell'elastica +N)
  --env K=V       STRATA_* di prova per il braccio (ripetibile)
  --routing       --dump-routing (traccia degli esperti instradati, solo analisi)
  --skip-long     niente L01/L02 (solo letture corte)
Si lancia sempre dentro bench_lock.py:  python bench_lock.py DET-ST0-x -- python st0_run.py --name DET-ST0-x ...
Uscite (dati, mai eseguiti): D:\\ds4_work\\strata\\lab_st0\\runs\\<name>\\ engine.log, res.json, pl.trace, ambiente.json.
"""
import argparse, hashlib, json, os, re, subprocess, sys, threading, time
from pathlib import Path

import psutil

H = Path(__file__).resolve().parent
RUNS = Path(r'D:\ds4_work\strata\lab_st0\runs')
D = Path(r'D:\ds4_work\strata\Strata')
SRC = D / 'build-0145-daily' / 'source'
CONFIG = H / 'strata-0145-daily-st0.json'
P0 = Path(r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_p0')
sys.path[:0] = [str(SRC), str(SRC / 'tools'), str(P0)]
sys.dont_write_bytecode = True
from strata_tokenizer import Tokenizer          # noqa: E402
from serve.frontend import ChatTemplate, openai_to_messages  # noqa: E402
from serve import server                         # noqa: E402
import banco_p0 as P0M                           # noqa: E402

assert Path(server.__file__).resolve().is_relative_to(SRC), server.__file__


PS_ENGINES = r'''
$s = Get-Counter '\GPU Engine(*)\Utilization Percentage','\GPU Adapter Memory(*)\Dedicated Usage' -SampleInterval 1 -MaxSamples 2 -EA SilentlyContinue
foreach ($x in $s) { foreach ($c in $x.CounterSamples) {
  $n = $c.InstanceName
  $l = if ($n -match 'luid_0x[0-9a-f]+_(0x[0-9a-f]+)') { $matches[1] } else { '' }
  if ($c.Path -like '*gpu engine*') {
    if ($c.CookedValue -gt 0.5) {
      $i = if ($n -match 'pid_(\d+)') { $matches[1] } else { '0' }
      $e = if ($n -match 'engtype_(\w+)') { $matches[1] } else { '' }
      'E|{0}|{1}|{2}|{3:N1}' -f $i, $l, $e, $c.CookedValue } }
  else { 'M|{0}|{1:N0}' -f $l, ($c.CookedValue / 1MB) } } }
'''



PS_PROCMEM = r'''
$c = Get-Counter '\GPU Process Memory(*)\Dedicated Usage' -EA SilentlyContinue
$c.CounterSamples | Where-Object { $_.CookedValue -gt 50MB } | ForEach-Object {
  $n = $_.InstanceName
  $i = if ($n -match 'pid_(\d+)') { [int]$matches[1] } else { 0 }
  $l = if ($n -match 'luid_0x[0-9a-f]+_(0x[0-9a-f]+)') { $matches[1] } else { '' }
  $p = (Get-Process -Id $i -EA SilentlyContinue).ProcessName
  '{0}|{1}|{2}|{3}' -f $l, $i, $p, [math]::Round($_.CookedValue / 1MB) }
'''


def proc_vram():
    """Memoria dedicata per processo e adattatore (luid) PRIMA dell'avvio del motore: chi occupa la VRAM delle due schede."""
    try:
        o = subprocess.run(['powershell', '-NoProfile', '-Command', PS_PROCMEM], capture_output=True, text=True, timeout=40,
                           creationflags=0x08000000).stdout
        smi = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used', '--format=csv,noheader,nounits'], capture_output=True, text=True,
                             timeout=10, creationflags=0x08000000).stdout
        return dict(per_process=[l.strip() for l in o.splitlines() if l.strip()], smi=[l.strip() for l in smi.splitlines()])
    except Exception as e:
        return dict(err=str(e)[:100])


def jump_state():
    """JumpConnect (Jump Desktop): processi, sessione, CPU cumulata.  Annotato a inizio, durante e fine di ogni braccio."""
    rows = []
    for p in psutil.process_iter(['name', 'pid']):
        if (p.info['name'] or '').lower().startswith('jumpconnect'):
            try:
                ct = p.cpu_times()
                sid = __import__('ctypes').c_ulong()
                __import__('ctypes').windll.kernel32.ProcessIdToSessionId(p.pid, __import__('ctypes').byref(sid))
                rows.append(dict(pid=p.pid, session=sid.value, cpu_s=round(ct.user + ct.system, 2)))
            except psutil.Error:
                pass
    return rows


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def commit_free_gib():
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPageFile / 2**30


def set_opt(args, k, v):
    out, i = [], 0
    while i < len(args):
        if args[i] == k:
            i += 2
            continue
        out.append(args[i]); i += 1
    return out + ([k, str(v)] if v is not None else [])


def get_opt(args, k):
    return args[args.index(k) + 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--extra-mib', type=int, default=0)
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--routing', action='store_true')
    ap.add_argument('--skip-long', action='store_true')
    ap.add_argument('--short-n', type=int, default=3)
    ap.add_argument('--short-tokens', type=int, default=5000)
    ap.add_argument('--tokens', type=int, default=1024)
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--set-opt', action='append', default=[], help='--opzione=valore sostituita negli argomenti')
    ap.add_argument('--drop-opt', action='append', default=[], help='--opzione (con valore) tolta dagli argomenti del Daily')
    ap.add_argument('--decodes', type=int, default=3, help='decode a 131K: L02 e poi L03, L04 (stesso prefisso in cache)')
    ap.add_argument('--gpu-engine', action='store_true', help='ogni ~10 s uso GPU per processo/adattatore (Get-Counter)')
    a = ap.parse_args()
    out = RUNS / a.name
    assert not out.exists(), out
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    exe = Path(cfg['exe'])
    pin = json.loads((exe.parent / 'build.json').read_text())
    assert pin['status'] == 'completed' and sha(exe) == pin['executable_sha256'], 'exe cambiato'

    tdir = Path(cfg['tokenizer'])
    vocab = json.loads((tdir / 'vocab.json').read_text(encoding='utf-8'))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = Tokenizer(toks, (tdir / 'merges.txt').read_text(encoding='utf-8').splitlines(),
                    json.loads((tdir / 'token_type.json').read_text(encoding='utf-8')))
    template = ChatTemplate(tdir / 'chat_template.jinja')

    def enc(msgs):
        m, tools, kw = openai_to_messages({'messages': msgs, 'temperature': 0})
        return tok.encode(template.render(m, tools, **kw), parse_special=True)

    man, casi, prefissi, prompts = P0M.carica_fixture()
    instr = man['istruzione_contesto']
    reqs = []   # (label, ids, max_tokens)

    # testo per le letture corte: fette disgiunte del prefisso a 32K (nessun riuso fra le fette)
    base = prefissi['ctx32k']
    cpt = len(base) / max(len(tok.encode(base)), 1)   # caratteri per token

    def slice_tokens(start_chars, want):
        n = int(want * cpt)
        s = base[start_chars:start_chars + n]
        for _ in range(5):
            got = len(enc([{'role': 'user', 'content': instr + s}]))
            if abs(got - want) <= want * 0.02:
                break
            n = max(200, int(n * want / got))
            s = base[start_chars:start_chars + n]
        return s, start_chars + n

    pos = 0
    s, pos = slice_tokens(pos, 1000)
    reqs.append(('warm1k', enc([{'role': 'user', 'content': instr + s}]), 4))
    for k in range(a.short_n):
        s, pos = slice_tokens(pos, a.short_tokens)
        reqs.append((f'short{k + 1}', enc([{'role': 'user', 'content': instr + s}]), 16))
    if not a.skip_long:
        for cid in ('L01', 'L02', 'L03', 'L04')[:1 + a.decodes]:
            pre = casi['L01']['prefisso_per_contesto']['ctx131k']
            msgs = [{'role': 'user', 'content': instr + prefissi[pre]}, {'role': 'assistant', 'content': 'pronto'},
                    {'role': 'user', 'content': prompts[cid]}]
            reqs.append((cid, enc(msgs), a.tokens))

    args = list(server.engine_args(cfg))
    args = set_opt(args, '--prompt-cache-file', None)
    for d in a.drop_opt:
        assert d in args, d
        i = args.index(d)
        n = 2 if i + 1 < len(args) and not args[i + 1].startswith('--') else 1
        del args[i:i + n]
    for ov in a.set_opt:
        k, v = ov.split('=', 1)
        assert k.startswith('--')
        args = set_opt(args, k, v)
    if a.extra_mib:
        r = int(get_opt(args, '--vram-reserve-mib'))
        args = set_opt(args, '--vram-reserve-mib', r + a.extra_mib)
        if '--batch' not in args:
            args = set_opt(args, '--elastic-reserve-mib', 500 + a.extra_mib)
    if a.routing:
        args += ['--dump-routing', str(out / 'routing.bin')]
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('STRATA_', 'CUDA_', 'HIP_'))}
    for k, v in (cfg.get('env') or {}).items():
        env[str(k)] = str(v)
    libs = [x for x in (cfg.get('lib_dirs') or []) if Path(x).is_dir()]
    if libs:
        env['PATH'] = os.pathsep.join(libs + [env.get('PATH', '')])
    env.update(STRATA_NO_LARGEPAGES='1', STRATA_ARENA_PIN_GIB='8', STRATA_DECODE_TIMING='1',
               STRATA_PIPELINE_TRACE=str(out / 'pl.trace'), STRATA_SPLIT_TIMING='1')
    for kv in a.env:
        k, v = kv.split('=', 1)
        assert k.startswith('STRATA_'), k
        env[k] = v
    assert 'STRATA_IQ_MT_MIN' not in env

    if a.dry:
        print(json.dumps({'prompt_tokens': {l: len(i) for l, i, _ in reqs}, 'args': args, 'exe': str(exe)}, indent=1)); return
    cf = commit_free_gib()
    t0 = time.time()
    while cf < 52 and time.time() - t0 < 240:
        time.sleep(5); cf = commit_free_gib()
    assert cf >= 52, f'commit libero {cf:.1f} GiB'
    out.mkdir(parents=True)
    competing = [p.info['name'] for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in
                 ('strata.exe', 'llama-server.exe', 'nvcc.exe', 'cl.exe')]
    assert not competing, competing
    snap0 = dict(commit_free_gib=round(cf, 1), avail_ram_gib=round(psutil.virtual_memory().available / 2**30, 1),
                 vram_before=proc_vram(), jump=jump_state(), cgcontrol=any((p.info['name'] or '').lower() == 'cgcontrol.exe' for p in psutil.process_iter(['name'])))
    plan = dict(name=a.name, extra_mib=a.extra_mib, env_probe=a.env, routing=a.routing, args=args, snap0=snap0,
                exe_sha=sha(exe), config_sha=sha(CONFIG), prompt_tokens={l: len(i) for l, i, _ in reqs},
                env={k: v for k, v in env.items() if k.startswith(('STRATA_', 'CUDA_'))})
    (out / 'plan.json').write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'run': a.name, 'extra_mib': a.extra_mib, 'snap0': snap0, 'prompt_tokens': plan['prompt_tokens']}), flush=True)

    # campionatore d'ambiente: ogni 5 s CPU fuori da strata, GPU (memoria, uso, clock, potenza, temperatura)
    amb, stop = [], threading.Event()

    def sampler():
        while not stop.wait(5):
            try:
                tot = psutil.cpu_percent(interval=None) * psutil.cpu_count() / 100
                eng = sum(p.cpu_percent(interval=None) for p in psutil.process_iter(['name'])
                          if (p.info['name'] or '').lower() == 'strata.exe') / 100
                smi = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu,clocks.sm,power.draw,'
                                      'temperature.gpu,clocks_throttle_reasons.active', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=10, creationflags=0x08000000).stdout
                row = dict(t=round(time.time()), cpu_altri=round(max(tot - eng, 0), 2), cpu_strata=round(eng, 2),
                           jump_cpu_s=round(sum(j['cpu_s'] for j in jump_state()), 2),
                           gpu=[l.strip() for l in smi.splitlines() if l.strip()])
                if a.gpu_engine and len(amb) % 2 == 0:
                    ps = PS_ENGINES
                    o = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True,
                                       timeout=30, creationflags=0x08000000).stdout
                    rows_e = []
                    for ln in o.splitlines():
                        ln = ln.strip()
                        if ln.startswith('E|'):
                            f = ln.split('|')
                            try:
                                f[1] = psutil.Process(int(f[1])).name() + ':' + f[1]
                            except Exception:
                                pass
                            ln = '|'.join(f)
                        if ln:
                            rows_e.append(ln)
                    row['engines'] = rows_e
                amb.append(row)
            except Exception as e:
                amb.append(dict(t=round(time.time()), err=str(e)[:80]))
    psutil.cpu_percent(interval=None)
    th = threading.Thread(target=sampler, daemon=True); th.start()

    logp = out / 'engine.log'
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(logp), env=env, lazy=True)
    result = dict(name=a.name, extra_mib=a.extra_mib, status='starting', requests=[])
    trace_p = out / 'pl.trace'

    def log_size():
        return logp.stat().st_size if logp.exists() else 0

    def run_with_deadline(fn, secs, label):
        box = {}

        def w():
            try:
                box['v'] = fn()
            except BaseException as e:   # noqa
                box['e'] = e
        t = threading.Thread(target=w, daemon=True); t.start()
        end = time.monotonic() + secs
        while t.is_alive():
            if time.monotonic() > end:
                raise TimeoutError(label)
            t.join(0.5)
        if 'e' in box:
            raise box['e']
        return box.get('v')

    try:
        ts = time.monotonic()
        for attempt in (1, 2):
            try:
                run_with_deadline(engine.restart, 420, 'avvio')
                break
            except Exception as e:
                rc = getattr(getattr(engine, 'proc', None), 'returncode', None)
                result.setdefault('start_failures', []).append(dict(attempt=attempt, rc=rc, err=repr(e)[:300]))
                if attempt == 2 or 'exited before it was ready' not in str(e):
                    raise
        result['startup_s'] = round(time.monotonic() - ts, 1)
        result['jump_start'] = snap0['jump']
        # righe di avvio (slot, riserve, prestito del percorso del prompt)
        startup = logp.read_text(errors='replace')
        result['startup_lines'] = [l for l in startup.splitlines() if any(k in l for k in (
            'expert cache', 'elastic', 'prompt path borrows', 'VRAM free with everything', 'ram core:   dev', 'free once the slots',
            'layer split: CUDA', 'reserve'))][:40]
        for label, ids, mt in reqs:
            l0 = log_size(); t0 = trace_p.stat().st_size if trace_p.exists() else 0
            emitted, first, box = [], [], {}
            tt = time.monotonic(); tw0 = time.time()

            def gen():
                for tk in engine.generate(ids, mt, dict(temperature=0, seed=73), threading.Event()):
                    if tk is not None:
                        if not emitted:
                            first.append(time.monotonic())
                        emitted.append(int(tk))
                box['last'] = dict(engine.last)
            run_with_deadline(gen, 1500, label)
            wall = time.monotonic() - tt
            time.sleep(1.5)   # le righe di fine richiesta (elastica, hit rate) arrivano dopo l'ultimo token
            with open(logp, 'rb') as f:
                f.seek(l0); chunk = f.read().decode('utf-8', 'replace')
            keep = [l for l in chunk.splitlines() if 'capturing the' not in l and 'captured the' not in l]
            (out / f'{label}.log').write_text('\n'.join(keep) + '\n', encoding='utf-8')
            if trace_p.exists() and trace_p.stat().st_size > t0:
                with open(trace_p, 'rb') as f:
                    f.seek(t0); (out / f'{label}.trace').write_bytes(f.read())
            result['requests'].append(dict(label=label, t0=round(tw0, 1), t1=round(time.time(), 1), prompt_tokens=len(ids), generated=len(emitted), wall_s=round(wall, 2),
                                           ttft_s=round(first[0] - tt, 2) if first else None, last=box.get('last')))
            m = re.search(r'strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms \(([\d.]+) tok/s\), '
                          r'(\d+) generated in (\d+) ms \(([\d.]+) tok/s\)', chunk)
            print(json.dumps({'req': label, 'prompt': m.groups() if m else None, 'wall_s': round(wall, 1)}), flush=True)
        result['status'] = 'completed'
    except BaseException as e:   # noqa
        result.update(status='failed', error=repr(e)[:400])
        raise
    finally:
        stop.set()
        try:
            run_with_deadline(engine.close, 40, 'chiusura')
        except BaseException as e:   # noqa
            result['close_error'] = repr(e)[:200]
        # processi rimasti del braccio: nessuno deve sopravvivere
        for p in psutil.process_iter(['name', 'pid']):
            if (p.info['name'] or '').lower() == 'strata.exe':
                try:
                    if engine.proc is not None and p.info['pid'] == engine.proc.pid:
                        p.kill(); result['killed_engine'] = True
                except psutil.Error:
                    pass
        result['jump_end'] = jump_state()
        (out / 'res.json').write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
        (out / 'ambiente.json').write_text(json.dumps(amb) + '\n', encoding='utf-8')
        print('res', result['status'], flush=True)


if __name__ == '__main__':
    main()
