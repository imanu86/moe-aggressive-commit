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

## Riancoraggio genealogia calda — warm_anchor_b1200_20260817

Decisione dell'utente (tramite coordinatore), arrivata dopo l'obiezione sollevata sopra: la
genealogia CALDA (residenza che sopravvive fra richieste consecutive nello stesso processo)
diventa il regime ufficiale per la produzione, separato e NON comparabile a verdetto con la
genealogia fredda dei 5 bracci sopra. Protocollo: un processo, `-Repetitions 4`, richiesta 1 =
warm-up (dato, fuori verdetto), verdetto = mediana delle richieste 2-4.

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'warm_anchor_b1200_20260817' -MaxTokens 1200
  -Repetitions 4 -PortoHotSnapshot 0 -SpecNmax 3
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0'
  (FORK_BLOCCHI non passato = default del runner = 8, stessa griglia di fb8)
telemetria = work\sample_hw.ps1 -Tag warm_anchor_b1200_20260817 -OutDir <runs> -IntervalSeconds 2
  (avviato non appena il processo llama-server compare, fermato da solo alla sua uscita)
```

**Cancelli di processo (una volta sola)**: manifesto `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` —
PASSATO. `sched-profilo` righe = 0 — PASSATO. Motore `n_max=3, n_min=0, p_min=0.00, conf_min=0.80`
— PASSATO. Riga cache-esperti identica al riferimento (473 slot, massa=2, sfratto_par=1, ...) —
PASSATO. FORK/JOIN acceso, blocchi copia 8 — PASSATO. `CONTESA`=0, `GGML_ASSERT`/`CUDA error`=0
— PASSATO. Processi residui dopo chiusura = 0 — PASSATO.

### Serie per richiesta (valuta calda: SHA/p1 sono DATO, non cancello)

| richiesta | ruolo | eval t/s | p1 (draft acceptance) | mean len | SHA output | content_chars | finish |
|---|---|---:|---|---:|---|---:|---|
| r1 | warm-up (dato) | 16,65 | 0.90281 (771/854) | 2,80 | `1EDA23452D...9089` — **identico al freddo** | 3782 | length |
| r2 | verdetto | 14,57 | 0.81078 (677/835) | 2,30 | `3CD00E94EA...4DABA` | 2107 | length |
| r3 | verdetto | 14,77 | 0.81862 (677/827) | 2,30 | `AA5A128AC7...9DDF7` | 3015 | length |
| r4 | verdetto | 15,89 | 0.85649 (746/871) | 2,65 | `C65F9F2414...8D78B` | 3133 | length |

**r1 riproduce ESATTAMENTE la traiettoria fredda** (stesso SHA, stesso p1 .90281, stesso
content_chars 3782 di tutti e 15 i run del sweep sopra) — coerente: e' la prima richiesta su
processo appena caricato, nessuna residenza ancora accumulata. **r2/r3/r4 divergono fra loro E
da r1** (tre SHA diversi, p1 in calo a .81-.86): la residenza che sopravvive cambia davvero la
traiettoria di calcolo a ogni richiesta successiva, non converge a un secondo stato fisso.

```text
valori ordinati (r2,r3,r4) : 14,57 / 14,77 / 15,89
MEDIANA (verdetto caldo)   : 14,77
spread max-min             : 9,06 %   (va oltre la soglia 5% del RUNBOOK: il caldo e' un banco
                                        piu' rumoroso del freddo, atteso e coerente con traiettorie
                                        diverse a ogni richiesta)
