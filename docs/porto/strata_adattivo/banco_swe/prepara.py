"""Banco SWE di casa, passo 2: ambienti dei casi e prova d'oro, su Windows e senza Docker.

Per ogni caso di candidati.json (seleziona.py):
  1. repository: un clone bare parziale per progetto (D:\\ds4_work\\swe_casa\\repos), una worktree staccata al
     base_commit del caso (casi\\<id>\\repo);
  2. ambiente: venv con la versione di Python delle specifiche ufficiali (uv), requisiti letti dal repository
     all'environment_setup_commit, pacchetti fissati, pre_install (le sole sostituzioni `sed -i 's/a/b/' file`),
     installazione del progetto;
  3. prova d'oro: test_patch applicata -> i FAIL_TO_PASS devono fallire; patch vera applicata -> devono passare;
     i PASS_TO_PASS che falliscono anche con la patch vera (piattaforma Windows) sono annotati ed esclusi dal voto;
  4. il repository torna al base_commit pulito.
Scrive casi\\<id>\\caso.json; riprende da dove era rimasto (i casi gia' fatti sono saltati).

    python prepara.py [--only ID ...] [--redo]
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

DATA = Path(r'D:\ds4_work\swe_casa')
CASI, REPOS = DATA / 'casi', DATA / 'repos'
VENDOR = Path(__file__).resolve().parent / 'vendor_swebench'
sys.path.insert(0, str(VENDOR))
import specs_py, log_parsers_py   # noqa: E402

NON_TEST_EXTS = ('.json', '.png', 'csv', '.txt', '.md', '.jpg', '.jpeg', '.pkl', '.yml', '.yaml', '.toml')


def run(cmd, cwd=None, env=None, timeout=1800):
    t0 = time.monotonic()
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=timeout)
        return p.returncode, p.stdout + p.stderr, time.monotonic() - t0
    except subprocess.TimeoutExpired as e:
        return 124, f'TIMEOUT after {timeout}s\n' + (e.stdout or '') if isinstance(e.stdout, str) else 'TIMEOUT', timeout


def git(*args, cwd=None, check=True):
    rc, out, _ = run(['git', *args], cwd=cwd, timeout=3600)
    if check and rc:
        raise RuntimeError(f'git {" ".join(args)}: {out[-2000:]}')
    return out


def uv(*args, timeout=3600):
    rc, out, _ = run([sys.executable, '-m', 'uv', *args], timeout=timeout)
    return rc, out


def mirror(repo):
    m = REPOS / (repo.replace('/', '__') + '.git')
    if not m.exists():
        REPOS.mkdir(parents=True, exist_ok=True)
        git('clone', '--bare', '--filter=blob:none', f'https://github.com/{repo}.git', str(m))
    return m


def requirements(repo, mirror_dir, commit):
    """swebench's get_requirements_by_commit, read from the local mirror (one level of -r includes)."""
    for path in specs_py.MAP_REPO_TO_REQS_PATHS[repo]:
        rc, text, _ = run(['git', '--git-dir', str(mirror_dir), 'show', f'{commit}:{path}'])
        if rc == 0:
            break
    else:
        raise RuntimeError(f'no requirements file for {repo} at {commit}')
    excl = lambda l: any(l.strip().startswith(x) for x in ('-e .', '#', '.[test'))
    base_dir = '/'.join(path.split('/')[:-1])
    extra, orig = [], []
    for line in text.splitlines():
        if line.strip().startswith('-r'):
            inc = (base_dir + '/' if base_dir else '') + line.strip()[2:].strip()
            rc2, t2, _ = run(['git', '--git-dir', str(mirror_dir), 'show', f'{commit}:{inc}'])
            if rc2 == 0:
                extra += [l for l in t2.splitlines() if not excl(l)]
        elif not excl(line):
            orig.append(line)
    return '\n'.join(extra + orig) + '\n'


def sed_edits(repo_dir, commands, log):
    """Only `sed -i 's/A/B/[g]' FILE` (the sphinx pre_install); anything else is recorded and skipped."""
    for c in commands or []:
        m = re.fullmatch(r"sed -i '?s/(.*?)/(.*?)/(g?)'? (\S+)", c.strip())
        if not m:
            log.append(f'pre_install skipped: {c}')
            continue
        f = repo_dir / m[4]
        if not f.exists():
            log.append(f'pre_install: {m[4]} missing')
            continue
        s = f.read_text(encoding='utf-8', errors='replace')
        f.write_text(re.sub(m[1], m[2].replace('\\', '\\\\'), s, count=0 if m[3] else 1), encoding='utf-8')
        log.append(f'pre_install applied: {c}')


