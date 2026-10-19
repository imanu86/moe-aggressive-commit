# Misure sullo stadio 0 (3060) per la stima 5060 Ti - 19 ottobre 2026

Risposta con numeri misurati alla contestazione dell'owner su `STIMA_5060TI_2026-10-19.md` (+5-10% «non supportato dai dati»).
Compilato no (nessuna build nuova: exe del Daily 0.1.45 `5dc49fe8`, sha verificato a ogni corsa), installato no, **provato si'** sulla
postazione. Tag: **M** misurato qui; **T** ricostruito su una traccia misurata (replay o modello); **E** estrapolato; **I** ipotesi
non verificabile oggi (nessuna 5060 Ti nel PC). Condizione di tutte le corse: **con Jump** (sessione 1 di Jump Desktop connessa, ma quasi
inattiva: CPU cumulata +0,2-0,4 s in tutta la serie), OktoCGControl aperta, 3060 con le sue app. I numeri assoluti e il costo del desktop vanno
letti «con Jump». Corse sotto `bench.lock` (una per volta, nomi `DET-ST0-*`, poll 0,2 s come `bench_fast.py`); `lab_locks\closed` (6/10) era
presente: ho seguito l'incarico del coordinatore, nessuna corsa fuori dal suo perimetro.

## 0. La cosa che cambia tutto: la config Daily 0.1.45 non e' quella della stima

Il motore, avviato con `strata-0145-daily.json` cosi' com'e' (ho solo cambiato porta e file di prefisso, copia in `20261019_stadio0\`), dice:

- `--pipeline-windows 2 is off: not with --batch slots`: **il decode del Daily e' seriale** (stadio 0, poi stadio 1, poi bozza e commit), non in pipeline.
- `elastic cache is not validated with --batch-groups; using fixed cache`: **cache dello stadio 0 fissa a 2 439 slot (3,40 GiB)**, non 3 526 -> 3 874-4 176 con l'elastica
  (la stima li prendeva da `replay_c1-daily`, che era senza `--batch`). Stadio 1: 7 554 slot (con la config senza `--batch` 8 956-9 145; DWM tiene 5 GB sulla 2080 Ti).
- La stima (e il suo 65,8/72,2 t/s) vive nella cornice «pipeline»: l'ho misurata a parte (variante senza `--batch`, §2b).

Quindi due cornici, misurate entrambe: **Daily batch** (cio' che l'owner usa) e **pipeline** (quella della stima).

## 1. Protocollo e limiti

Harness `st0_run.py` (stesso motore via `server.StrataEngine`, richieste dirette, niente HTTP): 1 riscaldamento ~1K, 5 letture fresche da ~5K (testo disgiunto), L01 a 131K
(lettura a freddo + decode 1024), poi L02-L04 sullo stesso prefisso in cache (decode 1024 ciascuna); temperatura 0, seed 73. Ogni braccio = un processo del motore. Env aggiunte
(identiche in tutti i bracci): `STRATA_DECODE_TIMING`, `STRATA_SPLIT_TIMING`, `STRATA_NO_LARGEPAGES`, `STRATA_ARENA_PIN_GIB=8`. Niente `STRATA_IQ_MT_MIN`, niente file di prefisso/cache su disco,
priorita' normale. Tempi per stadio dalle righe `strata serve: stage N` (differenze fra richieste) e `decode timing`; traccia di pipeline (`STRATA_PIPELINE_TRACE`, solo cornice pipeline);
tempo per fase del prefill (`STRATA_PREFILL_TIMING`, un braccio dedicato); traccia di instradamento (`--dump-routing`, un braccio dedicato); campionatore ogni 5 s (VRAM, clock, potenza 3060, CPU altrui, uso GPU per processo).

Limiti dichiarati:
- **B-A-B stretto sul solo consumo di VRAM non si puo' fare**: il dimensionamento automatico della cache non e' lineare (§3.1). Ho alternato i bracci (A=Daily auto, B=altre taglie) ma il fattore che separa i risultati e' il regime della 3060, non la taglia: lo riporto per regime.
- Scarto PLE: «PLE stage» (`gather` per finestra) 0,04 ms in tutti i bracci (soglia 0,6). «PLE bloccato >300 ms» in 5 richieste di decode su 57 (S3H2 L04, S5H3b L01, S5X1 L03, S5X2 L02, S5P2b L02): i tempi di stadio sono normali e le medie restano uguali
  (esplicita 3,1-3,3K, L01-L03: 55,3 t/s con tutte, 55,7 senza; 32,2 e 31,9 ms/finestra). Le tengo, dichiarate.
