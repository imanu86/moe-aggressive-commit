# ledgerfix — il transport ledger era cieco sotto DOV: commit differito alla prova

Data: 2026-07-29. Nessuna compilazione, nessun server, `D:\` non toccato.
Scritto solo in `.microbench/ledgerfix/`.

Base del diff: `ds4-p4a/ds4_cuda.cu` del tree CORRENTE, SHA-256
`dd1e4cd8b3b2d93c4414b6a80a2dfe153fd0bd20a11125decece4addda14ad71`.

Patch: `ledgerfix.patch`, SHA-256
`e139caff26464492c8fe6cb42bb697363887b96761240408d4f483447eef1a5d`,
`git apply --check` PASS sul tree corrente, `--numstat` +175/−14 su un solo
file. Roundtrip verificato: base corrente + patch → SHA-256
`f3ce544d4715bac82df4cdcb3eea72cdbbd9e59a76927b66056be63fc0fd8bfc`;
bilanciamento graffe verificato (6303/6303 nel file patchato, netto 0 come
la base). Le righe «:N» sotto sono della base `dd1e4cd8` salvo dove detto.

## 1. Dove il DOV sfuggiva al conteggio (la cecita', esatta)

Il registro (`DS4_CUDA_TRANSPORT_LEDGER=1`, blocco :28024-28423) conta gli
H2D cosi': il worker apre un batch per richiesta (`h2d_batch_begin`,
finestra `h2d_active`), appende una entry (layer, expert, byte) per ogni
copia ACCODATA (:41694, :41871, :42634), e committa i byte SOLO al finish
con prova di drain riuscito (`h2d_batch_finish(batch, drain_ok)`
:28249-28298: chiude la finestra e somma in `first_touch/repeat_h2d/`
`h2d_bytes_total`).

Sotto `DS4_CUDA_DRAIN_OVERLAP4=1` l'arm sostituisce il drain bloccante
(disegno drain4, I4 «versione minima»): al finish il worker non ha piu' la
prova, quindi il batch veniva **invalidato, mai committato**, in ENTRAMBI i
siti arm-riuscito:

- ENFORCE: `ds4_cuda.cu:42007-42008` (`ds4_transport_h2d_batch_invalidate`
  + `finish(&batch, 1)` su batch ormai `complete=0` → zero byte sommati);
- non-ENFORCE: `ds4_cuda.cu:42731-42732` (identico).

Ogni generazione armata perdeva TUTTI i suoi byte H2D; restavano contati
solo i ripieghi bloccanti (arm rifiutato). Ecco l'8,4 GB di FB1 contro i
3070,6 GB di FA0 a lavoro bit-identico (transienti 432.968 identici): lo
0,27% dei byte passava dal ramo bloccante, il resto spariva. In piu' la
finestra `h2d_active` veniva chiusa all'ARM (finish immediato), non al
completamento: `pcie_busy_pct` ~50% con byte ~0 → «26 MB/s», lo strumento
rotto del mandato.

## 2. Cosa ora viene contato, e dove

Principio: **la prova di completamento esiste gia', solo piu' tardi** — gli
stessi due punti che chiudono la finestra di overlap di drain4:
`cudaStreamQuery(upload)==Success` nel poll idle del worker, oppure il
claim-gate della generazione successiva (done-event dietro il waitEvent,
invariante I3). Il commit del batch viene DIFFERITO a quel punto. Nessuna
sync/barriera nuova: si riusano le query esistenti.

| pezzo | dove (file patchato `f3ce544d`) |
|---|---|
| `epoch` del registro (incrementata in `ds4_transport_clear` sotto lock) | struct :28070-28074, bump :28443-28445 |
| `ds4_transport_h2d_batch_finish_deferred(batch, epoch, drain_ok)` — corpo IDENTICO al finish (chiusura finestra + commit per-pair prima-volta/ripetizione + `h2d_bytes_total`) MA con guardia di epoca nella stessa presa di lock | :28340-28398 (disegno :28305-28339) |
| `ds4_transport_h2d_batch_defer(batch, pending, pending_epoch)` — consegna per copia allo slot pendente, fotografa l'epoca, LASCIA APERTA la finestra `h2d_active` (le copie sono davvero in volo) | :28400-28424 |
| Slot pendente nel sidecar DOV (`transport_deferred` + epoca; solo thread worker, come `arm_vetoes_logged`) | :37304-37310 |
| Commit al retire: `cuda_moe_drain_overlap4_retire` chiama `finish_deferred` con `drain_ok=credit_overlap` — via poll idle (stream query) e via retire-at-claim (claim-gate), i due chiamanti esistenti del retire | :37391-37401 |
| Sito ENFORCE: `invalidate+finish` → `defer` | :42159-42166 |
| Sito non-ENFORCE: `invalidate+finish` → `defer` (+ commento aggiornato) | :42876-42893 |
| Riga una-tantum aggiornata: `[transport] drain_overlap4=deferred ...` (dichiara la semantica e i limiti residui); commento I4 dell'arm aggiornato | :40538-40553 |

Semantica d'errore = quella classica: `credit_overlap=0` (errore osservato
sull'upload stream nel poll) → finestra chiusa, byte OMESSI, `complete=0`
— identico al trattamento del batch errato del percorso bloccante
(:28265-28268). La guardia di epoca scarta un commit che attraversa un
`clear()` (cambio richiesta): mai contaminare il registro di una richiesta
con byte di un'altra.

## 3. Perche' e' SOLO contabilita' (neutralita')

- Nessuna chiamata CUDA aggiunta o spostata: arm, fence, poll, claim-gate
  intatti nel loro testo (il poll :42127 e il retire-at-claim :42187 non
  sono stati toccati: cambia solo l'interno di `retire`, che gia' girava).
- Costo per generazione armata invariato in classe: prima
  invalidate(lock)+finish(lock) all'arm; ora defer(lock) all'arm +
  finish_deferred(lock+1 QPC) al retire. Tutto worker-side, fuori dal
  percorso GPU.
- A `DS4_CUDA_TRANSPORT_LEDGER=0`: `begin` non attiva mai il batch → defer
  e' un no-op, il pendente resta inattivo, `clear` esce prima del lock →
  zero lavoro nuovo, zero righe nuove di log.
- A DOV spento: defer/finish_deferred raggiungibili solo da istanze
  DOV=true e da un retire che a flag spento non viene mai chiamato →
  comportamento byte-identico a oggi.
- Commit ottimistico, VALID, ready, fallback bloccante: zero diff.

## 4. Criterio di accettazione (dichiarato)

Su workload identico (stesso sha del testo, stessi flag tranne
`DS4_CUDA_DRAIN_OVERLAP4`):

1. `h2d_bytes_total` sotto DOV ≈ controllo **entro pochi %** (atteso <1%:
   le fonti di scarto residue sono il batch di coda per richiesta, ≤6
   esperti ≈ 7 MB — vedi §5.1 — e i batch errati, omessi con `complete=0`
   in entrambi i bracci). Transienti gia' identici (432.968 nel fatto del
   29/7).
2. `repeat_h2d_bytes` / `first_touch_bytes`: stessa parita', perche' la
   classificazione per-pair avviene al commit e i commit restano in ordine
   di generazione (il retire precede il servizio successivo per
   costruzione: retire-at-claim sta fra claim e servizio).
3. `h2d_active_ms`/`pcie_busy_pct` tornano sensati: finestra chiusa
   all'OSSERVAZIONE del completamento (poll idle o claim), quindi limite
   superiore onesto, con lieve bias in ECCESSO (lag di osservazione) —
   dichiarato nella riga una-tantum. Il MB/s implicito (byte/attivo) torna
   nell'ordine del tubo reale, non piu' 26 MB/s.
4. `ledger_complete=1` nei run DOV puliti (prima era 0 per disegno).

## 5. Buchi residui noti (documentati, NON allargati qui)

1. **Batch di coda della richiesta**: se il retire dell'ultima generazione
   arriva dopo il report `final` (decode thread), quel batch manca dal
   final (sottoconteggio ≤1 batch); se arriva dopo il `clear` della
   richiesta successiva, la guardia di epoca lo scarta (mai contato
   altrove). Non eliminabile senza attese/sync nuove; dichiarato nella
   riga una-tantum. In pratica il poll idle lo ritira quasi sempre prima
   (il decode fa ancora lm_head/sampling dopo l'ultimo layer).
2. **Zero-copy masked / letture host-mapped**: byte PCIe mossi dai KERNEL
   (device legge memoria host), mai `cudaMemcpy` → fuori dal registro PER
   DISEGNO dichiarato (header :28031-28034). Identici nei due bracci del
   confronto; da tenere a mente per bilanci assoluti del tubo.
3. **Staged-KV** (`cuda_kv_staged_restore_to_device` :30817 e flussi KV):
   traffico H2D reale, fuori dal perimetro del registro (che e'
   expert-pair-scoped). Buco noto, invariato.
4. **Prefill**: il registro si arma al confine di decode (:30799-30801),
   il prefill e' fuori per disegno dichiarato.
5. **Drain anticipato pre-SSD** (ENFORCE, :41277-41296): resta bloccante
   anche sotto DOV e committa dal finish classico con prova — NON e' un
   buco, citato per completezza.
6. Il fail-safe «pendente gia' attivo» in defer (impossibile per
   costruzione: un solo overlap outstanding) chiude il pendente stantio
   come batch errato → gap visibile in `complete=0`, mai byte inventati.

## 6. Igiene di concorrenza sul tree

Durante la stesura il file e' oscillato `dd1e4cd8` → `57fea0c3` →
`dd1e4cd8`: un altro agente (ROUTEFIX1, snapshot-resync del precheck,
+14 righe a :31614) stava editando in place. Verificato: le sue righe sono
a >3.000 righe da ogni hunk di questa patch, e `git apply --check` PASSA
su entrambe le versioni osservate (le coordinate degli hunk assorbono lo
slittamento via contesto). Zone vietate rispettate: precheck
:42193-42286 non toccato (il punto piu' vicino modificato e' :42007, il
retire-at-claim :42173 e' solo LETTO); indexer, shared1, dspark*, logids,
lane, econ, pin2, Q1: zero diff.

## 7. SHA-256

```
dd1e4cd8b3b2d93c4414b6a80a2dfe153fd0bd20a11125decece4addda14ad71  ds4-p4a/ds4_cuda.cu (base, tree corrente al momento della verifica)
e139caff26464492c8fe6cb42bb697363887b96761240408d4f483447eef1a5d  ledgerfix.patch
f3ce544d4715bac82df4cdcb3eea72cdbbd9e59a76927b66056be63fc0fd8bfc  ds4-p4a/ds4_cuda.cu DOPO la patch (roundtrip verificato)
```
