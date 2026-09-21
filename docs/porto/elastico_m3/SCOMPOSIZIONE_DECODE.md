# Perché l'elastico era più lento di p11: è il deposito RAM (21 settembre 2026, sera)

**Conclusione.** Il runtime elastico non è lento: lo rallenta il **deposito RAM degli 8 strati**
(`LLAMA_MOE_RAM_LAYERS=8`), che costa il **13-16% del decode a 100k**. Con `LLAMA_MOE_RAM_LAYERS=0`, stessi binari,
l'adattivo fa **22,4-22,9 t/s a ~100k** contro 19,7-19,9 col deposito e 21,2 di p11 a 40 slot fissi: si torna nella
zona dei 23 t/s del 20/9, col desktop di oggi (2,0-3,2 GB di VRAM occupati da altri programmi). La banda morta di M3
su generazioni lunghe vale ±2% (rumore): la leva era un'altra. Nessuna build nuova: è una variabile d'ambiente.

## Misure (punto operativo: ~100k di contesto, 1536 token generati, greedy, senza MTP)

`banco_decode.py --run --profondita 100000 --genera 1536 --flusso`, server isolato su 127.0.0.1:8113, produzione
spenta, una corsa per braccio, in fila fra le 17:09 e le 18:15. «Regime» = mediana del ritmo sulle finestre da 128
pezzi, esclusa la prima (cache esperti fredda). Corse: `D:\ds4_work\qwen_gateway_run\20260921_17*_decode_*_L_*`.

| braccio | slot | strati nel deposito RAM | decode t/s | regime | prefill t/s |
|---|---|---|---|---|---|
| x4 (p11) | 40 fissi | — | 21,24 | 21,5 | 313 |
| M3 | 40 (tetto) | 0 | 21,82 | 21,9 | 341 |
| M3 | 40 (tetto) | 8 | 18,85 | 18,7 | 339 |
| M3 | adattivo (~61) | 8 | 19,65 | 19,5 | 334 |
| **M3** | **adattivo (~61)** | **0** | **22,87** | **22,9** | **353** |
| M2 | adattivo (55-57) | 8 | 19,86 | 20,0 | 338 |
| **M2** | **adattivo (55-57)** | **0** | **22,43** | **23,0** | **354** |
| M3 + 8 processi che occupano la CPU | adattivo | 8 | 20,08 | | 337 |
| M3 + 8 processi che occupano la CPU | adattivo | 0 | 22,10 | | 343 |

Letture:
- **Deposito RAM, a slot uguali (40): 21,82 → 18,85 = −13,6%.** In adattivo: M3 −14,1%, M2 −11,5%.
- **Il runtime elastico in sé non è più lento di p11**: a 40 slot e senza deposito fa 21,82 contro 21,24.
- **Gli slot in più valgono poco a 100k**: da 40 a ~61 slot i colpi salgono dal 62% al 73-78% (−40% di byte mancati)
  ma il decode guadagna solo il 4-5%. Il trasporto degli esperti è in gran parte sovrapposto al calcolo
  (`QWEN_MOE_OVERLAP_DOWN`): per questo «meno trasporto» non voleva dire «più veloce».
- **M3 contro M2** su generazione lunga: +2,0% senza deposito, −1,1% col deposito: rumore. Il verdetto «M3 non
  promosso» regge; M3 resta utile solo dove il desktop fa ballare molto la VRAM.
- **Il carico di CPU non c'entra**: con 8 processi occupati su 16 thread, −3% senza deposito e nessun calo col deposito.
- Il banco a 512 token sottostima: la prima finestra (cache fredda dopo il prefill) gira a 17-20 t/s, il regime
  arriva dopo ~130 token. I numeri del pomeriggio (18-19,8 t/s) erano per metà partenza a freddo.

## Da dove viene il costo (codice + contatori)

Negli strati normali i miss li legge **la GPU da sola** dalla RAM bloccata e mappata (`moe_grouped_gather_decode`,
`moe-demand.cuh:554-572`): nessun intervento dell'host, tutto asincrono. Negli 8 strati del deposito
(`moe-demand.cuh:528-553`) ogni token fa, **per strato**: copia del piano verso l'host (`cudaMemcpyAsync` D2H) →
`cudaLaunchHostFunc` **dentro lo stream di calcolo** → `ggml_cuda_ram_prepare` (`moe-ram-store.cuh:623-710`): mutex del
registro, sensore di memoria, `memcpy` dei miss dalla memoria paginabile allo staging bloccato → kernel di raccolta.
Lo stream GPU resta fermo finché la callback non torna: è un punto di sincronizzazione per strato, otto volte a token.

