# Strata: repo, fork, PR e commit — 2 ottobre 2026

Ricognizione richiesta dall'utente con macchina libera. Solo letture API/Git e
analisi dei sorgenti; nessuna compilazione, prova GPU o modifica al daily.
Branch di documentazione autorizzato `research/ds4-iq1-subbit-tier-planner`.

## Stato verificato

- Snapshot principale **04:16 Europe/Rome**, 02:16 UTC: upstream
  `1678de333d0e0711bc414ad992b640e1a37dd814`, release **0.1.34**.
  **39 commit** dopo lo snapshot serale 0.1.32 `c499bd102e`.
- **426 fork** nel contatore, **422 elencati** dalle pagine accessibili;
  **420 confronti riusciti**, **41 fork con commit propri**, **2 eccezioni**.
  `Asahi-Prv/Strata`: nessun antenato comune; `ConsultantTrail/Strata`: HTTP 404,
  confermato anche leggendo il repository. Non considerarli uguali a upstream.
- PR aperte: **57 all'inizio, 59 alla lettura finale**, con #442/#443 aggiunte
  durante la ricognizione. Nessuna sezione GitHub Discussions attiva; letti anche
  issue recenti, commenti tecnici e dati dei benchmark.
- Confrontati tutti i rami predefiniti dei fork accessibili; approfonditi i rami
  delle PR selezionate. Non e' un censimento di ogni branch di ogni fork.
- Fork sm75 **jklnvlink/Strata-2080ti invariato**, SHA `235350960d85`, 15 commit
  propri. Le ottimizzazioni HC/GDN FP16 e vector gia' installate restano quelle.
- Daily effettivo ancora `build-0131-daily`, hash
  `a74e4dadcd4fbb9e71b5cb0ae66922453c6a44a2704db25ddfb5e81601c5f766`;
  clone su D: `main` +13, sorgenti operativi nel bundle. Nessun Strata/llama-server
  attivo alla lettura. RTX 2080 Ti: 5761 MiB usati, 16470 MiB liberi, utilizzo 34%:
  macchina disponibile per l'utente, ma carichi desktop GPU presenti.

