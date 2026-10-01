# HANDOFF — Strata adattivo e daily sulla 2080 Ti (aggiornato 30/9/2026 18:20)

Da leggere per primo se la sessione riparte da zero. Repo: `moe-aggressive-commit`, branch
`research/ds4-iq1-subbit-tier-planner` (commit sempre con pathspec espliciti, formato `OPUS-SEZIONE-Descrizione`, trailer
`Co-Authored-By`, push subito). Regole utente: file del daily intatti, chiave API mai stampata ne' committata, download
solo con permesso, niente binari di terzi non compilati da noi.

## Macchina adesso
- **Solo la RTX 2080 Ti 22 GB** (sm_75, PCIe 3.0 x16, 13,1 GB/s misurati). La 3060 e' smontata; tornera' in OCuLink da
  uno slot M.2 (link x4).
- OktoCGControl di solito acceso; gli agenti dell'utente a volte compilano C# (fino a 7 core): campionare sempre la CPU.

## Lanciatore SOTA per l'utente (30/9 sera)
`Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat` (copia in `lanciatori/`): 0.1.29 + patch
0001-0005, `--elastic` (due zone), riserva di avvio 1393, porta 8100 solo su 127.0.0.1; la chiave API solo dalla variabile
`STRATA_API_KEY` (il file non la contiene); si ferma se strata.exe o llama-server sono gia' in esecuzione; la
configurazione porta `env.STRATA_WATCHDOG_S=240` e la tabella PLE in lettura diretta (predefinita). **`--ple-io mmap`
TOLTO l'1/10 alle 03:40:** con mmap la preparazione della finestra costa 6-7 ms (fino a 80 ms quando Windows scarica le
pagine) contro 0,7-0,9 ms con `direct` → ~12% in meno in decodifica e crolli (15,7 t/s); l'avevo messo il 30/9 guardando
solo il blocco della prima richiesta lunga (che resta da capire: con `direct` e' successo una volta; rimedio per ora solo
il limite a 240 s). Resta vero che la parte calda della tabella per 131k di conversazione sono ~2,8 GB, non 27,5.
Configurazione `D:\ds4_work\strata\Strata\strata-2080ti-sota.json` (log in `D:\ds4_work\strata\sota\`).

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
4a. **Esperti divisi fra le due schede (idea dell'utente, 30/9 sera): esiste gia' nell'originale**, «CUDA1–3 expert
   experiment» (`docs/SECOND_GPU.md` del clone; `--expert-cache-device1 N`, `--expert-cache-remote-placement
   stripe|layer`): CUDA0 = densi, KV, MTP e la sua cache; CUDA1 (la 3060) = una cache di esperti in piu' (~10 GB, ~6.000
   esperti: ~13.000 in VRAM in tutto contro 6.800); ogni strato manda lo stato (~25 KB) alla seconda scheda e aspetta i
   suoi risultati via RAM bloccata (niente P2P: va bene l'OCuLink). Sperimentale, nessuna misura pubblicata; prefill solo
   su CUDA0; su Windows la registrazione dell'arena si ferma a 8 GiB; la nostra elastica vale solo per CUDA0. Da misurare
   con l'OCuLink: una scheda / esperti divisi / strati divisi, stessi prompt.
4b. Idea dell'utente (30/9 sera): doppioni degli esperti. Su UNA scheda no (stessa banda, meno esperti diversi →
   meno colpi). Con due schede si': i piu' caldi su entrambe e una conversazione per scheda in parallelo (agente
   principale + subagente) = throughput ×2 con piu' agenti; dividere i token della stessa finestra fra le schede no.
5. Limiti noti di Strata: una sola conversazione in cache (F2: issue #57, PR #41/#52), nessuna cache su disco.
6. Difetto aperto dell'elastica 0003: oscilla quando la VRAM libera ha rumore (margine 192 MiB < ±300).

## Leva di velocita' trovata la sera del 30/9: i kernel degli esperti su Turing
Analisi della sequenza dei kernel (`strumenti/analizza_nsys.py` sul profilo `D:\ds4_work\strata\nsys\
strata_2080ti_cli.sqlite`): durante la decodifica la GPU e' occupata il 94%, i buchi fra kernel sono 0,2 us → la
FUSIONE di kernel darebbe poco (i piccoli, swiglu/quantizzazione/copie, sono <5%). Tratto tipico di strato 262 us:
`native_gu_kernel` 177 us + `native_down_kernel` 70 us (verify.cpp:682-689: lo stesso kernel fa gli esperti in VRAM e poi
i gruppi arrivati via PCIe). Per finestra ~1,5 GB di esperti letti in ~14 ms di kernel = **~100 GB/s su 616 (17%)**: i
kernel i-quant (tipi 16/17/21/22 gate/up, 42/20 down) sono tarati per RTX 50/40. Obiettivo: 35-40% della banda = ~+15%
complessivo. **Prossimo (deciso con l'utente 20:50, dopo la prova mmap):** Nsight Compute (installato: `C:\Program
Files\NVIDIA Corporation\Nsight Compute 2024.3.2`) su `native_gu_kernel`: banda ottenuta, occupazione, motivi di stallo;
poi ottimizzazione per sm_75 (2-4 token per finestra). I mancanti restano ~1/4 del tempo GPU (attesa CPU 16% + copie 8%).
**Nsight Compute NON si puo' usare sulla finestra di verifica (22:00):** ncu esegue i kernel uno alla volta e tiene
ferma la CPU, ma il `wait_flag_ge_kernel` di ogni strato aspetta un segnale scritto dalla CPU → blocco per sempre (GPU
al 100%, strata a 0 CPU). **Strumento al suo posto: `native_expert_bench`** (patch 0006, `build-0129\
native_expert_bench.exe <shard1.gguf> [strato] [esperti] [token] [iterazioni]`; PATH con CUDA 12.6\bin): esperti veri, forma
di una finestra, eventi CUDA, niente contatori. **Misure a GPU libera (22:10), 18 esperti, strato 20 (IQ3_S / Q2_0):**
1 token 254 us (132 GB/s), 2 token 477 us (71), 3 token 578 us (58), 4 token 763 us (44); strati 0 e 47 simili. **Il tempo
cresce con le coppie token-esperto (~14 us l'una), non coi byte:** `native_gu_kernel` / `native_down_kernel`
(`iq_kernels.cu:352-403`) rifanno la decodifica i-quant della riga per ogni coppia del gruppo (`row_dot` per voce), e anche
con 1 token un warp fa una riga sola (~2,5 pezzi per lane: latenza scoperta). **Lavoro in corso (22:15):** (1) prodotto
multi-token (decodifica una volta, prodotti per tutti i token del gruppo; formati 16/17/21/22 gate/up, 20/42 down, deve
restare identico bit per bit); (2) piu' righe per warp. Obiettivo: da ~58 a 150-200 GB/s effettivi = +10-20% complessivo.
**(1) FATTO (22:09, patch 0007, clone «Decodifica una volta i pesi...»):** `native_gu_multi_kernel` /
`native_down_multi_kernel` (+ `vdm_*` e `row_dot_multi` in `iq_kernels.cu`), uscite IDENTICHE bit per bit; banco strato 20:
1 token 255→259 us, 2 token ×1,30, 3 ×1,51, 4 ×1,63 (strati 0 e 47: ×1,35 e ×1,49 a 3 token). `STRATA_EXPERT_MULTI=0` =
kernel originali. **A/B sul motore (22:09-22:20) NON VALIDO:** Jump Desktop (`JumpConnect.exe`) prendeva 4,2-4,5 core e
il 32% del motore 3D della GPU (utente collegato da remoto): 42,8 ms per riga (nuovo) e 38,0 (vecchio) contro 18,9 del
pomeriggio, pool CPU 42-46 ms per finestra contro 13,7. Risultato collaterale: con Jump collegato Strata va a meta'
velocita'. **A/B a macchina ferma (1/10 03:22-03:36, nuovo → vecchio → nuovo, tutti con `--ple-io mmap`):** nuovo 21,4 ms
per riga (39,2 t/s), vecchio 20,5 (41,1), terzo giro non valido (preparazione 80 ms per finestra per via di mmap, ultimo
caso fallito). La voce che conta: **GPU per finestra 22,6 ms (nuovo) contro 23,7 (vecchio) = −4,7%, cioe' ~2-3% sul
totale** (nella finestra reale ~1,3 coppie per gruppo): sotto la soglia del 5%; resta acceso perche' e' esatto bit per
bit. **Kernel degli esperti: chiuso per ora (1/10 03:50).** Banco reso stabile (patch 0008: 200 chiamate di
riscaldamento, migliore di 5 giri): il caso base (un token per esperto) fa 171-176 us = **~195 GB/s**, non 132 (le prime
misure prendevano la scheda che saliva di frequenza); con i pesi tenuti in L2 (`... same`) 163 us (−5-7%): **il limite e'
il calcolo della decodifica i-quant, non la memoria**. Tempo GPU per gruppi (profilo Nsight): attesa CPU 16,3%, PCIe ~9%,
esperti ~22%, ricorrenza GDN ~18%, pesi densi ~19%, resto ~15%: nessun kernel sopra il 22%, +20% sul kernel degli
esperti = ~3% totale. **Rendimenti decrescenti su una scheda sola: la leva grossa rimasta e' il ~25% dei mancanti
(seconda scheda con gli esperti divisi, punto 4a).** Potenza misurata in generazione: 2080 Ti ~110-120 W (punte 160, limite 250); CPU non leggibile (stima 70-90
W); totale stimato alla presa 250-300 W in generazione, 110-140 a riposo (l'utente guardera' l'UPS).
Vecchio blocco (21:45): `ERR_NVGPUCTRPERM`, l'utente Windows non ha accesso ai contatori di prestazioni della GPU:
l'utente deve abilitarli (Pannello NVIDIA → Desktop → Abilita impostazioni sviluppatore → Sviluppatore → Gestisci
contatori di prestazioni GPU → Consenti a tutti gli utenti) oppure lanciare ncu da amministratore. Poi:
`python strumenti/prova_ncu.py --salta 400 --quante 8` (gia' con metriche minime in una passata: con le sezioni complete
ncu ripeteva ogni kernel ripristinando anche l'arena da 40 GB mappata). Usare `ncu.exe`, non `ncu.bat` (il `|` del
filtro). Nsight Systems non ha bisogno dei contatori.

## Originale e PR al 1/10 mattina (controllo chiesto dall'utente prima di lavorare «sulla banda»)
Decisione utente (1/10 04:00): la seconda scheda e' FUORI PERIMETRO per ora; si lavora sulla velocita' della 2080 Ti.
- **Originale 0.1.30 (30/9 17:50):** piu' conversazioni in RAM (`--conversation-cache-mib 8192
  --conversation-cache-slots 4`, opt-in, PR #189 = la nostra F2); modalita' poca RAM «residente» (`--resident-experts`:
  in RAM solo gli esperti che la GPU non tiene = niente doppione); prompt da 1-4k +17-28%; `--idle-unload`, `POST
  /unload|/load`; kernel CPU multi-token da un token (#152).
- **PR aperte utili per noi:** #258 (hireymage) kernel GDN `down` TILE=1280 per sm_75, −30% su quei kernel (RTX 2070);
  #186 (q8atnight) hyper-connection in 2 kernel, −1,5 ms per finestra; #284 (sergqwer) commit senza attesa, +5,6%;
  **#242 (gputier) = la nostra 0007** (decodifica una volta per tutte le voci), piu' completa (anche `iq_mmvq` denso,
  test `iq_multi_parity`); #270 (kenh0u) attenzione del prompt sui tensor core di Turing (m16n8k8), prefill +12%;
  #317 (BlueKingMuch) `STRATA_SSD_KEEPALIVE` per la tabella PLE (probabile causa del blocco della prima richiesta
  lunga); #315 hc multi-token; #241 kernel Q2_0; #292 esperti NVFP4; #286/#285 poca RAM su Windows.
- **Fork (69 aggiornati dopo la 0.1.29, 6 con commit propri):** niente sui kernel (Volta, AMD, API Codex).
- **Piano approvato dall'utente (1/10 04:15, «vai»):** (1) fork sulla 0.1.30; (2) #270, #258, #284, #317, poi #186 e
  #315 (stesso file della #258), una alla volta, ciascuna misurata con l'A/B sul motore (`STRATA_SPLIT_TIMING=1`: GPU per
  finestra) e col banco; (3) #242 contro la nostra 0007; (4) lanciatore SOTA aggiornato. Atteso: −3-4 ms su ~45 per finestra.
- **STATO 1/10 04:25 — passo (1) FATTO:** main del clone = **v0.1.30 (30ec18e) + 9 commit nostri** (le 8 patch portate +
  «Adatta la cache elastica al prestito per partecipante della 0.1.30», 8966caf: la 0.1.30 tiene il prestito al prefill
  in `pf_parts`, la ripianificazione aggiorna `pf_parts[0]` e il vincolo «si presta solo la coda» sta in `fits`). Punto di
  ripristino: tag `pre-0130-rebase` (= 0.1.29 + 8 patch). Build: `build-0130\strata.exe` (sm_75+86,
  `../strata_prova/build-strata-0130.bat`). Rami delle PR gia' scaricati nel clone: `pr-258 pr-186 pr-284 pr-242 pr-270
  pr-317 pr-315` (`git cherry-pick` del loro commit sopra main). **In corso:** riferimento `n0130_base` (profilo rapido,
  elastica, riserva 1393). Poi per ogni PR: cherry-pick → `build-strata-0130.bat` → `prova_sm75.py --exe
  ...build-0130\strata.exe --riserva 1393 --elastic --nome <pr> --env STRATA_SPLIT_TIMING=1` → confronto con
  `costo_passata.py` e la riga `stage 0:` del log.
- **Misure sulla 0.1.30 (1/10 03:51-, profilo rapido, elastica, riserva 1393, altri ~1,2-1,3 core):**
  | cosa | ms per riga | t/s | GPU per finestra | commit |
  |---|---:|---:|---:|---:|
  | riferimento: 0.1.30 + nostre patch (`n0130_base`) | 19,3 | 44,8 | 23,9 ms | 1,04 ms |
  | + #258 kernel GDN TILE=1280 per sm_75 (`n0130_pr258`) | 19,0 | 44,9 | 23,4 ms | 1,05 ms |
  Nel clone, sopra i 9 commit nostri: #258 (204cee8, conflitto risolto tenendo il `usable` per sm_60 della 0.1.30),
  #284 (20273f4, conflitti in generate.cpp: tenuti i controlli nuovi della 0.1.30 + `set_commit_async` + il
  `cudaDeviceSynchronize` a inizio richiesta), #186 (2 commit, puliti; **opt-in: `STRATA_GR_V3=1`**, non identica bit
  per bit). **Misurate 04:00-04:07 (ma con Codex sandbox, indicizzazione e OneDrive a 3,8-4,8 core: pool CPU 20 ms per
  finestra invece di 15, totale 42 t/s):** per le voci di GPU, che il disturbo tocca poco: + #284 → GPU 22,8 ms, commit
  **0,37 ms** (da 1,04); + #186 (`STRATA_GR_V3=1`) → GPU 22,6 ms, commit 0,41. Somma delle tre PR: ~−2,0 ms per
  finestra su ~46 (~+4% a macchina ferma, da confermare). Restano: #270 (prefill, da misurare col profilo lungo), #317,
  #315, #242 contro la 0007.
- **Scoperta sul disturbo (04:08):** nell'uso reale gira sempre qualcosa (agenti, Codex, indicizzazione, OneDrive, Jump)
  e la parte fragile e' la corsia CPU (thread fissati ai core, priorita' normale). **In corso:** A/B della priorita' di
  processo (`prova_sm75.py --priorita high` alza `strata.exe` a HIGH appena parte) contro normale, sotto lo stesso
  disturbo: `n0130_prio_high` poi `n0130_prio_norm`; guardare `pool + plan` per finestra.
- **Regola per le misure:** Jump Desktop spento (prende 4,5 core e 1/3 della GPU), niente `nvidia-smi` a ripetizione
  durante una corsa, banco dei kernel con riscaldamento lungo (patch 0008).

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
   **Quota PCIe 0,5 NON paga (19:30):** 23,8 ms per riga contro 18,9 (35,8 t/s): la GPU legge dal PCIe 3.0 piu' lenta
   (attesa 34,8 ms) e la preparazione sale da 0,7 a 9,0 ms per finestra; la sonda (0,28) ha ragione. Le manopole
   dell'originale sono gia' all'ottimo: il margine e' DENTRO i 24 ms di GPU per finestra (i byte ne valgono ~6).
   **Profilo Nsight (19:37, `strumenti/prova_nsys_cli.py`: strata.exe da riga di comando, prompt L01; dietro il server
   nsys non vede il figlio):** ripartizione del tempo GPU: `wait_flag_ge_kernel` 16,3% (la GPU aspetta la CPU),
   `fetch_blobs_kernel` 7,7% (esperti via PCIe), esperti in VRAM `gr_up/down_multi` 12,7%, pesi densi ~30%; ~590
   kernel per finestra (12 per strato). La cattura ha preso anche la fine della generazione: le percentuali di utilizzo
   non valgono, la ripartizione si'. **Conclusione:** ~1/4 del tempo GPU e' legato ai mancanti (scende con piu' VRAM:
   3060 in OCuLink); il resto e' fusione di kernel, che l'originale sta facendo (0.1.25→0.1.29 +19% per riga):
   riallinearsi spesso invece di rifarla. Il fork punta su adattivita' e memoria.
4. **Decisione utente (19:45): PRIMA LA VELOCITA'**, la F2 dopo. Via del prefetch degli esperti (tetto ~1/4 del tempo
   GPU; PCIe 3.0 a 13 GB/s: spostare tutti i mancanti costa ~18 ms per finestra; DS4 lo aveva falsificato: 70,8% copiato
   e mai usato). **Chiusa per ora (20:17):** prova 1 = scambi a ogni passata, 24 alla volta: 19,3 ms per riga contro
   18,9, colpi -1/-3 punti (i predefiniti 4/96 sono migliori); prova 2 = `strumenti/simula_prefetch.py` sulla traccia del
   29/9: prefetch per recenza nella coda +10 punti di colpi ma 399 MiB di copie per finestra (70% del PCIe 3.0), mancanti
   prevedibili dalla recenza solo 26/35/46/57% (1/2/4/8 finestre). Da riprovare con la 3060 sul PCIe 4.0.
5. **Misura a 131k (20:28, configurazione SOTA):** L02 a 131k = **35,1 t/s**, prefill 614 t/s (131k in 3,6 min), 46,7 ms
   per finestra (corti 45,4), GPU 26,1 ms per finestra (corti 24,3): l'attenzione a 131k costa poco (KV streaming 97% in
   VRAM), il ripiego FP32 di Turing NON e' una leva; il calo viene dalla bozza (1,64 token per finestra contro 2,05).
   **Difetto trovato:** la PRIMA richiesta lunga dopo l'avvio si e' bloccata («no progress for 60 s, reading the
   prompt, from token 0», 0 strati serviti): il controllo di sicurezza ha chiuso il motore e il server l'ha riavviato;
   dopo, la stessa richiesta e' andata a 614 t/s. Nei riscaldamenti la preparazione della finestra costava 74-89 ms
   (di solito 0,7). Sospetto: tabella PLE letta dal disco senza cache (`--ple-io direct`, predefinito; il daily la tiene
   tutta in RAM). Rimedio messo nel lanciatore SOTA: `env.STRATA_WATCHDOG_S=240` nella configurazione. **Da fare:** A/B
   `--ple-io mmap` (cache di Windows) contro direct sulla prima richiesta lunga dopo l'avvio.
   Prima prova (quota PCIe):
   Comando: `prova_sm75.py --exe ...build-0129\strata.exe --riserva 1393 --elastic --nome X --env STRATA_SPLIT_TIMING=1
   --arg --pcie-frac=0.5` (`--arg K=V` sostituisce o aggiunge un argomento del motore).
2b. F2 subito dopo: la 0.1.29 ha gia' `--prompt-cache 6` (catena di punti di ripresa su UNA storia, radice = fine del
   prompt di sistema, bloccata); manca salvare/rimettere la KV di ogni conversazione (1,4 GB ogni 100k token in int8).
3. Copia in RAM del nucleo: verificare prima se il prefill legge dalla RAM anche gli esperti residenti.
4. Poi: profilo lungo (~100k), F2 (piu' conversazioni), disposizione a due schede.
