# La mappa del runtime DS4

**166.593 righe non si tengono in mente. Si tiene un indice, e si tira giu' la
catena della cosa che serve, quando serve.** Questo e' l'indice.

Estratto meccanicamente dal codice: nessuna riga qui dentro e' stata dedotta a
occhio. O il simbolo c'e' nel testo o non c'e'.

```
78 file        5.164 funzioni      12.883 archi di chiamata
661 variabili DS4_*  in 927 siti di lettura    453 a semantica di PRESENZA
19.218 siti con catena di guardie    10.059 condizioni distinte
```

## Interrogarla

```bash
python catena.py DS4_CUDA_Q8_F16_CACHE_MB     # una variabile: tutta la catena
python catena.py cuda_q8_f16_cache_has_budget # una funzione: chi la chiama, cosa chiama
python catena.py --trappole                   # i siti "=0 la ACCENDE"
python catena.py --orfane                     # variabili lette e mai consumate
```

Per una variabile restituisce, nell'ordine:

- **dove si legge**, con quale funzione di lettura e quale semantica
- **sotto quali guardie**: le condizioni che devono essere tutte vere perche' si
  arrivi a quella riga, comprese le uscite anticipate (`if (!x) return;`)
- **chi deve chiamare** perche' la lettura avvenga, risalendo fino a `main`
- **cosa accende**: le funzioni raggiungibili da li'
- **quali ALTRE variabili vivono su quei cammini** — ognuna e' il prossimo collo
  di bottiglia possibile, ed e' la domanda per cui questa mappa esiste

## Rigenerarla

Va rifatta dopo ogni modifica al codice, altrimenti invecchia e mente:

```bash
python estrai.py     ../../../ds4-port mappa.json
python condizioni.py ../../../ds4-port mappa.json guardie.json
```

Circa un minuto in tutto.

## I pezzi

| file | cosa contiene |
|---|---|
| `estrai.py` | funzioni, archi di chiamata, letture env, globali. Delimita i corpi contando le graffe su un testo spogliato di commenti e stringhe |
| `condizioni.py` | la catena di guardie di ogni sito. Gestisce i blocchi con graffe, le guardie a istruzione singola, e le **uscite anticipate**, che in questo codice sono il modo normale di spegnere una funzione intera |
| `catena.py` | l'interrogazione |
| `router.py` | l'altra meta': come **ragiona** il modello, dal tracciato `[route-ids]` |
| `mappa.json`, `guardie.json` | gli estratti |

## Perche' due meta'

La struttura statica dice come il router e' implementato. **Non dice cosa
sceglie.** Quella e' una misura, e sta in `router.py`:

```bash
python router.py <log con DS4_EXPERT_TIERING_LOG_IDS=1> 181
```

Le due meta' rispondono a domande diverse e servono entrambe. La prima ha
trovato da sola la trappola di `vram_expert_cache.cpp:304` che avevamo scoperto
inciampandoci. La seconda ha falsificato in un colpo tutta la nostra politica di
residenza (vedi `RAGIONAMENTO_MODELLO.md`).

## Cosa NON fa, e va saputo

- Gli archi di chiamata sono per **nome**: non risolve i puntatori a funzione ne'
  il sovraccarico C++. Un nome che compare in due file produce due definizioni e
  gli archi vanno a entrambe (l'elenco e' in `duplicati`).
- Le macro non sono espanse. Una chiamata generata da una macro non si vede.
- La semantica `ignoto` sui `getenv` grezzi significa che il riconoscitore non ha
  trovato ne' una forma di presenza ne' una validazione: **va guardata a mano**,
  sono 143 siti.
- Vede il codice compilato per **tutte** le piattaforme, non solo la nostra. Un
  cammino dentro `#if defined(__APPLE__)` risulta raggiungibile e non lo e'.
