# Replay a 3 agenti sulla 0.2.6: rapporto per fasi - 27 ottobre 2026

**Solo analisi dei log della coda notturna del 26-27/10.** Nessuna GPU, nessun `strata.exe`, nessuna misura nuova (compilato no, installato no, provato no: i
numeri sono quelli delle corse già fatte). Script riproducibile: `analisi_fasi.py` (stessa cartella); l'uscita completa, corsa per corsa, è in `fasi_generato.md`.
Percorsi relativi a `docs/porto/strata_adattivo/corse_2080ti/20261026_leve/`; le corse sono in `corse/replay_<NN>_<braccio>/` (`res.json`, `engine.log`, `server.log`, `config.json`).
Nota: `corse/` e `coda_leve_026.run.log` oggi non sono tracciati in git (il commit `28e3649` ha preso solo i riepiloghi): i riferimenti riga sotto valgono sul disco.

## 0. Conclusioni (5 righe)

1. **La lettura è il percorso critico, non la scrittura.** Con 3 agenti le letture non si fondono mai (0,0 s con 2 letture insieme in tutte le 17 corse): si mettono in coda una dopo l'altra, e il tempo per finire è la catena delle letture (R3: 201 s di letture su 243, `summary.server_read_s` 200,6) più una coda di ~42 s. Per questo le leve sulla scrittura (L1-L4) non spostano il risultato.
2. **Il batch non regala scrittura aggregata a 3 agenti**: con 2-3 agenti che scrivono l'aggregato è 42-61 t/s (T-N, §2), sotto i 74 t/s di una chat singola con MTP; mentre qualcuno legge (59-63% del tempo in R3) gli scrittori fanno 14-19 t/s in tutto (~13 a testa) e la lettura grande scende da 1765 a ~1520 tok/s (-14%).
3. **Quasi tutto il guadagno R0 -> R3 (443 -> 243 s) viene dalla cache delle conversazioni, non dal batch**: R0 rilegge 603 K token (cache a 2 posti), le corse con batch 182 K (18 GiB / 16 posti). Un server seriale con la stessa cache, per stima S (non misurata), finisce in 223-233 s: pari o meglio di R3 (243), con TTFT medio ~31 s contro 19 s. Il batch compra soprattutto il TTFT (-39% medio, -43% p90 contro la stima), non il tempo totale.
4. **R2 (`--batch-groups 2` senza PIPED_CONCURRENT) legge a piena velocità ma ferma chi scrive** (nessun «thread proprio» nel log; scrittori ~3 t/s a testa durante le letture): TTFT migliore (12,9 / 21,5 s), tempo uguale (251 s). **R1 (gruppo seriale) è il peggiore** in lettura mista (691 tok/s sulla lettura da 77,6 K contro 1520-1765) e finisce in 354 s (R2 e R3: 251 e 243).
5. **Dalla 0.1.45 del 19/10 alla 0.2.6 la lettura è più veloce del 13-31%** (a parità di richieste A,B,C), ma i tempi totali di allora (937-1069 e 298-302 s) non sono confrontabili con questi (4 agenti con P a 140 K, 24 richieste). Manca la misura che separa cache e batch (R0 con cache grande: §4) e quella a 6 e 8 agenti sulla 0.2.6.

## 1. Che cosa è stato rigiocato e quanti agenti lavorano davvero

Replay `20261019_replay/replay_trace.py` sulla traccia `trace_dsh_20261016.json` (sessione DSH reale del 16/10), `--t0 3600 --span 1200 --only A,B,C`: 3 agenti,
**17 richieste**, orchestratore P escluso. Config: Daily 0.2.6 (`cfg-daily-base.json`); batch = `--batch 4`, cache conversazioni 18432 MiB / 16 posti, riserva VRAM 1905/700 MiB.
Bracci (da `coda_leve_026.py`): R0 senza batch; R1 `--batch 4` (gruppo seriale, default); R2 `--batch 4 --batch-groups 2`; R3 = R2 + `STRATA_PIPED_CONCURRENT=1`; R3L = R3 sulla build `leve026`
con le leve spente (6 corse: 02, 04, 18, 20, 22, 24); L1 `--batch-mtp` + `STRATA_PIPED_MTP=1` (03); L2 `STRATA_PW_WITH_BATCH=1` (19); L3 `STRATA_PIPE_ADAPT_EVERY=128` (21);
L4 righe attive + affinità + checkpoint di ramo (23). R0 ha 4 corse (05, 07, 09, 11). Tutte le corse: 17 richieste riuscite, 0 fallite, nessuna «disturbata» (`summary.disturbed=false`).

