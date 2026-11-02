# Prove notturne con la 3060 su riser - 1-2 novembre 2026

**Verdetto, aggiornato il 2/11 mattina (vedi in fondo).** La macchina migliore oggi e' a **due schede (3080 Ti + 2080 Ti), riserva 700/384, v0.2.9 + pila + leve della 2080 Ti**. Divisione da scegliere tra 20 e 24. La 3060 col riser non deve fare calcolo: strati ed esperti freddi peggiorano o non portano nulla. Compilato si', provato si' su questa postazione, installato no: Daily non toccata.

Banco della comunita': prompt freschi 4K e 32K, 3 corse, 256 token (`coda_notte.py`, dati in `corse/`, tabella con `riepilogo.py`). Replay DSH 3600+1200 s (`coda_multichat.py`, dati in `corse_mc/`, tabelle in `fasi_generato.md`).
Ordine schede con `CUDA_DEVICE_ORDER=PCI_BUS_ID`: 0=3080 Ti (Oculink), 1=3060 (riser x1 seconda generazione, ~500 MB/s), 2=2080 Ti. `STRATA_ROUTE_PRIOR=0` in tutte le corse.

**Ambiente.** OktoCGControl aperto sulla 3060 per tutta la notte: 0,7-3,5 core di CPU secondo il momento (10% medio nei replay), nessuna corsa segnata disturbata. Schermo 3840x2160 letto dal desktop da F6 in poi; il campo delle corse precedenti era letto male (Win32_VideoController) e va ignorato, ma per le tre schede il desktop era gia' a 4K (owner). Build `20261004_routed_keep/build-up0271pila-5fbc4784` (p) e `build-up029pila-b6ba3fa6` (u): sm_75+86, CUDA 12.6. Ramo del motore `lab/upsync-v0.2.9`, ultimo `b6ba3fa6`.

## v0.2.9 contro v0.2.7.1, due schede (2 ripetizioni alternate, media)

| divisione | lettura 4K u / p | lettura 32K u / p | scrittura 4K u / p | scrittura 32K u / p |
|---|---:|---:|---:|---:|
| 16 | 994 / 992 | 1641 / 1580 | 94,7 / 97,8 | 92,8 / 90,3 |
| 18 | 978 / 977 | 1693 / 1624 | 92,3 / 97,2 | 96,1 / 95,4 |
| **20** | 918 / 916 | **1769 / 1690** | 99,0 / 101,4 | 96,9 / 96,0 |
| 22 | 881 / 878 | 1840 / 1780 | 95,1 / 92,2 | 95,7 / 92,9 |

- Lettura 32K +3,4...+4,7% con v0.2.9, stabile tra ripetizioni. Lettura 4K pari.
- Scrittura pari: le differenze (-5...+3%) stanno dentro il rumore di questa macchina, che su una stessa configurazione ha toccato il 10% (d16: 85,9 e 99,1 t/s; u18: 97,3 e 87,3).
- La divisione sposta lettura 4K contro lettura 32K: 16 favorisce i prompt piccoli, 22 i grandi. La 20 ha la scrittura migliore e buona lettura grande. Rispetto alla 16 attuale la scrittura sale di 4-6 t/s a 32K, a 4K nessun distacco oltre il rumore.
- Riserva 1393 contro 700 su split 16: 943/1594 contro 928/1558 e 996/1581, rumore. 700 regge e libera posti esperti.

## Strati sulla 3060: bocciati

| corsa | esperti fissi per scheda | lettura 4K / 32K | scrittura 4K / 32K |
|---|---:|---:|---:|
| `20,44` | 2048 | 333 / 408 | 16,5 / 14,4 |
| `20,42` | 3072 | 265 / 322 | 15,0 / 14,4 |

Una corsa per braccio; distanza di 5-6 volte, non serve ripetere. Il freno e' il passaggio dal riser (sonda 0,2 GB/s contro 13,2 della 2080 Ti). Nessun errore di sistema. La riserva dopo lo stadio 0 deve essere almeno 1000: con 384 il secondo verificatore non entra (`t20_44`, `t20_42`, senza risultato, nessun guasto).

## Esperti freddi fissi sulla 3060: bocciati

`--split-device 2 --expert-cache-device1 N`, 3060 fuori dalla catena, esperti che non ruotano, tra quelli non tenuti dalle altre due. Spegne catena doppia, nucleo RAM ed elastic; incompatibile con `--prompt-cache-file`. Il paragone giusto e' `n20` (due schede senza catena e senza prefisso).

| corsa | lettura 4K / 32K | scrittura 4K / 32K | attesa 3060 ms/lancio | CPU Okto, core |
|---|---:|---:|---:|---:|
| n20_a | 925 / 1764 | 95,0 / 94,1 | - | 1,7 |
| n20_b | 933 / 1762 | 94,7 / 94,4 | - | 1,7 |
| f20 1000 | 918 / 1767 | 39,6 / 44,9 | 13,6 | 1,8 |
| f20 2000 | 936 / 1788 | 78,1 / 84,0 | 1,6 | 0,8 |
| f20 2000 ripetuta | 912 / 1779 | 34,0 / 39,5 | 11,5 | 1,8 |
| f20 3000 | 900 / 1777 | 31,8 / 36,6 | 10,2 | 2,0 |
| f20 4000 | 930 / 1789 | 79,0 / 80,4 | 1,3 | 0,6 |

