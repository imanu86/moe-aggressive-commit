# REAP-loop Tier A+B+C — sensore, attuatore runtime, recupero live

> Domanda (2026-07-06): il modello è CIECO alla potatura (bias solo in selezione, pesi
> rinormalizzati a 1.5 → nessun segnale d'errore interno). Un sistema ESTERNO può
> (A) vedere il distress, (0011) ruotare la mask a caldo, (B/C) recuperare la qualità?
> Pod: RTX 3090 24GB sm_86 (3080Ti/A5000 esauriti) — qui si misurano segnali e recupero
> (proprietà del modello), NON il fit 12GB (già chiuso nel README padre).

## Risultati in una tabella

| Test | Domanda | Esito |
|---|---|---|
| **A — sensore** | il distress si vede da fuori? | ✅ S1=0.86, S2 0.475-vs-0.269, detector ~30-80 tok, 0 falsi positivi |
| **E0 — scorciatoia** | riscrivere il FILE basta? | ❌ bias servito da cache HBM/UVA, file-write non propaga |
| **0011 — attuatore** | mask ruotabile a caldo? | ✅ v2 upsert: toggle = `mv mask.txt`, 0.00% violazioni |
| **B — recovery restart** | detect → K35 → redo? | ✅ 2° campione K35 quasi-pulito (degenera solo in coda, onset 85%) |
| **C1 — recovery LIVE** | switch a caldo salva la run? | ❌ **il contesto avvelenato vince** (meccanica ok, testo resta in loop) |
| **C2 — controprova** | K35 sano → K91 a caldo degrada? | ✅ degenerazione subito dopo lo switch → causalità provata |

## Tier A — sensore (run strumentate 800 tok, trace 0006)

- **S1 massa controfattuale = 0.86**: anche con la mask coding-OTTIMALE a K91, l'86% della
  massa di gate del modello full cade su expert potati → a K91 manca la **capacità**, non la
  selezione giusta. Cross-validato da E0 pre-toggle (84.2%) e C1 (87.0%): tre misure, stesso numero.
- **S2 periodicità routing** (Jaccard top-6 token consecutivi): K91 0.475 vs K0 0.269 →
  distingue sano/degenerato a runtime SENZA patch. In questo campione K91 è collassato dal
  token ~0 ("You started a chat..." in loop) → niente finestra pre-onset per provare l'anticipo.
- **S3 concentrazione pesi**: nullo (0.324 vs 0.330) — non discrimina, dichiarato.
- **Detector testuale** (4-gram ripetuto ≥3× in 60 parole): conferma in ~30-80 token, K0 CLEAN.
- Economia: sensore µs/token; attuazione 40×1KB H2D; ruotare 40 expert ≈ 100ms ≈ frazione di
  1 token in streaming → il monitoraggio è gratis rispetto al decode.

## E0 + Patch 0011 (attuatore)

- **E0**: bias-mask scritta nel gguf a processo vivo → selezioni INVARIATE (83.9% fuori keep
  = pre). Il router legge il bias da copia cachata, non dal file.
- **v1 fallita** (lezione): aggiornare i range HBM esistenti trova 0 range — con modello
  host-registered il bias è servito dal fallback UVA *senza entrare in `g_model_ranges`*.
- **v2 riuscita — upsert**: i range in `g_model_ranges` VINCONO sul fallback → la patch CREA
  un device-range da 1KB per ogni `exp_probs_b` con i valori mascherati e lo indicizza per
  offset; il router legge la nostra copia dal token dopo. + override del router CPU.
  `DS4_REAP_MASK_FILE` = righe `layer expert` (potati), mtime-poll per token.
  File: `patches/ds4/0011-reap-runtime-mask.patch` (v0: prefill non mascherato, dichiarato).
- Verifica: `40 device range aggiornati/creati`, **0.00% selezioni fuori keep** (17k+ sel).

## C1/C2 — il verdetto sul loop live

**C1 (K91 dal token 0 → detector fire al tok 106 → switch K35 a caldo, stesso processo, KV
intatto):** lo switch avviene (reload 9320→3600 entry, 40 range), le selezioni post-switch
rispettano keep35, MA il testo **continua identico il loop** `<head></html>` fino in fondo.
**Il contesto avvelenato domina**: ~100 token di spazzatura nel KV tengono il greedy
nell'attrattore ripetitivo anche con gli expert buoni disponibili.

**C2 (K35 sano per 154 tok → switch K91 a caldo):** fase 1 HTML pulito; subito dopo lo
switch degenera (`--bg: url) */* */` in loop). Aderenza keep-set **0.00% in entrambe le fasi**
(35.5k sel ⊆ keep35; 58.3k ⊆ keep91). → la mask live AGISCE sulla generazione: il
non-recupero di C1 è colpa del contesto, non dell'attuatore.

## Conclusione di design (misurata, non ipotizzata)

Il REAP-loop "detect → allarga K" così com'è NON basta: serve **(a)** detect prima che
l'attrattore si formi, **oppure (b) rewind** dei token degeneri allo switch (il restart di
Tier B è il rewind estremo, e funziona). Sensore ✅ e attuatore ✅ ora esistono e sono
misurati; il pezzo mancante del loop è la politica di rewind/timing.

