# Bozza di voce di registro — P0

Da integrare in [REGISTRO_CPU_GPU_14_SETTEMBRE.md](../REGISTRO_CPU_GPU_14_SETTEMBRE.md).
Bozza dell'esecutore, non una voce approvata.

## Data e fase

14 settembre 2026. **P0 — Base riproducibile.** Consegne A-E eseguite in una sessione.
**Nessun benchmark.** Le uniche due accensioni del server sono state: una corsa di fumo
(profilo `fumo`, quattro richieste) per provare che il banco funziona end-to-end, e una
seconda accensione di solo sigillo (`-SoloSigillo`, nessuna richiesta misurata) per
ricongelare le fixture dopo i difetti che il fumo aveva rivelato. La misura di variabilita'
della baseline (tre coppie) **non e' stata eseguita**: resta all'utente, in serie, perche'
un altro agente lavorava in parallelo sul simulatore e i banchi non possono sovrapporsi.

## Ipotesi

P0 non verifica un'ipotesi prestazionale. Verifica tre premesse operative:

1. lo stato sperimentale del 14/9 e' catturabile in modo immutabile e riproducibile;
2. le fixture possono essere congelate una volta, cosi' che i due lati di un A/B a giorni di
   distanza leggano input identici anche dopo che i sorgenti sono cambiati;
3. un blocco A/B si avvia, misura e chiude senza .bat, senza `pause`, senza toccare
   `bin_prod` e senza lasciare processi attivi.

Tutte e tre risultano soddisfatte, la terza **solo dopo una correzione** (sotto).

## File toccati

Nessun file del motore, dei binari, del lanciatore quotidiano o del modello e' stato
modificato. Nessuna ricompilazione. `bin_prod` e' stato solo letto. Tutti i file sono nuovi:

