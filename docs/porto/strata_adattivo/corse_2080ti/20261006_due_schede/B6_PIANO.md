# B6 — più token accettati per finestra di verifica

Fronte B6 dell'obiettivo 80 t/s a 131k su due schede (3060 + 2080 Ti, `--layer-split=16`).
Codice: fork `Strata-2080Ti-core` 434ddca; lavoro nel worktree `C:\Users\imanu\source\repos\Strata-wt\b6`,
branch `lab/b6-draft`.

## Conclusione

Il collo non è la quantità di bozze, ma il **prezzo di ogni riga**. Una riga in più costa circa 7,8 ms su
una finestra da ~33 ms (17 ms per token emesso). Una riga ripaga solo se aggiunge almeno ~0,46 token attesi.
Per questo spec 5/6 e min_p 0,3 non aiutano, e alberi o multi-radice sono in perdita con questo verificatore.
La leva di B6 resta il dimensionamento della finestra secondo il costo: la regola di Dinkelbach con la
calibrazione appresa online. Il guadagno misurato è **+1–2 %** (replay sulle stesse finestre; nelle corse A/B resta sotto il rumore), non +25 %. Il +25 % da sola
accettazione richiede di abbassare il costo per riga (fronte kernel) o un drafter migliore (fronte training).

## Fatti misurati (dai log delle corse finite)

Corse a due schede (`build-*`, split 16, spin 100): S-ref1/2, P-base2/3, H-s3/s5/s6/s8, H-spin2, H-mp65.

| corsa | caso | avg T | tok/finestra | ms/finestra | t/s | bozze accettate |
|---|---|---|---|---|---|---|
| S-ref1 | L01 | 2,35 | 1,96 | 33,35 | 58,8 | 502/703 (71 %) |
| S-ref1 | L02 | 2,02 | 1,69 | 30,52 | 55,4 | 420/617 (68 %) |
| S-ref2 | L01 | 2,12 | 1,80 | 31,91 | 56,4 | 455/640 (71 %) |
| H-mp65 (min_p 0,65) | L01 | 2,08 | 1,93 | 32,02 | 60,3 | 494/571 (87 %) |
| H-s3 | L01 | 2,27 | 2,06 | 32,31 | 63,6 | 526/632 |
| H-s5 | L01 | 2,64 | 2,20 | 35,05 | 62,8 | 561/763 |
| H-s6 | L01 | 2,93 | 2,25 | 38,32 | 58,7 | 574/876 |

- **Costo per riga.** Regressione su 18 punti (corsa × caso):
  `ms/finestra ≈ 15,5 + 7,8·T`, di cui `verify ≈ 15,5 + 6,2·T` e `draft ≈ 0,9·T`.
  La riga marginale vale ~34 % di una finestra da una riga. Non è banda: 10 esperti × 48 layer × ~1,5 MB
  fanno ~1,5 ms per riga sulle due schede, contro i 6,2 ms misurati. Il costo è implementativo
  (lanci ed esperti piccoli per layer).
- **Il testo cambia tra le corse.** Gli md5 di L01/L02 differiscono in ogni braccio: l'arrotondamento
  GPU/CPU degli esperti fa divergere il greedy. Da una corsa all'altra la stessa config oscilla di ±5 % in
  t/s e di ±0,15 bozze accettate per finestra (S-ref1 contro S-ref2). Un effetto sotto il 5 % non si vede
  con una corsa per braccio.
- **Calibrazione.** H-mp65 toglie 0,27 bozze per finestra rispetto a 0,5 e perde solo ~0,03–0,05 accettate
  per finestra (stima rumorosa). Le bozze con p in [0,5; 0,65) sembrano accettate ben sotto il 46 % che
  servirebbe a ripagarle. Da confermare con il log per finestra (sotto).
- **Lookup (`pick_lookup`/suffix).** Lavora su 2–19 finestre su 450–660 per richiesta, con 1–51 bozze
  accettate. Il guadagno massimo è sotto l'1 %: non è una leva.
- **Diagnostica top-2.** `STRATA_MTP_TOP2` è morta: `MtpDrafter::record_top2` non viene mai chiamata, quindi
  `top2()` restituisce sempre -1 e il conteggio dei runner-up non ha mai misurato nulla.

## Idee valutate, con numeri