Definizioni. **In volo** = richiesta inviata e non finita (coda + lettura + scrittura). **Serviti** = legge o scrive (esclusa la coda). **Scrivono** = in decode. Medie pesate sul tempo, da 0 al tempo per finire. Intervalli di una richiesta: coda
`[invio, primo - lettura]`, lettura `[primo - lettura, primo]` (lettura = `prompt_ms` del server = riga «strata serve: prompt ... read in X ms»), scrittura `[primo, fine]`.

| braccio (corse) | richieste | in volo medio (max) | serviti medi (max) | scrivono medi (max) | leggono medi (max) | token di prompt nuovi letti | token generati |
|---|---:|---:|---:|---:|---:|---:|---:|
| ORIGINALE (sessione vera, A,B,C) | 17 | 2,77 (3) | 0,58 (1) | 0,06 (1) | 0,52 (1) | 861.032 | 5.157 |
| R0 (4: 05, 07, 09, 11) | 17 | 2,69 (3) | 1,00 (1) | 0,14 (1) | 0,86 (1) | 584.563 (602.7-602.9 K; 11: 529.835) | 4.424 (4.041-4.621) |
| R1 (10) | 17 | 2,53 (3) | 1,92 (3) | 1,07 (3) | 0,86 (1) | 180.643 | 3.977 |
| R2 (08) | 17 | 2,45 (3) | 2,30 (3) | 1,57 (3) | 0,72 (1) | 181.674 | 3.825 |
| R3 (06) | 17 | 2,53 (3) | 1,99 (3) | 1,18 (3) | 0,81 (1) | 181.742 | 4.554 |
| R3L (6) | 17 | 2,55 (3) | 2,05 (3) | 1,21 (3) | 0,84 (1) | 181.523 | 4.285 (3.915-4.691) |
| L1 PIPED_MTP (03) | 17 | 2,40 (3) | 1,76 (3) | 0,94 (3) | 0,82 (1) | 181.511 | 4.339 |
| L2 PW_WITH_BATCH (19) | 17 | 2,38 (3) | 2,20 (3) | 1,43 (3) | 0,77 (1) | 181.676 | 4.360 |
| L3 PIPE_ADAPT_EVERY (21) | 17 | 2,51 (3) | 2,02 (3) | 1,18 (3) | 0,85 (1) | 181.898 | 3.976 |
| L4 righe attive + checkpoint (23) | 17 | 2,48 (3) | 2,07 (3) | 1,24 (3) | 0,83 (1) | 180.354 | 4.647 |

Letture dei numeri. (i) **Gli agenti non pensano**: ~2,5 su 3 sono sempre in volo (il «pensiero» fra turni è di pochi secondi): il server è il collo. (ii) In R0 serviti = 1 per costruzione (server seriale): gli altri 1,7 agenti aspettano in coda.
(iii) Con batch gli agenti serviti sono ~2 (non 3): in media 0,8 leggono e 1,2 scrivono; 0,5 aspettano la loro lettura in coda. (iv) **Max leggono = 1 ovunque**: una sola lettura per volta, anche con 4 slot; la lettura di un agente comincia 0,5-0,9 s dopo la fine di quella precedente (ammissione: copia dello slot 0,35-0,7 s,
riga «slot N takes ... copied in X ms»). Esempio R3: B legge 0-5 s, A 5,8-14,6, C 15,1-66,2 (`res.json` della 06: `t_first_rel` meno `prompt_ms`). (v) I **token generati** variano del ±10% da corsa a corsa (3.825-4.691) perché il modello si ferma quando vuole (nessun `min_tokens`): il tempo per finire va letto con questa incertezza.
(vi) R0 11: 409,9 s contro 443-449 perché cambia l'ordine di servizio e quindi il riuso: 529.835 token nuovi invece di 602.7 K (-73 K, una lettura da ~77 K in meno).
(vii) 02_R3L: il primo tentativo è fallito alla chiusura del server (`psutil.AccessDenied`, `coda_leve_026.run.log` riga 167) e il passo è stato rilanciato; `engine.log` contiene i due avvii e l'analisi usa il secondo.

## 2. Timeline per fasi

