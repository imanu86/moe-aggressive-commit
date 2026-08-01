# MANDATO — chi mangia la VRAM prima che la cache esperti venga dimensionata

LAVORO DI LETTURA E DIAGNOSI. **Non modificare nessun sorgente, non compilare, non lanciare
run.** Il prodotto e' un rapporto. Ho gia' sbagliato cinque ipotesi di fila provando a
indovinarlo dall'esterno, quindi stavolta si legge il codice.

  DOVE LEGGI:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a   **SOLA LETTURA**
  DOVE SCRIVI: solo `FREE_AT_SIZE_ANALISI.md` nella radice di quel worktree.

**Non usare git per scrivere.**

## IL FATTO, misurato oggi su macchina pulita

Run completo, 64 token, ctx 8000, binario `build-native/ds4_server.exe`, modello
`C:\ds4-models\ds4-2bit.gguf` (NVMe), VRAM a 297 MiB all'avvio, zero altri processi.

```
[iq2-expert-cache-size] result=sized requested=320 capacity=135
    per_expert_bytes=7077888  total_mib=911.2  free_at_size_mib=1045.2  reserve_mib=128.0
CUDA resident expert cache ready: 135/320 experts
```

L'aritmetica torna: `(1045,2 - 128) / 6,75 MiB = 135`. **Il problema non e' il calcolo: e' che
al momento del dimensionamento ci sono solo 1045 MiB liberi.**

Il riferimento della campagna, stesso ctx 8000, otteneva **capacity 253**, che richiede
~1,7 GiB liberi. **Mancano circa 700 MiB e non so dove siano finiti.**

Conseguenza a valle, ed e' il vero danno:

```
[vram-prio] ANOMALY evict_backbone=... victim_category=backbone reason=no-expert-victim
evict_backbone=70877   in 64 token   ->  ~1100 sfratti del backbone PER TOKEN
```

Con 135 slot il selettore non trova mai un esperto sacrificabile e sfratta il **backbone**, che
serve al 99,84% dei token. Richieste anche da 96 byte lo innescano.

## COSA DEVI RISPONDERE

**(1) Chi calcola `free_at_size_mib` e quando.** File e riga. In che punto della sequenza di
avvio viene chiamato rispetto a: allocazione del backbone, allocazione del KV, workspace
dell'attenzione, arena host pinnata, scratch del prefill.

**(2) L'inventario di cosa occupa la VRAM in quel momento**, voce per voce, con il codice che
la alloca. I 12,0 GiB totali meno i 1045 MiB liberi fanno ~10,9 GiB: **voglio sapere di chi
sono**, non dedurlo. Il log dice `CUDA startup cache excluded 72.56 GiB of routed-expert
tensors` e `backbone_reserve_mib=1536.0`: verifica se quei numeri quadrano col resto.

**(3) Quali variabili d'ambiente spostano quel bilancio**, e in che direzione. Per ciascuna:
dove viene letta, cosa libera o occupa, e **se ha un prerequisito**. Le candidate che conosco,
ma non fidarti dell'elenco:

```
DS4_CUDA_STREAM_RESERVE_MB=1024        DS4_CUDA_STREAMING_EXPERT_CACHE_RESERVE_GB=0.125
DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB=2      DS4_CUDA_STREAM_HOT_RESERVE_MB
DS4_CUDA_RELEASE_PREFILL_SCRATCH       DS4_CUDA_NO_Q8_F16_CACHE=1
DS4_CUDA_KV_MANAGED / KV_STAGED_RING   DS4_CUDA_PREFILL_TIER_RESERVE_SLOTS=128
```

**Un fatto verificato che ti risparmia una pista**: `STREAM_FROM_RAM_MASKED_BUDGET_GB=2` viene
letto (`masked_budget_mib=2048.0` nel log) ma **maschera zero** (`masked_mib=0.0`), e `capacity`
resta 135. Se capisci **perche' non maschera** e cosa gli serve per farlo, e' probabilmente la
risposta all'intera domanda.

**(4) La scelta della vittima**: dove si decide, e perche' con 135 slot arriva a
`reason=no-expert-victim`. Esiste una soglia sotto la quale gli esperti diventano tutti
non-sacrificabili? Il backbone puo' essere escluso dai candidati?

**(5) Il ctx cambia il bilancio?** Il riferimento e' ctx 8000, noi anche. Ma il KV e il
workspace dell'attenzione a 8000 quanto occupano davvero, e sono allocati **prima** o **dopo**
il dimensionamento della cache?

## COME RISPONDERE

- **Ogni affermazione con file:riga.** Se e' un'ipotesi, scrivi che lo e'.
- Se una delle mie premesse e' sbagliata — per esempio se `capacity 253` a ctx 8000 non e'
  ottenibile con questo binario — **dillo subito**: e' l'informazione piu' utile, perche'
  starei inseguendo un bersaglio che non esiste.
- Finisci con **l'ordine di verifica a variabile singola**: cosa provare per primo, e **cosa
  deve cambiare nel log** se l'ipotesi e' giusta. Non voglio accendere leve e interpretare
  dopo.
- Rispondi in italiano.
