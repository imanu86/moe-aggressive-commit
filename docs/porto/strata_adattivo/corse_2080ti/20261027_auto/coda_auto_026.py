"""Coda di misure della Daily "Auto" (batch dinamico su 0.2.6, build dyn026), 27/10/2026.

NON e' stata eseguita: senza --vai stampa soltanto l'ordine, le durate e i controlli sui file (nessuna GPU, nessun processo).

  python coda_auto_026.py                  # prova a secco: ordine, stima, file mancanti
  python coda_auto_026.py --vai            # esegue tutto in ordine (PC libero: nessun strata.exe, il Daily dell'owner va fermato)
  python coda_auto_026.py --vai --fino 8   # solo i primi 8 passi
  python coda_auto_026.py --vai --riprendi # salta i passi con fatto/<tag>.ok (dopo uno stop)
  python coda_auto_026.py --analisi        # tabelle base | leva | base, senza GPU

Prima di tutto: python make_configs.py <cartella build dyn026>  (scrive cfg-daily-base.json, cfg-auto.json, auto_build.txt).

Rifiuta di partire, e si ferma fra un passo e l'altro, se c'e' un strata.exe vivo, lab_locks\\pause, bench.lock o build.lock.
Chiusura del motore a fine passo: i runner uccidono il proprio strata.exe (e questo script ripulisce se un passo fallisce).
La prima richiesta di ogni avvio e' scartata (banchi: warmup da 19 token piu' la prima da 4K ancora fredda; replay: le letture di
riscaldamento a max_tokens 1 prima del cronometro; RAM: richiesta di riscaldamento fuori dai cicli).  Terne base-leva-base: ogni leva
ha una base subito prima e dopo; una terna con le due basi a piu' del 3% (banchi) o 5% (replay) e' marcata instabile e non vale.

Cosa si misura (leva = Auto, build dyn026 con STRATA_BATCH_DYNAMIC=1 e la config Auto: --batch 4 --batch-groups 2, riserva 1905/700,
cache conversazioni 18432 MiB / 16 posti; base = quanto indicato):
  c  RAM nel tempo del passaggio a caldo (perdita c4af6851): 8 cicli di entrata/uscita, memoria privata di strata.exe dopo ogni uscita
  a  chat singola, banco della comunita' corto (4K/32K, 4 corse), Auto contro Daily 0.2.6: a T=0 e a T=0,7 (top_p 0,8, top_k 20,
     presence 0: e' il caso in cui la pipeline a due finestre resta accesa, quindi il piu' severo per l'Auto) - DEVE PAREGGIARE
  b  replay della traccia DSH del 16/10 (finestra 3600-4800 s) con 3, 6 e 8 agenti (replay_trace.py --only/--dup):
       R2 = Daily 0.2.6 con --batch 4 --batch-groups 2 FISSO (nessun batch dinamico)   AU = Auto
       R0 = Daily 0.2.6 senza batch
     per ogni numero di agenti due terne: R2-AU-R2 (l'Auto in modo agenti vale il batch fisso?) e R0-AU-R0 (e batte il Daily senza batch?)
     3 agenti = sessioni A,B,C; 6 = A,B,C con --dup 2; 8 = A,B,C,P con --dup 2.  Nessun PIPED_CONCURRENT (facoltativo, makespan -3%, TTFT peggiore).
"""
import argparse, json, os, re, statistics as st, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
LOCKS = Path(r'D:\ds4_work\strata\lab_locks')
OUT = HERE / 'corse'
DAILY_BUILD = r'D:\ds4_work\strata\Strata\build-026-daily'
AUTO_BUILD = (HERE / 'auto_build.txt').read_text(encoding='utf-8').strip() if (HERE / 'auto_build.txt').exists() else r'<build dyn026: lanciare make_configs.py>'
CAMP = CORSE / '20261025_bisezione'
REPLAY = CORSE / '20261019_replay'
G = '--conversation-cache-mib 18432 --conversation-cache-slots 16'
R4 = '--vram-reserve-mib 1905 --vram-reserve-later-mib 700'
B4G2 = f'--batch 4 --batch-groups 2 {G} {R4}'
T0 = {'temperature': 0}
T7 = {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'presence_penalty': 0}
AUTO_EXE = f'{AUTO_BUILD}\\strata.exe'
DAILY_EXE = f'{DAILY_BUILD}\\strata.exe'

