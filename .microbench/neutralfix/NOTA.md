# NEUTRALFIX — log-neutralita' a flag spenti, igiene pool dedicato, semantica env, clamp thread

Data: 2026-07-29. Base: tree corrente (ds4-p4a/ non tracciato, nessun delta pendente sui due file toccati).
Deliverable: `neutralfix.patch` (in questa cartella). Nessun file del tree modificato: la patch e' stata
costruita e verificata su copie fuori-tree, poi validata con `git apply --check` sul tree reale (esito: pulito).

## Metodo

1. Letti i quattro dossier audit10 (09_neutralita, 03_pool_mutex, 02_thread_core, 04_arena_mailbox).
2. Ogni claim RIVERIFICATO sul sorgente prima di patchare (righe citate sotto = file base, pre-patch).
3. Patch costruita su copie in scratchpad (mai toccato il working tree: altri agenti lavorano sugli stessi file).
4. Verifica finale: `git apply --check` pulito dal root del repo + applicazione su copia pulita e confronto
   SHA-256 col file editato: la patch riproduce ESATTAMENTE lo stato inteso, byte per byte.

## Punto per punto

### 09-#4 (MEDIA) — riga `invalid-compose-snapshot ... resync=off` anche a flag spento — VERIFICATO, CHIUSO

Verifica: `ds4_cuda.cu:42574` inizializza `routefix1_reject="off"`; il ramo `if (routefix1_reject)` a
:42606-42620 stampa la riga anche con `DS4_CUDA_ROUTE_SNAPSHOT_RESYNC` assente (il helper memoizzato
:31913-31919 ritorna 0 ma non guarda la stampa). Il commento FATTO 1 (:42562) conferma che pre-ROUTEFIX1
quel ramo era il "veto MUTO" (solo `failures++`/`request_valid=0`).

Cura: la `fprintf` e' ora avvolta da `if (cuda_route_snapshot_resync_requested())` NEL punto dov'era
(nessuna riga del corpo RESYNC :42558-42604 toccata, come da perimetro). A flag spento il ramo torna il
veto muto pre-ROUTEFIX1: **log byte-identico al pre-patch**. Il helper e' memoizzato e gia' chiamato nello
stesso ramo (:42575): la guardia aggiunge un load+branch, zero getenv nuove, solo sul percorso di mismatch.

Scelta motivata (flag-only, NON latch una-tantum): il tema del mandato e' l'identita' al byte del log a flag
spenti — anche una sola riga latched la romperebbe. La diagnosi a freddo non e' persa: il veto resta
osservabile (cresce `failures`, il funnel a valle dice `request-invalid`), e per la riga completa si accende
il flag, che ad arena non quiescente stampa `resync=arena-busy` SENZA adottare nulla (l'adozione esige
txn nullo + hit abilitati + submission aperte + backing primario + generazione non nulla, invariato).
Effetto collaterale voluto: `resync=off` non puo' piu' comparire (quel valore esisteva solo a flag spento).

### 04-#2 (BASSA) — la riga `result=invalid` non stampa g133_epoch — VERIFICATO, CHIUSO

Verifica: `request_valid` include il termine g133 (:42537-42538, `cuda_g133_epoch_valid` = coppia non
nulla, :32410-32412), ma la riga :42546-42556 stampa solo sequence/layer/route/miss/byte: un epoch nullo
falliva invisibile con ogni campo stampato "sano".

Cura: aggiunti `g133_request_epoch=%llu g133_position_epoch=%llu` alla riga (campi
`request.g133_epoch.request_epoch/.position_epoch`, struct `ds4_gpu_g133_epoch` :890-893). La riga vive
solo sul percorso di errore (`!request_valid`): un run sano a flag spenti non la stampa mai, quindi
nessuna violazione di neutralita'; cambia solo il contenuto della riga diagnostica gia' esistente.

### 03-B1 (MEDIA) — ABA sul refcount del pool dedicato — VERIFICATO, CHIUSO

Verifica: `ds4_shared1_dedicated_acquire` :11463-11467 controlla solo `initialized` (mai `shutdown`);
l'ultimo release :11533-11548 rilascia il mutex durante la join lasciando `initialized=true`, poi azzera
incondizionatamente. Finestra confermata: acquire concorrente prende un ref fantasma; l'azzeramento lo
perde; una destroy successiva puo' consumare il ref di un'incarnazione nuova e spegnere il pool di un
terzo grafo.

