# Il tasso di cambio della VRAM — siamo sul ginocchio

3 agosto 2026. Spazzata su `-ngl`, quattro punti, per rispondere a due domande
con una misura sola: *quanto costa il backbone in RAM* (l'idea di liberare VRAM
per il draft DSpark) e *quanto vale un GB di VRAM* (la decisione hardware).

## La curva

```
           regime      VRAM        ms/token    costo marginale
-ngl 99     7,37     9.793 MiB      135,7
-ngl 32     4,58     7.761 MiB      218,3      41,6 ms per GB
-ngl 22     3,73     6.034 MiB      268,1      29,5 ms per GB
-ngl 12     3,31     4.318 MiB      302,1      20,3 ms per GB
```

Con `-cmoe` gli esperti stanno su CPU comunque, quindi `-ngl` muove **solo
backbone e attenzione**. La curva è **concava**: il costo marginale cala man
mano che si toglie.

## Il ginocchio

Letta al contrario, quella concavità dice che **i 12 GB della 3060 coprono
quasi esattamente ciò che il backbone chiede**. Siamo sul ginocchio:

```
sotto il ginocchio   1 GB vale  20-42 ms   backbone: DENSO, letto per intero ogni token
sopra il ginocchio   1 GB vale    4,5 ms   esperti: SPARSI, 6 selezionati su 256
```

**Nove volte di differenza**, e si può comprare solo nella fascia povera —
quella ricca è già piena.

Il 4,5 ms/GB viene dall'unico punto che abbiamo sopra il ginocchio: `ncmoe42`
contro `cmoe`, cioè uno strato di esperti in VRAM, che vale +5,8% (7,88 contro
7,45 di regime, dal ledger del 2/8).

## Conseguenza 1: backbone in RAM è morta

L'idea era liberare VRAM spostando il backbone in RAM, per metterci il draft di
DSpark residente e togliere il costo fisso della speculazione (110,6 ms/token
secondo il handoff).

I ~5 GB che servono al draft quantizzato a 2 bit costerebbero **+160 ms su una
base di 136**: la velocità si dimezza. Il criterio di morte (35%) era stato
fissato prima di guardare ed è stato superato al primo punto.

La ragione è strutturale: il backbone è denso e letto per intero a ogni token
(~7,6 GB), gli esperti selezionati sono 1,7 GB. Spostare il primo in RAM
significa quadruplicare il traffico sulla memoria più lenta. La speculazione lo
ammortizzerebbe su 4 token accettati, cioè lo dividerebbe per 4 — ma partendo da
-38% per soli 2 GB, la divisione non arriva in pari, e nel frattempo
moltiplicherebbe per 5 il lavoro sugli esperti.

## Conseguenza 2: la decisione hardware

```
+64 GB di RAM                 nessuna VRAM, ma toglie il RISCALDAMENTO
5060 16 GB (sostituzione)     +4 GB nella fascia povera     ~+13%
3060 12 GB usata + riser      +12 GB stessa fascia          ~+40% teorici
```

Il "+40%" è un'estrapolazione lineare da **un solo** punto sopra il ginocchio, e
questa macchina ha mostrato rendimenti decrescenti ovunque l'abbiamo guardata.
Aspettarsi +20-25% è più prudente.

E c'è un criterio che i t/s non catturano: **la RAM è l'unica opzione che toglie
il riscaldamento**, cioè i primi ~2000 token in cui il modello va da 4,5 a 8,3
t/s. Su scambi brevi il riscaldamento *è* quasi tutta la corsa, e un +13% di
regime non lo vedi mai perché il regime non lo raggiungi.

## Vincoli fisici accertati (3/8)

```
scheda madre   ASUS PRIME B550M-A WIFI II
slot           1 x PCIe 4.0 x16 (occupato)  +  2 x PCIe 3.0 x1
M.2            M.2_1 PCIe 4.0 x4 da CPU, M.2_2 PCIe 3.0 x4 da chipset
               uno solo occupato (Lexar 1TB) -> UNO LIBERO
Thunderbolt    assente
CPU            Ryzen 7 5800X
```

**Niente secondo slot x16.** Ma il traffico misurato sul bus durante il decode è
**55-66 MB/s** — le attivazioni attraversano il confine 43 volte per token e
costano solo questo, perché gli esperti li legge la CPU dalla RAM e non passano
mai dal PCIe.

Quindi anche un **PCIe 3.0 x1** (~985 MB/s) ha 16 volte il margine necessario, e
una seconda GPU su riser alimentato x1→x16 è tecnicamente sensata. Il solo punto
dolente è il caricamento: ~12 GB a 1 GB/s sono ~20 s per avvio.

Via **rete** invece no: gigabit dà 1,8x di margine invece di 16x, e soprattutto
aggiunge ~13 ms per token di sola latenza (43 attraversamenti x ~0,3 ms di round
trip). Più il fatto che il calcolo remoto sarebbe più lento, e gli strati sono
sequenziali: i tempi si sommano, non si sovrappongono.

## Da misurare prima di comprare

1. **`ncmoe41` rifatto.** A ledger è falsificato per travaso WDDM, ma quella
   misura è di una giornata in cui ogni server veniva ucciso senza rilasciare.
   Oggi ci sono 954 MB di margine. Se entra, hai già uno strato in più gratis.
2. **Il consumo reale della GPU durante il decode.** Con gli SM al 35-39% la
   3060 sta ben sotto i suoi 170 W, ma non l'abbiamo mai misurato: sono 30
   secondi di `nvidia-smi --query-gpu=power.draw` durante un run.
3. **Dove si piega la curva sopra il ginocchio.** Abbiamo un punto solo. Con due
   strati invece di uno si saprebbe se il rendimento cala subito o regge.