# ---- bracci -------------------------------------------------------------------------------------------------------
ARMS = {
    'D0': dict(kind='camp', cfg='cfg-daily-base.json', build=DAILY_BUILD, sampling=T0, targets='4096,32768', runs=4, min=5,
               nota='Daily 0.2.6, T=0, 4K/32K x4'),
    'A0': dict(kind='camp', cfg='cfg-auto.json', build=AUTO_BUILD, sampling=T0, targets='4096,32768', runs=4, min=5,
               nota='Auto, T=0, 4K/32K x4 (chat singola: dev\'essere la Daily)'),
    'D7': dict(kind='camp', cfg='cfg-daily-base.json', build=DAILY_BUILD, sampling=T7, targets='4096,32768', runs=4, min=5,
               nota='Daily 0.2.6, T=0,7 presence 0, 4K/32K x4'),
    'A7': dict(kind='camp', cfg='cfg-auto.json', build=AUTO_BUILD, sampling=T7, targets='4096,32768', runs=4, min=5,
               nota='Auto, T=0,7 presence 0, 4K/32K x4'),
}
# replay: (sigla, agenti) -> flag di replay_trace.py; durate stimate in minuti (3 agenti: misurate la notte 26-27/10; 6 e 8: stimate)
AG = {3: ('--only A,B,C', {'R0': 11, 'R2': 8, 'AU': 8}),
      6: ('--only A,B,C --dup 2', {'R0': 17, 'R2': 13, 'AU': 13}),
      8: ('--dup 2', {'R0': 25, 'R2': 17, 'AU': 17})}
for n, (flags, mins) in AG.items():
    ARMS[f'R0_{n}'] = dict(kind='replay', exe=DAILY_EXE, extra='', env='', flags=flags, min=mins['R0'], nota=f'Daily 0.2.6 senza batch, {n} agenti')
    ARMS[f'R2_{n}'] = dict(kind='replay', exe=DAILY_EXE, extra=B4G2, env='', flags=flags, min=mins['R2'],
                           nota=f'Daily 0.2.6 --batch 4 --batch-groups 2 fisso, {n} agenti')
    ARMS[f'AU_{n}'] = dict(kind='replay', exe=AUTO_EXE, extra=B4G2, env='STRATA_BATCH_DYNAMIC=1', flags=flags, min=mins['AU'],
                           nota=f'Auto (STRATA_BATCH_DYNAMIC=1, --batch 4 --batch-groups 2), {n} agenti')

# ---- terne (base, leva, perche'), nell'ordine di priorita' -----------------------------------------------------------
TERNE = [
    ('c1', 'ram', 'RAM nel tempo: 8 cicli entrata/uscita (perdita di ~10 GiB a ciclo corretta in c4af6851, mai rimisurata)',
     'e la correttezza: se perde, il resto non vale'),
    ('a1', ('D0', 'A0'), 'chat singola T=0: Auto contro Daily 0.2.6', 'deve pareggiare (0.1.45: pari entro il rumore, decode -1/+1,5%)'),
    ('a2', ('D7', 'A7'), 'chat singola T=0,7 (presence 0): Auto contro Daily 0.2.6', 'pipeline a due finestre accesa: il caso piu\' severo'),
    ('b3a', ('R2_3', 'AU_3'), '3 agenti: Auto contro batch fisso', 'in modo agenti l\'Auto deve valere il batch fisso (0.2.6: 251 s)'),
    ('b3b', ('R0_3', 'AU_3'), '3 agenti: Auto contro Daily senza batch', 'senza batch 443-449 s'),
    ('b6a', ('R2_6', 'AU_6'), '6 agenti: Auto contro batch fisso', 'oltre i 4 slot: coda; ingresso/uscita ripetuti'),
    ('b6b', ('R0_6', 'AU_6'), '6 agenti: Auto contro Daily senza batch', ''),
    ('b8a', ('R2_8', 'AU_8'), '8 agenti: Auto contro batch fisso', 'carico massimo della traccia x2'),
    ('b8b', ('R0_8', 'AU_8'), '8 agenti: Auto contro Daily senza batch', ''),
]


