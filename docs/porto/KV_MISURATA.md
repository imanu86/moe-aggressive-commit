# La KV, misurata — e perché il ring non serve

3 agosto 2026, notte. Quattro bracci, due contesti, con e senza `-nkvo`.

## Il dato

```
                       VRAM        regime      KV
A   ctx 10k, VRAM     9.793 MiB     7,37
B   ctx 10k, RAM      9.341 MiB     6,54      452 MiB
C   ctx 20k, VRAM    10.059 MiB     7,21
D   ctx 20k, RAM      9.336 MiB     6,83      723 MiB
```

**Verifica interna**: B e D danno la stessa VRAM (9.341 e 9.336) a contesti
diversi. Cinque MiB di scarto. Se la KV fosse rimasta anche solo in parte in
VRAM, il braccio a 20k ne mostrerebbe di più. La misura si valida da sola.

Da due punti misurati:

```
KV(n)  =  181 MiB fissi  +  26,5 MB per ogni 1k di contesto
a 150k:  ~4,1 GB
```

Concorda con la fonte esterna: il port di DSV4 su llama.cpp riporta ~6 GiB a
128k, cioè ~47 MB per 1k; noi misuriamo 44 a 10k e 26,5 al margine (la
differenza è la componente fissa, che nella media si diluisce).

## Il costo di tenere la KV in RAM CALA col contesto

```
ctx  10k                  -11,3%
ctx  20k                   -5,3%
ctx 150k (estrapolato)     sotto il 3%
```

Non è un'anomalia: è l'architettura. DeepSeek-V4 legge **~640 righe per token**
qualunque sia il contesto — finestra scorrevole di 128 più le 512 chiavi che
l'indexer seleziona. Quindi l'accesso alla memoria host costa una cifra
pressoché fissa per token, che pesa sempre meno man mano che il token si
allunga.

## Conseguenza: il ring KV non serve

A 150k la KV in VRAM è impossibile — 4,1 GB accanto ai 9,3 del modello su 12,3
disponibili. Ma spostarla in RAM costa meno del 3% e **lo fa gia' un flag che
esiste**, `-nkvo`. Il ring farebbe la stessa cosa scrivendo migliaia di righe,
per recuperare al massimo quel 3%.

Il ring non era sbagliato: e' **arrivato dopo**. Quando e' stato progettato su
DwarfStar, `-nkvo` non c'era e la KV non era compressa dall'architettura. Su
llama.cpp entrambe le condizioni sono cambiate.

## Due cose da non ripetere

**`-ctk` e `-ctv` sono IGNORATI su DSV4.** llama.cpp forza la KV a `f16` in due
punti, perché q8_0 corrompe l'inferenza in silenzio invece di dare errore.
Quindi il punto della coda del handoff — *"con KV in q8_0 il secondo strato
entra"* — e' morto in partenza, e chi lo prova vedra' solo il flag ignorato.

**I 900 token di questi bracci NON sono confrontabili con l'archivio.** I
finali (5,77 / 5,01 / 5,51 / 5,32) sembrano un crollo rispetto ai 6,86 del
riferimento, ma sono solo corti: a 900 token la media cumulativa e' ancora in
piena salita. I numeri buoni sono i regimi, e il braccio A a 7,37 e' in linea
con i 7,45-7,88 dell'archivio.

## Cosa resta aperto

Il muro dei 150k e' VRAM, non RAM, e nessuna quantita' di RAM lo sposta. Ma con
128 GB il contro-costo di `-nkvo` sparirebbe quasi del tutto (oggi si paga
perche' si sottrae spazio a un insieme di esperti gia' al limite, 62 GiB su
63,9). Quindi: **RAM + `-nkvo` = i 150k diventano raggiungibili**, senza
scrivere ring.

Da misurare quando ci sara' la RAM: `-nkvo` a 150k reali, con `ncmoe42` intatto.
