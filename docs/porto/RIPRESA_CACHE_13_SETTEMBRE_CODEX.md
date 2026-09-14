# Ripresa Qwen38: cache esperti, 13 settembre 2026

Il divario «41% reale contro 75% simulato» del precedente handoff non e' confermato. Sul banco HTTP, con 64 slot e MTP spento, la GPU e il simulatore concordano su tutti i **36,913 piani** catturati: **zero differenze**, zero errori di struttura della traccia. Il tasso diretto, esclusi i primi 64 passi di ciascuna cache, e' **75.54568%**. La cache non presenta la perdita di colpi ipotizzata dal confronto con i byte PCIe.

## Misura alla pari

Modello, opzioni e binari sperimentali del handoff; contesto configurato 262144, prompt effettivo 100 token, generazione 768 token, greedy, 64 slot, sparse FA spenta, MTP spento. Endpoint locale dedicato 8110. Il contesto totale della richiesta e' 867 token: non e' una prova a 32k o 250k.

La nuova traccia registra il gruppo di cache (distinto a ogni ricreazione), strato, passo, numero di righe, ID del router, richieste uniche, miss e byte per esperto. Il simulatore riproduce tutti i passi, incluse le inizializzazioni, e conserva stati separati per gruppo. Il confronto conta un miss quando l'esperto non e' residente prima del piano.

| Campione | Richieste uniche | Miss GPU | Miss simulati | Colpi |
|---|---:|---:|---:|---:|
| Intera traccia, incluse inizializzazioni | 369831 | 94267 | 94267 | 74.51079% |
| Passi > 64 di ciascuna cache | 337470 | 82526 | 82526 | 75.54568% |

Il vecchio simulatore anticipava di un passo il decadimento: usava `step >> 6` dopo l'incremento, mentre CUDA usa il valore precedente. La nuova analisi usa `(step - 1) >> 6`. Sulle vecchie rotte la correzione cambia solo 42 miss: non spiega uno scarto di 34 punti percentuali.

## Difetto della diagnostica corretto

La DLL precedente `321BA4AC` accumulava correttamente i contatori nel kernel, ma tentava di stamparli ogni N chiamate CPU a `remap`. Il replay dei CUDA graph esegue il kernel senza attraversare quel contatore CPU. Infatti due richieste da 768 token non hanno stampato alcun report con N=4096. Inoltre la copia sincrona in quel punto poteva cadere dentro una cattura CUDA.

La stampa ora avviene dopo `ggml_cuda_graph_evaluate_and_capture`, fuori dalla cattura e anche durante il replay. **N adesso conta chiamate al backend CUDA, non piani MoE.** La stampa comprende anche il payload esatto degli esperti, sommando i byte specifici di ogni strato. I contatori esposti sono cumulativi sui gruppi attualmente presenti: rilascio/ripristino della cache cambia il campione.

La cattura dettagliata richiede `LLAMA_MOE_ROUTE_TRACE=<percorso JSONL>` e `GGML_CUDA_DISABLE_GRAPHS=1`. E' una diagnostica intrusiva, da non usare per giudicare la velocita'. `LLAMA_MOE_HIT_REPORT=256` e' stato verificato separatamente con i CUDA graph attivi: 7 report validi; ultima lettura 75.355% su 316350 richieste. Un punto coincide esattamente tra le due modalita': 208350 richieste, 50864 miss, 100916480000 byte di payload. Quindi il risultato non dipende dallo spegnimento dei CUDA graph.

## Correttezza e velocita'

| Corsa | Decode token/s | SHA256 testo, prefisso |
|---|---:|---|
| counter64_r1 | 24.68 | 6939b7fdf7f7 |
| counter64_r2 | 24.85 | 6939b7fdf7f7 |
| captured64_r1 | 17.92 | 6939b7fdf7f7 |
| graph64_r1 | 24.87 | 6939b7fdf7f7 |
| graph64_r2 | 24.88 | 6939b7fdf7f7 |

Tutte e cinque le uscite hanno 768 token e lo stesso testo, includendo il ragionamento. Le righe `counter64` usano la DLL precedente; `captured64` usa traccia dettagliata e CUDA graph spenti; `graph64` usa la nuova DLL con sola stampa periodica e CUDA graph attivi. Le velocita' non dimostrano un'ottimizzazione: la modifica riguarda l'osservabilita'.

## Traffico PCIe ancora da attribuire

La traccia completa conta 187,062,758,400 byte di pesi degli esperti (incluse inizializzazioni), circa 243.57 MB per token emesso. La seconda corsa di riferimento somma circa 413748 MB nei campioni dmon, ossia 538.73 MB/token. Il campionamento a 1 secondo include i bordi della richiesta e va considerato approssimativo: non e' una misura delimitata ai soli kernel degli esperti.

Il residuo non va trasformato in ulteriori miss. Va attribuito con una misura dedicata al trasferimento e alle altre operazioni. La cache KV mappata aggiunge traffico, ma un contesto di soli 867 token non giustifica da solo un residuo di circa 300 MB/token. Anche il grande tensore PLE da 26.82 GiB richiede solo poche righe per token. La disassemblazione del gather mostra una lettura `LDG.E.128` e scrittura `STG.E.128`: l'ipotesi di quattro letture scalari al posto di una vettoriale non e' sostenuta.

Prossimo passo utile: isolare il traffico PCIe del gather su un numero noto di miss, poi attribuire il resto dell'esecuzione. Non cambiare la politica di sfratto sulla base del vecchio 41%.

## Stato lasciato e riproduzione

Produzione invariata: `bin_prod/ggml-cuda.dll` SHA256 `481D89C6`, `bin_prod/llama.dll` `2D558CA0`. Il lanciatore desktop originale non e' stato modificato. La sparse FA non e' stata promossa. Il server locale della prova e' stato chiuso al termine.

Sperimentale: `build/bin/ggml-cuda.dll` `089296F7`, `llama.dll` `59A97335`. Modificati solo `source/ggml/src/ggml-cuda/moe-demand.cuh` e `ggml-cuda.cu`. Il piano e il kernel di trasferimento non sono stati modificati. Compilazione `ggml-cuda` riuscita; warning preesistenti sui valori infiniti in `common.cuh`.

La patch `cache_diagnostics.patch` e' relativa alla directory `source` e parte dallo stato `321BA4AC`. Copia di sicurezza dei sorgenti e della DLL precedente in `C:/Users/imanu/Documents/Codex/2026-09-13/rip/work/cache_a/backup_before_trace/`.

Analisi ripetibile dopo aver estratto `cache_evidence.zip`:

```powershell
python analyze_trace.py --trace trace64.jsonl --out replay.json --slots 64
```

L'analizzatore esce con errore se trova differenze o una traccia invalida. `cache_validation.json` contiene i totali per strato, tutte le misure e gli hash completi. `cache_evidence.zip` conserva la traccia originale, i campioni PCIe, le misure HTTP, il testo, i report e la patch. Strumenti e questo resoconto sono copiati anche in `docs/porto` del repository.
