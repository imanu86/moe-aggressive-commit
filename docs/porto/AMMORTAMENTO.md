# L'ammortamento misurato — e perché la seconda GPU va al draft

3 agosto 2026. Il test che decide se DSpark vale una seconda scheda, fatto
senza comprare niente.

## Il metodo

La speculazione verifica K token in **una** passata. Guadagna solo se una parte
grossa del costo è **per passata** invece che **per token**. Il prefill è
esattamente quello scenario — molti token in una passata — quindi il rapporto
fra il costo per token in prefill e in decode misura direttamente la frazione
ammortizzabile.

Il modello va scaldato **prima**: il prefill dei run brevi del 2/8 dava 1,0-2,8
t/s, ma era dominato dal primo tocco delle pagine su modello freddo. Qui una
richiesta normale da 600 token precede la misura.

## Il dato

```
prefill  3374 token in batch      29,81 ms/token     33,5 t/s
decode      1 token per passata  138,05 ms/token      7,2 t/s
```

Per differenza (il termine `per_passata/512` è trascurabile):

```
costo PER PASSATA   ~108 ms     78% del totale
costo PER TOKEN      ~30 ms     22%
```

**Il 78% del costo di un token non dipende dal token.** Sono attenzione,
backbone, lanci di kernel e sincronizzazioni: pagati identici che se ne produca
uno o cinquecento.

È la conferma quantitativa della tesi *orchestration-bound* che stava in atlante
da luglio, con un numero pulito invece che per inferenza.

## Il conto di DSpark rifatto

Accettazione 0,907 (misurata il 2/8, blocco 1). Con 5 token abbozzati,
i token accettati per ciclo sono ~4,65.

```
verifica di 5 token      108 + 5 x 30    =  258 ms
draft su GPU dedicata    5 passate       =   50-150 ms    <- unica incognita
                                           ----------
totale per ciclo                            308-408 ms
diviso 4,65 accettati                        66-88 ms/token
```

Contro i 138 attuali: **da 1,6 a 2,1 volte**, cioè da 7,2 a 12-14 t/s.

## Perché DSpark era fallito

Non per l'accettazione, che era buona (0,907). Il draft girava su **CPU**
(`-ngld 0`), rubando tempo alla stessa CPU che macina gli esperti: costo fisso
+110,6 ms/token, che mangiava l'intero guadagno. Il handoff lo attribuiva a
"draft caricato più una passata", ed è esattamente la voce che una GPU dedicata
azzera.

## La conseguenza sulla decisione hardware

```
7 strati di esperti su GPU2    guadagno DENTRO IL RUMORE, mai dimostrato
                               (il +5,8% per strato sta dentro il 6,9% di
                               varianza fra run identici)
draft DSpark su GPU2           1,6-2,1x, su un ammortamento misurato
```

La seconda GPU va comprata **per il draft**. E si incastra con l'aritmetica:
il draft occupa 10.391 MiB dei 12.288 della scheda, non lascia spazio agli
esperti — ma non serve, perché quel posto varrebbe molto meno.

## Cosa resta da misurare

**Quanto costa una passata del draft su GPU dedicata.** Nel conto sopra sono
10-30 ms stimati, ed è l'unico anello non misurato: determina se il guadagno è
1,6 o 2,1.

Si può misurare **senza comprare la scheda**: caricare il solo draft sulla 3060
attuale (10,4 GiB su 12,3, ci sta) e cronometrare una passata. Il modello grande
non gira, ma non serve.

E resta il rischio non tecnico: **non c'è un secondo slot x16**. Il percorso è
riser alimentato su x1, mai provato — né che lo slot sia aperto in fondo, né che
llama.cpp bilanci due schede su link asimmetrici. Il traffico misurato (55-66
MB/s contro i ~985 dell'x1) dice che la banda basta, ma è l'unica delle tre
incognite che abbiamo chiuso.
