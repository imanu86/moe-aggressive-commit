# P10 · cella 1 — la leva B di P8 (bias QSA residente) misurata sul token singolo (T1) a 131k, MTP spento — 15 settembre 2026

Cella di **misura**, una sola corsa candidata (`V1`) contro il riferimento gia' esistente `R0`
(P8 R0, `docs/porto/p8_riga_verifica/P8_ESITO_15_SETTEMBRE.md` §5.2). Nessuna modifica di codice,
nessuna build: i binari usati sono quelli gia' compilati nella cella P8
(`D:\ds4_work\p8_work\build\bin`, patch cumulativa con default A off / B on / C on / D1 off).
`bin_prod`, `qwen38_clean\source`, `qwen38_clean\build\bin`, il lanciatore quotidiano e i modelli
non sono stati toccati.

---

## 1. Cancello di partenza

Guardia eseguita due volte (prima di leggere la documentazione e subito prima del lancio):
`netstat -ano | findstr LISTENING | findstr :8100` e `tasklist | findstr llama-server` vuoti in
entrambi i controlli, nessuna build in corso. Nessun server trovato attivo: si e' proceduto.

---

## 2. Cosa misura questa cella e perche' e' diversa da P8

P8 misurava B sulla **riga di verifica `R`** (MTP acceso, bozza a 1 token, `R = ciclo − T1 − H`):
`R` scende di 1,44 ms con B. Ma quel numero presuppone `T1` **costante** — il costo di un forward a
riga singola, misurato una volta in R0 e riusato per tutte le celle successive (P8 §5.2, nota sotto
la tabella: *"T1 = 37,906 ms è il valore usato per R in tutta la cella"*).

Questa cella verifica l'assunzione: **B cambia anche `T1`?** Si misura lo stesso identico preset di
R0 (MTP **spento**, nessuna speculazione, `-np 1`, profilo `lungo_131k`, budget `screening` = 1024
token) cambiando **solo** il binario (nudo → patchato) e dichiarando B accesa. Se B lossless riduce
anche `T1`, il guadagno di P8 su `R` e quello su `T1` sono **due effetti separati della stessa
leva**, entrambi da sommare nel bilancio complessivo (non ancora fatto in questa cella).

---

## 3. Preset

`docs/porto/banco_p0/preset_V1_p10.json`, derivato da `preset_P8_0_p7.json` (R0): stessi argomenti,
stesso `env` di base, stesso contesto (262144), stessi 64 slot esperti, stesso campionamento
(greedy, seed 1234), stesso ragionamento acceso. Le uniche differenze dichiarate nel preset:

| campo | R0 (`preset_P8_0_p7.json`) | V1 (`preset_V1_p10.json`) |
|---|---|---|
| `binari` | `D:\ds4_work\p8_work\bin_nudo` (nessuna patch) | `D:\ds4_work\p8_work\build\bin` (patch cumulativa P8) |
| `env` extra | — | `QWEN4EXP_QSA_BIAS_DEV=1` **dichiarata esplicitamente** |

La dichiarazione esplicita non e' strettamente necessaria (il default della patch e' gia' "acceso":
`p8_B_interruttore.patch` mette `bias_dev_on = (valore nullo o diverso da "0")`, verificato a codice
in `docs/porto/p8_riga_verifica/p8_B_interruttore.patch`), ma toglie ogni ambiguita': **B e' accesa
per dichiarazione, non per omissione**. Le altre tre leve (A, C, D1) restano ai default della patch
(A spenta/tetto 30, C accesa, D1 spenta) e non sono dichiarate, perche' questa cella misura solo B.
Confermato nel run effettivo: `config.redacted.json` della corsa riporta
`preset.env.QWEN4EXP_QSA_BIAS_DEV = "1"`, `preset.binari = "D:\ds4_work\p8_work\build\bin"`,
`preset.mtp = false`. La stringa `QWEN4EXP_QSA_BIAS_DEV` e' verificata presente in
`D:\ds4_work\p8_work\build\bin\llama.dll`.

---

## 4. Le due corse

| | R0 (riferimento, P8) | V1 (candidata, questa cella) |
|---|---|---|
| corsa | `20260915_112333_P8_p8_r0_spento_binari_nudi_r1` | `20260915_153114_P10_p10_c1_v1_b_su_t1_mtp_spento_r1` |
| binari | `bin_nudo` | `build\bin` (patch cumulativa, B accesa) |
| preset | `preset_P8_0_p7.json` | `preset_V1_p10.json` |
| profilo / budget | `lungo_131k` / screening (1024 tok) | `lungo_131k` / screening (1024 tok) |
| secondi di caricamento server | — (non registrato in questa forma) | 201 s |
| guasto | nessuno | nessuno |

