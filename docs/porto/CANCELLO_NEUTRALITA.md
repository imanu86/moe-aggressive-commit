# Il cancello di neutralità — NON passato (2 agosto 2026, sera)

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
