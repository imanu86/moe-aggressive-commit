# MANDATO — la sovrapposizione CPU∥GPU dei due rami esperti (INGEGNERIA)

*Scritto il 6/8/2026 sera. Autosufficiente: contiene tutto quello che serve,
non va rilétto altro per cominciare. Il pricing completo, scritto dalla
sessione che ha fatto la giornata di misura, è in
`docs/porto/PRICING_OVERLAP_CPU_GPU.md` — questo mandato lo riassume e fissa
le decisioni.*

## L'obiettivo, in una riga

Nel decode, i 6 esperti di ogni strato MoE si calcolano oggi tutti sulla GPU
(serviti dalla cache in VRAM) mentre la CPU sta ferma: **dividerli fra i due
processori e calcolarli insieme, dentro lo strato**. Atteso: **12,3-12,6 t/s
dal 9,26 di riferimento (+33-36%)**, con tutti i termini del conto misurati.

## Il quadro in cinque numeri (tutti misurati, 5-6/8)

```
8,94-8,99 t/s   metro CON cache, riprodotto sei volte il 6/8 (storico 9,12-9,26)
   55 ms        la parte sovrapponibile del token: 39 trasporto + 16,3 calcolo GPU
   87           confini CPU-GPU per token nell'ibrido (2×43+1, contati dalla sonda)
  3,43 ms       il pedaggio VERO dei confini: risveglio+piano del pool
                (79 µs/confine, fascia condvar) — il polling può limarlo
  3,29 ms       le copie di attraversamento: STRUTTURALI, scalano coi BYTE
                non col conteggio (37,8 µs è una MEDIA: mai moltiplicarla
                per un conteggio diverso — si addebita il totale)
```

Il `sync` (44,5 ms nell'ibrido) è attesa di calcolo GPU vero, non pedaggio:
misurato col timer che separa sync da copie dentro gli ingressi.

## Il bloccante, verificato nel sorgente

- `ggml-cpu.cpp:207/208/399` → `.event_record = NULL`, `.event_wait = NULL`,
  `.events = false`: **il backend CPU non ha eventi**.
- Lo scheduler (`ggml-backend.cpp:1562-1575`) ripiega su
  `ggml_backend_synchronize` **bloccante** quando un backend non ha eventi. Lo
  scheduler NON è sequenziale in generale — lo diventa quando c'è la CPU.
- `ggml_backend_cpu_set_threadpool` esiste già: un pool persistente con spin è
  la via per portare il risveglio da 79 µs verso la fascia polling.

## LE DECISIONI GIÀ PRESE (non rilitigarle: ognuna ha una misura dietro)

1. **Split parametrico per residenza, non binario.** x = non-residenti dati
   alla CPU. L'ottimo è **x\*≈91-96 = ~66% dei non-residenti** (bilancio
   `0,242x = 7,2 + (144−x)·0,334`): né bilancio-FLOP (x=52, +8%) né residenza
   pura (x=144, +11%). E **x\* sale col tasso di colpi**: cache e overlap si
   COMPONGONO, la cache è il moltiplicatore della leva.
2. **Il ramo CPU legge dalla RAM. Mai far leggere la GPU dal bus a batch 1**:
   lo zero-copy puro (zero confini!) fa 6,35 t/s, 33 ms PIÙ LENTO dell'ibrido
   con 87 confini. Il pedaggio PCIe seppellisce qualunque risparmio di confini.
3. **`-t 7`, non 8**: un core resta a nutrire la GPU. Con 8 si misura peggio
   del vero (x\* scende a ~91, 11,5 t/s: due punti, ma il braccio va fatto
   giusto).
4. **Bit-esattezza comprata, non sperata**: i due rami restituiscono i **6
   risultati per-esperto** e il join li accumula **nell'ordine di indice
   originale** — identico a oggi per costruzione. Costo 0,16 ms/token (4,0
   MiB/token attraverso il join). Il join per-parziale è l'ottimizzazione DOPO,
   con la proprietà già in tasca.
5. **Il cancello SHA giusto**: uscita stabile fra ripetizioni della stessa
   config, e uguale al **braccio cache W=0** (il predecessore vero). **MAI
   pretendere SHA uguale al metro ibrido**: ha gli esperti su CPU e un ALTRO
   ordine di accumulazione legittimo — quel cancello ucciderebbe
   un'implementazione corretta.
