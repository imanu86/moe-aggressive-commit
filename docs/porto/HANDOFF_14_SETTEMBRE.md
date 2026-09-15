# HANDOFF — CPU/GPU ibrido e speculazione MTP, 14 settembre 2026

Destinatario: chi riprende il lavoro (nuova sessione, o Codex). Scritto a fine giornata del 14/9,
dopo la chiusura di P7 cella 4 (**D28**). **Leggere per intero prima di toccare qualsiasi cosa.**
Documento gemello del [registro completo](REGISTRO_CPU_GPU_14_SETTEMBRE.md), che contiene tutti i
numeri con la prova; questo handoff è il punto di ingresso, non il sostituto.

---

## 0. In una pagina

La giornata è partita da un piano nuovo (CPU/GPU ibrido verso 50 t/s) ed è passata per nove fasi:
P0-P4 (baseline, contratto cache, esecutore, integrazione a uno strato, decode completo) e P7 in
quattro celle (speculazione MTP). **Tre piste si sono chiuse con una decisione motivata** (pista CPU
generale, divario dei colpi di cache, prefetch della riga di verifica), **una si è chiusa con un
acquisto netto** (sparse FA, ereditata dal 13/9, non ritoccata oggi), e **l'ultima cella aperta
(P7 cella 4) si è chiusa con un esito mistO**: un pezzo si adotta (l'impianto a polling), un pezzo si
corregge senza riserve (un difetto che valeva un fattore 12), un pezzo resta sospeso in attesa di una
sola corsa diagnostica (la corsia CPU sulle righe di bozza).

**Il numero da battere oggi è 28,66 t/s** (MTP bozza 1 token, testa condivisa), +17,31% sul
riferimento senza speculazione di 24,44 t/s. Nessuna leva provata oggi lo batte. Il tetto onesto di
questa architettura sul decode libero, con le sole leve minori ancora aperte, è stimabile
**nell'ordine di 32-35 t/s** — i 50 richiedono un cambio strutturale (§3.5).

---

## 1. Numeri di riferimento del banco P0

| grandezza | valore | condizioni |
|---|---:|---|
| Decode libero, MTP spento | **24,4344 t/s** (24,44 aggregato) | `solo_libero`, budget screening 1024, profilo `preset_A.json` |
| Decode libero, MTP bozza 1 (testa condivisa) | **28,6646 t/s** | +17,31% su MTP spento; accettazione 0,785, 1,788 token/passata — **D21** |
| Decode libero, MTP bozza 2 | 27,5030 t/s | −4,05% su bozza 1 — chiuso, **D22** |
| Rumore fra blocchi A/A identici | **0,06%** | due processi, stesso preset, `20260914_072049` / `074035` |
| Pavimento di rumore dopo una build | fino al 15% | non misurare a caldo dopo una ricompilazione (regola ereditata dal 13/9) |

Fixture congelate: [`banco_p0/fixtures/`](banco_p0/fixtures/). Banco e strumenti:
[`banco_p0/`](banco_p0/) (`avvia_blocco.ps1`, `banco_p0.py`, `aggrega.py`, preset `preset_*.json`).
Corse: `D:\ds4_work\banco_p0_run\20260914_*` (60 cartelle il 14/9). Aggregato della baseline:
[`banco_p0/risultati/aggregato_baseline_libero_20260914.json`](banco_p0/risultati/aggregato_baseline_libero_20260914.json).
Snapshot immutabile dei sorgenti di partenza: `D:\ds4_work\p0_snapshot_20260914\` (2999 file, con
`manifest_p0.json` e `source_hashes.json`).

**Regole vincolanti per ogni corsa futura, tutte decise oggi:**

- **D14 — "prima il B, poi l'A solo se serve".** Si lancia sempre prima il candidato contro il
  riferimento già noto; l'A (controllo) si esegue solo se B non mostra il vantaggio atteso, per
  distinguere una regressione generale da una specifica del candidato. Niente batterie di controllo
  lunghe senza un candidato pronto.
- **D11 — budget di token**: 1024 in screening / 1536 in conferma per i casi liberi, 768 per qualità
  strutturata e contesto lungo (non i 512/768 del protocollo originale).
- **D15 — la qualità dei liberi non è valutabile in screening.** Con `--reasoning on` e budget 1024,
  14 casi liberi su 16 finiscono per lunghezza con testo finale vuoto (budget consumato nel
  ragionamento). Le velocità restano valide; la qualità si valuta solo in conferma (P6, mai eseguita
  oggi) con budget 3072 o fino a `stop`.
- **R-RAM** — con testa MTP e contesto 32k la RAM libera scende a 4-5 GB; sotto i 4 GB il decode
  rallenta 3-4 volte per stallo di trasporto (non calcolo). Ogni preset futuro con MTP deve
  registrare la RAM libera minima raggiunta durante la corsa; una cella con un minimo sotto 4 GB non
  è una misura di velocità pulita. Il minimo toccato oggi è stato **5,1 GB** (cella 4, con due
  modelli caricati) — mai sceso sotto la soglia, ma con un solo gigabyte di margine.

---

## 2. Tabella di tutte le piste della giornata

| pista | esito | prova / riferimento | chiuso per sempre? |
|---|---|---|---|
| **P0** — baseline e fixture | COMPLETATA | [registro §P0](REGISTRO_CPU_GPU_14_SETTEMBRE.md#p0--base-riproducibile-149), riferimento 24,44 t/s | Sì, come base — si riusa, non si rifà |
| **P1** — contratto e simulatore della cache CPU/GPU | COMPLETATA | [`P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md`](P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md), [`P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md`](P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md), 36.913 piani a zero differenze | Sì, come contratto — riusato tale quale da P3/P4/P7c4 |
| **P2** — esecutore CPU (compilazione e verifica) | COMPLETATA | [`p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md`](p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md), [`ESITO_COMPILAZIONE_P2_14_SETTEMBRE.md`](p2_esecutore/ESITO_COMPILAZIONE_P2_14_SETTEMBRE.md), 540.672 confronti di float, 0 diversi | Sì, come esecutore — riusato tale quale |
| **P3** — un solo strato nel server, MTP spento | COMPLETATA, candidato non batte il riferimento | [`p3_uno_strato/P3_UNO_STRATO_14_SETTEMBRE.md`](p3_uno_strato/P3_UNO_STRATO_14_SETTEMBRE.md); B 23,51 contro 24,44 t/s (−3,8%); meccanismo 9× il risparmio di banda | Il **risultato** (meccanismo integra, è neutro da spento) resta acquisito; il **candidato a un solo strato** non si riprova senza una leva nuova |
| **P4 cella 1** — localizzazione del costo | COMPLETATA | [`p4_costo/P4_COSTO_MECCANISMO_14_SETTEMBRE.md`](p4_costo/P4_COSTO_MECCANISMO_14_SETTEMBRE.md); 85% dei costi era contesa di core, non meccanismo | Sì — **D16**, default thread da 4 a 2 |
| **P4 cella 2** — impianto leggero ed estensione | **CHIUSA (D18)**, pista CPU generale chiusa | [`p4_estensione/P4_ESTENSIONE_14_SETTEMBRE.md`](p4_estensione/P4_ESTENSIONE_14_SETTEMBRE.md); −1,6% a 8 strati, −5,9% a 24, sotto soglia di chiusura (<3%), perdita che cresce con la scala | **Sì (D18)** — si riapre solo se l'impianto scende sotto ~10 µs/strato senza nodi host, o se emerge un risparmio di banda molto maggiore. La cella 4 ha già portato l'impianto a 13,8 µs (D26): vedi apertura A2 |
| **P7 cella 1** — lunghezza della bozza MTP | COMPLETATA, leva chiusa | [`p7_speculazione/P7_BOZZA_MTP_14_SETTEMBRE.md`](p7_speculazione/P7_BOZZA_MTP_14_SETTEMBRE.md); bozza 2 perde 4,05% su bozza 1 | **Sì (D22)** — la leva è l'accuratezza, non la lunghezza; M3 (bozza 3) chiuso dalle guardie del percorso veloce (max 3 righe di verifica) |
| **Ricognizione GitHub** — accettazione MTP | COMPLETATA | [`RICOGNIZIONE_MTP_ACCETTAZIONE_14_SETTEMBRE.md`](RICOGNIZIONE_MTP_ACCETTAZIONE_14_SETTEMBRE.md); tre leve ordinate per guadagno/costo; la nostra accettazione (0,785) batte già la media pubblicata (0,661) | Sola lettura, non si richiude — resta come mappa per le prossime celle |
| **P7 cella 2** — testa MTP non condivisa | COMPLETATA, leva chiusa | [`p7_speculazione/P7_TESTA_NON_CONDIVISA_14_SETTEMBRE.md`](p7_speculazione/P7_TESTA_NON_CONDIVISA_14_SETTEMBRE.md); −21% grezzo (anomalia RAM/trasporto isolata a 2 casi su 16), accettazione pari o peggiore anche depurata | **Sì (D23)** — non riguadagnare senza una testa sostanzialmente più accurata |
| **P7 cella 3** — anatomia della riga di verifica / prefetch durante la testa | COMPLETATA, prefetch falsificato | [`p7_speculazione/P7_RIGA_DI_VERIFICA_14_SETTEMBRE.md`](p7_speculazione/P7_RIGA_DI_VERIFICA_14_SETTEMBRE.md); copertura 0,00% strutturale, finestra max 49% anche con oracolo | **Sì (D24)** — prefetch chiuso; l'anatomia della riga (15,66 ms) resta acquisita e riusata da cella 4 |
| **P7 cella 4** — impianto a polling e corsia CPU sulle righe di bozza | **COMPLETATA, esito misto** | [`p7_speculazione/P7_CELLA4_POLLING_E_CORSIA_BOZZA_14_SETTEMBRE.md`](p7_speculazione/P7_CELLA4_POLLING_E_CORSIA_BOZZA_14_SETTEMBRE.md); stadio 1 passa (13,8 µs/strato), stadio 2 non passa (R≈19,7 ms contro 13) | **No** — stadio 1 adottato come asset (D26); stadio 2 **inconclusivo** (D27), riaperto da A7 |
| **Divario dei colpi di cache (41% contro 75%)** | Falsificato il 13/9, riaperto per errore un'ora il 14/9, richiuso senza corse | [`DIGEST_CHAT_CODEX_13_SETTEMBRE.md`](DIGEST_CHAT_CODEX_13_SETTEMBRE.md) sessione 8; colpi reali 75,55% su 36.913 piani | **Sì (D19)** — non riaprire senza una misura diretta (non stimata dal traffico PCIe) che dia un tasso diverso |
| **FreeToken / Bonsai** (evidenza del 13/9, riusata come base del piano) | Storico, non ritoccato oggi | [`FREETOKEN_IBRIDO_13_SETTEMBRE.md`](FREETOKEN_IBRIDO_13_SETTEMBRE.md), [`FREETOKEN_BONSAI_13_SETTEMBRE.md`](FREETOKEN_BONSAI_13_SETTEMBRE.md) | Non è una pista del 14/9: solo evidenza di partenza. L'etichetta "baseline FreeToken" è stata scartata nella review del piano — i numeri storici (25,08/27,26/39,19 t/s) non sostituiscono i riferimenti di P0/D21 |

---

## 3. Che cosa resta aperto, in ordine

> **Nota di ripresa, 15/9.** L'apertura A7 di §3.1 è **CHIUSA** (P7 cella 5, commit `7e16b85`) e la
> corsia CPU sulle righe di bozza è **CHIUSA DEFINITIVAMENTE** (P7 cella 6, commit `6e7f879`,
> [`p7_speculazione/P7_CELLA6_THREAD_15_SETTEMBRE.md`](p7_speculazione/P7_CELLA6_THREAD_15_SETTEMBRE.md)):
> nessun numero di thread provato (2/3/4/6, affinità `auto`) fa scendere il ciclo sotto la corsia
> spenta, il minimo a 4 thread resta 3,74 ms/ciclo sopra il riferimento e la curva non è monotona
> (**D31**). **La pista della speculazione dentro l'architettura attuale è ESAURITA (D32)**: restano
> solo le leve minori lossless della §3.4 (A6a, A6b) e l'apertura A2 sull'impianto a polling applicato
> a P4, stimate insieme a +3-5% al massimo, nessuna misurata. I riferimenti del banco non cambiano:
> **24,44 t/s** a MTP spento, **28,66 t/s** a MTP bozza 1 (D21) — nessuna leva provata da P7 li batte.
> L'asset del polling (13,8 µs/strato, **D26**) e le tre correzioni di correttezza della cella 5
> (**D29**) restano nella copia di lavoro `D:\ds4_work\p3_work`, spente di default; le patch si
> applicano in ordine — P3, P4-costo, P4-estensione, P7-cella4, P7-cella5 — nessuna in cella 6 (nessun
> file di codice toccato). **P7 è SOSPESA**: la prossima azione è una decisione strutturale
> dell'utente, non una misura. Opzioni note, elencate senza raccomandarne una:
>
> | opzione | effetto stimato sul decode libero | motivo |
> |---|---|---|
> | (a) esperti residenti/cache a quantizzazione più bassa (IQ1 **escluso** per decisione utente) | al massimo **−5/−6%** | l'upload degli esperti è il 24,5% del tempo dei kernel; meno byte per esperto trasferito aiuta ma non cambia il numero di colpi/miss |
> | (b) più VRAM (GPU da 24 GB) | circa **+15/20%** | slot 64 → 128+, colpi 75% → ~90% misurato il 13/9, upload −60%, mmvq più veloce a batch più pieni |
> | (c) modello più piccolo (es. 35B-A3B interamente in VRAM+RAM) | **l'unica via nota ai 50+ t/s** su questo hardware | a costo di qualità, non misurato su questo modello |
> | (d) esperti Q6_K residenti convertiti a Q4_K | circa **−5%** | meno byte per gli stessi esperti oggi alla quantizzazione più alta (23% del tempo dei kernel), senza toccare IQ2_S/IQ3_S |
> | (e) testa MTP riaddestrata (FastMTP, §3.3) insieme a una riga di verifica più economica | **+5/10% solo insieme** | attacca sia l'accettazione (pos.2 0,48→0,62 su Qwen3-Next) sia il costo di riga, ma richiede addestramento su pod e nessuna delle due leve da sola basta |
>
> La scelta è dell'utente; nessuna raccomandazione.
>
> **Nota di ripresa, 15/9 (seconda).** La decisione strutturale attesa sopra è arrivata, ma non come
> una delle cinque opzioni della tabella: l'utente ha fissato il **punto operativo** a contesto ~100k
> con KV 250k (**D33**) — da questa data ogni misura di velocità o di leva si fa sul profilo
> `lungo_131k` del banco P0, non più a 32k; i riferimenti 24,44/28,66 t/s restano solo per rumore e
> impronte. Due celle nuove hanno rimisurato lì. **P7 cella 7 (COMPLETATA, commit `1857142`)**: MTP
> bozza 2 con ragionamento spento a 131k — `--reasoning-budget 0` è **FALSIFICATO** su questo profilo
> (il modello continua a riempire `reasoning_content` sui prompt lunghi), serve `--reasoning off`;
> 25,479 t/s, accettazione (0,735 ; 0,489), **sotto** la soglia di pareggio 0,633 — spegnere il
> ragionamento non alza l'accettazione e la bozza 2 non paga nemmeno così (**D34**); qualità buona ma
> troncata dal budget 1024, da qui budget **2048** per le corse di qualità a ragionamento spento
> (**D35**, D11 resta per lo screening di velocità); RAM libera minima 3,3 GiB. **P8 (COMPLETATA,
> commit `cc91ebb`)**: albero pulito dallo snapshot P0 in `D:\ds4_work\p8_work`; al punto operativo
> 131k, sui binari nudi, **R0 (MTP spento) = 26,381 t/s** (37,906 ms/token), **R1 (MTP bozza 1) =
> 26,229 t/s (−0,5% su R0: la speculazione era già una perdita netta a 131k)**, riga di verifica
> `R = 20,203 ms` (non 15,66: quel numero di P7 cella 3 era a un'altra profondità con un `T1` dedotto).
> Di quattro leve lossless misurate cumulativamente, solo **B** (bias QSA residente sul dispositivo
> invece di 49 copie H2D per forward) paga: **−1,44 ms su R, +2,3% su t/s**, che ribalta il segno
> dell'MTP — con B la bozza 1 rende **26,87 t/s, +1,8% sull'MTP spento**; A è ridondante una volta
> accesa B, C non compra nulla (l'ipotesi di occupancy è falsificata), D1 non guadagna (default spento).
> La bozza a 2 token resta chiusa anche con tutte le leve (−11,2%). **D36 — si adotta la leva B**
> (patch `p8_cumulativa.patch`, default B+C accese, A/D1 spente). Effetto collaterale: il GGUF non
> contiene un solo tensore IQ3_XXS (i 144 tensori esperti sono IQ2_S/IQ3_S/IQ4_NL) — la leva E del
> progetto CPU/GPU (D25 e seguenti) va riprogettata contro il ramo scalare di `mmvq.cu`, non contro
> `mul_mat_vec_q_moe`. **Riferimenti al punto operativo: 26,38 t/s MTP spento, 26,87 t/s MTP bozza 1 +
> B.** R-RAM è confermato **strutturale** a 131k con testa MTP (2,3-3,6 GiB in ogni corsa MTP di
> entrambe le celle, sempre sotto la soglia di 4 GiB — non un caso isolato). **P7 è ora CHIUSA** (non
> più sospesa) e **P8 è COMPLETATA**; la prossima azione è **P9 — anatomia del token singolo a 131k**
> (dove vanno i 37,9 ms: mmvq, gather esperti, attenzione/indexer, host) per scegliere la prossima leva
> (residenti Q6_K → Q4_K, fusione dei matvec densi, più VRAM) — una misura, non più una decisione in
> sospeso. Dettagli completi in
> [`REGISTRO_CPU_GPU_14_SETTEMBRE.md`](REGISTRO_CPU_GPU_14_SETTEMBRE.md) (D33-D36),
> [`p7_speculazione/P7_CELLA7_RAGIONAMENTO_SPENTO_131K_15_SETTEMBRE.md`](p7_speculazione/P7_CELLA7_RAGIONAMENTO_SPENTO_131K_15_SETTEMBRE.md),
> [`p8_riga_verifica/P8_ESITO_15_SETTEMBRE.md`](p8_riga_verifica/P8_ESITO_15_SETTEMBRE.md).

### 3.1 Apertura A7 — il contributo CPU arriva davvero a `moe_out` sulle righe di bozza?

La domanda che tiene in sospeso tutta la corsia (D27). Nella cella 4, S7 (corsia accesa, il pool
calcola) e S10 (corsia accesa, `LLAMA_MOE_CPU_NOCOMPUTE=1`, il pool non calcola niente) producono
**lo stesso identico testo** su 1.397 token. Tre letture possibili, la cella non ha i dati per
sceglierne una: (1) il contributo non arriva a `moe_out` — sarebbe un difetto di correttezza vero;
(2) il testo cambia per la sola mascheratura e la coincidenza è generosa ma possibile; (3) il testo
cambia per il **difetto 6** di cella 4 (il contesto della **bozza** eredita un nodo `add` di
`moe_out` che non gli appartiene, perché la condizione che lo costruisce in `llama-graph.cpp:2155`
non distingue il modello bersaglio dal modello di bozza) — difetto trovato, non corretto.

**Una sola corsa già pronta**: `preset_S13_p7.json`, modalità diagnostica, confronta il contributo
CPU con quello che la GPU calcola per le stesse route e riporta NRMSE e massimo assoluto. Se la
NRMSE è ~0,008 (coerente col resto del meccanismo) il pool calcola la cosa giusta e la lettura 1
cade; se è ~1,0 il contributo non c'è. **È la prima cosa da fare**, prima di correggere il difetto 6
e prima di rimisurare `R`.

**Aspettativa dopo A7**: se `R` scende sotto 13 ms la corsia CPU torna in gioco, e la soglia di
pareggio della seconda posizione di bozza scende da 0,633 (misurata 0,553, chiusa in D22) a **~0,50**
— la bozza a 2 token potrebbe tornare redditizia **senza toccare l'accettazione**. Se anche dopo la
correzione `R` resta sopra 13 ms, la corsia si chiude per davvero (non inconclusiva, negativa).

### 3.2 L'impianto a polling come asset (D26)

Già adottato, spento di default (`LLAMA_MOE_CPU_POLL=0`), nella copia di lavoro `D:\ds4_work\p3_work`.
Due aperture dirette, entrambe a basso costo:

- **A2** — applicarlo all'estensione P4 (D18): il costo per strato attivo misurato in cella 4 è
  **41,9 µs**, contro i ~156 che il bilancio di P4-estensione §9 sommava (impianto 59,1 + aritmetica
  ~97). Non è una riapertura di D18 — il confronto sta su profili diversi — ma è il confronto da
  rifare per primo: `preset_EB8_p4` con `LLAMA_MOE_CPU_POLL=1` sul profilo `solo_libero`, contro
  24,44 t/s.
- **A1** — staccare l'invariante 5 (frequenza/recenza non aggiornate sulle righe di sola bozza) dalla
  selezione CPU. Il flag `MOE_GROUPED_PLAN_UNIQUE_DRAFT` è già nel piano e già scritto; usarlo da solo,
  senza la corsia CPU, costa tre righe e zero millisecondi, e toglie dalla politica della cache i
  token con il 21,5% di probabilità di essere rifiutati.

### 3.3 FastMTP — solo dopo, su pod

Terza leva della ricognizione GitHub, non tentata oggi: testa MTP riaddestrata sulle proprie
generazioni auto-distillate (arXiv 2509.18362). Su Qwen3-Next-80B-A3B porta la posizione 2 da 0,476 a
0,616 — un delta analogo sul nostro 0,553 supererebbe il pareggio. **Nessuna testa pubblicata per
Flash-Next**: andrebbe addestrata da zero, costo pubblicato modesto (~8000 campioni, 2×H200, 443 s)
ma non fattibile su questa 3060 — richiede un pod. Da tentare solo dopo aver esaurito le leve senza
addestramento (A7, A1, A2, A6 sotto), e solo insieme alla leva 2 della ricognizione (il costo di riga
va comunque abbassato, altrimenti anche un'accettazione a 0,70 non basta: vedi ricognizione §"le tre
cose più promettenti").

### 3.4 Leve minori lossless sulla riga di verifica

Due aperture della cella 3, indipendenti dalla corsia CPU, non quantificate:

- **A6a — bias QSA per riga**: il termine H2D esplicito del bias QSA (+1,14 ms nella riga in più,
  cresce linearmente con la profondità del contesto) potrebbe costruirsi in F16 o sul dispositivo
  invece che trasferirsi da host.
- **A6b — dedup del gather QSA fra le due righe**: solo `k_get_rows` non è a banda satura (3,7 GiB/s,
  16% del bus) — margine per non ripetere il gather delle celle QSA condivise fra riga 0 e riga 1.
  Misura da dieci minuti mai fatta: intersezione dei top-2048 fra le due righe.

### 3.5 Prefill 131k/250k

Mai toccato oggi (P0-P7 sono tutti sul decode). Il piano originale chiedeva di consolidare oltre
400 t/s a 32k (già oltre, 414,83 t/s misurati il 13/9) e perseguirlo a 131k (357,61 t/s misurati il
13/9, poi 294,95 con la sparse FA a teste 256, +18,1%). 250k resta un'estensione successiva con un
proprio risultato — nessuna estrapolazione. Il batch (`-b`/`-ub`) va scelto per contesto, non
riusato dal preset del decode.

### 3.6 La constatazione onesta: il tetto è ~32-35 t/s, non 50

Il numero migliore misurato oggi resta **28,66 t/s**. Le leve ancora aperte e non chiuse per sempre
sono tutte **minori o incerte**: A1 e A2 sono a basso costo ma non quantificate sul libero; A6a/A6b
non sono misurate; la corsia CPU (A7) è sospesa e, anche se A7 si chiude a favore, il suo stesso
bilancio onesto (cella 4 §6.7) dice che manca "solo" un fattore 1,7, non un raddoppio. Sommando le
leve minori note e lossless a 28,66 t/s, una stima onesta e non misurata porta il tetto di questa
architettura, su questo hardware, **nell'ordine di 32-35 t/s** sul decode libero — un quarto della
strada verso l'obiettivo dichiarato (20 ms/token accettato, 50 t/s), non tre quarti.

**Per arrivare davvero a 50 serve un cambio strutturale.** Opzioni note, elencate senza raccomandarne
una — ciascuna richiede il proprio banco e la propria decisione:

1. **Quantizzazione più bassa degli esperti residenti** (oggi IQ2_S/IQ4_NL): meno byte per esperto
   trasferito, stesso numero di colpi/miss; rischio su qualità, non misurato su questo modello.
2. **Cache più grande = più VRAM** (oggi 64 slot, 5,8 GiB): la curva è nota e misurata il 13/9
   (0/32/64 slot = 14,71/22,18/24,64 t/s senza MTP, 2,9 GiB = +11%), ma richiede hardware diverso da
   questa 3060 da 12 GiB, già quasi satura con MTP e contesto lungo (R-RAM).
3. **Testa riaddestrata (FastMTP, §3.3) insieme a una riga di verifica più economica**: l'unica
   combinazione che attacca sia l'accettazione sia il costo, ma richiede addestramento su pod e la
   leva 2 della ricognizione (oggi chiusa in forma di prefetch, D24, ma non nella forma di corsia
   CPU, che è ancora aperta in A7).
4. **Modello più piccolo**: fuori perimetro di questo piano (che tiene i pesi GGUF correnti fissi,
   D01), ma è l'opzione che cambia il problema invece di ottimizzarlo.

---

## 4. Binari e alberi

| albero | stato | uso |
|---|---|---|
| `qwen38_clean\bin_prod` | **INTATTO**, mai toccato in nessuna fase del 14/9 | Produzione, lanciatore quotidiano |
| `qwen38_clean\build\bin` | **originale**, invariato — è quello usato da P7 celle 1-3 (nessuna patch, nessuna build in quelle celle) | Sperimentale "puro" |
| `D:\ds4_work\p0_snapshot_20260914\` | snapshot immutabile dei sorgenti allo stato di inizio giornata (2999 file, manifest + hash) | Base di ogni patch incrementale |
| `D:\ds4_work\p3_work\source` / `\build` | copia di lavoro, **patchata in sequenza da P3 → P4-costo → P4-estensione → P7-cella4** | Unico albero con l'ibrido CPU/GPU e il polling; tutto spento di default |
| `D:\ds4_work\p7_cella4_base` | stato dei 7 file toccati da cella 4 **prima** della patch, congelato per il diff | Solo riferimento del diff |

**Patch da applicare in ordine, tutte con `patch -p1 --binary`** (il flag `--binary` è necessario: i
sorgenti hanno terminatori CRLF e senza il flag `patch` di Git Bash rifiuta ogni hunk dei file `.cuh`
con «different line endings», pur non essendoci un solo CR né nella patch né nei sorgenti):

1. [`p3_uno_strato/p3_uno_strato.patch`](p3_uno_strato/p3_uno_strato.patch) — contro
   `D:\ds4_work\p0_snapshot_20260914\source` (17 file, 2.928 righe aggiunte, 17 tolte)
2. [`p4_costo/p4_costo.patch`](p4_costo/p4_costo.patch) — contro lo stato dopo (1) (6 file)
3. [`p4_estensione/p4_estensione.patch`](p4_estensione/p4_estensione.patch) — contro lo stato dopo (2)
   (6 file)
4. [`p7_speculazione/p7_cella4.patch`](p7_speculazione/p7_cella4.patch) — contro lo stato dopo (3)
   (9 file, 815 righe, verificata applicandola davvero: i file risultanti coincidono byte per byte
   con l'albero di lavoro)

Nessun commit del motore in nessuna delle quattro fasi: le patch sono l'unico record delle modifiche
al di fuori della copia di lavoro `D:\ds4_work\p3_work`.

---

## 5. Manopole introdotte oggi (tutte spente di default)

| variabile | introdotta in | valori | default | che cosa fa |
|---|---|---|---|---|
| `LLAMA_MOE_CPU` | P3 | 0/1 | 0 | accende l'ibrido CPU/GPU |
| `LLAMA_MOE_CPU_LAYERS` | P3 | elenco, es. `1` | — | strati su cui l'ibrido è attivo |
| `LLAMA_MOE_CPU_MAX` | P3 | 0/1/2 (tetto 4) | 0 | quanti miss per strato deviare sulla CPU |
| `LLAMA_MOE_CPU_DIAG` | P3 | 0/1 | 0 | esegue il calcolo CPU ma non lo commette (diagnostica) |
| `LLAMA_MOE_CPU_REPORT` | P3 | N (lanci) | — | stampa i contatori ogni N chiamate al piano |
| `LLAMA_MOE_CPU_THREADS` | P3, default rivisto in P4 cella 1 (**D16**) | N | **2** (era 4) | dimensione del pool CPU; a 2 il meccanismo costa 6,6× meno che a 4 (contesa col threadpool del server) |
| `LLAMA_MOE_CPU_WAIT_US` | P3 | N | 2.000.000 | scadenza dell'attesa nativa `WaitOnAddress` |
| `LLAMA_MOE_CPU_ACK_US` | P3 | N | 200.000 | scadenza del riconoscimento |
| `LLAMA_MOE_CPU_ALLOW_ZERO` | P4 cella 1 | 0/1 | 0 | consente `LLAMA_MOE_CPU_MAX=0` con l'impianto comunque costruito (misura il costo puro dell'impianto) |
| `LLAMA_MOE_CPU_NODES` | P4 cella 1 | maschera 0-31 | 31 | quali pezzi dell'impianto accodare (export/submit/wait/guardia/add) |
| `LLAMA_MOE_CPU_NOCOMPUTE` | P4 cella 1, riusata in P7 cella 4 | 0/1 | 0 | il job viene accettato ma il pool non esegue aritmetica — isola il costo di consegna da quello di calcolo |
| `LLAMA_MOE_CPU_FUSE` | P4 cella 2 | 0/1 | 1 | fonde submit/wait in un nodo host per strato invece di due |
| `LLAMA_MOE_CPU_GUARD_LIGHT` | P4 cella 2 | 0/1 | 1 | guardia del merge senza lettura PCIe pesante |
| `LLAMA_MOE_CPU_AFFINITY` | P4 cella 2 | `auto`/... | `auto` | affinità dei thread del pool, lontana dal thread del server |
| `LLAMA_MOE_CPU_FUSE_SPIN_US` | P4 cella 2 | N | 0 | spin prima del blocco nativo nel nodo fuso |
| `LLAMA_MOE_CPU_POLL` | **P7 cella 4** | 0/1 | **0** | toglie l'ultimo nodo host: l'attesa diventa il prologo della guardia del merge, un kernel che gira a vuoto su una parola mappata |
| `LLAMA_MOE_CPU_POLL_US` | **P7 cella 4** | N | **50.000** | scadenza del giro a vuoto, misurata **dentro** il kernel con `clock64()` in cicli di SM |
| `LLAMA_MOE_CPU_DRAFT_ROWS` | **P7 cella 4** | 0/1 | **0** | corsia CPU sulle sole righe di bozza dell'MTP: gli esperti non residenti chiesti solo dalle righe oltre la prima non si trasferiscono, si calcolano sulla CPU |

**Nessun preset di produzione accende nessuna di queste variabili.**

Preset del banco (in [`banco_p0/`](banco_p0/)): `preset_A.json`/`preset_B.json` (P0),
`preset_C<n>_p4.json` (P4 cella 1), `preset_E<n>_p4.json` (P4 cella 2), `preset_M1/M2/M4_p7.json`
(P7 celle 1-2), `preset_S<n>_p7.json` (P7 cella 4, S0-S12; **`preset_S8_p7.json`** e
**`preset_S13_p7.json`** generati e **mai eseguiti di proposito** — S8 è la bozza 2 che avrebbe avuto
senso solo con `R` sceso, S13 è la diagnostica NRMSE dell'apertura A7, la prossima corsa da fare).

---

## 6. Regole di metodo imparate oggi

1. **I contatori del ramo contano più delle impronte.** Un'impronta identica al riferimento non
   dimostra che un meccanismo sia girato: in P3 un difetto nei pesi di routing (`dst->src[4]` invece
   del nodo GLU nel percorso fuso) ha prodotto impronte identiche con il ramo CPU mai partito — «un
   successo apparente, la classe di difetto più cara». In P7 cella 4 lo stesso schema si è ripetuto
   con S7 r1 (gate CUDA dimenticato, corsia mai partita, tutto "sembrava a posto"). **Verificare
   sempre un contatore diretto del ramo**, non solo il testo.
2. **La fase di un pool non si decide dal numero di token del batch.** `graph_compute` riusava il
   booleano `batched = (n_tokens > 1)`, corretto per scegliere il threadpool, anche per mettere il
   pool degli esperti in fase prefill — dove un'attesa da 1 ms dura un tick Windows (~15,6 ms). Un
   batch di verifica della speculazione ha più token per un motivo che non c'entra col prefill: il
   criterio giusto è il **perimetro dichiarato dall'esecutore**, non un conteggio generico.
3. **Leggere i rapporti `*_CODEX.md` prima di aprire o riaprire un fronte.** Il divario dei colpi di
   cache (41%/75%) è stato riaperto per un'ora il 14/9 senza rileggere
   `RIPRESA_CACHE_13_SETTEMBRE_CODEX.md`, che lo aveva già falsificato il 13/9 — richiuso senza
   produrre corse (**D19**).
4. **Prima il candidato B, poi l'A solo se serve (D14).** Niente batterie di controllo lunghe senza
   un candidato pronto: ha fermato la misura di variabilità pianificata da D12 dopo tre blocchi
   invece dei sette previsti, e ha strutturato ogni cella di P3/P4/P7 nello stesso modo.
5. **Stimare il tetto dal modello di costo prima di costruire.** La ricognizione GitHub ha verificato
   il modello `ciclo = T1 + R + H` sui numeri pubblicati prima di scegliere quale leva provare in
   cella 3; la cella 3 ha stimato la finestra e la capacità della testa (5,67 ms, 136 MiB) prima di
   dichiarare chiuso il prefetch. Nella cella 4, il bilancio `n_cpu × costo_per_esperto` contro
   `byte_risparmiati / banda` andava fatto **prima** di misurare, non dopo la prima corsa da 695 ms.
6. **Una lettura di memoria mappata da un kernel costa ~1,1 µs/strato.** Misurato per differenza fra
   le due forme del prologo di attesa (tre letture contro una, 16,0 contro 13,8 µs/strato); vale come
   costo di riferimento per qualunque cella futura voglia leggere una parola mappata da un kernel.
7. **La RAM libera minima va registrata in ogni corsa con testa MTP (R-RAM).** Sotto i 4 GB il decode
   rallenta 3-4 volte per stallo di trasporto, non di calcolo — firma: potenza GPU dimezzata a clock
   uguale o più alto, temperatura in calo. La cella 4 ha toccato 5,1 GB, mai sotto soglia, ma con un
   solo gigabyte di margine: da tracciare, non da ignorare.

---

## 7. Collegamenti

Piano e protocollo: [`PIANO_CPU_GPU_14_SETTEMBRE.md`](PIANO_CPU_GPU_14_SETTEMBRE.md),
[`PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md`](PROTOCOLLO_CPU_GPU_14_SETTEMBRE.md). Registro completo con
tutti i numeri e le prove: [`REGISTRO_CPU_GPU_14_SETTEMBRE.md`](REGISTRO_CPU_GPU_14_SETTEMBRE.md).
Stato macchina-leggibile: [`stato_cpu_gpu_14settembre.json`](stato_cpu_gpu_14settembre.json).
Handoff del giorno precedente (contesto sparse FA, priorità ereditate):
[`HANDOFF_13_SETTEMBRE.md`](HANDOFF_13_SETTEMBRE.md).

Fasi: [P1 contratto](P1_CONTRATTO_CACHE_CPU_GPU_14_SETTEMBRE.md) ·
[P1 simulatore](P1_RAPPORTO_SIMULATORE_14_SETTEMBRE.md) ·
[P2 progetto](p2_esecutore/PROGETTO_P2_ESECUTORE_14_SETTEMBRE.md) ·
[P2 esito compilazione](p2_esecutore/ESITO_COMPILAZIONE_P2_14_SETTEMBRE.md) ·
[P2 review](p2_esecutore/REVIEW_P2_14_SETTEMBRE.md) ·
[P3 uno strato](p3_uno_strato/P3_UNO_STRATO_14_SETTEMBRE.md) ·
[P4 costo](p4_costo/P4_COSTO_MECCANISMO_14_SETTEMBRE.md) ·
[P4 estensione](p4_estensione/P4_ESTENSIONE_14_SETTEMBRE.md) ·
[P7 cella 1 — bozza MTP](p7_speculazione/P7_BOZZA_MTP_14_SETTEMBRE.md) ·
[P7 cella 2 — testa non condivisa](p7_speculazione/P7_TESTA_NON_CONDIVISA_14_SETTEMBRE.md) ·
[P7 cella 3 — riga di verifica](p7_speculazione/P7_RIGA_DI_VERIFICA_14_SETTEMBRE.md) ·
[P7 cella 4 — polling e corsia bozza](p7_speculazione/P7_CELLA4_POLLING_E_CORSIA_BOZZA_14_SETTEMBRE.md) ·
[ricognizione GitHub MTP](RICOGNIZIONE_MTP_ACCETTAZIONE_14_SETTEMBRE.md) ·
[digest chat Codex 13/9](DIGEST_CHAT_CODEX_13_SETTEMBRE.md).

Evidenza storica del 13/9, riusata come base: [`FREETOKEN_IBRIDO_13_SETTEMBRE.md`](FREETOKEN_IBRIDO_13_SETTEMBRE.md),
[`FREETOKEN_BONSAI_13_SETTEMBRE.md`](FREETOKEN_BONSAI_13_SETTEMBRE.md).
