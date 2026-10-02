# Top-k prefill con limite attivo — 2 ottobre 2026

Il daily a74e con KV262144 alloca uno stride di65538 blocchi per riga di
punteggi QSA. Il dispatcher top-k usa quello stride per verificare il limite
dei registri33792, quindi sceglie il kernel legacy anche a131k di contesto.
Il prefill conosce gia' il massimo n_bid+1 del batch monotono di256 query.

Patch0025: nuova API `qsa_block_topk_active`, chiamata solo dal prefill con
quel limite. I kernel e i punteggi restano identici; lo stride resta65538.
L'API originale e il decode con grafi catturati sono preservati: un limite
host fissato alla cattura diventerebbe errato quando il contesto cresce.
Con limite non valido o oltre33792 blocchi si torna all'API originale.
`STRATA_TOPK_CAPACITY_GUARD` presente forza il comportamento precedente;
il runner lo elimina sia dal JSON sia dall'ambiente per il confronto active.

Candidata compilata sugli input esatti del daily, ricompilando selezione CUDA
e prefill e riusando HC/GDN FP16, vector, PR315 e gli altri oggetti.
SHA256 exe **f469e096e868e4579daaec71ceef63693790e300e7a4cc5b49a8853d075a1d34**.
Nessuna CH16/BPW aggiunta in questa candidata. **Promossa alle07:18**, dopo
le prove sotto; daily precedente a74e conservato per il ripristino.

## Parita' e banco nativo

16casi superati: contesti1111/8192/32768/131072/131075/135164/135168/
250022/262144, batch1/8/255/256/257, code parziali, punteggi zero e tie,
fallback con limite0 e superiore allo stride. **Tutti gli indici selezionati
identici bit per bit**, anche all'ultimo limite registri33792 e al primo
fallback33793. Stride65538 in tutti i casi, capacita' reale del modello.
Banco funzionale deterministico, nessun modello o carico concorrente.

| Contesto / query | Capacity A1 ms | Active B ms | Capacity A2 ms |
|---|---:|---:|---:|
| 8192 /256 | 0,073 | 0,185 | 0,070 |
| 32768 /256 | 0,681 | 0,223 | 1,179 |
| 131072 /256 | 6,025 | 1,827 | 5,332 |
| 135164 /256 | 5,783 | 1,391 | 6,668 |
| 135168 /256 | 5,868 | 6,414 | 5,775 |
| 250022 /256 | 15,034 | 14,635 | 14,775 |

Sette ripetizioni, eventi CUDA, A/B/A nello stesso processo. Rumore ampio nei
casi brevi; a8192 il registro e' piu' lento. Non attribuire i tempi fallback
a un miglioramento: e' lo stesso kernel. Nessuna misura fisica dei GB/s.
Oltre135164 celle il nuovo percorso prefill torna al legacy: un eventuale
guadagno sul prefill250k riguarda il tratto iniziale, non il decode profondo.

## Confronto sul modello completato 06:53–07:07

Capacity/active/capacity, stessa candidata, due prompt131k/1024output per
corsa, KV262144, int8 residente32768, cache auto/elastica, nessun carico
artificiale. Prompt reali131248 e131239; il secondo riusa131072 token.

| Modalita' | Prefill nuovo t/s | TTFT s | Decode aggregato t/s | ms/riga verificata | Slot iniziali |
|---|---:|---:|---:|---:|---:|
| A1 capacity | 831,20 | 158,509 | 38,251 | 21,970 | 6537 |
| B active | 886,38 | 148,664 | 39,272 | 21,720 | 6524 |
| A2 capacity | 828,26 | 159,092 | 39,293 | 21,352 | 6872 |

Riferimento medio829,73t/s: **+6,83% prefill**, variazione A/A0,35%; B supera
entrambi i riferimenti, con cache iniziale molto simile adA1. TTFT medio
158,801→148,664s, risparmio10,137s. Beneficio nel singolo A/B/A molto superiore
alla variazione dei riferimenti; cache elastica e MTP variabili restano limiti
dell'attribuzione. Anche l'exe daily a74e misurato alle06:38 e' allineato:
827,53t/s prefill,39,048t/s decode.

Decode B identico adA2 entro0,02t/s: **nessun guadagno decode attribuito al
top-k prefill**. La nuova API non e' chiamata dal percorso decode.
Primi logits248320 finiti, argmax1596 in tutti i casi; A/A maxabs1,30/1,71,
A/B1,56/1,89. Nessuna parita' dell'intero modello o validazione generale della
qualita' rivendicata: la parita' bitwise riguarda gli indici del banco nativo.
JumpConnect CPU media zero; altre CPU medie0,956/0,865/0,887core.
Evidenza `corse_2080ti/20261002_topk_model/`, analizzatore riproducibile.

