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
Nessuna CH16/BPW aggiunta in questa candidata. Daily operativo a74e preservato.

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

Confronto modello capacity/active/capacity con due prompt131k/1024output per
corsa, KV262144 e cache auto/elastica: in corso. Nessuna promozione fino
all'esito combinato e al retrieval250k con decode lungo.

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
