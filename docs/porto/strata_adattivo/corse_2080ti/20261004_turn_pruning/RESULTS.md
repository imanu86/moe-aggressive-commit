# Pruning causale per turno: prova del 4 ottobre 2026

**La selezione congelata dai token precedenti non supera il filtro sperimentale,
neppure eliminando solo il 10% dei neuroni degli esperti selezionati.**
Nessuna modifica al Daily, al launcher, alla configurazione o allo ZIP pubblico.
I processi di prova sono terminati. Non e' stata misurata una nuova SOTA.

## Protocollo

RTX 2080 Ti modificata a 22 GB, Ryzen 5800X, 96 GiB RAM, Windows, CUDA 12.6,
SM75; Qwen3.8-Flash-Next GSQ-RCO IQ3_XXS. Riutilizzate le tracce full-model
code/explain/reason dell'esperimento probe100, senza generare nuovo carico
artificiale. Prefissi di 86/85/102 token; i quattro layer sono 0/1/35/36.
Il replayer non alloca KV: questa non e' una prova a profondita' 250k.
La cattura originale aveva capacita' 262144, KV int8/residente32768, spec4,
5080 slot esperto/8442 MiB; questi non sono consumi del replayer.

Per ogni testo, i primi 32 input della continuazione calibrano una maschera,
tenuta fissa sui successivi 31. Il codice che sceglie i neuroni riceve solo le
righe di calibrazione. Esperti con meno di quattro osservazioni restano completi.
Il primo input dopo il prefisso e' `pos=prefix`; si esclude la riga precedente
che appartiene all'ultimo token del prompt.

Due criteri separati ordinano i neuroni: media e massimo, sulle osservazioni
precedenti, di `router_weight^2 * h_i^2 * ||W_down[:, i]||_2^2`.
La norma delle colonne viene dai pesi originali dequantizzati; il criterio stima
il contributo individuale all'uscita, senza modellare le cancellazioni fra neuroni.
Il massimo tenta di conservare anche contributi importanti ma rari. Nessun criterio
usa le attivazioni future per scegliere i neuroni. Si conservano 576/512/480
neuroni su640: tagli esatti del10/20/25%, a parita' di esperti eleggibili.

Sono 18 combinazioni (3 testi x2 criteri x3 tagli), su **93 input distinti,
372 somme routed di layer e3720 chiamate esperto**. Le varianti condividono gli
input: non sono18 conversazioni indipendenti. Sei replay GPU valutano le tre
maschere contemporaneamente; una settima esecuzione ripete reason/mean con
controlli completi e azzerati. La prima serie precedente alla correzione del
quantizzatore, descritta sotto, non entra nei risultati finali.

Il filtro dichiarato prima delle misure richiedeva a una singola variante fissa,
su ciascuno dei tre testi: L2 medio <=3%, P99 <=10%, risparmio ideale dei pesi
>=3%. E' un criterio per decidere se investire nel kernel compatto, non una
garanzia sulla qualita' del modello. **Nessuna variante lo supera.**

## Risultati dopo la correzione del banco

Errore relativo L2 della somma dei dieci contributi routed, con pesi di routing
originali e riferimento sullo stesso backend GPU:

| Testo | Criterio | Medio, taglio10% | Medio, taglio20% | Medio, taglio25% | P99, taglio10% |
|---|---|---:|---:|---:|---:|
| Codice | Media | 8.520% | 12.890% | 14.722% | 28.033% |
| Codice | Massimo | 8.272% | 12.706% | 14.715% | 27.975% |
| Spiegazione | Media | 7.671% | 12.108% | 13.680% | 37.438% |
| Spiegazione | Massimo | 8.077% | 12.074% | 13.617% | 38.534% |
| Ragionamento | Media | 6.974% | 9.091% | 10.266% | 79.525% |
| Ragionamento | Massimo | 5.029% | 8.990% | 10.147% | 23.506% |

Già sul primo input successivo alla calibrazione, ogni variante ha un layer con
errore >10%; un controllo completo immediato con questa soglia disabiliterebbe
il pruning. Non si tratta soltanto di una maschera che invecchia a fine turno.
La media sulla calibrazione stessa e' comunque2.79–3.87% al taglio10%: anche la
selezione comune a molte osservazioni comporta un compromesso gia' in campione.

