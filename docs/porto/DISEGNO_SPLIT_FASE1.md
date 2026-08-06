# DISEGNO — split sequenziale dei due rami esperti (Fase 1 del mandato overlap)

*Cantiere overlap, 6/8 sera. Documento PRIMA del codice; passa in lettura al
coordinatore per la regola del dubbio. Riferimenti: `MANDATO_OVERLAP.md` (le
otto decisioni), `PRICING_OVERLAP_CPU_GPU.md` (i numeri), lettura del sorgente
`D:\llama-overlap\src\llama-graph.cpp:1947-2182` e `ggml-cuda/cache-esperti.*`.*

## Il fatto che semplifica tutto (dalla lettura, non dal desiderio)

Il join bit-esatto della decisione 4 **esiste già nel grafo di oggi**:
`build_moe_ffn` somma gli esperti come catena esplicita di `ggml_add` su
viste per-slot **in ordine 0..5** (`llama-graph.cpp:2151-2172`). Lo split non
deve costruire l'ordine di accumulazione: deve **consegnare alla catena
esistente gli stessi sei slot nello stesso ordine**. E il meccanismo di
riordino per-token esiste già anch'esso: `ggml_get_rows` con id per-token è
usato tre righe sopra per i pesi del router (riga 1963).

## La forma del grafo per strato (Fase 1, sequenziale)

Oggi:

    selected_experts [6, n] ──► mm_id(gate) ─ mm_id(up) ─ swiglu ─ mm_id(down)
                                     ──► experts [n_embd, 6, n] ──► ×weights ──► Σ slot 0..5

Fase 1:

    selected_experts [6, n]
        │
        ▼
    PARTIZIONE (kernel device, dentro il grafo, su CUDA)
        legge dove[] della cache (strato×256→slot, già su device)
        emette: ids_cpu [k, n]   ids_gpu [6−k, n]   perm_inv [6, n]
        │
        ├─► ramo GPU: mm_id(gate/up/down) su ids_gpu — servito dalla CACHE come oggi
        ├─► ramo CPU: mm_id(gate/up/down) su ids_cpu — PINNATO su CPU, legge i MAPPATI
        ▼
    concat [n_embd, 6, n] in ordine-di-ramo (cpu k righe + gpu 6−k)
        │
        ▼
    ggml_get_rows(perm_inv) ──► experts [n_embd, 6, n] in ORDINE DI SLOT ORIGINALE
        │
        ▼
    ×weights e Σ slot 0..5 — INVARIATE, righe 2144-2172 di oggi

La catena di add non cambia di una virgola: l'ordine numerico di accumulazione
è quello di oggi per costruzione. Il riordino costa una get_rows da
4096×6×4B×43 ≈ 4,1 MiB/token ≈ **0,17 ms — è esattamente il 0,16 preventivato
dalla decisione 4** (il conto del mandato e la lettura del sorgente si
incontrano sul numero).

## Le risposte alle tre domande aperte

**1. Dove vive la scelta (decisione 7, il rischio dichiarato n.1): TERZA VIA.**
Né copia stantia sull'host (a), né sync device→host per strato (b, il killer
di DwarfStar): la partizione è un **kernel device dentro il grafo**, sullo
stream principale, che legge `dove[]` **dove kern_decidi la aggiorna** — la
mappa di residenza e la decisione di routing stanno dalla stessa parte per
costruzione, a coerenza di stream (la partizione dello strato L legge la
tabella DOPO le decisioni dello strato L−1, in ordine di stream, senza
sincronizzazioni). Zero traversate aggiuntive: gli id partizionati viaggiano
come input normali degli split (il piccolo trasferimento ids_cpu 6×4B×n è una
copia di input che lo scheduler già gestisce, dentro i 3,3 ms strutturali).

**2. Forme statiche (i CUDA graph non devono ricatturare): k FISSO.**
k_cpu è costante per costruzione (non "i non-residenti", che variano per
token): il kernel di partizione sceglie i **k id meno-residenti** (non
residenti prima; a parità, quelli senza slot da più tempo) e li dà alla CPU;
gli altri 6−k alla GPU. Le forme [k,n] e [6−k,n] non cambiano mai → niente
ricattura. Il valore: **k=2 nominale** (x*≈96 su 43 strati = 2,23/strato),
env `LLAMA_OVERLAP_K` per la bisezione senza ricompilare (0 = split spento =
grafo di oggi, il controllo A/B gratis). A k fisso la quota-CPU non è
adattiva per strato: è la v1, e l'ottimo fine (k per strato dal tasso di
colpi) è un'ottimizzazione DOPO i cancelli.

