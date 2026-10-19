# Batch dinamico: passaggio a caldo fra chat singola e modo agenti — 19 ottobre 2026

Fork `imanu86/Strata-2080Ti`, branch `lab/batch-dyn` (da `lab/multichat45` = e42d8af8 + documenti), worktree
`C:\Users\imanu\source\repos\Strata-wt\batch-dyn`. Interruttore opt-in `STRATA_BATCH_DYNAMIC=1`. **M** = misurato, **S** = stimato,
**C** = letto dal codice. Le misure sono nella sezione 6 (aggiornata a fine giornata).

## 0. Conclusione

- **Nessuno l'ha già fatto** (ricognizione `gh` su upstream `Niko1221/Strata`, 1885 PR e 1276 issue, e sui fork più attivi): in tutti i
  lavori gli slot `--batch N` si fissano all'avvio. Pezzi riusabili: #3095 (Vop3p, aperta: `--pipeline-windows` e drafter sulla prima
  scheda accanto agli slot; portata da noi su `lab/multichat45b`, +2,4% e basta), #1117 (nostra, cache elastica: col batch gira già fra
  due finestre, esclusa con `--batch-groups` solo perché «not validated»), #2522 (GonzMartinez, aperta: `VRAM <reserve> [device]`
  ristringe/ricresce la cache di ogni stadio), #1232 (BlueKingMuch, aperta: `--kv-grow` per slot, il precedente più vicino a slot
  leggeri), #1637 (chiusa: l'adattivo fermo nelle finestre batch era un limite di codice), #1604 (chiusa: coi gruppi in pipeline le righe
  di riempimento sovrascrivono gli slot fermi), #2527/#2528 (slot che tengono le conversazioni, non allocati a richiesta), #726 (cambio a
  caldo delle cache, esclude il batch).
- **Le esclusioni non sono limiti tecnici** (C + PR): `--pipeline-windows` con `--batch` è spenta perché il commit d'origine non la
  supportava (la richiesta sola gira sulla sessione principale, che le finestre batch non toccano: #3095 e la nostra L1 lo provano); la
  cache elastica con `--batch-groups` è «not validated» perché i gruppi tengono finestre in volo, ma il passo elastico gira solo dove
  tutto è drenato; la cache conversazioni su disco richiede `o.batch <= 0` senza un perché pubblicato.
- **Il problema misurato oggi non è il batch in sé ma la VRAM della 3060**: con `--batch 4 --batch-groups 2` le 4 sessioni di slot
  (1,46 GiB) sono allocate prima della cache, la cache elastica è spenta, la 3060 ha il prompt in buffer propri (2,88 GiB, «no loan») e
  arriva a **0 MiB liberi**: WDDM pagina, decode 24-28 t/s e prefill 340-464 t/s contro 70-76 e 700-1720 senza batch (M, banco comunità).
- **Design scelto (il più semplice robusto)**: sulla 3060 le sessioni di slot si ritagliano **pigramente dalla cache elastica** al
  primo `BGEN` e tornano alla cache dopo `STRATA_BATCH_IDLE_S` secondi senza slot; tutto il resto della chat singola resta quello della
  config senza batch (finestre in pipeline, drafter sulla 3060, cache elastica, cache conversazioni su disco, prestito del prompt). La
  2080 Ti tiene le sue sessioni di slot fisse dall'avvio (cache fissa, nessuna paginazione: costa ~1 600 slot esperti su 9 146 nella chat
  singola, -2/-5% S). Costo di un passaggio: entrata 0,1-0,5 s, uscita 0,5-1 s (S, sezione 4), più le conversazioni degli slot da
  rileggere dalla cache RAM.

## 1. Come funziona oggi (C, `src/program/generate.cpp` di e42d8af8)

