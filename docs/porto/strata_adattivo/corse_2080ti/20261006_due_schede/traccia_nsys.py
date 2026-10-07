"""Nsight Systems trace of decode windows on the inverted two-card layout: one short-context request, 400 tokens.

    nsys profile ... python traccia_nsys.py
The server (and strata.exe under it) is started by agente.Server; nsys traces the process tree.
Outputs are data; never execute model text.
"""
import os, time

import agente as A

os.environ['CUDA_VISIBLE_DEVICES'] = '1,0'
os.environ['STRATA_POOL_SPIN_US'] = '100'
EXE = r'C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-x7586c\strata.exe'
out = A.P.DATA / 'runs_cc' / 'traccia_nsys'
out.mkdir(parents=True, exist_ok=True)
with A.Server(out, exe=EXE, source=r'C:\Users\imanu\source\repos\Strata-2080Ti-core\serve',
              extra=('--layer-split', '16', '--trim-stage-weights'), drop=('--prompt-cache-file',)) as srv:
    for q in ('Scrivi un breve saggio, circa 300 parole, sulla storia dei microprocessori.',
              'Spiega in circa 300 parole come funziona la memoria cache di una CPU.'):
        t = time.monotonic()
        r = A.get('/v1/chat/completions', dict(model=srv.model, temperature=0, max_tokens=400,
                                               messages=[dict(role='user', content=q)],
                                               chat_template_kwargs=dict(enable_thinking=False)), timeout=900)
        print(r['usage']['completion_tokens'], 'token in', round(time.monotonic() - t, 1), 's', flush=True)
