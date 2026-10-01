# PR #270 sulla 2080 Ti: prefill +22% — 1 ottobre 2026

**Compilazione, correttezza numerica e prova del modello completate.** Con KV 262.144 e lo stesso prompt
freddo da 131.248 token, la candidata passa da 661,76 a 808,91 token/s (+22,24%). Il primo token arriva
36,12 secondi prima. Nessun carico artificiale; programmi dell'utente lasciati aperti. Su richiesta dell'utente
si e' passati direttamente alla #270: il riempimento del prompt fino a circa 250k resta da verificare.

## Build e provenienza

- Base: `D:\ds4_work\strata\Strata\build-0130`, Strata 0.1.30 + 13 patch, clone `main` a `ade7160`.
- PR locale `pr-270`, commit `3d3939dbe395bcad8197b81f5f319cc40302f889`.
- Modificato solo `src/kernels/cuda/qsa_prompt_attn.cu`: ricompilazione CUDA 12.6/C++20, sm_75 e sm_86,
  poi ricostruzione della libreria e collegamento con tutti gli altri oggetti originali della build 0130.
- Candidata: `.codex_runs/strata_pr270_20261001/strata.exe`, separata dalla build operativa.
- SHA256 eseguibile: `713922610f2820b0e726adc371eb774a7d5502a548d08b59d244afbb38e898ed`.
- Clone, build originale e lanciatore Desktop preservati. Nessun download. Il primo tentativo fallito di
  compilazione era un problema di avvio della catena: l'invocazione diretta da Python ha prodotto oggetto ed eseguibile.

Strumento ripetibile: `strumenti/compila_pr270.py`. Prima di ricompilare controlla che il sorgente base corrisponda
al parent della PR e che non siano attivi altri motori. Riutilizza gli oggetti della build originale: per riprodurre
questo confronto occorre preservare quella build, oltre ai sorgenti.

## Correttezza e tempi del kernel

Il target originale `qsa_prompt_attn_parity` confronta il percorso tensor core con il precedente e con un
riferimento CPU FP64. Otto casi superati, zero fallimenti: int8/fp16 a contesto 32.768, query 128/2.048,
piu' casi int8 a contesto 1.500 e 2.100 per la transizione fra selezione completa e sparsa.

| Caso principale: contesto 32.768, query 2.048 | Precedente | PR #270 | Rapporto |
|---|---:|---:|---:|
| int8 | 65,359 ms | 20,161 ms | 3,24x |
| fp16 | 62,498 ms | 25,067 ms | 2,49x |

Una ripetizione cronometrata per caso: questi tempi sono indicativi del solo kernel. Nel caso principale int8,
errore massimo contro FP64 4,17e-6, differenza massima contro il percorso precedente 6,56e-6, pari a circa
1,7e-6 della scala dell'output. Soglie del test rispettate; **non e' identico bit per bit**.
Non sono stati eseguiti test di qualita' linguistica: il banco misura tempi e completamento del budget,
con 1.024 token di reasoning e senza risposta finale di testo nei due casi della candidata.

## Modello completo: candidata e riferimento ravvicinato

Profilo `lungo_131k`, KV int8 262.144, residenti 32.768, riserva 1.393 MiB, cache elastica a due zone,
stessi parametri MTP e watchdog 240 s. API loopback `127.0.0.1:18120`; chiave esclusa dal solo processo
di laboratorio, senza leggerla o modificare la configurazione operativa.

Sequenza delle corse: riferimento precedente (A1), candidata (B), riferimento ripetuto subito dopo (A2).

| Misura | A1: base precedente | B: PR #270 | A2: base successiva |
|---|---:|---:|---:|
| Prefill freddo L01 | 663,01 t/s | **808,91 t/s** | 661,76 t/s |
| Primo token L01 | 198,591 s | **162,980 s** | 199,103 s |
| Decode L01 | 46,104 t/s | 46,584 t/s | 44,634 t/s |
| Decode L02 | 40,373 t/s | 41,503 t/s | 40,061 t/s |
| Decode aggregato | 43,049 t/s | 43,897 t/s | 42,224 t/s |
| Costo per riga di verifica | 19,8 ms | 19,3 ms | 19,7 ms |