| file | ruolo |
|---|---|
| `D:\ds4_work\p0_snapshot_20260914\` | snapshot immutabile FUORI dal repo: 2999 file sorgente + copia di `build\bin`, 253 MB |
| `D:\ds4_work\p0_snapshot_20260914\manifest_p0.json` | manifest di P0 (binari, modello, ambiente, preset redatto) |
| `D:\ds4_work\p0_snapshot_20260914\source_hashes.json` | SHA256 per singolo file sorgente |
| `docs/porto/banco_p0/prepara_fixture.py` | genera UNA VOLTA il riempimento e il catalogo dei 28 casi |
| `docs/porto/banco_p0/sigilla_fixture.py` | ID token, conteggi esatti, `fixtures_manifest.json` |
| `docs/porto/banco_p0/preset_A.json`, `preset_B.json` | i due lati dell'A/B, leggibili e diffabili |
| `docs/porto/banco_p0/avvia_blocco.ps1` | guardia d'istanza unica, avvio, readiness, banco, chiusura |
| `docs/porto/banco_p0/banco_p0.py` | client SSE, metriche, impronte, sonda di carico, cartella di corsa |
| `docs/porto/banco_p0/aggrega.py` | somma/somma, rapporto per coppia, mediana, bootstrap 95% |
| `docs/porto/banco_p0/fixtures/` | fixture congelate: testo, ID token, hash, attesi, rubriche |

## Configurazioni confrontate

Oggi **nessun confronto**: `preset_B.json` e' una copia esatta di `preset_A.json`, perche'
l'opzione dell'ibrido non esiste ancora nel binario. E' la forma corretta del lato N della
matrice a P0: finche' resta cosi', una coppia A/B misura **solo la variabilita' del
controllo**, ed e' esattamente la misura che manca.

Preset A (sperimentale attuale, ibrido inesistente): binari `qwen38_clean\build\bin`,
modello UD-IQ3_XXS, contesto 262144, 64 slot esperti per strato, `--n-cpu-moe 48`,
`-b/-ub 2048`, `-t 16`, `-np 1`, KV `q8_0`, `--jinja`, `--reasoning on --reasoning-preserve`,
greedy (`temperature 0`, `seed 1234`), **MTP spento**, `QWEN4EXP_SPARSE_FA=0`, piu' le
sedici variabili BB/BM del lanciatore sperimentale. Tre deviazioni dichiarate dal lanciatore
quotidiano: host `127.0.0.1` invece di `0.0.0.0`, avvio diretto dell'eseguibile senza .bat,
nessun `pause` finale.

## Link ai run

| run | validita' | contenuto |
|---|---|---|
| `D:\ds4_work\banco_p0_run\20260914_070200_P0_sper_ibrido_assente_r1` | **valido come prova di funzionamento, NON come misura** | 2 riscaldamenti identici + `L01@corto` + `S01@corto` |
| accensione di solo sigillo, 14/9 | nessun dato di velocita' prodotto | rigenerazione di `fixtures_manifest.json` dopo le correzioni |

Corse non valide: nessuna. Corse interrotte: nessuna.

## Risultato e limite

**Snapshot.** L'albero sperimentale **non e' un repository git** (nessun `.git`, nessun HEAD):
lo snapshot e' quindi una copia con hash per file, non un commit. 2999 file, 253 MB in
totale con le DLL. Gli shard del modello non sono copiati e non sono hashati per intero
(76,3 GiB): dimensione, mtime e SHA256 del primo e dell'ultimo MiB, dichiarato nel manifest.

**Fixture congelate.** Riempimento generato una sola volta dai sorgenti del 14/9: 909 830
caratteri da 23 file (`common/arg.cpp` incluso, quindi la domanda tecnica a contesto lungo
ha davvero una risposta nel materiale). Tagli esatti verificati dal server:

| prefisso | caratteri | token | scarto dal bersaglio |
|---|---|---|---|
| `ctx32k` | 126 766 | **32 768** | 0 |
| `ctx131k` | 529 521 | **131 072** | 0 |
| `aghi131k` | 529 929 | 131 208 | +136, cioe' le cinque note operative |

Impronte dei prefissi: `ctx32k` `3a62c0f088f8567e`, `ctx131k` `441d0e5f6d33b227`,
`aghi131k` `ec73073434cdd80a`. Gli ID token sono salvati accanto al testo (JSON sotto i 4096
token, int32 little-endian compresso sopra), con l'SHA256 dei byte non compressi.

28 casi: 8 liberi (3 prosa/spiegazione, 2 ragionamento verificabile, 3 codice nuovo con
test) a contesto corto **e** a 32k, 2 di copia/rinomina sugli stessi input del banco
precedente, **24 di qualita' strutturata** (che includono gli 8 liberi, i 5 fatti a contesto
lungo e la domanda tecnica), 2 di prefill freddo.

**Corsa di fumo.** Caricamento del modello 201,5 s. Tutti gli schemi popolati.

| richiesta | wall HTTP | TTFT primo delta | TTFT primo testo finale | prompt_n | predicted_n | t/s del server | fine |
|---|---|---|---|---|---|---|---|
| riscaldamento 1 | 2,83 s | 2,23 s | — | 61 | 8 | 11,77 | length |
| riscaldamento 2 | 2,00 s | 1,42 s | — | 61 | 8 | 12,01 | length |
| `L01@corto` | 22,64 s | 2,17 s | **mai** | 145 | 512 | 24,97 | length |
| `S01@corto` | 14,62 s | 2,35 s | 12,95 s | 163 | 291 | 23,62 | stop |

- I due riscaldamenti hanno impronta **identica** (`b626d0e377e6075e`): il determinismo in
  greedy regge anche su questo binario, quindi l'impronta e' utilizzabile come oracolo.
- **Il timing del server include davvero tutto.** `wall_HTTP` meno
  (`prompt_ms` + `predicted_ms`) vale fra **+0,014% e +0,78%** (mediana +0,18% sui due casi
  misurati). Non c'e' una fase nascosta fuori dal timing: e' registrato per ogni richiesta nel
  campo `scarto_relativo_pct`.
- Sonda di carico: 21 campioni, GPU fino al 97% con SM a 1927 MHz e 61 °C, VRAM
  11 130 / 12 288 MiB, RAM usata 90,98 GB con **4,91 GB liberi**, RSS del server 78,1 GB.
  Il margine di RAM e' il vincolo stretto di questa macchina e va guardato a ogni corsa.

**Limiti.** Una sola corsa, un processo, quattro richieste: **non e' una baseline**. I 25,02
t/s dell'insieme libero vengono da **un solo caso** e non vanno confrontati con i 25,08 /
27,26 / 29,6 storici, che avevano preset, contesti e MTP diversi. Gli ID token vengono dal
`/tokenize` del binario in esame perche' **`llama-tokenize.exe` non e' compilato in questo
albero** (`build\tools\tokenize` contiene solo file di CMake): e' dichiarato nel manifest
delle fixture.

## Difetti trovati dalla corsa di fumo, e corretti

Sono il vero prodotto della corsa: tutti e cinque avrebbero inquinato ogni misura futura.

1. **Il banco lasciava il server VIVO.** In Windows PowerShell 5.1 lo stderr di un eseguibile
   nativo diventa un `ErrorRecord`: con `$ErrorActionPreference = "Stop"`, il solo fatto che
   `taskkill` stampi un avviso faceva **abortire lo script alla chiusura**, lasciando il
   processo in ascolto sulla 8100. Corretto (`Continue` dalla prima chiamata nativa in poi,
   stderr di `taskkill` deviato dentro `cmd`) e **verificato sul server ancora vivo**.
   Effetto collaterale misurato: `llama-server.exe` avviato senza finestra **non reagisce**
   alla richiesta di chiusura gentile, quindi si finisce sempre nella terminazione forzata.
   L'attesa gentile e' stata accorciata a 20 s e il modo effettivo e' registrato in
   `chiusura.json`. Non c'e' stato da preservare: ogni blocco e' un processo nuovo.
2. **512 token di budget non bastano al gruppo libero.** `L01@corto` ha consumato tutti e 512
   i token **dentro il ragionamento** e ha prodotto **zero testo finale**. Il protocollo dice
   che un output troncato nel solo ragionamento non supera la qualita': con quel budget
   l'intero insieme libero sarebbe invalutabile. Budget alzati a **1024 in screening e 1536 in
   conferma** per i liberi, 768 per la qualita' strutturata e per i casi a contesto lungo.
   **Questo scosta dalle 512/768 scritte nel protocollo: serve una decisione esplicita.**
3. **La virgola decimale italiana veniva letta come separatore delle migliaia.** In `S01` il
   modello ha risposto `mib_per_esperto: 1888` e `mib_per_token_lordi: 90624` invece di
   1,888 e 906,24: ragiona in inglese e legge `1,888` come milleottocentottantotto. Sarebbe
   stato rumore **sistematico** in ogni confronto di qualita', per un motivo che non c'entra
   nulla con l'ibrido. Ai sei casi con decimali e' premessa un'avvertenza di notazione.
4. **Falso allarme nel controllo degli aghi.** Il controllo «l'atteso compare gia' nel
   materiale?» deduceva l'atteso con una regex e segnalava `'F'` (da «Ferruccio»). Ora
   l'atteso arriva dal catalogo dei casi.
5. **La guardia della porta avrebbe impedito il lato B di ogni coppia.** Contava qualunque
   riga di `netstat` sulla 8100, e dopo un blocco restano decine di socket in **TIME_WAIT**
   per qualche minuto: lanciare B subito dopo A sarebbe stato rifiutato con «porta
   occupata». Ora la guardia guarda **solo LISTENING** e conta i TIME_WAIT come informazione.

I punti 2 e 3 sono stati corretti **prima** di qualunque misura, quindi nessun dato e' stato
invalidato; le fixture sono state ricongelate con la seconda accensione di solo sigillo.
Di conseguenza il `fixtures_manifest_sha256` registrato dalla corsa di fumo si riferisce alle
fixture **pre-correzione**: e' scritto nel suo `manifest.json` e la corsa resta cio' che
dichiara di essere, una prova di funzionamento.

## Decisione

**Proseguire.** Le consegne di P0 esistono e funzionano. Per dichiarare la fase COMPLETATA
mancano le tre coppie di variabilita' del controllo, da lanciare in serie a macchina quieta.

## Regressioni aperte

Nessuna introdotta. Due osservazioni invalidano documentazione esistente:

1. **Deriva rispetto all'HANDOFF del 13/9 §1.1.** L'handoff dice che fra `bin_prod` e
   `build\bin` differiscono **solo** `ggml-cuda.dll` e `llama.dll`. Oggi differiscono
   **quattro** file: si sono aggiunte `ggml-base.dll` (`D3842EB1` contro `5F4BA614`) e
   `llama-common.dll` (`2253BD46` contro `13648095`), ricompilate il 13/9 alle 13:09-13:10 dal
   lavoro sulle prestazioni. Conseguenza pratica: **«promuovere la sparse FA copiando due
   DLL» non e' piu' vero**, e una copia di quattro DLL non sarebbe piu' una promozione
   isolata della sparse FA.
2. **La `ggml-cuda.dll` in `build\bin` non e' quella del contatore dei colpi di cache.**
   L'handoff §4.A indica `321BA4AC`; su disco c'e' `26BA28B4` (13/9 12:57), la build
   successiva. Il manifest di pianificazione del 14/9 registrava gia' `26ba28b4...`, quindi
   **non c'e' deriva dal momento della pianificazione**; ma chi cercasse `LLAMA_MOE_HIT_REPORT`
   «nella DLL della §4.A» starebbe guardando un binario diverso da quello descritto.

Da decidere, non risolto qui: i budget di token del punto 2 sopra scostano dal protocollo.

## Stato dei processi avviati

Nessun `llama-server` attivo; nessun LISTENING sulla 8100 (restano solo socket in TIME_WAIT,
che scadono da soli). Verificato con `tasklist` e `netstat` dopo ciascuna delle due
accensioni. La prima chiusura ha richiesto un intervento manuale a causa del difetto n.1, ed
e' servita a validarne la correzione; la seconda si e' chiusa da sola con lo script corretto
(`modo_chiusura = stop_process_forzato`, come previsto per un processo senza finestra).
Caricamenti del modello misurati: 201,5 s e 190,9 s.

## Prossima azione

1. **Utente / sessione principale:** tre coppie A/B con
   `.\avvia_blocco.ps1 -Preset preset_A.json -Profilo screening -Replica N` e la controparte
   `preset_B.json`, alternando l'ordine dei lati, a macchina quieta e con l'altro agente
   fermo; poi `python aggrega.py --root D:\ds4_work\banco_p0_run --json-out ...`. Serve a
   fissare la variabilita' del controllo **prima** che esista qualcosa da confrontare.
2. Decidere sui budget di token (1024/1536 contro le 512/768 del protocollo) e registrare la
   decisione **prima** delle coppie, non dopo.
3. Registrare la variabilita' misurata come pavimento di rilevabilita' per P4 e P6, accanto
   al ±0,2% gia' noto del prefill.
4. Aprire P1 (contratto e simulatore della cache) lavorando sul sorgente dello snapshot.
