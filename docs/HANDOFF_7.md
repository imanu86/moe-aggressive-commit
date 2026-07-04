# HANDOFF_7 — ds4 su RTX 3060: leva-RAM + static-Q4 (ripresa a freddo)

> Documento autosufficiente per riprendere lo studio **DeepSeek-V4-Flash su RTX 3060** dopo esaurimento della chat (1M token). Scritto 2026-07-04. Fonti incorporate: `scratchpad/BRAINDUMP_SESSION2.md`, memoria `project_ds4_realtest_inflight.md`, stato live dal verificatore. Predecessore: `HANDOFF_6.md`.

---

## 1. NORD STAR + arco della sessione

**Obiettivo assoluto:** far girare **DeepSeek-V4-Flash** sulla **RTX 3060 (12GB VRAM) + 32GB RAM** dell'utente a **velocità usabile**, per **USO GENERALE**.

- Modello: **158B totali / 13B attivi** (NON 284B — corretto dalla HF API in sessione precedente; vedi ledger I-correzione-158B).
- Motore: **ds4 / DwarfStar** (di antirez).
- **Riferimento utente:** Qwen 30B gira a **25-30 t/s** sul suo HW → è il target mentale di "usabile".
- **Vincolo di scopo:** l'utente NON vuole restringere il dominio ("se va bene allargo"). Niente pruning-per-dominio come soluzione di prodotto; il pruning resta materiale-paper (studio madre `project_moe_reap_spex_closed`).
- Contesto: l'utente è **contento** anche di 100-200k token per task complessi.

**Arco delle due sessioni:**
1. (Sess. 1, HANDOFF_6) Setup 3060 via WSL, build ds4 CUDA, primo run 2-bit, eval qualità 2-bit vs 4-bit sui pod RunPod.
2. (Sess. 2, questo doc) **Scoperta della LEVA-RAM (+4× gratis)** e avvio build **static-Q4** su pod H200 per liberare VRAM e far entrare più modello in RAM.

---

## 2. LA LEVA-RAM — la scoperta chiave (+4× GRATIS)

**Intuizione dell'utente.** ds4-CUDA di default legge i pesi con **`O_DIRECT` + `posix_fadvise(POSIX_FADV_DONTNEED)`** (in `ds4_cuda.cu`, righe ~2687 e ~989). Questo **bypassa la page-cache del kernel e butta via le pagine appena lette** → la RAM da 32GB resta inutilizzata come tier caldo. Su un modello streaming-da-disco questo è lo spreco più grosso.

**Fix — 2 variabili d'ambiente:**
- **`DS4_CUDA_NO_DIRECT_IO=1`** → disattiva `O_DIRECT`, letture bufferizzate (passano dalla page-cache).
- **`DS4_CUDA_KEEP_MODEL_PAGES=1`** → salta il `fadvise`/`madvise(DONTNEED)` → le pagine dei pesi **restano in RAM**.

Con entrambe attive, la RAM diventa un **tier caldo per gli expert**: su prompt ripetuto la velocità sale man mano che la RAM si scalda.

**Numeri MISURATI** (2-bit su 3060, prompt ripetuto):
`0.49` (cold) → `1.2` → `1.4` → `1.7` → **`2.1 t/s` (4.3×)**, con ~26GB RAM in uso.

**PRECONDIZIONE WSL — obbligatoria.** `C:\Users\imanu\.wslconfig`:
```ini
[wsl2]
memory=28GB

[experimental]
autoMemoryReclaim=disabled
```
Senza `autoMemoryReclaim=disabled`, WSL **restituisce la RAM cached a Windows** → il tier caldo resta ~12GB invece di 26 e la leva non scala. **`pageReporting` NON è supportato** (era stato provato e rimosso → causa errori/ignore). Dopo modifica: `wsl --shutdown` e riavviare la distro.

