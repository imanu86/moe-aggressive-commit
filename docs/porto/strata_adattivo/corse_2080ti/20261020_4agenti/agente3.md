# Agente 3 — il server Python della passata unica (20 ottobre 2026)

**Conclusione**: `serve/server.py` ora raccoglie le letture concorrenti prima di mandare la riga di lettura.
Interruttore `STRATA_PACK_CONCURRENT=1` + `STRATA_PACK_WAIT_MS` (default 30 ms). **Compilato no (Python: non si
compila), installato no, provato solo con test unitari (59 passed), misurato no.** Nessun uso della GPU, nessun
`strata.exe` mio avviato, nessun lock preso.

## Cosa mancava lato server

`_pack_hint` mandava il prompt avanti (`BHINT`) solo se **qualcuno aveva già** le righe di controllo. Il motore
(`pk_prepare`, `generate.cpp` 14319-14331) prende i `BHINT` **già in coda** quando arriva la riga di lettura: quindi
chi prende le righe per primo partiva subito e i compagni arrivati 1-20 ms dopo (tempi di codifica del prompt)
finivano nella lettura **successiva**. Con 4 agenti che scrivono insieme è il caso più frequente, ed è quello che nel
log `pack3-conc` del 19/10 non ha mai impacchettato.

## Cosa ho fatto (2 file, un solo commit)

Commit `e29c8065` su `lab/passata-unica` (pushato): `QWEN-PASSATA-Raccogli le letture concorrenti prima della riga di
lettura`.

- `serve/server.py`
  - knobs a livello modulo (dopo `ADMIT_MAX_WAIT_S`): `PACK_CONCURRENT` (`STRATA_PACK_CONCURRENT`), `PACK_WAIT_MS`
    (`STRATA_PACK_WAIT_MS`, default 30, campo 0-500; spento se l'interruttore è spento).
  - stato d'ammissione (nel blocco `slot_cv` che sopravvive a `restart()`): `pack_pending` (quanti `BHINT` mandati
    dall'ultima riga di lettura), `pack_gathered` (quanti ne ha raccolti una finestra).
  - `_pack_hint`: quando l'interruttore è acceso conta la riga e sveglia `slot_cv`. **La riga `BHINT` è identica alla
    release**; con l'interruttore spento non tocca nessun contatore e nessuna Condition.
  - `_pack_gather()` (nuovo): chi ha le righe di controllo tiene la propria riga di prompt per `PACK_WAIT_MS`; esce
    prima quando i prompt avanti raggiunti gli **slot di pacco** (`INFO pack_hints=N`): un altro non verrebbe
    impacchettato comunque. Azzera `pack_pending` (quei prompt appartengono alla lettura che parte ora), conta
    `pack_gathered` e stampa una riga nel log del server:
    `[strata] pack: K prompt(s) sent ahead in the W ms window before this read (one packed pass, N pack slots)`.
  - `_take_control(..., pack=...)`: finestra chiamata **solo** dalle 4 riprese di `generate_batched` (ammissione
    iniziale, ripresa solo-again, attesa di uno slot, ripresa dopo `BYIELD`) e **solo per richieste di testo**
    (`pack=embeddings is None`: vision/embedding non pagano la finestra). Nessun altro chiamatore.
  - `/metrics`: `pack_gathered` accanto a `waiting`/`admitting` (lettura, nessuna azione).
- `serve/test_pack_gather.py` (nuovo): 8 casi — interruttore spento (nessuna attesa, nessun conteggio), niente slot di
  pacco (nessuna attesa), compagno arrivato tardi (raccolto), finestra chiusa al numero di slot, lettore solo paga la
  finestra una volta, la raccolta non viene pagata due volte, `BHINT` identico senza interruttore.

**Semantica scelta** (da misurare, non da stimare): la finestra è un limite fisso; si chiude prima **solo** a slot di
pacco pieni. Con 1 compagno su 3 slot si paga tutta la finestra: è il costo del primo lettore che il design già
annuncia, e `STRATA_PACK_WAIT_MS=0` lo azzera per il braccio di confronto.

## File toccati / NON toccati

Toccati: `serve/server.py`, `serve/test_pack_gather.py`. Non toccati: `src/program/generate.cpp`, `docs/MULTICHAT.md`,
`stack/*` (registrazione patch), il banco in `corse_2080ti/`, qualsiasi lock o processo.

## Chieste all'agente 1 / a chi integra

1. La build **deve essere rilanciata** se il suo `strata.exe` è stato fatto prima dei commit C++ degli altri agenti:
   il exe in `Strata-wt\passata-unica\build-sm7586\strata.exe` è delle 06:17 di oggi; il mio pezzo è solo Python ma il
   tag di `copia_build.py` prende l'HEAD attuale e potrebbe etichettare un exe più vecchio.
2. `copia_build.py` vuole il worktree **pulito** (`git status --porcelain --untracked-files=no` vuoto): il mio è pulito,
   gli altri agenti committino prima della copia.
3. Registrazione in `stack/` (non mia): una voce `pack-gather` dopo la 21, con
   `20261019_passata_unica/stack_add.py <worktree> e29c8065 <entry.json>`, poi `--verify-docs`.
4. Nota da scrivere in `docs/MULTICHAT.md` (non mia): la riga `[strata] pack:` del server è il marker server-side da
   greppare insieme a `strata pack:` del motore; e un `BYIELD` durante una lettura impacchettata resta "not taken"
   (lato motore) — la logica di yield del server **non l'ho toccata**.

## Comandi di misura pronti (GPU: solo con `bench.lock`, non miei)

Copia della build (no GPU):
```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
python -u copia_build.py C:\Users\imanu\source\repos\Strata-wt\passata-unica passata "finestra server pack-gather e29c8065"
```
Banco B-A-B completo (3 bracci, prende `bench.lock` da solo):
```
cd ..\20261019_passata_unica
bash coda_lc.sh build-passata-<sha8>
```
Braccio A solo (per vedere subito se la finestra raccoglie):
```
python -u ..\20261006_due_schede\bench_lock.py LC-a0 -- python -u -X utf8 letture_concorrenti.py --tag a0 ^
  --exe ..\20261004_routed_keep\build-passata-<sha8>\strata.exe ^
  --extra "--batch 4 --batch-groups 2 --conversation-cache-mib 20480 --conversation-cache-slots 16 --vram-reserve-mib 1905 --vram-reserve-later-mib 700" ^
  --env "STRATA_PIPED_CONCURRENT=1 STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1"
```
Cosa guardare in `20261019_passata_unica/lc_a0/`: `server.log` → righe `[strata] pack:` (devono comparire **solo** in
A, e `K > 0`); `engine.log` → `strata pack:`; `res.json` → `readers_wall`, `ttft` (il primo lettore può salire di
≈ `STRATA_PACK_WAIT_MS`), `writers_tps_during_reads`. Braccio senza finestra: aggiungere `STRATA_PACK_WAIT_MS=0`
(mantiene `STRATA_PACK_CONCURRENT=1`, così il confronto è sulla sola finestra).

Test Python (nessuna GPU, già girati):
```
python -m pytest serve/test_pack_gather.py serve/test_pack_hint.py serve/test_admit_order.py serve/test_parallel.py -q
```