## Retrieval250k, decode profondo e promozione

Retrieval upstream a10/50/90%: **3/3FOUND**, prompt reali30742/30742/30743,
tempi31/29/30s. Dimensione32k del tool e' stimata per caratteri; usare i token
reali qui riportati. Poi ago al50% del testo della fixture, **250022 token
reali**: ARCO-AMBRA-742913 recuperato, zero token riusati, prefill391472,7ms,
**638,67t/s**, richiesta392,86s. Il successivo follow-up ha prompt250091,
riusa250015 token e genera **1024 token fino a finish length**, raggiungendo
251115 token totali, dentro la capacita'262144.

Decode26110,5ms, **39,218t/s**; 76token nuovi letti in1317ms, richiesta28,48s.
Draft583accettati su944offerti, cachehit88,3%, blocchi KV95,09% letti daVRAM;
residenti32768 ed elastica preservati. E' un campione lungo di decode a250k,
non il vecchio campione di13token. Le quattro copie dei primi logits conservate
(due needle condividono lo stesso offset) hanno248320 valori finiti ciascuna.

| Profondita' prompt | Prefill nuovo t/s | Decode t/s | Output del campione |
|---|---:|---:|---:|
| 131248/131239 | 886,38 sul primo | 39,272 aggregato | 2×1024 |
| 250022, poi250091 | 638,67 sul primo | 39,218 sul follow-up | 1024 |

Due punti della curva, stessa capacita'262144 e stessa build; prompt e MTP
differenti, quindi non e' una curva controllata di un unico testo. Il confronto
causale della patch resta A/B/A a131k. Il daily precedente ha misurato442,4t/s
sulla stessa fixture250k in un'altra finestra: **non attribuire quella differenza
di velocita' interamente al top-k**. Il nuovo dispatcher accelera solo il tratto
prefill entro135164 celle, lasciando il decode e il tratto successivo invariati.

Installata la candidata esatta in `D:\ds4_work\strata\Strata\build-0131-topk-active`;
exe/source/hash uguali al lab. JSON SOTA punta al nuovo exe; BAT Desktop aggiorna
commento, controllo exe e percorso server dello stesso bundle. Port8100loopback,
KV262144/int8/residente32768, auto/elastica e riserva1393MiB preservati.
Nessuna lettura della chiave API. Copie repository/operative byte-identiche.

Ripristino: `D:\ds4_work\strata\ripristini\20261002_071823_0131_topk_active` contiene
le copie precedenti di JSON/BAT operativi e repository; riportare ciascuna al
percorso originale. Bundle a74e intatto. Helper `promuovi_topk_attivo.py` verifica
branch, hash, A/B/A, parita' e retrieval/decode prima di modificare il lanciatore.

**Avvio della copia installata superato** in42,84s, capacita'262144, cache6513;
fonte server dello stesso bundle, SHA2563e556df4e13f783f9d961113dd0bbed7481f677e265b45c3a7f238b18530484a.
Prova avvio su porta lab18120 senza chiave; il server operativo8100 si avvia dal
BAT quando richiesto dall'utente. Tutti i processi lab chiusi, nessun messaggio
ad altre chat. Evidenza `corse_2080ti/20261002_topk_quality/`.

## Pista BPW del fork2080Ti, tenuta separata

Patch0024 e strumenti `port_score_bpw.py`, `compila_score_bpw.py`,
`prova_score_bpw.py`: adatta il riuso dei query head del
[commit95afc8d del fork2080Ti](https://github.com/jklnvlink/Strata-2080ti/commit/95afc8d39aef).
Scorer BPW4/8/16 soltanto su sm75 con piu' di8 query; decode multi-query
e altre GPU preservati. Candidata SHA256df8ecdb06679f70ed07c59dd5b2e461a7254fc102e5beae1cb70fef12e78d9f4.

16casi superati: **tutti gli score bitwise, finiti, tutti gli indici uguali**,
compreso decode multi preservato. BPW16 a131k/8192query:
310,444/295,697/305,769ms (−4,03% sulla mediaA); a262k/8192query:
654,068/612,867/620,294ms, riduzione inferiore alla variazioneA/A.
BPW4/8 senza vantaggio chiaro. Questi batch8192 non sono il batch reale
della selezione prefill256: nessuna prova sul modello o promozione BPW.
Questa ricognizione ha portato alla scoperta del dispatcher top-k sopra.

Evidenza selezionata `corse_2080ti/20261002_topk_active/` e
`corse_2080ti/20261002_score_bpw/`. Sorgenti/build complete restano nel lab.
