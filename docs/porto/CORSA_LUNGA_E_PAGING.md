# La corsa lunga, e la premessa sbagliata sul disco

3 agosto 2026, pomeriggio. Chiude un buco metodologico trovato dall'utente e
ne apre uno vero nel mio lavoro di ieri.

## Il buco metodologico

**Tutti** i run speculativi della campagna erano da 300 token o meno — S2, T2,
T3, U1, W1, W2, e i 120 di Fable. Il verdetto «DSpark perde» era dato su
quelli, mentre la regola scritta la notte prima (`curva_run.py`, e in memoria)
dice che la media cumulativa dipende dalla lunghezza della corsa: lo stesso
controllo fa 4,24 t/s a 300 token e 6,73 di regime a 1500.

E c'era una ragione specifica per aspettarsi un ribaltamento: **l'accettazione
cresce con la lunghezza**.

```
120 token    0,503
300 token    0,636
1500 token   0,699      (1049 accettati / 1501, lunghezza media 4,41)
```

## Il verdetto, ora sulla corsa giusta

Due bracci, ctx 10000, 1500 token, `-ngl 99 -ncmoe 42 -ub 64`, stesso momento:

```
                  REGIME   finale   accettazione
L0  controllo      6,73     5,94        —
L1  DSpark         4,43     3,81      0,699
                   -34%
```

**DSpark perde il 34% anche sulla corsa lunga.** L'accettazione più alta non
compensa: il collo resta la verifica MoE-CPU, che non dipende da quanto bene
il draft indovina.

Il verdetto non cambia, ma adesso poggia sulla misura giusta.

## E la premessa che avevo sbagliato

Il 2/8 sera avevo scritto: *«in regime stazionario il disco è a zero e
l'insieme di lavoro (62 GiB) entra nei 63,9 disponibili»*. Su quella premessa
avevo **falsificato la fase 2 del reap-loop** — sfratto e prefetch — prima
ancora di scriverla.

Campionato durante questa corsa (classi CIM, non `Get-Counter`: i percorsi con
nomi inglesi danno `-1` su Windows italiano), **finestra di sola generazione**:

```
33 campioni
  mediana   1.343 fault duri/s
  media     2.068
  massimo  11.828
  a zero    3 campioni su 33
RAM libera inchiodata a ~280 MB per tutta la generazione
```

**Il disco non è a zero.** C'è traffico SSD→RAM continuo, a raffiche, per
tutta la corsa. La fase 2 del reap-loop, e con essa il gate per massa che
l'utente ha specificato, hanno lavoro da fare — **nella condizione che
l'utente aveva indicato: quando c'è il drafter.**

Il drafter aggiunge 6,8 GB di pressione residente, ed è quello che porta la
lista libera a 280 MB.

## I buchi della GPU

Normalizzati sul tempo di decode:

```
controllo   1 buco sotto 2,5 t/s ogni 161 s
drafter     1 ogni  36 s        <- 4,5 volte piu' frequenti
```

Più frequenti nel braccio con più pressione di memoria, con VRAM dedicata
piatta e CPU occupata durante il buco. Coerente con l'ipotesi dell'utente —
pagine fredde riprese da SSD — ma **non dimostrato**: il campionamento è a 10
secondi e i buchi durano ~2, quindi l'allineamento istantaneo non è
verificabile con questi dati. Il rapporto 4,5× è però un segnale, non
un'impressione.

## Due errori di misura fatti oggi, nello stesso pomeriggio

1. **`llama_confronto.ps1` non è usabile sotto Utilità di pianificazione**:
   stampa con `Write-Host`, che senza console fallisce con «Handle non valido»
   0x6 e uccide il braccio. Il run del regime ci ha perso il controllo.
2. **Ho letto «mediana 0 fault duri» su campioni presi dopo l'uscita del
   server.** La RAM libera che salta da 290 a 58.755 MB era il processo che
   terminava, non il regime stazionario. Misurare la finestra sbagliata, di
   nuovo.

E uno di lettura: i «278 MB liberi» del primo campionamento erano
`FreePhysicalMemory` (lista libera), non `AvailableMBytes` (libera + standby,
58 GB). Con un modello da 81 GB mappato, la RAM piena di pagine in cache è il
comportamento voluto, non una carestia.