**Come è ricostruita.** `engine.log` non ha un orario per riga (solo «engine started» in testa): uso l'**ordine e le durate** delle sue righe e i tempi lato client di `res.json`. Verifica: le letture ricostruite sono seriali e contigue (0,0 s di letture sovrapposte), e la durata di ogni lettura coincide col «read in X ms» del motore.
Fasi: **(a)** legge >=1, nessuno scrive; **(b)** scrivono >=2, nessuno legge; **(b1)** scrive 1, nessuno legge; **(c)** legge >=1 e scrive >=1; **(i)** né l'uno né l'altro. Velocità per fase con tre metodi, perché res.json non ha l'istante dei singoli token:
**T** = token distribuiti in modo uniforme sull'intervallo di ogni richiesta (peso uguale in tutte le fasi: non vede un rallentamento); **N** = minimi quadrati non negativi, una velocità per classe, sui token di ogni richiesta (vede un rallentamento ma è rumoroso con 17 richieste: scarto relativo 0,1-0,3); **E** = misure dirette del motore (righe «batch: read N tokens on a thread of its own ... decoded R rows meanwhile» solo con PIPED_CONCURRENT; «the prompt was read in N parts»; finestre del gruppo seriale).
Dove T e N divergono, il vero sta fra i due.

| braccio | (a) s | (a) lettura tok/s | (b) s | (b) scrittori | (b) agg. T / N t/s | (b) a testa (T) | (b1) s | (b1) t/s | (c) s | (c) scrittori | (c) lettura tok/s | (c) scrittura agg. T / N t/s | (c) a testa (T) | (i) s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ORIGINALE | 753 | 1143 | 0 | - | - | - | 83 | 62 | 0 | - | - | - | - | 603 (altre richieste, P) |
| R0 (4 corse) | 377 | 1551 | 0 | - | - | - | 60 | 74 | 0 | - | - | - | - | 1 |
| R1 | 114 | 664 | 34 | 2,42 | 34 / 53 | 13,9 | 17 | 21 | 189 | 1,48 | 555 | 13 / 8 | 8,9 | 0 |
| R2 | 36 | 776 | 39 | 2,70 | 24 / 30 | 9,1 | 25 | 57 | 146 | 1,82 | 1054 | 10 / 5 | 5,5 | 5 |
| R3 | 54 | 944 | 27 | 2,36 | 44 / 59 | 18,5 | 19 | 36 | 142 | 1,44 | 915 | 19 / 15 | 13,2 | 0 |
| R3L (6 corse) | 49 | 968 | 21 | 2,58 | 42 / 61 | 16,2 | 17 | 37 | 150 | 1,45 | 893 | 18 / 14 | 12,8 | 0 |
| L1 | 77 | 1013 | 20 | 2,14 | 46 / 61 | 21,4 | 24 | 33 | 121 | 1,33 | 854 | 22 / 17 | 16,3 | 0 |
| L2 | 35 | 760 | 32 | 2,45 | 33 / 63 | 13,2 | 23 | 44 | 158 | 1,62 | 985 | 14 / 7 | 8,9 | 2 |
| L3 | 46 | 1053 | 13 | 2,68 | 35 / (18, N instabile) | 13,0 | 19 | 45 | 150 | 1,46 | 893 | 18 / 17 | 12,3 | 4 |
| L4 | 40 | 913 | 19 | 2,26 | 42 / 62 | 18,7 | 23 | 35 | 164 | 1,46 | 881 | 19 / 15 | 12,8 | 0 |

