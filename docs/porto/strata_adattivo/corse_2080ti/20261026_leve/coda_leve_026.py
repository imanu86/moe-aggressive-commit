"""Coda unica di misure sulla Daily 0.2.6: ogni leva in terna base-leva-base (26/10/2026).

NON parte da sola e NON e' stata eseguita: senza --vai stampa soltanto l'ordine, le durate e i comandi (nessuna GPU, nessun processo).

  python coda_leve_026.py                  # prova a secco: ordine, stima, controlli sui file
  python coda_leve_026.py --vai            # esegue tutto in ordine (usa la GPU: PC libero, nessun strata.exe)
  python coda_leve_026.py --vai --fino 4   # solo i primi 4 passi
  python coda_leve_026.py --vai --riprendi # salta i passi con fatto/<tag>.ok (dopo uno stop)
  python coda_leve_026.py --analisi        # tabella base / leva / base dai risultati, senza GPU

Rifiuta di partire (e si ferma fra un passo e l'altro) se: gira un strata.exe (anche quello dell'owner: i runner lo
ucciderebbero a fine corsa), esiste lab_locks\\pause, esiste lab_locks\\bench.lock o lab_locks\\build.lock.
La prima richiesta di ogni avvio e' scartata: nei banchi e' il "warmup" da 19 token (piu' la prima da 4K, ancora fredda:
--tieni-fredda la rimette); nel replay sono le letture di riscaldamento a max_tokens 1 prima del cronometro.
Terne concatenate: se la leva successiva ha la stessa base, il braccio base in mezzo e' unico (base-L1-base-L2-base):
ogni leva ha comunque la base subito prima e subito dopo.  Una terna con le due basi a piu' del 3% (banchi) o 5% (replay)
una dall'altra e' segnalata instabile e non vale.
"""
import argparse, json, os, statistics as st, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
OUT = HERE / 'corse'
DAILY_BUILD = r'D:\ds4_work\strata\Strata\build-026-daily'
LEVE_BUILD = (HERE / 'leve_build.txt').read_text(encoding='utf-8').strip() if (HERE / 'leve_build.txt').exists() else r'<build-leve026: lanciare make_configs.py>'
CAMP = CORSE / '20261025_bisezione'
REPLAY = CORSE / '20261019_replay'
G = '--conversation-cache-mib 18432 --conversation-cache-slots 16'
R4 = '--vram-reserve-mib 1905 --vram-reserve-later-mib 700'
B4G2 = f'--batch 4 --batch-groups 2 {G} {R4}'
T0 = {'temperature': 0}

# ---- bracci -------------------------------------------------------------------------------------------------------
# camp: banco della comunita' corto/lungo (community_bench_camp.py); replay: replay_trace.py, finestra 3600-4800 s, sessioni A,B,C
ARMS = {
    'bf-base': dict(kind='camp', cfg='cfg-daily-base.json', build=DAILY_BUILD, sampling=T0, targets='4096,32768,128000', runs=3, min=11,
                    nota='Daily 0.2.6, T=0, 4K/32K/128K x3'),
    'bf-leva': dict(kind='camp', cfg='cfg-daily-bf16tc.json', build=DAILY_BUILD, sampling=T0, targets='4096,32768,128000', runs=3, min=11,
                    nota='Daily + STRATA_BF16_TC=1 (hc16 vince sui suoi punti: cambia router, indexer, strato bozza)'),
    'pw-base': dict(kind='camp', cfg='cfg-leve-r3.json', build=LEVE_BUILD, sampling=T0, targets='4096,32768', runs=4, min=7,
                    nota='chat singola con --batch 4 --batch-groups 2 (R3), build leve026 con le leve spente'),
    'pw-leva': dict(kind='camp', cfg='cfg-leve-r3-pw.json', build=LEVE_BUILD, sampling=T0, targets='4096,32768', runs=4, min=7,
                    nota='R3 + STRATA_PW_WITH_BATCH=1'),
    'R0': dict(kind='replay', exe=f'{DAILY_BUILD}\\strata.exe', extra='', env='', min=20, nota='Daily 0.2.6 senza batch'),
    'R1': dict(kind='replay', exe=f'{DAILY_BUILD}\\strata.exe', extra=f'--batch 4 {G} {R4}', env='', min=20,
               nota='--batch 4 con i default 0.2.6 (gruppo seriale)'),
    'R2': dict(kind='replay', exe=f'{DAILY_BUILD}\\strata.exe', extra=B4G2, env='', min=20, nota='--batch 4 --batch-groups 2'),
    'R3': dict(kind='replay', exe=f'{DAILY_BUILD}\\strata.exe', extra=B4G2, env='STRATA_PIPED_CONCURRENT=1', min=20,
               nota='R2 + STRATA_PIPED_CONCURRENT=1'),
}
LEVE_EXE = f'{LEVE_BUILD}\\strata.exe'
ARMS['R3L'] = dict(kind='replay', exe=LEVE_EXE, extra=B4G2, env='STRATA_PIPED_CONCURRENT=1', min=20, nota='R3 sulla build leve026, leve spente')
for k, extra, env, nota in [
        ('L1', '--batch-mtp', 'STRATA_PIPED_MTP=1', '#4121: bozze MTP nei gruppi in pipeline (2 slot per gruppo: non provato upstream)'),
        ('L2', '', 'STRATA_PW_WITH_BATCH=1', '#3095: la richiesta sola tiene --pipeline-windows accanto a --batch'),
        ('L3', '', 'STRATA_PIPE_ADAPT_EVERY=128', '#4010: i gruppi in pipeline adattano il livello VRAM ogni 128 finestre'),
        ('L4', '', 'STRATA_PIPELINE_ACTIVE_ROWS=1 STRATA_SLOT_CACHE_AFFINITY=1 STRATA_BRANCH_CHECKPOINT=1024 STRATA_SLOT_CHECKPOINTS=2',
         '#2527/#2528/#2843: righe attive, placement per cache, checkpoint di ramo (la traccia non ha rami: controllo di non-regressione)')]:
    ARMS[k] = dict(kind='replay', exe=LEVE_EXE, extra=f'{B4G2} {extra}'.strip(), env=f'STRATA_PIPED_CONCURRENT=1 {env}', min=20, nota=nota)

