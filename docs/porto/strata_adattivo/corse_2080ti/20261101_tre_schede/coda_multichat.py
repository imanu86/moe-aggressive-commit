"""Multichat 01/11/2026: 3080 Ti + 2080 Ti libere (3060 con schermo e OktoCGControl). Replay DSH 3600+1200 s, sessioni A,B,C, come 29/10.
Tutte le corse: STRATA_ROUTE_PRIOR=0, PIPED_CONCURRENT=1, batch 4, cache conversazioni 18432 MiB / 16 posti.

    python coda_multichat.py <split> braccio[:dup] ...     (dup 2 = 6 agenti)
Bracci s0/s1: due server di esperti (build BLOTTI, cfg-due-server.json, GPU 0,2,1), senza --layer-split: lo split si ignora.
Output in corse_mc/replay_<NN>_<braccio>_s<split>[_6ag]. Sempre dietro bench_lock; a fine corsa strata.exe spento e lock tolto.
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORSE = HERE.parent
K = CORSE / '20261004_routed_keep'
B0271, B029 = K / 'build-up0271pila-5fbc4784', K / 'build-up029pila-b6ba3fa6'
B0210 = K / 'build-up0210pila-ed6c8aa2'
B02131 = K / 'build-up02131pila-8eb601e3'   # 11/11: 0.2.13.1 + pila   # 04/11: 0.2.10 + pila + richieste 5149 5108 5137 (il candidato Daily)
BLOTTI = K / 'build-server-lotti-7988205b'   # da sostituire col nome vero
OUT = HERE / 'corse_mc'
G = '--batch 4 --conversation-cache-mib 18432 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700 --ple-io direct'
PC = 'STRATA_ROUTE_PRIOR=0 STRATA_PIPED_CONCURRENT=1'
COAL = PC + ' STRATA_COALESCE_PREFILL=4 STRATA_COALESCE_MIN_REQS=2 STRATA_COALESCE_BURST_MS=1000 STRATA_COALESCE_WAIT_MS=50'
ARMS = {
    'p': (B0271, PC),      # v0.2.7.1 + pila
    'u': (B029, PC),       # v0.2.9 + pila
    'c': (B029, COAL),     # v0.2.9 + lettura condivisa
    't': (B029, PC + ' STRATA_SM75_PERF=1 STRATA_EXP_MODE=8'),   # v0.2.9 + leve del 02/11 (e senza STRATA_MMVQ_IL: vedi cfg_t)
    'x': (B02131, PC + ' STRATA_SM75_PERF=1 STRATA_EXP_MODE=8 STRATA_ADAPT_NOWAIT=1 STRATA_ADAPT_LAG=2 STRATA_KQ_SPLIT=1 STRATA_GU_SWIGLU=1'),   # 11/11: 0.2.13.1 + tutte le leve
    'w': (B0210, PC + ' STRATA_SM75_PERF=1 STRATA_EXP_MODE=8 STRATA_ADAPT_NOWAIT=1 STRATA_ADAPT_LAG=2 STRATA_KQ_SPLIT=1 STRATA_GU_SWIGLU=1'),   # 04/11: 0.2.10 + tutte le leve vincenti
}
# due server di esperti (al posto della divisione a strati): s0 = STRATA_PEER_BATCH=0, s1 = STRATA_PEER_BATCH=1
PEER = ' STRATA_PEER_FUSED=1 STRATA_PEER2_FUSED=1 STRATA_PEER2_SKIP=1 STRATA_PEER2_STAGE=1 STRATA_PEER2_PREFILL=1 STRATA_ARENA_PIN_GIB=8'
ARMS['s0'] = (BLOTTI, ARMS['x'][1] + PEER + ' STRATA_PEER_BATCH=0')
ARMS['s1'] = (BLOTTI, ARMS['x'][1] + PEER + ' STRATA_PEER_BATCH=1')
# 12/11: con --batch 4 le sessioni a slot (0,95 GiB ciascuna) restringono la cache della 3080 Ti e la lettura scende a pezzi da 1024
ARMS['s2'] = (BLOTTI, ARMS['s1'][1] + ' STRATA_PF_SMALL=0')   # lettura a pezzi grandi comunque
ARMS['s3'] = (BLOTTI, ARMS['s1'][1])                          # K/V residente a 16K per slot (vedi G2K)
TWO = ('s0', 's1', 's2', 's3')
G2 = G.replace(' --vram-reserve-later-mib 700', '').replace('--vram-reserve-mib 1905', '--vram-reserve-mib 700 --peer-device 1,2 --peer-reserve-mib 3000,1000')
G2K = G2 + ' --kv-resident 16384'
# 12/11: stima delle repliche (ogni scheda le sue chat): motore su una scheda sola, 0.2.13.1 + leve. r0 = 3080 Ti, r2 = 2080 Ti
ARMS['r0'] = (B02131, ARMS['x'][1])
ARMS['r2'] = (B02131, ARMS['x'][1])
ONE = {'r0': '0', 'r2': '2'}
G1 = G.replace(' --vram-reserve-later-mib 700', '')
# 12/11 mattina: la 2080 Ti (22 GB, x16, schermo) come scheda principale. y = divisione a strati `2,0`; v = due server
# (3080 Ti e 3060, nessuno schermo: riserva 1000 ciascuno) come s3, la principale con la riserva dello schermo (1905)
ARMS['y'] = (B02131, ARMS['x'][1])
ARMS['v'] = (BLOTTI, ARMS['s3'][1])
TWO = TWO + ('v',)
GV = G2K.replace('--vram-reserve-mib 700', '--vram-reserve-mib 1905').replace('--peer-reserve-mib 3000,1000', '--peer-reserve-mib 1000,1000')
cfg = OUT / 'cfg-due-schede.json'
cfg_t = OUT / 'cfg-due-schede-leve.json'
cfg_2s = OUT / 'cfg-due-server.json'
OUT.mkdir(exist_ok=True)
c = json.loads((CORSE / '20261029_multichat' / 'cfg-up0271-3080ti.json').read_text(encoding='utf-8-sig'))
c['env'].update({'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'CUDA_VISIBLE_DEVICES': '0,2', 'STRATA_ROUTE_PRIOR': '0'})
cfg.write_text(json.dumps(c, indent=1), encoding='utf-8')
del c['env']['STRATA_MMVQ_IL']
cfg_t.write_text(json.dumps(c, indent=1), encoding='utf-8')
c['env']['CUDA_VISIBLE_DEVICES'] = '0,2,1'
for k in ('STRATA_RAM_CORE', 'STRATA_RAM_CORE_SLOTS_DEV1', 'STRATA_CONV_DISK', 'STRATA_PREFIX_DISK_MULTI'):
    c['env'].pop(k, None)
a, out_args, i = c['args'], [], 0
while i < len(a):
    if a[i] in ('--layer-split', '--pipeline-windows', '--prompt-cache-file', '--vram-reserve-later-mib'):
        i += 2
    elif a[i] in ('--elastic', '--trim-stage-weights'):
        i += 1
    else:
        out_args.append(a[i]); i += 1
c['args'] = out_args
cfg_2s.write_text(json.dumps(c, indent=1), encoding='utf-8')
cfg_v = OUT / 'cfg-due-server-2080ti.json'      # come cfg-due-server, principale la 2080 Ti
c['env']['CUDA_VISIBLE_DEVICES'] = '2,0,1'
cfg_v.write_text(json.dumps(c, indent=1), encoding='utf-8')
cy = json.loads(cfg_t.read_text(encoding='utf-8'))   # divisione a strati con la 2080 Ti prima
cy['env']['CUDA_VISIBLE_DEVICES'] = '2,0'
cy['env'].pop('STRATA_RAM_CORE_SLOTS_DEV1', None)   # tarato sulla 2080 Ti come seconda scheda
cfg_y = OUT / 'cfg-due-schede-2080ti-prima.json'
cfg_y.write_text(json.dumps(cy, indent=1), encoding='utf-8')
cfg_1 = {}
for arm, dev in ONE.items():      # come cfg-due-server ma con una scheda sola
    c['env']['CUDA_VISIBLE_DEVICES'] = dev
    cfg_1[arm] = OUT / f'cfg-una-scheda-{dev}.json'
    cfg_1[arm].write_text(json.dumps(c, indent=1), encoding='utf-8')
split = sys.argv[1]
n = len([p for p in OUT.iterdir() if p.name.startswith('replay_')])
for spec in sys.argv[2:]:
    arm, _, dup = spec.partition(':')
    n += 1
    build, env = ARMS[arm]
    # s0/s1: lo split dalla riga di comando si ignora (nessuna divisione a strati), ma resta nel tag della cartella
    tag = f'{n:02d}_{arm}_s{split}' + (f'_{int(dup) * 3}ag' if dup else '')
    cmd = [sys.executable, '-u', str(CORSE / '20261006_due_schede' / 'bench_lock.py'), f'MULTICHAT-{tag}', '--',
           sys.executable, '-u', '-X', 'utf8', str(CORSE / '20261019_replay' / 'replay_trace.py'), '--tag', tag, '--t0', '3600', '--span', '1200',
           '--only', 'A,B,C', '--config', str(cfg_1[arm] if arm in ONE else cfg_y if arm == 'y' else cfg_v if arm == 'v' else cfg_2s if arm in TWO else cfg_t if arm in ('t', 'w', 'x') else cfg), '--exe', str(build / 'strata.exe'),
           '--out-base', str(OUT), '--port', '8102', f'--extra={G1}' if arm in ONE else f'--extra={GV}' if arm == 'v' else f'--extra={G2K if arm == "s3" else G2}' if arm in TWO else f'--extra={G} --layer-split {split}', '--env=' + env]
    if dup:
        cmd += ['--dup', dup]
    if os.environ.get('MC_SAVE_TEXT') == '1':      # testo generato in <corsa>/testi/ (mai il prompt)
        cmd.append('--save-text')
    print(f'== {tag}: {env}', flush=True)
    rc = subprocess.run(cmd).returncode
    print(f'== {tag} uscita {rc}', flush=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)
    Path(r'D:\ds4_work\strata\lab_locks\bench.lock').unlink(missing_ok=True)
print('== multichat finita', flush=True)
