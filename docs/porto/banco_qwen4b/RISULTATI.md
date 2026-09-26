# Qwen3.5-4B sulla RTX3060: risultati kernel e MTP

## Decisione

- **MTP standalone funziona e accelera alcuni workload misurati.** La testa e pronta, il modello target non e stato modificato.
- **Kernel OCC12 respinto per l'uso quotidiano:** correttezza dei test preservata, ma nessun guadagno netto e regressioni nei casi tool.
- **Daily preservato:** runtime originale, Qwen3.5-4B Q4_K_M, porta8100, thinking acceso, senza MTP. Nessuna promozione automatica.
- Questo lavoro non riduce il modello. La testa MTP aggiunge660602592byte. Pruning REAP35B e vision restano progetti distinti.

## Ambiente e metodo

RTX3060 12GB, RAM96GB. Target2740937888byte, SHA256 `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`.
Runtime originale `D:\ds4_work\bin_q36m3`, contesto131072, KV Q8_0, batch2048/ubatch512, uno slot.
Test su porte locali isolate8114/8115, nessun comando reale Cockpit o telefono. GPU serializzata, nessuna compilazione concorrente nei benchmark riportati; Nsight separato dalle misure prestazionali. Desktop e applicazioni gia aperte non sono stati chiusi: rimane variabilita del sistema.

Greedy e thinking-off usati per confronto differenziale, non per cambiare il daily. Test thinking-on separato. Tre ripetizioni salvo smoke100k; i tre turni warm appartengono a UNA conversazione, non a tre sessioni indipendenti. Median e range nei JSON. Nessun intervallo di confidenza inferenziale.

La latenza qui e dalla richiesta HTTP alla risposta/chiamata completa generata. NON include l'esecuzione di MCP o azioni sui dispositivi.

## Risultati principali

| Prova | Baseline | MTP | Esito |
|---|---:|---:|---|
| tool_batch breve, MTP1, 3rep | 65.52t/s | 86.28t/s | output identico |
| tool_batch breve, MTP8, 3rep | 66.55t/s | 144.54t/s | 3/3 output identici e corretti |
| stessa prova: chiamata completa | 1.3595s | 0.8211s | rapporto1.656x; circa40%meno tempo |
| 102827token, cold smoke, MTP8 | 32.44t/s | 81.50t/s | output identico e corretto, n=1 |
| stesso cold smoke: richiesta totale | 82.07s | 88.97s | MTP PEGGIORA il primo turno |
| contesto103013-103385token, 3turni warm, MTP8 | 35.73t/s | 81.29t/s | output identici e corretti |
| stessi turni warm: chiamata completa | 2.4342s | 1.6666s | rapporto1.461x; circa31.5%meno tempo |
| stessi turni warm: primo delta tool | 0.7298s | 1.0110s | MTP PEGGIORA l'avvio dello stream |
| retry thinking-on, 3rep, MTP8 | 3.0208s /67.78t/s | 2.2103s /94.82t/s | chiamata corretta in entrambe; ragionamento diverso |

Il costo aggiuntivo del prefill MTP spiega perche decode piu rapido non significa sempre primo turno piu rapido. Nel warm test il server riusa102823/103009/103195token e processa190token nuovi a turno; il contesto occupato resta oltre100k. La cache NON e stata simulata con prompt corti.

La VRAM totale all'avvio del test MTP8 era10512MiB, desktop incluso: non e una misura del picco durante prefill, ne del solo modello. Non sono state provate immagini/vision.

## Correttezza: cio che abbiamo e non abbiamo provato

- Rebuild CUDA senza patch:15/15 output identici all'originale, prestazioni sostanzialmente in parita nel primo gate.
- MTP1:15/15 output identici sui cinque casi iniziali. Non e una prova universale di equivalenza.
- MTP2/3:12/15 identici; divergenza greedy sulla prosa in tutte e tre le ripetizioni. Causa numerica vs rollback ancora irrisolta.
- MTP8 thinking-on: anche il ragionamento diverge (187vs182token nel retry), pur producendo la stessa azione corretta. Nessun claim lossless.
- `tool_retry` thinking-off aggiunge un argomento errato anche in baseline. Il confronto identico non implica correttezza funzionale. Thinking-on corregge questo specifico caso in entrambe le varianti.
- Il runtime riporta probabilita placeholder per token speculativi: i logprobs MTP non sono prova di equivalenza. Vedere `../banco_qwen4b_mtp/DIVERGENCE.md` e il probe nativo preparato ma NON eseguito.
- Nessun confronto completo di logits/stati ricorrenti; nessun test sistematico di problem solving web, vision o tutti i casi di rollback. Il piano di dominio e `DOMINIO_COCKPIT_JEV2.md`.