# ---- terne, dalla piu' promettente (base, leva, perche') ---------------------------------------------------------------
TERNE = [
    ('a1', 'blocco', 'presence_penalty 0 contro 1,5 a T=0,7 (camp_bisezione.py --solo nopp, Daily 0.2.6)',
     'costo noto: con la penalita' + "'" + ' la pipeline a due finestre si spegne (-12% di decode a T=0,7); 3 avvii da 6 min'),
    ('b1', ('R3L', 'L1'), '#4121 STRATA_PIPED_MTP=1 sul replay', 'in upstream +20-30% di decode aggregato con 4 stream; e il lavoro vero a 3 agenti'),
    ('b2', ('R0', 'R3'), 'scala del batch: Daily senza batch contro R3', 'dice quanto vale il batch di per se'),
    ('b3', ('R0', 'R2'), 'scala del batch: R2 (senza PIPED_CONCURRENT)', 'isola PIPED_CONCURRENT (R3 contro R2)'),
    ('b4', ('R0', 'R1'), 'scala del batch: R1 (gruppo seriale, default 0.2.6)', 'riferimento: come si comporta 0.2.6 senza toccare nulla'),
    ('a2', ('bf-base', 'bf-leva'), 'STRATA_BF16_TC=1 a T=0, lettura prompt a 128K', 'hc16 gia in uso: atteso piccolo, ma 128K e il punto dolente'),
    ('a3', ('pw-base', 'pw-leva'), 'STRATA_PW_WITH_BATCH=1, chat singola con batch acceso (extra)', 'e il suo caso vero: +12-16% in upstream solo da soli'),
    ('b5', ('R3L', 'L2'), '#3095 STRATA_PW_WITH_BATCH=1 sul replay', 'solo quando un agente resta solo'),
    ('b6', ('R3L', 'L3'), '#4010 STRATA_PIPE_ADAPT_EVERY=128 sul replay', 'gli esperti si assestano dopo l avvio: serve su carico lungo'),
    ('b7', ('R3L', 'L4'), '#2527/#2528/#2843 checkpoint di ramo sul replay', 'senza rami nella traccia non c e guadagno atteso: controllo di regressione'),
]


