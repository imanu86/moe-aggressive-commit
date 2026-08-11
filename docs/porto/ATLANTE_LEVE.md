# ATLANTE DELLE LEVE — inventario per la composizione

**A chi legge (agente Codex o umano): questo documento è costruito dal CODICE e
dagli SCRIPT, non dalla memoria di chi lo scrive.** Ogni tabella qui sotto è
estratta meccanicamente. Le mie letture stanno in un solo posto, la §6, e sono
marcate come tali perché tu possa **scartarle**.

Lo scopo non è ripetere quello che sappiamo. È il contrario: mostrare **cosa
esiste, cosa è stato provato, e soprattutto cosa NON è mai stato provato** — in
particolare le combinazioni. Diverse leve promettevano +20/25% da sole e hanno
dato zero; nessuno ha mai verificato se il motivo è che vanno composte.

---

## 1. Le 77 leve, dalla tabella del manifesto di lancio

Fonte: `tools/server/server.cpp`, la tabella che il server stampa all'avvio con
provenienza `(E)=ambiente / (D)=difetto`. È la verità del binario, non una lista
scritta a mano.

| categoria | quante |
|---|---:|
| `cache` (cache esperti + cache bozza) | 17 |
| `spec` (speculazione, AcceptMoE) | 8 |
| `compute` (overlap CPU∥GPU, fusioni, mapped) | 10 |
| `kv` (anello KV, rollback, ring) | 10 |
| `vram` (VRAM a fasi, zavorra) | 8 |
| `reap` (reap-loop) | 17 |
| `diag` | 7 |
| **totale** | **77** |

Per l'elenco completo con i difetti: eseguire il server e leggere le righe
`srv server_manif:`, oppure `grep '{ "' tools/server/server.cpp`.

## 2. COPERTURA: cosa è stato davvero provato

Estratto da **160 script** in `D:\ds4_work\llama_run\*.ps1`, cercando ogni
assegnazione `$env:LLAMA_*` / `$env:GGML_*`.

**54 leve su 77 compaiono in almeno uno script. 33 non compaiono in nessuno.**

### 2a. Mai toccate da nessuno script

```
  cache     LLAMA_CACHE_ESPERTI_FORK_BLOCCHI      difetto 32
  cache     LLAMA_CACHE_ESPERTI_SPIN              difetto 256
  spec      LLAMA_ACCEPTMOE_BATCH_MAX             difetto 8
  spec      LLAMA_ACCEPTMOE_SOGLIA                difetto 0
  spec      LLAMA_ACCEPTMOE_SPIA                  difetto 0
  compute   LLAMA_OVERLAP_VERIFICA                difetto 0
  kv        LLAMA_KV_POSMIN_VERO                  difetto 0
  kv        LLAMA_KV_RING_VRAM_TRACE              difetto 0
  kv        LLAMA_KV_ROLLBACK_MARGINE             difetto 4
  kv        LLAMA_RING_BATTITO                    difetto 60
  kv        LLAMA_RING_PROFONDITA                 difetto 380
  vram      LLAMA_VRAM_A_FASI_SLOT                difetto 0
  vram      LLAMA_VRAM_A_FASI_SLOT_MAX            difetto 1024
  reap      (17 leve, tutto il sottosistema)
  diag      (5 leve)
```

### 2a-bis. RIABILITATA l'11/8: `LLAMA_CACHE_ESPERTI_FORK`

Stava qui sotto come «sempre 0». **Vale +5,5% sul banco senza lane CPU**, ed era
spenta per un verdetto preso nel regime sbagliato.

```
  banco sc_rif (spec OFF, ASYNC=0, IBRIDO=0, 512 slot), 600 token
    FORK=0   11,28 t/s   ciclo 88,7   SHA 5CD5806D6CA0
    FORK=1   11,90       84,0         SHA 0EFF1EBB450C
    FORK=2   11,92       83,9         SHA 0EFF1EBB450C   (sonda gratis)
  sonda: join visti 19.730 | copia gia' finita 19.613 (99,4%)
```

L'unica misura precedente era `c2_k2fork` (9/8, `audit/32-seconda-posizione.md`):
12,95 contro 12,83, cioe' +0,9%, **con la lane CPU accesa a K=2** — dove
`kern_copia` muove 0,08 GiB e non c'e' niente da coprire. Sul banco senza lane
`kern_copia` e' 37,87 ms/token, il 41% di una GPU satura al 97,3%.

**ATTENZIONE, due condizioni:**
- **non e' bit-esatta**: spezza il matmul esperti in due passate (residenti
  mascherati, poi i mancanti dopo il join) e l'ordine di somma cambia gli
  arrotondamenti. Lo SHA cambia per costruzione, quindi i COLPI non sono
  confrontabili fra `FORK=0` e `FORK>=1`; il t/s end-to-end si'.
