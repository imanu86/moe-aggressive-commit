# Multichat Claude Code, 2 chat in parallelo (6/10)

Casi django__django-14434 e sympy__sympy-13615, due sotto-agenti Haiku lanciati insieme; il gateway li manda alla
8100. Config Daily (fixed cache: con `--batch` la cache elastica si spegne). Dati in `D:\ds4_work\swe_casa\runs_cc\`.

| giro | motore | voto | richieste | token generati | velocita' |
|---|---|---|---|---|---|
| cc1 | Daily 0.1.39, una richiesta alla volta (le chat si alternano) | 2/2 | 59 | 32.295 | ~45 t/s, una chat per volta |
| cc2 | 0.1.40 merge, `--batch 2 --batch-mtp` | non valido | 2 | - | il motore esce alla prima ammissione (bug upstream, poi PR #1063); Claude Code ripiega su Opus |
| cc3 | 0.1.40 merge, `--batch 2` | django risolto; sympy fermato | - | - | 1,97 righe/finestra, 62 ms: ~23 t/s totali |
| cc4 | 0.1.40 + fix #1063, `--batch 2 --batch-mtp` | 2/2 | 59 | 36.033 | 3,43 righe/finestra, 85,8 ms: ~59 t/s totali nelle fasi batch |

- cc4: django in 11,7 min, sympy in 23,8 min (lo sympy di cc4 ha fatto 43 chiamate di strumenti contro 31 di cc1 e
  ~50 s di test per voto: i minuti dipendono dal percorso dell'agente, non solo dal motore).
- Riuso del prefisso tra le chat: la seconda parte con 39.937 di 39.938 token gia' in RAM; una chat che cresce legge
  solo la parte nuova (es. 3.320 token in 5,9 s); il passaggio di una conversazione tra slot costa ~0,3 s.
- Le "righe/s" del motore non sono token: contano le righe verificate di una finestra. Il totale in t/s e' la somma
  dei token delle righe `done:` del server diviso il tempo delle fasi batch.
- Il voto controlla che le richieste Haiku viste dal gateway siano LOCALE: se il motore muore, Claude Code passa a
  Opus e quelle richieste non sono piu' Haiku, quindi il voto risulta "valido" (cc2). Da aggiungere: richieste servite
  dal motore >= richieste stream con strumenti della finestra.
