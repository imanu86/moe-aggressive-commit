# AUDIT — `Set-SotaEnvironment` (p1b_conf.ps1). Censimento, rischio, piano di bonifica

**Analisi di sola lettura, 2/9 04:0x–04:4x.** Macchina OCCUPATA: `llama-server` PID 13448 vivo dalle
`02/09/2026 04:00:53`. **Nessun file toccato, nessun processo lanciato, zero GPU.**

## §0. mtime dei file letti (regola §49.3 del ledger 25/8)

| file | mtime alla lettura | byte |
|---|---|---|
| `D:\ds4_work\llama_run\lanciatori_salvati_20260825\p1b_conf.ps1` | **2026-09-01 20:30:25.196301000 +0200** | 23.159 |
| `…\vl_arm.ps1` | 2026-09-01 20:30:50.271519400 | 8.163 |
| `…\sw_arm.ps1` | 2026-08-31 09:36:18.704864800 | 5.039 |
| `…\r57_arm.ps1` | 2026-08-31 05:26:02.865831200 | 3.151 |
| `…\r58_arm.ps1` | 2026-08-31 06:44:07.324570000 | 4.621 |
| `…\r59_arm.ps1` | 2026-08-31 07:19:54.108056100 | 5.074 |
| `…\p2_arm.ps1` | 2026-08-31 09:06:02.661470500 | 3.466 |
| `…\r53/r54/r55_arm.ps1` | 30/8 19:21 / 20:05 / 20:26 | 3.769 / 3.611 / 1.739 |
| `C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1` | 2026-08-31 04:59:45.664683900 | 13.087 |
| `D:\llama-subtract\tools\server\server.cpp` (tabella manifesto) | 2026-08-31 17:23:45.472049100 | 34.166 |
| `D:\llama-subtract\scripts\manifesto_check.py` | 2026-08-12 11:23:14.112592200 | 5.276 |

**`p1b_conf.ps1` NON è cambiato sotto di me**: mtime identico all'inizio e alla fine dell'analisi
(`…20:30:25.196301000`). La campagna in corso non lo ha esteso.

⚠ **Caveat §49.2**: la colonna «difetto del codice» è letta dal SORGENTE di `D:\llama-subtract`,
non dal binario. Il ledger avverte che sorgente e DLL possono divergere. Le colonne «valore
inchiodato» e «riga» sono invece fatti sul file del lanciatore, non deduzioni.

---

## §1. CENSIMENTO COMPLETO

**62 variabili d'ambiente** sono scritte dal lanciatore:
- **61 dentro `Set-SotaEnvironment`** (righe 198–265): 60 assegnazioni `$env:X = …` + 1 *cancellazione*
  incondizionata (riga 264);
- **1 fuori dalla funzione ma dentro il ciclo delle shape** (riga 324).

Di queste: **18 sono già parametrizzate o derivate**, **44 sono inchiodate a letterale**
(43 assegnazioni + 1 cancellazione).

Legenda colonne: **Par.** = parametro che la alimenta (difetto). **Man.** = presente nella tabella
`server_manifesto_leve` di `server.cpp` (⇒ compare come `NOME=valore(E|D)` nel log). **arm:** = compare
nella riga `arm:` del summary (riga 305).

### 1.1 Le 18 GIÀ PARAMETRIZZATE / derivate — nessun debito

| riga | env | valore | Par. (difetto) | Man. | arm: |
|---|---|---|---|---|---|
| 200 | `LLAMA_MAPPED_IBRIDO_SOGLIA` | `$MappedIbridoSoglia` | `-MappedIbridoSoglia` (2) | ✔ | ✔ |
| 201 | `LLAMA_CACHE_ESPERTI_SLOT` | `$CacheEspertiSlot` | `-CacheEspertiSlot` (473) | ✔ | ✔ |
| 202 | `LLAMA_CACHE_BOZZA_SLOT` | `$CacheBozzaSlot` | `-CacheBozzaSlot` (12) | ✔ | ✔ |
| 210 | `LLAMA_CACHE_ESPERTI_W` | `$CacheEspertiW` | `-CacheEspertiW` (0) | ✔ | ✔ |
| 212 | `LLAMA_CACHE_ESPERTI_FORK` | `$CacheEspertiFork` | `-CacheEspertiFork` (2) | ✔ | ✔ |
| 216 | `LLAMA_CACHE_ESPERTI_MASSA` | `$CacheEspertiMassa` | `-CacheEspertiMassa` (2) | ✔ | ✔ |
| 223 | `LLAMA_ACCEPTMOE` | `$Acceptmoe` | `-Acceptmoe` ('1') | ✔ | ✔ |
| 225 | `LLAMA_ACCEPTMOE_SOGLIA` | `$AcceptmoeSoglia` | `-AcceptmoeSoglia` ('0.75') | ✔ | ✔ |
| 226 | `LLAMA_ACCEPTMOE_COMPATTA` | `$AcceptmoeCompatta` | `-AcceptmoeCompatta` ('1') | ✔ | ✔ |
| 227 | `LLAMA_GRAPH_REUSE_PER_TAGLIA` | `$GraphReusePerTaglia` | `-GraphReusePerTaglia` (1) | ✔ | ✔ |
| 230 | `LLAMA_OVERLAP_K` | `$OverlapK` (arg di funzione) | `-OverlapK` ('2') | ✔ | ✔ |
| 231 | `LLAMA_OVERLAP_BATCH_MAX` | `$OverlapBatchMax` (arg) | `-OverlapBatchMax` (3) | ✔ | **✘ ASSENTE** |
| 240 | `LLAMA_KV_PAD` | cond. `$KvPad`, altrimenti **UNSET** | `-KvPad` ('') | ✘ | ✔ (`kv-pad`) |
| 241 | `LLAMA_KV_RING_BATTITO` | cond. `$KvRingBattito`, altr. **UNSET** | `-KvRingBattito` ('') | ✘ | ✔ |
| 249 | `LLAMA_DSV4_HC_FUSO` | `$HcFused` | `-HcFused` (5) | ✔ | ✔ |
| 251 | `LLAMA_CUDA_FATTN_BLOCK_SPARSE` | `$BlockSparse` | `-BlockSparse` (1) | ✘ | ✔ (`block-sparse`) |
| 257 | `GGML_SCHED_OFFLOAD_PACCHETTI` | `$packetizerActive` | `-Packetizer`(−1)/`-BlockDenseCpu`(0) | ✘ | ✔ (`packetizer`) |
| 324 | `LLAMA_DSV4_PREFILL_MOE_UB` | `$shape.UBatch` | derivata dalla shape | ✘ | indiretto (tag + riga `DONE`) |

