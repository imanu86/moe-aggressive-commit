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

## Braccio B-cms32 — kvlong_cms32_20260817

Lancio staccato (`Win32_Process.Create`, PID launcher 19008, PID `llama-server` 11332),
telemetria `sample_hw.ps1` staccata (PID 15928) avviata non appena il processo server e'
comparso. Monitor di sfondo con polling attivo ogni 25 s, tetto di sicurezza 3600 s (non
raggiunto).

```text
comando = & '...\work\sota100k_ctx150k.ps1' -StartBatch 2048 -BlockSparse 0 -HcFused 5
  -RunLabel kvlong_cms32_20260817 -BlockDenseCpu 0 -Context 150000 -MaxTokens 256 -SpecNmax 3
  -Repliche 3
telemetria = work\sample_hw.ps1 -Tag kvlong_cms32_20260817 -OutDir D:\ds4_work\llama_run -IntervalSeconds 2
```

### Serie completa r1/r2/r3 (dal log, non dal riassunto)

| | r1 (piena) | r2 (restore) | r3 (restore) |
|---|---:|---:|---:|
| task id | 0 | 184 | 323 |
| prompt eval | 790.163,24 ms / 101.597 token (128,58 t/s) | **342,75 ms / 4 token** (11,67 t/s) | **340,82 ms / 4 token** (11,74 t/s) |
| decode (eval time) | 28.285,00 ms / 256 token (9,05 t/s) | 28.496,42 ms / 256 token (8,98 t/s) | 27.398,51 ms / 256 token (9,34 t/s) |
| p1 (draft acceptance) | 0,71264 (124/174), mean len 1,95 | 0,67429 (118/175), mean len 1,87 | 0,69274 (124/179), mean len 1,95 |
| wall della richiesta | 13,65 min | 0,49 min (29,4 s) | 0,47 min (28,2 s) |
| SHA output | 86ADC2E5...F3B | 1CDC38F1...1BAF | 290A0465...FD81 |
| output chars | 1173 | 1189 | 66 |
| finish_reason | length | length | length |

SHA-12: r1 `86ADC2E5FC5B`, r2 `1CDC38F15231`, r3 `290A0465B5A1` (tutti diversi fra loro, atteso
-- vedi Cancello 2).

### Cancello 1 — la prova del salto: **PASSATO**

Dal `.server.log` (`D:\ds4_work\llama_run\sota_ctx150000_densefa_stage_hc5_kvlong_cms32_20260817_f2_b2048.server.log`):

```text
:1522  created context checkpoint 3 of 32 (pos_min = 101592, pos_max = 101592, n_tokens = 101593, size = 18.906 MiB)
       -- il checkpoint di coda SOPRAVVIVE (con -cms 8192 di difetto sarebbe stato vetato: 101593 > 99549+8192 e' falso;
          con -cms 32: 101593 > 99549+32 e' vero -> sopravvive. Aritmetica del piano confermata.)
:1599  task 184 | restored context checkpoint (pos_min = 101592, pos_max = 101592, n_tokens = 101593, n_past = 101593, ...)
:1600  task 184 | cached n_tokens = 101593, memory_seq_rm [101593, end)
:1847  task 323 | restored context checkpoint (... n_past = 101593 ...)  -- identico per r3
:1848  task 323 | cached n_tokens = 101593, memory_seq_rm [101593, end)
```

n_past = 101593 >= 101593 richiesto -- PASSATO su r2 e r3. `prompt eval ... / 4 tokens` <= 4 --
PASSATO. **ASSENTI** su tutto il log: `forcing full prompt re-processing` e
`erased invalidated context checkpoint` (grep vuoto) -- PASSATO.

**Nota su una sotto-riga del cancello che NON compare, spiegata dal codice**: la riga
`selected slot by LCP similarity, sim_best = 1.000 ...` prevista dal piano **non e' presente**;
al suo posto, su tutte e tre le richieste: `task -1 | selected slot by id (0)`. Causa verificata
sul lettore (`server-context.cpp:1687-1690` vs `:1729-1732`): il ramo LCP-similarity stampa
`sim_best` solo `if (task.id_slot == -1)`; con `id_slot=0` dichiarato nella richiesta (la stessa
modifica autorizzata di oggi) il codice prende il ramo "by id", che salta il calcolo di
similarita' perche' non serve -- con `-np 1` i due rami selezionerebbero comunque lo stesso
(unico) slot. La sostanza del cancello (stato corretto individuato e ripristinato) e' provata
dalle righe `restored context checkpoint`/`cached n_tokens` sopra, identiche nella forma a
`banda.server.log`. Non e' un'anomalia, e' una conseguenza diretta e attesa della modifica
autorizzata (1).

### Cancello 2 — parita' di qualita' e contatori: **PARZIALE, con spiegazione**