**3. L'assegnazione del ramo CPU (l'inverso del supports_op):**
`ggml_backend_sched_set_tensor_backend` esiste già ed è il pin esplicito del
nodo. Il ramo CPU legge i pesi MAPPATI in place (proprietà UVA dell'ibrido:
is_host=true, la CPU li legge dalla RAM dove già stanno — decisione 2, il
trasporto di quei k esperti SPARISCE). Il ramo GPU resta sul percorso cache
di oggi (l'ammissione vede ids_gpu [6−k, n]: n_id = (6−k)·n, forme che
kern_decidi già accetta dopo il fix stride 3fb92b9).

## Il kernel di partizione: dove metterlo

Un'op nuova nel fork, CUDA-only, sagomata come le esistenti della cache
(stessa famiglia di cache-esperti.cu, un blocco, n=6 elementi: centinaia di
ns). NON tocca kern_decidi né le tabelle: LEGGE dove[] e basta. Contratto:

    ingresso:  selected_experts [6, n] (I32, vista con stride — lettura col
               passo di riga, lezione 3fb92b9), strato
    uscita:    ids_cpu [k, n], ids_gpu [6−k, n], perm_inv [6, n] (I32, densi)
    regola:    stabile e deterministica (non-residenti in ordine di slot;
               riempimento residenti con usato==0 prima, poi ordine di
               slot) — stessa entrata, stessa uscita, sempre
    confine:   ids_cpu attraversa il confine COME INPUT DI SPLIT — la sua
               visibilità alla CPU è garantita dal sync di confine dello
               scheduler, NON dal kernel. In Fase 1 è il meccanismo
               esistente; in Fase 2 quel punto diventa LA coordinazione.
    vincoli:   (a) tutto sullo STREAM PRINCIPALE — vale oggi perché il
               prefetch DMA è morto; chi lo rianima rivede PRIMA questo
               disegno; (b) l'op deve essere CATTURABILE dai CUDA graph:
               niente lavoro host, niente allocazioni fuori dal pattern
               di pool già catturato (i graph valgono 2×: 3,99 vs 8,04)

Fallback documentato se l'op-nel-grafo si rivelasse più costosa del previsto
in integrazione: la partizione host-stantia (opzione a del coordinatore),
aggiornata ogni N token dal contatore della cache. Si perde precisione di
residenza (~60 esperti/token cambiano su 380), si guadagna semplicità. La v1
prova la terza via; il fallback resta scritto.

**Il bivio implementativo (a) op-fusa / (b) composizione-di-op, CHIUSO in
revisione (6/8 notte, un commit di deviazione poi rivertito — 4cf5efd/5ac0237):**
la (b) aveva tre buchi — dove[]/usato[] non sono tensori ggml (la facciata è
un corpo estraneo per lo scheduler, e l'init pigro della cache rompe l'ordine
al primo build); usato è uint8 che get_rows non mangia; l'argsort CUDA è
bitonico non stabile — e il suo vantaggio dichiarato (catturabilità) NON
discriminava: i kernel della cache girano già sotto i graph catturati col
pattern g_cache-per-valore. In più il costo di BUILD del grafo (~430 nodi
piccoli, per-token su CPU: llama.cpp ricostruisce il grafo a ogni ubatch)
non era coperto dalla stima a replay. Quindi (a), con tre raffinamenti che
la revisione ha regalato:
- **un solo output** [12, n] I32 (ggml è mono-output) + tre VISTE gratuite:
  righe 0..k−1 = ids_cpu, k..5 = ids_gpu, 6..11 = perm_inv → ~4 nodi/strato;
- **kernel sequenziale a un blocco** come kern_decidi: la politica si applica
  camminando gli slot in ordine — NIENTE argsort, e il buco 3 (stabilità)
  muore per costruzione;
- **g_cache passata per valore** al lancio, come kern_decidi: eredita la
  catturabilità misurata (9,26 coi graph contro 5,03 senza), legge dove[]/
  chi[]/usato[] direttamente (la validazione su chi[] uccide i dove stantii
  e gli IN TRANSITO), e l'argomento-snapshot resta il motivo per cui la
  lettura viva è sicura: le righe di L le muta solo kern_decidi(L) del token
  precedente.

## Cosa NON cambia (perimetro)

- La cache: zero modifiche. L'ammissione vede forme diverse, già supportate.
- La catena di somma, i pesi del router, weight_before_ffn: INVARIATI.
- Il percorso batch>1 e il prefill: lo split si attiva SOLO a n_tokens ≤
  soglia (stessa igiene del cancello cache: fuori dal prefill per
  costruzione, `n_outputs == n_tokens` come criterio se servisse).
- Fase 1 è SEQUENZIALE: nessun evento, nessun threadpool nuovo. La
  sovrapposizione è la Fase 2, sopra questo grafo.

## I cancelli (dal mandato, con la meccanica di misura)

