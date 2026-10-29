# Multichat sulla build v0.2.7.1 + pila - 29 ottobre 2026

Build `20261004_routed_keep/build-up0271pila-5fbc4784` (v0.2.7.1 + 18 patch nostre; compilata sm_75+86; qui **provata solo su questa postazione**, installata no).
Config: copia di `strata-026-3080ti.json` (3080 Ti stadio 0, split 16) con l'exe nuovo: `cfg-up0271-3080ti.json`. Replay DSH `20261019_replay/replay_trace.py`, `--t0 3600 --span 1200 --only A,B,C`,
riscaldamento a parte (prima richiesta di ogni avvio fuori dal cronometro), priorita' normale. **In tutte le corse `STRATA_ROUTE_PRIOR=0`.**
Batch = `--batch 4`, cache conversazioni 18432 MiB / 16 posti, riserva VRAM 1905 / 700 MiB. Il log di P conferma la pipeline di default 0.2.7: «batch (pipelined, 2 groups of 2)».
Bracci: R0 senza batch; P batch 4 col default 0.2.7; PC = P + `STRATA_PIPED_CONCURRENT=1`. 6 agenti = `--dup 2` (34 richieste). Una corsa per braccio, nessuna ripetizione.
Script: `coda_multichat.py` (corse), `analisi_multichat.py` (usa `20261026_leve/analisi_fasi.py`; uscita in `fasi_generato.md`); dati in `corse/replay_*`.

**Ambiente.** Jump Desktop aperto (JumpConnect, 3 processi, inattivo); OktoCGControl (CGControl.exe) non in esecuzione (CPU Okto media 0). CPU di altri processi 4-6% (claude.exe, dwm), nessuna corsa «disturbata»,
17/17 (34/34) richieste riuscite, 0 fallite. La 3080 Ti aveva ~2,8 GiB gia' occupati dal sistema prima dell'avvio. Strata spento e nessun lock a fine lavoro.

## Tabella

| corsa | hardware | tempo totale s | TTFT medio / p90 s | (b) >=2 scrivono, agg. t/s (T / N) | (c) legge+scrive: scrittura agg. t/s (T / N) | lettura in (c) tok/s | lettura sola (a) tok/s |
|---|---|---:|---:|---:|---:|---:|---:|
| R0, 3 agenti | 3080 Ti + 2080 Ti, 0.2.7.1 | 338 | 48,9 / 110,8 | - (un solo scrittore: 80 t/s) | - | - | 1509 |
| **P** batch 4, pipeline default, 3 ag. | idem | **250** | 15,2 / 53,6 | 28 / 49 | 11 / 0 (N instabile) | 1093 | 887 |
| **PC** P + PIPED_CONCURRENT, 3 ag. | idem | **242** | 17,7 / 34,7 | 38 / 52 | 16 / 12 | 931 | 1030 |
| R0, 6 agenti | idem | 1201 | 157,9 / 261,7 | - | - | - | 1709 |
| PC, 6 agenti | idem | 470 | 46,5 / 106,8 | 30 / 10 (N instabile) | 16 / 15 | 981 | 1260 |
| rif. R0, 3 ag. (0.2.6) | 3060 + 2080 Ti | 438 | 65,8 / 119,1 | - | - | - | 1551 |
| rif. R2 batch-groups 2 (0.2.6) | idem | 251 | 12,9 / 21,5 | 24 / 30 | 10 / 5 | 1054 | 776 |
| rif. R3 R2+PIPED_CONCURRENT (0.2.6) | idem | 243 | 19,3 / 38,1 | 44 / 59 | 19 / 15 | 915 | 944 |

Riferimenti da `20261026_leve/RAPPORTO_FASI.md` / `fasi_generato.md`. **Attenzione, hardware diverso**: i riferimenti usano la 3060, queste corse la 3080 Ti; in piu' cambia il motore (0.2.6 -> 0.2.7.1 + pila,
con altri default di 0.2.7 non isolati: prefill a strati, pipeline) e la lettura grande C#22 (77.619 token) e' 1485-1623 tok/s qui contro 1520-1680 sui riferimenti. Non e' un confronto a parita' di scheda.

Quota di tempo (a / b / c / ferma): P 15 / 29 / 54 / 2 %, PC 16 / 21 / 63 / 0 %, PC a 6 agenti 9 / 12 / 79 / 0 %. Scrittura a testa in (b): P 9,8, PC 16,7 t/s (rif. R3 18,5).

## Letture dei numeri

- **Il batch vale come sulla 0.2.6**: 338 -> 250 s (P, -26%) e 242 s (PC, -28%); con la pipeline di default non serve `--batch-groups 2`. TTFT medio -69% (P) e -64% (PC).
- **P contro PC: 7 s (3%) e TTFT medio 2,5 s a favore di P, p90 19 s a favore di PC**: una corsa per braccio, i token generati variano del +-10% (4146 contro 4040): differenza nel rumore, nessun vincitore netto. Come sulla 0.2.6 (R2 251 / R3 243).
- **Scrittura con >=2 scrittori**: 28-38 t/s aggregati (T), 49-52 (N), dentro la forbice 24-61 dei riferimenti; mentre qualcuno legge gli scrittori fanno 11-16 t/s in tutto (T), come sui riferimenti (10-19): la lettura resta il percorso critico, 54-63% del tempo e' mista.
- **R0 qui e' piu' veloce del riferimento** (338 contro 438 s) ma anche piu' leggero: 441 K token nuovi letti contro 585 K (ordine di servizio diverso, meno riuso mancato) e 3560 token generati contro 4424. Il guadagno del batch su R0 va letto con questo.
- **6 agenti**: R0 1201 s (la cache a 2 posti non regge 6 conversazioni: 1,89 M token nuovi letti, 4,3x quelli a 3 agenti) contro 470 s di PC (-61%; TTFT medio -71%); PC a 6 agenti costa 1,9x il tempo di PC a 3 agenti per il doppio delle richieste. Le N di (b) a 6 agenti (10 t/s) sono instabili (fase di 45 s): fidarsi di T.
- Nessuna misura del 6 agenti con P (solo PC, il migliore per tempo totale a 3 agenti, per consegna).

## Verdetto

La 0.2.7.1 con pila e `ROUTE_PRIOR=0` regge il multichat: batch 4 col default pipeline porta 3 agenti da 338 a 242-250 s e 6 agenti da 1201 a 470 s, senza fallimenti e con TTFT medio 15-18 s; stesso comportamento della 0.2.6 (251/243 s), scrittura aggregata nella stessa forbice.
`PIPED_CONCURRENT=1` non cambia il tempo (242 contro 250 s, nel rumore) ma accorcia il p90 del TTFT (34,7 contro 53,6 s) e alza la scrittura mentre si legge (16 contro 11 t/s): da tenere acceso come sulla 0.2.6. Hardware diverso dai riferimenti, una corsa per braccio: tempi non provati su altra scheda.
