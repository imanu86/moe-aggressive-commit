"""16/11: chat che continuano a turni, il caso delle PR 5864-5868 (un nuovo turno letto nello slot che tiene la chat).
N conversazioni: un primo turno lungo (--start token nuovi), poi --turns turni da --turn token nuovi ciascuno, risposta di
--max-tokens; ogni turno rimanda la storia intera come un client di chat (risposte senza ragionamento: thinking spento).
  insieme     i turni di tutte le chat partono nello stesso momento (agenti che lavorano insieme)
  sfalsati    ogni chat parte --gap secondi dopo la precedente (agenti che si alternano: uno aspetta un tool)
Misura per turno: primo token, scrittura della risposta, token letti e quelli presi dalla cache; per giro: somma dei
token scritti sul tempo del giro.  Riusa Prompter e stream_request di tools/par_load.py dei sorgenti del motore.

    python turni.py URL --src <sorgenti> --conv 2 --mode insieme,sfalsati --out turni.json
"""
import argparse, json, statistics, sys, threading, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('url')
ap.add_argument('--src', required=True)
ap.add_argument('--conv', type=int, default=2)
ap.add_argument('--start', type=int, default=8000)
ap.add_argument('--turn', type=int, default=600)
ap.add_argument('--turns', type=int, default=4)
ap.add_argument('--max-tokens', type=int, default=300)
ap.add_argument('--mode', default='insieme,sfalsati')
ap.add_argument('--gap', type=float, default=8.0)
ap.add_argument('--out', required=True)
a = ap.parse_args()
sys.path.insert(0, str(Path(a.src) / 'tools'))
import par_load as pl  # noqa: E402

P = pl.Prompter(a.url, '', 'strata', 7, False)


def turno(conv, msgs, max_tokens, t0):
    rec = pl.stream_request(a.url, '', 'strata', '', max_tokens, False, t0, extra={'messages': msgs}, keep_text=True)
    ttft = rec['t_first'] - rec['t_send'] if rec['t_first'] else None
    dec = ((rec['completion_tokens'] or 0) - 1) / (rec['t_last'] - rec['t_first']) if rec['t_first'] and rec['t_last'] and rec['t_last'] > rec['t_first'] else None
    return rec, {'conv': conv, 'ttft': ttft, 'dec': dec, 'out': rec['completion_tokens'], 'prompt': rec['prompt_tokens'],
                 'cached': rec['cached_tokens'], 'err': rec['err'], 'finish': rec['finish'], 't_send': rec['t_send'], 't_end': rec['t_end']}


def giro(modo):
    storie = [[] for _ in range(a.conv)]
    giri = []
    for t in range(a.turns + 1):
        for i in range(a.conv):
            key = f'{modo}/c{i}/t{t}'
            testo = P.make(key, a.start if t == 0 else a.turn,
                           tail='Write a detailed essay about ' if t == 0 else 'Now continue the essay with a new section about ')
            storie[i].append({'role': 'user', 'content': testo})
        ris = [None] * a.conv
        t0 = time.perf_counter()

        def va(i):
            if modo == 'sfalsati':
                time.sleep(i * a.gap)
            rec, r = turno(i, list(storie[i]), a.max_tokens, t0)
            ris[i] = (rec, r)
        th = [threading.Thread(target=va, args=(i,)) for i in range(a.conv)]
        [x.start() for x in th]
        [x.join() for x in th]
        for i in range(a.conv):
            storie[i].append({'role': 'assistant', 'content': ris[i][0].get('text', '')})
        rr = [r for _, r in ris]
        wall = max(r['t_end'] for r in rr) - min(r['t_send'] for r in rr)
        g = {'turno': t, 'wall_s': wall, 'somma_ts': sum(r['out'] or 0 for r in rr) / wall if wall else None, 'req': rr}
        giri.append(g)
        print(f"{modo} turno {t}: giro {wall:.1f}s somma {g['somma_ts']:.1f} t/s | " +
              ' | '.join(f"c{r['conv']} letti {r['prompt']} cache {r['cached']} primo {r['ttft'] or 0:.2f}s scrive {r['dec'] or 0:.1f}"
                         + (f" ERR {r['err']}" if r['err'] else '') for r in rr), flush=True)
    seg = [g for g in giri if g['turno'] > 0]
    med = lambda v: statistics.median(v) if v else None
    sintesi = {'modo': modo, 'primo_token_s': med([r['ttft'] for g in seg for r in g['req'] if r['ttft']]),
               'scrittura_ts': med([r['dec'] for g in seg for r in g['req'] if r['dec']]),
               'somma_giro_ts': med([g['somma_ts'] for g in seg if g['somma_ts']]),
               'errori': sum(1 for g in giri for r in g['req'] if r['err'])}
    print(f"== {modo}: primo token {sintesi['primo_token_s']:.2f}s, scrittura {sintesi['scrittura_ts']:.1f} t/s, "
          f"somma del giro {sintesi['somma_giro_ts']:.1f} t/s, errori {sintesi['errori']}", flush=True)
    return {'sintesi': sintesi, 'giri': giri}


out = {'args': vars(a), 'calib': None, 'modi': {}}
for m in a.mode.split(','):
    out['modi'][m] = giro(m)
out['calib'] = P.calib
Path(a.out).write_text(json.dumps(out, indent=1), encoding='utf-8')
errs = sum(v['sintesi']['errori'] for v in out['modi'].values())
sys.exit(1 if errs else 0)
