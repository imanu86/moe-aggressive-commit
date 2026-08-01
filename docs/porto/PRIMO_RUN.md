# PRIMO RUN SUL TRONCO — protocollo, da fare quando il blocco 9 atterra

Fino a qui il porto e' **codice che compila e fixture che passano**. Nessuna misura. Questo
documento fissa il primo run *prima* di farlo, cosi' non si sceglie il protocollo dopo aver
visto i numeri.

## L'ORDINE DEI BRACCI, e perche' e' questo

Il primo braccio **non** e' "il porto con la nostra politica accesa". E' il substrato **nudo**:

```
A   fork attuale, preset promosso            il riferimento che gia' conosciamo
B   tronco portato, TUTTI I FLAG SPENTI      cosa costa/rende UPSTREAM da solo
C   tronco portato, nucleo acceso            cosa aggiunge LA NOSTRA POLITICA
```

**B e' il braccio che nessuno pensa di fare, ed e' quello che separa due domande.** Se saltiamo
B e C va peggio di A, non sappiamo se e' colpa del substrato o della nostra politica portata
male. Con B lo sappiamo.

I flag da lasciare **assenti** in B (non a `0`: assenti):

```
DS4_CUDA_DYNAMIC_ARENA_GB      DS4_CUDA_PREFILL_MASS_OBSERVE
DS4_CUDA_VRAM_EXPERT_CACHE     DS4_CUDA_KV_STAGED_RING
```

## LE QUATTRO METRICHE, tutte e quattro sempre

Una sola non basta, e ci ho gia' sbagliato leggendo `avg=` al posto del regime:

```
END2END    tempo totale a muro della richiesta
dec.avg    il contatore avg= del server
REGIME     mediana dei chunk OLTRE il token 300      <- la piu' onesta
max        il picco
```

## E DICHIARARE IL REGIME, sempre

Il ginocchio dell'indexer sta a **~2048 token** ed e' architetturale
(`indexer.top_k = 512`, sta nei metadati del modello, ce l'ha anche l'M3 Ultra con tutto
residente). Quindi:

```
run da 600 token     interamente PRIMA del ginocchio
run da 2250          ~250 token dopo
run da 4877          piu' della meta' dopo
```

**Confrontare due run che stanno in regimi diversi e' confrontare due macchine diverse.** Per
settimane l'abbiamo fatto senza accorgercene.

## IGIENE, non negoziabile

```
un solo server alla volta, e chiuso col POST /__g130_u1_shutdown col token
MAI Stop-Process -Force: lascia la VRAM sporca e falsa il run dopo
QUIETE = 300 s fra un braccio e l'altro
  (a 20 s si misura una tempesta di sfratti: 885 per token)
zero daemon codex vivi: i loro grep sfrattano le pagine del modello dalla page cache
nessun altro processo che scrive su disco durante il run
mediana come misura primaria, piu' il cancello sui MB/s di paging
```

**Quindi il primo run si fa quando gli agenti hanno finito, non mentre lavorano.**

## IL RIFERIMENTO

```
X_CTL8K       4,42 t/s prima del ginocchio  ->  3,28 dopo   (-25,8%)
X_P8K_comb    4,59                          ->  3,49        (-24,0%)
```

## COSA CI ASPETTIAMO, scritto PRIMA

Dichiararlo prima e' l'unico modo perche' la misura possa smentirci:

- **B (substrato nudo) andra' PIU' LENTO di A.** Upstream non ha arena ne' tiering: ogni
  selected-load riparte da zero. **Se B fosse gia' piu' veloce di A, vorrebbe dire che la
  nostra politica non serviva**, e sarebbe la scoperta piu' importante della campagna.
- **C dovrebbe riavvicinarsi ad A**, non superarlo: stiamo portando la stessa politica, non una
  migliore. **Superare A sarebbe sospetto**, non una vittoria: andrebbe spiegato prima di
  festeggiare.
- Il guadagno vero arriva dopo, dalla route Q4_K che rimette il drafter dentro il grafo, e da
  DSpark col sidecar. **Non da questo run.**

## E IL SIDECAR

`D:\ds4-models\DSpark-support-Q2K-w2Q4K.gguf`, 7,83 GB, verificato: `dspark.block_size = 5`,
`markov_rank = 256`, `target_layer_ids = [40,41,42]` dentro i nostri 43 layer. **Non entra in
questo run**: prima si stabilisce che il tronco regge a pari politica, poi si aggiunge una
variabile per volta.

---

## APERTO: il disco C: legge a 59 MB/s e non e' normale

Misurato l'1/8 durante il wrap dell'arena, con CIM (i contatori PowerShell a campione
singolo davano zero: i rate ne vogliono due):

```
C: Lexar EQ790 1TB NVMe    58,9 MB/s   971 letture/s   100% attivo
                            coda 8      lettura media 62,1 KB
                            latenza ~8,2 ms  (coda / IOPS, legge di Little)
```

**8,2 ms per lettura su un NVMe** che dovrebbe stare fra 0,05 e 0,2. E 62 KB non e' una
lettura minuscola: anche sparse, un NVMe a coda 8 dovrebbe fare piu' di 1 GB/s.

L'utente conferma che quel disco **ha sempre letto cosi'**, quindi non e' una degradazione
recente e non spiega la differenza col riferimento. **Ma non e' nemmeno normale**, ed e' a
monte di tutto: se il trasporto dal disco rende l'1% del nominale, ogni misura di velocita'
che facciamo sta misurando quello.

**Da separare con un test solo**, fuori dal runtime, a macchina libera: lettura sequenziale
di un blocco grosso dallo stesso disco.

```
3-6 GB/s   il disco sta bene, il collo e' il NOSTRO pattern di accesso
~60 MB/s   e' il supporto o il percorso di I/O, e va guardato prima di ottimizzare altro
```

Il disco e' pieno all'**89%** (99,5 GB liberi su 930,7), che e' un candidato noto per il
collasso di un SSD, ma resta un'ipotesi finche' il test sequenziale non la conferma.