- Il Daily vero passa dal server HTTP (`generate_batched`, che per una richiesta sola ripiega sul percorso solo `GEN`): qui `engine.generate`; le chat singole del server (59,6-65,5 t/s a ~8K di contesto) non sono confrontabili con questi 131K.
- Il «closed» dell'app (OktoCGControl) **non e' stato misurato**: non l'ho chiusa (§4). Pronto `st0_desktop.sh` per l'owner.

## 2. Quota dello stadio 0 (punto 1)

### 2a. Decode a 131K, Daily batch (seriale) - M

Regime «veloce» della 3060 (spiegato in §3.1), L01-L03, ms per finestra:

| slot stadio 0 | n | finestra | tok/fin | ms/token | stadio 0 (attesa GPU + pool/piano) | stadio 1 | resto (bozza, commit) | **quota stadio 0** | hit % |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 138 | 3 | 39,9 | 1,80 | 22,2 | 20,9 (9,4 + 11,2) | 15,0 | 4,1 | 52% | 79,2 |
| 1 563 | 3 | 37,8 | 1,75 | 21,6 | 18,9 (9,2 + 9,4) | 14,8 | 4,1 | 50% | 81,9 |
| 1 800 | 8 | 37,3 | 1,81 | 20,7 | 18,2 (9,1 + 8,8) | 15,0 | 4,1 | 49% | 83,2 |
| 2 440 (Daily, solo se «veloce») | 4 | 35,5 | 1,84 | 19,3 | 16,3 (9,2 + 6,8) | 15,1 | 4,1 | 46% | 86,8 |
| 3 100-3 260 (`--expert-cache` esplicito) | 12 | 32,2 | 1,79 | 18,0 | 12,9 (9,7 + 2,5) | 15,2 | 4,2 | **40%** | 94,8 |

- Nel decode seriale lo stadio 0 e' **il 40-52% della finestra** (e lo stadio 1 il 38-47%); accelerarlo di niente (tetto) darebbe da +67% (cache 3,2K) a +85% (cache 2,4K) di velocita'.
- Per layer: 3060 **0,61 ms** (9,73 ms / 16 layer, attesa GPU), 2080 Ti 0,38 ms (12,3 / 32, testa inclusa): **1,6x**, non 1,18x come nella stima (nsys 0,73 vs 0,62). Nel prefill (§2c) stesso rapporto 1,6x.
- La parte CPU dello stadio 0 (pool + piano, esperti mancanti calcolati dalla CPU) vale 2,5 ms con 3,2K slot e 11,2 ms con 1,1K: e' li' che la VRAM compra tempo.

### 2b. Decode a 131K, cornice pipeline (quella della stima) - M + T

Variante senza `--batch`/`--batch-groups` (pipeline 2 finestre, elastica: 3 411-3 417 slot a freddo, poi 3,6-3,7K; stadio 1 8 956), due bracci (S5P2a, S5P2b: stesso risultato).
Decode 70,8 / 59,0 / 61,6 t/s (L01-L03; L04 82,5; ripetizione 70,7 / 56,3 / 65,9), cioe' la stima (65,8 / 72,2) regge come ordine di grandezza. Dalla traccia di pipeline (`pl_analyze.py`):

| | L01 | L02 | L03 | L04 (T~2,9) |
|---|---:|---:|---:|---:|
| periodo di finestra (ms) | 28,3 / 29,1 | 25,7 / 27,6 | 25,9 / 26,9 | 32,9 / - |
| S0 = durata dello stadio 0 (ms) | 12,4 / 13,0 | 11,1 / 12,0 | 11,4 / 11,9 | 15,6 |
| S1 (ms) | 17,6 / 18,2 | 15,6 / 16,2 | 15,7 / 16,6 | 22,7 |
| **stadio 0 esposto** E0 (ms, % del periodo) | 10,3 (36%) / 10,5 (36%) | 9,7 (38%) / 11,0 (40%) | 9,9 (38%) / 10,0 (37%) | 9,7 (30%) |
| finestre con stadio 0 nascosto (speculazione riuscita) | 27% / 30% | 25% / 23% | 23% / 27% | 42% |

