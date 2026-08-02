
## SPEX — 2026-08-02, parcheggiato dall'utente

Nei log del fork: `SPEX stats ... hit_rate=0.9269 miss_per_expert=0.0697`, e in un
altro run `hit_rate=0.8216 miss_per_expert=0.1702`. E' il numero che l'utente
ricordava ("miss rate sotto il 17%") ed era preciso.

**Cos'e' (detto dall'utente, che l'ha inventato): un sistema di PREDIZIONE basato
su hidden layer con Markov.** Non e' una politica di cache: non sceglie cosa
tenere, predice cosa servira' e lo va a prendere prima.

Per questo il confronto con `[moecache]` (`hit_rate=0.099`, `cap=181`, uguale su
fork e su 0731) non e' fra due cache: sono due cose diverse.

E per questo l'82-93% non contraddice il tetto di Belady al 47,8% misurato il 2/8:
Belady limita lo **sfratto reattivo a capienza fissa**. Un predittore che
prefetcha gioca un'altra partita. Coerente con l'altra misura dello stesso giorno:
il 90,3% degli accessi va a esperti gia' visti, ma su distanze piu' lunghe di
quanto una cache reattiva possa ricordare -- cioe' esattamente il buco che un
predittore copre.

Nove variabili nel fork (`DS4_SPEX_CAP`, `_PREFETCH_K`, `_RING_SLOTS`, `_FUSED_TOPK`,
`_CPU_PROBE_K`, `_FILE`, `_AB_STAGE`, `_DRY_RUN_STATS_EVERY`, `_HIDDEN_GPU_DRY_RUN`).
**Su 0731 non esiste nulla**: e' l'unica cosa esclusa esplicitamente dal porto.

Da riprendere DOPO la mappatura. Prima domanda: perche' era stato messo da parte.


## RIPRESA dopo il riavvio del 2026-08-02, 13:50

### Lo stato

SOTA su 0731: **3,75 t/s** (braccio G + `DS4_EXPERT_TIER_CLOCK_CALLS=1000`),
ctx 10000, prompt da 43 token. Fork 4,49.

**llama.cpp b10227 ci batte**, ed e' il fatto piu' importante della giornata:

```
                        prompt 43 tok        prompt 2852 tok
llama.cpp -ngl99 -cmoe  decode 6,16 t/s      decode 4,37   prefill 7,83 t/s
noi                     REGIME 3,75          da misurare
```

Loro non hanno **nessuna** cache esperti: `-cmoe` mette tutto su CPU. Il divario
e' nel TRASPORTO: 9,7 GB/s contro i nostri 3,25 (`[worker-prof] read_mb_s=3249`).
Loro mappano il modello nel processo (RAM al 100%), noi facciamo `pread` in
buffer pinned (RAM al 22%).

### Due bug scoperti alla fine, da correggere PRIMA di rimisurare

1. **VRAM sporca.** A macchina ferma, nessun motore, `nvidia-smi` dava **2915
   MiB** contro un desktop che sta a ~700. Sono ~2,2 GB non rilasciati, e
   coincidono coi **2156 MiB non attribuiti** del bilancio. Colpevole probabile
   gia' noto dall'audit: ordine di teardown, `model_close` prima di
   `ds4_gpu_cleanup` (`src/platform/os_mmap.c:76`).
   **Tutte le misure di oggi sono state fatte con VRAM progressivamente sporca.**
2. **`prefill_lungo.ps1` aspetta `/health`**, che ha llama.cpp e il nostro server
   NO. Ha atteso 25 minuti invano mentre il server era gia' in ascolto
   (`listening on http://127.0.0.1:8097`). Va cambiato in una POST di prova.

### Cosa fare, in ordine

1. VRAM pulita dopo il riavvio: misurare la base a desktop fermo.
2. Correggere l'attesa in `prefill_lungo.ps1` e rifare il test del prefill lungo
   su entrambi i motori. Prompt deterministico, sha `939da284142eb5cc`.
3. **Varianza fra run**: stessa configurazione tre volte. Mai misurata, e le due
   vittorie di oggi (+7,4% q8/f16, +8,1% clock 1000) sono dello stesso ordine di
   una varianza plausibile.
4. Sintonizzare **llama.cpp**, dove il margine e' inesplorato: `-ncmoe` per usare
   i ~2,9 GB di VRAM libera, `-b`/`-ub`, `--no-mmap`, `--cache-reuse`,
   `-ot ".ffn_(up|down)_exps.=CPU"` (tiene il gate in VRAM).
5. La domanda vera: **perche' leggiamo a 3,25 GB/s dove ggml legge a 9,7.**

### Cosa NON si butta

La conoscenza del carico, che vale su qualunque motore: 258 esperti distinti per
token, 90,3% degli accessi sono riletture, la LRU pura prenderebbe zero colpi, il
percorso di lettura anti-scala col parallelismo, ogni punto di hit rate vale lo
0,7% di velocita'. E REAP Stage A, che e' una modifica al GGUF e gira su
entrambi i motori.

## DSpark su llama.cpp — 2026-08-02 pomeriggio: DIAGNOSI PRECISA, non funziona ANCORA

### Fatto

