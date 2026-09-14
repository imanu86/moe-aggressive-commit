# Registro CPU/GPU

Aggiornato il 14 settembre 2026, versione 1.0. Documenti correnti: [piano](PIANO_CPU_GPU_14_SETTEMBRE.md), [protocollo](PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md). Copie canoniche nel repository `moe-aggressive-commit/docs/porto`; copie di consegna in `outputs`.

**Stato corrente:** prototipo del 13 settembre completato; pianificazione dell'integrazione completata; **P0 COMPLETATA, baseline di variabilità inclusa e CHIUSA il 14/9** (snapshot immutabile in `D:\ds4_work\p0_snapshot_20260914\`, fixture congelate in `docs/porto/banco_p0/fixtures/`, banco in `docs/porto/banco_p0/`, corsa di fumo `D:\ds4_work\banco_p0_run\20260914_070200_P0_sper_ibrido_assente_r1`, aggregato in `docs/porto/banco_p0/risultati/aggregato_baseline_libero_20260914.json`); **P1 COMPLETATA** (contratto [P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md](P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md), rapporto [P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md](P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md), strumenti `strumenti_p1_cache_cpu_gpu/`; 36.913 piani confrontati con zero differenze a `cpu_max=0`, controllo negativo con 58.802 differenze, 13/13 scenari dedicati superati con CPU attiva); **P2 IN CORSO** — correzione dei due difetti bloccanti trovati dalla review indipendente. Il motore, i binari di produzione, il lanciatore quotidiano e il modello non sono stati modificati; il server sperimentale è stato acceso quattro volte per P0 (corsa di fumo, sola ricongelatura delle fixture, due blocchi validi della baseline più un blocco interrotto), nessuna misura di velocità oltre alla baseline dichiarata di seguito è stata prodotta da quelle accensioni.

**Prossima azione precisa:** correggere in P2 i due difetti bloccanti della review indipendente (B1 concorrenza in cancel/timeout, B2 contaminazione irreversibile; `docs/porto/p2_esecutore/REVIEW_P2_14_SETTEMBRE.md`), poi E1/E2; compilare ed eseguire il test host-only appena pronta la correzione. Al termine, aprire P3 riusando gli assert degli invarianti 2, 4 e 5 del simulatore di P1 come controlli di stato attorno all'interfaccia host, e battere il riferimento di 24,44 t/s sull'insieme libero registrato in questa chiusura di baseline.

| Fase | Stato | Dipendenza |
|---|---|---|
| Prototipo e audit 13/9 | COMPLETATO | Prove nel rapporto e nello ZIP storico |
| Piano/protocollo 14/9 | COMPLETATO | Richiesta dell'utente di pianificare e documentare |
| P0 — Baseline e fixture | COMPLETATO (baseline di variabilità inclusa) | Nessuna |
| P1 — Contratto cache | COMPLETATO | P0 |
| P2 — Esecutore/lifetime | IN CORSO | P1 |
| P3 — Uno strato reale | DA AVVIARE | P2 |
| P4 — Decode completo | DA AVVIARE | P3 |
| P5 — MTP | DA AVVIARE | P4 |
| P6 — Conferma/preset | DA AVVIARE | P5 |
| P7 — Divario residuo | DA AVVIARE | P6 oppure chiusura motivata della pista CPU |

**Decisioni attive.**

