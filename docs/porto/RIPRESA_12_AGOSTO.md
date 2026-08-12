---
name: resume-20260812-notte-sota-1477
description: "Ripresa del 12 agosto — SOTA 14,77, cinque fronti chiusi con un numero, e il solo fronte che resta è il calcolo CPU che la GPU non copre"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1c34df6e-b359-4454-9f30-2ea9f48b0bb4
  modified: 2026-08-12T04:09:44.790Z
---

# RIPRESA — notte fra l'11 e il 12 agosto

## La configurazione da usare, adesso

```
  LLAMA_CACHE_ESPERTI_SLOT          512      (era 339)
  LLAMA_CACHE_ESPERTI_FORK            2      (era 0)
  LLAMA_CACHE_ESPERTI_FORK_BLOCCHI    8      (difetto 32, mai toccato da 160 script)
  tutto il resto invariato: ASYNC=1 K=2, IBRIDO=1, bozza n-max 1,
  DSV4_HC_FUSO=5, LRU=1, SFRATTO_PAR=1, W=0
```

**14,77 t/s**, ciclo 125,3 ms, contro 14,22 del riferimento appaiato. Confermata a
macchina ferma con due ripetizioni allo 0,6%. Dettagli e caveat in
[[sota-1477-fork-blocchi-512]] — **lo SHA cambia** e 512 è al muro della VRAM.

## Cosa è stato chiuso, ognuno con un numero

- **Il prefetch, in tutte e tre le forme.** `CURA` è in un ramo irraggiungibile
  con `LRU=1`; `SCUDO` marca e non prenota (`kern_prenota:2534`); il `DMA`
  fra-strati non consegna un chunk su settemila. Vedi
  [[leva-esiste-solo-se-il-ramo-e-raggiungibile]].
- **La capienza oltre 512**: è un muro di VRAM, non una politica. A margine
  uguale, 512 slot fanno 12,01 e 768 fanno 9,44 — e i matmul crescono del 78%
  perché il set caldo non entra più in 12 GB.
- **Il join, per la terza volta e finalmente col perché**: non è sync-bound. Le
  barriere valgono **un ottavo**; il resto sono 15,4 ms per grafo in cui la CPU
  calcola e la GPU non la copre. `LLAMA_OVERLAP_JOIN_ASYNC` acceso toglie il 13%
  del `sync` e vale lo 0,5%.
- **Il proxy host**: chiuso da un microbench. Il giro di ritorno è **11 µs**, non
  era quello il problema — ma `cudaMemcpyAsync` interferisce col calcolo **più**
  del nostro kernel a 8 blocchi (+4,91 contro +2,91 ms). Siamo già sul cammino
  più economico. Vedi [[previsione-compra-il-meccanismo]] per il contesto esterno.
- **I pesi densi, per la decima volta**, con l'inventario che torna al byte:
  99,843% dei 7383,67 MiB è riletto a ogni token. Non è una stanza da liberare,
  è il pavimento.

## Cosa resta aperto

**Il fronte vero è uno solo**: i **15,4 ms per grafo** in cui il worker CPU
calcola e la GPU non riesce a coprirlo. Non è un problema di barriere — quello è
misurato e vale un ottavo. È lavoro vero sul ramo sbagliato.

**Un candidato lasciato in sospeso onestamente**: `LLAMA_DSV4_HC_FUSO=7`
migliora il ciclo del 2,9% e perde il 2,7% di p1 — netto dentro il rumore. La
decomposizione della maschera è nuova: **`post` paga sul ciclo e NON costa p1;
`pre` paga sul ciclo MA si ripaga col p1; `comb` da solo è il peggiore.** Va
deciso **a macchina fredda con ripetizioni**.

**Non ancora provato**: bozza accesa + lane CPU **spenta**, con fork e 512 slot.
Tutte le misure a lane spenta hanno anche la bozza spenta. Conta perché la lane
impone `IBRIDO=1`, che convoca le 277 copie a token del fallback dello scheduler.

## Lo stato del banco, e va letto prima di misurare

**Alle 05:00 la deriva era del 2,2%** — `f5` e `f5b`, stessa configurazione e
stesso SHA, davano 14,17 e 14,48; e la stessa configurazione faceva 14,77 alle
19:29. **Niente sotto il 4% era decidibile in coda alla sessione.** Rimisurare la
SOTA a macchina fredda prima di confrontarci qualunque cosa.

## Il porto da upstream

`git fetch upstream --unshallow` **fatto**: la base comune è `5c3a58686` (9
luglio), upstream avanti di **436** commit, noi 131. I «108» e «153» che avevo
riferito erano artefatti della profondità di fetch.

Cinque porti dentro (`c770ec41c`, `c91bb3678`, `9b7f9eea7`, `bd06d4ddf`), tutti
**inerti o igienici** — e lo sapevamo prima, perché quattro lettori indipendenti
avevano detto che nella finestra 2-11 agosto upstream non ha toccato **un solo
kernel del nostro profilo**. Il rebase è impossibile (nessun antenato prima
dell'unshallow): **cherry-pick, sempre**.

Le sei relazioni sono in `docs/porto/audit/70-…` e `71-…` e `7x-up_*`.

## Le regole che questa notte ha comprato

- **Ciclo e p1 vanno dichiarati SEPARATI.** Il t/s li moltiplica e nasconde quale
  si è mosso. Mi ha fatto ritirare una conclusione e aprire un cantiere inutile.
- **Il p1 di una traiettoria diversa è una lotteria, non un danno.** Il fork
  perdeva 12 punti a 339 slot e a 448 ne guadagnava rispetto al riferimento.
- **Una manopola tarata su un banco va RIPORTATA sull'altro prima di giudicare la
  leva che la usa.** `FORK_BLOCCHI=8` trovato sul banco spoglio e non riportato:
  la leva sembrava perdere il 4,2% e vale +3,9%.
- **Un cancello sui COLPI ha bisogno di una guardia sul MECCANISMO** (`in
  prefetch > 0`) prima di guardare qualunque numero.
- **Un microbench valida la FORMA che ha misurato, non il nome che le diamo.**
  «Altro stream» e «altro motore» sono due pezzi di hardware diversi.

## Delega

**Codex non consegna**: cinque mandati, zero byte, ~200k token — vedi
[[codex-non-consegna-verifica-sul-disco]]. Gli agenti `general-purpose` e
`Explore` hanno prodotto sei relazioni ottime. E **il tool Bash non restituisce
stdout** in queste sessioni: usare PowerShell.
