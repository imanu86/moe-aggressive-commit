# Passata unica per lettura e scrittura - design, 19 ottobre 2026

Compilato no, installato no, provato no (stato alla scrittura). M = misurato, S = stimato. Branch `lab/passata-unica`
(worktree `Strata-wt\passata-unica`, da `lab/multichat45b` faa52840); patch opt-in, registrata in `stack/`, da riportare su 0.2.0.

## Il caso da ottimizzare (owner)

Prefisso comune ~40k in cache per tutti; a ogni turno 1-4k token nuovi per agente; 3-4 agenti leggono mentre gli altri
scrivono. Oggi (M, log `mc2_r8/m-pack3`, `MULTICHAT.md`): una lettura corta costa ~1,0-1,5 s fissi + ~1 ms/token
(1,6-2k token in ~4,1-4,6 s = 390-480 t/s), le letture sono **una alla volta** (server `_take_control`), e con
`STRATA_PIPED_CONCURRENT=1` ogni lettura gira su un thread mentre i gruppi decodificano (replay: config 2 = 298-302 s).

## Cosa esiste gia' e cosa manca

| pezzo | stato | limite |
|---|---|---|
| `Prefill::run_packed` (segmenti di piu' sessioni in un flusso: hyper-connection, proiezioni, **esperti letti una volta per chunk**; GDN/conv/K-V/attenzione per sessione) | c'e' (L3, `STRATA_PACK_PREFILL=N`) | solo nel percorso senza decode concorrente |
| server `BHINT` (prompt mandato avanti da chi aspetta le control lines) | c'e' | solo se un'altra richiesta tiene gia' le control lines |
| `STRATA_PIPED_CONCURRENT=1` (lettura su thread, gruppi che decodificano) | c'e' (#2326, 0.1.45) | esce con `return true` **prima** di `pk_read`: nelle corse `pack3-conc` (r9) il pacco non e' mai scattato (0 righe `strata pack:` nel log) |
| pacco senza concorrenza (r8) | misurato | i decoder si fermano a ogni lettura (78% del wall): 16,8 t/s contro 19,6 |
| upstream 0.2.0-beta | guardato (`git log v0.1.45..upstream/main`) | nessuna lettura multi-sequenza, «Admissions are one at a time»; cambia solo il planner dei chunk (8253477b, request-sized): non tocca questa parte |

Il pacco da solo (M, `packdet:4:P`, 13/10): 4 code da ~1,6k lette in 11,1 s contro 18,8 s una alla volta (**-41%**);
nel log reale «6 token + 3 prompt mandati avanti (4410 token) in 9,5 s» contro 3-4 letture da 4,1-4,6 s.

## Perche' le righe di decode NON entrano nel chunk del prefill (qui)

Su questo rig il prefill corre a chunk (stream_all: ogni chunk ridequantizza tutti gli esperti del layer) e un chunk
dura secondi (M: 128 token 1,2 s, 512 1,9 s, 2k 4,5 s, 8k 10 s). Una riga di decode agganciata al chunk avanza di un
token (o una finestra MTP di 8) per chunk: tetto **< 1 t/s per agente** anche con chunk da 128 token, contro i 15-20
t/s per slot delle finestre concorrenti (M: 82,6 t/s aggregati con 2 chat). vLLM/SGLang mischiano decode e prefill
perche' il loro passo dura 20-50 ms con i pesi tutti residenti; da noi il passo del prefill e' 50-200x piu' lungo.
Quindi la «passata unica» qui e': **una passata per tutte le letture pendenti** (esperti letti una volta per tutti i
lettori) **mentre le finestre dei decoder girano in parallelo** sullo stesso GPU (sugli stream a priorita' alta di
#2326). La condivisione fisica degli esperti fra lettori e scrittori resta quella della cache residente (prestito).

## Passo 1 (implementato dietro `STRATA_PACK_CONCURRENT=1`)

Spezzare `pk_read` in tre parti e usarle nel percorso concorrente:

1. `pk_prepare` sul thread host, a pipeline scarica (dove gia' si fa `lend` e `reserve_uploads`): prende i `BHINT`,
   sceglie prefisso e slot di pacco, ripristina i prefissi (`conversation_kv_restore` + checkpoint), costruisce i
   segmenti, fa `lend(total)`, installa `on_pack_rows` (righe residue per il drafter).
2. Il thread di lettura chiama `sp.run_packed(segs)` invece di `sp.run(...)`; i gruppi decodificano via `pump` come
   oggi. Niente `stop_at_chunk` su una lettura impacchettata (lo `stopped_at` sarebbe nel flusso impacchettato, non nel
   segmento proprio): un `BYIELD` arrivato durante il pacco non viene preso (come oggi «not taken»).
3. `pk_finish` sul thread host dopo `join` + `pipe_drain`: checkpoint di ogni slot di pacco, log `strata pack:`.
   La ripresa della richiesta dal pack slot (`pack_source`, `copy_from_slot`) e' invariata.

Compatibilita' con `lab/batch-dyn`: stesse strutture (`pks`, `pack_ss`, `BSlot`), tutto sotto interruttore; la modalita'
agente puo' accendere `STRATA_PACK_PREFILL=N STRATA_PIPED_CONCURRENT=1 STRATA_PACK_CONCURRENT=1` senza altro.

Costi noti: N slot di pacco = N x (0,36 GiB sulla 3060 + 0,66 sulla 2080 Ti) (M): con la 3060 al limite si parte da
N=2-3 e si guarda la VRAM libera nel log; `cudaMemcpy` D2H di `on_pack_rows` sul thread di lettura (stream legacy:
puo' aspettare le finestre in coda, non blocca).

## Misura (passo 4)

Banco `letture_concorrenti.py` (cartella `corse_2080ti/20261019_passata_unica/`): W scrittori (chat su contesti in
cache, 600 token) partono a t=0; a t=+4 s N=4 lettori mandano insieme un turno di 2-4k token nuovi su conversazioni
R0..R3 (prefisso 32k + storia privata 0-70k, gia' in cache), `max_tokens 8`; due giri di letture per avvio. Si riporta:
wall delle 4 letture (primo invio -> ultima fine), TTFT per lettore, t/s dei scrittori **durante** la finestra delle
letture e sull'intera risposta, righe `strata pack:` / `read ... on a thread`. Bracci: B = config batch attuale +
`STRATA_PIPED_CONCURRENT=1`; A = B + `STRATA_PACK_PREFILL=3 STRATA_PACK_CONCURRENT=1`; alternanza B-A-B. Poi il replay
3 e 6-8 agenti (`replay_trace.py`) per il totale e i TTFT p50/p90.

## Stato esatto al STOP (19/10 ~19:50, token dell'owner finiti) e ripresa

**Fatto, committato, pushato**: codice su `imanu86/Strata-2080Ti` branch `lab/passata-unica` (worktree
`C:\Users\imanu\source\repos\Strata-wt\passata-unica`, da `lab/multichat45b` faa52840): 4ee62d09 (la leva, solo
`src/program/generate.cpp`, +124/-65), 9c57a4ac (registro `stack/21-pack-concurrent.patch`, INDEX/BLOCKS/manifest,
`--verify-docs` ok), 5c97ab45 (sezione in `docs/MULTICHAT.md`). Qui: banco `corse_2080ti/20261019_passata_unica/`
(`letture_concorrenti.py`, `coda_lc.sh`, `coda_replay_pu.sh`). **Compilato no, provato no, misurato no**: la build non e'
mai partita (lock GPU tenuto dall'agente batch-dyn per tutta la sessione); nessun lock, processo o `strata.exe` mio lasciato.
La pila 0.2.0 (`lab/upsync-020`) non e' toccata: la patch 21 dipende dai commit del pacco di `lab/multichat45`.

**Ripresa, in ordine** (tutto da `corse_2080ti\`; rispettare `D:\ds4_work\strata\lab_locks\pause` e `bench.lock`):
1. Build (prima volta: configure completo, sm_75+86):
   `python 20261006_due_schede\build_lock.py C:\Users\imanu\source\repos\Strata-wt\passata-unica --jobs 6`
   poi `python 20261006_due_schede\copia_build.py C:\Users\imanu\source\repos\Strata-wt\passata-unica passata "patch 21 pack-concurrent, 4ee62d09"`
   -> `20261004_routed_keep\build-passata-5c97ab45\` (il nome prende l'HEAD del worktree). Se il compilatore si lamenta:
   il blocco nuovo e' `pk_prepare`/`pk_finish`/`pk_read` (r.14290-14590) e il blocco `STRATA_PACK_CONCURRENT` dentro
   `read_part` (r.~14740-14960); `git diff faa52840 4ee62d09` lo mostra intero.
2. Banco corto B-A-B (3 avvii, ~10-12 min l'uno: 6 contesti da 32-100k da scaldare):
   `bash 20261019_passata_unica/coda_lc.sh build-passata-5c97ab45` -> `lc_b1/`, `lc_a1/`, `lc_b2/` (res.json, engine.log,
   `lc_*.run.log`). Numeri da riportare: `readers_wall`, `ttft`, `read_tps_wall`, `writers_tps_during_reads` /
   `_before` / `_after`, righe `strata pack:` (devono comparire SOLO in a1: «N tokens of this prompt read with K prompts
   sent ahead»), `jumpconnect_cpu_s.connected`, `load_other` (scartare se mean > 15 o p90 > 40), VRAM libera della 3060
   nel log (i 3 pack slot costano 1,1 GiB li': se va a 0, ripetere A con `STRATA_PACK_PREFILL=2`).
   Parita': `lc_a1/par_r*_R*.txt` contro `lc_b1/par_r*_R*.txt` (primo carattere diverso; sul 13/10 la divergenza era a
   meta' testo e c'era anche fra due corse base: non e' bitwise, va solo riportata).
3. Replay (stesso exe, stesso B-A-B): `bash 20261019_passata_unica/coda_replay_pu.sh build-passata-5c97ab45 1` (3 agenti +
   orchestratore, ~5 min a braccio) e poi `... 2` (8 agenti; VRAM a rischio sulla 3060: guardare il log). Esiti in
   `20261019_replay\replay_pu-*\res.json`: tempo totale, TTFT p50/p90, token riletti, decode aggregato; confronto con
   config 2 del 19/10 (298-302 s, TTFT 20/76 s).
4. Scrivere i numeri in `docs/MULTICHAT.md` (sezione «Passata unica») e in `stack/manifest.json` (`measured` della 21),
   rigenerare INDEX/BLOCKS con `20261019_passata_unica/stack_add.py <worktree> <sha> <entry.json>` (riusa
   `check_anchors.py`: format-patch, ancore, render; `entry21.json` accanto e' la voce usata), poi `--verify-docs`.
5. Solo con guadagno misurato: i «Passi dopo» qui sotto, nell'ordine.

## Passi dopo (solo se il passo 1 misura un guadagno)

- Server: `BHINT` anche per le richieste che arrivano **durante** una lettura (oggi il motore le impacchetta solo con
  la lettura successiva); finestra di raccolta `STRATA_PACK_WAIT_MS` prima di partire (TTFT del primo piu' alto, aggregato
  piu' basso: da misurare, non da stimare).
- Pacco senza slot di pacco: segmento scritto direttamente nello slot batch della richiesta (via la copia ~0,4-0,6 s
  «gave back ... in N ms», M) - serve che le righe di riempimento dei gruppi in pipeline non sporchino uno slot inattivo.
- `STRATA_PACK_CHUNK` sul planner 0.2.0 (request-sized chunks) perche' il pacco vada in pipeline fra i due stadi.