| ID | Decisione | Motivo e prova | Riesame |
|---|---|---|---|
| D01 | Pesi originali, Q4 rinviato | Priorità esplicita dell'utente; prototipo già utile senza conversioni | Solo come esperimento distinto successivo |
| D02 | RAM mappata + callback come candidato | Conferma: 253,5 microsecondi contro 387,7 con copie/flag, caso tre miss/due CPU/sei core | Se il server mostra un costo diverso |
| D03 | Uno/due esperti CPU iniziali; quattro/sei core da confrontare | Tre/quattro esperti CPU più variabili; differenze tra replay raggruppati e singoli | Dopo P4 |
| D04 | Frequenza/recenza attuale; ammissioni CPU separate | Cache reale già validata; commit differito nel piano CUDA | P1 deve dimostrare gli invarianti |
| D05 | MVP con righe GPU valide e peso zero per le route CPU | Forma del graph stabile e nessun ID negativo; richiede nuova misura del lavoro GPU fittizio | Maschera MMVQ solo se necessaria dopo P4 |
| D06 | MTP spento nella prima integrazione | Il prototipo copre un token; evitare di confondere cache, rollback e speculazione | P5 |
| D07 | Strato 2 sulla GPU | Gate/up IQ3_S, codice 21; altri 47 strati IQ2_S, codice 22 | Estensione separata dopo validazione |
| D08 | Fixture immutabili e nuovo A/B | Il filler del banco deriva dai sorgenti; i vecchi 25,08/27,26 differiscono anche per preset | Sempre |
| D09 | Un solo pool per contesto, attesa inattiva fuori decode | Il pool della sonda occupa core anche a riposo; no moltiplicazione per strato | P2 e prova prefill |
| D10 | Nessun numero del microbench diventa t/s generali | 39,19 era copia; 337->242 riguarda un blocco; profiler non additivo | Sempre |
| D11 | Budget di token 1024 in screening / 1536 in conferma per i liberi (768 per qualità strutturata e contesto lungo), al posto dei 512/768 del protocollo | Con `--reasoning on` il caso `L01@corto` ha consumato tutti i 512 token nel ragionamento e prodotto zero testo finale; un output troncato nel solo ragionamento non supera la qualità e con quel budget l'intero insieme libero sarebbe invalutabile. Decisione presa prima delle coppie di baseline | Se il ragionamento viene spento |
| D12 | La variabilità della baseline si misura sul profilo `solo_libero` (8 liberi a contesto corto e a 32k, metrica primaria del decode) con tre coppie A=A a ordine alternato, più un solo blocco `screening` completo come riferimento e prova dello schema a 131k | Un blocco `screening` completo dura circa 80 minuti (sei aghi a 131k), il libero circa 25; la variabilità del prefill è già nota (0,2% da misure precedenti) | Riesame in P6, dove la conferma usa la batteria completa |
| D13 | Ordine deterministico dei miss CPU per P3: i primi miss in ordine di indice unico | Proposto e verificato dal contratto/simulatore P1, già materializzato dal kernel e indipendente dallo stato della cache | Alternative (ordine per frequenza) rinviate a P4 |
| D14 | Decisione dell'utente, 14/9, vincolante: «Prima il B, poi l'A solo se serve». In ogni confronto si lancia PRIMA il candidato B contro il riferimento già noto e registrato; se B mostra il vantaggio, il lato A NON si esegue; se B non mostra vantaggio, si esegue anche A per distinguere una regressione generale (anche A cala) da una specifica del candidato. Niente batterie di controllo lunghe senza un candidato pronto | Le tre coppie A=A e il blocco `screening` completo di D12 erano rumore di controllo senza alcun candidato B da confrontare: misurare la variabilità del controllo da sola non è la domanda che serve, e ogni ora di macchina va spesa contro un candidato reale appena disponibile | Ad ogni nuovo confronto della matrice |
| D15 | Con `--reasoning on` e budget 1024, 14 casi liberi su 16 terminano per lunghezza con testo finale VUOTO (tutto il budget nel ragionamento; solo L04 corto e L04 32k arrivano a `stop`). La misura di velocità resta valida (i token di ragionamento sono generazione, come dice il protocollo), ma la rubrica di qualità sui liberi NON è applicabile in screening: la qualità dei liberi si valuta solo in conferma (P6) con budget 3072 o fino a `stop`, insieme ai casi strutturati S01-S10 e agli aghi che producono testo finale | Osservazione diretta sui due blocchi validi della baseline (`20260914_072049_..._r1` e `20260914_074035_..._lato_B_r1`); spegnere il ragionamento cambierebbe il carico rispetto all'uso reale, scartato per ora come alternativa | Riesame se P6 mostra che 3072 non basta |

**Rischi e verifiche aperte.** Residenti fantasma nel commit differito (P1); costo delle righe GPU fittizie e callback quando CPU=0 (P3/P4); contesa RAM e core (P4); variazione del comportamento libero dovuta all'aritmetica CPU/GPU (P3–P6); riferimenti a buffer nei graph e annullamento in volo (P2/P5); memoria di prefill e ritorno al decode (P5/P6). Job CPU fallito dopo che il gather ha già sovrascritto lo slot: non basta scartare il piano, serve invalidare l'incarnazione e bloccare ogni uso successivo finché non si esegue la pulizia esplicita (scenario `errore_job_cpu`, P1). Deriva rispetto all'HANDOFF del 13/9 §1.1: fra `bin_prod` e `build\bin` differiscono **quattro** DLL, non due — si sono aggiunte `ggml-base.dll` e `llama-common.dll`, ricompilate il 13/9 (trovato in P0). Il protocollo stabilisce come rilevarli, non li dichiara già risolti.

**Review del piano, 14/9:** riesaminati i punti di integrazione e il banco con agenti economici e verifica finale del principale sui sorgenti. Precisati il partizionamento prima dell'assegnazione degli slot/gather, la conservazione degli ID logici, l'alias verso una route GPU reale protetta e il merge CPU dopo la riduzione e prima dello shared expert. Sono decisioni progettuali revisionate, non patch eseguite. Scartata l'etichetta impropria "baseline FreeToken": i 25,08 t/s appartengono al nostro server precedente.

**Evidenze già disponibili.** [Rapporto CPU/GPU](FREETOKEN_IBRIDO_13_SETTEMBRE.md), [prove CPU/GPU](freetoken_ibrido_evidence.zip), [audit FreeToken/Bonsai](FREETOKEN_BONSAI_13_SETTEMBRE.md), [prove audit](freetoken_bonsai_evidence.zip). La conferma del prototipo contiene 45 prove, più controlli aggiuntivi; non è una conferma del server completo.

**Voce da aggiungere a ogni avanzamento.** Data e fase; ipotesi; ID della modifica/revisione; file toccati; configurazioni confrontate; link ai run validi e invalidi; risultato e limite; decisione (proseguire/correggere/chiudere); regressioni aperte; stato dei processi avviati; prossima azione. Una fase è COMPLETATA solo quando la sua consegna e i criteri di uscita sono verificati. Se si scopre un errore di misura, rettificare esplicitamente il riepilogo conservando il run originale.

