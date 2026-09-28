# Strata contro il daily sulla nostra macchina — 28 settembre 2026 sera

Stesso file (Qwen3.8-Flash-Next GSQ-RCO IQ3_XXS, i due shard in `Downloads`), stessi prompt del banco P0 (L01/L02 con
prefisso a 32k e a 131k, 1024 token, greedy, ragionamento acceso), una corsa per motore, uno dopo l'altro, con gli altri
programmi dell'utente aperti come richiesto («sempre adattivo, segneremo la VRAM occupata al lancio»).

## Risultato

| | Strata (b38c183, CUDA 12.6) | daily M2 (bat di produzione, `-c 139264`) |
|---|---:|---:|
| VRAM degli altri programmi al lancio | 5.537 MiB | 4.557 MiB |
| RAM disponibile dopo il caricamento | ~21 GB | **2,0-2,3 GB** |
| cache esperti in VRAM | 702 esperti, 1,16 GiB (fissa dal lancio) | 43 slot/strato al lancio, **0 dal primo prefill in poi** |
| L01@32k: prefill freddo / decode | 294 t/s / 16,55 t/s | 365 t/s / 7,25 t/s |
| L02@32k: decode | 19,66 t/s | 7,15 t/s |
| L01@131k: prefill (parte nuova) / decode | 245 t/s (98.480 token) / 21,27 t/s | 229 t/s (102.404 token) / 7,01 t/s |
| L02@131k: decode | 21,58 t/s | 6,98 t/s |
| **decode aggregato (4 casi, 4.096 token)** | **19,55 t/s** | **7,09 t/s** |

In queste condizioni Strata genera 2,8 volte piu' veloce; il prefill e' pari (il daily +24% a 32k, Strata +7% oltre 32k).
Il L01@131k non e' un prefill del tutto freddo: entrambi riusano l'inizio del prefisso a 32k (Strata 32.768 token, il
daily 28.844), perche' `ctx131k.txt` comincia con lo stesso testo.

## Perche' il daily crolla: la cache elastica resta a 0 slot

Il daily ha una cache di 43 slot al lancio; il primo prefill la rilascia (fase di prefill di M2) e poi non ricresce piu':
555 eventi `growth_blocked_ram` e 6 `growth_cancelled_ram` con `slots=0`, mentre la VRAM libera era 7,4 GB. Il cancello e'
in `llama-moecache.cpp` (M2/M3, righe ~755 e ~782): la crescita e' negata finche' `ram_growth.allows(ram_available,
ram_valid, pending_ram_bytes)` e' falso, cioe' finche' il deposito RAM ha byte da ripristinare che non stanno nella RAM
disponibile. Con gli altri programmi aperti la RAM non torna mai sopra la soglia: tutti gli esperti passano dal PCIe per
tutta la sessione. E' il candidato piu' forte per gli «11 t/s dell'uso reale» mai spiegati del 21/9.

Col `-c 262144` del bat il daily non parte nemmeno: `cudaHostAlloc` della KV mappata (3.264 MiB) va in out of memory con
questa RAM occupata. Per l'A/B e' stato lanciato con lo stesso contesto massimo di Strata (139.264); tutto il resto e'
identico al bat (`avvia_daily_lab.py`, comando in `corse/.../comando.json`).

## Strata sul nostro hardware

- Carica in 48 s: esperti 39,97 GiB in RAM bloccata (1,18 GiB/s, pagine da 4 KB: le large pages chiedono un privilegio
  che non c'e'), tabella PLE da 27 GB lasciata sull'SSD. Dopo il carico restavano 1.249 MiB di VRAM libera.
- Cache fissata al lancio: VRAM libera meno 700 MiB di riserva, poi mai ridimensionata. Se gli altri programmi crescono
  oltre la riserva, WDDM pagina e una richiesta puo' fermarsi (il loro watchdog riavvia il motore). In questa corsa non e'
  successo.
- MTP: bozza accettata al 67-74%, **1,56-1,92 token per passata** (dichiarati 2,35-3,52 sulla loro macchina); passata di
  verifica 116 ms al primo caso, 72 ms all'ultimo: la residenza adattiva (ogni 4 round) impara il lavoro durante la
  sessione. Con 702 esperti in VRAM quasi tutti gli esperti li calcola la CPU (7 thread + host).
- Numeri non paragonabili ai 40,5 t/s dell'utente con la 3060: lui usava IQ2_XS, 16 core, e quasi certamente piu' VRAM
  libera per la cache.

## M2g: il cancello corretto (stessa sera)

`../elastico_m2g/LEGGIMI.md`. Stessa configurazione, stessi prompt, altri programmi aperti: la cache ricresce dopo ogni
prefill (42-55 slot, zero `growth_blocked_ram`) e il decode aggregato passa da 7,09 a **17,71 t/s**; prefill 406 a 32k e
274 oltre 32k. E' il livello del daily a RAM libera (19,7-19,9 col deposito, 21/9), non un guadagno oltre quello.

## Confronto equo a regime (notte del 28/9) — la prima conclusione su Strata era sbagliata

