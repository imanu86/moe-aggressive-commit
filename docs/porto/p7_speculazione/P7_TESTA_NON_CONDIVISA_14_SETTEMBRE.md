# P7 · cella 2 — testa MTP non condivisa — 14 settembre 2026

Operatore: cella 2 di P7 del piano CPU/GPU verso 50 t/s. Macchina: RTX 3060 12 GB, Ryzen 5800X
(16 thread), 96 GB DDR4, Windows 11. Modello Qwen3.8-Flash-Next UD-IQ3_XXS, 64 slot di cache esperti.

**Nessuna modifica di codice e nessuna build in questa cella: solo preset e corse.** Binari
sperimentali ORIGINALI `qwen38_clean\build\bin` (gli stessi di M1/M2). `bin_prod`, i sorgenti, il
lanciatore quotidiano e il modello non sono stati toccati. Nessun commit.

---

## 0. Verdetto in tre righe

1. **M4 non migliora M1**, ne' sul t/s dell'insieme libero (**22,6316 contro 28,6646, −21,03%**) ne'
   sull'accettazione alla prima posizione (**0,7832 contro 0,7851, −0,24%**). **M5 non e' stato
   eseguito**, come da protocollo (nessuna delle due condizioni di innesco e' soddisfatta).
2. Il crollo del t/s **non e' un difetto della testa**: e' un'**anomalia di sistema** isolata a 2
   richieste su 16 (`L07@ctx32k`, `L08@ctx32k`), correlata a **RAM disponibile sotto i 4 GB**
   (mai successo in M1, minimo 4,86 GB) e a un crollo della potenza GPU (81 W contro 135 W a clock
   *piu' alto*, non piu' basso: firma di stallo di trasporto, non di calcolo). Depurando quei due
   casi, il t/s "pulito" salirebbe a 29,04 (+1,3% su M1) — ma **anche cosi' l'accettazione resta
   piatta o leggermente peggiore** (0,7797 contro 0,7851 sul sottoinsieme pulito), quindi la
   decisione di fermarsi non cambia.
3. **Correttezza confermata**: le impronte SHA256 di M4 sono **identiche a quelle di M1, tutte le 18
   (16 casi + 2 riscaldamenti)**, byte per byte. La testa non condivisa produce lo stesso identico
   testo della testa condivisa, come deve essere in greedy con verifica esatta: scambiare la testa
   non cambia il risultato, solo il costo.

---

## 1. Manopole usate

M4 e' identico a `preset_M1_p7.json` (bozza 1 token, `--spec-draft-n-max 1`), con **un'unica
differenza**: il file della testa MTP.

| manopola | M1 (riferimento) | M4 (candidato) |
|---|---|---|
| `-md` / `file_bozza` | `mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf` (2.786.568.256 B) | `mtp-Qwen3.8-Flash-Next-Q8_0.gguf` (4.137.429.120 B, **non condivisa, mai provata prima di oggi**) |
| `--spec-draft-n-max` / `-n-min` / `-p-min` | 1 / 1 / 0 | identico |
| `-otd` | `.*ffn_.*_exps.*=CUDA0_Mapped` | identico |
| `-ctkd` / `-ctvd` | `q8_0` / `q8_0` | identico |
| `QWEN4EXP_SPARSE_FA` | 0 | identico |
| `MOE_SLOTS` / `--moe-expert-cache` | 64 | identico |
| tutto il resto (contesto 262144, `-b`/`-ub` 2048, `-t 16`, `-np 1`, `--jinja --reasoning on`, greedy seed 1234) | identico | identico |

Preset in repo: `docs/porto/banco_p0/preset_M4_p7.json`. Profilo `solo_libero`, budget `screening`
(1024 token), una replica.

---

## 2. Tabella M1 / M4

`t/s` = somma token accettati finali / somma tempo di generazione del server (`predicted_n` /
`predicted_ms`), come da protocollo.

| cella | t/s libero | ms/token acc. | corto | ctx32k | accettazione | corto | ctx32k | token/passata | costo testa (ms/tok abbozzato) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **M1 — testa condivisa** | **28,6646** | 34,886 | 29,875 | 27,529 | **0,7851** | 0,7917 | 0,7785 | 1,79 | **5,674** |
| **M4 — testa non condivisa** | **22,6316** | 44,186 | 30,134 | 18,055 | **0,7832** | 0,7870 | 0,7793 | 1,78 | **5,991** |

Token accettati / tempo, per cella: M1 15.741 / 549,145 s · M4 15.741 / 695,531 s (**stesso identico
numero di token accettati**, unica differenza il tempo impiegato). Nessun NaN, nessun `error`,
nessun `assert` nel log del server.

### Delta

| confronto | insieme libero | solo corto (non contaminato) | solo ctx32k (contaminato, vedi §3) |
|---|---:|---:|---:|
| **M4 / M1 — t/s** | **−21,03%** | **+0,87%** | **−34,41%** |
| **M4 / M1 — accettazione** | **−0,24%** | −0,59% | +0,10% |
| M4 / M1 — costo testa per token abbozzato | **+5,59%** (5,991 contro 5,674 ms) | — | — |

**Soglia della cella: +5% sul riferimento M1.** Non raggiunta su nessuna lettura ufficiale
dell'insieme libero. Sul solo sottoinsieme `corto` — l'unico non toccato dall'anomalia — la
differenza e' **+0,87%**, dentro il rumore (l'A/B nullo di P0 misura 0,06% di variabilita' di
controllo, ma con **una sola replica per cella qui** un'oscillazione dell'ordine dell'1% non puo'
essere distinta da un vero effetto piccolo; resta comunque **lontanissima dal +5%**).