## P0 — Base riproducibile (14/9)

**Data e fase.** 14 settembre 2026. P0 — Base riproducibile. Consegne A-E eseguite in una sessione. Nessun benchmark dichiarato: le uniche due accensioni del server sono state una corsa di fumo (profilo `fumo`, quattro richieste) per provare che il banco funziona end-to-end, e una seconda accensione di solo sigillo (`-SoloSigillo`, nessuna richiesta misurata) per ricongelare le fixture dopo i difetti che il fumo aveva rivelato.

**Ipotesi.** P0 non verifica un'ipotesi prestazionale. Verifica tre premesse operative: (1) lo stato sperimentale del 14/9 è catturabile in modo immutabile e riproducibile; (2) le fixture possono essere congelate una volta, così che i due lati di un A/B a giorni di distanza leggano input identici anche dopo che i sorgenti sono cambiati; (3) un blocco A/B si avvia, misura e chiude senza `.bat`, senza `pause`, senza toccare `bin_prod` e senza lasciare processi attivi. Tutte e tre risultano soddisfatte, la terza solo dopo una correzione.

**ID della modifica/revisione.** Nessun file del motore, dei binari, del lanciatore quotidiano o del modello è stato modificato. Nessuna ricompilazione. `bin_prod` è stato solo letto.

**File toccati.** Tutti nuovi:

