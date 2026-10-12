# mtp_distill — affinamento del layer MTP (testa di bozza) di Qwen3.8-Flash-Next per Strata

Obiettivo: accettazione delle bozze MTP da ~65-70 % a ≥ 75 % (oggi 1,7-2,0 token per finestra con `--spec 4
--spec-min-p 0.5` e draft vocab `rt_it48k`), quindi +4-10 % di t/s, con una distillazione sulle conversazioni
dell'owner (riferimento: ursuciprian/qwen3.8-flash-next-dgx-spark-tp-2 #97, stesso modello).  Il lavoro pesante
va su un pod RunPod per un giorno: `RUNBOOK_POD.md`.

## La catena

| Passo | File | Dove gira | Stato |
|---|---|---|---|
| 1. Corpus dalle conversazioni (Claude Code, Codex, DSH), bonificato | `build_corpus.py`, `scrub.py` | PC | **fatto e provato** sui dati veri (§ numeri) |
| 2. Sequenze di token col template del server | `render_sequences.py` | PC | **fatto e provato**: 3,5M token in `D:\ds4_work\mtp_distill\seqs` |
| 3. Cattura del target (residui finali + top-20) | hook C++ `STRATA_MTP_CAPTURE` nel fork, branch `lab/mtp-capture` (6e5b24f6); `capture_driver.py` | pod | hook **compilato in locale** (build-mtpcap, sm_75/86), **non eseguito** (bench.lock, VRAM piena); driver non provato contro un motore |
| 4. Training (KL top-20 srotolata, 4 passi) | `mtp_model.py`, `train_mtp.py` | pod (GPU) | forward trascritto da `src/core/mtp.cpp`; **selftest su CPU verde** (12/10, cattura finta, 2 passi, catena di 3, 2 thread, 1,3 min): carica i pesi veri, allena, valuta, salva |
| 5. Export nel formato del motore | `export_mtp.py` | pod/PC | **provato**: il blocco originale riprodotto **byte per byte** uguale a `rt_it48k` (dense.bin, dense.txt, experts.bin) |
| 6. Misura sul motore vero | `bench_pack.py` | pod | non provato (serve il motore) |

### Scelta della cattura: (a) Strata sul pod, non HF transformers

Il GGUF del target usa il tipo ggml 42 (`Q2_0`, proprio di Strata): né llama.cpp né gguf-py lo caricano, e il
checkpoint BF16 originale (~240 GB) non entra in una scheda e darebbe residui di un tronco diverso da quello di
produzione.  Strata già legge il prompt a finestre di verifica teacher-forced (`read_windows`, le stesse del
decode) e vi tiene `final_R_all()` (il residuo a 4 flussi che il drafter consuma) e `head_logits_`: l'hook copia
quelli, un thread di lavoro fa top-20, log-sum-exp e scrittura.  Con `--short-read 1000000000 --prompt-cache 0` tutto
il prompt passa dalle finestre (nessun prefill batched), così ogni posizione è coperta tranne l'ultima, che il render
riempie con un `\n` di coda.

### Il forward (da `src/core/mtp.cpp`, in `mtp_model.py`)

Cella i = (R_i, tok_{i+1}) a rope i → predice tok_{i+2}.  Embedding IQ3_S e testa Q5_K del GGUF; `fc_embedding`,
`fc_hidden` per flusso dopo una RMS su tutti i 10240 valori (default del motore); hyper-connection `gr_read`
(norma per flusso, `silu((w_down·xn)/hc)`, media pesata da `sigmoid(w_up·lo)`, inject) e `gr_write`
(`R += y · 2 sigmoid(inj/hc)`); attenzione densa causale GQA 24/2, head 256, rope neox parziale 64 con theta 1e7,
q/k norm (1+w), gate `attn·sigmoid`; router softmax top-10 rinormalizzato (clamp 2^-14); 512 esperti SwiGLU 640
**Q2_0 dal pacco del motore** (congelati, quelli che il motore esegue); esperto condiviso con gate scalare; mixer
finale; testa sul sottoinsieme `draft_vocab.bin` (48 542 token, come il motore).  Le norme sono memorizzate grezze
nel checkpoint e `1+w` nel pacco: export e modello lo rispettano.

Allenabili 88,9M (attenzione, router, esperto condiviso, le tre hyper-connection, fc, norme); congelati esperti,
testa, embedding, indexer.  `--no-train-fc` riporta al perimetro di #97.

## Numeri del corpus (solo conteggi; `D:\ds4_work\mtp_distill\corpus\corpus_stats.json`)

