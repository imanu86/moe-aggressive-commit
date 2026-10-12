# Runbook locale — distillazione del layer MTP sulla workstation (una notte, 0 $)

Tutto gira sul PC dell'owner, con le due schede del Daily (3060 stadio 0 + 2080 Ti stadio 1), **a server Strata spento**,
sotto `D:\ds4_work\strata\lab_locks\bench.lock` (`lab_run.py`: O_EXCL, tetto di tempo, figli uccisi prima del padre).
I dati non lasciano mai il PC.  Numeri misurati il 12/10 (pilota: 300 + 63 sequenze, 1,03 M token).

## Tempi misurati e stima della notte

| Tappa | Misurato (pilota) | Stima corpus intero (1 197 sequenze, 3,5 M token) |
|---|---|---|
| Avvio del motore (pack, PLE, split, cache) | ~3 min per avvio | 3 min |
| Cattura dal prefill (`capture_driver.py`, due schede, config `strata-dueschede.json`) | **427 tok/s** stabili su 1,03 M token (42 min) | 2,5 M token restanti → **~1,6 h** (si riprende: `capture_map.json`) |
| Eval del drafter attuale sulla heldout (95 seq, 277 k token) | 100–135 s per eval | idem |
| Training (`train_mtp.py`, 2080 Ti fp16, celle attive a blocchi) | 268 seq / 750 k token: ~25 min per epoca + 2,2 min per eval | 1 132 seq / 3,3 M token: **~1,8 h per epoca** |
| Export + verifica d'identità | 0,2 min | 0,2 min |
| Bench sul motore (`bench_pack.py`, 24 prompt × 256 token, due pacchi) | ~15 min | 15 min |
| **Totale** | 1 h 25 min | **~4 h con 1 epoca, ~6 h con 2** |

Memoria: training 15,7 GiB sulla 2080 Ti con `--active-chunk 768` (senza blocchi una sequenza lunga superava i 22 GB).
Disco: cattura 20,6 KB/token → 72 GB per il corpus intero (`D:` ha 227 GB liberi); si può cancellare dopo l'export.

## Comandi (dalla cartella `mtp_distill`)

```bat
set M=C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\mtp_distill
set W=D:\ds4_work\mtp_distill
rem 1. cattura di tutto il corpus (riprende da capture_pilot: le 363 sequenze gia' fatte si saltano) — ~1,6 h
python %M%\lab_run.py --name mtp-capture-full --max-min 150 -- python %M%\capture_driver.py ^
  --exe C:\Users\imanu\source\repos\Strata-wt\mtp-capture\build-mtpcap\strata.exe ^
  --config D:\ds4_work\strata\Strata\strata-dueschede.json --env STRATA_VRAM_FREE=device ^
  --seqs %W%\seqs --out %W%\capture_pilot
rem 2. training 1 epoca (eval ogni 50 passi), poi export e bench — ~2,3 h
python %M%\lab_run.py --name mtp-train-full --max-min 200 -- python %M%\pilot_local.py --work %W% --tag pilot ^
  --from train --epochs 1 --eval-every 50 --eval-items 120 --train-extra "--step-weights 1,0.8,0.6,0.5"
rem 3. bench sul motore, pacco attuale contro il nuovo (greedy, stessi prompt heldout per conversazione)
cd %W%\work\bench && python %M%\lab_run.py --name mtp-bench --max-min 45 -- python %M%\bench_pack.py ^
  --exe C:\Users\imanu\source\repos\Strata-wt\mtp-capture\build-mtpcap\strata.exe ^
  --config D:\ds4_work\strata\Strata\strata-dueschede.json --env STRATA_VRAM_FREE=device --seqs %W%\seqs --by-conv 10 ^
  --mtp D:\ds4_work\strata\Strata-data\mtp\rt_it48k --mtp %W%\runs\pilot_ft1\rt_pilot --n 24 --prompt-tokens 1024 --max-new 256
```

Una sola invocazione di `lab_run.py` tiene il lock per tutta la tappa; fra una tappa e l'altra il banco è libero.
`pilot_local.py --from capture` fa tutto in sequenza (cattura → eval → train → export) sotto un solo lock (`--max-min 400`).

## Cosa guardare

- `eval iniziale` / `final` in `runs\pilot_ft1\eval.json`: per passo `acc` (greedy), `offered` (p ≥ 0,5), `acc_offered`
  (quel che il motore accetta davvero con `--spec-min-p 0.5`), `sampled.think/nothink` (accettazione attesa dello
  speculative sampling con T=1,0/top_p 0,95/top_k 20 e T=0,7/top_p 0,8), `chain_len_mean`.
- `bench_pilot.json`: `acceptance`, `tokens_per_window`, `decode_tps` per pacco; le uscite greedy devono coincidere.
- Il pacco nuovo si carica col motore invariato: `--mtp <cartella>` (stesso layout di `rt_it48k`).  La release la fa l'owner.

## Seconda fase (on-policy, 0 $)

L'hook di cattura vale anche per il decode: registrare nel serve le righe accettate (R e top-20 del target sui token
che il modello genera davvero) accumula dati on-policy durante l'uso normale, senza GPU in più; il training resta
locale (token grezzi, non bonificati).  Non ancora scritto: è il passo dopo, se il primo giro paga.

## Pod (alternativa)

`RUNBOOK_POD.md` resta valido con due correzioni: A100 80 GB (sm_80 nella lista standard, 1,59 $/h) invece di H100, e la
cattura dal prefill (12–30 min stimati per 3,5 M token invece di 2–3,5 h).  Ha senso solo se la notte locale non basta o se
si vuole generare on-policy in batch sul pod.
