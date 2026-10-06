"""Prefix file on disk with a Claude Code-sized system turn (~40K tokens, past the drafter's 32K window).

    python prova_prefisso.py --exe <strata.exe> --source <serve folder> [--name NOME]

Three engine starts on the Daily config (prefix file in its own folder, deleted first):
  1. cold: request A reads the whole system turn and must save the prefix file;
  2. restart: the same request A must load the file (prompt time a fraction) and answer byte for byte the same;
  3. restart: request B (same system turn, another question) loads the file too.
Greedy (temperature 0).  Outputs are data; never execute model text.
"""
import argparse, json, re, time
from pathlib import Path

import agente as A

CASE = Path(r'D:\ds4_work\swe_casa\casi\django__django-14434\repo\django\db')
QUESTIONS = ["In tre righe: cosa fa _create_unique_sql e quali argomenti passa a Columns?",
             "In tre righe: a cosa serve la classe Statement e chi la usa?"]


def system_text(chars=150_000):
    parts, n = [], 0
    for p in sorted(CASE.rglob('*.py')):
        t = p.read_text(encoding='utf-8', errors='replace')
        parts.append(f'# file: {p.relative_to(CASE.parent)}\n{t}')
        n += len(t)
        if n >= chars:
            break
    return 'Sei un revisore di codice. Ecco il codice di riferimento:\n\n' + '\n\n'.join(parts)


def ask(model, system, q):
    t0 = time.monotonic()
    r = A.get('/v1/chat/completions', dict(model=model, temperature=0, max_tokens=160, stream=False,
                                           messages=[dict(role='system', content=system), dict(role='user', content=q)],
                                           chat_template_kwargs=dict(enable_thinking=False)), timeout=1800)
    return r['choices'][0]['message']['content'], round(time.monotonic() - t0, 1)


def lines(log, n0):
    s = log.read_text(encoding='utf-8', errors='replace').splitlines()[n0:]
    return [l for l in s if 'prefix disk cache' in l or re.search(r'serve: prompt \d+', l)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--name', default='prefisso')
    a = ap.parse_args()
    out = A.P.DATA / 'runs_cc' / a.name
    out.mkdir(parents=True, exist_ok=True)
    pfx = A.DATA / 'prefix-swe.bin'
    pfx.unlink(missing_ok=True)
    system = system_text()
    res = []
    for step, q in (('1-freddo', QUESTIONS[0]), ('2-disco-stessa', QUESTIONS[0]), ('3-disco-altra', QUESTIONS[1])):
        d = out / step
        d.mkdir(exist_ok=True)
        with A.Server(d, exe=a.exe, source=a.source) as srv:
            text, secs = ask(srv.model, system, q)
        ev = lines(d / 'engine.log', 0)
        res.append(dict(step=step, seconds=secs, prefix_file_mb=round(pfx.stat().st_size / 2**20, 1) if pfx.exists() else 0,
                        engine=ev, text=text))
        print(json.dumps(res[-1], ensure_ascii=False)[:900], flush=True)
    same = res[0]['text'] == res[1]['text']
    print('STESSA RISPOSTA a freddo e da disco:', same, flush=True)
    (out / 'esito.json').write_text(json.dumps(dict(same_answer=same, steps=res), indent=1, ensure_ascii=False) + '\n',
                                    encoding='utf-8')


if __name__ == '__main__':
    main()