- Lo stadio 0 resta sul percorso critico per il **36-40%** del periodo (la stima assumeva fresche 67-72% -> coerente: 70-77% esposte).
- Tetto (stadio 0 a costo zero, replay sulla traccia): **+43-49%** di velocita' (+32% su L04). Scala S0 x0,75: +8-9%; x0,5: +18-20% (T).
- Dentro S0 (media L01-L03): attesa GPU 10,6 ms + pool/piano 1,4 ms: la CPU pesa poco, **S0 e' quasi tutto tempo GPU della 3060**.

### 2c. Prefill - M

Tempo per fase (`STRATA_PREFILL_TIMING`, braccio S6T1: `--expert-cache` esplicito, 3 108 slot, chunk 7 936) e wall per stadio:

| lettura | stadio 0 (3060) | stadio 1 (2080 Ti) | totale | lettura |
|---|---|---|---|---|
| 131K a freddo (95,1 s) | GPU 92,5 s di cui 17,5 s di attesa («embed+steps»): **~75 s attivi = 79%** (4,4 s/chunk) | 17 chunk, 5,3-6,2 s ciascuno, **somma 95 s = 100%** (5,5 s/chunk) | 1 307 tok/s con `PREFILL_TIMING` acceso (altri bracci sani: 1 452-1 462) | **limite = stadio 1**; stadio 0 ha 21% di margine |
| 5K fresca (9,5-9,6 s) | wall 4,5-4,6 s (**47-48%**), di cui attesa righe PLE da SSD 1,9-3,4 s (non GPU) | wall 4,1-4,15 s (43%) | in serie, ~0,9 s altro | stadi non sovrapposti |

- Per layer-chunk (7 936 token): 3060 **0,275 s**, 2080 Ti **0,172 s** (1,6x; la stima: 0,267 e 0,149 a 8 192).
- A split 16 una 3060 piu' veloce **non accorcia** la lettura lunga (stadio 1 al 100%); serve spostare layer sullo stadio 0 (E, §5).
- Lettura corta: lo stadio 0 vale meta' del tempo, ma 1,9-3,4 s del suo wall sono attesa PLE da SSD (12 ms a lettura), invariante col cambio di scheda.

## 3. Sensibilita' alla VRAM dello stadio 0 (punto 2)

### 3.1 Il fattore dominante non e' la taglia della cache: e' la VRAM libera sulla 3060

Il Daily «auto» (`--expert-cache auto --vram-reserve-mib 1905`) chiude il caricamento con **0-82 MiB liberi** sulla 3060 (il motore stesso scrive «LOW: requests may stall», e la riga c'e' nel log di ogni avvio). Stato di avvio della 3060 (prima del motore):
2,29-2,39 GB occupati da app (OktoCGControl 1,85-1,98 GB, Claude Desktop 0,59-0,76, csrss 0,17, explorer 0,05). Risultato sul decode a 131K (M, 52 richieste):

