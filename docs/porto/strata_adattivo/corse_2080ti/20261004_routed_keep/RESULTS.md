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

## Taratura di `--pcie-frac` e prefetch PCIe dello strato successivo — 2026-10-05

Compito code, arena intera registrata (come il Daily), una riga per corsa. File: `pcie_sweep.txt`,
`prefetch_ab.txt`, `prefetch_dma_ab.txt`.

`--pcie-frac` (copy kernel, il modo automatico): 0,20 -> 44,6 / 39,6 t/s; 0,28 -> 38,0 / 40,8; **0,36 (auto)
-> 46,1 / 45,7 / 44,3**; 0,45 -> 41,5; 0,55 -> 37,2 / 38,5; 0,70 -> 34,3; 0,85 -> 31,3. Piu' esperti via PCIe
tolgono lavoro alla CPU ma ogni esperto costa ~120 us sul percorso critico: il valore automatico e' il migliore.

Prefetch `STRATA_PREFETCH_NEXT=P` (prototipo di laboratorio, build-pf1): la previsione top-20 dello strato l+1
(router l+1 sull'ingresso MoE dello strato l) va in memoria mappata col doorbell; l'host accoda sul motore di
copia, dietro le copie dello strato, i primi P esperti previsti non residenti; allo strato l+1 i mancanti
prefetchati diventano gruppi GPU. Solo in modo DMA (`--pcie-mode dma`); nel modo automatico (copy kernel) non
scatta, ma la previsione costa comunque 3–6 ms per finestra di attesa GPU.

| Modo DMA | t/s | attesa GPU ms | CPU ms | esperti CPU / strato | prefetch usati |
|---|---:|---:|---:|---:|---|
| P=0 | 47,6 · 48,2 · 46,3 | 23–25 | 33–37 | 8,3–8,5 | — |
| P=3 | 44,1 · 47,3 | 30–31 | 30–31 | 7,1 | 2,0 su 2,9 (68%) |
| P=5 | 42,9 · 47,8 | 32 | 27–29 | 6,1–6,4 | 3,0 su 4,9 (61–63%) |
| P=8 | 43,5 · 41,4 | 39–41 | 25 | 5,3–5,6 | 4,4 su 7,8 (55–57%) |
| P=16 | 29,6 · 27,9 | 84–86 | 16–17 | 3,6–3,8 | 6,5 su 15,4 (41–43%) |

- Il prefetch toglie davvero lavoro alla CPU, ma su PCIe 3 (13 GB/s) un esperto costa ~140 us di bus contro
  ~90 us per calcolarlo sulla CPU dove sta; con precisione 55–68% e le copie in coda davanti a quelle dello
  strato successivo l'attesa GPU cresce quanto o piu' del risparmio CPU. Nessun P migliora il riferimento.
- Margine residuo: togliere la previsione dal percorso critico (calcolarla dopo il doorbell) vale al piu' i
  3–6 ms che costa; potrebbe rendere P=3–5 appena positivo. Su PCIe 4/5 il conto cambia (bus 2–4x).
- Il modo DMA senza prefetch (47,4 t/s di media) batte il copy kernel automatico (~45–46): +3–4%, ma upstream
  l'ha tolto per un blocco del driver (issue #31); in 16 corse DMA non si e' visto.

## VRAM sul 2080 Ti: dove va, budget WDDM, cache piu' grande — 2026-10-05

Strumento: `STRATA_TRACE=1` con la build di laboratorio (fork `main` d868840) stampa per ogni fase la VRAM libera per
CUDA, il budget DXGI del processo, il suo uso e la VRAM usata dalla scheda (NVML). Corse `TR-*`, `OB-*`, `LB-*`.

Base del motore (uso del processo prima della cache, MiB): contesto CUDA 174, pesi densi del pack 1.468, proiezioni
dense native dal GGUF 1.781, sessione ~970 (QSA a 262k 849: KV in VRAM e tabella RoPE; stati GDN 112), bozza MTP 840:
**~5,3 GiB, tutto giustificato**. Gli esperti hanno ~10,2–10,9 GiB.

- Il budget WDDM del processo scende mentre il processo cresce (21,5 -> 17,7 GB): Windows trattiene ~2 GB e comprime
  gli altri programmi. `cudaMemGetInfo` = budget - uso: a regime il motore vede ~0,8 GiB liberi, la scheda ne ha ~2,7.
- Il primo tentativo di cache automatica prova ~13,9 GiB (spazio letto prima che il budget scenda), satura la scheda
  a 22,2 GB e poi si riduce: risultato finale corretto, percorso goffo.
- Contesto massimo (262k -> 131k -> 64k: +124 / +210 slot) e blocco di prefill (8.192 -> 2.048: stessi slot, prefill
  830 -> 483 t/s) non liberano VRAM utile.
- Cache fissa oltre l'automatico (`OB-*`, codice corto): fino a 11,6 GiB il budget sale (19,0 GB) e tutto sta in
  VRAM, 12,6 GiB sfora il budget (scheda piena) e rallenta un po'; nessun crollo da paging.
- **A 131k (`LB-*`, B, B, poi A)**: inizio a 11,6 GiB -> L01 38,3 / 42,2 t/s, L02 37,1 / 37,2; automatica -> L01
  42,0, L02 38,6. L'elastico porta comunque la cache a ~10,9–11,1 GiB: **nessun guadagno, l'automatico resta**.
  A 131k la CPU pesa poco (~2 esperti per strato, 9–15 ms su 43–52 ms per finestra): dominano l'attesa GPU
  (~22–25 ms) e le bozze accettate (1,6–2,0 token per finestra).

## Port upstream v0.1.39 (`port/0139`, fd7f51f) contro il Daily — 2026-10-05

Velocita' a 131k (`LP-*`, prima B due volte, poi A; arena intera):

| Corsa | L01 t/s | L02 t/s | prefill L01 |
|---|---:|---:|---:|
| port 0.1.39 | 46,4 · 43,4 | 41,3 · 41,8 | 128 s · 294 s |
| Daily 0.1.38 | 38,7 | 38,0 | 129 s |

Decode +9–20%: lavoro dell'host per strato da ~2,8 a ~0,5 ms per finestra (plan/actq/jobs/stage). Il prefill da
294 s della seconda corsa e' la tabella PLE letta dall'SSD (195 s bloccati in letture contro 6 s: pagine non piu' nella
cache file di Windows), non il port.

Fedelta' in teacher forcing (`TF-P0139-*` contro `TF-A1-*`; `TF-A2-*` = rumore A/A del Daily), `tf_port0139.txt`:

| Compito | KL A/A | KL port | PPL A/A | PPL port |
|---|---:|---:|---:|---:|
| code | 0,0004 | 0,0006 | +0,32% | +0,23% |
| explain | 0,0005 | 0,0018 | -0,19% | -1,77% |
| ledger | 0,0001 | 0,0002 | +0,13% | +0,72% |

Token sicuri (scarto >= 0,5 nat) concordanti al 100% ovunque; nessuno spostamento sistematico della perplessita'.

## Bozze MTP a 131k sul Daily 0.1.39 — 2026-10-05

`LM-*` (prima B, poi A), eseguibile installato, arena intera. Greedy: l'output non cambia, conta il costo per token.

| Variante | L01 t/s | L02 t/s | token/finestra L01 | ms/finestra L01 | esperti CPU / VRAM per strato L01 |
|---|---:|---:|---:|---:|---|
| `--spec-min-p 0.3` | 47,3 | 40,9 | 2,53 | 53,6 | 3,19 / 30,2 |
| `--spec 6 --spec-min-p 0.3` | 39,2 | 37,3 | 2,42 | 61,7 | 3,76 / 35,3 |
| `--spec-min-p 0.2` | 41,5 | 36,6 | 2,32 | 55,9 | 3,48 / 30,4 |
| **Daily `--spec 4 --spec-min-p 0.5`** | **46,8** | **42,9** | 2,05 | 43,8 | 2,60 / 21,0 |

Bozze piu' aggressive fanno accettare piu' token per finestra, ma ogni token in piu' porta i suoi esperti (CPU e
VRAM per strato crescono quasi in proporzione): la finestra costa quanto si guadagna. Il Daily resta com'e'.