---

## 3. L'anomalia: `L07@ctx32k` e `L08@ctx32k`

Le ultime due delle otto richieste `ctx32k` (settima e ottava della sequenza, quindi con la storia
di cache/RAM piu' lunga) hanno un tempo di generazione **3-4 volte piu' lungo del previsto**, a
parita' di accettazione e di prefill:

| task | `eval time` (decode) | atteso (~M1) | accettazione | prompt eval | wall client |
|---|---:|---:|---:|---:|---:|
| `L07@ctx32k` (task 7774) | **113.689,79 ms** | ~37.200 ms | 0,774 (normale) | 2.334,85 ms (normale) | 116,08 s |
| `L08@ctx32k` (task 8354) | **110.275,67 ms** | ~36.600 ms | 0,841 (normale) | 2.652,23 ms (normale) | 112,99 s |

L'accettazione e il tempo di prefill sono **entrambi normali**: non e' un problema di qualita' della
bozza ne' di lettura del prefisso. Solo il decode (`eval time`) esplode.

### Firma nella sonda di carico

Confrontando gli ultimi campioni di `carico.jsonl` di M4 con gli ultimi di M1 (stessa posizione
nella sequenza):

| | M1 (`L07`/`L08@ctx32k`) | M4 (`L07`/`L08@ctx32k`) |
|---|---:|---:|
| RAM disponibile | **4,86 - 6,22 GB** (minimo dell'intera corsa) | **3,84 - 4,00 GB** (minimo dell'intera corsa, mai toccato in M1) |
| Watt GPU | 118 - 145 W (normale) | **81 - 83 W** (crollo) |
| Clock SM | 1927 MHz | **1935 - 1950 MHz** (uguale o PIU' alto, non piu' basso) |
| Temperatura GPU | ~63 °C | **51 - 58 °C** (in calo) |
| `gpu_util_pct` | 94-99% | 95-100% (invariato) |

**Lettura:** clock alto + temperatura in calo + potenza dimezzata, a fronte di un'utilizzazione GPU
dichiarata comunque al 95-100%, e' la firma di un GPU che lancia kernel piccoli e frequenti restando
per lo piu' in attesa (di trasporto PCIe, di pagine, di un mutex) invece di calcolare: la metrica
"utilizzazione" di `nvidia-smi` conta qualunque kernel attivo, anche minuscolo, ma i watt seguono il
lavoro reale. Non e' termico (il clock non scende, la temperatura scende). E' correlato con la
**RAM disponibile scesa sotto i 4 GB**, soglia mai toccata nella replica M1 (minimo 4,86 GB): la
testa non condivisa mappa da RAM ~1,5 GB di esperti in piu' della condivisa (4.137 MB contro 2.786
MB su disco), e con 92 GB di RAM gia' impegnati su 96 il margine si e' esaurito proprio nelle ultime
due richieste della sequenza, quelle con lo storico di cache piu' lungo.