**Un buco anche qui**: `-OverlapBatchMax` è passabile ma **non compare nella riga `arm:`**. È visibile
solo nel manifesto del server. Se la riga `arm:` è l'unico testimone che si legge (lo è, nei triage
rapidi), un braccio con `BATCH_MAX=4` è indistinguibile dal controllo — e quel valore ha un crash
noto al taglio del reasoning.

### 1.2 Le 44 INCHIODATE — il debito

| riga | env | valore inchiodato | difetto del codice | Man. | arm: | fascia |
|---|---|---|---|---|---|---|
| 199 | `LLAMA_MAPPED_IBRIDO` | `'1'` | 0 (**diverso**) | ✔ | ✘ | GIALLA |
| 203 | `LLAMA_CACHE_ESPERTI_BATCH` | `'8'` | 8 | ✔ | ✘ | **ROSSA P2** |
| 204 | `LLAMA_CACHE_ESPERTI_BATTITO` | `'45'` | 60 (**diverso**) | ✔ | ✘ | **ROSSA P1** |
| 205 | `LLAMA_CACHE_ESPERTI_CODA_MAX` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 206 | `LLAMA_CACHE_ESPERTI_CURA` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 207 | `LLAMA_CACHE_ESPERTI_SCUDO` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 208 | `LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO` | `'0'` | 0 | ✔ | ✘ | **ROSSA P1** |
| 209 | `LLAMA_CACHE_ESPERTI_LRU` | `'1'` | 1 | ✔ | ✘ | **ROSSA P2** |
| 211 | `LLAMA_CACHE_ESPERTI_SFRATTO_PAR` | `'1'` | 0 (**diverso**) | ✔ | ✘ | **ROSSA P1** |
| 213 | `LLAMA_CACHE_ESPERTI_FORK_BLOCCHI` | `'8'` | 32 (**diverso**) | ✔ | ✘ | **ROSSA P1** |
| 214 | `LLAMA_CACHE_ESPERTI_FORK_RIUSA_SLOT` | `'0'` | 0 | **✘** | ✘ | **ROSSA P2** |
| 215 | `LLAMA_CACHE_ESPERTI_FORK_SALTA_COPIA_PARITA` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 217 | `LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE` | `'0'` | **1** (**diverso**) | **✘** | ✘ | **ROSSA P1** |
| 218 | `LLAMA_CACHE_ESPERTI_MASSA_CORSIE` | `'0'` | **1** (**diverso**) | **✘** | ✘ | **ROSSA P1** |
| 219 | `LLAMA_CACHE_ESPERTI_DMA` | `'0'` | 0 | ✔ | ✘ | **ROSSA P2** |
| 221 | `LLAMA_SPEC_DRAFT_TOPK` | `'1'` | 1 | ✔ | ✘ | GIALLA |
| 222 | `LLAMA_SPEC_CONF_ESENTA_POS0` | `'1'` | 0 (**diverso**) | ✔ | ✘ | GIALLA |
| 224 | `LLAMA_ACCEPTMOE_ESATTE` | `'1'` | 1 | ✔ | ✘ | **ROSSA P1** |
| 229 | `LLAMA_OVERLAP_ASYNC` | `'1'` | 0 (**diverso**) | ✔ | ✘ | **ROSSA P1** |
| 232 | `LLAMA_OVERLAP_GRIGLIA_VARIABILE` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 233 | `LLAMA_OVERLAP_PIN` | `'1'` | 1 | ✔ | ✘ | **ROSSA P1** |
| 234 | `LLAMA_OVERLAP_JOIN_ASYNC` | `'0'` | 0 | ✔ | ✘ | **ROSSA P1** |
| 236 | `LLAMA_KV_RING` | `'1'` | 0 (**diverso**) | ✔ | ✘ | GIALLA |
| 237 | `LLAMA_KV_RING_VRAM_TOKEN` | `'2048'` | 2048 | ✔ | ✘ | GIALLA |
| 238 | `LLAMA_KV_ROLLBACK_PARZIALE` | `'1'` | 0 (**diverso**) | ✔ | ✘ | GIALLA |
| 239 | `LLAMA_KV_ROLLBACK_SOLO_ANELLO` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 242 | `LLAMA_VRAM_A_FASI` | `'2'` | 0 (**diverso**) | ✔ | ✘ | **ROSSA P2** |
| 243 | `LLAMA_VRAM_A_FASI_UB` | `'64'` | 64 | ✔ | ✘ | GIALLA |
| 244 | `LLAMA_VRAM_A_FASI_CALDO` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 245 | `LLAMA_VRAM_A_FASI_MIN` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 246 | `LLAMA_VRAM_A_FASI_MARGINE` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 248 | `LLAMA_DSV4_INDEXER_FUSO` | `'1'` | 0 (**diverso**) | ✔ | ✘ | **ROSSA P2** |
| 250 | `LLAMA_DSV4_MASK_F16_INPUT` | `'0'` | **nessun lettore** | ✘ | ✘ | VERDE (morta) |
| 252 | `LLAMA_DSV4_PREFILL_LAYER_STAGING` | `'1'` | off (**diverso**) | **✘** | ✘ | **ROSSA P2** |
| 253 | `LLAMA_DSV4_PREFILL_LAYER_EXECUTOR` | `'0'` | off | **✘** | **falso** | **ROSSA P1** |
| 254 | `LLAMA_DSV4_PREFILL_LAYER_SPLIT` | `'0'` | off | **✘** | ✘ | **ROSSA P2** |
| 255 | `LLAMA_DSV4_PREFILL_FFN_SUPEROP` | `'0'` | off | **✘** | **falso** | **ROSSA P1** |
| 258 | `GGML_CUDA_GRAPH_OPT` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 259 | `GGML_CUDA_GRAPH_STATS` | `'1'` | 0 (**diverso**) | ✔ | ✘ | VERDE (strumento) |
| 260 | `GGML_SCHED_PROFILO` | `'1'` | 0 (**diverso**) | ✔ | ✘ | VERDE (strumento) |
| 261 | `LLAMA_CKPT_CRONO` | `'0'` | 0 | ✔ | ✘ | VERDE |
| 262 | `LLAMA_VRAM_ZAVORRA` | `'0'` | 0 | ✔ | ✘ | GIALLA |
| 263 | `LLAMA_MMQ_X_IDS` | `'64'` | 0/`<spento>` (**diverso**) | ✔ | ✘ | **ROSSA P2** |
| 264 | `LLAMA_DSV4_PREFILL_FATTN_Q_TILE` | **CANCELLATA** | **nessun lettore** | ✘ | ✘ | VERDE (morta) |

