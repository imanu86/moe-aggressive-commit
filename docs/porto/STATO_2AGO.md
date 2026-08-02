# STATO — notte fra 1 e 2 agosto

## Il fatto che ribalta la serata

Tutti i numeri di velocita' del 1/8 sono stati misurati col binario del **fork**
(`ds4-p4a`, ramo `codex/prep4-mtp-secondary-map`), che si stacca da upstream il
**12/05/2026** ed e' indietro di **314 commit**. Niente DSpark (2 riscontri contro
1224), niente Markov (0 contro 169), niente route Q4_K nel dispatcher CUDA.

Il tronco coi 14 blocchi (`ds4-port`, ramo `port/upstream-substrate`) fino alle
23:43 del 1/8 aveva girato **quattro volte per un massimo di 200 token**, e mai
coi pesi nuovi: i pesi 0731 sono arrivati su C: alle 20:59, i bracci del tronco
sono delle 18:57-19:40.

**Il lavoro della giornata non era mai stato misurato.**

## Le quattro celle, misurate la notte del 2/8

Stesso prompt (campagna HTML, sha `38f6ec5e...`), ctx 10000, pesi
`DS4-0731-IQ2XXS.gguf`, `DS4_METAL_PREFILL_CHUNK=256` ovunque.

| cella | arena | `--ssd-streaming` | REGIME | prefill | RAM libera | page cache |
|---|---|---|---|---|---|---|
| fork (riferimento, motore di maggio) | 30 GiB | n/d | **4,49** | — | — | — |
| tronco, solo streaming | no | si | **2,73** | 19,0 s | 50,0 GB | 3,6 GB |
| tronco, arena + streaming | 30 GiB | si | **1,70** | 66,6 s | 4,0 GB | 3,5 GB |
| tronco, solo arena | 30 GiB | no | **non parte** | — | — | — |

Log: `C_234337` (arena+streaming, interrotto a gen 600), `C_235432` (solo arena,
zero token), `B_235634` (solo streaming). Ledger:
`D:\ds4_work\porto_run\LEDGER_RUN.tsv`.

### Cosa dicono

**1. La nostra arena sul tronco costa il 38%** (2,73 -> 1,70). Duplica un lavoro
che upstream fa gia' per conto suo, e in piu' pinna 30 GB che non puo' restituire:
la page cache crolla a 3,5 GB, **91.870 hard fault al secondo**, cinque ricarichi
del modello durante il decode.

**2. Il substrato nudo costa comunque il 39%** rispetto al fork (4,49 -> 2,73).
Causa da stabilire. **Non e' tutta colpa del porto.**

**3. `--ssd-streaming` e' obbligatorio su questo hardware.** Senza, upstream vuole
il modello intero in host: sale 16,37 -> 27,52 -> 32,07 -> 39,99 -> 47,77 -> 48,43
GiB, poi chiede 1,79 GiB per lo span 99 e muore. Il modello e' 80,76 GiB, la RAM 64.

**4. Quindi DSpark e' bloccato per costruzione.** `--dspark` pretende `--mtp`
(`ds4.c:55951`), `--mtp` e' rifiutato con `--ssd-streaming` (`ds4.c:56365`), e
`--ssd-streaming` non si puo' togliere. Non e' un guardiano da aggirare: e' una
conseguenza.

## La cucitura, trovata

`ds4.c:56805-56812`:

```c
if (!accelerator_cache_model_tensors(...)) {
    fprintf(stderr, "ds4: %s failed to prepare optional model cache\n", ...);
    ds4_engine_close(e);      // "optional", e poi chiude il motore
    return 1;
}
```

**Il messaggio dice *optional*, il codice tratta il fallimento come fatale.** Il
ramo di ripiego — servire i byte dall'arena invece che da quella cache — non
esiste. Se esistesse avremmo il modo *pigro servito da noi*, e `e->ssd_streaming`
resterebbe falso, quindi cadrebbe anche il blocco di DSpark. **Una cura, due
risultati.**

Il bivio del caricamento e' a `ds4.c:56636`: con streaming la mappa iniziale e'
ristretta all'embedding, senza si passa la lista completa degli span.

## L'ipotesi aperta: il modello non entra mai in page cache

Con 50 GB di RAM libera la page cache resta a **3,6 GB**. Un file letto
normalmente ne occuperebbe decine. Sospetto: upstream apre il modello **senza
buffering**. Se confermato, spiega in un colpo solo i 48 MB/s a coda 2 del fork,
i 518 MB/s di paging del tronco, e il fatto che aggiungere RAM non aiuterebbe.
**Da verificare nei flag di apertura del file.**

