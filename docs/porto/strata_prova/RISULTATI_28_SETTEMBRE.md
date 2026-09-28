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

## Cosa ne esce per noi, in ordine

1. **Il cancello di crescita RAM di M2**: con la RAM sotto pressione la cache non deve restare a 0 slot. Gli slot in VRAM
   non chiedono RAM in piu'; il ripristino del deposito non dovrebbe bloccarli. Guadagno atteso nell'uso reale: da ~7 a
   ~20 t/s (le misure del 21/9 a RAM libera), da misurare.
2. **PLE sull'SSD come Strata** (~0,3 ms/token dichiarati): libera ~27 GB di RAM, toglie la pressione che innesca il
   punto 1 e fa ripartire il `-c 262144` con i programmi aperti.
3. Solo dopo, le leve di Strata gia' elencate in `../RICOGNIZIONE_STRATA_28_SETTEMBRE.md` (mancanze divise fra PCIe e
   CPU, verifica MTP economica).

## File

- `build-strata.bat` (compilazione con CUDA 12.6 e `CMAKE_CUDA_RUNTIME_LIBRARY=Shared`), `strata-iq3_xxs.json` (lancio).
- `banco_strata.py` (client comune; `--motore llama` per il daily), `avvia_daily_lab.py` (il bat del daily in laboratorio).
- `corse/`: risultati, riassunti, stato al lancio, estratti dei log. Le uscite testuali restano in `D:\ds4_work\strata\banco_run`.
- Strata e i suoi dati: `D:\ds4_work\strata\Strata` (sorgente, build, `.venv`), `D:\ds4_work\strata\Strata-data`
  (pack 1,4 GB e testa MTP 5,2 GB scaricata + 0,9 GB impacchettata).