**Totali**: ROSSA **21** (P1 = 12, P2 = 9) · GIALLA **18** · VERDE **5**.

### 1.3 Tre reperti collaterali del censimento

1. **`arm:` MENTE su due campi.** La riga 305 stampa `executor=0; superop=0` come **testo
   letterale**, non come interpolazione. Se domani un braccio muovesse `LLAMA_DSV4_PREFILL_LAYER_EXECUTOR`
   o `…_FFN_SUPEROP` (il che oggi è comunque impossibile: sono inchiodate), il summary
   continuerebbe a dichiarare `0`. È un **falso testimone già scritto**, non un rischio ipotetico.
2. **Due leve MORTE vengono scritte lo stesso**: `LLAMA_DSV4_MASK_F16_INPUT` (riga 250) e
   `LLAMA_DSV4_PREFILL_FATTN_Q_TILE` (riga 264). Grep su `D:\llama-subtract`
   (`src/`, `ggml/`, `tools/`, `common/`, ogni estensione): **zero lettori**. Righe di rumore che
   fanno sembrare la config più ricca di quanto sia.
3. **14 delle 62 non compaiono nella tabella `server_manifesto_leve`** ⇒ per queste **nemmeno il
   manifesto del server è un testimone**: `FORK_RIUSA_SLOT`, `MASSA_AMMISSIONE`, `MASSA_CORSIE`,
   `KV_PAD`, `KV_RING_BATTITO`, `DSV4_MASK_F16_INPUT`, `CUDA_FATTN_BLOCK_SPARSE`,
   `PREFILL_LAYER_STAGING`, `PREFILL_LAYER_EXECUTOR`, `PREFILL_LAYER_SPLIT`, `PREFILL_FFN_SUPEROP`,
   `GGML_SCHED_OFFLOAD_PACCHETTI`, `PREFILL_FATTN_Q_TILE`, `PREFILL_MOE_UB`.
   Di queste, **5 sono ROSSE e completamente invisibili** (`MASSA_AMMISSIONE`, `MASSA_CORSIE`,
   `FORK_RIUSA_SLOT`, `PREFILL_LAYER_SPLIT`, `PREFILL_LAYER_STAGING`) — né manifesto né `arm:`.
4. **`LLAMA_DSV4_INDEXER_FUSO` diverge fra i due banchi**: il lungo la mette a `'1'` (riga 248), il
   corto `run_porto_hot.ps1:100` a `'0'`. Non è un difetto del lanciatore, ma qualunque confronto
   corto↔lungo porta dentro questa differenza senza dichiararla.

### 1.4 I bracci: chi sarebbe stato tradito