6. **Ordine di costruzione: split sequenziale PRIMA, async POI.** Il pezzo
   async da solo non compra niente (a batch 1 il MoE sta tutto da una parte:
   niente da sovrapporre finché il grafo non ha due rami — stessa forma
   dell'errore del prefetch). Lo split sequenziale è bit-verificabile subito,
   senza eventi, e ha un guadagno proprio misurabile da solo: ~96 esperti
   spostati dal ramo che trasporta al ramo che legge dalla RAM = **−26
   MiB/token dal bus**.
7. **Il rischio tecnico dichiarato è lo split del `mul_mat_id` per residenza**:
   lo scheduler NON deve farsi dettare l'assegnazione dalla collocazione dei
   pesi (è il problema inverso del `supports_op` dell'ibrido). E la mappa di
   residenza e la decisione di routing devono stare **dalla stessa parte**: una
   traversata in più per strato costa +43 confini = +3,4 ms/token, un terzo del
   guadagno.
8. **La motivazione giusta**: la GPU è occupata il **96% del tempo** (misurato:
   il "6%" era intensità aritmetica, non occupazione). Il guadagno NON viene
   dal riempire vuoti sulla GPU — non ce ne sono — ma dallo **spostare lavoro
   sulla CPU che è ferma** e dal far **sparire** il trasporto dei non-residenti.

## Fasi e cancelli

**Fase 1 — split sequenziale.** Il grafo del MoE si spezza in due `mul_mat_id`
(residenti → GPU/cache, non-residenti scelti → CPU sui mappati), eseguiti in
fila, join per-esperto in ordine d'indice.
- Cancello A: SHA identico al braccio cache W=0 su 300 token, temperatura 0.
- Cancello B: contatore cache ~157/token sul ramo GPU (la parte residente
  della domanda), non ~17 (scavalcata).
- Misura attesa: il t/s può anche NON migliorare (i rami sono in fila), ma i
  byte sul bus devono scendere di ~26 MiB/token — si vede dalla sonda
  (`GGML_SCHED_PROFILO=1`, voce copie) e dal tempo del ramo trasporto.

**Fase 2 — sovrapposizione.** Eventi per il backend CPU (o pool persistente
con spin via `ggml_backend_cpu_set_threadpool`) perché lo scheduler non
ripieghi sul sync bloccante fra i due rami.
- Cancello: stessa bit-esattezza della fase 1, e il token scende verso
  79,5-81,3 ms. Ogni ms sopra: guardare prima i confini (sonda) e poi lo split.

## L'ambiente (non standard — ogni voce è una lezione pagata)

- **Worktree: `D:\llama-overlap`** (ramo `overlap`, creato da `jacobi`
  d4c4633). GIÀ PRONTO, con `build_cuda.bat` adattato dentro. Non toccare
  `D:\llama-dspark`.
- Dopo OGNI link: `editbin /STACK:67108864` (previo `vcvars64.bat`).
- `--no-mmap` obbligatorio col mappato; `LLAMA_MAPPED_IBRIDO=1` per l'ibrido.
- La cache: `LLAMA_CACHE_ESPERTI_SLOT=380`, `LLAMA_CACHE_ESPERTI_W=0`,
  `LLAMA_CACHE_ESPERTI_BATCH` (tetto token/passaggio, difetto 8),
  `LLAMA_CACHE_ESPERTI_BATTITO=5` nelle run corte.
- La sonda: `GGML_SCHED_PROFILO=1`, stampa ogni 50 grafi su stderr con
  `di cui sync`. Le stampe sono CUMULATIVE: usare la **finestra marginale**
  fra due stampe lontane dal transitorio (i primi grafi portano ~11 s di
  spillover del prefill + primo tocco delle 74 GiB mappate).
- Modello: `C:\ds4-models\DS4-0731-IQ2XXS.gguf`. Config di riferimento:
  `-c 10000 -np 1 -ngl 99 -ub 64 -b 64` + `-ot "ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped"`.

## Protocollo macchina e report

**`docs/porto/PROTOCOLLO_MACCHINA.md`, vincolante.** In sintesi: nessuna build
o run senza `[RICHIESTA MACCHINA]` alla sessione coordinatrice
(`local_1c34df6e-b359-4454-9f30-2ea9f48b0bb4`) e relativo `[MACCHINA A TE]`;
compilare È usare la macchina; report continui con i numeri; ledger per ogni
run; il dubbio si passa all'altra sessione.

## Contesto largo (per non ri-derivare)

Sei leve di parallelismo speculativo sono morte su questa scheda (speculazione
batch-8, drafter CPU, lane G132, DSpark, Jacobi/lookahead, catena K=2 a
n-grammi): il verdetto e le ragioni in `docs/porto/JACOBI_VERDETTO.md`. La
strada parallela di RICERCA (testa addestrata, p1>0,56) è di un'altra sessione:
se i due cantieri si toccano (es. colpi della cache a batch 2), il punto di
contatto passa dal coordinatore. Ledger completo: `docs/porto/LEDGER_RUN.tsv`
(118 righe). Righe chiave: LLAMA_SONDA_CONFINI, LLAMA_PEDAGGIO_SCOMPOSTO,
LLAMA_CACHE_CONTIGUITA_FIX, LLAMA_CURVA_BATCH_VERA, LLAMA_GPU_DURANTE_DECODE.
