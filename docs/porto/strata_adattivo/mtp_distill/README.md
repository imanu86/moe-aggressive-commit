# mtp_distill — affinamento del layer MTP (testa di bozza) di Qwen3.8-Flash-Next per Strata

Obiettivo: accettazione delle bozze MTP da ~65-70 % a ≥ 75 % (oggi 1,7-2,0 token per finestra con `--spec 4
--spec-min-p 0.5` e draft vocab `rt_it48k`), quindi +4-8 % di t/s, con una distillazione sulle conversazioni
dell'owner (riferimento: ursuciprian/qwen3.8-flash-next-dgx-spark-tp-2 #97, stesso modello).  Il lavoro gira **in
locale, in una notte, a 0 $** (`RUNBOOK_LOCALE.md`); il pod resta l'alternativa (`RUNBOOK_POD.md`, A100 80 GB).

## La catena

| Passo | File | Dove gira | Stato (12/10) |
|---|---|---|---|
| 1. Corpus dalle conversazioni (Claude Code, Codex, DSH), bonificato | `build_corpus.py`, `scrub.py` | PC | **fatto** sui dati veri (§ numeri) |
| 2. Sequenze di token col template del server | `render_sequences.py` | PC | **fatto**: 3,5M token in `D:\ds4_work\mtp_distill\seqs` |
| 3. Cattura del target (residui finali + top-20) | hook C++ `STRATA_MTP_CAPTURE` nel fork, branch `lab/mtp-capture` (`91dbf2ed`, `c3148e62`); `capture_driver.py` | PC, due schede | **fatto e provato**: 1,03 M token a **427 tok/s** dal prefill (pilota); dati coerenti |
| 4. Parità PyTorch ↔ motore | `parity.py` + dump `STRATA_MTP_DUMP` | PC | **verde**: argmax 100 % / 100 % / 95,5 % ai passi 0/1/2, KL 0,012 / 0,008 / 0,043 (34 richieste heldout) |
| 5. Training (KL top-20 srotolata, 4 passi) | `mtp_model.py`, `train_mtp.py` | 2080 Ti (fp16) | **fatto** sul pilota: 268 seq / 750 k token, 1 epoca, 25 min + eval |
| 6. Export nel formato del motore | `export_mtp.py` | PC | **provato**: il blocco originale riprodotto **byte per byte** uguale a `rt_it48k` |
| 7. Misura sul motore vero | `bench_pack.py` | PC | **preliminare** (corsa interrotta dal coordinatore subito dopo la scrittura del json; da rifare): 24 prompt heldout x 256 token greedy, `rt_it48k` accettazione 0,724, 2,24 token/finestra, 66,7 t/s; `rt_pilot` 0,795, 2,33 token/finestra, 70,1 t/s (+5 %); letture del prompt 2,8 s medi, nessuna attesa PLE |

Orchestrazione: `pilot_local.py` (cattura → eval → train → export, tabella del cancello) sotto `lab_run.py` (bench.lock).

### La cattura: dal prefill, testa e top-k su GPU

Il GGUF del target usa il tipo ggml 42 (`Q2_0`, proprio di Strata): né llama.cpp né gguf-py lo caricano, e il checkpoint
BF16 originale (~240 GB) darebbe residui di un tronco diverso da quello di produzione.  La cattura vive quindi nel motore.
Due vie: la prima versione leggeva tutto il prompt a finestre teacher-forced di 8 token (~160 tok/s in locale) e faceva
top-20 e log-sum-exp su 248k logit per token su un thread CPU (tetto ~500 tok/s).  Ora il percorso batched del prompt
(`Prefill::on_chunk`, lo stesso che passa le righe al drafter) consegna i residui finali di ogni chunk a
`MtpCapture::chunk`, che applica la testa otto righe per volta con i kernel della finestra (`Verifier::head_rows`) e fa
top-k e LSE sul device (`kernels/topk_lse.cu`); la coda del prompt (`--short-read`) passa dalle finestre come prima.
Misurato: 500-600 tok/s con una scheda, **427 tok/s** con la config del Daily a due schede (prefill + testa + copia).

### Il forward (da `src/core/mtp.cpp`, in `mtp_model.py`)

