# moe-aggressive-commit

Studio + prototipo di una policy di inferenza MoE: **commit aggressivo per-sessione**.

> Osservo le attivazioni degli expert in una finestra di **warm-up**, stimo il **working set** del
> task, e **committo** su quel sottoinsieme tenendolo in VRAM — trattando il resto come
> evictabile / offloadato in RAM / quantizzato. Per workload ad **alta località** baratto un filo
> di accuratezza per molto meno footprint VRAM, e **misuro esattamente il cambio**.

**Stato 2026-07-10: repo storico/dati — punto d'ingresso [HANDOFF.md](HANDOFF.md); il lavoro vivo è nel repo [reap-loop](https://github.com/imanu86/reap-loop).** Vedi
[`docs/00_architecture.md`](docs/00_architecture.md) per il disegno storico completo.

## Domanda decisiva
Per un task ad alta località, esiste una regione in cui taglio gran parte degli expert dalla VRAM
perdendo **< 2 % di accuratezza su TUTTE le lunghezze di contesto testate**? E come scala col grado
di sparsità del modello?

## I quattro assi dell'esperimento
| Asse | Simbolo | Valori |
|---|---|---|
| Aggressività commit | `K` | 100 / 50 / 25 / 12 / 6 % degli expert residenti |
| Sparsità (strutturale + concentrazione empirica) | `s`, `N_eff` | ≥ 2 modelli + sweep top-k within-model |
| Lunghezza di contesto | `ctx` | 1k / 4k / 16k / 64k / max |
| Gestione miss | `miss_mode` | `fetch-lossless` / `precision-cascade` / `hard-drop` |

## Le tre policy
- **`FULL`** — nessuna eviction (ground truth di accuratezza).
- **`COARSE`** — top-K expert più frequenti globalmente (baseline stile MoE-Infinity).
- **`AGGRESSIVE-COMMIT`** — working set per-sessione, committato; resto secondo `miss_mode`.

## Struttura
```
docs/        architettura, positioning, modelli, rischi
configs/     modelli · policy · griglia (YAML)
src/msc/     instrument · workingset · policies · residency · validator · experiment · report
scripts/     pipeline a 4 passi (warmup → estimate → grid → report)
tests/       gate di determinismo del validatore
```

## Pipeline
```bash
python scripts/01_warmup_trace.py      --config configs/grid/sweep.yaml
python scripts/02_estimate_workingset.py --trace runs/<id>/trace.jsonl
python scripts/03_run_grid.py          --config configs/grid/sweep.yaml
python scripts/04_make_report.py       --runs runs/
```

## Deliverable
Una **famiglia di curve** (accuratezza vs VRAM/K, una linea per ctx, per modello) + un grafico
riassuntivo "guadagno VRAM a iso-accuratezza vs sparsità". Vedi `docs/00_architecture.md` §10.
