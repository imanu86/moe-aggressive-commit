# METRICA DELLA TESTA — p1, definito una volta per tutte

*Cantiere TESTA, 7/8/2026 (aperto la sera del 6/8). Risponde al punto 1 di
`MANDATO_TESTA.md`. Ogni numero futuro del cantiere si misura così; ogni numero
passato si riclassifica così. Base: HEAD 8852c22.*

## La definizione

**p1 = accettazione greedy in prima posizione.** Il bersaglio gira a
temperatura 0; il proponente (testa, drafter, n-grammi — il meccanismo non
entra nella definizione) propone UN token per la posizione successiva; il
bersaglio calcola il suo argmax per quella posizione.

    p1 = (proposte in prima posizione == argmax del bersaglio) / (proposte in prima posizione)

Niente altro è p1. In particolare, nel ledger e nei documenti girano quattro
numeri che NON sono p1 e non vanno confusi:

| numero | cos'è | esempio a ledger |
|---|---|---|
| accettazione su blocco | accettati/proposti su blocchi n_max=5: mescola le posizioni 1..5, ognuna condizionata all'accettazione delle precedenti | 0,596-0,699 (S3, W1, L1) |
| lunghezza media blocco | posizioni accettate per ciclo, dipende da n_max | 4,11-4,41 |
| recall di route | indovinare la ROUTE del token dopo, non il token | 0,594 (TESTA_ROUTE_SONDA) |
| P(≥1) del simulatore | frazione di passi con almeno un n-gramma accettato | 0,26 codice / 0,076 prosa |

L'unica misura esistente *quasi*-p1 sul nostro carico è l'accettazione a
**n_max=1** del fork (riga `LLAMA_T3_nmax1`, 3/8): **0,899** — una sola
posizione proposta per ciclo, quindi accettazione = p1 per costruzione. Ma:
300 token (l'accettazione cresce col run, vedi sotto), ctx4096, meccanismo del
fork. Va rifatta, non creduta.

## La verifica è greedy, la bit-esattezza è gratis, il cancello no

Con la verifica speculativa a temperatura 0 la sequenza emessa è IDENTICA alla
greedy pura *per costruzione*: proposta giusta → è l'argmax; proposta
sbagliata → si emette l'argmax del bersaglio. Quindi p1 non ha un costo di
qualità da misurare — ma il MECCANISMO può essere rotto e veloce insieme
(KV corrotta, stati iniettati male, cache invalidata storta). Il cancello di
validità di ogni run che produce un p1:

1. **SHA-256 del testo generato == SHA della greedy pura** nella stessa
   config (stesso prompt, stesso seed, stessa quantizzazione). Divergenza =
   run invalida, qualunque p1 dica.
2. **Contatore cache attivo** se la run passa dalla cache esperti (~257
   domande/token = lavora; ~17 = scavalcata; assente = NON DECIDIBILE).
3. **Cancelli macchina** del protocollo: RAM ≥ 10 GiB all'avvio, VRAM ≥ 400
   MiB liberi, un processo pesante alla volta, battito contatore a 5 s.

## La soglia non è un numero: è una funzione dei colpi della cache

Una catena di profondità 1 mette due posizioni consecutive (t, t+1) nello
stesso passaggio. Unione di route misurata sui consecutivi: **~446 esperti**
contro 380 slot → sborda per costruzione. Il passo costa:

    passo(h) = 52,7 (pavimento) + 16,3 (calcolo GPU) + trasporto(h)

con `trasporto` proporzionale ai miss (identità del trasporto: contano i miss
VRAM, non i byte): trasporto(h) ≈ 120,7 × (1−h) ms. Ancore misurate:
h=17,3% → 99,8 ms; h=44% → 67,6 ms. Il passo produce 1+p1 token attesi contro
1 token in 108 ms del decode normale, quindi:

    pareggio:  1 + p1  >  passo(h) / 108
    p1_soglia(h) = (69 + 120,7·(1−h)) / 108  −  1

| colpi h nel regime a 2 posizioni | passo | p1 richiesto |
|---|---|---|
| 17,3% (misurato a np=2, slot separati) | 168,8 ms | **> 0,56** |
| 30% | 153,5 ms | > 0,42 |
| 44% (se il regime a 2 tenesse quelli di np=1) | 136,6 ms | **> 0,26** |
| 100% (residenza piena, scheda 24 GB) | 69 ms | > 0 (paga sempre) |

Il 17,3% è misurato su **due slot separati** (np=2, richieste identiche); la
catena vera è un grafo solo con lo stesso contesto e potrebbe fare meglio.
**Il braccio "colpi della catena vera" fissa h e quindi la soglia** — finché
non c'è, il numero prudente è 0,56. La capienza/politica della cache è del
cantiere overlap: ogni cambio di regime lì sposta la soglia qui (punto di
contatto: il coordinatore).

## Il protocollo di misura (per qualunque proponente)

- **Dominio dichiarato sempre**: p1 si scrive col pedice — p1_codice
  (NeuraForge, `par_*.req.json`, `prompt_lungo.txt`), p1_prosa (saggio
  fenici). L'accettazione ha un forte pedice di dominio (n-grammi: 0,26
  contro 0,076); la cache no (−1,6%). Un p1 senza pedice non è un numero.
