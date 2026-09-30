# HANDOFF — Strata adattivo e daily sulla 2080 Ti (aggiornato 30/9/2026 18:20)

Da leggere per primo se la sessione riparte da zero. Repo: `moe-aggressive-commit`, branch
`research/ds4-iq1-subbit-tier-planner` (commit sempre con pathspec espliciti, formato `OPUS-SEZIONE-Descrizione`, trailer
`Co-Authored-By`, push subito). Regole utente: file del daily intatti, chiave API mai stampata ne' committata, download
solo con permesso, niente binari di terzi non compilati da noi.

## Macchina adesso
- **Solo la RTX 2080 Ti 22 GB** (sm_75, PCIe 3.0 x16, 13,1 GB/s misurati). La 3060 e' smontata; tornera' in OCuLink da
  uno slot M.2 (link x4).
- OktoCGControl di solito acceso; gli agenti dell'utente a volte compilano C# (fino a 7 core): campionare sempre la CPU.

## Attenzione: il daily di produzione NON gira sulla 2080 Ti
`D:\ds4_work\bin_elastico_m2` (quello del bat sul Desktop) contiene solo sm_86. Runtime per la 2080 Ti gia' pronti, in
laboratorio: `D:\ds4_work\daily_sm75\runtime` (M2) e `runtime-m3` (M3). Il bat non e' stato toccato: per usarli va
cambiato il percorso nel bat, **solo col permesso dell'utente**.

## Strata
- Clone `D:\ds4_work\strata\Strata` (origin = github.com/Niko1221/Strata). Commit nostri solo locali:
  0001 dump routing, 0002 blocchi allineati ai punti di ripresa, 0003 cache elastica `--elastic` (copie in `patches/`).
