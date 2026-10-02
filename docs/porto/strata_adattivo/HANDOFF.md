# HANDOFF — Strata daily sulla RTX 2080 Ti (0.1.31 + HC/vector/PR315, elastica e KV 262k)

Da leggere per primo se la sessione riparte da zero. Repo `moe-aggressive-commit`, branch
`research/ds4-iq1-subbit-tier-planner` (autorizzato dall'utente per questa ripresa). Commit con pathspec espliciti,
formato `MODELLO-SEZIONE-Descrizione` col modello autore effettivo, trailer
`Co-Authored-By`, push subito. Regole dell'utente aggiornate: **tutte le patch validate vanno integrate e
promosse nell'operativo dopo la prova combinata**; il precedente vincolo di non toccare il lanciatore
e' superato da questa richiesta esplicita. Chiave API mai letta, stampata o
committata; download solo con permesso; niente binari di terzi non compilati da noi; **a ogni aggiornamento di questo
file dare il link GitHub**:
https://github.com/imanu86/moe-aggressive-commit/blob/research/ds4-iq1-subbit-tier-planner/docs/porto/strata_adattivo/HANDOFF.md

## 1. In breve
- Macchina: **solo la RTX 2080 Ti 22 GB** (sm_75, PCIe 3.0, 13,1 GB/s), Ryzen 7 5800X (8 core, AVX2), 96 GB di RAM. La
  3060 e' smontata; tornera' in OCuLink. **La seconda scheda e' fuori perimetro per ora** (decisione utente, 1/10).
- Motore: **Strata** (github.com/Niko1221/Strata, MIT) col nostro fork locale. Misure storiche su prompt brevi:
  Strata 44-45 t/s, daily llama ricompilato 12-16 t/s. Daily combinato realmente promosso, a 131k:
  **38,995 t/s decode, 822,66 t/s prefill** (1/10, cache auto/elastica). Non confondere profondita' e capienza KV.
- Lanciatore pronto per l'utente: `Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat`.
- Il daily di produzione (`D:\ds4_work\bin_elastico_m2`, solo sm_86) **non gira sulla 2080 Ti**; runtime sm_75 pronti
  in `D:\ds4_work\daily_sm75\runtime` (M2) e `runtime-m3` (M3). Il bat del daily non e' stato toccato.

## 2. Cosa usare oggi
- **Lanciatore SOTA** (copia in `lanciatori/`): configurazione `D:\ds4_work\strata\Strata\strata-2080ti-sota.json` →
  **`build-0131-daily\strata.exe`**, 0.1.31 + nove patch locali + HC/GDN FP16 + dequant vettoriale + #315.
  Il BAT usa il server della stessa build in **`build-0131-daily\source\serve\server.py`**.
  `--elastic` (cache a due zone), riserva di avvio 1393 MiB,
  contesto 262144, KV int8, residenti 32768, tabella PLE in lettura diretta, `env.STRATA_WATCHDOG_S=240`; porta 8100 solo su 127.0.0.1;
  la chiave solo dalla variabile `STRATA_API_KEY`; si ferma se strata.exe o llama-server sono gia' accesi.
- **Promozione operativa completata alle 21:26 l'1/10:** parita' del kernel combinato superata,
  riferimento e candidata entrambi con cache auto/elastica e due richieste 131k/1024 token completate.
  Prefill **714,58 → 822,66 t/s (+15,12%)**, TTFT **184,263 → 160,347 s**;
  decode **37,866 → 38,995 t/s**, costo per riga **22,350 → 22,003 ms**. Singolo confronto
  della combinazione, cache e testo/MTP variabili; nessun carico artificiale.
  SHA256 exe `a74e4dadcd4fbb9e71b5cb0ae66922453c6a44a2704db25ddfb5e81601c5f766`.
  JSON e BAT precedenti salvati in `D:\ds4_work\strata\ripristini\20261001_212635_0131_daily\`;
  #270 conservata. Logits/retrieval precedenti limitano la validazione FP16: qualita' generale
  non misurata; a quella promozione riempimento 250k non ripetuto nella combinazione elastica.
  **Ora completato il 2/10 sul daily operativo**, come riportato sotto.
  Dettagli **`PROMOZIONE_DAILY_0131_1_OTTOBRE.md`**, evidenza `corse_2080ti/20261001_daily_0131/`.
  Processi lab chiusi, daily spento, **VIA a OCGC-IA e PROMO**; nessun'altra corsa programmata.
  **Le tappe del 1/10 qui sotto sono storiche; seguono prima le prove e la ricognizione del 2/10.**
- **Prove concluse il 2/10 alle 05:03, #439 non promossa:** daily operativo a74e,
  **250022 token reali, retrieval al centro riuscito**, richiesta 566,61 s, prefill 442,4 t/s.
  Solo 13 token generati: **non e' una misura robusta del decode a 250k**; curva KV/t/s ancora aperta.
  Cache sempre auto/elastica, nessun carico artificiale. Port #439 compilato sulla combinazione daily:
  **34 parita' gather superate**, A/B/A stesso exe candidato con gather singolo/batch/singolo,
  prompt 131248 nuovo + secondo prompt riusato, due output di 1024 token per corsa.
  Prefill **852,99 / 849,50 / 833,67 t/s**, batch **+0,73%** sulla media A, variazione A/A **2,29%**:
  beneficio non dimostrato. Decode **39,684 / 38,553 / 39,004 t/s**, non attribuibile al gather.
  Primi logits finiti e stesso argmax, ma anche A/A non bit-identico nel profilo elastico.
  Candidata conservata `build-0131-pr439`, SHA256 `686be366da45626d4f67ad696b152c862f95b74b46a7c4445a5bfd52ce084a51`.
  **JSON/BAT/Desktop e daily a74e preservati**; non eseguito il riempimento 250k della candidata dopo l'esito A/B/A.
  Rapporto `RISULTATI_PR439_2_OTTOBRE.md`, evidenza `corse_2080ti/20261002_pr439/`, patch `0021-PR439-*`.
  Seconda finestra 04:48–05:03, entro 30 min. Processi propri chiusi, **VIA a OCGC-IA/PROMO alle 05:04**.
  **Prossima priorita' #363 decode**, non iniziata; nessun altro test/monitoraggio programmato.
  Attendere una nuova richiesta dell'utente prima di usare ancora la GPU.
- **Ripresa del 2/10, ricognizione completata senza prove GPU:** upstream **0.1.34**
  `1678de333d0e`, 39 commit dalla precedente scansione; 422 fork elencati, 420 confrontati,
  41 con commit propri, due eccezioni esplicite; 59 PR aperte alla lettura finale.
  Fork2080Ti invariato. **Prima candidata individuata prefill #439** (gather, IQ3_XXS/Windows/PCIe3.0,
  +3,6–4,3% dell'autore), alternativa alla #372; **ora provata senza vantaggio dimostrato sopra**.
  **Decode #363** resta la prossima priorita' (beneficio contenuto).
  #413 recurrence richiede sm80+ e non accelera quel kernel su2080Ti; #443 sperimentale.
  Fix server disconnect #430/#431 e metodo numerico #410 letti. Curva contesto ancora da fare;
  riempimento250k della combinazione elastica completato nella prova sopra. **Daily attuale preservato**.
  Rapporto `RICERCA_FORK_2_OTTOBRE.md`, snapshot `ricognizioni/20261002/`.
- **Validazione completata e lanciatore aggiornato (1/10):** 4.000 MiB di pressione per 60 s, 4.096 token in 99,2 s,
  nucleo fisso preservato, nessuno stallo; entrambe le richieste a 131k completate, 41,8 t/s e 20,4 ms per riga.
  Dettagli: `RISULTATI_1_OTTOBRE.md`, log in `corse_2080ti/20261001_0130_validazione/`. Confronti col 30/9 storici,
  senza A/B nella stessa sessione: non attribuire tutto il guadagno alla versione.
- **Ripristino 0.1.29:** copie del JSON operativo e del bat del Desktop prima della promozione in
  `D:\ds4_work\strata\ripristini\20261001_0130\`; istruzioni nel documento dei risultati. `build-0129` conservata.
- **Contesto richiesto dall'utente: circa 250k**, cioe' 262.144 token (come il precedente daily). Configurazione
  candidata in `lanciatori/strata-2080ti-256k.json`, KV int8 e residenti in VRAM 32.768. **Capacita' 262.144 provata**
  su due prompt a 131k: avvio 61 s, KV in RAM bloccata 3,09 GiB, decode 43,0 t/s, prefill freddo 663 t/s,
  nessuno stallo; RAM disponibile minima 32,59 GB. Dettagli in `RISULTATI_KV262K_1_OTTOBRE.md`.
  Il riempimento fino a circa 250k era allora da provare; ora completato sulla candidata HC nella finestra serale.
  **JSON operativo a 262.144**, con #270; riempimento reale 250k non ancora provato su questo lanciatore.
  L'utente ha abilitato l'accesso completo e autorizzato la promozione, poi richiesto standby;
  **ha ripreso il lavoro l'1/10 dichiarando la macchina libera** (prove #315 qui sotto).
- **PR #270 validata l'1/10 in build separata:** 8 casi di parita' numerica superati, zero fallimenti;
  KV 262.144 e prompt 131k: prefill **808,91 contro 661,76 t/s (+22,24%)**, primo token **162,98 contro 199,10 s**.
  Decode 43,90 contro 42,22 t/s, senza attribuire la differenza alla patch. Primo avvio 223 s, riavvio 61 s:
  rallentamento del caricamento non ripetuto, causa non identificata. Nessun carico artificiale o motore rimasto
  acceso. **Promossa nello stesso lanciatore Desktop**, in `D:\ds4_work\strata\Strata\build-0130-pr270\strata.exe`;
  hash identico alla candidata verificata. Backup JSON e BAT prima della promozione in
  `D:\ds4_work\strata\ripristini\20261001_060447_pr270_262k\`; build-0130 conservata. Sorgenti del clone intatti.
  Verificati Python del lanciatore, parser server e help eseguibile; solo exe e max-context cambiati nel JSON.
  Dettagli e limiti in `RISULTATI_PR270_1_OTTOBRE.md`, evidenza `corse_2080ti/20261001_pr270/`.
- **PR #315 provata l'1/10, candidata conservata:** controllo HC bit per bit superato su sm75,
  v3 selezionata; kernel a 2/4 token −36,6%/−43,8% nel banco breve. Sul modello, prima serie
  elastica A/B/A 39,34 / 42,39 / 44,65 t/s, con cache e CPU diverse: non causale. Con cache
  fissa di laboratorio (budget 5.000, 6.705 slot reali): decode **39,78 → 41,22 t/s (+3,62%)**,
  costo per riga **21,074 → 20,789 ms (−1,35%)**, prefill **754,60 / 754,34 t/s**.
  Output e accettazione delle bozze diversi: beneficio contenuto da confermare. KV sempre 262.144,
  prompt sempre circa 131k; dieci richieste lunghe accettate completate, nessun carico artificiale.
  Una prova fissa a budget 6.600 e' stata interrotta/esclusa per zero VRAM libera: ora il banco
  rifiuta prima dei prompt una cache fissa con meno di 1.000 MiB liberi. Lanciatore ancora #270.
  Candidata `.codex_runs/strata_pr315_20261001/strata.exe`; integrazione preserva #258 e #270,
  sostituisce HC opt-in #186. Dettagli: `RISULTATI_PR315_1_OTTOBRE.md`, evidenza
  `corse_2080ti/20261001_pr315/`, patch `0015-PR315-HC-bitwise-*.patch`, strumento `compila_pr315.py`.
  Pubblicazione inizialmente rinviata dal profilo di accesso in sola lettura su `.git` e senza
  scritture su `D:\ds4_work`/Desktop; l'accesso completo e' tornato nella ripresa successiva.
  **A questa tappa nessuna promozione della #315; ora inclusa nel daily combinato sopra.**
  Processi lab chiusi e hash/configurazione operativa #270 verificati alla precedente pausa.

- **Pausa precedente della 0.1.31, prima della ripresa serale (1/10):** nove patch
  locali portate e ricostruzione riproducibile; controlli IQ/MMVQ/GDN/QSA superati.
  Dequantizzazione vettoriale: 18 confronti numerici superati e A/B/A a cache fissa 4.200
  (5.621 slot effettivi), KV262144/prompt131k: prefill **752,52 / 756,44 / 754,99 t/s**,
  vantaggio circa **0,36%**, nessuna promozione. Sei richieste lunghe completate.
  Decode 36,828 / 39,875 / 38,403 t/s con testo/MTP diversi; non attribuirlo al kernel di prefill.
  HC/GDN FP16 compilata separatamente, 12 controlli delle copie superati; 69.729 valori
  dei pesi non esatti dopo conversione FP16. **Prova sul modello/qualita' ancora da fare.**
  A quella pausa il prompt reale 250k era preparato ma non eseguito; prima prova nei risultati serali sotto. Dettagli in
  `RISULTATI_0131_FORK_1_OTTOBRE.md`, evidenza `corse_2080ti/20261001_0131_fork/`, patch
  `patches/su-0.1.31/`. Lanciatore #270 e hash preservati, processi del laboratorio chiusi.
  OCGC-IA informata della disponibilita' GPU rispetto a Strata; coordinarsi prima della ripresa.
  **Non avviare altri test o monitoraggi: attendere una nuova richiesta dell'utente.**

- **Finestra serale conclusa l'1/10:** tre corse entro 30 minuti, macchina libera e nessun
  carico artificiale. HC/GDN FP16 + diagnostica dei primi logits sul server persistente:
  prefill **725,83 → 828,53 t/s (+14.15%)**, TTFT **181,432 → 159,000 s** a 131k;
  decode aggregato 37,409 → 36,489 t/s, output/MTP diversi. Logits finiti ma non bitwise,
  argmax primo token uguale sui due prompt lunghi; verifica generale della qualita' aperta.
  **Prima prova reale 250k completata sulla candidata:** 250022 token runtime, ago a meta'
  recuperato. Non e' una validazione del lanciatore elastico operativo. Nessuna promozione.
  Upstream ora 0.1.32 (`c499bd102e`), 380 fork confrontati, 39 avanti, zero errori; fork 2080ti
  invariato. Piste nuove #372 gather, #374 PLE, #378 KV VMM (non applicabile direttamente
  con kv-resident), #407 policy adattiva. Dettagli `RISULTATI_SERA_HC_FP16_1_OTTOBRE.md`,
  evidenza `corse_2080ti/20261001_sera_hc_fp16/`, patch diagnostica `0019`.
  **Carichi chiusi e via dato a OCGC-IA. Nessuna ulteriore corsa Strata programmata.**

## 3. Il clone `D:\ds4_work\strata\Strata`
- **Daily corrente:** bundle `build-0131-daily\`, sorgenti completi in `source\`, server della
  0.1.31 e metadati di compilazione/promozione. Il checkout sotto resta a 0.1.30 +13:
  ricompilarlo direttamente non ricostruisce il daily. Usare `strumenti/compila_daily_0131.py`
  con gli input validati; composizione e hash nel rapporto della promozione.
- `main` = **v0.1.30 (30ec18e) + 13 commit** (copie in `patches/su-0.1.30/`, ricostruibile con `git am`):
  1. 0001 traccia di instradamento con fflush · 0002 blocchi del prompt allineati ai punti di ripresa
  2. 0003 cache esperti elastica `--elastic` (arena VMM) · 0004 **due zone** (nucleo fisso + coda di al massimo
     `--elastic-tail-mib`, predefinito min(6144, meta'), che ruota, cala a passi di `--elastic-shrink-step-mib` e si
     presta al prefill; crescita sul minimo della finestra con margine = rumore, attesa che raddoppia dopo un calo) ·
     0005 lettura di ~0 MiB = passo pieno · 0009 adattamento al prestito per partecipante (`pf_parts`) della 0.1.30
  3. 0006/0008 `native_expert_bench` (banco del kernel degli esperti) · 0007 kernel degli esperti a decodifica unica
     (`STRATA_EXPERT_MULTI=0` = originali; identico bit per bit)
  4. PR dell'originale applicate: **#258** kernel GDN `down` TILE=1280 per sm_75 · **#284** commit senza attesa
     (`STRATA_COMMIT_SYNC=1` = attesa) · **#186** hyper-connection in 2 kernel (**opt-in `STRATA_GR_V3=1`**, non
     identica bit per bit)
- Tag di ripristino: `pre-0129-rebase` (0.1.21 + 3 patch), `pre-0130-rebase` (0.1.29 + 8 patch). Rami delle PR scaricati:
  `pr-258 pr-186 pr-284 pr-242 pr-270 pr-317 pr-315`. I commit del clone restano locali (pubblicare il fork = chiedere).
- Build (CUDA 12.6, sm_75+86): `../strata_prova/build-strata-0130.bat` → `build-0130\`; `build-strata-0129.bat` →
  `build-0129\` (ripristino precedente); `build\` = 0.1.21 sm_86; `build-sm75\` = 0.1.21 sm_75. Banco dei kernel:
  `D:\ds4_work\strata\build-bench.bat` (target `native_expert_bench`, per ora punta a `build-0129`).
- Build operativa `build-0130-pr270\`: copia della candidata verificata; eseguibile, PDB, nuovo oggetto/libreria,
  sorgente CUDA della PR e metadati conservati li'. Il checkout `main` resta a +13 commit: la #270 non e' stata
  applicata ai suoi sorgenti. Prima di ricostruire questa variante usare `strumenti/compila_pr270.py` o applicare
  la patch preservata; una normale ricompilazione del checkout base non include #270.
- Dati: `D:\ds4_work\strata\Strata-data` (pack iq3_xxs, mtp). Modello: GSQ-RCO IQ3_XXS in `Downloads`.

## 4. Misure (profilo `rapido`: 4 prompt corti + copia di codice da 4k; t/s aggregati)
| quando / cosa | t/s | ms per riga | note |
|---|---:|---:|---|
| 3060, Strata 0.1.21 fissa / elastica, quasi ferma (29/9) | 22,7 / 24,8 | 37,5 / 34,2 | |
| 3060 sotto OktoCGControl | 13,2 / 13,7 | 64,7 / 62,3 | la CPU e' il collo |
| 3060, daily M2 con gli agenti che compilavano | 6,2 | — | cache a 0 nel 34%, RAM a 0,7 GB |
| 2080 Ti, daily M2 / M3 (tetto 140 slot) ricompilati | 12,4 / 15,6 | — | si svuota a ogni prefill |
| 2080 Ti, Strata 0.1.21 fissa | 37,6 | 22,4 | 6.532 esperti, colpi 73-89% |
| 2080 Ti, Strata 0.1.29 + patch: fissa / elastica / due zone | 45,1 / 43,4 / 44,3 | 18,9 / 19,3 / — | pari entro il rumore |
| 2080 Ti, 0.1.30 + patch nostre (`n0130_base`) | 44,8 | 19,3 | GPU 23,9 ms e commit 1,04 ms per finestra |
| + #258 | 44,9 | 19,0 | GPU 23,4 ms |
| + #284 (+ #186 con `STRATA_GR_V3=1`) | — | — | GPU 22,8 (22,6) ms, commit 0,37 ms; totale falsato da Codex e indicizzazione |
| 0.1.30 + patch + PR, altri ~2 core (ultima prova) | 43,8-45,4 | 19,5-18,8 | commit 0,32-0,34 ms |
| a 131k (0.1.29 + patch) | 35,1 | 24,2 | prefill 614 t/s; 1,64 token per finestra |
| a 131k (0.1.30 + 13 patch, 1/10) | **41,8** | **20,4** | prefill 628,8 t/s; 1,72 token per finestra; altri 0,86 core in media |
| KV 262.144, prompt 131k (0.1.30 + 13 patch, 1/10) | **43,0** | **19,8** | prefill 663 t/s; KV in RAM 3,09 GiB; carico reale, nessun hog |
| + #270, KV 262.144, prompt 131k (1/10) | **43,9** | **19,3** | prefill 809 contro 662 t/s nel riferimento successivo; primo token -36,1 s |
| sotto 4 GB di pressione per 60 s (due zone) | 4.096 token in 95,9 s | — | calo a passi da ~1 GiB, nucleo intatto (3060: 146 s / 170 s) |
| sotto 4 GB di pressione per 60 s (0.1.30, 1/10) | 4.096 token in 99,2 s | — | cache 7.291 → 4.400 slot, nucleo 3.357 preservato, poi 4.461 slot |

Dettagli e log: `RISULTATI_2080TI_30_SETTEMBRE.md`, `RISULTATI_ELASTICO_29_SETTEMBRE.md`, `corse_2080ti/`,
`../strata_prova/RISULTATI_28_SETTEMBRE.md`.

## 5. Dove va il tempo (2080 Ti, finestra di verifica ~45 ms, ~2,05 token)
- Per voce (`STRATA_SPLIT_TIMING=1`): la CPU aspetta la GPU ~23-24 ms; la GPU aspetta la CPU (esperti mancanti + piano)
  ~14-15 ms; preparazione 0,7 ms; commit 1,0 ms (0,35 con #284); resto ~5 ms (testa MTP, lancio).
- Tempo GPU per gruppi di kernel (Nsight Systems, `corse_2080ti/nsys/`): attesa della CPU 16%, esperti via PCIe ~9%,
  esperti ~22%, ricorrenza GDN ~18%, pesi densi ~19%, resto ~15%. GPU occupata al 94%, buchi fra kernel 0,2 us.
- Kernel degli esperti (`native_expert_bench`): caso base ~195 GB/s su 616; con i pesi in L2 solo −5-7% → **il limite e'
  il calcolo della decodifica i-quant, non la memoria**.

## 6. Provato e scartato (con le misure)
- Bozze piu' lunghe (`--spec-min-p 0.3`): 43,2 contro 45,1 t/s; una riga in piu' costa ~10,7 ms, le bozze aggiunte
  passano al 37%.
- Quota PCIe 0,5 contro lo 0,28 della sonda: 23,8 ms per riga contro 18,9.
- Scambi a ogni passata (`--adapt-every 1 --adapt-swaps 24`): colpi piu' bassi, 19,3 contro 18,9.
- Prefetch per recenza (`strumenti/simula_prefetch.py`): +10 punti di colpi ma 399 MiB di copie per finestra sul PCIe 3.0;
  mancanti prevedibili dalla recenza 26-57%.
- `--ple-io mmap`: toglie il blocco della prima richiesta lunga ma la preparazione sale a 6-80 ms per finestra → tolto.
- Riserva di avvio 500: la sessione resta lenta (31 t/s). Regola: **avvio largo (1393), poi l'elastica cresce**.
- Priorita' alta di `strata.exe` (`prova_sm75.py --priorita high`): nessun effetto con gli altri a ~2 core; non provata
  con 4-5 core occupati.
- Nsight Compute sulla finestra di verifica: impossibile (ncu esegue un kernel alla volta e il `wait_flag` aspetta la
  CPU per sempre); servono anche i contatori GPU abilitati dall'utente (`ERR_NVGPUCTRPERM`).
- Doppioni degli esperti sulla stessa scheda: inutili (stessa banda, meno esperti diversi).

## 7. Cosa pesa nell'uso reale
- **Altri programmi sulla CPU**: Jump Desktop collegato (4,5 core + 1/3 della GPU) dimezza la velocita'; Codex,
  indicizzazione di Windows, OneDrive, compilazioni degli agenti portano il pool CPU da 15 a 20+ ms per finestra.
  Ogni corsa registra la CPU di tutti i processi (`cpu_*.jsonl`, riassunto con `strumenti/cpu_altri.py`).
- **Prima richiesta lunga dopo l'avvio**: una volta si e' bloccata oltre 60 s (lettura diretta della tabella PLE);
  rimedio per ora `STRATA_WATCHDOG_S=240`. Da provare la PR #317 (`STRATA_SSD_KEEPALIVE`).
- **Potenza**: 2080 Ti ~110-120 W in generazione (punte 160, limite 250); totale stimato alla presa 250-300 W in
  generazione, 110-140 a riposo. L'utente leggera' il valore vero dall'UPS.

## 8. L'originale (aggiornato il 2/10; sotto anche la ricognizione storica)
- **2/10, 04:16 Roma:** release0.1.34, SHA `1678de333d0e`, +39 commit da0.1.32.
  Molti cambiamenti AMD/installer; non un guadagno generale sm75. Novita' pertinenti
  #439 gather con test bitwise, #363 decode lean, cancellazione server11ad074262a8.
  La #413 ha gate compute capability>=8 e la #443 mantiene esperimenti opt-in.
  Non sommare #439/#372/gather2080Ti. Fork2080Ti fermo a `235350960d85`.
  Dettagli, eccezioni dei confronti e priorita' in `RICERCA_FORK_2_OTTOBRE.md`.
- **Ricognizione aggiornata l'1/10, 10:28 UTC:** upstream **0.1.31**, SHA `9259cad4cf`, 61 commit
  dopo 0.1.30. Gia' incluse #242 (anche densa), #270 con follow-up, #258 e #186 opt-in: non riapplicarle
  alla nuova base. #284 ancora da mantenere. 326 fork accessibili confrontati, 35 con commit propri,
  46 PR aperte censite. Dettagli e snapshot in `RICERCA_FORK_1_OTTOBRE.md` e `ricognizioni/20261001/`.
  Fork prioritario **jklnvlink/Strata-2080ti**, 15 commit sopra 0.1.31: dequantizzazione vettoriale
  (+5% prefill dichiarato), HC prefill FP16 (+14% dichiarato), gather raggruppato. Misure dell'autore
  su due 2080 Ti/Coder: da replicare sulla nostra singola scheda/IQ3_XXS. Non sommare percentuali.
  L'utente ha autorizzato di procedere: preparare sorgenti/build 0.1.31 separati nel laboratorio,
  conservare le patch elastiche, provare prima dequant vettoriale e poi HC FP16 completo dei fix.
  Il percorso HC FP16 cambia arrotondamenti: validare logits/qualita', non dichiararlo bitwise.
  Nessuna modifica al lanciatore in questa ricognizione; risultati #315 pubblicati in `00542a8`.
- **0.1.30** ha gia': piu' conversazioni in RAM (`--conversation-cache-mib 8192 --conversation-cache-slots 4`, opt-in);
  modalita' poca RAM «residente» (`--resident-experts`: in RAM solo gli esperti che la GPU non tiene); prompt da 1-4k
  +17-28%; `--idle-unload`, `POST /unload|/load`; RTX 20 ufficiali dalla 0.1.27.
- **Esperti divisi su due schede** esistono gia' («CUDA1–3 expert experiment», `docs/SECOND_GPU.md`,
  `--expert-cache-device1 N`): per quando torna la 3060.
- PR aperte pertinenti: #282 (prefill auto 16k/32k), #317 (SSD), #315 (HC), #320 (profiler), #309
  (riuso conversazioni). #242/#270 chiuse: il lavoro e' upstream pur senza `merged_at`.
  #343 documenta una strada negativa: GEMV BF16 di decode su tensor core sm75 piu' lenta nel banco;
  non confonderla con GEMM HC del prefill. #353 sostituisce #292 per NVFP4, non prioritaria sul nostro IQ3_XXS.
- Fork: ora esiste lavoro concreto sm75 nel fork 2080ti. StrataGP ha misure 5090 ma base molto divergente,
  ammissione sm80+ e molte parti gia' assorbite. Non usare i suoi guadagni come stime per la nostra scheda.

## 9. Prossimi passi, in ordine

**Daily combinato promosso; utente ha ripreso il 2/10 con macchina libera. Ricognizione fatta,
nessun nuovo job GPU avviato o programmato da questa chat.**
HC/GDN FP16, vector e #315 ora sono nel lanciatore operativo, con elastica e KV262144.
Alla prossima ripresa: curva contesto/t/s col medesimo daily/policy (4k,32k,64k,131k,250k),
quality/retrieval piu' ampi e riempimento 250k sulla combinazione elastica; poi **#439 prefill
(alternativa #372), #363 decode**, fix server disconnect/stager, #374.
Valutare porting 0.1.34 senza duplicare #315/commit async gia' upstream. Regola: una patch
validata va integrata, provata nella combinazione operativa e promossa con ripristino.

1. **Fatto l'1/10:** `build-0130` promossa nel lanciatore dopo la prova sotto pressione e quella a 131k (sezione 2).
2. **#270 verificata e promossa nel lanciatore:** patch `patches/da-valutare/0014-PR270-prefill-Turing.patch`, compilazione CUDA 12.6 e
   parita' superate, prefill +22% nel confronto base/candidata/base su KV 262.144. Rimaste #317 (SSD), #315, #242 al posto
   della 0007. Preparazione in `PREPARAZIONE_256K_PR270.md`, misure in `RISULTATI_PR270_1_OTTOBRE.md`.
   Il prompt pieno a circa 250k fu rinviato dall'utente per passare prima alla #270; ora provato sulla candidata HC.
   **Ripresa autorizzata l'1/10 con macchina libera:** #315 compilata e provata, numerica superata,
   kernel piu' rapido, guadagno modello contenuto (+3,62% t/s ma −1,35% ms/riga a cache fissa).
   **Ora inclusa nel daily combinato dopo nuova parita' e confronto elastico.** Priorita' storica dopo la ricognizione:
   base di laboratorio 0.1.31 (ha gia' #242 densa e #270), poi dequant vettoriale e HC prefill FP16
   dal fork 2080ti, separatamente e con parita'/qualita'. Autorizzato dall'utente; clone operativo intatto.
   Misure #315 e piano aggiornato nei rispettivi documenti.
3. Provare le due funzioni nuove della 0.1.30 nell'uso reale: `--conversation-cache-*` (agente + subagenti) e
   `--resident-experts` (RAM).
4. Robustezza al carico degli altri programmi: priorita' sotto carico vero (4-5 core occupati), meno thread del pool
   (`--pool-workers`), quota PCIe adattiva.
5. Quando torna la 3060: una scheda / esperti divisi / strati divisi sugli stessi prompt.
6. Vecchio daily llama: riserva (runtime sm_75 pronti; M4 = ridimensionamento che conserva il contenuto).
   Il daily operativo corrente e' Strata: tenere il lanciatore allineato alle patch validate.

## 10. Strumenti e comandi
- Prova sul motore: `python strumenti/prova_sm75.py --exe <strata.exe> --riserva 1393 --elastic --nome X
  [--profilo rapido|lungo_131k] [--env K=V] [--arg --opzione=valore] [--priorita high|above]`; poi
  `python ../strata_prova/costo_passata.py etichetta=D:\ds4_work\strata\f0\strata_X.log` e la riga `stage 0:` del log.
- Pressione: `python strumenti/prova_hog.py --elastico si --exe <strata.exe> --hog-mib 4000 --nome X`.
- Kernel: `native_expert_bench.exe <shard1.gguf> [strato] [esperti] [token] [iterazioni] [same]` (PATH con CUDA 12.6\bin).
- KV 262k: `strumenti/prova_kv262k.py --nome X --exe <strata.exe>`; `--cache-fissa 5000`
  solo per confronto di laboratorio (toglie elasticita', controlla VRAM iniziale >=1.000 MiB).
  Il pack puo' trasformare il budget richiesto in un numero maggiore di slot; leggere `/metrics`.
  Nel laboratorio 0.1.31 budget 5.000 rifiutato (900 MiB liberi); A/B/A accettata con 4.200.
  `--server-source <sorgenti>` seleziona il server della base; `--needle-lengths` e
  `--retrieval-250k` conservati; nella finestra serale eseguito `--solo-retrieval-250k` sulla HC.
  `--durata-max-s` limita tutta la corsa, `--logits-first` abilita il dump nella build con 0019.
- Profilo: `strumenti/prova_nsys_cli.py` + `strumenti/analizza_nsys.py`. Daily di laboratorio:
  `strumenti/daily_rapido.py [--runtime DIR] [--env K=V]`. Fork: `../strata_prova/fork_strata.py`.
- Regole di misura: Jump Desktop spento; niente `nvidia-smi` a ripetizione durante una corsa; motori alternati nella
  stessa sessione; confrontare le voci per finestra e i ms per riga, non solo i t/s (il testo cambia).
- **Vincolo aggiornato dall'utente l'1/10:** c'e' gia' pressione reale; proseguire senza aggiungere pressione al sistema.
  **Significa niente carichi artificiali per simulare la saturazione**, per esempio hog GPU o stress CPU/RAM.
  Compilazioni e prove normali del motore restano nel lavoro; misurare con il carico reale gia' presente.

## 11. Decisioni e idee dell'utente
1. Si lavora su Strata (MIT); vecchio daily llama come riserva. Prima la velocita'.
   **Chiarimento dell'utente l'1/10 sera: tutte le patch validate vanno nel daily operativo Strata.**
2. Cache a due zone (fatta). Niente doppione in RAM degli esperti fissi (l'originale: `--resident-experts`).
3. Con l'OCuLink: 2080 Ti piena e fissa + 3060 che ruota, oppure esperti divisi (sezione 8); doppioni dei piu' caldi
   solo per servire due conversazioni in parallelo.
4. Limite da superare: una sola conversazione in cache (l'originale: `--conversation-cache-*`).
5. Contesto desiderato circa 250k: 262.144 token. Non confondere il limite del banco a 139.264 con questo obiettivo.
