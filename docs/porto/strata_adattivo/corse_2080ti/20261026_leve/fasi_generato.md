# Dati generati da analisi_fasi.py (non editare a mano)


#### 02_R3L

makespan 228.5 s; 17 richieste; token nuovi letti 181.566; token generati 3.915; TTFT medio 20.5 s. p90 55.1 s; attesa in coda media 8.8 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.70, max 3; serviti (legge o scrive) medio 2.05, max 3; in coda medio 0.65; che scrivono medio 1.18, max 3; che leggono medio 0.87, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 47 | 21% | 1.00 | 0.00 | 986 | - (-/agente) |
| (b) >=2 scrivono | 22 | 10% | 0.00 | 2.71 | - | 45.2 (16.7/agente) |
| (b1) 1 scrive | 7 | 3% | 0.00 | 1.00 | - | 13.2 (13.2/agente) |
| (c) mista | 152 | 66% | 1.00 | 1.33 | 889 | 18.6 (14.0/agente) |
| (i) ferma | 0.1 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 12.2 t/s; 2+ scrivono senza letture 23.7 t/s; mentre qualcuno legge 12.0 t/s (scarto relativo 0.10).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 2.696 tok in 5 s = 560 tok/s; misto 160.489 tok in 169 s = 951 tok/s; parziale 18.381 tok in 26 s = 720 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 560 tok/s; <3K con scrittori (3): 295 tok/s; 3-8K con scrittori (6): 627 tok/s; 8-16K con scrittori (4): 830 tok/s; >50K con scrittori (1): 1573 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2508 righe in 132.1 s = 19.0 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 2689 tok in 4.3 s = 629 tok/s; con righe nel frattempo 178758 tok in 169.6 s = 1054 tok/s, 2508 righe = 14.8 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 430 passi 430 righe 34.5 s 12.5/s; 2x2 1009 passi 1321 righe 47.9 s 27.6/s; 2x2 959 passi 1175 righe 44.4 s 26.5/s; 2x2 251 passi 382 righe 12.8 s 29.9/s; 2x2 21 passi 21 righe 1.9 s 10.8/s; 2x2 54 passi 54 righe 3.8 s 14.1/s; 2x2 202 passi 202 righe 13.5 s 14.9/s; 2x2 51 passi 51 righe 3.5 s 14.5/s; 2x2 259 passi 259 righe 12.4 s 21.0/s

#### 03_L1

makespan 242.8 s; 17 richieste; token nuovi letti 181.511; token generati 4.339; TTFT medio 20.8 s. p90 58.9 s; attesa in coda media 9.2 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.40, max 3; serviti (legge o scrive) medio 1.76, max 3; in coda medio 0.64; che scrivono medio 0.94, max 3; che leggono medio 0.82, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 77 | 32% | 1.00 | 0.00 | 1013 | - (-/agente) |
| (b) >=2 scrivono | 20 | 8% | 0.00 | 2.14 | - | 45.9 (21.4/agente) |
| (b1) 1 scrive | 24 | 10% | 0.00 | 1.00 | - | 32.9 (32.9/agente) |
| (c) mista | 121 | 50% | 1.00 | 1.33 | 854 | 21.6 (16.3/agente) |
| (i) ferma | 0.4 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 21.2 t/s; 2+ scrivono senza letture 28.6 t/s; mentre qualcuno legge 12.9 t/s (scarto relativo 0.25).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 21.741 tok in 29 s = 762 tok/s; misto 69.851 tok in 101 s = 690 tok/s; parziale 89.919 tok in 68 s = 1315 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K con scrittori (4): 327 tok/s; 3-8K senza scrittori (2): 705 tok/s; 3-8K con scrittori (3): 634 tok/s; 8-16K senza scrittori (1): 845 tok/s; 8-16K con scrittori (4): 818 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2429 righe in 104.9 s = 23.2 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 21720 tok in 25.1 s = 864 tok/s; con righe nel frattempo 159672 tok in 149.5 s = 1068 tok/s, 2429 righe = 16.3 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 242 passi 404 righe 24.2 s 16.7/s; 2x2 615 passi 1193 righe 42.3 s 28.2/s; 2x2 96 passi 154 righe 7.2 s 21.5/s; 2x2 434 passi 746 righe 24.4 s 30.5/s; 2x2 2 passi 3 righe 1.0 s 2.9/s; 2x2 382 passi 640 righe 19.9 s 32.1/s; 2x2 131 passi 227 righe 5.5 s 41.1/s; 2x2 82 passi 145 righe 4.5 s 32.0/s; 2x2 10 passi 20 righe 1.5 s 12.9/s; 2x2 105 passi 203 righe 11.4 s 17.7/s; 2x2 2 passi 3 righe 0.1 s 56.5/s

#### 04_R3L

