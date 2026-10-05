# HANDOFF Strata 2080 Ti — 5 ottobre 2026, sera

Documento autosufficiente per riprendere il lavoro da un'altra chat. Misure e dettagli completi:
`corse_2080ti/20261004_routed_keep/RESULTS.md` (sezioni del 5/10), `corse_2080ti/20261004_kernel_profile/RESULTS.md`,
`ALLINEAMENTO_0139_5_OTTOBRE.md`. Script di questa giornata: `corse_2080ti/20261005_handoff/script/`.

## 0. In breve

- **Daily in produzione**: 0.1.39 r1 (`D:\ds4_work\strata\Strata\build-0139-daily`, exe `dd82377a…`), invariato
  oggi pomeriggio. Release `v0.1.39-sm75-20261005-r1`.
- **Candidato r2 pronto e pubblicato nel fork** (`main` `d5c049c`): PR 904 + Encapsulate + diagnostica PLE + merge v2
  (#910) + kernel Q2_0 esatto. Tutto **identico bit per bit** a posizionamento fisso; configurazione con nucleo
  elastico adattivo e DMA. A 131k L01 48–51 / L02 43–48 t/s: nel rumore rispetto al main precedente e al Daily r1
  (51,4 / 44,2), ben sopra la 0.1.38 (38,7 / 38,0).
- **Stallo del prefill trovato**: la tabella PLE (26,8 GB) sta su C:, NVMe senza DRAM pieno al 96%; ogni tanto il
  disco rallenta ~50x per minuti. L'utente ha delegato a un'altra chat la liberazione di spazio su C:.
- **Prossimi passi, in ordine** (§6): A/B della tabella su D: dopo la pulizia → benchmark notturno a turni (B = r2,
  A = Daily) quando l'utente va a dormire → release 0.1.39-r2 → valutazione di #930 e #934.

## 1. Regole che valgono sempre

Dal `CLAUDE.md` globale e dalla memoria (`feedback_strata_*`):

- Italiano, utente chiamato **Grandissimo**, conclusione in cima, risposte brevi; una riga di stato ogni 2–3 comandi.
- Si lavora su `main` (fork). Prima di toccare un repo: `git branch --show-current` e `git status --short --branch`.
  Commit piccoli con pathspec espliciti (mai `git add .`), formato `OPUS-SEZIONE-Descrizione` +
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, `git fetch` + `git log HEAD..origin/main` prima del push,
  push subito. Mai force-push o riscritture. Niente lavoro lasciato solo su disco.
- **Esattezza prima**: si porta nel Daily tutto cio' che non altera output/perplessita'. Le leve che cambiano
  l'output (esperti freddi Q2_0, scarto esperti, gate-first) sono «ultima spiaggia», non da fare ora.
- **Protocollo A/B**: sempre **prima B** (anche due volte), **poi A**; se B non promette, A si salta. Test rapidi a
  contesto realistico: L01/L02 a 131k. Il test piu' vero e' la conversazione a turni fino a ~130k: solo come
  benchmark finale, **la sera quando l'utente dice che va a dormire**. Prompt corti: misure senza senso.
- I ~2,7 GB di VRAM usati dagli altri programmi non si toccano (l'elastica esiste per questo).
- **Pubblicare sempre** i Daily validati (release GitHub del fork autorizzata in modo permanente).
- Niente impostazioni di sistema (pagefile, BIOS, driver, ibernazione): le fa l'utente. Download: chiedere con nome,
  fonte e dimensione. Cancellazioni: conferma esplicita.
- `TaskStop` non uccide i processi figli: fermare a mano `bash`, `python run_*` e `strata.exe` (PowerShell
  `Stop-Process` sui PID verificati).

## 2. Macchina

RTX 2080 Ti modificata 22 GB (PCIe 3.0 x16, solo Gen3), Ryzen 7 5800X (Zen 3, AVX2), 96 GB DDR4 a 3000 MT/s (4 moduli
misti, ~34 GB/s), Windows 11, alimentatore 1300 W. Dischi: **C:** Lexar EQ790 1 TB NVMe senza DRAM (sistema;
40,7 GB liberi il 5/10 pomeriggio); **D:** EMTEC X160 1 TB SATA (369 GB liberi). Budget WDDM: il budget per processo
scende mentre il processo cresce (21,5 → ~18–19 GB). In arrivo un adattatore Oculink (3060 come GPU d'appoggio);
valutata piattaforma AM5 (Ryzen 7 7700/7900X3D, DDR5 2x48 GB, X870/B650).

## 3. Repository e percorsi

| cosa | percorso | stato al 5/10 sera |
|---|---|---|
| fork (lavoro) | `C:\Users\imanu\source\repos\Strata-2080Ti-core`, branch `main`, origin `imanu86/Strata-2080Ti` | `d5c049c`, pulito, pubblicato |
| build di laboratorio del fork | `…\Strata-2080Ti-core\build-sm75` (Release, sm_75, test accesi) | contiene r2 + `attn_merge_parity`, `q2_exact_parity`, `pool_quant_parity`, `cpu_format_bench` |
| checkout con `upstream` (Niko1221/Strata) | `C:\Users\imanu\source\repos\Strata-2080Ti` | branch `port/0139`, pulito; serve per `git fetch upstream` e i controlli periodici |
| checkout del Daily | `D:\ds4_work\strata\Strata`, `main` `46aa04b` | 48 file non tracciati da preservare |
| eseguibile Daily | `D:\ds4_work\strata\Strata\build-0139-daily\strata.exe` | sha `dd82377ab682108b…` |
| config Daily | `D:\ds4_work\strata\Strata\strata-2080ti-sota.json` | `--mtp …\mtp\rt_it48k`; env: `STRATA_WATCHDOG_S=240`, `STRATA_PARALLEL_INTERMEDIATE_QUANT=0`, `STRATA_PREFILL_EXACT_SMALL=1`, `STRATA_QSA_PREFILL_MULTI=1` |
| lanciatore | `C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat` | punta a `build-0139-daily` |
| punto di ripristino 0.1.39 | `D:\ds4_work\strata\ripristini\20261005_093653_allineamento039` | bundle repo, config, BAT, non tracciati |
| ricerca | `C:\Users\imanu\source\repos\moe-aggressive-commit`, branch `research/ds4-iq1-subbit-tier-planner` | questo documento; `cpu_onetok_iq2xxs.txt` modificato da prima e cartelle non tracciate (`.codex_runs` ecc.): non toccare |
| modello, shard 1 (esperti nativi) | `C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf` | 43,8 GB |
| modello, shard 2 (tabella PLE) | `C:\Users\imanu\Downloads\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf` | 26,8 GB, letta a righe dall'SSD |
| pack, MTP, profilo | `D:\ds4_work\strata\Strata-data\packs\iq3_xxs`, `…\Strata-data\mtp\rt_it48k`, `D:\ds4_work\strata\Strata\data\expert-profile.bin` | |
| memoria | `C:\Users\imanu\.claude\projects\C--Users-imanu-source-repos-cgc-ia-pipeline\memory\` | `feedback_strata_realistic_context`, `feedback_strata_publish_releases`, `feedback_strata_exactness_and_ds4_first`, `project_strata_retest_with_new_hardware`, `project_strata_ple_ssd_stall` |

Argomenti del Daily (config): `--pack … --native <shard1> --ple-gguf <shard2> --expert-profile … --expert-cache auto
--prefill auto --spec 4 --spec-min-p 0.5 --mtp …\rt_it48k --max-context 262144 --kv int8 --kv-resident 32768
--vram-reserve-mib 1393 --elastic --prompt-cache-tail --prompt-cache-every 16384 --prompt-cache-file
D:\ds4_work\strata\sota\prompt-prefix-v1.bin`.

## 4. Fatto il 5 ottobre

Commit del fork in ordine (tutti su `origin/main`):

| commit | cosa | verdetto |
|---|---|---|
| `73cb2d4`, `46aa04b` | upstream v0.1.39 nel fork; manifest e validazione | **Daily 0.1.39 r1** installato e pubblicato: L01 51,4 / L02 44,2 t/s contro 38,7 / 38,0 della 0.1.38 |
| `5646233`, `f26a46e` | kernel IQ2_XXS a token singolo (laboratorio, `cpu_format_bench onetok`) | identico a ggml; varianti gather/vsign piu' lente su Zen 3: nessun guadagno |
| `0f3ffb3` | PR upstream #904 (Hardin22): rami del grafo, accodamenti in batch | identico bit per bit; +2–5% |
| `f0071e7` | Encapsulate `6784a365` (Karoly Sardi): kernel QSA del decode | identico bit per bit; bozza da 3,7 a 3,0 ms/finestra |
| `2d1e452` | manifest di laboratorio | |
| `3d702c7`, `099f88a` | **diagnostica PLE**: media, massimo e letture >100 ms su tutte le letture; riga per i chunk che aspettano >1 s | solo stampe |
| `3effa9d` | **merge v2** (#910, Hardin22 `b1f03d33`), `STRATA_ATTN_MERGE_V2` attivo, `STRATA_MTP_KV` opt-in spento | 768/768 parita' sul 2080 Ti, TF fisso identico; bozza -0,3 ms; totale nel rumore |
| `c3fc8f3` | **kernel Q2_0 AVX2 esatto** (al posto della #706, che cambia l'arrotondamento); `STRATA_Q2_LEGACY=1` = vecchio | 504 casi + 64 del pool + TF fisso identici; pool reale -4% (down Q2_0); a 131k ~0,5% |
| `d5c049c` | manifest di laboratorio `r2cand-20261005.json` | `check_source.py` SOURCE_OK |

Valutazioni chiuse (nessun port): `--pcie-frac` automatico gia' ottimo; prefetch PCIe dello strato successivo
(`STRATA_PREFETCH_NEXT`, nel fork, spento) non paga su PCIe 3; bozze MTP piu' aggressive (`--spec-min-p 0.3`) non
pagano oggi; cache esperti piu' grande: nessun guadagno a 131k; formato in RAM (IQ3_S, IQ4) non e' una leva di
velocita' CPU; **#706** (Q2_0 bit-plane) non identica e senza guadagno a 131k; **#764** (`STRATA_ADAPT_LAG`) e tier
piu' vivace senza guadagno; **#903** (chunk uguali) a 131k lascia il taglio identico (16 x 8192 + 176, sotto 1024
resta la coda corta). Nucleo elastico adattivo (`STRATA_ELASTIC_CORE_ADAPT=1`): piccolo positivo. DMA (`--pcie-mode
dma`): identico bit per bit, L02 +3–7%, rischio blocco del driver (issue upstream #31) da provare nella notte.

## 5. Candidato 0.1.39-r2

- Sorgente: fork `main` `d5c049c` (codice = `c3fc8f3`). **Aggiornato il 5/10 sera**: `main` `52a39e5` (codice =
  `862c18a`, + PR #930 e `iq256_dump`), eseguibile `build-pr930` (sha `c69ed166…`); misure in `RESULTS.md` «PR 930».
- Eseguibile di laboratorio: `corse_2080ti/20261004_routed_keep/build-r2cand/strata.exe` (sha `404cb28c486380ba…`,
  `build.json`).
- Configurazione candidata = Daily + `STRATA_ELASTIC_CORE_ADAPT=1` (env) + `--pcie-mode dma` (argomento).
- Misure a 131k (`LR-*`): L01 50,6 / 48,1, L02 43,3 / 44,7 t/s contro `build-plediag` 49,5 / 47,6 (rumore: le L02 di B
  hanno avuto piu' esperti sulla CPU). Teacher forcing fisso `TFX-r2-*` identico a `TFX-enc-*`.
- Non ancora fatto: build shipping, CTest completa, test server, benchmark a turni, prova di resistenza DMA.

## 6. Da fare, in ordine

### 6.1 Dopo la pulizia di C: — tabella PLE su D: (A/B)

**Fatto il 5/10 sera.** Copia verificata, A/B passato (D: prefill 135 s stabile; C: dopo la pulizia ancora in stallo,
294–492 s), Daily r1 spostato su D: con l'ok dell'utente e controllato sulla 8100 (salute, oracolo JSON, riga
`PLE on … D:\…`). Il config ha anche due `--native-dense-gguf` (shard 1 in Downloads, shard 2 su D:): col solo
`--ple-gguf` il motore non parte. Dettagli in `corse_2080ti/20261004_routed_keep/RESULTS.md` «Tabella PLE su D:» e
`corse_2080ti/20261005_ple_d/`; ripristino `D:\ds4_work\strata\ripristini\20261005_162333_ple_d`. Da qui in poi i
banchi che leggono il config del Daily (anche `run_turns.py`) usano la tabella su D:. Piano originale sotto.

Prima: `Get-PSDrive C,D` (C: almeno 15–20% libero e nessuna copia/scrittura in corso). L'utente ha gia' approvato la
**copia** (non lo spostamento) dello shard 2 su D:.

1. Copia con verifica: `D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf`
   (cartella nuova; confrontare sha256 di origine e copia). Non lanciare test durante la copia.
2. A/B a 131k, configurazione candidata (`$CAND` sotto), **B prima due volte**:
   - B: `python -u run_long.py --name LPD-d1 --build build-r2cand $CAND --set-opt=--ple-gguf=D:\ds4_work\strata\Strata-data\gguf\Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00002-of-00002.gguf`
     e poi `LPD-d2`;
   - A: `python -u run_long.py --name LPD-c --build build-r2cand $CAND` (tabella su C:).
   - Controllare nel log che compaia `strata generate: PLE on, table 320001536 rows of D:\…` (shard 2 letto da D:;
     verificare che l'avvio non cerchi lo shard 2 accanto allo shard 1).
3. Criteri: prefill L01 entro ±3% di A (~130 s); L01/L02 decode nel rumore; `ple io` di B con media letture e
   attesa totale (~4–6 s su C: sano) senza righe `waited`; in decode il delta `blocked` tra `decode PLE before/after`
   resta di qualche decina di ms su 1024 token.
4. Se passa: proporre all'utente (non farlo da soli) di puntare `--ple-gguf` del config Daily su D: (ripristino =
   rimettere il percorso). Se C: liberato basta, si puo' anche restare su C: e osservare gli stalli con la diagnostica
   nelle corse successive.

### 6.2 Benchmark finale a turni — solo quando l'utente va a dormire

`run_turns.py` (cartella `20261004_routed_keep`): turno 1 ~12k token di codice, poi un turno per richiesta lunga
(`--gen 14000`) fino a `--max-context 130000`, 10 turni. Ore di macchina: lanciare in background, B poi A:

- B (r2): `python -u run_turns.py --name TURNI-r2 --build build-pr930 --env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma`
  (aggiornato il 5/10 sera: `build-pr930` = r2 + PR #930, identica bit per bit; fork `862c18a`)
- A (Daily): `python -u run_turns.py --name TURNI-daily --daily-exe --env STRATA_ARENA_PIN_GIB=64`

Vale anche come **prova di resistenza DMA** (#31): se il motore si blocca (nessun avanzamento per minuti, driver
che non risponde), annotare e ripiegare su `--pcie-mode` automatico (copy kernel) per la r2. Lettura: t/s per turno,
prefill per turno, righe `decode timing`, `ple io`, eventuali `waited`.

### 6.3 Release Daily 0.1.39-r2

Procedura gia' collaudata: `corse_2080ti/20261005_daily0139/` (prepare → build → manifest → install → check →
publish). Copiarla in una cartella nuova (es. `20261006_daily0139r2/`) e adattare nomi e versioni:

1. `prepare`: fork pulito a HEAD, punto di ripristino (bundle dei due repo, config, BAT, manifest, non tracciati),
   `git archive` del commit.
2. `build`: shipping sm_75 da sorgente congelata; CTest (8 test di prima + `attn_merge_parity` + `q2_exact_parity`),
   `pool_quant_parity` sul GGUF reale, test server (2 errori noti non del fork: `test_winjob` legge `tasklist` come
   UTF-8 su Windows italiano; `test_responses` json_schema 502 fallisce identico su upstream 0.1.39). Lo script 0.1.39
   asseriva sui test server: il `build.json` era stato scritto a mano.
3. `manifest`: `source-manifest.json` nuovo (versione r2), i precedenti come storici; manifest di laboratorio come
   storici.
4. `install`: `build-0139r2-daily`, config con `STRATA_ELASTIC_CORE_ADAPT=1` in env e `--pcie-mode dma` negli
   argomenti (solo se la notte e' passata), righe di intestazione del BAT; cambio atomico con ripristino.
5. `check`: server sulla 8100, salute e oracolo JSON.
6. `publish`: release `v0.1.39-sm75-AAAAMMGG-r2` con le misure (turni, 131k, identita'), poi `ALLINEAMENTO_…`,
   `HANDOFF.md`, `lanciatori/` e memoria.

Condizioni: notte B >= A e nessun blocco; altrimenti r2 senza DMA (o senza la parte che delude).

### 6.4 PR upstream da valutare (aperte il 5/10)

- **#930** (sanastasiou): decodifica IQ3_S/IQ2_S AVX2 senza shift/mask/or per indice, 1,07–1,6x per riga. Nel nostro
  GGUF il gate/up di parte degli strati e' IQ3_S (es. strato 20: gu=21, down=42): rilevante per gli esperti su CPU.
  Provare l'identita' contro il kernel attuale con un banco come `q2_exact_parity`, poi TF fisso, poi 131k (atteso
  piccolo: la CPU calcola ~2 esperti per strato-finestra).
- **#934** (Chromadera): con `--expert-cache-per-layer` gli slot usano la dimensione reale del blob di ogni strato; sul
  nostro identico modello 146 → 194 slot per strato a parita' di VRAM (+33%). Il Daily usa la cache elastica condivisa,
  non per-strato: valutare se il principio si applica all'elastica. Cautela: oggi una cache piu' grande non ha dato
  guadagni a 131k.
- **#931**: `<|im_end|>` dentro un messaggio resta testo (correttezza del server): portare col prossimo allineamento.
- **#910 (resto), #905, #936**: pipeline su due GPU, tier asincrono, sovrapposizione dello split. Per quando c'e' la
  3060 su Oculink.
- Non portate: #903, #706, #764.

### 6.5 Righe calde della tabella PLE in RAM (idea, non iniziata)

L'utente vorrebbe parte della tabella in RAM. Mezza tabella (13 GB) non ci sta con l'arena da 64 GiB fissata. Idea
migliore: precaricare all'avvio le righe piu' frequenti nella cache di righe (oggi parte vuota a ogni avvio; 1M righe
~95 MB servirebbero fino all'82% delle letture secondo le misure upstream; dentro un prompt da 131k le ripetizioni
danno il 53,5%). Stessi byte, output identico. Serve un profilo delle righe calde (dal corpus o dalle conversazioni
reali) e un caricamento sequenziale.

### 6.6 Hardware nuovo

Con la 3060 su Oculink: provarla come cache d'appoggio (`--expert-cache-device1 auto --remote-expert-opt` oppure
`--peer-device 1`) a 131k con l'arena intera; controllare KL. Dopo ogni cambio di hardware rifare: MTP
`--spec-min-p 0.3`, `--pcie-frac`/prefetch dello strato successivo, DMA (memoria
`project_strata_retest_with_new_hardware`).

### 6.7 Da tenere d'occhio

- Stallo all'avvio una volta (oltre 300 s alla registrazione dell'arena, `TFX-dma-explain-failed-startup`).
- Stalli PLE: ora diagnosticabili (`ple io … read mean … over 100 ms`, righe `waited`).
- Controlli periodici upstream/fork (cron, sola lettura): ultimo alle 13:12Z del 5/10, upstream fermo a `6f32ec0`.

## 7. Come si testa

Cartella di lavoro dei banchi: `docs/porto/strata_adattivo/corse_2080ti/20261004_routed_keep/`. Ogni corsa scrive
`<nome>/engine.log`, `plan.json`, `result.json` (+ `logpos.tsv` per il teacher forcing). Il banco controlla che exe e
config del Daily non cambino.

**Build** (fork): `script/build_target.py` (percorso della build da adattare a `Strata-2080Ti-core\build-sm75`) o lo
snippet con `vcvars64.bat` + `cmake --build … --target strata …` (CUDA 12.6 nel PATH). Poi copiare l'exe in
`build-<nome>/` con `build.json` (`status`, `executable_sha256`, `note` col commit). Mai compilare durante una misura di
velocita' (carica la CPU).

**Livello 1 — identita' a posizionamento fisso** (prova che una modifica non cambia nulla):
`bash script/tf_fixed.sh "TFX-<nome>|--build build-<nome>"` (code ed explain, teacher = risposte `A-code`/`A-explain`,
cache fissa 5000, adattivo spento, `--pcie-frac 0.36`, niente elastica). Confronto: `logpos.tsv` uguale byte per byte a
`TFX-enc-*` (riferimento valido perche' tutto cio' che e' entrato dopo e' identico), poi
`python analyze_tf.py TFX-<nome>-code TFX-enc-code`. Due corse dello stesso exe sono identiche: qualsiasi differenza e'
la modifica.

**Livello 1b — parita' dei kernel** (in `build-sm75`): `attn_merge_parity.exe [--bench]`,
`q2_exact_parity.exe [--bench]`, `pool_quant_parity.exe <shard1>`,
`cpu_format_bench.exe <shard1> pool 400` (A con `STRATA_Q2_LEGACY=1`), `ctest`.

**Livello 2 — velocita' a 131k**: `run_long.py` (L01 = prompt da 131.248 token e 1024 generati; L02 = stesso prefisso
da 131.072 riusato + 167 nuovi). Configurazione candidata:

    CAND="--env STRATA_ARENA_PIN_GIB=64 --env STRATA_ELASTIC_CORE_ADAPT=1 --set-opt=--pcie-mode=dma"
    python -u run_long.py --name <nome> --build build-<nome> $CAND

Script pronti: `script/r2cand.sh`, `script/mergev2.sh` (identita' + B, B, A in sequenza, attesa macchina libera con
`run_keep.snapshot()`: nessun processo concorrente e >= 58 GiB di commit libero). Leggere: t/s per caso, righe
`strata decode timing` (ms/finestra, token/finestra, bozza, esperti CPU per strato-finestra), `ple io`, `waited`,
`serve: prompt … read in … ms`. Rumore tipico: ±3–5% per singola corsa; le L02 dipendono molto dal piazzamento.

**Livello 3 — conversazione a turni**: `run_turns.py` (§6.2), solo la sera.

**Manifest di laboratorio** dopo ogni modifica di sorgente nel fork (altrimenti `check_source.py` fallisce):
`script/make_lab_manifest.py` (uso nella docstring; modello: `docs/sm75/r2cand-20261005.json`).

## 8. Trappole note

- Heredoc bash con Python: `\n` dentro stringhe C/Python diventa un a-capo vero (errore C2001). Scrivere i file con lo
  strumento Write, non con heredoc.
- Python `Path.write_text` su Windows scrive CRLF: il fork e' LF (`core.autocrlf=false`). Usare `write_bytes`.
- `/tmp` in Python Windows non esiste (diventa `C:\tmp`): usare lo scratchpad o percorsi espliciti.
- Argomenti con trattino ai banchi: `--set-opt=--opzione=valore` (non `--set-opt --opzione`).
- MSYS converte percorsi tipo `/nologo`: `MSYS_NO_PATHCONV=1`.
- Percorsi oltre 260 caratteri: prefisso `\\?\` in Python.
- `rpcndr.h` definisce `small`: `#undef small` dopo `dxgi1_4.h` (gia' nel fork).
- Una scansione del disco o una copia grossa su C: durante un prefill falsa le misure (e' esattamente il carico che
  causa gli stalli).
- Lo scratchpad delle sessioni Claude (`AppData\Local\Temp\claude\…`) puo' sparire con la pulizia: gli script utili
  di questa giornata sono gia' copiati in `corse_2080ti/20261005_handoff/`.

## 9. Spazio su C: (delegato a un'altra chat)

Scansione in sola lettura del 5/10 (C: 889,9 GB usati su 930): `Documents\Codex` 313 GB (2026-09-29 cgc-infra 76,
2026-10-03 promo-r21 63, 2026-10-01 moe-aggressive 49, 2026-09-09 moe 32, 2026-09-21-fable 20); `AppData\Local\Temp\claude`
78 GB, quasi tutto nello scratchpad della sessione `…MultiPhoneControls--claude-worktrees-sweet-leakey-bb2aa7\8dbad78f…`
(67,9 GB contati due volte senza hard link: 72 copie `rel-<commit>` di **promo-platform**, sorgente + `node_modules` +
`.next/cache` webpack, 1,6 milioni di file; i 72 commit esistono tutti in `promo-platform` e su un branch remoto;
il confronto file per file con i commit non e' stato completato perche' l'utente l'ha fermato); `hiberfil.sys` 38,4 GB
(impostazione di sistema, la decide l'utente); `cgc-cockpit\artifacts` 39 GB; `moe-aggressive-commit\.codex_runs`
29 GB; pip cache 9 GB, npm cache 5 GB; in `Downloads` `t5xxl_fp16.safetensors` 9,1 GB, installer CUDA 12.6 3 GB,
`memtest86-usb.img` 1 GB. **Non toccare** i due shard del modello in `Downloads` finche' il Daily li usa.
