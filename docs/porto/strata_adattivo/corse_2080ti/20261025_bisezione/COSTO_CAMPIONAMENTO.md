# Costo del campionamento a T=0.7: da dove vengono i t/s persi (26/10/2026)

Stato: **analisi dei log esistenti fatta; corse di bisezione preparate, NON lanciate** (PC dell'owner in uso, nessuna GPU toccata). Compilato no, installato no, provato no: il sospetto sotto e' ricavato da log e sorgente, non da una misura che lo isoli.

## Conclusione

Il decode a T=0.7 (top_p 0.8, top_k 20, presence 1.5) e' ~10% sotto T=0 e **la perdita sta tutta nei ms per finestra** (+12%, circa +3,3 ms su ~29), **non nei token per finestra** (2,31 contro 2,31). Le bozze accettate calano di poco (-2,5 punti) senza che i token per finestra se ne accorgano.
Sospetto principale: la **presence penalty spegne la pipeline a due finestre** (le due schede non si sovrappongono piu'); il costo dei kernel di campionamento in se' e' trascurabile. Da confermare con la bisezione sotto.

## 1. Scomposizione sui log (engine.log, richiesta 0 di ogni avvio scartata)

Mediane per richiesta; D = Daily 0.1.43, B = 0.2.6 + pila + greedy-temp0. T=0: samp0_daily1/2, samp0_B. T=0.7: samp7_daily1/2, samp7_B, s7r_D1-4, s7r_B1-4. Riproducibile: `python camp_analisi.py storico ..\20261019_banco_comunita` (con `--senza-prima` scarta anche la prima richiesta da 4K, ancora fredda: 36-58 ms/finestra contro 28-33).

| cella | n T0 / T.7 | t/s T0 -> T.7 | token/finestra | ms/finestra | accettazione |
|---|---|---|---|---|---|
| 4K D | 6 / 18 | 73,3 -> 70,0 (-4,6%) | 2,349 -> 2,296 | 31,36 -> 33,04 | 0,664 -> 0,621 |
| 4K B | 3 / 15 | 82,0 -> 67,9 (-17%) | 2,415 -> 2,327 | 28,65 -> 32,07 | 0,699 -> 0,632 |
| 32K D | 6 / 18 | 73,5 -> 71,0 (-3,4%) | 2,226 -> 2,349 | 29,68 -> 32,49 | 0,637 -> 0,639 |
| 32K B | 3 / 15 | 78,3 -> 71,6 (-8,6%) | 2,286 -> 2,306 | 28,68 -> 31,65 | 0,680 -> 0,638 |
| 4K D, senza la prima fredda | 4 / 12 | 82,5 -> 71,7 (-13%) | 2,417 -> 2,276 | 29,52 -> 31,90 | 0,681 -> 0,619 |
| 4K B, senza la prima fredda | 2 / 10 | 83,7 -> 74,8 (-11%) | 2,382 -> 2,327 | 28,47 -> 31,30 | 0,700 -> 0,636 |

Tutte le celle insieme (D+B, 4K+32K, escluse richiesta 0 e prima da 4K; T=0 n=15, T=0.7 n=55; media ± errore standard):
- token/finestra 2,314 ± 0,028 -> 2,317 ± 0,016: **+0,1%** (z = 0,1)
- ms/finestra 29,5 -> 33,2: **+12,3%** (z = 5,9); sulle mediane 28,7 -> 32,0 (+11,6%)
- accettazione 0,663 -> 0,638: -2,5 punti (z = -2,3)
- t/s 78,5 -> 70,4: -10,4%

Scomposizione (log del rapporto): token/finestra +0,1 punti, ms/finestra -11,6 punti, totale -11,5. **Circa il 100% della perdita e' costo per finestra.**
Coerenza: i ms/finestra salgono del +8..+10% in tutte e quattro le celle (D e B, 4K e 32K) e le righe di ogni avvio a T=0.7 sono alte in modo uniforme; i token/finestra cambiano di segno da cella a cella (4K -2..-6%, 32K +1..+5%): rumore di richiesta (deviazione ~0,12 su n piccoli), non un effetto. Solo a 4K l'accettazione cala davvero (-6..-7 punti, e i token/finestra -4% con z = -2,5): possibile effetto secondario (bozze greedy contro bersaglio campionato, vedi sotto), ma a 32K non c'e'. D e B si comportano allo stesso modo: non e' un difetto della 0.2.6.

Prova diretta che a T=0.7 la pipeline salta: **11 avvii su 11 a T=0.7 hanno nell'engine.log la riga** `strata serve: --pipeline-windows: a request with repetition penalties (penalty_last_n) decodes serially`, **0 su 3 a T=0** (che invece annunciano `two verifiers per stage, 2 stages overlap across windows`).

## 2. Dove nel sorgente (fork `lab/upsync-026`, 5b2e9102)

1. **Presence penalty -> pipeline spenta (sospetto principale).** `serve/server.py:1403-1418` (`sampling_keys`): un `presence_penalty` diverso da 0 emette `penalty_present` e **sempre** `penalty_last_n=64`. In `src/program/generate.cpp:15147` `hist_n = min(penalty_last_n, 4096)` = 64, e a `generate.cpp:15566-15568` `pl_serial = hist_n > 0 ? "repetition penalties (penalty_last_n)"`: con `--pipeline-windows 2` la richiesta decodifica **in seriale** (riga di log sopra), cioe' scheda 0 (layer 0-15) poi scheda 1 (16-47) una dopo l'altra invece che sovrapposte. A T=0 la scheda del modello non si fonde (patch greedy-temp0, `server.py:5085-5087`) e la pipeline resta accesa.
2. **Campionamento fuori dal grafo, con sincronizzazione.** A T=0 l'argmax e' catturato nel grafo della finestra (`src/core/verify.cpp:2370-2378`, sp greedy) e non costa lanci in piu'. Con `temperature > 0` o storia di penalita', `Verifier::run` (`verify.cpp:3198-3240`) e `pl_finish` (`verify.cpp:4483-4492`) rilanciano **lato host, per ogni finestra** `sample_tokens` (`src/kernels/cuda/sampler.cu:1239`): `sampler_split_part_kernel` (61 blocchi x T righe) + `sampler_split_merge_kernel`, poi `cudaStreamSynchronize(cs_)`. top_k, top_p, temperatura e pescata (Philox, `sampled_tail_warp`) stanno tutti qui, su GPU, in una warp per riga; la penalita' e' una bitmap per blocco da 4096 logit piu' `history_count` di 64 elementi solo sui logit presenti (`sampler.cu:696-775`).
3. **Storia delle penalita' per ogni finestra.** `generate.cpp:16811-16820`: `penalty_rows` sull'host e `cudaMemcpy` sincrona di `T x 64` interi (<= 1 KB) prima di ogni finestra, solo se `hist_n > 0`.
4. **Bozze greedy.** Senza `STRATA_SPEC_COUPLED`/`STRATA_SPEC_PROB` (spenti) `mtp.set_draft_sampling` (`generate.cpp:15129`) non fa nulla: il drafter propone l'argmax e il bersaglio campiona, quindi l'accettazione puo' scendere (osservato -2,5 punti in media). Costo per finestra: nessuno.

Stima del contributo ai +3,3 ms/finestra (ragionamento, non misura): kernel di campionamento + lancio + sincronizzazione + copia della storia ~0,2-0,5 ms (sono ~4 MB di logit per finestra e una warp per riga: <1,5% di 30 ms); il resto, **>= 2,8 ms, e' compatibile con la sovrapposizione persa** tra le due schede. top_k, top_p e temperatura, da soli, pesano meno del rumore di misura.

## 3. Corse da fare (preparate, non lanciate)

Una variabile per volta, ogni variante tra due corse base (B-A-B: B = base T=0.7 completo, A = variante). Il corpo della richiesta porta solo i campi del braccio; un campo a 0 o 1.0 e' esplicito e **batte la scheda del modello** (`server.py:5085-5092`), che altrimenti rimetterebbe 0.8/20/1.5 sulle richieste con temperatura > 0.

| n | braccio | campi | cosa isola | esito atteso se il sospetto regge |
|---|---|---|---|---|
| 1,3,5,7,9 | base | T 0.7, top_p 0.8, top_k 20, presence 1.5 | riferimento d'uso | come i log sopra, riga "decodes serially" presente |
| 2 | nopp | come base, presence 0 | la penalita' (e la pipeline) | t/s ~ +8-10%, ms/finestra ~ -3 ms, **riga assente** |
| 4 | notopp | come base, top_p 1.0 | il taglio per massa | a pari della base (+-2%) |
| 6 | topk64 | come base, top_k 64 | la larghezza della lista (non esiste "off": 64 e' il massimo) | a pari o appena sotto la base |
| 8 | puro | T 0.7, top_p 1.0, top_k 20, presence 0 | solo temperatura + percorso campionato fuori dal grafo | vicino al T=0 (resta il costo di lancio+sync, ~1%) |
| 10 | t0 | temperature 0 | greedy, controllo | livelli del T=0 sopra |

Se `nopp` NON recupera: la causa non e' la pipeline ma il percorso campionato (punto 2): confrontare `puro` con `t0`; poi un profilo con `STRATA_TRACE`/`prof_on_` su una finestra campionata. Se `puro` recupera ma `nopp` no, pesa la combinazione top_p/temperatura nel kernel di coda.

File (tutti in questa cartella, copie dei runner T=0.7 dello scratchpad `...\3df9aedd-b31a-4188-90dd-ec5b5610cd14\scratchpad\community_bench_corto_t07.py` e `benchmark_t07.py`, con il blocco di campionamento letto da `CAMP_SAMPLING`):
- `camp_bisezione.py` (sequenza; senza `--vai` e' solo una prova a secco; rifiuta di partire se c'e' un strata.exe, un `pause` o un `bench.lock`)
- `community_bench_camp.py`, `benchmark_camp.py` (runner e banco; 4 richieste per contesto invece di 3, uscita in `camp_NN_<braccio>`)
- `camp_analisi.py` (`storico` per i log gia' fatti, `corse` per la bisezione: ogni variante contro i due base adiacenti, con la riga "serial")

Prima di lanciare: PC libero (l'owner non lo sta usando), nessun strata.exe (il runner a fine corsa fa `taskkill /F /IM strata.exe`), nessun `pause` in `D:\ds4_work\strata\lab_locks`, annotare Jump/OktoCGControl; priorita' normale.

```
python C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261025_bisezione\camp_bisezione.py --vai --solo nopp
```
(terna base-nopp-base, ~15 min, risponde alla domanda principale). Sequenza completa di 10 avvii (~50 min): stesso comando senza `--solo`. Analisi: `python camp_analisi.py corse <questa cartella>` (`--senza-prima` scarta la prima richiesta da 4K).
Motore predefinito B (0.2.6 + pila `build-up026pila-ffe66174`); `--motore D` usa la Daily 0.1.43.

## Risultati della bisezione

| braccio | t/s 4K | t/s 32K | ms/finestra | token/finestra | accettazione | "decodes serially" |
|---|---|---|---|---|---|---|
| da misurare | | | | | | |