**Questa e' un'ipotesi correlazionale, non isolata sperimentalmente**: non e' stato ripetuto un
braccio a RAM piu' libera per falsificarla (vedi §6, difetto 1). Resta pero' l'unica differenza di
sistema misurata fra M1 e M4 in quella finestra, ed e' coerente in direzione, ampiezza e tempistica.

### Che cosa cambia nel verdetto se si esclude l'anomalia

Togliendo `L07@ctx32k` e `L08@ctx32k` dal calcolo (post-hoc, **non e' il numero ufficiale della
cella**, il protocollo chiede tutti e otto i casi):

- token accettati: 15.741 − 1.024 − 1.024 = 13.693
- tempo di generazione: 695,531 − 113,690 − 110,276 = 471,566 s
- **t/s "pulito": 29,037** (+1,30% su M1, ancora lontano dal +5%)
- accettazione sui rimanenti 6 casi ctx32k + 8 corto: (8814−576−555 draft, 6903−446−467 accettati) =
  **0,7797**, ancora **sotto** 0,7851 di M1.

Anche nello scenario piu' favorevole alla leva, **l'accettazione non migliora**: la seconda
condizione di innesco di M5 resta non soddisfatta, e la prima (t/s) supera si' M1 ma di un margine
(+1,3%) compatibile con rumore a singola replica. Il verdetto non cambia.

---

## 4. Impronte

| confronto | uguali | diverse |
|---|---:|---|
| M4 contro riferimento MTP spento (`20260914_072049_P0_sper_ibrido_assente_r1`) | **10 / 18** (2 riscaldamenti + tutti e 8 i casi `ctx32k`) | tutti e 8 i casi `corto` |
| **M4 contro M1** | **18 / 18 — TUTTE identiche** | nessuna |

Lo schema contro il riferimento MTP spento e' **identico a quello di M1** (stesso elenco di casi
uguali/diversi, stessa spiegazione: a 32k il *gather* satura e la verifica esatta riproduce il
riferimento byte per byte; a contesto corto i tre bracci divergono per motivi numerici gia'
documentati in `P7_BOZZA_MTP_14_SETTEMBRE.md` §3, non falsificati neanche oggi).

**Il fatto nuovo e utile e' la riga 2**: M4 e M1 producono **lo stesso testo in ognuno dei 18 casi**,
inclusi tutti gli otto `corto` che divergevano dal riferimento MTP spento. Questo e' il comportamento
corretto atteso — in greedy con verifica esatta il testo finale dipende solo dal modello bersaglio,
non da quale testa proponga i candidati — ed e' una conferma diretta che lo scambio della testa e'
stato eseguito senza introdurre errori di verifica.

---

## 5. Carico, memoria, prefill

| | M1 (testa condivisa) | M4 (testa non condivisa) | delta |
|---|---:|---:|---:|
| VRAM di picco | 11.588 MiB | **11.890 MiB** | +302 MiB (+2,61%) |
| RAM usata di picco | 91,03 GB | **92,06 GB** | +1,03 GB (+1,13%) |
| RAM disponibile, minimo di corsa | 4,86 GB | **3,84 GB** | −1,02 GB |
| GPU media | 93,8% | 94,9% | +1,1 pt |
| caricamento del server | 201 s | 206 s | +5 s (+2,5%) |
| prefill `L01@ctx32k`, cache vuota (32.944 token) | 329,19 t/s | **331,84 t/s** | +0,80% (rumore) |
| `n_rs_seq` / `llama_memory_recurrent: size` | 1 / 225,14 MiB | **1 / 225,14 MiB** | identico |

