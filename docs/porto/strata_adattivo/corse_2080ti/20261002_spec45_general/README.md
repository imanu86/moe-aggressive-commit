# Prova generale spec 4 / 5 / 4 — 2 ottobre 2026

Richiesta: provare spec 5 come configurazione generale. Nessuna modifica al daily.
Spec5 verifica davvero quattro bozze e conserva gli stessi testi del riferimento,
ma non mostra un vantaggio nei campioni: -2,02% a20k, -1,43% a131k rispetto
alla media dei due spec4. Gli scarti tra riferimenti sono 2,83% e0,96%:
un solo A/B/A non misura la significatività statistica. Manteniamo spec4.
Stesso eseguibile 0.1.36 c35505ca, RTX 2080 Ti modificata 22 GB, Ryzen 5800X,
Windows/CUDA 12.6. Tre bracci sequenziali A1 spec4, B spec5, A2 spec4,
con massimo MTP uguale a spec. Lookup spento e min-p 0,5.
Ragionamento attivo, sforzo low, greedy, stessi prompt congelati e ordine.
KV 262144/int8/resident32768, cache laboratorio fissa a 6167 slot reali,
budget 4600, chunk2048, riserva configurata1393 MiB, IQ_MT_MIN1;
adattamento e PCIe miss spenti, quantizzazione intermedia seriale.
Il daily rimane automatico/elastico. Non confrontare queste velocità con il
SOTA storico misurato con più slot e diverse impostazioni.

## Decode

Due campioni da 1024 token per profondità e braccio, con prefisso già letto.
Valore aggregato: token generati divisi per il tempo totale di decode.
Il contesto indicato nella prima colonna è il prompt dell'oracolo; il prompt
di throughput ha una coda diversa, quindi la seconda colonna dà i token reali.
Le risposte lunghe sono limitate per misura e possono finire in length:
non vengono usate per il gate delle risposte complete. Trace e timing sono
attivi identicamente per tutti i bracci, per verificare le finestre effettive.

| Contesto oracolo | Prompt reale decode | A1 spec4 t/s | B spec5 t/s | A2 spec4 t/s | B vs media A | Scarto A1/A2 |
|---:|---:|---:|---:|---:|---:|---:|
| 20000 | 20046 | 38.768 | 38.532 | 39.882 | -2.02% | 2.83% |
| 131072 | 131118 | 36.604 | 35.908 | 36.255 | -1.43% | 0.96% |

Nel braccio B a131k, finestre effettive T=5 nei campioni di throughput: **388**.
T include il token principale: T=5 significa quattro bozze effettivamente
verificate nella stessa finestra. La soglia di confidenza può usare T inferiori.
Conteggi completi, accettazione, log e tempi sono nelle evidenze.

## Correttezza e formato

Otto oracoli per braccio: sei domande brevi eterogenee e tre record recuperati
al10/50/90% in prompt freddi da20000 e131072 token. Non sono 24 problemi
indipendenti. Il criterio richiede risposta JSON esatta e finish=stop.
Un eventuale blocco Markdown non soddisfa il requisito solo JSON, anche se
i codici interni sono corretti. La diagnosi del formato è separata, fatta
dopo la corsa e non modifica il verdetto originale.

| Braccio | Gate JSON originale | Contenuto corretto dopo diagnosi del formato |
|---|---:|---:|
| A1 | 6/8 | 8/8 |
| B | 6/8 | 8/8 |
| A2 | 6/8 | 8/8 |

Gate originale complessivo: **FAIL**.
Campioni bounded completi: **True**.
Testi B identici al riferimento A1, contenuto e ragionamento:
**12/12 richieste**.
La prova aritmetica già avviata prima del chiarimento è conservata a parte:
spec5 senza ragionamento92, con ragionamento105; entrambe finish=stop.

## Limiti e riproduzione

Un A/B/A locale, due campioni per profondità, prompt specifici. Nessuna
conclusione universale sulla qualità o sulla velocità; non è un nuovo SOTA.
Nessun dump completo dei logits o nuova validazione kernel in questa prova.
Non provati250k, cache elastica in confronto controllato o PR512 isolata.
Eseguibile, server, lanciatore e configurazione operativa non modificati.
Nessun carico artificiale o altra chat coinvolta; i motori della prova sono
chiusi al termine. I dati completi sono in
[corse_2080ti/20261002_spec45_general](.).
Il runner locale riproduce dipendenze e percorsi della workstation; gli ID,
gli hash e il piano registrano gli input esatti.