- **A — bit-esattezza**: SHA identico al braccio cache W=0 su 300 token
  temp 0, stessa config (`-c 10000 -np 1 -ub 64 -b 64`, mappati, SLOT=380).
  Con `LLAMA_OVERLAP_K=0` — che significa **op NON INSERITA al build del
  grafo** (il grafo spento è STRUTTURALMENTE quello di oggi), non "forme a
  zero" — il binario deve riprodurre il braccio W=0 anche come tempo,
  **entro il rumore misurato 0,4-1,4%** (R0/R0b del 5/8): la soglia è
  dichiarata, non a occhio.
- **B — il contatore prima della velocità**: domanda **~171/token** sul
  ramo GPU (4/6 × 257 = 171,4 a k=2; il "157" del mandato era un errore di
  conto, corretto in ce08ba5), non ~17. Battito a 5 s.
- **C — i byte**: copie della sonda e tempo del ramo trasporto giù di ~26
  MiB/token equivalenti (a k=2: ~2/6 dei non-residenti × 6,6 MiB). Il t/s
  può NON migliorare: i rami sono in fila — è il cancello di Fase 2, non
  di Fase 1.

## Le due domande del revisore (6/8 notte), con le risposte nel disegno

**1. Politica di riempimento quando non-residenti ≠ k (scelta di POLICY):**
- Caso comune (≥k non-residenti; a 44% di colpi i non-residenti per strato
  sono ~Binomiale(6; 0,56), media 3,4): la CPU prende i k meno-residenti,
  e i non-residenti AVANZATI restano alla GPU col loro trasporto. Questo
  sbilancio è VOLUTO: x*≈96 < 144 significa che l'ottimo LASCIA ~1/3 dei
  non-residenti sul bus — il k fisso implementa x* in media naturale.
- Caso raro (<k non-residenti, ~6% degli strati a 44% di colpi): la CPU
  riceve residenti di riempimento, scelti per **recency inversa** (i
  residenti usati meno di recente: i più prossimi allo sfratto, il cui
  calcolo su CPU è lo spreco atteso minimo). Costo locale ~0,18-0,36
  ms/strato colpito → **~0,05-0,1 ms/token attesi**: quantificato e
  accettato in v1; il k adattivo per strato è l'ottimizzazione dopo.
- Regola scritta nel contratto del kernel (CORRETTA in revisione: la
  "recency dei non-residenti" NON ESISTE — dove[] per loro dice solo −1):
  **non-residenti in ORDINE DI SLOT ORIGINALE; riempimento fra i residenti
  con `usato==0` prima** (la seconda chance a 1 bit: usato==0 = più vicino
  allo sfratto = spreco atteso minimo), poi ordine di slot. Deterministico
  e implementabile con le tabelle che esistono. MAI duplicati.

**2. Allineamento dei pesi di gating (correttezza): i pesi NON viaggiano
attraverso la permutazione.** `weights` [1,6,n] è raccolto dai
`selected_experts` ORIGINALI (riga 1963) e resta in ordine di slot 0..5;
il riordino get_rows(perm_inv) riporta gli output-esperti allo stesso
ordine PRIMA della moltiplicazione (riga 2145) → i due lati della ×
arrivano entrambi in ordine originale, allineati per costruzione. L'unico
punto da non sbagliare è perm_inv stessa, e ha un invariante verificabile
a livello di ID, prima che tocchi un float: **perm_inv ∘ concat(ids_cpu,
ids_gpu) == selected_experts, per ogni token e strato.** Env di verifica
`LLAMA_OVERLAP_VERIFICA=1`: un kernel debug confronta gli id riordinati
con gli originali e conta i disallineamenti — il "veloce e corrotto"
diventa un contatore che urla al PRIMO token, non uno SHA divergente a
valle. Nei bracci dei cancelli si tiene acceso; in produzione spento.

## Rischi dichiarati e mitigazioni

1. **La partizione legge dove[] mentre kern_decidi la muta** (stesso stream,
   strati diversi): a coerenza di stream non c'è corsa, ma l'ORDINE dei nodi
   nel grafo va garantito (partizione L dopo mm_id L−1): da verificare che
   lo scheduler non riordini — se serve, dipendenza esplicita via
   ggml_build_forward_expand.
2. **Il pin CPU e la collocazione dei pesi**: sched_set_tensor_backend è
   documentato ma va verificato che regga un nodo i cui pesi stanno in un
   buffer che anche CUDA accetta (il conflitto di collocazione della
   decisione 7). Test dedicato prima dell'integrazione completa.
3. **k=2 fisso su strati a residenza piena**: se tutti e 6 sono residenti,
   dare 2 esperti alla CPU è un peggioramento locale (la GPU li avrebbe
   fatti in 0,13 ms, la CPU in 0,48). Accettato in v1 (a 44% di colpi è
   raro); il k adattivo è l'ottimizzazione dopo.
