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

## A/B rapido sotto carico (12:21-12:43, OktoCGControl acceso, l'utente al PC)
Stesso profilo `rapido`, stessa riserva di avvio (1393), prima l'elastica e poi la fissa. Altri programmi: 2.907 MiB di
VRAM al lancio dell'elastica, 2.146 al lancio della fissa. Durante l'elastica (12:31) la CPU era al 100%: Strata
riceveva ~5,3 core (vuole 7 thread del pool + quello principale), OktoCGControl ~1 core e ~10% del decodificatore video,
Jump Desktop ~7% del motore 3D. RAM disponibile 31-35 GB: il primo avvio ha caricato gli esperti a 0,10 GiB/s (398 s),
il secondo a 0,98 GiB/s. Sonda PCIe 23,2 e 20,3 GB/s (26,3 a macchina ferma).

Avvio: elastica 1.919 slot, blocco di prefill 4.096; fissa 1.732 slot (Windows: 0 MiB liberi al primo tentativo),
blocco 3.072.

| ms per riga (t/s) | L01 | L02 | L03 | L04 | C01 copia | totale |
|---|---:|---:|---:|---:|---:|---:|
| cache fissa | 85,4 (10,1) | 65,2 (12,9) | 61,7 (13,5) | 56,6 (15,2) | 51,8 (17,1) | 64,7 (13,2) |
| cache elastica | 48,2 (17,7) | 60,8 (14,0) | 86,0 (9,4) | 49,8 (17,3) | 61,4 (14,7) | **62,3 (13,7)** |

Colpi in cache: fissa 66,9 / 66,7 / 70,2 / 58,0 / 61,1%; elastica 73,0 / 69,7 / 73,2 / 62,2 / 64,7% (+3-6 punti con
300-500 esperti in piu'). Prefill: fissa 14 / 42 / 42 / 47 / 112 t/s, elastica 60 / 76 / 76 / 114 / 333 t/s (C01: 38,0 s
al primo token contro 12,9). Le prime due richieste della fissa sono state lentissime (61 token letti in 12 s, 8 generati
a 2 t/s): compatibile con Windows che sposta in RAM parte della VRAM di una cache partita a 0 MiB liberi, non provato.

**Lettura.** Sotto questo carico una riga costa quasi il doppio che a macchina quasi ferma (62-65 ms contro 34-37), con
qualunque cache. Fra le due, −3,7% per riga per l'elastica: sotto la soglia del 5% e dentro un rumore di ±40% per caso,
perche' il carico cambia di minuto in minuto (L01 85 contro 48, L03 61 contro 86). Il vantaggio netto qui e' il prefill:
3 volte piu' veloce sul prompt da 4k. Il blocco (4.096 contro 3.072) non basta a spiegarlo.

**Difetto: la cache elastica oscilla.** Con OktoCGControl la VRAM libera letta da `cudaMemGetInfo` si muove di ±200-300 MiB
in pochi secondi. In 13 minuti: 10 crescite (+57...+306 esperti, 1.172 in tutto) e 13 restringimenti (−42...−180 slot,
994 in tutto; 560 caldi spostati, 434 usciti); VRAM libera dopo ogni passo fra 303 e 856 MiB. Il margine di crescita
(192 MiB) e' piu' stretto del rumore e la crescita arriva fin sulla soglia di restringimento: ciclo limite. Non si vede
nel costo per riga, ma butta via esperti caldi e banda.

**Il collo sotto carico e' la CPU, non la cache** (ipotesi da provare): il pool di Strata vuole 7 thread + 1 su 8 core
fisici e la finestra aspetta il piu' lento; con 2-3 core presi da altri, un thread fermo dallo scheduler ferma la
passata. E' la F2b del piano.

## Il daily sugli stessi prompt (13:19-13:34, OktoCGControl acceso, agenti dell'utente al lavoro)
Il daily di produzione (runtime M2 `bin_elastico_m2`, llama.dll 5b219d21) col lanciatore di laboratorio
(`../strata_prova/avvia_daily_lab.py`: il bat letto senza modificarlo, porta 18110, `-c 139264` come Strata), profilo
`rapido`, e per la prima volta la CPU di tutti i processi campionata ogni 10 s (`corse_elastico/cpu_daily_m2_rapido_carico.jsonl`).
Al lancio: altri programmi 3.099 MiB di VRAM, 75,5 GB di RAM disponibile.

