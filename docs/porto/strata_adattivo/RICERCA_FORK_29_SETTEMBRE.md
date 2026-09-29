# Fork, PR e novita' dell'originale — 29 settembre 2026

Letture via API (nessun codice di terzi eseguito). Fonti: 41 commit dell'originale dopo b38c183, PR #16 #37 #38 #41 #52
#80 #83 #84 #89 #102, 14 fork con commit propri su 136 (`../strata_prova/fork_avanti_29settembre.json`).

## Originale, 0.1.19 → 0.1.21 (29/9)
- `--calibrate` (0.1.19) misura una volta `--pcie-frac`, `--spec-min-p`, `--pool-workers`; tiene guadagni sopra il 3%.
- Probe della banda host→GPU all'avvio (da 20 GB/s in su `pcie_frac` resta 0,55; sotto 4 GB/s tutto alla CPU).
- Percentuale di colpi in cache per richiesta (#69) e ritentativi della `cudaMalloc` della cache a 3/4 (fino a 8 volte).
- 0.1.20: punti di ripresa in LRU con la radice fissata, punto di ripresa alla fine del system prompt.
- 0.1.21: layer split su 2-3 GPU (build `-DSTRATA_EXPERIMENTAL_SM75=ON` per Turing, cioe' la 2080 Ti), ma **spegne il KV
  streaming**: la KV intera su ogni scheda, in conflitto con 250K sulla 3060.
- Invariati: adattamento (ogni 4 round, max 96 scambi, soglie 2,0 / +1,5 / decadimento 0,7 fisse nel codice, senza
  opzioni), KV streaming, limite di 262.144 token. **Il difetto dei punti di ripresa con blocchi da 6.144 non e'
  corretto**; rimedio senza patch: `--prefill 8192` esplicito. Cache di piu' conversazioni: in lavorazione (issue #57).

## Cache elastica: nessuno l'ha fatta funzionare
PR #37 (code-martin, un commit, fermo 85 commit indietro): `CUDA::cuda_driver` in CMake, `cuMemAddressReserve` della
dimensione di AVVIO, blocchi da 2 MiB con `cuMemCreate`/`cuMemMap`/`cuMemSetAccess`, ripiego su `cudaMalloc`; resize solo
fra una richiesta e l'altra con comandi RESIZE/GROW. Difetti (confermati dal codice): non cresce oltre l'avvio, ricopia la
residenza di avvio sopra `host_res` (esperti sbagliati dopo l'adattamento), toglie gli slot prestati al prefill.
Da riusare: solo le chiamate VMM e il link CMake. Attenzione: su Windows anche la VRAM cosi' allocata pesa sul commit di
sistema; la VRAM «libera» e' affidabile solo dopo aver scritto le pagine; blocchi da 2 MiB = migliaia di handle.

## 250K: il fork RX5950XT (stesso file GSQ-RCO IQ3_XXS)
5060 Ti 16 GB (x8), Ryzen 7 5700X, 96 GB DDR4-2133, motore prima della 0.1.15. `--kv int8` senza `--kv-resident` (tutta
la KV in VRAM), riserva 700, `--spec 4 --spec-min-p 0.5`, `--mtp-window 65536` (+4% a 131K), `--prefill 8192` (+33% di
prefill a 32K rispetto a 4096). Configurazione 200K: 3.823 slot, 35-40 t/s fino a 64K, 33,9 a 204K. Configurazione 262K:
3.303 slot, 31,9 t/s a 261K, prefill 399, primo token dopo 655 s, **RAM di picco 78-80 GB**. Pinnata: la registrazione
intera fallisce, 48 fette (39 GiB) a pagine da 4 KB. Tetto della RAM pinnata ~78 GiB su 96 GB. Seconda GPU in un
processo separato (due contesti nello stesso processo contano la pinnata due volte): +12-32% di decode.

## Audit StrataGP (solo stime, sulla stessa base b38c183)
Round da 34,3 ms su 5070, 13,4 ms di esperti CPU. Per AVX2/12 GB: pool CPU sbilanciato (+5-8% sul tempo CPU degli
esperti), **detokenizzazione O(n²) nel server (2,2 ms/token a 16K)**, indexer QSA in FP32 (201 MB/token a 128K), refill
bloccante degli slot prestati (~180 ms), blocchi da 6.144 contro 8.192 con divergenza KL 0,33 (sospetto difetto al confine
dei blocchi). Nessuna misura su GPU.

## Multi-GPU
13600k: cache complementari sulle GPU secondarie, fisse all'avvio, mai eseguito. rhgo1749: un processo per GPU per
richieste in parallelo (Linux). PR #16 (GPU helper come cache esperti) e' entrata nella 0.1.21.

## Altre PR
#41 (conversazione principale conservata durante le chiamate ausiliarie, bozza, assorbita da #57), #102 (guardia RAM/VRAM,
bozza), #80 (esperti su tre livelli VRAM/RAM/SSD, solo Linux, ~53 t/s con 32 GB), #84 (YaRN oltre 262K), #83 (tempi in
stile llama-server), #89 (con MSVC letture a blocchi da 4.095 byte: avvio da 1.249 s a 72 s con la lettura in blocco).