## D3/D4 — la manopola intelligente (stessa data, secondo giro)

**D3 (analisi locale, gratis).** Copertura della massa di gate a keep-23 sulla gen sito:
statica media-condizionale **14.1%**, statica per-MASSA (12 prompt) **15.3%**, oracle
in-sample **71.3%**, **mask di SESSIONE dai primi 100/150/300 tok: 55/62/66%** (a keep-64:
74/79/83%). → il working-set a K91 e' **per-sessione** e si impara online in ~150 token.

**D4a (pod 3090) — discesa a scalini con session-mask: FUNZIONA.**
K0 fino a tok 151 → session keep-64 → tok 309 keep-40 → tok 462 **keep-23 (K91)** → fine 700.
Detector **CLEAN su tutto**, codice CSS/HTML valido anche nella fase keep-23 e in coda.
Aderenza keep-set 0.05/0.00/0.08% per fase. hit_rate finale 0.79, 4.46 t/s aggregate.

**D4b (controllo statico) — CORREZIONE ONESTA del verdetto fase-1.**
La statica K91 **per-MASSA** dal token 0 resta **CLEAN a 700 token** (CSS valido, hit 0.57,
2.44 t/s) — mentre la K91 media-condizionale collassava in ~40 token. Quindi:
- il collasso di K91 in fase 1 era in gran parte **colpa del criterio di ranking**
  (media condizionale = specialisti rari, zero cavalli-da-tiro), non della sola capacita';
- la copertura di massa (15%) NON predice il collasso: per la fluidita' contano i workhorses;
- la **session-mask resta superiore in efficienza** (hit 0.79 vs 0.57, 4.46 vs 2.44 t/s)
  e in copertura (62% vs 15%), ma la coerenza a K91 e' raggiungibile anche in statico
  col ranking giusto. Caveat: 700 tok di CSS coerente ≠ sito completo con JS funzionante
  (per il verdetto pieno serve una gen 2600 tok + render, non fatta qui).

**Risposte alle domande di design:**
1. *Scendere vs salire*: asimmetrico — scendere con contesto sano funziona (D4a);
   salire dopo il collasso no (C1, serve rewind).
2. *Ripulire l'allucinazione*: detector→taglio all'onset→resume largo (rewind coarse);
   con D4a/D4b la degenerazione si PREVIENE, il rewind resta rete di sicurezza.
3. *Resa a K alto*: due corsie misurate — statica per-massa (semplice, 2.4 t/s) e
   session-adaptive a scalini (piu' efficiente, 4.5 t/s, hit 0.79).

## Artefatti

`loop_signals.json` (analisi A), `loop_traces.tgz` (trace k91/k0), `c_traces.tgz` (trace
c1/c2), `gen_*.log` (tutte le generazioni), `analyze_loop_signals.py`, `b_run.log`/`c_run.log`
(orchestrazione), patch in `patches/ds4/0011-reap-runtime-mask.patch`.
Pod 3090 terminato + verificato; costi in `../meta.json`.

## POST-SCRIPTUM (secondo giro, v3): ritrattazioni e verdetti finali — TUTTI aderenza-verificati

**Bug cold-start scoperto e fixato (0011 v3)**: l'apply al token ~1 veniva soppiantato dai
range del model-load → mask silenziosamente OFF nei run cold (A1F 52% violazioni, D4b 85%).
v3 = re-apply ogni 32 token. REGOLA NUOVA: aderenza verificata su OGNI run mascherata.

| Verdetto finale | Dato (mask verificata) |
|---|---|
| Statica K91 (media O massa) sul coding | **collassa** (mass: onset 8%, hit 0.99) — "mass regge" RITRATTATO |
| Scala sessione HOT sul coding | regge 94%-100% (2 seed) |
| Stessa mask COLD sul coding | **degenera al 70%** (hit 0.96, 11.4 t/s) → **asimmetria di QUALITÀ reale**; quella di efficienza era artefatto |
| Segnali (north-star): K91-reuse cold | **pareggio col full a livello campo (0.70 vs 0.70)**; danno solo di formato |
| Head-to-head vs reattiva 2x VRAM | loop vince 3.7x (9.2 vs 2.5 t/s) |
| Sensori router (S2 lag 1-16) | morti (0% sopra soglia durante il loop) |
| Sensore S1 (0012) | deriva monotona reale 0.80→0.89, ma lenta: indicatore, non allarme |
| ppl keep-23: session/domain/random | 1.22× / 3.5-3.7× / **9.34×**; transfer stesso-output-type 1.19× |
