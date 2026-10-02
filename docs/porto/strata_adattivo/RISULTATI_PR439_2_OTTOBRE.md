# PR439 su daily elastico: correttezza gather verificata, velocita' non dimostrata

Prove del 2 ottobre 2026, RTX 2080 Ti 22 GB, Ryzen 5800X, Windows/CUDA 12.6.
**Daily mantenuto su `build-0131-daily`: #439 non promossa.** Il riempimento reale
250k del daily operativo e' riuscito. Il gather batch supera tutti i controlli delle
copie, ma il confronto A/B/A sul modello non separa un guadagno dalle oscillazioni
dei riferimenti. Nessun carico artificiale; cache sempre auto/elastica.

## Riempimento reale del daily operativo

Eseguibile realmente indicato dal JSON/Desktop, SHA256
`a74e4dadcd4fbb9e71b5cb0ae66922453c6a44a2704db25ddfb5e81601c5f766`.
Server `build-0131-daily/source/serve/server.py`. Capacita' KV **262144**, int8,
residenti 32768. Prompt nuovo, **250022 token reali**, nessun token riusato;
parola `ARCO-AMBRA-742913` al 50% dei caratteri del filler. Una sola profondita',
non una batteria di accuratezza sul lungo contesto.

- Risposta esatta `ARCO-AMBRA-742913`: retrieval riuscito, stop regolare.
- Richiesta 566,61 s; lettura motore 565,117 s, **442,4 t/s**.
- Avvio 65,97 s; cache iniziale 6580 esperti, 10895 MiB, 2234 MiB liberi.
- 13 token generati: 25,0 t/s dal contatore motore. Campione troppo corto per
  stimare il decode a 250k o una curva KV/t/s.
- Cache elastica a due zone confermata; prestito prefill 2959 slot, 4,73 GiB.
- Limite totale 900 s, processi propri chiusi dopo il successo.

La lettura comprende il primo chunk freddo: non confrontare i 442 t/s di questa
prova con gli 800+ del banco 131k come se la profondita' fosse l'unica differenza.
Il daily combinato HC/GDN FP16 + vector + #315 ha ora un controllo retrieval reale
250k; accuratezza generale e curva decode rispetto alla profondita' restano aperte.

## Port e controllo delle copie

