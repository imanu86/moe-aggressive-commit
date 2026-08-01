# Dove sta la roba — campagna porto, 1/8

Scritto perche' l'1/8 sera l'utente ha chiesto di aprire gli HTML e ho impiegato
mezz'ora a cercarli, per poi scoprire che meta' non esistevano.

## Le pagine generate

**`docs/porto/pagine/`** — nel repo, versionate, con `INDICE.tsv`. Sette pagine
della campagna del 31/7-1/8, copiate qui dallo scratchpad temporaneo della
sessione `998f14b4` prima che venisse ripulito.

| id | data | ~tok | sez | JS | form | completa |
|---|---|---|---|---|---|---|
| RIF_GSPEC_turno1 | 31/07 | 5355 | 7 | 9 | 5 | **SI** |
| RIF_GSPEC_turno2 | 31/07 | 5373 | 7 | 9 | 5 | **SI** |
| X_P8K_comb | 01/08 | 5082 | 7 | 11 | 9 | no, finisce con prosa |
| X_CTL8K | 01/08 | 2113 | 0 | 0 | 0 | **NO, troncata nel CSS** |
| K2_TF2p1 | 01/08 | 2068 | 0 | 0 | 0 | **NO** |
| FD1_shared220 | 01/08 | 2196 | 0 | 0 | 0 | **NO** |
| FD2_sharedded | 01/08 | 2196 | 0 | 0 | 0 | **NO** |

**Quattro pagine su sette non sono pagine.** Si fermano dentro il foglio di
stile: zero sezioni, zero JavaScript, zero elementi di form, mentre il prompt
chiede navigazione, hero, form e popup JS.

Conseguenza diretta: **`X_CTL8K` non e' un riferimento valido.** L'1/8 sera l'ho
usato come colonna di confronto contro il run del 31/7 (`REGIME 4,48` contro
`4,49`) come se fossero lo stesso carico. Uno e' una pagina completa da 5355
token con 9 handler, l'altro un frammento di CSS da 2113. Ogni confronto che
passa per X_CTL8K va rifatto.

## I log dei bracci della sera

**`D:\ds4_work\porto_run\`** — 17 `.server.log` dal 16:16 al 23:08.
I `.log.out` sono **tutti a 0 byte**: l'harness leggeva
`$resp.usage.completion_tokens` e buttava `$resp.choices[0].message.content`.
Il testo di quei 17 run non esiste piu' da nessuna parte, ne' su disco ne' in
chat. Corretto in `braccio.ps1` la sera stessa.

## Da adesso in poi

`docs/porto/braccio.ps1` scrive, con lo **stesso identificativo** `<tag>`:

```
D:\ds4_work\porto_run\<tag>.server.log     log del binario
D:\ds4_work\porto_run\<tag>.output.html    il testo generato
D:\ds4_work\porto_run\<tag>.meta.json      metriche + preset + sha256
D:\ds4_work\porto_run\LEDGER_RUN.tsv       una riga appesa per braccio
```

`<tag>` = `<braccio>_<HHMMSS>[_CHIAVE=VALORE]` per gli override, cosi'
l'identificativo dice gia' che prova era.

Il `.meta.json` contiene `output_sha256` e `prompt_sha256`: il cancello di
neutralita' si verifica confrontando quello, non a occhio.

## Altre cose che si perdono facilmente

| cosa | dove |
|---|---|
| preset del fork | `docs/porto/preset_A.ps1` — 34 variabili, con la storia dei fallimenti in testa |
| atlante rivisto | `.microbench/atlante/REVISIONE.md` — le voci C-1..C-9, con i verdetti da riscrivere |
| piano del porto | `docs/porto/PIANO.md` — 12 blocchi, "cosa non portare", stime, cancelli |
| pesi nuovi | `C:\ds4-models\DS4-0731-IQ2XXS.gguf` (80,76 GB) |
| pesi vecchi | `C:\ds4-models\ds4-2bit.gguf` (80,76 GB) |
| sidecar DSpark | `D:\ds4-models\DSpark-support-Q2K-w2Q4K.gguf` (7,83 GB) |
| scratchpad sessione sera | `...Temp\claude\...\8e3de907-...\scratchpad\` — **temporaneo, non fidarsi** |
