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
   (Nel worktree overlap l'editbin è DENTRO `build_cuda.bat`: strutturale,
   non affidato alla memoria di chi lancia.)
9. **Chi prepara un artefatto per un altro cantiere lo VERIFICA leggendo il
   risultato**, non il comando che l'ha prodotto. Il 6/8 sera un `sed` è
   passato in no-op silenzioso (quoting: `\l` letto come `l`, pattern mai
   combaciato) e ha consegnato un build script «adattato» che compilava
   l'albero SBAGLIATO — fermato dal cantiere ricevente al pre-lancio.
10. **Le decisioni di disegno incrociate viaggiano ancorate e si eseguono solo
    dopo ack.** Ogni messaggio che decide un bivio di disegno dichiara il
    commit di base a cui risponde, e NESSUNA esecuzione parte finché l'altro
    non conferma l'allineamento con un ack esplicito. Un giro in più solo sui
    bivi; i report di stato restano liberi — non hanno mai fatto danni, le
    decisioni incrociate sì (6/8 notte: sei commit e zero codice netto per un
    bivio deciso tre volte su messaggi che si accavallavano; la storia resta
    nel log del ramo overlap perché È la lezione).
    Tre corollari, ognuno pagato la stessa notte:
    - **Una regola scavalcata si revoca PER NOME**, non si lascia in vita
      accanto al suo contrario (due direttive contraddittorie entrambe vive
      hanno causato un'esecuzione legittima nella direzione sbagliata).
    - **Una contraddizione fra direttive non si risolve eseguendo: si
      rimanda** con un giro di ack (clausola del cantiere overlap).
    - **Alla collisione vince l'ALBERO, non l'ultimo messaggio.** Se due
      direttive si incrociano in volo, lo stato dei commit al momento della
      collisione è la verità; nessun movimento di forma senza una ratifica
      emessa DOPO la collisione. I messaggi hanno latenza, l'albero no: dieci
      movimenti in una notte — con diff finale vuota due volte — perché
      ciascun lato si allineava all'ultimo messaggio VISTO dell'altro mentre
      il successivo viaggiava.
    - **La regola del RICEVENTE, che rende stabile tutto il resto: ancora ≠
      HEAD corrente → il messaggio è NULLO ALL'ARRIVO.** Non si esegue, non
      si fa il revert di conformità: si segnala e basta. Senza questa metà,
      il mittente ratifica sempre un albero che non esiste più e il ricevente
      conforma sempre a una direttiva già stantia: tredici movimenti l'hanno
      dimostrato — il livelock è sopravvissuto anche alle ratifiche, perché
      ogni ratifica nasceva ancorata e arrivava stantia. Una direttiva che
      comanda movimento è eseguibile SOLO se la sua ancora è l'HEAD del
      momento in cui viene letta.

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
