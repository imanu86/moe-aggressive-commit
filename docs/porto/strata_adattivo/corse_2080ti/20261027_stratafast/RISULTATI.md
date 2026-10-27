# Prova del `--prompt-split` di StrataFast sulle nostre schede (27/10/2026)

**Esito: non misurabile. StrataFast non gira sulla 2080 Ti senza riscrivere i suoi kernel di lettura del prompt. Nessun numero di prompt tok/s, quindi nessuna tabella spento/acceso.**
Compilato si (con 6 modifiche locali), installato no, provato in parte (avvio e decode sì, lettura del prompt no).

## Fork
`eddoursul/StrataFast`, ramo `custom`, `dd0390fb` (motore 0.1.43.1), clonato in `C:\Users\imanu\source\repos\Strata-wt\stratafast` (solo sorgenti).
`--prompt-split L` esiste solo con `--second-gpu` (seconda scheda come livello di esperti, niente `--layer-split`, `--pipeline-windows`, `--kv-resident`, `--elastic`, cache conversazioni, `--host-core`).
La scheda principale esegue tutto il modello; la seconda esegue i livelli L.. di ogni pezzo di prompt mentre la principale legge il pezzo dopo. Valore del suo autore: 26 su 48 livelli (3090 + 5070 Ti).

## Perché non gira su sm_75 (2080 Ti)
1. CMake rifiuta compute < 8.0 (riga 54 di `CMakeLists.txt`). Tolto il rifiuto, la compilazione con CUDA 12.6 si ferma su: `cudaMemcpyBatchAsync` (serve CUDA 13), `__reduce_max_sync`, `cp.async`, `mma m16n8k16/k32` (bf16, f16, int8) in 6 file.
2. Le ho portate a mano (`turing_port.diff`: copie di riserva a una a una, mma spezzate in m16n8k8 / m8n8k16, riduzioni con shuffle). Compila (`strata.exe` sha256 `8520c2e7...91dd`, in `20261004_routed_keep\build-stratafast-dd0390fb`) e **parte**: carica 40 GiB di esperti, riempie le cache (2080 Ti principale, 3060 seconda), risponde al primo "READY" (decode di 2 token, 0,7 s).
3. Poi si ferma, e non è una modifica da poco:
   - Il kernel di attenzione del decode in int8 (`attn_mma_kernel`, 384 thread, più di 64 KB di memoria condivisa) non parte su Turing (limite 64 KB): con `--kv int8` il motore muore alla prima richiesta (`qsa_decode_attn: ... previous error during capture`). Con `--kv fp16` il decode va.
   - La lettura del prompt in blocchi si ferma subito: `gdn_scan: the kernel's shared memory`. Il kernel `gdn_chunk_kernel` (livelli GDN, 36 su 48) chiede 97 KB di memoria condivisa; la 2080 Ti ne concede 64 KB. Serve riprogettare il kernel (buffer, schedulazione dei warp), non un ritocco. La 3060 (sm_86, 100 KB) lo reggerebbe, ma la scheda principale e la seconda li usano entrambe.
   - Senza lettura a blocchi non c'è `--prompt-split`.
   - Nota: anche il README del fork elenca fra le cose tolte "le build Turing".
4. Per questo non ho fatto i bracci (Daily 0.2.6, upstream 0.1.43 puro): annullati dall'owner; restava solo spento-acceso-spento sullo stesso exe, impossibile senza la lettura del prompt.

Jump Desktop era connesso (sessione 1, ~1027 s di CPU totali). Nessun processo `strata*` e nessun `bench.lock` rimasti a fine prova.

## Verdetto: non vale la pena portarlo sulla 0.2.6
- Lo stesso meccanismo c'è già nella nostra base: `docs/MULTI_GPU.md` della 0.2.6, riga 111: "Prompts are read in chunks that flow through the cards in turn: while a later card reads chunk c, the first card reads chunk c+1". Con `--layer-split 16` il prompt viaggia già a due stadi sulle nostre schede (3060 livelli 0-15, 2080 Ti il resto). Il +24/43/55% del fork è rispetto alla *sua* lettura a uno stadio (seconda scheda solo come livello di esperti), non rispetto a una divisione per livelli.
- Quello che il fork aggiunge (seconda scheda che esegue "per intero" i livelli L.. con gli esperti in streaming, scelta di L in base alla velocità delle due schede) per noi equivale a ritarare `layer_split` per la lettura del prompt (la 2080 Ti è circa 2x la 3060 sui passi densi, quindi il confine ottimo per il prompt è diverso dal 16 scelto per il decode). È un esperimento di taratura sulla 0.2.6 (`docs/MULTI_GPU.md`: barra "hand sweep of layer_split": 12/18/24/28/32 dà 582/693/762/802/803 tok/s su 4060 Ti + 3060), non un porting.
- Costo del porting vero: riscrivere per Turing `gdn_chunk_kernel` e il decode `attn_mma_kernel`, e poi verificare la qualità (le mma f16/bf16 convertite e le somme in ordine diverso cambiano l'arrotondamento). Giorni di lavoro per una leva che abbiamo già.

## File
- `strata-stratafast.json`: configurazione adattata (stesse fonti della Daily 0.1.43, tolte le opzioni sconosciute, `--second-gpu 0 --main-gpu 1`, `--kv fp16 --kv-grow`, `--prompt-shift 0.2` come l'esempio del fork).
- `sf_bench.py`: banco con `--targets 32768,65536,128000`, prende `bench.lock`, `--prompt-split L` se L > 0 (mai usato oltre lo smoke).
- `turing_port.diff`: le modifiche locali al fork (non pubblicate).
- `smoke2/`: log dell'unica corsa utile (decode ok, `gdn_scan` ferma il prompt).