def test_directives(inst):
    d = re.findall(r'diff --git a/.* b/(.*)', inst['test_patch'])
    d = [x for x in d if not any(x.endswith(e) for e in NON_TEST_EXTS)]
    if inst['repo'] == 'django/django':
        d = [(x[:-3] if x.endswith('.py') else x) for x in d]
        d = [(x[len('tests/'):] if x.startswith('tests/') else x).replace('/', '.') for x in d]
    return d


def test_command(spec, py):
    """The spec's test_cmd for Windows: (argv prefix, extra env)."""
    cmd, env = spec['test_cmd'], {}
    m = re.match(r"(\w+)='([^']*)' (.*)", cmd)
    if m:
        env[m[1]] = m[2]
        cmd = m[3]
    parts = cmd.split()
    if parts[0] in ('./tests/runtests.py', 'tests/runtests.py'):
        return [py, 'tests/runtests.py', *parts[1:]], env
    if parts[0] == 'bin/test':
        return [py, 'bin/test', *parts[1:]], env
    if parts[0] in ('pytest', 'tox'):
        return [py, '-m', parts[0], *parts[1:]], env
    raise RuntimeError(f'test_cmd not handled: {cmd}')


def run_tests(case_dir, inst, spec, py, name):
    argv, extra = test_command(spec, py)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', **extra)
    env.pop('PYTHONPATH', None)
    rc, out, sec = run([*argv, *test_directives(inst)], cwd=case_dir / 'repo', env=env, timeout=1800)
    (case_dir / f'{name}.log').write_text(out, encoding='utf-8')
    parser = log_parsers_py.MAP_REPO_TO_PARSER_PY[inst['repo']]
    return parser(out, None), rc, sec


def apply(case_dir, patch_text, name):
    p = case_dir / f'{name}.patch'
    p.write_text(patch_text, encoding='utf-8', newline='\n')
    rc, out, _ = run(['git', 'apply', '--whitespace=nowarn', str(p)], cwd=case_dir / 'repo')
    if rc:
        raise RuntimeError(f'{name}.patch does not apply: {out[-1500:]}')


def reset(case_dir, commit):
    git('reset', '-q', '--hard', commit, cwd=case_dir / 'repo')
    git('clean', '-q', '-fd', cwd=case_dir / 'repo')


