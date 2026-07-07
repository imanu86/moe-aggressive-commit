# Ginocchio keep-K con eval funzionale GRADUATO L0-L3 (2026-07-07) — batch SPEX

> Mandato SPEX: repeat-rate/ppl NON distinguono "sito col bottone rotto" da "pagina che non
> si apre". Servono task che PRODUCONO UN DELIVERABLE, valutati con una SCALA funzionale
> automatica. Suite: FRONTPAGE (HTML: nav+hero+bottone-cablato+form) · PYTHON (merge_intervals,
> unit test) · JSON (estrazione schema). Livelli: **L0**=non parse/non apre · **L1**=apre ma
> feature rotta · **L2**=feature presenti, difetti minori · **L3**=pieno e pulito.
> Pod 3090, ds4+reap, mask STATICA da tok0, cache-1024, stream separati (stdout=testo pulito),
> auto-gate aderenza (selezioni⊆keep, pruned=0). n=1/config (greedy deterministico).

## Risultato #1: IL GINOCCHIO SCALA CON LA LARGHEZZA DEL TASK

Mask **cold-static** (salienza coding-corpus, applicata da tok0). K = esperti tenuti/layer (su 256).

| task | full | keep-32 | keep-28 | keep-23 | keep-20 | keep-16 | keep-12 | **ginocchio** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **JSON** (estrazione) | L3 | L3 | L3 | L3 | **L3** | L0 | L0 | **keep-20** (7.8%) |
| **PYTHON** (funzione) | L3 | **L3** | L0 | L0 | L0 | L0 | L0 | **keep-32** (12.5%) |
| **FRONTPAGE** (pagina) | L3 | L0 | L0 | L0 | L0 | L0 | L0 | **>32 (nessuno regge)** |

**Il K più basso che resta funzionale scala con la complessità del task:**
- **JSON** (output stretto, 4 campi): regge fino a **keep-20** — estrae ESATTO (L3) col 7.8% degli esperti.
- **PYTHON** (funzione, logica): regge a **keep-32**, passa TUTTI gli unit test; a keep-28 si rompe.
- **FRONTPAGE** (HTML+CSS+JS interattivo): **collassa a OGNI K testato** (anche keep-32 → L0, loop
  rep 0.87-0.99). Troppo largo per una mask a freddo.

Questo è ciò che l'eval graduato doveva mostrare e la ppl non poteva: **la potatura tollerabile
non è una costante — è una funzione della larghezza del dominio del task.** Numero difendibile per
il paper: *"a keep-20 l'estrazione JSON è esatta; a keep-32 la funzione Python gira; la pagina
completa si rompe a qualunque potatura statica a freddo."* Il controllo **random** collassa ovunque
(random keep-23 → L0 su tutti i task) → conta il RANKING di salienza, non solo il numero.

## Risultato #2: il SESSION-LEARNING riscatta il task largo (pavimento del learn ≈ W=50)

Il frontpage cold-static collassa a ogni K. Ma se osservi **W token wide in-sessione** poi congeli
la mask session-learned keep-23 (rank per massa-gate), il quadro cambia (dettaglio in `../warmup/`):

| W warmup | livello frontpage | note |
|---:|:-:|---|
| 30 | L1 | troppo poca osservazione → bottone non cablato |
| **50** | **L3** | pagina completa e cablata ✅ |
| 80 | L2 | funziona, ma restart del documento |
| 110 | L2 | funziona, restart |
| **130** | **L3** | pulito ✅ |
| 150 | L1 | degrada |

**Cold-static keep-23 = uniforme L0 (loop). Session-learned keep-23 = L2-L3 da W≥50.** Il
working-set osservato in-sessione è ciò che serve alla mask: ~50 token di osservazione bastano a
riscattare un task che a freddo era irrecuperabile. Pavimento del learn ≈ **W=50** su questo task.
(Non monotono oltre: W=150 ricade a L1 — freeze-point sensibile, n=1 greedy.)

## Velocità (cache-1024, generation t/s aggregato)
Le mask entrano in cache → **6-24 t/s vs full 2.5-3.5 t/s** (3-8×). Il livello funzionale è
indipendente dalla cache; il t/s qui è pod-generoso (su 12GB reali sarebbe più basso, vedi
`../` streaming-analysis: le miss colpiscono l'SSD non la RAM).

## Rigore & caveat
Stream separati (fix del bug 2>&1 che intrecciava le diagnostiche ds4: nel testo); grader
fence-robusto (sceglie il doc più completo, cap L2 se restart); aderenza 0.000 su tutte le mask
(nessuna inerte); random control a più K; greedy deterministico (n=1 = risposta deterministica,
non campione). Caveat: 1 prompt/task, 1 pod, mask cold da coding-corpus (out-of-session per
frontpage). Artefatti: `out_clean/` (frontpage), `out_python/`, `out_json/`, `masks/`,
`../warmup/` (session-learned). Tool: `scripts/{functional_grade,knee_aggregate,make_keepK_mask,
build_session_mask}.py`.
