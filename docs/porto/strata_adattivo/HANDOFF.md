# HANDOFF — Strata Daily 0.1.38 SM75, QSA/exact-small, elastica/tail, KV262k

## 4 ottobre: sessione di quattro ore

Daily aggiornato con **exact-small, contratto prefisso PR652 e QSA a gruppi di
otto query**. Diagnostica HtoD/PLE inclusa ma spenta. KV int8 **262144**, residenti
**32768**, cache auto/elastica e checkpoint tail conservati; grid originale e
adattamento BF16 respinti restano esclusi. Il launcher operativo è aggiornato
nei commenti e conserva le stesse istruzioni di avvio.

- QSA, confronto fisso off/on/off: warm **+5,38% a 130380** e **+6,26% a 249322**;
  quattro righe complete di logits e 258 ID per braccio bitwise. Non è una nuova
  SOTA cold/decode. Gate teacher esteso: 1456/1536 righe, tutte le posizioni
  comuni bitwise; mancano 80 righe A2, quindi il gate esteso resta incompleto.
- Conversazione HTTP completa: **190 turni, 20k→250130**, prefill aggregato warm
  **286,5 t/s**, decode **38,0 t/s**. Curva per profondità pubblicata. Risposte
  complete ma alcuni contenuti ripetitivi/imprecisi: nessuna qualità generale attestata.
- Replay finale del Daily, thinking off/on, oltre 250k: cinque fatti e aritmetica
  corretti in entrambe le risposte. L'oracle automatico rifiuta soltanto il
  suffisso «modificata» nel nome GPU senza thinking; esito originale conservato.
- Anomalie cold mantenute: circa 19 contro 212 secondi, con forte attesa nel
  percorso PLE. La causa precisa è aperta. `--ple-sync-submit` non mostra un
  vantaggio dimostrato; nessuna modifica a clock o politica I/O.
- Daily exe `a17d0dd5…`, configurazione `f0237b6a…`, manifest storico conservato.
  Backup QSA/exact-small/diagnostica e overlay disponibili; 286 sorgenti/frontend
  confrontati con il fork. Nessun altro test GPU da avviare in questa finestra.

**Leggere prima di riprendere:**
[risultati, limiti, repository, prossima diagnosi e ripristino](SESSIONE_QUATTRO_ORE_4_OTTOBRE.md).
Prossimo passo: scomporre le attese PLE; runner HTTP da 130k a 134k con soli
contatori preparato ma non eseguito. PR693 per chunk lunghi da validare;
PR663 da rivalutare con la futura seconda 3060. Nessuna misura inventata per
le prove rinviate.

## Stato precedente

- **3ottobre, Daily e main aggiornati:** upstream99f3dbd/0.1.38, commit
  fc9a767b15c3. Grid originale rimossa; tail614abilitato,
  elastica e SM75conservati; top-k largo603validato/integrato, seriale.
  Numerica A/B/A: 2560 righe/braccio, bitwise, KL 0, top-1 100%; sei recall.
  Auto Daily131k/250k:1024token per profondità e6oracoli corretti.
  Prefill1027.01/833.50t/s; decode lungo36.913/39.065t/s, singoli campioni.
  Controllo603250k: 701.49/832.03/699.49t/s,
  +18.78% rispetto alla media A, spread0.29%; logits bitwise.
  Shipping/BAT/config/server coerenti; health e JSON su8100passano,
  48untracked preservati, rollback0136disponibile. Release038pubblicata,
  nessun workflow. Motori chiusi; test senza pressione artificiale.
  [Dati, provenienza, limiti e ripristino](ALLINEAMENTO_0138_GRID_RIMOSSA_3_OTTOBRE.md).

## Stato storico (le note Daily invariato sotto si riferiscono ai giri precedenti)


- **3 ottobre, controllo duplicati e PR614 aperta ready:**632fork elencati,
  630default esterni leggibili,1179branch pubblici e535commit distinti controllati.
  Nessun checkpoint tail equivalente emerso; PR614su upstream038,
  head8dad0ca, due file. Messaggio con @Niko1221 inviato sulla PR.
  Elastica sovrapposta a37/378/563 e piano manuale533: nessuna nuova PR
  della cache; proposta e dati segnalati al maintainer per un contributo mirato.
  Fork operativo main pulito e Daily invariato; nessun test GPU in questo giro.
  [PR, messaggio, audit e limiti](CONTROLLO_DUPLICATI_PR614_3_OTTOBRE.md).

- **3 ottobre, port upstream038 elastica + nuovo checkpoint tail validati:**
  contributi separati; elastica A/off/VMM/A e tail A/B/A con2560teacher rows
  (2557posizioni) per braccio, tutti bitwise/KL0. Elastica35test CUDA/CTest3/3,
  CLI42; ultima revisione64teacher+fresh/follow bitwise contro V1.
  Tail:3coppie33.8k, TTFT branch17.047→4.470s(−73.78%), fresh+0.93%;
  non nuovaSOTA e non fix della grid originale, che conservaFAIL.
  Autoelastica+tail:9recall corretti, grow/shrink/relayout8192 reali.
  Conversazione chiusa correttamente a131k/250k:1024token entrambe,
  6oracoli inclusi4marcatori distinti; tentativo precedente48token conservato.
  Daily invariato e motori chiusi. Stato pubblicazione aggiornato sopra:
  PR614 tail aperta; elastica da concordare per sovrapposizione upstream.
  [Misure, provenienza e limiti](PORT_ELASTICA_CHECKPOINT_TAIL_3_OTTOBRE.md).

