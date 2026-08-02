
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