## Prossimi passi

1. **Codex**: progettare il ripiego a `ds4.c:56805` — cosa si rompe a valle se
   quella cache non c'e', e quale chiamata deve trovare l'arena. Piu' la verifica
   dei flag di apertura del file del modello.
2. **Misurare** perche' il substrato nudo costa il 39% in piu' del fork.
3. **Non riaccendere l'arena sul tronco** finche' la cucitura non c'e': oggi e'
   solo un peso.

## Igiene, imparata a caro prezzo

- L'output ora arriva su disco **mentre esce** (`curl` in streaming su
  `<tag>.stream.ndjson`): due run della serata hanno perso il testo perche'
  `Invoke-RestMethod` lo teneva in memoria fino alla fine.
- `docs/porto/cataloga.ps1` cataloga un run **a posteriori** dal solo log, quando
  l'harness muore prima di scrivere meta e ledger.
- I run lunghi si lanciano **staccati** da Claude (`Start-Process`), altrimenti
  muoiono con la sessione.
- Durante un run non si tocca C:: un `git add` con l'albero pieno di directory non
  tracciate ha dimezzato la velocita' per sei minuti.
- Lo spegnimento senza token esiste: `CTRL_BREAK_EVENT` chiama la stessa
  `server_request_stop()` dell'endpoint (`ds4_server.c:167-176`).

---

# PORTO v2 — le variabili della politica su 0731 (notte 2/8)

Quattro Codex in parallelo, un worktree ciascuno, rami `port/v2-*`.
`DS4_SPEX_*` escluso per decisione dell'utente.

| worktree | ramo | ambito |
|---|---|---|
| `ds4-0731-vittima` | `port/v2-vittima` | politica vittima, cache VRAM esperti, telemetria `[vram-prio]`/`[iq2-expert-cache-size]` |
| `ds4-0731-tiering` | `port/v2-tiering` | `EXPERT_TIER_*`, `EXPERT_TIERING`, `G133_*` |
| `ds4-0731-moeio` | `port/v2-moeio` | coda I/O, `MOE_CACHE_POLICY`, route worker |
| `ds4-0731-prefill` | `port/v2-prefill` | `PREFILL_TIER_*`, `REAP_MASS_*`, riserve di stream, arena |

## Fatti stabiliti dagli agenti, che valgono a prescindere dal codice

**La catena della vittima su 0731 non esiste.** Nel fork la policy opera su
`g_model_ranges`, pool MISTO dove gli esperti sono sfrattabili e il backbone e'
`pinned`. Su 0731 `mass_lfru_policy::choose_victim` riceve **solo slot esperto
validi**: backbone, KV e range modello non entrano nella lista candidati. Le
stringhe `reason=no-expert-victim` e `victim_category=backbone` non esistono in
tutto l'albero. Meta' del mandato "vittima" e' **non portabile perche' il guasto
non c'e'**.

**`[iq2-expert-cache-size]` mancava solo la stampa.** Il dimensionamento esiste
a `ds4_cuda.cu:26817` (`cuda_stream_resident_cache_prepare_locked`), al primo
selected-load dopo l'allocazione dell'attenzione. **La cache si attivava solo con
budget non nullo E la cache VRAM opt-in**, e `DS4_CUDA_STREAMING_EXPERT_CACHE_N`
non era letto da NESSUN file di 0731. Ora una richiesta positiva abilita da sola
lo slab, senza il vecchio `DS4_CUDA_VRAM_EXPERT_CACHE`.

**L'ipotesi "lettura senza buffering" e' FALSA su Windows.**
`src/platform/os_file.c:100`: `CreateFileW` con `FILE_ATTRIBUTE_NORMAL |
FILE_FLAG_RANDOM_ACCESS | FILE_FLAG_OVERLAPPED`, **niente `FILE_FLAG_NO_BUFFERING`**.
Lo stesso handle alimenta `CreateFileMappingW`/`MapViewOfFile`
(`os_mmap.c:44-49`). Su Linux invece CUDA tenta `O_DIRECT` a
`ds4_cuda.cu:5855`, disattivabile con `DS4_CUDA_NO_DIRECT_IO`.
**Correzione di metodo**: leggevo `SystemCacheResidentBytes`, che NON conta le
pagine di file mappati. I "3,6 GB di page cache" non misuravano quel che credevo.