- **3 ottobre, perimetro PR riconfermato dall'utente:** proporre il codice
  della cache elastica e dell'allineamento checkpoint usato nel Daily.
  L'ultimo A/B sullo stesso Daily confronta solo frequenza16384/8192,
  con elastica e checkpoint-grid presenti in entrambi: non è il gate delle PR
  né una bocciatura del Daily operativo. Nessuna nuova patch prodotta da quel test.
  Checkpoint-grid isolato su upstream038 ha ancora il FAIL già documentato;
  ripristino cold/cached bitwise nel caso provato non risolve il confronto A/B.
  Elastica: manca confronto isolato upstream/patch; non attribuire al suo codice
  il FAIL dell'esperimento di frequenza. Mantenere le impostazioni operative.
  Prossima validazione: stessa base upstream, contributi separati, geometria e
  residenza controllate per parità; poi comportamento operativo auto/elastico,
  senza carichi artificiali. Conservare attribuzione originale delle patch.
  Accesso completo ripristinato; blocchi index.lock delle note sotto sono storici.

- **3 ottobre, misure Daily elastico concluse:** stesso exe0136 c35505ca,
  auto/elastic/KV262144, confronto checkpoint16384/8192,3coppie a131072 e250000.
  **Gate breve FAIL, QA estesa A/B/A FAIL** (2557 posizioni/braccio).
  A 250k, corpus doc: PPL A/B 1.173/1.383, top1 A/B 88.56% contro A/A 96.68%;
  primo output fresh oltre il limite KL a entrambe le profondità.
  Oracoli 36/36 e 12/12, fixture ripetute; niente qualità generale/SOTA.
  A 131k branch TTFT mediano 20.695/10.770 s; a 250k nessun riuso aggiuntivo.
  Daily invariato per SHA, motori chiusi. Conservare la frequenza operativa 16384.
  Prossimo lavoro: isolare le differenze con cache automatica ed elastica,
  senza attribuire ora una causa non verificata. Tutti i fallimenti conservati.
  Blocco iniziale index.lock storico; evidenze nel commit di pubblicazione.
  [Dati e limiti](CHECKPOINT_DAILY_ELASTICO_3_OTTOBRE.md).

- **3 ottobre, diagnosi checkpoint conclusa:** A/B chunk1536 e6144, prompt33.8k
  letto da zero contro precedente riuso: logits bitwise in4/4 confronti,
  primo output+64posizioni/braccio. Differenza A/B già presente prima del riuso:
  percorso prefill modificato, singolo kernel/arrotondamenti non ancora isolati.
  Elastica disattivata,5357slot fissi. Configurazione alternativa senza tagli
  `--prefill6144 --prompt-cache-every6144`: upstream e patch bitwise tra loro
  e contro baseline6144 originale, fresh/follow+64posizioni,4risposte corrette;
  riuso30720 invece18432. Un campione temporale/braccio: niente SOTA o
  attestazione generale; ancora da provare131k/250k/elastica/Daily036.
  Gate patch originale16384 restaFAIL; Daily invariato, motori chiusi.
  [Dati e limiti](CHECKPOINT_DIAGNOSI_3_OTTOBRE.md).
  Il primo staging fu negato su `.git/index.lock`; accesso completo ora ripristinato.
  Evidenze complete salvate e verificate, identificate dal commit di pubblicazione.

- **3 ottobre: PR512 integrata upstream0.1.38; ripetizione isolata +7,46% prefill, spread riferimenti0,54%, parità16/16.** [Dati e limiti](PR512_RIPETIZIONE_3_OTTOBRE.md). Daily invariato.
- **3 ottobre, accesso completo ripristinato:** pubblicati i report spec4/spec5,
  quattro ore e ripetizione PR512 sul branch research autorizzato, con manifest
  verificati. I blocchi Git descritti nelle note precedenti sono storici.
  Checkpoint-grid su upstream0.1.38, tre soli file: misure e QA concluse.
  **Gate numerico FAIL: nessuna nuova PR di merge o promozione.**
  Follow-up33.8k TTFT37.284→3.510s (chunk1536) e17.047→3.517s (chunk6144),
  tre coppie/configurazione; costo sul fresco+2.35%/+6.33%.42 risposte corrette,
  384 righe teacher finite/top1 100%, riferimenti bitwise; KL p990.0321/0.0885
  oltre soglia. Con --prompt-cache0 logits bitwise. Non chiamare SOTA o qualità
  generale attestata.197 test server:190pass/7skip. GGML1376file identici al pin.
  I due tentativi QA con ABI Prefill incompatibile sono invalidi e restano solo
  locali; dopo il ripristino dei timestamp Ninja ricompila entrambe le unità.
  Daily/launcher invariati per SHA; motori propri chiusi, RAM67.9GiB/VRAM18409MiB
  libere. [Misure, limiti e fallimenti](CHECKPOINT_GRID_0138_3_OTTOBRE.md).

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
  Strata 44-45 t/s, daily llama ricompilato 12-16 t/s. Riferimento storico0.1.31 a 131k:
  **39,272 t/s decode,886,38 t/s prefill a131k** (2/10, cache auto/elastica);
  **39,218t/s decode e638,67t/s prefill a250k**, output lungo1024token.
  Non confondere profondita' e capienza KV. Il decode a250k e' un follow-up riusato.