Il costo statico (VRAM, tempo di caricamento, prefill, stato ricorrente) e' **quasi indistinguibile**
da M1: la testa non condivisa non costa slot di cache esperti (conferma dell'ipotesi
dell'handoff §8), e la sua impronta VRAM aggiuntiva (+302 MiB) e' piccola. Il costo vero e' **dinamico
e di RAM**: +1,5 GB di esperti unici mappati che, sommati al resto del processo, hanno eroso il
margine libero fino a farlo scendere sotto la soglia mai toccata da M1 (§3). Nessun NaN, nessun
errore, nessun crash; server chiuso correttamente, porta 8100 libera, nessun processo residuo.

---

## 6. Perche' M5 non e' stata eseguita

Il protocollo autorizzava M5 solo se, in M4, l'accettazione alla prima posizione fosse salita sopra
0,7851 **oppure** il t/s fosse salito sopra 28,6646. **Nessuna delle due condizioni e' soddisfatta**
sui numeri ufficiali dell'insieme libero (accettazione 0,7832, t/s 22,6316). Anche depurando
dall'anomalia di RAM (§3.3), l'accettazione resta sotto la soglia. La regola di stop della cella
("se M4 non migliora M1 su t/s e accettazione, fermarsi") si applica quindi senza ambiguita':
**M5 non va eseguita**.

Va detto con chiarezza: **la domanda per cui questa cella e' stata aperta — la testa non condivisa
accetta di piu'? — ha risposta negativa**. 0,7832 contro 0,7851 (o 0,7797 contro 0,7851 sul
sottoinsieme pulito) non e' un miglioramento, e' rumore o un lieve peggioramento. L'apertura
dell'handoff del 13/9 ("la testa non condivisa e' l'unica variabile che sposterebbe l'ottimo verso
bozze piu' lunghe") **non e' confermata**: a parita' di tutto il resto, una testa piu' grande, con
piu' parametri propri e nessuna condivisione col modello bersaglio, non accetta di piu'. Il tetto
del percorso veloce (3 righe di verifica, §5 di `P7_BOZZA_MTP_14_SETTEMBRE.md`) resta quindi il vero
limite, non l'accuratezza della testa attualmente disponibile su disco.

---

## 7. Difetti

1. **L'anomalia RAM/GPU di `L07`/`L08@ctx32k` non e' stata isolata.** E' una correlazione forte
   (soglia di RAM mai toccata prima, crollo watt a clock invariato, niente crash/errori) ma non
   e' stata falsificata ripetendo la cella con piu' margine di RAM libero (es. chiudendo altri
   processi) o ripetendo lo stesso braccio due volte per vedere se ricompare negli stessi punti
   della sequenza. Resta un'ipotesi, non un fatto misurato in isolamento.
2. **Una sola replica.** Come in M1/M2, il protocollo di screening chiederebbe tre coppie; qui ce
   n'e' una. Il delta `corto` (+0,87%) e' troppo piccolo per essere distinto da un vero effetto con
   una sola misura.
3. **Il banco misura ragionamento, non prosa** (identico difetto di M1/M2, §6.3 del documento
   della cella 1): 14 casi su 16 esauriscono il budget in `reasoning_content` senza mai produrre
   `content`.
4. **Le passate di verifica sono ricavate, non lette**, come in M1/M2 (stesso difetto §6.4 della
   cella 1).
