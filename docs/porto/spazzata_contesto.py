"""
SPAZZATA DEL CONTESTO — dove cade davvero la velocita' quando il KV si RIEMPIE.

Perche' serve: tutta la campagna e' misurata a -c 10000 con un prompt da 64
token. L'utente ha dichiarato che la produzione e' "una chat vera fino a
100-150k". Fra le due cose non c'e' nessuna misura.

DISEGNO — e il punto che rende la spazzata onesta: alzare `-c` ALLOCA il KV,
non lo RIEMPIE. Con un prompt corto, `-c 131072` misurerebbe il nulla. Quindi
ogni braccio ha un prompt costruito per OCCUPARE davvero il contesto, tagliato
dal corpus di calibrazione IQ1 (prosa+codice+agente, gia' reso nel formato DS4).

Una variabile per braccio: la LUNGHEZZA DEL PROMPT. Resta fisso tutto il resto
(K=2, ASYNC=1, SLOT=380, W=0, -t 7) e la generazione a 300 token, cosi' il t/s
si legge nella convenzione nuova: "t/s @ 300 token, contesto occupato N".
"""

import io, os, subprocess, sys, time

SORG = (r'C:\Users\imanu\source\repos\moe-aggressive-commit\.codex_validate_g73'
        r'\gguf-tools\imatrix\dataset\rendered_prompts_nothink.txt')
FUORI = r'D:\ds4_work\llama_run'
BIN = r'D:\llama-overlap\build\bin\llama-cli.exe'
MODELLO = 'C:/ds4-models/DS4-0731-IQ2XXS.gguf'

# (etichetta, token di prompt voluti, -c da allocare)
BRACCI = [
    ('08k',   6000,  10000),
    ('32k',  28000,  32768),
    ('64k',  58000,  65536),
]
CAR_PER_TOKEN = 3.6      # stima grezza; il conteggio VERO lo stampa llama


def fai_prompt(nome, n_token):
    testo = io.open(SORG, encoding='utf-8', errors='replace').read()
    voluti = int(n_token * CAR_PER_TOKEN)
    while len(testo) < voluti:
        testo = testo + testo
    p = os.path.join(FUORI, 'ctx_%s_prompt.txt' % nome)
    io.open(p, 'w', encoding='utf-8').write(testo[:voluti])
    return p


def bat(nome, prompt, ctx):
    righe = [
        '@echo off',
        'set LLAMA_MAPPED_IBRIDO=1',
        'set LLAMA_REAP=0',
        'set LLAMA_CACHE_ESPERTI_SLOT=380',
        'set LLAMA_CACHE_ESPERTI_W=0',
        'set LLAMA_CACHE_ESPERTI_BATTITO=30',
        'set LLAMA_OVERLAP_K=2',
        'set LLAMA_OVERLAP_ASYNC=1',
        'echo === CONDIZIONI: braccio=ctx_%s -t=7 K=2 ASYNC=1 SLOT=380 W=0 ctx=%d n=300 === > %s\\ctx_%s_log.txt'
        % (nome, ctx, FUORI, nome),
        ('%s -m %s -c %d -ub 64 -b %d -np 1 -ngl 99 '
         '-ot "ffn_(gate|up|down)_exps\\.weight=CUDA0_Mapped" -t 7 --no-mmap --temp 0 '
         '-n 300 -no-cnv -f %s < NUL 1> %s\\ctx_%s_text.txt 2>> %s\\ctx_%s_log.txt')
        % (BIN, MODELLO, ctx, ctx, prompt, FUORI, nome, FUORI, nome),
        'echo EXIT=%ERRORLEVEL% >> ' + '%s\\ctx_%s_log.txt' % (FUORI, nome),
    ]
    p = os.path.join(FUORI, 'ctx_%s.bat' % nome)
    io.open(p, 'w', encoding='ascii', newline='\r\n').write('\n'.join(righe) + '\n')
    return p


if __name__ == '__main__':
    solo = sys.argv[1] if len(sys.argv) > 1 else None
    for nome, ntok, ctx in BRACCI:
        if solo and solo != nome:
            continue
        pr = fai_prompt(nome, ntok)
        b = bat(nome, pr, ctx)
        print('[%s] prompt %s (%.1f MB) -> bat %s' % (nome, os.path.basename(pr),
                                                      os.path.getsize(pr) / 1e6, os.path.basename(b)))