(R0, R3L: medie di corsa; N con le equazioni di tutte le corse insieme. R0: l'aggregato in (c) è vuoto, le sbavature di ammissione sotto 0,3 s non contano.)

### (a) Solo letture: unite o in coda?
**In coda, mai unite.** Un solo agente legge per volta in tutti i bracci (max leggono = 1). Quindi il «prefill aggregato» in (a) è la velocità di **una** lettura e dipende dalla taglia: la tabella (a) sopra mescola tante letture piccole (a inizio corsa, e quelle da 2-6 K di ogni turno) e perciò sta sotto i valori del banco.
A parità di taglia, letture senza scrittori (da `fasi_generato.md`, «Lettura per taglia»): R0 <3 K ~500 tok/s, 3-8 K ~720, 8-16 K ~957, **>50 K 1765-1795**; R3 3-8 K 784 (1 lettura), 8-16 K non ha letture pure; la lettura grande è sempre in (c). Pesa un costo fisso di ~2 s per richiesta anche quando i token nuovi sono pochi (85 token in 2,1 s e 145 in 2,5 s: `10_R1/engine.log` righe 247, 282): non è l'attesa PLE, che compare solo 3 volte per corsa sulle letture da zero («the chunk at token 0 waited 2010-2502 ms for its PLE rows», `06_R3/engine.log` righe 75, 77, 100).
Nelle corse con batch (a) occupa 14-32% del tempo (R3: 54 s, 22%): sono quasi sempre le prime letture (nessuno ancora scrive) e le letture isolate a fine corsa.

### (b) Solo scrittura (>=2 in decode)
Nelle corse con batch è la fase più corta (R3: 27 s = 11%; R3L 21 s; R1 34 s; R2 39 s) più (b1) con un solo scrittore (17-25 s).
Aggregato con 2,4-2,7 scrittori: **R3/R3L 42-44 (T) - 59-61 (N) t/s** (16-18 t/s a testa T); i tratti di sessione più puliti del motore stanno a 27-36 righe/s («batch (pipelined, 2 groups of 2): 942 group-steps, 1073 rows in 36.1 s = 29.7 rows/s» e «228 group-steps, 228 rows in 6.3 s = 36.0 rows/s», `06_R3/engine.log` righe 230 e 263), quindi la stima prudente per R3 è **~35-45 t/s aggregati (13-18 a testa)**, non i 59-61 di N.
R1 ha il numero più chiaro, perché il motore stampa le finestre di sola scrittura: **3.703 righe in 70,9 s = 52,2 righe/s con 1,86 righe per finestra** (`10_R1/engine.log` righe 134, 196, 218, 234, 250, 285, 301; ~28 t/s a testa): il gruppo seriale da 4 slot scrive meglio dei gruppi pipeline da 2 quando legge nessuno.
R2 in (b): 24 (T) - 30 (N). Un solo scrittore (b1): R0 74 t/s (MTP attivo, «drafts accepted 128 of 211»), R3 36, R2 57, R1 21, ORIGINALE 62: con batch lo slot scrive senza MTP.

### (c) Miste (uno legge, gli altri scrivono) - la fase dove si perde tempo
È la fase dominante: **59-67% del tempo in R3/R3L/L2-L4 (50% in L1), 58% in R2, 53% in R1**. Scrittori medi 1,3-1,6.
- **R3 (PIPED_CONCURRENT)**: lettura 915 tok/s (T), la lettura grande da 77,6 K a **1520 tok/s** (vs 1765 in R0: -14%) con **655 righe decodificate nel frattempo, 13,1 righe/s** (`06_R3/engine.log` riga 134); scrittura aggregata **15-19 t/s** (N-T), 13 a testa. Il motore, su tutte le 17 letture: 172.460 token in 163 s = 1057 tok/s con 2.432 righe = 14,9 righe/s sul tempo intero delle letture, **19,3 righe/s** sul solo tempo in cui qualcuno scrive durante la lettura.
- **R2 (senza PIPED_CONCURRENT)**: lettura 1054 tok/s, la grande a **1680** (-5% su R0, `08_R2/engine.log` riga 131); scrittura aggregata **5 (N) - 10 (T)**, 2,9-5,5 t/s a testa: **gli scrittori sono praticamente fermi mentre l'altro legge** (indizio indiretto, nel log non c'è nessuna riga «righe decodificate nel frattempo»; sessioni «13,9 / 10,1 rows/s (admissions included)» righe 150, 212).
- **R1 (gruppo seriale)**: lettura 555 tok/s, la grande a **691** (112 s invece di 44-51: `10_R1/engine.log` riga 139, «read in 9 parts, the slots decoding 17888 ms between them» riga 135): le letture sono spezzettate e alternate alle finestre di scrittura; scrittura aggregata 8-13 t/s. Peggiore dei tre in lettura (-61% sulla grande).
- **Leve**: L1 854 tok/s / 17-22 t/s, L3 893 / 17-18, L4 881 / 15-19: identici a R3L (893 / 14-18) entro il rumore. **L2 si comporta come R2**: lettura 985, scrittura 7-14, TTFT 13,9 / 19,1 s (R3L 18,7 / 42,0), cioè la lettura passa davanti agli scrittori (n=1: indicativo).

