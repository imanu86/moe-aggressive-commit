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
