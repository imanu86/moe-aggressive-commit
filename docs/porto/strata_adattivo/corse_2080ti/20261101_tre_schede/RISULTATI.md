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

## Divisioni con tutte le leve e correzioni di Fable (2/11, OktoCGControl acceso, Jump spento)

Banco completo, medie di due corse, v0.2.9 + pila, riserva 700/384, `TUTTE` = `STRATA_SM75_PERF=1 STRATA_EXP_MODE=8`, senza `STRATA_MMVQ_IL`.

| divisione | lettura 4K/32K/128K | scrittura 4K/32K/128K |
|---|---:|---:|
| 20 | 936/1876/2210 | 104/100/106 |
| 22 | 904/1937/2323 | 104/97/99 |
| 24 | 856/2014/2336 | 90/92/91 |

Correzioni di Fable a divisione 20, due corse, stessa fase (`rif`, senza attesa attiva, tre impostazioni sm_86, entrambe): lettura 128K 2140-2210 e scrittura 98-109 in tutti i bracci. Nessuna distacca il riferimento, nel rumore.

## I ms non scomposti (2/11)

- `Pserie` (senza catena): 101/102/104 t/s, 25,3-25,6 ms/finestra = verifica 22,4 + bozze 2,5 + emissione 0,5. Nella verifica le voci nominate fanno 7,7 ms: ~14,7 non scomposti.
- `Ptheta35` (catena, soglia 0,35): 99/104/107 t/s, 22,5-23,8 ms/finestra, scarti dal 66% al 54% (ultima richiesta), nel rumore. Le finestre scartate non sono la causa; la catena a due schede non da' un guadagno misurabile.
- Nel codice la riga dei tempi usa `ver`, cioe' solo lo stadio 0: l'attesa della 2080 Ti non compare. Deduzione, da misurare con `STRATA_SPLIT_TIMING=1` (`Pstadi20/22/24`, F15).
- Le bozze costano 2,5 ms a finestra, il 10%: `bozze0` in F16 prova il drafter sulla 3080 Ti.

Prova a piu' turni con tutte le leve, divisione 20 (`t20`): 65,0 s, TTFT mediano 10,1, massimo 10,6; 16 senza leve 64,8-65,4 s. Pari: su 83K token nuovi il tempo e' tutto lettura a 1300-1400 t/s. Prova sintetica: genera solo 127 token su 844 previsti.

In coda: `t22`, multichat `t` a 20 e 22 con 3 e 6 agenti, F15. Poi F16 (leve residue) e F17 (sotto carico con `carico_cpu.py 6`).

## Attesa di ogni scheda (2/11, `Pstadi*`, senza catena, tutte le leve)

`STRATA_SPLIT_TIMING=1`, medie su ~950 finestre di scrittura, ms a finestra.

| divisione | 3080 Ti attesa + CPU | 2080 Ti attesa + CPU | somma | esperti su CPU per strato |
|---|---:|---:|---:|---:|
| 20 | 6,5 + 1,6 | 12,6 + 1,1 | 21,8 | 0,24 |
| 22 | 5,7 + 3,3 | 11,5 + 1,0 | 21,5 | 0,44 |
| 24 | 6,0 + 5,7 | 10,6 + 0,7 | 23,0 | 1,04 |

- La somma chiude la verifica (22-23 ms): non c'e' tempo perso. I ms mancanti erano la 2080 Ti, che la riga dei tempi non legge.
- Costo per strato: 2080 Ti 0,44-0,45 ms costanti con 24, 26 e 28 strati; 3080 Ti 0,40-0,41 ms tutto compreso a 20-22, 0,49 a 24 quando la VRAM finisce e gli esperti vanno sulla CPU. La 2080 Ti e' circa il 20% piu' lenta a strato: pesa di piu' soprattutto perche' ha 28 strati su 48.
- In serie la finestra e' 48 strati per ~0,45 ms. Se le schede lavorassero davvero insieme il limite sarebbe la piu' lenta, 13,7 ms invece di 21,8; la catena oggi ne prende solo ~4% perche' butta le finestre sbagliate.

## Giro veloce a contesto lungo (2/11, `banco_lungo.py`, divisione 20, tutte le leve)

Una lettura da 128K e 6 turni sullo stesso contesto, una corsa, solo filtro. Il testo cambia tra le corse anche a parita' di impostazioni.