Indice di lavoro in (c), per capire se «uno che legge e due che scrivono» rende più di uno solo: velocità della lettura grande / 1765 + scrittura aggregata / 74 (R0 da solo). **R3 0,86 + 0,20-0,26 = 1,06-1,12**; R3L ~0,87 + 0,19-0,24 = 1,06-1,11; R2 0,95 + 0,07-0,14 = 1,02-1,09; **R1 0,39 + 0,11-0,18 = 0,50-0,57**. Cioè R3 e R2 non perdono capacità (la somma del lavoro è appena sopra una macchina sola), R1 ne butta metà. Indicativo (S): usa la sola lettura da 77,6 K.

### Intero ciclo: dove va il tempo (R3, 243 s)
Catena di letture 201 s (`server_read_s` 200,6; leggono 0,81 in media) + coda di ~42 s. R0: 387 s di letture su 443 (87%); ORIGINALE: 753 s di letture + 83 s di scrittura su 1439, il resto (603 s) lo occupano le richieste di P che il server serviva in mezzo.
Nelle corse con batch: R1 catena 308 s (+46); R2 184 s (+67, la scrittura ferma durante le letture si recupera dopo); R3 200,6 s (`summary.server_read_s`).

## 3. Riferimenti per giudicare

| misura | valore | fonte |
|---|---|---|
| Sessione vera, 17 richieste A,B,C nel tratto 3600-4800 s | 1438,9 s; TTFT medio 229,9 / p50 207 / p90 436 s; letture 753 s a 1143 tok/s (>50 K: 1221); scrittura 83 s a 62 t/s; riuso 50% (861 K nuovi) | riga ORIGINALE in `res.json` -> `original`; `trace_dsh_20261016.json` |
| R0, senza batch (4 corse) | 443,0 / 448,9 / 449,2 / 409,9 s; tutto in coda, 1 servito; letture 387 s a 1551 tok/s (>50 K 1765-1795; 3-8 K ~720); scrittura da sola **73,6 t/s** (69,8 t/s con MTP sulla richiesta da 265 token, `05_R0/engine.log` riga 165) | `05/07/09/11_R0` |
| Banco comunità 25-26/10, chat singola, Daily T=0 (`bf-base`, `12/14_bf-base`) | decode 4 K 88,2-89,5; 32 K 80,2-84,1; 125 K 83,7 t/s; prefill 4 K 804-808, **32 K 1550-1551**, 125 K 1826-1836 tok/s | `ANALISI_20261027.txt` a2 |
| Chat singola con batch acceso (`pw-base`, build leve026, R3 a riposo) | decode 4 K 73,4-73,5; 32 K 74,2 t/s; prefill 4 K 741, **32 K 1381** tok/s | `ANALISI_20261027.txt` a3 |
| Valori attesi dall'owner | decode ~74-80 t/s; prefill 32 K ~1400-1550 tok/s | richiesta |

Come si leggono i confronti. (1) **Scrittura da soli**: 74 t/s (R0, replay) contro 74-80 del banco: coerenti. (2) **Lettura da soli, grande**: 1765 tok/s su 77,6 K nuovi in un contesto di 86 K, sopra il 32 K del banco (1551) perché il costo fisso di 2-4 s si spalma e il banco 125 K arriva a 1826-1857: la velocità sale con la taglia. Le letture a 3-8 K stanno a ~720 tok/s perché il fisso pesa.
(3) **Con altri che scrivono (R3)** la lettura grande è a 1520: -14% sulla stessa lettura da soli (1765). Il banco 32 K con batch acceso (1381) ha un'altra taglia: non è confrontabile alla pari.
(4) **ORIGINALE contro R0**: la stessa macchina, ma la build di allora legge a 1143-1221 tok/s e scrive a 62: la 0.2.6 è +36-45% in lettura, +19% in scrittura (S: build e giornata diverse). Il resto del divario (1439 -> 443 s) è soprattutto il riuso: 861 K token nuovi contro 603 K (R0) contro 182 K (con cache grande).
(5) **Il batch a 3 agenti non supera il singolo in scrittura** (aggregato 42-61 contro 74), e vince in TTFT: R3 19,3 s contro 66-68 di R0.