**`DS4_EXPERT_TIER_ADMIT_KNOCKS_SSD` non e' portabile**: su 0731 il seed RAM e'
ranking upstream (`dynamic_arena.cu:1168`), non una transizione governata dalla
policy. Era la leva promossa a +4,0%: qui non ha dove attaccarsi.

**Il route worker di 0731 e' diverso per scelta**: rendezvous generation-aware
che promuove dal working set gia' verificato, con reserve/drain/publish/refund
come transazione unica. `MOE_DEMAND_PIPELINE` e `G73` non appartengono a questa
infrastruttura e non sono stati innestati. La route Q4_K resta intatta.

## Riconciliazione

`docs/porto/riconcilia.ps1`. I Codex non possono committare: `workspace-write`
li limita alla radice `-C`, ma i metadati del worktree stanno in
`ds4-p4a/.git/worktrees/<nome>`. Committa il coordinatore.

Merge sequenziale su `port/v2-merge` per superficie crescente sul file conteso
(`ds4_cuda.cu`, toccato da tutti e quattro): **prefill -> moeio -> vittima ->
tiering**, con build vera a ogni passo.

Nota di build: nvcc non trova `cl.exe` senza `vcvars64.bat`. Non e' un errore di
codice; ha fatto perdere tempo a due agenti. `build.bat` scritto nei worktree.

---

# ESITO — il porto v2 misurato (2/8, notte)

## Il risultato

| braccio | configurazione | token | REGIME | pagina |
|---|---|---|---|---|
| rif. 31/7 | fork, 33 variabili | 5812 | 2,60 | completa |
| **B** | 0731 nudo, porto v2 | 4500 | **2,70** | completa 15.504 car. |
| **D** | 0731 + `DS4_CUDA_MOE_IO_QD=4` | 3859 | **3,09** | completa 13.379 car. |
| C | 0731 + politica intera + arena 30 GiB | 65 | 0,14 | cache DISABLED |
| E | 0731 + cache + tiering + coda, senza arena | 92 | 0,20 | cache DISABLED |

**`DS4_CUDA_MOE_IO_QD=4` vale +14,4% a variabile singola** (2,70 -> 3,09) e porta
0731 a **+19% sul riferimento del 31/7**. E' la leva indicata da giorni dai 229
IOPS a coda 2 su un NVMe, e su 0731 non esisteva: portata stanotte.

Da ripetere prima di promuoverla: un run per configurazione.

## Perche' la cache esperti non si accende — e non e' una taratura

```
[iq2-expert-cache-size] result=disabled requested=320 capacity=0
                        free_at_size_mib=0.0
```

```
totale VRAM      12287 MiB
backbone          8394
cache q8/f16      1980
                ──────
resterebbero      1913 MiB, ma free al dimensionamento = 0
```

Il resto lo prende lo spazio di lavoro dell'attenzione a ctx 10000. E qui c'e'
la differenza **strutturale** che l'agente `vittima` aveva gia' scritto nel suo
rapporto: **su 0731 il dimensionamento della cache avviene DOPO l'allocazione
dell'attenzione**, sul fork avveniva prima. Stessa VRAM, momento diverso: vede
zero invece di 1977 MiB.

Upstream stesso avverte che 320 slot sono sotto la soglia:
```
WARNING: SSD streaming expert cache (320 experts) is under twice the per-token
         routed working set (43 layers x 6 experts = 258); expect heavy thrashing
```

**Ipotesi falsificata**: non e' l'arena. Il braccio E la toglie e la cache resta
`disabled` lo stesso. L'idea che i 30 GiB mapped-pinned costassero VRAM in
tabelle di pagina WDDM e' morta al primo test.

## Cosa ha reso possibile diagnosticarlo in un secondo

La riga `[iq2-expert-cache-size]` con `result=disabled`. Prima del porto v2 quel
caso era **silenzio**, ed e' cosi' che il braccio C dell'1/8 ha girato per ore
con un'arena orfana. Il costo di portare la telemetria si e' ripagato al primo run.

## Prossimi passi, in ordine

1. **Ripetere D** (in corso). Un run non e' un verdetto.
2. **Liberare VRAM prima del dimensionamento**: `DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB`
   e' la leva che sul fork porto' la capacity da 135 a 253 mascherando 2 GiB di
   pesi perche' arrivassero dalla RAM. E' stata portata dal braccio prefill.
3. **Oppure spostare il dimensionamento** prima dello spazio attenzione, che e'
   la differenza vera col fork. E' un cambio di codice, non di configurazione.
4. `DS4_CUDA_MOE_IO_QD` oltre 4: il fork lo limitava a 4, verificare su 0731.