| t/s | L01 | L02 | L03 | L04 | C01 copia | totale |
|---|---:|---:|---:|---:|---:|---:|
| daily M2 | 13,7 | 7,0 | 3,9 | 6,8 | 5,6 | **6,2** |

Primo token 2,3 / 7,5 / 4,4 / 2,8 / 12,8 s (C01: 329 t/s di prefill, come la cache elastica di Strata). L04 ha chiuso a
686 token come Strata: stessa risposta.

**Carico degli altri (75 campioni):** 7,3 core in media (4,4-11,8): Jump Desktop 2,25, Defender 1,32, il compilatore C#
degli agenti (VBCSCompiler + MSBuild + dotnet) 1,25, claude 0,56, CGControl 0,40, node 0,37. Il daily stesso 3,0 core in
media (ne chiede 16). RAM disponibile fino a 0,7 GB: il daily tiene in RAM ~67 GiB (27,5 GiB sulla CPU con `--no-mmap`,
35,2 di esperti in RAM bloccata, 6 di deposito); Strata ~44 GB (la tabella PLE resta mappata dal file).

**Cache M2:** a 0 slot nel 34% dei campioni (47 slot per strato in media, massimo 75); svuotata a 0 sette volte
all'inizio di una richiesta (`workspace_change`) e tenuta giu' dalla RAM (252 `growth_blocked_ram`); il deposito RAM ha
riletto 2,2 GB di esperti dal disco (4.425 letture). E' il difetto del 28/9 sera (M2 a 7,09 t/s), corretto da M2g, che
pero' non e' in produzione.

## Confronto a tre (t/s di decodifica aggregati)
Non tutte le righe sono nello stesso momento: si confrontano solo i numeri sulla stessa riga.

| condizione | Strata | Strata elastica | daily llama |
|---|---:|---:|---:|
| 28/9 notte, PC libero, un motore dopo l'altro (`regime`) | 31,6 | — | 19,0 (M2g) |
| 28/9 sera, programmi aperti, stessa sessione | 19,55 | — | 7,09 (M2) |
| 29/9 11:01-11:11, quasi fermo (Jump Desktop ~2 core) | 22,7 | 24,8 | — |
| 29/9 12:21-12:43, CGControl (altri ~2-3 core, solo campioni a vista) | 13,2 | 13,7 | — |
| 29/9 13:19-13:34, CGControl + agenti che compilano (altri 7,3 core, registrati) | — | — | 6,2 |

**Lettura.** Le ultime due righe non sono alla pari: durante il daily la CPU degli altri era piu' carica (compilazioni
degli agenti), e per le corse di Strata ho solo campioni a vista. Gli agenti dell'utente lavoravano anche nelle corse
precedenti e possono averle falsate, soprattutto le differenze caso per caso sotto carico (±40%). Il crollo del daily
pero' ha una causa sua, che gli agenti non spiegano: la RAM esaurita dal suo stesso carico (~67 GiB) e la cache svuotata a
ogni richiesta. Da qui in poi ogni corsa registra la CPU di tutti i processi.

## Da fare
- Elastica senza oscillazioni: margine di crescita piu' largo del rumore misurato (massimo meno minimo delle letture
  recenti), crescita sul minimo della finestra e fino a riserva + margine, attesa crescente dopo ogni restringimento;
  lettura del budget WDDM (DXGI) come nel nostro M2.
- F2b: thread del pool e ripartizione CPU/PCIe adattivi alla CPU libera. Prima misurare la passata sotto carico:
  quanto aspetta il GPU il pool CPU.
- Nessun controllo durante un prefill lungo (131k ≈ 4-5 minuti): la coda e' prestata; un restringimento li' va studiato.
- A/B a regime contro la cache fissa senza pressione (profilo `regime`).
- Il campionatore della CPU (`strumenti/daily_rapido.py`, riassunto con `strumenti/cpu_altri.py`; eventi della cache
  M2 con `strumenti/eventi_m2.py`) anche nelle corse di Strata (`f0_profilo.corsa`), e Strata e daily
  alternati nella stessa sessione se si rifa' il confronto sotto carico.
