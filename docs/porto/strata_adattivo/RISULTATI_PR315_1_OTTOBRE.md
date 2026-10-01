# PR315 — hyper-connection sulla RTX 2080 Ti, 1 ottobre 2026

**Esito:** parita' numerica superata e kernel piu' rapido. Nel confronto sul modello a cache
fissa, decode **41,219 contro 39,780 t/s (+3,62%)**, costo per riga verificata **−1,35%**,
prefill invariato. Segnale positivo contenuto, da confermare prima di una promozione:
una sola coppia e risposte diverse. **Lanciatore operativo ancora con #270.**

Ripresa autorizzata dall'utente dopo lo standby: macchina disponibile, nessun carico artificiale.
La SOTA operativa resta Strata 0.1.30 + 13 patch + PR270, KV int8 con capacita' **262.144**,
32.768 token residenti in VRAM. Tutte le prove sul modello usano due richieste da circa **131k**,
1.024 token generati ciascuna: non validano ancora il riempimento fino a 250k.

## Candidata e integrazione

PR upstream [#315](https://github.com/Niko1221/Strata/pull/315), commit
`334bb2bf7c43f8612b18e527d7c6e03f22d159eb`. Normalizzazione per token e stream (v2),
proiezione down con staging delle attivazioni (v3), controllo numerico automatico per GPU
e scelta della variante piu' recente che passa. Su **sm75 lo staging usa copie normali**:
il messaggio generico upstream cita `cp.async`, che qui non viene usato.

L'integrazione sostituisce il percorso HC opzionale della #186 (`STRATA_GR_V3`), mantenendo
il tile 1280 della #258 per sm75 nei kernel v1/v2 e il prefill #270. La SOTA non aveva
`STRATA_GR_V3=1`. Dieci corpi di funzione del percorso base risultano identici dopo la
rimozione di commenti e spazi; evidenza in `baseline_math_check.json`.

Compilata con CUDA 12.6 e MSVC, sm75+86, in una cartella del repository, usando gli oggetti
invariati della build originale e il nuovo oggetto di attenzione #270. Nessuna modifica
ai sorgenti o al lanciatore operativo in `D:\ds4_work`.

- SOTA: `D:\ds4_work\strata\Strata\build-0130-pr270\strata.exe`, SHA256
  `713922610f2820b0e726adc371eb774a7d5502a548d08b59d244afbb38e898ed`.
- Candidata: `.codex_runs/strata_pr315_20261001/strata.exe`, SHA256
  `365882aaef21941839e128859ce06348bb257549b329e35f345d50441c9dc893`.
- Riproduzione: `strumenti/compila_pr315.py prepare --out <cartella nuova>`, poi
  `strumenti/compila_pr315.py build --out <stessa cartella> --bench`.
- Patch originale con attribuzione e patch integrata: `patches/da-valutare/0015-PR315-HC-bitwise-*.patch`.
  `git apply --check` della patch integrata sul clone operativo superato; patch non applicata al clone.

## Parita' e banco del kernel

Il controllo upstream compara v2 e v3 con v1 su **1–8 token**, con e senza scrittura pendente,
e v1 con il percorso singolo a un token. Geometria reale N=2560, HC=4, LR=320.
Nessun errore o scarto registrato: la GPU seleziona **v3**. Il controllo viene ripetuto
all'avvio della verifica nel motore candidato, con fallback automatico.

Banco breve: 20 riscaldamenti e tre serie da 200 chiamate per caso, scrittura pendente attiva,
tempi CUDA; mediana in microsecondi. I tempi sono del solo kernel, non del modello.

| Token | v1 riferimento | v2 | v3 | Riduzione v3/v1 |
|---:|---:|---:|---:|---:|
| 1 | 67,642 | 56,200 | 49,080 | 27,4% |
| 2 | 79,319 | 57,058 | 50,289 | 36,6% |
| 4 | 122,337 | 83,149 | 68,697 | 43,8% |
| 8 | 139,679 | 134,464 | 130,632 | 6,5% |

Una sessione breve, varianti in sequenza: frequenze e temperatura non sono bloccate.
Il risultato dimostra un vantaggio locale del kernel in questa prova; non va trasformato
direttamente in una percentuale di guadagno del decode.

## Modello con cache elastica: riferimento / candidata / riferimento

Stesso profilo `lungo_131k`, KV 262.144, nessun hog GPU o stress CPU/RAM. Due riscaldamenti,
poi L01 fredda (131.248 token) e L02 con 131.072 riutilizzati e 167 nuovi.
Entrambe le richieste completano 1.024 token con `finish=length` in tutte le corse accettate.

| Corsa | Prefill L01 t/s | Primo token s | Decode aggregato t/s | ms/riga verificata | Esperti iniziali | Altri core CPU medi |
|---|---:|---:|---:|---:|---:|---:|
| A1 SOTA | 756,42 | 174,088 | 39,338 | 21,729 | 6.602 | 0,808 |
| B candidata v3 | 765,18 | 172,271 | 42,386 | 20,066 | 6.742 | 1,800 |
| A2 SOTA | 811,00 | 162,427 | 44,646 | 18,815 | 7.753 | 0,360 |

Il riferimento cambia piu' del vantaggio apparente della candidata. A2 parte con una cache
maggiore e meno attivita' CPU. Gli output generati differiscono, anche fra A1 e A2:
la residenza GPU/CPU degli esperti cambia gli arrotondamenti e l'accettazione delle bozze.
**Questa serie non dimostra un incremento del decode attribuibile alla #315.**

I ms/riga sono ricalcolati dai log: passate = token generati meno bozze accettate;
righe verificate = passate piu' bozze offerte. Il monitor CPU campiona ogni 10 secondi,
esclude il primo campione senza intervallo e conta 1,0 come un core intero. Le medie
comprendono caricamento e prefill; i pochi campioni nel decode sono conservati separatamente.

## Controllo con cache fissa

Per ridurre la variabilita' della dimensione della cache, solo nel laboratorio viene rimosso
`--elastic` e impostato un budget numerico. Il conteggio richiesto non e' quello effettivo:
il pack nativo dimensiona gli slot per strato e puo' contenerne circa il 30% in piu'.

La prima corsa C con richiesta 6.600 ha prodotto 8.577 slot e **zero MiB liberi**. E' stata
interrotta e **esclusa dai risultati**, senza accettarne misure. Log e motivo conservati in
`C_esclusa_fissa6600/`. Il banco ora controlla `/metrics` prima di inviare qualsiasi prompt
e rifiuta una cache fissa con meno di 1.000 MiB di VRAM libera.

La richiesta corretta 5.000 produce **6.705 slot effettivi, 11.107 MiB** in entrambe le build:
1.157 MiB liberi nel riferimento C2 e 1.513 nella candidata D. Sono prove sequenziali;
il carico naturale della macchina rimane misurato, senza bloccare o chiudere le app dell'utente.

| Corsa | Prefill L01 t/s | Primo token s | Decode L01 / L02 t/s | Decode aggregato t/s | ms/riga verificata | Altri core CPU medi |
|---|---:|---:|---:|---:|---:|---:|
| C2 SOTA fissa | 754,60 | 174,530 | 41,694 / 38,035 | 39,780 | 21,074 | 0,766 |
| D candidata v3 fissa | 754,34 | 174,591 | 43,028 / 39,556 | 41,219 | 20,789 | 0,715 |

Cinque campioni CPU nel decode per corsa: altri processi medi 0,610 / 0,678 core.
Il testo generato differisce anche a parita' di numero di slot: la cache fissa mantiene la
dimensione, mentre l'adattamento dei contenuti e l'esecuzione CPU/GPU restano attivi.
Token per finestra 1,714 / 1,739; righe per finestra 2,044 / 2,029; ms per finestra
43,082 / 42,177. Il guadagno del decode include quindi una diversa accettazione delle bozze.
Nell'ultima statistica cumulativa, attesa GPU 26,024 / 25,265 ms e pool+piano 10,058 / 9,729 ms
per finestra: non varia solo la parte GPU. Non attribuire l'intero +3,62% alla #315.

L01 usa tutto il prefill; L02 riutilizza 131.072 token, quindi i suoi 73,93 / 73,69 t/s sono
calcolati sui **167 nuovi**, non sui 131k riutilizzati. Tutte le dieci richieste lunghe
delle cinque corse accettate completano il budget; nessuno stallo o errore di kernel.

## Decisione e prossimo controllo

La #315 e' **validata numericamente sulla 2080 Ti e promettente sul kernel**. Conservare la
candidata per un confronto di conferma v1/v3 nello stesso binario, con cache di uguale budget
e condizioni misurate. Questa sessione non giustifica dichiarare un nuovo record stabile
o cambiare il lanciatore sulla base del solo +3,62%. Dopo quel controllo, il prossimo lavoro
per la velocita' resta la parte densa della #242: la parte esperti a decodifica unica e' gia'
nella patch 0007; evitare di attribuirle un miglioramento nuovo.

Alla fine delle corse tutti i processi di laboratorio sono stati chiusi; verificati zero motori
e zero server di laboratorio attivi, hash e configurazione operativa ancora #270/KV 262.144.
Durante le prove il profilo di accesso impediva commit/push e scritture su `D:\ds4_work`/Desktop.
L'accesso completo e' stato ripristinato nella ripresa successiva e permette la pubblicazione
di risultati e strumenti sul branch autorizzato. **Nessuna promozione della #315 effettuata.**

## Evidenza e limiti

`corse_2080ti/20261001_pr315/` conserva build e hash, controllo numerico, banco HC,
configurazioni, health, metriche iniziali, log motore/server, CPU e risultati delle corse.
`analizza.py` ricalcola `confronto.json` e i riassunti CPU dai file conservati.
Gli eseguibili e gli oggetti compilati restano in `.codex_runs/`, fuori dall'evidenza da pubblicare.

Non sono testati: prompt pieno a circa 250k, accuratezza semantica del modello, stabilita'
su altre GPU, confronto prestazionale lungo o con frequenze bloccate. La parita' bit per bit
si riferisce agli HC nei casi numerici controllati, non a tutte le risposte dell'intero modello.
