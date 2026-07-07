# PACE pilot (2026-07-07) — controller in-engine 0014, validazione convergenza

> Mandato SPEX-main: validare PACE sul cold-start/task-piccoli, NON solo a regime.
> Pod RTX 3090 24GB (poi terminato), ds4 `80ebbc3` + reap-loop 0001-0014e (repo pubblico
> github.com/imanu86/reap-loop). Pressione forzata: `--ssd-streaming-cache-experts 1024`
> (keep-24=960 exp ENTRA, keep-40=1600 NO → keep-K ha motivo di stringere). Prompt sito web,
> n=700, da COLD. t/s = aggregato (il sampler per-finestra ha misurato righe-CSV, non token — scartato).

## 🎯 Il punto #1 del mandato: la traiettoria keep-K SI MUOVE (validato)

DS4_PACE_LOG mostra la macchina a stati viva:
- **PACE-live**: WARMUP(150) → DESCENT keep-40 → BREATH(ngram) @tok323 keep-64 → relearn → keep-44.
- **PACE-fast**: WARMUP(40) → keep-40 → **TIGHTEN keep-32** @tok161 → BREATH @220 → relearn → 40 → BREATH(clock) @650.
I breath sono innescati dal detector n-gram in-memory (ngram 0.03→0.35→0.65). **keep-K, breath e
cadenza si muovono davvero** — la cosa mai osservata prima.

## Ma il verdetto sulla CONVERGENZA è negativo per il learn-live

| arm | t/s | hit | vs full | keep-K operativo |
|---|---:|---:|---:|---|
| full (no mask) | 3.36 | 0.586 | 1.0× | — |
| **static-24 (cached-profile)** | **19.26** | **0.987** | **5.7×** | 24 da tok 0 |
| PACE-live | 4.14 | 0.735 | 1.2× | 40↔64 (breathing) |
| PACE-fast-descent | 4.41 | 0.735 | 1.3× | 32→64 (breathing) |

**Perché PACE-live perde (5.7× vs 1.2×):**
1. **Non converge al regime veloce.** Su questo workload il testo ha CSS ripetitivo → il detector
   n-gram sale (0.35-0.65) → BREATH frequenti allargano keep-K a 64 → working-set 2560 > cache 1024
   → thrash → resta a hit 0.735. Non scende mai stabilmente a keep-24 (dove entrerebbe: hit 0.99).
2. **Tassa di warmup:** 150 tok a full prima di iniziare → sui task PICCOLI (~60 tok) PACE-live
   **non finisce nemmeno il warmup** → = full, zero beneficio. Per costruzione i task piccoli non
   beneficiano del learn-live.
3. **Il cached-profile è instantaneo e domina** — esattamente l'ipotesi del mandato: keep-24 da
   tok 0, nessun warmup, nessun breath, 19.3 t/s.

## Criteri pre-registrati → esito

| criterio | esito |
|---|---|
| keep-K SI MUOVE | ✅ SI (validato) |
| cached-profile ≈ istantaneo | ✅ SI (19.3 t/s da tok 0) |
| plateau in POCHI token (task piccoli) | ❌ NO per learn-live (warmup 150; il piccolo non converge) |
| PACE-live Pareto-domina static/full | ❌ NO — dominato da static-24 (4.1 vs 19.3) |
| tassa reattiva < guadagno | ❌ su questo workload i breath frequenti tengono keep-K largo → nessun guadagno |

## Conclusione (onesta, pilot n=1/workload)
**Il valore di REAP-LOOP NON è nell'imparare live — è nel spedire un profilo-dominio pre-appreso
e applicarlo dal token 0** (cached-profile, 5.7× istantaneo). PACE-learn-live, su un workload con
testo ripetitivo, entra in un loop detector→breath→thrash che gli impedisce di convergere al regime
veloce. Leve da tarare prima di rigettare il learn-live: (a) detector n-gram meno sensibile al
CSS ripetitivo legittimo; (b) far dominare la spinta hit-cache (non solo selection-hit) alla legge
di tighten così scende a keep-24; (c) breath più corti/rari. Ma l'edge pratico oggi = **cached-profile**.

Caveat: 1 workload (sito web, testo ripetitivo che stressa il detector), 1 pod 3090, pressione
cache-1024. Il beneficio massimo di PACE è sull'edge (12GB); qui era per iterare in fretta.
Artefatti: `gen_*.log`, `pacelog_{live,fast}.log` (traiettorie), `pace_pilot.tgz`.
