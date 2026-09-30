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

## Idee dell'utente da valutare
- Gli esperti che restano fissi in VRAM non tengono la copia in RAM (oggi l'arena in RAM li contiene tutti: ~10,6 GiB
  di doppione con questa cache); chi esce si rilegge dal disco.
- Con l'OCuLink: la 2080 Ti piena e fissa (~20 strati interi, 865 MiB per strato: niente scambi ne' PCIe, link x4
  irrilevante, niente copia in RAM per quegli strati) e la 3060 sul PCIe 4.0 x16 con la cache che ruota per gli altri
  ~28 strati. Da verificare: quota PCIe e scambi per scheda nella 0.1.21; il layer split spegne il KV streaming.