def passi():
    """Lista piatta dei passi: terne concatenate con la base unica fra due leve vicine."""
    out, ult = [], None
    for tid, arms, titolo, perche in TERNE:
        if arms == 'ram':
            out.append(dict(tid=tid, arm='ram', ruolo='blocco', min=12, titolo=titolo))
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
    if p['ruolo'] == 'blocco':
        return [sys.executable, '-u', str(HERE / 'run_ram.py'), p['tag'], str(HERE / 'cfg-auto.json'), '--cicli', '8', '--agenti', '4',
                '--idle', '10', '--out', str(OUT)], {}
    a = ARMS[p['arm']]
    if a['kind'] == 'camp':
        env = dict(CAMP_OUT=str(OUT), CAMP_SAMPLING=json.dumps(a['sampling']), CAMP_RUNS=str(a['runs']), CAMP_TARGETS=a['targets'])
        return [sys.executable, str(CAMP / 'community_bench_camp.py'), p['tag'], str(HERE / a['cfg']), a['build']], env
    inner = [sys.executable, '-u', '-X', 'utf8', str(REPLAY / 'replay_trace.py'), '--tag', p['tag'], '--t0', '3600', '--span', '1200',
             *a['flags'].split(), '--config', str(HERE / 'cfg-daily-base.json'), '--exe', a['exe'], '--out-base', str(OUT),
             '--port', '8102', '--extra=' + a['extra'], '--env=' + a['env']]
    return [sys.executable, '-u', str(CORSE / '20261006_due_schede' / 'bench_lock.py'), f'AUTO-{p["tag"]}', '--'] + inner, {}


def controlla(lista):
    mancano = []
    for p in lista:
        if p['ruolo'] == 'blocco':
            fs = [HERE / 'cfg-auto.json', Path(AUTO_BUILD) / 'strata.exe', HERE / 'run_ram.py', CORSE / '20261019_batch_dyn' / 'turno_lock.py']
        else:
            a = ARMS[p['arm']]
            fs = [HERE / a['cfg'], Path(a['build']) / 'strata.exe'] if a['kind'] == 'camp' else [Path(a['exe']), HERE / 'cfg-daily-base.json']
        for f in fs:
            if not Path(f).exists() and str(f) not in mancano:
                mancano.append(str(f))
    return mancano


# ---- analisi ----------------------------------------------------------------------------------------------------------
def metriche(p, fredda):
    if p['ruolo'] == 'blocco':
        return None
    a = ARMS[p['arm']]
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
        return dict(m=m, alto=True, info={})
    f = OUT / f'replay_{p["tag"]}' / 'res.json'
    if not f.exists():
        return None
    s = json.loads(f.read_text(encoding='utf-8'))['summary']
    m = {k: s.get(k) for k in ('makespan', 'ttft_mean', 'ttft_p90', 'queue_wait_mean')}
    m['decode agg tok/s'] = s['out'] / s['makespan'] if s.get('makespan') else None
    info = {k: s.get(k) for k in ('mem_strata_private_max_gib', 'mem_avail_min_gib', 'mem_swap_used_max_gib')}
    return dict(m=m, alto=False, info=info,
                note=('DISTURBATO ' if s.get('disturbed') else '') + ('FALLITE ' if s.get('failed') or s.get('unfinished_agents') else ''))