### Confrontabile con il 19/10 e cosa no (`20261019_replay/RISULTATI.md`, `replay_c1-daily`, `replay_c1b-daily`, `replay_c2-g2cc`, `replay_c2b-g2cc`)
Le corse del 19/10 sono sul motore **0.1.45** (`engine.log`: «session is up (engine 0.1.45)»; il «0.1.43» del titolo è la Daily della sessione originale del 16/10), quelle di oggi sulla **0.2.6** («engine 0.1.51» nei log).
- **Non confrontabili**: tempo totale e TTFT (24 richieste e 4 agenti con P a 140 K di contesto, contro 17 e 3; P pesa 530 K token nuovi in c1 e 12 K in c2; 938-1069 s contro 410-449 per R0 è soprattutto P); cache a 28 GiB contro 18; build diversa.
- **Confrontabili, sul sottoinsieme A,B,C (17 richieste)**: c1 (Daily 0.1.45, 2 posti) legge **683.384 token in 507,8 s = 1346 tok/s** contro R0 0.2.6 **602.7 K in 387 s = 1558 tok/s** (+16% a velocità, -12% token: ordine di servizio diverso). c2 (batch + PIPED_CONCURRENT 0.1.45) legge **181.162 token in 231 s**, la 0.2.6 R3 **181.7 K in 200,6 s** (-13% di tempo; lettura mista 694-706 contro 893-915 tok/s, +27-31%).
  In scrittura mista c2: 14 t/s aggregati T (9-11 N) contro 18-19 (14-15 N) di R3/R3L; (b) c2b 33 contro 42-44. La 0.2.6 è dunque ~13-30% meglio in lettura mista e simile o un po' meglio in scrittura.
- 8 agenti (`replay_q1-b4-8ag`, 0.1.45, `--batch 4` con 4 slot): 1139 s contro 1583 della sessione di allora; TTFT p50 75 / p90 390 s; mai provato sulla 0.2.6.

## 4. Tabella finale

Legenda: (a) = una lettura sola; (b) = >=2 scrivono, nessuno legge; (c) = uno legge e altri scrivono. T-N = i due metodi di §2 (il vero è fra i due; per R3/R3L la stima prudente di (b) è 35-45). «S» = stima, non misura.

| configurazione | tempo per finire s | TTFT medio / p90 s | prefill in (a) tok/s (grande) | scrittura aggregata in (b) t/s | in (c): lettura tok/s (grande) + scrittura t/s |
|---|---:|---:|---:|---:|---|
| ORIGINALE (sessione vera) | 1439 | 230 / 436 | 1143 (1221) | solo 1 scrive: 62 | non esiste (server seriale) |
| R0 senza batch (4 corse) | 438 (410-449) | 66 / 119 | 1551 (1765) | solo 1 scrive: 74 | non esiste (server seriale) |
| R0 + cache grande (S, non misurata) | 223-233 | ~31 / ~67 | ~1550 | solo 1 scrive: 74 | non esiste |
| R1 gruppo seriale (default 0.2.6) | 354 | 31 / 93 | 664 | 34-53 (motore: 52 righe/s) | 555 (691) + 8-13 |
| R2 `--batch-groups 2` | 251 | 12,9 / 21,5 | 776 | 24-30 | 1054 (1680) + 5-10 (scrittori quasi fermi) |
| R3 + PIPED_CONCURRENT | 243 | 19,3 / 38,1 | 944 | 44-59 | 915 (1520) + 15-19 |
| R3L (stessa config, build leve026; 6 corse) | 238 (229-245) | 18,7 / 42,0 | 968 | 42-61 | 893 (1500-1573) + 14-18 |
| L1 PIPED_MTP | 243 | 20,8 / 58,9 | 1013 | 46-61 | 854 (1562) + 17-22 |
| L2 PW_WITH_BATCH | 250 | 13,9 / 19,1 | 760 | 33-63 | 985 (1522) + 7-14 |
| L3 PIPE_ADAPT_EVERY | 231 | 18,1 / 55,1 | 1053 | 35 (N non affidabile) | 893 (1571) + 17-18 |
| L4 righe attive + checkpoint | 245 | 17,8 / 37,6 | 913 | 42-62 | 881 (1499) + 15-19 |

Limiti: R1, R2, R3 e ogni L hanno **una sola corsa** (R3L sei, R0 quattro): la variabilità di R3L (229-245 s, TTFT p90 28,8-58,9 s) è il metro del rumore; i `TERNA INSTABILE` di `ANALISI_20261027.txt` valgono. I token generati variano di ±10% fra corse. I metodi T e N non vedono l'istante dei token: (b) e (c) sono stime, sicure solo dove il motore le stampa (R1 finestre, R3 righe durante le letture).