La prima corsa di Strata era azzoppata: cache di 702 esperti perche' al lancio gli altri programmi tenevano 5,5 GB di
VRAM (picco), 4 richieste sole mentre la residenza adattiva stava ancora imparando (passata 116 → 72 ms), nessun caso di
codice. Rifatto con gli altri programmi a ~1,6 GB di VRAM per entrambi, un motore subito dopo l'altro, profilo `regime`
(8 casi di fila a 32k, L01/L02 a 131k, copia/rinomina). Strata con `--vram-reserve-mib 1032`, consigliato dal motore
stesso al lancio (con i 700 di default restavano 180 MiB liberi, «requests may stall»).

| | Strata | M2g |
|---|---:|---:|
| VRAM altri programmi al lancio | 1.652 MiB | 1.597 MiB |
| esperti in VRAM | 1.915 (3,15 GiB, fissi) | ~3.400 (71 slot/strato, elastici) |
| decode 32k, 8 casi | **31,5 t/s** | 22,4 t/s |
| decode 32k, ultimi 4 (regime) | 32,0 | 22,4 |
| decode 32k, 3 casi di codice | 30,4 | 21,9 |
| decode 131k (punto operativo) | **28,8** | 22,0 |
| decode copia/rinomina (C01/C02) | **35,3** | **11,0** (ripetuto: 11,1 / 10,9) |
| prefill freddo 32k | 497 | 480 |
| prefill oltre 32k (fino a 131k) | 415 | 314 |
| decode aggregato | **31,6** | 19,0 |

Strata e' +40% a 32k e +31% a 131k con meta' degli esperti in VRAM. Bozza MTP: 1,6-3,3 token per passata.

**Corsia CPU di Strata (`--pcie-frac 1.0` = tutti i mancanti via PCIe, come noi):** 33,1/29,3/29,3/33,8 → 27,9/25,2/25,6/
29,0 a 32k, 30,1/27,6 → 27,1/23,3 a 131k: **la corsia CPU vale il 10-16%** sulla nostra macchina (a parita' di token per
passata la passata sale da 58-66 a 65-79 ms). Anche senza corsia CPU Strata resta a 23-29 t/s contro i 22 di M2g: il
resto viene dalla bozza MTP e dal grafo unico. Noi la corsia CPU non l'abbiamo proprio (quella del 14/9 e' chiusa, D18).

**Difetto nuovo del nostro motore:** sui casi di copia/rinomina (prompt di codice da 4,2k) M2g fa 11 t/s, ripetibile. Non
e' la cache (colpi 69-78% come sui casi lunghi) e non e' il contesto corto (L01/L06 senza prefisso: 20,5 / 19,3 t/s).
Causa da trovare.

**Per usare Strata come daily:** la cache e' fissata al lancio. Durante la giornata la VRAM degli altri programmi va da
1,6 a 5,5 GB: se cresce oltre la riserva dopo il lancio, WDDM pagina e una richiesta puo' fermarsi (il watchdog riavvia
il motore). Una riserva che copra quei 4 GB rimpicciolisce la cache. In compenso usa ~27 GB di RAM in meno del daily
(tabella PLE su SSD) e non e' mai andato sotto pressione di RAM.

## Cosa ne esce per noi, in ordine

Aggiornato dopo il confronto equo:

1. **Il cancello di crescita RAM di M2: FATTO (M2g)**, 7,09 → 17,71 t/s sotto pressione di RAM. Da promuovere su ok.
2. **Scelta di fondo:** Strata e' gia' +31-40% sul daily a parita' di condizioni. O lo si usa (sulla 8100 dietro il
   gateway, con una riserva di VRAM scelta per la giornata), o se ne portano le leve nel nostro motore, in ordine di peso
   misurato: bozza MTP con verifica economica e grafo unico (il grosso: Strata senza corsia CPU fa ancora +10-30%), poi
   la corsia CPU (10-16%).
3. **Il difetto copia/rinomina a 11 t/s** del nostro motore, se il daily resta nostro: e' il carico degli agenti.
4. **PLE sull'SSD come Strata:** libera ~27 GB di RAM e fa ripartire il `-c 262144` con i programmi aperti.

## File

- `build-strata.bat` (compilazione con CUDA 12.6 e `CMAKE_CUDA_RUNTIME_LIBRARY=Shared`), `strata-iq3_xxs.json` (primo
  lancio), `strata-iq3_xxs-r1032.json` (riserva 1032, confronto equo), `strata-iq3_xxs-r1032-pcie1.json` (senza corsia CPU).
- `banco_strata.py` (client comune; `--motore llama` per il daily), `avvia_daily_lab.py` (il bat del daily in laboratorio).
- `corse/`: risultati, riassunti, stato al lancio, estratti dei log. Le uscite testuali restano in `D:\ds4_work\strata\banco_run`.
- Strata e i suoi dati: `D:\ds4_work\strata\Strata` (sorgente, build, `.venv`), `D:\ds4_work\strata\Strata-data`
  (pack 1,4 GB e testa MTP 5,2 GB scaricata + 0,9 GB impacchettata).