def passi():
    """Lista piatta dei passi: terne concatenate con la base unica fra due leve vicine."""
    out, ult = [], None
    for tid, arms, titolo, perche in TERNE:
        if arms == 'blocco':
            out.append(dict(tid=tid, arm='a1-pp', ruolo='blocco', min=18, titolo=titolo))
            ult = None
            continue
        base, leva = arms
        if ult != base:
            out.append(dict(tid=tid, arm=base, ruolo='base', min=ARMS[base]['min'], titolo=titolo))
        out.append(dict(tid=tid, arm=leva, ruolo='leva', min=ARMS[leva]['min'], titolo=titolo))
        out.append(dict(tid=tid, arm=base, ruolo='base', min=ARMS[base]['min'], titolo=titolo))
        ult = base
    for i, p in enumerate(out, 1):
        p['n'] = i
        p['tag'] = f'{i:02d}_{p["arm"]}'
    return out


def occupato():
    p = []
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq strata.exe', '/NH'], capture_output=True, text=True, errors='replace')
    if 'strata.exe' in r.stdout.lower():
        p.append('un strata.exe e in vita (il runner lo ucciderebbe a fine corsa)')
    for n in ('pause', 'bench.lock', 'build.lock'):
        if (LOCKS / n).exists():
            p.append(f'{LOCKS / n} esiste')
    return p


def comando(p):
    """(argv, env aggiuntivo) del passo."""
    a = ARMS.get(p['arm'])
    if p['ruolo'] == 'blocco':
        return [sys.executable, str(CAMP / 'camp_bisezione.py'), '--vai', '--solo', 'nopp', '--config', str(HERE / 'cfg-daily-base.json'),
                '--build', DAILY_BUILD, '--out', str(OUT / p['tag'])], {}
    if a['kind'] == 'camp':
        env = dict(CAMP_OUT=str(OUT), CAMP_SAMPLING=json.dumps(a['sampling']), CAMP_RUNS=str(a['runs']), CAMP_TARGETS=a['targets'])
        return [sys.executable, str(CAMP / 'community_bench_camp.py'), p['tag'], str(HERE / a['cfg']), a['build']], env
    inner = [sys.executable, '-u', '-X', 'utf8', str(REPLAY / 'replay_trace.py'), '--tag', p['tag'], '--t0', '3600', '--span', '1200',
             '--only', 'A,B,C', '--config', str(HERE / 'cfg-daily-base.json'), '--exe', a['exe'], '--out-base', str(OUT),
             '--port', '8102', '--extra=' + a['extra'], '--env=' + a['env']]
    return [sys.executable, '-u', str(CORSE / '20261006_due_schede' / 'bench_lock.py'), f'LEVE-{p["tag"]}', '--'] + inner, {}


def controlla(lista):
    mancano = []
    for p in lista:
        if p['ruolo'] == 'blocco':
            for f in (HERE / 'cfg-daily-base.json', Path(DAILY_BUILD) / 'strata.exe', CAMP / 'camp_bisezione.py'):
                if not f.exists() and str(f) not in mancano:
                    mancano.append(str(f))
            continue
        a = ARMS[p['arm']]
        for f in ([HERE / a['cfg'], Path(a['build']) / 'strata.exe'] if a['kind'] == 'camp' else [Path(a['exe'])]):
            if not Path(f).exists() and str(f) not in mancano:
                mancano.append(str(f))
    return mancano


# ---- analisi ----------------------------------------------------------------------------------------------------------
def metriche(p, fredda):
    a = ARMS.get(p['arm'])
    if p['ruolo'] == 'blocco':
        return None
    if a['kind'] == 'camp':
        f = OUT / p['tag'] / 'results.json'
        if not f.exists():
            return None
        rows = [r for r in json.loads(f.read_text(encoding='utf-8')) if r['label'] != 'warmup']
        if rows and not fredda:
            rows = rows[1:]       # la prima da 4K e ancora fredda
        m = {}
        for t in a['targets'].split(','):
            s = [r for r in rows if r['label'].startswith(f'tokens-{t}-')]
            if s:
                m[f'decode {int(t) // 1024}K'] = st.median(r['engine']['engine_generated'] / (r['engine']['decode_ms'] / 1000) for r in s)
                m[f'prompt {int(t) // 1024}K'] = st.median(
                    (r['engine']['prompt_tokens'] - (r['engine'].get('reused') or 0)) / (r['engine']['prompt_ms'] / 1000) for r in s)
        return dict(m=m, alto=True)
    f = OUT / f'replay_{p["tag"]}' / 'res.json'
    if not f.exists():
        return None
    s = json.loads(f.read_text(encoding='utf-8'))['summary']
    m = {k: s.get(k) for k in ('makespan', 'ttft_mean', 'ttft_p90', 'queue_wait_mean')}
    m['decode agg tok/s'] = s['out'] / s['makespan'] if s.get('makespan') else None
    return dict(m=m, alto=False, note=('DISTURBATO ' if s.get('disturbed') else '') + ('FALLITE ' if s.get('failed') or s.get('unfinished_agents') else ''))