Profilo GPU a 131k (`GP-ship139`, `STRATA_VERIFY_PROFILE=1`): finestra 47,7 ms = attesa GPU 25,2 + CPU 10,5 + resto;
dentro la GPU ~11 ms sono attese (waitB ~6 dati PCIe, waitA ~3 piano dell'host, waitCPU ~2), il calcolo e' sparso
(VRAM hits 6,4, hc-read+router 4,0, scores+topk QSA 2,0, gemv qkv 2,2, shared 1,9, out-proj 1,9, head 1,5, attenzione 1,3).

## Candidati GPU: PR 904 di upstream e kernel di attenzione di Encapsulate — 2026-10-05

Identita' verificata con teacher forcing a posizionamento fisso (`TFX-*`: cache fissa 5000, `--adapt-every 0`,
`--pcie-frac 0.36`): due corse del Daily 0.1.39 sono identiche bit per bit, e lo sono anche la PR 904 (fork `0f3ffb3`)
e la PR 904 + Encapsulate 6784a365 (`f0071e7`) su code ed explain (KL 0, argmax 100%). Test `verify_batch_parity` e
`pdl_parity` della PR superati sul 2080 Ti.

Velocita' a 131k (`LG-*`, prima B poi A):

| | L01 t/s | L02 t/s | ms/finestra L01 · L02 | bozza ms/finestra |
|---|---:|---:|---:|---:|
| PR 904 + Encapsulate | 46,9 | 44,1 | 41,6 · 36,7 | 2,96 |
| PR 904 | 47,0 | 43,3 | 43,0 · 37,9 | 3,60 |
| Daily 0.1.39 | 45,9 | 41,9 | 42,9 · 38,7 | 3,68 |