## 5. Cosa manca per una misura completa

1. **R0c: Daily senza batch ma con la cache grande** (`--conversation-cache-mib 18432 --conversation-cache-slots 16` e le riserve), 20 minuti. Dice quanto del -45% è cache e quanto è batch; la stima S dice 223-233 s. È la prova più importante: se la stima regge, a 3 agenti il batch serve solo al TTFT.
2. **6 e 8 agenti sulla 0.2.6 (mai provati)**; `--dup N` duplica le sessioni rimaste dopo `--only`. Dalla cartella `corse_2080ti/20261026_leve` (PC libero, nessun `strata.exe`, Jump Desktop annotato; una corsa = 25-40 minuti):
```
C="C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti"   # Git Bash; la prima volta aggiungere --dry (stampa il piano, niente GPU)
E="--conversation-cache-mib 20480 --conversation-cache-slots 16"
R4="--vram-reserve-mib 1905 --vram-reserve-later-mib 700"; R8="--vram-reserve-mib 3400 --vram-reserve-later-mib 1100"
run() { # tag, argomenti del replay, extra del motore
  python -u "$C/20261006_due_schede/bench_lock.py" "FASI-$1" -- python -u -X utf8 "$C/20261019_replay/replay_trace.py" --tag "$1" --t0 3600 --span 1200 $2 \
    --config "$C/20261026_leve/cfg-daily-base.json" --exe D:/ds4_work/strata/Strata/build-026-daily/strata.exe --out-base "$C/20261026_leve/corse" --port 8102 \
    --extra="$3" --env="$4" ; }
run s6-b4g2 "--only A,B,C --dup 2" "--batch 4 --batch-groups 2 $E $R4" "STRATA_PIPED_CONCURRENT=1"   # 6 agenti, 4 slot: due aspettano uno slot
run s6-b8g2 "--only A,B,C --dup 2" "--batch 8 --batch-groups 2 $E $R8" "STRATA_PIPED_CONCURRENT=1"   # 6 agenti, 8 slot (riserva larga del 19/10)
run s8-b4g2 ""                     "--batch 4 --batch-groups 2 $E $R4" "STRATA_PIPED_CONCURRENT=1"   # 8 agenti = A,B,C,P x2, come q1-b4-8ag del 19/10
run r0c     "--only A,B,C"         "$E $R4" ""                                 # R0c: nessun batch, cache grande (3 agenti)
```
   (config, exe e porta come in `coda_leve_026.py`, `comando()`; R0c senza `--batch` né variabili). Con più di 4 agenti la cache conversazioni è il vincolo: 20 GiB bastano per ~8-10 conversazioni da 100 K (RISULTATI.md §C.5), tenere d'occhio «MemAvailable» (sotto 3 GiB il 19/10 la corsa è saltata). Per 6 e 8 agenti ripetere R0c (stessa cache, senza batch) come riferimento.
3. **Misura diretta delle fasi**: oggi il motore non marca l'orario per riga e `replay_trace.py` salva solo primo token e fine. Proposta: (i) nel replay annotare l'istante di ogni chunk SSE (decode per agente per fase, senza metodi T/N); (ii) un orario per riga nel `engine.log` (oggi solo la riga di avvio) per allineare «read N tokens ... decoded R rows» agli istanti. Servono poche righe nel replay; il log del motore è codice del fork (nessun interruttore da inventare qui).
4. **Una seconda corsa per R1, R2, R3 e per ogni leva** (oggi n=1), in terne base-leva-base come `coda_leve_026.py`; in particolare R2 contro R3 per confermare che PIPED_CONCURRENT vale -3% di tempo e +50% di TTFT (12,9 -> 19,3 s) e che L2 si sposta verso R2.
5. **Normalizzare i token generati**: il modello si ferma quando vuole (3.825-4.691 token). Un replay con `max_tokens` uguale al generato originale e `min_tokens` (se il server lo avesse) renderebbe il tempo totale più stabile.
6. Fuori dal batch: **leggere più agenti insieme non è provato** (nessuna configurazione unisce le letture); è la leva che sposterebbe di più il tempo totale, dato che la catena di letture è il 73-87% di tutto.
