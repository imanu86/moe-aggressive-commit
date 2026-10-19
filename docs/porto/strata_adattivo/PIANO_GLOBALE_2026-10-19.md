# PIANO GLOBALE per gli agenti locali — Strata sul PC dell'owner (19 ottobre 2026, sera)

Scritto da Fable (Claude) per agenti che girano su Strata stesso (Qwen3.8-Flash-Next). Istruzioni esplicite: eseguire i passi
nell'ordine, un passo alla volta, registrare i numeri, fermarsi al primo criterio non rispettato. Non inventare varianti.
Stato alla scrittura: tutto il codice qui citato è committato e pushato; **compilato no, provato no, misurato no** dove scritto.

## 0. Regole che valgono per ogni passo (leggere due volte)

1. **GPU solo con il lock**: ogni corsa GPU prende `D:\ds4_work\strata\lab_locks\bench.lock` (creazione esclusiva `O_EXCL`, una corsa per
   volta) e lo rilascia subito dopo. I runner citati sotto lo fanno da soli; se lanci il motore a mano usa
   `python corse_2080ti\20261006_due_schede\bench_lock.py <NOME> -- <comando>`. Se il file c'è già: **aspettare**, mai cancellarlo.
2. Se esiste `D:\ds4_work\strata\lab_locks\pause`: **fermarsi** (nessuna build, nessuna corsa) finché non sparisce.
3. **Mai priorità alta** a nessun processo (build in `BELOW_NORMAL`, motore a priorità normale).
4. **Daily intoccabile**: non modificare, spostare o cancellare `D:\ds4_work\strata\Strata\build-0145-daily`, `build-0143-daily`,
   `strata-0143-daily.json`, `strata-0145-daily.json`, i `.bat` sul Desktop. Le config si **copiano** in una cartella propria e si modifica la copia.
   Mai `taskkill /IM strata.exe` (ucciderebbe il Daily): i runner fermano solo il proprio albero di processi.
5. **Git**: branch indicato in ogni lavoro; prima di toccare un repo `git branch --show-current` e `git status --short --branch`; `git pull --ff-only`.
   Commit piccoli con **pathspec espliciti** (`git add <file1> <file2>`), **mai `git add .`**, **mai `git add -A`**. Messaggio
   `QWEN-SEZIONE-Descrizione imperativa` (sezioni: `OVERLAP`, `PASSATA`, `BATCH`, `UPSYNC`, `DOC`), riga finale
   `Co-Authored-By: <modello> <noreply@local>`. Push subito dopo ogni commit. Mai force-push, mai rebase di branch già pushati
   (eccezione documentata in §4 passo 4.3). Mai toccare i branch `lab/passata-unica`, `lab/batch-dyn`, `lab/upsync-020` se non è il tuo lavoro.
6. **Annotare l'ambiente** di ogni corsa: Jump Desktop connesso o no (`tasklist | findstr JumpConnect`, i runner scrivono `ambiente.txt`),
   OktoCGControl aperto (sempre: condizione standard), altri `strata.exe` vivi (`tasklist | findstr strata.exe`: il Daily è uno di questi).
7. **Dichiarare sempre** nel doc e nel report: «compilato sì/no, installato no, provato sì/no, misurato sì/no». Installare non è mai compito tuo.
8. Dati personali e contenuti delle chat: mai nei log o nei doc. Solo conteggi e tempi.
9. Un numero vale solo se è B-A-B (braccio base, braccio con la leva, braccio base di nuovo) **sullo stesso exe o con exe dichiarati**, con la stessa
   config e lo stesso ambiente. Una corsa singola è «indicazione», non verdetto. Un effetto più piccolo della dispersione fra i due A è «inconclusivo».
