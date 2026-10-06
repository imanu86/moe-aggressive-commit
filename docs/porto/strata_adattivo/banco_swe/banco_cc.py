"""Banco SWE via Claude Code (6/10): le chat sono sotto-agenti Haiku di Claude Code, che il gateway (qwen_gateway, 8787)
manda al server Strata della 8100.  Questo script fa le parti fuori dalla chat:

    python banco_cc.py server --name CORSA        tiene acceso il server del Daily (prefisso in D:) finche' esiste
                                                  runs\\CORSA\\server.on (cancellarlo lo ferma); log del motore in runs\\CORSA
    python banco_cc.py prepara --name CORSA ID    repo del caso al base_commit + modifiche d'ambiente, committato in
                                                  locale; scrive il prompt della chat in runs\\CORSA\\ID\\prompt.txt
    python banco_cc.py vota --name CORSA ID       diff del modello, test ufficiali, voto; dal log del gateway le richieste
                                                  Haiku della finestra (LOCALE o no); dal log del motore prefill/decode
"""
import argparse, json, re, sys, time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import agente as A   # noqa: E402
import prepara as P   # noqa: E402

RUNS = P.DATA / 'runs_cc'
GWLOG = Path(r'D:\ds4_work\qwen_gateway_run\log_gateway')

PROMPT = """Lavora su un problema reale di un progetto Python open source (benchmark SWE di casa).

Cartella di lavoro: {repo}
Ambiente Python del progetto (gia' installato): {py}

Regole:
- Lavora SOLO dentro la cartella di lavoro. Non leggere, modificare o cancellare nulla fuori da li'. Niente rete
  (niente pip install, curl, git fetch/push), niente commit.
- Con Bash usa sempre `cd "{repo_posix}" && ...` all'inizio di ogni comando, e per Python usa "{py_posix}".
- Non modificare i test esistenti salvo che il problema lo richieda; puoi creare uno script di prova nella cartella e
  cancellarlo alla fine.
- Modifica il codice sorgente in modo minimo e mirato al problema.
- Quando hai finito rispondi con: FATTO, e una riga che dice quali file hai cambiato.

Il problema (issue originale):
<issue>
{issue}
</issue>
"""


def cmd_server(a):
    out = RUNS / a.name
    out.mkdir(parents=True, exist_ok=True)
    flag = out / 'server.on'
    with A.Server(out) as srv:
        flag.write_text(datetime.now().isoformat(), encoding='utf-8')
        print('server acceso; cancella', flag, 'per fermarlo', flush=True)
        t0 = time.monotonic()
        while flag.exists() and time.monotonic() - t0 < a.hours * 3600:
            time.sleep(5)
    flag.unlink(missing_ok=True)
    print('server spento', flush=True)


def load(i):
    rec = json.loads((P.CASI / i / 'caso.json').read_text(encoding='utf-8'))
    inst = next(json.loads(l) for l in (P.DATA / 'swe_bench_verified.jsonl').read_text(encoding='utf-8').splitlines()
                if json.loads(l)['instance_id'] == i)
    return rec, inst


def cmd_prepara(a):
    rec, inst = load(a.id)
    case_dir = P.CASI / a.id
    A.baseline(case_dir, rec)
    out = RUNS / a.name / a.id
    out.mkdir(parents=True, exist_ok=True)
    repo, py = case_dir / 'repo', case_dir / 'venv' / 'Scripts' / 'python.exe'
    posix = lambda p: '/' + str(p)[0].lower() + str(p)[2:].replace('\\', '/')
    text = PROMPT.format(repo=repo, py=py, repo_posix=posix(repo), py_posix=posix(py), issue=inst['problem_statement'])
    (out / 'prompt.txt').write_text(text, encoding='utf-8')
    elog = RUNS / a.name / 'engine.log'
    n_lines = len(elog.read_text(encoding='utf-8', errors='replace').splitlines()) if elog.exists() else 0
    (out / 'inizio.json').write_text(json.dumps(dict(start=datetime.now().isoformat(), engine_lines=n_lines), indent=1),
                                     encoding='utf-8')
    print(out / 'prompt.txt')


def gateway_window(t0, t1):
    rows = []
    # the log lines carry only the time of day: read only the gateway's current log (a restart opens a new one)
    for f in [max(GWLOG.glob('gateway_*.jsonl'), key=lambda p: p.stat().st_mtime)]:
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                j = json.loads(line)
            except ValueError:
                continue
            m = str(j.get('modello') or '')
            if 'haiku' not in m.lower() or not j.get('ora'):
                continue
            ts = datetime.combine(t0.date(), datetime.strptime(j['ora'], '%H:%M:%S.%f').time())
            if t0 <= ts <= t1:
                rows.append(j)
    return rows


def engine_window(run_dir, n_before):
    log = run_dir / 'engine.log'
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines() if log.exists() else []
    reqs = []
    for s in lines[n_before:]:
        m = re.search(r'serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms .*?(\d+) generated in (\d+) ms', s)
        if m:
            reqs.append(dict(prompt=int(m[1]), reused=int(m[2]), read=int(m[3]), prompt_ms=int(m[4]), gen=int(m[5]),
                             gen_ms=int(m[6])))
    return reqs


def cmd_vota(a):
    rec, inst = load(a.id)
    out = RUNS / a.name / a.id
    start = json.loads((out / 'inizio.json').read_text(encoding='utf-8'))
    t0 = datetime.fromisoformat(start['start'])
    t1 = datetime.now()
    case_dir = P.CASI / a.id
    patch = A.model_patch(case_dir)
    (out / 'patch.diff').write_text(patch, encoding='utf-8', newline='\n')
    vote = A.grade(case_dir, rec, inst, patch)
    gw = gateway_window(t0, t1)
    local = sum(1 for j in gw if j.get('esito') == 'LOCALE')
    stream_tool = [j for j in gw if j.get('stream') and j.get('tool')]
    reqs = engine_window(RUNS / a.name, start.get('engine_lines', 0))
    eng = dict(requests=len(reqs), prompt_tokens=sum(r['prompt'] for r in reqs), reused=sum(r['reused'] for r in reqs),
               read=sum(r['read'] for r in reqs), prefill_s=round(sum(r['prompt_ms'] for r in reqs) / 1000, 1),
               generated=sum(r['gen'] for r in reqs), decode_s=round(sum(r['gen_ms'] for r in reqs) / 1000, 1))
    if reqs:
        eng['reuse_pct'] = round(100 * eng['reused'] / max(eng['prompt_tokens'], 1), 1)
        eng['decode_tps'] = round(eng['generated'] / max(eng['decode_s'], 1e-9), 1)
        eng['first_prompt'] = reqs[0]['prompt']
    (out / 'motore.json').write_text(json.dumps(dict(summary=eng, requests=reqs), indent=1) + '\n', encoding='utf-8')
    res = dict(instance_id=a.id, minutes=round((t1 - t0).total_seconds() / 60, 2), **vote,
               haiku_requests=len(gw), haiku_stream_tool=len(stream_tool), served_locally=local,
               valid=len(stream_tool) > 0 and local == len(stream_tool), engine=eng)
    (out / 'voto.json').write_text(json.dumps(res, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('server'); s.add_argument('--name', required=True); s.add_argument('--hours', type=float, default=2)
    for n in ('prepara', 'vota'):
        p = sub.add_parser(n); p.add_argument('--name', required=True); p.add_argument('id')
    a = ap.parse_args()
    dict(server=cmd_server, prepara=cmd_prepara, vota=cmd_vota)[a.cmd](a)


if __name__ == '__main__':
    main()