| idea | guadagno atteso | costo / rischio | verdetto |
|---|---|---|---|
| Albero / multi-radice (top-2 alla prima posizione incerta) | +P(rifiuto)·P(top2 giusto) ≤ ~0,3·0,4 ≈ 0,12 token per riga in più, sotto la soglia 0,46 → in perdita | i layer GDN sono ricorrenti: un ramo richiede uno stato forkato o kernel con maschera ad albero su sm_75 e sm_86 | **scartata** |
| Finestra più lunga quando il drafter è sicuro (spec 5/6) | H-s5 +4 %, H-s6 −1 % contro il rumore ±5 % | nessuno | inclusa nella regola di costo (con `--spec=5` sceglie lei) |
| min_p più basso (0,3/0,2) | negativo sulla singola scheda (LM-p03 −0 %/−5 %, LM-p02 −11 %) | — | le corse M-mp30/M-mp20s5 del coordinatore lo verificano; nessun duplicato |
| min_p fisso più alto (0,6–0,7) | +0–4 % (H-mp65 60,3 contro 56–59) | nessuno | sotto-caso della regola di costo |
| **Regola di costo (Dinkelbach) + calibrazione online** | +2–6 % (taglia le righe sotto 0,46 token, estende quelle a catena sicura) | solo host, nessun kernel; uscita identica | **implementata, opt-in** |
| Stop cumulativo nel drafter | −0,3–0,5 ms di draft sulle catene a bassa probabilità composta | nessuno | implementato (`STRATA_SPEC_ADAPT_CUM`) |
| Lookup più aggressivo | < 1 % | — | scartata |

## Cosa è implementato (opt-in, default off)

- `STRATA_SPEC_LOG=<file>`: una riga per finestra del ciclo serve: T, accettate, probabilità di ogni bozza
  offerta più la prima trattenuta, verdetto controfattuale della trattenuta (gratis: quando tutte le bozze
  passano, la riga bonus dice se la successiva sarebbe passata) e tempi verify/commit/draft/giro.
  Analisi: `b6_analisi.py <log>`: costo per T dentro la stessa corsa (niente confondimento tra testi),
  calibrazione per profondità e probabilità, replay offline di min_p, regole cumulative e Dinkelbach sulle
  stesse finestre.
- `STRATA_SPEC_ADAPT=1`: T = argmax_t E(t) − R·C(t), con E(t) = 1 + Σ prodotti cumulativi
  dell'accettazione calibrata, C(t) il costo misurato da `DraftPolicy` per dimensione, R i token/ms
  correnti (EMA). La calibrazione si impara online per profondità × decile di probabilità, con prior = p.
  Manopole: `_R_SCALE` (severità), `_PRIOR_N`, `_MINP` (stop del drafter), `_CUM` (stop cumulativo).
- La verifica non cambia: ogni token emesso è quello del target.

## Misure (fase 2)

1. **B6-1 diag**: build del worktree, config Daily a due schede, `--spec=5`, `STRATA_SPEC_LOG`. Dà il costo
   per T dentro la corsa e la calibrazione fino a 4 bozze. → replay offline.
2. **B6-x on/off**: `STRATA_SPEC_ADAPT=1` (con lo `_R_SCALE` scelto dal replay) contro off, stesso build.
   Gate: t/s su L01+L02 sopra il rumore, ms/finestra spiegati, testo normale (L01/L02 senza loop, rapporto
   parole distinte/totali ~0,5).

## Idee rimaste (fuori da B6, più grandi)

- **Costo per riga** (fronte kernel/verify): 6,2 ms contro ~1,5 di banda. Con 2 ms per riga, min_p 0,3 e
  spec 6 (T ~3,5, ~2,5 tok/finestra) darebbero ~2,5/(23+2·2,5) ≈ 89 t/s. È la vera strada per gli 80.
- **Drafter più accurato** (training su più dati o fine-tune rt_it48k sul dominio): ogni +0,1 di accettazione
  per bozza vale ~+5 %.
- **Finestre in pipeline** (`--pipeline-windows 2`): sovrappone i due stadi, un altro fronte.

## Risultati fase 2 (6 ottobre, sera)

Build `build-b6-1` (dfd9f6e) e `build-b6-2` (bc9f881, costo a retta). Log per finestra in
`20261004_routed_keep\B6-logs\*.log`; analisi con `b6_analisi.py`.

