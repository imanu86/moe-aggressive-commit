# Dati generati da analisi_multichat.py (non editare a mano)


#### 01_p_s20

makespan 238.5 s; 17 richieste; token nuovi letti 181.211; token generati 4.639; TTFT medio 15.9 s. p90 23.0 s; attesa in coda media 5.0 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.47, max 3; serviti (legge o scrive) medio 2.12, max 3; in coda medio 0.36; che scrivono medio 1.34, max 3; che leggono medio 0.78, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 23 | 10% | 1.00 | 0.00 | 972 | - (-/agente) |
| (b) >=2 scrivono | 28 | 12% | 0.00 | 2.24 | - | 39.3 (17.6/agente) |
| (b1) 1 scrive | 24 | 10% | 0.00 | 1.00 | - | 30.8 (30.8/agente) |
| (c) mista | 163 | 68% | 1.00 | 1.42 | 975 | 17.1 (12.0/agente) |
| (i) ferma | 0.1 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 31.8 t/s; 2+ scrivono senza letture 23.8 t/s; mentre qualcuno legge 8.6 t/s (scarto relativo 0.18).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 2.696 tok in 4 s = 600 tok/s; misto 178.515 tok in 181 s = 984 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 600 tok/s; <3K con scrittori (3): 256 tok/s; 3-8K con scrittori (6): 668 tok/s; 8-16K con scrittori (6): 871 tok/s; >50K con scrittori (1): 1677 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2576 righe in 133.0 s = 19.4 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 2689 tok in 3.9 s = 682 tok/s; con righe nel frattempo 178403 tok in 148.5 s = 1201 tok/s, 2576 righe = 17.3 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 857 passi 857 righe 50.3 s 17.0/s; 2x2 1477 passi 2048 righe 80.9 s 25.3/s; 2x2 180 passi 180 righe 12.3 s 14.6/s; 2x2 260 passi 260 righe 7.3 s 35.5/s; 2x2 132 passi 132 righe 4.9 s 27.1/s; 2x2 106 passi 106 righe 6.8 s 15.5/s; 2x2 151 passi 151 righe 11.2 s 13.5/s; 2x2 83 passi 83 righe 6.4 s 13.0/s; 2x2 177 passi 177 righe 11.4 s 15.5/s

#### 02_u_s20

makespan 236.9 s; 17 richieste; token nuovi letti 181.373; token generati 4.600; TTFT medio 18.5 s. p90 50.8 s; attesa in coda media 7.7 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.64, max 3; serviti (legge o scrive) medio 2.09, max 3; in coda medio 0.55; che scrivono medio 1.31, max 3; che leggono medio 0.78, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 32 | 13% | 1.00 | 0.00 | 1049 | - (-/agente) |
| (b) >=2 scrivono | 30 | 13% | 0.00 | 2.72 | - | 42.7 (15.7/agente) |
| (b1) 1 scrive | 23 | 10% | 0.00 | 1.00 | - | 27.6 (27.6/agente) |
| (c) mista | 152 | 64% | 1.00 | 1.36 | 975 | 17.7 (13.0/agente) |
| (i) ferma | 0.1 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 11.0 t/s; 2+ scrivono senza letture 21.5 t/s; mentre qualcuno legge 9.7 t/s (scarto relativo 0.22).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 2.696 tok in 5 s = 589 tok/s; misto 174.506 tok in 173 s = 1011 tok/s; parziale 4.171 tok in 6 s = 658 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 589 tok/s; <3K con scrittori (3): 275 tok/s; 3-8K con scrittori (5): 685 tok/s; 8-16K con scrittori (6): 870 tok/s; >50K con scrittori (1): 1724 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2368 righe in 123.7 s = 19.1 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 2689 tok in 4.0 s = 668 tok/s; con righe nel frattempo 178565 tok in 146.5 s = 1219 tok/s, 2368 righe = 16.2 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 430 passi 430 righe 34.9 s 12.3/s; 2x2 930 passi 1303 righe 41.0 s 31.8/s; 2x2 39 passi 39 righe 2.6 s 14.9/s; 2x2 1009 passi 1172 righe 43.2 s 27.1/s; 2x2 343 passi 479 righe 17.5 s 27.3/s; 2x2 103 passi 103 righe 8.1 s 12.7/s; 2x2 200 passi 200 righe 15.9 s 12.6/s; 2x2 78 passi 78 righe 6.4 s 12.1/s; 2x2 231 passi 231 righe 12.4 s 18.7/s

