"""Daily 0.1.40-r1, passo 3: le verifiche sull'eseguibile e sul sorgente costruiti (NIENTE server, NIENTE porta 8100).

1. CTest completo della build (95 test registrati).  Due fallimenti sono noti su questa macchina e per cause ambientali:
   ple_parity (modello a percorso relativo) ed expert_multi_test (richiede AVX512).  Qualsiasi altro fallimento (o test
   non eseguito) ferma lo script con codice 2, dopo aver scritto check.json.
2. pool_quant_parity sul GGUF reale.
3. Test python del server (unittest di serve/).  Errori noti, non del fork: test_winjob (tasklist letto come UTF-8 su
   Windows italiano) e test_responses json_schema (502, identico su upstream).  Altri errori fermano con codice 3.
4. Controlli di sola lettura prima dell'installazione: nessun strata.exe in esecuzione e porta 8100 libera (solo
   informativo, non fatale), eseguibile = quello della build, configurazione proposta coerente (file esistenti, ogni opzione
   `--xxx` presente nel sorgente 0.1.40, argomenti = configurazione viva, cambia solo l'exe).
Scrive check.json; i log restano accanto allo script.
"""
import hashlib, json, os, re, socket, subprocess, sys, time
from pathlib import Path

B = Path(__file__).resolve().parent
R = B / 'daily0140_20261006'
S = R / 'source'
D = Path(r'D:\ds4_work\strata\Strata')
CM = Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake')
CUDA = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6')
GGUF = r'C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf'
KNOWN_CTEST = {'ple_parity', 'expert_multi_test'}
# skipped by design on sm_75: both need a CUDA device of sm_80 or newer (exit 77, SKIP_RETURN_CODE)
KNOWN_SKIP = {'prefill_fused_moe_test', 'prefill_fused_iq_test'}
KNOWN_SERVER = {'test_json_schema_text_format', 'test_children_end_with_a_killed_server'}

