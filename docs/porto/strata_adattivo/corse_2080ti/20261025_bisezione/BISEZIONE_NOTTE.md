# Bisezione notte 25-26/10/2026: calo del decode dalla 0.1.45 in poi - CAUSA TROVATA

**Colpevole: upstream `a8091f4d` (Niko1221, 15/10, #2685) "serve: a request with no sampling gets the model card's ...; greedy only when
asked".** Non e' il motore: e' il server (`serve/server.py`). Compilato si (sm_75+86), installato no. Misure fatte tutte con build pure e
config Daily senza `--elastic`, `--prompt-cache-file` e senza env `STRATA_*`; PC libero, Jump staccato non verificato di nuovo, priorita' normale.

## Meccanismo (provato)

`_run()` ora fonde `model_card_sampling(arch, thinking)` sotto i campi della richiesta. Per Flash-Next senza ragionamento
(`reasoning_effort: none`, come fa il banco della comunita') sono `top_p 0.8, top_k 20, presence_penalty 1.5`. Il banco manda
`temperature: 0`, che resta "greedy" per la temperatura, ma `sampling_keys` passa lo stesso `top_p/top_k/penalty_present` al motore, che
esce dal percorso argmax puro e fa il percorso con filtri e penalita': circa -12% di decode (accettazione bozze invariata, 62-66%).
Prova: build pura 0.1.45 con il solo `model_card_sampling` spento (copia di `build-pure0145-477ac13c`, una riga in `server.py`) = decode della 0.1.43.

## Numeri (decode t/s, mediana delle 3 corse; 4K / 32K)

| build | sessioni | 4K | 32K |
|---|---|---|---|
| pura v0.1.43 (`7695859a`) | 6 (a-f) | 77,6 74,3 77,2 81,2 76,8 80,1 -> ~77 | 73,2 59,6* 71,7 75,1 72,4 70,0 -> ~72 |
| pura v0.1.45 (`477ac13c`) | 5 (a-e) | 65,4 70,7 68,4 68,3 67,6 -> ~68 (-12%) | 64,2 66,2 64,3 64,2 64,4 -> ~64,5 (-11%) |
| pura 0.1.45 + model card spenta | 2 | 79,3 73,8 -> ~76 | 70,8 74,2 -> ~72 |

(*) una corsa a 51 t/s per disturbo di macchina; prompt tok/s uguali in tutti i bracci (~710-735 a 4K, ~1280-1300 a 32K).
Il calo c'e' quindi gia' in upstream puro: la pila nostra non c'entra con questo -9/-12%.

## Bisezione (579 commit v0.1.43..v0.1.45, 9 passi, worktree `Strata-wt\bisect-step`; soglie = meta' fra pura 0.1.43 piu' recente e pura 0.1.45)

| passo | commit | esito | decode 4K/32K | oggetto |
|---|---|---|---|---|
| ref0 | pura 0.1.43 | - | 76,2 / 72,5 | |
| 1 | 226e0617 | GOOD | 78,7 / 73,9 | Mac: link the merged tree |
| 2 | 926b0bbe | BAD | 71,8 / 60,8 | Merge perf-PR group sycl |
| 3 | 0408f092 | GOOD | 79,9 / 70,9 | Merge f-145-q36speed |
| ref1 | pura 0.1.43 | - | 76,1 / 75,5 | |
| 4 | 27835694 | GOOD | 77,8 / 73,5 | setup: pin Q6K_EXPERTS |
| 5 | a1447b67 | BAD | 68,4 / 68,7 | Merge f-145-fix3 |
| 6 | 4a1ef86b | GOOD | 77,4 / 70,8 | layer split auto: SPLIT_SPEED_SCALE |
| ref2 | pura 0.1.43 | - | 75,9 / 72,3 | |
| 7 | 194c2688 | BAD | 68,3 / 64,1 | serve: Anthropic thinking.budget_tokens |
| 8 | e8634865 | BAD | 68,5 / 66,0 | web: no sampling until the user changes it |
| 9 | a8091f4d | BAD | 68,4 / 66,3 | **serve: model card sampling when none asked (#2685)** |
| ref3 | pura 0.1.43 | - | 77,3 / 70,2 | |

`git log 4a1ef86b..a8091f4d` = solo `a8091f4d`: intervallo chiuso. Grezzi in `20261019_banco_comunita\bs_*`, `n_*` (non committati); `passi_bs.tsv` e' il log grezzo.

## Cosa significa per il Daily e per le nostre build

- Vale per **ogni** build con server >= `a8091f4d` (0.1.45, 0.2.6 e le nostre pile sopra): una richiesta che non manda i campi di sampling riceve
  quelli della scheda modello. Per il traffico reale (ragionamento acceso: `1.0/0.95/20`, senza penalita') il costo e' diverso da quello del
  banco e **non misurato qui**; il banco a `temperature: 0` con `reasoning none` e' il caso peggiore.
- Il Daily 0.1.43 non ha questo codice: nessun calo. Il confronto 0.1.43 contro 0.1.45+ del 19/10 e del 25/10 era in buona parte questo effetto, non il motore.
- Con il solo blocco `sampling` della config non si riporta al greedy puro: `top_k: 0` viene comunque mandato come `top_k=64` (`sampling_keys`), quindi serve una patch.

## Prossimo passo (non fatto: serve decisione)

Patch nel fork, in `serve/server.py`: se la richiesta chiede esplicitamente `temperature <= 0`, non fondere dalla scheda modello `top_p/top_k/presence_penalty`
(greedy = argmax), oppure farlo solo quando la temperatura non e' stata detta. Poi rimisurare 0.2.6 + pila con banco a `temperature: 0` e,
separatamente, con un client reale (ragionamento acceso), per sapere il costo del campionamento nel traffico vero. Prima di dare ragione
al calo della pila 0.2.6 (-4/-6% del 25/10) rifare il confronto con questa patch o con la model card spenta su entrambe.