| leva | scrittura t/s | esito |
|---|---:|---|
| riferimento | 93,2 / 94,6 / 95,0 | |
| `STRATA_MTP_STAGE0=1` | 120,1 (702 token) | da validare, testo non salvato |
| `--adapt-swaps 32` | 98,9 | candidata |
| `--spec 3` | 98,0 | nel rumore |
| `--no-host-worker` | 92,8 | neutra |
| solo `STRATA_EXP_MODE=8` | 91,5 | neutra |
| `--spec 6` | 93,6 | neutra |
| `--spec-min-p 0.7` | 91,4 | neutra |
| `STRATA_VERIFY_DEVICE_PLAN=1` | 90,4 | neutra |
| `STRATA_MTP_SHARED_BRANCH` tolta | 82,2 | bocciata |
| `--spec-min-p 0.35` | 76,5 | bocciata |

Con 6 core occupati: riferimento 81,4; senza `STRATA_POOL_SPIN_US=100` 88,4; `--adapt-swaps 32` 89,2; `--no-host-worker` 83,2.

## RAM e tabella n-grammi (2/11)

- Working set ~61 GiB: arena esperti 28,25 + tabella n-grammi 26,8 + ~6 altro. L'arena torna: 16 esperti fuori dalle schede + 10 di copie che ruotano + 2,2 fissi con copia. La memoria privata di 70-74 GiB comprende ~34 GiB di blocchi che con ogni probabilita' rispecchiano la VRAM (dedotto).
- Da v0.2.7 la tabella va in RAM da sola se il motore trova ~75 GiB liberi: da 03:39 del 2/11 quasi tutte le corse, a volte alternate. Dal confronto spontaneo la RAM vale 1-2% in lettura, nel rumore.
- `Rple_a` (`STRATA_PLE_AUTO_RAM=0`): lettura 128K 2108 contro 2162 di `Rrif_a`, working set 39 GiB contro 61. Una corsa, entrambe con campionamento `nvidia-smi` a 1 s attivo, scrittura non confrontabile col resto. Avvio 380 s, arena a 0,13 GiB/s con altre chat al lavoro: da rimisurare.
- Da qui le code fissano `--ple-io direct`. F19 fermata alle 12:47 su richiesta dell'owner, `Rcore7000` e `Rrif2` non fatte.

## Traffico (2/11, `passaggio.csv`, `nvidia-smi dmon`, scheda <-> host)

| fase | 3080 Ti rx/tx MB/s, calcolo | 2080 Ti rx/tx MB/s, calcolo |
|---|---:|---:|
| lettura | 4515/610, 71% | 5786/743, 93% |
| scrittura | 743/203, 45% | 881/185, 60% |

Tra le schede passano ~51 KB per riga (`ANALISI_FABLE.md`, misura del 13/10): stimati ~6 MB/s in scrittura e ~110 MB/s in lettura, poche unita' percentuali del traffico. Il resto sono esperti, righe e K/V da e verso la RAM. In scrittura 183/168 W medi e 229 W di picco (11 campioni), nessun freno; i picchi da 270-280 W sono della lettura.

## BAB bozze sulla prima scheda e parallelismo (2/11, tabella su SSD, `banco_lungo.py`)

Riferimento 87,3 / 80,2 / 76,6 t/s, `STRATA_MTP_STAGE0=1` 86,6 / 88,2: +7% su poche corse, riferimento in calo. Finestre riuscite in parallelo 14,4-14,7 ms contro 19-24 e 13,7 teorici, ma l'81% delle anticipate scartato (73 su 90 in `Bbozze1`). Il limite della catena e' indovinare, non il calcolo. Il 120 del giro veloce e' stato quasi certamente testo facile.

Tabella su SSD: avvio 107-120 s (una volta 288). Riferimento 77-87 contro 93-95 in RAM: causa da separare, altre chat al lavoro. Riuso da SSD non riuscito: `prefissi/` vuota, il banco non ha messaggio di sistema.

Punto Fable: `STRATA_MTP_DEVICE=1` scritto, compilato (`build-up029pila-835f73b2`), non provato; esperti sulla 3060 con catena: non conviene ora. Con `STRATA_MTP_STAGE0=1` salvataggio e ripristino conversazione su disco usano la scheda sbagliata, da correggere.

`Vgpu` (visione sulla 3060) fermata alle 13:24: il PC era in crisi e CGControl si e' chiuso con errore in CoreMessagingXP.dll alle 13:24:20, nello stesso momento dello stop del motore. Causa non isolata. Nessun dato utile dalla corsa. A desktop 3840x2160 senza programmi la 3060 resta al 100%, `dwm` 65%: la risoluzione 8K non spiega da sola il carico.

## SSD contro RAM a PC riavviato (2/11, 14:05-14:21, OktoCGControl acceso)

Dopo il riavvio la 3060 scende all'8% a vuoto e sta a 31-35% di media con OktoCGControl, picchi 42-59%, contro l'86-100% di prima. Il carico alto non era strutturale.

