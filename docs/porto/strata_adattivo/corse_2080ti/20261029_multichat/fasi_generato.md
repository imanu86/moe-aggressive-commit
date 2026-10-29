# Dati generati da analisi_multichat.py (non editare a mano)


#### 01_R0

makespan 337.9 s; 17 richieste; token nuovi letti 441.510; token generati 3.560; TTFT medio 48.9 s. p90 110.8 s; attesa in coda media 31.6 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.59, max 3; serviti (legge o scrive) medio 1.00, max 1; in coda medio 1.59; che scrivono medio 0.13, max 1; che leggono medio 0.87, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 293 | 87% | 1.00 | 0.00 | 1509 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 45 | 13% | 0.00 | 1.00 | - | 79.8 (79.8/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 0.7 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 76.3 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.12).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 441.510 tok in 293 s = 1509 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 505 tok/s; 3-8K senza scrittori (6): 807 tok/s; 8-16K senza scrittori (4): 1032 tok/s; >50K senza scrittori (4): 1811 tok/s

#### 02_P

makespan 249.9 s; 17 richieste; token nuovi letti 181.454; token generati 4.146; TTFT medio 15.2 s. p90 53.6 s; attesa in coda media 5.0 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.50, max 3; serviti (legge o scrive) medio 2.16, max 3; in coda medio 0.34; che scrivono medio 1.47, max 3; che leggono medio 0.69, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 37 | 15% | 1.00 | 0.00 | 887 | - (-/agente) |
| (b) >=2 scrivono | 46 | 18% | 0.00 | 2.86 | - | 28.2 (9.8/agente) |
| (b1) 1 scrive | 27 | 11% | 0.00 | 1.00 | - | 51.9 (51.9/agente) |
| (c) mista | 136 | 54% | 1.00 | 1.54 | 1093 | 10.7 (7.0/agente) |
| (i) ferma | 4 | 2% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 34.2 t/s; 2+ scrivono senza letture 17.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.39).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 32.836 tok in 37 s = 887 tok/s; misto 148.618 tok in 136 s = 1093 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 395 tok/s; <3K con scrittori (1): 486 tok/s; 3-8K senza scrittori (1): 899 tok/s; 3-8K con scrittori (5): 702 tok/s; 8-16K senza scrittori (2): 1040 tok/s; 8-16K con scrittori (4): 921 tok/s; >50K con scrittori (1): 1623 tok/s
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 880 passi 1308 righe 87.9 s 14.9/s; 2x2 926 passi 1342 righe 85.0 s 15.8/s; 2x2 81 passi 81 righe 9.4 s 8.6/s

#### 03_PC

makespan 242.4 s; 17 richieste; token nuovi letti 182.517; token generati 4.040; TTFT medio 17.7 s. p90 34.7 s; attesa in coda media 6.4 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.50, max 3; serviti (legge o scrive) medio 2.04, max 3; in coda medio 0.45; che scrivono medio 1.25, max 3; che leggono medio 0.79, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 39 | 16% | 1.00 | 0.00 | 1030 | - (-/agente) |
| (b) >=2 scrivono | 28 | 12% | 0.00 | 2.30 | - | 38.3 (16.7/agente) |
| (b1) 1 scrive | 22 | 9% | 0.00 | 1.00 | - | 21.6 (21.6/agente) |
| (c) mista | 153 | 63% | 1.00 | 1.42 | 931 | 16.3 (11.4/agente) |
| (i) ferma | 0.1 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 23.3 t/s; 2+ scrivono senza letture 22.8 t/s; mentre qualcuno legge 8.7 t/s (scarto relativo 0.18).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 2.696 tok in 4 s = 607 tok/s; misto 171.267 tok in 176 s = 974 tok/s; parziale 8.554 tok in 12 s = 737 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 607 tok/s; <3K con scrittori (3): 282 tok/s; 3-8K con scrittori (6): 678 tok/s; 8-16K con scrittori (5): 897 tok/s; >50K con scrittori (1): 1485 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2318 righe in 130.8 s = 17.7 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 2689 tok in 3.9 s = 688 tok/s; con righe nel frattempo 179709 tok in 161.4 s = 1113 tok/s, 2318 righe = 14.4 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 784 passi 784 righe 48.9 s 16.0/s; 2x2 886 passi 1167 righe 47.6 s 24.5/s; 2x2 552 passi 757 righe 32.9 s 23.0/s; 2x2 88 passi 88 righe 6.9 s 12.8/s; 2x2 230 passi 230 righe 6.2 s 37.1/s; 2x2 61 passi 61 righe 3.9 s 15.6/s; 2x2 86 passi 86 righe 6.0 s 14.2/s; 2x2 196 passi 196 righe 13.1 s 15.0/s; 2x2 63 passi 63 righe 4.3 s 14.7/s; 2x2 250 passi 250 righe 11.8 s 21.2/s