I contatori `RAM_STORE {...}` (stderr del server; nel banco finiscono in `logs\server.stderr.txt`) lo misurano: nel
braccio M3 del pomeriggio 12 225 chiamate di staging = 6,27 s, cioè **513 µs a chiamata × 8 = 4,1 ms a token (7,8% del
token a 100k)** di sola copia (62 GB a 10,2 GB/s); il resto del 13-16% è latenza della callback e dello stallo.
Il bat di produzione non cattura lo stderr: in produzione questi contatori non si vedono.

## Cosa si è escluso, e cosa resta aperto

- **64 slot fissi su p11 oggi non stanno in VRAM** (`…_163226_decode_x4_slot64`): 16,5 t/s a 1k, poi 7,9 a 50k e 5,6 a
  100k, prefill a 79 t/s con `qwen_prefetch: skipped, insufficient free VRAM`. La VRAM occupata dal desktop è salita
  nel pomeriggio da 2,05 a 3,2 GB (Chrome, DSH Desktop, WebView, app Claude). Il 16/9 (modello UD, 64 slot fissi,
  24-25 t/s a ogni profondità) il desktop ne occupava evidentemente molta meno. È il motivo per cui la cache adattiva
  serve; il confronto fra bracci va fatto a slot bloccati, altrimenti lo inquina il desktop.
- **Storia** (`archeologia_decode.py`, generazioni reali ≥ 100 token, mediane): 16/9 sota_X4 64 slot modello UD 24,1 t/s
  oltre 112k; 19/9 p11 40 slot GSQ-RCO 19-20,5; 20/9 stesso assetto 22,6-23,4 fino a 112k; 21/9 elastico M2 11,2 a 50-80k.