5. **Il consumo di RAM del solo file della testa non e' stato isolato dal resto del processo.** Si
   sa che il file su disco e' 1,35 GB piu' grande, ma non si e' misurato quanti di quei byte
   arrivano effettivamente mappati in RAM residente (il picco totale del processo e' salito di
   "solo" 1,03 GB, meno della differenza fra i due file: parte del file mappato potrebbe non essere
   mai stata toccata nei 28 casi di fixture usati).

---

## 8. Aperture

1. **Ripetere M4 con piu' margine di RAM libero** (chiudere applicazioni in background, o ripetere
   la sequenza `ctx32k` da sola con `--cache-ram` diverso) per vedere se l'anomalia di `L07`/`L08`
   e' deterministica nella posizione o e' legata alla pressione assoluta di RAM indipendentemente
   da quale richiesta la incontra per prima.
2. **Il tetto delle 3 righe di verifica resta il limite reale**, non l'accuratezza della testa: le
   due teste disponibili (condivisa e non condivisa) accettano quasi lo stesso (0,785 contro 0,783
   alla singola posizione disponibile con `n_max=1`). Nessuna delle due sposta la soglia di pareggio
   della seconda posizione (0,633, misurata 0,553 in M2): manca ancora una testa sostanzialmente
   piu' accurata, oppure allungare il percorso veloce oltre 3 righe (apertura gia' registrata in
   `P7_BOZZA_MTP_14_SETTEMBRE.md` §7.1-2).
3. **Misurare separatamente il costo RAM del file mappato**, con una sonda che campioni la working
   set del processo prima/dopo il primo prompt lungo, per capire quanto della differenza di 1,35 GB
   su disco si traduce davvero in RAM residente durante l'uso.
4. **Non riproporre la testa non condivisa per allungare la bozza** (M5, M3 a 3 token) finche' non
   si dispone di una testa con accettazione misurabilmente piu' alta: i dati di oggi dicono che
   cambiare solo il file della testa, a parita' di tutto il resto, non la alza.

---

## 9. Bozza di voce di registro