Guadagno piccolo (+2–5%), stesso ordine del rumore fra corse, ma senza alcun cambio dell'output: entrambe su `main`,
da includere nel prossimo Daily. Il kernel di Encapsulate accelera anche la testa MTP (bozza -20%).

## Nucleo elastico adattivo a 131k sul codice 0.1.39 + PR 904 + Encapsulate — 2026-10-05

`LCA-*` (prima B due volte, poi A), stesso eseguibile (`build-pr904enc`), arena intera.

| `STRATA_ELASTIC_CORE_ADAPT` | L01 t/s | L02 t/s | hit L01 · L02 | esperti CPU/strato L01 · L02 |
|---|---:|---:|---:|---|
| 1 | 46,7 | 44,2 | 0,88 · 0,90 | 2,30 · 1,60 |
| 1 | 48,9 | 42,7 | 0,885 · 0,883 | 2,37 · 1,82 |
| spento | 46,0 | 43,3 | 0,87 · 0,88 | 2,43 · 1,92 |

Piccolo ma coerente: circa +1 punto di hit e meno esperti calcolati dalla CPU, L01 +1–6%. Cambia solo il
posizionamento degli esperti (classe di arrotondamento gia' presente con il tier adattivo): proposto acceso nel
prossimo Daily.

## Modo DMA (`--pcie-mode dma`) sul codice 0.1.39 + PR 904 + Encapsulate, nucleo adattivo acceso — 2026-10-05

Identita': teacher forcing a posizionamento fisso (`TFX-dma-*`) identico bit per bit al Daily su code ed explain
(KL 0). Una prima corsa explain si e' fermata all'avvio (oltre 300 s alla registrazione dell'arena, prima del decode:
non e' il blocco #31) ed e' conservata come `TFX-dma-explain-failed-startup`; ripetuta, avvio in 60 s e risultato
identico. Unico stallo d'avvio su decine di avvii della giornata, da tenere d'occhio.

Velocita' a 131k (`LD-*`, prima B due volte, poi A): DMA L01 46,9 / 47,8, L02 47,2 / 45,2 t/s; automatico (copy
kernel) L01 48,8, L02 34,8 (corsa anomala: 45 ms per finestra in L02) - contro le corse automatiche `LCA-on*`
L01 46,7 / 48,9, L02 44,2 / 42,7. DMA: L01 alla pari, L02 +3–7%. Resta il rischio del blocco del driver (#31): prova
di resistenza nel benchmark finale a turni della sera.

## PR 706 (Q2_0 AVX2 bit-plane), PR 764 (`STRATA_ADAPT_LAG`) e tier piu' vivace (#907) — 2026-10-05

Dal report #913 (4060 Ti, PCIe 3 x8, AVX2, DDR3: +15–16%). Patch applicate su `main` 2d1e452 (conflitti della 764 risolti
tenendo `pin_live` e `pending_age`): `pr706_pr764_su_main_2d1e452.patch`.

Identita' a posizionamento fisso (`TFX-q2lag-*`, tier spento: conta solo la 706): **non bit-identica**. KL 0,0008 / 0,0015,
argmax 100% / 99%, token sicuri 100%, PPL -0,60% / +0,36% (code / explain). Il kernel unisce le scale di due blocchi in
una FMA: stessa matematica, arrotondamento diverso.

Velocita' a 131k (`LQ-*`, prima B, poi A; tutte con nucleo adattivo e DMA):

| | L01 t/s | L02 t/s | ms/finestra | hit |
|---|---:|---:|---|---|
| 706 + 764 | 49,7 | 46,4 | 39,1 · 34,0 | 0,882 · 0,900 |
| 706 + 764 + `--adapt-every 1 --adapt-swaps 160 --adapt-decay 0,97` | 47,3 | 46,8 | 39,8 · 34,9 | 0,895 · 0,909 |
| candidato (904 + Encapsulate) | 49,9 | 46,2 | 39,2 · 34,7 | 0,897 · 0,896 |

Nessun guadagno misurabile a 131k (la CPU calcola ~2 esperti per strato): 706 e 764 non entrano; la 706 non e' neppure
identica. Da rivedere a contesto corto o con hardware diverso.

## Stallo della tabella PLE nel prefill e PR 903 (chunk uguali) — 2026-10-05

Due prefill a 131k su 26 si sono bloccati: `LP-port2` 293 s (195 s di attesa delle letture PLE) e `LQ-q2lag` 175 s (54 s),
contro 122–133 s e 3,6–7 s di attesa di tutte le altre. Stesse 567.472 letture dall'SSD (2,37 GB, 53,5% dalla cache di
righe): cambia solo quanto risponde il disco. Il p50/p99 stampato copriva solo le ultime 65.536 letture e per questo
sembrava normale. Nessuna attivita' di questa sessione sui dischi durante le due corse, nessun evento disco o scansione
Defender nei registri di sistema, pagefile mai oltre 144 MB. La tabella e' letta da `C:\Users\imanu\Downloads`: Lexar
EQ790 NVMe senza DRAM, lo stesso disco del sistema (D: e' un EMTEC X160 SATA, peggiore). Causa del disco o del sistema,
non del motore.

Diagnostica nel fork (`3d702c7`, solo stampe): `ple io` aggiunge media, massimo e letture oltre 100 ms su tutte le
letture; il prefill stampa i chunk che aspettano piu' di 1 s le loro righe. Prova `LX-diag1` (configurazione candidata:
nucleo adattivo, DMA): prefill 127,7 s, attesa 3,8 s, media 1,7 ms, massimo 8,7 ms, 0 letture oltre 100 ms; L01 49,5 /
L02 44,6 t/s. Al prossimo stallo si vedra' se sono poche letture ferme per secondi (aiuterebbe leggere piu' chunk in
anticipo) o un disco lento uniforme (no).