Snapshot sintetici pubblicati in `ricognizioni/20261002/`; risposte complete e
diff locali in `.codex_runs/strata_ricognizione_20261002/approfondimenti/`.
[Release upstream](https://github.com/Niko1221/Strata/releases/tag/v0.1.34).

## Cosa vale la pena provare sulla nostra scheda

| Priorita' | Proposta | Evidenza dell'autore | Applicabilita' e controllo necessario |
|---|---|---|---|
| 1, prefill | [#439 gather batch](https://github.com/Niko1221/Strata/pull/439), `2a3a99b2d49e` | +3,6% a 8k, +4,3% a 30k, IQ3_XXS/Windows/PCIe 3.0, RTX 5070 Ti; piccoli prompt invariati | stesso pack e tipo di piattaforma, copia byte per byte, test incluso; portare alla nostra 0.1.31 e misurare su sm75 |
| 2, decode | [#363 grouped lean](https://github.com/Niko1221/Strata/pull/363), `ae958ae96899` | chiamata PCIe -0,47 ms per finestra; circa +1% in richieste deterministiche su 4080 SUPER/IQ3_S | nessun requisito sm80; fusione SwiGLU/q8_1 e griglia PCIe ridotta. Parita' IQ3_XXS + costo per riga; guadagno totale puo' essere assorbito dalla CPU |
| 3, robustezza | [#385 stager DMA](https://github.com/Niko1221/Strata/pull/385), `c55854cf3f23` | possibile riuso del buffer pinned prima della fine del DMA, nessuna corruzione osservata; velocita' invariata | pertinente quando blob non pinned; controllo con gather e ring. Fix di correttezza, non promessa di t/s |
| 4, latenza | [#374 PLE](https://github.com/Niko1221/Strata/pull/374), `89e2994dc588` | lettura prima chunk sovrapposta a layer 0, inflight 64→256; -2,9% a 32k sull'SSD dell'autore | verificare sul nostro SSD e a chunk 8192; beneficio soprattutto sulla prima chunk, non proporzionale a 250k |

**Prima scelta: #439**, perche' misura lo stesso IQ3_XXS su Windows/PCIe 3.0,
contiene un test delle copie e uno switch A/B nello stesso eseguibile
(`STRATA_PREFILL_GATHER_ONE=1` ripristina il comportamento precedente).
La patch modifica `moe_mmq.hpp`, `moe_mmq.cu`, `prefill.cpp` e CMake/test. Non richiede
cp.async, a differenza di altre proposte recenti. Il beneficio su 2080 Ti non e' misurato.

La [#372](https://github.com/Niko1221/Strata/pull/372), `b28f806dfff3`, resta una
**alternativa allo stesso gather**, non una patch da sommare alla #439 o al gather
del fork 2080 Ti `496a4f3a195b`. Ora ha ulteriori riscontri: 4080 SUPER +3,8–4,3%
su 32/64k, AMD +3,8–4% su prompt lunghi, controllo logits dell'autore su 0.1.32.
Le proposte sovrappongono gli stessi file e la gestione degli eventi/ring:
sceglierne una, controllare le copie e provare il modello prima di promuovere.
I valori pubblicati -9/-10,5% nel tempo del prefill non sono una previsione locale.

## Altre patch sm75 nel fork gia' noto

Non sono nuove dall'ultima visita, ma **non sono ancora nel nostro daily**:

- `95afc8d39aef`: QSA indexer con piu' blocchi per warp. L'autore dichiara QSA
 70 → 45 ms/chunk e prefill 1477 → 1492 a 4k, 2110 → 2141 a 28k, stesso calcolo per score.
  **Incoerenza da risolvere prima del porting:** titolo/messaggio dicono 8 blocchi,
  commenti 4, codice del commit e della testa attuale **`SCORE_BPW=16`**. Non usare
  il solo titolo come specifica. Serve parita' score/id e microbenchmark sm75.
- `498482910045`: prompt attention con buffer singolo e pipeline nei registri;
  `80fae03ee1c7` aggiunge il relativo banco e indica letture KV ripetute come limite.
  Da provare separatamente, specialmente a contesto lungo.
- `caf592c5daf5`: `moe_combine` con float4, aritmetica per elemento conservata:
  candidata piccola dopo i gather, con controllo output.
- `ad75581084d3`: batch prefill della bozza nel layer split: la seconda GPU e'
  fuori perimetro, quindi non e' la priorita' della macchina attuale.
- `c8fd794e6bbd`: MMVQ multicolonna **non piu' rapida su sm75**, strada negativa
  gia' documentata nel fork; non promuoverla come nuovo guadagno.

[Fork e commit](https://github.com/jklnvlink/Strata-2080ti/commits/main).

## Novita' che non danno il guadagno pubblicizzato sulla 2080 Ti

- [#413 GDN key-head](https://github.com/Niko1221/Strata/pull/413), `8badd174ab84`:
  ricorrenza 1,3–1,4x sui kernel, circa +2% prefill totale sui modelli dell'autore.
  Il codice richiede **compute capability >= 8.0** e condizioni di occupancy/SM:
  la nostra **7.5 mantiene la vecchia ricorrenza**. Solo la rimozione di uno store
  FP32 nella normalizzazione si applica anche qui; non attribuirle il guadagno
  della nuova ricorrenza. Il banco dell'autore blocca SM con un kernel sintetico:
  non eseguirlo indiscriminatamente, dato il vincolo utente contro carichi artificiali.
- [#443 GR max4/MMVQ warp1](https://github.com/Niko1221/Strata/pull/443),
  `5c1a003e6344`: sperimentali separati e spenti per default. GR max4 +2% circa
  su Blackwell ma 3070 -0,03% nel singolo confronto; MMVQ warp1 cambia associazione
  floating-point e token, misurata su 5500 XT. Non c'e' prova 2080 Ti e il GR va
  riconciliato con la nostra #315. Priorita' inferiore a #363.
- [#441 non-MTP serving](https://github.com/Niko1221/Strata/pull/441): abilita
  richieste senza bozza e migliora il tempo totale in una prova su RX5500XT;
  decode piu' lento in quel caso. MTP resta piu' rapido nelle risposte lunghe RTX
  misurate. Utile per casi brevi/diagnostica, non spegnere la bozza nel daily ora.
- [#407 adaptive tuned](https://github.com/Niko1221/Strata/pull/407): meno miss/CPU
  su UD-Q4_K_XL, tempo per finestra entro il rumore, nessun guadagno su IQ2_XS nei
  casi misurati. La nostra IQ3_XXS resta da provare. L'autore ha anche usato carico
  CPU artificiale: non replicarlo.
- #378 KV-grow resta incompatibile direttamente con il nostro `--kv-resident 32768`.
  AMD/HIP, Volta e nuovi installer non accelerano questa RTX 2080 Ti per se'.

## Fix upstream utili e metodo di misura

La 0.1.34 non e' un aggiornamento generale di velocita' sm75: gran parte dei 39
commit e' installer/documentazione/AMD. Due punti incidono comunque sul lavoro:

1. [Commit 11ad074262a8](https://github.com/Niko1221/Strata/commit/11ad074262a8):
   server che rileva la disconnessione del client durante richiesta streamed o
   non-streamed, con test mock; chiude #430/#431. Porting server CPU/test prima
   della prova reale su prompt lungo: il nostro server 0.1.31 non contiene il watcher.
2. [Issue 410](https://github.com/Niko1221/Strata/issues/410) e
   [commit 382d68e47fd8](https://github.com/Niko1221/Strata/commit/382d68e47fd8):
   ripetizioni greedy identiche richiedono, nella misura upstream,
   `STRATA_IQ_MT_MIN=1 --prompt-cache 0 --adapt-swaps 0 --pcie-frac 0`.
   La quota PCIe conta oltre alla cache prompt e ai ribilanciamenti. Profilo solo
   numerico, **non sostituire quello operativo**: azzerare PCIe puo' rallentare
   decode. Poi misurare performance con elastica/PCIe normali e accettazione MTP.

[Issue 375](https://github.com/Niko1221/Strata/issues/375): vecchia #186 opt-in
`STRATA_GR_V3=1` non coerente sullo split Turing; upstream la disattiva su quel
caso (`0bea89206cc8`). **Il nostro daily usa la #315, senza quel vecchio selettore**,
con `STRATA_HC_V2` e controllo bitwise automatico gia' passato: non confondere
il nome v3 del nuovo kernel con la vecchia opzione e non annullare la #315 per errore.

Fork con aggiornamenti propri dalla precedente scansione: CC-David, christ-pher,
DmitriyW9, he-be, jmnargi/V100, RandoTeam/LowVRAM, RenZekta, victorjavier, webzone.
I contributi rilevanti sono gia' separati nelle PR lette. Nuovi kernel V100 e
modifiche budget 4 GB non sono automaticamente applicabili al nostro daily 22 GB.
StrataGP e il fork 2080 Ti non aggiungono nuovi commit propri in questa finestra.

## Sequenza proposta

1. **Riferimento attuale**, senza cambiare build: curva 4k/32k/64k/131k/250k
   con KV 262144, cache auto/elastica, output 512–1024; retrieval a 250k sul **daily
   combinato operativo**, ancora mancante. Registrare slot/VRAM/CPU e riuso.
2. **Portare una sola candidata #439** ai sorgenti del bundle, controllare copie
   e ring su chunk piccolo/grande; A/B nello stesso binario. Confronto modello
   a 131k, retrieval/qualita' prima di promuovere. Preservare HC/vector/#315 ed elastica.
3. **#363 per decode**, stessa disciplina, costo per riga e finestra oltre ai t/s.
4. **Fix server disconnect e stager**, poi #374 e ulteriori kernel sm75.

Non e' necessario aggiornare in blocco alla 0.1.34 per provare #439/#363: un porting
ristretto rende il confronto piu' leggibile e preserva le patch locali. Se si
porta tutta la base, riconciliare prima commit asincrono/events, #315 e contatori
dei buffer FP16; non duplicare cio' che e' gia' upstream.

Le patch che superano i controlli vanno **nella combinazione operativa e poi nel
lanciatore**, con backup e stessa policy elastica. Nessuna candidata modificata
o promossa in questa ricognizione; nessuna finestra GPU occupata.