Nessuno dei bracci letti (`r53`, `r54`, `r55`, `r57`, `r58`, `r59`, `p2`, `sw`, `vl`) imposta
dall'esterno una env che `Set-SotaEnvironment` inchioda: **hanno già pagato tutti e nove i dazi** e
oggi passano per parametro. Ciò che i bracci impostano dall'esterno e che **sopravvive** è solo:
`LLAMA_KV_GATHER`, `LLAMA_CACHE_ESPERTI_FORK_SERIALE`, `LLAMA_CACHE_ESPERTI_FORK_COMPONI`,
`LLAMA_TRASPORTO_ONLINE(_BUDGET)`, `GGML_CPU_MMID_REUSE_SRC1` — cioè **esattamente i nomi che il
lanciatore NON scrive**, e infatti sono gli unici che la riga `arm:` rilegge da `$env:` (riga 305).
**È la prova empirica della regola**: una env sopravvive al lanciatore **se e solo se** il lanciatore
non la nomina. Chiunque scelga una leva fuori da quella lista di cinque cade nella trappola n.10.

---

## §2. CLASSIFICAZIONE DEL RISCHIO — motivazione delle 21 ROSSE

Criterio: **(A)** il valore inchiodato *diverge* dal difetto del codice ⇒ qualcuno l'ha già scelto
deliberatamente, quindi è una manopola, non una costante; **(B)** appartiene a un fronte aperto o
già misurato. Rossa = (A) o (B) *e* muoverla è un braccio a una variabile sensato.

### ROSSA P1 — le prossime trappole (12)

