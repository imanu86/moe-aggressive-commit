# Esperti a basso peso scartati in decode: fedelta' e velocita' reali

**Esito: scartare in decode gli esperti a basso peso che costerebbero CPU/PCIe accelera
il decode CPU-bound del 25–57% con una perdita di fedelta' piccola e misurata.**
Prototipo di laboratorio nel fork (`2d47c09`, `a530246`, `8dd24f0`), spento per
default; Daily, config e launcher invariati. Macchina in uso durante le prove
(CGControl acceso, GPU altrui 2,4–3,7 GB, carico variabile): velocita' rumorose,
riportate come mediane con tutti i singoli valori.

## Perche' questa prova

Lo schermo offline del mattino (errore L2 della somma routed <=3%) non era tarato.
Togliere il solo decimo esperto (5,6% di peso) dava gia' il 14% su quella metrica.
Qui la fedelta' si misura sul testo: teacher forcing con `STRATA_LOGPOS` e
`STRATA_LOGPOS_TOPK=20` sulla risposta greedy del modello completo (stesso exe,
configurazione elastica del Daily); la risposta passa dalle finestre di verifica
(`--short-read` dopo il prompt in cache), quindi la sonda agisce solo li', come in
uso reale. Metriche: argmax uguale, argmax sulle posizioni nette (scarto >=0,5 nat),
KL(A||X) su top-20 piu' resto. Scala: due run A identici KL 0,0001–0,0005; upstream
misura Strata contro llama.cpp sugli stessi pesi KL 0,0008–0,0016 (risposte brevi)
e 0,039 dopo un prompt da 16K (`docs/UNSLOTH_Q4.md`).

## Varianti (env del fork)

- `STRATA_ROUTED_KEEP=k`: solo i primi k per peso (`_RENORM=1` rinormalizza).
- `STRATA_ROUTED_MIN_W=t`: scarta peso < t oltre i primi `STRATA_ROUTED_MIN_KEEP` (4).
- `STRATA_ROUTED_KEEP_SKIP=1`: gli scartati escono davvero dal piano (niente job CPU,
  fetch PCIe o gruppo GPU). Verifica: top-8 con e senza salto KL 0,0006.
- `STRATA_ROUTED_MISS_W=t`: scarta peso < t (oltre i primi 4) **solo se non residente**
  in VRAM: i residenti costano poco e restano.

## Fedelta' (KL medio contro A1; prosa = sole posizioni della risposta)

| Variante | Esperti/token | Codice (2470+164) | Magazzino (1680+152) | Prosa IT (85+512) |
|---|---:|---:|---:|---:|
| A2 (rumore) | 10 | 0,0004 | 0,0001 | 0,0005 |
| top-8 | 8 | 0,0032 | 0,0010 | 0,0120 |
| top-6 | 6 | 0,0066 | 0,0017 | 0,0460 |
| top-6 rinormalizzato | 6 | 0,0130 | — | 0,0584 |
| top-4 | 4 | 0,0136 | — | 0,1509 |
| peso >= 0,06 | ~7,6 | 0,0032 | 0,0016 | 0,0086 |
| peso >= 0,07 | ~6,5 | 0,0055 | 0,0022 | 0,0195 |
| non residenti < 0,08 | variabile | 0,0066 | 0,0031 | 0,0188 |
| non residenti < 0,10 | variabile | 0,0102 | 0,0039 | 0,0490 |

Argmax sulle posizioni nette: >=98,2% in tutte le varianti fino a 0,08/0,07; la prosa
italiana e' la piu' sensibile. Rinormalizzare peggiora. Run liberi: top-8 sul
magazzino produce gli stessi 152 token del completo; nessuna variante ha prodotto
JSON rotti o loop (a differenza della cache chiusa del mattino).

## Velocita' reale (generazione libera, mediane; singoli tra parentesi)