- Lanciatore pronto per l'utente: `Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat`.
- Il daily di produzione (`D:\ds4_work\bin_elastico_m2`, solo sm_86) **non gira sulla 2080 Ti**; runtime sm_75 pronti
  in `D:\ds4_work\daily_sm75\runtime` (M2) e `runtime-m3` (M3). Il bat del daily non e' stato toccato.

## 2. Cosa usare oggi
- **2/3 ottobre, sessione quattro ore:** candidato037 preparato e test kernel dinamico228casi; controllo stesso processo a131k +1,148%, sotto soglia3%, nessuna nuova SOTA da questo kernel. Nuove PR546/547 esaminate; esiti finali e stato pubblicazione nel [report quattro ore](QUATTRO_ORE_2_OTTOBRE.md). Daily fisico036/auto/elastico/KV262144 conservato; fork e GitHub non aggiornati per blocco scrittura403/profilo. Questo aggiornamento HANDOFF è locale finché non risulta pushato.
- **2/10, confronto generale spec4/spec5/spec4 concluso:** ragionamento low
  attivo, sei controlli brevi, retrieval20k/131k e due decode1024 per profondità.
  Spec5:38,532t/s a20046 token e35,908t/s a131118; contro media spec4
  39,325 e36,430. Nessun guadagno nei campioni; testi identici12/12.
  Otto contenuti corretti/braccio, gate JSON6/8 per fence nei due retrieval.
  Cache laboratorio6167 slot fissa, KV262144, daily elastico invariato.
  Finestre effettive e formattazione JSON registrate separatamente dalla
  correttezza dei codici. Nessuna promozione automatica a SOTA o modifica daily.
  Dati e limiti: [SPEC45_GENERALE_2_OTTOBRE.md](SPEC45_GENERALE_2_OTTOBRE.md),
  `corse_2080ti/20261002_spec45_general/`. Motori della prova conclusi.
- **2/10, validazione qualità A/B/A conclusa:** metodo teacher-forced e
  oracoli versionati su main nel fork. A1/B/A2 hanno logits completi identici
  su 2.557 posizioni valutate: top-1 100%, KL 0, PPL identica. Stessi 6.167
  slot nel laboratorio, KV 262144/int8/resident 32768, chunk2048; il daily
  resta auto/elastico. Sei controlli su sette corretti in ogni braccio,
  incluso retrieval con tre codici a131072 token al10/50/90%, tutti stop.
  **Gate complessivo FAIL**: 3*17+2*23+8 riceve92 invece105 in tutti i bracci
  senza ragionamento. Anche zero bozze dà92; con ragionamento dà105. Non
  fatto sweep di tutti i limiti MTP. Non cancellare il fallimento originale.
  Cinque test CPU harness PASS. Tre avvii senza prompt conservati; corretto
  esplicitamente il gate di ammissione post-buffer prima di valutare token.
  Binario/lanciatore/config daily invariati; strumenti e risultati aggiunti
  su main senza nuova build. PR512 resta bozza: queste non sono prove della
  patch isolata. Nessun nuovo SOTA, nessun aumento bozze, motori conclusi.
  Dettagli [QUALITA_0136_2_OTTOBRE.md](QUALITA_0136_2_OTTOBRE.md), evidenze
  `corse_2080ti/20261002_quality_0136/`. Qualità generale/250k non certificata.
  Fork e checkout operativo ora `main/2c39467`, strumenti QA inclusi;
  48 file locali conservati e punto di recupero `20261002_202321_quality_tools`.