- 2 435 file letti (Claude Code 1 254 conversazioni, Codex 947, DSH 153) in 200 s; 20 duplicati scartati; 0 errori.
- 252 260 messaggi dell'assistente, 252 514 chiamate a tool, 253 791 risultati; 842M caratteri (527M di risultati).
- Quota di codice (argomenti tool + risultati + blocchi ```) 0,915; italiano sul testo dell'assistente 0,85.
- Bonifiche: **81 744** sostituzioni — chiave=valore 38 186, alta entropia 23 064, email 14 272, telefoni 3 724,
  righe .env 1 226, carte (Luhn) 1 061, Bearer 83, URL con password 37, JWT 34, OpenAI 19, GitHub 5, RunPod 4,
  IBAN 4, Netlify 4, AWS 3, HF 2, Telegram 2, PEM 1, codici fiscali 13.  Nessun valore stampato.
- On-policy (generato da Qwen3.8 via gateway/strata-local): 9 conversazioni soltanto; il resto è testo di
  Claude/GPT, ma il segnale di distillazione sono i top-20 **del target** su quel contesto (limite noto, § sotto).
- Nessun pensiero: Claude Code e DSH li salvano vuoti, Codex li cifra → turni resi con `<think>\n\n</think>`.

Render (`seqs/render_stats.json`): 1 197 pezzi ≤ 4 096 token, **3 503 405 token**, 851 551 generati (0,243);
heldout 36 pezzi (116 602 token); on-policy 195 597 token; claude 1,47M / codex 1,23M / dsh 0,80M; italiano 0,60
sul testo generato; round-trip della tokenizzazione esatto salvo il `\n` di coda.

## Prova in locale (CPU, `selftest.py`) — verde il 12/10

Cattura finta nello stesso formato dell'hook (R casuale, top-1 = token vero) → `train_mtp.py` 2 passi, catena di 3,
pesi veri → `export_mtp.py`.  Verifica che lettura, catena srotolata, perdita, metriche, salvataggio ed export
girino; non dice nulla sulla qualità (serve la cattura vera).  Corsa del 12/10 (2 sequenze × 48 token, 2 thread,
sotto `bench.lock`): modello pronto in 2 s (cache embedding/testa), eval iniziale + 2 passi + eval finale in 0,7 min
(11,5 s per passo, 47 token per sequenza, 44 celle valide × 3 passi), export in 20 s, 24 tensori toccati, `experts.bin`
copiato: **1,3 min in tutto**.  Profilo (`profile_step.py`, 16 token × 3 passi, 2 thread): forward 3,9 s.

Due giri rossi prima: non era compute ma un **ciclo infinito** — con finestre prese dall'inizio della sequenza nessuna
cella aveva `gen = 1`, la KL era zero senza gradiente e il ciclo di training faceva `continue` per sempre.  Corretto:
guardia `useful == 0` → stop con messaggio; le finestre di prova (`--max-len`, cattura finta) contengono token
generati; `--threads`; pesi f32 fuori da CUDA (i GEMM bf16 su CPU di PyTorch sono lentissimi).  L'identità
dell'export resta la prova forte: `export_mtp.py --check-against rt_it48k` → `IDENTICO` ×3.

Regola locale: niente lavoro pesante su CPU/GPU senza `D:\ds4_work\strata\lab_locks\bench.lock` (O_EXCL), rilasciato
subito dopo; i B-A-B dell'owner girano sulla stessa macchina.

## Limiti e scelte da decidere

1. **Off-policy**: i prefissi vengono da risposte di altri modelli; l'inferenza vede risposte di Qwen.  Il drafter
   impara comunque "da R del target alla sua prossima distribuzione", che è locale; #97 usava risposte del target.
   Se la cattura fosse veloce, un giro di generazione on-policy sul pod (prompt dell'owner, 1-2M token) è la mossa
   successiva (non nel runbook di oggi: 60-100 t/s single-stream = 5-9 h).
2. **Pensieri assenti**: i token di ragionamento non sono nel corpus; il drafter non vi si allena.
3. Precisione: il training usa pesi f32 e bf16 nelle matmul; il motore esegue le proiezioni affinate in Q8_0
   (errore ~0,4 % rel.; `export_report.json` lo stampa per tensore) e gli esperti Q2_0 identici a quelli del training.
4. KL sul sottoinsieme del draft head (i top-20 fuori dal sottoinsieme sono scartati e il resto rinormalizzato):
   coerente col motore; `--full-head` per l'altra scelta.
5. La velocità della cattura sul pod è una stima (300-600 tok/s); il runbook prevede la misura con `--count 30`.

## Dati e cartelle sul PC

`D:\ds4_work\mtp_distill\corpus\` (18 shard jsonl, 843 MB, bonificati), `seqs\` (3,5M token), `seqs_smoke\`,
`work\` (log, cache embedding/testa .npy, selftest, rt_identity).  **Niente di questo va in git.**
Fork Strata: worktree `C:\Users\imanu\source\repos\Strata-wt\mtp-capture`, branch `lab/mtp-capture` (da
`lab/candidate` 443ce1c9), build `build-mtpcap\strata.exe`.