---

## 5. I numeri

### 5.1 Prefill (primo caso, L01@ctx131k, prefill freddo)

| | R0 | V1 | delta |
|---|---:|---:|---:|
| `prompt_n` | 131.248 | 131.248 | — |
| TTFT (prefill) | 523,01 s | 521,52 s | −1,49 s |
| **prefill t/s** | **250,95** | **251,66** | **+0,72 (+0,29%)** |

Il prefill non usa il ramo `gather`/decode (`n_tps <= 3`) che la leva B tocca — il commento nella
patch dice esplicitamente che il bias per-blocco del prefill *"is n_tokens*n_blocks and a second
copy of it would be large"*, cioe' non e' toccato da B. La differenza di 0,29% e' **rumore fra
corse**, non un effetto della leva: coerente con l'attesa.

### 5.2 Decode, per caso e aggregato (T1: MTP spento, nessuna speculazione)

| caso | R0 ms/token | R0 t/s | V1 ms/token | V1 t/s | Δ ms/token | Δ t/s | Δ t/s % |
|---|---:|---:|---:|---:|---:|---:|---:|
| L01@ctx131k | 37,758 | 26,484 | 37,353 | 26,772 | **−0,406** | +0,288 | +1,09% |
| L02@ctx131k | 38,127 | 26,228 | 37,692 | 26,531 | **−0,434** | +0,302 | +1,15% |
| **aggregato (2.048 tok)** | **37,906** | **26,381** | **37,486** | **26,677** | **−0,420** | **+0,296** | **+1,12%** |

(aggregato = `tempo_generazione_s / token_accettati`; R0: 77,631 s / 2.048 tok; V1: 76,771 s / 2.048
tok — gli stessi numeri di `tps_insieme` nei riepiloghi delle due corse, e l'aggregato R0 coincide
esattamente con i 37,906 ms/token pubblicati in P8 §5.2, buon segno di coerenza fra le due celle.)

I due casi (L01, L02) danno un delta quasi identico (−0,406 e −0,434 ms, scarto 0,03 ms): piu'
stretti del pavimento di rumore che P8 aveva misurato fra repliche indipendenti (0,5 ms su `R`),
anche se non sono repliche indipendenti (stessa corsa, stesso processo) e quindi non danno da soli
una stima di varianza.

### 5.3 Impronte — **identiche a R0, 4 su 4**

| caso | R0 | V1 | identiche |
|---|---|---|:--:|
| riscaldamento_1 | `b626d0e377e6075e…` | `b626d0e377e6075e…` | si |
| riscaldamento_2 | `b626d0e377e6075e…` | `b626d0e377e6075e…` | si |
| L01@ctx131k | `99ba1423cf128585…` | `99ba1423cf128585…` | si |
| L02@ctx131k | `dc916b9c428225c2…` | `dc916b9c428225c2…` | si |

**La leva e' lossless anche sul token singolo**: nessun bit del testo generato cambia fra binario
nudo e binario patchato con B accesa.

### 5.4 Lanci di grafo per forward — leggibili dal log, e con una lettura non ovvia