## Testa MTP

`D:\models\qwen35-4b\Qwen3.5-4B-MTP-Q8_0-head-original-Q6_K-embedding.gguf`

SHA256 `4e1dfbc30b1c1d8b2861be93fb14e5ae0f2481df347f4484df763c347cea26e7`.
17tensori:15head Q8/F32 piu embeddingQ6_K e normF32 copiati dal target, tokenizer invariato.15test CPU e lettura indipendente superati. Donatore Unsloth pinned; nessun confronto numerico con checkpointBF16 ufficiale. Nessuna patch al runtime necessaria per questa configurazione standalone.

Bozze1/2/3/4/6/8 provate. Sul singolo caso tool breve,3/4/6 circa109t/s e8 circa145t/s; non generalizzare questa classifica alla prosa o ad altri siti.

## Kernel: esperimento isolato, esito negativo

Profilo originale Nsight: MMVQ quantizzato circa83% della somma dei tempi kernel; Q4_K fused sullo shape9216x2560 circa28.1%. Somma tempi kernel non equivale necessariamente a quota del wall-clock.

Patch defaultOFF `GGML_CUDA_QWEN4B_Q4K_OCC12=1`, solo sm86/dense/Q4_K/fusedSwiGLU/colonna singola/shape esatto. Cambia launch_bounds min_blocks12, non algoritmo matematico. Non interessa direttamente la verifica MTP multi-token.

- Unita GPU:12fixture, output bit-identici/max_abs0, registri53->40, blocchi teoricamente residenti9->12, zero spill.
- Runtime OFF/ON/OFF:15/15 output identici. ON tool_batch68.21t/s vsOFF73.69/72.39; prosa68.65vs68.64/71.40. Nessun vantaggio stabile. Non attivare nel daily.
- ABI identica:11export e import compatibili. DLL candidata SHA256 `1798a55bb05fa852f8734f4f4c51e472a21d79536e29aef1a1d93bb07b335253`.
- DispatchON verificato:18374lanci effettivi con min_blocks12,grid9216/block32x4,40registri. Mediana del singolo kernel profilato89.374us vs96.990us nel profilo originale, MA finestre/profiler diversi e il runtime non profilato perde: il verdetto resta negativo. Vedere `../banco_qwen4b_kernel/FINAL_RESULT.md`.

## Riproduzione e sicurezza

`run_variant.py` si rifiuta di partire se esiste qualsiasi llama-server; non lo arresta. La sospensione del daily e il ripristino sono responsabilita del coordinatore. Esempi da eseguire SOLO dopo aver chiuso esplicitamente il daily:

```text
python run_variant.py --label baseline --out D:\ds4_work\nuovo_test_baseline
python run_variant.py --label mtp8 --draft D:\models\qwen35-4b\Qwen3.5-4B-MTP-Q8_0-head-original-Q6_K-embedding.gguf --draft-max 8 --out D:\ds4_work\nuovo_test_mtp8
python run_variant.py --label warm --case tool_batch --multi-turn --repeats 4 --long-tokens 102400 --out D:\ds4_work\nuovo_test_warm
```

Ogni directory output deve essere nuova. Il runner conserva hash, flag, risposte, metriche, log e conferma shutdown. Il finally copre errori ordinari; una terminazione brutale puo lasciare figli: controllare il PID registrato prima del ripristino. Nessun kill indiscriminato.

Ripristino daily: lanciatore Desktop `Qwen 4B - DSH Cockpit - 128k.bat`, non il vecchio Ling. Le credenziali non sono nei report o negli script del banco.

## Evidenza locale

Root `D:\ds4_work\qwen4b_campaign`:

- `clean_original_a`, `clean_rebuild`, `clean_original_b`, `clean_mtp1/2/3` e relativi confronti;
- `tool_sweep_0/3/4/6/8`, `tool_sweep_8-comparison.json`;
- `long102k_0/8`, `long102k_8-comparison.json`;
- `warm102k_0/8`, `warm102k-comparison.json`;
- `kernel-unit.txt`, `kernel_off_a`, `kernel_on`, `kernel_off_b` e confronti;
- `thinking_retry_0/8` e confronto;
- `nsys_original`, `nsys_occ12_on` (solo diagnostica, non benchmark).

Benchmark HTTP:7test CPU superati, compreso storico multi-turn con risposte tool simulate. Corpus1000, pruning35B, n-gram e vision non avviati da questi script.
