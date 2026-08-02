# Il cancello di neutralità (2 agosto 2026, sera)

> **AGGIORNAMENTO, stessa sera.** Il verdetto qui sotto è RIBALTATO. La pagina
> rotta era la **modalità di ragionamento**, non il motore. Vedi §0.

---

## 0. Il ribaltamento: era il pensiero, non llama.cpp

L'utente ha dubitato che i pesi fossero gli stessi. Non lo erano? Lo erano — ma
il controllo ha fatto emergere l'asimmetria vera: `braccio.ps1:291` passa
`think=false` esplicito, il banco llama non passava niente, e llama.cpp tiene il
ragionamento **acceso** di default. Provato: la risposta del run `sota8k` aveva
un campo `reasoning_content` da 634 caratteri.

Rifatto con `--reasoning-budget 0`:

```
                     token   byte    CSS  ancore rotte   forma
llama pensiero ON     6535  25244   103    #services     hero vuoto a tutta altezza,
                                                         servizi promessi e mai scritti
llama no-think 8k     4184  14072    63    nessuna
llama no-think 20k    4527  15022    70    nessuna       hero a due colonne con mockup
                                                         di terminale, servizi presenti
DwarfStar B           4500  15293    67    nessuna       3 schede con icone
```

**2000 token in meno, stessa velocità** (7,15 contro 7,12 t/s), e la pagina
diventa migliore: due colonne invece di un hero vuoto, un mockup di terminale
che scrive `$ ./deploy_ai --model=neural-v2 ... ✓ ready. 99.9% accuracy`, i
servizi presenti come elenco, e **nessuna ancora rotta**.

Contro DwarfStar il confronto è ora quasi pari: 4527/4500 token, 15022/15293
byte, 70/67 regole CSS. La differenza residua è di forma — DwarfStar mette tre
schede con icone, llama un elenco.

**Quindi llama.cpp non produce documenti peggiori.** Il difetto era nostro, per
la seconda volta in una sera: prima il mojibake nel salvataggio, poi il
confronto fra un motore che pensava e uno che non pensava.

### Nota sui riferimenti "NeuraForge"

L'utente ricordava pagine migliori intitolate *NeuraForge*. Esistono
(`D:\ds4_work\lane_ab\runs\X_GSPEC\pagina_turno*.html`, 20.701 byte, 4 sezioni,
3 schede, nessuna ancora rotta) ma vengono da un **prompt diverso** — "AI
Startup" invece di "AI programming shop" — e sono precedenti al 1° agosto,
quando il prompt di campagna è stato fissato con `dcc645d`. Non sono
confrontabili con i run attuali. Avevo risposto che "il prompt non è mai
cambiato": era vero solo per i banchi creati il 1-2 agosto.

---

## Il verdetto originale, superato da §0

Il confronto fra motori si è sempre giocato sui t/s. Guardando le pagine, non è
alla pari.

## Il fatto

Stesso prompt (sha `38f6ec5ee5403f59`), stessi pesi `DS4-0731-IQ2XXS.gguf`,
temperatura 0, stessa macchina.

```
                      byte    regole CSS   link interni   ancore rotte   schede servizio
DwarfStar B_031840    15.293      67             4          nessuna            3
llama.cpp sota8k      25.244     103             4          #services          0
```

**La pagina llama.cpp mette "SERVICES" nella navigazione, aggiunge un pulsante
"EXPLORE CAPABILITIES", e poi la sezione non la scrive mai.** Il link punta nel
vuoto. Ha più byte e più CSS, ma il contenuto promesso manca; DwarfStar produce
le tre schede con icone e descrizioni e non ha ancore rotte.

Quindi il **+63% di velocità** (7,12 contro 4,37 t/s) è stato pagato con un
documento incompleto — almeno su questo campione.

## Perché i due motori divergono così tanto

Divergono dal **carattere zero**:

```
DwarfStar   "Here is a complete, single-file HTML landing page for a cybe..."
llama.cpp   "<!DOCTYPE html>\n<html lang=\"en\">..."
```

A 2 bit, due implementazioni diverse degli stessi pesi accumulano differenze
numeriche che fanno divergere l'argmax quasi subito. Non esiste un confronto
token per token: la qualità va giudicata sull'insieme.

(Di passaggio: DwarfStar **ignora** l'istruzione "Return only the HTML
document" e antepone una frase; llama.cpp restituisce solo il documento, sia
pure incartato in un blocco markdown.)

## Due riparazioni servite per poter guardare

Prima di questo confronto le due pagine non erano confrontabili, e per colpa
nostra:

1. **Mojibake sul lato llama.** `Get-Content -Raw` senza `-Encoding UTF8` legge
   con la codepage ANSI: ogni carattere multibyte veniva letto come
   windows-1252 e riscritto come UTF-8. Provato confrontando col JSON grezzo,
   `U+2014` → `U+00E2 U+20AC U+201D`. Riguardava OGNI documento della campagna:
   trattini, frecce, emoji sparsi per la pagina come spazzatura. Corretto in
   `llama_confronto.ps1`, `dspark.ps1`, `prefill_lungo.ps1`.
2. **Quirks mode sul lato DwarfStar.** I 187 caratteri di prosa prima del
   `<!DOCTYPE` mandavano il browser in quirks mode, cambiando il layout di
   tutta la pagina.

Le pagine confrontabili sono i file `.pulito.html`, rigenerati dal JSON e
ritagliati fra `<!DOCTYPE` e `</html>`.

## Il protocollo che manca

**n=1 per motore, e ripetere non aiuta**: a temperatura 0 lo stesso prompt dà
lo stesso output, quindi la ripetizione non aggiunge informazione. Serve una
**batteria di prompt diversi**, giudicati su criteri che non richiedono un
giudice:

```
ancore interne rotte            (misurabile)
sezioni promesse dalla nav      (misurabile: ogni voce ha il suo id?)
campi del form richiesti dal prompt
tag strutturali aperti/chiusi
degenerazione (righe ripetute consecutive)
```

più una lettura a occhio. Cinque prompt per due motori sono dieci run: circa
un'ora, ed è il prezzo per poter dire quale motore è migliore invece di quale
è più veloce.

**Finché non è fatto, "llama.cpp vince" resta una affermazione sulla velocità,
non sul motore.**