> **14 settembre 2026 — fase P7, cella 2: testa MTP non condivisa.**
>
> *Ipotesi.* Sostituire la testa MTP condivisa (`shared-Q8_0.gguf`, 2.786.568.256 B) con quella non
> condivisa (`Q8_0.gguf`, 4.137.429.120 B, mai provata) a parita' di tutto il resto (bozza 1 token,
> stesso banco `solo_libero`, stesso budget 1024) alza l'accettazione alla prima posizione sopra
> 0,7851 e/o il t/s sopra 28,6646, aprendo la strada a una bozza piu' lunga (M5) con margine positivo
> alla seconda posizione (soglia di pareggio 0,633).
>
> *File toccati.* Nuovo: `docs/porto/banco_p0/preset_M4_p7.json`,
> `docs/porto/p7_speculazione/P7_TESTA_NON_CONDIVISA_14_SETTEMBRE.md`,
> `docs/porto/p7_speculazione/log/{blocco,server_estratto,riepilogo,results,analisi}_M4_r1.*`.
> Nessun sorgente, nessuna build, nessun commit. `bin_prod`, lanciatore quotidiano e modello
> invariati.
>
> *Configurazioni.* Binari `qwen38_clean\build\bin`. Identico a `preset_M1_p7.json` tranne `-md`
> (testa non condivisa). Profilo `solo_libero`, budget 1024, greedy, seed 1234, 64 slot, sparse FA
> spenta.
>
> *Run validi / invalidi.* Una corsa valida: `20260914_150347_P7_p7_mtp_testa_non_condivisa_r1`.
> Nessun guasto, nessun NaN, nessun errore nel log del server; server chiuso correttamente, porta
> 8100 libera, nessun processo residuo. Riferimenti riusati: M1
> `20260914_143936_P7_p7_mtp_bozza1_r1` (28,6646 t/s), MTP spento
> `20260914_072049_P0_sper_ibrido_assente_r1`. M5 **non eseguita**.
>
> *Risultato e limite.* M4 = **22,6316 t/s** sull'insieme libero (M1 = 28,6646 t/s, **−21,03%**),
> accettazione **0,7832** (M1 0,7851, **−0,24%**). Il calo del t/s e' quasi interamente dovuto a
> un'anomalia isolata in 2 richieste su 16 (`L07`/`L08@ctx32k`, decode 3-4 volte piu' lento del
> previsto), correlata a RAM disponibile scesa sotto i 4 GB (mai successo in M1) e a un crollo della
> potenza GPU a clock invariato o piu' alto — firma di stallo di trasporto, non di calcolo, non
> isolata sperimentalmente. Depurando quei due casi il t/s salirebbe a 29,04 (+1,3%, dentro il
> rumore a singola replica) ma **l'accettazione sul sottoinsieme pulito resta a 0,7797, ancora sotto
> M1**. Le impronte di M4 sono identiche a quelle di M1 in tutti e 18 i casi: la sostituzione della
> testa e' corretta, verificata esattamente come deve essere in greedy. Costo per token abbozzato:
> 5,991 ms contro 5,674 ms di M1 (+5,6%: la testa non condivisa e' anche piu' cara da eseguire, oltre
> a non essere piu' accurata). VRAM +302 MiB, RAM +1,03 GB, caricamento +5 s, prefill invariato.
>
> *Decisione.* **La testa non condivisa non si adotta**: non alza l'accettazione (0,783 contro
> 0,785, sostanzialmente pari) e costa di piu' per token abbozzato (+5,6%) e di RAM (+1,5 GB su
> disco, +1 GB residente). **M5 non va eseguita**: nessuna delle due condizioni di innesco
> (accettazione o t/s sopra M1) e' soddisfatta, nemmeno depurando l'anomalia di RAM. L'apertura
> dell'handoff del 13/9 sulla testa non condivisa e' chiusa con esito negativo.
>
> *Prossima azione.* Isolare l'anomalia RAM/GPU di `L07`/`L08@ctx32k` con una replica a piu' margine
> di memoria libera, prima di attribuirla con certezza alla pressione di RAM (oggi e' una
> correlazione forte ma non falsificata in isolamento). Per allungare la bozza oltre 1 token restano
> solo le due strade gia' in coda nell'handoff: alzare il tetto delle 3 righe di verifica (lavoro di
> sorgente, fuori scopo per questa fase di soli preset), o attendere una testa MTP addestrata meglio.

---

## 10. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/banco_p0/preset_M4_p7.json` | preset della cella M4 (testa non condivisa, bozza 1 token) |
| `docs/porto/p7_speculazione/log/blocco_M4_r1.txt` | uscita completa di `avvia_blocco.ps1` |
| `docs/porto/p7_speculazione/log/riepilogo_M4_r1.txt` | riepilogo del banco con tutte le impronte |
| `docs/porto/p7_speculazione/log/results_M4_r1.jsonl` | una riga per richiesta: timings del server, `draft_n`, `draft_n_accepted`, impronte |
| `docs/porto/p7_speculazione/log/analisi_M4_r1.json` | uscita di `analizza_p7.py` (corsa M4 contro riferimento MTP spento) |
| `docs/porto/p7_speculazione/log/server_estratto_M4_r1.txt` | righe `n_rs_seq`, `graph nodes`, `print_timing`, `acc per pos`, `common_specu` del log del server |
| `D:\ds4_work\banco_p0_run\20260914_150347_P7_p7_mtp_testa_non_condivisa_r1` | corsa M4 completa (output, carico, manifest, log del server non redatto) |

Comando per rigenerare l'analisi:

```
python docs\porto\p7_speculazione\analizza_p7.py ^
  --corsa D:\ds4_work\banco_p0_run\20260914_150347_P7_p7_mtp_testa_non_condivisa_r1 ^
  --riferimento D:\ds4_work\banco_p0_run\20260914_143936_P7_p7_mtp_bozza1_r1
```
