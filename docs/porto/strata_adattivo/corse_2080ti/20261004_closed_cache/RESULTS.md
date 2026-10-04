# Cache esperti chiusa dopo il prefill

Il prototipo esegue il decode senza chiamare il pool CPU degli esperti. Sul testo
discorsivo passa da 28.03 a 44.13 token/s, includendo due rinnovi della cache.
La politica non supera pero' il controllo di qualita': i due output strutturati
diventano JSON malformati e uno degenera in ripetizioni mentre l'accettazione MTP
resta al 97%. Il solo rapporto accettate/proposte non protegge il modello ridotto.
Nessuna promozione al Daily, allo ZIP o a una nuova SOTA.

## Politica effettivamente provata

Il prefill usa tutti gli esperti. Le sue frequenze selezionano i residenti per
ciascun layer, mantenendo il numero di slot gia' assegnato a quel layer. I pesi
sono copiati in VRAM, poi la cache resta ferma fino al successivo rinnovo.

- `resident`: top 10 scelti tra i soli residenti, con pesi normalizzati.
- `drop`: top 10 originali, contributi degli assenti azzerati senza rinormalizzare.
  ID residenti con peso zero sostituiscono gli assenti nel planner GPU; questo
  prototipo puo' ancora calcolare un esperto fittizio a peso zero.
- `observe`: routing completo, soli conteggi diagnostici; nessuna chiusura.
- Variabile `STRATA_CLOSED_ROUTING` assente: percorso ordinario.

Si registra anche il routing non mascherato sugli input del modello corrente.
Durante il decode si contano solo le righe confermate, non le bozze scartate.
Ogni blocco di almeno 64 bozze proposte e 32 token emessi viene valutato: sotto
il 50% di accettazione si riempie nuovamente la cache dai conteggi accumulati.
I conteggi sono azzerati al rinnovo; il blocco di accettazione a ogni valutazione.
La scelta nuova e' quindi causale, ma dipende dagli stati del modello gia' ridotto.

## Condizioni e risultati

RTX 2080 Ti modificata da 22 GB, Ryzen 5800X AVX2, 96 GiB RAM, Windows,
CUDA 12.6/MSVC Release SM75, Qwen3.8-Flash-Next IQ3_XXS. Cache fissa: 5080 slot,
8442 MiB, circa 8.24 GiB. KV int8 con capacita' 262144 e 32768 celle residenti.
**Le profondita' reali sono 85, 1680 e 2470 token iniziali, non 250k.**

Ogni riga usa un processo nuovo, temperatura zero, seed 73 e ragionamento
disabilitato. CLI spec 4, mtp-max-t 4, spec-min-p 0.5; T comprende il token
target, quindi non va letto come quattro bozze accettabili. Sono disattivati
elasticita', swaps ordinari, cache prompt, suffix draft e split speculativo.
Il controllo completo usa lo stesso eseguibile del candidato, con il probe
disabilitato. Il confronto misura l'intera politica, compresa la diversa scelta
iniziale degli esperti; non isola il solo effetto del pruning.

| Compito e token prompt | Politica | Token emessi | Decode t/s | MTP accettate/proposte | Esito osservato |
|---|---|---:|---:|---:|---|
| Magazzino, 1680 | Completo | 152 | 31.94 | 112/116 | JSON valido, totale errato |
| Magazzino, 1680 | Residenti | 151 | 73.45 | 111/115 | JSON malformato |
| Traccia LRU, 2470 | Completo | 170 | 33.43 | 124/132 | JSON valido, stati errati |
| Traccia LRU, 2470 | Residenti | 224 | 75.57 | 161/166 | Ripetizione D,E,F, JSON malformato |
| Spiegazione, 85 | Completo | 512 | 28.03 | 272/451 | Testo discorsivo, interrotto al limite |
| Spiegazione, 85 | Residenti | 512 | 44.13 | 225/417 | Testo discorsivo con errori, interrotto al limite |
| Spiegazione, 85 | Assenti azzerati | 512 | 44.96 | 68/114 | Degenera nella ripetizione S'S'S |

