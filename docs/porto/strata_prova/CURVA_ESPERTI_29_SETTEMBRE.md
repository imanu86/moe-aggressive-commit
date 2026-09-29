# Strata: esperti in VRAM contro velocita' — 29 settembre 2026 mattina

Domanda dell'utente prima di costruire la cache elastica: con piu' esperti in VRAM si va piu' veloce? Stesso motore
(b38c183), stesso banco (`banco_strata.py --profilo curva`: L01-L04 a 32k, L01-L02 a 131k), quattro dimensioni di cache
in serie fra le 6:27 e le 7:15 (`curva_strata.py`), altri programmi a 0,55-0,98 GB di VRAM.

Il testo generato cambia con la residenza degli esperti (GPU e CPU arrotondano diversamente), quindi l'accettazione
della bozza cambia da corsa a corsa: la misura della cache e' il **costo per riga verificata** (`costo_passata.py`:
righe = passate + bozze offerte), non i t/s grezzi.

| esperti in VRAM | GiB | VRAM libera a carico finito | ms per riga | token per passata | t/s |
|---:|---:|---:|---:|---:|---:|
| 788 | 1,30 | 4.111 MiB | 45,1 | 1,91 | 19,0 |
| 1.451 | 2,39 | 2.669 MiB | 35,9 | 1,88 | 23,6 |
| 2.691 | 4,41 | 822 MiB | 32,6 | 1,82 | 25,9 |
| 2.795 | 4,58 | 459 MiB | 33,3 | 1,89 | 25,5 |
| 1.915 (28/9 notte, altre condizioni) | 3,15 | 616 MiB | 27,1 | 2,18 | 31,6 |

**Lettura.** Rendimenti decrescenti: da 788 a 1.451 esperti la riga costa il 20% in meno, da 1.451 a 2.691 il 9%, oltre
niente. Il router e' concentrato: i primi ~1.500 esperti prendono gran parte del traffico. La cache elastica serve
soprattutto a non restare piccola (lanciata su un picco di VRAM: 702-788 esperti, 43-45 ms per riga) e a non andare in
sovraccarico quando gli altri programmi crescono; oltre ~2.000 esperti il guadagno di velocita' e' piccolo.

**Le condizioni contano piu' della cache.** A parita' di esperti, la mattina costa il 20-30% in piu' della notte:
durante le corse `JumpConnect` (Jump Desktop, il controllo remoto) usava ~2,6 core e Defender ~1 core, e la corsia CPU
di Strata ne vuole 7 su 8. Con meno esperti in VRAM la CPU ha piu' lavoro e ne soffre di piu'.

**Difetto trovato in Strata.** Con piu' slot il prefill sceglie blocchi da 6.144 token (con meno slot 4.096): i punti di
ripresa della conversazione (ogni 16K) cadono ai bordi dei blocchi, a 18.432 invece di 16.384 e 32.768, e i follow-up a
32k rileggono ~14.500 token (31 s invece di 2). Rimedio: blocchi che dividono 16K (4.096 o 8.192) o punti di ripresa
esatti.

## Fork e PR (29/9)

`fork_strata.py` (136 fork, 14 con commit propri: `fork_avanti_29settembre.json`) e `pr_elenco_29settembre.tsv`.
Per la cache elastica esiste gia' la PR #37 di code-martin (VMM: `cuMemAddressReserve`/`cuMemCreate`/`cuMemMap`,
provata su Windows con CUDA 12.6), chiusa dal manutentore per tre difetti: cresce solo fino alla dimensione di avvio,
dopo un resize ricopia la tabella di residenza di avvio sopra quella viva (esperti sbagliati dopo l'adattamento),
restringendo toglie la regione che il prefill prende in prestito. La #38 ritoccava l'adattamento (decadimento 0,985
invece di 0,7): il manutentore accetterebbe solo opzioni per le soglie, con misura prima/dopo.
