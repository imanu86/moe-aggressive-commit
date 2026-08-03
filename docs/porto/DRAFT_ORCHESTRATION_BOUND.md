# Il draft è orchestration-bound: 6,8 GB spostati, costo invariato

3 agosto 2026, mattina. Chiude la domanda «un modello da 6,8 GB su una 3060
non può costare un secondo — sistema la configurazione».

La configurazione **era** rotta. L'ho sistemata. Non è bastato, e ora sappiamo
perché.

## Cosa era rotto davvero

La sonda `-lv 10` sulla configurazione speculativa:

```
bersaglio (22 strati) su CUDA0    3.905 MiB    grafo 34.066 nodi
compute buffer del bersaglio      1.276 MiB
DRAFT su CUDA0                    6.831 MiB    grafo  2.074 nodi
compute buffer del draft             33 MiB
VRAM: dedicata 11.935  CONDIVISA 1.233 MiB      <- traboccava
```

Due difetti veri:

1. **Si traboccava di 1,2 GB in memoria condivisa.** La causa a monte sta in
   `server-context.cpp:1156`: il server prova a misurare quanto occupa il draft
   *prima* di piazzare il bersaglio, e fallisce sempre, perché
   `llama-context.cpp:129` pretende `ctx_other` per l'architettura DFLASH (il
   draft non ha embedding propri, li prende dal bersaglio) e in fase di misura
   il bersaglio non esiste ancora. Il fitting automatico piazza quindi il
   modello grande come se il draft non ci fosse.

2. **Il draft occupava 6,8 GB di VRAM per immagazzinare esperti che non usa.**

```
n_layer = 3      n_expert = 256   n_expert_used = 6 (+1 condiviso)
expert_ffn = 2048   n_embd = 4096   6,68 GiB a 2,89 bpw
```

I nove tensori `blk.{0,1,2}.ffn_{gate,down,up}_exps.weight` pesano 6,50 GiB,
cioè il **97,3%** del file. Il resto del draft — attenzione, testa, indexer —
sta in 185 MiB.

## La cura, e la sua misura

`-cmoed` manda in RAM solo gli esperti del draft, lasciando il resto sulla GPU.
Il backbone denso torna intero in VRAM.

Tre bracci identici in tutto tranne il draft: `-ngl 99 -ncmoe 42 -ub 64`,
ctx 4096, 300 token, stesso prompt, stesso momento.

```
                                     ms/token   t/s    VRAM ded/cond   accettaz.
S1  controllo, niente draft            231,33   4,32    9.663 / 193       —
S2  draft, esperti in RAM (-cmoed)     343,06   2,91   10.777 / 202     0,632
S3  draft tutto in RAM (-ngld 0)       376,45   2,66   10.600 / 199     0,596
```

La cura funziona per quello che prometteva: il travaso sparisce (202 MiB
condivisi contro 1.267), il backbone è intero, l'accettazione regge. **E la
speculazione perde comunque il 48%.**

## Il numero che chiude la questione

Costo del draft per ciclo, ricavato sottraendo la verifica (`108/30 ms` per
passata/token dall'ammortamento misurato) dal ciclo osservato:

```
draft tutto su GPU        (braccio B, -ngl 22)     ~936 ms
draft esperti in RAM      (S2, testa su GPU)       ~919 ms
draft tutto in RAM        (S3)                     ~864 ms
```

**6,8 GB spostati fra VRAM, RAM e una via di mezzo: il costo si muove del 7%.**

Non è banda, non è collocazione, non è il PCIe. È il lavoro dentro le tre
passate che DSpark fa a ogni ciclo (`speculative.cpp`, `process()` +
`gen_draft()`):

```
llama_encode(ctx_dft)    fonde le feature estratte da 3 strati del bersaglio
llama_decode(ctx_dft)    inietta la K/V ai token accettati
llama_decode(ctx_dft)    decodifica il blocco di 5 (1 token + 4 maschere)
```

Aritmetica di quanto *dovrebbe* costare una passata: 5 token × 3 strati × 7
esperti = fino a 90 istanze di esperto, 816 MiB letti, 5,3 GFLOP. Sulla 3060
sono ~3 ms di banda; su CPU ~80 ms. Misurati: ~310 per passata. **Il resto è
orchestrazione** — la stessa diagnosi del decode principale, ripetuta dentro
il draft.

## Due ipotesi mie, falsificate per strada

```
"i grafi CUDA non si attivano, 34.066 lanci per passata"
    LLAMA_GRAPH_REUSE_DISABLE=1 sul controllo: 399,44 contro 388,69.
    Ricostruire il grafo costa 10,75 ms, il 2,8%.

"il draft traboccato paga il PCIe a ogni pescata"
    draft caricato ma fermo (--spec-draft-n-max 0): 409,28 contro 388,69.
    La presenza del draft costa 20,59 ms/token, il 5,3%.
```

Il `graphs reused = 8` in speculazione è reale — `dsv4_can_reuse_comp_input`
confronta le dimensioni del piano di compressione DSV4, periodico sui rapporti
4 e 128, e la speculazione avanza di 4,16 token in media, un passo variabile —
ma costa 11 ms, non un secondo.

## La conseguenza che ribalta il verdetto del braccio B

Il 3/8 alle 07:22 la speculazione **guadagnava** il 3,5% a `-ngl 22`. Qui, a
configurazione buona, ne perde il 48%. Non è una contraddizione:

```
-ngl 22    passata ~380 ms    tanto da ammortizzare  ->  un draft da 1 s conviene
ngl 99     passata ~180 ms    poco da ammortizzare   ->  un draft da 1 s stronca
```

**La speculazione paga solo quando la base è cattiva.** Migliorare la base
riduce ciò che la speculazione può recuperare, mentre il costo del draft resta
fisso. È il motivo per cui il +3,5% non era una porta aperta.

## Cosa decide, in pratica

```
seconda GPU per il draft      NO. Il costo non e' dove stanno i pesi: una
                              scheda dedicata sposterebbe 6,8 GB per il 7%.
draft sul minipc / in rete    NO, e a maggior ragione: hardware piu' lento
                              piu' ~13 ms di rete per 43 attraversamenti.
piu' RAM per il draft         NO. S3 lo tiene tutto in RAM ed e' il piu' lento.
```

La leva, se mai si tirasse, è dentro `common/speculative.cpp`: ridurre le tre
passate per ciclo, o sovrapporre il draft alla verifica invece di metterli in
sequenza. È lavoro di codice, non di configurazione.
