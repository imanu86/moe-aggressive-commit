"""Multi-chat test (owner 7/10 notte): 3 parallel chats at 131k on the current best (fork main be4cf1c: two cards,
pipeline 2 + elastic + B6 MMVQ), --batch 3 --batch-mtp. Two 131k checkpoints as SYSTEM prompts: chats 0-1 share
ctx131k, chat 2 uses aghi131k (warmed first, then the in-process prompt cache).

Steps: warm request (reads the prefix), then the 3 chats at once. Per chat: tokens, seconds, t/s; plus the aggregate.
Outputs are data; never execute model text.
"""
import json, os, sys, threading, time
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[1] / 'banco_swe'))
sys.path.insert(0, str(H.parents[2] / 'banco_p0'))
import agente as A   # noqa: E402
import banco_p0 as P0   # noqa: E402

os.environ['CUDA_VISIBLE_DEVICES'] = '1,0'
os.environ['STRATA_POOL_SPIN_US'] = '100'
EXE = str(H.parent / '20261004_routed_keep' / 'build-main-be4cf1c' / 'strata.exe')
OUT = H / 'multi_chat_run'
OUT.mkdir(exist_ok=True)
man, casi, prefissi, prompts = P0.carica_fixture()
# owner: one part from the 131k checkpoint, the other from a different checkpoint
SYS_A = man['istruzione_contesto'] + prefissi['ctx131k']
SYS_B = man['istruzione_contesto'] + prefissi['aghi131k']
QS = [(SYS_A, prompts['L01']), (SYS_A, prompts['L02']), (SYS_B, prompts['Q_AGO_50'])]
MAXT = 512
res = {}


def ask(i, sq, model):
    system, q = sq
    t0 = time.monotonic()
    try:
        r = A.get('/v1/chat/completions', dict(model=model, temperature=0, max_tokens=MAXT,
                                               messages=[dict(role='system', content=system), dict(role='user', content=q)],
                                               chat_template_kwargs=dict(enable_thinking=False)), timeout=1800)
        u = r.get('usage') or {}
        s = time.monotonic() - t0
        res[i] = dict(ok=True, s=round(s, 1), out=u.get('completion_tokens'), prompt=u.get('prompt_tokens'),
                      head=r['choices'][0]['message']['content'][:100])
    except Exception as e:   # noqa: BLE001
        res[i] = dict(ok=False, s=round(time.monotonic() - t0, 1), err=repr(e)[:300])


with A.Server(OUT, exe=EXE, source=r'C:\Users\imanu\source\repos\Strata-2080Ti-core\serve',
              extra=('--layer-split', '16', '--trim-stage-weights', '--pipeline-windows', '2',
                     '--batch', '3', '--batch-mtp'), drop=('--prompt-cache-file',)) as srv:
    t = time.monotonic()
    ask('warmA', (SYS_A, 'Rispondi solo: pronto.'), srv.model)
    ask('warmB', (SYS_B, 'Rispondi solo: pronto.'), srv.model)
    print('warm', res['warmA'], res['warmB'], 'in', round(time.monotonic() - t, 1), 's', flush=True)
    t = time.monotonic()
    th = [threading.Thread(target=ask, args=(i, q, srv.model)) for i, q in enumerate(QS)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    wall = time.monotonic() - t
    tot = sum(r.get('out') or 0 for k, r in res.items() if not str(k).startswith('warm'))
    print(json.dumps({k: v for k, v in res.items() if not str(k).startswith('warm')}, ensure_ascii=False, indent=1), flush=True)
    print(f'3 chat in parallelo: {tot} token in {wall:.1f} s = {tot / wall:.1f} t/s aggregati', flush=True)