- **Gli 11 t/s dell'uso reale di oggi restano senza spiegazione.** Escluse: ridimensionamenti (pause 1,4-3,4%), sfratto
  del deposito (RAM disponibile 5-21 GiB, mai sotto i 2 GiB), campionatori/grammatiche (stessa catena del 20/9), monitor
  `watch_mtp.ps1` (c'era anche il 19-20/9), carico di CPU (provato). Al banco lo stesso M2 con la stessa
  configurazione fa 19,9 t/s. Sospetto non verificato: contesa della GPU col rendering del desktop (a server spento
  la GPU segna ~40% a 360 MHz, quasi tutto dell'app Claude e di dwm) o pagine del deposito sfoltite da Windows.
  Da verificare sul campo dopo il cambio: `archeologia_decode.py <log di produzione>`.
- Senza deposito il prefill a 100k può perdere lo staging (`qwen_prefetch` chiede 900 MiB + 512 di riserva invece di
  566 + 512, perché i tensori degli strati 0-7 sono i più grossi): visto solo quando il desktop occupava 3,2 GB
  (prefill 310/256 t/s a 50k/100k contro 392/276); nelle corse lunghe il prefill senza deposito è stato il più veloce.

## Le misure di Codex con GSQ-RCO (oltre i 25 t/s) e dove sono finite

Le chat stanno nell'app Codex, thread **«Qwen 3.8»** (id `01a099f1-9a13-73f2-a761-1f11c25a0591`, file
`~\.codex\sessions\2026\09\13\rollout-2026-09-13T10-45-42-01a099f1-….jsonl`, 73 MB, attivo fino al 21/9 mattina); in DSH
«GSQ» compare solo come nome del modello. I rapporti sono in `C:\Users\imanu\Documents\Codex\2026-09-13\rip\outputs\`:
`BENCHMARK_GSQ_20_SETTEMBRE.md`, `VRAM_ELASTICA_…`, `VARIANTE_A_CACHE_DINAMICA_…`, `DECODING_RAM_SSD_…`,
`OTTIMIZZAZIONE_RAM_SSD_…`, `MTP_RAM_…`. Banco `lungo_131k` (131.248 token, due generazioni da 1024, greedy, senza MTP),
laboratorio `work\qwen_x4_lab_20260920` (`bench_gsq.py --slots N --profile lungo_131k`), binari p11:

| quando (20/9) | assetto | decode t/s |
|---|---|---|
| mattina | p11, 40 slot fissi | 23,21 |
| mattina | p11, 64 slot fissi | 24,97 (colpi 62,9% → 73,8%; VRAM max 11,5 GB: ci stavano) |
| ~14:00 | p11, 70 slot fissi | **25,43** (minimo di VRAM fisica libera 754 MB) |
| sera | p11, 70 slot fissi, «controllo ravvicinato» | 23,06 (**stesso binario, −9,3%**) |
| sera | A1 = elastico senza deposito RAM, tetto 70 / tetto 40 | 23,07 / 21,21 |
| sera | R1/O2 = con deposito RAM | 18,7-20,6 contro 21,60 di A1: **−13,3%**, già scritto da Codex («resta overhead da recuperare») |

I numeri di oggi coincidono con quelli della sera del 20/9 (x4 a 40 slot 21,24 ≈ 21,21; adattivo senza deposito 22,87 ≈
23,07). I 25,4 sono la stessa macchina **col desktop scarico**. Misurato oggi: durante il decode il server ha l'85% del
motore GPU, il desktop il ~7% (app Claude 3,8%, dwm 2,5%, CGControl 0,6% più il 9% del decodificatore video); la VRAM
dedicata degli altri processi è passata in giornata da 2,0 a **4,4 GB** (CGControl 2,1 GB, app Claude 0,7, csrss 0,4,
Chrome 0,4, Visual Studio 0,2…). Con 40 slot FISSI e il desktop a 4,4 GB il decode è sceso da 16,1 a 12,4 t/s dentro una
sola generazione (`…_decode_x4_contesa_gpu`): è il degrado silenzioso che l'adattivo evita, ed è il candidato più serio per
gli 11 t/s dell'uso reale (non dimostrato). Conto: 25,4 → ~23 per il desktop (meno slot + ~7% di GPU), → ~20 per il deposito RAM.

## Proposta

1. **Subito, senza build:** produzione con `LLAMA_MOE_RAM_LAYERS=0` (binari M2 già promossi; M3 equivalente).
   Guadagno atteso a 100k: da ~19,9 a ~22,4-23 t/s (+13-16%). Prezzo: si perde la valvola che sfratta 5,8 GiB di
   esperti verso SSD sotto i 2 GiB di RAM disponibile; restano paginabili i 27 GiB del buffer CPU. È l'assetto di RAM
   con cui p11 ha girato il 19-20/9. Durante le corse la RAM disponibile era la stessa coi due assetti (6,7-8 GiB).
2. **Se la valvola serve (giornate con poca RAM): M4 — deposito bloccato finché non c'è pressione.** `cudaHostRegister`
   dei 24 tensori del deposito finché sono tutti residenti → gli 8 strati passano dal percorso diretto (costo zero);
   alla prima pressione di RAM: unregister + rebind sul percorso a staging di oggi, e lo sfratto funziona come ora; a
   pressione finita e pagine ripristinate si ri-blocca. Tocca `moe-ram-store.cuh`, `moe-demand.cuh`, `ggml-cuda.cu`
   (build nvcc come M2) e il rebind in `llama-moecache.cpp`; collaudo = prova del canary. Premio: la velocità del
   punto 1 con la sicurezza di oggi.
3. **Per tornare ai 25: liberare la GPU dal desktop.** 4,4 GB di VRAM e ~7% del motore GPU vanno ad altri programmi,
   CGControl (mirroring video dei telefoni) per primo. Leve dell'utente: meno flussi video aperti mentre si genera,
   accelerazione hardware spenta nelle app Electron/Chromium (Claude, DSH, Chrome), finestre ridotte a icona. Leva
   strutturale: con la 2080 Ti 22 GB in arrivo, desktop su una scheda e modello sull'altra.
4. **Oltre:** la leva successiva è MTP1 sopra l'assetto senza deposito (Codex, `MTP_RAM_20_SETTEMBRE.md`: +11% in decode a
   32k, +4,8% a 131k, pagato col −9,8% nel prefill profondo), da misurare con questo stesso banco a 100k.

## Strumenti aggiunti

- `qwen_gateway/banco_decode.py`: `--env NOME=VALORE`, `--slot N`, `--profondita`, `--genera`, `--flusso` (ritmo per
  finestre da 128 pezzi), `--carico-cpu N`, `--etichetta`; `qwen_gateway/server_locale.py`: leve e slot per corsa.
- `elastico_m3/archeologia_decode.py <log>…`: modello, slot e t/s per profondità da un log storico di llama-server.
- `elastico_m3/analizza_resize.py <server.log>`: ridimensionamenti e pause per generazione.