- **con un walker concorrente aborta**: `ggml_cuda_cache_esperti_fork_fase`
  chiama `GGML_ABORT` se la terna gate/up/down cambia stream. Da verificare con
  `LLAMA_OVERLAP_ASYNC=1` prima di portarla nella configurazione adottata.

### 2b. Presenti negli script ma SEMPRE allo stesso valore letterale

Queste hanno un nome, un codice dietro e un audit che le descrive, e **nessuna
corsa le ha mai spostate**:

```
  LLAMA_CACHE_ESPERTI_SCUDO             sempre 0   (protezione dei predetti)
  LLAMA_CACHE_ESPERTI_MASSA             sempre 0   (politica a massa)
  LLAMA_CACHE_ESPERTI_CURA              sempre 0   (scadenza previsioni)
  LLAMA_CACHE_ESPERTI_CODA_MAX          sempre 0
  LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO   sempre 0
  LLAMA_CKPT_CRONO                      sempre 0
  LLAMA_SPEC_CONF_ESENTA_POS0           sempre 0
  LLAMA_KV_ROLLBACK_SOLO_ANELLO         sempre 0
  LLAMA_VRAM_A_FASI_MARGINE / _MIN      sempre 0
  LLAMA_VRAM_A_FASI_UB                  sempre 64
  LLAMA_CACHE_BOZZA_BATTITO             sempre 200 (difetto del codice: 60)
```

**Cautela sul metodo**: alcune leve compaiono negli script come `$p.X`, cioè
variabili di spazzata. Il mio estrattore non ne vede i valori, quindi voci come
`PF_TUTTI`, `ORACOLO`, `OVERLAP_SPIN`, `ACCEPTMOE_ESATTE`, `*_SINKHORN_ITERS`
risultano «sempre []» ma in realtà **sono state variate**. Non fidarti di quella
riga: ricontrolla nello script.

## 3. Le fonti primarie: 68 audit

`audit/*.md` nel ramo `overlap`. Ognuno contiene, con le parole di chi l'ha
scritto, l'**attesa dichiarata prima** della misura e il **cancello**. La
marcatura convenzionale è `[MISURATO]` / `[CONTATO]` / `[DEDOTTO]` / `[IPOTESI]`
(vedi `audit/30-attenzione-mla.md` §0 per la legenda).

Quelli che descrivono un sottosistema per intero, utili per la composizione:

```
  14-leve-overlap            le leve di overlap, cancelli e domini
  19-reap                    il reap-loop (17 leve, mai accese)
  20-leve-trasversale        censimento di TUTTE le leve d'ambiente
  40-vram-a-fasi             i livelli 0/1/2, la ricarica calda, il ledger delle transizioni
  42-cache-esperti-intera    il file intero, tredici reperti ancora aperti
  43-cammino-bozza           da dove viene p1 e chi lo muove
  44-overlap-macchina        il sottosistema che dà il nome al ramo
  46-dormienti               ring-esperti, reap, kv-ring: cosa dorme
  47-default-che-danneggiano ogni difetto del binario e quali ci danneggiano
  56-kernel                  i kernel: dove sta il muro e perché
```

## 4. LE LEVE CHE PROMETTEVANO MOLTO E HANNO DATO ZERO

Ognuna fa **esattamente quello che dichiara** — è stato verificato con contatori
— e **non arriva al ciclo**. Questa è la lista che merita una rilettura fresca,
perché nessuna di queste è mai stata composta con le altre.

**CORRETTA il 10/8 sera** dopo che un agente ha riletto il trascritto grezzo
(`RECUPERO_SESSIONE.md` §1): due righe di questa tabella erano sbagliate, e
sbagliate nella direzione comoda -- «nullo» invece di «dannoso», «mai
misurato» invece di «misurato male».