- Lettura 32K +1% su n20, nel rumore. **Scrittura sempre sotto**: -11...-18% nel caso buono, -52...-66% nel caso cattivo.
- La scrittura ha due stati e non dipende da N. **Il legame con OktoCGControl e' smentito**: a programma chiuso (sezione finale) restano nello stato basso.
- Il tasso di riuso alla fine della corsa e' 99,3% contro 99,1%: le altre due schede tengono gia' quasi tutto, quindi la 3060 ha poco da aggiungere. Anche a Okto chiuso il massimo atteso e' il caso buono, comunque sotto n20.
- Rifatta a OktoCGControl chiuso: nessun recupero (sezione finale).

## Catena doppia a due schede

`n20` senza `--pipeline-windows` contro `p20` con catena, stessa build: lettura 32K 1763 contro 1693 (+4%), scrittura 4K 94,9 contro 99,2 e 32K 94,3 contro 96,2 (-4% e -2%; p20_a, p20_b, p20_senzaprefisso). Il prefisso spento da solo non cambia la lettura (938/1700). A v0.2.9 la lettura sale gia' a 1769 con la catena accesa: resta accesa.

## Multichat, divisione 20

Una corsa per braccio, tutte le richieste riuscite (17/17, 34/34), batch 4, PIPED_CONCURRENT=1.

| corsa | tempo s | TTFT medio / p90 s | token nuovi letti | token generati | lettura grande C#22 tok/s | scrittura >=2 T / N t/s | scrittura mentre si legge T / N t/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| p 0.2.7.1, 3 agenti | 239 | 15,9 / 23,0 | 181.211 | 4.639 | 1677 | 39 / 53 | 17 / 12 |
| u 0.2.9, 3 agenti | 237 | 18,5 / 50,8 | 181.373 | 4.600 | 1724 | 43 / 59 | 18 / 13 |
| c 0.2.9 + lettura condivisa, 3 agenti | 242 | 15,8 / 24,0 | 181.630 | 4.586 | 1690 | 35 / 47 | 18 / 15 |
| u, 6 agenti | 414 | 39,7 / 106,2 | 358.274 | 7.062 | 1759 | 28 / 30 | 16 / 14 |
| c, 6 agenti | 393 | 40,8 / 77,8 | 359.853 | 4.445 | 1740 | 26 / 8 | 14 / 15 |
| rif. 29/10 PC, split 16, 3 agenti | 242 | 17,7 / 34,7 | 182.517 | 4.040 | 1485 | 38 / 52 | 16 / 12 |
| rif. 29/10 PC, split 16, 6 agenti | 470 | 46,5 / 106,8 | 419.215 | 7.346 | 1526 | 30 / 10 | 16 / 15 |

- A 3 agenti p, u e c sono pari (237-242 s); la differenza di p90 tra p e u (23 contro 51 s) e' una sola lettura lunga in una sola corsa.
- La grande lettura C#22 con scrittori accesi sale del 13-16% rispetto al 29/10 (split 20 piu' v0.2.9; riferimento a split 16 con 0.2.7.1). A 3 agenti p ha 1677: buona parte viene dalla divisione.
- 6 agenti: 470 -> 414 s (-12%) rispetto al 29/10, ma con il 15% in meno di token riletti (358 K contro 419 K): parte del guadagno viene dalla cache e dall'ordine delle richieste, non e' misurato separatamente. Memoria libera minima 10 GiB.
- **Lettura condivisa (`STRATA_COALESCE_PREFILL`) scartata, il 393 non e' un guadagno.** A 6 agenti genera il 37% di token in meno (4.445 contro 7.062) e chiude 16 richieste sotto il 30% del bersaglio contro 5, varie a 3-4 token. Sono risposte tronche o finite prima, non velocita'. Va aggiunto che ne' server.log ne' engine.log registrano quando scatta: non e' provato che sia la causa, ma non c'e' motivo di approfondire finche' resta una funzione di ricerca spenta di default.

## Cosa cambiare e cosa no

- Da fare a mano nella Daily, con decisione dell'owner: `CUDA_VISIBLE_DEVICES=0,2` e' **obbligatorio** prima di riavviarla (`0,1` ora prende la 3060). Split 20 e riserva 700/384 sono il miglioramento consigliato; v0.2.9 + pila va installata come nuova versione a parte.
- 3060: solo schermo, OktoCGControl e visione, finche' sta sul riser.
- Con un secondo Oculink il verdetto sugli **strati** va rimisurato, perche' il freno misurato e' il riser. Anche quello sugli esperti, per la lettura: qui e' misurato solo a 4K/32K, e Lamina usa la scheda in piu' anche per gli esperti della lettura.
- Non provato: `STRATA_PF_W16_CACHE_MIB`, divisioni 19/21, target 128K.

## Aggiornamento 2 novembre mattina: OktoCGControl chiuso e banco completo 4K/32K/128K

