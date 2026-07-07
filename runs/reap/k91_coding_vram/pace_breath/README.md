# PACE breath battery (2026-07-07) — le 4 domande aperte, task grande

> Domande utente: (Q1) quanto corto può essere il warmup PACE? (Q2) possiamo prevedere la
> deriva prima che sporchi il codice? (Q3) allargare la finestra di respiro recupera qualità?
> quanto grande? (Q4) nel respiro devo tornare a K0/full o basta K50? Pod 3090, ds4+PACE
> (0014e), cache-1024, task = sito web GRANDE (che degenera), n≈300/arm, DS4_PACE_LOG.
> **Chiave: guardo t/s E rep-rate (coerenza), non solo velocità.**

## Tabella completa (throughput + coerenza)

| arm | cosa varia | t/s | hit | **rep-rate** | note |
|---|---|---:|---:|---:|---|
| default | warmup150, breath→keep64, len80 | 6.27 | 0.80 | 0.311 | baseline |
| warm20 | warmup **20** | 6.37 | 0.81 | **0.673** | degenera peggio |
| warm40 | warmup **40** | 5.92 | 0.79 | **0.524** | degenera |
| breathK50 | breath→**keep128** | **6.99** | 0.825 | 0.488 | + veloce, sporco |
| breathK0 | breath→**keep256 (full)** | 5.93 | 0.79 | **0.163** | + pulito |
| blen160 | finestra respiro **160** | 5.45 | 0.77 | 0.197 | pulito, lento |
| blen40 | finestra respiro **40** | 3.88 | 0.78 | 0.219 | pulito, molto lento (6 respiri) |

*(rep-rate = frazione 4-gram ripetuti; più basso = più coerente. full di riferimento ≈ 0.03.)*

## Risposte alle 4 domande

**Q1 — warmup corto? NO sul task grande (opposto del task piccolo).**
Monotono e netto: warmup 150 → rep **0.311**, warmup 40 → **0.524**, warmup 20 → **0.673**.
Meno warmup = più degenerazione. Sul task PICCOLO il pavimento era ~40 tok (directwarmup); sul
task GRANDE 40 non basta più — serve il warmup lungo. **Il pavimento di warmup scala con la
complessità del task**, non è una costante. (t/s quasi invariato: 5.9–6.4 → il warmup non paga
in velocità qui, solo in qualità.)

**Q2 — prevedere la deriva? PARZIALMENTE: sì per il collasso finale, no per i loop transitori.**
Due segnali, due comportamenti (dal pacelog + s1_default.csv):
- **n-gram (detector attuale) = REATTIVO.** Fira DOPO che il loop è partito: sale 0.075→0.35 in
  ~90 tok, poi il breath. Lead-time pratico ~40-90 tok, ma solo una volta che la ripetizione è già
  visibile. Soglia più bassa (0.15) firerebbe prima ma con falsi positivi sul CSS legittimo.
- **S1 (massa-controfattuale) = LENTO ma ANTICIPA il collasso grosso.** È cronicamente alto (~0.75
  da subito → NON distingue i respiri di routine: S1_pre60 ai breath 457/937/1417/1897 = 0.73-0.76,
  = baseline). MA **deriva verso l'alto nell'ultimo terzo**: 0.73→0.79→**0.84**, e prima del breath
  fatale @2308 (quello che poi esplode a ngram 0.92) S1_pre60=**0.814** vs 0.73 di base. Cioè S1 dà
  **~200-300 tok di preavviso sul collasso catastrofico**, non sui loop transitori.
- **Smoking gun causale:** a tok 2217 PACE stringe a **keep-28** *mentre S1 stava già salendo a 0.81*
  → 90 tok dopo esplode il loop. Il controller ha stretto DENTRO un segnale di distress crescente
  **che non stava guardando** (la legge di tighten legge selection-hit ~1.0, non S1). **Fix
  proposto: gate del tighten sulla PENDENZA di S1** — non stringere quando S1 sale. Questo è il
  preavviso che chiedevi: guarda la *pendenza* di S1, non il valore assoluto.

**Q3 — allargare la finestra recupera qualità? SÌ, ma costa velocità (e 80 è un minimo-di-qualità).**
Sorprendente e non-monotono: blen40 rep 0.219, blen80 (default) **0.311**, blen160 **0.197**.
Sia stringere (40) sia allargare (160) la finestra MIGLIORA la coerenza rispetto a 80 — ma
entrambi rallentano (blen40 a 3.88 t/s per respiri più frequenti; blen160 a 5.45). Il default-80
è un punto **veloce ma peggiore in coerenza**. Allargare a 160 dà la miglior qualità/velocità del
gruppo-finestra. **Non c'è pasto gratis: coerenza e velocità si scambiano.**

**Q4 — tornare a K0/full o basta K50? Torna a FULL per la qualità; K50 solo per la velocità.**
breath→full(256) rep **0.163** = il più pulito di tutta la batteria, a costo modesto (5.93 vs
6.27 t/s). breath→keep128 è il più VELOCE (6.99) ma sporco (0.488). Quindi:
**respiro profondo (a full) = recupero di qualità reale; respiro a metà (K50/128) = veloce ma non
recupera.** La tua intuizione "basta tornare a K50" → sì per la velocità, no per la coerenza.

## Verdetto unificante
Su TUTTE le manopole (warmup, profondità respiro, larghezza respiro) c'è **un solo asse di
scambio: apri di più → testo più pulito → più lento.** Il respiro FUNZIONA (breath→full 0.163 vs
default 0.311 dimezza la ripetizione) ma **il recupero costa throughput** e **nessuna config torna
pulita come il full** (0.163 vs 0.03): il respiro *attenua e ritarda* la degenerazione, non la
elimina — coerente col finding "il contesto avvelenato domina il greedy" ([[reap-k91-coding-vram]]).
Config consigliata per qualità-a-parità-di-velocità: **warmup lungo + breath→full + finestra ~160**.

⚠️ Caveat: n=1/arm, greedy CUDA non-deterministico, 1 task (sito grande con ripetizione CSS
legittima che alza il rep-rate di base). Il punto breathK50=0.488 è probabilmente rumore (rompe la
monotonia 64→128→256). Da replicare prima di fissare i numeri; il TREND (warmup↔qualità,
apertura↔qualità, velocità↔qualità) è robusto su 7 run.