- **2/10, main e daily0.1.36 aggiornati e verificati.**
  PRupstream [#512](https://github.com/Niko1221/Strata/pull/512) aperta in bozza,
  branchremoto autorizzato `prefill-topk-active-bound`, commit42131caf; aggiornata
  senza riscrivere storia alla main0.1.36/36fa455; mergeable,4file soltanto.
  La PRisolata attende A/B/A modello sulla nuova base; i test del fork completo
  non sono attribuiti alla PR. Nessun commento/review al controllo2/10.
  Core del fork e daily validati al commit **729eb4a14c0a102cf7a57149e8e3fd93a9d18a5f**,
  tree completo upstream0.1.36 + sm75/elastica conservati,17file core di port.
  #315/commitasync mantenuti upstream; sola attesa pre-verifica #463 inclusa.
  #500 quantizzazione parallela inclusa **opt-in**, profilo daily seriale0:
  gain decode0,37% non causale, pool+plan11,631→12,136ms, nessun vantaggio CPU.
  Tre bracci2x1024 completati, prompt131248freddo/131239riusato, KV262144:
  **0.1.31:974,05prefill/41,255decode;0.1.36seriale:972,68/40,123;
  0.1.36parallela:970,60/40,272t/s**. Record osservato131k aggiornato a974,05;
  il precedente daily lo raggiunge anch'esso, nessuno speedup nuove patch dedotto.
  Cache/MTP/pressione reali variabili; nessun carico artificiale o altra chat.
  Build CMake completa sm75PASS,16parita'top-k,64pool realibitwise,HCzeroerrori,
  **100testserverPASS**,sourcecheck575file+manifeststoricoPASS. I nuovi fused
  prefill0.1.36 richiedono sm80+, decodecluster sm90+: indisponibili suTuring.
  LanciatoreDesktop/JSONcanonico ora **`build-0136-daily\strata.exe`** e
  **`build-0136-daily\source\serve\server.py`**; copie repo byte-identiche.
  Exe **c35505ca79b790bd37ed7073fcadd399dd30d1b88e85bb99a6eb24a52d945d0a**,cap262144/int8/resident32768,riserva1393,
  cacheauto/elastica,MTP,poolquant0. Smoke configurazione reale **40,72sPASS**.
  Backup **`D:\ds4_work\strata\ripristini\20261002_191326_0136_main_daily`**;48untrackedpreservati, vecchiof469/build0131
  disponibile, manifest0.1.31 conservato separatamente. Nessun workflow.
  Release [v0.1.36-sm75-20261002-r1](https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.36-sm75-20261002-r1) pubblicata,exe/PDB/manifest esatti;
  releaseprecedente conservata. Processi propri conclusi, nessuna prova futura
  pianificata. Retrieval250k0.1.36 e qualita'generale **non** validati; non
  riprendere automaticamente la vecchia conversazione interrotta per bloccoUI.
  Dettagli **`ALLINEAMENTO_0136_2_OTTOBRE.md`**,evidenze
  `corse_2080ti/20261002_port_0136/`; preparazione0.1.35 storica conservata.
- **Correttezza risposte e bozze, nota precedente alla nuova QA:** i6output del banco131k
  sono troncati a1024 durante il ragionamento, nessuna risposta finale valutata.
  I100testserver sono mock; parita'kernel non dimostra qualita'generale.
  Letti i2ragionamenti seriali, temi pertinenti ma esempiGiB/GB intermedi
  incoerenti: non segnare PASS del modello. Nessun'altra chat/reviewer coinvolto.
  `spec=6,mtp_max=4` runtime significa fino3bozzeMTP e5lookup, includendo il
  token corrente. Non fatto sweep MTP4/6/8 sulla0.1.36. Vecchio minp0,3:
  43,2contro45,1t/s. Prossime prove: risposte complete con oracoli, poi bozze;
  nessuna nuova corsa avviata. `corse_2080ti/20261002_port_0136/CORRETTEZZA_E_BOZZE.md`.
- **Metodo upstream, controllo 2/10:** kernel confrontati con riferimenti
  indipendenti e tolleranze specifiche; modello confrontato in teacher forcing
  su testi fissi tramite logits, KL e perplexity. Non trovato un unico harness
  pubblico obbligatorio. Il gate locale è ora completato come riportato sopra;
  resta il caso aritmetico negativo con ragionamento spento.
  Fonti e limiti: `corse_2080ti/20261002_port_0136/STANDARD_TEST_UPSTREAM.md`.
- **Prova conversazionale del 2/10 interrotta per blocco UI Windows.**
  Richiesta utente:20k iniziali, turni da1k fino250k. Raccolti **89turni**,
  **19999→131790token**, **22920token generati**, tutti89finish=stop,
  nessuna cronologia troncata, stesso daily f469/KV262144/elastica/MTP.
  Prefill freddo20k **913,95t/s**; incrementale1k circa335,72t/s a20k
  e272,19t/s a130k. Decode aggregato per finestre:38,37t/s a20k,
  39,20a50k,39,87a80k,43,46a100k,39,88a130k. Un singolo percorso con
  testi/MTP diversi: niente nuovo SOTA causale o sweep controllato.
  L'utente ha segnalato che **nessuna app/finestra Windows era cliccabile**.
  RAMlibera29,55GiB/95,89; CPU29,4%; VRAMusata21229MiB/libera1002MiB,
  GPU99%. DiscoC circa6MiB/s lettura,0,32scrittura; coda0, idleC96%/D98%.
  Strata RSS46,03GiB. Nessuna saturazione RAM/disco osservata; contesa
  GPU/desktop plausibile ma recupero UI da confermare con l'utente.
  **Fermati i soli processi della prova** al termine del turno corrente:
  RAMlibera76,56GiB, VRAMlibera18736MiB; nessun engine attivo.
  **Target250k NON raggiunto.** Non rilanciare automaticamente lo stesso
  profilo mentre Windows e' inutilizzabile. Configurazione daily invariata.
  Curva parziale, CSV, esempi, diagnostica e limiti:
  `corse_2080ti/20261002_conversazione_curva/README.md`.
  Raw transcript/server/native in `.codex_runs/20261002_conversazione_20k_250k`.
- **Pubblicazione e allineamento del 2/10, 09:59 Europe/Rome completati.**
  Fork pubblico: https://github.com/imanu86/Strata-2080Ti ; release esatta:
  https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.31-sm75-20261002-r1 .
  Il checkout operativo **`D:\ds4_work\strata\Strata` e' ora `main` del nostro
  fork**, commit `ad4700d61852af3481c8c36a98e5411a76e167cc`; preservati i 13
  commit locali con un merge il cui tree coincide con lo snapshot validato.
  `origin` punta a `imanu86/Strata-2080Ti`, `upstream` a `Niko1221/Strata`.
  **`build-0131-daily` e' aggiornato al binario f469**, server e sorgenti esatti
  del bundle top-k validato. JSON/BAT operativi e copie repository puntano ora
  al percorso canonico daily, e sono byte-identici. KV262144, resident32768,
  riserva1393MiB, cache auto/elastica e MTP preservati.
  Backup completo daily precedente, cronologia Git e JSON/BAT:
  `D:\ds4_work\strata\ripristini\20261002_095931_allinea_daily_sota`.
  **Workflow rimosso e GitHub Actions disabilitato** su richiesta dell'utente.
  Nessuna nuova build/prova GPU; processi motore spenti, macchina libera.
  Dettagli **`PUBBLICAZIONE_FORK_2_OTTOBRE.md`**. La precedente nota sul checkout
  operativo fermo a0.1.30 nei rapporti dell'1/10 e' storica, ora superata.
- **Lanciatore SOTA storico0.1.31** (ora superato dalla0.1.36 sopra; copia in `lanciatori/`): configurazione `D:\ds4_work\strata\Strata\strata-2080ti-sota.json` →
  **`build-0131-daily\strata.exe`**, 0.1.31 + nove patch locali + HC/GDN FP16 + dequant vettoriale + #315 + top-k attivo.
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
- **Stato corrente 2/10 07:20: top-k promosso sul daily e lanciatore Desktop.**
  Patch0025, API prefill col limite dei blocchi attivi: stride65538 del KV262k
  impediva il kernel a registri anche a131k. Originale API/decode preservati,
  fallback oltre33792blocchi (~135k). **16parita' bitwise superate**.
  A/B/A nello stesso exe capacity/active/capacity: prefill831,20/886,38/828,26,
  **+6,83%**, variazioneA/A0,35%; TTFT158,801→148,664s, −10,14s.
  Decode38,251/39,272/39,293: nessun guadagno decode attribuito alla patch.
  Jump CPU zero; cache auto/elastica e KV262144 sempre preservati.
  Retrieval10/50/90% **3/3FOUND**, poi **250022token reali**, ago alcentro trovato,
  prefill638,67t/s; follow-up250091/riusati250015, **1024output a39,218t/s**.
  Primi logits finiti, qualita' generale non misurata; A/A modello non bitwise.
  Exe **f469e096e868e4579daaec71ceef63693790e300e7a4cc5b49a8853d075a1d34**
  in `D:\ds4_work\strata\Strata\build-0131-topk-active`, copia esatta testata;
  JSON/BAT operativi e repository byte-identici. Avvio installato42,84s PASS.
  Backup `D:\ds4_work\strata\ripristini\20261002_071823_0131_topk_active`,
  daily precedente a74e conservato. **Tutti i processi lab chiusi**, nessun
  messaggio ad altre chat; non interagire con OCGC-IA/PROMO.
  **L'utente ha richiesto di concludere le prove per lasciare libera la macchina:**
  sessione conclusa, standby, nessun altro test avviato o programmato.
  Rapporto **`RISULTATI_TOPK_2_OTTOBRE.md`**, evidenze topk_active/model/quality.
  **CH16 trattenuta** (vantaggio modello non dimostrato); **BPW trattenuta**
  (16parita' score/indici superate, banco8192 non e' batch reale256, niente modello).
  Prossime piste: scorer BPW su batch256 + prova combinata, oppure #363 decode.
  Banda DRAM fisica non misurata: NCU ERR_NVGPUCTRPERM, niente modifica driver.
- **Stato storico 2/10 06:56: ripetizione senza Jump conclusa, CH16 non promossa.**
  JumpConnect CPU media zero. A/B/A CH32/16/32: prefill828,28/833,75/443,72;
  decode38,690/39,069/38,193. A2 rallentata per causa non isolata: non usarla
  per attribuire guadagni. CH16 solo+0,66% suA1, beneficio non dimostrato.
  Ulteriore riferimento **daily operativo esatto a74e**, alle06:38:
  **827,53t/s prefill,39,048t/s decode**, prompt131k/KV262144, elastica.
  Primi logits finiti/stessoargmax, ancheA/A non bitwise; qualita' generale non misurata.
  Evidenza `corse_2080ti/20261002_qsa_model_nojump/`.
  **Nuova candidata top-k attivo in prova**: stride65538 dal KV262k impediva
  il kernel a registri anche a131k. Nuova API solo prefill usa limite blocchi
  attivi <=33792, vecchia API/decode e fallback oltre135k preservati.
  16casi con stride reale/partial/tie/confine superati, indici identici;
  A/B/A modello131k in corso. Daily e lanciatori invariati fino a validazione.
- **Ripresa attiva del 2/10 dalle05:54, richiesta dall'utente: tutti i test necessari.**
  **Non interagire piu' con le chat OCGC-IA/PROMO** (istruzione esplicita utente).
  Candidata QSA CH16 integrata solo Turing/int8, overrideCH32, altriKV/GPU preservati:
  `.codex_runs/strata_qsa_ch16_20261002`, SHA437edc05de9c.
  Banco FP64 ampliato8192 query:4PASS; A/B/A kernel128/2048/8192:12PASS,
  FP16 output identico. Int8 chunk8192 **88,49/66,44/87,72ms (−24,59%)**.
  NCU isolato: **ERR_NVGPUCTRPERM**, nessuna misura banda DRAM; driver intatto.
  Prima A/B/A modello06:00 **esclusa**: JumpConnect attivo e carico variabile,
  A2 interrotta su richiesta utente alle06:12. Ripetere l'intera serie dopo chiusura
  JumpConnect; ripetizione ora conclusa come sopra, nessuna promozione CH16.
  Patch0023 e strumenti `compila_qsa_ch16.py` / `prova_qsa_ab.py`.
- **Ultima finestra 2/10 05:24–05:50: QSA CH16 promettente, non promossa.**
  Daily operativo a74e, KV262144/elastica preservati. Profiling Nsight Systems
  parziale + timer interni: timeout 480 s, nessun benchmark modello completo.
  Kernel attivo Turing QSA v1 int8: 37904 B shared/blocco, limite un blocco/SM.
  Nsight Compute fermo sul warmup 61 token, interrotto: **banda DRAM non misurata**.
  Prototipo CH16 corretto (tile score da 8 celle; carveout int8): 27536 B shared,
  quattro controlli FP64/CH32 superati, **21,904 → 16,142 ms (−26,30%)** nel
  banco int8 ctx131072/2048 query. FP16 peggiora: non estendere CH16 a quel KV.
  Nessuna prova CH16 sul modello, nessun nuovo t/s operativo, nessuna promozione.
  **Prossimo step: integrare CH16 solo Turing/int8, A/B/A reale daily a131k,
  poi retrieval250k/logits e promozione se valida.** #363 decode resta alternativa.
  Rapporto `RISULTATI_QSA_KERNEL_2_OTTOBRE.md`, patch0022, strumento `prova_qsa_ch16.py`,
  evidenza `corse_2080ti/20261002_qsa_kernel/`. Niente carico artificiale.
  Processi propri chiusi, **VIA OCGC-IA/PROMO alle05:50**; niente altre corse programmate.
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
  Priorita' a quella tappa: #363 decode. Successiva finestra QSA descritta sopra.
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

## 12. Ripresa 3/10: profilo 0.1.38 e accounting prefill

Misurato il profilo ai contesti 131k e 250k, senza carico artificiale. QSA selection è il maggiore costo a 250k (33,5%, circa 124 s); gate/up GEMM è il successivo (12,7%). Incremental tokenization non è la priorità per aumentare i t/s del prompt in questa traccia. Report e limiti: `corse_2080ti/20261003_profilo_tempi/RISULTATI_PROFILO_E_PR547.md`.

La correzione di memoria di [PR #547](https://github.com/Niko1221/Strata/pull/547) è stata portata sul fork `main`, compilata SM75, verificata e installata nel Daily 0.1.38 con backup. Migliora l'accounting e recupera circa 0,31 GiB di riserva al chunk 8192, ma A/B/A non mostra un guadagno di velocità sopra la variabilità: non aggiornare la SOTA. L'utente ha poi autorizzato una prova di conversazione reale con OktoCGControl aperto; risultati e limiti sono nella sezione 13. La curva warm non è confrontabile con i prefill freddi e non aggiorna la SOTA. Prossimo lavoro consigliato: isolare il costo QSA e valutare un'ottimizzazione con parità numerica; mantenere FP16 e tokenizzazione incrementale come ipotesi separate.

## 13. Conversazione reale 20k → 250k sulla Daily 0.1.38

Completata il 3/10 con OktoCGControl aperto e senza carico artificiale: una conversazione continua, dossier iniziale 20.001 token, poi 186 turni utente da circa 1k, cronologia completa fino a 250.012 token. Daily SHA-256 `13ee1a89be497ad83c67f62553b1133fec2a8d9309230d43a9dae639d89008a5`; Strata 0.1.38, KV int8 262.144, residenti 32.768, cache elastica, MTP. Durata 30,5 min inclusi startup; 187 turni, nessun errore/OOM, temperatura massima 62 °C.

Il primo tentativo è stato fermato su richiesta a 40.110 token dopo 17 turni: il primo prefill (95 t/s) era anomalo. La prova valida è ripartita da zero in una nuova cartella; primo prefill freddo 913,8 t/s, poi media warm aggregata 291,4 t/s prefill e 42,9 t/s decode, TTFT medio 4,08 s. Nella curva dei turni utente completi da circa 1k il prefill incrementale è circa 362 t/s a 20k, 306 a 100k, 288 a 130k, 268 a 200k, 269 a 230k e 252 a 250k; TTFT medio cresce da 3,1 a 5,1 s. La risposta finale ha usato solo 451 nuovi token utente ed è esclusa da curva/tabella, ma resta in CSV e trascrizione.

Questi valori descrivono il riuso cache in una singola conversazione e non sono confrontabili con un prompt freddo unico né con la SOTA prefill; non cambiano launcher, kernel o Daily. Dettagli, curve SVG/CSV, summary e campioni: `corse_2080ti/20261003_conversazione_daily0138/README.md`. La trascrizione completa resta nei dati locali `.codex_runs`; il primo tentativo interrotto è conservato separatamente.


## 14. Prefill incrementale e tokenizzazione, sera del 3/10

Ripresa dopo il via dell'utente, con OktoCGControl aperto (processo osservato) e senza carichi artificiali. Due corse sequenziali sul Daily nativo invariato: base e `STRATA_PREFILL_STREAM_MIN=1000`, entrambe con eventi `STRATA_PREFILL_TIMING` e `STRATA_SPLIT_TIMING`. Ricostruiti gli input reali dei turni 90 e 186 della curva: **130.380 e 249.322 token**, ciascuno con **1.014 nuovi token**, di cui 1.007 nel batch GPU. Il limite KV resta 262.144, KV int8 e 32.768 residenti. La cronologia viene preparata prima di ciascuna continuazione; non e' una ripetizione dell'intera curva.

| Fase GPU del batch da 1.007 | 130k base | 130k streaming 1000 | 249k base | 249k streaming 1000 |
|---|---:|---:|---:|---:|
| Totale | 3.685 ms | 3.526 ms | 4.055 ms | 3.999 ms |
| Attesa copie esperti | 1.001 ms | 398 ms | 925 ms | 417 ms |
| Preparazione pesi (`dequant`, include gather MMQ) | 656 ms | 486 ms | 656 ms | 442 ms |
| QSA selection | 528 ms | 529 ms | 883 ms | 929 ms |
| Staging KV | 125 ms | 640 ms | 240 ms | 765 ms |

Lo streaming anticipato riduce la fase di attesa esperti ma aumenta quella KV. La contesa delle copie RAM->GPU e' una spiegazione da verificare, non una misura diretta di utilizzo della banda. Il probe di avvio della base misura **13,2 GB/s PCIe**, distinto dalla banda interna VRAM. Il codice del prestito dimensiona gia' i buffer sulla richiesta reale arrotondata: non presta sempre un chunk da 8k a un turno da 1k.

Il prefill completo della continuazione misura 251,1 -> 264,4 t/s a 130k e 231,3 -> 237,0 t/s a 249k. **Non sono una nuova SOTA ne' un confronto causale controllato**: profilatore attivo, due sole continuazioni, cache elastica iniziale 6.042 vs 6.361 esperti (6.657 vs 6.832 prima del secondo warm), e solo otto token greedy verificati per punto. Gli otto token coincidono in entrambi i punti, ma non costituiscono un gate numerico. **Soglia 1000 non promossa; Daily resta a 1024.** Non confondere questi campioni profilati con i t/s della curva completa o del prefill freddo.

**Miglioramento validato e installato: tokenizzazione incrementale della PR567 di Guillaume PUTIER/gputier**, commit upstream `f29e527856b85e37bda90626ccc28e002b4989dd`. Non e' un algoritmo nuovo nostro. Sul tokenizer, template e trascrizione reali, tutti i **187 prompt / 25.306.163 token di input** coincidono esattamente con la codifica completa pre-patch. Una ripetizione cronologica CPU, base poi candidata su ogni prompt, Okto aperto, motore GPU spento. Mediane: a 125-135k (8 turni) **434,1 -> 7,77 ms**; a 240-250k (9 turni) **931,9 -> 10,57 ms**. Sono tempi della componente di tokenizzazione; non misurano TTFT HTTP completo e non cambiano il prefill/decode GPU.

Suite upstream tokenizer + server col vocabolario reale: 132 test eseguiti, 131 passati, uno saltato per fixture llama.cpp mancante. Fork e clone operativo `main` aggiornati al commit **1838b00d95f167b6ee16cf1da145b4b748124689**, pubblicato. Aggiornata anche la sorgente realmente caricata dal lanciatore, `D:\ds4_work\strata\Strata\build-0138-daily\source`; verifica finale `Service.prepare` su due turni con vocabolario reale e MockEngine: token uguali e prefisso riusato. Binario nativo, configurazione e manifest storico invariati.

Ripristino: `D:\ds4_work\strata\Strata\build-0138-daily\backup-frontend-567-20261003\recovery.json` elenca copie precedenti e hash; overlay corrente in `frontend-567-validation.json`. Ripristinare i file runtime elencati usando le copie sotto `backup-frontend-567-20261003/runtime`; il nuovo `tools/test_strata_tokenizer.py` non esisteva prima ed e' solo un test. Nessun server e' stato lasciato acceso.

Evidenze compatte: `corse_2080ti/20261003_chat_bottleneck/profile-summary.json`, `tokenizer567.json` e le due tracce di fase `.txt`. Script, input e log completi sono in `.codex_runs/20261003_chat_bottleneck`, con hash negli artefatti. La prima corsa `baseline_profile` era stata interrotta prima di completare una misura quando l'utente aveva chiesto di riaprire Okto: esclusa.

Prossimo lavoro GPU: misurare una coda di copie/ring adatta alle continuazioni da circa 1k e il gather MMQ dei piccoli batch; verificare il caso ring dimensionato sul T arrotondato. Evitare di anticipare piu' pesi se cio' fa attendere lo staging KV. La ricognizione ha trovato anche **PR655** (BF16->FP16 tensor core su SM75, head `671a387d3695d922db1399677608eb1aa6f5caf9`) e **PR583** (budget ring/chunk, head `817aa9c7a0f0538e3b514e787d5680fc02c865ca`): candidati da validare localmente, non integrati e nessun loro guadagno rivendicato. PR583 si sovrappone in parte all'accounting #547 gia' presente. Il main upstream letto durante la sessione e' ancora `99f3dbd0`.


### Decisione utente: riprovare con la RTX 3060 aggiunta

Conservare l'esperimento di streaming anticipato (`STRATA_PREFILL_STREAM_MIN=1000`) tra le prove da ripetere quando sara' installata la vecchia RTX 3060 accanto alla 2080 Ti. L'esito modesto attuale vale per la singola scheda: con piu' esperti residenti in VRAM cambiano volume e distribuzione delle copie, quindi non scartare definitivamente l'idea. L'utente deve ancora scegliere tra lo slot PCI Express e un collegamento OCuLink tramite M.2; generazione, numero di linee, condivisioni e banda effettiva sono da verificare sulla configurazione montata, senza presumere equivalenza. Ripetere base/candidata a pari testi, contesto, residenza esperti e topologia, registrando separatamente copie RAM->GPU, trasferimenti tra schede, staging KV, prefill warm/freddo e correttezza. Il collegamento non e' ancora deciso. Questa e' una voce del piano, non una promozione nel Daily o un test gia' svolto su due GPU.


Ricognizione successiva: [PR663](https://github.com/Niko1221/Strata/pull/663), head `46c4715f4d8701eae321c7752d23c27101fed528`, usa la scheda inattiva di un layer split per eseguire parte degli esperti dei prompt che stanno in un chunk, anche senza P2P attraverso memoria host mappata. E' una pista per 2080 Ti + 3060: aperta, non integrata e non testata qui. Le misure dell'autore sono su due 3090 con due collegamenti PCIe 4.0 x16; non trasferirne i guadagni alla nostra futura topologia. L'autore dichiara output ripetibile ma non bit-identico alla base per il diverso raggruppamento MMQ: prima di promuoverla servono parita'/qualita' e misure locali.

Per PR655, la lettura del sorgente conferma una sovrapposizione parziale con i percorsi FP16 SM75 gia' nel fork. Il rimpiazzo generale di `Gemm::bf16` raggiunge anche il popolamento KV delle bozze, che il codice attuale mantiene deliberatamente BF16. Non applicarla alla cieca: separare i prodotti ancora BF16 del target dal drafter, verificare numerica e accettazione MTP, e misurare solo il beneficio residuo sulla nostra base. Nessun port o test PR655 eseguito in questa sessione.


## 15. Buffer dei turni brevi: parita' passata, promozione sospesa

Patch pubblicata su fork `main`: `15fd2eacd46c0057a91e876dca0a3e99990907ca`
(documentazione corretta nel successivo `ef2a99b`).
Nuova opzione **disattivata per default** `STRATA_PREFILL_EXACT_SMALL=1`:
layout1007 anziche'1024 per il batch routed da1007, prestito517 anziche'1033 slot.
Compilazione SM75 e519268 controlli C++ passati. A/B/A breve completo: a1007
2336,1/2196,2/2324,9ms, +6,12% t/s sul campione breve. Non trasferire il dato alla
chat profonda. Dodici casi completati (8 brevi +4 richieste lunghe) con tutti i
248320 logits della prima riga target bit-identici e130 token greedy uguali.
Il gather raggruppato esplorativo non mostra vantaggi e non e' nella patch finale.

A130380 token, coppia A1/E:3873,1/3713,9ms per1014 nuovi; a249322:4357,9/4363,1ms.
**Confronto prestazionale lungo inconclusivo:** entrambi i tentativi del controllo
A2 sono diventati molto lenti nel prefill freddo e sono stati fermati, senza
richieste completate. Anche lo smoke con la configurazione elastica del Daily
(6426 slot,1001MiB liberi) e' stato fermato nel primo chunk lento. Causa ignota;
non attribuirla a Okto o alla patch. Candidata non promossa, nessuna nuova SOTA.
Daily nativo e configurazione verificati invariati, PR567 del frontend resta
attiva. Tutti i nostri processi del motore chiusi. Nessun test programmato.

Prossimo passo: diagnosi circoscritta del primo chunk8192, vecchio Daily vs
candidata con flag spento, profilo di fase e memoria/I/O; poi controllo lungo
ripetibile e smoke elastico prima di abilitare l'opzione. Report, hash, limiti,
prove escluse e percorsi in `corse_2080ti/20261003_request_chunk/README.md`.
La decisione RTX3060 e le piste PR663/PR655 restano nella sezione14.


### Ripetizione B dopo le anomalie: riuscita

L'utente ha richiesto di rifare solo B: una sola corsa con cache auto/elastica,
stessi input/argomenti/binario/profilo del tentativo candidato interrotto.
Completata in372,2s: cold129366 a937,1t/s; warm130380 a279,6t/s e249322 a248,5t/s,
1014 token nuovi per entrambe le continuazioni.32 output ciascuna, logits finiti.
Cache iniziale6342 esperti; nessun compilatore in64 campioni, CPU mediana22%.
Il rallentamento non si e' ripresentato; causa precedente non identificata.
Niente altri test, motore chiuso. Non e' un nuovo A/B/A o una nuova SOTA.
Il banco usa anche IQ_MT_MIN=1 (default motore2), gia' nel tentativo precedente:
non descrivere il decode misurato come profilo Daily senza override.
Daily invariato in questa richiesta di sola ripetizione. Evidenze aggiunte a
`corse_2080ti/20261003_request_chunk/README.md` e `single-B-repeat.json`;
nota pubblicata anche sul fork in158f208. Conservare le prove interrotte.


## 16. Sessione di quattro ore: controlli iniziali del 3 ottobre sera

Finestra autorizzata 19:59–23:59UTC, agenti economici OpenAI, un solo carico GPU e nessuna build durante le misure. Check repo/fork ogni ora; disattivare il heartbeat `strata-controlli-nella-sessione-di-quattro-ore` al termine.

Completata A elastica e A2 fissa ritardata; Daily aggiornato a exact-small (engine default off), SHA `d46a0752fd7b92726b34dd0332bf772cba22bba589aa22aed6e730becfb4b8fa`. KV 262144/int8/resident 32768 e cache elastica invariati. Backup `build-0138-daily/backup-request-chunk-4h-20261003`; manifest storico invariato. Le verifiche numeriche fisse passano, ma i controlli HTTP hanno limiti importanti: cap 128 genera risposte tronche anche con patch off; cap 512 produce 9 risposte complete, poi il runner fallisce sul sizing finale. Prefill lento in due avvii, anche off, causa irrisolta. Vedere `corse_2080ti/20261003_request_chunk/final-validation.json`; nessuna nuova SOTA.

Ricognizione iniziale: upstream 99f3dbd0 già incluso. PR652 (anon761) e variante main-only di PR655 (rafatxf) preparate localmente, non ancora compilate o validate in questo checkpoint. La variante 655 riusa scratch esistente, preserva BF16X2 e draft MTP, default off. PR663 resta per la futura 3060. Piano/script in `.codex_runs/20261003_four_hours`.
