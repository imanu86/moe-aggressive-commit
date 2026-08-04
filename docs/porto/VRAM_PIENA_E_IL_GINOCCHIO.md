# Riempire la VRAM costa il 12%. Mappare di piu' rende ancora.

4 agosto 2026, sera.

## L'idea dell'utente, e perche' era buona

Restano sempre ~1,5 GB di VRAM non allocati che non si riempiono mai. E' un
difetto di granularita': libero 2.144 MiB, uno strato di esperti 1.728 MiB,
llama.cpp alloca per unita' intere e si ferma quando il pezzo successivo non ci
sta.

L'argomento per riempirlo non era il calcolo (vale ~0,7%, sotto il rumore): uno
strato in VRAM **sparisce dalla RAM e non puo' mai faultare**. E' la stessa
logica del pinned, sulla memoria migliore.

Si e' fatto posto con `-ub 32` invece di 64, che libera 557 MiB. Costa sul
prefill, che nel banco e' di 74 token.

## Il dato

Tutti a `-ub 32`, cosi' il confronto ha una variabile sola.

```
                        ms/token   t/s    mediana   min    p10    sotto 2 t/s
Y0  17 mappati           157,51    6,35    6,52    3,37   5,97      0,0%
Y1  17 mappati + 1 VRAM  178,85    5,59    6,45    0,54   2,17      9,0%
Y2  22 mappati + 1 VRAM  162,48    6,15    6,31    3,64   5,79      0,0%
```

Due confronti puliti:

```
Y0 -> Y1   aggiungere lo strato in VRAM     -12,0%
Y1 -> Y2   passare da 17 a 22 mappati       +10,0%
```

## Riempire la VRAM: falsificato, ma non per il motivo che sembra

Tutto quello che doveva succedere e' successo:

```
lo strato E' in VRAM       dedicata +1.803 MiB (esattamente lo strato)
NON sborda in condivisa    29.541 contro 29.542, identica
il paging SCENDE           2.260 -> 1.501 pagine/s  (-34%)
```

E la velocita' cala del 12%.

**La perdita non e' nel calcolo.** La mediana e' 6,45 contro 6,52: uguale. E'
tutta nel pavimento -- min 0,54, p10 2,17, il 9% del tempo sotto 2 t/s contro
lo 0,0% di Y0. Lo strato in VRAM ha **rimesso in circolo i crolli** che lo
zero-copy aveva eliminato.

Il meccanismo NON e' stabilito, e due spiegazioni comode sono gia' morte:

- **Non e' la strettoia di VRAM.** Y1 lascia 341 MiB liberi, Y2 ne lascia 354 --
  praticamente identici -- e Y2 non crolla mai.
- **Non e' la pressione sulla RAM.** Tutti e tre girano con ~330-355 MB
  disponibili: la macchina e' satura in tutti e tre.

Resta che cinque strati mappati in piu' (Y2) **curano** il danno. Perche', non
lo so.

## Il ginocchio non c'e' ancora

```
 8 strati    6,11        meta' del beneficio di 17
17 strati    6,37        +12,1% sul controllo
22 strati    +10,0% su Y1, con lo strato in VRAM ancora addosso
```

Sempre in salita. E' l'unica leva della campagna che scala con un parametro, e
non ha ancora mostrato un limite.

## Il buco nel disegno, dichiarato

Y2 ha **due** differenze da Y0: cinque strati mappati in piu' *e* lo strato in
VRAM. Quindi **22 mappati senza strato in VRAM non e' misurato da nessun
braccio**, ed e' la configurazione piu' interessante che abbiamo.

L'aritmetica la darebbe a 6,15 / 0,88 = 6,99 t/s. Non la conto: e' lo stesso
metodo -- dedurre per sottrazione da un rapporto assunto costante -- che il 4/8
mattina ha prodotto i 538 ms fantasma della testa di Markov, misurati poi a 2.

Il braccio `M22` in `mappa_ginocchio.ps1` lo misura, insieme a `M26` (43,9 GiB
pinned, che dovrebbe rompersi: piu' page cache di quanta RAM ci sia) e a un
terzo `M17` di riproducibilita'.

## Nota di riproducibilita'

`-ub 32` e `-ub 64` sulla stessa configurazione danno **6,35 e 6,37**: 0,3% di
scarto fra due run in giorni e condizioni diverse, contro il +-7,6% misurato
con gli esperti su CPU.

Non e' un caso. Senza crolli non resta niente che vari -- ed e' un effetto
collaterale utile dello zero-copy che vale quasi quanto la velocita': i
confronti tornano a essere leggibili.
