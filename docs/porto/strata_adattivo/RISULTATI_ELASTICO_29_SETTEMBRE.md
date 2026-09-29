# Cache esperti elastica su Strata — 29 settembre 2026

Patch `0003` del fork (commit 111fcf5 nel clone, su 0.1.21 + 0001 + 0002). Opzione `--elastic` (serve, una GPU).

## Come funziona
- **Arena**: intervallo di indirizzi riservato per tutta la VRAM (`cuMemAddressReserve`), memoria fisica a blocchi da
  64 MiB (`cuMemCreate`/`cuMemMap`/`cuMemSetAccess`). La base non si sposta mai; `slot_offsets()` ha capacita' riservata
  per ogni coppia strato/esperto, quindi i puntatori dati al pool, al prefill e alla tabella di residenza restano validi.
- **Verita' unica**: `host_res` (la tabella viva che anche l'adattamento scrive), mai la residenza di avvio.
- **Quando**: al punto sicuro della decodifica (finestra, commit, bozza e scambi adattivi finiti; dopo la misura dei tempi
  che la politica della bozza legge) ogni 1 s, e a ogni inizio richiesta (solo restringimento).
- **Restringe subito** sotto `--elastic-reserve-mib` (500): libera la coda; in ogni strato gli esperti della coda piu'
  caldi di 1 punto d'uso rispetto ai piu' freddi rimasti vengono copiati al loro posto (device→device), gli altri escono.
  Minimo 256 slot.
- **Cresce** dopo `--elastic-stable-ms` (5 s) con almeno 192 MiB oltre la riserva: i mancanti con uso ≥2 (come i
  candidati dell'adattamento), poi l'ordine del profilo; al massimo 512 MiB per passo, copie asincrone pubblicate come
  gli scambi (`apply_pending`). Se dopo la scrittura la VRAM non c'era davvero (WDDM), la crescita si annulla.
- **Prestito al prefill**: dopo ogni cambio si ripianifica con la regola di `plan_lend`; `Prefill::init` riceve
  `chunk_max` (8192 con prefill auto) cosi' il blocco torna grande quando la cache cresce. `lend()` pubblica prima gli
  scambi in volo; all'inizio di una richiesta la cache non cresce (la coda sta per essere prestata).

## Collaudo sotto pressione (`strumenti/prova_hog.py`, `strumenti/hog.cu`)
Una richiesta da 4.096 token (saggio in italiano, greedy); dopo 20 s dal primo token un altro processo occupa 2,5 GB di
VRAM per 60 s e poi li rilascia. Altri programmi a ~1,74-1,76 GB. t/s per finestre di 10 s:

| | 0-20 s | pressione (20-80 s) | dopo (90-130 s) | 4.096 token |
|---|---|---|---|---:|
| cache fissa (originale) | 28,9 / 34,1 | **15,2 16,8 15,1 16,9 19,6 17,3** | 25,1 27,9 28,5 30,7 31,1 | 170,2 s |
| cache elastica | 27,4 / 33,4 | **20,6 27,2 27,5 25,4 25,8 24,1** | 29,0 31,6 32,5 34,2 | **146,3 s** |

Elastica: 1.476 → 1.558 slot; alla pressione 1.219 → 886 → 548 → 256 in 4 passi (193, 203, 158, 108 esperti caldi
spostati), blocco di prefill 1.024 → 512; al rilascio +308 +306 +307 +305 +153 → **1.635 slot** (2,67 GiB), piu' di
prima. La cache fissa non cede nulla: Windows sposta in RAM parte della sua VRAM e la decodifica perde il 45% per tutta
la durata della pressione.

## Avvio prudente (fumo)
Con `--vram-reserve-mib 2000` l'avvio si ferma a ~1.080 slot (la lettura di Windows oscilla: 543 → 1.637 MiB liberi);
la cache elastica cresce dopo il carico e il blocco di prefill risale (prefill 292 → 404 t/s dopo la correzione di
`chunk_max`). Con la riserva di esercizio a 700 + 256 di margine si fermava a ~1.390 slot: portata a 500 + 192.

## A/B rapido a macchina quasi ferma (11:01-11:11, OktoCGControl e quasi tutto spento)
Profilo `rapido` (L01-L04 corti + C01 copia di codice, 1024 token), riserva di avvio 1393 per entrambi, altri
programmi a ~1,78 GB. Entrambi gli avvii hanno pescato il biglietto basso (Windows: 0 MiB liberi al primo tentativo →
1.477 e 1.452 esperti). L'elastica e' cresciuta dopo il carico (+194 → 1.646) e al prompt di C01 ha restituito 52 slot
(33 caldi spostati) quando la VRAM libera e' scesa sotto 500 MiB.

| ms per riga (t/s) | L01 | L02 | L03 | L04 | C01 copia | totale |
|---|---:|---:|---:|---:|---:|---:|
| cache fissa | 32,6 (25,8) | 36,1 (23,1) | 35,1 (23,3) | 34,4 (25,4) | **49,4 (18,5)** | 37,5 (22,7) |
| cache elastica | 33,2 (24,8) | 36,9 (22,3) | 35,5 (23,9) | 32,2 (26,7) | **32,5 (27,5)** | **34,2 (24,8)** |

Colpi in cache: fissa 65,9 / 62,3 / 66,7 / 55,7 / 59,9%; elastica 67,6 / 66,3 / 67,7 / 55,9 / 61,9%. Sui primi tre
casi pari entro il 2% (rumore), poi l'elastica vince: nel caso C01 la cache fissa ha pagato il 52% in piu' per riga
proprio dove l'elastica ha visto la VRAM stringersi e ha ceduto 86 MiB in anticipo (lettura, non provata dai log
della fissa: niente dice che Windows abbia spostato la sua VRAM). Totale -8,8% di costo per riga, +9% di t/s.

## Da fare
- Nessun controllo durante un prefill lungo (131k ≈ 4-5 minuti): la coda e' prestata; un restringimento li' va studiato.
- La VRAM «libera» e' `cudaMemGetInfo`; il budget WDDM (DXGI) del nostro M2 sarebbe una lettura migliore.
- A/B a regime contro la cache fissa senza pressione (profilo `regime`), e con Jump Desktop acceso.
