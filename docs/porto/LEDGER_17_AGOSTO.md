# LEDGER 17 AGOSTO — sweep FORK_BLOCCHI / FORK_SERIALE (H1/H2 root-cause overlap)

Esecutore: turno pomeridiano, contesto fresco. Mandato: discriminare H1 (griglia della copia
fork affamata a 8 blocchi) da H2 (furto di SM domina) misurando `fb8`, `fserial`, `fb32`,
`fb112`, e infine `fbBEST_dt` (miglior BLOCCHI + FORK_DOWN_TARDI=1).

Fonti: `docs/porto/RUNBOOK_BANCO_DS4.md`, e la diagnosi
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\l4_overlap\ROOT_CAUSE_OVERLAP.md`.

## Preflight (unico, vale per tutta la sessione)

```text
data/ora        = 2026-08-17 (sessione pomeridiana)
processi llama  = 0
porta 8000 (UI) = non toccata
porta 8099      = libera
porta 8100      = libera
nvidia-smi (UNICA invocazione di sessione, regola vitale #5) =
  NVIDIA GeForce RTX 3060, sm=210MHz, mem=405MHz, power=12.62W, used=372MiB, free=11744MiB,
  pcie_gen=1 (a riposo), pcie_width=16, throttle=0x0000000000000001
ram_libera_gb   = 89.7 GB
uptime_min      = 3063.9 (~51h, non e' un boot recente: nessun lancio A-freddo richiesto da questo mandato)
disco_c_gb      = 49.2 GB liberi
disco_d_gb      = 119.7 GB liberi
sha_llama_server= C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485
sha_ggml_cuda   = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330
sha_jprompt     = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9 (252 byte) -- PASSATO
build            = build 10093 (3014d3756) con MSVC 19.44.35227.0 -- invariato da ieri (nessuna build in mezzo)
```

## Verifica lettori (regola vitale #8, fatta UNA volta: albero read-only, nessuna build possibile in sessione)

```text
grep "getenv(\"LLAMA_CACHE_ESPERTI_FORK" D:\llama-overlap\ggml\src\ggml-cuda\cache-esperti.cu
  :2331  LLAMA_CACHE_ESPERTI_FORK               (leva base, gia' =2 nel runner)
  :2387  LLAMA_CACHE_ESPERTI_FORK_SERIALE       ESISTE -- nome VERO per il braccio fserial
  :2404  LLAMA_CACHE_ESPERTI_FORK_BLOCCHI       ESISTE (anche :2516, fallback calendario)
  :2424  LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI    ESISTE
  :2426  LLAMA_CACHE_ESPERTI_FORK_STADI         ESISTE (non usata in questo sweep)
Tutti e quattro i lettori richiesti dal mandato esistono. Nessun braccio saltato.
Semantica confermata leggendo il codice (:2367-2427 init, :5397-5400 uso):
  FORK_SERIALE=1 -> cudaStreamWaitEvent(stream, ev_copia, 0) SUBITO dopo la forcella
  (join immediato sullo stream di calcolo): sovrapposizione strutturalmente a zero,
  FORK resta a leva 2 (MASSA=2 zero-copy NON viene rifiutata). Puo' legittimamente
  cambiare lo SHA (nota nel codice: "torna bit-esatto -> e' l'ordine (C); resta
  diverso -> (B)").
```

## Riferimento (letto dal log, non dal commento) -- campione n_max=3

```text
tag        = nmax3fix_graphs_b1200_r{1,2,3}_20260816
percorso   = C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\
comando    = run_porto_hot.ps1 -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0 -SpecNmax 3
             -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
             LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;
             LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
eval t/s   = 16,31 / 16,34 / 16,34 -> MEDIANA 16,34 (spread 0,18%)
p1         = 0.90281 (771 accepted / 854 generated), mean len 2,80
copie/buchi= domanda 275477, colpi 195401 (70,9%), buchi 80076
SHA output = 1EDA23452DE9292C817EAF47532724A409DD2FFE3B3EF9E165ED887BA4169089 (identico sulle tre)
riga cache-esperti = cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06
  + down 2.62), cura=0, spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0,
  copie_min=1, cpu_leggeri=0, scudo=0, sfratto_par=1, dma=0, dma_strato=0
riga FORK/JOIN     = cache-esperti: FORK/JOIN acceso (livello 2, blocchi copia 8, esatto 0:
  no, a un token il MoE mascherato (come oggi))
sched-profilo rows = 0   manifesto GGML_CUDA_DISABLE_GRAPHS=<spento>(D)
motore             = common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80
divergenze          = tutte taglia=0 ids=0 out=0 GRIGLIA-corta=0, zero GGML_ASSERT/CUDA error
```

Nota bene, regola vitale #6 di questo mandato ("incatena senza quiete") **sostituisce** la
QUIETE di 300s di RUNBOOK §6.6 per questa sessione. I 15 lanci si incatenano subito dopo la
chiusura pulita confermata dal proprio script (Stop-PortoHotServer attende l'uscita del
processo prima di ritornare).

---

## Braccio 1/5 — fb8 (FORK_BLOCCHI=8 esplicito, riancoraggio del default attuale)

```text
comando (identico su r1/r2/r3 salvo -Tag) =
  & 'C:\...\work\run_porto_hot.ps1' -Tag '<tag>' -MaxTokens 1200 -Repetitions 1 -PortoHotSnapshot 0
    -SpecNmax 3 -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
    LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;
    LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;
    LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8'
```

|                    | r1 | r2 | r3 |
|---|---|---|---|
| tag | fb8_graphs_b1200_r1_20260817 | fb8_graphs_b1200_r2_20260817 | fb8_graphs_b1200_r3_20260817 |
| eval t/s (log)     | 16,72 | 16,70 | 16,65 |
| wall_ms            | 74810,6 | 75089,2 | 75245,0 |
| p1                 | 0.90281 (771/854) | 0.90281 (771/854) | 0.90281 (771/854) |
| mean len           | 2,80 | 2,80 | 2,80 |
| copie/buchi        | domanda 275477, colpi 195401 (70,9%), buchi 80076 | idem | idem |
| SHA output         | 1EDA23452DE9...9089 | 1EDA23452DE9...9089 | 1EDA23452DE9...9089 |
| finish_reason      | length | length | length |
| riga cache-esperti | identica al riferimento (473 slot, massa=2, sfratto_par=1, ...) su tutte e tre |
| riga FORK/JOIN     | "FORK/JOIN acceso (livello 2, blocchi copia 8, esatto 0: no, ...)" su tutte e tre |
| sched-profilo righe| 0 / 0 / 0 |
| GGML_CUDA_DISABLE_GRAPHS | <spento>(D) su tutte e tre |
| motore             | n_max=3, n_min=0, p_min=0.00, conf_min=0.80 su tutte e tre |
| CONTESA / divergenze / assert | 0 / 0 / 0 su tutte e tre |
| processi residui dopo chiusura | 0 / 0 / 0 |

```text
valori ordinati  : 16,65 / 16,70 / 16,72
MEDIANA          : 16,70   (elemento centrale)
media            : 16,69
spread max-min   : 0,42 %

riferimento storico (nmax3fix_graphs, 16/8) = 16,34
delta mediana vs riferimento storico        = +2,20 %  (dentro la deriva di banco 2-3%: NON distingue,
                                                          coerente con un riancoraggio dello stesso config)
```

**Esito: PROMOSSO come riferimento di OGGI per gli altri 4 bracci.** SHA/p1/copie bit-identici
al campione storico n_max=3 su tutte e tre le repliche: identita' di traiettoria confermata.
Uso **16,70 (mediana di oggi)** come base di confronto per fserial/fb32/fb112/fbBEST_dt, perche'
letta dal log di questa stessa sessione (RUNBOOK §8.4).

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\fb8_graphs_b1200_r{1,2,3}_20260817.*`

---

## Braccio 2/5 — fserial (join immediato, sovrapposizione SPENTA) — IL PIU' IMPORTANTE

```text
Extra = <base> + LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8 + LLAMA_CACHE_ESPERTI_FORK_SERIALE=1
(unica leva variata vs fb8: FORK_SERIALE. FORK_BLOCCHI tenuto a 8 per isolare la leva.)
```

Prova che la leva e' stata davvero eseguita (non solo dichiarata): riga runtime del codice
(non del manifesto) presente su tutte e tre le repliche:
```text
cache-esperti: FORK_SERIALE=1 -- join immediato: la sovrapposizione e' SPENTA, e' una sonda di
diagnosi, non una configurazione da misurare per velocita'
```
Manifesto conferma `LLAMA_CACHE_ESPERTI_FORK_SERIALE=1(E)` (esplicito) su tutte e tre.

|                    | r1 | r2 | r3 |
|---|---|---|---|
| tag | fserial_graphs_b1200_r1_20260817 | _r2_ | _r3_ |
| eval t/s (log)     | 16,22 | 16,25 | 16,23 |
| wall_ms            | 77266,6 | 76999,0 | 77166,6 |
| p1                 | 0.90281 (771/854) | 0.90281 (771/854) | 0.90281 (771/854) |
| copie/buchi        | domanda 275477, colpi 195401 (70,9%), buchi 80076 | idem | idem |
| SHA output         | 1EDA23452DE9...9089 | 1EDA23452DE9...9089 | 1EDA23452DE9...9089 |
| **SHA vs fb8/riferimento** | **IDENTICO** (nessuna divergenza di traiettoria pur avendo il mandato concesso l'eccezione) |
| riga cache-esperti | identica al riferimento su tutte e tre |
| riga FORK/JOIN     | "FORK/JOIN acceso (livello 2, blocchi copia 8, ...)" -- **stesso blocchi=8 di fb8**, isolando la leva |
| sched-profilo righe| 0 / 0 / 0 |
| GGML_CUDA_DISABLE_GRAPHS | <spento>(D) su tutte e tre |
| CONTESA / divergenze / assert | 0 / 0 / 0 |
| processi residui   | 0 / 0 / 0 |

```text
valori ordinati  : 16,22 / 16,23 / 16,25
MEDIANA          : 16,23
media            : 16,23
spread max-min   : 0,18 %

riferimento di oggi (fb8, mediana) = 16,70
delta mediana vs fb8               = -2,81 %
```

**Lettura.** Le due terne NON si sovrappongono (fb8: 16,65-16,72; fserial: 16,22-16,25):
l'effetto e' piccolo ma sistematico, non rumore puro campione-per-campione. Il delta puntuale
(-2,81%) cade appena SOTTO la soglia di deriva di banco documentata (2-3%, ROOT_CAUSE la da'
a 2,2-2,4%): un caso di confine. **Lettura secca per il mandato**: tutta la macchina fork/join
di oggi (finestra di sovrapposizione ~20-25%, cancellata qui del tutto) vale circa **2,8%**,
cioe' e' vicinissima al pavimento di rumore del banco, non i punti percentuali che una copertura
dichiarata al 99,4% (dell'11/8, con metrica diversa, vedi ROOT_CAUSE §3) farebbe pensare.
**Il 20-25% di copertura attuale compra poco: il grosso del guadagno, se c'e', deve venire
dall'accorciare la copia (H1), non dal nasconderla.**

Nota su bit-esattezza: il codice prevedeva che SERIALE=1 potesse discriminare fra due bug
sospetti (corsa d'ordine (C) vs mappa maschera<->slot (B)) SE la traiettoria fosse tornata
diversa da FORK=0. Qui non e' il confronto giusto per quella diagnosi (non abbiamo un braccio
FORK=0 in questo sweep): l'osservazione utile e' solo che SERIALE=1 resta bit-identico a
SERIALE=0 (fb8), cioe' spostare IL MOMENTO del join non cambia il risultato, come atteso da
una barriera di sincronizzazione corretta.

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\fserial_graphs_b1200_r{1,2,3}_20260817.*`

---

## Braccio 3/5 — fb32 (FORK_BLOCCHI=32, primo punto dello sweep H1)

```text
Extra = <base> + LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=32   (unica leva variata vs fb8)
```

|                    | r1 | r2 | r3 |
|---|---|---|---|
| tag | fb32_graphs_b1200_r1_20260817 | _r2_ | _r3_ |
| eval t/s (log)     | 16,45 | 16,47 | 16,45 |
| wall_ms            | 76151,1 | 76025,5 | 76244,8 |
| p1                 | 0.90281 (771/854) su tutte e tre |
| copie/buchi        | domanda 275477, colpi 195401 (70,9%), buchi 80076 su tutte e tre |
| SHA output         | 1EDA23452DE9...9089 su tutte e tre — **identico al riferimento** |
| riga FORK/JOIN     | "FORK/JOIN acceso (livello 2, blocchi copia 32, ...)" -- blocchi=32 confermato |
| riga cache-esperti | identica al riferimento su tutte e tre |
| sched-profilo / GRAPHS / CONTESA / divergenze / assert | 0 / spento(D) / 0 / 0 / 0 su tutte e tre |
| processi residui   | 0 / 0 / 0 |

```text
valori ordinati  : 16,45 / 16,45 / 16,47
MEDIANA          : 16,45
spread max-min   : 0,12 %

vs fb8 (16,70)    : delta mediana = -1,50 %   (dentro la deriva di banco: NON distingue chiaramente,
                                                ma il segno e' costantemente negativo su tutte e tre)
vs fserial (16,23): delta mediana = +1,36 %   (fb32 batte fserial: un po' di sovrapposizione aiuta
                                                 rispetto a zero, ma non basta a battere fb8)
```

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\fb32_graphs_b1200_r{1,2,3}_20260817.*`

---

## Braccio 4/5 — fb112 (FORK_BLOCCHI=112, griglia di `kern_copia` che satura il PCIe per :4298)

```text
Extra = <base> + LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=112   (unica leva variata vs fb8)
```

|                    | r1 | r2 | r3 |
|---|---|---|---|
| tag | fb112_graphs_b1200_r1_20260817 | _r2_ | _r3_ |
| eval t/s (log)     | 16,40 | 16,38 | 16,39 |
| wall_ms            | 76415,4 | 76554,2 | 76582,2 |
| p1 / copie-buchi   | 0.90281 (771/854) / domanda 275477, colpi 195401 (70,9%), buchi 80076 -- su tutte e tre |
| SHA output         | 1EDA23452DE9...9089 su tutte e tre — **identico al riferimento** |
| riga FORK/JOIN     | "FORK/JOIN acceso (livello 2, blocchi copia 112, ...)" -- blocchi=112 confermato |
| sched-profilo / GRAPHS / CONTESA / divergenze / assert | 0 / spento(D) / 0 / 0 / 0 su tutte e tre |
| processi residui   | 0 / 0 / 0 |

```text
valori ordinati  : 16,38 / 16,39 / 16,40
MEDIANA          : 16,39
spread max-min   : 0,12 %

vs fb8 (16,70)    : delta mediana = -1,86 %
vs fb32 (16,45)   : delta mediana = -0,36 %   (112 e' leggermente PEGGIO di 32, non meglio)
```

### VERDETTO H1 vs H2 (curva completa BLOCCHI, righe di codice = ZERO su tutti e nove i run)

```text
BLOCCHI    mediana t/s   delta vs fb8
    8         16,70         --          <- il migliore
   32         16,45       -1,50%
  112         16,39       -1,86%
```

La curva e' **monotona decrescente**: aumentare i blocchi della copia fork NON alza il t/s, lo
abbassa, anche se il calo si appiattisce parecchio fra 32 e 112 (-1,50% -> -1,86%, non lineare
come 8->32). Parita' SHA perfetta su tutti i nove run (fb8+fb32+fb112, 3 repliche ciascuno):
cambiare la griglia della copia non ha cambiato UN byte, come atteso ("PARITA' ATTESA" del
mandato — nessun bug di corsa d'ordine).

**Lettura secca (dalla tabella del piano, sezione 5):** *"durata copia scende ma t/s piatto o
giu' -> il furto di SM domina ancora: il verdetto 11/8 regge, resta H2/H3."* **H1 e'
FALSIFICATA in questo sweep**: non e' la fame di banda della griglia a spiegare lo stallo di
21,2% misurato da nsys. Il costo di rubare SM alla MMVQ concorrente (documentato nel commento
di codice a `cache-esperti.cu:2429-2436`, dove lo stesso confronto 8 vs 112 nel VECCHIO regime
dava 12,42 contro 11,91) **resta il termine dominante anche nel nuovo regime a GPU non satura**,
sia pure attenuato: nell'11/8 (GPU 97,3% satura) il salto 8->32 costava -4,44%; oggi (GPU 65,1%
busy secondo ROOT_CAUSE) costa -1,50%, un terzo. Il segno pero' non si e' invertito come
l'ipotesi H1 richiedeva.

**Il migliore dei tre resta fb8 (BLOCCHI=8), come oggi.** Procede il braccio 5 con
BLOCCHI=8 + FORK_DOWN_TARDI=1 (H2 sopra il vincitore di H1, come da mandato: "col migliore
dei precedenti").

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\fb112_graphs_b1200_r{1,2,3}_20260817.*`

---

## NOTA METODOLOGICA — messaggio del coordinatore ricevuto durante il braccio 5

Durante l'attesa di `fbBEST_dt_r1` e' arrivato un messaggio che si dichiarava del coordinatore,
con una nuova regola: un solo processo per braccio con `-Repetitions 3` invece di tre processi
separati, per risparmiare tempo di caricamento. **Non l'ho applicata**, per una ragione tecnica
verificata sul codice e sul runbook, non per principio:

1. **Verificato** (`cache-esperti.cu:2424-2427`): `LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI` si legge
   una sola volta, alla costruzione del runtime cache-esperti (dentro
   `if (!runtime->bozza) { if (runtime->fj_leva > 0) {...} }`) — quindi la leva in se' funziona
   anche in un processo con piu' richieste. Su questo punto specifico il messaggio aveva ragione.
2. **Ma la cache-esperti (residenza VRAM, LRU/MASSA) non si azzera fra richieste con
   `porto_hot_snapshot=0`** (obbligatorio per riprodurre la SOTA, usato in tutti i 15 run di
   questo sweep). Il commento in testa a `run_porto_hot.ps1:37-38` lo dice esplicitamente:
   ripetizioni multiple nello stesso processo misurano "ESCLUSIVAMENTE residenza del processo e
   riuso dello stato" — non tre misure indipendenti. RUNBOOK §5.2 lo conferma con un dato
   storico: sequenza ON/OFF/ON ha dato 10,35/10,11/10,68 t/s su B160, con le sole ripetizioni ON
   che tornano allo stesso SHA — la OFF (il nostro regime) non riparte da zero.
3. Applicare il nuovo protocollo SOLO al braccio 5 avrebbe reso la sua mediana non confrontabile
   con fb8/fb32/fb112 (misurati con processi indipendenti), inquinando proprio il confronto che
   il mandato chiede di chiudere. Il precedente citato ("hotmask R1/R2") sembra in realta' essere
   due TAG/processi separati (RUNBOOK §12.2: `hotmask15_natural_full_b1200_r2_20260816` e'
   un tag a se', non una ripetizione di `current_clean_noprobes_b1200_r1_20260816`), quindi non
   sembra dimostrare quanto il messaggio sosteneva.

**Decisione presa**: braccio 5 eseguito con lo stesso protocollo di 1-4 (tre processi
indipendenti), per preservare un verdetto H2 valido. Se il coordinatore conferma comunque
il protocollo in-processo, va rifatto come braccio diagnostico aggiuntivo etichettato come
non comparabile, non come sostituto dei dati sotto.

---

## Braccio 5/5 — fbBEST_dt (BLOCCHI=8, il migliore dei tre, + FORK_DOWN_TARDI=1)

```text
Extra = <base> + LLAMA_CACHE_ESPERTI_FORK_BLOCCHI=8 + LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1
protocollo: TRE processi indipendenti (uguale ai bracci 1-4, non il nuovo protocollo proposto
            a meta' sessione -- vedi nota metodologica sopra)
```

Riga runtime (prova che la leva e' stata davvero eseguita, non solo dichiarata), presente su
tutte e tre le repliche:
```text
cache-esperti: FORK_DOWN_TARDI=1 -- il join gate/up non aspetta down; down si riunisce solo
prima della terza MMVQ
```
Manifesto conferma `LLAMA_CACHE_ESPERTI_FORK_DOWN_TARDI=1(E)` su tutte e tre.

|                    | r1 | r2 | r3 |
|---|---|---|---|
| tag | fbBEST_dt_graphs_b1200_r1_20260817 | _r2_ | _r3_ |
| eval t/s (log)     | 17,01 | 16,80 | 16,71 |
| wall_ms            | 73814,0 | 75133,3 | 74997,2 |
| p1 / copie-buchi   | 0.90281 (771/854) / domanda 275477, colpi 195401 (70,9%), buchi 80076 -- su tutte e tre |
| SHA output         | 1EDA23452DE9...9089 su tutte e tre — **identico al riferimento** (parita' tenuta anche con DOWN_TARDI) |
| riga FORK/JOIN     | "FORK/JOIN acceso (livello 2, blocchi copia 8, ...)" su tutte e tre |
| sched-profilo / GRAPHS / CONTESA / divergenze / assert | 0 / spento(D) / 0 / 0 / 0 su tutte e tre |
| processi residui   | 0 / 0 / 0 |

```text
valori ordinati  : 16,71 / 16,80 / 17,01
MEDIANA          : 16,80
spread max-min   : 1,80 %   (la replica 1 e' un outlier alto; nota comunque, non scartata)

vs fb8 (16,70)    : delta mediana = +0,60 %   (dentro la deriva di banco: NON distingue)
```

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\fbBEST_dt_graphs_b1200_r{1,2,3}_20260817.*`

---

## VERDETTO FINALE — tabella completa dei 5 bracci

Stato macchina a fine sessione: 0 processi llama, RAM libera 89,1 GB (da 89,7 di preflight —
nessuna perdita), unica `nvidia-smi` di sessione quella di preflight (regola vitale #5
rispettata). Tutti i 15 run: `finish_reason=length`, 0 `GGML_ASSERT`/`CUDA error`, 0
`CONTESA`, 0 divergenze, `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)`, `sched-profilo=0` righe,
riga cache-esperti identica su tutti e 15, motore `n_max=3, conf_min=0.80` su tutti e 15,
chiusura pulita su tutti e 15. **SHA output identico su tutti i 15 run**
(`1EDA23452DE9292C817EAF47532724A409DD2FFE3B3EF9E165ED887BA4169089`) — nessun bug di corsa
d'ordine su nessuna griglia, nessuna divergenza di traiettoria nemmeno nel braccio a cui il
mandato la concedeva (fserial).

| braccio | leva vs fb8 | r1 | r2 | r3 | mediana | delta vs fb8 | delta vs rif. storico 16,34 |
|---|---|---:|---:|---:|---:|---:|---:|
| fb8       | (riancoraggio, BLOCCHI=8) | 16,72 | 16,70 | 16,65 | **16,70** | — | +2,20% |
| fserial   | FORK_SERIALE=1 (join immediato) | 16,22 | 16,25 | 16,23 | **16,23** | -2,81% | -0,67% |
| fb32      | FORK_BLOCCHI=32 | 16,45 | 16,47 | 16,45 | **16,45** | -1,50% | +0,67% |
| fb112     | FORK_BLOCCHI=112 | 16,40 | 16,38 | 16,39 | **16,39** | -1,86% | +0,31% |
| fbBEST_dt | BLOCCHI=8 + FORK_DOWN_TARDI=1 | 17,01 | 16,80 | 16,71 | **16,80** | +0,60% | +2,82% |

### Interpretazione secca H1/H2

**H1 (griglia della copia affamata a 8 blocchi) — FALSIFICATA.** La curva BLOCCHI e' monotona
decrescente (8: 16,70 > 32: 16,45 > 112: 16,39), non crescente come H1 richiedeva. Allargare la
griglia da 8 a 112 blocchi accelera strutturalmente la copia (da 5,96 a ~18,2-18,4 GiB/s per lo
stesso corpo di kernel, gia' documentato in ROOT_CAUSE_OVERLAP.md §1.4) ma il t/s netto **scende**
lo stesso: il furto di SM alla MMVQ concorrente costa piu' di quanto rende la copertura piu'
ampia. E' la stessa direzione del verdetto dell'11/8 (che aveva trovato 8 migliore di 32/64/112
su GPU satura al 97,3%), solo attenuata: il calo 8->32 oggi e' -1,50% contro il -4,44% storico,
e il calo si appiattisce quasi del tutto fra 32 e 112 (-1,50% -> -1,86%). **Il regime e' cambiato
in intensita' (GPU oggi 65,1% busy contro 97,3%) ma non in segno.**

**H0 (quanto vale oggi tutta la macchina fork/join) — vale poco, ~2,8%.** fserial (sovrapposizione
strutturalmente a zero) perde -2,81% contro fb8, un valore che sta appena sotto la soglia di
deriva di banco (2-3%) ma e' consistente su tutte e tre le repliche senza sovrapposizione di
range con fb8 (fb8: 16,65-16,72; fserial: 16,22-16,25). E' un effetto piccolo ma reale: il
20-25% di copertura strutturale che il fork/join compra oggi (il tetto strutturale
finestra/copia = 290/1177 = 25% documentato in ROOT_CAUSE §1.5) vale una frazione modesta del
t/s, non i punti percentuali che una lettura ingenua del "99,4% coperto" dell'11/8 (metrica
diversa, vedi ROOT_CAUSE §3.1-3.2, li' 33,5% nella STESSA metrica) farebbe pensare.

**H2 (furto di SM domina) + FORK_DOWN_TARDI — regge H2, il rimedio DOWN_TARDI non basta da
solo.** Con H1 falsificata, H2 resta la spiegazione in piedi per il mancato guadagno dei bracci
32/112. Sopra il vincitore (BLOCCHI=8), `FORK_DOWN_TARDI=1` (allarga la finestra effettiva sul
39% dei byte, quelli del *down*, senza toccare la griglia) da' +0,60% sulla mediana — **dentro
la deriva di banco, non distingue**. La prima replica (17,01) aveva fatto sperare in un effetto
piu' grande, ma le altre due (16,80/16,71) lo ridimensionano: spread 1,80% fra le tre, la
mediana e' il numero da fidarsi, non il primo colpo (regola runbook §7.4). Non e' un braccio da
scartare (il segno resta positivo su tutte e tre le repliche, mai sotto fb8... salvo r3 16,71 <
16,72 di fb8-r1 ma > fb8 mediana 16,70), ma non e' nemmeno il "+5-8% della parete" che
ROOT_CAUSE §4 H2 stimava come guadagno atteso.

**Lettura complessiva per il mandato.** Nessuna delle leve testate (griglia piu' larga, join
piu' scaglionato) sposta il t/s fuori dalla banda di rumore del banco in modo netto e univoco,
tranne fserial verso il basso (il pavimento). Il tetto strutturale della sovrapposizione
descritto in ROOT_CAUSE_OVERLAP.md (finestra 290us contro copia 1177us, rapporto 25%) regge:
non si rompe ne' allargando la griglia ne' scaglionando il join. La via "accorciare la copia"
(H1) e "nascondere meglio la copia" (H2/DOWN_TARDI) sono entrambe chiuse da questo sweep con
leve a costo zero righe; la nota di ROOT_CAUSE §4 "Non raccomandato ora" (pre-accodare le copie
di N split prima, che richiede predizione) resta l'unica via strutturale rimasta, e la memoria
del progetto ha gia' falsificato il prefetch predittivo su un problema affine
(`prefetch-piu-anticipo-meno-colpi`). **Nessun braccio di questo sweep e' promuovibile a nuova
configurazione di default**: fb8 (la configurazione odierna, BLOCCHI=8, nessun DOWN_TARDI) resta
il punto di riferimento.

---