**Costo per riga, dentro la stessa corsa** (B6-d5b, spec 5): T=1 23,5 ms · T=2 29,8 · T=3 35,8 · T=4 42,0 ·
T=5 50,6. In tutte le corse `giro ≈ 16,6–17,7 + 6,3–7,3·T` ms. La retta stimata tra corse
(15,5 + 7,8·T) era giusta.

**Calibrazione: il drafter è calibrato, anzi un po' prudente.** Profondità 0: p 0,2→0,26–0,31 accettate ·
0,3→0,36–0,43 · 0,4→0,46–0,55 · 0,5→0,56–0,61 · 0,6→0,64–0,69 · 0,7→0,68–0,84 · 0,8→0,84–0,89 ·
0,9→0,96–0,98. Alle profondità 1–3 lo stesso, un po' più basso. Il sospetto su H-mp65 era rumore tra testi.

**Copertura del vocabolario di bozza.** I token generati fuori da `rt_it48k/draft_vocab.bin` sono lo
0,53 % su 10 uscite (utilization, colleague, analogy…). Non è una leva.

**Replay sulle stesse finestre (t/s; 7 corse × 2 casi).** La regola cambia, il testo no:
- min_p 0,65 rispetto a 0,5: **da −0,8 a −2,9 %**; min_p 0,70: **da −1,4 a −4,8 %**. Upstream #775 dice
  il contrario, ma qui una riga costa solo 6,5 ms contro una base di 17: le bozze tra 0,5 e 0,7 (accettate
  al 56–69 %) ripagano.
- Dinkelbach rispetto a min_p 0,5: **da +0,2 a +1,6 %** (in media +0,9 %); cum 0,4 circa uguale.
- Spec 5 rispetto a spec 4 (B6-d5b): +0,5 % in L01, 0 in L02.
- **Oracolo** (accettazione nota: righe esatte più una bozza trattenuta): +12–16 %. È il tetto di qualunque
  regola di selezione con questo drafter e questo costo.

**A/B reale (L01 | L02 t/s):**

| braccio | config | L01 | L02 |
|---|---|---|---|
| B6-off2 | spec 4, min_p 0,5 | 61,4 | 52,9 |
| B6-off3 | idem | 57,2 | 55,2 |
| B6-on1 | ADAPT, spec 5 (host disturbato: CPU 4,9 ms/layer-window) | 53,4 | 52,3 |
| B6-on2 | ADAPT, spec 5 | 54,7 | 55,8 |
| B6-on3 | ADAPT, spec 5 | 62,4 | 56,2 |
| B6-ad5a | ADAPT, spec 5, costo a tabella (b6-1) | 61,8 | 55,0 |
| B6-d5b | spec 5, min_p 0,5 | 61,0 | 54,1 |
| B6-p65s4a / p70s4a | spec 4, min_p 0,65 / 0,70 | 58,6 / 59,4 | 54,5 / 53,3 |
| B6-p65s5a / p70s5a | spec 5, min_p 0,65 / 0,70 | 57,4 / 54,0 | 52,3 / 54,1 |

ON senza on1 fa in media 57,7, OFF 56,7: +1,7 %. È coerente con il replay, ma dentro il rumore di ±5 %
(contesa CPU degli altri agenti). Testo: L01/L02 normali in tutti i bracci, senza loop; il rapporto
distinte/totali con il tokenizer `\w+` è 0,39–0,46, come S-ref1 (0,37–0,38).

**Verdetto.** `STRATA_SPEC_ADAPT` resta opt-in, default off: vale circa +1 %. Il default 0,5 è giusto;
0,65/0,70 peggiorano. Per gli 80 t/s le leve sono altrove: il costo per riga (6,5 ms contro ~1,5 ms di
banda), la base fissa da ~17 ms per finestra (pipeline delle due schede) e un predittore di accettazione
più ricco della sola p del drafter (tetto +12–16 %).

Commit su `lab/b6-draft` (non pushati): dfd9f6e, bc9f881.

## Costo per riga della verifica: profilo (solo log esistenti, nessuna corsa)