Le velocita' degli output deteriorati sono throughput grezzo, non velocita' di
risposte corrette. Anche i due controlli completi falliscono l'oracolo semantico:
non si puo' dedurne una percentuale generale di perdita di accuratezza.
Le risposte discorsive hanno sola ispezione manuale, nessun PASS di correttezza.
La variante residenti contiene anche formulazioni scorrette come "se non non";
il controllo completo contiene semplificazioni tecniche discutibili.

Nel confronto discorsivo il guadagno grezzo e' 57.46%. Il TTFT sale da 1.329 a
1.922 s, mentre la richiesta intera scende da 19.532 a 13.484 s. Il caricamento
iniziale del modello e' escluso da questi tempi. Il primo riempimento costa
613 ms e 4.98 GB H2D; due rinnovi, entrambi al 46.875% di accettazione del blocco,
costano insieme 758 ms e 6.23 GB H2D. Questi rinnovi sono inclusi negli 11.601 s
di decode. I riempimenti dei due task strutturati costano 869 e 813 ms.

Tutte le esecuzioni chiuse registrano zero chiamate al pool CPU durante il decode,
confermato dai contatori del driver e dai tempi interni. La CPU non e' spenta:
restano orchestrazione, I/O PLE e trasferimenti durante i rinnovi. Sul testo
discorsivo il processo usa circa 0.70 core equivalenti dopo il primo token,
contro 7.61 nel controllo. Gli zeri nei vecchi contatori host hits/lookups non
misurano il numero di letture VRAM: quel planner host e' saltato.

## Perche' il rinnovo non basta

La ripetizione LRU arriva al 100% di accettazione in un blocco e non rinnova mai
la cache. La bozza puo' predire bene un testo gia' degenerato: accettazione alta
non equivale a fedelta' al modello completo. Nella variante `drop`, inoltre,
il drafter propone sempre meno token per la soglia di confidenza 0.5: solo
114 proposte in 444 finestre. Un criterio che attende 64 proposte puo' rimanere
senza nuovi campioni, pur avendo una resa speculativa pessima. Zero rinnovi.

Prima di un'eventuale continuazione servono un controllo indipendente rispetto
al modello completo e una politica che consideri anche la scarsita' di bozze.
Non basta alzare o abbassare la soglia MTP. Questo test dimostra il meccanismo
e un margine di velocita', non una riduzione sicura del modello.

## Verifiche e conservazione

87 casi CUDA passano: parita' bitwise con tutti gli esperti residenti, riferimento
CPU indipendente per top-k e pesi, maschere/tie/underflow, replay del cambio di
politica nel grafo e conteggio delle sole righe confermate. Un difetto di
sincronizzazione del primo banco e' stato corretto prima delle misure.
Il primo avvio del motore falliva prima di READY per una riserva di exchange
su una sorgente file non usata: corretto, risultato fallito conservato.

Sul magazzino, tutti i 152 ID emessi coincidono tra probe spento, observe e
vecchio eseguibile Daily, comprese entrambe le prove di quest'ultimo. E' una
regressione circoscritta degli output, non una prova di identita' di tutti i logits.
Il Daily con gli stessi parametri fissi aveva una misura anomala a 19.58 t/s:
ripetuta, diventa 28.90 t/s. Entrambe sono conservate; nessuna e' usata per
gonfiare il confronto principale 31.94 -> 73.45. Cause esterne non identificate.

Undici esecuzioni completate, un avvio fallito, tutti i processi terminati.
Daily, config e launcher verificati per hash e invariati; release non modificata.
Il codice del probe e' nel fork e rimane disabilitato per default.

`summary.json`, `verification.json` e le directory delle singole prove contengono
tempi, token, risposte, oracoli, comandi e log. `build.json` fissa sorgenti e
SHA256 dell'eseguibile. Gli script sono copie esatte dei runner locali; i percorsi
workstation e i helper allegati vanno adattati per ripetere altrove. Nessun modello
generato e' stato eseguito come codice, nessun carico artificiale aggiunto.