| riga | env | perché qualcuno la muoverebbe |
|---|---|---|
| 213 | `FORK_BLOCCHI=8` | il difetto del codice è **32** e la SOTA storica del 12/8 era **512**: la granularità della copia fork è una manopola già spazzolata, e il fronte fork/trasporto è aperto (r57/r58). |
| 211 | `SFRATTO_PAR=1` | è **la variabile** della «regressione del 13-14%» del 12/8 (non impostata dal runner); `r58_arm.ps1:60-68` dichiara che a `MASSA=1` diventa inerte ⇒ è un confondente attivo in ogni braccio MASSA. |
| 217 | `MASSA_AMMISSIONE=0` | il codice ha difetto **1** (`cache-esperti.cu:2750`), il lanciatore forza 0: è una scelta, non una costante. Fronte MASSA aperto (r58 `fork0massa0`/`fork2massa0`) e **invisibile ovunque**. |
| 218 | `MASSA_CORSIE=0` | idem, difetto **1** (`:2751`). Esiste già `run_massa_corsie.ps1` sul disco ⇒ è stata spazzolata in passato. **Invisibile ovunque**. |
| 204 | `BATTITO=45` | difetto del codice **60**. Il candidato n.5 a registro è «la VITA DEL BUFFER»: il battito *è* la vita del buffer. Primo numero che si muoverebbe aprendo quel fronte. |
| 208 | `PREFETCH_FILTRO=0` | il fronte prefetch è aperto (r57 `w1/w2componi`, r58 `tonline`); a `COMPONI=1` funzionante il filtro è la manopola immediatamente successiva. |
| 229 | `OVERLAP_ASYNC=1` | difetto del codice 0. È **il controllo naturale** di ogni braccio fork/overlap («spento l'overlap i colpi crollano 56→18,8%», misura di casa). |
| 234 | `OVERLAP_JOIN_ASYNC=0` | il join è il **23,4%** della parete a registro: la leva più ovvia del fronte host, con lettore vivo (`ggml-backend.cpp:1929`). |
| 233 | `OVERLAP_PIN=1` | sul Vision il vincolo che morde è **il tetto della memoria PINNATA** (`cudaHostAlloc di 2224 MiB fallita`, `vl_arm.ps1:44`). Togliere il pin è lo sfogo che si prova *prima* di `-OtDraft`, e oggi non è provabile. |
| 253 | `PREFILL_LAYER_EXECUTOR=0` | fronte prefill; **e la riga `arm:` stampa `executor=0` come letterale** ⇒ chi lo muovesse otterrebbe un testimone falso oltre che una leva inerte. Doppio danno. |
| 255 | `PREFILL_FFN_SUPEROP=0` | identico: `superop=0` è letterale nella riga 305. |
| 224 | `ACCEPTMOE_ESATTE=1` | **tre dei suoi fratelli sono già le trappole n.7, n.8, n.9**. È l'unico membro della famiglia AcceptMoE ancora inchiodato: statisticamente, è il prossimo. |

### ROSSA P2 — plausibili e già toccate (9)

| riga | env | perché |
|---|---|---|
| 263 | `MMQ_X_IDS=64` | difetto `<spento>`; il decode è **dequant-bound** (verdetto 31/8) e questa è l'unica manopola numerica dentro quel kernel (`mmq.cuh:4057`). |
| 252 | `PREFILL_LAYER_STAGING=1` | difetto off; ha anche un **alias di ripiego** `LLAMA_DSV4_PREFILL_LAYER_MAJOR` (`ggml-cuda.cu:2295-2299`) che nessuno stampa. |
| 254 | `PREFILL_LAYER_SPLIT=0` | stessa famiglia, invisibile ovunque. |
| 203 | `CACHE_ESPERTI_BATCH=8` | partner naturale di `SLOT`/`BOZZA_SLOT` in uno sweep di ammissione. |
| 209 | `LRU=1` | «la LRU prende ZERO colpi» è un reperto a registro ⇒ sostituire la politica di sfratto è un'idea viva. |
| 219 | `DMA=0` | fronte DMA studiato a lungo (il «margine 6×» era un artefatto): riaprirlo richiede muovere questa. |
| 214 | `FORK_RIUSA_SLOT=0` | micro-leva del fork, **assente dalla tabella del manifesto** ⇒ muoverla dall'esterno sarebbe muta *e* invisibile. |
| 242 | `VRAM_A_FASI=2` | difetto 0; l'intera campagna Vision è un problema di budget VRAM/pinnata e questa è la macchina che lo governa. |
| 248 | `DSV4_INDEXER_FUSO=1` | difetto 0, **e vale 0 sul banco corto**: è già una differenza non dichiarata fra i due banchi. |

### GIALLA (18) — plausibile ma improbabile
`MAPPED_IBRIDO` (199), `CODA_MAX` (205), `CURA` (206), `SCUDO` (207), `FORK_SALTA_COPIA_PARITA` (215),
`SPEC_DRAFT_TOPK` (221), `SPEC_CONF_ESENTA_POS0` (222), `OVERLAP_GRIGLIA_VARIABILE` (232),
`KV_RING` (236), `KV_RING_VRAM_TOKEN` (237), `KV_ROLLBACK_PARZIALE` (238), `KV_ROLLBACK_SOLO_ANELLO` (239),
`VRAM_A_FASI_UB` (243), `_CALDO` (244), `_MIN` (245), `_MARGINE` (246), `GGML_CUDA_GRAPH_OPT` (258),
`VRAM_ZAVORRA` (262).
Sono fronti chiusi o interruttori che **cambiano macchina** (spegnere `MAPPED_IBRIDO` o `KV_RING` non
è un braccio a una variabile: è un altro esperimento). Tutte visibili nel manifesto del server, quindi
una sovrascrittura mancata sarebbe almeno *diagnosticabile a posteriori* dal log.

### VERDE (5) — non ha senso muoverle
`DSV4_MASK_F16_INPUT` (250) e `PREFILL_FATTN_Q_TILE` (264): **morte, nessun lettore** — da cancellare,
non da parametrizzare. `GGML_CUDA_GRAPH_STATS` (259) e `GGML_SCHED_PROFILO` (260): strumenti di misura,
devono restare identici sui due lati di ogni A/B (lo dice `r54_arm.ps1:7-10`). `LLAMA_CKPT_CRONO` (261):
diagnostica spenta.

---

## §3. PIANO DI BONIFICA NEL PATTERN DI CASA (da applicare A MACCHINA FERMA)

Il pattern è codificato dal diff `p1b_conf.ps1.bak_20260901_pre_compatta` → corrente, ed è
**tre punti** per leva: (1) una riga nel param block col **difetto uguale al letterale**, (2) la
sostituzione del letterale con l'interpolazione, (3) un campo nella riga `arm:`.

### 3.0 Prima di toccare: backup datato
```
Copy-Item p1b_conf.ps1 p1b_conf.ps1.bak_20260902_pre_bonifica
```
(convenzione confermata: 8 backup già presenti, da `.bak_20260826_pre_bm` a `.bak_20260901_pre_compatta`).

### 3.1 Diff testuale proposto — ROSSE P1 (12 leve, 25 righe di codice)

**(1) Param block** — la riga 148 `[string] $OtDraft = '…')` perde la parentesi finale, che si sposta
in coda alle nuove righe. Testo da inserire (difetti = letterali attuali, verificati uno a uno):

```powershell
    # 2/9 -- bonifica sistematica: le dodici ROSSE P1 del censimento
    # AUDIT_SET_SOTA_ENVIRONMENT.md. Ogni difetto qui sotto e' IDENTICO al
    # letterale che stava in Set-SotaEnvironment ⇒ comportamento byte-per-byte.
    [int]    $CacheEspertiBattito      = 45,     # era riga 204, letterale '45'
    [int]    $CacheEspertiPrefetchFiltro = 0,    # era riga 208, letterale '0'
    [int]    $CacheEspertiSfrattoPar   = 1,      # era riga 211, letterale '1'
    [int]    $CacheEspertiForkBlocchi  = 8,      # era riga 213, letterale '8'
    [int]    $CacheEspertiMassaAmmissione = 0,   # era riga 217, letterale '0'
    [int]    $CacheEspertiMassaCorsie  = 0,      # era riga 218, letterale '0'
    [int]    $AcceptmoeEsatte          = 1,      # era riga 224, letterale '1'
    [int]    $OverlapAsync             = 1,      # era riga 229, letterale '1'
    [int]    $OverlapPin               = 1,      # era riga 233, letterale '1'
    [int]    $OverlapJoinAsync         = 0,      # era riga 234, letterale '0'
    [int]    $PrefillLayerExecutor     = 0,      # era riga 253, letterale '0'
    [int]    $PrefillFfnSuperop        = 0)      # era riga 255, letterale '0'
```

**(2) Interpolazioni** — 12 righe sostituite in loco, una a una:

```diff
-204:    $env:LLAMA_CACHE_ESPERTI_BATTITO = '45'
+204:    $env:LLAMA_CACHE_ESPERTI_BATTITO = "$CacheEspertiBattito"
-208:    $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = '0'
+208:    $env:LLAMA_CACHE_ESPERTI_PREFETCH_FILTRO = "$CacheEspertiPrefetchFiltro"
-211:    $env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = '1'
+211:    $env:LLAMA_CACHE_ESPERTI_SFRATTO_PAR = "$CacheEspertiSfrattoPar"
-213:    $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = '8'
+213:    $env:LLAMA_CACHE_ESPERTI_FORK_BLOCCHI = "$CacheEspertiForkBlocchi"
-217:    $env:LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE = '0'
+217:    $env:LLAMA_CACHE_ESPERTI_MASSA_AMMISSIONE = "$CacheEspertiMassaAmmissione"
-218:    $env:LLAMA_CACHE_ESPERTI_MASSA_CORSIE = '0'
+218:    $env:LLAMA_CACHE_ESPERTI_MASSA_CORSIE = "$CacheEspertiMassaCorsie"
-224:    $env:LLAMA_ACCEPTMOE_ESATTE = '1'
+224:    $env:LLAMA_ACCEPTMOE_ESATTE = "$AcceptmoeEsatte"
-229:    $env:LLAMA_OVERLAP_ASYNC = '1'
+229:    $env:LLAMA_OVERLAP_ASYNC = "$OverlapAsync"
-233:    $env:LLAMA_OVERLAP_PIN = '1'
+233:    $env:LLAMA_OVERLAP_PIN = "$OverlapPin"
-234:    $env:LLAMA_OVERLAP_JOIN_ASYNC = '0'
+234:    $env:LLAMA_OVERLAP_JOIN_ASYNC = "$OverlapJoinAsync"
-253:    $env:LLAMA_DSV4_PREFILL_LAYER_EXECUTOR = '0'
+253:    $env:LLAMA_DSV4_PREFILL_LAYER_EXECUTOR = "$PrefillLayerExecutor"
-255:    $env:LLAMA_DSV4_PREFILL_FFN_SUPEROP = '0'
+255:    $env:LLAMA_DSV4_PREFILL_FFN_SUPEROP = "$PrefillFfnSuperop"
```

**(3) Riga `arm:` (riga 305)** — una sola riga modificata; **si correggono anche i due falsi
testimoni e si aggiunge la voce mancante**:

```diff
-    ... packetizer=$packetizerActive; executor=0; superop=0; ctx=$Context; ...
+    ... packetizer=$packetizerActive; executor=$PrefillLayerExecutor; superop=$PrefillFfnSuperop; ctx=$Context; ...
```
e in coda, prima di `draft loaded`:
```
+ ; overlap-batch-max=$OverlapBatchMax; battito=$CacheEspertiBattito; prefetch-filtro=$CacheEspertiPrefetchFiltro; sfratto-par=$CacheEspertiSfrattoPar; fork-blocchi=$CacheEspertiForkBlocchi; massa-ammissione=$CacheEspertiMassaAmmissione; massa-corsie=$CacheEspertiMassaCorsie; acceptmoe-esatte=$AcceptmoeEsatte; overlap-async=$OverlapAsync; overlap-pin=$OverlapPin; join-async=$OverlapJoinAsync
```

**Righe toccate, P1**: 12 nuove nel param block + 12 sostituzioni + 1 riga `arm:` = **25 righe di
codice** (≈ +40 righe se si commenta ogni voce nello stile di casa).

### 3.2 Estensione alle ROSSE P2 (altre 9 leve)
Stesso schema per le righe **203, 209, 214, 219, 242, 248, 252, 254, 263**:
9 param + 9 sostituzioni + gli stessi campi in coda a `arm:` (la riga 305 è già contata).
**Totale ROSSE (21)**: 21 + 21 + 1 = **43 righe di codice**.

### 3.3 Ordine consigliato
1. **Backup datato** (`.bak_20260902_pre_bonifica`).
2. **Le due correzioni a costo zero e a rischio zero**: i letterali `executor=0; superop=0` nella riga
   `arm:` e l'aggiunta di `overlap-batch-max`. Non toccano l'ambiente ⇒ **non possono cambiare lo SHA**.
3. **Le 12 P1**, in un solo passaggio (il cancello è unico e vale per tutte).
4. **Le 9 P2**, secondo passaggio.
5. **Pulizia**: cancellare le righe 250 e 264 (leve morte). ⚠ Non è neutra per definizione — la 264
   *cancella* una variabile; se una env `LLAMA_DSV4_PREFILL_FATTN_Q_TILE` fosse presente nell'ambiente
   e nessuno la leggesse, l'effetto resta nullo, ma **va fatta in un passaggio separato col suo
   cancello**, non insieme alle altre.
6. **Le GIALLE**: non ora. Vanno assorbite dalla proposta strutturale del §4, non parametrizzate a mano.

### 3.4 CANCELLO DI NON-REGRESSIONE

**Pre-cancello a costo zero, PRIMA di accendere la macchina** (pura PowerShell, nessuna GPU):
dot-source il lanciatore vecchio e il nuovo, chiamare `Set-SotaEnvironment 3 '2'` in due processi
distinti, `Get-ChildItem Env: | Sort-Object Name` in due file, e pretendere un **diff vuoto**.
Se il diff non è vuoto, il lavoro è sbagliato e non si è ancora bruciato un load da 86 GiB.

**Cancello vero, a macchina ferma:**

| banco | comando | SHA che deve tornare |
|---|---|---|
| **corto 0731** | `run_porto_hot.ps1`, **nessun parametro nuovo passato** | `AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11` |
| **lungo Vision A** | `vl_arm.ps1 -Braccio vision_A`, **nessun parametro nuovo passato** | `B2B8F84E96ED34679C53E1F194B48DB4BE54C1789462DFFAE8ACD43169FFEE8D` |

Condizioni al contorno, non negoziabili:
- **bit-esatto, non «in banda»**: il cancello è lo SHA identico, non il t/s (il t/s serve solo a dire
  che non si è rotto qualcosa di grosso: banda ±3%).
- **la prova di neutralità è «non passare nulla»** — è esattamente il ruolo del braccio `ctrl0731`
  descritto in `vl_arm.ps1:14-18`. Passare i nuovi parametri ai loro difetti **non è** la stessa prova.
- **i difetti dei nuovi parametri devono essere identici ai letterali attuali**, verificabili
  meccanicamente: per ogni voce, il difetto del param block deve combaciare col letterale che stava
  nel backup `.bak_20260902_pre_bonifica`. Questo confronto si fa a occhio sul diff, ed è il motivo
  per cui il pattern di casa tiene **una riga di commento con il letterale d'origine**.
- **testimone obbligatorio prima di lasciar correre**: nel `server.log` la riga
  `manifesto/<gruppo>: … NOME=<valore>(E)`. La `(E)` viene da `getenv()!=nullptr`
  (`server.cpp:236`), non dal valore ⇒ `0(E)` prova che la variabile *è impostata a zero*, non assente.
  ⚠ Per le 5 ROSSE assenti dalla tabella (`MASSA_AMMISSIONE`, `MASSA_CORSIE`, `FORK_RIUSA_SLOT`,
  `PREFILL_LAYER_STAGING`, `PREFILL_LAYER_SPLIT`) **questo testimone non esiste**: per loro il campo
  nella riga `arm:` è l'*unico* testimone, oppure si chiude anche il debito gemello del §5.
- **costo macchina**: 2 load (1 corto ≈ pochi minuti, 1 lungo ≈ 1 h), a load freddo, con il cancello
  di quiete 3×40 s nello stesso processo del lancio.

---

## §4. PROPOSTA STRUTTURALE — valutazione onesta

### Il reperto che decide: il pattern (b) ESISTE GIÀ IN CASA e ha già prodotto ancore ratificate
`run_porto_hot.ps1` (il banco corto, mtime 31/8 04:59:45) inchioda **46 env** esattamente come il
lungo — ma alle righe **107-113** ha un punto di override unico:

```powershell
if ($Extra) {
    foreach ($entry in ($Extra -split ';')) {
        if ($entry -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2])
        }
    }
}
```
applicato **dopo** il blocco inchiodato. È il banco che ha prodotto `AD3D3770…` e
`V-ANCORA-CORTO-A 28ADE339…`. **Il lungo non ha mai avuto questo meccanismo**: è per questo che le
nove trappole sono nate tutte di là.

### (a) «rispetta l'ambiente esistente» — **DA RESPINGERE**
*Forma*: `if ($null -eq $env:X) { $env:X = 'valore' }` su tutte e 44, o un helper `Set-SeAssente`.
**Pro**: immune per costruzione, ~44 modifiche meccaniche, nessun parametro nuovo mai più.
**Contro, e sono decisivi**:
- **inverte il contratto e sposta il danno sull'ANCORA.** Oggi il modo di fallire è *falso negativo*:
  chiedi la leva, misuri la SOTA — sgradevole, ma **rilevabile** (il t/s non si muove e lo SHA combacia
  con l'ancora). Con (a) il modo di fallire diventa *falso positivo*: una `LLAMA_CACHE_ESPERTI_FORK=0`
  rimasta in una shell interattiva da un esperimento precedente **avvelena silenziosamente il
  controllo**, e con lui l'ancora. Tutto il metodo di casa poggia sull'idea che l'ancora sia
  riproducibile **da una shell sporca**: (a) toglie proprio quella garanzia.
- **rompe ogni script esistente che si affida alla ripulitura**. I bracci ripuliscono a mano solo le
  leve *che il lanciatore non nomina* (`r57:37-41`, `r58:48-53`, `r59:67-73`, `p2:43-49`, `sw:66-72`,
  `vl:95-102`): per le 44 nominate si fidano della sovrascrittura. Con (a) andrebbero riscritti tutti
  e nove, e ognuno diventerebbe un punto di rottura nuovo.
- l'env-interruttore per il comportamento attuale sarebbe **essa stessa una leva che nessuno stampa**:
  la trappola si riproduce un livello più su.
**Rischio di regressione**: **ALTO sulle ancore**, basso sul singolo braccio. **Righe**: ~44 + 1 helper.

### (b) hash-table dei difetti + un unico punto di override — **DA SCEGLIERE**
*Forma*:
```powershell
$difetti = [ordered]@{ 'LLAMA_MAPPED_IBRIDO'='1'; 'LLAMA_CACHE_ESPERTI_BATTITO'='45'; ... }   # le 44
foreach ($k in $difetti.Keys) { [Environment]::SetEnvironmentVariable($k, $difetti[$k]) }
foreach ($e in ($Override -split ';' | Where-Object { $_ })) {
    $n,$v = $e -split '=',2
    if (-not $difetti.Contains($n.Trim())) { throw "override su env sconosciuta: '$n'" }   # <- la differenza da -Extra
    [Environment]::SetEnvironmentVariable($n.Trim(), $v)
    Note "OVERRIDE: $($n.Trim())=$v (difetto era $($difetti[$n.Trim()]))"
}
```
**Pro**:
- **conserva il contratto «tabula rasa»** ⇒ le ancore restano al sicuro (il difetto di (a));
- **un solo parametro copre tutte e 44 per sempre**: fine della parametrizzazione a una a una, e la
  trappola n.10 non può nascere;
- **è già validato in casa** (`-Extra` del corto) su ancore ratificate;
- rende **gratuita la (c)**: la tabella *è* la lista da stampare;
- il `throw` su nome sconosciuto è **l'unico miglioramento necessario** rispetto a `-Extra`, che oggi
  accetta in silenzio un nome storpiato (`LLAMA_CACHE_ESPERTI_ACCEPTMOE` invece di `LLAMA_ACCEPTMOE`
  è **già costato una corsa muta**, ledger §34).
**Contro**:
- è una **riscrittura dell'intera funzione** (66 righe → ~50): la prova di neutralità non è più
  «leggi tre righe di diff», è il cancello bit-esatto + il pre-cancello meccanico del §3.4;
- i 17 parametri tipizzati esistenti **vanno conservati** (portano `ValidateSet`, che una tabella di
  stringhe perde): convivenza tabella + parametri, con i parametri applicati **dopo** la tabella e
  **prima** dell'override;
- l'ordine conta per il valore derivato (`$packetizerActive`): va calcolato prima della tabella.
**Rischio**: **MEDIO ma interamente coperto dal cancello** — senza `-Override` l'ambiente emesso deve
essere byte-identico, e questo si verifica **prima di accendere la macchina** (§3.4). **Righe**: la
funzione riscritta (~-66/+50) + 1 parametro + il blocco override (~8).

### (c) stampare TUTTE le env impostate — **DA FARE, ma è complemento, non cura**
*Forma*: dopo `Set-SotaEnvironment`, iterare la tabella ed emettere `manifesto-lanciatore/<gruppo>: …`.
**Pro**: costo ~4 righe, **rischio di regressione ZERO** (non cambia comportamento), e copre proprio
le **14 env che la tabella del server non stampa** — cioè il buco che nessun'altra misura chiude.
**Contro**: **non impedisce nulla.** Trasforma una trappola silenziosa in una trappola rumorosa solo
se qualcuno legge la riga; e 44 campi in coda alla riga `arm:` sono un muro di testo. Da sola non
sarebbe bastata a fermare nessuna delle nove.

### Raccomandazione
**(b) + (c), insieme, in un unico intervento a macchina ferma. (a) respinta.**
- **(b)** è il meccanismo: rende impossibile la trappola n.10 senza toccare il contratto su cui
  poggiano le ancore, e riusa un pattern che in casa ha già prodotto SHA ratificati.
- **(c)** è il testimone: la firma della trappola («ho chiesto un valore che non compare nella lista
  emessa») diventa un diff stampato, e copre le 14 invisibili al manifesto del server.
- **(a)** protegge il braccio al prezzo dell'ancora: scambia un errore rilevabile con uno che
  contamina il riferimento. È il baratto sbagliato per questo progetto.

**Il rischio che (b)+(c) introduce, dichiarato**: la neutralità non è più ispezionabile a occhio su
tre righe di diff — è una riscrittura, e la sua prova sta tutta nel cancello. Mitigazione obbligatoria:
il **pre-cancello meccanico env-diff** del §3.4 (costo zero, zero GPU) *prima* dei due load bit-esatti.
Secondo rischio: un nome di override storpiato sarebbe un no-op silenzioso — mitigato dal `throw`, che
è la ragione per cui (b) non è un semplice copia-incolla di `-Extra`.

**Sequenza pratica**, in funzione della finestra di macchina ferma disponibile:
- **finestra ≥ ~1,5 h** → fare direttamente **(b)+(c)** e saltare il §3: i 21 parametri diventano
  superflui (un braccio scriverà `-Override 'LLAMA_OVERLAP_PIN=0'`) e si evitano 43 righe usa-e-getta.
- **finestra breve** → fare solo le ROSSE P1 richieste dal **prossimo** braccio, col pattern del §3,
  più le due correzioni a rischio zero del §3.3 punto 2, e rimandare la struttura.

---

## §5. COLLEGAMENTO AL DEBITO GEMELLO (`manifesto_check.py`)

Sono **due lavori distinti con un'unica invariante**. `manifesto_check.py`
(`D:\llama-subtract\scripts\manifesto_check.py`, mtime **2026-08-12 11:23:14**, 5.276 byte — presente
anche in `D:\llama-overlap\scripts\`; **nessun `.yml`/`.ps1`/`.sh`/`.cmake` del fork lo invoca**,
confermato per grep ⇒ «non gira in nessun cancello» è vero sul disco) guarda il **lato server**:
*ogni env che il binario legge deve comparire nella tabella stampata*. La bonifica del lanciatore
guarda il **lato client**: *ogni env che il lanciatore scrive deve essere sovrascrivibile e stampata*.
Nessuna delle due implica l'altra, e questo audit lo misura: **14** delle 62 env del lanciatore sono
assenti dalla tabella del server (le avrebbe prese la guardia, se girasse), mentre **44** sono nella
tabella eppure restano non sovrascrivibili (su queste la guardia è cieca — è esattamente il buco che
è costato le nove trappole). L'invariante condivisa è una sola: *un valore che decide una misura deve
essere visibile e modificabile nel record di lancio*. Conseguenza operativa: **due patch, in due
alberi diversi, ma un cancello solo** — un preflight che (1) esegue `manifesto_check.py` e (2) diffa
la tabella emessa dal lanciatore contro le righe `manifesto/…` del `server.log`; se la proposta (b)+(c)
passa, quel diff è meccanico e la riconciliazione del manifesto smette di essere un lavoro manuale.
