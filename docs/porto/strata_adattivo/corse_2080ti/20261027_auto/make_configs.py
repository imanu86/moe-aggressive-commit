"""Config della Daily "Auto" (batch dinamico su 0.2.6, 27/10/2026). Sola lettura di strata-026-daily.json (mai modificato).

    python make_configs.py <cartella build, es. ...\\20261004_routed_keep\\build-dyn026-<sha>> [--installa-config]

Scrive in questa cartella:
  cfg-daily-base.json   copia esatta della Daily 0.2.6 (exe = build-026-daily): il riferimento
  cfg-auto.json         la config Auto con exe = la build dyn026 (il banco ridirige il prefisso su disco nella cartella della corsa)
  auto_build.txt        percorso della build, letto da coda_auto_026.py
Con --installa-config scrive anche D:\\ds4_work\\strata\\Strata\\strata-026-auto.json (se esiste con altro contenuto non la
sovrascrive): e' la config della bat "Strata 0.2.6 Auto - porta 8100.bat".  Non installa nessuna build: l'exe resta nella cartella delle build.

Auto = Daily 0.2.6 + --batch 4 --batch-groups 2 (ESPLICITO: il gruppo seriale, default 0.2.6, e' molto peggio) + STRATA_BATCH_DYNAMIC=1
(STRATA_BATCH_IDLE_S resta al default, 30 s) + riserva VRAM 1905 / 700 MiB + cache conversazioni 18432 MiB / 16 posti.
Il prefisso su disco ha un file suo (prompt-prefix-026-auto.bin): non condivide quello della Daily.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAILY = Path(r'D:\ds4_work\strata\Strata\strata-026-daily.json')
AUTO_JSON = Path(r'D:\ds4_work\strata\Strata\strata-026-auto.json')
if len(sys.argv) < 2:
    raise SystemExit(__doc__)
BUILD = Path(sys.argv[1]).resolve()
if not (BUILD / 'strata.exe').exists():
    raise SystemExit(f'{BUILD}\\strata.exe non esiste')
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


AUTO_ARGS = ['--batch', '4', '--batch-groups', '2', '--conversation-cache-mib', '18432', '--conversation-cache-slots', '16',
             '--vram-reserve-mib', '1905', '--vram-reserve-later-mib', '700']
auto = json.loads(json.dumps(base))
drop = {o[0] for o in split_opts(AUTO_ARGS)} | {'--prompt-cache-file'}
args = [x for o in split_opts(auto['args']) if o[0] not in drop for x in o]
pcf = [o for o in split_opts(base['args']) if o[0] == '--prompt-cache-file']
args += [x for o in split_opts(AUTO_ARGS) for x in o]
if pcf:   # il prefisso su disco: un file suo, accanto a quello della Daily
    args += ['--prompt-cache-file', str(Path(pcf[0][1]).with_name('prompt-prefix-026-auto.bin'))]
auto['args'] = args
auto['env']['STRATA_BATCH_DYNAMIC'] = '1'
auto['exe'] = str(BUILD / 'strata.exe')
auto['vision']['exe'] = str(BUILD / 'strata-vision.exe')
auto['log'] = str(Path(base['log']).with_name('strata_026_auto.log'))

(HERE / 'cfg-daily-base.json').write_text(json.dumps(base, indent=1), encoding='utf-8')
(HERE / 'cfg-auto.json').write_text(json.dumps(auto, indent=1), encoding='utf-8')
(HERE / 'auto_build.txt').write_text(str(BUILD) + '\n', encoding='utf-8')
print('cfg-daily-base.json | exe', base['exe'])
print('cfg-auto.json       | exe', auto['exe'], '| env +', sorted(set(auto['env']) - set(base['env'])))
if '--installa-config' in sys.argv:
    txt = json.dumps(auto, indent=1)
    if AUTO_JSON.exists() and AUTO_JSON.read_text(encoding='utf-8-sig') != txt:
        print(f'{AUTO_JSON} esiste con altro contenuto: non la sovrascrivo (cancellarla a mano se e davvero da rifare)')
    else:
        AUTO_JSON.write_text(txt, encoding='utf-8')
        print('scritta', AUTO_JSON)
