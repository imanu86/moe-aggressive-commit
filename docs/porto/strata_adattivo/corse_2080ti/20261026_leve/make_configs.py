"""Copie di config per la coda delle leve (26/10). Sola lettura di strata-026-daily.json (mai modificato).

    python make_configs.py <cartella build leve026, es. ...\\20261004_routed_keep\\build-leve026-<sha>>

Scrive in questa cartella:
  cfg-daily-base.json    copia esatta della Daily 0.2.6 (exe = build-026-daily)
  cfg-daily-bf16tc.json  Daily + STRATA_BF16_TC=1                       (a2: lettura prompt a T=0)
  cfg-leve-r3.json       R3 sulla build leve026, leve spente: --batch 4 --batch-groups 2, cache conversazioni 18432 MiB / 16 posti,
                         riserva 1905 / 700 MiB, STRATA_PIPED_CONCURRENT=1, senza --prompt-cache-file come nel replay  (a3: chat singola con batch, base)
  cfg-leve-r3-pw.json    R3 + STRATA_PW_WITH_BATCH=1                    (a3)
Le config dei bracci del replay non servono: replay_trace.py parte dalla Daily e applica --extra / --env (vedi coda_leve_026.py).
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAILY = Path(r'D:\ds4_work\strata\Strata\strata-026-daily.json')
DAILY_BUILD = Path(r'D:\ds4_work\strata\Strata\build-026-daily')
if len(sys.argv) != 2:
    raise SystemExit(__doc__)
LEVE = Path(sys.argv[1]).resolve()
if not (LEVE / 'strata.exe').exists():
    raise SystemExit(f'{LEVE}\\strata.exe non esiste')
base = json.loads(DAILY.read_text(encoding='utf-8-sig'))


def split_opts(toks):
    out, cur = [], None
    for t in toks:
        if t.startswith('--'):
            cur = [t]
            out.append(cur)
        else:
            cur.append(t)
    return out


def con(env=None, extra=None, exe=None, drop_opts=()):
    c = json.loads(json.dumps(base))
    c['env'].update(env or {})
    if extra:
        new = split_opts(extra)
        drop = {o[0] for o in new} | set(drop_opts)
        c['args'] = [x for o in split_opts(c['args']) if o[0] not in drop for x in o] + [x for o in new for x in o]
    if exe:
        c['exe'] = str(exe / 'strata.exe')
        c['vision']['exe'] = str(exe / 'strata-vision.exe')
    return c


R3 = ['--batch', '4', '--batch-groups', '2', '--conversation-cache-mib', '18432', '--conversation-cache-slots', '16',
      '--vram-reserve-mib', '1905', '--vram-reserve-later-mib', '700']
R3ENV = {'STRATA_PIPED_CONCURRENT': '1'}
out = {
    'cfg-daily-base.json': con(),
    'cfg-daily-bf16tc.json': con({'STRATA_BF16_TC': '1'}),
    'cfg-leve-r3.json': con(R3ENV, R3, LEVE, ('--prompt-cache-file',)),
    'cfg-leve-r3-pw.json': con({**R3ENV, 'STRATA_PW_WITH_BATCH': '1'}, R3, LEVE, ('--prompt-cache-file',)),
}
for name, c in out.items():
    (HERE / name).write_text(json.dumps(c, indent=1), encoding='utf-8')
    print(name, '| exe', c['exe'], '| env +', sorted(set(c['env']) - set(base['env'])))
assert out['cfg-daily-base.json'] == base, 'la copia base non e identica alla Daily'
(HERE / 'leve_build.txt').write_text(str(LEVE) + '\n', encoding='utf-8')