Cura (identita' di generazione, due meta'):
- **acquire fallisce se shutdown in corso**: nuovo check `if (p->shutdown) return 0` prima del ramo
  `initialized`. Chiude la radice dell'ABA: nessun ref puo' nascere su un'incarnazione morente; il
  chiamante ripiega sul percorso odierno e lo dichiara (riga "dedicated pool unavailable" gia' esistente).
  Con questo, ogni release e' matematicamente sulla stessa incarnazione dell'acquire (shutdown parte solo
  a refs==0, e refs>0 lo impedisce).
- **gen counter incrementato a ogni azzeramento**: nuovo `static uint32_t g_shared1_dedicated_gen`
  (protetto da `p->mutex`); il joiner fotografa la generazione prima della join e DOPO la join azzera solo
  se invariata (altrimenti rientra senza toccare lo stato altrui). Rende l'identita' verificabile e
  future-proof.
- Il gen vive FUORI dalla struct (statico file-local) perche' il mandato vieta di cambiare layout alle
  struct condivise fra thread (`ds4_shared1_dedicated_pool` e `ds4_shared1` lo sono entrambe); per lo
  stesso motivo la meta' "gen cambiata" del check sta nel release (unico punto con una baseline attraverso
  un rilascio del mutex), non in acquire, che sotto un singolo lock non ha baseline precedente.
- Bonus: sparisce anche la menzogna del summary segnalata dall'audit (I3: `pool=dedicated` con eval
  inline) — un detentore di ref non puo' piu' vedersi azzerare il pool sotto i piedi.

### 03-B2 (MEDIA) — `DS4_G132_CPU_LANE=0` non neutro in shared1 — VERIFICATO, CHIUSO

Verifica: shared1 testava la PRESENZA (`getenv(...) != NULL`, :11963-11964); la lane CUDA arma solo con
valore esattamente `"1"` (:51141-51147); l'engine-open usa gia' `strcmp(...,"1")==0` (:22662-22663,
:22681). Unico sito a presenza nel file: :11963-11964.

Cura: nuovo helper `ds4_shared1_lane_env_active()` = `value && strcmp(value,"1")==0`, usato per entrambe
le variabili. Semantica IDENTICA al parser della lane (piu' stretta del minimo "0/false/vuoto = spento"
chiesto dal mandato, e per questo coerente anche su valori tipo "true"/"2", che la lane NON arma).
Con variabili assenti: stesso numero di getenv (2), stesso esito, nessun log — comportamento invariato.
Con `=0`: shared1 ora usa il g132 come se la variabile non ci fosse (il fix).

### 02-#3 (MEDIA) — promessa "salta i sibling SMT, mai CPU0" non garantita — VERIFICATO, CHIUSO (minimale)

