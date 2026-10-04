# Esperti divisi in blocchi GPU/CPU: prova completata, 4 ottobre 2026

**Il completamento CPU funziona: nessun neurone viene eliminato. Nel confronto
a parita' di pesi attivi in VRAM non emerge un vantaggio di velocita'.**
Il prototipo resta sperimentale; Daily, configurazione, launcher e ZIP invariati.

## Implementazione reale

Un esperto da 640 neuroni viene diviso in dieci blocchi da 64. I blocchi 0, 4, 9
vanno in GPU (192 neuroni); gli altri sette restano in RAM (448 neuroni).
Si copiano righe gate/up e blocchi down originali: nessuna riquantizzazione,
colonna azzerata o duplicazione dei blocchi di peso. La ricostruzione dei due
pacchetti riproduce tutti i byte originali.

Il kernel GPU esistente riceve un blob fisicamente piu' piccolo. Il pool CPU
ora usa la larghezza del formato n_ff per distribuire righe e quantizzare h,
entro il limite dei suoi buffer da 640 neuroni. La larghezza ordinaria 640
resta il percorso operativo. La CPU e la GPU calcolano parti complementari;
la CPU somma i propri contributi pesati, ne trasferisce 2560 float alla GPU,
che completa la somma. Il trasferimento dell'input alla CPU e' incluso.

Il programma separato `hybrid_expert_probe` si compila solo con
`STRATA_BUILD_NEURON_REPLAY=ON`; non e' integrato nel dispatcher del server.
Il confronto e' fra:

- tre esperti completi in GPU e sette completi su CPU;
- il 30% di ciascuno dei dieci esperti in GPU e il restante 70% su CPU.

In entrambi i casi i pesi attivi occupano esattamente tre esperti in GPU e sette
in RAM. Buffer di lavoro e metadati differiscono: non si afferma che il totale
di tutte le allocazioni CUDA sia identico. Per ciascun caso tutti i pesi sono
precaricati; nel primo percorso i tre esperti sono quelli col maggiore peso
di routing corrente. Nessuno dei due percorsi misura una politica di cache online.

## Campione e controlli

RTX 2080 Ti modificata a 22 GB, Ryzen 5800X, 96 GiB RAM, CUDA 12.6, SM75.
Qwen3.8-Flash-Next IQ3_XXS. Input e routing reali dalle tracce code/explain/reason,
prefissi 86/85/102 token, primi dieci input della continuazione, layer 0/1/35/36:
120 casi distinti, dieci esperti per caso. Si verifica un token alla volta;
non e' una misura di decode speculativo con gruppi di token.
Il banco non alloca KV: non e' una prova a profondita' 250k.

Controlli completati:

- ricostruzione dei pesi bit per bit e dimensioni esatte 30%+70%;
- somma delle parti CPU contro esperto completo CPU: L2 massimo 2.11e-7;
- somma delle parti GPU contro esperto completo GPU: L2 massimo 9.19e-8;
- somma finale del percorso misurato contro somma indipendente dei contributi;
- guardia dell'output CPU, output finiti, dataset e sorgenti verificati con SHA256;
- 192 scenari del test `pool_quant_parity`, larghezze 192/448/640, token 1..8,
  host partecipante/non partecipante, quantizzazione seriale/parallela e batch 97
  oltre il limite interno di 96. Risultati bitwise uguali fra le due modalita';
- smoke dei quattro formati anche con quantizzazione intermedia parallela.

Il percorso misto differisce dal riferimento tutto GPU dello 0.8495% L2 medio,
massimo 1.2687%; il riferimento tutto CPU differisce dello 1.0330% medio,
massimo 1.5474%. Sono confronti locali fra backend e quantizzazioni delle
attivazioni. **Non provano identita' dei token o correttezza di una conversazione
completa**; le differenze piccole possono comunque cambiare la generazione.

## Tempi e ripetizione per variabilita'

La prima serie (5 round da 20 iterazioni) includeva anche tutto CPU e tutto GPU.
Mostrava esiti misti e forte variabilita': variazione della latenza ibrida rispetto
al confronto con tre esperti GPU pari a -1.80% / +6.29% / +1.58%.
Per questo e' stata ripetuta alternando A/B e B/A **sullo stesso caso a ogni
round**, 9 round da 60 iterazioni per percorso. Nessun carico artificiale,
nessun altro benchmark o build in parallelo.

Tabella della ripetizione: mediana dei round per caso, poi media dei 40 casi
di ciascun testo. Un valore positivo nell'ultima colonna significa piu' lento.

| Testo | 3 GPU completi + 7 CPU, microsecondi | 30% GPU + 70% CPU, microsecondi | Variazione latenza |
|---|---:|---:|---:|
| Codice | 947.98 | 970.39 | +2.36% |
| Spiegazione | 865.64 | 876.67 | +1.27% |
| Ragionamento | 720.04 | 730.99 | +1.52% |
| Tutti i 120 casi | 844.55 | 859.35 | +1.75% |

Il percorso ibrido vince in 47/120 casi. Persiste variabilita': il rapporto
massimo/minimo fra round del medesimo caso ha mediana 1.48 nel riferimento e
1.56 nell'ibrido. Non interpretiamo la piccola differenza come una stima precisa
di un rallentamento universale: **non c'e' un'accelerazione riproducibile da
promuovere**, nemmeno nel caso favorevole di pesi gia' pronti.

Il cronometro comprende D2H dell'input, quantizzazioni, calcolo CPU e GPU,
riduzione CPU, H2D del contributo, somma GPU e sincronizzazione finale.
Esclude costruzione/upload dei pacchetti, allocazioni e riscaldamento.
Le letture sono ripetute su working set caldi: non rappresentano la pressione
sulle cache e sulla memoria dell'intero modello. Il costo diagnostico
`pack_and_inverse_check_us` comprende anche la ricostruzione di controllo e
non e' una misura del solo costo di packing utilizzabile in produzione.

## Esito

La divisione a blocchi risolve l'eliminazione dei contributi e consente di
eseguire davvero porzioni di esperto su dispositivi diversi. Con il budget
3:10 conserva pero' la stessa quantita' totale di pesi da leggere del confronto
3 GPU + 7 CPU; distribuisce quel lavoro su piu' esperti. Il banco non dimostra
un risparmio di latenza. Nessuna nuova SOTA e nessuna conversione di questi tempi
in t/s del server. Una futura integrazione richiederebbe un motivo misurato
per migliorare cache, trasferimenti o bilanciamento, oltre a verifica completa
delle risposte e del costo di rinnovo.

`measurements.json` conserva tutti i round, i due protocolli, controlli e SHA256;
`analyze_hybrid.py` ricalcola le statistiche senza GPU; `verification.json`
attesta controlli indipendenti dell'analizzatore e preservazione del Daily.
`build.json` conserva i sorgenti esatti della build misurata. Il convertitore
pubblico `tools/sm75/hybrid_probe_input.py` riproduce i tre dataset byte per byte.
I processi di test sono terminati.
