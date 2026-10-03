# Strata: sessione di quattro ore, 3–4 ottobre 2026

Finestra autorizzata: 3 ottobre 19:59–23:59 UTC, cioè 21:59–01:59 italiana.
Hardware misurato: RTX 2080 Ti modificata da 22 GB, Ryzen 7 5800X, RAM 96 GB,
CUDA 12.6, PCIe 3.0. Un solo motore GPU per volta, nessuna compilazione durante
le misure, nessuna pressione artificiale e nessuna azione sulle applicazioni
dell'utente. Agenti OpenAI economici per esecuzione, monitoraggio e ricognizione;
revisione e verifiche indipendenti nel processo principale.

## Modifiche validate e installate nel Daily

- **Exact-small:** controllo A2 fisso completato; quattro righe complete di logits
  e 66 ID d'uscita bitwise. Il confronto fisso misura +3,85% a 130380 e −0,10%
  a 249322 token. Il confronto elastico ha conteggi slot diversi e non attesta
  parità bitwise: non confondere le due prove. Evidenza nel commit `237efba`.
- **Contratto del prefisso emesso, PR652:** 12 richieste, cap da 1 a 256 token,
  ID e prima riga bitwise; candidato con prefisso esatto in 11/11 casi applicabili.
  I riferimenti eccedevano l'uscita di 1/2/1 token in tre casi. Il problema
  originario di perdita del contratto non è stato riprodotto. Nessuna misura
  di velocità e nessuna prova che risolva da solo le risposte brevi.