Le maschere si applicano soltanto al37.34%/25.16%/13.63% delle chiamate future
(code/explain/reason); le altre usano l'esperto integrale. Si riporta anche
l'errore condizionato agli esperti effettivamente potati nel JSON, per non
nascondere l'errore dietro al fallback.

| Testo | Risparmio ideale sui pesi, taglio10% | Taglio20% | Taglio25% |
|---|---:|---:|---:|
| Codice | 2.452% | 4.904% | 6.130% |
| Spiegazione | 1.647% | 3.293% | 4.116% |
| Ragionamento | 0.905% | 1.810% | 2.263% |

Queste stime riguardano i pesi delle chiamate routed nei quattro layer, su tutti
i tier, includendo il fallback. Contano le righe gate/up conservate e i blocchi
down originali ancora toccati, senza riquantizzare i pesi. Media e massimo danno
qui gli stessi byte. Non sono traffico DRAM/PCIe misurato, spazio totale del
modello, o guadagni t/s. Il replayer legge ancora l'intero esperto e azzera h;
indici, aggiornamenti delle maschere e controlli periodici costerebbero in piu'.

## Controllo fallito, correzione e ripetizione

Il controllo iniziale con tutti i neuroni conservati ha mostrato una differenza
in1/2560 chiamate: reason, posizione141, layer1, esperto67. L2 locale0.039054%,
delta assoluto massimo2.737716e-5; L2 della somma routed0.001674%.
Il percorso masked usava `native_quantize_q8_1`, mentre il riferimento conservava
il Q8 prodotto da `native_expert_grouped`. H e i riferimenti completi coincidevano.

Il replayer ora usa `quantize_q8_1_rows`, lo stesso quantizzatore del percorso
grouped. Cambia solo il diagnostico, non i kernel online. Sono state ripetute
tutte le sei prove e il controllo completo: le2560 uscite del controllo full
coincidono bit per bit, le zero sono esattamente nulle, la ripetizione del taglio
10% coincide bit per bit. Quattro coppie GU/down:17/20,16/42,18/20,18/42.
La piccola differenza iniziale non spiegava gli errori del pruning; la correzione
rende il confronto piu' rigoroso. [Audit iniziale](initial-control.json).

Altri controlli: ricostruzione identica delle sei maschere, aggregazione L2
indipendente, dequantizzazione vettoriale contro scalar su blocchi reali e
fixture note, conteggi e maschere annidate, fallback bitwise, riferimenti full
e h bitwise rispetto alla cattura precedente. I vecchi vettori oracle2..4 non
sono un vincolo bitwise: erano calcolati col quantizzatore standalone.

## Artefatti e riproduzione

- [Misure complete e curve](measurements.json), [verifica](verification.json),
  [build e sorgenti](build.json), [stato finale](final-state.json).
- [Runner](measure.py), [controlli e ripetizione](verify.py), maschere in `masks/`.
- Replayer corretto SHA256:
  `64b55b1bef1b4ef4528ab8be9d7cc7f4465ed878e40ddf3b60bd00667d7a970c`.

Compilare `neuron_trace_replay` nel fork con `STRATA_BUILD_NEURON_REPLAY=ON`.
I runner accettano `--fork`, `--lab`, `--config`, `--replayer`, una directory di
output nuova; `measure.py` richiede anche l'hash del binario, `verify.py` la
directory `--run`. `--config` viene letto solo per il percorso modello/DLL e
per verificare che il Daily resti identico. Il modello e le grandi tracce SNT/SNR
non sono inclusi nel repository. `--lab` deve contenere le cartelle originali
`probe100-{code,explain,reason}-normal-v1`, con `result.json`, `c0-target.snr` e
`target/trace.bin`; hash degli input nei risultati. Non avviare il replayer
mentre e' attivo un engine Strata: i runner lo rifiutano.

Questa e' una prova locale su input/routing del modello completo. Non propaga
l'errore nei layer successivi, non genera risposte potate, non misura accuratezza
o latenza di chat e non prova la stabilita' su un corpus di domini. I risultati
non escludono altri predittori condizionati sull'input corrente o selezioni con
piu' dati; escludono la promozione di questa specifica euristica al Daily.