#### 04_R0_6ag

makespan 1200.6 s; 34 richieste; token nuovi letti 1.889.802; token generati 7.579; TTFT medio 157.9 s. p90 261.7 s; attesa in coda media 125.4 s.
Agenti: in volo (coda+lettura+scrittura) medio 4.55, max 6; serviti (legge o scrive) medio 1.00, max 1; in coda medio 3.55; che scrivono medio 0.08, max 1; che leggono medio 0.92, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 1106 | 92% | 1.00 | 0.00 | 1709 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 93 | 8% | 0.00 | 1.00 | - | 81.1 (81.1/agente) |
| (c) mista | 0.1 | 0% | - | - | - | - |
| (i) ferma | 1 | 0% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 76.1 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.24).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 1.889.802 tok in 1106 s = 1709 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (5): 365 tok/s; 3-8K senza scrittori (4): 775 tok/s; 8-16K senza scrittori (5): 998 tok/s; >50K senza scrittori (20): 1795 tok/s

#### 05_PC_6ag

makespan 470.0 s; 34 richieste; token nuovi letti 419.215; token generati 7.346; TTFT medio 46.5 s. p90 106.8 s; attesa in coda media 34.3 s.
Agenti: in volo (coda+lettura+scrittura) medio 5.19, max 6; serviti (legge o scrive) medio 2.71, max 4; in coda medio 2.48; che scrivono medio 1.83, max 4; che leggono medio 0.88, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 43 | 9% | 1.00 | 0.00 | 1260 | - (-/agente) |
| (b) >=2 scrivono | 45 | 10% | 0.00 | 2.74 | - | 29.8 (10.9/agente) |
| (b1) 1 scrive | 10 | 2% | 0.00 | 1.00 | - | 12.1 (12.1/agente) |
| (c) mista | 372 | 79% | 1.00 | 1.95 | 981 | 15.8 (8.1/agente) |
| (i) ferma | 0.1 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 13.5 t/s; 2+ scrivono senza letture 3.5 t/s; mentre qualcuno legge 7.8 t/s (scarto relativo 0.32).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 2.510 tok in 5 s = 463 tok/s; misto 414.424 tok in 405 s = 1023 tok/s; parziale 2.281 tok in 5 s = 506 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 463 tok/s; <3K con scrittori (6): 235 tok/s; 3-8K con scrittori (10): 643 tok/s; 8-16K con scrittori (13): 863 tok/s; >50K con scrittori (3): 1510 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 5775 righe in 324.8 s = 17.8 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (34): senza righe nel frattempo 2503 tok in 4.0 s = 632 tok/s; con righe nel frattempo 416474 tok in 360.5 s = 1155 tok/s, 5775 righe = 16.0 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 18 passi 18 righe 1.1 s 16.6/s; 2x2 1901 passi 2357 righe 146.4 s 16.1/s; 2x2 1093 passi 1334 righe 73.2 s 18.2/s; 2x2 395 passi 588 righe 35.6 s 16.5/s; 2x2 2024 passi 2469 righe 142.9 s 17.3/s; 2x2 482 passi 482 righe 18.3 s 26.3/s