```

### Controllo di coerenza sul testo (prima richiesta-verdetto = r2)

Letto per intero `warm_anchor_b1200_20260817.r2.output.txt` (2107 caratteri, 59 righe): apre con
"Ecco il codice HTML completo per una landing page cyberpunk neon di NeuraForge..." poi markdown
fence + HTML/CSS in tema (header, variabili colore neon, font Orbitron/Rajdhani), si interrompe a
meta' di una dichiarazione CSS per esaurimento del budget di 1200 token. **Sano**: nessun loop,
nessuna ripetizione patologica, nessun testo fuori tema o degenerato — la brevita' (2107 contro
3782 caratteri di r1) e' spiegata dal mean len piu' basso (2,30 contro 2,80: piu' round di
verifica per token accettato), non da un guasto.

### Contatori cache-esperti — trend, non serie per richiesta esatta

**Trovato un limite reale, riportato onestamente invece di forzare una precisione che il log non
offre**: il blocco `domanda` + `bussate al momento del buco` (cache-esperti.cu:6632-6649) si
stampa a intervalli irregolari legati a un trigger interno (non un timer, non un confine di
richiesta) — 8 istantanee del contatore bersaglio nell'intero processo, i cui numeri di riga
(498, 553, 620, 675, 762, 851, 886, 970) **non cadono esattamente sui confini delle 4 richieste**
(righe p1 a 579/700/818/939). Non e' possibile isolare "buchi della richiesta N" senza inventare
un'attribuzione che il log non sostiene. Riporto invece il TREND cumulativo, che e' un dato reale:

```text
riga  domanda    colpi%   buchi     bussate 8+ (quota sul totale buchi classificati)
498     70153    68,9%     21831    56,0%
553    253765    70,8%     74136    72,0%
620    378901    71,4%    108277    75,9%
675    543437    70,4%    160783    75,7%
762    667485    71,0%    193287    77,7%
851    822905    70,7%    241387    77,6%
886    979684    70,7%    286668    77,7%
970   1104724    70,4%    327079    77,7%   <- finale, fine processo (dopo r4)
```

**Colpi% resta piatto 68,9-71,4% per tutto il processo**, comprese le richieste con p1 piu'
basso: l'hit-rate della cache esperti (quali esperti sono residenti in VRAM) NON segue il calo di
p1 (accettazione della bozza). Sono due meccanismi indipendenti: la cache-esperti decide quali
pesi sono in VRAM, la bozza decide quanti token proporre/accettare. **Il calo di t/s nel caldo
sembra guidato da p1, non dalla cache-esperti.** La quota di buchi "8+ bussate" (tempo di attesa
lungo prima dello sfratto) sale dal 56% al 77,7% e poi si stabilizza: primo segno di residenza che
lavora, poi satura.

### Contatori richiesti ma non presenti nel log

`lane_cpu`, `lane_gpu`, `lane_scudati`: **non presenti nel log** — cercato con
`Select-String -Pattern 'lane'` sull'intero file (990 righe), zero corrispondenze. I contatori
esistono nel codice come interi device incrementati con `atomicAdd`
(`cache-esperti.cu:2096-2098` dichiarazione, molteplici siti di incremento), ma non ho trovato
nessuna `fprintf` che li stampi con quel nome in questa configurazione (K=2 di default, non
K=0). Non deducibili da altri numeri senza inventare. Se servono, vanno cercati con K=0 (braccio
successivo) o serve indicare il sito di stampa esatto.

### Telemetria (work\sample_hw.ps1, 2 s/campione, 187 campioni validi)

```text
campioni con util.gpu>30%   : 140/187
SM clock (busy)              : mediana 1935 MHz (min 225, max 1942) -- combacia col regime SOTA storico (1950 MHz), nessun throttle
VRAM usata (busy)            : mediana 11896 MiB (picco assoluto 11898 MiB, minimo 372 MiB a processo concluso)
potenza (busy)                : mediana 101,1 W (combacia col regime storico 95-100 W)
```

### Riferimenti annotati accanto (NESSUN confronto di verdetto attraverso la genealogia)

```text
freddo fb8 di oggi (mediana 3 processi indipendenti)  = 16,70
campione storico freddo (nmax3fix_graphs, 16/8)       = 16,34
CALDO — r1 (warm-up, = freddo per costruzione)        = 16,65
CALDO — verdetto (mediana r2-r4)                      = 14,77   <-- PRIMO RIFERIMENTO GENEALOGIA CALDA
```

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\warm_anchor_b1200_20260817.*`

---

## warm_k0_b1200_20260817 — ABORTITO, CUDA error. NESSUNA MISURA.

Primo braccio della campagna adaptive-K (`LLAMA_OVERLAP_K=0`, lane CPU spenta), stesso
protocollo di warm_anchor + `LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8` (igiene, inerte:
il trasporto calendario resta sincrono in questa configurazione).

```text
comando = come warm_anchor, -Extra con in piu' 'LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;LLAMA_OVERLAP_K=0'
```

**La corsa e' fallita durante la richiesta 1 (task 0), PRIMA di generare un solo token**, subito
dopo l'elaborazione del prompt (`cached n_tokens = 64`, poi `init_sampler`), nella fase di
riserva/cattura del grafo CUDA:

```text
CUDA error: operation failed due to a previous error during capture
  current device: 0, in function ggml_cuda_kernel_launch at D:\llama-overlap\ggml\src\ggml-cuda\common.cuh:1681
  cudaGetLastError()
1.58.936.671 E CUDA error: operation failed due to a previous error during capture
1.58.936.677 E   current device: 0, in function ggml_cuda_kernel_launch at D:\llama-overlap\ggml\src\ggml-cuda\common.cuh:1681
1.58.936.677 E   cudaGetLastError()
D:\llama-overlap\ggml\src\ggml-cuda\ggml-cuda.cu:123: CUDA error
```

Il server e' morto immediatamente dopo (righe 492/495/498 del `.server.log`, che finisce li':
498 righe totali). `run_porto_hot.ps1` ha ricevuto `Invoke-RestMethod: Connessione sottostante
chiusa... chiusa dal server in modo imprevisto` alla riga 209, e allo shutdown ha trovato il
processo `gia-uscito` (crash, non un Ctrl+C riuscito).

**Cancelli**: manifesto confermava `LLAMA_OVERLAP_K=0(E)` (esplicito, la leva era davvero
impostata) e `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` (grafi CUDA attivi, coerente con la regola
vitale). Riga cache-esperti identica al riferimento fino al punto del crash. **Salute: FALLITA**
— CUDA error presente, `finish_reason` mai raggiunto, nessun `summary.json` prodotto.

**Postflight**: 0 processi llama residui, RAM libera 90,4 GB (nessuna perdita). Chiusura non
pulita (il processo e' morto da solo, non e' stato un Ctrl+C) ma senza residui rilevabili.

**Nessun t/s riportato: non e' zero, e' NESSUNA MISURA** (RUNBOOK §4.8). Non ho riprovato con
una variante (niente K frazionario, niente disattivazione grafi, niente altro tentativo): la
regola vitale e' fermarsi e riportare. Il commento del codice a `llama-graph.cpp:1814-1817`
descrive K=0 come il cammino piu' semplice ("il nodo di partizione NON viene inserito, il grafo
e' strutturalmente quello di oggi") — il crash durante la CATTURA del grafo CUDA suggerisce che
K=0 in combinazione con i grafi CUDA attivi percorre un ramo raramente esercitato (la baseline
usa sempre K=2) con un problema latente, non che la leva in se' sia incoerente con la sua
descrizione. **Non e' stato possibile determinare se il problema sia specifico di K=0+grafi, di
K=0 in generale, o di qualcos'altro nella combinazione con il resto della configurazione calda
senza ulteriori bracci — decisione che spetta all'utente/coordinatore, non presa qui.**

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\warm_k0_b1200_20260817.server.log` (498 righe, nessun `.summary.json`, nessun `.r*.output.txt`)

---

## k0_nograph_diag_b1200_20260817 — diagnosi isolamento del crash: RISOLTA

Un solo lancio diagnostico, `-Repetitions 1`, identico a `warm_k0` (K=0) ma con
**`GGML_CUDA_DISABLE_GRAPHS=1` impostato ESPLICITAMENTE**. Questo NON e' la trappola descritta
nella regola vitale #1 del mandato originale (quella riguarda il lasciarla impostata per errore
in un banco di certificazione dove si vogliono i grafi accesi): qui e' uno **strumento usato
intenzionalmente** per isolare la causa del crash, e va letto come tale. `t/s` di questo braccio
**non e' confrontabile con nient'altro** in questo ledger (grafi spenti cambiano il cammino di
calcolo in modo massiccio) — e' diagnostica pura.

```text
comando = come warm_k0, -Extra con in piu' 'GGML_CUDA_DISABLE_GRAPHS=1', -Repetitions 1
manifesto = GGML_CUDA_DISABLE_GRAPHS=1(E)  LLAMA_OVERLAP_K=0(E)   -- entrambi confermati come da intenzione
```

**Risultato: NESSUN crash.** Completato per intero, `finish_reason=length`, 1200 token generati,
0 `CUDA error`, 0 `GGML_ASSERT`, 0 `CONTESA`, 0 processi residui.

```text
eval time = 102988.83 ms / 1200 tokens (85.82 ms/token, 11,65 t/s)   [NON CONFRONTABILE: grafi spenti]
p1        = 0.78319 (643 accepted / 821 generated), mean len = 2,16
SHA       = F501E5C5785EF309B34870AA0AAC54161FF90700011F37825F1EBE5172FE194A
copie/buchi = domanda 357588, colpi 197595 (55,3%), buchi 159993 (44,7% miss)
```

Prime righe del testo generato (controllo di coerenza): "Ecco il codice HTML completo per una
landing page cyberpunk di NeuraForge..." poi HTML/CSS in tema, sano, nessuna degenerazione.

**VERDETTO DELLA DIAGNOSI: il bug e' specifico della CATTURA del grafo CUDA sul cammino
tutto-GPU.** Con K=0 e grafi ATTIVI (`warm_k0`, sopra) il server crasha con `CUDA error:
operation failed due to a previous error during capture` durante la primissima cattura. Con K=0
e grafi SPENTI (questo braccio) lo stesso identico calcolo (K=0, nessuno split CPU) procede senza
errori. Per esclusione: l'operazione che va in errore e' illegale **solo durante la cattura**
(non nell'esecuzione normale), e oggi sopravvive nella configurazione standard (K=2) solo perche'
lo split CPU spezza il grafo in pezzi piu' piccoli che non includono mai quell'operazione nello
stesso segmento catturato. **Non e' stato necessario uno stack completo**: il primo ramo
dell'ipotesi (nessun crash senza grafi) si e' verificato, quindi la diagnosi si chiude qui come
da mandato, senza esplorare oltre.

**Nota supplementare non richiesta ma osservata**: il colpi% crolla a 55,3% (contro 70-71% del
regime K=2) — coerente col fatto che K=0 toglie l'intera valvola di sfogo verso la CPU: tutti gli
esperti devono passare dalla cache VRAM da 473 slot, che quindi si sovraccarica rispetto al
regime K=2 dove una parte del traffico va altrove. Non e' il focus della diagnosi richiesta, ma e'
coerente e va tenuto a mente per la campagna adaptive-K.

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\k0_nograph_diag_b1200_20260817.*`

