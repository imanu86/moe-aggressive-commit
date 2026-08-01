# MANDATO — cosa fanno davvero le leve sequenziali del wrap

LAVORO DI LETTURA E DIAGNOSI. **Non modificare nessun sorgente.** Il tuo prodotto e' un
rapporto: serve a decidere quali leve accendere in una misura, e accenderle alla cieca oggi
mi e' gia' costato quattro run.

  DOVE LEGGI:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a
               il nostro fork. **SOLA LETTURA.**
  DOVE SCRIVI: solo `WRAP_SEQUENTIAL_ANALISI.md` nella radice di quel worktree.

**Non usare git per scrivere** e non lanciare build: il disco e' occupato da una
compattazione e ogni I/O in piu' falsa le misure in corso.

## IL FATTO MISURATO CHE ORIGINA LA DOMANDA

Lo stesso disco NVMe, a un'ora di distanza, sullo stesso stato:

```
durante una compattazione (blocchi grandi)   574 MB/s lettura, 595 scrittura, 96% attivo
durante il wrap dell'arena                    58,9 MB/s, 971 letture/s, 62 KB medi,
                                              coda 8, ~8,2 ms di latenza per lettura
```

**Dieci volte piu' lento**, e il profilo del wrap dice perche':

```
[arena-wrap-profile] result=published schedule=source-parts source=mmap
    checksum=fnv1a64-worker-only loads=6546 workers=8
    begin=0.007 copy_checksum=119.038 finish=0.000 publish=0.004 total=119.049
    parts=19638 copy_workers=8 checksum_workers=0
    file_qd=1 file_qd_observed=1 file_submits=0 file_completions=0 file_failures=0
```

`source=mmap` e **zero submit**: non emette letture, percorre il file a page fault.

## LE VARIABILI DA CAPIRE

Esistono nel sorgente e **nessuna e' mai stata accesa** (non compaiono nell'atlante delle leve,
ne' come attive ne' come falsificate):

```
DS4_CUDA_ARENA_WRAP_SEQUENTIAL_FILE
DS4_CUDA_ARENA_WRAP_SEQUENTIAL_WORKERS
DS4_CUDA_ARENA_WRAP_FILE_QD
DS4_CUDA_ARENA_WRAP_RANDOM_FILE
DS4_CUDA_ARENA_WRAP_TRIM_BETWEEN_PHASES
DS4_CUDA_ARENA_WRAP_PART_PROFILE
DS4_CUDA_ARENA_WRAP_LAYOUT_PROFILE
DS4_CUDA_ARENA_WRAP_SLOW_PART_MS
```

Quelle gia' nel preset, per contesto: `SCHEDULE=source-parts`,
`TRUST_WORKER_CHECKSUM=1`, `UNLOCK_SOURCE_RANGES=1`, `UNLOCK_WAVE_GIB=4`.

## COSA DEVE CONTENERE IL RAPPORTO

**(1) Per ciascuna delle otto variabili**: dove viene letta (file:riga), quali valori accetta,
cosa cambia nel percorso di caricamento, e **quale altra variabile deve essere impostata
perche' abbia effetto** — se una richiede un prerequisito, e' l'informazione piu' utile.

**(2) La domanda centrale**: `SEQUENTIAL_FILE` sostituisce davvero il percorso `mmap` con
letture di file esplicite? Se si', **con che dimensione di richiesta e con che profondita' di
coda**, e chi le emette (il thread di copia? i worker? uno separato?). Se invece fa altro,
dillo: la mia ipotesi e' che serva a questo, e potrebbe essere sbagliata.

**(3) Quali valori sono SICURI** e quali possono rompere o appendere. Oggi ho appeso il wrap
due volte aggiungendo variabili prese da un preset vecchio: voglio sapere in anticipo cosa
richiede cosa.

**(4) Un ordine di accensione a variabile singola**, con per ciascun passo **cosa deve cambiare
nel log** se la leva sta funzionando. La riga `[arena-wrap-profile]` gia' stampa
`file_qd`, `file_qd_observed`, `file_submits`, `file_completions`, `file_failures`: dimmi quali
di questi devono muoversi e in che direzione.

**(5) Se qualcuna di queste leve tocca il percorso del DECODE** e non solo il caricamento
iniziale. Il wrap riempie l'arena una volta; ma nel decode facciamo **598 letture per token**, e
se una di queste variabili cambia anche la forma di quelle, il ritorno e' molto piu' grande di
un caricamento piu' rapido. **Questa e' la parte che mi interessa di piu'.**

## VINCOLI

- **Ogni affermazione con file:riga.** Se non l'hai verificata, scrivi che e' un'ipotesi.
- Se una variabile risulta **inerte** o non collegata a niente, dillo: e' un risultato utile
  quanto il contrario, e mi risparmia una misura.
- Rispondi in italiano.