| file | ruolo |
|---|---|
| `D:\ds4_work\p0_snapshot_20260914\` | snapshot immutabile fuori dal repo: 2999 file sorgente + copia di `build\bin`, 253 MB |
| `D:\ds4_work\p0_snapshot_20260914\manifest_p0.json` | manifest di P0 (binari, modello, ambiente, preset redatto) |
| `D:\ds4_work\p0_snapshot_20260914\source_hashes.json` | SHA256 per singolo file sorgente |
| `docs/porto/banco_p0/prepara_fixture.py` | genera una volta il riempimento e il catalogo dei 28 casi |
| `docs/porto/banco_p0/sigilla_fixture.py` | ID token, conteggi esatti, `fixtures_manifest.json` |
| `docs/porto/banco_p0/preset_A.json`, `preset_B.json` | i due lati dell'A/B, leggibili e diffabili |
| `docs/porto/banco_p0/avvia_blocco.ps1` | guardia d'istanza unica, avvio, readiness, banco, chiusura |
| `docs/porto/banco_p0/banco_p0.py` | client SSE, metriche, impronte, sonda di carico, cartella di corsa |
| `docs/porto/banco_p0/aggrega.py` | somma/somma, rapporto per coppia, mediana, bootstrap 95% |
| `docs/porto/banco_p0/fixtures/` | fixture congelate: testo, ID token, hash, attesi, rubriche |

**Configurazioni confrontate.** Oggi nessun confronto: `preset_B.json` è una copia esatta di `preset_A.json`, perché l'opzione dell'ibrido non esiste ancora nel binario. È la forma corretta del lato N della matrice a P0: finché resta così, una coppia A/B misura solo la variabilità del controllo, ed è esattamente la misura che manca. Preset A (sperimentale attuale, ibrido inesistente): binari `qwen38_clean\build\bin`, modello UD-IQ3_XXS, contesto 262144, 64 slot esperti per strato, `--n-cpu-moe 48`, `-b/-ub 2048`, `-t 16`, `-np 1`, KV `q8_0`, `--jinja`, `--reasoning on --reasoning-preserve`, greedy (`temperature 0`, `seed 1234`), MTP spento, `QWEN4EXP_SPARSE_FA=0`, più le sedici variabili BB/BM del lanciatore sperimentale. Tre deviazioni dichiarate dal lanciatore quotidiano: host `127.0.0.1` invece di `0.0.0.0`, avvio diretto dell'eseguibile senza `.bat`, nessun `pause` finale.

**Link ai run validi e invalidi.**

| run | validità | contenuto |
|---|---|---|
| `D:\ds4_work\banco_p0_run\20260914_070200_P0_sper_ibrido_assente_r1` | valido come prova di funzionamento, NON come misura | 2 riscaldamenti identici + `L01@corto` + `S01@corto` |
| accensione di solo sigillo, 14/9 | nessun dato di velocità prodotto | rigenerazione di `fixtures_manifest.json` dopo le correzioni |

Corse non valide: nessuna. Corse interrotte: nessuna.

**Risultato e limite.** Snapshot: l'albero sperimentale non è un repository git (nessun `.git`, nessun HEAD), quindi lo snapshot è una copia con hash per file, non un commit; 2999 file, 253 MB in totale con le DLL; gli shard del modello non sono copiati e non sono hashati per intero (76,3 GiB): dimensione, mtime e SHA256 del primo e dell'ultimo MiB, dichiarato nel manifest. Fixture congelate: riempimento generato una sola volta dai sorgenti del 14/9, 909.830 caratteri da 23 file (`common/arg.cpp` incluso, quindi la domanda tecnica a contesto lungo ha davvero una risposta nel materiale); tagli esatti verificati dal server:

| prefisso | caratteri | token | scarto dal bersaglio |
|---|---:|---:|---:|
| `ctx32k` | 126.766 | 32.768 | 0 |
| `ctx131k` | 529.521 | 131.072 | 0 |
| `aghi131k` | 529.929 | 131.208 | +136, cioè le cinque note operative |

Impronte dei prefissi: `ctx32k` `3a62c0f088f8567e`, `ctx131k` `441d0e5f6d33b227`, `aghi131k` `ec73073434cdd80a`. Gli ID token sono salvati accanto al testo (JSON sotto i 4096 token, int32 little-endian compresso sopra), con l'SHA256 dei byte non compressi. 28 casi: 8 liberi (3 prosa/spiegazione, 2 ragionamento verificabile, 3 codice nuovo con test) a contesto corto e a 32k, 2 di copia/rinomina sugli stessi input del banco precedente, 24 di qualità strutturata (che includono gli 8 liberi, i 5 fatti a contesto lungo e la domanda tecnica), 2 di prefill freddo.

Corsa di fumo: caricamento del modello 201,5 s, tutti gli schemi popolati.

| richiesta | wall HTTP | TTFT primo delta | TTFT primo testo finale | prompt_n | predicted_n | t/s del server | fine |
|---|---:|---:|---:|---:|---:|---:|---|
| riscaldamento 1 | 2,83 s | 2,23 s | — | 61 | 8 | 11,77 | length |
| riscaldamento 2 | 2,00 s | 1,42 s | — | 61 | 8 | 12,01 | length |
| `L01@corto` | 22,64 s | 2,17 s | mai | 145 | 512 | 24,97 | length |
| `S01@corto` | 14,62 s | 2,35 s | 12,95 s | 163 | 291 | 23,62 | stop |

I due riscaldamenti hanno impronta identica (`b626d0e377e6075e`): il determinismo in greedy regge anche su questo binario, quindi l'impronta è utilizzabile come oracolo. Il timing del server include davvero tutto: `wall_HTTP` meno (`prompt_ms` + `predicted_ms`) vale fra +0,014% e +0,78% (mediana +0,18% sui due casi misurati); nessuna fase nascosta fuori dal timing, registrato per ogni richiesta nel campo `scarto_relativo_pct`. Sonda di carico: 21 campioni, GPU fino al 97% con SM a 1927 MHz e 61 °C, VRAM 11.130/12.288 MiB, RAM usata 90,98 GB con **4,91 GB liberi**, RSS del server 78,1 GB — il margine di RAM è il vincolo stretto di questa macchina e va guardato a ogni corsa.

Limiti: una sola corsa, un processo, quattro richieste — non è una baseline. I 25,02 t/s dell'insieme libero vengono da un solo caso e non vanno confrontati con i 25,08/27,26/29,6 storici, che avevano preset, contesti e MTP diversi. Gli ID token vengono dal `/tokenize` del binario in esame perché `llama-tokenize.exe` non è compilato in questo albero (`build\tools\tokenize` contiene solo file di CMake): dichiarato nel manifest delle fixture.

**Cinque difetti trovati dalla corsa di fumo, e corretti** (il vero prodotto della corsa: tutti e cinque avrebbero inquinato ogni misura futura):

1. **Il banco lasciava il server vivo.** In Windows PowerShell 5.1 lo stderr di un eseguibile nativo diventa un `ErrorRecord`: con `$ErrorActionPreference = "Stop"`, il solo fatto che `taskkill` stampi un avviso faceva abortire lo script alla chiusura, lasciando il processo in ascolto sulla 8100. Corretto (`Continue` dalla prima chiamata nativa in poi, stderr di `taskkill` deviato dentro `cmd`) e verificato sul server ancora vivo. Effetto collaterale misurato: `llama-server.exe` avviato senza finestra non reagisce alla richiesta di chiusura gentile, quindi si finisce sempre nella terminazione forzata; l'attesa gentile è stata accorciata a 20 s e il modo effettivo è registrato in `chiusura.json`. Non c'era stato da preservare: ogni blocco è un processo nuovo.
2. **512 token di budget non bastano al gruppo libero.** `L01@corto` ha consumato tutti e 512 i token dentro il ragionamento e ha prodotto zero testo finale. Il protocollo dice che un output troncato nel solo ragionamento non supera la qualità: con quel budget l'intero insieme libero sarebbe invalutabile. Budget alzati a 1024 in screening e 1536 in conferma per i liberi, 768 per la qualità strutturata e per i casi a contesto lungo — scostamento dalle 512/768 scritte nel protocollo, formalizzato come **D11**.
3. **La virgola decimale italiana veniva letta come separatore delle migliaia.** In `S01` il modello ha risposto `mib_per_esperto: 1888` e `mib_per_token_lordi: 90624` invece di 1,888 e 906,24: ragiona in inglese e legge `1,888` come milleottocentottantotto. Sarebbe stato rumore sistematico in ogni confronto di qualità, per un motivo che non c'entra nulla con l'ibrido. Ai sei casi con decimali è premessa un'avvertenza di notazione.
4. **Falso allarme nel controllo degli aghi.** Il controllo «l'atteso compare già nel materiale?» deduceva l'atteso con una regex e segnalava `'F'` (da «Ferruccio»). Ora l'atteso arriva dal catalogo dei casi.
5. **La guardia della porta avrebbe impedito il lato B di ogni coppia.** Contava qualunque riga di `netstat` sulla 8100, e dopo un blocco restano decine di socket in TIME_WAIT per qualche minuto: lanciare B subito dopo A sarebbe stato rifiutato con «porta occupata». Ora la guardia guarda solo LISTENING e conta i TIME_WAIT come informazione.

I punti 2 e 3 sono stati corretti prima di qualunque misura, quindi nessun dato è stato invalidato; le fixture sono state ricongelate con la seconda accensione di solo sigillo. Di conseguenza il `fixtures_manifest_sha256` registrato dalla corsa di fumo si riferisce alle fixture pre-correzione: è scritto nel suo `manifest.json` e la corsa resta ciò che dichiara di essere, una prova di funzionamento.

**Decisione.** Proseguire. Le consegne di P0 esistono e funzionano; snapshot, fixture e banco sono la base riproducibile richiesta. La fase si dichiara **COMPLETATA** in questo registro, baseline di variabilità inclusa: chiusa il 14/9 dopo due blocchi validi in applicazione di **D14**, vedi voce di avanzamento dedicata sotto.

**Regressioni aperte.** Nessuna introdotta. Due osservazioni invalidano documentazione esistente: (1) deriva rispetto all'HANDOFF del 13/9 §1.1 — l'handoff dice che fra `bin_prod` e `build\bin` differiscono solo `ggml-cuda.dll` e `llama.dll`; oggi differiscono quattro file: si sono aggiunte `ggml-base.dll` (`D3842EB1` contro `5F4BA614`) e `llama-common.dll` (`2253BD46` contro `13648095`), ricompilate il 13/9 alle 13:09-13:10 dal lavoro sulle prestazioni — conseguenza pratica: «promuovere la sparse FA copiando due DLL» non è più vero, e una copia di quattro DLL non sarebbe più una promozione isolata della sparse FA; (2) la `ggml-cuda.dll` in `build\bin` non è quella del contatore dei colpi di cache — l'handoff §4.A indica `321BA4AC`, su disco c'è `26BA28B4` (13/9 12:57), la build successiva; il manifest di pianificazione del 14/9 registrava già `26ba28b4...`, quindi non c'è deriva dal momento della pianificazione, ma chi cercasse `LLAMA_MOE_HIT_REPORT` «nella DLL della §4.A» starebbe guardando un binario diverso da quello descritto.

**Stato dei processi avviati.** Nessun `llama-server` attivo; nessun LISTENING sulla 8100 (restano solo socket in TIME_WAIT, che scadono da soli). Verificato con `tasklist` e `netstat` dopo ciascuna delle due accensioni. La prima chiusura ha richiesto un intervento manuale a causa del difetto n.1, ed è servita a validarne la correzione; la seconda si è chiusa da sola con lo script corretto (`modo_chiusura = stop_process_forzato`, come previsto per un processo senza finestra). Caricamenti del modello misurati: 201,5 s e 190,9 s.

**Prossima azione.** Nessuna ulteriore misura di baseline: D14 ferma le batterie di controllo lunghe senza un candidato pronto. Procedere a P2 (esecutore/lifetime) lavorando sul sorgente dello snapshot — P1 (contratto e simulatore della cache) è già stata aperta e completata, vedi voce successiva; il riferimento per P3/P4 è quello registrato nella voce di avanzamento seguente.

### Baseline di variabilità (P0, chiusa il 14/9)

**Data e decisione.** 14 settembre 2026. La misura di variabilità pianificata da **D12** (tre coppie A=A sul profilo `solo_libero` più un blocco `screening` completo) è stata **FERMATA dopo tre blocchi** (due completi + uno interrotto) per applicazione di **D14**, la decisione dell'utente del 14/9: «Prima il B, poi l'A solo se serve». Niente batterie di controllo lunghe senza un candidato pronto; il blocco di screening completo NON si esegue. Il riferimento per P3/P4 è la coppia A/B già raccolta.

**Blocchi validi.** `20260914_072049_P0_sper_ibrido_assente_r1` (A, replica 1) e `20260914_074035_P0_sper_ibrido_assente_lato_B_r1` (B, replica 1, preset identico ad A): insieme libero, 16 casi ciascuno, 15.687 token, 642,00 s (A) e 641,64 s (B). **24,4344 contro 24,4484 t/s**, rapporto B/A 1,0006 (aggregato somma/somma in `docs/porto/banco_p0/risultati/aggregato_baseline_libero_20260914.json`). Una sola coppia: l'intervallo bootstrap non è interpretabile secondo il protocollo (serve pluralità di coppie), ma con preset identici il rapporto misura comunque il rumore fra blocchi: **0,06%**.

Blocco `20260914_075924_P0_sper_ibrido_assente_lato_B_r2` **INVALIDO**: interrotto dall'orchestratore dopo 11 casi su 16 per applicare D14 (`failure.json` nella cartella del run: «Blocco interrotto dall'orchestratore (Fable) il 14/9 dopo 11 casi su 16: decisione utente di non proseguire con le corse di controllo A»). I singoli casi completati restano utilizzabili per il confronto per caso, non per l'aggregato.

**Impronte.** SHA256 del testo identiche caso per caso nei tre blocchi — zero differenze su 17 chiavi, riscaldamento incluso: il banco è deterministico e l'impronta è l'oracolo (vedi anche la voce d'indice del 13/9 sullo stesso principio).

**Contesto.** Casi corti fra 22,2 e 24,1 t/s del server, casi a 32k fra 25,4 e 26,5 (il 32k è più veloce del corto: da spiegare, non da correggere, in una fase successiva).

**Riferimento per P3/P4.** Sull'insieme libero, profilo `solo_libero`, budget 1024, **24,44 t/s** (aggregato somma/somma) è il riferimento da battere. I 25,08 t/s del 13/9 restano storici: preset e budget diversi, non sostituiscono questo riferimento (già scartata l'etichetta "baseline FreeToken" nella review del piano).

**Qualità dei liberi in screening — D15.** Con `--reasoning on` e budget 1024, **14 casi liberi su 16 terminano per lunghezza con testo finale VUOTO** (tutto il budget consumato nel ragionamento; solo `L04@corto` e `L04@ctx32k` arrivano a `stop`). La misura di velocità resta valida — i token di ragionamento sono generazione, come dice il protocollo — ma la rubrica di qualità sui liberi NON è applicabile in screening. Decisione: lo screening misura la velocità; la qualità dei liberi si valuta solo in conferma (P6) con budget 3072 o fino a `stop`, insieme ai casi strutturati S01-S10 e agli aghi che producono testo finale. Alternativa scartata per ora: spegnere il ragionamento, perché cambierebbe il carico rispetto all'uso reale; riesame se P6 mostra che 3072 non basta.

## P1 — Contratto e simulatore della cache CPU/GPU (14/9)

**Data e fase.** 14 settembre 2026. P1 del [piano CPU/GPU](PIANO_CPU_GPU_14_SETTEMBRE.md). Specifica: [P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md](P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md). Strumenti: `docs/porto/strumenti_p1_cache_cpu_gpu/`. Solo lavoro analitico su CPU: nessun server avviato, nessuna compilazione, nessun uso della GPU, nessuna modifica ai sorgenti del motore né agli alberi `qwen38_clean\source` e `Documents\Codex\2026-09-13`. Nessuna misura di velocità e nessun t/s è ricavabile da questo rapporto.

**Ipotesi.** La politica attuale può essere riscritta con l'ammissione differita esplicita e con la partizione dei miss in CPU/GPU prima dell'assegnazione degli slot, senza cambiare nulla quando `cpu_max = 0` e senza produrre residenti fantasma quando `cpu_max > 0`.

**ID della modifica/revisione.** Nessun sorgente del motore, nessun binario, nessun launcher toccato. Riferimento riusato: la classe `Cache` di `analyze_trace.py` (copia in `docs/porto/strumenti_qwen38_13settembre/`, SHA256 `6f756836bcf89ed4166a183ca8541631624293687800e9642b76ba47f6eeb165`, identica a quella dell'audit), che sulla stessa traccia riproduce senza differenze i miss misurati dalla GPU. Il riferimento applica l'ammissione subito; il simulatore nuovo la applica differita, come il kernel.

**File toccati.** `docs/porto/P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md`, `docs/porto/P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md`, `docs/porto/strumenti_p1_cache_cpu_gpu/` (`cache_cpu_gpu.py` SHA256 `83c7f864849195a6`, `replay_p1.py` SHA256 `94a6e8fcb234e44a`, `test_scenari_p1.py` SHA256 `d71d63fff7461d20`, sei JSON di risultato).

**Configurazioni confrontate.** Traccia `trace64.jsonl` (36.913 record storici, `C:\Users\imanu\Documents\Codex\2026-09-13\rip\work\freetoken_audit\replay_verify\`, SHA256 `690d7c26e248d05a83f244c477e5d55fe644b40d481c3c90ebb9f63ea9861212`, la stessa di `cache_policy_results.json` e dello ZIP di evidenza — non è stato necessario ripiegare su `routes.bin`), 64 slot, 512 esperti, `cpu_max` 0/1/2, ordini `route` e `freq`, strato 2 escluso dal ramo CPU. Struttura della traccia: `k = 10` in tutti i record, `rows = 1` in 36.819 record e `rows = 2` in 94 (tutti dentro i primi 64 passi), ID in `[0, 511]`, 95 incarnazioni su 48 strati fisici, `bytes_per_miss` 1.971.200 su 47 strati e 2.329.600 sullo strato 2 (coerente con D07).

Confronto per ogni piano: (1) contenuto del piano — numero di richieste uniche, numero e identità dei miss nell'ordine degli indici unici, slot assegnati nello stesso ordine, esperti sfrattati nello stesso ordine; (2) stato dopo il commit — mappatura `expert_for_slot`/`slot_for_expert`, frequenze, epoche e ordine totale di recenza degli slot; lo stato del simulatore al passo `t+1`, subito dopo la fase differita, è confrontato con lo stato del riferimento dopo il passo `t`. La recenza si confronta come ordine e non come valore: il dispositivo riserva `n_routes` tick per piano e ne consuma `n_unique`, il riferimento ne consuma `n_unique`, quindi i numeri assoluti divergono per costruzione mentre l'ordine totale — l'unica cosa che la scelta della vittima legge — coincide. Esclusi dal confronto di stato i 95 primi piani (nessuno stato precedente) e i 47 ultimi piani delle incarnazioni sostituite in corsa: 36.913 − 95 + 48 = 36.866. I 47 piani pendenti mai applicati sono la conseguenza dichiarata del commit differito, non una differenza.

**Link ai run validi e invalidi.** Un solo processo Python alla volta, nessun argomento con credenziali:

```
python replay_p1.py --trace $T --cpu-max 0 --out p1_replay_cpu0.json
python replay_p1.py --trace $T --cpu-max 0 --controllo-negativo --out p1_controllo_negativo.json
python replay_p1.py --trace $T --cpu-max 1 --strato-escluso 2 --out p1_replay_cpu1.json
python replay_p1.py --trace $T --cpu-max 2 --strato-escluso 2 --out p1_replay_cpu2.json
python replay_p1.py --trace $T --cpu-max 1 --cpu-order freq --strato-escluso 2 --out p1_replay_cpu1_freq.json
python replay_p1.py --trace $T --cpu-max 2 --cpu-order freq --strato-escluso 2 --out p1_replay_cpu2_freq.json
python test_scenari_p1.py
```

`replay_p1.py` esce con 1 se trova una differenza o un residente fantasma; `test_scenari_p1.py` esce con 1 se uno scenario fallisce. Tutte le corse sopra sono uscite con 0, tranne il controllo negativo che deve fallire e fallisce. Nessuna corsa invalida o interrotta; nessun server coinvolto.

**Risultato e limite.**

*Riproduzione della politica attuale:*

| Finestra | Piani | Richieste uniche | Colpi | Miss | Colpi % | Payload dei miss |
|---|---:|---:|---:|---:|---:|---:|
| Intera traccia | 36.913 | 369.831 | 275.564 | 94.267 | 74,51079% | 187.062.758.400 |
| Passi oltre 64 | 33.747 | 337.470 | 254.944 | 82.526 | 75,54568% | 163.807.436.800 |

Coincide cifra per cifra con `cache_policy_results.json` del 13 settembre e con il tasso diretto misurato dai contatori del dispositivo. Sfratti effettivi nella traccia intera: 89.789.

*Curve con `cpu_max` 1 e 2 — solo informative* (tratto caldo, passi oltre 64, strato 2 escluso, 337.470 richieste uniche in tutte le righe):

| `cpu_max` | Ordine | Colpi GPU | Miss GPU | Miss CPU | Job CPU | Byte caricati | Colpi GPU % | Byte rispetto a `cpu_max=0` |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | — | 254.944 | 82.526 | 0 | 0 | 163.807.436.800 | 75,55% | 1,000 |
| 1 | route | 246.729 | 62.300 | 28.441 | 28.441 | 123.937.945.600 | 73,11% | 0,757 |
| 2 | route | 238.192 | 45.185 | 54.093 | 54.093 | 90.200.857.600 | 70,58% | 0,551 |
| 1 | freq | 250.853 | 59.240 | 27.377 | 27.377 | 117.906.073.600 | 74,33% | 0,720 |
| 2 | freq | 245.593 | 41.160 | 50.717 | 50.717 | 82.266.777.600 | 72,77% | 0,502 |

Non sono t/s e non ne implicano nessuno; qui il tasso di colpi scende, perché i miss serviti dalla CPU non vengono ammessi e tornano miss al passo successivo. I byte non caricati non sono tempo risparmiato: il calcolo CPU ha un costo proprio non misurato qui, e la sovrapposizione con la GPU è la vera variabile. Il carico CPU non si può calcolare dalla traccia storica: sommando `min(cpu_max, miss)` sui miss storici si otterrebbero 26.737 job con `cpu_max=1` e 46.503 con `cpu_max=2`, mentre le corse reali ne producono 28.441 e 54.093 (+6,4% e +16,3%) — la partizione cambia la traiettoria della cache, i miss futuri non sono quelli della traccia. L'ordine `freq` domina l'ordine `route` su questa traccia in entrambe le colonne (più colpi, meno byte), ma è una sola traccia su un carico di circa 703 token, ed è un candidato per P4, non una decisione di P1. Contesto della traccia calda: 33.747 piani, di cui 7.010 senza alcun miss (20,8%) e 20.963 con uno-quattro miss (62,1%); l'82,9% dei piani ha al massimo quattro miss. Lo strato 2, escluso, mantiene con `cpu_max=2` i suoi 3.470 miss GPU e zero miss CPU: il fallback è neutro come richiesto.

*Scenari dedicati, 13 su 13 superati:* `cambio_di_vittima` (con un miss CPU cambiano sequenza delle vittime e residenti finali), `vittima_argmin_lfu` (argmin di frequenza efficace/ultimo uso/indice: LFU, non LRU), `saturazione` (cache piena, quattro miss nuovi: con `cpu_max=0` quattro sfratti, con `cpu_max=2` solo due e le due route CPU condividono un unico slot alias; `n_routes` oltre gli slot rifiutato), `riuso_ravvicinato` (un esperto CPU al passo `t` richiesto a `t+1` resta miss, non residente, frequenza logica comunque aggiornata), `invalidazione_incarnazioni` (nuova incarnazione parte vuota, ammissione pendente della vecchia persa), `id_ai_limiti` (0 e 511 accettati, `-1` e `512` rifiutati), `zero_uno_due_job_cpu` (`n_cpu = max(0, min(cpu_max, n_miss, n_unique - 1))` su nove combinazioni; con un solo unico non si usa la CPU per mancanza della route GPU reale per l'alias), `stesso_esperto_due_token` (due token sullo stesso esperto CPU generano due job: pesi deduplicati, calcolo no), `pesi_zero_e_non_uniformi` (peso GPU zero sulle route CPU, resto identico bit per bit, peso originale nel job, nessuna rinormalizzazione), `fallback_non_supportato` (strato non idoneo con `cpu_max=2`: firme identiche a `cpu_max=0`), `errore_job_cpu` (il piano fallito non resta pendente, non ammette nulla, invalida i residenti degli slot già sovrascritti dal gather e blocca ogni uso successivo finché non si esegue la pulizia esplicita), `alias_slot_protetto` (alias sullo slot di una route GPU reale del piano corrente, protetto, tre banche pronte prima del consumo), `frequenza_include_cpu` (12 aggiornamenti di frequenza contro 8 scritture di recenza su quattro piani da tre unici con `cpu_max=1`: la contabilità logica include le route CPU, la recenza no).

**Limiti e ambiguità del codice trovate, non risolte in P1:**

1. I pesi del router non sono nella traccia: il simulatore usa pesi sintetici deterministici con una route a peso zero per piano. Verificata la contabilità dell'invariante 5 (ogni coppia una volta sola, peso originale, nessuna rinormalizzazione), non un valore numerico del modello; la verifica numerica del contributo CPU contro il percorso interamente GPU appartiene a P3.
2. Invarianti 6 e 7 coperti solo in parte: il simulatore copre la macchina a stati dell'errore e il fallback deciso prima dell'invio; concorrenza, callback, mutex e durata dei buffer non sono simulabili in Python e restano a P2, con i controlli indicati nel contratto.
3. Una sola traccia, un solo carico: 36.913 piani da una sessione di 768 token generati con MTP spento e contesto effettivo di 867 token; non copre prefill, contesti lunghi, più turni né la speculazione. Le curve del punto precedente vanno rifatte su una traccia del banco congelato di P0 prima di sceglierne l'ordine.
4. Lo schema della traccia va esteso con un campo per i miss CPU prima di riusare `LLAMA_MOE_ROUTE_TRACE` con la CPU attiva, altrimenti un replay futuro confronterebbe grandezze diverse.
5. Servono tre contatori invece di due nel dispositivo, e due percentuali distinte in `report_hits`: con i miss CPU la formula attuale `1 - mancanti/richiesti` li conterebbe come colpi.
6. `rows > 1`: il contratto è scritto per coppie token/esperto e gli scenari coprono due token, ma la semantica completa della speculazione resta a P5.
7. Il costo delle righe GPU fittizie dell'alias non è misurabile qui: è una misura di P3/P4.

**Decisione.** Proseguire. Adottare per P3 l'ordine deterministico «primi miss in ordine di indice unico» (**D13**), già materializzato dal kernel e indipendente dallo stato della cache; tenere `freq` come prima alternativa da confrontare in P4. Portare nel kernel la separazione fra `n_misses` (miss GPU) e miss CPU, aggiornando insieme gather, commit differito, contatori e traccia. La fase si dichiara **COMPLETATA**: contratto, simulatore, controllo negativo e 13 scenari dedicati sono i criteri di uscita verificati per questa fase analitica.

**Regressioni aperte.** Nessuna introdotta; restano i rischi già registrati sul commit differito e sul costo delle righe GPU fittizie, più il caso del job CPU fallito dopo gather (vedi rischi in testa al registro).

**Stato dei processi avviati.** Nessuno; solo processi Python seriali su CPU, tutti conclusi.

**Prossima azione.** P0 congela le fixture e la baseline (COMPLETATA, riferimento 24,44 t/s sull'insieme libero); P2 sull'esecutore/lifetime è IN CORSO, in correzione dopo la review indipendente (B1/B2 bloccanti, E1/E2 meccanici), riusando gli assert degli invarianti 2, 4 e 5 come controlli di stato attorno all'interfaccia host.

**Rollback previsto:** opzione ibrida spenta e riavvio sul preset sperimentale di riferimento; se il percorso spento non è neutro, ritorno al binario/snapshot di P0. Non si sostituisce il launcher di uso quotidiano durante l'integrazione. Il rollback è un test da eseguire in P6, non ancora una prova superata.
