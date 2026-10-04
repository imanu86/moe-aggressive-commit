# Esperti fuori VRAM: attivazioni e pacchetto 3:10, 4 ottobre 2026

**Il contesto mostra un segnale utile, ma il semplice taglio di neuroni non
raggiunge ancora un sostituto accurato di dieci esperti nello spazio di tre.**
Sono state analizzate le tracce esistenti e completati tre nuovi replay GPU
delle maschere sotto budget. Nessuna modifica al Daily o al pacchetto pubblico.

## Campione e metodo

RTX 2080 Ti modificata a 22 GB, Ryzen 5800X, RAM 96 GiB, CUDA 12.6/SM75.
Tre testi sintetici code/explain/reason; prefissi 86/85/102 token, 63 input della
continuazione per testo, quattro layer 0/1/35/36. La capacita' KV era 262144,
residente 32768: **non e' una prova a profondita' 250k**. Le acquisizioni sono
quelle `probe100-*-normal-v1`, con pagine normali e pinning arena limitato a
8 GiB; configurazione e controlli completi in `probe100-measurements.json`.

Nonresidenti significa tier originale CPU oppure PCIe; VRAM e' esclusa dalla
compressione. Le attivazioni h sono ricostruite con replay GPU dell'input
registrato, anche per gli esperti originariamente eseguiti su CPU.
La loro uscita compressa e' confrontata con l'uscita GPU integrale usando
lo stesso percorso MMVQ, per isolare l'errore delle maschere.

Per ogni testo si usa il suo primo insieme di 100 posizioni candidate:
dieci root target distinti seguiti ciascuno da nove passi MTP. Sono alternative
generate prima della continuazione osservata; non sono 100 token distinti.
Si scelgono, **per ciascun layer**, le dieci identita' nonresidenti con piu'
massa di routing nei candidati. Ogni identita' riceve un budget di 0.3 esperti;
il totale e' al massimo tre. Restano distinti ID, routing e neuroni degli esperti:
non si sommano direttamente matrici di reti non lineari.

La maschera seleziona avidamente energia h^2 pesata per routing^2 per byte
incrementale. Conteggia righe gate/up, blocchi down originali e una stima degli
indici; condivide il costo del blocco down fra neuroni selezionati nello stesso
blocco. Non e' un algoritmo ottimo di compressione. Sono esclusi padding,
allocatore e costo di costruzione/trasferimento. La maschera e' congelata;
gli esperti assenti usano il fallback integrale. Nessun input futuro effettivo
viene usato per scegliere esperti o neuroni.

## Quanto dipendono dal testo i neuroni attivi?

Confronto dei top160/640 per |h|, solo per lo stesso (layer,expert)
nonresidente, osservato almeno due volte in entrambi i testi. Media delle
intersezioni/160 su tutte le coppie di chiamate, poi peso uguale per esperto.

| Coppia di testi | Esperti confrontabili | Sovrapposizione dentro ciascun testo | Sovrapposizione fra testi |
|---|---:|---:|---:|
| Codice / spiegazione | 71 | 46.16% | 28.76% |
| Codice / ragionamento | 91 | 44.91% | 30.13% |
| Spiegazione / ragionamento | 79 | 41.18% | 29.64% |

Questo e' un segnale di variazione associata al testo. Un solo testo per genere
non separa tema, lingua, formato, token ripetuti e posizione: non dimostra
neuroni specializzati per argomento. Inoltre la sovrapposizione interna resta
lontana dal 100%, quindi una maschera fissa perde parte delle attivazioni.

Il solo top160 ideale, scelto conoscendo l'h corrente, mantiene circa il 91–92%
dell'energia h^2 media, ma richiede il 54–55% dei byte dei pesi nonresidenti
chiamati: i neuroni sparsi toccano molti blocchi down. L'unione dei top160
dei candidati arriva al 70–71% dei byte degli esperti nonresidenti selezionati
dai candidati. Entrambe queste stime superano il budget del 30%.

## Prova effettiva delle maschere 3:10

Ogni pacchetto di dieci identita' occuperebbe 2.9908–2.9965 esperti integrali
nel layout stimato, indici inclusi. I quattro pacchetti complessivi occuperebbero
circa 20.2 MiB per testo. Questo NON significa tre esperti per tutto il modello.

