"""Banco SWE di casa, passo 1: sceglie i casi candidati da SWE-bench Verified.

Solo progetti in Python puro installabili su Windows senza compilare, difficolta' "<15 min fix" o "15 min - 1 hour",
patch che tocca al massimo 2 file, al massimo 5 test FAIL_TO_PASS, Python dell'ambiente >= 3.8 (con uv).  Scelta
deterministica (seme fisso), bilanciata per progetto.  Scrive candidati.json con le specifiche ufficiali dell'ambiente
(swebench 3.0.17, MAP_REPO_VERSION_TO_SPECS_PY).

    python seleziona.py [--n 40]
"""
import argparse, json, random, sys
from collections import defaultdict
from pathlib import Path

DATA = Path(r'D:\ds4_work\swe_casa')
VENDOR = Path(__file__).resolve().parent / 'vendor_swebench'   # swebench 3.0.17 (MIT): specs and log parsers
REPOS = {   # quota per progetto (sul totale proporzionale), solo Python puro
    'django/django': 10, 'sympy/sympy': 8, 'sphinx-doc/sphinx': 5, 'pytest-dev/pytest': 6, 'pylint-dev/pylint': 3,
    'psf/requests': 3, 'pydata/xarray': 3, 'mwaskom/seaborn': 1, 'pallets/flask': 1,
}


def specs():
    sys.path.insert(0, str(VENDOR))
    import specs_py
    return specs_py.MAP_REPO_VERSION_TO_SPECS_PY


def files_touched(patch):
    return {l[6:] for l in patch.splitlines() if l.startswith('+++ b/')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=40)
    a = ap.parse_args()
    M = specs()
    rows = [json.loads(l) for l in (DATA / 'swe_bench_verified.jsonl').read_text(encoding='utf-8').splitlines()]
    by = defaultdict(list)
    for r in rows:
        if r['repo'] not in REPOS or r['difficulty'] not in ('<15 min fix', '15 min - 1 hour'):
            continue
        s = M.get(r['repo'], {}).get(r['version'])
        if not s or tuple(int(x) for x in s['python'].split('.')) < (3, 8):
            continue
        f2p = json.loads(r['FAIL_TO_PASS'])
        if len(files_touched(r['patch'])) > 2 or not (1 <= len(f2p) <= 5):
            continue
        by[r['repo']].append(r)
    rng = random.Random(20261006)
    total = sum(REPOS.values())
    out = []
    for repo, q in REPOS.items():
        pool = sorted(by[repo], key=lambda r: r['instance_id'])
        rng.shuffle(pool)
        k = max(1, round(q * a.n / total))
        for r in pool[:k]:
            s = M[r['repo']][r['version']]
            out.append(dict(instance_id=r['instance_id'], repo=r['repo'], version=r['version'], difficulty=r['difficulty'],
                            base_commit=r['base_commit'], environment_setup_commit=r['environment_setup_commit'],
                            python=s['python'], spec=s, files=sorted(files_touched(r['patch'])),
                            fail_to_pass=json.loads(r['FAIL_TO_PASS']), pass_to_pass=json.loads(r['PASS_TO_PASS'])))
        print(f'{repo}: {len(pool)} idonei, presi {min(k, len(pool))}')
    (DATA / 'candidati.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(len(out), 'candidati ->', DATA / 'candidati.json')


if __name__ == '__main__':
    main()