- Regressione su 30 richieste a due schede: verify = 14,95 + 6,52·T ms. Stadio 3060 (layer 0-15): GPU
  5,45 + 2,05·T, host 0,79·T. Stadio 2080 Ti (layer 16-47): GPU 10,17 + 1,66·T, host 1,58·T. Per riga:
  ~3,7 ms GPU (la 3060 costa 2,5 volte di più per layer), ~2,4 ms di host (esperti su CPU e piano),
  draft +0,25. Il commit vale 0,04 ms a T=1 e 1,1 ms fissi per ogni T ≥ 2.
- Per kernel (unico profilo in grafo esistente: C-prof, split 32, pendenza L01-L02, ±0,25 per voce;
  6,7 ms/riga di GPU):
  - proiezioni dense ~2,5 (BF16 hc/router 0,95, mmvq Q6_K/IQ4_XS/Q4_K/IQ3_S 1,55);
  - esperti in VRAM ~1,7 (pavimento di banda ~1,2: 10 esperti × 1,24 MB × 48 layer);
  - attese sull'host ~0,9; QSA (indicizzatore e attenzione su 131k) ~0,85; head ~0,4.
- Pesi densi: ~67 MiB per layer (hc BF16 25, Q6_K 17, IQ4_XS 7, Q4_K 5,5). Una colonna in più dovrebbe
  costare solo calcolo (~0,05 ms in tutto), invece ne costa ~2,5. Causa probabile: il layout EXACT
  multi-colonna (ROWS=1, 4 warp). Ogni colonna ricarica le sue attivazioni per ogni blocco di pesi e il
  carico dei pesi non è pipelinato.
- Proposta (`STRATA_B6_MMVQ_ROWS`, opt-in): 2-4 righe d'uscita per gruppo di warp, attivazione riusata
  in registro, prefetch dei pesi. Stesso ordine di accumulo, quindi bit per bit uguale a ncols=1.
  Atteso: da −1,0 a −1,5 ms per riga, da −1,3 a −2,0 ms per finestra (+4–6 %). Da confermare con una
  corsa del profilo per T (3c3ceb5, `build-b6-3`) o con un micro-bench mmvq, quando il coordinatore lo
  autorizza.

## Micro-bench MMVQ multi-colonna (6 ottobre, notte; solo GPU, `b6_mmvq_bench`, commit 065566a)

- `STRATA_B6_MMVQ_ROWS=1` (Q4_K, Q5_K, Q6_K, IQ4_XS): attivazioni caricate una volta per blocco di pesi e
  riusate fra le 2 righe del blocco, scale Q6_K in registro. Il confronto memcmp è identico in tutto:
  15 casi × ncols 1, 2, 3, 4, 5, 8 × 2080 Ti e 3060.
- Per riga, sui tensori densi grandi del modello (qkv, gate, ssm_out, attn_q, attn_output, head):
  - default: 0,54 ms (3060) + 0,98 ms (2080 Ti);
  - B6: 0,28 + 0,26 ms.
  - Differenza: circa −0,95 ms per riga, −1,2 ms per finestra a T 2,3 (+3,5 % atteso).
- 4 righe vincono solo sulla 2080 Ti a T ≥ 4; 8 righe peggiorano ovunque.
- Restano fuori: IQ3_S, IQ4_NL, router BF16, matrici piccole dello shared expert (1–2 µs per colonna),
  i kernel hc BF16 (~0,9 ms/riga) e il percorso host degli esperti su CPU (~2,4 ms/riga).
- Eseguibile `20261004_routed_keep\build-b6-4`: l'A/B sul banco deterministico lo lancia il coordinatore.

## Lettura hyper-connection BF16 (7 ottobre, notte)

- `b6_gr_bench` (commit 491dae2): lettura hc come nel motore (variante staged, apply e inject), T = 1–6,
  mediana di 500 chiamate, pesi su 8 copie. Default a T=4: 82,4 us sulla 2080 Ti e 107,5 sulla 3060,
  contro 59,6 e 76,8 a T=1, cioè ~6–8 us per token in più. La up pesa più della down.
- `STRATA_B6_HC=1` (commit d16a823): nella proiezione up le fette di lo stanno in registro per tutte le
  righe del warp, le T somme diventano un'unica farfalla trasposta e i pesi della riga successiva si
  caricano in anticipo.
  - Hash identici a quelli del default per ogni T e su entrambe le schede.
  - Up a T=4: 32,6 → 22,7 us (2080 Ti), 48,1 → 38,9 us (3060). Lettura intera: 82,4 → 73,0 e
    107,5 → 98,3 us.