**ENV ANCORA DA TESTARE** (non provate, potenziale extra oltre il 2.1):
- `DS4_CUDA_WEIGHT_CACHE` + `DS4_CUDA_WEIGHT_CACHE_LIMIT_GB=N` → cache pesi host **esplicita** (candidato #1 per spremere ancora).
- `DS4_CUDA_COPY_MODEL`
- `DS4_CUDA_STREAMING_EXPERT_CACHE_RESERVE_GB`

**Soffitto teorico stimato:** RAM-bound ~10-25 t/s (headroom = overhead page-cache WSL/vhdx + staging CUDA). Il 2.1 attuale è ancora lontano dal soffitto → c'è da spremere.

---

## 3. STATO LIVE (2026-07-04) + AZIONI URGENTI

> Aggiornato dal verificatore poche ore fa. **Budget basso — priorità: non bruciare soldi.**

### Pod attivo
- **Pod1 H200** `m44id9q34d95eo` — **`ssh root@213.186.10.12 -p 13526`** — **$3.59/h**.
- **Pod2 B200** `596e18liorr02k` — **GIÀ TERMINATO** (non compare più nella lista pods). Non fare nulla.

### Build static-Q4: IN CORSO, non finita
- Il quantize è **ancora in esecuzione**, fermo a **layer 14** (w3 192/256 experts). 1 processo `deepseek4-quantize` vivo.
- GGUF parziale: `/workspace/models/DeepSeek-V4-Flash-staticQ4.gguf` = **~26.64 GB** (24.8 GiB), timestamp Jul 4 08:29, **ancora in scrittura**. Il modello V4-Flash ha molti più layer di 14 → **manca parecchio**.
- **Nessun sentinel presente**: `BUILDQ4_DONE`, `QUANT_OK`, `QUANT_FAIL` assenti. (Nota: il braindump menzionava anche `/workspace/QUANT_OK` — stesso concetto.)

### Budget — ATTENZIONE
- Balance RunPod: **$11.34**. Costo pod: 3.59 $/h → **autonomia ~3.1h**.
- (Il braindump riportava ~$13.77 a fine sessione; ora $11.34 → il pod ha continuato a consumare.)
- **Rischio reale:** il pod può **spegnersi per balance esaurito prima che il quantize finisca** → GGUF parziale inutilizzabile. Valutare all'atto della ripresa se il build può completare entro le ~3h o se serve aggiungere credito.

### AZIONI URGENTI (in ordine)
1. **Connettiti al pod** e controlla lo stato del quantize:
   ```bash
   ssh root@213.186.10.12 -p 13526
   ls -la /workspace/models/DeepSeek-V4-Flash-staticQ4.gguf   # cresce?
   ls /workspace/{QUANT_OK,BUILDQ4_DONE,QUANT_FAIL} 2>/dev/null
   ps aux | grep deepseek4-quantize
   # log del quantize se catturato in un file, altrimenti tail dell'output del processo
   ```
2. **Se `QUANT_OK` / `BUILDQ4_DONE` presente** → **SCARICA subito** il gguf sul 3060 (vedi §5 per il metodo di copia), poi **SPEGNI il pod** (vedi sotto).
3. **Se ancora in build** → decidi in base a balance/ETA. Se il credito non basta, o aggiungi credito o accetta di perdere il build.
4. **SPEGNI il pod** appena hai il gguf (o se decidi di abbandonare):
   ```
   GraphQL podTerminate(input:{podId:"m44id9q34d95eo"})
   Bearer key da C:\Users\imanu\Desktop\Runapod.txt
   Header User-Agent browser (altrimenti 403).
   Verifica: myself { pods } → deve essere vuoto.
   ```
5. **RUOTA le chiavi** (finite nei log/transcript con `set -x`):
   - **Key RunPod** in `C:\Users\imanu\Desktop\Runapod.txt`.
   - **Token HF** in `~/.cache/huggingface/token` sul pod (loggato).

### Altro non completato
- **Generazione cyberpunk** (`berdjzoe3`): NON completata. `C:\Users\imanu\Desktop\ds4-cyberpunk-browser.html` **assente**. Nice-to-have, non prioritario.
- **Server ds4 sul 3060**: girava via WSL tenuto vivo da ssh-blocking con le env leva-RAM. Se il PC si è spento, va **rilanciato** (§4).

---

## 4. SETUP 3060 (validato, tutto funziona)

- **ds4 NON builda su Windows nativo** → usare **WSL2 Ubuntu-24.04** (glibc **2.39**). ⚠️ **Ubuntu 25.04 (glibc 2.43) FALLISCE** il build CUDA per conflitto `noexcept`. Restare su 24.04.
- **CUDA 12.8** toolkit. Build: `make cuda CUDA_ARCH=sm_86` (Ampere = 3060). `gcc-13` default ok.
- **Precondizione BIOS:** SVM Mode = Enabled (ASUS PRIME B550M-A: F7 → Advanced → CPU Configuration → SVM Mode → Enabled), per WSL2.
- Modello 2-bit copiato su **ext4 WSL**: `/root/models/ds4-2bit.gguf` (86.7GB) — copiato da `/mnt/d` che è lento. Pesi anche su Windows `D:\models\ds4\`.

### Comando server (con leva-RAM)
```bash
DS4_CUDA_NO_DIRECT_IO=1 DS4_CUDA_KEEP_MODEL_PAGES=1 \
ds4-server -m /root/models/ds4-2bit.gguf \
  --cuda --ssd-streaming --ssd-streaming-cache-experts 1GB \
  --prefill-chunk 512 -c 6144 \
  --host 0.0.0.0 --port 8000 --cors
```
- **`--prefill-chunk 512` ESSENZIALE.** Col default 4096 la cache-expert veniva **disabilitata** (reserve 6GB > VRAM libera) → andava **OOM**.
- **VINCOLO #1 (dal sim, confermato):** su 12GB VRAM lo **statico (~10GB) soffoca la cache-expert** (resta ~1-2GB = ~151 expert). → **è il motivo dello static-Q4** (statico più piccolo = più VRAM per la cache-expert).

### No-think (per-richiesta)
V4-Flash è un modello **reasoning** (pensa di default). Per disattivare il thinking, **nel body della richiesta**:
```json
{ "think": false, "thinking": { "type": "disabled" } }
```
(oppure `model: "deepseek-chat"`). Il flag `--nothink` è del **CLI `ds4`**, NON del server. Con think ON serve budget-token alto + strip di `</think>`.

### Client / script
- Chat UI: `C:\Users\imanu\Desktop\ds4-chat.html` (toggle think, streaming). ⚠️ Il contatore t/s in pagina è **inaffidabile** (conta chunk SSE); il numero **vero** è nel log del server: riga `decoding X t/s`.
- Restart server: `scratchpad/ds4_server_restart.sh` (contiene già le env leva-RAM).
- Il server va tenuto vivo da un **ssh-blocking** (o processo in foreground); se il PC si spegne cade.

---

## 5. RICETTA static-Q4 (comando completo + gotcha)

**Tool:** `gguf-tools/deepseek4-quantize` (plain C, gira su **CPU**). Build: `make -C gguf-tools`.
**Input:** safetensors HF originali (`deepseek-ai/DeepSeek-V4-Flash`, 159GB fp8, 46 shard) + un **template** (il gguf 2bit-imatrix, da cui prende struttura/imatrix).

```bash
gguf-tools/deepseek4-quantize \
  --hf /workspace/hf \
  --template <2bit-imatrix.gguf> \
  --out /workspace/models/DeepSeek-V4-Flash-staticQ4.gguf \
  --routed-w1 iq2_xxs --routed-w2 q2_k --routed-w3 iq2_xxs \
  --attention q4_k --attention-proj q4_k --shared q4_k \
  --embedding q4_k --output q4_k --dense q4_k \
  --threads 96
```

**Cosa fa / perché.** Porta lo **statico** (HC/Compressor/Indexer che erano F16, attn/shared/out che erano Q8) → **Q4_K**: statico ~10GB → **~5GB** VRAM. Gli **expert routed restano 2-bit** (iq2_xxs/q2_k, come il 2-bit imatrix). Risultato: **libera ~5GB VRAM per la cache-expert** + modello complessivo più piccolo → **più % entra nei 26GB di RAM** → la **leva-RAM scalda di più**. Output atteso complessivo **~50GB**.

**GOTCHA di build (osservati):**
- **Download HF via curl seriale si STALLA** (throttle HF) → usare **parallelo**: `xargs -P 4 curl -C -` (resume + 4 stream).
- **`huggingface_hub` ROTTO** sull'immagine del pod → **non usarlo**; scaricare con **curl diretto + `Authorization: Bearer <token HF>`**.
- **Disco pieno.** Volume 320GB si riempie: 2-bit 86.7 + 4-bit 164 + hf 159. → **cancellare il 4-bit**. ⚠️ **TRAPPOLA:** un `ds4-server` residuo teneva il file 4-bit **aperto** (`deleted` ma held-open) → lo spazio **NON si libera** finché non **killi il processo**. Controlla `lsof | grep deleted` se `df` non torna.

---

## 6. NUMERI MISURATI

### Velocità (2-bit, RTX 3060)
| Config | t/s |
|---|---|
| SENZA leva-RAM (WSL vhdx) | 0.73 |
| CON leva-RAM, cold | 0.49 |
| CON leva-RAM, warm (~26GB RAM) | **2.1** (4.3×) |

### Qualità (eval_gold 140, misurata su pod H200)
- **2-bit:** MATH 40/40 = **100%**; KNOWLEDGE (MMLU-hard) 34/40 = **85%**; CODING 33/60 = **55%** — ma **CONFUSO**: 15 troncamenti + grader fragile, CI ampi.
- **4-bit PARZIALE** (fermato a 49): CODING 37/49 = **75%**.
- → Il 2-bit **degrada il coding ~20pt**. **DA CONFERMARE** con: full 4-bit + grading pulito + agreement appaiato + ispezione dei fail.

### Simulazioni (`sim_3060_static.py`, ancorato a 0.49)
- static-Q4 su WSL: ~1.4 t/s; su NVMe nativo: ~5.6; +temp-experts: ~10. Il path I/O (vhdx vs NVMe) pesa ~4×.
- ⚠️ La sim è **pre-scoperta leva-RAM**: la leva già dà 2.1 reali → il soffitto RAM-bound teorico è **~10-25 t/s** (headroom da spremere: overhead page-cache WSL + staging CUDA). Le sim vanno **ri-ancorate**.

---

## 7. CONTESTO

- V4-Flash è **nativo 1M token**.
- **KV COMPRESSA** (CSA/HCA) ≈ **25KB/token** → a ctx 6144 = **151MB**.
- Sul 3060: **16-32k comodi** in VRAM; **100-200k+** con **`--kv-disk-dir`** (KV-su-disco di DwarfStar). Prefill lento (pattern load-once-then-interact).
- **Static-Q4 alza il tetto** del contesto-in-VRAM (libera VRAM). L'utente è contento con 100-200k per task complessi.

---

## 8. ROADMAP / NEXT (in ordine)

1. **static-Q4 → test sul 3060.** Appena `QUANT_OK`: scarica il gguf (`D:\models\ds4\` o `/root/models`), lancia col comando server + env leva-RAM, **misura**: velocità (statico Q4 → cache-expert più grande + più RAM-fit) e **qualità** (l'**attention Q4** degrada rispetto al Q8? → eval_gold). **Poi SPEGNI l'H200.**
2. **Tuning env aggressivo.** `DS4_CUDA_WEIGHT_CACHE` + `DS4_CUDA_WEIGHT_CACHE_LIMIT_GB`, cache-experts più grande (VRAM liberata dallo static-Q4), reserve. Spremere verso ~10-25 t/s.
3. **temperature-per-expert quant** — **IL CONTRIBUTO PAPER dell'utente.** Expert freddi a **1–1.58 bit** in base alla frequenza-routing (dati: nostri trace + REAP). **Ortogonale all'imatrix** (imatrix = qualità a taglia fissa; temp-quant = memoria). Deve **battere i baseline** (dwarf-2bit / layer-mixed / 4bit) a **parità di GB** → è la tesi del paper.
4. **DSpark vero** (non il `--mtp` base di antirez, che è "slight speedup"): confidence-head + STS + scheduler dal paper (`docs/references/DSpark_paper.txt`). Velocizza il **reasoning** (auto-predicibile) → brilla quando **compute-bound**. Base: `--mtp MTP.gguf --mtp-draft 2`; testare con **think ON**.
5. **Diagnosi fail coding** (ispeziona `eval_results_2bit.json` — era su pod effimero, forse perso → potrebbe servire ri-run). **Full 4-bit eval** per il delta pulito.
6. **RUOTA key RunPod + token HF** (§3, azione urgente 5).

---

## 9. FILE / PATH (mappa durevole)

**Memoria (persistente cross-sessione):**
- `C:\Users\imanu\.claude\projects\C--Users-imanu-source-repos\memory\project_ds4_realtest_inflight.md` (aggiornata con leva-RAM + ricetta static-Q4).
- Studio madre: `...\memory\project_moe_reap_spex_closed.md`.

**Repo `moe-aggressive-commit\docs\`:**
- `EXPERIMENTS_LEDGER.md` — I1–I11 (redundancy, speed-sim, coverage, REAP, quality-2bit, correzione 158B).
- `HANDOFF_6.md` (predecessore), **`HANDOFF_7.md`** (questo).
- `MODELS_qwen235_vs_deepseekv2.md`.
- `references/DSpark_paper.txt`.

**Script (`moe-aggressive-commit\scripts_pod\`):**
- `sim_3060_static.py` (⚠️ da ri-ancorare post leva-RAM), `reap_union_sim.py`, `expert_union_coverage.py`, `run_eval_ds4.py` (grade unit-test/exact-match/mcq), `build_eval_gold.py`, logica `deepseek4-quantize`.

**Script scratchpad:**
- `ds4_server_restart.sh` (CON le env leva-RAM), `test_rampages.sh`, `warm_and_measure.sh`, `gen_cyberpunk.sh`.
- `BRAINDUMP_SESSION2.md` (fonte di questo handoff).

**Dati / config:**
- Eval: `D:\models\eval\eval_gold.jsonl` (140 = 60 coding+test, 40 gsm8k, 40 mmlu-hard).
- Pesi 3060: `D:\models\ds4\` (2-bit imatrix 86.7GB + MTP 3.8GB) e copia ext4 `/root/models/ds4-2bit.gguf`.
- `C:\Users\imanu\.wslconfig` (28GB + autoMemoryReclaim=disabled).
- `C:\Users\imanu\Desktop\ds4-chat.html` (chat UI), `C:\Users\imanu\Desktop\Runapod.txt` (key RunPod — **DA RUOTARE**).
- Target output cyberpunk (non fatto): `C:\Users\imanu\Desktop\ds4-cyberpunk-browser.html`.

**Pod (finché vivo):** `ssh root@213.186.10.12 -p 13526` — `/workspace/models/DeepSeek-V4-Flash-staticQ4.gguf`, sentinel attesi `/workspace/{QUANT_OK,BUILDQ4_DONE,QUANT_FAIL}`, HF orig in `/workspace/hf`, token in `~/.cache/huggingface/token` (**DA RUOTARE**).