Le corse di prima si fermavano a 32K: era un taglio di tempo mio, il banco della comunita' arriva a 128K. Sotto, 2 corse per riga, alternate, stessi prompt del 19/10 (hash identici).

| v0.2.9, divisione 20 | lettura 4K / 32K / 128K | scrittura 4K / 32K / 128K |
|---|---:|---:|
| riferimento (`Lbase`) | 923 / 1766 / 2068 | 103 / 95 / 96 |
| togli `STRATA_MMVQ_IL=0` (`Lil`) | 924 / 1775 / 2072 | 102 / 97 / 100 |
| `STRATA_SM75_PERF=1` (`Lsm75`) | 924 / 1868 / 2212 | 95 / 92 / 97 |
| piu' `STRATA_EXP_MODE=8` (`Lsm75m8`) | 915 / 1867 / 2217 | 102 / 102 / 103 |
| **tutte** (`Ltutte`) | **939 / 1860 / 2199** | **109 / 102 / 106** |

| divisione, senza leve | lettura 4K / 32K / 128K | scrittura 4K / 32K / 128K |
|---|---:|---:|
| 16, 0.2.7.1, riserva 1393 | 986 / 1644 / 1851 | 99 / 94 / 95 |
| 20, v0.2.9 | 923 / 1766 / 2068 | 103 / 95 / 96 |
| 22, v0.2.9 | 882 / 1843 / 2208 | 97 / 96 / 95 |
| 24, v0.2.9 | 856 / 1948 / 2373 | 94 / 93 / 93 |

- Le leve danno +5-6% in lettura grande e +6-10% in scrittura. Rumore fino al 10%, 2 sole coppie: da confermare.
- Salire di divisione costa poco in scrittura e rende molto in lettura grande. Mai provate insieme leve e divisione 22/24.
- Riferimento 19/10, due schede, divisione 16: 1836 lettura e 94 t/s a 128K.

**OktoCGControl chiuso, 2 corse.** Due schede v0.2.9 922/1774 e 102/98 contro 918/1769 e 99/97 da aperto: nel rumore. Esperti freddi 2000: 934-947/1795-1805, scrittura 28-30/28-39; 4000: 932/1812, 26/35; niente divisione per stato di OktoCGControl. Strati 20,44: 421/503, 23,5/20,8. La 3060 resta all'86% con 300-650 MB/s dal riser anche senza programmi: causa ignota, non e' il video dei telefoni.

**Prova a piu' turni (29K -> 97K, sessione A, pensiero azzerato).** Solo le corse finite prima dello stop, senza ripetizione:

| corsa | tempo s | TTFT medio s | richieste |
|---|---:|---:|---:|
| u16_a | 65 | 9.2 | 7/7 |
| v16_a | 65 | 9.3 | 7/7 |

**Profilo della catena fallito.** `STRATA_DECODE_TIMING=1 STRATA_VERIFY_PROFILE=1` in `Ptempi`: dopo il riscaldamento il motore si ferma con finestre in volo («the GPU did not finish within 5 s», `strata-stall-*.dmp`), il server lo riavvia ogni 8 minuti, 3 volte. Le stesse leve senza quelle variabili (`Ltutte`) non hanno dato problemi. Sospetta `STRATA_VERIFY_PROFILE`, non provato. Da rifare col solo `STRATA_DECODE_TIMING=1`.

**Non fatti:** leve di Fable (`ANALISI_FABLE.md`), tutte le leve a 22/24, multichat con la configurazione vincente, prova a piu' turni completa, prova sotto carico CPU, PR #4942.

Daily: `strata-026-3080ti-daily.json` portata a `0,2`, non ancora avviata; split 16 e riserva 1393/384 invariati.

## Jump e OktoCGControl durante la scrittura (2/11, 07:29-07:43)

`prova_jump.py`, dati in `corse_jump/j1/secondi.csv`. v0.2.9, divisione 20, tutte le leve, scrittura continua su richieste da 3000 token; una sola corsa, secondi senza token (cambio richiesta) esclusi.

| tratto | secondi | media t/s | 5 percento dei secondi peggiori sotto | CPU Jump, core |
|---|---:|---:|---:|---:|
| solo motore | 449 | 102 | 83 | 0 |
| Jump collegato | 93 | 103 | 85 | 0,5 |
| Jump + OktoCGControl | 253 | 95 | 66 | 0,2 |

- Jump da solo non pesa sulla scrittura; solo 3-4 secondi a 42-65 t/s all'aggancio, con 2,5 core per Jump.
- Con OktoCGControl la media perde il 7% e i secondi peggiori il 20%. La 3060 non calcola per il motore, quindi il colpo passa per la CPU: la media del banco nasconde questo effetto.
- Lag di tastiera con motore + Jump + OktoCGControl, desktop a 2732x2008: 3060 al 100% e riser a ~600 MB/s in arrivo. Questi due numeri restano uguali a motore spento, ma l'owner riferisce che a motore spento e schermo a 4K il lag sparisce: non misurano il lag e **la causa non e' isolata**. Da provare a 4K con motore acceso, una variabile alla volta.