- **Run ≥ 1.200 token**: l'accettazione cresce col run (0,503 a 120 → 0,636
  a 300 → 0,699 a 1500, riga `LLAMA_L1_lunga_dspark`). I verdetti su ≤300
  token sottostimano; 300 token va bene solo per smoke test, non per verdetti.
- **Contatori per posizione, non medie**: proposte_1/accettate_1 (→ p1),
  proposte_2/accettate_2 (→ p2 condizionato), ... La media su blocco non si
  riporta come risultato primario.
- **n ≥ 3 run per verdetto** (protocollo fail-fast); mediana primaria.
- **Ledger**: ogni run una riga in `LEDGER_RUN.tsv` + output catalogato,
  successi e fallimenti.

## I numeri di partenza, riclassificati con questa metrica

| valore | cos'è nella metrica | dominio | fonte |
|---|---|---|---|
| 0,26 | P(≥1) n-grammi ≈ p1 ottimistico del pool ideale | codice | sim_lookahead_pool |
| 0,076 | idem | prosa | LLAMA_TETTO_PROSA |
| 0,899 | quasi-p1 (n_max=1), 300 token, fork | codice | LLAMA_T3_nmax1 |
| 0,767 | p1 vero del drafter DSpark addestrato | traduzione, DGX | PR upstream #25784 |
| 0,596-0,699 | accettazione su blocco n_max=5 (NON p1) | codice | S3/W1/L1 |
| 0,00167 | accettazione nel porto, drafter Q2K (file O metodo, da separare) | codice | LLAMA_SPEC_DSPARK / FITOFF |
| 0,594 | recall di ROUTE, non di token (pavimento di apprendibilità) | codice | TESTA_ROUTE_SONDA |

Lettura onesta della tabella: quando il meccanismo funziona (fork, 3/8), il
drafter DSpark **già supera 0,56 sul nostro carico** in prima posizione
(0,899 quasi-p1). Il suo problema misurato è il COSTO (158 ms per posizione,
testa di Markov 538 ms/chiamata), mai l'accuratezza. La testa da costruire
deve essere *economica*, prima che *brava*.

## Il costo del proponente entra nel pareggio

Il pareggio sopra assume proponente a costo zero. Il conto completo:

    (1 + p1) / (passo(h) + c_testa)  >  1 / 108

con `c_testa` = costo per chiamata del proponente. Bilancio per la testa
~90 MB del mandato (45 M parametri): ~0,09 GFLOP/chiamata contro i 12,98 del
token — trascurabile SE sta nel grafo GPU e non paga orchestrazione. Il
DSpark insegna il rovescio: 165 M di MAC (~0,02 ms di conti) diventavano
538 ms di orchestrazione. **c_testa si misura, non si assume.**