- **Compilato** `YanissAmz/llama.cpp -b dspark-dsv4` con CUDA in `D:\llama-dspark`
  (`build_cuda.bat`, arch 86, Ninja+Release, `BUILD_EXIT=0`). La punta del ramo e'
  `c2e5186 "dflash: use the DeepSeek-V4 rotary pairing for a DeepSeek-V4 backbone"`.
- **Scaricato** `C:\ds4-models\DSV4-Flash-DSpark-draft-bf16.gguf`, 10,15 GiB.

### Il draft, geometria vera (il nome MENTE)

```
arch dflash    81 tensori    19,85 MILIARDI di parametri    4,39 bit per peso
tipi: tipo39 (MXFP4) = 19,33B,  Q8_0 = 0,45B,  BF16 = 0,07B
dflash.block_count = 3     dflash.block_size = 5
dflash.expert_count = 256  dflash.expert_used_count = 6    <- il draft e' a sua volta un MoE
dflash.target_layers = [41, 42, 43]
```

Non e' BF16: e' **MXFP4, gia' a 4 bit**. E non e' un modellino denso: e' un MoE con
256 esperti, quindi **draftare costa letture di esperti anche al draft** — un pezzo
di costo che non era nel conto del tetto 1,83x.

### Perche' fallisce

```
il nostro target    blk.0 .. blk.42        43 strati
il draft vuole      target_layers = [41, 42, 43]
                    -> l'indice 43 NON ESISTE -> "invalid vector subscript"
```

Il nostro GGUF dichiara `nextn_predict_layers = 1` ma **non contiene i tensori**:
sono stati estratti nei file MTP separati alla quantizzazione. Il target di
YanissAmz (`DeepSeek-V4-Flash-UD-IQ3_XXS` di unsloth) ha quasi certamente 44
strati, col nextn incluso.

Il backbone invece **e' supportato**: `dflash.cpp:34` rileva il DSv4 dalla presenza
di `attn_q_a`.

### Tre configurazioni provate, tutte fallite, con la loro causa

```
-ngl 99 -cmoed        invalid vector subscript   (il draft, indice 43)
-ngl 99 -devd none    output.weight pre-allocato su CUDA0 senza device per eseguirlo
--fit on              abortito da tensor_buft_overrides (li mette -cmoe sul target),
                      poi stesso invalid vector subscript
```

Nota: `--fit` e' l'adattatore automatico che colloca target e draft nella memoria
disponibile. **Forzare `-ngl` o usare `-cmoe` lo abortisce.** I miei primi due
tentativi lo avevano disattivato senza che me ne accorgessi.

### Cosa serve per farlo funzionare

1. **Un target con 44 strati** (nextn incluso). Da verificare se unsloth
   `UD-IQ3_XXS` ce l'ha: la lettura remota dell'header e' fallita perche' i
   metadati eccedono i 12 MB che avevo chiesto. E' ~103 GB.
2. **Oppure innestare il nostro MTP** (`DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf`,
   32 tensori `mtp.0.*`) come `blk.43` del target. **Ma la convenzione non
   coincide**: llama.cpp vuole `blk.%d.nextn.{eh_proj,embed_tokens,enorm,hnorm,
   shared_head_head,shared_head_norm}` (convenzione DeepSeek-V3) mentre il nostro
   ha `mtp.0.{main_proj,main_norm,attn_*,ffn_*,hc_*}`. Non e' un rinominare.
3. E comunque **il caricatore deepseek4 di llama.cpp non carica nessuno strato
   nextn**: zero occorrenze di `nextn` nel suo blocco di `create_tensor`.

### Il conto economico, aggiornato

Tetto della speculazione su questo modello (issue upstream #636): **1,83x** con
accettazione perfetta, **perdita netta sotto 0,72**. Misurato da YanissAmz su
Strix Halo: 0,72-1,00 a contesto corto (+19-25%), 0,54 a 176k (perdita netta).

E il draft e' un MoE da 19,85B: le sue letture di esperti si sommano a quelle
della verifica, quindi il tetto reale e' piu' basso di 1,83x.

### ESITO FINALE 2/8 sera: DSpark su llama.cpp GIRA, e PERDE

La coppia carica con `-ngl 99` (target, esperti su CPU) + `-ngld 0` (draft tutto
su CPU). La mia diagnosi "manca lo strato 43" era SBAGLIATA: unsloth UD-IQ2_XXS
ha la stessa struttura del nostro file (43 strati, 1328 tensori) e l'indice 43
e' lo stato nascosto finale. Il crash era lo split GPU del draft MoE.

Misurato sul banco (prompt 43 tok, 800 generati, ctx 10000):

    accettazione   0,707  (blocchi medi 4,42)   <- sulla soglia 0,72 di #636
    decode         3,19 t/s   contro 6,61 senza speculazione   = -52%

Causa strutturale: il draft e' un MoE da 19,85B che gira sulla stessa CPU che
serve gli esperti del target. Competono per la stessa risorsa satura. A ctx
corto -- il regime MIGLIORE -- gia' si perde meta' della velocita': la curva
dell'incrocio non esiste su questo hardware.

Riaprire solo se: (a) esce un draft V4 PICCOLO E DENSO, o (b) si cambia hardware
verso memoria unificata (Strix Halo-like), dove YanissAmz misura +19-25%.