---

## warm_anchor_restore_b1200_20260817 — IPOTESI CONFERMATA: il caldo con restore e' riproducibile

Stesso protocollo di `warm_anchor` ma con lo snapshot hot attivo nella forma verificata il 16/8
(`hotmask15_natural_full`): `-PortoHotSnapshot 1` **costante su tutte e 4 le richieste**
(non una sequenza ON/OFF: la prima chiamata ON in un processo senza snapshot precedente CATTURA
da sola, per costruzione del meccanismo — verificato nel precedente storico
`hotmask15_natural_full_b1200_r2_20260816`, dove 2 richieste ON diedero R1=cattura/R2=ripristino
con SHA identico) + `PORTO_HOT_MASK=15` (target=1, draft=2, stato spec=4, cache esperti=8: tutti
e quattro i componenti).

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'warm_anchor_restore_b1200_20260817' -MaxTokens 1200
  -Repetitions 4 -PortoHotSnapshot 1 -SpecNmax 3
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE=0;LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15'
telemetria = work\sample_hw.ps1, stesso schema dei bracci precedenti
```

**Cancelli di processo**: manifesto `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` — PASSATO.
`sched-profilo`=0 — PASSATO. Motore `n_max=3, conf_min=0.80` — PASSATO. Riga cache-esperti
identica al riferimento — PASSATO. `CONTESA`=0, `CUDA error`/`GGML_ASSERT`=0 — PASSATO.
Processi residui = 0 — PASSATO.

**Righe porto-hot (prova diretta del meccanismo, non dedotta)**:

```text
riga 501: task 0    | porto-hot: cattura    n_tokens=64, coda=4, mask=15, ... numero=1     <- r1
riga 615: task 432  | porto-hot: ripristino n_tokens=64, ...            mask=15, numero=1  <- r2
riga 711: task 862  | porto-hot: ripristino n_tokens=64, ...            mask=15, numero=2  <- r3
riga 829: task 1292 | porto-hot: ripristino n_tokens=64, ...            mask=15, numero=3  <- r4
```

### Serie per richiesta

| richiesta | ruolo | eval t/s | p1 | SHA output | content_chars |
|---|---|---:|---|---|---:|
| r1 | cattura | 16,72 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |
| r2 | ripristino #1 (verdetto) | 16,88 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |
| r3 | ripristino #2 (verdetto) | 16,86 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |
| r4 | ripristino #3 (verdetto) | 16,83 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |

**Le quattro richieste sono bit-identiche fra loro** (stesso SHA, stesso p1, stesso
content_chars) — e identiche anche al riferimento freddo (`fb8`, campione storico n_max=3).
L'ipotesi e' **CONFERMATA senza ambiguita'**: con restore dello stato canonico, il caldo smette
di essere una traiettoria diversa a ogni richiesta e torna esattamente riproducibile.

```text
valori ordinati (r2,r3,r4) : 16,83 / 16,86 / 16,88
MEDIANA (verdetto caldo con restore) : 16,86
spread max-min                       : 0,30 %   (molto stabile, ben sotto il 5%)