- Build: `build\` = 0.1.21 sm_86; `build-sm75\` = 0.1.21 sm_75+86 con `-DSTRATA_EXPERIMENTAL_SM75=ON`
  (`../strata_prova/build-strata-sm75.bat`).
- Dati: `D:\ds4_work\strata\Strata-data` (pack iq3_xxs, mtp). Configurazione base: `Strata\strata-iq3_xxs-r1032.json`.
- Prova: `strumenti/prova_sm75.py [--elastic]` (profilo `rapido`, CPU campionata; per un altro exe cambiare
  `C.BASE["exe"]`). Costo per riga: `../strata_prova/costo_passata.py etichetta=log`.
- **30/9 18:40: main del clone = 0.1.29 (d6708a4) + le 3 patch portate** (1bd8fe4, 4d59ab5, 495580b; copie in
  `patches/su-0.1.29/`; la 0001 l'originale l'ha fatta da se', resta solo il nostro fflush). Punto di ripristino: tag git
  `pre-0129-rebase` (= 0.1.21 + patch). Build `build-0129\` (sm_75+86, `../strata_prova/build-strata-0129.bat`: dalla
  0.1.27 sm_75 non chiede piu' l'opzione sperimentale).
- **30/9 18:35 — configurazione migliore: `build-0129` + `--elastic`, riserva di avvio 1393** (prova C: 43,4 t/s, 19,3 ms
  per riga; A fissa 45,1 / 18,9, pari entro il rumore; 0.1.21 era 37,6 / 22,4). Con riserva di avvio 500 (B) la sessione
  resta lenta (31,2): avvio largo, poi l'elastica cresce. Comando:
  `python strumenti/prova_sm75.py --exe D:\ds4_work\strata\Strata\build-0129\strata.exe --riserva 1393 --elastic --nome X`.

## Misure (profilo `rapido`, t/s aggregati)
| scheda / motore | t/s | note |
|---|---:|---|
| 3060, Strata 0.1.21 fissa / elastica, 29/9 quasi ferma | 22,7 / 24,8 | 37,5 / 34,2 ms per riga |
| 3060 sotto CGControl, fissa / elastica | 13,2 / 13,7 | la CPU e' il collo |
| 3060, daily M2 con agenti che compilano | 6,2 | cache a 0 nel 34%, RAM a 0,7 GB |
| 2080 Ti, Strata 0.1.21 fissa (6.532 esperti) | 37,6 | 22,4 ms per riga, colpi 73-89%, prefill 512 t/s |
| **2080 Ti, Strata 0.1.29 + patch, elastica, avvio 1393** | **43,4** | 19,3 ms per riga (fissa: 45,1 / 18,9), prefill 644 t/s |
| 2080 Ti, daily M2 sm_75 | 12,4 | si svuota a ogni prefill |
| 2080 Ti, daily M3 sm_75, `LLAMA_MOE_ELASTIC_MAX=140` | 15,6 | copia di codice 8,4 |

Dettagli: `RISULTATI_2080TI_30_SETTEMBRE.md`, `RISULTATI_ELASTICO_29_SETTEMBRE.md`, `../strata_prova/RISULTATI_28_SETTEMBRE.md`.

## Decisioni e idee dell'utente (in ordine)
1. Si lavora su **Strata** (MIT), non sul daily; il daily solo il minimo per la nuova scheda.
2. **Cache a due zone:** nucleo fisso (i migliori esperti, mai ruotati ne' svuotati, senza copia in RAM: ~10 GB
   risparmiati) + coda elastica di **al massimo 6 GB**, l'unica che ruota, cresce e cala **a passi fino a stabilita'** e
   si presta al prefill; il resto sulla CPU.
3. Riserva piccola (500 MiB): col KV streaming 1,4 GB liberi sono troppi.
4. Con l'OCuLink: 2080 Ti piena e fissa (~20 strati interi) + 3060 sul PCIe 4.0 con la cache che ruota.
5. Limiti noti di Strata: una sola conversazione in cache (F2: issue #57, PR #41/#52), nessuna cache su disco.
6. Difetto aperto dell'elastica 0003: oscilla quando la VRAM libera ha rumore (margine 192 MiB < ±300).

## Cosa portiamo su Strata da DS4, Qwen38 e llama (lista del 30/9, in ordine di guadagno atteso)
Base: sulla 2080 Ti una riga costa ~19 ms, i byte da leggere a 616 GB/s ne valgono ~4-5: il margine e' in attese e
sincronizzazioni, non nel calcolo.
1. **Misurare le attese, poi tagliarle** (DS4: «il rendezvous costa 23,4% e compra 1,5%»). Strata sincronizza GPU e
   CPU 48 volte per passata (una per strato); `STRATA_SPLIT_TIMING=1` da' per finestra: attesa della GPU, pool + piano,
   preparazione, commit. Poi: piu' colpi (cache), quota PCIe al posto della CPU, o meno appuntamenti.
2. **Speculazione tarata sui costi** (Qwen38 14/9: aritmetica del ciclo; DS4: il premio e' nel giro). Oggi ~2,1 token
   per passata con `--spec-min-p 0.5`; se il costo fisso della passata domina, bozze piu' lunghe (`--spec-min-p`
   0,3-0,4, finestra fino a 6) e poi la versione adattiva (F3).
3. **Bozze che guardano la residenza** (DS4: AcceptMoE che scartava per residenza): accorciare la bozza quando i suoi
   token vanno su esperti fuori dalla VRAM. Solo se la 2 paga.
4. **Nucleo senza copia in RAM** (idea dell'utente): ~5,5 GiB di RAM ora, ~17 GB con l'OCuLink; base: `--mmap-experts`
   della 0.1.26.
5. **Piu' conversazioni (F2, dal doubleKVring di DS4):** salvare/rimettere la KV per conversazione (1,4 GB ogni 100k in
   int8, copia RAM→RAM in una frazione di secondo contro minuti di rilettura); la 0.1.29 ha gia' `--prompt-cache` (catena
   su una storia, radice bloccata).
Da NON portare: profilo per massa (F0 provato: +1%), piu' lavoro alla CPU per esperto (cimitero di DS4), i kernel di
attenzione del daily (Strata ha i suoi).

## Prossimi passi
1. (Fatto 18:35: 0.1.29 + patch = +19% per riga; configurazione C.)
2. (Fatto 19:03: **cache a due zone, patch 0004**, clone 30657c4, `patches/su-0.1.29/0004-...`: 44,3 t/s, pari a fissa ed
   elastica a regime.) **Sotto pressione (4 GB per 60 s) fatto 19:15:** calo in 4 passi da ~1 GiB con la patch 0005
   (lettura 0 = passo pieno), nucleo intatto, niente oscillazioni; 4.096 token in 95,9 s (3060: 146/170 s).
   Clone: main = 0.1.29 + 0001-0005 (ultimo commit: «Con una lettura di 0 MiB cala di un passo intero»).
3. **Tempi della finestra misurati (19:21, `STRATA_SPLIT_TIMING=1`, stessi prompt, 45,1 t/s):** finestra ~45 ms =
   CPU che aspetta la GPU 24,3 (54%) + GPU che aspetta la CPU per gli esperti mancanti 13,7 (30%) + preparazione e commit
   1,7 + resto ~5,7 (testa MTP, lancio). La GPU lavora 24 ms dove i byte valgono ~6: il costo e' fisso per strato, non nei
   byte. **Bozze piu' lunghe NON pagano (19:25):** `--spec-min-p 0.3` = 2,40 token e 3,36 righe per finestra, 55,6 ms,
   43,2 t/s contro 45,1: una riga in piu' costa ~10,7 ms, la parte fissa ~19,6 ms per finestra (0,4 ms per strato), le
   bozze aggiunte passano al 37% → 0,5 e' gia' vicino all'ottimo, la F3 adattiva vale al massimo pochi punti.
   **In corso 19:26:** `--pcie-frac 0.5` contro lo 0,28 della sonda (la GPU aspetta la CPU per il 30% della finestra).
   Comando: `prova_sm75.py --exe ...build-0129\strata.exe --riserva 1393 --elastic --nome X --env STRATA_SPLIT_TIMING=1
   --arg --pcie-frac=0.5` (`--arg K=V` sostituisce o aggiunge un argomento del motore).
2b. F2 subito dopo: la 0.1.29 ha gia' `--prompt-cache 6` (catena di punti di ripresa su UNA storia, radice = fine del
   prompt di sistema, bloccata); manca salvare/rimettere la KV di ogni conversazione (1,4 GB ogni 100k token in int8).
3. Copia in RAM del nucleo: verificare prima se il prefill legge dalla RAM anche gli esperti residenti.
4. Poi: profilo lungo (~100k), F2 (piu' conversazioni), disposizione a due schede.
