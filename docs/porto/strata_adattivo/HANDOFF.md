# HANDOFF — Strata adattivo sulla RTX 2080 Ti (consolidato l'1/10/2026 alle 04:20)

Da leggere per primo se la sessione riparte da zero. Repo `moe-aggressive-commit`, branch
`research/ds4-iq1-subbit-tier-planner`. Commit con pathspec espliciti, formato `OPUS-SEZIONE-Descrizione`, trailer
`Co-Authored-By`, push subito. Regole dell'utente: file del daily intatti; chiave API mai letta, stampata o
committata; download solo con permesso; niente binari di terzi non compilati da noi; **a ogni aggiornamento di questo
file dare il link GitHub**:
https://github.com/imanu86/moe-aggressive-commit/blob/research/ds4-iq1-subbit-tier-planner/docs/porto/strata_adattivo/HANDOFF.md

## 1. In breve
- Macchina: **solo la RTX 2080 Ti 22 GB** (sm_75, PCIe 3.0, 13,1 GB/s), Ryzen 7 5800X (8 core, AVX2), 96 GB di RAM. La
  3060 e' smontata; tornera' in OCuLink. **La seconda scheda e' fuori perimetro per ora** (decisione utente, 1/10).
- Motore: **Strata** (github.com/Niko1221/Strata, MIT) col nostro fork locale. Sugli stessi prompt: Strata 44-45 t/s,
  daily llama ricompilato 12-16 t/s. A 131k di contesto: 35 t/s, prefill 614 t/s.
- Lanciatore pronto per l'utente: `Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat`.
- Il daily di produzione (`D:\ds4_work\bin_elastico_m2`, solo sm_86) **non gira sulla 2080 Ti**; runtime sm_75 pronti
  in `D:\ds4_work\daily_sm75\runtime` (M2) e `runtime-m3` (M3). Il bat del daily non e' stato toccato.

## 2. Cosa usare oggi
- **Lanciatore SOTA** (copia in `lanciatori/`): configurazione `D:\ds4_work\strata\Strata\strata-2080ti-sota.json` →
  `build-0129\strata.exe` (0.1.29 + patch nostre 0001-0008), `--elastic` (cache a due zone), riserva di avvio 1393 MiB,
  contesto 139264, KV int8, tabella PLE in lettura diretta, `env.STRATA_WATCHDOG_S=240`; porta 8100 solo su 127.0.0.1;
  la chiave solo dalla variabile `STRATA_API_KEY`; si ferma se strata.exe o llama-server sono gia' accesi.
- **Candidato non ancora promosso:** `build-0130\strata.exe` = 0.1.30 + le 13 patch (sezione 3). Per riga ~4% meglio
  nelle voci di GPU. Prima di metterlo nel lanciatore: prova sotto pressione (`prova_hog.py`) e prova a 131k
  (`--profilo lungo_131k`), perche' la 0.1.30 ha cambiato il prestito al prefill e l'elastica e' stata adattata.

## 3. Il clone `D:\ds4_work\strata\Strata`
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
  `build-0129\` (quello del lanciatore); `build\` = 0.1.21 sm_86; `build-sm75\` = 0.1.21 sm_75. Banco dei kernel:
  `D:\ds4_work\strata\build-bench.bat` (target `native_expert_bench`, per ora punta a `build-0129`).
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
| sotto 4 GB di pressione per 60 s (due zone) | 4.096 token in 95,9 s | — | calo a passi da ~1 GiB, nucleo intatto (3060: 146 s / 170 s) |

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

## 8. L'originale (controllato l'1/10 mattina)
- **0.1.30** ha gia': piu' conversazioni in RAM (`--conversation-cache-mib 8192 --conversation-cache-slots 4`, opt-in);
  modalita' poca RAM «residente» (`--resident-experts`: in RAM solo gli esperti che la GPU non tiene); prompt da 1-4k
  +17-28%; `--idle-unload`, `POST /unload|/load`; RTX 20 ufficiali dalla 0.1.27.
- **Esperti divisi su due schede** esistono gia' («CUDA1–3 expert experiment», `docs/SECOND_GPU.md`,
  `--expert-cache-device1 N`): per quando torna la 3060.
- PR aperte da seguire: #242 (= la nostra 0007, piu' completa: anche il kernel denso), #270 (attenzione del prompt sui
  tensor core di Turing: prefill +12%), #317, #315, #241, #292 (esperti NVFP4: decodifica piu' semplice), #286/#285.
- Fork: niente sui kernel (Volta, AMD, API Codex). L'originale esce piu' volte al giorno: riallinearsi spesso.

## 9. Prossimi passi, in ordine
1. Promuovere `build-0130` nel lanciatore dopo la prova sotto pressione e quella a 131k (sezione 2).
2. PR rimaste: #270 (misurare col profilo `lungo_131k`), #317 (blocco iniziale), #315, #242 al posto della 0007.
3. Provare le due funzioni nuove della 0.1.30 nell'uso reale: `--conversation-cache-*` (agente + subagenti) e
   `--resident-experts` (RAM).
4. Robustezza al carico degli altri programmi: priorita' sotto carico vero (4-5 core occupati), meno thread del pool
   (`--pool-workers`), quota PCIe adattiva.
5. Quando torna la 3060: una scheda / esperti divisi / strati divisi sugli stessi prompt.
6. Daily: solo se serve come riserva (runtime sm_75 pronti; M4 = ridimensionamento che conserva il contenuto).

## 10. Strumenti e comandi
- Prova sul motore: `python strumenti/prova_sm75.py --exe <strata.exe> --riserva 1393 --elastic --nome X
  [--profilo rapido|lungo_131k] [--env K=V] [--arg --opzione=valore] [--priorita high|above]`; poi
  `python ../strata_prova/costo_passata.py etichetta=D:\ds4_work\strata\f0\strata_X.log` e la riga `stage 0:` del log.
- Pressione: `python strumenti/prova_hog.py --elastico si --exe <strata.exe> --hog-mib 4000 --nome X`.
- Kernel: `native_expert_bench.exe <shard1.gguf> [strato] [esperti] [token] [iterazioni] [same]` (PATH con CUDA 12.6\bin).
- Profilo: `strumenti/prova_nsys_cli.py` + `strumenti/analizza_nsys.py`. Daily di laboratorio:
  `strumenti/daily_rapido.py [--runtime DIR] [--env K=V]`. Fork: `../strata_prova/fork_strata.py`.
- Regole di misura: Jump Desktop spento; niente `nvidia-smi` a ripetizione durante una corsa; motori alternati nella
  stessa sessione; confrontare le voci per finestra e i ms per riga, non solo i t/s (il testo cambia).

## 11. Decisioni e idee dell'utente
1. Si lavora su Strata (MIT); il daily solo come riserva. Prima la velocita'.
2. Cache a due zone (fatta). Niente doppione in RAM degli esperti fissi (l'originale: `--resident-experts`).
3. Con l'OCuLink: 2080 Ti piena e fissa + 3060 che ruota, oppure esperti divisi (sezione 8); doppioni dei piu' caldi
   solo per servire due conversazioni in parallelo.
4. Limite da superare: una sola conversazione in cache (l'originale: `--conversation-cache-*`).
