# Strata sulla RTX 2080 Ti 22 GB — 30 settembre 2026

Scheda montata al posto della 3060 (per ora da sola): RTX 2080 Ti, 22.528 MiB, compute capability 7.5, driver
596.21, PCIe 3.0 x16. I binari del 29/9 (Strata `build\strata.exe` e il daily `bin_elastico_m2\ggml-cuda.dll`)
contengono solo sm_86: sulla 2080 Ti non girano. Il daily non e' ancora stato ricompilato.

**Build:** `../strata_prova/build-strata-sm75.bat` → `D:\ds4_work\strata\Strata\build-sm75\strata.exe` (sm_75 + sm_86,
3 minuti, nessun errore; la build sm_86 resta). Serve l'opzione sperimentale dell'originale `STRATA_EXPERIMENTAL_SM75`:
Strata chiede sm_80 (tf32 mma nell'attenzione, conti bf16); su Turing il punteggio dell'attenzione passa a FMA FP32.

**Prova:** `strumenti/prova_sm75.py` (configurazione del confronto equo, riserva 1393, cache fissa, profilo `rapido`,
CPU di tutti i processi ogni 10 s). 17:35-17:42, OktoCGControl acceso, altri programmi 6.053 MiB di VRAM (la 2080 Ti
ora pilota anche lo schermo) e 1,26 core di CPU in media (0,68-3,34; niente compilazioni degli agenti).

- Sonda PCIe 13,1 GB/s → `pcie_frac` 0,28 (0,55 sulla 3060).
- Cache: 15,46 GiB liberi → 6.499 slot, poi «0 MiB liberi» (la solita lettura di Windows) → **6.532 esperti, 10,57 GiB**
  (3,4 volte la 3060); a carico finito 1.462 MiB liberi.

| ms per riga (t/s) | L01 | L02 | L03 | L04 | C01 copia | totale |
|---|---:|---:|---:|---:|---:|---:|
| 2080 Ti, cache fissa | 22,3 (37,7) | 23,1 (35,4) | 21,5 (38,8) | 22,1 (39,7) | 22,7 (37,1) | **22,4 (37,6)** |
| 3060 fissa, 29/9 quasi ferma | 32,6 (25,8) | 36,1 (23,1) | 35,1 (23,3) | 34,4 (25,4) | 49,4 (18,5) | 37,5 (22,7) |
| 3060 elastica, 29/9 quasi ferma | 33,2 (24,8) | 36,9 (22,3) | 35,5 (23,9) | 32,2 (26,7) | 32,5 (27,5) | 34,2 (24,8) |

Colpi in cache 86,1 / 88,4 / 89,3 / 73,1 / 77,3% (3060: 56-68%). Prefill 82 / 80 / 83 / 115 / **512 t/s** (C01: 8,4 s al
primo token; 3060 elastica 333 t/s). Strata ha usato 2,4 core di CPU in media (sulla 3060 5,3 sotto carico): con l'86-89%
degli esperti sulla GPU la corsia CPU ha poco lavoro. Momento e carico diversi dalle righe della 3060, ma la differenza
(−40% per riga, +66% di t/s) e' molto sopra il rumore.

## Il daily ricompilato per la 2080 Ti (stessi prompt, subito dopo)
`../daily_sm75/build_daily_sm75.py`: sorgente base di Codex (sola lettura) + i 3 file M2, opzioni CMake del build O2, sm_75,
7,5 minuti → `D:\ds4_work\daily_sm75\runtime` (produzione e bat intatti). M3: i suoi 3 file di `src/` sopra, solo
`llama.dll` ricompilata → `runtime-m3`. Lanciati con `strumenti/daily_rapido.py --runtime ... [--env K=V]`.

| t/s | L01 | L02 | L03 | L04 | C01 copia | totale |
|---|---:|---:|---:|---:|---:|---:|
| daily M2 (altri 4,2 GB di VRAM) | 16,0 | 16,2 | 15,9 | 15,9 | 6,9 | 12,4 |
| daily M3, `LLAMA_MOE_ELASTIC_MAX=140` | 19,6 | 21,2 | 21,0 | 19,2 | 8,4 | 15,6 |
| Strata 0.1.21 fissa (sopra) | 37,7 | 35,4 | 38,8 | 39,7 | 37,1 | 37,6 |

M2: la cache arriva a 184 slot per strato (~8.800 esperti) ma a ogni prefill si svuota a 0 e ricresce piano. M3 col tetto:
torna a 140 in un passo dopo il prefill (0,3 s), ma vuota; tiene la cache nel prefill solo per prompt piccoli (94 token
nuovi si', 188 no). Il caso copia resta il difetto noto del daily (8,4 t/s).

## Strata 0.1.29 + patch del fork (18:23-18:35, stessi prompt, CGControl acceso)
Clone portato sulla 0.1.29 con le 3 patch (`patches/su-0.1.29/`), `build-0129` (sm_75+86). Altri programmi 3,5-5,1 GB di
VRAM e 0,9-1,1 core di CPU (registrati). Prima B (il candidato), poi A e C per capire perche' B perdeva.

| motore | cache | ms per riga | t/s | colpi |
|---|---|---:|---:|---|
| 0.1.21 fissa, riserva 1393 (sopra) | 6.532 | 22,4 | 37,6 | 73-89% |
| B: 0.1.29 elastica, riserva di avvio 500 | 7.661 → 7.100-7.300 | 26,9 | 31,2 | 76-92% |
| **A: 0.1.29 fissa, riserva 1393** | 6.772 | **18,9** | **45,1** | 75-89% |
| **C: 0.1.29 elastica, riserva di avvio 1393** (esercizio 500) | 6.726 → 6.776-7.378 | 19,3 | 43,4 | 78-91% |

- **La 0.1.29 vale +19% per riga sulla 0.1.21** (22,4 → 18,9 ms); prefill del caso copia 512 → 662 t/s.
- **B e' una trappola dell'avvio, non dell'elastica:** con riserva 500 l'avvio scende a 0-33 MiB liberi prima di
  stabilizzarsi, e tutta la sessione resta lenta (prefill 22-50 t/s sui prompt corti, 110 sul caso copia contro 662).
  Probabile spostamento in RAM di allocazioni di Strata da parte di Windows, non provato. C, con la stessa riserva di
  esercizio (500) ma avvio a 1393, va come A. Regola: **avvio largo (1393), poi l'elastica cresce da sola**.
- C contro A: +2% per riga, dentro il rumore (testi diversi: C01 689/810 bozze contro 725/837), con 1-2 punti di colpi in
  piu'. A carico fermo l'elastica non paga e non costa; protegge quando gli altri programmi si prendono la VRAM (3060,
  29/9: 24-27,5 contro 15-17 t/s).
- **Configurazione migliore oggi: C** = `build-0129` + `--elastic`, riserva di avvio 1393.

## Cache a due zone (patch 0004, clone 30657c4; 19:00-19:03, stessi prompt)
Nucleo = i primi slot riempiti dal profilo (mai scelti dagli scambi, mai ristretti, mai prestati); coda =
`--elastic-tail-mib` (predefinito min(6144, meta' della cache)), l'unica che ruota, cala a passi di
`--elastic-shrink-step-mib` (1024) e si presta al prefill. Crescita sul minimo della finestra con margine = rumore
misurato; un calo entro 60 s da una crescita raddoppia l'attesa (fino a 8x), 5 minuti tranquilli la riportano a 1x.

Avvio: 6.759 slot → **nucleo 3.347 (5,46 GiB), coda 3.412 (5,46 GiB)**. Durante le 5 richieste: +276, −241 (100 caldi
spostati), +77 (con 1.205 MiB liberi: margine largo), poi fermo.

| | L01 | L02 | L03 | L04 | C01 | totale t/s |
|---|---:|---:|---:|---:|---:|---:|
| D: due zone | 45,3 | 41,2 | 43,1 | 46,9 | 46,5 (prefill 672) | **44,3** |
| A: fissa | 44,2 | 42,2 | 43,4 | 47,2 | 49,9 (662) | 45,1 |
| C: elastica | 43,5 | 41,4 | 44,0 | 45,3 | 43,5 (644) | 43,4 |

A regime le tre sono pari (entro il rumore). Resta un piccolo ciclo all'inizio delle richieste (+300/−240): a inizio
richiesta qualcosa occupa 300-500 MiB di VRAM in piu' (da capire: grafi delle finestre? punti di ripresa?).

## L'originale e i fork al 30/9 pomeriggio
Originale: da 0.1.21 a **0.1.29** in due giorni. Per noi: supporto ufficiale RTX 20 (0.1.27), cache su WDDM a passi da
1 GiB (0.1.28), risposte campionate fino al 40% piu' veloci (0.1.29), prompt 4-28% piu' veloci (0.1.25-26), modalita'
poca RAM (`--mmap-experts` anche per i pack nativi), prefetch delle righe i-quant sul percorso AVX-2 (la nostra CPU non ha
AVX-512). Fork (100 aggiornati dopo il 29/9, 7 con commit propri): niente su cache elastica o piu' conversazioni; utili
he-be (output vincolato a uno schema JSON), jielin99/Strata-codex (Responses API), tntcannon5000 (batch di esperti fra
richieste, concorrenza).

## Idee dell'utente da valutare
- Cache a due zone: nucleo fisso (i migliori, mai ruotati ne' svuotati, senza copia in RAM) + coda elastica di al
  massimo 6 GB, l'unica che ruota, cresce e cala a passi e si presta al prefill; il resto sulla CPU.
- Gli esperti che restano fissi in VRAM non tengono la copia in RAM (oggi l'arena in RAM li contiene tutti: ~10,6 GiB
  di doppione con questa cache); chi esce si rilegge dal disco.
- Con l'OCuLink: la 2080 Ti piena e fissa (~20 strati interi, 865 MiB per strato: niente scambi ne' PCIe, link x4
  irrilevante, niente copia in RAM per quegli strati) e la 3060 sul PCIe 4.0 x16 con la cache che ruota per gli altri
  ~28 strati. Da verificare: quota PCIe e scambi per scheda nella 0.1.21; il layer split spegne il KV streaming.