def prepare(c, inst):
    case_dir = CASI / c['instance_id']
    case_dir.mkdir(parents=True, exist_ok=True)
    log, t0 = [], time.monotonic()
    m = mirror(c['repo'])
    if not (case_dir / 'repo').exists():
        git('--git-dir', str(m), 'worktree', 'add', '--detach', '--force', str(case_dir / 'repo'), c['base_commit'])
    reset(case_dir, c['base_commit'])
    spec = c['spec']
    venv = case_dir / 'venv'
    py = venv / 'Scripts' / 'python.exe'
    if not py.exists():
        rc, out = uv('venv', '--seed', '--python', spec['python'], str(venv))
        if rc:
            raise RuntimeError('uv venv: ' + out[-1500:])
        pkgs = spec.get('packages')
        if pkgs == 'requirements.txt':
            req = case_dir / 'requirements.txt'
            req.write_text(requirements(c['repo'], m, c['environment_setup_commit']), encoding='utf-8')
            rc, out = uv('pip', 'install', '--python', str(py), '-r', str(req))
            if rc:   # one line at a time, the failing ones recorded (Windows-only build failures)
                for line in [l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith('#')]:
                    rc1, out1 = uv('pip', 'install', '--python', str(py), line)
                    if rc1:
                        log.append(f'requirement skipped: {line}')
        elif pkgs and pkgs != 'environment.yml':
            rc, out = uv('pip', 'install', '--python', str(py), *pkgs.split())
            if rc:
                log.append('packages failed: ' + out[-500:])
        if spec.get('pip_packages'):
            rc, out = uv('pip', 'install', '--python', str(py), *spec['pip_packages'])
            if rc:
                log.append('pip_packages failed: ' + out[-800:])
    sed_edits(case_dir / 'repo', spec.get('pre_install'), log)
    inst_cmd = spec.get('install', '')
    if inst_cmd:
        argv = inst_cmd.split()
        if argv[0] == 'python':
            argv[0] = str(py)
        elif argv[0] == 'pip':
            argv = [str(py), '-m', 'pip', *argv[1:]]
        rc, out, _ = run(argv, cwd=case_dir / 'repo', timeout=3600)
        (case_dir / 'install.log').write_text(out, encoding='utf-8')
        if rc:
            log.append('install failed (see install.log)')
    # the pre_install edits are part of the environment: commit-free, kept as a patch to re-apply after resets
    rc, env_diff, _ = run(['git', 'diff'], cwd=case_dir / 'repo')
    (case_dir / 'env.patch').write_text(env_diff, encoding='utf-8', newline='\n')
    # gold check
    apply(case_dir, inst['test_patch'], 'test')
    before, rc_b, sec_b = run_tests(case_dir, inst, spec, py, 'tests-before')
    apply(case_dir, inst['patch'], 'gold')
    after, rc_a, sec_a = run_tests(case_dir, inst, spec, py, 'tests-gold')
    reset(case_dir, c['base_commit'])
    if env_diff.strip():
        apply(case_dir, env_diff, 'env-reapply')
    f2p, p2p = c['fail_to_pass'], c['pass_to_pass']
    f2p_gold = [t for t in f2p if after.get(t) == 'PASSED']
    f2p_before_failing = [t for t in f2p if before.get(t) != 'PASSED']
    p2p_ok = [t for t in p2p if after.get(t) == 'PASSED']
    rec = dict(c, usable=len(f2p_gold) == len(f2p) and len(f2p_before_failing) == len(f2p),
               f2p_pass_with_gold=len(f2p_gold), f2p_fail_before=len(f2p_before_failing),
               p2p_ok=p2p_ok, p2p_excluded=[t for t in p2p if t not in p2p_ok],
               test_seconds=dict(before=round(sec_b, 1), gold=round(sec_a, 1)), notes=log,
               prepare_seconds=round(time.monotonic() - t0, 1))
    (case_dir / 'caso.json').write_text(json.dumps(rec, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--redo', action='store_true')
    a = ap.parse_args()
    cands = json.loads((DATA / 'candidati.json').read_text(encoding='utf-8'))
    insts = {json.loads(l)['instance_id']: json.loads(l) for l in (DATA / 'swe_bench_verified.jsonl').read_text(encoding='utf-8').splitlines()}
    for c in cands:
        if a.only and c['instance_id'] not in a.only:
            continue
        done = CASI / c['instance_id'] / 'caso.json'
        if done.exists() and not a.redo:
            r = json.loads(done.read_text(encoding='utf-8'))
            print(f"{c['instance_id']}: gia' fatto, utilizzabile={r['usable']}", flush=True)
            continue
        try:
            r = prepare(c, insts[c['instance_id']])
            print(f"{c['instance_id']}: utilizzabile={r['usable']} F2P {r['f2p_pass_with_gold']}/{len(c['fail_to_pass'])} "
                  f"P2P esclusi {len(r['p2p_excluded'])} ({r['prepare_seconds']:.0f} s) {'; '.join(r['notes'])[:200]}", flush=True)
        except Exception as e:   # one broken case must not stop the others
            (CASI / c['instance_id']).mkdir(parents=True, exist_ok=True)
            (CASI / c['instance_id'] / 'errore.txt').write_text(repr(e), encoding='utf-8')
            print(f"{c['instance_id']}: ERRORE {str(e)[:300]}", flush=True)
    ok = [json.loads((CASI / c['instance_id'] / 'caso.json').read_text(encoding='utf-8'))
          for c in cands if (CASI / c['instance_id'] / 'caso.json').exists()]
    usable = [r['instance_id'] for r in ok if r['usable']]
    (DATA / 'casi_utilizzabili.json').write_text(json.dumps(usable, indent=1) + '\n', encoding='utf-8')
    print(f'utilizzabili: {len(usable)} su {len(cands)}')


if __name__ == '__main__':
    main()