PR 903 (upstream, chunk del prompt di uguale lunghezza): a 131k non cambia nulla. 131.248 token = 16 x 8.192 + 176, e
sotto 1.024 token la PR tiene i chunk pieni con la coda corta; L02 legge 167 token in un chunk come prima. Nei turni
(segmenti nuovi di ~14k) varrebbe forse mezzo secondo su ~15 s di prefill a fronte di minuti di generazione, e sposta i
confini dei chunk (identita' non garantita). Non portata: arrivera' col prossimo allineamento se upstream la unisce.

## Merge dell'attenzione limitato alla larghezza (#910, Hardin22 `b1f03d33`) — 2026-10-05

`STRATA_ATTN_MERGE_V2` (attivo di default su NVIDIA): il merge del decode si ferma a ceil(larghezza/64) chunk e
carica i parziali a blocchi di 16, stesse `fmaf` nello stesso ordine. `STRATA_MTP_KV` (formato K/V del drafter) e'
opt-in e spento. Fork: `3effa9d`.

Identita': `attn_merge_parity` sul 2080 Ti 768/768 casi identici (fp16, int8, q4_0, k8v4); teacher forcing a
posizionamento fisso `TFX-mv2-*` identico bit per bit a `TFX-enc-*` su code ed explain (`tf_fixed_mv2.txt`).
Bench del merge (cap 32768 del drafter, 1 query): larghezza 32768 da 224 a 50 us; 5 query a larghezza ~2051 da
45–88 a 9–17 us.

Velocita' a 131k (`LV-*`, configurazione candidata: nucleo adattivo, DMA; prima B due volte, poi A):

| | L01 t/s | L02 t/s | bozza ms/finestra (L01 · L02) |
|---|---:|---:|---|
| merge v2, corsa 1 | 48,5 | 45,6 | 3,11 · 2,55 |
| merge v2, corsa 2 | 46,7 | 45,2 | 2,78 · 2,59 |
| candidato senza (`build-plediag`) | 49,9 | 46,2 | 3,33 · 2,83 |

Bozza ~0,3 ms piu' veloce per finestra; totale nel rumore. Portato perche' identico.

## Kernel Q2_0 AVX2 esatto — 2026-10-05

Richiesta dell'utente: una versione della #706 che non cambi l'output. Fork `c3fc8f3`: stesso calcolo in virgola
mobile del kernel precedente (stesse FMA nello stesso ordine, stessa riduzione, stessa correzione dell'offset -1);
cambiano lo spacchettamento dei codici (8 operazioni invece di ~17, vettori lo/hi uguali byte per byte), d x scala
in vettore, 4 righe insieme sui down corti (<= 16 blocchi; sulle righe lunghe l'interleave rompeva il prefetcher:
0,89x da RAM, tolto). `STRATA_Q2_LEGACY=1` tiene il vecchio.

Identita': `q2_exact_parity` 504 casi, 570.634 uscite identiche bit per bit; `pool_quant_parity` 64 casi sul GGUF
reale; `TFX-r2-*` identico bit per bit a `TFX-enc-*` (`tf_fixed_r2.txt`).

Velocita': un thread 1,11–1,45x (cache e RAM, nt 1–4). Pool reale (`cpu_format_bench <gguf> pool 400`, 7 worker,
us per strato, due giri alternati): IQ2_XXS + Q2_0 down 526–532 contro 551 (-4%); Q2_0 + IQ4_NL 480–485 contro
517–527 (-8%); Q2_0 + Q2_0 347–351 contro 423 (-17%). Nel nostro GGUF il Q2_0 e' solo il down di parte degli strati
(es. strato 20: gate/up IQ3_S, down Q2_0): a 131k atteso ~0,5%, non misurabile.

## Candidato 0.1.39-r2 (merge v2 + Q2 esatta + diagnostica PLE) — 2026-10-05

Fork `main` `d5c049c` (manifest di laboratorio `r2cand-20261005.json`, `check_source.py` SOURCE_OK). Eseguibile
`build-r2cand` (sha in `build.json`). Configurazione candidata: `STRATA_ELASTIC_CORE_ADAPT=1`, `--pcie-mode dma`
(piu' `STRATA_ARENA_PIN_GIB=64` dei banchi).

| `LR-*`, prima B due volte poi A | L01 t/s | L02 t/s | esperti CPU per strato-finestra (L02) |
|---|---:|---:|---:|
| r2, corsa 1 | 50,6 | 43,3 | 1,96 |
| r2, corsa 2 | 48,1 | 44,7 | 1,64 |
| `build-plediag` (main senza merge v2 e Q2 esatta) | 49,5 | 47,6 | 1,35 |

Nel rumore: le L02 di B hanno avuto piu' esperti calcolati sulla CPU (piazzamento elastico/adattivo diverso), non
un effetto del codice, che a posizionamento fisso e' identico bit per bit. Il verdetto spetta al benchmark finale a
turni.

## Stallo PLE colto con la diagnostica (`LV-mv2b`) — 2026-10-05

Prefill 336,5 s contro ~130. `ple io`: lettura media 113.654 us (normale 1.700–2.500), massimo 273 ms, 248.019
letture su 567.472 oltre 100 ms, attesa 252,7 s. Attese per chunk: 57,1 / 41,3 / 28,0 / 28,7 / 24,0 / 17,7 / 10,2 s
sui chunk 0–49152, poi normali: tutto il disco rallentato ~50x per ~4 minuti, poi ripreso da solo. Non poche
letture bloccate: leggere piu' chunk in anticipo non servirebbe.

Causa probabile: C: (Lexar EQ790 NVMe senza DRAM, disco di sistema, contiene la tabella in
`C:\Users\imanu\Downloads`) con 40,7 GB liberi su 930 (96% pieno): manutenzione interna del controller; calore non
verificabile senza permessi di amministratore. Il prefill a 131k richiede in media ~4.500 letture/s (567k in
~125 s), quindi anche D: (EMTEC X160 SATA, 369 GB liberi) basterebbe. Liberazione di spazio delegata dall'utente a
un'altra chat; poi A/B con la tabella su D: (vedi `HANDOFF_5_OTTOBRE_SERA.md`).

## Tabella PLE su D: — 2026-10-05 sera

Copia dello shard 2 in `D:\ds4_work\strata\Strata-data\gguf\` (robocopy, 61 s), sha256 di origine e copia uguali
(`316B46F3…61E113`). L'originale in `Downloads` resta.

Avvio: `--ple-gguf` da solo fallisce con `native dense: duplicate split shard number` (`LPD-d*-failed-dupshard`). Il
motore elenca ogni shard accanto a `--native` (anche lo shard 2 in `Downloads`) e poi accoda `--ple-gguf`. Con
`--native-dense-gguf` esplicito (shard 1 da `Downloads` + copia su D: dello shard 2) quell'elenco non si costruisce e
lo shard 2 letto e' solo quello su D: (`PLE on, table 320001536 rows of D:\…`). Anche il sorgente del Daily r1
(`46aa04b`) ha `--native-dense-gguf`. `run_long.py --add-opt` accoda opzioni ripetibili; script
`20261005_handoff/script/ple_d.sh`.

A/B a 131k, configurazione candidata r2 (nucleo adattivo, DMA), `build-r2cand`. C: con 96–103 GB liberi (10,4%)
dopo la pulizia. GPU gia' occupata da altri programmi (20–40%, 3,7–4,9 GB: browser con video): le t/s di decode non
si confrontano con le corse precedenti.

| corsa | tabella | prefill L01 | lettura media / max | letture >100 ms | attesa prefill | L01 / L02 t/s |
|---|---|---:|---:|---:|---:|---|
| `LPD-c` (A prima di B, C: in scrittura) | C: | 294,4 s | 81,4 / 533 ms | 176.271 | 185,7 s | 41,3 / 44,3 |
| `LPD-d1b` | D: | 134,7 s | 10,1 / 16,1 ms | 0 | 23,2 s | 41,5 / 33,2 |
| `LPD-d2b` | D: | 135,6 s | 10,1 / 16,1 ms | 0 | 23,1 s | 42,2 / 39,7 |
| `LPD-cb` (A) | C: | 491,6 s | 195,4 / 401 ms | 434.704 | 445,2 s | 47,0 / 40,4 |
| `LR-r2a` (4/10, C: sano) | C: | 129,1 s | 3,3 / 57 ms | 0 | 7,7 s | 50,6 / 43,3 |

Attesa PLE durante il decode (delta `blocked`, 1024 token): D: 4,6–48 ms, C: 4,4–63 ms, trascurabile ovunque: la
posizione della tabella non tocca il decode. Su D: ogni lettura costa ~10 ms (SATA) ma senza code lunghe: unica attesa
il primo chunk (~2 s), prefill +4% sul C: sano. Su C: lo stallo questa volta copre 12 chunk su 17 (0–90112) e il p50
resta 1,4 ms: la maggior parte delle letture va, una parte resta ferma ~200–400 ms. Liberare 55 GB non l'ha tolto;
probabile manutenzione del controller dopo la cancellazione in massa (TRIM e garbage collection), non verificabile
senza SMART (servono i permessi di amministratore).

Verdetto: la tabella su D: passa i criteri del §6.1 (prefill stabile, nessuna attesa lunga, decode invariato). Per il
Daily servono tre righe nel config: `--ple-gguf <D:>` e `--native-dense-gguf` due volte (shard 1, shard 2 su D:).
Fatto col consenso dell'utente (`20261005_ple_d/`, controllo sulla 8100 superato); il suo sospetto sulle scritture
continue su C: (video YouTube in un browser) e' compatibile con un NVMe senza DRAM. Pagefile escluso: picco 144 MB
dal boot.

## PR 930: decodifica IQ3_S / IQ2_S AVX2 senza shift per indice (sanastasiou) — 2026-10-05 sera

Upstream #930 (`9233f998`, aperta): solo `iq_avx2.cpp`; indici della griglia da tabella costante, segni con un
`pshufb`, scale da tabella, gather di IQ3_S scelto una volta per chiamata. Nel nostro GGUF i gate/up degli esperti
sono IQ3_S in 13 strati e IQ2_S in 10 su 48 (gli altri IQ2_XS 10, IQ2_XXS 9, IQ3_XXS 6). Fork: `087212e` (strumenti),
`862c18a` (port), `52a39e5` (manifest `r2cand930-20261005.json`, SOURCE_OK). Cartella `20261005_pr930/`.

Identita':
- `iq256_dump` (nuovo, laboratorio): 972 casi (sei formati, 1–9 token, righe con resti, `iq256_rows` e
  `iq256_gu_rows`), 739.238 uscite: file uguali byte per byte prima/dopo e con `STRATA_IQ256_GATHER=1`
  (sha256 `9731e590…`). Mutazione di un bit IQ3_S (`qh = 0x02`) rilevata; quella piu' grossolana la ferma gia' la
  `static_assert` della PR.
- Teacher forcing a posizionamento fisso `TFX-pr930-*` identico bit per bit a `TFX-enc-*` (code ed explain, 3,5–6
  esperti per strato-finestra sulla CPU), col config del Daily gia' su D: (`tf_fixed_pr930.txt`).

Velocita' (macchina con video nel browser: rumore alto, base e PR alternati):

| banco | IQ3_S | IQ2_S |
|---|---|---|
| gate/up a un thread, 640 x 10 blocchi (`bench_iq256.txt`) | 1,25–1,40x | 1,00–1,31x |
| pool reale 7 worker, us per strato-finestra (`pool_iq256.txt`) | 1248/1493 -> 957/874 (strato 20) | 1008/783 -> 678/633 (strato 21) |

I formati non toccati nello stesso banco oscillano di ±10–15% (rumore). Atteso a 131k: ~26 us risparmiati per voce
IQ3_S e ~15–25 per IQ2_S, con ~2,8 voci CPU per strato-finestra ~1–1,7 ms su ~45 ms di finestra, cioe' +1–3% di
decode se la parte CPU resta sul percorso critico. Da misurare a macchina libera; candidato a entrare nella r2 (B del
benchmark notturno = `build-pr930`).