L01 legge tutti i 131.248 token. L02 ha 131.239 token, ma ne riusa 131.072: legge solo 167 token nuovi,
quindi non rappresenta un secondo prefill completo. Entrambe le richieste della candidata e del riferimento A2
finiscono con `length`, 1.024 token, senza errore CUDA, stallo o intervento del watchdog.

Il prefill guadagna **22,24%** rispetto ad A2, con **18,14%** di riduzione del tempo al primo token.
I due riferimenti di prefill sono vicini fra loro; resta una singola corsa completa della candidata,
con carico reale e cache dinamica. Il decode varia con testo, accettazione delle bozze e residenza degli esperti:
il piccolo miglioramento osservato non dimostra un'accelerazione dei kernel di decode causata dalla #270.

Cache iniziale B: 7.273 slot, core 3.604 e tail 3.669; crescita a 7.574, poi calo a 7.417 durante il prompt.
A2 parte da 7.317 slot. RAM minima B 32,35 GB, A2 32,16 GB. CPU degli altri processi, includendo avvio e prove:
B media 0,60 core (massimo 1,97), A2 media 0,68 (massimo 1,67). Sampler ogni 10 s; nessun polling GPU ripetuto.

## Avvio e pulizia

Primo avvio della candidata: **222,91 s**, caricamento esperti 0,20 GiB/s. A2: **55,91 s**, 1,14 GiB/s.
Per verificare il ritardo si e' ripetuto solo l'avvio della stessa candidata, senza prompt: **60,92 s**,
1,01 GiB/s, health `max_context=262144`. Il ritardo del primo caricamento non si e' ripetuto; la causa non e'
stata identificata. I tempi di avvio restano separati dal prefill.

Terminati soltanto i processi di laboratorio avviati da queste prove; verificata l'assenza di Strata/llama-server
rimasti accesi alla fine.

## Evidenza e stato operativo

`corse_2080ti/20261001_pr270/` contiene compilazione e parita', configurazioni, health, metriche iniziali,
risultati, log e campioni CPU/RAM. Sottocartelle `candidata`, `riferimento_dopo`, `riavvio`.
Temporanei e output completi restano nelle corse `.codex_runs/20261001_054515_pr270_kv262k_prompt131k`,
`20261001_055247_base_dopo_pr270_kv262k_prompt131k`, `20261001_055815_pr270_riavvio_kv262k`.

`strumenti/prova_kv262k.py --exe <candidata> --nome <etichetta>` ripete il banco; `--solo-avvio` controlla
solo caricamento e capacita'. Richiede il Python 3.12 integrato o un Python funzionante con le dipendenze del clone.

## Promozione operativa autorizzata, dopo l'accesso completo

L'utente ha richiesto di aggiornare il lanciatore e poi fermarsi in standby. Installata la build verificata in
`D:\ds4_work\strata\Strata\build-0130-pr270\strata.exe`: hash SHA256 identico alla candidata dei test.
Il consueto BAT Desktop ora controlla questa build e usa il JSON operativo con **max-context 262144**.
Nel JSON cambiano soltanto exe e max-context; restano KV int8, residenti 32768 e tutti gli altri parametri.
Conservati build-0130 e i sorgenti del clone; nessun processo del modello lasciato in esecuzione.

Backup precedente alla promozione: `D:\ds4_work\strata\ripristini\20261001_060447_pr270_262k\`, contenente
JSON operativo, BAT Desktop e manifest `promozione.json`. Per ripristinare, a motore fermo copiare il JSON nella
cartella del clone e il BAT nella sua cartella Desktop; torneranno build-0130 e contesto 139264.
Il manifest della promozione e' anche in `corse_2080ti/20261001_pr270/promozione.json`.

Controlli di installazione superati: hash eseguibile, confronto JSON contro il backup (solo le due modifiche
previste), identita' delle copie versionate del BAT/JSON, Python del lanciatore con dipendenze, `strata --help`
e `serve/server.py --help`. Nessuna ulteriore corsa lunga: l'eseguibile installato e' quello gia' verificato.
I blocchi di scrittura della precedente sessione protetta sono stati rimossi dall'accesso completo.