- Tentativo down a 2 righe per warp (`STRATA_B6_HC=2`): bit per bit uguale, ma più lento sulla 2080 Ti
  (down a T=4 da 28,3 a 36,9 us) e solo pari sulla 3060 fino a T=4. Scartato: non committato, patch in
  `patch/b6_hc_down_2righe_scartata.patch`.
- A/B deterministico (`det_b6h.sh`, `build-b6-5` = main be4cf1c + d16a823, 3 coppie alternate):
  - L01: +6,7 / +0,4 / +0,6 %; L02: +0,3 / +0,8 / +0,6 %; somma media +1,5 %.
  - Il +6,7 della coppia 1 viene da off1 lento (15,51 s contro 14,5–14,6 degli altri off).
  - Finestre identiche in tutte le corse. **NON PASSA** (soglia 2,7 %): resta opt-in.
- Head Q5_K a 4 righe sulla 2080 Ti: guadagna solo da T ≥ 4 (−0,065 ms a T=4). Con il mix di finestre
  del banco (28 % a T=4 in L01, 16 % in L02) vale circa −0,02 ms per finestra, lo 0,07 %. Non vale una
  regola per tipo.

## Profilo della base be4cf1c (pipeline + elastica + MMVQ; 7 ottobre notte, una corsa DET-b6p-prof)

- Il profilatore aggiunge l'11 % (31,1 contro 28,0 ms/finestra in L01); i ms qui sotto sono profilati.
  Traccia degli eventi: `b6p/pl_trace.txt`.
- Finestra fresca (68 %, 33,9 ms):
  - 3,0 ms di catena MTP prima dello stadio 0 (2,5 ms a T=1, 3,7 a T=4);
  - stadio 0 (3060): 10,8;
  - passaggio fra gli stadi: 1,2;
  - stadio 1 (2080 Ti): 18,8.
- Finestra speculativa sul percorso (32 %, 25,0 ms): 1,6 ms dal verdetto al lancio dello stadio 1,
  poi lo stadio 1 dura 23,2 ms.
- A parità di T lo stadio 1 dura 3–5,7 ms in più nelle finestre speculative (T=1 15,0 → 18,0;
  T=4 24,1 → 29,8): con ogni probabilità è la catena MTP sulla stessa 2080 Ti.
- I rollback costano al massimo 0,35 ms/finestra.
- Stadio 1 a T=1 (15,8 ms): letture hc 3,5 ms (la voce fissa più grande), VRAM hits 2,26, attese
  host/CPU 1,9.
- Proposta ordinata, in ms/finestra su L01:
  1. Priorità degli stream (catena bassa, stadio 1 alta) o drafter sulla 3060: −0,9 / −1,3.
  2. Lettura hc senza il kernel norm, bit per bit: −0,6 / −0,9.
  3. Lancio dello stadio 1 prima del lavoro host del verdetto e passaggio fra stadi più rapido:
     −0,4 / −0,7.
  4. Catena fresca più corta: −0,5 / −1,0.
  5. Dimensione della finestra che tenga conto della pipeline: +10 punti di percorso valgono −0,7.
  6. Attese CPU dentro gli stadi: −0,5 / −1.
  7. Residuo dei rollback: −0,35.

## Riepilogo della notte 6–7 ottobre (B6)

Commit su `lab/b6-draft` (worktree `Strata-wt\b6`, nessun push), sopra main be4cf1c:

| commit | cosa | esito |
|---|---|---|
| 065566a (→ main 542dd41) | MMVQ multi-colonna, attivazioni riusate fra le righe | **PASSA** +3,7 % (3/3), di default in main be4cf1c |
| 491dae2 | micro-bench `b6_gr_bench` della lettura hc | strumento |
| d16a823 | `STRATA_B6_HC=1`: up hc con lo in registro e somme trasposte | bit per bit; DET +1,5 % (reale ~0,6), **non passa**, opt-in |
| bc30da7 | `STRATA_B6_S1_PRIO`, `STRATA_B6_EARLY_S1` | pre-screen peggiore, opt-in spenti |
| 80d1b1a | `STRATA_B6_EARLY_S1=2` (solo lancio al verdetto) | pre-screen peggiore (L01 −2,7 %) |

