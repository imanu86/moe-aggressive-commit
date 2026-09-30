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
- **Prossima prova (B):** `python strumenti/prova_sm75.py --exe D:\ds4_work\strata\Strata\build-0129\strata.exe
  --riserva 500 --elastic --nome b0129_elastica_r500`; riferimento da battere 37,6 t/s (0.1.21 fissa, riserva 1393).

## Misure (profilo `rapido`, t/s aggregati)
| scheda / motore | t/s | note |
|---|---:|---|
| 3060, Strata 0.1.21 fissa / elastica, 29/9 quasi ferma | 22,7 / 24,8 | 37,5 / 34,2 ms per riga |
| 3060 sotto CGControl, fissa / elastica | 13,2 / 13,7 | la CPU e' il collo |
| 3060, daily M2 con agenti che compilano | 6,2 | cache a 0 nel 34%, RAM a 0,7 GB |
| **2080 Ti, Strata 0.1.21 fissa (6.532 esperti)** | **37,6** | 22,4 ms per riga, colpi 73-89%, prefill 512 t/s |
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

## Prossimi passi
1. Finire la prova B sulla 0.1.29 (sopra); A (0.1.29 senza elastica) solo se B non batte 37,6.
2. Cache a due zone sopra 0003 (scambi solo nella coda, tetto 6 GB, crescita e calo a passi) + correzione oscillazione.
3. Copia in RAM del nucleo: verificare prima se il prefill legge dalla RAM anche gli esperti residenti.
4. Poi: profilo lungo (~100k), F2 (piu' conversazioni), disposizione a due schede.
