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

## Da fare
- Nessun controllo durante un prefill lungo (131k ≈ 4-5 minuti): la coda e' prestata; un restringimento li' va studiato.
- La VRAM «libera» e' `cudaMemGetInfo`; il budget WDDM (DXGI) del nostro M2 sarebbe una lettura migliore.
- A/B a regime contro la cache fissa senza pressione (profilo `regime`), e con Jump Desktop acceso.