#### 03_c_s20

makespan 241.8 s; 17 richieste; token nuovi letti 181.630; token generati 4.586; TTFT medio 15.8 s. p90 24.0 s; attesa in coda media 5.0 s.
Agenti: in volo (coda+lettura+scrittura) medio 2.47, max 3; serviti (legge o scrive) medio 2.11, max 3; in coda medio 0.35; che scrivono medio 1.36, max 3; che leggono medio 0.76, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 37 | 15% | 1.00 | 0.00 | 968 | - (-/agente) |
| (b) >=2 scrivono | 32 | 13% | 0.00 | 2.51 | - | 35.4 (14.1/agente) |
| (b1) 1 scrive | 27 | 11% | 0.00 | 1.00 | - | 31.6 (31.6/agente) |
| (c) mista | 145 | 60% | 1.00 | 1.52 | 1002 | 17.9 (11.8/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 17.4 t/s; 2+ scrivono senza letture 18.7 t/s; mentre qualcuno legge 9.8 t/s (scarto relativo 0.21).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 9.166 tok in 12 s = 793 tok/s; misto 153.951 tok in 148 s = 1038 tok/s; parziale 18.513 tok in 23 s = 816 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 590 tok/s; <3K con scrittori (3): 267 tok/s; 3-8K senza scrittori (1): 926 tok/s; 3-8K con scrittori (5): 668 tok/s; 8-16K con scrittori (4): 904 tok/s; >50K con scrittori (1): 1690 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 2328 righe in 120.5 s = 19.3 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (17): senza righe nel frattempo 9152 tok in 10.1 s = 906 tok/s; con righe nel frattempo 172359 tok in 141.8 s = 1216 tok/s, 2328 righe = 16.4 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 816 passi 816 righe 48.9 s 16.7/s; 2x2 1574 passi 2130 righe 82.4 s 25.9/s; 2x2 363 passi 363 righe 17.5 s 20.8/s; 2x2 121 passi 121 righe 5.0 s 24.3/s; 2x2 64 passi 64 righe 3.9 s 16.3/s; 2x2 269 passi 269 righe 6.7 s 40.4/s; 2x2 28 passi 28 righe 3.4 s 8.3/s; 2x2 134 passi 134 righe 10.3 s 13.0/s; 2x2 2 passi 2 righe 0.0 s 51.5/s

#### 04_u_s20_6ag

makespan 414.2 s; 34 richieste; token nuovi letti 358.274; token generati 7.062; TTFT medio 39.7 s. p90 106.2 s; attesa in coda media 29.1 s.
Agenti: in volo (coda+lettura+scrittura) medio 4.89, max 6; serviti (legge o scrive) medio 2.50, max 4; in coda medio 2.39; che scrivono medio 1.64, max 4; che leggono medio 0.87, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 39 | 9% | 1.00 | 0.00 | 1231 | - (-/agente) |
| (b) >=2 scrivono | 35 | 9% | 0.00 | 2.96 | - | 28.5 (9.6/agente) |
| (b1) 1 scrive | 20 | 5% | 0.00 | 1.00 | - | 45.7 (45.7/agente) |
| (c) mista | 320 | 77% | 1.00 | 1.73 | 970 | 16.1 (9.3/agente) |
| (i) ferma | 0.3 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 22.6 t/s; 2+ scrivono senza letture 10.2 t/s; mentre qualcuno legge 8.0 t/s (scarto relativo 0.27).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 10.053 tok in 14 s = 729 tok/s; misto 348.221 tok in 345 s = 1009 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (1): 409 tok/s; <3K con scrittori (8): 288 tok/s; 3-8K senza scrittori (1): 986 tok/s; 3-8K con scrittori (9): 673 tok/s; 8-16K con scrittori (13): 902 tok/s; >50K con scrittori (2): 1724 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 5070 righe in 269.6 s = 18.8 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (34): senza righe nel frattempo 10039 tok in 10.9 s = 924 tok/s; con righe nel frattempo 347997 tok in 293.0 s = 1188 tok/s, 5070 righe = 17.3 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 475 passi 475 righe 33.4 s 14.2/s; 2x2 516 passi 726 righe 47.9 s 15.2/s; 2x2 2081 passi 3013 righe 139.9 s 21.5/s; 2x2 409 passi 465 righe 35.0 s 13.3/s; 2x2 1232 passi 1489 righe 99.0 s 15.0/s; 2x2 2 passi 2 righe 0.1 s 34.8/s

#### 05_c_s20_6ag

makespan 392.9 s; 34 richieste; token nuovi letti 359.853; token generati 4.445; TTFT medio 40.8 s. p90 77.8 s; attesa in coda media 30.4 s.
Agenti: in volo (coda+lettura+scrittura) medio 4.76, max 6; serviti (legge o scrive) medio 2.13, max 4; in coda medio 2.63; che scrivono medio 1.23, max 4; che leggono medio 0.90, max 1 (tempo con 2+ letture insieme: 0.0 s).

| fase (metodo T) | s | quota | letture medie | scrittori medi | lettura tok/s | scrittura t/s aggregato |
|---|---:|---:|---:|---:|---:|---:|
| (a) solo letture | 89 | 23% | 1.00 | 0.00 | 947 | - (-/agente) |
| (b) >=2 scrivono | 18 | 5% | 0.00 | 2.91 | - | 25.6 (8.8/agente) |
| (b1) 1 scrive | 20 | 5% | 0.00 | 1.00 | - | 8.3 (8.3/agente) |
| (c) mista | 266 | 68% | 1.00 | 1.55 | 1036 | 14.4 (9.3/agente) |
| (i) ferma | 0.2 | 0% | - | - | - | - |

Metodo N, scrittura per agente: 1 solo scrive 2.8 t/s; 2+ scrivono senza letture 2.7 t/s; mentre qualcuno legge 9.4 t/s (scarto relativo 0.26).
Lettura misurata dal server (token nuovi / prompt_ms) per richiesta, divisa per sovrapposizione con chi scrive: puro 2.598 tok in 9 s = 294 tok/s; misto 314.083 tok in 293 s = 1072 tok/s; parziale 43.172 tok in 53 s = 813 tok/s
Lettura per taglia (token nuovi / tempo di lettura del server): <3K senza scrittori (2): 294 tok/s; <3K con scrittori (6): 293 tok/s; 3-8K con scrittori (10): 703 tok/s; 8-16K con scrittori (9): 984 tok/s; >50K con scrittori (2): 1682 tok/s
Motore, righe/s sul solo tempo in cui qualcuno scrive durante le letture: 3993 righe in 228.8 s = 17.5 righe/s (tempo dalla ricostruzione).
Motore, letture «su un thread proprio» (34): senza righe nel frattempo 2584 tok in 5.2 s = 492 tok/s; con righe nel frattempo 357031 tok in 295.1 s = 1210 tok/s, 3993 righe = 13.5 righe/s sul tempo intero delle letture.
Motore, sessioni batch pipeline (gruppi, slot, passi, righe, ms, righe/s, ammissioni incluse): 2x2 138 passi 138 righe 9.5 s 14.6/s; 2x2 1043 passi 1108 righe 77.8 s 14.2/s; 2x2 189 passi 189 righe 27.9 s 6.8/s; 2x2 266 passi 266 righe 17.4 s 15.3/s; 2x2 1176 passi 1835 righe 88.1 s 20.8/s; 2x2 117 passi 117 righe 7.2 s 16.3/s; 2x2 2 passi 2 righe 0.0 s 42.9/s; 2x2 14 passi 14 righe 1.5 s 9.6/s; 2x2 131 passi 131 righe 7.6 s 17.2/s; 2x2 144 passi 144 righe 9.8 s 14.7/s; 2x2 15 passi 15 righe 1.8 s 8.2/s; 2x2 196 passi 196 righe 14.0 s 14.0/s; 2x2 51 passi 51 righe 5.9 s 8.7/s; 2x2 106 passi 106 righe 7.8 s 13.6/s; 2x2 48 passi 48 righe 4.7 s 10.2/s; 2x2 40 passi 40 righe 4.4 s 9.2/s; 2x2 2 passi 2 righe 0.0 s 51.1/s

## Riepilogo (una riga per corsa)

| corsa | makespan s | TTFT medio / p90 s | in volo medio (max) | serviti medi (max) | scrivono medi (max) | token nuovi letti | token generati | (a) lettura tok/s | (b) scrittura agg. t/s: T / N (N per agente) | (c) lettura tok/s | (c) scrittura agg. t/s: T / N (N per agente) | quota a / b / c / ferma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01_p_s20 | 239 | 15.9 / 23.0 | 2.47 (3) | 2.12 (3) | 1.34 (3) | 181.211 | 4.639 | 972 | 39 / 53 (23.8) | 975 | 17 / 12 (8.6) | 10 / 22 / 68 / 0 |
| 02_u_s20 | 237 | 18.5 / 50.8 | 2.64 (3) | 2.09 (3) | 1.31 (3) | 181.373 | 4.600 | 1049 | 43 / 59 (21.5) | 975 | 18 / 13 (9.7) | 13 / 22 / 64 / 0 |
| 03_c_s20 | 242 | 15.8 / 24.0 | 2.47 (3) | 2.11 (3) | 1.36 (3) | 181.630 | 4.586 | 968 | 35 / 47 (18.7) | 1002 | 18 / 15 (9.8) | 15 / 24 / 60 / 0 |
| 04_u_s20_6ag | 414 | 39.7 / 106.2 | 4.89 (6) | 2.50 (4) | 1.64 (4) | 358.274 | 7.062 | 1231 | 28 / 30 (10.2) | 970 | 16 / 14 (8.0) | 9 / 13 / 77 / 0 |
| 05_c_s20_6ag | 393 | 40.8 / 77.8 | 4.76 (6) | 2.13 (4) | 1.23 (4) | 359.853 | 4.445 | 947 | 26 / 8 (2.7) | 1036 | 14 / 15 (9.4) | 23 / 10 / 68 / 0 |

## Tabella per fasi (T = token uniformi nell intervallo; N = minimi quadrati; tempi in s, medie di corsa)

| braccio | (a) s | (a) lettura tok/s | (b) s | (b) scrittori | (b) agg. T / N | (b) per agente T | (b1) s | (b1) t/s | (c) s | (c) scrittori | (c) lettura tok/s | (c) scrittura agg. T / N | (c) per agente T | (i) s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 01_p_s20 | 23 | 972 | 28 | 2.24 | 39 / 53 | 17.6 | 24 | 31 | 163 | 1.42 | 975 | 17 / 12 | 12.0 | 0 |
| 02_u_s20 | 32 | 1049 | 30 | 2.72 | 43 / 59 | 15.7 | 23 | 28 | 152 | 1.36 | 975 | 18 / 13 | 13.0 | 0 |
| 03_c_s20 | 37 | 968 | 32 | 2.51 | 35 / 47 | 14.1 | 27 | 32 | 145 | 1.52 | 1002 | 18 / 15 | 11.8 | 0 |
| 04_u_s20_6ag | 39 | 1231 | 35 | 2.96 | 28 / 30 | 9.6 | 20 | 46 | 320 | 1.73 | 970 | 16 / 14 | 9.3 | 0 |
| 05_c_s20_6ag | 89 | 947 | 18 | 2.91 | 26 / 8 | 8.8 | 20 | 8 | 266 | 1.55 | 1036 | 14 / 15 | 9.3 | 0 |

## La stessa lettura grande (C#22: 77.619 token nuovi) in ogni corsa

| corsa | lettura s | tok/s | quota di tempo con qualcuno che scrive |
|---|---:|---:|---:|
| 01_p_s20 | 46.3 | 1677 | 90% |
| 02_u_s20 | 45.0 | 1724 | 77% |
| 03_c_s20 | 45.9 | 1690 | 87% |
| 04_u_s20_6ag | 42.1 | 1759 | 62% |
| 05_c_s20_6ag | 42.6 | 1740 | 65% |
