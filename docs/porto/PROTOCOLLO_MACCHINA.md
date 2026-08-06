# PROTOCOLLO MACCHINA — due cantieri, una GPU, un arbitro

*Scritto il 6/8/2026 sera. Vale per le sessioni OVERLAP e TESTA e per chiunque
si aggiunga. La macchina è UNA: RTX 3060 12 GB, 96 GB RAM, e il modello ne
occupa 74 quando gira.*

## La regola unica

**Nessuna build e nessuna run senza autorizzazione della sessione
coordinatrice** (`local_1c34df6e-b359-4454-9f30-2ea9f48b0bb4`; se l'ID non
risolve, cercarla con `list_sessions`). Compilare **è** usare la macchina: il
6/8 un build atterrato durante i bracci altrui ha invalidato una passata
intera, e ci è costato un'ora capirlo.

## Come si chiede

Un messaggio con:

    [RICHIESTA MACCHINA] tipo: build | run corta (<10 min) | run lunga
    cosa: una riga
    stima: minuti
    worktree/binario: quale

Si parte SOLO dopo `[MACCHINA A TE]`. A fine lavoro: `[MACCHINA LIBERA]` con
l'esito in una riga. Se dopo la stima dichiarata la macchina non è stata
liberata, il coordinatore può verificare i processi e riprendersela.

## I cancelli, per ogni run (non negoziabili — ognuno è costato una lezione)

1. **RAM libera ≥ 10 GiB** all'avvio, o il braccio non vale (5/8: due processi
   da 74 GiB insieme, un'ora di misure false).
2. **Un processo pesante alla volta.**
3. **VRAM libera campionata**: sotto ~400 MiB la scheda si strozza e il braccio
   non vale, qualunque cosa dica il tasso di colpi.
4. **Battito del contatore a 5 s** (`LLAMA_CACHE_ESPERTI_BATTITO=5`) nelle run
   corte: a 60 il contatore non stampa dentro una richiesta da 41 s, e la
   differenza fra due zeri fa zero.
5. **Il contatore prima della velocità**: ~257 domande/token = la cache lavora;
   ~17 = scavalcata e il t/s non significa niente; mai stampato = NON
   DECIDIBILE, non «scavalcata».
6. **Ledger obbligatorio**: ogni run produce la sua riga in
   `docs/porto/LEDGER_RUN.tsv` e l'output catalogato. Vale anche per i
   fallimenti.
7. **Ogni sessione lavora nel SUO worktree.** `D:\llama-dspark` (ramo jacobi) è
   riservato al coordinatore per le misure di riferimento; `D:\llama-overlap`
   è del cantiere overlap. Due processi sullo stesso albero si bloccano le DLL
   (5/8).
8. **Dopo ogni link**: `editbin /STACK:67108864` sul binario, previo
   `vcvars64.bat`. Senza, exit muto `0xC00000FD` sui grafi frammentati.

## I report

Report **continui** alla sessione coordinatrice: a ogni risultato, correzione o
blocco — non a fine giornata. Numeri nel messaggio, non solo «fatto». Le
correzioni incrociate sono il meccanismo che il 6/8 ha tenuto il registro
onesto in entrambe le direzioni: quattro ritrattazioni, zero numeri sbagliati
sopravvissuti.

## La regola del dubbio (dall'utente, 6/8 pomeriggio)

**Tutto ciò che sembra dubbio si passa all'altra sessione.** Codice proprio
toccato due volte con convinzione sbagliata → lo rivede l'altro. Ha pagato ogni
singola volta che è stata applicata: due difetti trovati in revisione che
l'autore non vedeva, di cui uno che avrebbe corrotto il routing in silenzio.