| leva | cosa fa, verificato | effetto sul ciclo |
|---|---|---|
| prefetch (`_W`, `_PREFETCH_FILTRO`) | copia in anticipo, colpi fino al 78% | **da −15% a −44%**, non ~0 |
| `LLAMA_ACCEPTMOE` | −349 GiB di trasporto misurati | ~0 |
| capienza (`_SLOT` 339→480) | colpi 54,0 → 63,8% | **−8,8%** |
| join asincrono | sync −30% misurato | ~0 |
| `LLAMA_OVERLAP_SPIN` | da 2M a 0 | 0 |
| `LLAMA_VRAM_A_FASI` livello 1 | restituisce 506 MiB, SHA identico | 0 (e non serve piu') |
| K frazionario | 6 bracci esistono (K 1,5/2,0/2,33/2,5) | **misurati PRIMA della correzione del parser `atoi`/`atof` (979efd899): contaminati, mai rifatti** |
| D2R (fusione) | dichiarato +25% dall'upstream | non ancora misurato |
| checkpoint | 2,36 ms/ciclo | 1,6% |
| `ub` 64 → 1024 | prefill x4,5 | **0 sul decode: e' gratis** |
| `ub` 1024 → 2048 | 4 passate invece di 7 | **−47% di prefill**: il termine per token triplica |

**La domanda aperta, mai affrontata**: sono nulle perché il ciclo è saturo per
un'altra ragione (e allora comporle non serve), oppure ognuna toglie un pezzo
diverso di un tempo che poi viene riempito da un'altra causa (e allora comporle
è l'unico modo di vederle)? **Il braccio con tutte le leve accese insieme non è
mai stato eseguito.**

## 5. Vincoli fisici misurati, da rispettare in qualunque composizione

Fatti, non letture:

```
  RAM bloccata          tetto ~78.300 MiB. Esperti mappati 74.304. Il KV
                        compresso cresce di 6,6 MiB ogni mille token.
  VRAM condivisa        Windows la limita a ~76,7 GB; i mappati ne usano 74,3.
  VRAM dedicata         12.288 MiB. Desktop 600-700. Parte densa 7.384.
                        Cache esperti 6,75 MiB per slot.
  PCIe                  Gen4 x16. DUE NUMERI INCOMPATIBILI, non uno:
                        24,35-24,46 GiB/s dal microbanco (400 x 6,75 MiB in
                        108,28 ms; copia da 54 MiB) contro 18,4 GiB/s
                        dall'audit. IPOTESI non verificata: 24,4 e' copia
                        sintetica da RAM pinnata, 18,4 e' lettura a domanda
                        da memoria mappata. Finche' non sono etichettati,
                        usare 18,4 come costante fisica unica E' SCORRETTO.
  deriva del banco      2,4% fra due corse identiche con SHA identico.
                        Qualunque verdetto sotto il 3% va rifatto.
  ricattura grafo CUDA  ~50 ms a ogni cambio di taglia del batch.
  sfratto sequenziale   ~0,07-0,08 ms per slot per ciclo, DEDOTTO da tre
                        punti (339/448/480) con deriva 2,4%: e' una pendenza
                        fra bracci, non una misura diretta del termine.
  contesto 104k         CARICA, verificato due volte (ub 64: VRAM 419 MiB,
                        prefill 22,61, decode 9,71 -- ub 512 con indexer
                        fuso: VRAM 965, prefill 75,62, decode 9,81).
                        Quello che manca e' la velocita' a CODA 102k-110k.
  ripristino slot       meccanicamente funziona (0,68-0,78 s, 23.693 token,
                        233,5 MiB) ma la richiesta successiva ri-prefilla
                        tutto lo stesso, anche con LCP similarity 1,000 e
                        anche con LLAMA_KV_POSMIN_VERO=1. Causa ignota.
```

## 6. LE MIE LETTURE — da verificare o scartare

**Tutto quello che segue è interpretazione mia, non misura.** È qui perché tu
possa contraddirla, non per essere ereditata.

- Credo che la caduta a 448/480 slot venga per due terzi dalla scansione di
  sfratto e per un terzo dal p1 che si sposta. **Non l'ho separata**: servirebbe
  un braccio a 448 slot con lo sfratto reso economico.
- Credo che qualunque leva sposti il confine CPU/GPU paghi un pedaggio sulla
  bozza, perché DSpark legge gli stati interni del bersaglio. Ho tre conferme
  (AcceptMoE, rollback KV, capienza) ma l'effetto è **erratico**, quindi
  potrebbe essere un artefatto di tre casi scelti male.
- Credo che il ciclo sia «inchiodato» a ~145-150 ms e che nessuna leva lo muova.
  Questa credenza ha già impedito di provare la composizione, quindi è
  esattamente quella da attaccare per prima.
- Ho una preferenza per il decode rispetto al prefill che non è mai stata
  giustificata da un profilo d'uso reale.

## 7. Cosa chiedo a chi legge

1. **Rileggi il codice, non questo documento.** I riferimenti servono a trovare
   i file in fretta, non a sostituirli.
2. **Cerca le composizioni non provate**, in particolare fra i sottosistemi che
   nessuno ha mai acceso insieme: VRAM a fasi × capienza × overlap ×
   speculazione.
3. **Contraddicimi sulla §6.** Le premesse sbagliate di chi coordina sono
   costate più delle leve mancanti: in una sola giornata otto agenti su otto ne
   hanno corretta almeno una, e ogni volta il valore è venuto da lì.
4. Ogni proposta deve arrivare con **l'attesa dichiarata prima** e il **cancello**
   che la falsifica, nel formato degli audit esistenti.