Tentativi scartati, non committati (patch in `patch/`):
- down hc a 2 righe per warp: bit per bit, ma più lento sulla 2080 Ti;
- norm hc dentro la down (`b6_hc_norm_nel_down_scartata.patch`): bit per bit (hash uguali su
  T = 1–6 e su entrambe le schede), ma più lento.
  - 2080 Ti: lettura a T=1 da 59,5 a 65,5 us, a T=4 da 81,9 a 94,2.
  - 3060: a T=4 da 107,8 a 113,7.
  - Lo stamp "norm" resta ~7,7 us anche senza il kernel norm: è il costo di lancio/stamp, non il calcolo.
    Ricalcolare le somme di quadrati in ogni blocco e lo staging sincrono costano di più.

Pipeline (profilo DET-b6p-prof):
- Il percorso critico è lo stadio 1 (2080 Ti) in tutte le finestre, più la catena MTP davanti allo
  stadio 0 nelle finestre fresche.
- Nelle finestre speculative lo stadio 1 dura ~4 ms in più. Le priorità degli stream non lo cambiano,
  quindi non è contesa GPU con la catena. Causa probabile: il thread host unico che serve entrambi gli
  stadi e il pool CPU degli esperti condiviso (attese waitA/waitCPU dello stadio 1).

### Proposta (solo progetto): un thread host per stadio

Oggi un solo ciclo (il thread principale) chiama in sequenza `pump0` (verifier dello stadio 0) e
`V1(A).service` (stadio 1). Ogni `Verifier::service` pubblica i piani per layer e chiama
`drive_pool_split`, che esegue gli esperti CPU del layer sul pool. Uno stadio aspetta quindi che l'host
finisca il layer dell'altro, e il pool CPU è condiviso.

Disegno:
1. **Thread di servizio per stadio**, vivo quanto la richiesta (come il thread dell'adapt asincrono).
   Possiede i `PV[st][0..1]` del suo stadio e cicla `service()` → `done()` → `pl_finish()`. Pubblica
   `finished`/`s1_done` in atomici per finestra. Il ciclo principale non chiama più `service` e tiene
   solo le decisioni (catena, verdetti, lanci, commit, rollback). Lanci e commit restano sul thread
   principale, perché toccano lo stato condiviso (snapshot GDN, ple_prev, A/B/D).
2. **`drive_pool_split` rientrante.** Oggi scrive nei campi del `Drive` condiviso (`plan`,
   `cache_base`, `cache_slot_off`, `pcie_num`): ci vuole una copia di `Drive` per stadio, oppure i
   campi passati per argomento. Contatori e statistiche (`ms_*`, `cache_hits`, `usage` per l'adapt) per
   stadio, sommati a fine richiesta.
3. **Pool CPU (area dell'agente CPU: `src/kernels/cpu/pool.cpp` e `service()`).** Due chiamanti
   concorrenti hanno bisogno di una coda con priorità: un job dello stadio 1 passa davanti a quelli
   dello stadio 0 quando lo stadio 1 è sul percorso critico (sempre, nelle finestre speculative).
   In alternativa, partizionare i worker (per esempio 5 allo stadio 1 e 2 allo stadio 0). Da decidere
   con l'agente CPU, che ci lavora già: io non tocco quei file.
4. **Gli invarianti di `pl_drain`** (nulla in volo fuori dal ciclo) diventano «i thread di servizio
   hanno svuotato le loro code». Il watchdog (#267) e `release_gpu_waits` vanno chiamati da tutti i
   thread.
5. **Guadagno atteso.** Fino a ~4 ms sulle finestre speculative (32 %) se l'inflazione è tutta attesa
   host, cioè −1,3 ms/finestra. Più qualcosa sulle fresche, dove le attese CPU degli stadi (waitA/waitCPU
   ~1–2 ms) si sovrappongono meglio. Verifica prima di scrivere codice: con la traccia di pipeline e
   `STRATA_VERIFY_PROFILE`, confrontare waitA/waitCPU dello stadio 1 fra finestre speculative e fresche
   (oggi il profilo non le separa per classe: è un'aggiunta di poche righe).
