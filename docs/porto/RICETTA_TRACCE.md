# RICETTA — come si fa una traccia di stati e route (e come NON si fa)

*Scritta il 6/8/2026 notte, dopo che tre run a vuoto hanno riscoperto da capo
quello che la traccia del 5/8 già sapeva. Il costo della ricetta non scritta:
tre lanci, due bat rotti, un'ora. Chiunque debba produrre una traccia nuova
parte da qui.*

## Il principio, che non è ovvio

**Il dump vive nell'eval-callback, e nessun tool normale lo installa.**
`common_debug_cb_eval` (in `common/debug.cpp`, blocco `LLAMA_DEBUG_DUMP` alle
righe ~191-240) è dichiarato in `debug.h` e NON è referenziato da `llama-cli`
né da `llama-server`: lanciare quelli con gli env del dump produce **zero file,
zero errori** — tredicesimo strumento muto. L'unico binario che lo installa è
**`llama-eval-callback`**.

E `llama-eval-callback` **non genera: valuta un prompt**. Quindi la ricetta è
in due tempi:

1. **generare il testo** (llama-cli o server, temperatura 0, dominio voluto);
2. **rileggerlo come PROMPT** con `llama-eval-callback` e gli env del dump —
   ogni posizione del testo passa nel grafo e i tensori filtrati finiscono su
   disco, ubatch per ubatch.

La prova storica: `prompt_lungo.txt` (il ragionamento NeuraForge, 6.116
caratteri) è datato sei minuti PRIMA di `INDICE.tsv` del dump del 5/8 — era
l'ingresso della ricetta, non un residuo.

## Il comando (traccia di prosa del 6/8, replicabile)

```bat
@echo off
set "LLAMA_DEBUG_DUMP=D:\ds4_work\dump_prosa"
set "LLAMA_DEBUG_FILTER=ffn_(norm|moe_topk)-"
set "LLAMA_MAPPED_IBRIDO=1"
set "LLAMA_REAP=0"
set "LLAMA_CACHE_ESPERTI_SLOT=0"
D:\llama-dspark\build\bin\llama-eval-callback.exe -m C:/ds4-models/DS4-0731-IQ2XXS.gguf ^
  -c 4096 -b 4096 -ub 64 -ngl 99 -ot "ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped" ^
  -t 8 --no-mmap -f D:/ds4_work/llama_run/<testo>.txt < NUL
```

## Le quattro trappole, una per run bruciata

1. **`-b` è il batch LOGICO e deve coprire il testo intero**: eval-callback
   passa TUTTO il prompt in una sola `llama_decode`
   (`GGML_ASSERT(n_tokens_all <= cparams.n_batch)`, `llama-context.cpp:1800`).
   `-b 4096` con `-c 4096`; l'**ubatch** (`-ub 64`) resta piccolo e decide la
   taglia dei pezzi su disco.
2. **I bat si scrivono con CRLF**: con fine-riga LF le continuazioni `^` di
   cmd si rompono (exit 255, log mai creato).
3. **I `set` con pipe si QUOTANO**: `set "VAR=ffn_(norm|moe_topk)-"` — senza
   virgolette la `|` è un metacarattere anche dentro un set e spezza la riga.
4. **Da Git Bash niente `cmd.exe /c`**: MSYS converte `/c` in `C:\` e cmd
   parte interattivo senza eseguire nulla. I bat si lanciano da PowerShell.
   E `< NUL` sullo stdin, o llama entra in modalità interattiva fantasma.

## Come si LEGGE la traccia (lezioni già pagate, righe in `albero_unione_route.py`)

- Più chiamate per tensore: **concatenare NELL'ORDINE dell'INDICE** — la
  sequenza temporale è tutto.
- **`ffn_moe_topk` è una VISTA CON STRIDE**: le prime 6 righe di un argsort su
  256. Letta come contigua dà spazzatura plausibile (`passo = (size − ne0) /
  (ne1 − 1)`).
- Il cancello di ogni analisi: la pipeline senza maschera/modifica deve
  **riprodurre la curva nota** (codice: 258/446/751/1.244) prima che qualunque
  numero nuovo venga creduto.
- Chi RICOSTRUISCE le route invece di leggerle: il router DSV4 **non è**
  `top-k(W·h + bias)` (fedeltà 90,4%, non 100 — sigmoide con selezione a
  gruppi). Validare il ricostruttore prima di usarlo.

## Le tracce esistenti

| dove | dominio | contenuto | prodotta |
|---|---|---|---|
| `D:\ds4_work\dump` | CODICE (NeuraForge) | 1.678 token × 43 strati, `ffn_norm` + `ffn_moe_topk` | 5/8 20:17 |
| `D:\ds4_work\dump_prosa` | PROSA (saggio fenici) | ~2.000 token × 43 strati, idem | 6/8 notte |

Analisi che le consumano: `working_set_per_finestra.py`,
`albero_unione_route.py`, `warm_start_strati.py`, `maschera_e_parallelismo.py`
(tutte in `docs/porto/`, tutte con la variabile `D` in testa da puntare alla
traccia voluta).