def analisi(fredda):
    lista = passi()
    for i, p in enumerate(lista):
        if p['ruolo'] == 'blocco':
            print(f'\n== {p["tid"]} {p["titolo"]}')
            d = OUT / p['tag']
            if d.exists():
                subprocess.run([sys.executable, str(CAMP / 'camp_analisi.py'), 'corse', str(d)])
            else:
                print('  (non ancora eseguito)')
            continue
        if p['ruolo'] != 'leva':
            continue
        b1, b2 = lista[i - 1], lista[i + 1]
        r = [metriche(x, fredda) for x in (b1, p, b2)]
        print(f'\n== {p["tid"]} {p["titolo"]}   [{b1["tag"]} | {p["tag"]} | {b2["tag"]}]')
        if not all(r):
            print('  (terna non completa)')
            continue
        soglia = 0.03 if ARMS[p['arm']]['kind'] == 'camp' else 0.05
        for k in r[1]['m']:
            v = [x['m'].get(k) for x in r]
            if None in v:
                continue
            mb = (v[0] + v[2]) / 2
            d = (v[1] / mb - 1) if r[1]['alto'] else (mb / v[1] - 1)    # +% = meglio (decode piu alto, tempo piu basso)
            inst = abs(v[0] - v[2]) / mb > soglia
            print(f'  {k:18s} {v[0]:9.1f} {v[1]:9.1f} {v[2]:9.1f}   leva {d * 100:+6.1f}%{"   TERNA INSTABILE (basi a piu del %d%%)" % (soglia * 100) if inst else ""}')
        notes = [x.get('note') for x in r if x.get('note')]
        if notes:
            print('  attenzione:', ' / '.join(notes))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vai', action='store_true')
    ap.add_argument('--fino', type=int, default=0, help='ultimo passo da eseguire')
    ap.add_argument('--riprendi', action='store_true')
    ap.add_argument('--analisi', action='store_true')
    ap.add_argument('--tieni-fredda', action='store_true')
    a = ap.parse_args()
    if a.analisi:
        return analisi(a.tieni_fredda)
    lista = passi()
    tot = 0
    print(f'build leve026: {LEVE_BUILD}\nuscita: {OUT}\n')
    for p in lista:
        tot += p['min']
        argv, _ = comando(p)
        print(f'{p["n"]:02d} {p["ruolo"]:6s} {p["arm"]:8s} {p["min"]:3d} min  (cumulo {tot // 60} h {tot % 60:02d})  [{p["tid"]}] {p["titolo"]}')
    print(f'\ntotale stimato: {tot // 60} h {tot % 60:02d} min in {len(lista)} passi')
    mancano = controlla(lista)
    if mancano:
        print('\nMANCANO (la coda non parte finche non ci sono):\n  ' + '\n  '.join(mancano))
    if not a.vai:
        print('\n(prova a secco: niente lanciato)')
        return
    if mancano:
        raise SystemExit('file mancanti: lanciare make_configs.py e verificare le build')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'fatto').mkdir(exist_ok=True)
    for p in lista:
        if a.fino and p['n'] > a.fino:
            break
        ok = OUT / 'fatto' / (p['tag'] + '.ok')
        if a.riprendi and ok.exists():
            continue
        pr = occupato()
        if pr:
            raise SystemExit(f'PC non libero al passo {p["n"]:02d}: ' + '; '.join(pr))
        argv, env = comando(p)
        print(f'[{time.strftime("%H:%M:%S")}] passo {p["n"]:02d} {p["tag"]}: {" ".join(argv[:4])} ...', flush=True)
        r = subprocess.run(argv, env=dict(os.environ, **env))
        print(f'[{time.strftime("%H:%M:%S")}] passo {p["n"]:02d} uscita {r.returncode}', flush=True)
        if r.returncode != 0:
            raise SystemExit(f'passo {p["n"]:02d} {p["tag"]} fallito: coda interrotta (riprendere con --riprendi)')
        ok.write_text(time.strftime('%Y-%m-%d %H:%M'), encoding='utf-8')
    print('fatto. Analisi: python coda_leve_026.py --analisi')


if __name__ == '__main__':
    main()
