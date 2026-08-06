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
    regola:    stabile e deterministica (a parità di residenza, ordine di
               slot originale) — stessa entrata, stessa uscita, sempre

Fallback documentato se l'op-nel-grafo si rivelasse più costosa del previsto
in integrazione: la partizione host-stantia (opzione a del coordinatore),
aggiornata ogni N token dal contatore della cache. Si perde precisione di
residenza (~60 esperti/token cambiano su 380), si guadagna semplicità. La v1
prova la terza via; il fallback resta scritto.

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
  Con `LLAMA_OVERLAP_K=0` il binario DEVE riprodurre il braccio W=0 anche
  come tempo (il controllo che lo split "spento" è davvero spento).
- **B — il contatore prima della velocità**: domanda ~157/token sul ramo GPU
  (4/6 della domanda piena a k=2), non ~17. Battito a 5 s.
- **C — i byte**: copie della sonda e tempo del ramo trasporto giù di ~26
  MiB/token equivalenti (a k=2: ~2/6 dei non-residenti × 6,6 MiB). Il t/s
  può NON migliorare: i rami sono in fila — è il cancello di Fase 2, non
  di Fase 1.

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