- **QSA a gruppi di otto query su SM75:** estensione della
  [PR187 di q8atnight](https://github.com/Niko1221/Strata/pull/187), riuso dei
  blocchi chiave FP32 e ordine aritmetico della singola query conservato.
  `STRATA_QSA_PREFILL_MULTI=1` è opt-in nel motore, selezionato nel Daily.
  Dodici casi sintetici, 26 processi: buffer completi identici. Nel modello
  off/on/off coincidono quattro righe complete finite e 258 ID per braccio.
- **Contatori HtoD e snapshot PLE:** diagnostica opt-in, spenta nel Daily.
  Due gate di quattro bracci ciascuno, descritti sotto, verificano le righe
  complete e gli ID d'uscita. Non modificano la politica di I/O operativa.

Il Daily mantiene KV int8 da **262144** celle, **32768** residenti, cache esperti
automatica ed elastica, spec CLI 4, checkpoint tail ogni 16384 token.
La grid originale respinta nei giri precedenti resta esclusa.

## QSA: beneficio misurato e limiti numerici

| Contesto effettivo | Token nuovi / riusati | A1 ms | B ms | A2 ms | Guadagno throughput |
|---|---:|---:|---:|---:|---:|
| 130380 | 1014 / 129366 | 3722,0 | 3520,2 | 3697,0 | +5,38% |
| 249322 | 1014 / 248308 | 4233,5 | 4000,3 | 4268,0 | +6,26% |

Formula: `(media(A1 prompt_ms, A2 prompt_ms) / B prompt_ms - 1) × 100`.
Controllo a 6167 slot fissi / 10218 MiB, KV 262144/int8/residenti 32768,
spec 4, exact-small attivo, IQ_MT_MIN predefinito 2; suffix, adattamento,
PCIe fraction e conv disattivati. Il dump della prima riga avviene dopo
`prompt_ms` e influenza decode e tempo totale.

Cold 129366: 325,298 / 130,794 / 417,148 secondi. La dispersione dei controlli
impedisce di attribuire un guadagno causale. Il successivo contesto 248308 riusa
130373 token: non è un cold da 250k. Non emerge un guadagno decode dimostrato.
**Nessuna nuova SOTA cold/decode.** La variante di gruppi/griglia, ripetuta
sull'anomalia, non mostra un vincitore consistente: archiviata e non installata.

Il gate teacher esteso prevedeva 256 posizioni a 130380 e 256 a 249000 per
ciascuno dei tre bracci. Il limite di lavoro interrompe A2; durata registrata
1712,984 secondi. Sono raccolte **1456 delle 1536 righe previste**: A1 e B ne
hanno 512 ciascuno, A2 ne ha 432. Revisione indipendente di byte, finitezza e
hash: A1/B coincidono su tutte le 512 posizioni; A2 coincide sulle 256 a 130k
e sulle 176 disponibili a 249k. Mancano 80 righe A2: **gate esteso incompleto,
nessun PASS complessivo**. Nessuna discrepanza osservata nelle righe raccolte.
[Copertura e hash](https://github.com/imanu86/Strata-2080Ti/blob/main/docs/sm75/qsa-teacher-partial-20261004.json).

Codice e riproduttore QSA: `3f436aa`; `ac142dc` corregge solo terminatori e spazi
degli allegati generati, conservando dati e geometria.

## Conversazione reale: 190 turni fino a 250k

Conversazione HTTP da **20002 a 250130 token d'ingresso**, cronologia completa,
prima domanda da 20k, successive circa 1k; ultima più corta per rispettare il
target. Temperatura 0,6, top_p 0,95, top_k 20, thinking off, cap 512. Profilo
Daily auto/elastico, spec CLI 4 con policy adattiva, nessun override IQ,
profiler, trace o dump. Durata 2017,73 secondi con avvio e chiusura.
Tutte le 190 risposte terminano con `stop`.

| Fascia dei follow-up | N | Prefill aggregato t/s | Decode aggregato t/s | TTFT mediana s |
|---|---:|---:|---:|---:|
| 20–50k | 24 | 230,6 | 31,5 | 2,99 |
| 50–100k | 40 | 328,2 | 36,1 | 3,16 |
| 100–150k | 41 | 307,5 | 39,8 | 3,42 |
| 150–200k | 41 | 290,3 | 40,6 | 3,64 |
| 200k–fine | 43 | 269,6 | 41,0 | 3,86 |

Tutti i 189 follow-up: **286,5 prefill e 38,0 decode t/s**, includendo i turni
lenti iniziali. Il cold da 20k anomalo richiede 214,342 secondi (93,3 t/s);
il processo recupera dal sesto turno senza modifiche. Ultimo turno: 151 token
nuovi, 73,7 t/s e TTFT 2,218 secondi, non confrontabile con un turno da 1k.
Vicino a 130k, il turno con contesto 130820 misura 304,7/41,5 t/s. La fascia
completa è più rappresentativa di un singolo punto scelto.

La precedente curva di 187 turni ha cronologie e risposte diverse: il confronto
non è causale. I 6420 slot riportati dall'API sono uno snapshot iniziale;
i conteggi nel log cambiano con l'elastica e non dimostrano residenza fisica.

Una successiva prova HTTP sul Daily operativo completa tre turni fino a 22505
in 89,47 secondi. Cold 20002: 18,332 secondi, **1091,1 t/s**. Follow-up da 1017
e 934 token: 376,7 e 339,7 t/s; decode 36,6 e 36,3 t/s. Il contenuto utente
iniziale coincide per hash con la curva lenta; il primo run non registrava
l'hash del prompt interamente renderizzato. Cache iniziale 6420 contro 6361
slot: la differenza cold è intermittente, ma la causa non è dimostrata.

Lettura manuale di 17 risposte: frasi complete, con ripetizioni e affermazioni
tecniche non supportate. Questa curva attesta continuità e prestazioni,
non qualità semantica generale; non attribuire quegli errori alla patch senza
un confronto isolato.

[Curva, CSV, protocollo e hash del fork](https://github.com/imanu86/Strata-2080Ti/blob/main/docs/sm75/BENCHMARKS.md#grouped-query-qsa-prefill-4-october-2026).

## Diagnosi banda e rallentamenti

Primo gate: A1 originale, B contatori spenti, C stessa build con contatori
accesi, A2 originale. Prefissi 20001/21015, un token d'uscita, tutte le righe
complete bitwise. Cold 19,087 / 211,984 / 19,208 / 19,259 secondi; warm
3,796 / 13,738 / 3,792 / 3,784 secondi. L'anomalia B è conservata: C torna
veloce con la stessa build. Host PLE **193044 ms contro 693 ms** nel cold A1;
delta warm 9720 contro 75 ms. Il tratto CUDA fra eventi può includere attese
host: 193795 ms nella fase combine non significa 193 secondi di kernel combine.

Contati **110833920000 byte** di esperti nel cold e **33418368000 byte** nel
follow-up, tutti da arena pinned. I contatori coprono 19994 e 1013 token batched,
mentre i token nuovi nativi sono 20001 e 1014. La verifica del token finale
resta esterna ai contatori. Sono somme delle chiamate HtoD sul ring primario:
escludono accessi residenti, peer, refill e P2P. Dividere per tempo prompt non
misura la banda istantanea PCIe né quella interna della VRAM. Il fixture warm
attraversa un confine di turno/checkpoint e usa due chunk, non il tipico turno
HTTP singolo.

Durante B una lettura NVIDIA mostra P5, SM 660 MHz, memoria 810 MHz, 29,8 W,
senza limiti termici o di potenza attivi. Può essere una conseguenza delle
attese; nessuna impostazione clock è stata modificata. Il percorso PLE include
attesa del gather asincrono, letture/decodifica, upload/sincronizzazione e avvio
del gather seguente. La diagnosi restringe la fase, non isola ancora ogni passo.

Secondo gate, con snapshot PLE: quattro bracci, 248,907 secondi, otto righe
complete finite e bitwise, ID coincidenti, otto record di contatori coerenti.
Cold A1/B/C/A2: 19,231 / 19,209 / 19,278 / 19,790 secondi; follow-up
3,784 / 3,744 / 3,917 / 3,901 secondi. C aggiunge `--ple-sync-submit`, che
disabilita anche il keepalive esistente: non isola il solo thread.
Nessun vantaggio dimostrato; politica I/O operativa invariata.

Conteggi e tempi di attesa delle snapshot sono cumulativi; p50/p99 coprono
al massimo le ultime 65536 letture e non si sottraggono. Tempi gather/collect
e GPU possono sovrapporsi e non sono additivi al tempo della richiesta.
Codice diagnostico `3634cad`, opt-in `STRATA_PREFILL_STATS=1`, spento nel Daily.
[Bracci, contatori e hash](https://github.com/imanu86/Strata-2080Ti/blob/main/docs/sm75/prefill-diagnostics-20261004.json).

Nell'ultimo replay Daily il log annuncia gli esperti caricati dopo circa 266
secondi; l'endpoint HTTP è pronto dopo 274,740 secondi. Sono letti 39,97 GiB
di arena a 0,18 GiB/s, con 7082 slot iniziali. Il messaggio generico del motore cita
la priorità bassa come possibile causa, ma il processo osservato è `Normal`
(priorità base 8): non è una causa dimostrata. GGUF su C: NVMe, pack ed eseguibile
su D: SATA. Healthy/Online non esclude uno stallo. Distinguere questo caricamento
iniziale dalle attese PLE durante il prefill; nessuna politica I/O o clock cambiata.

## Esperimento BF16 escluso

Adattamento locale della [PR655](https://github.com/Niko1221/Strata/pull/655):
prodotti BF16 del modello principale via FP16 tensor core, percorso MTP
conservato. Microtest superati; gate modello su 256 righe teacher per profondità
a 20001/130380/249000 **FALLITO**. A1/A2 bitwise, KL 0; accordo top-1 del
candidato 97,27% / 98,44% / 94,92%, che non equivale ad accuratezza semantica.
P99 KL 0,06082 / 0,46965 / 0,38426 oltre le soglie locali. Sorgenti archiviati
e rimossi prima della build QSA; **mai installati nel Daily**. Non è un giudizio
sulla PR655 originale.
[Evidenza](https://github.com/imanu86/Strata-2080Ti/blob/main/docs/sm75/bf16-main-rejected-20261003.json).

## Repository e prossimi passi

Controlli periodici di main, PR e fork. La [PR693](https://github.com/Niko1221/Strata/pull/693)
modifica la geometria dei chunk lunghi: il segmento da 1014 token mantiene
lo stesso arrotondamento; nessun beneficio warm dimostrato qui. L'autore misura
+2,2% a 20k e +1% a 100k per la sola equalizzazione su 5070 Ti; i +21–38%
richiedono `auto:16384`, altra geometria/cache. Non sono misure sulla nostra 2080 Ti.
La [PR698](https://github.com/Niko1221/Strata/pull/698) aggiunge un benchmark
2080 Ti/IQ3_XXS su i9-9900KF/Windows, non una patch. La PR656 riguarda richieste
concorrenti; la issue605 riguarda PLE direct su HDD/Linux, analogia di categoria
e non diagnosi del nostro caso Windows/NVMe.

La [PR663](https://github.com/Niko1221/Strata/pull/663) resta interessante per
la futura seconda 3060 e maggiore residenza dei pesi in VRAM. Non attribuirle
vantaggi sulla scheda singola senza misure.

Priorità successiva: separare attesa del future PLE, enqueue HtoD, attesa
dell'evento di riuso del buffer, avvio del gather, issue/collect/decodifica e
coda IOCP. Poi misurare traffico di un vero turno elastico da 1k e geometrie
del prefill lungo. Il runner HTTP 130k→134k, cap 600 secondi, è preparato e
controllato a CPU; rinviato per rispettare la finestra di quattro ore.
Nessuna misura viene attribuita a questa prova non eseguita.

Runner locale: `.codex_runs/20261003_four_hours/run_http_prefill_stats.py`, SHA256
`f61c95379e5c6c6cf5a55b1d521852d75e4379e4c5c16cf6e38db84383841dd8`.
Usa l'eseguibile Daily verificato, un clone della configurazione con il solo
`STRATA_PREFILL_STATS=1`, limiti temporali e chiusura dei propri processi.
Prima di lanciarlo in una nuova sessione, riconfermare hash, assenza di altri
test/build, tempo disponibile e confronto tra record HTTP e contatori nativi.

Ogni confronto deve conservare anomalie, controlli A prima/dopo, cache e
contesto effettivi, gate numerico e lettura delle risposte.
Prima di dichiarare completo il gate teacher esteso, serve un nuovo controllo
A2 con copertura delle 256 posizioni a 249k e provenienza coerente: le 80 righe
mancanti non vanno considerate implicitamente superate.

## Replay finale e chiusura

Il replay finale usa l'eseguibile Daily effettivo, diagnostica spenta, i 190
turni completi più domanda finale, temperatura 0 e cap 1536. Nessuna cronologia
troncata; la prima risposta non viene aggiunta alla seconda richiesta.

| Thinking | Prompt effettivo | Riusati | Output | Prefill nativo s | Oracle automatico |
|---|---:|---:|---:|---:|---|
| off | 250487 | 0 | 52 | 293,332 | FAIL sul suffisso del nome GPU |
| on | 250523 | 0 | 306 | 407,485 | PASS |

Entrambe le risposte finali riportano i cinque dati corretti: RTX 2080 Ti,
VRAM 22 GB, KV 262144, residenti 32768, margine
`262144 - 250130 - 512 = 11502`. Senza thinking il nome include «modificata»,
corretto per questa scheda ma non previsto dal matcher letterale. L'esito
automatico originale resta FAIL; la verifica manuale dei fatti è distinta.
Con thinking il JSON supera anche il matcher originale.

Durata complessiva 989,66 secondi; avvio HTTP 274,74 secondi, cache iniziale
7082 slot, runtime spec 6 con CLI spec 4 e policy adattiva. Entrambe le richieste
leggono il prompt completo. Le osservazioni singole, con attese intermittenti
e cache variabile, non dimostrano un effetto causale del thinking sui tempi.
I fatti sono presenti anche in precedenti risposte dell'assistente: non è un
benchmark hidden-needle o di qualità generale.
[Risultato pubblico e hash](https://github.com/imanu86/Strata-2080Ti/blob/main/docs/sm75/qsa-daily-recall-20261004.json).

Motore e server di prova chiusi, input verificati invariati dopo il test.
La misura HTTP aggiuntiva dei byte resta rinviata. Log grezzi, risposte private,
ragionamenti, configurazioni e ID grezzi restano locali in
`.codex_runs/20261003_four_hours/`.

## Provenienza operativa e recupero

- Eseguibile Daily: `a17d0dd5362bc35420ca9ef3d1a8cf8c014dafbb3aea189c6c664fe7930e8674`.
- Configurazione: `f0237b6abdacd73944fb9232bcdaf016c733bc2dd1fdae6723284ae3659f2e8d`.
- Manifest storico conservato: `1e85822a2b869e82bf8e1c48b4df630c589948e027c8cd8d13fd170130b343e1`.
- Sorgenti/frontend runtime: 286 file tracciati confrontati, tutti identici al
  fork. I 48 file non tracciati storici del checkout operativo sono preservati.
- Launcher desktop: hash `9bbddc9b0ab63c6dbd3dde24b81b36635fafda7203a9b2c160a3ecfefca23686`;
  22 righe operative identiche al backup, esclusi commenti e righe vuote.
  Punta ancora al Daily su `127.0.0.1:8100`.
- Recupero diagnostica: `build-0138-daily/backup-prefill-diagnostics-20261004/`;
  contiene eseguibile precedente, configurazione, tre sorgenti e `recovery.json`.
  Overlay separato: `build-0138-daily/prefill-diagnostics-validation.json`.
  Restano anche i backup QSA e exact-small; nessun manifest originale riscritto.

Ultima ricognizione: **23:51:37 UTC**. Main upstream resta
`99f3dbd0b21d1401b3769e0c0d963913607f380b`; PR652/655/663 senza nuovi head.
La [PR614](https://github.com/Niko1221/Strata/pull/614) resta aperta su `8dad0ca`,
senza review o commenti del maintainer rilevati. Non sono stati inviati altri
messaggi in questo giro. La ricerca di duplicati riconosce il kernel upstream
multi-query della PR187 come lavoro precedente; non è emersa una seconda
implementazione della nostra estensione ai gruppi di prefill SM75 più ampi.
La ricerca non è una prova di assenza in ogni fork o branch.

La release scaricabile più recente resta
[`v0.1.38-sm75-20261003-r1`](https://github.com/imanu86/Strata-2080Ti/releases/tag/v0.1.38-sm75-20261003-r1),
basata su `fc9a767`: è precedente al main con QSA e diagnostica e distinta
dall'eseguibile Daily locale `a17d0dd5…`. Il README del fork esplicita questa
distinzione. Nessuna nuova release binaria o workflow aggiunto in questa sessione.

Rapporti ed evidenze sanitizzate pubblicati nel fork; handoff e questo rapporto
nel branch research autorizzato. Checkout operativo riallineato ai soli report
finali, senza ricompilare né cambiare runtime, configurazione o file non tracciati.
Fork e checkout operativo chiusi sul commit `d21d66013d1452d895b046cd2cf58bb720be3911`;
la modifica sorgente più recente rimane `3634cad`. Il punto di recupero prima
dell'ultimo fast-forward è registrato localmente in `daily-before-final-docs.json`.
La finestra si chiude con i motori di prova terminati e il richiamo periodico
disattivato. La prossima misura richiede una nuova sessione, non un proseguimento
automatico oltre le quattro ore.
