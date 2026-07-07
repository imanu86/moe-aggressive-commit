# Direct-warmup sweep (2026-07-07) — la cella mancante: W corto + discesa DIRETTA a keep-23

> Domanda utente: warmup 30-40 tok a K0 poi DRITTO a keep-23 (saltando keep-64/40) — mai
> testata (avevo `corto+scala` e `lungo+direct`, non `corto+direct`). Pod 3090, reap-loop
> 0011 canonico (no v3-bug), cache-1024, sito web, n=700, mask di sessione imparata dai
> primi W token, UNA sola discesa. Metrica velocita': t/s aggregato; qualita': rep-rate
> (frazione 4-gram ripetuti) + ispezione testo.

## Due gradienti OPPOSTI → uno sweet-spot netto

| arm | t/s | hit | rep-rate | coerenza |
|---|---:|---:|---:|---|
| static-23 (mask D5 cross-sessione, tok0) | 21.37 | 0.986 | **0.537** | ❌ loop `fofa.fa-fw href=…` |
| dw30 (own-session, W=30) | 17.98 | 0.967 | **0.679** | ❌ loop `'bg-body','bg-body'…` |
| **dw40 (own-session, W=40)** | **12.72** | 0.925 | **0.065** | ✅ **CSS coerente** |
| dw60 (W=60) | 12.18 | 0.919 | 0.091 | ✅ |
| dw150 (W=150, = D7-direct) | 9.08 | 0.865 | 0.033 | ✅ |
| full | 3.74 | — | 0.032 | ✅ |

**VELOCITÀ: monotona, più corto = più veloce.** Confermata la teoria cache: le fasi larghe di
warmup avvelenano la cache-1024. W=30 → 18 t/s (quasi il soffitto statico 21.4); W=150 → 9 t/s.
La scala intermedia era pura tassa; il *direct* la elimina.

**COERENZA: soglia netta a W≈40.** Sotto (static tok0, W=30) il modello DEGENERA in loop; da
W=40 in su è pulito (rep 0.03-0.09). La mask imparata da troppo pochi token (o cross-sessione)
affama il modello degli expert giusti nell'apertura → loop; ~40 token di contesto in-sessione
bastano a stabilizzare prima di stringere.

### 🎯 Sweet-spot = **W=40 direct**: pulito E il più veloce tra i puliti (12.7 t/s = 3.4× full).
Risposta alla domanda: sì, si può accorciare molto il warmup **saltando la scala**, ma c'è un
pavimento a ~40 token sotto cui la coerenza crolla. 40 è il punto: metà della tassa di W=150
(9.1→12.7 t/s) a coerenza invariata.

## ⚠️ Correzione al PACE-pilot
Il PACE-pilot aveva dichiarato "static-24 cached-profile DOMINA 5.7×" guardando solo la velocità.
Qui la stessa config (`static-23`, mask cross-sessione da tok0) ha **rep-rate 0.537 = DEGENERA**:
era veloce ma INCOERENTE. Correzione: **il cached-profile cross-sessione da tok0 non basta — serve
~40 token di warmup IN-SESSIONE.** Rafforza il finding "working-set per-sessione" (D3): profili di
altre sessioni applicati a freddo collassano.

Caveat: n=1 per W (greedy CUDA non-deterministico); la soglia esatta (30 vs 40) va replicata, ma il
trend corto-degenera / ≥40-pulito è netto su 5 run. 1 workload (sito web). Artefatti: `gen_*.log`,
`*_render.html`, `tr_dw{30,40}.csv`.