| corsa | lettura 128K | scrittura t/s | token |
|---|---:|---:|---:|
| `Cssd1` | 2223 | 92,9 | 1481 |
| `Cram1` | 2193 | 107,7 | 932 |
| `Cssd2` | 2241 | 93,1 | 1218 |
| `Cram2` | 2203 | 95,2 | 1636 |

La lettura su SSD non perde. In scrittura pari, `Cram1` ha testo facile (932 token). Gli 87 t/s delle BAB dipendevano dalla macchina in sofferenza: quelle corse non valgono per le bozze e vanno ripetute.

Con la tabella in RAM il motore arriva a 76 GB e il totale a 90-91 su 96 durante il caricamento. OktoCGControl segnalato spesso senza risposta dall'owner; `Responding` vero quando letto, 0 pagine/s. `Cpieno` fermata.

Decisione: tabella su SSD.

## BAB bozze a PC riavviato (2/11, 14:26-15:20, build `835f73b2`, tabella su SSD, OktoCGControl acceso)

| corsa | riferimento | bozze sulla 3080 Ti | bozze sulla 3060 |
|---|---:|---:|---:|
| scrittura t/s | 85,2 / 85,3 / 94,6 | 97,2 / 92,0 | 84,5 / 92,8 |
| media | 88,4 | 94,6 | 88,7 |
| lettura 128K | 2063-2212 | 2222-2225 | 1950-1975 |

Bozze sulla 3080 Ti +7% di media, dentro l'escursione del riferimento: non confermata. Bozze sulla 3060: scrittura pari, lettura 128K -9%, 3060 fino al 100%, costo riser 0,07 ms a catena. Finestre riuscite in parallelo 14,3-17 ms ma 75-80% scartate.

Banco completo `Epieno`: 937/1862/2190, 101/102/104, come `Z20tutte`: a tabella su SSD e con la build di Fable a variabili spente i ~100 t/s restano. `banco_lungo.py` dà valori piu' bassi del banco, 85-95: i due non si confrontano tra loro.

Caricamento 105-519 s secondo l'occupazione del disco C:, da cui si legge la prima parte del modello.

## Tappa 0 del parallelo vero: span GPU del server (2/11, 18:10-18:45, `FEP0`, build `8ad3bef3`, `banco_lungo.py`, OktoCGControl acceso)

`PIPELINE3_PIANO.md` tappa 0: con `STRATA_PEER_STAMP=1` due stamp `%globaltimer` sul flusso della 2080 Ti per strato (prima della prima copia di `PeerExperts::launch`, dopo `scatter_rows_f32`), configurazione `PEER` (`--peer-device 1 --peer-reserve-mib 3000`, `STRATA_ARENA_PIN_GIB=8`) + tutte le leve + `STRATA_DECODE_TIMING`. `Vst` = stamp; `Vns` = stamp + `STRATA_PEER_NOSWITCH=1`. Tre coppie alternate, 7 richieste a contesto 128K ciascuna (42 righe `strata decode peer:` per braccio). Tutto M.

| braccio | span GPU a strato p50 (mediana delle 7 richieste, min-max) | p90 | somma span ms/finestra | host launch + finish ms/finestra | ms/finestra | scrittura t/s mediana | lettura 128K |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vst1 | **310** (291-353) | 422 | 14,9 | 2,3 + 9,8 = 12,1 | 35,2 | 64,3 | 1466 |
| Vns1 | **311** (265-360) | 410 | 14,6 | 2,3 + 9,7 = 11,9 | 34,3 | 66,0 | 1457 |
| Vst2 | **313** (270-358) | 424 | 15,1 | 2,4 + 9,4 = 11,7 | 34,6 | 64,9 | 1454 |
| Vns2 | **311** (246-338) | 424 | 15,1 | 2,7 + 8,9 = 11,4 | 34,8 | 68,9 | 1454 |
| Vst3 | **297** (242-355) | 399 | 14,2 | 2,3 + 8,7 = 11,4 | 33,9 | 67,2 | 1452 |
| Vns3 | **315** (249-347) | 418 | 15,0 | 2,3 + 9,0 = 11,4 | 34,5 | 71,1 | 1460 |