| Variante | Codice t/s | CPU ms/finestra | Prosa t/s | CPU ms/finestra |
|---|---:|---:|---:|---:|
| A | 35,1 (25,5 39,4 37,3 32,9) | 60,7 | 34,6 (35,7 37,0 33,6 33,3) | 21,7 |
| peso >= 0,06 | 44,8 (44,0 45,6) | 34,7 | 36,5 (37,2 35,9) | 14,4 |
| peso >= 0,07 | 47,8 (48,9 46,8) | 29,7 | 33,2 (25,2* 41,1) | 9,3 |
| non residenti < 0,08 | **49,3 (50,2 48,3)** | 26,7 | **40,8 (40,8)** | 7,8 |
| non residenti < 0,10 | **55,0 (54,3 55,7)** | 17,0 | 36,4 (46,9 25,9*) | 6,5 |

\* run con `stage` anomalo (~34 ms per finestra): contesa GPU esterna. Un avvio
(`S-M08-2-explain`) e' scaduto (startup 300 s) ed e' escluso.
L'attesa GPU per finestra resta 22–28 ms in tutte le varianti: il guadagno viene
solo dalla CPU. Sul codice (CPU-bound, 2470 token di prompt) +40% (0,08) e +57%
(0,10) sulla mediana di A, +25%/+40% sul miglior A. Sulla prosa breve la cache
elastica copre gia' l'80–87% e la CPU pesa poco: +18% con 0,08 (un solo run).

## Limiti

Tre compiti, profondita' 85–2470 token, non 131k/250k. Velocita' con macchina in
uso e poche ripetizioni: serve una finestra quieta con >=4 coppie A/B alternate.
Fedelta' locale misurata, non correttezza su un insieme ampio di compiti.
Il conteggio `usage` della cache adattiva esclude gli scartati: la residenza puo'
divergere da A nelle sessioni lunghe.

## Gate-first sui neuroni: fedelta' (build-v4, `STRATA_GATE_KEEP`)