| config | slot | VRAM libera dopo il carico | richieste lente | decode medio |
|---|---:|---|---|---|
| Daily auto e simili (5 bracci: A1, S2A1-A3, S2B1a; l'ultimo con riserva +1 GiB, ma il motore ha dato 2 490 slot e 0 MiB liberi) | 2 434-2 490 | 0-82 MiB | **14 su 18** | **33,3 t/s** (28,1 lente; 51,6 veloci; mediana 28,2) |
| riserva alta (S2B3a, B2a, S2B2a, S3H1, S3H2) | 1 138-1 853 | 0,9-3,4 GB | 0 su 18 | 43-53 t/s |
| `--expert-cache 2000-2900` (S3H3, S5X1, S5X2, S5H3b) | 3 108-3 259 | 0,8-1,2 GB | **0 su 16** | **52-65 t/s** (L01-L04 media 57,5; L01-L03 55,3) |

«Lenta» = attesa GPU dello stadio 0 > 14 ms per finestra: in quelle richieste lo stadio 0 impiega 30-80 ms invece di ~10 (clock invariati a ~1 930 MHz, potenza mediana 81-82 W invece di 110-131 W: la 3060 aspetta, non e' strozzata).
Prefill 131K sullo stesso asse: Daily auto **461-870 tok/s** (media 632, chunk 6 144), lettura corta da 5K **15,0 s** (mediana; 4 bracci su 5, A1 9,9 s) contro 1 452-1 462 tok/s (chunk 7 936) e 8,7 s con la cache esplicita.
Lettura prudente: non dimostro la causa (paginazione WDDM della memoria piena e/o condivisione di tempo con CGControl e Claude Desktop sulla stessa scheda: durante le corse sulla 3060 giravano
CGControl NVDEC 9,9% + 3D 2,3%, claude.exe 3D 4,6%, csrss 2,6%, DWM 0,4%); dimostro che la **correlazione con i MiB liberi e' netta** (14/18 contro 0/38).
`--expert-cache N` esplicito (qui unita' di 2,33 MB: N=2000 -> 3 108 slot da 1,43 MB, N=2500 e 2900 -> 3 259 e 3 236, tetto) lascia ~1-1,2 GB liberi e 1 GB di slot in piu' del Daily: lo trovo senza aver capito perche'
l'auto lasci piu' VRAM occupata (con la lettura a chunk 6 144 «posseduta» invece che «presa in prestito» dalla cache, come ipotesi). **E' una scoperta di config che l'owner puo' usare oggi** (da validare nel tempo: con CGControl e altre app
il margine di 1 GB puo' variare).

### 3.2 Pendenza nel regime sano (3060 con >=0,8 GB liberi) - M

Fra 1 138 e ~3 200 slot (5 famiglie di §2a, regressione lineare sulle medie di famiglia):

| grandezza | pendenza |
|---|---|
| ms per token di decode | **-2,07 ms ogni 1 000 slot = -1,48 ms/GiB** (-7% del tempo per GiB a ~20 ms/token); 1 GiB = 716 slot |
| pool + piano dello stadio 0 | -4,07 ms/finestra ogni 1 000 slot = -2,9 ms/finestra per GiB |
| finestra | -3,5 ms ogni 1 000 slot = -2,5 ms/GiB |
| hit (globale, decode) | 79,2% a 1,1K -> 81,9% a 1,6K -> 83,2% a 1,8K -> 86,8% a 2,4K -> 94,8% a 3,2K |
| costo di un esperto servito dalla CPU | **~0,07 ms** (8,7 ms di pool in meno per ~128 esperti CPU in meno per finestra fra 1,1K e 3,2K slot) |

Prefill sullo stesso asse (M): il chunk scala con la cache (1 792 token a 1 138 slot, 3 328 a 1 563, 4 096 a 1 820, 6 144 a 2 440 con 0 MiB liberi, 7 936 a 3 108+; 8 192 nella cornice pipeline: tetto dato dai 7 554/8 956 slot dello stadio 1):
131K: **709 -> 1 070 -> 1 180 -> 1 452-1 462 tok/s** (1 533 in pipeline). Pendenza 1,1K -> 3,2K slot: **+753 tok/s su 2,75 GiB = +270 tok/s/GiB**, ma e' effetto del chunk e **si ferma al tetto**: sopra ~3,1K slot, con il chunk al massimo, la pendenza e' ~0.
Lettura da 5K: 9,5 s (1,1K) -> 9,0 s (1,6K) -> 9,1-9,2 s (1,8K) -> 8,7 s (3,1-3,3K): **-0,4 s ogni 1 000 slot (-0,6 s/GiB)**, saturante.

### 3.3 Esperti mancanti e hit dello stadio 0 (traccia di instradamento) - M + T

Corsa S5R1 (`--dump-routing`, 4 decode a 131K = 235 632 righe token-layer, k=10): **hit/miss per stadio** con cache statica = primi S accoppiamenti del profilo (come riempie il motore), e col migliore possibile sulla traccia (oracolo, limite alto).
`routing_stage0.py`; mancanti = esperti distinti per chiamata di layer (cio' che costa CPU o PCIe).

| slot stadio 0 | hit profilo | mancanti/chiamata (profilo) | hit oracolo | mancanti/chiamata (oracolo) | previsione CPU esp./chiamata globale (oracolo) |
|---:|---:|---:|---:|---:|---:|
| 1 138 | 39,5% | 11,34 | 58,1% | 8,17 | 3,29 |
| 1 563 | 48,8% | 9,61 | 67,7% | 6,34 | 2,68 |
| 1 853 | 54,3% | 8,56 | 73,1% | 5,30 | 2,33 |
| 2 440 | 64,2% | 6,68 | 81,8% | 3,59 | 1,76 |
| 3 108 | 73,1% | 4,99 | 88,7% | 2,26 | 1,32 |
| 3 260 | 74,4% | 4,72 | 89,9% | 2,03 | 1,24 |
| 4 000 | 81,2% | 3,40 | 94,4% | 1,14 | 0,95 |
| 5 000 | 88,1% | 2,12 | 97,8% | 0,46 | 0,72 |
| 6 000 | 93,0% | 1,27 | 99,4% | 0,13 | 0,61 |
| 7 000 | 96,4% | 0,66 | 99,9% | 0,01 | 0,57 |
| 8 192 | 100% | 0 | 100% | 0 | 0,57 (solo stadio 1) |

Controllo col motore (CPU esperti per layer-finestra, globali, misurati): 4,55 / 3,83 / 3,51 / 2,41 / 0,8-1,4 a 1,1K / 1,6K / 1,8K / 2,4K / 3,2K slot. Sotto i 2,4K il modello statico del profilo
li riproduce (4,35 / 3,77 / 3,42 / 2,79); da 3,1K in su il motore sta sull'**oracolo** (1,32; adattamento in corsa) e non sul profilo statico (2,23). Stadio 1 (7 554 slot): oracolo 4,2% di miss, 0,85 esperti/chiamata.
Limite: traccia di 4 sole richieste dello stesso prefisso (in-sample per l'oracolo).

### 3.4 Estrapolazione verso +4-5 GiB (E)

+4-5 GiB sono +2 900-3 600 slot: sopra ~5 300-6 000 slot (65-73% dei 8 192 esperti dello stadio 0, oracolo: 0,1-0,5 mancanti/chiamata). La pendenza lineare di §3.2 **non si estrapola**: la parte CPU dello stadio 0 e' gia' a 2,5 ms
(di cui ~1 ms e' pavimento fisso, misurato 0,8-1,4 ms in pipeline con hit 97-98%) e la relazione misurata pool = -0,85 + 3,24 x (CPU esperti globali) la porta a ~1,1-1,5 ms con 5-6K slot. Quindi da 3,2K slot **restano da guadagnare ~1,5-2,5 ms per finestra (-5-7%)**
nel decode batch, e ~0 sul prefill (tetto del chunk).

## 4. Costo del desktop sulla 3060 (punto 3) - M parziale

Non ho chiuso OktoCGControl (regola: non chiudere app dell'utente) e quindi **manca la coppia aperta/chiusa**; resta il dato storico del 13/10 (~77/70 t/s chiusa, -7% aperta). Misurato adesso, app aperta, con Jump:
- 3060 prima del motore: 2,29-2,39 GB di VRAM tenuti da app (CGControl 1,85-1,98 GB). Sulla 2080 Ti, DWM tiene 5,1 GB (display e cattura Jump li': condizione non standard); coerente con lo stadio 1 a 7 554 slot invece di 9 145 (causa non isolata).
- Durante le corse, sulla 3060: CGControl NVDEC 9,9% medio (silicio diverso dagli SM) + 3D 2,3%; claude.exe 3D 4,6%; csrss 2,6%; DWM 0,4% (non compone sulla 3060 in questa condizione).
- Effetto: §3.1. L'impronta in VRAM (non il calcolo) decide il regime: con il Daily auto 14 decode su 18 sono «lenti» (28 invece di 52 t/s) e la lettura lunga e' a 632 tok/s medi invece di ~1 450.
  Con una scheda dedicata solo al calcolo (nessuna app, nessun DWM) il regime lento non esiste: e' un guadagno che **non dipende dalla 5060 Ti**, ma si ottiene anche rimettendo ~1-2 GB di margine alla 3060 (config esplicita, §3.1).
- Coppia aperta/chiusa: `20261019_stadio0\st0_desktop.sh aperta 1 | chiusa 1 | aperta 2` (due bracci ciascuno, Daily auto ed esplicito). Serve che l'owner chiuda/riapra l'app tra una chiamata e l'altra.

## 5. Visione (punto 4) - M

`st0_vision.py`: encoder da solo (visione su CPU, 8 thread, 1 008 token d'immagine, PNG sintetici 1600x900 da ~117 KB) e server completo (Daily, porta 8104), `max_tokens` 4, temperatura 0.

| misura | valore |
|---|---|
| encoder da solo (4 immagini diverse) | **16,7-17,3 s** (media 16,9) |
| richiesta di solo testo (27 token) | 0,53-0,61 s |
| richiesta con immagine (1 032 token di prompt), end-to-end | **20,8-23,3 s** (media 21,5) |
| resto (lettura dei token d'immagine + motore) | ~4 s |

Un'immagine oggi costa ~21 s, di cui ~17 s (80%) sono l'encoder su CPU, indipendenti dalla GPU dello stadio 0. Una 5060 Ti ci guadagnerebbe solo con l'encoder su GPU (`vision.gpu: true`): non misurato (E/I).

## 6. La stima rifatta solo su questi numeri

Notazione: **k** = tempo per layer della scheda dello stadio 0 diviso quello della 3060 (0,61 ms nel decode, 0,275 s per chunk nel prefill). Misurato: 2080 Ti = **0,6** (1,6x). Per la 5060 Ti non c'e' misura:
ipotesi **k = 0,5-0,75** (da «come una 2080 Ti» a «solo la banda 448 contro 360 GB/s» + qualcosa); centrale 0,6. E' l'incognita dell'intera stima. Esperti dello stadio 0 con 16 GB: tutti e 8 192 residenti (11,4 GiB + ~3,5 GB di resto del motore misurato) -> miss ~0 (I per il margine di VRAM).

**Decode a 131K**

| cornice / base | oggi (M) | con 5060 Ti | come si ottiene |
|---|---|---|---|
| Daily batch com'e' (auto) | **33,3 t/s** (14/18 lente) | **63-69 t/s (x1,9-2,1)** | non solo la scheda: ~55 t/s li da' gia' la config esplicita sulla 3060 (M) |
| Daily batch, 3060 sana (cache esplicita) | 55,5 t/s (L01-L03; 57,3 con L04) | **63-69 t/s: +14...+24%**, centrale +20% | stadio 0: 12,9 ms -> 0,7 (fissi) + 1,0 (pool) + 9,73 x k = 6,6-9,0 ms (E, k=0,5-0,75); finestra 32,2 -> 25,9-28,3 |
| pipeline (cornice della stima) | 64 t/s (L01-L03 medi; 56-71) | **+9...+18%**, centrale +14%; con k=0,8 (solo banda) +8% | replay della traccia con S0 scalato (T, §2b): x0,73 -> +9,4%, x0,60 -> +14,5%, x0,51 -> +18,1% |

Confronto con la stima (+3,5/+10%, centrale +7% in pipeline): il centro **raddoppia** perche' lo stadio 0 della 3060 e' piu' lento di quanto ipotizzato (1,6x la 2080 Ti per layer, non 1,18x) e quindi k vale meno; l'estremo basso (+7%) coincide con la stima.
La parte «cache» della stima (A: +3,8K slot) e' qui di scarso peso: la CPU dello stadio 0 e' gia' a 1,4 ms (pipeline) o 2,5 ms (batch con cache esplicita).

**Prefill**

| lettura | oggi (M) | con 5060 Ti | note |
|---|---|---|---|
| 131K a freddo, split 16 | 1 452-1 462 tok/s (sano); **632 medi con il Daily auto** | **0%** a split 16 | stadio 1 al 100%, stadio 0 al 79% (M): una scheda piu' veloce sullo stadio 0 non cambia il passo |
| 131K, con ribilanciamento dei layer | idem | tempo/chunk = 48 a0 a1/(a0+a1) con a1 = 0,172 s e a0 = 0,275 k: **k=1: +8%; k=0,75: +22%; k=0,6: +36%; k=0,5: +50%** (E teorico; non provato: serve `--layer-split` ~22-27 e la verifica del decode) | e' un tetto: testa/MTP/KV restano sullo stadio 1, i layer sono interi, il PLE da SSD non scala |
| 5K fresca | 8,7 s (sano), 15,0 s (Daily auto) | **-3...-14%**, centrale -8% (-0,3...-1,4 s) | stadio 0 = 4,5 s, dei quali 1,9-3,4 s attesa PLE da SSD non scalabile: la parte GPU e' 1,1-2,7 s, ridotta del 25-50% |

Rispetto alla stima (5K: -13...-23%, replay -8...-16%): il corto e' **meta' circa** (-8% contro -18%) per via dell'attesa PLE; la lettura lunga e' 0% a split 16 (la stima dava 0/+3%) e dipende interamente dal ribilanciamento.
Il prestito di VRAM al percorso del prompt (§3.1) ha il chunk massimo a ~3,1K slot: sopra, niente da guadagnare in prefill.

**In una riga**: il +5-10% della stima e' **corretto come ordine di grandezza solo nella cornice pipeline e solo per k vicino a 0,75**; con k=0,6 (scheda da classe 2080 Ti) e' +14%. Nel Daily vero (batch, seriale) il guadagno hardware e' piu' alto (+14...+24% sulla 3060 sana)
e, soprattutto, **circa il 70% del miglioramento visibile oggi (33 -> ~66 t/s) arriva dalla VRAM libera sulla 3060, non dal tipo di scheda**: Daily auto 33 t/s -> cache esplicita 55-57 t/s -> 5060 Ti ~63-69 t/s (E).

## 7. Cosa manca (onesto)

1. Coppia **OktoCGControl aperta/chiusa**: serve l'owner (`st0_desktop.sh`).
2. Nessuna 5060 Ti: k e' ipotesi; l'unica misura vera di k sarebbe la scheda (o un proxy: stadio 0 sulla 2080 Ti con `CUDA_VISIBLE_DEVICES=0,1`, non provato per il rischio di VRAM sulla 3060 come stadio 1).
3. Il modello degli esperti e' su 4 richieste dello stesso prefisso; i punti sopra 3,26K slot sono modello, non corsa (la 3060 non ne regge di piu').
4. Esplicito = ~1 GB di margine: stabilita' nel tempo (CGControl e altre app) non verificata oltre le ~4 ore di queste corse; l'avviso LOW dello stadio 1 (482 MiB) e' presente in tutte.
5. Con Jump: tutti i numeri assoluti. Senza Jump il DWM torna sulla 3060 (8K DSR) e il costo del desktop sale (non misurato).

## 8. File

Script e dati in `corse_2080ti\20261019_stadio0\`: `st0_run.py` (braccio), `st0_lock.py` (copia di `bench_fast.py`), `st0_vision.py`, `st0_report.py`, `st0_agg.py`, `st0_final.py`, `pl_analyze.py` (traccia di pipeline),
`routing_stage0.py` (hit/miss per stadio), `serie1.sh`, `serie2.sh`, `serie3.sh`, `serie5.sh`, `serie6.sh` (l'ordine dei bracci; la 4 non e' mai partita; l'ultimo braccio S6E1 e' stato annullato in coda), `st0_desktop.sh`, `strata-0145-daily-st0.json` (copia della config, porta 8104, file di prefisso suo), `dati_corse.json` (riassunto di tutte le richieste), `visione_S5V1.txt`.
Log grezzi, tracce e `routing.bin` restano in `D:\ds4_work\strata\lab_st0\runs\DET-ST0-*` (non nel repo). Bracci: P1 (profilo), A1/B2a (esplorativi, fuori protocollo), S2A1-A3, S2B1a/B2a/B3a, S3H1-H3, S5X1/X2/H3b/R1/V1/P2a/P2b, S6T1.
Daily e bat del Desktop non toccati; nessuna priorita' alta; `bench.lock` preso per singola corsa.