- caratteri generati: r1 1173, r2 1189 (stesso ordine di grandezza) -- **PASSATO**; r3 66, vedi
  Cancello 5 per la spiegazione (non e' un difetto del meccanismo).
- riga `cache-esperti: 473 slot ...`: **UNA SOLA per processo** (le tre repliche condividono lo
  stesso processo server), e coincide carattere per carattere col riferimento SOTA di RUNBOOK
  §12.1/§4.1 incluso `sfratto_par=1` -- **PASSATO** (identita' per costruzione).
- salute dura: zero `GGML_ASSERT`/`CUDA error`/`out of memory`/`invalid index`; l'unico hit su
  `inf` e' `logit bias = -inf` per il token end-of-sentence, inizializzazione normale, non un
  errore numerico -- **PASSATO**. Zero `divergenze` diverse da tutti-zero sull'intero log --
  **PASSATO**.
- contatori cache-esperti (cumulativi di processo, il log non li segmenta per richiesta --
  stessa limitazione gia' documentata sopra per `warm_anchor`): domanda 841 colpi 58,7% (inizio
  r1) -> domanda 89.008 colpi 68,5% (fine r1) -> domanda 170.632 colpi 69,1% (fine r3). Banda
  stabile 68-69% da fine-r1 a fine-r3, **nessun salto** al passaggio r1->r2 -- **PASSATO**
  (coerente con "non e' ripristinata, ci si aspetta un transitorio iniziale non una banda
  diversa a regime").
- **p1**: r1 0,71264 -> r2 0,67429 (**-5,38%**) -> r3 0,69274 (**-2,79%**). Il piano chiede
  "entro 2,2-2,4%": **NON rispettato in senso stretto su nessuna delle due repliche**.
  Osservazioni prima di giudicare:
  1. il campione e' piccolo: 174-179 proposte di bozza per replica (MaxTokens 256), contro le
     792-854 del banco B1200 su cui e' stata caratterizzata la banda 2,2-2,4% (`capienza-non-
     paga`, `resume-20260812`) -- un campione ~4,5 volte piu' piccolo. L'errore standard atteso
     di una proporzione a p~=0,71 con n=175 e' sqrt(0,71*0,29/175) = 3,4 punti percentuali (1
     sigma): il calo di r2 (3,8 punti assoluti) sta a ~1,1 sigma di puro rumore campionario a
     questa taglia, quello di r3 (2,0 punti) a ~0,6 sigma. La banda 2,2-2,4% non e' stata
     misurata a questa taglia di campione e applicarla tale e quale sottostima il rumore atteso.
  2. il piano stesso (`KV_REUSE_VERIFICA.md` tabella §1.1) documenta che il ripristino da
     checkpoint e' **PARZIALE per costruzione** sul target DSV4 (`LLAMA_STATE_SEQ_FLAGS_
     PARTIAL_ONLY`: solo la meta' SWA + i comp-state, i tre `kv_csa/hca/lid` grezzi **non**
     passano) -- una via gia' segnalata dal piano come "lo stato non e' neutro per costruzione"
     per il testo/SHA; la stessa via puo' plausibilmente introdurre differenze numeriche minime
     che, sotto campionamento greedy, cambiano l'esatta sequenza accettata dalla bozza.
  3. nessuna deriva monotona: r3 e' piu' vicino a r1 di r2 (non un decadimento sostenuto come
     visto invece nel meccanismo SEPARATO `porto_hot_snapshot` free-run di oggi, sezione
     `warm_anchor` sopra, dove il calo e' stato fino a -10 punti e MAI recuperato).
  **Verdetto su questo punto**: divergenza reale e sopra soglia letterale, ma di ampiezza e
  forma compatibili con rumore di campione piccolo + stato-parziale-per-costruzione, non con uno
  stato "non e' quello catturato" nel senso allarmante del piano. Segnalato, non nascosto: **il
  coordinatore decide se la soglia del 2,4% va ricalibrata per campioni piccoli prima di
  promuovere**. E' anche materiale utile per il mandato in coda (`P1_DEGRADO_ROOT_CAUSE.md`),
  perche' e' un SECONDO meccanismo (checkpoint restore, non `porto_hot_snapshot`) che mostra un
  calo di p1 fra richieste consecutive nello stesso processo.

  **RIVALUTAZIONE (decisione del coordinatore, 17/8, dopo il report)**: la soglia fissa 2,4% non
  vale per campioni piccoli. **Nuova regola per il cancello p1, da applicare da ora**: banda =
  **2σ binomiali**, con `σ = sqrt(p·(1-p)/n_proposte)`, `p` = p1 del riferimento (r1),
  `n_proposte` = generated della replica in esame (non un valore arrotondato comune alle due
  repliche). Ricalcolo con l'aritmetica esatta di questo braccio:

  ```text
  r1 (riferimento): p = 0,71264, n = 174 (generated)

  r2: n = 175 -> sigma = sqrt(0,71264*0,28736/175) = sqrt(0,0011704) = 3,421 punti  -> banda 2 sigma = ±6,842 punti
      delta assoluto = 0,67429-0,71264 = -3,835 punti  ->  |−3,835| < 6,842  ->  PASSA (≈1,12 sigma)
      delta relativo (quello riportato sopra, -5,38%)   ->  |−5,38| < 7 (banda arrotondata del coordinatore) -> PASSA anche in questa lettura

  r3: n = 179 -> sigma = sqrt(0,71264*0,28736/179) = sqrt(0,0011442) = 3,383 punti  -> banda 2 sigma = ±6,765 punti
      delta assoluto = 0,69274-0,71264 = -1,990 punti  ->  |−1,990| < 6,765  ->  PASSA (≈0,59 sigma)
      delta relativo (-2,79%) -> PASSA anche in questa lettura
  ```

  Nota sull'unita' (controllo dovuto, `check-counter-units`): `sigma` e' una deviazione standard
  di una PROPORZIONE, quindi e' in punti percentuali assoluti (stessa unita' di p1), non in
  percentuale relativa. Ho ricalcolato in entrambe le convenzioni per chiarezza: il verdetto
  **PASSA in entrambe**, con margine piu' ampio nella lettura assoluta (corretta per la formula
  data) che in quella relativa. **Cancello 2 PASSATO RETROATTIVAMENTE su r2 e r3.** Con questo,
  **tutti e cinque i cancelli di B-cms32 sono PASSATI**, nessuna riserva residua sulla parita' di
  qualita'.

### Cancello 3 — il premio: **PASSATO, ampiamente**

```text
prompt eval r1 = 790.163,24 ms
prompt eval r2 =     342,75 ms   -> rapporto r1/r2 = 2.305,6x
prompt eval r3 =     340,82 ms   -> rapporto r1/r3 = 2.318,7x
soglia B-cms32 richiesta: >= 500x   ->  PASSATO con margine ~4,6x oltre soglia
(per confronto: banda.server.log storico misurava 2.787x sullo stesso meccanismo)
```

### Cancello 4 — nessuna regressione decode: **PASSATO**

```text
decode r1 = 9,050735 t/s  (riferimento)
decode r2 = 8,983585 t/s  -> delta = -0,74%   (soglia -2,4%: PASSATO)
decode r3 = 9,343573 t/s  -> delta = +3,24%   (PASSATO, piu' veloce di r1)
```

### Cancello 5 — coerenza del testo: **PASSATO, con osservazione utile**

Letti per intero r1, r2 e r3 (il terzo aggiunto per il conteggio caratteri anomalo). Verificato
sul JSON di risposta grezzo (non solo sull'`.output.txt`) quale campo il server ha popolato:

```text
r1: content = VUOTO/assente | reasoning_content = 1173 char ("We need to answer in Italian...")
r2: content = VUOTO/assente | reasoning_content = 1189 char ("We need to produce a short technical paragraph...")
r3: content = 66 char ("Il sistema di cache per-esperti in VRAM e lo split sequenziale dei")
    | reasoning_content = 1095 char (stesso tipo di apertura di r1/r2)
```

Il modello e' un modello "thinking": scrive il proprio ragionamento in `reasoning_content` e la
risposta finale in `content`. Con `MaxTokens=256` r1 e r2 esauriscono l'intero budget dentro il
ragionamento (mai raggiunto `content`, lo script ricade su `reasoning_content` per non scrivere
un file vuoto); r3 comprime leggermente il ragionamento (1095 contro ~1180 char) e lascia spazio
a 66 caratteri di risposta italiana reale, in tema, poi troncata per fine budget.
**Giudizio esplicito**: lingua sana = si (su tutti e tre, incluso il ragionamento in inglese:
grammaticalmente valido, non gibberish); assenza di loop/ripetizioni patologiche = si; pertinenza
al prompt = si (tutti e tre parlano di cache-esperti/DSV4/overlap, l'argomento vero del contesto
incollato); degradazione progressiva = no. **r1 e r2 si comportano in modo qualitativamente
IDENTICO** (stesso tipo di testo, stessa lunghezza, stesso campo vuoto) -- il fatto piu'
rassicurante per l'ipotesi del salto: lo stesso "limite" (budget insufficiente per un modello
thinking) si riproduce identico a stato ripristinato. Non e' un difetto del meccanismo KV, e'
una caratteristica nota di banchi con budget corto su un modello reasoning (coerente con le note
RUNBOOK su "modalita' no-think" altrove); da tenere presente per il dimensionamento di banchi
futuri con questo prompt/modello, non per questo verdetto.

### Telemetria (`kvlong_cms32_20260817.hw.csv`/`.cpu.csv`, 422 campioni a 0,5 Hz)

```text
campioni busy (util>30%) : 378/422
SM clock (busy)           : mediana 1920 MHz (min 607, max 1942) -- regime SOTA, nessun throttle sostenuto
VRAM usata (busy)         : mediana 11.907 MiB (picco 11.924 MiB) -- vicino al tetto dei 12 GB per il contesto 150k
potenza (busy)             : mediana 135,4 W
CPU% media                 : 24,2 % (422 campioni)
```

### Strumentazione (dichiarata, non promossa a cancello di questa sessione)

`sched-profilo` = 286 righe (>0) -> profiler **ACCESO**; `GGML_CUDA_GRAPH_STATS=1`. Questo NON
e' una deviazione introdotta oggi: `Set-SotaEnvironment` dentro `sota100k_ctx150k.ps1` fissa
`GGML_SCHED_PROFILO='1'` e `GGML_CUDA_GRAPH_STATS='1'` incondizionatamente (righe gia' presenti
prima delle mie modifiche, fuori dai due punti autorizzati -- non toccate). E' quindi lo stesso
stato di TUTTE le corse storiche di questo runner (incluso il riferimento archiviato `_m256`),
quindi il confronto r1-vs-r2-vs-r3 interno a questo braccio resta a pari strumentazione (RUNBOOK
§8.2). Segnalato per trasparenza rispetto alla regola vitale generale "GGML_SCHED_PROFILO=0":
qui non e' rispettata, ma cambiarla avrebbe richiesto una TERZA modifica non richiesta al file.
`GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` confermato dal manifesto -- grafi accesi, regola vitale
rispettata.

### VERDETTO B-cms32

**Il meccanismo di salto (Cancello 1) e il premio (Cancello 3) sono confermati in modo netto e
inequivocabile**: checkpoint di coda a 101.593 token creato e ripristinato su r2 e r3, riprefill
di 4 token invece di 101.597, guadagno 2.306-2.319x (oltre 4x la soglia dei 500x richiesta). Il
decode non regredisce (Cancello 4). Il testo resta sano su tutte e tre le repliche (Cancello 5).
L'unico punto sotto soglia letterale e' la parita' p1 (Cancello 2, -5,4%/-2,8% contro soglia
2,4%), con una spiegazione statisticamente e meccanicamente fondata (campione piccolo + stato
parziale per costruzione) che il coordinatore deve validare. **Procedo a B-base** come da mandato
(il core del meccanismo e' provato; B-base misura il premio SENZA checkpoint fine, punto
distinto dalla parita' p1) e segnalo la questione p1 esplicitamente nel report finale.

Postflight: 0 processi llama, RAM libera 89,3 GB (da 89,4 di preflight), VRAM 321 MiB (da 372),
`shutdown: ctrl-c` pulito. Percorsi: log/summary/output/response/hw.csv/cpu.csv tutti in
`D:\ds4_work\llama_run\` con tag `kvlong_cms32_20260817` / `sota_ctx150000_densefa_stage_hc5_
kvlong_cms32_20260817_f2_b2048*`.

## Terza modifica (flaggata) a `sota100k_ctx150k.ps1` — parametro `-CtxCheckpointMinStep`

L'autorizzazione originaria copriva **due** modifiche, non tre. Il mandato pero' chiede anche
B-base "identico SENZA il -cms nel server": impossibile con `-cms` fissato a `'32'` incondizionato
(modifica 2 originaria) senza toccare di nuovo il file. Il messaggio in coda del coordinatore,
arrivato nel frattempo per un mandato diverso, descrive **esplicitamente** questo stesso caso
("se serve una modifica al runner: parametro -X, stessa procedura autorizzata di -SpecNmax,
diff salvato") come procedura standard. Ho applicato **la stessa procedura, sullo stesso file**,
per necessita' interna al mandato originario (B-base ne fa parte fin dal testo del mandato), non
per iniziativa autonoma su un punto nuovo:

```text
param(...) : aggiunto [int] $CtxCheckpointMinStep = 32   (difetto = comportamento odierno invariato)
$serverArgs: '-cms', '32'  ->  '-cms', "$CtxCheckpointMinStep"
```

Verificato sul lettore (`D:\llama-overlap\common\arg.cpp:1492-1501`): l'handler fa solo
`params.checkpoint_min_step = value`, nessuna distinzione fra "esplicito" e "di difetto" --
passare `-cms 8192` e passare NIENTE producono lo stesso `checkpoint_min_step`, quindi
`-CtxCheckpointMinStep 8192` per B-base e' bit-equivalente a "senza -cms nel server" a runtime,
pur restando un argomento passato (piu' semplice da implementare di un array condizionale, zero
rischio di rompere gli altri argomenti). Diff isolato di questa sola modifica salvato in
`C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\runs\sota100k_kvreuse_ctxcheckpointminstep.patch`
(2 hunk, verificato che non tocca nient'altro). Sintassi riverificata con
`[System.Management.Automation.Language.Parser]::ParseFile` (0 errori). **Segnalato esplicitamente
al coordinatore nel report finale come giudizio preso in autonomia, non pre-autorizzato
testualmente** -- da confermare o correggere.

**CONFERMATO dal coordinatore (17/8, dopo il report)**: "seguiva esattamente il pattern
autorizzato (lettore verificato, diff isolato, default bit-equivalente). Ben fatto a segnalarla
comunque: e' la prassi giusta." Nessuna correzione richiesta, nessun'altra azione dovuta su
questo punto.

## Braccio B-base — kvlong_base_20260817 — R1 valido, R2/R3 ABORTITI (CUDA OOM): NESSUNA MISURA

QUIETE di 300 s eseguita per intero (polling attivo, 0 processi/321 MiB VRAM/89,2 GB RAM stabili
per tutta la finestra) prima del lancio. Lancio staccato identico a B-cms32 (`Win32_Process.Create`,
PID launcher 20228, PID `llama-server` 14804, telemetria PID 17684 su tag `kvlong_base_20260817`).

```text
comando = & '...\work\sota100k_ctx150k.ps1' -StartBatch 2048 -BlockSparse 0 -HcFused 5
  -RunLabel kvlong_base_20260817 -BlockDenseCpu 0 -Context 150000 -MaxTokens 256 -SpecNmax 3
  -Repliche 3 -CtxCheckpointMinStep 8192
```

### r1 — PASSATO, bit-identico a B-cms32/r1

```text
prompt eval = 819.227,35 ms / 101.597 token (124,02 t/s)      [B-cms32/r1: 790.163,24 ms, 128,58 t/s -- entro la dispersione nota del prefill lungo, spread 13,86% gia' documentato in RUNBOOK §12.5]
decode      =  28.325,23 ms /    256 token (9,04 t/s)          [B-cms32/r1: 9,05 t/s]
p1          = 0,71264 (124 accettati / 174 generati), mean len 1,95   [IDENTICO a B-cms32/r1]
SHA output  = 86ADC2E5FC5B7BF2AB08DC79DD1CF5347E269BDD6C3C4D10CADE8C96BCF99F3B   [IDENTICO a B-cms32/r1]
checkpoint creato = "created context checkpoint 2 of 32 (pos_min=99548, pos_max=99548, n_tokens=99549)"
                     -- SOLO questo (con -cms 8192 di difetto il checkpoint di coda a 101.593 e' vetato:
                     101593 > 99549+8192=107741 e' falso -- aritmetica del piano confermata anche qui)
```

SHA e p1 identici a B-cms32/r1 confermano che i due bracci sono correttamente comparabili a
livello di r1 (stessa traiettoria fredda, sola differenza e' `-cms`, che non tocca la richiesta
fresca).

### r2/r3 — ABORTITI: CUDA error out of memory. NESSUNA MISURA (RUNBOOK §4.8)

```text
r2: "REQUEST FAILED: Connessione sottostante chiusa ... chiusa dal server in modo imprevisto"
r3: "REQUEST FAILED: Impossibile effettuare la connessione al server remoto"  (server gia' morto)
```

**Causa esatta, dal log** (`sota_ctx150000_densefa_stage_hc5_kvlong_base_20260817_f2_b2048.server.log:1598-1644`):

```text
:1598-1602  task 184 | new prompt, n_tokens=101597
            checking checkpoint with [99548, 99548] against 101596...
            restored context checkpoint (pos_min=99548, pos_max=99548, n_tokens=99549, n_past=99549)
            -- IL RIPRISTINO FUNZIONA CORRETTAMENTE anche con -cms 8192: trova ed usa il checkpoint 2.
            residuo da ririprocessare = 101.597 - 99.549 = 2.048 token (esattamente l'atteso del mandato)
:1625       vram-a-fasi: fase=prefill livello=2  cache 473 -> 0 slot (-473, -3194 MiB)  VRAM libera 2707 MiB [cambio n. 3]
            -- il residuo di 2.048 token supera la riserva-ubatch di 64 della modalita' decode:
            il gestore VRAM-a-fasi torna in modalita' prefill, liberando i 3194 MiB della cache esperti
:1631-1636  sched_reserve: CUDA0 compute buffer = 1772,18 MiB; buffer di calcolo 137,95 -> 2296,35 MiB (+2158,40 MiB) -- RIESCE
:1637-1638  layer-major: staging di 1729 MiB NON allocabile
            CUDA error: out of memory
:1639       current device: 0, in function ggml_cuda_mul_mat_q at ggml-cuda\mmq.cu:183
```

Aritmetica: 2.707 MiB liberati dalla cache esperti, 2.158 MiB assorbiti dalla ricrescita del
buffer di calcolo (riesce, restano ~549 MiB), poi lo staging layer-major da 1.729 MiB NON ci
sta (549 << 1729) -> OOM dentro un lancio di matmul, il processo muore (`shutdown: already-
exited`, non un Ctrl+C pulito).

**Perche' B-cms32 NON lo incontra**: confermato rileggendo il suo `.server.log` -- l'INTERO
braccio (3 repliche) mostra **solo due** transizioni `vram-a-fasi` (`cambio n. 1` all'ingresso
di r1, `cambio n. 2` al passaggio r1-prefill -> decode), **zero** transizioni successive: il
residuo di r2/r3 li' e' **4 token**, sotto la riserva-ubatch=64 della modalita' decode, quindi
il gestore VRAM-a-fasi non torna MAI in modalita' prefill per r2/r3 e la cache esperti (3194 MiB)
resta residente per tutto il processo. La telemetria conferma indipendentemente: `kvlong_
base_20260817.hw.csv` mostra VRAM 11.899 MiB -> 10.355 MiB (r2 avvia, libera la cache) ->
10.343 MiB -> **382 MiB** (crash, contesto CUDA distrutto) fra le 06:41:40 e le 06:41:52, in
coincidenza con la fine di r1 (06:41:46,8 attesa da `[06:27:38] + 14,13 min`).

**Conclusione**: il meccanismo di IDENTIFICAZIONE e RIPRISTINO del checkpoint funziona
correttamente anche a `-cms` di difetto (8192) -- non e' un bug del cammino KV-reuse in se'.
Il crash e' un problema SEPARATO e a valle: la gestione VRAM-a-fasi di questo binario non ha
abbastanza margine per rientrare in modalita' prefill a meta' processo su un residuo di 2.048
token, su questa scheda da 12 GB a ctx=150k. **Questo e' un argomento aggiuntivo, non previsto
dal piano, a favore di B-cms32**: oltre a essere ~2.300x piu' veloce, evita STRUTTURALMENTE
la transizione che fa crashare B-base, perche' il suo residuo (4 token) non supera mai la
soglia che innesca il cambio di modalita'.

### Telemetria (413 campioni, interrotta dal crash a ~06:41:57)

```text
SM clock (busy)    : 1920 MHz (regime SOTA, nessun throttle fino al crash)
VRAM usata (busy)  : mediana e picco ~11.899 MiB (satura, coerente con ctx 150k)
```

### Postflight dopo il crash

```text
processi_llama = 0 (il processo e' morto da solo, nessun residuo rilevato)
vram_usata     = 319 MiB (da 372 MiB del preflight di sessione -- nessuna perdita)
ram_libera     = 88,8 GB (da 89,2 GB pre-lancio -- nessuna perdita apprezzabile)
```

Nessun residuo, ma chiusura NON pulita (`shutdown: already-exited`, non `ctrl-c`): per
RUNBOOK §10.1, un riferimento successivo da questo stesso processo andrebbe rimisurato --
non applicabile qui perche' non e' previsto un braccio successivo in questo mandato.

### Esito B-base

`r1 = PROMOSSO` (diagnostico, bit-identico al controllo). `r2/r3 = NESSUNA MISURA (crash CUDA
OOM)`, non "0x" e non un numero negativo -- per RUNBOOK §4.8 un crash non e' una misura, e non
ne invento una. **Non e' possibile quantificare il "premio senza checkpoint fine" atteso dal
mandato** (atteso ~50x, riprefill ~16,6 s) perche' il braccio non arriva a generare quel numero:
si ferma prima, con una causa determinata e determinabile (OOM VRAM-a-fasi), non con un esito
ambiguo.

### REGOLA DI SICUREZZA (scolpita dal coordinatore, 17/8, da questo momento vale come RUNBOOK)

> **Ogni banco lungo MULTI-RICHIESTA a ctx150k DEVE passare `-cms 32` (o `CtxCheckpointMinStep`
> basso): la spaziatura a difetto lascia un residuo di ~2k token che forza il rientro in
> modalita' prefill a meta' processo e va in OOM (staging 1.729 MiB vs ~549 liberi) --
> instabilita' strutturale, non lentezza. I banchi storici mono-richiesta non sono esposti (mai
> un restore).**

Ambito verificato della regola: si applica a `sota100k_ctx150k.ps1` con `-Repliche > 1` a
`-Context 150000`. Non verificato (fuori dallo scopo di questo braccio) se il residuo-soglia
scali con `-Context` diverso o con `-StartBatch` diverso da 2048 -- da trattare come ignoto, non
come sicuro, finche' non misurato.

## INTERPRETAZIONE FINALE per il mandato — nuovo protocollo del banco lungo

**Il nuovo protocollo esiste, condizionato**: sul banco lungo (101.597 token, ctx 150k), la
sequenza «prima richiesta piena (~14 min) + repliche successive a costo di decine di secondi»
e' **confermata e misurata** (B-cms32: r2/r3 a 0,49/0,47 min contro 13,65 min di r1, premio
2.306-2.319x sul prefill), **ma solo con `-cms 32`** (spaziatura minima checkpoint fine). Il
banco B-base ha mostrato che la configurazione a difetto (`-cms 8192`) su questo stesso banco
**non degrada soltanto** il premio (da atteso ~50x a probabilmente meno, visto il residuo di
2.048 token) -- **rompe il processo**: il residuo di 2.048 token e' abbastanza grande da forzare
il gestore VRAM-a-fasi a rientrare in modalita' prefill a meta' processo, e su questa scheda da
12 GB a ctx=150k quella transizione va in OOM. `-cms 32` evita il problema non solo perche' e'
piu' veloce, ma perche' il suo residuo (4 token) resta sempre sotto la riserva-ubatch=64 della
modalita' decode e non innesca mai quella transizione.

**Annotazione per la promozione B,B,A,B-lungo**: il braccio "B-lungo" per banchi futuri su
questo prompt/contesto va eseguito con `sota100k_ctx150k.ps1 -Repliche N -CtxCheckpointMinStep 32`
(il difetto attuale del parametro, quindi basta non passare `-CtxCheckpointMinStep` oppure
passarlo esplicitamente a 32) -- **mai** con la spaziatura a difetto del binario (8192) su
contesti di questa taglia, che oggi e' non solo piu' lenta ma **non sicura**.

---

# Scala mask p1 — GO SCALA ricevuto, mandato `P1_DEGRADO_ROOT_CAUSE.md`

Protocollo comune (tutti gli A1/A2/A3/A6): `run_porto_hot.ps1 -MaxTokens 1200 -Repetitions 4
-PortoHotSnapshot $true -SpecNmax 3 -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=<N>'`, lanci staccati (Win32_Process.Create),
telemetria `sample_hw.ps1`, QUIETE 300s fra bracci. Verificato prima di lanciare (lettore, non
assunto): `server-context.cpp:3237-3274` conferma bit-per-bit la semantica del piano (1=KV target,
2=KV draft, 4=spec, 8=cache esperti). r1 = cattura (fuori verdetto), verdetto = p1 di r2-r4 con
cancello **binomiale 2σ** (deciso dal coordinatore oggi): σ = sqrt(0,90281·0,09719/n), riferimento
p=0,90281 (771/854, r1, identico su tutti i bracci).

Per A7 (unico diverso): `-PortoHotSnapshot $false -CtxCheckpointMinStep 8` (nessun mask, il
free-run vero non passa mai dal porto-hot). **Modifica al runner**, stessa procedura autorizzata
di `-SpecNmax`/`-CtxCheckpointMinStep` su `sota100k_ctx150k.ps1`: aggiunto `[int]
$CtxCheckpointMinStep = 8192` (difetto = comportamento invariato) e `'-cms', "$CtxCheckpointMinStep"`
a `$argsServer` (`run_porto_hot.ps1:12,119`). Diff in `...\work\runs\run_porto_hot_ctxcheckpointminstep.patch`
(2 hunk). Sintassi verificata, 0 errori.

## Tabella completa

| braccio | mask | prompt eval r2/r3/r4 | p1 r2/r3/r4 | 2σ (n proprio) | dentro banda? | t/s r2/r3/r4 | SHA r2/r3/r4 |
|---|---|---|---|---|---|---|---|
| **A1** | 1 (solo KV tgt) | 4/4/4 tok | .82706/.86811/.87192 | ±2,03/±2,03/±2,03 pt | **NO/NO/NO** (delta 7,58/3,47/3,09 pt) | 15,18/15,72/16,13 | tutte diverse |
| **A2** | 8 (solo cache) | 68/68/68 tok | .82054/.82054/.82054 | ±2,03 pt (n=847) | **NO** (delta 8,23 pt, costante) | 15,02/15,06/15,09 | identiche fra loro |
| **A3** | 0 (nessuno stato) | 68/68/68 tok | .78654/.87074/.85766 | ±2,10/±2,03/±2,10 pt | **NO/NO/NO** (delta 11,63/3,21/4,52 pt) | 13,89/15,88/15,56 | tutte diverse |
| **A6** | 4 (solo spec) | 68/68/68 tok | .78654/.87074/.85766 | come A3 | **BIT-IDENTICO ad A3** (stesso p1, stesse SHA, stessi content_chars) | 13,84/15,82/15,53 | = A3 esatte |
| **A7** | free-run+cms8 | **4/4/4 tok** | .81078/.81862/.85649 | ±2,03/±2,06/±1,99 pt | **NO/NO/NO** (delta 9,20/8,42/4,63 pt) | 14,78/14,96/16,16 | **= baseline storica esatte** |

(riferimento comune r1, tutti i bracci: prompt eval 68 tok, p1 .90281 (771/854), SHA
`1EDA23452D...9089`, identico in ognuno dei 5 lanci — identità di traiettoria fredda confermata
5/5.)

## Le tre letture meccaniche, verificate sul log

1. **Prompt eval segue esattamente la meccanica prevista dal piano su tutti e 5 i bracci**: bit 1
   acceso (A1) o checkpoint upstream con spaziatura bassa (A7) → 4 token; bit 1 spento (A2, A3,
   A6) → 68 token. **Zero sorprese su questo fronte**: il meccanismo del checkpoint/KV-restore
   fa esattamente quello che il codice dice che deve fare.
2. **A6 = A3 bit-per-bit**: conferma diretta, non dedotta, che il bit 4 (stato speculativo) è
   inerte con `draft-dspark`, esattamente come l'analisi statica del piano prevedeva
   (`common/speculative.cpp:182-183`, nessun override in `914-1283`). Nessun buco nel piano su
   questo punto.
3. **A1 migliora p1 ma non lo recupera**: rispetto al free-run originale (.81-.86), mask=1 porta
   p1 a .827-.872 — un miglioramento reale (confermato: A1 > free-run su tutte e tre le repliche)
   ma **non** dentro banda 2σ da .90281 su nessuna delle tre. Per la regola del piano ("p1 ≠
   .90281 ⇒ C2 è co-responsabile"): **C2 è co-responsabile**, confermato.

## IL RISULTATO CHE CAMBIA IL VERDETTO: A7

**A7 riproduce ESATTAMENTE, bit per bit, la traiettoria del free-run storico rotto**
(`warm_anchor_b1200_20260817`, già a ledger sopra), nonostante il meccanismo del prefill funzioni
alla perfezione:

```text
                    A7 (con -cms 8, prompt eval->4 tok)     free-run storico (-cms 8192 di difetto, prompt eval->67 tok)
r2: p1              0,81078 (677/835)                        0,81078 (677/835)              <- IDENTICO
r2: SHA             3CD00E94EA1DE63A...CDEA4DABA             3CD00E94EA...4DABA              <- IDENTICO
r2: content_chars   2107                                     2107                            <- IDENTICO
r3: p1/SHA/chars    0,81862 (677/827) / AA5A128AC7...9DDF7 / 3015   <- IDENTICI su tutti e tre i campi
r4: p1/SHA/chars    0,85649 (746/871) / C65F9F2414...8D78B / 3133   <- IDENTICI su tutti e tre i campi
```

Verificato sul log che il meccanismo E' scattato correttamente (non e' un fallimento silenzioso):

```text
1.57.943.060  created context checkpoint 2 of 32 (pos_min=63, pos_max=63, n_tokens=64) -- esattamente
              come previsto dal piano (FIX-0 §4): "sara' esattamente (n_tokens=64, pos_min=63, pos_max=63)"
3.10.247.276  task 432 | checking checkpoint with [63, 63] against 67...
3.10.251.019  task 432 | restored context checkpoint (pos_min=63, pos_max=63, n_tokens=64, n_past=64)
              -- identico su r3 (task 956) e r4 (task 1480)
```

**Lettura**: il prefill si riduce esattamente come previsto (67->4 token, il "tempo" e' recuperato
al 100%), ma la QUALITA' (p1, traiettoria, testo) resta **bit-per-bit quella del cammino rotto** --
non solo "non migliora", riproduce l'IDENTICA sequenza di byte del baseline che il fix doveva
correggere. Questo **falsifica l'ipotesi di lavoro di FIX-0/A7** ("se p1 regge ~.90 il fix e'
spedibile via flag upstream"): il fix upstream (`--ctx-checkpoint-min-step` basso) risolve
**solo** il sintomo cronometrico, non la causa della degradazione di p1.

**Perche' verosimilmente**: A7 usa il cammino checkpoint **`PARTIAL_ONLY`** (§1.1 del piano), che
**non** ripristina i tre tensori `*_hot` dell'anello DSV4 (`kv_csa/hca/lid`, coperti solo in
modalita' `ON_DEVICE`). A1 (mask=1, porto-hot) usa **`ON_DEVICE`** e infatti mostra un
miglioramento reale (seppure incompleto) che A7 non mostra affatto. La differenza fra "A1 migliora
parzialmente" e "A7 non migliora per niente" isola **C3** (il cammino `PARTIAL_ONLY` non copre
l'anello caldo) come fattore che pesa, non solo C2. **Nessuna delle due canonicalizzazioni prese
da sole (checkpoint upstream A7, o KV target ON_DEVICE A1) chiude interamente il divario**: A1 ci
arriva piu' vicino ma non basta, A7 non ci arriva affatto pur risolvendo il sintomo cronometrico.

## Controllo di coerenza (campione: A7/r2)

Letto per intero. HTML/CSS coerente in tema (landing page cyberpunk NeuraForge, come da prompt),
nessun loop, nessuna corruzione, lingua sana (italiano nel testo introduttivo, poi codice). Sano.
Atteso, dato che e' la stessa identica traiettoria byte-per-byte del baseline storico gia' letto e
verificato in precedenza.

## VERDETTO C1/C2/C3 (secco, per il mandato)

- **C1 (riuso prompt morto, 67/68 ricalcolati)**: MECCANISMO CONFERMATO (prompt eval si comporta
  esattamente come previsto su tutti i bracci) **MA NON E' LA CAUSA SUFFICIENTE della perdita di
  p1**: A7 lo risolve al 100% sul piano cronometrico e ottiene ZERO recupero di p1. **C1 da solo
  non spiega il degrado.**
- **C2 (residenza cache esperti -> partizione CPU/GPU -> arrotondamento)**: **CO-RESPONSABILE**,
  confermato da A1 (miglioramento parziale senza toccare la cache) e dal confronto A2-vs-A3 (la
  canonicalizzazione della sola cache, senza il KV, non produce un beneficio distinguibile da
  2σ) -- indicazione che l'effetto della cache non e' isolabile pulito con gli strumenti di
  questa scala, resta plausibile ma non quantificato da solo.
- **C3 (checkpoint `PARTIAL_ONLY` non copre l'anello caldo DSV4)**: **e' il candidato che meglio
  spiega il divario A1-vs-A7** (stesso obiettivo dichiarato -- ridurre il prefill -- esito
  qualitativo opposto). Non dimostrato con un braccio dedicato che isoli SOLO C3 (richiederebbe
  confrontare ON_DEVICE vs PARTIAL_ONLY a parita' di tutto il resto, non fatto in questa scala).
- **Nessun braccio arriva a p1≈.90281 dentro la banda 2σ.** Il fix "zero righe" (A7/FIX-0) NON e'
  spedibile cosi' com'e': risolve il tempo, non la qualita'. **FIX-1** (una riga,
  `server-context.cpp:3800`, gia' proposta nel piano) produrrebbe lo stesso identico checkpoint
  di A7 (verificato aritmeticamente nel piano) e quindi **erediterebbe lo stesso limite** -- non
  e' una via diversa da A7 dal punto di vista del risultato, solo un modo piu' pulito di ottenere
  lo stesso `-cms` piccolo. Il fronte resta aperto: serve un braccio che isoli C3 (`ON_DEVICE` vs
  `PARTIAL_ONLY` a parita' di tutto) prima di proporre un fix definitivo.

Postflight finale: 0 processi llama, RAM libera 88,6 GB, VRAM 305/11.811 MiB. Nessun errore/
divergenza su nessuno dei 5 bracci. Percorsi: `...\work\runs\mask_a{1,2,3,6,7}_*` (server.log,
summary.json, r*.output.txt/response.json, hw.csv/cpu.csv per ciascuno).

**Riserve esplicite per il coordinatore, non decise qui**:
1. la parita' p1 di Cancello 2 (-5,4%/-2,8% contro soglia 2,4%) e' spiegata ma non ri-misurata
   con un campione piu' grande -- vale la pena un braccio diagnostico a `MaxTokens` piu' alto
   (es. 1200 come B1200) per vedere se la banda si stringe come l'aritmetica del rumore
   campionario suggerisce;
2. la terza modifica (`-CtxCheckpointMinStep`) e' stata applicata in autonomia, non
   pre-autorizzata testualmente -- da confermare;
3. il crash OOM di B-base e' un fatto nuovo sulla capacita' della scheda a ctx=150k con
   checkpoint grossolani: potrebbe interessare anche altri banchi lunghi che non usano `-cms 32`
   esplicitamente.

NESSUN commit eseguito. Percorsi completi di tutti gli artefatti (log/summary/output/response/
hw.csv/cpu.csv, entrambi i bracci) in `D:\ds4_work\llama_run\` con tag `kvlong_cms32_20260817`* e
`kvlong_base_20260817`*; diff in `C:\Users\imanu\Documents\Codex\2026-08-14\ds4-porto-20tps\work\
runs\sota100k_kvreuse.patch` e `sota100k_kvreuse_ctxcheckpointminstep.patch`.

---

# SETTIMA RIPRESA — binario nuovo D:\llama-subtract: V0/V1/FIX-1/SONDA (le tre patch A/B/C)

Esecutore: settimo turno, contesto fresco. Mandato del coordinatore: certificare sul banco il
binario nuovo `D:\llama-subtract\build\bin\llama-server.exe` (patch A adaptive-K v0, B fix-1
checkpoint fine-prompt, C fix cattura K=0 — vedi `D:\ds4_work\design\impl\NOTE_IMPLEMENTAZIONE.md`)
su quattro bracci in ordine: V0 (non-regressione, leve nuove spente), V1 (il braccio decisivo del
fix cattura, `LLAMA_OVERLAP_K=0` con grafi accesi), FIX-1 (meccanismo del checkpoint di fine
prompt), SONDA adaptive-K (osservativa).

**Correzione di protocollo ricevuta a metà sessione (vince sul runbook)**: la QUIETE di 300 s fra
bracci (RUNBOOK §6.6) è **abolita** — con chiusura pulita verificata (0 processi llama residui,
VRAM tornata al livello di riposo) si incatena subito il braccio successivo, nessuna attesa a
tempo. Applicato dalla transizione V0→V1 in poi.

## Preflight

```text
data/ora        = 2026-08-17 08:11:19
uptime_min      = 3349,7 (~55,8h, nessun riavvio recente)
processi llama  = 0
porta 8000 (UI) = nessun listener (non toccata)
porta 8099      = libera
porta 8100      = libera
nvidia-smi (UNICA invocazione di preflight) =
  NVIDIA GeForce RTX 3060, sm=210MHz, mem=405MHz, power=12.57W, used=305MiB, free=11811MiB,
  pcie_gen=1 (a riposo), pcie_width=16, throttle=0x0000000000000001
ram_libera_gb   = 88.4 GB
disco_c_gb      = 49.3 GB liberi
disco_d_gb      = 119.7 GB liberi
sha_llama_server= 8E98393EB0225C05A5CE19AF1A02BB6D6112D6B69C2DC901B22F43465B7FB1CD  (NUOVO binario)
sha_ggml_cuda   = 1E2037EDAB78CB9C09D4503C9913A9357C4B713AED3D37C9A4118768A04D4177  (NUOVO binario)
sha_llama_impl  = 91FF17F0F64B6771A61A5545CEF3ECAE10172A0ACEA3F2D48CBD11596F2AEA29  (NUOVO — FIX-1 vive qui)
sha_jprompt     = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9 (252 byte) -- PASSATO
build           = build 10093 (3014d3756) -- stesso numero upstream, gli SHA sopra sono l'identita' vera
```

Tutti e tre gli hash **coincidono esattamente** con le impronte dichiarate dal mandato e con quelle
registrate in `NOTE_IMPLEMENTAZIONE.md` §6.1 dopo la build (`exit 0`, 13,4 s). Cancello 1.7-1.8
PASSATO.

## Verifica lettori PRIMA di lanciare (regola vitale, grep sul codice di `D:\llama-subtract`)

```text
cache-esperti.cu:2206-2209   K_ADATTIVO senza scadenza_ep -> cache_leva_rifiutata("K_ADATTIVO",
                              "richiede CALENDARIO_TRACE + CALENDARIO_PIANO validi...")
cache-esperti.cu:1136-1139   cache_calendario_trasporto_carica: LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO
                              assente/vuota -> return false SILENZIOSO (nessun log)
cache-esperti.cu:1050-1051   cache_calendario_carica: LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE
cache-esperti.cu:455-470     cache_leva_rifiutata: senza LLAMA_CACHE_ESPERTI_STRICT=0 esplicito,
                              stampa e poi exit(1) -- FATALE DI DIFETTO, non un avviso
cache-esperti.cu:7074/7162   righe di dump "adaptive-K ->" e "fork cronometro ->" (mis_saltati)
server-context.cpp:3810-3820 LLAMA_CTXCP_PROMPT_END: leggo il cancello a valore, near_prompt_end
                              gia' calcolato, SRV_WRN una sola volta se acceso
```

**Scoperta rilevante prima di lanciare la SONDA**: nessun piano PORTCAL1 compatibile con questo
carico (B1200, warm-restore, K=2, `CALENDARIO_K0=0`) esiste sul disco. L'unico piano trovato
(`macro_v2_current_codegen_calendar_k0_tail77_q8_drain_b160_r1_20260815.portcal`, in
`...\work\runs\`) e' stato costruito per il carico **B160 con K0/SLOT_DIRETTI** (`--lane k0
--tail-cycles 77 --copy-quanta 8 --drain-cycle`), un regime diverso e incompatibile col mandato di
oggi (che impone esplicitamente `CALENDARIO_K0=0` su tutti e 4 i bracci). Usarlo avrebbe introdotto
una variabile sperimentale non autorizzata. Deciso di lanciare comunque la SONDA cosi' come
letteralmente specificata dal mandato (sola `LLAMA_CACHE_ESPERTI_K_ADATTIVO=1`) per verificare
empiricamente l'esito, non dedurlo soltanto dal codice.

---

## Braccio 1/4 — V0 (`v0_k2_subtract`) — non-regressione, leve nuove spente

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'v0_k2_subtract' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15'
protocollo = warm-restore (1 processo, cattura r1 fuori verdetto, mediana r2-r4)
telemetria = work\sample_hw.ps1 -Tag v0_k2_subtract -OutDir <runs> -IntervalSeconds 2
```

| richiesta | ruolo | eval t/s | p1 | SHA output | content_chars |
|---|---|---:|---|---|---:|
| r1 | cattura | 16,87 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |
| r2 | verdetto | 17,07 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |
| r3 | verdetto | 17,05 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |
| r4 | verdetto | 17,06 | 0.90281 (771/854) | `1EDA23452D...9089` | 3782 |

```text
valori ordinati (r2,r3,r4) : 17,05 / 17,06 / 17,07
MEDIANA                    : 17,06
spread max-min              : 0,12 %

vs riferimento 16,86 (warm_anchor_restore_b1200_20260817, binario vecchio) : +1,19 %
  -> NON DISTINGUE (dentro banda ±3%): non-regressione confermata
```

**Righe testimone (verbatim)**:

```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0,
  spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0,
  scudo=0, sfratto_par=1, dma=0, dma_strato=0                              <- identica al riferimento
manifesto: GGML_CUDA_DISABLE_GRAPHS=<spento>(D)                            <- grafi ACCESI
manifesto: LLAMA_CACHE_ESPERTI_SFRATTO_PAR=1(E)
righe sched-profilo = 0
motore: common_speculative_impl_draft_dflash: - n_max=3, n_min=0, p_min=0.00, conf_min=0.80
porto-hot: cattura n_tokens=64, coda=4, mask=15, target=0.009 MiB, draft=0.002 MiB, numero=1  (r1)
porto-hot: ripristino n_tokens=64, mask=15, ..., numero=1/2/3                                  (r2/r3/r4)
cache-esperti: FORK/JOIN acceso (livello 2, blocchi copia 8, esatto 0: no, a un token il MoE
  mascherato (come oggi))
cache-esperti: fork cronometro -> lanci=7793, campioni=121, saltati in cattura=5380, durata media
  della copia=0.941 ms                                          <- mis_saltati>0 anche a K=2 (nota
                                                                     NOTE_IMPLEMENTAZIONE SS5.8: puo'
                                                                     legittimamente essere 0 qui; e'
                                                                     >0, ancora meglio)
cache-esperti: domanda 1099385 (colpi 780122 = 71.0%, buchi 319263, miss 29.0%, in ritardo 0)
CANCELLO 1 di A (leva spenta -> nessuna riga "adaptive-K"): ASSENTE, come atteso -- PASSATO
```

**Cancelli**: riga cache-esperti identica -- PASSATO. `sfratto_par=1` -- PASSATO. `GGML_CUDA_
DISABLE_GRAPHS=<spento>(D)` -- PASSATO. `sched-profilo`=0 su entrambi i lati del confronto (anche
il riferimento 16,86 aveva 0 righe) -- PASSATO. `GGML_CUDA_GRAPH_STATS=0(D)` -- PASSATO. p1
identico -- PASSATO. Zero `GGML_ASSERT`/`CUDA error`/divergenze/`CONTESA` -- PASSATO. Nessuna riga
"adaptive-K" -- PASSATO (cancello 1 di A). Chiusura: `ctrl-c`, nessuna `RISERVA`. SHA output r2
verificato via `Get-FileHash`: `1EDA23452DE9292C817EAF47532724A409DD2FFE3B3EF9E165ED887BA4169089`
(3788 byte, 3784 caratteri raw) -- identico allo storico.

**Controllo di coerenza testuale** (r2, banco lungo in token ma corto in caratteri: 3782,
letto per intero): apre in italiano corretto ("Ecco il codice HTML completo..."), HTML/CSS
cyberpunk neon pertinente al prompt NeuraForge, si interrompe a meta' di una dichiarazione CSS per
esaurimento budget. Lingua sana=si, loop/ripetizioni=no, pertinenza=si, degradazione=no.

**Telemetria** (`v0_k2_subtract.hw.csv`, 124 campioni/2s, 119 busy util>30%):
SM mediano 1927 MHz (min 1927, max 1942, regime SOTA, nessun throttle) · potenza mediana 104,6 W ·
VRAM picco 11893 MiB (riposo 305 MiB) · CPU% media 55,3%.

**ESITO: PROMOSSO.** Non-regressione confermata; V0 diventa il riferimento del binario nuovo per
gli altri bracci di oggi (17,06, genealogia calda-con-restore).

percorsi file: `...\work\runs\v0_k2_subtract.*`

---

## Braccio 2/4 — V1 (`v1_k0_subtract`) — IL BRACCIO DECISIVO del fix cattura K=0

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'v1_k0_subtract' -MaxTokens 1200 -Repetitions 1
  -PortoHotSnapshot $false -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;LLAMA_OVERLAP_K=0'
protocollo = FREE-RUN (snapshot 0), 1 sola richiesta, grafi CUDA ACCESI
```

Contesto: il precedente turno di oggi aveva registrato `warm_k0_b1200_20260817` **ABORTITO** con
`CUDA error: operation failed due to a previous error during capture` (`common.cuh:1681`), e aveva
isolato con `k0_nograph_diag_b1200_20260817` che il crash e' specifico della CATTURA del grafo
(K=0 con grafi spenti gira senza errori: 11,65 t/s, p1 0.78319, SHA `F501E5C5...E194A`). Il fix C
di oggi (`fix_k0_capture.patch`) protegge la sonda `fork_gate` durante la cattura con
`cudaStreamIsCapturing` + contatore `mis_saltati`.

**Risultato: NESSUN CRASH.** 1200 token generati, `finish_reason=length`.

```text
r1 (unica) : eval 13,30 t/s   wall 93295,1 ms   p1 0.78319 (643 accepted / 821 generated)
             SHA output = F501E5C5785EF309B34870AA0AAC54161FF90700011F37825F1EBE5172FE194A
             content_chars = 1794   prompt_tokens = 68   completion_tokens = 1200
```

**Confronto con `k0_nograph_diag_b1200_20260817` (K=0, grafi SPENTI, diagnostico storico)**:

```text
                    V1 (K=0, grafi ACCESI, oggi)     k0_nograph_diag (K=0, grafi SPENTI, storico)
eval t/s            13,30                             11,65                    <- +14,2% coi grafi
p1                  0.78319 (643/821)                 0.78319 (643/821)        <- IDENTICO
SHA output          F501E5C5785EF3...E194A            F501E5C5785EF3...E194A   <- IDENTICO
copie/buchi         domanda 357588, colpi 55.3%,       domanda 357588, colpi    <- IDENTICO
                    buchi 159993                       55.3%, buchi 159993
```

Traiettoria di calcolo **bit-identica** con e senza grafi (atteso: i grafi CUDA sono
un'ottimizzazione dell'esecuzione, non cambiano l'aritmetica) -- prova ulteriore di correttezza,
non solo di assenza di crash.

**Righe testimone (verbatim)**:

```text
manifesto: LLAMA_OVERLAP_K=0(E)                                    <- leva confermata esplicita
manifesto: GGML_CUDA_DISABLE_GRAPHS=<spento>(D)                    <- grafi ACCESI, regola vitale
cache-esperti: 473 slot da 6.75 MiB = ... sfratto_par=1, ...        <- identica al riferimento
righe sched-profilo = 0
CANCELLO DECISIVO: cache-esperti: fork cronometro -> lanci=2197, campioni=34,
  saltati in cattura=1591, durata media della copia=2.015 ms       <- N=1591 > 0 -- FIX CONFERMATO
eval time = 90231.26 ms / 1200 tokens (75.19 ms per token, 13.30 tokens per second)
(nessuna riga GGML_ASSERT / CUDA error / invalid index nel log)
(nessuna riga RISERVA / MORTO / RICHIESTA FALLITA / CONTESA)
shutdown = ctrl-c
```

**Cancelli**: 1200 token generati con 0 `CUDA error` -- PASSATO. `saltati in cattura`=1591 (N>0,
l'unico esito falsificante era N==0) -- PASSATO, **ipotesi CONFERMATA, non falsificata**. Riga
cache-esperti identica -- PASSATO. Zero `GGML_ASSERT`/divergenze/`CONTESA` -- PASSATO. Chiusura
`ctrl-c` -- PASSATO.

**Controllo di coerenza testuale** (r1, 1794 caratteri, letto per intero): italiano corretto,
HTML/CSS cyberpunk pertinente al prompt NeuraForge, tronco a meta' di un commento per esaurimento
budget. Lingua sana=si, loop=no, pertinenza=si, degradazione=no.

**Telemetria** (`v1_k0_subtract.hw.csv`, 43 campioni/2s, 40 busy util>30%):
SM mediano 1927 MHz (min 1792, max 1942, nessun throttle) · potenza mediana 107,4 W · VRAM picco
11807 MiB · CPU% media 31,2% (piu' bassa di V0: K=0 toglie lavoro alla lane CPU, coerente).

**ESITO: PROMOSSO.** Il fix di cattura K=0 (`fix_k0_capture.patch`) funziona: risolve il crash
storico, produce un output verificabilmente corretto (bit-identico al percorso di riferimento
senza grafi) e recupera +14,2% di velocita' grazie ai grafi CUDA. t/s non confrontabile con la
SOTA K=2 (regime di calcolo diverso, atteso): e' un dato, non un verdetto di velocita'.

percorsi file: `...\work\runs\v1_k0_subtract.*`

---

## Braccio 3/4 — FIX-1 (`fix1_freerun`) — meccanismo del checkpoint di fine prompt

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'fix1_freerun' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $false -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;LLAMA_CTXCP_PROMPT_END=1'
protocollo = FREE-RUN (snapshot 0), 4 richieste, r1 warm-up fuori verdetto
```

Contesto: il turno precedente di oggi aveva gia' scoperto (banco maschera A1-A7) che il fix
upstream equivalente (`-cms` basso, braccio A7) riproduce **bit per bit** la traiettoria del
free-run rotto e non recupera p1 per niente (colpa isolata su C3, il checkpoint `PARTIAL_ONLY` che
non copre l'anello caldo DSV4). Il mandato di oggi chiedeva quindi di verificare **solo il
meccanismo** (prompt eval ridotto + checkpoint creato), non la qualita'.

| richiesta | ruolo | eval t/s | p1 | prompt eval | SHA output | content_chars |
|---|---|---:|---|---:|---|---:|
| r1 | warm-up | 16,92 | 0.90281 (771/854) | 68 tok | `1EDA23452D...9089` (= freddo) | 3782 |
| r2 | verdetto | 14,81 | 0.81078 (677/835) | **4 tok** | `3CD00E94EA...4DABA` | 2107 |
| r3 | verdetto | 14,99 | 0.81862 (677/827) | **4 tok** | `AA5A128AC7...9DDF7` | 3015 |
| r4 | verdetto | 16,20 | 0.85649 (746/871) | **4 tok** | `C65F9F2414...8D78B` | 3133 |

```text
valori ordinati (r2,r3,r4) : 14,81 / 14,99 / 16,20
MEDIANA                    : 14,99
spread max-min              : 9,39 %   (sopra soglia 5%: banco free-run rumoroso, atteso §8.9 punto 3)

SHA/p1 di r2/r3/r4 = IDENTICI bit-per-bit al free-run rotto storico (warm_anchor_b1200_20260817):
  la qualita' NON recupera -- ESATTAMENTE come anticipato dal mandato e dalla scoperta A7 di ieri.
```

**Righe testimone (verbatim) -- CANCELLO MECCANISMO**:

```text
prompt eval time =    3233.76 ms /    68 tokens (...)   task 0    (r1, nessun checkpoint ancora)
prompt eval time =     286.54 ms /     4 tokens (...)   task 432  (r2)  <- 4 <= 4, PASSATO
prompt eval time =     271.30 ms /     4 tokens (...)   task 956  (r3)  <- 4 <= 4, PASSATO
prompt eval time =     272.80 ms /     4 tokens (...)   task 1480 (r4)  <- 4 <= 4, PASSATO
LLAMA_CTXCP_PROMPT_END = 1: la spaziatura non veta piu' il checkpoint di fine prompt   (1 volta)
created context checkpoint 2 of 32 (pos_min = 63, pos_max = 63, n_tokens = 64, ...)    (dopo r1)
task 432 | checking checkpoint with [63, 63] against 67...
task 432 | restored context checkpoint (pos_min = 63, pos_max = 63, n_tokens = 64, n_past = 64, ...)
(pattern identico su task 956 e task 1480)
```

**Cancelli**: prompt eval r2-r4 <= 4 token -- PASSATO. Checkpoint di fine prompt creato e
ripristinato esplicitamente nel log -- PASSATO (meccanismo confermato, non dedotto). Riga
cache-esperti identica -- PASSATO. `GGML_CUDA_DISABLE_GRAPHS=<spento>(D)` -- PASSATO. Zero
`GGML_ASSERT`/`CUDA error`/`CONTESA` -- PASSATO. Chiusura `ctrl-c` -- PASSATO. p1 **non** e' un
cancello in regime free-run (§8.9 punto 5): registrato come dato, coerente con l'atteso .81-.87.

**Controllo di coerenza testuale** (r2, 2107 caratteri, letto per intero -- stessa traiettoria
byte-per-byte gia' letta e giudicata sana nel turno precedente): italiano corretto, HTML/CSS
cyberpunk NeuraForge pertinente, tronco a meta' di una dichiarazione CSS per esaurimento budget.
Lingua sana=si, loop=no, pertinenza=si, degradazione=no.

**Telemetria** (`fix1_freerun.hw.csv`, 134 campioni/2s, 129 busy util>30%):
SM mediano 1927 MHz (nessun throttle) · potenza mediana 102,9 W · VRAM picco 11895 MiB · CPU% media
60,0%.

**ESITO: PROMOSSO (meccanismo).** Il prefill si riduce esattamente come progettato (67-68 -> 4
token, premio di latenza ~3200ms -> ~280ms per richiesta calda). La qualita' (p1, traiettoria)
resta quella del cammino rotto, **atteso e non un fallimento della patch**: il colpevole rimane C3
(checkpoint `PARTIAL_ONLY` non copre l'anello caldo DSV4), gia' isolato ieri e fuori mandato oggi.

percorsi file: `...\work\runs\fix1_freerun.*`

---

## Braccio 4/4 — SONDA adaptive-K (`adk_sonda`) — NESSUNA MISURA (prerequisito mancante)

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'adk_sonda' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1'
protocollo = warm-restore, come da mandato -- lanciato letteralmente cosi' com'e' specificato
```

**La corsa e' fallita durante l'inizializzazione**, dopo il caricamento completo dei pesi e la
riserva del compute buffer (`sched_reserve: reserve took 49.17 ms`), nella fase di warmup
(`common_init_: warming up the model with an empty run`), **prima di aprire la porta HTTP** (mai
raggiunto `/health`, ~1 min 44 s dall'avvio del processo):

```text
cache-esperti: *** K_ADATTIVO CHIESTA MA SPENTA: richiede CALENDARIO_TRACE + CALENDARIO_PIANO
               validi: senza piano non c'e' deadline ***
cache-esperti: la corsa si ferma qui. Proseguendo, il banco misurerebbe un'altra
               configurazione e restituirebbe un t/s plausibile lo stesso.
               Correggere la configurazione, oppure LLAMA_CACHE_ESPERTI_STRICT=0
               per proseguire sapendo che quella leva non c'e'.
```

Il processo esce da solo (`exit(1)`, confermato nel codice a `cache-esperti.cu:470`); il runner
riceve `shutdown=gia-uscito` (non un `ctrl-c` riuscito, ma nessun residuo: vedi postflight sotto).
Nessun `.summary.json`, nessun `.r*.output.txt` prodotto. `sample_hw.ps1` non avviato (mai
raggiunto `/health`).

**Diagnosi (verificata sul codice, non dedotta a posteriori)**: `LLAMA_CACHE_ESPERTI_K_ADATTIVO`
richiede un piano PORTCAL1 caricato tramite le variabili **`LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE`**
(trace) + **`LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO`** (piano, file binario `PORTCAL1`) — nessuna
delle due e' nel mandato ne' ha un default embedded (`cache-esperti.cu:1136-1139`:
senza `CALENDARIO_PIANO` valorizzata, `cache_calendario_trasporto_carica` ritorna `false` in
silenzio; poi `cache-esperti.cu:2206-2209` rifiuta esplicitamente `K_ADATTIVO` per l'assenza di
`scadenza_ep`). Senza `LLAMA_CACHE_ESPERTI_STRICT=0` esplicito (non presente nel mandato), il
cancello e' **fatale di difetto** (`cache-esperti.cu:455-470`, `exit(1)`) — per design ("Fermarsi
costa trenta secondi. Non fermarsi e' costato due notti.", commento in testa alla funzione).

Nessun piano compatibile col carico di oggi esiste sul disco: l'unico trovato
(`macro_v2_current_codegen_calendar_k0_tail77_q8_drain_b160_r1_20260815.portcal`, `HANDOFF_PORTO_
16_AGOSTO_2026.md` §18.3) e' per B160 con `CALENDARIO_K0=1`/`SLOT_DIRETTI=1` (`--lane k0
--tail-cycles 77 --copy-quanta 8 --drain-cycle`) — un regime opposto a quello di oggi, che impone
`CALENDARIO_K0=0` su tutti e 4 i bracci. Usarlo avrebbe misurato una configurazione diversa da
quella chiesta (lo stesso errore per cui `cache_leva_rifiutata` esiste). Non generato un piano
nuovo: costruirlo (`LLAMA_CACHE_ESPERTI_TRACCIA=<file>` per registrare, poi
`analyze_route_trace.py --tail-cycles N --lane ... --copy-quanta N [--drain-cycle]` per costruirlo)
richiede scelte di parametri (tail-cycles, lane, copy-quanta) non specificate dal mandato per il
regime K=2/warm-restore di oggi: improvvisarle avrebbe violato la regola di non decidere al posto
del coordinatore.

**Postflight**: 0 processi llama residui, VRAM 305 MiB (= riposo), RAM libera 88,5 GB — **nessun
danno alla macchina** nonostante l'uscita non fosse un `ctrl-c` pulito.

**ESITO: NESSUNA MISURA** (RUNBOOK §4.8: un'uscita prima di `eval time` non e' 0 t/s, e' nessuna
misura). Non e' un fallimento della leva K_ADATTIVO in se' (il codice si comporta esattamente come
progettato: rifiuta con un messaggio esplicito invece di misurare in silenzio un'altra
configurazione — la stessa disciplina gia' vista per `FORK`/`MASSA=2`/`CALENDARIO_SLOT_DIRETTI` in
questo stesso file). E' un **prerequisito operativo mancante dal mandato**: serve una trace +
piano PORTCAL1 costruiti apposta per il carico B1200/warm-restore/K=2 di oggi, oppure
un'autorizzazione esplicita a girare con `LLAMA_CACHE_ESPERTI_STRICT=0` (nel qual caso la leva
sarebbe silenziosamente spenta e il braccio misurerebbe V0, non la sonda) — decisione che spetta al
coordinatore, non presa qui.

percorsi file: `...\work\runs\adk_sonda.server.log` (261 righe, nessun `.summary.json`)

---

## VERDETTO FINALE — tabella dei 4 bracci

| braccio | tag | t/s (mediana) | p1 | cancello specifico | esito |
|---|---|---:|---|---|---|
| V0 | v0_k2_subtract | **17,06** (r2-r4, spread 0,12%) | 0.90281 costante | nessuna riga "adaptive-K" (leva spenta) — PASSATO | **PROMOSSO** — non-regressione vs 16,86 (+1,19%, dentro banda) |
| V1 | v1_k0_subtract | 13,30 (r1 unica) | 0.78319 | `saltati in cattura=1591` (N>0) — PASSATO | **PROMOSSO** — fix cattura CONFERMATO, 0 CUDA error, bit-identico allo storico senza grafi (+14,2% t/s) |
| FIX-1 | fix1_freerun | 14,99 (r2-r4, spread 9,39%) | .81078/.81862/.85649 (= rotto storico) | prompt eval r2-r4 = 4/4/4 token, checkpoint fine-prompt creato/ripristinato — PASSATO | **PROMOSSO (meccanismo)** — qualita' invariata (atteso, colpa C3) |
| SONDA | adk_sonda | — | — | server `exit(1)` prima di `/health`: piano PORTCAL1 assente | **NESSUNA MISURA** — prerequisito mancante dal mandato |

**Verdetto per leva**:
- **C (fix cattura K=0)**: **CONFERMATO FUNZIONANTE**, pronto per l'adozione nel regime K=0. Prova
  diretta (`saltati in cattura`>0) + prova indiretta di correttezza (traiettoria bit-identica al
  riferimento senza grafi) + salute piena su 1200 token.
- **B (FIX-1, checkpoint fine-prompt)**: **meccanismo SI** (prompt eval 67-68 -> 4 token,
  verificato nel log, non dedotto), **qualita' NO** (p1/traiettoria identiche al free-run rotto,
  colpa isolata ieri su C3 = checkpoint `PARTIAL_ONLY` che non copre l'anello caldo DSV4 — fuori
  mandato di oggi).
- **A (sonda adaptive-K)**: **NON VALUTABILE in questo turno** — manca un piano PORTCAL1 costruito
  per il carico odierno; nessuna conclusione tratta sul merito della leva stessa.

**Stato macchina a fine sessione**: 0 processi llama, VRAM 305 MiB (= preflight), RAM libera 88,5
GB (da 88,4 di preflight — nessuna perdita su 4 bracci + 1 fallimento controllato). Chiusura pulita
su 3/4 bracci (`ctrl-c`); il quarto (`adk_sonda`) e' uscito da solo con `exit(1)` per un cancello
di leva applicativo, senza lasciare residui. QUIETE a tempo abolita su indicazione del coordinatore
a meta' sessione: verifica "macchina pulita" (processi=0, VRAM~riposo) applicata invece fra tutte e
quattro le transizioni. NESSUN commit eseguito.

Percorsi completi di tutti gli artefatti (server.log/server.out/summary.json/r*.output.txt/
r*.response.json/hw.csv/cpu.csv) in
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\` con tag
`v0_k2_subtract`, `v1_k0_subtract`, `fix1_freerun`, `adk_sonda`.

---

## MANDATO SUPPLEMENTARE — costruzione piano PORTCAL1 dedicato e rilancio SONDA

Decisione del coordinatore dopo il blocco `adk_sonda` (nessun piano compatibile col carico
odierno): costruire un piano PORTCAL1 dedicato a B1200/warm-restore/K=2/nmax3, NIENTE
`STRICT=0` (spegnerebbe la leva). **Ultimo mandato del turno** (budget di rotazione a fine
corsa).

### 1) Provenienza del generatore — verificata, non riscritta

Generatore trovato: `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\
work\analyze_route_trace.py`. Formato **non ambiguo**: le struct Python (`HEADER="<8s7I"`,
`RECORD="<IhBBBBH6h6B6B4x6f"` = 64 byte, `PLAN_HEADER="<8s6I"`, `PLAN_CYCLE="<III"` = 12 byte,
`PLAN_ENTRY="<HHIhh"` = 12 byte) combaciano byte per byte con le struct C verificate sul codice:
`static_assert(sizeof(cache_esperti_traccia_record) == 64)` (`cache-esperti.cuh:1774` regione),
`static_assert(sizeof(cache_cal_cycle) == 12)` / `sizeof(cache_cal_voce) == 12`
(`cache-esperti.cu:77-78`). Nessun nuovo generatore scritto.

**Scoperta corretta rispetto all'assunto implicito**: la campagna del 15/8 (piano
`macro_v2_..._tail77_q8_drain...portcal`) usava `--lane k0` perché il suo carico era
B160/`CALENDARIO_K0=1`/`SLOT_DIRETTI=1`. Per il regime di oggi (`CALENDARIO_K0=0`, K=2 reale) la
lane corretta e' **`--lane trace`** (il default dello script): usa il `k_cpu` realmente osservato
nella trace, non "tutto GPU". Usare `k0` avrebbe misurato la sonda su un piano costruito per un
regime diverso da quello richiesto.

**Due variabili distinte, verificate sul codice** (non assunte dal nome):
- `LLAMA_CACHE_ESPERTI_TRACCIA=<path>` — **REGISTRA** una trace nuova (`cache-esperti.cu:2181-
  2196` alloca il buffer device da 200.000 record; `:6805-6823` la scrive su disco nel dump,
  quindi **richiede chiusura pulita** per essere salvata).
- `LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=<path>` — **CARICA** una trace esistente per il replay/
  rilevatore di divergenza (`cache_calendario_carica`, `:1048-1134`); precondizione di
  `LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO` (`cache_calendario_trasporto_carica` verifica
  `runtime->cache.calendario` a `:1137`, cioè il piano non si carica se la trace non si e' gia'
  caricata con successo).

### 2) Braccio TRACCIA (`adk_trace_capture`) — servizio, fuori genealogia

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'adk_trace_capture' -MaxTokens 1200
  -Repetitions 1 -PortoHotSnapshot $true -SpecNmax 3
  -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra '<base>;PORTO_HOT_MASK=15;
  LLAMA_CACHE_ESPERTI_TRACCIA=D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc'
```

**Scelta -Repetitions 1, non 4** (deviazione motivata dal mandato "config IDENTICA alla sonda"):
il buffer trace ha capacita' FISSA di 200.000 record per l'intero processo, non per richiesta.
Con warm-restore le repliche sono bit-identiche (dimostrato oggi su V0 e nello storico
`warm_anchor_restore`), quindi 1 sola richiesta (r1=cattura) e' un campione equivalente a 4 per
lo scopo, **e** evita il rischio concreto di overflow (stima ~4× la capacita' con 4 richieste da
1200 token, dato il consuntivo reale sotto).

**Risultato**: completata, 1200 token, `finish_reason=length`, chiusura `ctrl-c` (necessaria per
salvare la trace). **Nota onesta**: la sola presenza di `LLAMA_CACHE_ESPERTI_TRACCIA` ha
perturbato la traiettoria rispetto a V0 — p1 0.89858 (contro 0.90281 di V0) e SHA output diverso
(`49668E37...C9464D`) — come il coordinatore aveva anticipato ("la traccia puo' perturbare il
t/s: e' un braccio di SERVIZIO, fuori genealogia").

```text
eval t/s = 15,90   p1 = 0.89858   wall_ms = 79467
riga di salvataggio = cache-esperti: traccia route salvata 27778/27778 record in
  D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc          <- NESSUNA TRONCATURA (n=totale)
file trace = D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc, 1.777.828 byte
  (= header 36 + 27778 record x 64 byte, verificato aritmeticamente)
SHA256 file = 8B325ADE551DAA3999A2E177D522BD8977268725AE86C4BEC78AFD4CDC85C5EA
0 CUDA error / GGML_ASSERT, macchina pulita dopo (0 processi, VRAM 306 MiB)
```

percorsi file: `...\work\runs\adk_trace_capture.*`, `D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_
20260817.cestrc`

### 3) Costruzione del piano — riuscita, zero errori

```text
comando = python analyze_route_trace.py D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc
  --lane trace --copy-quanta 8
  --emit-layer-plan D:\ds4_work\adk\adk_piano_b1200_k2_nmax3_20260817.portcal
```

`--copy-quanta 8` allineato a `FORK_BLOCCHI`/`CALENDARIO_BLOCCHI=8` di oggi (fb8, il vincitore
dello sweep di stamattina). Nessun `--tail-cycles` (unica richiesta gia' pulita), nessun
`--drain-cycle` (specifico del replay diretto-slot/`SLOT_DIRETTI`, spento nel nostro regime).

**Nessun `rescue_keys != 0` sollevato dallo script** (il generatore fallisce esplicitamente se il
piano non riesce a coprire la domanda con la capacita' data — non e' successo):

```text
meta={'version': 2, 'records': 27778, ..., 'slots': 473, 'experts': 256}
cycles=279 layers_per_cycle={43: 279}
cycle_working_set: mean=253.32 p95=328.4 max=365            <- sempre sotto 473 (capacita')
layer_plan_written=...adk_piano_b1200_k2_nmax3_20260817.portcal lane=trace quanta=8
  cycles=279 entries=33106 max_cycle_entries=473 max_release_entries=473 bytes=400652
```

File verificato aritmeticamente contro il parser C++ (`cache-esperti.cu:1147-1180`): header
32 byte + 279×12 (cicli) + 33106×12 (voci) = 400.652 byte — combacia esattamente. `h[2]`
(capacity)=473 = `n_slot` runtime; `h[4]`/`h[5]` (12/12) = `sizeof(cache_cal_cycle)`/
`sizeof(cache_cal_voce)`. Tutti i vincoli del parser rispettati per costruzione.

percorso file: `D:\ds4_work\adk\adk_piano_b1200_k2_nmax3_20260817.portcal` (400.652 byte)

### 4) SONDA finale (`adk_sonda_piano`) — piano CARICATO con successo, meccanismo osservato

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'adk_sonda_piano' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra '<base>;PORTO_HOT_MASK=15;
  LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc;
  LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_b1200_k2_nmax3_20260817.portcal;
  LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1'
```

**Differenza decisiva rispetto al tentativo precedente (`adk_sonda`, ABORTITO)**: il server ha
raggiunto `/health` e completato tutte e 4 le richieste. Manifesto: `cache-esperti: calendario
corsie ACCESO: 27778/27778 record, 279 cicli, fonte '...cestrc'` — trace caricata per intero.
Nessun `cache_leva_rifiutata`, nessun `exit(1)`.

| richiesta | ruolo | eval t/s | p1 | SHA output | content_chars |
|---|---|---:|---|---|---:|
| r1 | cattura | 15,76 | 0.88502 (762/861) | `3FBE4F0B54...28CBA6` | 3743 |
| r2 | verdetto | 16,03 | 0.88502 (762/861) | `3FBE4F0B54...28CBA6` | 3743 |
| r3 | verdetto | 15,84 | 0.88502 (762/861) | `3FBE4F0B54...28CBA6` | 3743 |
| r4 | verdetto | 15,79 | 0.88502 (762/861) | `3FBE4F0B54...28CBA6` | 3743 |

```text
valori ordinati (r2,r3,r4) : 15,79 / 15,84 / 16,03
MEDIANA                    : 15,84
spread max-min              : 1,52 %

vs V0 (17,06)  : delta = -7,15 %   FUORI banda ±3% (vedi lettura sotto — non isolato dal costo
                                    dell'apparato calendario+trace+piano+async)
```

**Cancello con-restore: PASSATO.** SHA/p1/content_chars **bit-identici su tutte e 4** le
richieste — il restore funziona correttamente anche con calendario+trace+piano+async+k_adattivo
tutti attivi insieme (nessuna divergenza fra cattura e ripristini).

**CANCELLO PRIMARIO (mandato): la riga "adaptive-K →", letta PRIMA del t/s — ANOMALIA
RISCONTRATA, non nascosta**:

```text
prima istantanea : ... rescue=2361 (20.1%), senza piano=9409 (79.9%)
ultima istantanea: non residenti valutati=261549, in tempo (classe 4)=0 (0.0%),
                    rescue = deadline miss=27541 (10.5%), senza piano=234008 (89.5%)
```

`senza piano` **non scende** dopo il primo ciclo come atteso dal mandato — sale (79,9% → 89,5%)
e si stabilizza li'. **Secondo segnale, piu' netto**: `in tempo (classe 4)=0 (0.0%)` su **ogni
singola istantanea** del dump, mentre `rescue` e' sempre positivo (10,5-20,1%) — cioe' ogni volta
che una deadline VIENE TROVATA nella tabella, e' **sempre** classificata rescue, **mai** in
tempo. Questo e' esattamente il sintomo descritto come segnale d'allarme in
`NOTE_IMPLEMENTAZIONE.md` §5 punto 5 ("dubbi aperti"): *"Un `scadenza` in unità diverse
renderebbe lo slack assurdo e la leva o sempre-rescue o mai-rescue: il primo sguardo va alla
riga di dump, non al t/s."* — qui e' **sempre-rescue**.

**Causa più probabile, verificata sul codice ma non isolata con un braccio dedicato** (fuori
budget di questo turno): il replay/rilevatore di divergenza si arma **solo se gli ID del primo
gruppo della richiesta corrente coincidono esattamente con quelli del primo gruppo della trace
registrata** (`cache-esperti.cu:5638-5674`, commento esplicito: *"Il calendario non si arma sul
prompt/warm-up: aspetta che layer, taglia e tutti gli id coincidano col primo gruppo della
reference"*). Confermato sul log: `cache-esperti: calendario corsie -> posizione=0/27778,
stato=0, ...` **resta fisso a zero per tutta la corsa** (mai armato). La trace fu registrata in
un regime leggermente diverso (solo `TRACCIA` attiva, p1=0.89858) da quello della sonda finale
(calendario+piano+async+k_adattivo insieme, p1=0.88502) — le due traiettorie **divergono già dal
primo token generato**, quindi gli ID non possono mai coincidere. Il trasportatore persistente
(che popola `scadenza_ep` indipendentemente dal replay, `cache-esperti.cu:6013-6028`/`:6087-
6102`) segue comunque il proprio ciclo di rilascio, ma le chiavi che scrive non sempre
corrispondono a quelle richieste dalla sequenza reale — da cui l'89,5% "senza piano" e lo
sbilanciamento verso "sempre-rescue" quando una corrispondenza c'è. **Non dimostrato con un
esperimento che isoli la causa esatta** (richiederebbe una registrazione trace fatta con
l'apparato completo già attivo, o un piano costruito con margini di ETA diversi — entrambi fuori
mandato/budget di questo turno). Riportato come richiesto, senza trarre conclusioni ulteriori.

**Salute: piena.** 0 `GGML_ASSERT`/`CUDA error`, 0 `PERMUTAZIONE ROTTA` (guasto muto assente),
0 `CONTESA`, riga cache-esperti identica al riferimento, chiusura `ctrl-c` pulita.

**t/s -7,15% vs V0**: non attribuibile al solo `K_ADATTIVO` senza un braccio che isoli l'apparato
calendario+trace+piano+async da solo (a `K_ADATTIVO=0`) — non eseguito in questo turno. E' quindi
un dato, non un verdetto sul costo della leva in se'.

**Controllo di coerenza testuale** (r2, 3743 caratteri, letto per intero): italiano corretto,
HTML/CSS cyberpunk NeuraForge pertinente al prompt, tronco a meta' di una dichiarazione CSS per
esaurimento budget. Lingua sana=si, loop=no, pertinenza=si, degradazione=no.

**Telemetria** (`adk_sonda_piano.hw.csv`, 136 campioni/2s, 130 busy util>30%): SM mediano 1927 MHz
(nessun throttle) · potenza mediana 103,1 W.

**Postflight**: 0 processi llama, VRAM 306 MiB (= riposo), RAM libera 88,5 GB.

percorsi file: `...\work\runs\adk_sonda_piano.*`

### VERDETTO DEL MANDATO SUPPLEMENTARE

- **Meccanismo di caricamento del piano: FUNZIONANTE.** Trace e piano si costruiscono col
  generatore esistente, si caricano senza errori, il server gira in salute piena su 4 richieste
  con restore bit-identico.
- **Sonda A: raggiungibile ma ANOMALA, non "sana".** Il segnale "sempre-rescue, mai in-tempo" +
  "senza piano" che non scende sono entrambi i sintomi che il design doc stesso elenca come
  bandiera di un problema di fondo (disallineamento traccia/misura, o unità di `scadenza`), non
  una lettura pulita del merito della leva. **Non si può oggi promuovere né respingere
  `K_ADATTIVO` sul merito**: serve un braccio che chiuda il ciclo trace→piano→misura sulla
  STESSA traiettoria (es. registrare la trace già con calendario+async attivi, senza
  `K_ADATTIVO`, poi costruire il piano da quella) prima di leggere un verdetto di qualità/costo.
- **Nessuna variante tentata oltre questa** (niente `STRICT=0`, niente secondo piano, niente
  ri-registrazione) per rispetto del budget di fine rotazione dichiarato dal coordinatore.

Stato macchina a fine intero turno (bracci 1-4 + mandato supplementare): 0 processi llama, VRAM
306 MiB (= preflight 305 MiB), RAM libera 88,5 GB (da 88,4 di preflight — nessuna perdita su 6
lanci del server). NESSUN commit eseguito.

Percorsi completi di tutti gli artefatti (server.log/server.out/summary.json/r*.output.txt/
r*.response.json/hw.csv/cpu.csv) in
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\` con tag
`v0_k2_subtract`, `v1_k0_subtract`, `fix1_freerun`, `adk_sonda`, `adk_trace_capture`,
`adk_sonda_piano`; trace e piano in `D:\ds4_work\adk\`.

---

# OTTAVO TURNO — S1/T2/piano v2/SONDA v2: isolare apparato da leva, MAI ARMATA anche col trace giusto

Esecutore: ottavo turno, contesto fresco. Mandato del coordinatore: quattro passi per separare il
prezzo dell'apparato (calendario+trace+piano+async) dal prezzo della leva K_ADATTIVO nella
`−7,15%` osservata dal turno precedente (`adk_sonda_piano`, 15,84 vs riferimento V0 17,06),
e verificare se una traccia registrata SOTTO l'apparato completo (invece che con sola TRACCIA)
permette finalmente al replay del calendario di armarsi.

**Nota di processo, dichiarata per trasparenza**: durante l'esecuzione mi sono erroneamente
convinto che il coordinatore avesse aggiunto a meta' sessione un quinto braccio (`MASSA_CORSIE`,
leva preesistente scoperta per caso durante la lettura del codice). Non e' mai stato chiesto nel
mandato reale. Ho scritto uno script per quel braccio ma **non l'ho mai eseguito** (nessuna corsa,
nessun consumo di tempo macchina, nessun dato prodotto) — l'errore e' stato individuato e corretto
prima del lancio. Non compare nei risultati sotto perche' non fa parte del mandato.

## Preflight

```text
data/ora        = 2026-08-17 09:2x (poco prima dell'avvio di S1)
uptime_min      = 3417,9 (nessun riavvio dal turno precedente)
processi llama  = 0
porta 8000 (UI) = nessun listener (non toccata)
porta 8099/8100 = libere
nvidia-smi      = NVIDIA GeForce RTX 3060, sm=210MHz, mem=405MHz, power=12.58W, used=306MiB,
                  free=11810MiB, pcie_gen=1 (a riposo), pcie_width=16, throttle=0x1
ram_libera_gb   = 88.2 GB
disco_c_gb      = 49.3 GB liberi     disco_d_gb = 119.7 GB liberi
sha_llama_server= 8E98393EB0225C05A5CE19AF1A02BB6D6112D6B69C2DC901B22F43465B7FB1CD  -- combacia col mandato
sha_ggml_cuda   = 1E2037EDAB78CB9C09D4503C9913A9357C4B713AED3D37C9A4118768A04D4177  -- combacia col mandato
sha_llama_impl  = 91FF17F0F64B6771A61A5545CEF3ECAE10172A0ACEA3F2D48CBD11596F2AEA29  -- combacia col mandato
sha_jprompt     = C2D18E35A0B933F68B1CDAB9CAD905776AD59399B7E916D8A4DF1ED56A9090A9 (252 byte) -- PASSATO
build           = build 10093 (3014d3756)
```

Tutti i cancelli 1.1-1.8 PASSATI. Riferimento V0 = **17,06** letto da `v0_k2_subtract.server.log`
(turno precedente, stesso SHA binario, stesso uptime ininterrotto: non rimisurato, §8.5 non lo
impone in assenza di riavvio/cambio binario/>3h/>3 bracci).

Verifica lettori PRIMA di lanciare (grep mirato su `D:\llama-subtract\ggml\src\ggml-cuda\cache-esperti.cu`,
non assunto dal nome):
- righe 5638-5674: l'aggancio del replay (`calendario_usa`) confronta `c.calendario`, popolato
  **solo** da `LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE` — mai da `CALENDARIO_PIANO`.
- righe 5752-5759: quando armato, `chiave[i] = piano.stati[i]` legge anch'essa da `c.calendario`
  (cioe' da CALENDARIO_TRACE), incondizionata da `LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI`.
- riga 5836: il blocco contatori 49-53 di K_ADATTIVO (`k_ad_valutati/in_tempo/rescue/senza_piano`)
  e' dietro `if (c.k_adattivo && c.scadenza_ep && c.eta_pub && attiva)` — indipendente da
  `calendario_usa`: e' un meccanismo separato che legge `scadenza_ep` (da CALENDARIO_PIANO).
- riga 5860: `if (c.k_adattivo >= 2) chiave[i] = 4;` — **a livello 1 (sonda) la leva conta e non
  tocca mai `chiave[]`**, conferma testuale di NOTE_IMPLEMENTAZIONE.md.
- riga 2206: `if (runtime->cache.k_adattivo && !runtime->cache.scadenza_ep)` — a `K_ADATTIVO=0`
  questo corto-circuita, nessun rifiuto, nessun effetto collaterale.

---

## Passo 1/4 — S1 (`adk_s1_apparato`) — prezzo del solo apparato

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'adk_s1_apparato' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;
  LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc;
  LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_b1200_k2_nmax3_20260817.portcal;
  LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_K_ADATTIVO=0'
protocollo = warm-restore (1 processo, cattura r1 fuori verdetto, mediana r2-r4)
telemetria = work\sample_hw.ps1 -Tag adk_s1_apparato -OutDir <runs> -IntervalSeconds 2
```

| richiesta | ruolo | eval t/s | p1 | SHA output | content_chars | prompt tok |
|---|---|---:|---|---|---:|---:|
| r1 | cattura | 16,19 | 0.88502 | `3FBE4F0B54...28CBA6` | 3743 | 68 |
| r2 | verdetto | 16,45 | 0.88502 | `3FBE4F0B54...28CBA6` | 3743 | 4 |
| r3 | verdetto | 16,46 | 0.88502 | `3FBE4F0B54...28CBA6` | 3743 | 4 |
| r4 | verdetto | 16,43 | 0.88502 | `3FBE4F0B54...28CBA6` | 3743 | 4 |

```text
valori ordinati (r2,r3,r4) : 16,43 / 16,45 / 16,46
MEDIANA                    : 16,45          spread max-min : 0,18 %
vs V0 (17,06)               : delta = -3,58 %   FUORI banda ±3% (di poco)
```

**Righe testimone (verbatim)**:

```text
cache-esperti: 473 slot da 6.75 MiB = 3194 MiB in VRAM (gate 2.06 + up 2.06 + down 2.62), cura=0,
  spin=256, filtro=0, coda_max=0, lru=1, massa=2, peso_copia_pm=0, copie_min=1, cpu_leggeri=0,
  scudo=0, sfratto_par=1, dma=0, dma_strato=0                       <- identica al riferimento V0
manifesto: GGML_CUDA_DISABLE_GRAPHS=<spento>(D)                     <- grafi ACCESI
adaptive-K -> : ASSENTE (0 occorrenze nel log)                      <- atteso, K_ADATTIVO=0 (il
                                                                        dump e' dietro `if (k_adattivo)`)
cache-esperti: calendario corsie -> posizione=0/27778, stato=0, divergenze=0, gruppi=0,
  domanda-allineata hit=0 miss=0                                    <- presente 8 volte, MAI cambia
cache-esperti: domanda 1144316 (colpi 794444 = 69.4%, buchi 349872, miss 30.6%, in ritardo
  0 = 0.0% dei prenotati)                                           <- totale finale (ultima riga)
righe sched-profilo = 0        GGML_CUDA_GRAPH_STATS=0(D)
0 GGML_ASSERT / CUDA error / divergenze / CONTESA / MORTO           shutdown = ctrl-c
```

**Cancelli**: riga cache-esperti identica -- PASSATO. `sfratto_par=1` -- PASSATO. Grafi accesi --
PASSATO. `sched-profilo`=0 su entrambi i lati (anche V0 aveva 0) -- PASSATO.
`GGML_CUDA_GRAPH_STATS` spento -- PASSATO. p1 identico sulle 4 richieste (con-restore, cancello
§8.9.5) -- PASSATO. Zero errori/divergenze/CONTESA -- PASSATO. Nessuna riga "adaptive-K" (leva
spenta per costruzione) -- PASSATO.

**Controllo di coerenza testuale** (r2, 3743 caratteri, stesso SHA su tutte e 4 le richieste = lo
stesso testo gia' letto e giudicato dal turno precedente per `adk_sonda_piano`): lingua sana=si,
loop/ripetizioni=no, pertinenza=si, degradazione=no (tronco a meta' di una dichiarazione CSS per
esaurimento budget, atteso).

**Telemetria** (`adk_s1_apparato.hw.csv`, 186 campioni/2s, 130 con util>30%): SM mediano 1927 MHz
(min 210 a riposo, max 1942, nessun throttle) · potenza mediana 104,71 W · VRAM picco 11875 MiB,
media 10597,8 MiB · CPU% media 44,2%.

**ESITO: DIAGNOSTICO (di riferimento per i passi successivi).** Isola il costo del solo apparato
(calendario+trace+piano v1+async, blocco contatori 49-53 mai eseguito perche' `k_adattivo=0`
corto-circuita la guardia di riga 5836): **-3,58% vs V0**, circa meta' della `-7,15%` originale.

percorsi file: `...\work\runs\adk_s1_apparato.*`

---

## Passo 2/4 — T2 (`adk_trace_v2`) — traccia a punto fisso sotto l'apparato acceso

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'adk_trace_v2' -MaxTokens 1200 -Repetitions 1
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;
  LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_b1200_k2_nmax3_20260817.cestrc;
  LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_b1200_k2_nmax3_20260817.portcal;
  LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1;
  LLAMA_CACHE_ESPERTI_TRACCIA=D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc'
protocollo = warm-restore, 1 sola richiesta (cattura) -- stessa scelta motivata dal turno
  precedente per `adk_trace_capture`: buffer trace a capacita' FISSA (200.000 record/processo),
  1 richiesta basta con repliche bit-identiche e evita il rischio di overflow.
```

**Config = sonda COMPLETA del turno 7 (K_ADATTIVO=1, piano v1 caricato, ASYNC=1) + `TRACCIA`
attiva**: la traiettoria registrata e' quella dell'apparato ACCESO, non quella "sola TRACCIA" del
turno precedente.

```text
r1 (unica) : eval 16,24 t/s   wall 77323,5 ms   p1 0.88502 (IDENTICO a S1)
             SHA output = 3FBE4F0B544C27EA0CEA100E3FEDD5284DBC3641C93A6167D2045D463928CBA6
             (IDENTICO a S1: la sola registrazione TRACCIA, sopra all'apparato gia' attivo, non
             perturba oltre -- diverso dal precedente isolato "sola TRACCIA senza calendario" del
             turno 7 che invece spostava p1 da .90281 a .89858)
             content_chars = 3743   prompt_tokens = 68   completion_tokens = 1200
vs V0 (17,06) : delta = -4,81 %   (informativo: 1 sola richiesta, "fuori genealogia" per
                                    costruzione, come dichiarato dal mandato)
```

**Righe testimone (verbatim)**:

```text
cache-esperti: traccia route ACCESA: D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc
  (200000 record)
cache-esperti: traccia route salvata 8041/8041 -> 23236/23236 -> 25241/25241 record (tre dump
  intermedi durante la stessa richiesta; il valore e' CUMULATIVO, l'ultimo e' il totale)
cache-esperti: adaptive-K -> leva=1, copia=1177 us, strato=3100 us | non residenti valutati=65967,
  in tempo (classe 4)=0 (0.0%), rescue = deadline miss=7171 (10.9%), senza piano=58796 (89.1%)
                                                                     <- ultima istantanea di T2
cache-esperti: calendario corsie -> posizione=0/27778, stato=0, ...  <- MAI cambia, come nel
                                                                        turno precedente
cache-esperti: domanda 286724 (colpi 199256 = 69.5%, buchi 87468, miss 30.5%, in ritardo 0 = 0.0%)
righe sched-profilo = 0        grafi ACCESI        0 errori         shutdown = ctrl-c
```

**Verifica aritmetica del file salvato** (obbligatoria prima di fidarsi del trace):
`D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc` = 1.615.460 byte;
(1.615.460 - 36) / 64 = **25.241,0 esatto** -- combacia col totale dell'ultimo dump, nessuna
troncatura.

**Cancelli**: riga cache-esperti identica -- PASSATO. Trace salvata senza troncamento (verifica
aritmetica sopra) -- PASSATO. p1/SHA identici a S1 (stesso apparato, TRACCIA in piu' non
perturba) -- coerente, non un cancello del mandato ma un'utile controprova. 0 errori -- PASSATO.

**Controllo di coerenza testuale**: SHA identico a S1, gia' letto e giudicato sano sopra.

**ESITO: SERVIZIO (fuori genealogia, come dichiarato dal mandato).** Traccia salvata su disco,
identita' SHA/p1 = `3FBE4F0B54...28CBA6` / `0.88502` registrata come riferimento per il cancello
(d) del passo 4.

percorsi file: `...\work\runs\adk_trace_v2.*`,
`D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc`

---

## Passo 3/4 — Piano v2 — costruito dal trace v2, zero errori

```text
comando = python analyze_route_trace.py D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc
  --lane trace --copy-quanta 8
  --emit-layer-plan D:\ds4_work\adk\adk_piano_v2_b1200_k2_nmax3_20260817.portcal
```

`--copy-quanta 8` allineato a `CALENDARIO_BLOCCHI=8` (invariato dal turno precedente). `--lane
trace` (non `k0`): il nostro regime e' `CALENDARIO_K0=0`, K=2 reale.

```text
meta={'version': 2, 'records': 25241, ...}                    <- combacia col trace su disco
cycles=261   layers_per_cycle={43: 261}
cycle_working_set: mean=250.23 p95=315.0 max=380              <- sempre sotto la capacita' (473)
layer_plan_written=...adk_piano_v2_b1200_k2_nmax3_20260817.portcal lane=trace quanta=8
  cycles=261 entries=30378 max_cycle_entries=473 max_release_entries=473 bytes=367700
  dropped_last=0 rescue_burst=0                                <- nessun rifiuto, equivalente al
                                                                    "rescue_keys>0" del collaudo:
                                                                    non sollevato
exit code = 0
```

Verifica aritmetica contro il parser C++: header 32 + 261×12 (cicli) + 30.378×12 (voci) =
**367.700 byte** -- combacia esattamente col file su disco.

percorso file: `D:\ds4_work\adk\adk_piano_v2_b1200_k2_nmax3_20260817.portcal` (367.700 byte)

---

## Passo 4/4 — SONDA v2 (`adk_sonda_v2`) — MAI ARMATA, nemmeno col trace ricostruito

**DEVIAZIONE [S] dalla lettera del mandato, dichiarata e motivata sul codice** (non assunta dal
nome): il mandato dice "identica a T2 ma piano v2 al posto del v1". Letta alla lettera, questa
frase cambierebbe solo `CALENDARIO_PIANO`, lasciando `CALENDARIO_TRACE=v1`. Verificato pero' sul
codice (vedi "Verifica lettori" sopra, righe 5638-5674 e 5752-5759) che sia l'aggancio del replay
sia la riscrittura di `chiave[]` quando armato leggono **entrambi** da `c.calendario`, popolato
**solo** da `CALENDARIO_TRACE` — `CALENDARIO_PIANO` non entra mai in quel confronto (serve solo a
`scadenza_ep`). Tenere `CALENDARIO_TRACE=v1` avrebbe quindi garantito la stessa non-armatura gia'
vista 3 volte (turno 7, S1, T2), rendendo inutile il passo 3 per il cancello (a). Interpretato
percio' "piano v2" come il **pacchetto** trace+piano v2 (come lo chiama lo stesso preambolo del
mandato, sempre in coppia: "trace+piano v1"/"trace+piano v2") — `CALENDARIO_TRACE` **e**
`CALENDARIO_PIANO` sono passati **entrambi** a v2. Se l'intenzione del coordinatore era diversa,
il braccio va rifatto con `CALENDARIO_TRACE` fermo su v1: e' un'ora di macchina, non di piu'.

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'adk_sonda_v2' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;
  LLAMA_CACHE_ESPERTI_CALENDARIO_TRACE=D:\ds4_work\adk\adk_trace_v2_b1200_k2_nmax3_20260817.cestrc;
  LLAMA_CACHE_ESPERTI_CALENDARIO_PIANO=D:\ds4_work\adk\adk_piano_v2_b1200_k2_nmax3_20260817.portcal;
  LLAMA_CACHE_ESPERTI_CALENDARIO_ASYNC=1;LLAMA_CACHE_ESPERTI_K_ADATTIVO=1'
protocollo = warm-restore, identico a T2 salvo: niente TRACCIA (non serve piu' registrare)
```

| richiesta | ruolo | eval t/s | p1 | SHA output | content_chars |
|---|---|---:|---|---|---:|
| r1 | cattura | 16,15 | 0.86845 | `023703BF98...5FDE2FF6B` | 3504 |
| r2 | verdetto | 16,21 | 0.86845 | `023703BF98...5FDE2FF6B` | 3504 |
| r3 | verdetto | 16,17 | 0.86845 | `023703BF98...5FDE2FF6B` | 3504 |
| r4 | verdetto | 16,19 | 0.86845 | `023703BF98...5FDE2FF6B` | 3504 |

```text
valori ordinati (r2,r3,r4) : 16,17 / 16,19 / 16,21
MEDIANA                    : 16,19          spread max-min : 0,25 %
vs S1 (16,45) : delta = -1,58 %   DENTRO banda ±3%: NON DISTINGUE dalla deriva di banco
vs V0 (17,06) : delta = -5,10 %   FUORI banda ±3%
```

**Righe testimone (verbatim)**:

```text
cache-esperti: 473 slot da 6.75 MiB = ... sfratto_par=1, ...          <- identica al riferimento
manifesto: GGML_CUDA_DISABLE_GRAPHS=<spento>(D)                       <- grafi ACCESI
cache-esperti: calendario corsie -> posizione=0/25241, stato=0, divergenze=0, gruppi=0,
  domanda-allineata hit=0 miss=0                       <- denominatore ORA 25241 (= trace v2,
                                                            conferma che il file giusto e' stato
                                                            caricato) ma posizione=0/stato=0 su
                                                            TUTTE le 8 istantanee della corsa:
                                                            MAI SI ARMA, invariato rispetto a
                                                            S1/T2/turno 7
cache-esperti: adaptive-K -> leva=1, copia=1177 us, strato=3100 us | non residenti valutati=294022,
  in tempo (classe 4)=0 (0.0%), rescue = deadline miss=30710 (10.4%), senza piano=263312 (89.6%)
                                                                        <- ultima istantanea
cache-esperti: domanda 1123676 (colpi 797140 = 70.9%, buchi 326536, miss 29.1%, in ritardo 0=0.0%)
righe sched-profilo = 0        0 errori/divergenze/CONTESA/MORTO      shutdown = ctrl-c
```

**Serie "senza piano" e "in tempo (classe 4)" sulle 8 istantanee della corsa** (crescente, mai in
calo; classe 4 sempre zero):

```text
senza piano %   : 85.7 -> 89.2 -> 88.8 -> 89.1 -> 89.3 -> 89.1 -> 89.5 -> 89.6
in tempo (cl.4) : 0.0  -> 0.0  -> 0.0  -> 0.0  -> 0.0  -> 0.0  -> 0.0  -> 0.0    (sempre zero)
rescue %        : 14.3 -> 10.8 -> 11.2 -> 10.9 -> 10.7 -> 10.9 -> 10.5 -> 10.4  (sempre positivo)
```

**CANCELLI, in ordine (dal mandato)**:

```text
(a) il replay SI ARMA (posizione avanza, stato cambia)              FALLITO
    posizione=0/25241, stato=0 su TUTTE le 8 istantanee, su tutte e 4 le richieste. Nemmeno con
    un trace registrato SOTTO l'apparato completo il replay si arma.

(b) "senza piano" basso o in calo dopo il primo ciclo                FALLITO
    Sale 85,7% -> 89,x%, si stabilizza alto, non scende mai sotto il valore iniziale.

(c) "in tempo (classe 4)" > 0                                        FALLITO
    Resta 0 (0,0%) su OGNI istantanea, da 21.149 (S1, escluso qui) / 27.162 valutati (prima
    istantanea di questa corsa) fino a 294.022 (ultima). Nota metodologica IMPORTANTE: questo
    contatore e' popolato dal blocco K_ADATTIVO (cache-esperti.cu:5836-5866, guardia
    `c.k_adattivo && c.scadenza_ep`), che legge `scadenza_ep` da CALENDARIO_PIANO ed E'
    INDIPENDENTE da `calendario_usa`/dall'armamento del replay (meccanismo diverso, righe
    5638-5674/5752-5759). E' quindi un test valido ANCHE SE (a) e' fallito: col piano v2,
    costruito dalla traiettoria "giusta", il pattern "sempre rescue, mai in tempo" e' IDENTICO
    al piano v1 del turno precedente. Per il mandato: "se resta 0 = unita' di scadenza sbagliata:
    riporta e fermati" -- riportato qui, nessuna variante ulteriore tentata.

(d) SHA/p1 IDENTICI al passo 2 (T2)                                   FALLITO
    p1 0.86845 (sonda v2) contro 0.88502 (T2); SHA diverso (`023703BF98...` contro
    `3FBE4F0B54...`). Attribuzione onesta, non forzata: dato che (a) e' fallito, `calendario_usa`
    non e' MAI stato 1 in questa corsa (verificato: stato=0 su tutte le istantanee), quindi la
    riscrittura `chiave[i]=piano.stati[i]` (righe 5752-5759) non e' MAI stata eseguita -- la
    divergenza NON puo' venire da li'. La configurazione di SONDA v2 differisce pero' da T2 su
    TRE variabili insieme, non una sola: CALENDARIO_TRACE (v1->v2), CALENDARIO_PIANO (v1->v2), e
    TRACCIA (accesa in T2, spenta qui, per istruzione esplicita del mandato "TRACE spenta"). Il
    precedente empirico piu' vicino nel progetto (turno 7: la sola presenza di TRACCIA, senza
    calendario, sposta p1 da .90281 a .89858) rende il differenziale TRACCIA il sospetto piu'
    probabile per QUESTA divergenza specifica -- ma non e' stato isolato con un braccio dedicato
    in questo turno (richiederebbe una quinta corsa: T2 rifatta identica ma senza TRACCIA, fuori
    budget). Non e' quindi possibile distinguere con certezza una "fuga della sonda" genuina
    (indotta dal cambio trace/piano) da un effetto gia' noto e separato della strumentazione
    (TRACCIA stessa). Riportato come richiesto, senza forzare una conclusione che i dati non
    sostengono.

(e) t/s vs S1 = costo della leva sola; vs 17,06 = costo totale
    vs S1 (16,45): -1,58% -- DENTRO la banda di deriva 2-3% (RUNBOOK SS8.3): NON DISTINGUE.
    vs V0 (17,06): -5,10% -- FUORI banda.
```

**Salute: piena.** 0 `GGML_ASSERT`/`CUDA error`, 0 `PERMUTAZIONE ROTTA`, 0 `CONTESA`, riga
cache-esperti identica, `sched-profilo`=0, grafi accesi, chiusura `ctrl-c` pulita su tutte e 4 le
richieste, p1/SHA bit-identici sulle 4 richieste (cancello con-restore §8.9.5 PASSATO).

**Controllo di coerenza testuale** (r2, 3504 caratteri, testo NUOVO -- letto per intero: righe
1-129, inizio/centro/fine): HTML5 valido, CSS cyberpunk NeuraForge pertinente al prompt (variabili
colore, griglia di sfondo, hero con radial-gradient), tronco a meta' di una dichiarazione CSS per
esaurimento budget (stesso pattern di troncamento di tutte le corse di questo turno). Lingua
sana=si, loop/ripetizioni=no, pertinenza=si, degradazione=no.

**Telemetria** (`adk_sonda_v2.hw.csv`, 311 campioni/2s, 132 con util>30%): SM mediano 1935 MHz
(min 210, max 1950, nessun throttle) · potenza mediana 104,09 W · VRAM picco 11894 MiB · CPU%
media 33,6%.

**Postflight**: 0 processi llama, VRAM 306 MiB (= riposo), RAM libera 88,4 GB.

**ESITO: NON ARMATA.** Salute piena, misura valida come dato di costo (cancello e), ma il
meccanismo di replay/calendario resta inerte -- il costruire un trace+piano dalla traiettoria
"giusta" (apparato acceso) NON e' bastato a farlo armare.

percorsi file: `...\work\runs\adk_sonda_v2.*`

---

## VERDETTO FINALE — tabella dei 4 passi

| passo | tag | t/s (mediana) | p1 | vs V0 (17,06) | cancello specifico | esito |
|---|---|---:|---|---:|---|---|
| S1 | adk_s1_apparato | **16,45** (r2-r4, spread 0,18%) | 0.88502 costante | -3,58% | nessuna riga "adaptive-K" (leva spenta) -- PASSATO | **DIAGNOSTICO** — isola il costo del solo apparato |
| T2 | adk_trace_v2 | 16,24 (r1 unica) | 0.88502 | -4,81% (informativo) | trace salvata 25.241/25.241, verifica aritmetica esatta -- PASSATO | **SERVIZIO** — trace v2 su disco, riferimento d'identita' per (d) |
| piano v2 | (costruzione) | n/a | n/a | n/a | `dropped_last=0`, nessun rifiuto, aritmetica byte esatta -- PASSATO | **COSTRUITO** |
| SONDA v2 | adk_sonda_v2 | 16,19 (r2-r4, spread 0,25%) | 0.86845 | -5,10% | (a) posizione=0/25241 fisso -- **FALLITO** | **NON ARMATA** |

**Verdetto sonda: NON ARMATA.** Diagnosi: nessuna delle tre corse di questo turno (S1, T2, SONDA
v2) ha mai fatto avanzare `calendario_stato` oltre `posizione=0`, nemmeno quando il trace di
riferimento e' stato ricostruito appositamente dalla traiettoria "apparato acceso" (v2, 25.241
record, verificati byte per byte). Poiche' il fallimento persiste anche col trace piu' fedele
costruibile con lo strumento esistente, il sospetto si sposta dall'ipotesi del turno 7 ("la
traccia e' stata registrata in un regime diverso") verso: (i) il confronto del primo gruppo
(cache-esperti.cu:5638-5661: strato/riga/n_tok/k_cpu/**tutti** gli ids devono combaciare
ESATTAMENTE alla primissima chiamata utile — un solo id fuori posto a t=0 e la corsa non arma
mai, per costruzione, e non ci sono log che dicano DOVE fallisce il confronto), oppure (ii)
NOTE_IMPLEMENTAZIONE.md §5 punto 5 (formato di `scadenza` come indice di strato: mai validato dal
codice al caricamento del PORTCAL1) -- rinforzato dal fatto che il contatore "in tempo (classe
4)", che NON dipende dall'armamento del replay (meccanismo separato), resta a zero anche col
piano v2 costruito dalla traiettoria corretta: se fosse SOLO un problema di trace disallineata,
questo contatore (che non tocca `calendario_usa`) non avrebbe motivo di restare "sempre rescue,
mai in tempo" identico al piano v1. Nessuna delle due ipotesi isolata con un braccio dedicato in
questo turno (fuori budget): servirebbe (i) un log a livello del singolo confronto id-per-id alla
primissima chiamata, oppure (ii) un piano PORTCAL1 costruito con `scadenza` in un'altra unita' per
falsificare/confermare per esclusione.

**Attribuzione della `-7,15%` originale (turno 7: 15,84 vs 17,06)**:
- S1 isola il costo del **solo apparato** (calendario+trace+piano v1+async, `K_ADATTIVO=0`: il
  blocco contatori 49-53 e' compilato ma mai eseguito, riga 5836): **-3,58% vs V0** — circa la
  **meta'** della `-7,15%` originale.
- Il margine sonda-vs-apparato di oggi (SONDA v2 vs S1) e' **-1,58%**, dentro la banda di deriva
  2-3% di banco: **NON distingue da rumore** — a livello 1 (sonda) `K_ADATTIVO` conta e non
  decide (riga 5860: solo `>=2` scrive `chiave[]`), quindi non ci si aspettava un costo grande.
- **NESSUNA** delle configurazioni di questo turno riproduce l'esatta `-7,15%` del turno 7: il
  residuo (~2 punti percentuali fra il -5,10% di SONDA v2 e il -7,15% di allora) **non e'
  spiegato** dai quattro passi di oggi. Possibili cause non isolate: deriva di sessione (RUNBOOK
  §8.3, 2-3%), oppure una differenza reale fra piano v1 (279 cicli, costruito da una traccia
  "sola TRACCIA senza apparato") e piano v2 (261 cicli, costruito dalla traiettoria "apparato
  acceso") che nessun braccio di oggi isola direttamente — mancherebbe un braccio "S1 con piano
  v2 al posto di v1" per chiudere il confronto. Riportato come gap aperto, nessuna cifra forzata.

**Stato macchina a fine turno**: 0 processi llama, VRAM 306 MiB (= 305-306 di preflight), RAM
libera 88,4 GB (da 88,2 di preflight -- nessuna perdita su 3 lanci del server + 1 costruzione
piano). Chiusura pulita (`ctrl-c`) sui 3 lanci del server. NESSUNA quiete a tempo fra bracci
(verifica "macchina pulita" applicata fra tutte le transizioni, come da mandato). NESSUN commit
eseguito. Il braccio `MASSA_CORSIE` scritto per errore di processo (vedi nota a inizio sezione)
**non e' stato eseguito**.

Percorsi completi di tutti gli artefatti (server.log/server.out/summary.json/r*.output.txt/
r*.response.json/hw.csv/cpu.csv/telemetry_wait.log) in
`C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\runs\` con tag
`adk_s1_apparato`, `adk_trace_v2`, `adk_sonda_v2`; trace e piano in `D:\ds4_work\adk\`
(`adk_trace_v2_b1200_k2_nmax3_20260817.cestrc`, `adk_piano_v2_b1200_k2_nmax3_20260817.portcal`).

---

## Braccio supplementare — MASSA_CORSIE (`massa_corsie_b1`) — confermato dal coordinatore dopo il fatto

**Nota di processo.** Questo braccio era stato scritto (script pronto) durante la preparazione dei
quattro passi sopra, sulla base di una convinzione erronea di aver ricevuto un ordine del
coordinatore mentre S1 girava — non trovavo traccia di alcun messaggio simile nel mio contesto e
l'ho dichiarato esplicitamente come probabile errore, **senza eseguire lo script**. Il coordinatore
ha poi confermato ESPLICITAMENTE, in un messaggio successivo ricevuto per il canale normale, che
l'ordine era reale ("mandato via messaggio mentre S1 girava, consegna arrivata in forma anomala")
e ne ha richiesto l'esecuzione. Eseguito da quel punto in poi. Resta il fatto, riportato per
completezza, che non ho mai avuto modo di verificare in modo indipendente il contenuto del
presunto messaggio originale delle 09:2x — il braccio e' stato eseguito sulla base della conferma
esplicita ricevuta, non di un ricordo recuperato.

```text
comando = & '...\work\run_porto_hot.ps1' -Tag 'massa_corsie_b1' -MaxTokens 1200 -Repetitions 4
  -PortoHotSnapshot $true -SpecNmax 3 -ServerPath 'D:\llama-subtract\build\bin\llama-server.exe'
  -Extra 'GGML_SCHED_PROFILO=0;LLAMA_CACHE_ESPERTI_CALENDARIO_K0=0;
  LLAMA_CACHE_ESPERTI_CALENDARIO_SLOT_DIRETTI=0;LLAMA_CACHE_ESPERTI_CALENDARIO_BLOCCHI=8;
  LLAMA_DSV4_DECODE_GATE_UP_FUSO=0;LLAMA_DSV4_DECODE_EXPERT_REUSE=0;
  LLAMA_DSV4_DECODE_EXPERT_REUSE_ZERO_DST=0;PORTO_HOT_MASK=15;LLAMA_CACHE_ESPERTI_MASSA_CORSIE=1'
protocollo = config campione V0 pulita (apparato calendario/trace/piano/K_ADATTIVO SPENTO --
  nessuna di quelle variabili e' impostata) + warm-restore 4 richieste, mediana r2-r4
```

**Grep del lettore PRIMA del lancio** (`D:\llama-subtract\ggml\src\ggml-cuda\cache-esperti.cu`):
nome confermato `LLAMA_CACHE_ESPERTI_MASSA_CORSIE` (righe 1924/1930), lettura **a valore**
(`cache_env_intero`, non a presenza), riga di log testimone `cache-esperti: massa globale ACCESA:
... corsie=%d ...` (riga 2682-2687). **Scoperta prima del lancio**: il default nel codice-sorgente
e' 1, ma `run_porto_hot.ps1` (righe 47-48) lo forza esplicitamente a `'0'` insieme a
`MASSA_AMMISSIONE` — confermato anche sul log reale di V0 (`v0_k2_subtract.server.log`:
`corsie=0`). La leva e' quindi rimasta spenta in **ogni** braccio di questa sessione (V0, S1, T2,
SONDA v2 compresi) fino a questo momento: accenderla e' un test reale, non un no-op.

| richiesta | ruolo | eval t/s | p1 | SHA output | content_chars |
|---|---|---:|---|---|---:|
| r1 | cattura | 15,94 | 0.86449 | `5368487D8B...AAA837EA3` | 3602 |
| r2 | verdetto | 16,09 | 0.86449 | `5368487D8B...AAA837EA3` | 3602 |
| r3 | verdetto | 16,09 | 0.86449 | `5368487D8B...AAA837EA3` | 3602 |
| r4 | verdetto | 16,09 | 0.86449 | `5368487D8B...AAA837EA3` | 3602 |

```text
valori ordinati (r2,r3,r4) : 16,09 / 16,09 / 16,09
MEDIANA                    : 16,09          spread max-min : 0,00 %
vs V0 (17,06)               : delta = -5,69 %   FUORI banda ±3%, NEGATIVO
```

**Righe testimone (verbatim)**:

```text
cache-esperti: massa globale ACCESA: emivita=64 cicli, unita=4, floor=3, margine vittima=2,
  ammissione=0, corsie=1, domanda=tutti i 6 esperti route                <- corsie=1, RAGGIUNTA
cache-esperti: 473 slot da 6.75 MiB = ... sfratto_par=1, ...             <- identica al riferimento
manifesto: GGML_CUDA_DISABLE_GRAPHS=<spento>(D)                         <- grafi ACCESI
cache-esperti: domanda 1108329 (colpi 783925 = 70.7%, buchi 324404, miss 29.3%, in ritardo
  0 = 0.0% dei prenotati)                                                <- totale finale
cache-esperti: byte a domanda (stream calcolo) 2139.51 GiB, in prefetch (stream DMA) 0.00 GiB
                                                                           <- totale finale
cache-esperti: riusi dell'installato -> mai=269652 (83.3%), 1=32128 (9.9%), 2-3=15744 (4.9%),
  4+=6008 (1.9%) | installati=323532                                     <- totale finale
cache-esperti: prefetch prenotati 0, saltati 0, scartati 0, guasti 0     <- sempre, ogni istantanea
righe sched-profilo = 0        0 GGML_ASSERT/CUDA error/divergenze/CONTESA/MORTO
shutdown = ctrl-c
```

**CANCELLI (dal mandato del coordinatore)**:

```text
(a) raggiungibilita': corsie=1 nel log                                   PASSATO
    (altrimenti l'esito sarebbe da buttare -- non e' il caso qui)

(b) p1 in banda 2sigma [0.8825; 0.9231]                                  FALLITO
    p1 = 0.86449, SOTTO il limite inferiore (0.8825). Traiettoria spostata, non rumore di banco.

(c) colpi VRAM in salita vs V0 (71.0%)                                   FALLITO
    70.7% finale -- leggermente IN CALO, non in salita (differenza piccola, ~0,3 punti,
    ma nella direzione sbagliata).

(d) byte a domanda in calo vs V0 (2105,60 GiB)                           FALLITO
    2139,51 GiB finale -- in SALITA (+1,6%), non in calo. Coerente con buchi in salita
    (324.404 contro 319.263 di V0, stesso +1,6%).

(e) contatore "mai" in calo vs V0 (85,2%)                                PASSATO
    83,3% finale -- in calo di 1,9 punti percentuali. L'UNICO segnale nella direzione attesa:
    coerente con l'ipotesi del lettore (l'ordinamento per merito dentro ogni classe di residenza
    tiene gli esperti piu' spesso riusati in GPU e manda alla CPU quelli di massa minore prima).

(f) guasti=0 e coerenza testo letta                                      PARZIALE
    guasti=0 -- PASSATO (sempre zero, ogni istantanea). Testo letto per intero (r2, 3602
    caratteri, 113 righe): italiano corretto in apertura, HTML/CSS cyberpunk NeuraForge
    pertinente -- MA un DIFETTO isolato trovato: il blocco `.logo span { color: #ff00ff;`
    (riga 94-95) non si chiude mai con `}` prima che inizi `.nav-links {` (riga 96) --
    una graffa CSS mancante, non presente negli altri tre bracci di oggi (S1/T2/SONDA v2, testo
    sempre ben formato). Isolato, non un loop/ripetizione patologica, non gibberish -- ma e'
    un'anomalia da riportare per RUNBOOK SS4.10 ("qualunque anomalia -> il braccio e' fermato e
    riportato, anche con tutti i contatori verdi"). Lingua sana=si, loop=no, pertinenza=si,
    degradazione=si (un difetto strutturale isolato nel CSS, non progressivo).
```

**Telemetria** (`massa_corsie_b1.hw.csv`, 183 campioni/2s, 134 con util>30%): SM mediano 1935 MHz
(min 210, max 1950, nessun throttle) · potenza mediana 101,51 W · VRAM picco 11898 MiB, media
10749,2 MiB · CPU% media 46,4%.

**Postflight**: 0 processi llama, VRAM 306 MiB (= riposo), RAM libera 88,4 GB.

**VERDETTO**: mediana **16,09** vs riferimento 17,06 = **-5,69%**, fuori banda e negativo. Non
"sopra +3%" (anzi, chiaramente negativo): niente B×3 + braccio A, per istruzione esplicita del
coordinatore va a **PARCHEGGIO con un solo braccio speso**. Su 6 cancelli: 2 passati (a, f-parziale
su guasti), 1 passato con segnale reale ma piccolo (e), 3 falliti (b, c, d, f-testo). Raggiungibile
e sano nei contatori duri (zero crash/assert), ma la leva **non porta il beneficio atteso** in
questa configurazione: sposta la traiettoria (p1 fuori banda) senza migliorare ne' i colpi ne' i
byte a domanda, con un solo segnale positivo isolato (contatore "mai", -1,9pp) che non compensa il
costo di velocita' (-5,69%) ne' il piccolo difetto testuale trovato.

**ESITO: PARCHEGGIO.** Aggiunta alla tabella §8.8 del runbook:

| leva | risultato B (1 replica, mediana r2-r4) | note |
|---|---:|---|
| `MASSA_CORSIE` | -5,69% (16,09 vs 17,06) | raggiunta (corsie=1), p1 fuori banda 2σ, colpi e byte-a-domanda nella direzione sbagliata, unico segnale positivo sul contatore "mai" (-1,9pp); difetto CSS isolato nel testo (graffa mancante) |

percorsi file: `...\work\runs\massa_corsie_b1.*`

Stato macchina dopo questo braccio: 0 processi llama, VRAM 306 MiB (= preflight), RAM libera 88,4
GB (invariata dal preflight su 4 lanci del server totali in questo turno). Chiusura pulita
(`ctrl-c`). NESSUN commit eseguito.

**Fine turno (budget di rotazione esaurito, dichiarato dal coordinatore).** Riepilogo consegne:
quattro passi del mandato originale (S1/T2/piano-v2/SONDA-v2) completi con verdetto "non armata"
diagnosticato; braccio supplementare MASSA_CORSIE completo con verdetto PARCHEGGIO. Cinque lanci
del server llama in tutto il turno, tutti con chiusura pulita, zero perdite di RAM/VRAM, zero
commit.