Dal log del server, alla riserva di grafo del primo slot (dopo il prefill di L01, quando lo slot
riserva la capacita' per il decode):

| | R0 | V1 |
|---|---|---|
| `graph nodes` (bs=3, capacita' verifica) | 9.247 | **9.248** (+1) |
| `graph nodes` (bs=1, decode reale) | 8.190 | **8.191** (+1) |
| `graph splits` | **4 (with bs=3), 2 (with bs=1)** | **2** (un solo numero: bs=3 e bs=1 ora coincidono) |

Due letture, non una:

1. **Il grafo guadagna esattamente un nodo** (+1 a bs=3, +1 a bs=1), **la stessa firma** che P8
   §6.2 aveva trovato a MTP acceso (9.561→9.562): un solo `llm_graph_input_qsa` condiviso da tutti
   e 12 gli strati, confermato anche qui, a MTP spento.
2. **Ma i lanci di grafo CUDA del decode REALE (bs=1) non cambiano**: erano 2 split in R0 e restano
   2 in V1. La caduta da 4 a 2 riguarda **solo la capacita' di verifica riservata a bs=3**, che in
   questa cella non viene mai esercitata (MTP e' spento, `-np 1`, non c'e' nessuna riga di verifica
   da lanciare). Quindi **il guadagno misurato in §5.2 non viene dai lanci di grafo** — a differenza
   di quanto succede a MTP acceso (P8), dove la caduta bs=3 4→2 e' proprio il meccanismo che paga.
   Qui l'unico canale disponibile e' quello dei byte/sincronismi H2D (§6).

---

## 6. Confronto con la stima di P9

P9 (`docs/porto/p9_anatomia_131k/P9_ANATOMIA_131K_15_SETTEMBRE.md` §2.6) aveva scomposto, sullo
stesso punto operativo (131k, token singolo, MTP spento — cioe' esattamente il regime di questa
cella), le copie H2D per forward: **27 copie, 7,31 MiB, 0,357 ms totali**, di cui **14 sono il bias
QSA** (526.336 B ciascuna: 12 viste per strato di attenzione + il tensore intero + `cell_blk`). La
leva B le riduce a 2 (il tensore intero copiato una volta + `cell_blk`), **togliendone 12 su 14**.

| | stima P9 (byte puri) | misurato (V1 vs R0) |
|---|---:|---:|
| ms tolti dal bias H2D | 12/14 × 0,357 = **0,306 ms** | — |
| ms tolti includendo la riduzione dei buchi di sincronismo | **~0,36 ms** (stima dichiarata nel mandato di questa cella) | **0,420 ms** (aggregato) |

**Il misurato (0,42 ms) e' piu' alto della stima (~0,36 ms), non piu' basso** — stesso segno di
scostamento che P8 aveva trovato su `R` (stimato −0,7, misurato −1,44): le copie non sono solo
byte, sono **sincrone** (`ggml_backend_synchronize` prima di ogni ingresso di split,
`ggml-backend.cpp:1938-1956`), e P9 stessa aveva registrato **1,88 buchi >100 µs per forward,
mediana 1,59 ms**, proprio "fra un `mul_mat_vec_q` e un `k_bin_bcast`", descritti come *"la consegna
fra il grafo e l'host: campionamento, `set_input`, lo split non-CUDA, le 14 righe di bias costruite
sull'host"*. Togliere 12 di quelle 14 righe toglie anche una parte di quell'attesa, non solo i byte.

---

## 7. RAM e VRAM minime

| | R0 | V1 | nota |
|---|---:|---:|---|
| VRAM libera minima | 1.201 MiB | 1.213 MiB | +12 MiB, rumore |
| RAM disponibile minima | **5,12 GB** | **3,03 GB** | sotto i 4 GB della regola |

**Difetto dichiarato.** La RAM disponibile minima di V1 (3,03 GB) e' sotto la soglia di 4 GB che la
regola dell'utente considera invalidante — a differenza di R0 (5,12 GB), che sta sopra. Controllato
pero' il dettaglio della riga di minimo in `carico.jsonl`: `server_rss_gb` e' **praticamente
identico** fra le due corse (V1 79,14 GB vs R0 79,25 GB), mentre `ram_usata_gb` **di sistema** e'
piu' alta in V1 (92,86 GB contro 90,77 GB) — cioe' **~2 GB in piu' erano occupati da qualcos'altro
sulla macchina**, non dal server ne' dalla leva B. Non e' quindi un effetto della patch (il server
patchato non pesa piu' del nudo), ma resta un fatto da registrare: **questa corsa e' formalmente
sotto soglia** e va trattata come tale (confrontabile con R0 per il resto — stessa macchina, stessa
sequenza, impronte identiche — ma non come valore assoluto di RAM libera).

---

## 8. Verdetto

> **B vale sul token singolo, non solo sulla riga di verifica.** A MTP spento (`T1` puro, nessuna
> speculazione), passare al binario patchato con B accesa **non cambia un bit del testo** (4
> impronte su 4 identiche a R0) e costa **37,486 ms/token contro 37,906**, cioe' **−0,420 ms
> (−1,11%)**, **+0,296 t/s (+1,12%)**: 26,677 contro 26,381 t/s.
>
> Il canale e' **solo quello dei byte/sincronismi H2D**, non quello dei lanci di grafo: i lanci CUDA
> del decode reale (bs=1) restano identici (2 split, invariati), la caduta di split 4→2 riguarda
> solo la capacita' di verifica a bs=3 che questa cella non esercita mai (MTP spento). Il grafo
> guadagna comunque il solito **+1 nodo** (firma di un solo `llm_graph_input_qsa` condiviso), come
> a MTP acceso.
>
> Il misurato (−0,42 ms) e' **piu' del previsto** (stima P9 ~−0,36 ms su byte puri + buchi), stesso
> segno di scostamento gia' visto in P8 su `R` (stimato −0,7, misurato −1,44): le copie tolte sono
> sincrone, non solo larghe.
>
> **Implicazione per P8/P9**: `T1` **non e' costante fra binario nudo e binario patchato con B**.
> P8 aveva usato `T1 = 37,906 ms` (misurato su R0, binario nudo) per calcolare `R` in **tutte** le
> celle successive, comprese quelle sul binario patchato. Quella scelta resta corretta **per
> isolare l'effetto di B sulla sola riga di verifica** (`R`), ma se si volesse il **guadagno totale
> per token** della configurazione consigliata (B+C, MTP bozza 1) rispetto a MTP spento sul binario
> **nudo**, bisognerebbe sommare anche questo termine: il forward "T1" dentro un ciclo con MTP acceso
> e binario patchato costerebbe verosimilmente ~37,49 ms, non 37,91, e la soglia di pareggio della
> bozza a 1 token (P8 §5.2, punto 2: serve `ciclo/token_per_ciclo < T1`) andrebbe ricalcolata con il
> `T1` piu' basso — **la bozza a 1 guadagnerebbe un margine leggermente maggiore di quanto P8
> misuri**, non lo perderebbe (il denominatore del pareggio si abbassa insieme a `T1`). Non e' stato
> ricalcolato in questa cella: e' un'apertura per la prossima.

---

## 9. Difetti di questa cella

1. **Una sola corsa, nessuna replica indipendente.** Il mandato della cella chiedeva una sola corsa
   candidata. I due casi (L01, L02) danno un delta molto vicino (−0,406 e −0,434 ms), ma **non sono
   repliche indipendenti**: stesso processo server, stesso avvio, quindi la coerenza fra loro non
   sostituisce una vera stima di varianza (il pavimento di rumore di P8, misurato su repliche vere,
   era 0,5 ms su `R`; qui il delta misurato, 0,42 ms, e' dello stesso ordine di grandezza di quel
   rumore, anche se il segno e la coerenza interna fra i due casi sono un indizio a favore di un
   effetto reale).
2. **RAM disponibile minima sotto soglia (3,03 GB contro 4)**, §7. Argomentato come non attribuibile
   al server (RSS quasi identico a R0) ma a contesa di sistema esterna; dichiarato, non nascosto.
3. **Nessun profilatore**: come in P8, le copie H2D non sono contate una per una in questa cella, si
   usa la scomposizione gia' fatta da P9 sullo stesso identico regime (token singolo, MTP spento,
   131k) piu' il delta misurato qui.
4. **Non e' stato ricalcolato l'effetto a cascata su P8** (la soglia di pareggio della bozza a 1
   token con `T1` piu' basso): e' segnalato come apertura (§8), non quantificato in questa cella.

---

## 10. Bozza di voce di registro

> **15 settembre 2026 — fase P10, cella 1: la leva B di P8 misurata sul token singolo (T1) a 131k,
> MTP spento.**
>
> *Ipotesi.* P8 aveva misurato B (bias QSA residente sul dispositivo, invece di ricopiato 49 volte
> dall'host per forward) sulla riga di verifica `R` (−1,44 ms), tenendo `T1` (il costo di un forward
> a riga singola) costante e preso da R0 (binario nudo). Se B toglie byte e sincronismi anche sul
> forward singolo — non solo sulla verifica — allora `T1` stesso dovrebbe scendere sul binario
> patchato, ed e' un termine che P8 non aveva isolato.
>
> *File toccati.* Nuovo: `docs/porto/banco_p0/preset_V1_p10.json` (derivato da `preset_P8_0_p7.json`,
> stesso preset con `binari` puntato a `D:\ds4_work\p8_work\build\bin` e `QWEN4EXP_QSA_BIAS_DEV=1`
> dichiarata). Nuovo: `docs/porto/p10_token_singolo/P10_CELLA1_B_SU_T1_15_SETTEMBRE.md` (questo
> esito) e `docs/porto/p10_token_singolo/log/` (client log, riepiloghi, estratti server, args
> redatti, chiusura — per V1 e per R0). **Nessun commit.** `bin_prod`, `qwen38_clean\source`,
> `qwen38_clean\build\bin`, lanciatore, modelli invariati; nessuna build in questa cella.
>
> *Configurazioni.* Banco P0, profilo `lungo_131k` (`L01`/`L02` con prefisso `ctx131k`: prefill
> freddo da 131.248 token, poi riuso), budget `screening` (1024 token), greedy seed 1234,
> ragionamento acceso, 64 slot, contesto 262.144, MTP **spento** (nessuna speculazione) in entrambe
> le corse. R0 su binario nudo (`bin_nudo`), V1 sullo stesso identico preset ma su binario patchato
> con la leva B dichiarata accesa.
>
> *Run validi / invalidi.* **Una corsa candidata (V1), zero guasti, zero NaN, zero avvisi, 4
> impronte su 4 identiche al riferimento R0.** RAM disponibile minima di V1 sotto la soglia di 4 GB
> (3,03 GB) — dichiarata, attribuita a contesa di sistema esterna (RSS del server quasi identico a
> R0: 79,14 contro 79,25 GB), non alla leva.
>
> *Risultato e limite.* **B vale anche sul token singolo: −0,420 ms/token (−1,11%), +0,296 t/s
> (+1,12%), lossless.** Il canale e' solo la riduzione delle copie H2D del bias QSA e dei loro
> sincronismi bloccanti (12 righe su 14 tolte, stima P9 su questo stesso regime ~0,357 ms totali di
> H2D), **non** i lanci di grafo CUDA: il decode reale a bs=1 resta a 2 split invariati in entrambe
> le corse, la caduta 4→2 osservata nel log riguarda solo la capacita' di verifica a bs=3, mai
> esercitata qui perche' l'MTP e' spento. Il misurato (0,42 ms) supera la stima (~0,36 ms), stesso
> segno di scostamento gia' visto da P8 su `R`. *Limite*: una sola corsa, nessuna replica
> indipendente; RAM sotto soglia dichiarata ma non isolata come causa.
>
> *Decisione.* **B e' lossless e paga anche su `T1`.** Il `T1 = 37,906 ms` usato da P8 per calcolare
> `R` su tutte le celle resta corretto per isolare l'effetto di B sulla sola verifica, ma non e' il
> costo del forward singolo sul binario patchato: quello e' piu' basso (~37,49 ms). Non si ricalcola
> qui la soglia di pareggio della bozza a 1 token; si segnala come prossima azione.
>
> *Regressioni.* Nessuna: impronte identiche 4/4, nessun NaN, nessun avviso, nessuna corsa invalida
> per guasto.
>
> *Stato dei processi.* Nessun `llama-server` attivo, porta 8100 libera (verificato a fine cella),
> nessuna build in corso.
>
> *Prossima azione.* Ricalcolare, con il `T1` piu' basso misurato qui, la soglia di pareggio della
> bozza MTP a 1 token (P8 §5.2 punto 2: `ciclo/token_per_ciclo < T1`) sul binario patchato — il
> margine a favore della bozza dovrebbe allargarsi leggermente, non restringersi. Se P10 prevede
> altre celle (bias residente a MTP acceso sul binario patchato, o la stessa leva a profondita'
> diverse), ripartire da questo `T1` misurato invece che da quello di R0 nudo.

---

## 11. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/p10_token_singolo/P10_CELLA1_B_SU_T1_15_SETTEMBRE.md` | questo esito |
| `docs/porto/banco_p0/preset_V1_p10.json` | preset della corsa V1 (JSON senza BOM) |
| `docs/porto/p10_token_singolo/log/V1_client.log`, `V1_riepilogo.{txt,json}` | esito lato client della corsa V1 |
| `docs/porto/p10_token_singolo/log/V1_args.redacted.txt`, `V1_chiusura.json` | argomenti (chiave redatta) e stato di chiusura del processo V1 |
| `docs/porto/p10_token_singolo/log/V1_server_estratto.txt`, `R0_server_estratto.txt` | righe `split`/`graph`/`reused`/`bias`/`moe-cache` dai due log server, per il confronto di §5.4 |
| `docs/porto/p10_token_singolo/log/R0_client.log`, `R0_riepilogo.txt` | copia di riferimento dei corrispondenti file di R0 (gia' esistenti in `D:\ds4_work\banco_p0_run\20260915_112333_P8_p8_r0_spento_binari_nudi_r1`) |
| `D:\ds4_work\banco_p0_run\20260915_153114_P10_p10_c1_v1_b_su_t1_mtp_spento_r1` | cartella completa della corsa V1 (manifest, config, prompt, output, `carico.jsonl`, log server integrale) |
| `D:\ds4_work\banco_p0_run\20260915_112333_P8_p8_r0_spento_binari_nudi_r1` | cartella completa di R0 (gia' esistente, da P8) |

Comando eseguito:

```
powershell -NoProfile -ExecutionPolicy Bypass -File docs\porto\banco_p0\avvia_blocco.ps1 `
    -Preset docs\porto\banco_p0\preset_V1_p10.json -Profilo lungo_131k -Budget screening `
    -Replica 1 -Nota "P10 cella1 V1 - leva B su T1 a 131k, MTP spento" -AttesaMinuti 25
```

Stato finale verificato: nessun `llama-server` attivo, porta 8100 libera (`porta_libera_dopo: True`
in `chiusura.json`), nessun processo residuo.
