# Il decadimento è falsificato: dimenticare fa perdere gli esperti strutturali

4 agosto 2026, mattina. Lo sweep sul decadimento della massa, su NeuraForge a
8000 token.

## Perché lo si è provato

La misura precedente diceva che la mappa invecchia: col blocco per massa, a
1500 token il minimo era 2,87 t/s e zero campioni sotto i 2; a 8000 il minimo
scendeva a 1,12 e il 2,7% stava sotto i 2. La massa si accumula da inizio corsa
e non dimentica mai, quindi a fine corsa descrive una fase che non c'è più.

E l'utente aggiungeva l'osservazione giusta: dentro **una** pagina HTML il
dominio cambia di colpo — corpo, poi CSS, poi JS, poi prosa nei commenti.

## Il dato

Media mobile esponenziale sull'incremento fra passate, `TOPK=1200`, tutto il
resto identico. Tutti e tre hanno prodotto 5.822 token.

```
                    ms/token   t/s   mediana   min   <4t/s  <2t/s   p10
D10  nessun decad.   153,89   6,50    6,98   1,62    4,7%   1,8%   5,73
D09  emivita 660     184,41   5,42    6,64   0,32   25,9%  10,1%   1,97
D08  emivita 300     174,52   5,73    6,77   0,52   18,3%   8,0%   2,31
```

**Il decadimento perde su tutto**: velocità (−12% e −17%), coda (minimo da 1,62
a 0,32), e soprattutto decimo percentile — da 5,73 a 1,97, cioè il caso
sfavorevole diventa tre volte peggiore.

## Il meccanismo del danno è nei contatori della politica

```
                     sbloccati   falliti
D10  nessun decad.      2.006        55
D09  emivita 660        3.871       410
D08  emivita 300        6.100       862
```

**La rotazione triplica e i fallimenti si moltiplicano per sedici.** L'insieme
sbatte: ogni sbattimento costa una coppia di chiamate di sistema *più* il
rifault delle pagine appena rilasciate, che il modello richiede subito dopo.

La lettura: dimenticare fa perdere gli esperti **strutturali** — quelli che
servono per tutta la pagina, in ogni fase — per inseguire quella corrente. La
mappa accumulata li contiene entrambi, ed è per questo che vince.

Nota: 5,42 e 5,73 sono dentro il rumore fra loro (la varianza fra run identici
è ±7,6%, vedi sotto). Il risultato solido è «decadimento peggio di nessun
decadimento», non l'ordinamento fra i due valori di alfa.

## Il cancello di identità regge, e la varianza no

```
D10  22.918 caratteri   sha 26639992d995d473
D09  22.918 caratteri   sha 26639992d995d473
D08  22.918 caratteri   sha 26639992d995d473
```

Uscita identica bit per bit fra i tre — e identica anche ai tre bracci
dell'ablazione precedente. Il gate non tocca cosa il modello calcola.

Ma D10 ha fatto **6,50** dove M1, con configurazione *identica*, aveva fatto
**6,04** tre ore prima: **7,6% di scarto fra due run della stessa cosa.** È il
motivo per cui il riferimento va rifatto dentro ogni giro, e per cui nessuna
differenza sotto il 10% qui significa qualcosa.

## Conseguenza sullo sweep reattivo, che era pronto

Era pronto `reattivo_8k.ps1` con emivita 50 e 100 token e periodo di ricalcolo
a 25 token, sull'intuizione che servisse **più** reattività. Quello sweep va
nella direzione appena falsificata, e i contatori dicono perché: a emivita 300
la rotazione era già 6.100 sblocchi: a 50 token esploderebbe.

Non è stato lanciato. Se si vuole ancora tirare quel filo, l'unico braccio con
un'ipotesi propria è `E00` — periodo 25 token **senza** decadimento — che
separa l'effetto del ricalcolo più fitto da quello del dimenticare. Ma è una
domanda diversa da quella che l'utente aveva posto.
