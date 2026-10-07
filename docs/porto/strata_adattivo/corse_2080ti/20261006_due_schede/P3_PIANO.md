# P3 — Finestre in pipeline con la cache elastica dello stadio 0

Fronte 3 della corsa «due schede» (3060 = CUDA0, layer 0-15; 2080 Ti = CUDA1, layer 16-47 + testa + MTP).
Fork: `Strata-2080Ti-core` @ 434ddca. Worktree di lavoro: `Strata-wt/p3`, branch `lab/p3-pipeline`.

## Conclusione

1. **Si fa**: `--pipeline-windows 2` + cache elastica su CUDA0, dietro l'opt-in `STRATA_PIPELINE_ELASTIC=1`.
   Il gestore elastico *decide* a ogni verdetto (lettura della VRAM libera, nessun lavoro sul device) e
   *agisce* solo in un punto quieto della pipeline: nessuna finestra in volo su nessuno dei due stadi, la catena
   del drafter ferma, il giro del tier adattivo finito. Quando un'azione è pendente non si lancia la finestra
   speculativa successiva, quindi il punto quieto arriva al massimo al verdetto dopo (≤ 1 finestra non sovrapposta,
   ~10-12 ms, per evento elastico; gli eventi sono rari: crescita dopo 5 s di spazio, controllo ogni 1 s; nelle
   corse 131k c'è stato 1 evento per corsa).
2. **Guadagno atteso**: quello della pipeline, +4-5 % sul default (G-pw2 63,7 / 58,4 contro G-spin 60,9 / 55,4;
   P-pw2b 63,8 / 58,2), più la crescita elastica che oggi la pipeline perde (+217..+325 esperti, ~0,3-0,45 GiB,
   hit rate 96,4 → ~97 %). Obiettivo realistico del fronte: **~63-65 / 58-59 t/s**, non 80. Gli 80 non arrivano
   dalla sola sovrapposizione finché metà delle finestre speculative va annullata.
3. **Scartate con i numeri**: righe di finestra divise (raddoppiano le letture dei pesi), draft su stadio 1 durante
   lo stadio 0 (esiste già: catena forzata `chain_kind 1`), stadio 0 di N+1 senza speculazione (impossibile: i
   token di N+1 dipendono dal verdetto di N).

## Fatti verificati nel codice (434ddca)

- `generate.cpp:4204` `el_split_ok = !multi_gpu || o.pipeline_windows == 0`; stessa condizione a `5360` (zone
  core/coda) e `7303` (`el_on`). Con la pipeline la cache di CUDA0 si apre fissa (`open_sized`).
- La pipeline (decode `generate.cpp:~10000-10560`): due verificatori per stadio (parità), `A` = finestra più vecchia
  non verificata, `B` = speculativa lanciata sullo stadio 0 appena `A` ha finito lo stadio 0, `D` = speculativa
  sbagliata che finisce e poi si annulla (snapshot GDN + replay del commit). Le finestre **girano su flag host**:
  `Verifier::service()` alza `h_flag` layer per layer (verify.cpp:3148). Quindi un `cudaDeviceSynchronize` sul
  thread del loop mentre una finestra è in volo = **stallo** (nessuno serve i layer). È il motivo vero per cui
  l'elastico va tenuto fuori dalle finestre in volo, oltre al rischio sulle slot.
- `el_shrink` (7340): copie D2D fra slot (sovrascrive slot che una finestra in volo potrebbe leggere),
  `res_upload`, `cudaDeviceSynchronize`, poi `cuMemUnmap` della coda: **non sicuro** con finestre in volo.
- `el_grow` (7390): `cuMemMap` + `cudaMemset` di slot **nuove** (nessuno le legge), `cudaDeviceSynchronize`
  (stallo come sopra), riempimenti asincroni su `adapt_stream` e pubblicazione via `pending` — lo stesso canale
  degli scambi adattivi, che la pipeline già pubblica in modo sicuro (`pl_apply`/`pl_release` con fence
  `exch_ev`).
- L'arena elastica è un intervallo VMM riservato: `base_` e `slot_offsets()` non si muovono mai (riservati per
  tutte le coppie layer×esperto). `host_res` non si rialloca. I grafi catturati restano validi.