vs CALDO free-run (warm_anchor, 14,77)      : +14,15 %
vs FREDDO fb8 di oggi (16,70)               : +0,96 %   (sostanzialmente lo stesso numero)
vs campione storico freddo (16,34)          : +3,18 %
```

### Controllo di coerenza (r2, identica per costruzione a r1/r3/r4)

Letto `warm_anchor_restore_b1200_20260817.r2.output.txt`: apre con "Ecco il codice HTML completo
per una landing page cyberpunk neon di NeuraForge..." poi HTML/CSS coerente in tema (reset CSS,
variabili colore). Sano, nessuna anomalia — atteso, dato che questa e' la stessa identica
traiettoria byte-per-byte gia' letta e verificata nel braccio `fb8` a inizio turno.

### Telemetria (180 campioni validi, 123 busy util>30%)

```text
SM clock (busy)   : mediana 1927 MHz (min 225, max 1942) -- regime SOTA, nessun throttle
VRAM usata (busy) : mediana 11898 MiB (picco 11898 MiB)
potenza (busy)    : mediana 103,3 W (regime storico 95-100 W)
```

### Verdetto per il mandato

**QUESTO e' il protocollo caldo vero**: veloce (16,86, sostanzialmente pari al freddo 16,70) E
riproducibile (SHA identico su tutte le richieste post-cattura). Il 14,77 del free-run
(`warm_anchor`, sopra) resta annotato come **regime free-run**, non scartato: la produzione reale
**e'** free-run (nessun sistema di produzione fa restore-a-ogni-richiesta di serie), quindi resta
un numero legittimo e rilevante — ma ora sappiamo CHE COSA lo distingue dal caldo-con-restore.

**FRONTE NUOVO, da annotare per il prossimo turno**: *"p1 degrada fra richieste consecutive in
regime free-run: e' uno stato del drafter/della speculazione che si trascina, non rumore."*
Prova diretta raccolta in questo turno: `warm_anchor` free-run ha dato p1 = .90281 (r1, fresco) →
.81078 (r2) → .81862 (r3) → .85649 (r4) — un calo di quasi 10 punti percentuali dopo la prima
richiesta, poi un recupero parziale, MAI un ritorno al valore iniziale. Con restore attivo (questo
braccio) p1 resta fisso a .90281 su tutte e quattro. Questo isola il colpevole: **non e' la
cache-esperti** (il suo hit-rate resta piatto 68,9-71,4% in entrambi i regimi, vedi sopra), **e'
qualcosa nello stato del drafter o della pipeline speculativa che il restore azzera e il free-run
lascia derivare**. Nessuna ipotesi sul meccanismo esatto e' stata verificata in questo turno:
resta un'indagine aperta, non un risultato.

percorsi file: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\warm_anchor_restore_b1200_20260817.*`

---

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

# SESTA RIPRESA — KV reuse sul banco lungo (verifica `KV_REUSE_VERIFICA.md`)

Esecutore: sesto turno, contesto fresco. Mandato del coordinatore: applicare le due modifiche
autorizzate a `sota100k_ctx150k.ps1` (repliche in-processo + `-cms 32`) e misurare il braccio
B-cms32 secondo il disegno B-first del piano.

