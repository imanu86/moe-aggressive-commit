# Il gate deve essere dinamico: il nucleo stabile è il 5%

3 agosto 2026, sera. Seconda metà della misura per la soglia del gate SSD→RAM.
La prima diceva quanto vale il rango; questa dice se una soglia tarata su un
dominio vale su un altro.

## Il dato

Tre mappe per rango, 1500 token ciascuna, ctx 10000, stessa configurazione.
Domini scelti lontani fra loro:

```
campagna   landing page HTML cyberpunk      9.032 esperti toccati
prosa      saggio storico in italiano       8.931
codice     albero rosso-nero in C           8.949
```

Esperti necessari a coprire il 90% della massa (peso `2^-rango`):

```
                        esperti      RAM
campagna                  2.381    15,7 GB
prosa                     2.220    14,6 GB
codice                    2.795    18,4 GB

NUCLEO comune ai tre         268     1,8 GB    = 5% dell'unione
UNIONE                     5.511    36,3 GB
```

**Il nucleo stabile è il 5%.** Un insieme caldo statico coprirebbe un
ventesimo del lavoro: il gate *deve* essere dinamico, esattamente come l'utente
lo ha specificato — «appena diventano rilevanti si portano in RAM, quando
freddi escono su SSD».

Coerente col 28% di colpi che l'insieme caldo statico prende a ledger, e con la
ragione documentata per cui la mask collassa fuori dominio.

## Una validazione che viene gratis

Le somiglianze a coppie rispettano la semantica:

```
HTML  <-> codice    jaccard 0,25      <- entrambi codice
prosa <-> codice    jaccard 0,15
HTML  <-> prosa     jaccard 0,11      <- i piu' lontani
```

I due domini di codice si somigliano più di quanto ciascuno somigli alla prosa.
Non l'avevamo imposto in nessun modo: è la struttura del modello che affiora
dalla misura, ed è un buon segno che il dato sia reale.

## Dove vive la specializzazione

```
quota di nucleo comune ai tre domini, per fascia di strati

primi 3   (0-2)      20,8%      generici
primi 6   (0-5)      14,3%
centrali  (6-36)      2,8%      specializzati
ultimi 6  (37-42)     2,3%
```

I primi tre strati sono da sette a nove volte più indipendenti dal dominio del
resto. **Quei 268 esperti del nucleo — 1,8 GB — sono candidati a restare
residenti senza alcuna decisione**, e i primi tre strati sono dove conviene
cercarne altri.

E la dimensione per fascia dice quanto costa il dominio:

```
                    campagna   prosa   codice
primi 3                  334     417      379
centrali                1480    1513     1804
ultimi 6                 410     129      408
```

Negli ultimi sei strati la prosa impegna 129 esperti, HTML e codice oltre 400.
La profondità è dove i compiti di codice pagano.

## I parametri che ne escono per il gate

```
residente per dominio      15-18 GB
churn al cambio dominio    fino a 14,1 GB  (2.140 esperti)
unione di tre domini       36,3 GB         -> ENTRA nei 64 GB
```

L'ultima riga è la più importante: **tenendo residente l'unione dei domini
recenti si sta dentro la RAM**, con ~25 GB liberi per il resto — drafter
compreso. Il modello nudo da 80,76 GB non ci sta; il suo insieme di massa sì.

Il churn di 14 GB non si paga in blocco: la politica lo spalma man mano che gli
esperti diventano rilevanti, che è il disegno.

## Cosa resta aperto

**Quale `w(rango)`.** Il compromesso è ora visibile e non era ovvio: la massa
ripida dà un insieme più piccolo per dominio (14,6-18,4 contro 22,9-25,8 GB)
ma **sovrappone di meno** fra domini (jaccard 0,11-0,25 contro 0,20-0,35),
quindi più churn al cambio. Più selettiva significa più specializzata. La
scelta dipende da quanto spesso il dominio cambia, ed è una misura, non un
gusto.

**Un conteggio non spiegato.** I run `campagna` e `codice` hanno prodotto
esattamente 194.274 record e 1.165.644 selezioni, con prompt di 43 e 41 token.
Le mappe sono dimostrabilmente diverse (md5 distinti, 17.959 righe differenti,
testi generati in tema), quindi l'analisi regge — ma la coincidenza non ha una
spiegazione e resta annotata.