Cella i = (R_i, tok_{i+1}) a rope i → predice tok_{i+2}.  Embedding IQ3_S e testa Q5_K del GGUF; `fc_embedding`,
`fc_hidden` per flusso dopo una RMS su tutti i 10240 valori (default del motore); hyper-connection `gr_read`
(norma per flusso, `silu((w_down·xn)/hc)`, media pesata da `sigmoid(w_up·lo)`, inject) e `gr_write`
(`R += y · 2 sigmoid(inj/hc)`); attenzione densa causale GQA 24/2, head 256, rope neox parziale 64 con theta 1e7 (nessun
rope scaling: la config non ha `--rope-scaling`), q/k norm (1+w), gate `attn·sigmoid`; router softmax top-10
rinormalizzato (clamp 2^-14); 512 esperti SwiGLU 640 **Q2_0 dal pacco del motore** (congelati; righe gate/up
interleaved, come il blob del motore); esperto condiviso con gate scalare; mixer finale; testa sul sottoinsieme
`draft_vocab.bin` (48 542 token).  Le norme sono grezze nel checkpoint e `1+w` nel pacco (tutte).

Precisione: parametri f32; matmul in bf16 (Ampere+) o **fp16 su Turing** (la 2080 Ti non ha bf16) con GradScaler;
R, norme, softmax, router e accumuli degli esperti in f32.  La catena gira solo sulle **celle attive** (quelle che
predicono un token generato: ~1/4), a blocchi di 768 con backward per blocco (15,7 GiB sulla 2080 Ti).  Allenabili
88,9M (attenzione, router, esperto condiviso, le tre hyper-connection, fc, norme); congelati esperti, testa, embedding.

La parità con il motore (stessi ingressi: R catturata, token e bozze del motore dal dump) spiega il residuo con K/V
INT8 del drafter nel motore, attivazioni Q8 e R in bf16 nella cattura.

## Numeri del pilota (12/10, heldout per conversazione: 95 pezzi, 277 k token, 87 k celle generate)

Drafter attuale (`rt_it48k`), per passo 0/1/2/3:

| | acc greedy | offerte (p ≥ 0,5) | acc & offerte | campionata «think» (T 1, top_p .95, top_k 20) | catena greedy |
|---|---|---|---|---|---|
| esperti Q2_0 (il pacco) | 0,783 / 0,726 / 0,685 / 0,652 | 0,787 / 0,774 / 0,760 / 0,750 | 0,710 / 0,666 / 0,630 / 0,600 | 0,795 / 0,736 / 0,695 / 0,663 | 2,03 |
| esperti BF16 (diagnosi D) | 0,796 / 0,748 / 0,718 / 0,692 | 0,799 / 0,793 / 0,788 / 0,781 | 0,722 / 0,689 / 0,664 / 0,641 | 0,810 / 0,763 / 0,732 / 0,706 | 2,12 |
| **affinato, 1 epoca** (268 seq, 750 k token, lr 3e-5, accum 4) | **0,813 / 0,760 / 0,727 / 0,702** | 0,776 / 0,729 / 0,700 / 0,678 | 0,724 / 0,668 / 0,633 / 0,606 | **0,823 / 0,764 / 0,728 / 0,701** | 2,10 |

- Q2_0 costa 1,3 / 2,2 / 3,3 / 4,0 punti di accuratezza per posizione rispetto a BF16: non è il collo principale.
- Il training alza l'accuratezza di +3,0 / +3,4 / +4,2 / +5,0 punti (KL passo 0: 0,675 → 0,492) ma **abbassa le bozze
  offerte** (il drafter, allenato sulla distribuzione intera del target, è meglio calibrato e meno spesso sicuro oltre
  0,5): con il gate `--spec-min-p 0.5` il guadagno netto è +1,4 / +0,2 / +0,3 / +0,6 punti, catena +3,6 %.  Il cancello
  «+2 al passo 0» passa sull'accuratezza (greedy e campionata), non sulla metrica con gate.  Da provare: `--spec-min-p`
  più basso con il drafter affinato (bench sul motore), 2 epoche e il corpus intero (3,5 M), `--nll-weight`.