- `slot_off_d_` del verificatore (copiato una volta all'init con `n_slots`) si usa solo con `all_resident_` o
  `device_plan_`, entrambi spenti con `set_always_publish` (pipeline). Nessun puntatore stantio.
- `pl_commit_async` non richiede servizio host (solo un grafo + evento): dopo i verdetti restano in coda solo
  commit, che terminano da soli.
- Invariante esistente (`pl_drain`): fuori dal loop pipelined e da `read_windows_pl` niente è in volo. Quindi
  `elastic_step(true)` a inizio richiesta (solo ritiro) è già sicuro anche con la pipeline.

## Disegno (opt-in `STRATA_PIPELINE_ELASTIC=1`)

1. `el_split_ok` / zone / `el_on` ammettono la pipeline quando l'opt-in è acceso. Senza l'env: comportamento
   identico a oggi (log «elastic cache requires ...»).
2. `elastic_step(request_start, e, ElPlan* defer = nullptr)`: con `defer` fa la stessa contabilità (finestra di
   stabilità, isteresi, backoff) ma **non tocca il device**: salta `apply_pending(true)` e, invece di chiamare
   `el_shrink`/`el_grow`, scrive l'azione in `*defer`. `elastic_run(plan)` esegue l'azione (con
   `apply_pending(true)` davanti, come oggi). Il percorso seriale non cambia (defer nullo).
3. Nel loop pipelined, al verdetto di `A` (non ultimo): se nessuna azione è pendente si chiama
   `elastic_step(false, ee, &el_plan)` (si auto-limita a 1 lettura/s).
4. Con `el_plan` pendente: niente prestage né lancio di `B` (conta come «below the gate»).
5. Punto quieto = ramo «fuori percorso» del verdetto con `B` non lanciato (quindi `doomed` falso), prima del
   lancio della nuova catena: si verifica che nessun `PV[st][par]` sia `in_flight()`, che la catena MTP sia
   ferma e che il thread del tier adattivo abbia finito (altrimenti si rimanda al verdetto dopo: mai attese
   bloccanti finché qualcosa può girare su flag); si sincronizzano gli stream dei due stadi e quello degli
   snapshot (solo commit/copie in coda); `pl_release` se c'è uno scambio in attesa; poi `elastic_run`.
6. Riepilogo per richiesta: «strata pipeline: elastic events N (quiet points, M windows held)».

## Argomento di sicurezza

- **Nessuna finestra legge slot che cambiano**: ritiro (copie D2D + unmap) e crescita (map + memset) avvengono solo
  con zero finestre in volo su entrambi gli stadi (verificato con `in_flight()`, non dedotto), e con il tier
  adattivo fermo (thread unito). Le finestre lanciate dopo pianificano su `host_res` già aggiornato e caricato
  su tutti i `d_res` (`res_upload` è sincrono).
- **Nessuno stallo**: le uniche attese bloccanti (sync degli stream, `cudaDeviceSynchronize` dentro
  `el_shrink`/`el_grow`, join del thread adattivo) avvengono quando niente gira su flag host; se il thread
  adattivo non ha finito si rimanda (non si aspetta), perché la sua fence aspetta finestre servite dal loop.
- **Riempimenti della crescita**: entrano via `pending` + `adapt_ev`; la pipeline li pubblica con `pl_apply` e
  rilascia la RAM solo dopo la fence `exch_ev` — lo stesso percorso già usato dagli scambi adattivi con finestre
  in volo. Uno slot nuovo non è letto da nessuno finché `host_res` non lo nomina.
- **Annulli**: l'azione non scatta mai con `doomed` vero; lo snapshot GDN e il replay del commit non toccano
  l'arena degli esperti.
- **Testo identico**: l'elastico cambia solo dove viene calcolato un esperto (GPU o CPU), come oggi in seriale;
  la pipeline resta esatta rispetto al seriale (stadio 1 non esegue mai finestre speculative).
- **Rollback**: togliere `STRATA_PIPELINE_ELASTIC` = comportamento di 434ddca.

## Altre sovrapposizioni giudicate

| Idea | Stima | Verdetto |
|---|---|---|
| Pipeline + elastico (questa) | +4-5 % sul default, elastico conservato | **fare** |
| Gate θ più alto (0,35-0,5) | P-th35 60,9/58,3, P-th50 64,5/56,8 contro θ 0,2 63,8/58,2: dentro il rumore | lasciare 0,2 |
| Righe della finestra divise in due metà sfalsate tra gli stadi | il costo per finestra è dominato da letture di pesi fisse per finestra (T medio 2,0-2,4); ogni metà rilegge pesi densi ed esperti: costo per metà ≈ 70-90 % di una finestra intera → più lento | scartare |
| Draft su stadio 1 mentre lo stadio 0 parte | già presente: dopo un verdetto «sul percorso» la catena MTP gira forzata sui draft di B mentre lo stadio 0 esegue B | nulla da aggiungere |
| Stadio 0 di N+1 senza speculazione | i token di N+1 = bonus di N + draft: noti solo dopo verdetto + draft (~2 ms) | impossibile |
| Ridurre il costo degli annulli | finestre fresche 38,9 ms contro ~34 seriali: ~5 ms persi per annullo (contesa CPU pool/PCIe: GPU-reach wait 14,8 contro 10,0) | fronte a parte, dopo P3 |

Tetto teorico della sovrapposizione: con ogni speculazione giusta il passo è max(s0, s1 + commit + draft) ≈
max(12, 17 + 0,8 + 2) ≈ 20 ms contro ~34 → ~90 t/s; con ~40 % di finestre sul percorso e ~5 ms persi per annullo
si resta a +5 %. Gli 80 t/s richiedono di alzare la quota sul percorso (draft migliori) o di abbassare il costo
dell'annullo, non altra sovrapposizione.

## Misure (fase 2)

Bracci `long_ab_run.sh` (131k, L01 + L02), base comune `CUDA_VISIBLE_DEVICES=1,0 --layer-split=16
--trim-stage-weights STRATA_POOL_SPIN_US=100`:

- `P3-1-def`: build P3, nessuna pipeline (default, elastico on) — controllo che il seriale non sia cambiato.
- `P3-1-pw`: build P3, `--pipeline-windows=2`, senza opt-in (elastico off, come oggi).
- `P3-1-pwel`: build P3, `--pipeline-windows=2` + `STRATA_PIPELINE_ELASTIC=1`.

Cancello: `P3-1-pwel` più veloce di `P3-1-def`; «strata elastic: on» nel log; righe «strata elastic:» durante il
decode senza crash; L01/L02 prosa o codice senza loop, rapporto parole distinte/totali ~0,5.

---

## Stato al 06/10 sera (fase 2 chiusa, branch `lab/p3-pipeline` @ 83c27bb, non pushato)

Il disegno sopra (drenaggio a un verdetto quieto) è stato sostituito, su richiesta dell'owner, dal passaggio
d'epoca ai **vuoti dello stadio 0** (nessuna finestra di CUDA0 in volo, la stessa fence di upstream #1122): niente
drenaggio, niente finestre trattenute.

| commit | cosa |
|---|---|
| dd8eba5 | v1: elastico accanto alla pipeline (drenaggio a un verdetto quieto), opt-in `STRATA_PIPELINE_ELASTIC=1` |
| bdaf85d | porto di upstream #1122 (pipeline + `--adapt-async 1`) |
| 1541e34 | coda elastica ai vuoti dello stadio 0, senza drenaggio; coda 1,5 GiB; elastico ammesso con `--resident-experts` |
| 5140210 | porto architectds: finestra verificata servita prima, lookup oltre una finestra, theta 0,10 |
| 12a6f55 | prestito di tutta la cache al prompt (prompt 131k da 134 s a 88 s), `STRATA_PL_EARLY_CHAIN` opt-in, latenza della catena nel log |
| ae6a456 | tabella del costo dei rollback nel log (mai girata) |
| 83c27bb | default spostati riportati dietro l'opt-in: senza `STRATA_PIPELINE_ELASTIC` il percorso è quello di 434ddca |

Profilo misurato: `--pipeline-windows 2` + `STRATA_PIPELINE_ELASTIC=1` (build-p3-5 = 12a6f55, priorità Normal):
pw 62,3 / 53,4 e 65,9 / 55,1 contro def 54,7 / 47,2 e 60,0 / 52,8 (medie 64,1 / 54,3 contro 57,4 / 50,0). Elastico
acceso nel log, crescite e ritiri durante il decode senza crash, testo regolare (parole distinte/totali 0,38-0,44
come il default). L'owner ha poi fermato tutte le prove: il rumore della macchina supera gli effetti; i numeri
vanno rifatti sul banco deterministico. Su 83c27bb non gira ancora nessun braccio.

Costi misurati dell'elastico ai vuoti: ritiro 2,6-42 ms sul thread del loop (di solito < 6 ms), crescita da 126
MiB 18-32 ms (sorgente mmap paginabile: H2D sincrona). Le 2 finestre dopo un evento costano 5-20 ms in più.

## Proposte (nessun braccio senza decisione dell'owner)

Dati da pw5a, pw5b, v5b, v5ec (Normal, theta 0,10). Finestre fresche 32-38 ms ≈ seriale (def 31-39 ms): un rollback
**non** rallenta il percorso verificato in modo misurabile. Finestre speculative sul percorso 20-27 ms: ~11 ms
risparmiati ciascuna. Sul percorso il 25-38 % delle finestre.

1. **Theta**: con i rollback quasi gratis la soglia deve restare bassa. Sotto 0,10 la calibrazione dà il 5-9 % di
   finestre sul percorso (~5 finestre a richiesta, ~0,3 %). Salire a 0,20 perde il decile 0,1 (13-26 % sul
   percorso, 12-22 finestre × 11 ms ≈ 1-1,5 % più lento). **Atteso: < ±1 %, sotto il rumore. Proposta: nessuno
   sweep, theta 0,10 nel profilo.**
2. **Latenza della catena** (dallo sblocco al B pronto: forzata 3,4-5,0 ms, fresca 3,2-4,4 ms) sul cammino critico
   di ogni finestra sul percorso (chain late 150-175 a richiesta). Toglierla del tutto: ~4 ms × ~170 ≈ 0,7 s su
   16-19 s, **≤ 4 %**. Spostare il drafter su CUDA0 ne recupera solo una parte (2-3 ms di passi MTP restano), costa
   ~0,8 GB sulla 3060 e tocca parcheggio, prefisso su disco e checkpoint. **Proposta: no.**
3. **Crescita senza stallo**: copia da paginabile a un bounce pinned su un thread di lavoro e H2D asincrona al vuoto
   successivo (lo schema del tier asincrono di #1122). **Atteso: ~0,3-0,5 %**. Basso rischio, solo con l'opt-in.
4. **Bug del default** (fuori P3, da correggere su main a parte): la regola del core del tier adattivo bloccante
   confronta gli slot dello stadio 1 con `el_core` di CUDA0. Con split + elastico gli esperti dello stadio 1 negli
   slot < el_core non ruotano mai. In 83c27bb la correzione vale solo con l'opt-in.
5. **Per gli 80 t/s**: la sovrapposizione rende al massimo ~11 ms per finestra sul percorso. Da ~64 a 80 serve circa
   il 20 % di tempo in meno per token. Le leve sono fuori dal fronte 3: più finestre sul percorso (draft migliori,
   accettazione intera più frequente) o finestre fresche più corte (stadi più veloci, hit rate).