makespan 241.6 s; 17 richieste; token nuovi letti 181.413; token generati 4.318; TTFT medio 18.6 s. p90 38.2 s; attesa in coda media 7.0 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.49, max 3; serviti (legge o scrive) medio 2.00, max 3; in coda medio 0.49; che scrivono medio 1.18, max 3; che leggono medio 0.82, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 50 | 21% | 1.00 | 0.00 | 966 | - (-/agente) |
| (b) >=2 scrivono | 24 | 10% | 0.00 | 2.40 | - | 41.0 (17.1/agente) |
| (b1) 1 scrive | 19 | 8% | 0.00 | 1.00 | - | 36.4 (36.4/agente) |
| (c) mista | 148 | 61% | 1.00 | 1.40 | 900 | 17.7 (12.6/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 24.8 t/s; 2+ scrivono senza letture 23.8 t/s; mentre qualcuno legge 9.8 t/s (scarto relativo 0.21).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 9.160 tok in 13 s = 696 tok/s; misto 153.813 tok in 159 s = 966 tok/s; parziale 18.440 tok in 25 s = 725 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 552 tok/s; <3K con scrittori (3): 295 tok/s; 3-8K senza scrittori (1): 782 tok/s; 3-8K con scrittori (5): 617 tok/s; 8-16K con scrittori (4): 842 tok/s; >50K con scrittori (1): 1521 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2401 righe in 129.9 s = 18.5 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 9146 tok in 11.7 s = 781 tok/s; con righe nel frattempo 172148 tok in 163.3 s = 1054 tok/s, 2401 righe = 14.7 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 790 passi 790 righe 45.4 s 17.4/s; 2x2 1035 passi 1310 righe 54.7 s 24.0/s; 2x2 253 passi 384 righe 16.2 s 23.7/s; 2x2 586 passi 586 righe 21.8 s 26.9/s; 2x2 102 passi 102 righe 6.5 s 15.6/s; 2x2 196 passi 196 righe 5.7 s 34.3/s; 2x2 89 passi 89 righe 3.9 s 22.7/s; 2x2 77 passi 77 righe 4.6 s 16.7/s; 2x2 190 passi 190 righe 14.2 s 13.4/s; 2x2 2 passi 2 righe 0.0 s 44.0/s

#### 05_R0

makespan 443.0 s; 17 richieste; token nuovi letti 602.748; token generati 4.041; TTFT medio 67.5 s. p90 115.8 s; attesa in coda media 44.7 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.71, max 3; serviti (legge o scrive) medio 1.00, max 1; in coda medio 1.71; che scrivono medio 0.12, max 1; che leggono medio 0.87, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 387 | 87% | 1.00 | 0.00 | 1556 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 55 | 12% | 0.00 | 1.00 | - | 73.7 (73.7/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 0.8 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 69.0 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.28).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 602.748 tok in 387 s = 1556 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 501 tok/s; 3-8K senza scrittori (4): 720 tok/s; 8-16K senza scrittori (4): 956 tok/s; >50K senza scrittori (6): 1777 tok/s

#### 06_R3

makespan 243.0 s; 17 richieste; token nuovi letti 181.742; token generati 4.554; TTFT medio 19.3 s. p90 38.1 s; attesa in coda media 7.7 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.53, max 3; serviti (legge o scrive) medio 1.99, max 3; in coda medio 0.54; che scrivono medio 1.18, max 3; che leggono medio 0.81, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 54 | 22% | 1.00 | 0.00 | 944 | - (-/agente) |
| (b) >=2 scrivono | 27 | 11% | 0.00 | 2.36 | - | 43.7 (18.5/agente) |
| (b1) 1 scrive | 19 | 8% | 0.00 | 1.00 | - | 35.6 (35.6/agente) |
| (c) mista | 142 | 59% | 1.00 | 1.44 | 915 | 19.0 (13.2/agente) |
| (i) ferma | 0.2 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 21.9 t/s; 2+ scrivono senza letture 25.2 t/s; mentre qualcuno legge 10.5 t/s (scarto relativo 0.21).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 9.177 tok in 13 s = 699 tok/s; misto 144.687 tok in 146 s = 990 tok/s; parziale 27.878 tok in 38 s = 741 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 554 tok/s; <3K con scrittori (3): 275 tok/s; 3-8K senza scrittori (1): 784 tok/s; 3-8K con scrittori (5): 627 tok/s; 8-16K con scrittori (3): 884 tok/s; >50K con scrittori (1): 1520 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2432 righe in 125.9 s = 19.3 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 9163 tok in 11.7 s = 784 tok/s; con righe nel frattempo 172460 tok in 163.1 s = 1057 tok/s, 2432 righe = 14.9 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 790 passi 790 righe 45.9 s 17.2/s; 2x2 986 passi 1353 righe 50.2 s 27.0/s; 2x2 53 passi 53 righe 3.4 s 15.5/s; 2x2 942 passi 1073 righe 36.1 s 29.7/s; 2x2 86 passi 86 righe 5.4 s 15.9/s; 2x2 228 passi 228 righe 6.3 s 36.0/s; 2x2 120 passi 120 righe 4.7 s 25.5/s; 2x2 56 passi 56 righe 3.4 s 16.3/s; 2x2 217 passi 217 righe 14.3 s 15.2/s; 2x2 2 passi 2 righe 0.0 s 43.4/s

#### 07_R0

makespan 448.9 s; 17 richieste; token nuovi letti 602.916; token generati 4.449; TTFT medio 68.0 s. p90 116.0 s; attesa in coda media 45.2 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.71, max 3; serviti (legge o scrive) medio 1.00, max 1; in coda medio 1.71; che scrivono medio 0.14, max 1; che leggono medio 0.86, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 387 | 86% | 1.00 | 0.00 | 1558 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 61 | 14% | 0.00 | 1.00 | - | 72.7 (72.7/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 0.8 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 72.8 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.14).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 602.916 tok in 387 s = 1558 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 494 tok/s; 3-8K senza scrittori (4): 725 tok/s; 8-16K senza scrittori (4): 958 tok/s; >50K senza scrittori (6): 1780 tok/s

#### 08_R2

makespan 251.2 s; 17 richieste; token nuovi letti 181.674; token generati 3.825; TTFT medio 12.9 s. p90 21.5 s; attesa in coda media 2.2 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.45, max 3; serviti (legge o scrive) medio 2.30, max 3; in coda medio 0.15; che scrivono medio 1.57, max 3; che leggono medio 0.72, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 36 | 14% | 1.00 | 0.00 | 776 | - (-/agente) |
| (b) >=2 scrivono | 39 | 15% | 0.00 | 2.70 | - | 24.5 (9.1/agente) |
| (b1) 1 scrive | 25 | 10% | 0.00 | 1.00 | - | 56.8 (56.8/agente) |
| (c) mista | 146 | 58% | 1.00 | 1.82 | 1054 | 9.9 (5.5/agente) |
| (i) ferma | 5 | 2% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 65.4 t/s; 2+ scrivono senza letture 11.0 t/s; mentre qualcuno legge 2.9 t/s (scarto relativo 0.27).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 28.108 tok in 36 s = 776 tok/s; misto 153.566 tok in 146 s = 1054 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 381 tok/s; <3K con scrittori (1): 511 tok/s; 3-8K senza scrittori (2): 687 tok/s; 3-8K con scrittori (4): 693 tok/s; 8-16K senza scrittori (1): 1090 tok/s; 8-16K con scrittori (5): 820 tok/s; >50K con scrittori (1): 1680 tok/s
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 899 passi 1324 righe 95.0 s 13.9/s; 2x2 488 passi 802 righe 79.8 s 10.1/s; 2x2 273 passi 273 righe 10.1 s 27.1/s

#### 09_R0

makespan 449.2 s; 17 richieste; token nuovi letti 602.753; token generati 4.621; TTFT medio 68.0 s. p90 117.3 s; attesa in coda media 45.2 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.71, max 3; serviti (legge o scrive) medio 1.00, max 1; in coda medio 1.71; che scrivono medio 0.14, max 1; che leggono medio 0.86, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 387 | 86% | 1.00 | 0.00 | 1557 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 61 | 14% | 0.00 | 1.00 | - | 75.4 (75.4/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 0.9 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 72.8 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.21).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 602.753 tok in 387 s = 1557 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 507 tok/s; 3-8K senza scrittori (4): 716 tok/s; 8-16K senza scrittori (4): 957 tok/s; >50K senza scrittori (6): 1780 tok/s

#### 10_R1

makespan 354.0 s; 17 richieste; token nuovi letti 180.643; token generati 3.977; TTFT medio 30.6 s. p90 93.4 s; attesa in coda media 12.7 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.53, max 3; serviti (legge o scrive) medio 1.92, max 3; in coda medio 0.61; che scrivono medio 1.07, max 3; che leggono medio 0.86, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 114 | 32% | 1.00 | 0.00 | 664 | - (-/agente) |
| (b) >=2 scrivono | 34 | 10% | 0.00 | 2.42 | - | 33.6 (13.9/agente) |
| (b1) 1 scrive | 17 | 5% | 0.00 | 1.00 | - | 20.8 (20.8/agente) |
| (c) mista | 189 | 53% | 1.00 | 1.48 | 555 | 13.2 (8.9/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 23.2 t/s; 2+ scrivono senza letture 22.1 t/s; mentre qualcuno legge 5.6 t/s (scarto relativo 0.23).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 12.151 tok in 16 s = 744 tok/s; misto 131.406 tok in 224 s = 586 tok/s; parziale 37.086 tok in 62 s = 595 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 574 tok/s; <3K con scrittori (3): 283 tok/s; 3-8K con scrittori (6): 471 tok/s; 8-16K senza scrittori (1): 812 tok/s; 8-16K con scrittori (2): 553 tok/s; >50K con scrittori (1): 691 tok/s
Motore, gruppo seriale: finestre di sola scrittura 3703 righe in 70.9 s = 52.2 righe/s, 1.86 righe per finestra.
Motore, gruppo seriale: 10 letture spezzate, scrittori fermi tra le parti 41.2 s in tutto; finestre: 536 finestre, 1.62 righe medie, 39.0 ms = 41.6 righe/s; 648 finestre, 2.36 righe medie, 38.6 ms = 61.1 righe/s; 237 finestre, 1.99 righe medie, 29.9 ms = 66.4 righe/s; 75 finestre, 1.00 righe medie, 31.9 ms = 31.4 righe/s; 96 finestre, 1.97 righe medie, 30.1 ms = 65.5 righe/s; 66 finestre, 1.95 righe medie, 29.3 ms = 66.5 righe/s; 37 finestre, 1.00 righe medie, 36.6 ms = 27.3 righe/s; 70 finestre, 1.00 righe medie, 32.3 ms = 30.9 righe/s; 207 finestre, 1.53 righe medie, 30.1 ms = 50.8 righe/s; 14 finestre, 1.00 righe medie, 52.8 ms = 18.9 righe/s; 3 finestre, 1.00 righe medie, 22.1 ms = 45.4 righe/s

#### 11_R0

makespan 409.9 s; 17 richieste; token nuovi letti 529.835; token generati 4.585; TTFT medio 59.6 s. p90 127.4 s; attesa in coda media 39.2 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.62, max 3; serviti (legge o scrive) medio 1.00, max 1; in coda medio 1.63; che scrivono medio 0.15, max 1; che leggono medio 0.84, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 346 | 84% | 1.00 | 0.00 | 1531 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 63 | 15% | 0.00 | 1.00 | - | 72.8 (72.8/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 0.9 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 71.8 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.12).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 529.835 tok in 346 s = 1531 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 416 tok/s; 3-8K senza scrittori (5): 755 tok/s; 8-16K senza scrittori (4): 927 tok/s; >50K senza scrittori (5): 1795 tok/s

#### 18_R3L

makespan 240.5 s; 17 richieste; token nuovi letti 181.796; token generati 4.312; TTFT medio 17.3 s. p90 28.8 s; attesa in coda media 5.6 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.45, max 3; serviti (legge o scrive) medio 2.05, max 3; in coda medio 0.39; che scrivono medio 1.22, max 3; che leggono medio 0.83, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 53 | 22% | 1.00 | 0.00 | 923 | - (-/agente) |
| (b) >=2 scrivono | 19 | 8% | 0.00 | 2.60 | - | 40.1 (15.4/agente) |
| (b1) 1 scrive | 22 | 9% | 0.00 | 1.00 | - | 38.1 (38.1/agente) |
| (c) mista | 146 | 61% | 1.00 | 1.53 | 911 | 18.5 (12.1/agente) |
| (i) ferma | 0.2 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 19.9 t/s; 2+ scrivono senza letture 26.2 t/s; mentre qualcuno legge 8.2 t/s (scarto relativo 0.23).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 9.162 tok in 13 s = 698 tok/s; misto 139.135 tok in 146 s = 956 tok/s; parziale 33.499 tok in 40 s = 834 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 554 tok/s; <3K con scrittori (3): 287 tok/s; 3-8K senza scrittori (1): 782 tok/s; 3-8K con scrittori (5): 625 tok/s; 8-16K con scrittori (3): 775 tok/s; >50K con scrittori (1): 1500 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2483 righe in 128.7 s = 19.3 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 9148 tok in 11.7 s = 782 tok/s; con righe nel frattempo 172529 tok in 164.2 s = 1051 tok/s, 2483 righe = 15.1 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 869 passi 869 righe 51.6 s 16.8/s; 2x2 1579 passi 2104 righe 81.1 s 25.9/s; 2x2 221 passi 221 righe 15.6 s 14.2/s; 2x2 94 passi 94 righe 3.7 s 25.4/s; 2x2 69 passi 69 righe 4.0 s 17.0/s; 2x2 96 passi 96 righe 3.5 s 27.8/s; 2x2 38 passi 38 righe 2.9 s 13.1/s; 2x2 27 passi 27 righe 2.7 s 9.9/s; 2x2 2 passi 2 righe 0.0 s 44.4/s

#### 19_L2

makespan 250.1 s; 17 richieste; token nuovi letti 181.676; token generati 4.360; TTFT medio 13.9 s. p90 19.1 s; attesa in coda media 2.6 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.38, max 3; serviti (legge o scrive) medio 2.20, max 3; in coda medio 0.18; che scrivono medio 1.43, max 3; che leggono medio 0.77, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 35 | 14% | 1.00 | 0.00 | 760 | - (-/agente) |
| (b) >=2 scrivono | 32 | 13% | 0.00 | 2.45 | - | 32.5 (13.2/agente) |
| (b1) 1 scrive | 23 | 9% | 0.00 | 1.00 | - | 44.0 (44.0/agente) |
| (c) mista | 158 | 63% | 1.00 | 1.62 | 985 | 14.5 (8.9/agente) |
| (i) ferma | 2 | 1% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 40.3 t/s; 2+ scrivono senza letture 25.5 t/s; mentre qualcuno legge 4.4 t/s (scarto relativo 0.22).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 24.273 tok in 30 s = 812 tok/s; misto 153.297 tok in 154 s = 998 tok/s; parziale 4.106 tok in 9 s = 459 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (2): 390 tok/s; <3K con scrittori (1): 472 tok/s; 3-8K senza scrittori (1): 782 tok/s; 3-8K con scrittori (4): 663 tok/s; 8-16K senza scrittori (1): 1048 tok/s; 8-16K con scrittori (5): 797 tok/s; >50K con scrittori (1): 1522 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 1587 righe in 141.3 s = 11.2 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 24245 tok in 26.3 s = 921 tok/s; con righe nel frattempo 157312 tok in 145.0 s = 1085 tok/s, 1587 righe = 10.9 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 855 passi 943 righe 66.3 s 14.2/s; 2x2 1183 passi 1522 righe 71.8 s 21.2/s; 2x2 232 passi 390 righe 20.0 s 19.5/s; 2x2 344 passi 344 righe 17.5 s 19.7/s; 2x2 137 passi 137 righe 13.9 s 9.9/s; 2x2 10 passi 10 righe 1.0 s 10.4/s; 2x2 2 passi 2 righe 0.0 s 42.7/s

#### 20_R3L

makespan 244.0 s; 17 richieste; token nuovi letti 181.254; token generati 4.691; TTFT medio 18.4 s. p90 40.7 s; attesa in coda media 6.6 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.54, max 3; serviti (legge o scrive) medio 2.08, max 3; in coda medio 0.46; che scrivono medio 1.25, max 3; che leggono medio 0.83, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 46 | 19% | 1.00 | 0.00 | 934 | - (-/agente) |
| (b) >=2 scrivono | 22 | 9% | 0.00 | 2.51 | - | 44.3 (17.6/agente) |
| (b1) 1 scrive | 20 | 8% | 0.00 | 1.00 | - | 36.3 (36.3/agente) |
| (c) mista | 155 | 64% | 1.00 | 1.48 | 890 | 19.2 (12.9/agente) |
| (i) ferma | 0.0 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 29.1 t/s; 2+ scrivono senza letture 25.0 t/s; mentre qualcuno legge 10.0 t/s (scarto relativo 0.17).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 5.387 tok in 8 s = 648 tok/s; misto 157.401 tok in 168 s = 936 tok/s; parziale 18.466 tok in 25 s = 741 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K con scrittori (4): 350 tok/s; 3-8K senza scrittori (1): 648 tok/s; 3-8K con scrittori (5): 614 tok/s; 8-16K con scrittori (4): 828 tok/s; >50K con scrittori (1): 1505 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2736 righe in 135.4 s = 20.2 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 5380 tok in 6.9 s = 782 tok/s; con righe nel frattempo 175755 tok in 169.5 s = 1037 tok/s, 2736 righe = 16.1 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 842 passi 842 righe 46.7 s 18.0/s; 2x2 1681 passi 2243 righe 82.8 s 27.1/s; 2x2 119 passi 119 righe 7.8 s 15.3/s; 2x2 187 passi 187 righe 5.0 s 37.7/s; 2x2 80 passi 80 righe 3.5 s 22.9/s; 2x2 52 passi 52 righe 3.4 s 15.3/s; 2x2 195 passi 195 righe 12.5 s 15.5/s; 2x2 56 passi 56 righe 3.9 s 14.5/s; 2x2 208 passi 208 righe 12.2 s 17.1/s

#### 21_L3

makespan 231.1 s; 17 richieste; token nuovi letti 181.898; token generati 3.976; TTFT medio 18.1 s. p90 55.1 s; attesa in coda media 6.6 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.51, max 3; serviti (legge o scrive) medio 2.02, max 3; in coda medio 0.49; che scrivono medio 1.18, max 3; che leggono medio 0.85, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 46 | 20% | 1.00 | 0.00 | 1053 | - (-/agente) |
| (b) >=2 scrivono | 13 | 6% | 0.00 | 2.68 | - | 34.8 (13.0/agente) |
| (b1) 1 scrive | 19 | 8% | 0.00 | 1.00 | - | 45.0 (45.0/agente) |
| (c) mista | 150 | 65% | 1.00 | 1.46 | 893 | 18.0 (12.3/agente) |
| (i) ferma | 4 | 2% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 54.3 t/s; 2+ scrivono senza letture 6.8 t/s; mentre qualcuno legge 11.7 t/s (scarto relativo 0.21).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 24.317 tok in 30 s = 813 tok/s; misto 157.581 tok in 166 s = 951 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 381 tok/s; <3K con scrittori (1): 476 tok/s; 3-8K senza scrittori (1): 742 tok/s; 3-8K con scrittori (5): 617 tok/s; 8-16K senza scrittori (1): 1099 tok/s; 8-16K con scrittori (5): 749 tok/s; >50K con scrittori (1): 1571 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2527 righe in 132.6 s = 19.1 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 24282 tok in 26.6 s = 913 tok/s; con righe nel frattempo 157497 tok in 148.0 s = 1064 tok/s, 2527 righe = 17.1 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 430 passi 430 righe 34.7 s 12.4/s; 2x2 1216 passi 1602 righe 61.2 s 26.2/s; 2x2 648 passi 928 righe 51.3 s 18.1/s; 2x2 202 passi 202 righe 14.1 s 14.3/s

#### 22_R3L

makespan 234.7 s; 17 richieste; token nuovi letti 181.530; token generati 4.413; TTFT medio 19.5 s. p90 55.2 s; attesa in coda media 7.7 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.69, max 3; serviti (legge o scrive) medio 2.13, max 3; in coda medio 0.56; che scrivono medio 1.28, max 3; che leggono medio 0.85, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 42 | 18% | 1.00 | 0.00 | 996 | - (-/agente) |
| (b) >=2 scrivono | 21 | 9% | 0.00 | 2.74 | - | 41.2 (15.0/agente) |
| (b1) 1 scrive | 14 | 6% | 0.00 | 1.00 | - | 42.1 (42.1/agente) |
| (c) mista | 157 | 67% | 1.00 | 1.46 | 886 | 18.9 (12.9/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 27.9 t/s; 2+ scrivono senza letture 19.9 t/s; mentre qualcuno legge 11.2 t/s (scarto relativo 0.18).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 9.319 tok in 14 s = 664 tok/s; misto 162.696 tok in 173 s = 941 tok/s; parziale 9.515 tok in 13 s = 750 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 556 tok/s; <3K con scrittori (3): 299 tok/s; 3-8K senza scrittori (1): 721 tok/s; 3-8K con scrittori (5): 613 tok/s; 8-16K con scrittori (5): 797 tok/s; >50K con scrittori (1): 1569 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2704 righe in 137.6 s = 19.7 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 9305 tok in 11.7 s = 794 tok/s; con righe nel frattempo 172106 tok in 163.6 s = 1052 tok/s, 2704 righe = 16.5 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 430 passi 430 righe 35.0 s 12.3/s; 2x2 885 passi 1218 righe 41.0 s 29.7/s; 2x2 94 passi 94 righe 5.4 s 17.5/s; 2x2 1478 passi 1932 righe 82.3 s 23.5/s; 2x2 195 passi 195 righe 14.7 s 13.3/s; 2x2 2 passi 2 righe 0.0 s 43.1/s

#### 23_L4

makespan 245.2 s; 17 richieste; token nuovi letti 180.354; token generati 4.647; TTFT medio 17.8 s. p90 37.6 s; attesa in coda media 5.8 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.48, max 3; serviti (legge o scrive) medio 2.07, max 3; in coda medio 0.40; che scrivono medio 1.24, max 3; che leggono medio 0.83, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 40 | 16% | 1.00 | 0.00 | 913 | - (-/agente) |
| (b) >=2 scrivono | 19 | 8% | 0.00 | 2.26 | - | 42.3 (18.7/agente) |
| (b1) 1 scrive | 23 | 9% | 0.00 | 1.00 | - | 34.6 (34.6/agente) |
| (c) mista | 164 | 67% | 1.00 | 1.46 | 881 | 18.7 (12.8/agente) |
| (i) ferma | 0.2 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 30.1 t/s; 2+ scrivono senza letture 27.2 t/s; mentre qualcuno legge 10.4 t/s (scarto relativo 0.17).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 11.835 tok in 17 s = 715 tok/s; misto 168.519 tok in 187 s = 903 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K con scrittori (4): 341 tok/s; 3-8K senza scrittori (2): 715 tok/s; 3-8K con scrittori (4): 577 tok/s; 8-16K con scrittori (6): 773 tok/s; >50K con scrittori (1): 1499 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2965 righe in 142.1 s = 20.9 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 11821 tok in 14.2 s = 833 tok/s; con righe nel frattempo 168414 tok in 162.9 s = 1034 tok/s, 2965 righe = 18.2 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 862 passi 862 righe 48.2 s 17.9/s; 2x2 1081 passi 1184 righe 46.5 s 25.5/s; 2x2 181 passi 181 righe 11.2 s 16.2/s; 2x2 929 passi 964 righe 36.1 s 26.7/s; 2x2 136 passi 136 righe 9.2 s 14.9/s; 2x2 246 passi 246 righe 6.2 s 40.0/s; 2x2 65 passi 65 righe 3.5 s 18.5/s; 2x2 133 passi 133 righe 8.5 s 15.6/s; 2x2 210 passi 210 righe 14.1 s 14.9/s; 2x2 2 passi 2 righe 0.0 s 43.9/s

#### 24_R3L

makespan 236.0 s; 17 richieste; token nuovi letti 181.578; token generati 4.061; TTFT medio 17.9 s. p90 34.0 s; attesa in coda media 6.3 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.45, max 3; serviti (legge o scrive) medio 2.00, max 3; in coda medio 0.45; che scrivono medio 1.16, max 3; che leggono medio 0.84, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 57 | 24% | 1.00 | 0.00 | 1005 | - (-/agente) |
| (b) >=2 scrivono | 18 | 7% | 0.00 | 2.53 | - | 37.3 (14.8/agente) |
| (b1) 1 scrive | 21 | 9% | 0.00 | 1.00 | - | 42.6 (42.6/agente) |
| (c) mista | 140 | 59% | 1.00 | 1.49 | 884 | 18.0 (12.1/agente) |
| (i) ferma | 0.4 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 25.3 t/s; 2+ scrivono senza letture 21.4 t/s; mentre qualcuno legge 8.4 t/s (scarto relativo 0.30).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 24.015 tok in 27 s = 899 tok/s; misto 147.560 tok in 158 s = 935 tok/s; parziale 10.003 tok in 13 s = 768 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 554 tok/s; <3K con scrittori (3): 273 tok/s; 3-8K senza scrittori (1): 786 tok/s; 3-8K con scrittori (5): 627 tok/s; 8-16K senza scrittori (1): 1092 tok/s; 8-16K con scrittori (4): 746 tok/s; >50K con scrittori (1): 1526 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2397 righe in 122.8 s = 19.5 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 23994 tok in 24.2 s = 990 tok/s; con righe nel frattempo 157465 tok in 150.2 s = 1049 tok/s, 2397 righe = 16.0 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 790 passi 790 righe 45.5 s 17.4/s; 2x2 887 passi 1184 righe 47.8 s 24.8/s; 2x2 959 passi 1055 righe 49.1 s 21.5/s; 2x2 59 passi 59 righe 3.9 s 15.2/s; 2x2 45 passi 45 righe 3.0 s 14.9/s; 2x2 107 passi 107 righe 7.3 s 14.7/s; 2x2 19 passi 19 righe 1.7 s 11.1/s; 2x2 2 passi 2 righe 0.0 s 44.7/s

#### ORIGINALE (sessione vera, tratto 3600-4800 s, solo A,B,C)


#### ORIGINALE

makespan 1438.9 s; 17 richieste; token nuovi letti 861.032; token generati 5.157; TTFT medio 229.9 s. p90 436.4 s; attesa in coda media 185.5 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.77, max 3; serviti (legge o scrive) medio 0.58, max 1; in coda medio 2.19; che scrivono medio 0.06, max 1; che leggono medio 0.52, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 753 | 52% | 1.00 | 0.00 | 1143 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 83 | 6% | 0.00 | 1.00 | - | 62.4 (62.4/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 603 | 42% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 64.9 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.18).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 861.015 tok in 753 s = 1144 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (3): 148 tok/s; 3-8K senza scrittori (2): 378 tok/s; 8-16K senza scrittori (3): 589 tok/s; >50K senza scrittori (9): 1221 tok/s

#### 19/10 c1-daily

makespan 937.5 s; 24 richieste; token nuovi letti 1.213.870; token generati 4.354; TTFT medio 136.4 s. p90 333.8 s; attesa in coda media 100.4 s.
Agenti: in volo (coda+lettura+scrittura) medio 3.57, max 4; serviti (legge o scrive) medio 1.00, max 1; in coda medio 2.57; che scrivono medio 0.07, max 1; che leggono medio 0.92, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 864 | 92% | 1.00 | 0.00 | 1404 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 70 | 7% | 0.00 | 1.00 | - | 62.4 (62.4/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 3 | 0% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 63.5 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.08).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 1.213.870 tok in 864 s = 1404 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (4): 412 tok/s; 3-8K senza scrittori (5): 635 tok/s; 8-16K senza scrittori (4): 837 tok/s; >50K senza scrittori (11): 1505 tok/s

#### 19/10 c1b-daily

makespan 1069.1 s; 24 richieste; token nuovi letti 1.448.789; token generati 3.750; TTFT medio 141.4 s. p90 274.8 s; attesa in coda media 99.5 s.
Agenti: in volo (coda+lettura+scrittura) medio 3.23, max 4; serviti (legge o scrive) medio 1.00, max 1; in coda medio 2.23; che scrivono medio 0.06, max 1; che leggono medio 0.94, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 1007 | 94% | 1.00 | 0.00 | 1439 | - (-/agente) |
| (b) >=2 scrivono | 0.0 | 0% | - | - | - | - |
| (b1) 1 scrive | 61 | 6% | 0.00 | 1.00 | - | 61.7 (61.7/agente) |
| (c) mista | 0.0 | 0% | - | - | - | - |
| (i) ferma | 2 | 0% | 0.00 | 0.00 | - | - (-/agente) |

Metodo N, scrittura per agente: 1 solo scrive 61.3 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 0.0 t/s (scarto relativo 0.07).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 1.448.789 tok in 1007 s = 1439 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (4): 377 tok/s; 3-8K senza scrittori (5): 618 tok/s; 8-16K senza scrittori (2): 772 tok/s; >50K senza scrittori (13): 1509 tok/s

#### 19/10 c2-g2cc

makespan 298.3 s; 24 richieste; token nuovi letti 193.378; token generati 3.905; TTFT medio 28.3 s. p90 76.5 s; attesa in coda media 17.2 s.
Agenti: in volo (coda+lettura+scrittura) medio 3.64, max 4; serviti (legge o scrive) medio 2.25, max 4; in coda medio 1.38; che scrivono medio 1.36, max 4; che leggono medio 0.90, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 44 | 15% | 1.00 | 0.00 | 866 | - (-/agente) |
| (b) >=2 scrivono | 22 | 7% | 0.00 | 2.47 | - | 31.8 (12.9/agente) |
| (b1) 1 scrive | 8 | 3% | 0.00 | 1.00 | - | 11.7 (11.7/agente) |
| (c) mista | 223 | 75% | 1.00 | 1.53 | 694 | 13.9 (9.1/agente) |
| (i) ferma | 0.1 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 90.7 t/s; 2+ scrivono senza letture 0.0 t/s; mentre qualcuno legge 6.2 t/s (scarto relativo 0.48).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 268 tok in 3 s = 79 tok/s; misto 188.081 tok in 256 s = 734 tok/s; parziale 5.029 tok in 8 s = 633 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 79 tok/s; <3K con scrittori (8): 265 tok/s; 3-8K con scrittori (7): 527 tok/s; 8-16K con scrittori (6): 706 tok/s; >50K con scrittori (1): 1265 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 3126 righe in 197.6 s = 15.8 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (24): senza righe nel frattempo 261 tok in 2.3 s = 115 tok/s; con righe nel frattempo 192949 tok in 235.1 s = 821 tok/s, 3126 righe = 13.3 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 115 passi 115 righe 7.9 s 14.5/s; 2x2 395 passi 563 righe 54.7 s 10.3/s; 2x2 407 passi 408 righe 22.0 s 18.5/s; 2x2 191 passi 293 righe 22.7 s 12.9/s; 2x2 797 passi 1050 righe 69.5 s 15.1/s; 2x2 108 passi 108 righe 7.9 s 13.7/s; 2x2 856 passi 968 righe 43.5 s 22.2/s; 2x2 352 passi 352 righe 17.6 s 20.0/s

#### 19/10 c2b-g2cc

makespan 302.2 s; 24 richieste; token nuovi letti 191.928; token generati 3.960; TTFT medio 24.0 s. p90 71.7 s; attesa in coda media 13.0 s.
Agenti: in volo (coda+lettura+scrittura) medio 3.15, max 4; serviti (legge o scrive) medio 2.12, max 4; in coda medio 1.03; che scrivono medio 1.25, max 4; che leggono medio 0.88, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 59 | 19% | 1.00 | 0.00 | 793 | - (-/agente) |
| (b) >=2 scrivono | 21 | 7% | 0.00 | 2.71 | - | 32.7 (12.0/agente) |
| (b1) 1 scrive | 17 | 5% | 0.00 | 1.00 | - | 22.8 (22.8/agente) |
| (c) mista | 206 | 68% | 1.00 | 1.48 | 706 | 14.1 (9.5/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 22.6 t/s; 2+ scrivono senza letture 13.4 t/s; mentre qualcuno legge 7.6 t/s (scarto relativo 0.29).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 6.833 tok in 13 s = 532 tok/s; misto 179.860 tok in 241 s = 745 tok/s; parziale 5.235 tok in 10 s = 501 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 79 tok/s; <3K con scrittori (7): 269 tok/s; 3-8K senza scrittori (1): 696 tok/s; 3-8K con scrittori (6): 502 tok/s; 8-16K con scrittori (6): 714 tok/s; >50K con scrittori (1): 1264 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2917 righe in 180.3 s = 16.2 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (24): senza righe nel frattempo 6819 tok in 10.8 s = 633 tok/s; con righe nel frattempo 184941 tok in 221.7 s = 834 tok/s, 2917 righe = 13.2 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 115 passi 115 righe 8.0 s 14.5/s; 2x2 386 passi 500 righe 55.6 s 9.0/s; 2x2 1154 passi 1461 righe 78.5 s 18.6/s; 2x2 833 passi 915 righe 46.9 s 19.5/s; 2x2 128 passi 128 righe 9.7 s 13.2/s; 2x2 270 passi 270 righe 7.5 s 36.1/s; 2x2 12 passi 12 righe 1.0 s 12.1/s; 2x2 115 passi 115 righe 7.8 s 14.7/s; 2x2 153 passi 153 righe 12.4 s 12.3/s; 2x2 2 passi 2 righe 0.0 s 41.8/s

#### 19/10 q1-b4-8ag

makespan 1138.9 s; 48 richieste; token nuovi letti 1.094.575; token generati 9.470; TTFT medio 130.1 s. p90 390.0 s; attesa in coda media 107.7 s.
Agenti: in volo (coda+lettura+scrittura) medio 6.34, max 8; serviti (legge o scrive) medio 1.80, max 4; in coda medio 4.54; che scrivono medio 0.86, max 4; che leggono medio 0.94, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 560 | 49% | 1.00 | 0.00 | 1184 | - (-/agente) |
| (b) >=2 scrivono | 40 | 4% | 0.00 | 2.75 | - | 34.6 (12.6/agente) |
| (b1) 1 scrive | 24 | 2% | 0.00 | 1.00 | - | 17.3 (17.3/agente) |
| (c) mista | 514 | 45% | 1.00 | 1.64 | 839 | 14.9 (9.1/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 4.0 t/s; 2+ scrivono senza letture 5.1 t/s; mentre qualcuno legge 9.5 t/s (scarto relativo 0.31).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 125.821 tok in 107 s = 1171 tok/s; misto 370.069 tok in 467 s = 793 tok/s; parziale 598.685 tok in 500 s = 1197 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (2): 59 tok/s; <3K con scrittori (13): 279 tok/s; 3-8K senza scrittori (1): 537 tok/s; 3-8K con scrittori (11): 534 tok/s; 8-16K con scrittori (8): 753 tok/s; >50K senza scrittori (1): 1285 tok/s; >50K con scrittori (3): 1108 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 7751 righe in 481.0 s = 16.1 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (49): senza righe nel frattempo 3803 tok in 9.4 s = 403 tok/s; con righe nel frattempo 1090436 tok in 1019.9 s = 1069 tok/s, 7751 righe = 7.6 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 213 passi 213 righe 11.1 s 19.3/s; 2x2 981 passi 1606 righe 78.4 s 20.5/s; 2x2 1226 passi 1495 righe 101.6 s 14.7/s; 2x2 920 passi 1126 righe 63.5 s 17.7/s; 2x2 843 passi 1176 righe 85.5 s 13.7/s; 2x2 3 passi 3 righe 0.6 s 4.7/s; 2x2 107 passi 107 righe 6.7 s 15.9/s; 2x2 1 passi 1 righe 0.0 s 25.7/s; 2x2 73 passi 73 righe 4.5 s 16.3/s; 2x2 1 passi 1 righe 0.0 s 25.7/s; 2x2 258 passi 258 righe 17.1 s 15.1/s; 2x2 65 passi 65 righe 3.8 s 16.9/s; 2x2 333 passi 333 righe 16.1 s 20.6/s; 2x2 51 passi 51 righe 5.6 s 9.0/s; 2x2 106 passi 106 righe 7.3 s 14.5/s; 2x2 201 passi 201 righe 13.4 s 15.0/s; 2x2 203 passi 203 righe 28.8 s 7.0/s; 2x2 89 passi 89 righe 5.5 s 16.2/s; 2x2 45 passi 45 righe 3.3 s 13.8/s; 2x2 364 passi 401 righe 24.1 s 16.7/s; 2x2 381 passi 464 righe 30.9 s 15.0/s; 2x2 172 passi 177 righe 14.8 s 11.9/s; 2x2 609 passi 912 righe 33.2 s 27.4/s

## Riepilogo (una riga per corsa)

| corsa | makespan s | TTFT medio / p90 s | in volo medio (max) | serviti medi (max) | scrivono medi (max) | token nuovi letti | token generati | (a) lettura tok/s | (b) scrittura agg. t/s: T / N (N per agente) | (c) lettura tok/s | (c) scrittura agg. t/s: T / N (N per agente) | quota a / b / c / ferma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 02_R3L | 229 | 20.5 / 55.1 | 2.70 (3) | 2.05 (3) | 1.18 (3) | 181.566 | 3.915 | 986 | 45 / 64 (23.7) | 889 | 19 / 16 (12.0) | 21 / 13 / 66 / 0 |
| 03_L1 | 243 | 20.8 / 58.9 | 2.40 (3) | 1.76 (3) | 0.94 (3) | 181.511 | 4.339 | 1013 | 46 / 61 (28.6) | 854 | 22 / 17 (12.9) | 32 / 18 / 50 / 0 |
| 04_R3L | 242 | 18.6 / 38.2 | 2.49 (3) | 2.00 (3) | 1.18 (3) | 181.413 | 4.318 | 966 | 41 / 57 (23.8) | 900 | 18 / 14 (9.8) | 21 / 18 / 61 / 0 |
| 05_R0 | 443 | 67.5 / 115.8 | 2.71 (3) | 1.00 (1) | 0.12 (1) | 602.748 | 4.041 | 1556 | - | n.d. | - | 87 / 12 / 0 / 0 |
| 06_R3 | 243 | 19.3 / 38.1 | 2.53 (3) | 1.99 (3) | 1.18 (3) | 181.742 | 4.554 | 944 | 44 / 59 (25.2) | 915 | 19 / 15 (10.5) | 22 / 19 / 59 / 0 |
| 07_R0 | 449 | 68.0 / 116.0 | 2.71 (3) | 1.00 (1) | 0.14 (1) | 602.916 | 4.449 | 1558 | - | n.d. | - | 86 / 14 / 0 / 0 |
| 08_R2 | 251 | 12.9 / 21.5 | 2.45 (3) | 2.30 (3) | 1.57 (3) | 181.674 | 3.825 | 776 | 24 / 30 (11.0) | 1054 | 10 / 5 (2.9) | 14 / 25 / 58 / 2 |
| 09_R0 | 449 | 68.0 / 117.3 | 2.71 (3) | 1.00 (1) | 0.14 (1) | 602.753 | 4.621 | 1557 | - | n.d. | - | 86 / 14 / 0 / 0 |
| 10_R1 | 354 | 30.6 / 93.4 | 2.53 (3) | 1.92 (3) | 1.07 (3) | 180.643 | 3.977 | 664 | 34 / 53 (22.1) | 555 | 13 / 8 (5.6) | 32 / 14 / 53 / 0 |
| 11_R0 | 410 | 59.6 / 127.4 | 2.62 (3) | 1.00 (1) | 0.15 (1) | 529.835 | 4.585 | 1531 | - | n.d. | - | 84 / 15 / 0 / 0 |
| 18_R3L | 240 | 17.3 / 28.8 | 2.45 (3) | 2.05 (3) | 1.22 (3) | 181.796 | 4.312 | 923 | 40 / 68 (26.2) | 911 | 19 / 13 (8.2) | 22 / 17 / 61 / 0 |
| 19_L2 | 250 | 13.9 / 19.1 | 2.38 (3) | 2.20 (3) | 1.43 (3) | 181.676 | 4.360 | 760 | 33 / 63 (25.5) | 985 | 14 / 7 (4.4) | 14 / 22 / 63 / 1 |
| 20_R3L | 244 | 18.4 / 40.7 | 2.54 (3) | 2.08 (3) | 1.25 (3) | 181.254 | 4.691 | 934 | 44 / 63 (25.0) | 890 | 19 / 15 (10.0) | 19 / 17 / 64 / 0 |
| 21_L3 | 231 | 18.1 / 55.1 | 2.51 (3) | 2.02 (3) | 1.18 (3) | 181.898 | 3.976 | 1053 | 35 / 18 (6.8) | 893 | 18 / 17 (11.7) | 20 / 14 / 65 / 2 |
| 22_R3L | 235 | 19.5 / 55.2 | 2.69 (3) | 2.13 (3) | 1.28 (3) | 181.530 | 4.413 | 996 | 41 / 55 (19.9) | 886 | 19 / 16 (11.2) | 18 / 15 / 67 / 0 |
| 23_L4 | 245 | 17.8 / 37.6 | 2.48 (3) | 2.07 (3) | 1.24 (3) | 180.354 | 4.647 | 913 | 42 / 62 (27.2) | 881 | 19 / 15 (10.4) | 16 / 17 / 67 / 0 |
| 24_R3L | 236 | 17.9 / 34.0 | 2.45 (3) | 2.00 (3) | 1.16 (3) | 181.578 | 4.061 | 1005 | 37 / 54 (21.4) | 884 | 18 / 13 (8.4) | 24 / 16 / 59 / 0 |
| ORIGINALE | 1439 | 229.9 / 436.4 | 2.77 (3) | 0.58 (1) | 0.06 (1) | 861.032 | 5.157 | 1143 | - | n.d. | - | 52 / 6 / 0 / 42 |
| 19/10 c1-daily | 938 | 136.4 / 333.8 | 3.57 (4) | 1.00 (1) | 0.07 (1) | 1.213.870 | 4.354 | 1404 | - | n.d. | - | 92 / 7 / 0 / 0 |
| 19/10 c1b-daily | 1069 | 141.4 / 274.8 | 3.23 (4) | 1.00 (1) | 0.06 (1) | 1.448.789 | 3.750 | 1439 | - | n.d. | - | 94 / 6 / 0 / 0 |
| 19/10 c2-g2cc | 298 | 28.3 / 76.5 | 3.64 (4) | 2.25 (4) | 1.36 (4) | 193.378 | 3.905 | 866 | 32 / - | 694 | 14 / 9 (6.2) | 15 / 10 / 75 / 0 |
| 19/10 c2b-g2cc | 302 | 24.0 / 71.7 | 3.15 (4) | 2.12 (4) | 1.25 (4) | 191.928 | 3.960 | 793 | 33 / 36 (13.4) | 706 | 14 / 11 (7.6) | 19 / 12 / 68 / 0 |
| 19/10 q1-b4-8ag | 1139 | 130.1 / 390.0 | 6.34 (8) | 1.80 (4) | 0.86 (4) | 1.094.575 | 9.470 | 1184 | 35 / 14 (5.1) | 839 | 15 / 16 (9.5) | 49 / 6 / 45 / 0 |
| R0 (4 corse: 05.07.09.11) | 438 | 65.8 / 119.1 | 2.69 (3) | 1.00 (1) | 0.14 (1) | 584.563 | 4.424 | 1551 | - | n.d. | - | 86 / 14 / 0 / 0 |
| R3L (6 corse: 02.04.18.20.22.24) | 238 | 18.7 / 42.0 | 2.55 (3) | 2.05 (3) | 1.21 (3) | 181.523 | 4.285 | 968 | 42 / 61 (23.5) | 893 | 18 / 14 (9.8) | 21 / 16 / 63 / 0 |

## Tabella per fasi (T = token uniformi nell intervallo; N = minimi quadrati; tempi in s, medie di corsa)

| braccio | (a) s | (a) lettura tok/s | (b) s | (b) scrittori | (b) agg. T / N | (b) per agente T | (b1) s | (b1) t/s | (c) s | (c) scrittori | (c) lettura tok/s | (c) scrittura agg. T / N | (c) per agente T | (i) s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 (4 corse: 05,07,09,11) | 377 | 1551 | 0 | n.d. | n.d. / n.d. | n.d. | 60 | 74 | 0 | n.d. | n.d. | n.d. / n.d. | n.d. | 1 |
| 10_R1 | 114 | 664 | 34 | 2.42 | 34 / 53 | 13.9 | 17 | 21 | 189 | 1.48 | 555 | 13 / 8 | 8.9 | 0 |
| 08_R2 | 36 | 776 | 39 | 2.70 | 24 / 30 | 9.1 | 25 | 57 | 146 | 1.82 | 1054 | 10 / 5 | 5.5 | 5 |
| 06_R3 | 54 | 944 | 27 | 2.36 | 44 / 59 | 18.5 | 19 | 36 | 142 | 1.44 | 915 | 19 / 15 | 13.2 | 0 |
| R3L (6 corse: 02,04,18,20,22,24) | 49 | 968 | 21 | 2.58 | 42 / 61 | 16.2 | 17 | 37 | 150 | 1.45 | 893 | 18 / 14 | 12.8 | 0 |
| 03_L1 | 77 | 1013 | 20 | 2.14 | 46 / 61 | 21.4 | 24 | 33 | 121 | 1.33 | 854 | 22 / 17 | 16.3 | 0 |
| 19_L2 | 35 | 760 | 32 | 2.45 | 33 / 63 | 13.2 | 23 | 44 | 158 | 1.62 | 985 | 14 / 7 | 8.9 | 2 |
| 21_L3 | 46 | 1053 | 13 | 2.68 | 35 / 18 | 13.0 | 19 | 45 | 150 | 1.46 | 893 | 18 / 17 | 12.3 | 4 |
| 23_L4 | 40 | 913 | 19 | 2.26 | 42 / 62 | 18.7 | 23 | 35 | 164 | 1.46 | 881 | 19 / 15 | 12.8 | 0 |
| ORIGINALE | 753 | 1143 | 0 | n.d. | n.d. / n.d. | n.d. | 83 | 62 | 0 | n.d. | n.d. | n.d. / n.d. | n.d. | 603 |

## La stessa lettura grande (C#22: 77.619 token nuovi) in ogni corsa

| corsa | lettura s | tok/s | quota di tempo con qualcuno che scrive |
|---|---:|---:|---:|
| 02_R3L | 49.3 | 1573 | 70% |
| 03_L1 | 49.7 | 1562 | 49% |
| 04_R3L | 51.0 | 1521 | 70% |
| 05_R0 | 44.0 | 1765 | 0% |
| 06_R3 | 51.1 | 1520 | 72% |
| 07_R0 | 43.9 | 1768 | 0% |
| 08_R2 | 46.2 | 1680 | 100% |
| 09_R0 | 44.1 | 1762 | 0% |
| 10_R1 | 112.3 | 691 | 51% |
| 11_R0 | 43.9 | 1769 | 0% |
| 18_R3L | 51.8 | 1500 | 81% |
| 19_L2 | 51.0 | 1522 | 100% |
| 20_R3L | 51.6 | 1505 | 79% |
| 21_L3 | 49.4 | 1571 | 70% |
| 22_R3L | 49.5 | 1569 | 71% |
| 23_L4 | 51.8 | 1499 | 81% |
| 24_R3L | 50.9 | 1526 | 71% |

## Stima S: server seriale con la cache grande (nessuna corsa lo ha misurato)

Lettura singola adattata sulle 4 corse R0: tempo = 4.63 s + token/1961 tok/s; scrittura singola R0 73.6 t/s. Piano e pensiero della corsa 06_R3; stesso numero di token nuovi di 06_R3 (cache come R3).

- piano di 06_R3: tempo per finire 233 s (misurato in quella corsa: 243 s); TTFT medio 31.6 s, p90 67.3 s (misurati: 19.3 / 38.1).
- piano di 08_R2: tempo per finire 223 s (misurato in quella corsa: 251 s); TTFT medio 30.9 s, p90 67.3 s (misurati: 12.9 / 21.5).
- piano di 02_R3L: tempo per finire 224 s (misurato in quella corsa: 229 s); TTFT medio 31.4 s, p90 67.3 s (misurati: 20.5 / 55.1).
- piano di 24_R3L: tempo per finire 226 s (misurato in quella corsa: 236 s); TTFT medio 31.1 s, p90 66.8 s (misurati: 17.9 / 34.0).