Fonti: `docs/porto/RUNBOOK_BANCO_DS4.md`, `D:\ds4_work\design\KV_REUSE_VERIFICA.md` (risposta in
una riga del piano: prefill R1 1.169.865 ms / 101.558 token, R2 419,73 ms / 4 token nello stesso
processo, fattore ~2.787x, gia' misurato l'11/8 su `banda.server.log`; il banco lungo di oggi non
lo sfrutta perche' lo script manda una sola richiesta per processo).

## Preflight (nuovo turno)

```text
data/ora        = 2026-08-17 (turno serale)
processi llama  = 0
porta 8000 (UI) = non toccata (nessun listener trovato)
porta 8099      = libera
porta 8100      = libera
nvidia-smi (UNICA invocazione extra di preflight) =
  NVIDIA GeForce RTX 3060, sm=210MHz, mem=405MHz, power=12.55W, used=372MiB, free=11744MiB,
  pcie_gen=1 (a riposo), pcie_width=16, throttle=0x0000000000000001
ram_libera_gb   = 89.4 GB
uptime_min      = 3206.6 (~53,4h, nessun riavvio dall'ultimo preflight di oggi)
disco_c_gb      = 49.2 GB liberi
disco_d_gb      = 119.7 GB liberi
sha_llama_server= C727251E7F88A9AE76541F14DDA6BAE6DE8CB58A9712A3BB661CF41A567F1485  (IDENTICO al preflight precedente di oggi)
sha_ggml_cuda   = 1ED035D3D3782F3981928E71EA8459506AEE364ED6FADE077EBFE343E6902330  (IDENTICO)
build           = build 10093 (3014d3756) -- invariato, nessuna ricompilazione in mezzo
sha_jprompt102k = 3B4994877D4074E1249DA6EDE53ADC26C10D1297005428BE02990284560A1473 (285.268 byte,
                  20260811 05:16 -- il banco lungo usa jprompt102k.txt, non jprompt.txt da 252
                  byte/§1.8 del banco corto; nessuna firma storica con cui confrontarlo, registrata
                  qui come nuova baseline)
```

## Modifica autorizzata a `sota100k_ctx150k.ps1` (unico file, NIENT'ALTRO)

Autorizzazione esplicita del coordinatore per questo file soltanto, due modifiche dal piano KV
(`KV_REUSE_VERIFICA.md` §2.a, §3.5):

1. nuovo parametro `-Repliche N` (difetto 1, i bracci storici restano riproducibili) con un
   ciclo di N richieste IDENTICHE consecutive nello STESSO processo, attorno all'`Invoke-RestMethod`
   (riga ~235 originale); artefatti per-replica con suffisso `_q$r` su `response.json`/`output.txt`
   (log/summary restano un solo file per processo); `id_slot=0` e `cache_prompt=true` dichiarati
   nel corpo JSON (righe 152-158 originali) -- gia' veri per difetto (`common.h:626`, `server-
   context.cpp:4592`), ora resi espliciti nella richiesta;
2. `'-cms', '32'` aggiunto a `$serverArgs` (righe 190-198 originali).

**Verifica lettori PRIMA di usare la leva** (regola vitale, grep eseguito su `D:\llama-overlap`,
sola lettura):

```text
D:\llama-overlap\common\arg.cpp:1484-1499
  {"-ctxcp","--ctx-checkpoints","--swa-checkpoints"} -> params.n_ctx_checkpoints    (difetto 32)
  {"-cms","--checkpoint-min-step"}                   -> params.checkpoint_min_step (difetto 8192)
D:\llama-overlap\common\common.h:628-629 conferma i due difetti (32 / 8192).
D:\llama-overlap\tools\server\server-context.cpp:4592
  task.id_slot = json_value(data, "id_slot", -1);   -- campo confermato, -1=auto senza il campo
```

Nota di precisione: il testo del mandato citava `-cms` come "(--ctx-checkpoints 32)" fra
parentesi; il grep mostra che `-cms` e' in realta' `--checkpoint-min-step` (spaziatura minima fra
checkpoint), distinto da `--ctx-checkpoints`/`-ctxcp` (numero massimo di checkpoint, gia' 32 di
difetto e non toccato). La modifica applicata e' quella letterale del mandato (`'-cms', '32'`) e
corrisponde esattamente all'aritmetica del piano (`checkpoint_min_step` 8192 -> 32, per far
sopravvivere il checkpoint di coda a 101.593 token invece di fermarsi a 99.549 -- piano §1.3).

Diff completo salvato in
`C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\runs\sota100k_kvreuse.patch`
(4 hunk: param `Repliche`, `cache_prompt`/`id_slot`, `-cms`, ciclo repliche -- nessun'altra riga
toccata, verificato leggendo il diff per intero). Sintassi verificata con
`[System.Management.Automation.Language.Parser]::ParseFile` (0 errori) prima del lancio. Nessuna
ricompilazione: la modifica e' solo nel wrapper PowerShell, il binario resta quello del preflight.