| cosa | dove | quando |
|---|---|---|
| sessioni di slot (`bslot_ss[stadio][slot]`) | `cudaMalloc` + `session_init` per stadio, **prima** che la cache esperti sia dimensionata | avvio; mai liberate |
| finestre batch (`Verifier::init_slots`) | buffer `arena_b_`, staging mappato, grafi per layout di righe (`exec_bm_`, 20-30 MiB l'uno) che contengono gli indirizzi delle sessioni | avvio; grafi catturati al primo uso |
| `--pipeline-windows 2` | spenta con «not with --batch slots» salvo `STRATA_BATCH_PIPELINE=1` (L1) | avvio |
| drafter sulla prima scheda (`mtp_first`) | richiede `batch == 0` (#3095 lo toglie) | avvio |
| cache elastica | spenta con `--batch-groups > 1` (due punti, prima e dopo la risoluzione dei gruppi) | avvio |
| cache conversazioni su disco (`STRATA_CONV_DISK`) | `o.batch <= 0` | avvio |
| smistamento | `serve/server.py::generate_batched`: da sola una richiesta va sul percorso solo (`GEN`, con bozze MTP); se ne arriva un'altra viene fermata e continua in uno slot (`BGEN` con prompt + generato); uno slot rimasto solo torna al percorso solo (`_may_go_solo`) | per richiesta |

Il motore riceve `BGEN` **solo** quando il server vede più di una richiesta (slot occupato o qualcuno in attesa): è il segnale naturale per
entrare nel modo agenti, senza cambiare il server.

## 2. Il design

**Modo chat singola** (all'avvio, e dopo l'uscita): CUDA0 come senza `--batch`: nessuna sessione di slot ritagliata, la cache elastica
occupa quella VRAM, `--pipeline-windows 2` e drafter sulla 3060, cache conversazioni su disco accesa, lettura del prompt normale (non
quella concorrente di `STRATA_PIPED_CONCURRENT`), `BYIELD` rifiutato (la lettura va avanti: non c'è dove parcheggiarla).

**Entrata** (primo `BGEN`, fra due righe, niente in volo):
1. VRAM: se la 3060 ha meno di sessioni + 64 MiB + `STRATA_BATCH_DYN_FREE_MIB` (1024) liberi, la coda della cache elastica si
   restringe del mancante (`el_shrink`: gli esperti più usati della coda scendono negli slot più freddi, gli altri passano alla CPU, i
   pezzi tornano al driver, il prestito del prompt viene ripianificato). Il nucleo non si tocca.
2. Le 4 sessioni si ritagliano (`cudaMalloc`, `session_init`, `session_zero`) negli stessi oggetti `SessionState` (puntatori stabili) e
   il verificatore dello stadio 0 le lega (`init_slots`).
3. La politica elastica tiene libera `max(--elastic-reserve-mib, FREE_MIB)` finché si resta lì: la 3060 non scende sotto ~1 GB.
4. RAM: la soglia della cache conversazioni sale a `STRATA_BATCH_DYN_RAM_FLOOR_MIB` (8192) e le conversazioni parcheggiate più vecchie
   escono finché è rispettata (richiesta dell'owner, sezione 5).
5. Cache su disco delle conversazioni spenta; lettura concorrente e `BYIELD` riaccesi.

**Uscita** (nessuno slot attivo né lettura parcheggiata da `STRATA_BATCH_IDLE_S` = 30 s: o scade l'attesa della riga, o arriva un `GEN`
dopo il tempo): `Verifier::release_slots()` (nuovo: distrugge i grafi batch, libera i buffer), sessioni liberate, cache degli slot
dimenticate (le conversazioni restano nella cache RAM al punto della loro ammissione), la cache elastica ricresce **subito** nello
spazio (passi da 512 MiB, gli esperti mancanti più usati poi l'ordine del profilo, pubblicati prima della richiesta), soglia RAM e cache
su disco tornano come prima.

**Perché così e non altro**:
- riusa solo meccanismi già in produzione nel Daily (shrink/grow della cache elastica, `session_init`, `init_slots`) e un solo metodo
  nuovo (`release_slots`); il percorso della chat singola è quello del Daily senza batch, il modo agenti quello della config con batch
  (più la cache elastica che tiene 1 GB libero);
- nessun cambio nel server: il segnale è il `BGEN`;
- la 2080 Ti (cache fissa, niente monitor, niente paginazione) tiene le sessioni dall'avvio: rendere elastica anche la sua cache è il
  passo 2 (generalizzare `el_shrink` allo stadio k, ripianificare il suo prestito; #2522 lo fa via comando), da fare solo se la misura (a)
  mostra un divario.

Scartati: due processi (avvio 84 s, doppia RAM); sessioni di slot che crescono con `--kv-grow` (#1232: lo slot da 4096 celle non basta a
contesti da 100k, e ogni crescita sposta indirizzi catturati nei grafi); restringere la cache via `POST /v1/vram` dal server (#533:
spento con lo split, e il server non sa quanta VRAM servono le sessioni).

Esclusi dall'interruttore (il motore lo spegne e lo dice): `--batch-mtp`/`STRATA_PIPED_MTP` (drafter di slot legati alle sessioni),
`STRATA_PACK_PREFILL`, senza `--elastic`.

## 3. Rischi e come sono coperti (C)

| rischio | copertura |
|---|---|
| grafi batch con indirizzi di sessioni liberate | `release_slots` li distrugge tutti; i layout si ricatturano al primo uso dopo la rientrata |
| shrink con il prompt in prestito o finestre in volo | entrata solo fra due righe (`adapt_tick(true)` fatto, pipeline della richiesta sola drenata a fine richiesta, nessun gruppo in volo), mai durante una lettura: `BYIELD` rifiutato nella chat singola |
| crescita elastica coi gruppi in pipeline | `elastic_step` gira solo all'inizio richiesta (gruppi drenati) e nel decode della richiesta sola (gruppi drenati a fine lettura concorrente); nel ciclo dei gruppi nessun passo, come prima |
| riempimenti della crescita ancora in volo | `apply_pending(true)` prima di ogni passaggio; con `el_fill` non vuoto niente shrink |
| entrata che non trova VRAM | `BGEN` rifiutato con `ERR BGEN:` (il server riprova un altro slot, #1994) e sessioni liberate |
| slot che tiene una lettura parcheggiata (`BYIELD`) | l'uscita aspetta che nessuno slot sia `active` o `partial` |

## 4. Costi stimati del passaggio (S, verificati in sezione 6)

| passo | costo |
|---|---|
| entrata: shrink di 0,5-1,5 GiB (copie device-device di qualche centinaio di MB, upload tabelle, unmap a pezzi da 64 MiB) | 50-300 ms |
| entrata: 4 sessioni da 0,36 GiB (allocazione + azzeramento) e `init_slots` | 10-100 ms |
| primo uso di ogni layout batch (cattura grafo) | come oggi, 10-50 ms a layout |
| esperti tolti dalla coda della 3060 | qualche % di hit in più sulla CPU nel modo agenti (la config batch di oggi ne ha ancora meno) |
| uscita: liberazioni + crescita di 1,5-2,5 GiB dalla RAM a ~6 GB/s | 0,4-1 s |
| conversazioni degli slot | perse con le sessioni: il turno successivo riparte dalla cache RAM (al punto dell'ammissione) e rilegge risposta + nuovo turno (1-5k token, 1-5 s); parcheggiarle all'uscita costerebbe ~13 ms/1k token a slot ed è il passo 3 se la misura lo chiede |

## 5. Le due richieste aggiunte dell'owner

**RAM per modo.** Nel replay a 8 agenti con 27,5 GiB di cache conversazioni Windows è sceso a 2,9 GiB disponibili: la soglia RAM della
cache (`--conversation-cache-min-free-mib`, default 2560) teneva, ma è bassa per l'owner. Nel modo agenti la soglia sale a
`STRATA_BATCH_DYN_RAM_FLOOR_MIB` (8192) **all'entrata** e le conversazioni parcheggiate più vecchie escono subito finché è rispettata;
ogni parcheggio successivo la rispetta (sfratto LRU già esistente); all'uscita torna quella di prima. Le copie host transitorie di
un'ammissione (immagini K/V fino a qualche GB per 100k token) stanno nei 8 GB. Non è una prenotazione con `VirtualAlloc` (servirebbe un
allocatore a pool per `ConversationBuffer`, ~1 giorno): la soglia ottiene lo stesso effetto osservabile — Windows non scende sotto 8 GB
per colpa del motore — senza bloccare RAM quando non serve.

**Rotazione a caldo del nucleo della 2080 Ti.** Prima di implementarla va misurato quanto cambia l'insieme caldo: il motore ora stampa a
ogni fine richiesta e a ogni passaggio (`strata core stat`) la quota del routing recente (conteggi decaduti delle finestre, batch
comprese) servita dal nucleo fisso di ogni scheda, contro il miglior nucleo della stessa misura per quel routing, e quanti esperti del
nucleo sono fra i più usati. Se la differenza fra nucleo attuale e ideale resta piccola (qualche punto) sia nella chat singola sia con
3-4 agenti, la rotazione non vale (costo: lettura in background da SSD/GGUF degli esperti uscenti, copia RAM, isteresi). Esito in
sezione 6.

## 6. Misure

(da completare con le corse del 19/10)
