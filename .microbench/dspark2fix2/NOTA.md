# DSPARK-2fix2 — Fatto 1: da 186 ms/passo al pavimento di banda (~20 ms)

Data: 2026-07-29. Tree bersaglio: `ds4-p4a` CORRENTE (= tree del binario
3DE06FD01C7CFB4D: dspark1 + logids + shared1 + dspark2 + dspark2fix + drain4fix;
preimage sha256 sotto). `dspark2fix2.patch`: solo `ds4-p4a/ds4.c`, 201 inserimenti /
34 rimozioni, 7 hunk. `git apply --check` PASS. Niente build, niente server, D:\ non
toccato. Fatto 2 non indagato (ritirato dal coordinatore).

## Risposta alla DOMANDA A

**Sì: il working set si pre-tocca e si pinna una volta a engine-open.** Ma il solo
prewarm NON bastava a stare sotto i 20 ms: nel mio schema di dspark2/2fix il denso
Q8 del passo (~178 MB) girava INLINE sul solo thread drafter (era il prezzo del
vincolo "mai submittare a g_pool"), quindi anche a memoria calda il passo sarebbe
costato ~30-45 ms (13-18 ms di denso mono-core + 2-3 di routed in pool + 14-18 di
testa in pool). Il fix ha quindi TRE pezzi, non due:

1. **PREWARM** (`DS4_NEXTN_PREWARM`, default 1, `=0` off): a engine-open una
   passata sequenziale (tocco ogni pagina da 4 KiB) su tutta la finestra tensori
   del modulo (~3,7 GiB) e sulla testa (562,6 MB). Il first-touch da ~820 MB/passo
   che oggi si paga a fault sparsi si paga UNA volta a velocità di readahead:
   ~1,3-2,5 s di avvio su NVMe (loggati). Riga: `[nextn-cpu] prewarm module=...
   MB in ... ms, head=... MB in ... ms`.
2. **PIN** (`DS4_NEXTN_PIN`, default 1): `VirtualLock` (con crescita del working
   set minimo del processo) / `mlock` sul working set per-passo GARANTITO:
   - modo 1 (default): denso del modulo (attn 113,8 + e/h_proj 35,7 + shexp 26,7 +
     hc/router/norm ~1,6 ≈ **178,5 MB**) + testa (**562,6 MB**) ≈ **741 MB
     bloccati** — è la parte letta IDENTICA a ogni passo;
   - modo 2: anche i 256 esperti Q4_K (**+3,54 GiB**, totale ≈ **4,27 GiB
     bloccati**) per macchine con RAM da spendere;
   - modo 0: off. I fallimenti di lock sono soft (riga `[nextn-cpu] pin mode=...
     locked=... failed=...`), si resta su page cache.