- Andamento in epoca (eval ogni 20 passi, acc passo 0): 0,783 → 0,808 → 0,811 → 0,813: la curva si appiattisce con il
  coseno del lr; più dati pesano più di più epoche (#97: la seconda epoca +0,9 punti).

## Numeri del corpus (solo conteggi; `D:\ds4_work\mtp_distill\corpus\corpus_stats.json`)

- 2 435 file letti (Claude Code 1 254 conversazioni, Codex 947, DSH 153) in 200 s; 20 duplicati scartati; 0 errori.
- 252 260 messaggi dell'assistente, 252 514 chiamate a tool, 253 791 risultati; 842M caratteri (527M di risultati).
- Quota di codice 0,915; italiano sul testo dell'assistente 0,85.  Bonifiche: 81 744 sostituzioni (nessun valore stampato).
- On-policy (generato da Qwen3.8): 9 conversazioni soltanto; il resto è testo di Claude/GPT (il target vi concorda al
  top-1 nel 40-44 % delle posizioni).  Nessun pensiero: resi con `<think>\n\n</think>`.

Render (`seqs/render_stats.json`): 1 197 pezzi ≤ 4 096 token, **3 503 405 token**, 851 551 generati (0,243).  Lo split
dell'indice (un pezzo ogni 33) mescola conversazioni fra train e heldout: usare `--split-by-conv 10` (heldout = 14
conversazioni, 95 pezzi).

## Limiti e scelte

1. **Off-policy**: i prefissi vengono da risposte di altri modelli.  La cattura passiva nel decode del serve (righe
   accettate: R e top-20 sui token generati davvero) darebbe dati on-policy a costo zero durante l'uso; training locale.
2. **Pensieri assenti** nel corpus.
3. Il motore esegue le proiezioni affinate in Q8_0 (errore 0,4-1,2 %) e gli esperti Q2_0 identici a quelli del training.
4. KL sul sottoinsieme del draft head (top-20 fuori dal sottoinsieme scartati e rinormalizzati).  `--full-head` per l'altra.
5. La cattura e il dump non sono nel Daily (build `be4cf1c`): servono il fork `lab/mtp-capture` e `build-mtpcap`.

## Dati e cartelle sul PC

`D:\ds4_work\mtp_distill\corpus\` (843 MB, bonificati), `seqs\` (3,5M token), `capture_pilot\` (1,03 M posizioni, 21 GB),
`capture_parity\`, `runs\pilot_ft1\` (pesi, eval, `rt_pilot` = il pacco), `work\` (log, cache, bench).  **Niente in git.**
Fork Strata: worktree `C:\Users\imanu\source\repos\Strata-wt\mtp-capture`, branch `lab/mtp-capture`, build `build-mtpcap\strata.exe`.

## Giro on-policy sul pod (12/10, H100)

`onpolicy_gen.py`: prompt dai punti in cui l'assistente inizia (contesto ≤ 2 000 token, tagliato a un `<|im_start|>`),
risposte di Qwen con `--batch 8` (BGEN), T 1.0 / top_p 0.95 / top_k 20, seed = numero della richiesta, max 512.
1 407 risposte, **479 093 token** generati in 58 min (115-178 tok/s aggregati; `--batch-mtp` non aiuta: 149 contro 162).
Cattura di prompt + risposta: 2,2 M token in 28 min.  Training: ripresa da `ft2_lr1e4`, lr 1e-4, 1 epoca su misto
(1 407 on-policy + 402 off-policy, quota 0,25), 416 passi, 20 min.

| acc passo 0 / catena | rt_it48k | ft1 | ft1b (= ft2_lr1e4) | ft2 (on-policy) |
|---|---|---|---|---|
| heldout off-policy (95 pezzi) | 0,781 / 2,014 | 0,821 / 2,137 | **0,829 / 2,155** | 0,824 / 2,134 |
| heldout on-policy (48 risposte di Qwen) | 0,791 / 1,986 | 0,819 / **2,046** | 0,814 / 1,993 | **0,821** / 2,020 |
| motore, 24 heldout greedy: accettate/offerte, token/finestra | 0,652 / 2,165 | 0,760 / **2,233** | 0,758 / 2,224 | 0,728 / 2,194 |
| motore, 16 fuori dominio (`ood_prompts.py`) | 0,699 / **2,377** | 0,769 / 2,279 | 0,782 / 2,223 | 0,791 / 2,251 |

Uscite identiche in tutti i bench.  Fuori dominio tutti i pacchi affinati offrono meno bozze e perdono 4-6 % di token
per finestra rispetto al blocco originale; il PC a 131k (B-A-B) non vede guadagno da `ft1`.  Ipotesi: contesti di
training ≤ 4 096 token.  Per un giro a contesto lungo servono render a 32-64k, cattura a quella lunghezza (≈ 20 KB/token
di residui: 64k = 1,3 GB a pezzo, conviene catturare solo le finestre generate più un campione) e un training con
attenzione a blocchi (flash/SDPA a chunk, K/V del drafter lunghi) e rope alle posizioni vere.
