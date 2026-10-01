# Validazione e promozione Strata 0.1.30 — 1 ottobre 2026

Le due prove richieste dall'handoff sono completate: pressione sulla VRAM e contesto a 131k. Il lanciatore esistente
del Desktop e la configurazione operativa ora selezionano `build-0130\strata.exe`. Nome e porta del lanciatore restano
quelli conosciuti dall'utente.

## Build e configurazione

- RTX 2080 Ti da 22 GB, sola GPU presente; Ryzen 7 5800X, 96 GB RAM.
- Clone `D:\ds4_work\strata\Strata`, branch `main`, commit `ade7160`: 0.1.30 + 13 commit locali.
- Riserva iniziale 1.393 MiB, `--elastic`, contesto 139.264, KV int8, `--kv-resident 32768`, profilo esperti originale.
- Kernel #186 nella modalita' predefinita: `STRATA_GR_V3` non impostata; #258 e #284 presenti nella build.
- `STRATA_WATCHDOG_S=240`; nella prova a 131k anche `STRATA_SPLIT_TIMING=1`.
- Banco sulla sola interfaccia `127.0.0.1:18120`, senza chiave: variabile `STRATA_API_KEY` esclusa dal solo processo
  di laboratorio. Nessuna lettura, stampa o modifica della chiave del lanciatore operativo.
- Impronta dell'eseguibile, commit e dimensione in `corse_2080ti/20261001_0130_validazione/build.json`.

Un primo lancio di laboratorio e' stato interrotto durante l'avvio: PowerShell 7 conserva una variabile impostata
a stringa vuota e Strata 0.1.30 rifiuta una chiave esplicitamente vuota. Nessuna misura da quel tentativo; le corse
valide seguenti escludono del tutto la variabile dall'ambiente figlio.

## Pressione: 4.000 MiB per 60 secondi

Comando, con `STRATA_WATCHDOG_S=240` e variabile API esclusa dal processo di laboratorio:

```text
python strumenti/prova_hog.py --elastico si --exe D:\ds4_work\strata\Strata\build-0130\strata.exe --hog-mib 4000 --nome p0130_validazione_4g_20261001
```

Altri programmi: 3.018 MiB di VRAM all'avvio. `hog.exe` ha allocato e mantenuto tutti i 4.000 MiB dal secondo 20
per 60 secondi, poi li ha rilasciati. Generazione completata: **4.096 token in 99,2 s**, 41,3 token/s lato motore.
Lo script conta 4.096 delta nello stream; il log del motore conferma 4.096 token generati.

| Intervallo dal primo token | Token/s nello stream |
|---|---:|
| 0–10 s | 49,1 |
| 10–20 s | 49,8 |
| 20–30 s | 31,1 |
| 30–40 s | 38,2 |
| 40–50 s | 41,8 |
| 50–60 s | 39,4 |
| 60–70 s | 39,6 |
| 70–80 s | 40,6 |
| 80–90 s | 42,0 |
| 90–fine | 38,0* |

*Ultima finestra parziale: lo script divide comunque per 10 s.*

Cache iniziale: 6.783 slot, **nucleo fisso 3.357** (5,48 GiB) e coda 3.426 (5,48 GiB). Crescita fino a 7.291;
sotto pressione calo fino a **4.400 slot** (7,15 GiB), sempre sopra il nucleo. Dopo il rilascio crescita a 4.461.
Colpi in cache 75,5%. Nessuno stallo o errore CUDA segnalato e richiesta completata. Il comportamento sotto pressione
e' validato per questo carico e questa durata; il confronto con i 95,9 s del 30/9 e' storico, senza A/B contestuale.

## Contesto a 131k

```text
python strumenti/prova_sm75.py --exe D:\ds4_work\strata\Strata\build-0130\strata.exe --riserva 1393 --elastic --nome q0130_validazione_131k_20261001 --profilo lungo_131k --env STRATA_SPLIT_TIMING=1
```

Altri programmi: 3.132 MiB di VRAM all'avvio. Due riscaldamenti da 8 token, poi entrambe le fixture del profilo.

| Caso | Prompt | Riusati | Prefill token/s | Decode token/s | Primo token | Output |
|---|---:|---:|---:|---:|---:|---:|
| L01 | 131.248 | 0 | **628,75** | **42,414** | 209,431 s | 1.024 |
| L02 | 131.239 | 131.072 | 79,08* | **41,131** | 2,716 s | 1.024 |

*L02 legge solo 167 token nuovi: questa velocita' non misura un secondo prefill completo a 131k.*

Entrambe terminate con `finish_reason=length`, raggiungendo il budget. **Decode aggregato 41,763 token/s**;
da `costo_passata.py`: **20,4 ms per riga**, 41,2 ms per finestra, 1,72 token e 2,02 righe per finestra.
Colpi in cache 88,3% / 89,6%. Nessuno stallo o errore CUDA segnalato; prestito al prefill e successiva generazione
completati. Primo avvio 7.328 slot, nucleo fisso 3.630; crescita fino a 7.670, poi assestamento a 7.667 slot.

La CPU degli altri processi, nei 31 campioni dell'intera corsa (compreso avvio e prefill), usa in media **0,86 core**,
massimo 1,66. RAM disponibile minima 33,9 GB. I valori `proc` del campionatore sono gia' espressi in core; sommarli
direttamente, senza dividere ancora per 100.

Rispetto al riferimento storico 0.1.29 (35,1 token/s, 24,2 ms/riga, prefill 614 token/s), questa corsa e' migliore.
Carico e testi generati possono cambiare: **non e' un A/B nella stessa sessione e non isola il contributo della versione**.
La promozione si basa sul completamento delle due prove di robustezza richieste, insieme alle misure rapide gia'
registrate nell'handoff, non su una promessa di guadagno costante del 19%.

## Evidenza e ripristino

Log integrali del motore, server, hog, campioni CPU e risultati del banco in
`corse_2080ti/20261001_0130_validazione/`. Gli output testuali delle fixture restano nel banco locale
`D:\ds4_work\strata\banco_run\20261001_042836_f0_q0130_validazione_131k_20261001_lungo_131k`.

Prima della promozione, JSON operativo e bat del Desktop coincidevano byte per byte con quelli del repository.
Copie precedenti conservate in `D:\ds4_work\strata\ripristini\20261001_0130\`. Per tornare alla 0.1.29, a motore
spento, ripristinare entrambi:

```powershell
Copy-Item -LiteralPath 'D:\ds4_work\strata\ripristini\20261001_0130\strata-2080ti-sota.json' -Destination 'D:\ds4_work\strata\Strata\strata-2080ti-sota.json'
Copy-Item -LiteralPath 'D:\ds4_work\strata\ripristini\20261001_0130\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat' -Destination 'C:\Users\imanu\Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat'
```

Prossimo passo dell'handoff: valutare #270 sul prefill a 131k e #317 sul blocco iniziale; nessuna delle due e' stata
applicata in questa validazione. Daily, seconda GPU e pubblicazione del clone Strata restano fuori da questo giro.
