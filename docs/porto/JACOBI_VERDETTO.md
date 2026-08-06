# VERDETTO JACOBI — il crash ha un nome, e la leva non paga su questa scheda

*Chat parallela Jacobi, 6/8/2026. Risponde a `MANDATO_JACOBI.md`. Niente worktree
(ordine dell'utente a mandato superato): branch `jacobi` su `D:\llama-dspark`,
commit `b2b432b`.*

---

## La risposta in tre righe

1. **Il crash muto è un'eccezione C++**: `DSV4 coupled raw writes require equal
   sequence lengths` (`llama-kv-cache-dsv4.cpp:90`), **identica nel vanilla
   upstream f5919bf**. Il lookahead su DeepSeek-V4 non è mai partito per nessuno.
2. **Anche riparandolo non pagherebbe**: con le costanti già misurate, il passo
   Jacobi costa 255-1.300 ms e il pareggio col metro (8,04 t/s) richiede
   2,05-10,48 token/passo; il tetto di accettazione simulato sul nostro flusso
   reale è **1,43-1,60**. Deficit 1,4-6,6× **nell'angolo più favorevole**.
3. La leva **si compone con la residenza esperti** (scheda 24 GB), non la
   sostituisce: su esperti residenti la posizione marginale è quasi gratis ed è
   lì che la letteratura e la PR upstream misurano i guadagni.

## 1. La diagnosi del crash (mandato, parte "farlo funzionare")

**Sintomo**: carica, stampa il prompt, un token, exit muto. Nessun log, nessun
dump, nessuna statistica.

**Catena vera**: eccezione C++ non gestita → in release MSVC `terminate()` è
completamente muto → fast-fail `0xC0000409` (niente WER, niente dump).
Falsificati per strada: stack overflow (`0xC00000FD` — l'`editbin /STACK`
inseguiva un fantasma: WER attivo e zero dump lo escludevano già), DLL
disallineate (albero pulito, build coerente), interazione col buffer mappato
(l'eccezione scatta anche prima di arrivarci), scala del grafo.

**Strumentazione che resta** (branch `jacobi`, commit `b2b432b`,
`examples/lookahead/lookahead.cpp`):
- catch che **nomina l'eccezione** su stderr (exit 250/251) — senza, ogni
  eccezione del fork è un exit muto; candidata all'upstream;
- `W/N/G` da `LOOKAHEAD_W/N/G` — bisezione della scala senza ricompilare.

**Il vincolo violato**: il percorso raw-write della KV DSV4 espande i token
multi-sequenza in un reticolo denso `[sequenza × token]` e pretende lunghezze
uguali per sequenza. Il batch Jacobi (31 sequenze: 1 token per la corrente,
finestre scalate per le W, n-grammi per le G) è sbilenco per costruzione. Il
prompt passa (una sequenza), il primo batch Jacobi no.

**Dietro il primo muro, altri due** (letti in `llama-kv-cache-dsv4.cpp`):
- con `kv_unified` (stream unico) la parte compressa rifiuta ubatch con >1
  sequenza unica (riga 379-381 e 573-575) — e il lookahead forza `kv_unified`;
- la cache è **append-only**: `seq_rm` di coda rifiutata (1153-1176; il
  lookahead ne ignora il ritorno → celle fantasma), `seq_cp`/`seq_keep`
  chiamano `clear_compressed(true)` **globale** (1178-1186). Il rollback
  sanzionato è il checkpoint (è così che il server fa speculazione).

**Il disegno che funzionerebbe** (documentato per quando ci sarà la residenza):
token duplicati in copie singleton per stream (`has_coupled`=false → percorso
standard collaudato) + `kv_unified=false` (31 stream, regime del server np>1) +
modalità "scratch speculativo" nel compressore (niente persist dell'anello,
niente commit per posizioni sopra la punta committata — il meccanismo scratch
esiste già a metà: "a non-boundary decode step can target a masked scratch
row") + re-decode dei token accettati in modalità normale. Passo a due fasi,
append-only rispettato. Stimate: ~20-40 righe nella cache (gated da env,
inerte per la produzione) + ristrutturazione del batch in lookahead.cpp.

**Nota di igiene emersa**: i log di stamattina catturavano solo stdout —
l'eventuale stderr era perso a console. E il "modello piccolo" del mandato
(DSpark-draft) è arch `dflash`: pretende `ctx_other` (è una testa MTP), non può
fare da banco di prova standalone. Bonus: il suo percorso d'errore muore in
access violation invece di uscire pulito.

## 2. La misura (mandato, parte "misurarlo contro il metro") — per aritmetica

Non serviva costruire il pezzo KV per rispondere: bastavano le costanti già
misurate del ledger e una simulazione offline.

**Costo del passo** (tutte le ipotesi A FAVORE di Jacobi: FLOP GPU gratis,
dedup perfetta, banda piena 24,35 GiB/s, taglia batch della forma accoppiata,
64 ms fissi non-esperti):

| config | batch | esperti distinti | passo | pareggio richiesto (8,04) | max fisico |
|---|---|---|---|---|---|
| W15 N5 G15 | 92 | ~4.680 | 1.303 ms (870 con cache 35%) | **10,48** (6,99) | 5 |
| W4 N3 G4 | 12 | ~1.680 | 509 ms (353) | **4,09** (2,84) | 3 |
| W2 N3 G2 | 6 | ~1.100 | 357 ms (255) | **2,87** (**2,05**) | 3 |

La configurazione del mandato è **matematicamente impossibile**: servono 10,48
token/passo e il massimo fisico è N=5. La fisica è quella catalogata: una
posizione marginale costa o 62,4 ms di FLOP CPU o byte di esperti su PCIe, e
Jacobi **moltiplica i byte** (curva del working set: 92 posizioni ≈ 4.680
esperti distinti ≈ 30 GiB/passo). Il "GPU al 6%" parlava dei FLOP — e la
misura del 6/8 notte (LLAMA_GPU_DURANTE_DECODE) chiude la cornice: la GPU è
occupata il 96% del TEMPO a bassa intensità, quindi non ci sono vuoti da
riempire, solo intensità da alzare. Il decode è
byte-bound sugli esperti. Stesso muro della speculazione a batch 8.

**Tetto di accettazione** (simulatore `sim_lookahead_pool.py`: pool IDEALE di
Fu et al. — limite superiore, il pool vero fa peggio — su 1.046 token greedy
veri del nostro carico HTML; metro riconfermato 8,1 t/s nella stessa sessione):

| config | tetto token/passo | passi ad accettazione zero |
|---|---|---|
| W15 N5 G15 | **1,598** | 76% |
| W4 N3 G4 | **1,445** | 73% |
| W2 N3 G2 | **1,426** | 74% |

**Ancora esterna indipendente** (PR upstream #25784, unita il 2/8, da ricerca
della sessione DS4 L3): il drafter DSpark *addestrato* misura su traduzione
0,767·0,488·0,264·0,137·0,051 ≈ **1,71 accettati/passo** — sopra il nostro
tetto a pool (com'è giusto: drafter addestrato > n-grammi), e comunque **sotto
ogni asticella di pareggio su questa scheda**, anche con `--fit off` e la
configurazione giusta. L'autore stesso: *"performance regression with heavy MoE
layer offloading to CPU"*, *"beneficial primarily when model and drafter are
both on the GPU"*. Sul suo DGX (esperti residenti): baseline 16,4 → 19,8-39,3.

## 3. Il verdetto

**Su questa macchina (3060 12 GB, esperti su RAM host) la decodifica Jacobi/
lookahead è falsificata per aritmetica**: il tetto di accettazione (1,4-1,6)
sta sotto il pareggio (2,05 nel migliore dei casi con cache, 10,5 nella
configurazione del mandato) di un fattore 1,4-6,6. Nessuna implementazione,
per quanto perfetta, può colmarlo: è il muro dei byte-esperti, il medesimo di
speculazione batch-8, drafter CPU, lane G132 e DSpark (quarta e quinta leva
indipendente sullo stesso muro).

**La leva resta giusta nel dominio giusto**: con esperti residenti (24 GB) la
posizione marginale crolla a ~millisecondi e il pareggio scende sotto il tetto
misurato. Jacobi/DSpark si COMPONGONO con la residenza — vanno in coda alla
decisione hardware, non davanti. Coerente con `hw-verdicts` e con la curva del
working set: prima i GiB, poi il parallelismo.

**Cosa cambierebbe il verdetto**: (a) esperti residenti; (b) un carico con
tetto ≥2,9 a N=3 (il nostro HTML "ripetitivo" fa 1,43 — la ripetitività
percepita non è ripetitività di n-grammi a granularità token); (c) una banda
verso gli esperti ≥5× (non esiste su PCIe 4 x16).

## CORREZIONE 6/8 sera — l'ingrediente principale era misurato sull'oggetto sbagliato

*Da `LLAMA_ALBERO_UNIONE` (a387d32, sessione DS4 L3, su provocazione
dell'utente), aritmetica verificata qui compresa l'assunzione implicita
(trasporto addebitato su unione × 56%, cioè col tasso di colpi applicato).*

La curva batch→esperti-distinti usata sopra è misurata su token
**consecutivi** (posizioni diverse, prefissi diversi). I rami di un albero
stanno nella **stessa posizione dopo lo stesso prefisso**: la loro unione è
il 27-41% più piccola (K=8: 771 contro 1.249, raggruppamento onesto di
posizioni vere). Pareggi corretti: K=2 **1,12**, K=4 **1,33**, K=8 **1,72**
— contro il tetto di accettazione misurato 1,43-1,60 e l'1,71 del drafter
addestrato DSpark.

**Cosa cambia e cosa no:**
- La config del mandato (W15N5G15, batch 92) resta **impossibile**: anche
  con l'unione ad albero il pareggio sta a 7-9 su un massimo fisico di 5.
- Il metodo a POOL N-GRAMMI resta sotto o al pari del pareggio corretto
  (il tetto 1,43-1,60 è un limite superiore ideale; il pool vero fa meno).
- Ma a K stretto **il muro dei byte non è più ciò che decide: decide
  l'accettazione**. "Quinta leva sullo stesso muro" era la diagnosi
  sbagliata per QUESTA leva a QUESTA larghezza.
- La riga finale va riscritta: si riapre **con un drafter la cui
  accettazione superi ~1,3-1,7 accettati/passo** (il DSpark addestrato è
  già lì, 1,71, SU QUESTA SCHEDA) — oppure con la residenza, che abbassa
  il pareggio comunque. Nota il rovescio: il lookahead qui resta comunque
  bloccato dai tre muri KV (sezione 1), che tornano rilevanti SOLO se un
  drafter buono esiste.
- Caveat onesti della correzione: vicini-coerenti è un tetto (i rami veri
  condividono TUTTO il prefisso: plausibilmente unione ancora più piccola,
  non misurato); il termine di calcolo resta fisso → pareggi ad alto K
  sottostimati; la quota-cache sul batch è generosa (K1 insegna).
- **La misura che chiude**: top-K candidati a una posizione vera, K
  passaggi da un token col dump delle route, unione vera. Cinque minuti di
  macchina, accodata alla sessione della sonda confini.

**Forma finale della conclusione (6/8 sera, seconda passata — il caveat
sulla quota-cache portato ai due estremi È il risultato):**

| K | unione | contro 380 slot | pareggio (44%) | pareggio (0%) |
|---|---|---|---|---|
| 2 | 343 | **ENTRA** | 1,12 | 1,50 |
| 4 | 495 | 1,3× troppo grande | 1,33 | 1,88 |
| 8 | 771 | 2,0× | 1,72 | 2,57 |
| 16 | 1.191 | 3,1× | 2,31 | 3,62 |

Da K=4 in su l'unione NON ENTRA nella cache: è la condizione di K1 (220
slot contro 258/token → **0,0% colpi su 272.922 domande**), quindi la
colonna onesta è quella a 0% e la porta si richiude. A K=2, dove entra, il
pareggio 1,12-1,50 sta DENTRO l'accettazione misurata 1,43-1,60.

> **La larghezza dell'albero è limitata dalla CAPACITÀ DELLA CACHE, non
> dal metodo. Su questa scheda il tetto è K=2** (343 ≤ 380 slot; 495 no).

E "si riapre con la residenza" smette d'essere una frase: **la scheda da
24 GB compra la LARGHEZZA** (~2.000 slot: union(16)=1.191 entra comoda),
che è la variabile da cui dipende il resto.

**Chiusura degli assi (6/8 notte, terza passata):** la larghezza pura NON
produce token — dieci candidati nella stessa posizione danno dieci ipotesi
per UNA posizione: se ne tiene una, il testo avanza di uno, e il pareggio
minimo è 1,12. Morta per aritmetica pura, prima ancora dei byte. **La
larghezza compra il tasso per posizione (p1 sale con K); solo la
profondità produce token** (attesi = 1 + Σ prodotti-prefissi dei tassi).
Assi con unità diverse: non si sommano, si compongono.

Su questa scheda quindi: cache ⇒ K=2 ⇒ **catena di profondità 1**, e
tutto si riduce a UN numero, p1 (indovinare il token successivo):

    p1 > 0,12   se la cache regge a union 343 su 380 slot
    p1 > 0,50   se i colpi crollano (regime K1)
    p1 ≈ 0,26   n-grammi MISURATI (P(≥1) = 192/733 dal simulatore) ← IN MEZZO

La forbice non è sul metodo: **è sul comportamento della cache a 343/380
slot — vicino alla capienza, non oltre — il regime mai campionato** (K1
era sopra: 258 su 220; K3 era largo: 258 su 380). Coerenza verificata: il
batch K=2 (corrente+bozza) supera esattamente la soglia batch≥2
dell'ibrido, quindi il percorso GPU/cache si innesca.

**La misura da 5 minuti, criterio finale:** (1) PRIMARIO: tasso di colpi
a K=2 con union ~343 su 380 — l'unica variabile libera rimasta; ~44% ⇒
la catena a profondità 1 paga già con gli n-grammi; crollo ⇒ serve un
drafter con p1>0,50. (2) SECONDARIO: union(2) reale (343 è un tetto) e
accettazione per posizione, per mappare gli assi.

**ADDENDUM 6/8 notte (curva del batch a cache viva, dati DS4 L3): il
"343 su 380" era l'oggetto sbagliato per le catene.** La chiusura degli
assi dice che solo la profondità produce token — e una catena di
profondità 1 occupa DUE POSIZIONI CONSECUTIVE (t, t+1): la sua unione è
per costruzione quella dei consecutivi, **~446 > 380**, non il 343 dei
rami stessa-posizione (che appartiene alla larghezza, sterile). L'ancora
empirica: a np=2 con richieste IDENTICHE i colpi crollano da 43,1% a
**17,3%** — anche quando l'unione "entrerebbe", il regime a due token
non tiene (sfasamento degli slot; e per la catena, che è un grafo solo,
il working set 446-ciclante su 380 slot è il regime-K1 marginale). A
17,3% di colpi il pareggio della catena sale a ~1,54 token/passo →
**p1 > ~0,54**: gli n-grammi (0,26-0,29 misurati) sono FUORI anche a
K=2. Il corridoio residuo su questa scheda è UNO: **drafter addestrato
con p1 > ~0,5 nel dominio d'uso** — il primo-posizione DSpark (0,767 su
traduzione) lo supererebbe, ma va misurato qui. La "misura da 5 minuti"
cambia oggetto: non più i colpi a 343, ma l'accettazione per posizione
del drafter sul nostro carico.

## Artefatti

- Branch `jacobi` su `D:\llama-dspark` (base 394a797, commit b2b432b): catch +
  W/N/G da env. NON unito a `dspark-dsv4`: strumentazione diagnostica, si
  unisce se/quando servirà il pezzo KV.
- Log: `D:\ds4_work\llama_run\jacobi5..8*.log` (la catena exit 127 → 0xC0000409
  → eccezione nominata), `greedy600_*.txt` (flusso di riferimento + ids).
- Simulatori: `sim_lookahead_pool.py`, `costo_passo_jacobi.py` (in questa
  cartella, vedi sotto).
- Il difetto upstream (lookahead × DeepSeek-V4 rotto ovunque, muto in release)
  è materiale da issue su ggml-org/llama.cpp: la riproduzione è banale e il
  catch è il fix minimo di cortesia. Da fare coi tre controlli della regola
  "post esterni".