- **Span GPU del server a strato: p50 ~300 µs (242-360 su 42 richieste), p90 ~400-460.** Il criterio della tappa 0 era: < 150 → server a grafo; 150-250 → solo con caldi alla padrona e righe bf16; **≥ 250 → `procede = false`**. Siamo a 300: **il parallelo vero come disegnato in `PIPELINE3.md` §3a (esposto 125-140 µs a strato, 109-121 t/s) non è sostenuto dalla misura e si ferma qui.**
- Che cosa c'è dentro lo span: le due copie H2D (x fp32 30 KB + piano), `hadamard_rows`, `quantize_q8_1_rows`, 3-5 lanci di `native_expert_grouped` (14-15 esperti, 19-21 voci a strato-finestra), lo `scatter_rows_f32` sulle righe mappate dell'host (~200 KB a strato sull'x16), e i vuoti in cui la 2080 Ti aspetta la sottomissione successiva dell'host. La somma degli span (14-15 ms a finestra) è maggiore dell'attesa in `finish` (6-11): il flusso parte prima che `launch` sia finita, quindi lo span può contenere fino al tempo di `launch` (2,1-3,1 ms a finestra, cioè ≤ 45-65 µs a strato). **Limite inferiore del lavoro GPU puro**: l'attesa in `finish` (l'host non fa altro che girare) = 120-230 µs a strato; limite superiore = lo span, ~300. Anche al limite inferiore si sta sopra i 150 del server a grafo semplice, e al centro sopra i 250 dello stop.
- Il banco `ep_bench` (`exp.host` 118 µs con esperti come letture di banda) sottostimava il server di 2-2,5 volte: i kernel veri sulla 2080 Ti costano quel che restava «non spiegato» nel piano (200-285 µs a strato, S, ora M ~300). La banda non è il collo: 14 blob da 1,7 MB a 616 GB/s sono ~40 µs.
- `STRATA_PEER_NOSWITCH=1`: nessuna differenza misurabile (launch 2,2-2,7 ms in entrambi, finish uguale), mai rifiutata dal driver (nessuna riga «refused»). Si può lasciare spenta.
- Testo: `Vns1 = Vst2 = Vst3` identici in tutti i 7 turni, `Vns2 = Vns3` identici fra loro, `Vst1` diverge dal turno 2: le differenze seguono l'adattamento (quale scheda calcola quale esperto: sm_75 contro sm_86), non lo stamp né il cambio di scheda. Il confronto «testo identico a `Vpeer` con STAMP=0 sulla stessa build» non era fra i bracci (`Vpeer` è di un'altra build e di un altro banco) e **non è misurato**; a cache fissa resta da fare se serve.
- Finestra 34-35 ms a 128K contro 39,8-53 di `Vpeer` sul banco della comunità (altro banco, altra build: non si confrontano). `host launch+finish` 11,4-12,1 ms a finestra = 237-251 µs a strato, di cui launch 44-64 e finish 120-230.
- Lettura 128K 1452-1466 t/s contro 2063-2225 del riferimento a divisione 20 (`Erif*`): −34%, come `Vpeer`.

**Che cosa resta da misurare se si vuole riaprire** (non fatto): un terzo stamp dopo le copie e prima di `hadamard`, e un quarto dopo i kernel esperti e prima dello scatter: dicono se i ~300 µs stanno nelle copie e nello scatter sulle righe mappate (righe bf16 o sommate per token dimezzerebbero) o nei kernel esperti stessi (allora serve un kernel più veloce, non un server a grafo). Finché non c'è, `procede = false`.

## Leve sui kernel della 2080 Ti (2/11 sera, `lab/upsync-v0.2.9` 9102270f..7a837206, build `7a837206`, riferimento `67908ef8`)

Obiettivo: accorciare i kernel sulla 2080 Ti a testo identico (0,45 ms a strato nello stadio 1, ~300 µs a strato come server del peer). Tre leve, ognuna in un commit, tutte spente di default.

| leva | commit | che cosa | misura a livello kernel (2080 Ti, `bench.lock`) |
|---|---|---|---|
| PR #4942 (IQ3_S/IQ3_XXS interleaved) | 9102270f | porto com'è, `git apply --3way` senza conflitti | `mmvq_il_parity`: OK bit a bit (T 1-8, righe 1/2/4). `--bench --emit-table` due corse: **ogni cella IQ3_S/IQ3_XXS a 0** (2-4, 5-8 e 1 colonna). Le forme grandi pareggiano al decimo di µs (IQ3_S 2560x6144 T=2: multi 43,2, il 43,2; 2560x12288 T=4: 112,2 / 112,1). Anche i tipi già in `kIlRows_75` escono a 0 (IQ4_XS 2560x10240 T=4: 72,0 contro 72,5 µs, documentati 81→37; testa Q5_K 1696 contro 1694, documentati 1671→1045): il bench su questa scheda oggi non distingue i due percorsi, come #4962 sulla T4 |
| `STRATA_GU_FUSED_MINB=4` (gate/up fuso a 64 registri) | 04608b02 + 7a837206 | `native_gu_fused_kernel_minb4` con `__launch_bounds__(256, 4)`: 64 registri e 32-48 B di stack (da 71-78 registri, 3 blocchi/SM) | `native_expert_bench`, 14 esperti x 2 token, modo 8 contro modo 8, due giri alternati: gate/up **IQ3_S 65,5 → 72 µs, IQ3_XXS 61 → 65,5, IQ2_S 55 → 59 (+7-10%)**, hash uguali. **Bocciata**: gli spill costano più dei 4 blocchi; non entra nel banco |
| `STRATA_PEER_ONE_COPY=1` (una copia H2D nel peer) | 3c779296 | piano (1,9 KB, arrotondato a 2 KB) e righe x in un blocco bloccato, una `cudaMemcpyAsync` per strato invece di due; sul percorso diretto le righe passano da un memcpy di n_tok x 10 KB | solo col peer: `FK3` |

Incidente: un `ninja -n` con il ninja 1.13 di Python ha cancellato `.ninja_log` (v6) di `build-sm7586`; ricostruito da `ninja -t compdb` + MurmurHash64A (357/357 hash verificati sul registro di `_tmp-up`), così la build del riferimento è restata incrementale (6 oggetti + link, 220 s) invece di un rifacimento intero.

Primo tentativo della leva 2 con `template<int TG, int MINB = 1>`: `__launch_bounds__(256, 1)` non equivale a `__launch_bounds__(256)`, ptxas dava al kernel di default 87-95 registri (2 blocchi/SM). Corretto in 7a837206 con il corpo in una device function e due kernel; cuobjdump: default 71/77/78/63/77 come bee277a0.

Banco: `FK0` (testo a cache fissa, `--adapt-swaps 0`, 4K e 32K una corsa), `FK1` (banco completo alternato rif/lev/rif/lev/rif, due corse, leva = righe IQ3 forzate con `STRATA_MMVQ_IL_ROWS=21:n:2,2,2,2,2;18:n:2,2,2,2,2` per n 2-4 su entrambe le schede), `FK3` (peer: due copie contro una, `STRATA_PEER_STAMP`, contesto lungo, due coppie). Risultati sotto.

**FK0, testo a cache fissa**: `Krif0` (67908ef8) e `Klev0` (7a837206 + righe IQ3 forzate) **identici** a 4K (1217 caratteri) e a 32K (1137 caratteri), 256 token a T=0. Il motore prende le righe forzate da `STRATA_MMVQ_IL_ROWS` prima delle tabelle (`native_mmvq_il_rows_for`) con `STRATA_SM75_PERF=1`: il percorso interleaved IQ3_S era acceso su entrambe le schede.

## Sera del 2/11 e notte sul 3/11: parallelo vero, kernel, leve sm_86

- `--peer-device` provato sul serio (`Vpeer`): 52-56 t/s, attese host 21-31 ms a finestra. Banco `ep_bench`: server persistente 98-113 µs esposti a strato, quello guidato dall'host 118: il salto non e' il problema.
- Tappa 0 del parallelo vero (`STRATA_PEER_STAMP`): il server sulla 2080 Ti impiega ~300 µs di GPU a strato (p50 297-334), sopra la soglia di 250: workflow fermato dalla sessione. Modo esperti (`Xm*`): 8 resta il migliore (~290 µs), 4 ~325, 0 ~305.
- PR #4876 (`STRATA_GDN_TC=2`): +1,4/+1,5/+0,1% in lettura, nel rumore. PR #4942 con tabella: sotto il riferimento, la tabella emessa sulla 2080 Ti da' zeri per IQ3_XXS. Una sola copia d'ingresso nel peer: invariato. Variabili su Turing (`T*`): nessuna stacca.
- `STRATA_SA_BET=0`: invariato. Riga della scommessa: A intera 61-63%, bonus indovinato 56-57%.
- Con le schede miste la tabella sm_86 del motore non si applica. `STRATA_ADAPT_NOWAIT=1 STRATA_ADAPT_LAG=2` (`A*`): scrittura +1/+3%. Insieme con `STRATA_KQ_SPLIT=1 STRATA_GU_SWIGLU=1` (`C*`, coda staccata dalla sessione): lettura 925/1881/2234 contro 914/1837/2236, scrittura 101,0/101,5/105,0 contro 100,1/102,1/103,2: +0,7%, nel rumore, niente peggiora.
- Il motore lanciato come figlio della sessione l'ha fatta cadere e ha costretto a due riavvii: da qui le code partono con `lancia_staccato.ps1`.