Verifica: la selezione :11409-11418 e' pura aritmetica sugli ID (`cpus-1-2*tid`, wrap sui pari);
`os_cpu_count` (os_thread.c:67-71) ritorna `dwNumberOfProcessors`, nessuna topologia. Su numerazioni SMT
non a coppie adiacenti due worker possono condividere il core fisico. CPU0: il mapping che la produce
ritorna -1 e il thread resta LIBERO (lo scheduler puo' comunque mandarlo ovunque, inclusa CPU0): la
promessa onesta e' "maschere solo su ID logici alti, CPU0 mai NELLA maschera".

Cura minimale (come da mandato, niente topologia SMT):
- log dell'arm: aggiunto `mask=high-logical-ids-no-cpu0 smt=not-queried` (stampa solo a flag acceso);
- i due commenti (:11330-11335 e :11404-11408) riscritti: promettono solo cio' che il codice fa.
- Conteggio `applied=K/N` verificato ONESTO: `affinity_applied` incrementa solo su
  `SetThreadAffinityMask` riuscito (:11501-11503); thread saltati (core<0 o >=64) e fallimenti restano
  liberi e fuori dal conteggio. Nessuna modifica necessaria: documentato nel commento del log.

### 02-#4 (BASSA) + 02-#1 (guardia) — N non clampato alle CPU disponibili — VERIFICATO, CHIUSO

Verifica: il parser :11384-11397 clampa solo a `DS4_SHARED1_DEDICATED_MAX=16`; con 8 logici e
`DEDICATED=16` partono 16 compute; con NextN attivo il totale supera i core (02-#1, oversubscription che
si traveste da guasto I/O sul route worker).

Cura: in `ds4_shared1_dedicated_env_threads`, dopo il clamp a 16:
`N = min(N, max(1, os_cpu_count() - 2 - (NextN attivo ? 1 : 0)))` — il -2 riserva route worker + decode,
il -1 il thread drafter. "NextN attivo" usa lo stesso parser dell'engine-open (valore esattamente "1");
se l'open NextN poi fallisse, si riserva un core in piu' del necessario: conservativo e innocuo. Una riga
di log SOLO quando il clamp interviene (`DS4_CPU_SHARED_EXPERT_DEDICATED=%u clamped to %ld ...`).
Il blocco gira solo con `DEDICATED>0` (a variabile assente si esce prima; a `=0` `n==0` salta il blocco):
a flag spenti zero getenv e zero os_cpu_count nuove. Primo passo del budget globale, tenuto semplice:
NON tocca il dimensionamento del pool g132 ne' i suoi submitter (fuori perimetro; il budget completo
raccomandato dall'audit resta lavoro futuro).

## Neutralita' della patch stessa a flag spenti (tema del mandato)

Con `DS4_CUDA_ROUTE_SNAPSHOT_RESYNC` / `DS4_CPU_SHARED_EXPERT*` / `DS4_G132_CPU_LANE*` /
`DS4_NEXTN_CPU_DRAFTER` assenti:
- nessuna riga di log nuova o cambiata su run sano; l'unico ramo che PERDE una riga rispetto al tree
  corrente e' il mismatch compose (che torna al comportamento pre-ROUTEFIX1: questo E' il fix 09-#4);
  la riga `result=invalid` cambia contenuto ma vive solo sul percorso di richiesta malformata;
- nessuna getenv nuova (B2: stesso conteggio; clamp e NextN-check: dietro `DEDICATED>0`; guardia 09-#4:
  helper gia' memoizzato dallo stesso ramo);
- nessuna struct condivisa cambia layout (il gen del pool e' uno static file-local nuovo, non un campo);
- lavoro aggiunto a flag spenti: un load+branch nel solo ramo di mismatch compose (gia' raro e gia'
  ROUTEFIX1-instrumentato). Nessuna allocazione, nessun lock nuovo, nessuna chiamata CUDA.

## Perimetro rispettato

Non toccati: os_file.c/transiente, teardown/ledger (LEDGERFIX, `ds4_transport_*`, DOV), budget host-pin
(INDEXERZC :4017-4052, :17283-17295), corpo del RESYNC :42558-42604 (byte-identico: la guardia sta nel
ramo successivo, fuori range), indexerzc. Nessun file del tree modificato da questo lavoro.

## Applicazione e hash

- `git apply --check .microbench/neutralfix/neutralfix.patch` dal root: **pulito** sul tree corrente.
- Round-trip verificato: patch applicata a copia pulita → SHA-256 identico ai file di lavoro editati.

| file | SHA-256 base (tree corrente) | SHA-256 post-patch |
|---|---|---|
| ds4-p4a/ds4.c | 2F4555965716ADB494496E3D4EB6BF5FA1769D36BAB3527A37CEC63C1E7CBF20 | 6DB7EB31F93135BB0DFB4DA99ADDD29207BB3C4B9789A05F1F2B88EC696E14B4 |
| ds4-p4a/ds4_cuda.cu | F0DD5CFC6E001A61E818F8569E74E9AD07D536C55108418FEF7851712224BA36 | D4793C008A627DA6A7A554067A47F7063578C4F40309BA2620D0729830A15A5D |
| neutralfix.patch | — | F22F1EAADF13F4B012CE2BF9C79BB1BF93CC6B7E98ADD5D902E2FE16EF6F8FC6 |

Stat: ds4.c +91/-13, ds4_cuda.cu +38/-16 (righe, gran parte commenti di motivazione).
NON compilato ne' eseguito (vincolo di mandato): la patch usa solo costrutti gia' presenti nel file
(C99 mixed declarations, `os_cpu_count` gia' chiamata in ds4.c:746/:11491, format `%ld/%u/%llu`).