def passaggi_dyn(tag):
    """Dal log del motore: quanti passaggi chat singola <-> agenti e quanto durano ('strata batch-dyn: modo ...')."""
    f = OUT / f'replay_{tag}' / 'engine.log'
    if not f.exists():
        return None
    ent, usc = [], []
    for l in f.read_text(encoding='utf-8', errors='replace').splitlines():
        m = re.search(r'strata batch-dyn: modo (agenti|chat singola) \((\d+)[^)]*\) in (\d+) ms', l)
        if m:
            (ent if m.group(1) == 'agenti' else usc).append(int(m.group(3)))
    return ent, usc


def analisi(fredda):
    lista = passi()
    for i, p in enumerate(lista):
        if p['ruolo'] == 'blocco':
            print(f'\n== {p["tid"]} {p["titolo"]}')
            f = OUT / p['tag'] / 'ram_cicli.json'
            if not f.exists():
                print('  (non ancora eseguito)')
                continue
            rows = json.loads(f.read_text(encoding='utf-8'))
            for r in rows:
                print(f'  ciclo {r["ciclo"]}: privata agenti {r["privata_agenti_gib"]:6.1f} GiB, dopo l\'uscita {r["privata_dopo_gib"]:6.1f} GiB, '
                      f'RAM disponibile {r["ram_disponibile_gib"]:5.1f} GiB, decode solo prima/dopo {r["decode_pre"]} / {r["decode_post"]}')
            d = rows[-1]['privata_dopo_gib'] - rows[0]['privata_dopo_gib']
            print(f'  differenza ciclo {len(rows)} meno ciclo 1: {d:+.2f} GiB -> {"OK, nessuna perdita" if d <= 1.0 else "PERDITA"}')
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
        for k in r[1]['info']:
            v = [x['info'].get(k) for x in r]
            if None not in v:
                print(f'  {k:28s} {v[0]:7.1f} {v[1]:7.1f} {v[2]:7.1f}  (informativo)')
        notes = [x.get('note') for x in r if x.get('note')]
        if notes:
            print('  attenzione:', ' / '.join(notes))
        if p['arm'].startswith('AU_'):
            pd = passaggi_dyn(p['tag'])
            if pd:
                print(f'  passaggi dell\'Auto: {len(pd[0])} entrate (ms: {pd[0][:8]}), {len(pd[1])} uscite (ms: {pd[1][:8]})')


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
    print(f'build dyn026: {AUTO_BUILD}\nuscita: {OUT}\n')
    for p in lista:
        tot += p['min']
        print(f'{p["n"]:02d} {p["ruolo"]:6s} {p["arm"]:6s} {p["min"]:3d} min  (cumulo {tot // 60} h {tot % 60:02d})  [{p["tid"]}] {p["titolo"]}')
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
        for _ in range(12):   # il motore del passo prima puo' metterci qualche secondo a uscire
            if not pr:
                break
            subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
            time.sleep(10)
            pr = occupato()
        if pr:
            raise SystemExit(f'PC non libero al passo {p["n"]:02d}: ' + '; '.join(pr))
        argv, env = comando(p)
        print(f'[{time.strftime("%H:%M:%S")}] passo {p["n"]:02d} {p["tag"]}: {" ".join(argv[:4])} ...', flush=True)
        r = subprocess.run(argv, env=dict(os.environ, **env))
        print(f'[{time.strftime("%H:%M:%S")}] passo {p["n"]:02d} uscita {r.returncode}', flush=True)
        if r.returncode != 0:
            # un passo fallito non ferma la coda (si annota e si va avanti; motore e lock ripuliti)
            print(f'passo {p["n"]:02d} {p["tag"]} FALLITO: annotato, si prosegue', flush=True)
            (OUT / 'fatto' / (p['tag'] + '.fallito')).write_text(time.strftime('%Y-%m-%d %H:%M'), encoding='utf-8')
            subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
            (LOCKS / 'bench.lock').unlink(missing_ok=True)
            continue
        ok.write_text(time.strftime('%Y-%m-%d %H:%M'), encoding='utf-8')
    print('fatto. Analisi: python coda_auto_026.py --analisi')


if __name__ == '__main__':
    main()
