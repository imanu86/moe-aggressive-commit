# Sampling: patch temperatura 0 greedy puro e misure (26/10/2026)

Stato: **patch fatta, misure NON eseguite** (l'owner ha chiesto di aspettare). Compilato no (solo `serve/server.py`, il motore C++ non cambia), installato no, provato solo con i test Python.
Annotazione PC al momento della preparazione: Jump aperto (4 processi JumpConnect), OktoCGControl non rilevato; nessun file `lab_locks\pause`.

## Patch (fork Strata, `lab/upsync-026`)

- `0083469d` `serve/server.py` `_run()`: se la richiesta chiede `temperature <= 0` (numero, non bool) non si fonde la scheda modello (top_p/top_k/presence_penalty). Blocco `sampling` della config e impostazioni Chat condivise valgono come prima; gli altri casi invariati.
- Test: `serve/test_model_card_sampling.py` aggiornato (temp 0 -> nessuna chiave; temp 0 + `top_k=5` -> solo `top_k=5`); suite `serve/test_*.py` intera: 1035 test OK (15 saltati).
- Registro: patch 19 `greedy-temp0` in `stack/` (`--build` e `--verify-docs` ok), commit `SONNET-SAMPLING-Registra in stack/ la patch 19 greedy-temp0`.
- `server.py` copiato in `20261004_routed_keep\build-up026pila-ffe66174\source\serve\` (cartella non tracciata in git, come prima).

## Misure da fare (comandi pronti, non eseguiti)

Runner: `R = C:\Users\imanu\AppData\Local\Temp\claude\C--Users-imanu-source-repos-MultiPhoneControls\3df9aedd-b31a-4188-90dd-ec5b5610cd14\scratchpad\community_bench_corto.py`
Config B: `corse_2080ti\20261019_banco_comunita\up026p-B-pila\config.json` (exe e build `build-up026pila-ffe66174`). Prima di partire: nessun `pause` in `D:\ds4_work\strata\lab_locks`, nessun strata.exe in corsa, priorita' normale, Jump/OktoCGControl annotati.

(a) temperatura 0 (banco com'e'), in sequenza:

```
python R samp0_daily1 D:\ds4_work\strata\Strata\strata-0143-daily.json D:\ds4_work\strata\Strata\build-0143-daily
python R samp0_B_patch C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261019_banco_comunita\up026p-B-pila\config.json C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261004_routed_keep\build-up026pila-ffe66174
python R samp0_daily2 D:\ds4_work\strata\Strata\strata-0143-daily.json D:\ds4_work\strata\Strata\build-0143-daily
```

(b) temperatura da coding (0.7 / top_p 0.8 / top_k 20 / presence_penalty 1.5, `reasoning_effort: none`): copiare `R` in `community_bench_corto_t07.py` e `benchmark.py` (`upsync-main\bench\results\2026-09-30-community-rtx-5090\`) in `benchmark_t07.py`; nel runner puntare `BENCH` alla copia; nella copia di `benchmark.py` (riga ~45) sostituire `"temperature": 0` con `"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5`. Stesse tre corse con tag `samp07_daily1`, `samp07_B_patch`, `samp07_daily2`. Le bozze accettate si leggono da `engine.log`/`server.log` di ogni corsa (con temperatura > 0 l'accettazione cambia).

## Risultati

| braccio | decode 4K | decode 32K | accettazione bozze |
|---|---|---|---|
| (a) Daily / B patchata / Daily | da misurare | da misurare | da misurare |
| (b) Daily / B patchata / Daily | da misurare | da misurare | da misurare |

Riferimento atteso (BISEZIONE_NOTTE.md): con la scheda spenta il decode torna ai livelli 0.1.43 (~76 t/s a 4K, ~72 a 32K contro ~68 / ~64,5 con la scheda).

## Risultati 26/10 10:00-10:25 (PC pulito; mediane decode t/s 4K / 32K, bozze accettate ~140-155 su 210-240 in tutti i bracci)
| braccio | T=0 | T=0.7 coding (top_p 0.8, top_k 20, presence 1.5) |
|---|---|---|
| Daily 0.1.43 (1) | 88,1 / 72,9 | 68,4 / 65,2 |
| 0.2.6 + pila + greedy-temp0 | 82,0 / 78,3 | 60,3 / 61,7 |
| Daily 0.1.43 (2) | 69,8 / 74,1 | 60,5 / 69,9 |
- T=0: la patch chiude il divario (B dentro la forbice dei due Daily, sopra a 32K).
- T=0.7 (uso reale): B -6% a 4K e -9% a 32K sulla media dei Daily, a parità di accettazione: resta un costo del percorso con campionamento nella 0.2.6 da isolare. In uso reale il decode è ~10-15% sotto il T=0.