Per ogni (token, esperto) si tengono i neuroni con |silu(gate)| piu' alto e si azzera h
sugli altri, sia nel percorso GPU (kernel prima di SwiGLU) sia nel pool CPU nativo.
Le righe sono ancora calcolate: e' una misura di qualita'. Coerenza CPU/GPU verificata
sul banco esperti (L2 routed 1,1–4,1% con meta' dei neuroni, contro 0,9–1,3% senza).

| Neuroni tenuti | Codice KL | Magazzino KL | Prosa KL (argmax nette) |
|---:|---:|---:|---:|
| 70% | 0,0037 | 0,0024 | 0,0141 (99,6%) |
| 60% | 0,0087 | 0,0023 | 0,0254 (99,1%) |
| 50% | 0,0116 | 0,0047 | 0,0471 (97,1%) |

Il 70% sta nella fascia delle soglie sugli esperti (peso >= 0,06/0,07). Il risparmio
possibile e' minore: con il 70% dei neuroni si salta circa il 10% dei pesi dell'esperto
(solo righe `up`) o il 20% con `down` memorizzato per neurone; la soglia 0,07 sugli
esperti ne salta circa il 31% con KL simile. Un primo run (G70 codice) e' fallito per
memoria impegnata insufficiente (WinError 1455): il runner ora attende >=52 GiB di commit.

## Perplessita' della risposta del modello completo (teacher forcing)

`exp(-media lp(target))` sulle sole posizioni della risposta greedy di A; rumore A2 +-0,2%.

| Variante | Codice | Magazzino | Prosa IT |
|---|---:|---:|---:|
| peso >= 0,06 | +0,8% | +0,5% | +1,8% |
| non residenti < 0,08 | +0,7% | +1,0% | +3,6% |
| non residenti < 0,10 | +1,3% | +1,0% | +6,5% |
| gate-first 70% | — | +0,6% | +3,7% |
| top-6 | +1,2% | +0,6% | +8,0% |
| top-4 | +2,6% | — | +22,6% |

Misura favorevole ad A (e' il suo testo). Da ripetere su testo umano e su compiti CGC con
risposta verificabile prima di qualunque uso: l'utente intende provarlo sul lavoro reale.

## A 131k (casi L01/L02 del banco P0, `run_long.py`, config elastica del Daily)

Un processo per braccio: L01 legge 131.248 token (prefill ~134 s), L02 riusa 131.072 token dal
prompt cache; 1024 token generati, temperatura 0, ragionamento predefinito del server.
Bracci alternati, macchina in uso. Medie (singoli in `K-*`):

| Braccio | n | L01 t/s | L02 t/s | Finestra | Attesa GPU | CPU esperti | Token/finestra |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 39,5 | 36,8 | 47,0 ms | 22,9 | 11,1 | 1,80 |
| non residenti < 0,08 | 3 | 47,4 (+20%) | 41,0 (+11%) | 41,9 | 24,6 | 5,6 | 1,86 |
| non residenti < 0,10 | 2 | 46,3 (+17%) | 42,5 (+15%) | 40,3 | 24,8 | 4,0 | 1,79 |
| vocabolario allargato | 2 | 40,1 (+2%) | 36,2 (−2%) | 47,8 | 23,3 | 11,2 | 1,83 |
| vocabolario + 0,08 | 2 | 47,8 (+21%) | 41,6 (+13%) | 41,7 | 24,6 | 5,7 | 1,87 |

A 131k la CPU pesa meno (11 ms su 47 per finestra) e il guadagno dello scarto scende a +11–20%.
Il vocabolario e' neutro qui: i casi L01/L02 ragionano e scrivono in inglese. Un primo K-A1 e'
stato bloccato dal controllo di stato (motore precedente ancora in chiusura) e ripetuto come K-A1b.
Fedelta' a 131k non misurata (il teacher forcing e' stato fatto a contesto corto).

## Tier adattivo e nucleo elastico adattivo (5 ottobre)

**Scambi adattivi** (default `--adapt-every 4 --adapt-swaps 96`) contro `--adapt-swaps 0`, exe del Daily,
vocabolario rt_it48k (`AD-*`, `KD-*`; esclusi AD-off1-explain e KD-on2 per contesa GPU, stage 47/25 ms):

| | Hit rate on -> off | t/s on -> off |
|---|---|---|
| codice 2470 | 61-68% (vedi CA) -> n/d | 39,0 -> 33,4 (+17% con gli scambi) |
| prosa | 80% -> 55% | 37,8 -> 30,1 (+26%) |
| 131k L01 / L02 | 85% -> 65% | 39,5 / 35,0 -> 32,2 / 29,2 (+23% / +20%) |

Il profilo statico da solo copre il 55-67% delle chiamate; gli scambi portano all'80-87%. E' la
causa del decode che "migliora con la profondita'": la cache si adatta mentre si genera.

**Nucleo adattivo** (`STRATA_ELASTIC_CORE_ADAPT=1`, fork main 8b9c342, port/0139 fd7f51f; build-core1):
- 131k (`KC-*`): L01 38,7 -> 41,5 t/s (+7%), L02 invariato, hit +0,5 punti;
- contesto corto (`CA-*`): prosa +4%, codice nel rumore (hit 61-68% in entrambi i bracci);
- sessioni lunghe (`SS-*`, 9 richieste alternate nello stesso processo): hit +1-3 punti al terzo
  giro; alternando compiti l'hit rate non cresce. SS-ada2 fallita all'avvio (timeout 300 s), da ripetere.

Esatto per costruzione (cambia solo dove si calcolano gli esperti). Guadagno piccolo: decisione
sull'attivazione di default dopo la ripetizione di SS-ada2.

## Arena limitata a 8 GiB (laboratorio) contro arena intera (Daily) — 2026-10-05

Compito code, exe del Daily, una corsa per lato. I run di laboratorio usano `STRATA_ARENA_PIN_GIB=8`: solo 10
fette dell'arena sono registrate per la GPU e la quota PCIe dei mancanti (0,36 sul nostro link da 13 GB/s)
vale su pochi strati. Il Daily registra tutta l'arena (43 GB).

| Run | t/s | ms/finestra | CPU ms | attesa GPU ms | per strato-finestra: CPU / VRAM / PCIe |
|---|---:|---:|---:|---:|---|
| P-cap8-code | 41,9 | 88,2 | 42,5 | 25,8 | 9,89 / 26,46 / 0,93 |
| P-full-code | 43,7 | 83,4 | 38,2 | 27,1 | 8,25 / 23,88 / 3,86 |

Con l'arena intera la GPU prende ~4 esperti per strato via PCIe (+4% di decode, una corsa), ma la CPU resta il
46% della finestra: circa 96 us per esperto nel motore contro 81 nel banco del pool (finestra da 10).