10. Doc di lavoro: in `C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\` (repo `moe-aggressive-commit`, branch
    `research/ds4-iq1-subbit-tier-planner`). Esiti grezzi in `corse_2080ti\<cartella del lavoro>\`. Log grezzi grandi (>50 MB) restano su `D:\ds4_work\strata\lab_runs\`.

### 0a. Percorsi fissi

| cosa | percorso |
|---|---|
| repo dei doc e dei banchi | `C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\` (sotto: `corse_2080ti\`) |
| worktree del fork (branch `lab/*`) | `C:\Users\imanu\source\repos\Strata-wt\<nome>\` (fork `imanu86/Strata-2080Ti`, remote `origin`; upstream `Niko1221/Strata`, remote `upstream`) |
| Daily (sola lettura) | `D:\ds4_work\strata\Strata\` |
| lock | `D:\ds4_work\strata\lab_locks\` (`bench.lock`, `build.lock`, `pause`) |
| build di laboratorio | `corse_2080ti\20261004_routed_keep\build-<nome>-<sha8>\` (exe + `build.json` + `source\serve` + `source\tools`) |
| banco DET (teacher forcing, 131k, L01+L02, 1024 token) | `corse_2080ti\20261006_due_schede\det_force.sh`, verdetto `bab_verdict.py` |
| banco della comunità (4K/32K/128K freschi, 256 token) | `corse_2080ti\20261019_banco_comunita\community_bench.py` |
| replay del lavoro reale (3 agenti DSH) | `corse_2080ti\20261019_replay\replay_trace.py` |

### 0b. Comandi standard (copiarli così, cambiando solo le parti fra `< >`)

**Build** (una sola per volta su tutta la macchina; aspetta `bench.lock` libero e prende `build.lock`; ~20-40 min la prima volta, incrementale dopo):
```
cd C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\strata_adattivo\corse_2080ti\20261006_due_schede
python -u build_lock_noeng.py C:\Users\imanu\source\repos\Strata-wt\<worktree> --jobs 4
```
`build_lock_noeng.py` **non esiste ancora**: crearlo una volta (passo 1.0) copiando `build_lock.py` e togliendo ` and not engine_running()` dalle
due condizioni dell'attesa (il Daily dell'owner è sempre acceso: l'originale aspetterebbe per sempre). Esito atteso: ultime righe `rc 0` e
`sha256 <hash>`; l'exe è in `<worktree>\build-sm7586\strata.exe`. Se `rc` non è 0: leggere le righe `error` stampate, correggere **solo** il file
indicato, ricompilare. Poi copiare la build accanto ai banchi:
```
python copia_build.py C:\Users\imanu\source\repos\Strata-wt\<worktree> <nome> "<nota: branch, sha, leva>"
```
→ `corse_2080ti\20261004_routed_keep\build-<nome>-<sha8>\` (`<sha8>` = HEAD del worktree).

**Banco DET B-A-B** (3 corse: A, B, A; ~6-7 min ciascuna dopo il primo prefill; da Git Bash, cartella `corse_2080ti\20261006_due_schede`):
```
bash det_force.sh DET-<tag>-A1 build-<nome>-<sha8>
bash det_force.sh DET-<tag>-B1 build-<nome>-<sha8> --env STRATA_<LEVA>=1
bash det_force.sh DET-<tag>-A2 build-<nome>-<sha8>
python bab_verdict.py DET-<tag>-A1 DET-<tag>-B1 DET-<tag>-A2
```
`bab_verdict.py` vuole `A B1 [B2]`: con due A e un B chiamarlo come `python bab_verdict.py DET-<tag>-B1 DET-<tag>-A1 DET-<tag>-A2` e leggere il
segno al contrario (stampa «guadagno di ogni B su A»: qui dice quanto gli A guadagnano sul B). Criterio: la leva vale solo se **entrambi** gli A
sono più lenti del B e la differenza supera la dispersione fra A1 e A2. Il banco forza gli stessi token in tutti i bracci (teacher forcing): un
braccio che produce `finestre` diverse nel verdetto ha cambiato il lavoro → corsa non valida.

**Identità dei token** (ogni leva deve dare lo stesso testo a leva spenta e accesa): `det_force.sh` scrive `<DET-...>/force_trace.txt`; con la
leva accesa il file deve essere **identico byte a byte** a quello del braccio A (`fc /b` su Windows o `cmp`). Se differisce: la leva cambia i token,
scriverlo nel doc e fermarsi (non promuovere).

**Banco della comunità** (una corsa ≈ 7 min; config = copia di quella del Daily con `exe`/`vision.exe` della build):
```
python corse_2080ti\20261019_banco_comunita\community_bench.py <tag> <config.json assoluto> <cartella build assoluta>
```
Esito in `corse_2080ti\20261019_banco_comunita\<tag>\summary.json` (mediane `prefill_tok_s`, `decode_tok_s` per 4096/32768/128000) e
`ambiente.txt`. Riferimento (19/10, Jump scollegato): Daily 0.1.43 r2 prompt/decode **701/75,9 · 1439/70,4 · 1720/75,3**; 0.1.45 senza batch 663/67,0 ·
1282/66,4 · 1519/69,2; comunità 2x5060 Ti 911/84,8 · 2087/86,5 · 2440/83,8.

**Replay del lavoro reale** (24 richieste, 4 sessioni, ~5-17 min; `--extra` sostituisce opzioni della config, `--env` aggiunge variabili):
```
cd corse_2080ti\20261019_replay
python ..\20261006_due_schede\bench_lock.py REPLAY-<tag> -- python -u replay_trace.py --tag <tag> --t0 3600 --span 1200 --exe <exe assoluto> --extra "<opzioni>" --env "<K=V K2=V2>"
```
Esito in `replay_<tag>\res.json`: tempo totale, TTFT p50/p90, token riletti, decode aggregato. Riferimento: config 1 (Daily senza batch) **937-1069 s**,
TTFT 135-171 / 275-334 s; config 2 (`--batch 4 --batch-groups 2 --conversation-cache-mib 28672 --conversation-cache-slots 16` + `STRATA_PIPED_CONCURRENT=1`)
**298-302 s**, TTFT 17-20 / 72-76 s.

## 1. Obiettivo 1 — Chat singola: le due schede davvero in parallelo (finestre in pipeline + MTP)

### 1.1 Cosa dicono le misure (letto, non rifatto; fonti: `Strata-wt\pipeline2\docs\PIPELINE2.md`, `Strata-wt\struct-b\docs\STRUCT_B.md`, `MISURE_STADIO0_2026-10-19.md`)

- Finestra fresca (72% delle finestre, 28,3 ms, in serie): catena MTP 2,1 → stadio 0 sulla 3060 10,1 → stadio 1 sulla 2080 Ti 15,9. Finestra
  speculativa (28%, 19,8 ms): solo stadio 1 (+ catena in contesa). Media 25,9 ms per 1,7-2,0 token.
- Perché solo il 28%: la finestra B (indovinata) parte nell'89% delle finestre ma è giusta nel 31%. A viene accettata intera nell'**80%**; a
  sbagliare è la **riga 0 di B** = la bozza che la regola `--spec-min-p 0.5` ha scartato (probabilità 0,1-0,4, giusta il 38% delle volte).
  Quindi la «lunghezza di accettazione» è già indovinata bene; il problema è il **token bonus**.
- Chi sta ferma: nelle fresche la 3060 è ferma 2,1 ms (catena) + 5,8 ms (dopo B); la 2080 Ti ferma ~6 ms (durante lo stadio 0 di A). Nelle
  speculative la 3060 è ferma ~10 ms e la 2080 Ti è il collo (stadio 1 + catena kind 1 che le ruba 0,6-7,5 ms a seconda di T).
- Tetto: ogni 10 punti in più di B giuste = −0,85 ms a finestra (−3,3%). Con B sempre giusta la finestra sarebbe ~17-19 ms (90-100 t/s).
- Leve già scartate con numeri (non riprovarle): expert-parallel (−0,5/−2 ms, 15-25 giorni), tensor-parallel (pari con MTP), micro-finestre (+5/+7 ms),
  `--pipeline-windows 3` (lo stadio 1 è il collo), post() persistente (bacino ≤0,95 ms), P-state (P0 al 100%), `STRATA_P2_SMEM`, `STRATA_P2_FLUSH_US`.
- Leva grossa ma lunga: **B ad albero** (due ipotesi per la riga 0 di B nello stesso passaggio dello stadio 0: bozza top-1 + seconda scelta). Copre
  +15 punti di B giuste **se** la seconda scelta è giusta ~30% delle volte (stima, **non misurata**). Serve stato GDN a rami, una cella K/V in più
  nei 4 layer QSA dello stadio 0, top-2 nella catena, seconda catena sulla 2080 Ti nei ~6 ms liberi. 8-12 giorni; un fork l'ha provata senza guadagno.
  **Non è per gli agenti locali.** Il passo 1.2 misura il numero che decide se vale (la seconda scelta).

### 1.2 Passi (ordine obbligato; ogni passo chiude con numeri nel doc `OVERLAP_2026-10-19.md`, da creare)

Branch: `lab/overlap` da `lab/upsync-main` (0.1.45 + pila), nuovo worktree:
```
cd C:\Users\imanu\source\repos\Strata-wt\upsync-main
git pull --ff-only
git worktree add ..\overlap -b lab/overlap lab/upsync-main
```

**1.0 Preparazione** (nessuna GPU): creare `corse_2080ti\20261006_due_schede\build_lock_noeng.py` (§0b); creare `corse_2080ti\20261019_overlap\`;
copiare `D:\ds4_work\strata\Strata\strata-0143-daily.json` in `20261019_overlap\cfg-overlap.json` e cambiare solo `exe`, `vision.exe`
(→ build di laboratorio), `log`, `--prompt-cache-file` (→ file nella cartella). Compilare `lab/overlap` così com'è (= upsync-main) → `build-overlap-<sha8>`
e fare **un DET A/A** (`DET-ov-A0`, `DET-ov-A0b`): la dispersione fra i due è il metro di tutto il lavoro. Criterio: dispersione (max−min)/media su L01+L02
sotto il 3%; se è sopra, ripetere a PC fermo (Jump scollegato) prima di proseguire.

**1.1 Leve senza codice, B-A-B DET** (3 corse ciascuna, stessa build, stessa config, solo l'env cambia; una leva per volta):
| leva | braccio B | perché | criterio |
|---|---|---|---|
| polling senza cambio scheda | `STRATA_P2_FLUSH_NOSWITCH=1` | 13/10: L02 −3/−4% con un solo A, inconclusivo | promuovere nel doc solo se entrambi gli A sono più lenti oltre la dispersione |
| drafter sulla prima scheda | `STRATA_MTP_STAGE0=1` | upstream +21% su 2x R9700; qui primo braccio 63-66 contro 66-69 (peggio) | se peggiora anche al B-A-B: chiudere, scrivere «no» |
| soglia bozze | `--spec-min-p 0.70` (nella copia della config, `--add-opt` non basta: è un'opzione già presente → modificare la copia) | B scommette su bozze più sicure ma le fresche rendono meno token | guardare **ms per token**, non ms per finestra |
Scrivere per ogni leva: t/s L01 e L02 dei tre bracci, dispersione A1/A2, `force_trace.txt` identico sì/no, verdetto.

**1.2 Diagnostica «seconda scelta»** (codice piccolo, opt-in, bitwise; decide il futuro della B ad albero). Un solo file per volta:
- `src/core/mtp.cpp`: dove la catena legge la probabilità della bozza top-1 (cercare `prob` vicino a `chain_poll` / `chain_outputs_ready`), aggiungere
  dietro `STRATA_OV_TOP2_STAT=1` la lettura anche del secondo token più probabile e della sua probabilità (una riduzione top-2 nel kernel che oggi fa
  l'argmax, oppure copia host dei logit del drafter: va bene anche lenta, è solo diagnostica).
- `src/program/generate.cpp`, blocco del verdetto della finestra A (cercare `chain_kind` e il confronto `A.tok[a + 1] == outp[a]`): quando A è accettata
  intera, confrontare il token bonus vero con top-1 e top-2 della catena per quella posizione; contatori per richiesta; riga di log a fine richiesta
  `strata overlap top2: bonus=top1 N1, bonus=top2 N2, altro N3 su N` (con `STRATA_DECODE_TIMING`).
- Verifica: build, `det_force.sh DET-ov-top2 build-overlap-<sha8> --env STRATA_OV_TOP2_STAT=1`; `force_trace.txt` identico al braccio A0; leggere la riga.
- Esito da scrivere: N2/(N2+N3) = quota recuperabile dalla seconda scelta. **Se < 20%: la B ad albero è chiusa per sempre; se ≥ 30%: segnalare
  all'owner come lavoro da 8-12 giorni per un modello grande.** Non implementarla.

**1.3 Catena kind 1 senza contesa** (codice piccolo, bitwise): in `src/core/mtp.cpp` riga ~442 lo stream della catena è creato con priorità massima
(`cudaStreamCreateWithPriority(&cs_, cudaStreamNonBlocking, prio_hi)`). Aggiungere `STRATA_OV_CHAIN_PRIO=0|1` (0 = come oggi; 1 = priorità normale, cioè
`cudaStreamCreateWithFlags`). Nelle speculative la catena kind 1 gira insieme allo stadio 1 e lo rallenta di 0,6-7,5 ms; la 3060 ha ~5 ms di margine
per ricevere B più tardi. Misura: B-A-B DET (criterio §0b) **e** le righe `pipeline classes` dell'`engine.log` (ms delle speculative a parità di T: devono
scendere; «B: fine stadio 0 prima del verdetto» non deve andare sotto 0). Se le speculative non calano: chiudere la leva, lasciare il codice opt-in.

**1.4 Registrazione in `stack/`** per ogni leva di codice che resta (1.2, 1.3): un commit per leva (solo i file toccati), poi
`python stack/check_anchors.py --build . --range lab/upsync-main..HEAD` nel worktree, `python stack/check_anchors.py --verify-docs` deve dire `docs ok`;
compilare la voce in `stack/manifest.json` (`summary`, `switch`, `origin`, `upstream_status`, `measured` con i numeri del B-A-B). Commit
`QWEN-OVERLAP-Registra in stack/ la patch NN <nome>`.

**1.5 Banco della comunità** una volta a fine lavoro, solo con le leve che hanno superato il DET, B-A-B (Daily 0.1.43 → build con env delle leve → Daily).
Criterio di successo dell'obiettivo 1: decode mediano 128K ≥ **78 t/s** (Daily 75,3) con token identici; obiettivo pieno 80.

**Cosa NON fare**: non riscrivere i kernel; non cambiare lo split dei layer (16); non toccare `--pipeline-windows`; non accendere nel Daily niente;
non ripetere le misure di PIPELINE2 (nsys, hop_bench, census); nessun B-A-B con `STRATA_P2_SWITCH_STAT=1` (altera i tempi).

## 2. Obiettivo 2 — Multichat (3-8 agenti sullo stesso prefisso)

### 2.1 Passata unica prefill+decode (`lab/passata-unica`, patch 21 `STRATA_PACK_CONCURRENT`, codice scritto, mai compilato)

Fonte: `PASSATA_UNICA_2026-10-19.md` (leggere la sezione «Stato esatto al STOP e ripresa»: i passi sono già lì, qui il riassunto operativo).
Worktree `C:\Users\imanu\source\repos\Strata-wt\passata-unica`, branch `lab/passata-unica` (HEAD 5c97ab45, da `lab/multichat45b`).
1. `git pull --ff-only`; build (§0b) → `copia_build.py ... passata "patch 21 pack-concurrent, 4ee62d09"` → `build-passata-5c97ab45`. Se non compila:
   il blocco nuovo è `pk_prepare`/`pk_finish`/`pk_read` (r. ~14290-14590) e il blocco `STRATA_PACK_CONCURRENT` dentro `read_part` (r. ~14740-14960);
   `git diff faa52840 4ee62d09` lo mostra intero. Correggere solo lì, commit `QWEN-PASSATA-Corregge la compilazione di <funzione>`.
2. Banco corto B-A-B: `bash corse_2080ti/20261019_passata_unica/coda_lc.sh build-passata-5c97ab45` → `lc_b1/`, `lc_a1/`, `lc_b2/` (`res.json`).
   Numeri da riportare: `readers_wall`, `ttft`, `read_tps_wall`, `writers_tps_during_reads`/`_before`/`_after`; righe `strata pack:` **solo** in `lc_a1`
   (se mancano la leva non è scattata: fermarsi, leggere `engine.log` per «declined»); `load_other` (scartare se mean > 15 o p90 > 40); VRAM libera
   della 3060 nel log (3 pack slot = 1,1 GiB: se va a 0, ripetere A con `STRATA_PACK_PREFILL=2`).
   **Criterio di successo**: `readers_wall` di A sotto quello di **entrambi** i B di almeno il 20% (il pacco da solo misurava −41%) **e**
   `writers_tps_during_reads` di A non sotto il minimo dei B di più del 10%.
3. Replay: `bash corse_2080ti/20261019_passata_unica/coda_replay_pu.sh build-passata-5c97ab45 1` (3 agenti), poi `... 2` (8 agenti; guardare la VRAM).
   Criterio: tempo totale sotto 298 s (config 2) e TTFT p90 sotto 72 s; token riletti non sopra 0,19 M.
4. Scrivere i numeri in `docs/MULTICHAT.md` (sezione «Passata unica») e in `stack/manifest.json` (`measured` della 21), rigenerare con
   `python corse_2080ti/20261019_passata_unica/stack_add.py <worktree> <sha> entry21.json`, poi `--verify-docs`. Commit `QWEN-PASSATA-...`, push.
5. Solo con guadagno misurato: i «Passi dopo» di `PASSATA_UNICA_2026-10-19.md` (BHINT durante la lettura, `STRATA_PACK_WAIT_MS`), uno per volta.
Non fare: non portare la patch su 0.2.0 (dipende dai commit del pacco di `lab/multichat45`: va dopo l'obiettivo 3); non accendere `STRATA_PACK_PREFILL` nel Daily.

### 2.2 Passaggio a caldo chat singola ↔ agenti (`lab/batch-dyn`, patch 21 `STRATA_BATCH_DYNAMIC`, compilato sì, misure parziali)

Fonte: `BATCH_DINAMICO_2026-10-19.md` (§6 vuoto: va riempito). Worktree `Strata-wt\batch-dyn` (HEAD c4af6851). Build già fatta nel worktree
(`build-sm7586\strata.exe`, log `corse_2080ti\20261019_batch_dyn\build3.log`); se l'exe manca, build (§0b) e `copia_build.py ... batchdyn "..."`.
Esiti già in cassetto (19/10, da leggere prima): `20261019_batch_dyn\a-dyn\summary.json` (banco comunità in modo dinamico: 4K decode mediano **68,0 t/s**
contro 24,6 della config batch fissa e 67,0 senza batch), `a-dyn\switch.json` e `c-dyn\switch.json` (cicli solo→agenti→solo: solo-dopo 69,6 t/s,
agenti 14-27 t/s a 3 chat), `b-dyn-v2-perdita` (perdita di RAM pinned, corretta in c4af6851).
1. Completare la coda: `bash corse_2080ti/20261019_batch_dyn/coda_dyn.sh <cartella build>` (banco comunità + 2 cicli di passaggio, poi replay `b-dyn`).
   Numeri: 4K/32K/128K prompt e decode in `a-dyn`; per ogni ciclo in `switch.json` `decode_tok_s` di `solo-prima`, `agenti`, `solo-dopo`, `ttft_s`;
   `vram.csv` (3060 mai sotto 500 MiB liberi durante «agenti»); nel log `strata core stat` e nessuna riga «ERR BGEN».
   **Criteri**: `solo-dopo` ≥ 95% di `solo-prima`; `solo-prima` ≥ 95% del Daily senza batch (75,9 a 4K); replay `b-dyn` ≤ 302 s con TTFT p90 ≤ 76 s;
   working set del motore dopo 2 cicli non cresciuto di più di 1 GiB (la perdita era ~10 GiB a ciclo).
2. Se un criterio fallisce: leggere `engine.log` attorno al passaggio («release_slots», «el_shrink», «grow»), scrivere il sintomo in §6 del doc,
   **non** correggere a tentativi: proporre la correzione in una riga e fermarsi.
3. Prefisso comune da disco anche col batch: oggi `STRATA_CONV_DISK` e `--prompt-cache-file` con `--batch` sono gestiti da batch-dyn
   (commit 89e79d2d: la cache conversazioni su disco resta accesa nel modo agenti). Verifica: nel replay `b-dyn`, al secondo turno di ogni sessione,
   `cached_tokens` deve coprire il prefisso (≥ 9218 token) e le righe `prefix ... restored from file` devono comparire in `engine.log` dopo un riavvio
   del motore (fare un avvio, una chat da 40k, stop, riavvio, stessa chat: TTFT del secondo avvio < 10 s). Scrivere i numeri; se il prefisso non viene
   ripreso col batch, segnalare (lavoro di codice per un modello grande: «le fasi ripristinano solo immagini intere», `MULTICHAT.md` 19/10 §C.3).
4. Registrare in §6 del doc e in `stack/manifest.json` (`measured` della 21 batch-dyn), `--verify-docs`, commit `QWEN-BATCH-...`, push.
Non fare: non combinare batch-dyn con `STRATA_PACK_PREFILL`/`STRATA_PIPED_MTP`/`--batch-mtp` (il motore li rifiuta); non alzare `--vram-reserve-mib`
sopra 1393 senza scriverlo; non cambiare `STRATA_BATCH_IDLE_S` (30) nelle misure.

### 2.3 Ordine fra 2.1 e 2.2
Prima 2.2 (è già compilato e ha esiti parziali), poi 2.1. Mai le due build insieme (un solo `build.lock`); mai due corse GPU insieme.

## 3. Obiettivo 3 — Riallineamento a upstream 0.2.0-beta (`lab/upsync-020`)

Fonte: `Strata-wt\upsync-020\docs\UPSYNC_020.md` (§4 ha i comandi; patch portate 18 di 18, compilato no). Worktree `Strata-wt\upsync-020`.
1. `git pull --ff-only`; build (§0b, `build_lock_noeng.py`, `--jobs 4`). Rischi alla compilazione: blocchi 3-way delle patch 05 e 12 (`expert_source.cpp/.hpp`),
   13 (`verify.cpp`), 17 (`mtp.cpp`, `verify.cpp`), 18 (kernel `gr_*`). Correzione: `git commit --fixup=<sha della patch>` poi
   `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash upstream/main` (**unica eccezione** alla regola «mai rebase»: il branch è usato solo da questo lavoro;
   avvisare nel doc che la cronologia è stata riscritta), poi `python stack/check_anchors.py --build . --range upstream/main..HEAD` e `--verify-docs`.
   `copia_build.py ... upsync020 "0.2.0-beta f57c0adc + 18 patch"`; `strata-vision.exe` viene dal Daily (va bene per il banco).
2. Config: copie di `strata-0143-daily.json` in `corse_2080ti\20261019_upsync020\`: braccio **A** = env del Daily + `STRATA_HC16_SM75=1`, tolte
   `STRATA_NODECUT`, `STRATA_TOPK_GRID`, `STRATA_B6_HEAD_MINB` (inerti); braccio **C** = A + `STRATA_ADAPT_NOWAIT=1 STRATA_ADAPT_LAG=2 STRATA_CPU_IQ_ALL_EXACT1=1
   STRATA_GR_UP75=1 STRATA_GU_SWIGLU=1` (la tabella sm_86 di upstream, che con 8.6+7.5 non scatta da sola). Lanciare sempre con `STRATA_NO_PRESET=1`
   nell'ambiente del runner; **mai** rieseguire il setup automatico (riscrive le config).
3. Banco della comunità B-A-B: Daily 0.1.43 r2 → A → Daily → C. Criteri: A entro −3% del Daily su tutte e 6 le mediane (altrimenti bisezione per
   patch: §3.5); C ≥ A con token identici ad A (`tokens-*-raw.json` uguali; se diversi: C non è bitwise qui, scriverlo).
4. Banco DET: `det_force.sh DET-u020-A1/B1/A2` con build Daily-equivalente (`build-upsmain-d9a26384`, 0.1.45 + pila) come A e `build-upsync020-<sha8>` come B;
   `force_trace.txt` identico; criterio: B entro −2% di entrambi gli A.
5. Bisezione se serve: ricompilare `upstream/main` nudo (`git worktree add ..\u020-nudo f57c0adc`) e poi con le patch 1..k (`git am stack/01-*.patch ...`),
   banco comunità sul solo 128K (una corsa per punto), fino a trovare la patch che costa più del 2%. Scrivere la tabella in `UPSYNC_020.md` §5.
6. Scrivere §5 di `UPSYNC_020.md` con tutti i numeri; commit `QWEN-UPSYNC-...`, push. Il Daily **non** si cambia: la decisione di installare è dell'owner.
Non fare: non aprire/riaprire PR upstream (lista in `UPSYNC_020.md` §6: decide l'owner); non portare qui le patch 19-21 (multichat45b, passata-unica,
batch-dyn) prima che 2.1 e 2.2 abbiano numeri; non toccare `--layer-split`, `--pipeline-windows`.

## 4. Ordine complessivo e dipendenze

| ordine | lavoro | GPU | durata stimata | dipende da |
|---|---|---|---|---|
| 1 | 2.2 batch-dyn: coda `coda_dyn.sh` + verifica prefisso da disco | sì | ~1 h | build già fatta |
| 2 | 3 upsync-020: build + banco comunità A e C | build poi sì | 1 h build + ~45 min banco | nulla |
| 3 | 2.1 passata-unica: build + `coda_lc.sh` + replay | build poi sì | 1 h build + ~1,5 h | nulla (ma dopo 2 per il lock) |
| 4 | 1.0-1.1 overlap: A/A + 3 leve senza codice | sì | ~4 h | nulla |
| 5 | 1.2-1.3 overlap: diagnostica top-2, priorità catena | build poi sì | 1-2 giorni | 4 |
| 6 | 1.4-1.5, poi porto delle patch 19-21 su 0.2.0 | sì | — | 2, 3, 5 |

Una sola build e una sola corsa GPU per volta su tutta la macchina: gli agenti si coordinano **solo** con `build.lock`/`bench.lock` (attesa, mai rimozione).
Un agente che trova `pause` si ferma e scrive nel suo doc l'ora.

## 5. Formato del report di ogni passo (nel doc del lavoro e nel messaggio finale)

```
Passo <n> — <nome>. Compilato <sì/no>, installato no, provato <sì/no>, misurato <sì/no>. Jump <connesso/scollegato>.
Build: build-<nome>-<sha8> (sha256 <8 cifre>). Config: <file>. Bracci: <A1 | B1 | A2> = <numeri>. Dispersione A1/A2: <x%>.
Token identici: <sì/no (file confrontati)>. Verdetto: <promossa in doc / inconclusiva / scartata>. Commit: <sha> <messaggio>. Prossimo passo: <n+1>.
```
Massimo 10 righe per passo. Numeri sempre con l'unità e la fonte (`res.json`, `summary.json`, `engine.log` riga «...»).
