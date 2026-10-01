# KV 262.144 token: prova con prompt a 131k — 1 ottobre 2026

**Prova completata.** Strata 0.1.30 + 13 patch avviata con capacita' KV 262.144; le due fixture a 131k raggiungono
entrambe il budget di 1.024 token. Nessun hog o carico artificiale aggiunto; programmi dell'utente lasciati aperti.
Questa prova verifica l'allocazione della capacita' 262k e il funzionamento con prompt a 131k. **Non verifica ancora
un prompt da circa 250k token.**

## Configurazione e avvio

- Eseguibile `D:\ds4_work\strata\Strata\build-0130\strata.exe`, versione runtime 0.1.30.
- `--max-context 262144`, `--kv int8`, `--kv-resident 32768`, `--vram-reserve-mib 1393`, `--elastic`.
- Profilo `lungo_131k`, stessi messaggi e budget della corsa precedente con capacita' 139.264.
- Watchdog 240 s e `STRATA_SPLIT_TIMING=1`; modalita' HC opt-in non aggiunta.
- API di laboratorio solo su `127.0.0.1:18120`. Variabile della chiave API esclusa dal solo processo di prova,
  senza leggere o modificare quella del lanciatore operativo.
- Python 3.12.14 integrato con dipendenze gia' presenti nel clone. Nessun download o ricompilazione.
- Configurazione, log, temporanei e output nella cartella scrivibile del checkout; niente scritture nel clone su D:.

Il runtime conferma `max_context=262144` e `kv_resident=32768`. **Avvio in 60,95 s**.
K/V in RAM bloccata: **3,09 GiB**, contro 1,64 GiB registrati con capacita' 139.264.
Cache esperti iniziale 7.061 slot: nucleo fisso 3.493 (5,70 GiB) e coda 3.568 (5,70 GiB).
Durante le richieste: crescita fino a 7.548 slot, con un calo intermedio di 90 slot.

## Risultati

| Caso | Prompt | Riusati | Prefill token/s | Decode token/s | Primo token | Output |
|---|---:|---:|---:|---:|---:|---:|
| L01 | 131.248 | 0 | **663,01** | **46,104** | 198,591 s | 1.024 |
| L02 | 131.239 | 131.072 | 77,71* | **40,373** | 2,769 s | 1.024 |

*L02 legge solo 167 token nuovi: non e' un secondo prefill completo.*

Decode aggregato: **43,049 token/s**. Da `costo_passata.py`: **19,8 ms per riga**, 40,9 ms per finestra,
1,76 token per finestra e 2,07 righe per finestra. Entrambe le richieste terminate con `finish_reason=length`.
Nessuno stallo, errore CUDA o intervento del watchdog osservato. Processi di laboratorio terminati a fine prova;
verificata l'assenza di motori rimasti accesi.

RAM disponibile minima: **32,59 GB**. Nei campioni validi di CPU dell'intera corsa, inclusi avvio e prefill,
gli altri processi usano in media circa **0,72 core**, massimo 2,83. Il sampler registra CPU e RAM ogni 10 s e non
interroga ripetutamente `nvidia-smi`; il banco originale legge la VRAM prima delle singole richieste.

## Confronto storico

| Capacita' KV, stessi prompt a 131k | Decode aggregato | Prefill freddo | ms/riga | K/V in RAM bloccata |
|---|---:|---:|---:|---:|
| 139.264, corsa precedente | 41,763 token/s | 628,75 token/s | 20,4 | 1,64 GiB |
| 262.144, questa corsa | 43,049 token/s | 663,01 token/s | 19,8 | 3,09 GiB |

In questa corsa non emerge una regressione di prestazioni con la capacita' maggiore. **Non e' un A/B alternato
nella stessa sessione**: carico, residenza degli esperti e testo generato possono cambiare. L'esito utile e'
l'allocazione riuscita e il completamento delle richieste con KV 262k, non un guadagno garantito dal contesto maggiore.

## Ripetizione e stato operativo

Strumento: `strumenti/prova_kv262k.py`. Richiede un Python 3.12 utilizzabile; nella sessione protetta quello
integrato di Codex ha funzionato con le dipendenze gia' installate del clone. Prima del lancio escludere la
variabile API dall'ambiente del solo processo di laboratorio; il programma rifiuta di avviare un secondo motore
se Strata o llama-server sono gia' attivi.

Evidenza in `corse_2080ti/20261001_kv262k_prompt131k/`: configurazione effettiva, health, log del motore/server,
risultati, campioni CPU/RAM e SHA256 dell'eseguibile. Output testuali e bootstrap restano in
`.codex_runs/20261001_052405_kv262k_prompt131k_20261001/`.

Al termine di questa prima prova il lanciatore operativo conservava ancora capacita' 139.264: la sessione
protetta impediva staging Git e scritture nelle cartelle operative. **Successivamente l'utente ha dato accesso
completo e autorizzato la promozione della #270 con KV 262.144 nello stesso lanciatore**. Installazione,
controlli e ripristino sono documentati in `RISULTATI_PR270_1_OTTOBRE.md`; la configurazione operativa attuale
e' la copia versionata `lanciatori/strata-2080ti-sota.json`.
