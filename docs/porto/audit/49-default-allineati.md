# 49 - Default allineati e manifesto di lancio

Data: 10 agosto 2026. Worktree `D:\wt-default`, ramo `fix/default`.

Vincolo rispettato: non ho compilato e non ho avviato il server. Le prove dinamiche
restano sulla macchina di misura.

## Cosa e' cambiato

Tre default ora coincidono con la configurazione che ha vinto i cancelli:

| Leva | Prima | Ora | Vecchio valore ancora selezionabile |
|---|---:|---:|---:|
| `LLAMA_CACHE_ESPERTI_W` | 2 | 0 | `LLAMA_CACHE_ESPERTI_W=2` |
| `LLAMA_CACHE_ESPERTI_LRU` | 0 | 1 | `LLAMA_CACHE_ESPERTI_LRU=0` |
| `LLAMA_SPEC_DRAFT_TOPK` | 10 | 1 | `LLAMA_SPEC_DRAFT_TOPK=10` |

Il server chiama inoltre `server_manifesto_stampa()` all'ingresso comune delle sue
due vie di avvio. La stampa e' protetta da un `static atomic_flag`, quindi avviene
una sola volta per processo. `LLAMA_MANIFESTO` vale 1 per difetto;
`LLAMA_MANIFESTO=0` la spegne.

Il manifesto contiene le 77 chiamate ambientali `LLAMA_*` proprie del fork,
raggruppate in sette righe (`cache`, `spec`, `compute`, `kv`, `vram`, `reap`,
`diag`) piu' intestazione. Ogni voce ha forma `NOME=valore(E|D)`, con legenda:

- `E`: variabile presente nell'ambiente;
- `D`: variabile assente, quindi valore di difetto.

Le `LLAMA_ARG_*` non appartengono a questo censimento: sono il canale standard del
parser degli argomenti e possono essere superate dalla riga di comando. Mescolarle
qui produrrebbe una provenienza falsa a due stati; i 77 nomi censiti sono invece le
leve dirette a `getenv` introdotte dal fork. Sonde, trace e diagnostica sono incluse,
non solo le leve della configurazione SOTA.

## Diff commentato

1. `src/models/deepseek4.cpp`: il ripiego di `cache_w` passa da 2 a 0. Il clamp
   0..8 e il ramo ambiente restano identici.
2. `ggml/src/ggml-cuda/cache-esperti.cu`: l'assenza di
   `LLAMA_CACHE_ESPERTI_LRU` seleziona LRU; qualunque valore ambiente continua a
   passare dallo stesso `atoi`, quindi 0 ripristina l'orologio.
3. `common/speculative.cpp`: il ripiego di `spec_top_k` passa da 10 a 1. Il ramo
   ambiente non cambia; il commento ora dichiara argmax come metro riproducibile.
4. `tools/server/server.cpp`: una tabella esplicita registra nome, gruppo e default
   delle leve del fork. La funzione stampa il valore ambiente quando presente e il
   default altrimenti, marcandone la provenienza. E' chiamata prima di qualunque
   distinzione fra router e server a modello singolo.

La tabella e' stata confrontata per insieme con le stringhe `LLAMA_*` aggiunte dal
fork rispetto al merge-base upstream `936918514`: 77 attese, 77 presenti, zero
mancanti e zero extra.

## Cancelli

### Identita' con ambiente esplicito

Configurazione da provare:

```text
LLAMA_CACHE_ESPERTI_W=0
LLAMA_CACHE_ESPERTI_LRU=1
LLAMA_SPEC_DRAFT_TOPK=1
```

Il codice continua a entrare negli stessi rami ambiente di prima. Risultato atteso:
SHA `33D76723EB8D` e 13,19-13,26 t/s. Il manifesto deve mostrare:

```text
LLAMA_CACHE_ESPERTI_W=0(E)
LLAMA_CACHE_ESPERTI_LRU=1(E)
LLAMA_SPEC_DRAFT_TOPK=1(E)
```

### Nuovo default senza ambiente

Rimuovere le tre variabili. Risultato atteso: lo stesso SHA `33D76723EB8D`. Il
manifesto deve mostrare:

```text
LLAMA_CACHE_ESPERTI_W=0(D)
LLAMA_CACHE_ESPERTI_LRU=1(D)
LLAMA_SPEC_DRAFT_TOPK=1(D)
```

### Ritorno ai valori vecchi

Una corsa di controllo con `W=2`, `LRU=0`, `TOPK=10` deve mostrare le tre voci con
`(E)` e riprodurre i vecchi cammini. Questo cancello verifica che il cambio sia
solo nei ripieghi, non nella semantica delle variabili.

I cancelli dinamici non sono dichiarati passati in questo rapporto: per mandato non
ho compilato ne' eseguito il server.

## Altri default incontrati

Non ho trovato un quarto default dimostrato perdente da una misura gia' presente
nel sorgente. Restano due candidati gia' censiti dall'audit 47, che non vanno
promossi o cambiati senza la loro prova:

- `LLAMA_OVERLAP_SPIN=2000000`: attesa attiva accesa per difetto, valore netto non
  ancora isolato contro `=0`;
- `LLAMA_CACHE_ESPERTI_PF_TUTTI=1`: comportamento nuovo acceso per difetto, non
  ancora misurato in isolamento contro `=0`.

Il manifesto rende entrambi visibili in ogni log, ma questa patch non inventa un
verdetto che le misure non hanno ancora dato.

## Verifiche statiche eseguite

- `git diff --check`: pulito.
- Censimento manifesto: 77 nomi attesi, 77 presenti, zero differenze.
- Controllo testuale dei sei punti che devono concordare (tre call site e tre
  voci del manifesto): una corrispondenza per ciascuno.
- Scansione byte diretta dei cinque file modificati: zero byte CR, zero sequenze
  CRLF e nessun BOM UTF-8. Tutti i fine riga sono LF.
- Righe aggiunte: nessun carattere fuori ASCII.