Risultati sui **primi dieci input effettivi della continuazione**, l'orizzonte
delle predizioni. Le chiamate coperte hanno una maschera; le altre restano integrali.

| Testo | Chiamate nonresidenti coperte | Energia h^2 conservata nelle chiamate coperte, pesata per routing^2 | Errore L2 medio della somma routed dei 10 esperti | P99 dello stesso errore |
|---|---:|---:|---:|---:|
| Codice | 36.39% | 69.03% | 34.84% | 67.65% |
| Spiegazione | 33.21% | 56.56% | 29.85% | 65.80% |
| Ragionamento | 29.71% | 61.24% | 17.43% | 46.82% |

Errore = norma L2 della differenza / norma L2 dell'uscita GPU integrale,
calcolato sulla somma pesata degli esperti per layer/input. Media su 40 righe
(10 input x 4 layer); **non e' percentuale di risposte sbagliate** e non include
la propagazione dell'errore nel modello. Il solo contributo nonresidente ha
errori medi 39.59% / 37.66% / 35.30%. Residenti e fallback possono diluire
l'errore sulla somma totale: confrontare questi tre valori totali non misura
una diversa qualita' finale delle risposte.

Le stime ideali di byte letti in meno sono 21–25% sul percorso nonresidente,
oppure 9–20% includendo tutti i tier, nei primi dieci input. Sono stime senza
costi di costruzione e trasferimento e con errore elevato; **nessun aumento
di t/s e' stato misurato**. Il replay legge ancora blob integrali, calcola h
integrale e ne azzera le componenti escluse prima della proiezione down.
Non esiste ancora un kernel che legga un pacchetto fisico da tre esperti.

Le finestre a 20 e 63 input sono nei JSON. Un calo dell'errore aggregato con
l'aumento della finestra puo' derivare da maggiore fallback integrale; non
dimostra che una maschera vecchia diventi piu' accurata.

## Controlli e riproduzione

Tre replay diagnostici completati in 8.44 / 8.66 / 6.02 secondi di processo.
Per tutti: h e le cinque uscite di riferimento coincidono bit per bit con i
replay precedenti; maschere piene, maschere vuote, fallback e residenti passano
i controlli. La differenza numerica fra i due percorsi integrali e' circa
1.6–1.8e-8 L2 medio sui primi dieci input, lontana dall'errore di pruning.
Nessun processo di test rimasto attivo.

- `analyze_nonresident.py`: analisi CPU e selezione delle maschere; controlli
  sui byte delle quattro geometrie, condivisione dei blocchi, budget e determinismo.
- `nonresident-measurements.json`: indici di tutte le maschere, finestre,
  confronto degli stessi esperti fra testi e SHA256 degli input. Il campo
  `packed_output_error: null` descrive la sola fase CPU; il replay seguente
  contiene la misura GPU.
- `replay_nonresident.py` e `nonresident-gpu-replay.json`: runner con timeout,
  riferimenti SHA256, controlli e distribuzioni dell'errore. Dipendenze Python:
  numpy e psutil; replayer del fork con SHA256
  `ccb4bdc653912f5028dd87f3b15ceb1b8ffa725a6a146bf9388c86fa0a523375`.

Esempio da questa cartella, con percorsi adattati al laboratorio:

```text
python analyze_nonresident.py --lab <LAB> --output audit.json
python replay_nonresident.py --analysis audit.json --lab <LAB> --replayer <EXE> --replayer-sha256 <SHA256> --config <CONFIG_DAILY_LETTA_SOLTANTO> --output-dir <NUOVA_CARTELLA>
```

## Decisione

Mantenere il requisito 3:10 come obiettivo sperimentale. Questa euristica
non soddisfa l'accuratezza necessaria alla promozione nel Daily. Il prossimo
esperimento utile deve selezionare/compensare i neuroni in funzione dell'errore
**sull'uscita**, rispettare lo stesso budget in byte e usare input separati
per costruzione e verifica. Solo dopo va misurato un formato fisico compatto
con costo di rinnovo incluso. Il segnale di contesto giustifica studiare
pacchetti adattivi; non garantisce che il rapporto 3:10 sia raggiungibile.