## Riepilogo (una riga per corsa)

| corsa | makespan s | TTFT medio / p90 s | in volo medio (max) | serviti medi (max) | scrivono medi (max) | token nuovi letti | token generati | (a) lettura tok/s | (b) scrittura agg. t/s: T / N (N per agente) | (c) lettura tok/s | (c) scrittura agg. t/s: T / N (N per agente) | quota a / b / c / ferma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01_R0 | 338 | 48.9 / 110.8 | 2.59 (3) | 1.00 (1) | 0.13 (1) | 441.510 | 3.560 | 1509 | - | n.d. | - | 87 / 13 / 0 / 0 |
| 02_P | 250 | 15.2 / 53.6 | 2.50 (3) | 2.16 (3) | 1.47 (3) | 181.454 | 4.146 | 887 | 28 / 49 (17.0) | 1093 | 11 / 0 (0.0) | 15 / 29 / 54 / 2 |
| 03_PC | 242 | 17.7 / 34.7 | 2.50 (3) | 2.04 (3) | 1.25 (3) | 182.517 | 4.040 | 1030 | 38 / 52 (22.8) | 931 | 16 / 12 (8.7) | 16 / 21 / 63 / 0 |
| 04_R0_6ag | 1201 | 157.9 / 261.7 | 4.55 (6) | 1.00 (1) | 0.08 (1) | 1.889.802 | 7.579 | 1709 | - | n.d. | - | 92 / 8 / 0 / 0 |
| 05_PC_6ag | 470 | 46.5 / 106.8 | 5.19 (6) | 2.71 (4) | 1.83 (4) | 419.215 | 7.346 | 1260 | 30 / 10 (3.5) | 981 | 16 / 15 (7.8) | 9 / 12 / 79 / 0 |

## Tabella per fasi (T = token uniformi nell intervallo; N = minimi quadrati; tempi in s, medie di corsa)

| braccio | (a) s | (a) lettura tok/s | (b) s | (b) scrittori | (b) agg. T / N | (b) per agente T | (b1) s | (b1) t/s | (c) s | (c) scrittori | (c) lettura tok/s | (c) scrittura agg. T / N | (c) per agente T | (i) s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01_R0 | 293 | 1509 | 0 | n.d. | n.d. / n.d. | n.d. | 45 | 80 | 0 | n.d. | n.d. | n.d. / n.d. | n.d. | 1 |
| 02_P | 37 | 887 | 46 | 2.86 | 28 / 49 | 9.8 | 27 | 52 | 136 | 1.54 | 1093 | 11 / 0 | 7.0 | 4 |
| 03_PC | 39 | 1030 | 28 | 2.30 | 38 / 52 | 16.7 | 22 | 22 | 153 | 1.42 | 931 | 16 / 12 | 11.4 | 0 |
| 04_R0_6ag | 1106 | 1709 | 0 | n.d. | n.d. / n.d. | n.d. | 93 | 81 | 0 | n.d. | n.d. | n.d. / n.d. | n.d. | 1 |
| 05_PC_6ag | 43 | 1260 | 45 | 2.74 | 30 / 10 | 10.9 | 10 | 12 | 372 | 1.95 | 981 | 16 / 15 | 8.1 | 0 |

## La stessa lettura grande (C#22: 77.619 token nuovi) in ogni corsa

| corsa | lettura s | tok/s | quota di tempo con qualcuno che scrive |
|---|---:|---:|---:|
| 01_R0 | 43.2 | 1798 | 0% |
| 02_P | 47.8 | 1623 | 100% |
| 03_PC | 52.3 | 1485 | 76% |
| 04_R0_6ag | 42.6 | 1742 | 0% |
| 05_PC_6ag | 48.6 | 1526 | 68% |