Fonte: [PR #439](https://github.com/Niko1221/Strata/pull/439), head fissata
`2a3a99b2d49ea9e8466e4657430535a56ddaf9ad`.
La PR raccoglie fino a 16 esperti nativi per lancio MMQ e rimanda il rilascio dei
ring slot finche' il gather e' stato lanciato. Il decode resta invariato. Il
guadagno dell'autore (3,6–4,3%, RTX 5070 Ti) non e' una misura sulla nostra GPU.

Applicata alle sorgenti complete del daily 0.1.31, conservando tutte le patch
operative. Adattato il target CMake alla posizione del ramo CUDA/MMQ della 0.1.31.
Il test originale e' esteso a **34 casi**: ogni dimensione da 1 a 16, ogni partenza
intermedia da 1 a 15, sorgenti non allineate, dimensioni dispari e caso piccolo.
Tutti confrontano le copie batch/singole e i byte originali: **34 pass, zero fail**.
Controllo breve su buffer, senza carichi per simulare saturazione della macchina.

Ricompilati solo `prefill.cpp` e `moe_mmq.cu`; librerie engine/kernel daily, kernel
HC/GDN FP16 e oggetto generate diagnostico riusati con hash registrati. Il helper
`strumenti/compila_pr439.py` conserva comandi/log e verifica la base prima del build.
Il confronto usa lo stesso binario in entrambe le modalita'. Candidata conservata in:

`D:\ds4_work\strata\Strata\build-0131-pr439\strata.exe`

SHA256 `686be366da45626d4f67ad696b152c862f95b74b46a7c4445a5bfd52ce084a51`.
Sorgenti completi e server nello stesso bundle; il server ha lo stesso hash del
daily operativo. La patch portata e' `patches/su-0.1.31/0021-PR439-Raggruppa-gather-native-MMQ.patch`.
**La presenza nella cartella delle patch applicabili alla 0.1.31 non significa promozione.**

## A/B/A sul modello, cache operativa preservata

Tre avvii separati della candidata installata nel percorso definitivo, ordine
singolo/batch/singolo. `--gather-modo uno` imposta `STRATA_PREFILL_GATHER_ONE=1`;
`batch` la rimuove anche dall'ambiente ereditato: il codice controlla la presenza,
non il valore. MMQ compilato e IQ3_XXS supportato; nessun override MMQ/ring ereditato.

Ogni corsa: due riscaldamenti brevi, L01 da **131248 token tutti nuovi**, L02 da
131239 con 131072 riusati; **1024 token generati per ciascuna richiesta lunga**,
stop length. KV 262144, int8, residenti 32768, `--expert-cache auto --elastic`,
riserva 1393 MiB, MTP operativo. Diagnostica primo token e timing uguali in A e B.
Nessuna cache fissa, nessuna pressione aggiunta. Limite 480 s per corsa.

| Corsa | Gather | Prefill L01 t/s | TTFT L01 s | Decode aggregato t/s | Costo per riga ms | Slot iniziali | VRAM libera MiB | CPU altrui media, core |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | singolo | 852,99 | 154,470 | 39,684 | 21,512 | 6516 | 1280 | 0,89 |
| B | batch | 849,50 | 155,093 | 38,553 | 21,771 | 6924 | 854 | 1,03 |
| A2 | singolo | 833,67 | 158,024 | 39,004 | 21,715 | 6524 | 1065 | 0,85 |

Media dei riferimenti prefill **843,33 t/s**. B rispetto alla media **+0,73%**,
rispetto ad A1 **−0,41%**, rispetto ad A2 **+1,90%**. I due riferimenti differiscono
del **2,29%** rispetto alla loro media. Una sola B, cache e CPU variabili:
**nessun beneficio di velocita' dimostrato sulla 2080 Ti nel profilo daily**.
Il decode non misura un effetto del gather; testo e accettazione MTP differiscono.
Il costo per riga e' somma ms decode / somma `(generated - accepted + offered)`
delle sole due richieste lunghe.

Questi riferimenti usano il binario candidato con la logica gather precedente;
non sono nuove misure del vecchio exe a74e. Per il daily realmente promosso resta
il confronto dell'1/10: 822,66 t/s prefill e 38,995 t/s decode, vedi
`PROMOZIONE_DAILY_0131_1_OTTOBRE.md`. I riferimenti odierni confermano l'ordine
di grandezza oltre 800 t/s sullo stesso insieme di kernel.

## Numerica e decisione

Primi logits L01/L02: 248320 valori, tutti finiti, stesso argmax 1596 nelle tre
corse. Non bit-identici fra avvii. Anche A1/A2 differisce: L01 massimo assoluto
1,6877 e media 0,2668; A1/B 1,3639 e 0,1925; A2/B 1,5323 e 0,2499. Questo
controllo non attribuisce le differenze al gather e non certifica la qualita'
generale. La parita' byte-per-byte verificata e' quella delle copie del kernel.
Diagnostica completa in `corse_2080ti/20261002_pr439/logits-confronto.json`.

La #439 resta una candidata di laboratorio: **non validata come accelerazione**,
quindi non rientra nelle patch da promuovere automaticamente nell'operativo.
Non eseguito il successivo riempimento 250k della candidata, dato l'esito A/B/A;
il retrieval 250k riuscito sopra riguarda il daily gia' operativo. JSON/BAT Desktop
e relative copie versionate sono byte-identici, exe a74e preservato. Nessun cambio
dei parametri operativi o della chiave API, mai ispezionata.

Finestra retrieval 04:37–04:48; seconda finestra compilazione/parita'/A-B-A
04:48–05:03, entro il massimo 30 minuti concordato. Processi propri chiusi,
nessun strata/llama-server rimasto, **VIA a OCGC-IA e PROMO alle 05:04**.
Nessun altro test o monitoraggio GPU programmato.

Prossima priorita' dalla ricognizione: **#363, decode grouped PCIe + SwiGLU/q8_1**.
Non portata in questa finestra; beneficio dell'autore contenuto e da distinguere
dalla CPU. Altra pista successiva: fork sm75 QSA, prima chiarendo la discrepanza
tra documentazione e costante effettiva. Non sovrapporre #439 a #372/altre patch gather.

Evidenza: `corse_2080ti/20261002_pr439/`, con output esito, log, CPU, risultati
del banco, hash della build e verifica dello stato operativo in `operativo.json`.
Curva KV/t/s omogenea ancora assente: il campione da 13 token a 250k non la sostituisce.