3. **Denso in pool** (la parte nuova): il thread drafter è marcato da una
   thread-local e `ds4_parallel_for_min_rows` ora instrada i SUOI job row-parallel
   alla pool G132 (stesso mutex di submit condiviso con shared1, guardia di
   rientranza via `g_parallel_depth` dentro `ds4_nextn_g132_submit`); i job piccoli
   (<512 righe: router, norm) restano inline. Così attn/shexp/e-h_proj girano sui
   worker della lane come i kernel Q4_K e la testa, e `g_pool` resta del solo
   decode thread come prima. Il `g_parallel_depth = 1` del worker (che forzava
   l'inline) è rimosso.

### Quanto costa in RAM

| Voce | Byte | Stato |
|---|---|---|
| prewarm modulo | ~3,7 GiB letti una volta | page cache, sfrattabile |
| prewarm testa | 562,6 MB letti una volta | page cache (o già pinned dal registro CUDA primario) |
| PIN=1 (default) | ≈741 MB | bloccati (working set) |
| PIN=2 | ≈4,27 GiB | bloccati |

Il lock della testa insiste su pagine che il registro primario CUDA può avere già
pinnato: ridondante e innocuo (conteggiato nel log).

### Quanto scende step_ms (aritmetica dichiarata, da verificare col summary)

Byte per passo: 178 (denso) + 85 (6 esperti) + 563 (testa) ≈ **826 MB**. A memoria
calda e tutto in pool il passo è bandwidth-bound: a 35-44 GB/s di DRAM il
**pavimento è ~19-24 ms/passo** (826/40 ≈ 20,6 ms) + ~0,3-0,5 ms di overhead
submit (≈15 submit/passo). Contro i 186 ms misurati: **~8-9x**. Il one-shot
`[nextn-cpu] first chain step done fwd=... head=...` e `step_ms_avg/max` nel
summary sono la verifica.

**La testa È la voce dominante: 563 MB = 68% dei byte per passo (~14-16 ms dei
~21).** Per questo è pinnata di default e prewarmata/loggata separatamente. Sotto
i ~15 ms/passo si scende solo tagliando byte, non scaldandoli: testa su GPU
(~2 ms, ma richiede arbitraggio del command context col decode thread — fuori
perimetro del drafter) o testa requantizzata (fuori mandato). Ciclo k=7 = 8
passi (holdback) ≈ **155-190 ms**: dentro la finestra di ~270 ms del regime; se
serve tassativamente <150 ms, `DS4_NEXTN_DRAFT_K=5..6` (7 passi ≈ 135-165) è il
knob già esistente.

## Correzione di lettura sul "rancido" (per il prossimo run)

Nel log citato, `rebase=0` dice che l'ancora del ciclo era vecchia di UN commit,
non di 6: con la catena persistente la validazione per-offset impedisce per
costruzione di consegnare draft posizionalmente stantii (li ri-basa o li uccide).
I 1690 ms sono comparsi come attesa più lunga PRIMA del take (il token GPU stesso
era lento sulla macchina già degradata), e `k_accepted=0` è un free-check miss
su drafts[0]: in dominio chat l'attesa a pos1 è ~0,60, quindi su n=1 ciclo non è
segnale. Con i passi a ~20 ms l'accettazione si misura su centinaia di cicli.

## Hunk (righe preimage) e neutralità

- 685: dichiarazione thread-local `g_nextn_drafter_thread` + fwd-decl del submit
  (spostate in testa, vicino a `g_parallel_depth`).
- 788: dispatch drafter in `ds4_parallel_for_min_rows`. **Unico costo a flag
  spento di tutta la patch**: una load thread-local + un branch per chiamata,
  stessa classe della load thread-local `g_parallel_depth` già presente due righe
  sotto nello stesso percorso. Su ogni thread non-drafter il flusso è identico.
- 6780: shim `ds4_nextn_parallel_for` ridotto a delega (il dispatch ora sta nel
  punto comune); rimossi i doppioni di declaration.
- 10002: worker: rimosso `g_parallel_depth = 1` (comment aggiornato).
- 11283: `ds4_nextn_g132_submit`: guardia di rientranza (`g_parallel_depth++/--`
  attorno al submit) — un nested parallel_for da dentro un worker fn degrada
  inline invece di ri-acquisire il mutex.
- 21940: blocco warm-up (touch/lock helper + `ds4_nextn_engine_warmup`; include
  `<sys/mman.h>` solo non-Windows).
- 22206: chiamata `ds4_nextn_engine_warmup(e)` dentro il ramo flag-acceso di
  engine-open, dopo la riga "enabled".

Nessuna riga di shared1/dspark1/drain4/drain4fix/logids toccata. A flag spento:
zero getenv nuove (il warm-up vive nel ramo già flag-guardato), zero thread,
zero lock; resta la sola load+branch thread-local di cui sopra.

## Log attesi nel prossimo run (sequenza sana)

```
ds4: [nextn-cpu] NextN CPU drafter enabled draft_k=7 (...)
ds4: [nextn-cpu] prewarm module=3719.x MB in ~1500 ms, head=562.6 MB in ~200 ms
ds4: [nextn-cpu] pin mode=1 locked=741.x MB failed=0.0 MB (...)
ds4: [nextn-cpu] drafter worker online (g132 pool initialized=1 workers=11; ...)
ds4: [nextn-cpu] first chain step done fwd=~6-9 ms head=~14-16 ms (...)
...
summary ... chain_steps=N step_ms_avg=19-24 step_ms_max=<50 ...
```
Se `step_ms_avg` resta sopra ~30 con `pin locked` pieno, il collo non è più il
first-touch: guardare `failed` (lock rifiutati) e la pressione di memoria di
sistema (il degrado ambientale del batch precedente).

## Verifiche eseguite

- `git apply --check .microbench/dspark2fix2/dspark2fix2.patch`: PASS sul tree
  corrente (verificato = preimage dspark2fix2 == tree del binario, hash sotto);
  `--numstat`: `201  34  ds4-p4a/ds4.c` (unico file).
- Bilanciamento `{} () []` sul file patchato: OK.
- `g_parallel_depth = 1` rimosso ovunque; nessun residuo dei simboli spostati.
- Reentrancy: submit → caller-partition sullo stesso thread → eventuale
  parallel_for annidato vede `g_parallel_depth>0` → inline (nessun re-lock).
- Nessuna compilazione, nessun server.

## SHA-256

Preimage (tree corrente):

```text
ds4-p4a/ds4.c
022474c7cb6013fbf4d2dbacbbe65d99701483f9530f7e5fa34bd1f496179a6e
```

Artefatto patch:

```text
.microbench/dspark2fix2/dspark2fix2.patch
0e14fbd035c63c0c4089437ea0be438e0e741ac584174366ef6c155bba7ea817
```
