# MANDATO — L'ANELLO: la VRAM tiene il CONTESTO, non i pesi

*Cantiere aperto il 7/8/2026 su richiesta dell'utente. Worktree `D:\llama-ring`,
ramo `ring`, staccato da `overlap` a `f809d21` (dove vive la SOTA).*

## L'idea dell'utente, nelle sue parole

> «il ring vero, che in VRAM tenga solo il contesto — che attualmente ci costa
> per 10k»

Oggi la VRAM da 12 GB ospita **2.566 MiB di cache esperti** (380 slot × 6,75
MiB) piu' il KV. A contesto lungo il KV cresce e i due si contendono lo stesso
spazio. La proposta e' rovesciare la priorita': **la VRAM e' spazio del
contesto**, e i pesi degli esperti attraversano un **anello di transito**
invece di risiedere in slot.

## I FATTI MISURATI CHE VINCOLANO IL DISEGNO

Non sono opinioni: sono numeri di questa campagna, e chi progetta deve
rispettarli o falsificarli **con una misura**, non con un ragionamento.

**1. La cache esperti VALE, e vale molto.** 9,26 contro 8,04 t/s (+15%) contro
la stessa config senza cache. Un anello che non tiene niente in VRAM parte da
-15%: deve ricomprarsi quel margine altrove.

**2. I colpi decidono la velocita', ma NON linearmente.** Spazzata K misurata:

```
  K=1  9,3 t/s  colpi 45,9%     K=3  9,8  colpi 64,9%
  K=2  9,9      colpi 55,4%     K=4  8,6  colpi 75,5%   <- piu' colpi, PIU' LENTO
```

Esiste un punto oltre il quale alzare i colpi **peggiora** il token. Chi
progetta l'anello deve dire **quale grandezza** ottimizza, e non puo' essere
"il tasso di colpi".

**3. IL PREFILL NON SCALDA LA CACHE, ed e' probabilmente il difetto che
l'anello risolve davvero.** Il cancello d'ammissione accetta solo `batch <= 8`;
il prefill gira a `ub 64` e passa **fuori** dal percorso della cache. Quindi
dopo ogni prompt lungo il decode **riparte a cache fredda**. Misurato oggi:

```
  prompt   64 token   colpi 55,4%   ->  9,9 t/s @ 300 token
  contesto  6.000     colpi 36,3%   ->  8,8
  contesto 28.000                   ->  7,5
```

In una chat vera ogni turno paga questo. **E' la conseguenza pratica piu'
grossa che abbiamo trovato oggi.**

**4. La memoria degli esperti e' BLOCCATA per costruzione.**
`ggml-cuda.cu:1345` alloca `CUDA0_Mapped` con `cudaHostAlloc(cudaHostAllocMapped)`:
72,6 GB **non paginabili**, perche' la GPU li legge via PCIe in zero-copy.
Conseguenze: il muro della RAM e' a **23 GB, non 96**; e **il pinning e' cio'
che rende possibile lo zero-copy** — un anello che rende paginabili gli esperti
deve reintrodurre una copia sul cammino freddo, che e' gia' il dominante (598
letture per token).

**5. Il trasporto NON e' il collo.** `-dio` ha azzerato 63 MB/s di traffico
disco reale e il t/s si e' mosso di **0,01**. E la sovrapposizione CPU/GPU e'
satura: l'attesa GPU e' **piatta a 45 ms** su tutta la spazzata K, perche' sono
attenzione + grafo di join, dove la CPU non puo' lavorare **per dipendenza**.

## LA DOMANDA DEL MANDATO

**Qual e' la politica di VRAM che massimizza i token al secondo A CONTESTO
VARIABILE, e l'anello e' il meccanismo giusto per attuarla?**

Sotto-domande, in ordine di costo crescente:

1. **Quanto costa davvero il contesto oggi?** La spazzata (10k/32k/64k/128k,
   generazione 300 e 1200) e' in corso: i risultati stanno in
   `ctx_*_text.txt` e nel ledger. Leggerli **prima** di progettare.
2. **Il cancello del batch e' la leva a costo zero?** Se il prefill potesse
   popolare la cache, il decode non ripartirebbe freddo. Perche' il cancello
   e' a 8? E' igiene o e' un vincolo del kernel? **Questa e' la prima cosa da
   verificare: potrebbe valere piu' dell'anello intero e costare una riga.**
3. **Serve un anello, o serve una cache DIMENSIONATA sul contesto?** Una
   politica che riduce gli slot quando il KV cresce e' molto piu' semplice di
   un anello di transito, e usa meccanismi gia' provati.
4. Solo se le prime tre non bastano: **l'anello vero**, col suo costo di copia
   sul cammino freddo dichiarato e misurato.

## REGOLE (non negoziabili, pagate care)

- **Protocollo macchina**: `docs/porto/PROTOCOLLO_MACCHINA.md`. Nessuna run
  senza `[RICHIESTA MACCHINA]` all'arbitro.
- **Convenzione SOTA (ordine dell'utente 7/8)**: un t/s si scrive **sempre**
  col numero di token a cui e' misurato, ed e' la **generazione**, prefill
  escluso.
- **Cancello del testo**: nessun numero di velocita' vale senza il conteggio
  del 5-gramma piu' ripetuto **nello stesso messaggio**. Sano < 5; degenere
  visto fino a 576. Strumento in `docs/porto/cancello_testo.ps1`.
- **Una variabile per braccio**, e verificata sul **file eseguito**, non sul
  nome del braccio.
- **`n >= 3`** per ogni punto di una curva, non solo per i verdetti.
- **Lanciare STACCATO** (`llama-cli` non esce dopo il footer), **nomi di file
  univoci** (i bat troncano), e **guardare il disco prima di lanciare**.
- **Committare il binario PRIMA di girarlo**, o la provenienza del numero e'
  irrecuperabile.

## STATO DA CUI SI PARTE

```
SOTA        9,9 t/s @ 300 token   (K=2, -t 7, ASYNC=1, SLOT=380, W=0, ctx 10k)
            8,8 @ 300 token con contesto  6.000
            7,5 @ 300 token con contesto 28.000
worktree    D:\llama-ring  ramo `ring`  da overlap f809d21
```

Il ledger e' `docs/porto/LEDGER_RUN.tsv` (165 righe). Le memorie che contano:
`sota-99-overlap-fase2`, `overlap-fase2-tetto-cpu`,
`paging-contamina-i-bracci-col-drafter`, `capienza-cache-decide-tutto`,
`vram-libera-batte-gli-slot`, `strumenti-che-mentono-in-silenzio`.