env = {k: v for k, v in os.environ.items() if not k.upper().startswith('STRATA_')}
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PATH'] = str(CUDA / 'bin') + os.pathsep + env.get('PATH', '')
build = json.loads((R / 'build.json').read_text())
prep = json.loads((R / 'preparation.json').read_text())
out = dict(fork_head=prep['fork_head'], version=prep['version'], steps={})


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save():
    (R / 'check.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def run(cmd, name, cwd=R, timeout=3300):
    print(time.strftime('%H:%M:%S'), name, flush=True)
    t0 = time.monotonic()
    with (R / (name + '.log')).open('w', encoding='utf-8') as f:
        try:
            q = subprocess.run([str(x) for x in cmd], cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            rc = q.returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    out['steps'][name] = dict(rc=rc, seconds=round(time.monotonic() - t0, 1))
    return rc


assert sha(R / 'strata.exe') == build['shipping_exe_sha256'] == sha(R / 'build/strata.exe')

# 1. CTest completo
rc = run([CM / 'CMake/bin/ctest.exe', '--test-dir', R / 'build', '--output-on-failure', '-j', '1', '--timeout', '900'], 'ctest')
log = (R / 'ctest.log').read_text(encoding='utf-8', errors='replace')
m = re.search(r'(\d+)% tests passed, (\d+) tests failed out of (\d+)', log)
failed_part = log.split('The following tests FAILED:')[-1] if 'The following tests FAILED:' in log else ''
notrun_part = log.split('The following tests did not run:')[-1].split('The following tests FAILED:')[0]     if 'The following tests did not run:' in log else ''
failed = re.findall(r'^\s*\d+ - (\S+) \(([^)]*)\)', failed_part, re.M)
skipped = re.findall(r'^\s*\d+ - (\S+) \(([^)]*)\)', notrun_part, re.M)
out['ctest'] = dict(summary=m.group(0) if m else None, total=int(m.group(3)) if m else None,
                    failed=int(m.group(2)) if m else None, failed_tests=[f'{n} ({why})' for n, why in failed],
                    skipped_tests=[f'{n} ({why})' for n, why in skipped], passed=(int(m.group(3)) - len(failed) - len(skipped)) if m else None,
                    known_failures=sorted(KNOWN_CTEST), known_skips=sorted(KNOWN_SKIP), registered=build['ctest_registered'])
unexpected = [n for n, _ in failed if n not in KNOWN_CTEST] + [n + ' (skipped)' for n, _ in skipped if n not in KNOWN_SKIP]
out['ctest']['unexpected_failures'] = unexpected
out['ctest']['known_failures_seen'] = sorted(n for n, _ in failed if n in KNOWN_CTEST)
if m is None or unexpected or int(m.group(3)) != build['ctest_registered']:
    out['status'] = 'ctest-unexpected'
    save()
    print('CTEST UNEXPECTED:', unexpected, m.group(0) if m else 'no summary', flush=True)
    sys.exit(2)

# 2. pool_quant_parity sul GGUF reale
rc = run([R / 'build/pool_quant_parity.exe', GGUF], 'pool-quant-parity')
out['pool_quant_parity'] = dict(rc=rc, last=(R / 'pool-quant-parity.log').read_text(errors='replace').strip().splitlines()[-1:])
if rc != 0:
    out['status'] = 'pool-quant-parity-failed'; save(); sys.exit(2)

# 3. test python del server
code = ("import sys,runpy; sys.path.insert(0,r'D:\\ds4_work\\strata\\Strata\\.venv\\Lib\\site-packages'); "
        "sys.argv=['unittest','discover','-s','serve','-p','test_*.py','-t','.']; runpy.run_module('unittest',run_name='__main__')")
rc = run([sys.executable, '-B', '-u', '-X', 'utf8', '-c', code], 'server-tests', cwd=S, timeout=1500)
tail = (R / 'server-tests.log').read_text(encoding='utf-8', errors='replace').splitlines()
bad = [re.match(r'(?:ERROR|FAIL): (\w+)', s).group(1) for s in tail if re.match(r'(?:ERROR|FAIL): (\w+)', s)]
out['server_tests'] = dict(rc=rc, summary=[s for s in tail if s.startswith(('Ran ', 'OK', 'FAILED'))], failed=bad,
                           known=sorted(KNOWN_SERVER), unexpected=[n for n in bad if n not in KNOWN_SERVER])
# an unexpected server-test failure stops the script (exit 3) unless it is accepted by name on the command line, with the
# reason, e.g.  --accept-server-failure "test_turns=reason"; accepted ones are recorded in check.json and never hidden
accepted = {}
for i, a in enumerate(sys.argv):
    if a == '--accept-server-failure':
        name, _, why = sys.argv[i + 1].partition('=')
        accepted[name] = why
out['server_tests']['accepted_by_operator'] = {n: accepted[n] for n in out['server_tests']['unexpected'] if n in accepted}
out['server_tests']['unexpected'] = [n for n in out['server_tests']['unexpected'] if n not in accepted]
if rc == 'timeout' or out['server_tests']['unexpected']:
    out['status'] = 'server-tests-unexpected'; save()
    print('SERVER TESTS UNEXPECTED:', out['server_tests']['unexpected'], flush=True)
    sys.exit(3)

# 4. controlli di sola lettura prima dell'installazione
pre = {}
procs = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True, errors='replace').stdout
pre['strata_exe_running'] = 'strata.exe' in procs.lower()
with socket.socket() as sock:
    sock.settimeout(1)
    pre['port_8100_listening'] = sock.connect_ex(('127.0.0.1', 8100)) == 0
live = json.loads((D / 'strata-2080ti-sota.json').read_text(encoding='utf-8-sig'))
prop_path = R / 'strata-2080ti-sota.proposed.json'
prop = json.loads(prop_path.read_text(encoding='utf-8-sig'))
assert prop['args'] == live['args'] and not any(a in prop['args'] for a in ('--batch', '--batch-mtp', '--slots'))
assert {k: v for k, v in prop.items() if k not in ('exe', 'args')} == {k: v for k, v in live.items() if k not in ('exe', 'args')}
assert prop['exe'] == str(D / 'build-0140-daily/strata.exe') and not (D / 'build-0140-daily').exists()
src_text = (S / 'src/program/generate.cpp').read_text(encoding='utf-8') + (S / 'serve/server.py').read_text(encoding='utf-8')
flags = sorted({a for a in prop['args'] if a.startswith('--')})
missing_flags = [f for f in flags if f'"{f}"' not in src_text]
cache_file = prop['args'][prop['args'].index('--prompt-cache-file') + 1]   # created by the engine at run time
paths = [a for a in prop['args'] if re.match(r'^[A-Za-z]:[\\/]', a) and a != cache_file]
missing_paths = [a for a in paths if not os.path.exists(a)]
cache_dir = Path(prop['args'][prop['args'].index('--prompt-cache-file') + 1]).parent
pre.update(flags_checked=flags, flags_missing_in_source=missing_flags, paths_checked=len(paths), paths_missing=missing_paths,
           prompt_cache_dir_exists=cache_dir.is_dir(), proposed_config_sha256=sha(prop_path), exe_sha256=sha(R / 'strata.exe'))
out['preinstall'] = pre
if missing_flags or missing_paths or not cache_dir.is_dir():
    out['status'] = 'preinstall-problem'; save(); print(json.dumps(pre, indent=2)); sys.exit(4)
out['status'] = 'ok-with-accepted-server-failures' if out['server_tests']['accepted_by_operator'] else 'ok'
save()
print('CHECK OK', json.dumps({k: out[k] for k in ('ctest', 'pool_quant_parity', 'server_tests')}, indent=2), flush=True)
