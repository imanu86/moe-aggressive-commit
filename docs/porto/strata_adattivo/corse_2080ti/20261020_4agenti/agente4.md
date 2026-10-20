# Agente 4 — misura (20/10/2026, dalle 05:56)

**Conclusione**: i comandi B-A-B della passata unica sono pronti e agganciati alla build dell'agente 1
(`build-passata-e29c8065`), più un **banco nuovo a 4 agenti con contesti di lunghezze diverse** (2k, 8k, 30k, 90k di
contesto; 1-4k token nuovi) che leggono mentre gli altri scrivono, e un **verdetto automatico** che stampa guadagni,
dispersione e identità dei token. **Compilato no (non è compito mio), installato no, provato no, misurato no**: qui non
è stata avviata nessuna corsa GPU. Provato sì, ma solo fuori dalla GPU: sintassi Python e bash, parser dei log del
motore provati su righe reali prese dai formati di `generate.cpp`, verdetto provato su dati finti, replay validato con
`--dry` (stampa il piano, niente server). Nessuna GPU usata, nessun `bench.lock` preso o cancellato, nessun
`strata.exe` fermato (quello della 8100 è vivo).

## File toccati (solo i miei)

| file | cosa |
|---|---|
| `corse_2080ti/20261019_passata_unica/letture_miste.py` | **nuovo** — banco 4 agenti a contesti misti, lettura+scrittura in contemporanea |
| `corse_2080ti/20261019_passata_unica/coda_lc_miste.sh` | **nuovo** — coda B-A-B del banco misto (prende `bench.lock` da sé) |
| `corse_2080ti/20261019_passata_unica/pu_verdict.py` | **nuovo** — verdetto B-A-B dei `lc_*/res.json` + confronto byte dei testi |
| `corse_2080ti/20261019_passata_unica/coda_lc.sh` | modificato — build auto-detect, bracci selezionabili, nota servizio 8100 |
| `corse_2080ti/20261019_passata_unica/coda_replay_pu.sh` | modificato — build auto-detect, nota servizio 8100 |
| `corse_2080ti/20261020_4agenti/agente4.md` | questo doc |

Non toccati: `letture_concorrenti.py` (funziona così com'è, prende l'exe come argomento), `misura_4agenti.py` (è di un
altro: vedi la nota in fondo), `src/`, `serve/`, qualsiasi lock o processo.

## Banco nuovo: `letture_miste.py`

4 conversazioni con contesti di lunghezze diverse, tagliati dal prefisso `ctx131k` della fixture + storia privata a
seme fisso (default 2k, 8k, 30k, 90k token; i token reali vengono dal `prompt_tokens` della scaldata, e da lì si
calibra quanto deve essere lungo ogni «coda» nuova). Ogni contesto viene scaldato una volta prima del cronometro.

Giri per braccio:
- **misti** (default 2): 2 agenti mandano INSIEME una lettura (1-4k token nuovi, `max_tokens 8`) mentre gli altri 2
  scrivono (turno corto, 400 token); i ruoli si scambiano a ogni giro → misura il decode degli altri **durante** le letture;
- **burst** (default 1): **tutte e 4 le letture insieme**, con 1 scrittore di supporto (contesto 2k, 600 token) partito
  4 s prima → misura il tempo totale delle 4 letture eterogenee e il t/s di chi decodifica mentre le 4 leggono.

Per ogni giro riporta: `readers_wall` (primo invio → ultima fine), TTFT per lettore, token nuovi letti e t/s di lettura,
t/s degli scrittori durante / prima / dopo la finestra, e **il lato motore** dal log: `prompt N tokens = R reused + L
read in X ms` per richiesta, `read N tokens on a thread of its own ... the slots decoded M rows meanwhile (rows/s)`,
righe `strata pack:` / `gave back ...`, e le righe `[strata] pack: K prompt(s) sent ahead in the W ms window` del
server (l'agente 3). Poi la **parità**: l'ultima lettura di ogni agente rimandata da sola (temperature 0, 64 token),
testo salvato per il confronto fra bracci. Campiona anche il carico CPU altrui e JumpConnect.

Parametri utili: `--ctx 2000,8000,30000,90000`, `--tails 1000,2000,3000,4000`, `--split 2`, `--rounds 2 --burst 1`,
`--wmaxt 400 --smaxt 600 --rmaxt 8 --pmaxt 64`, `--port 8105` (non toca il 8104 del banco vecchio né il 8100).

## Comandi pronti (nell'ordine, da Git Bash)

Prerequisito, e non è nelle mie mani: **il servizio agenti sulla 8100 (`servi_agenti.py`) tiene `bench.lock` e un
`strata.exe` vivo** → `bench_lock.py` aspetta che non ci sia nessun `strata.exe` e che il lock sia libero. Se il
servizio resta su, i bracci aspettano per sempre: va fermato **dall'owner** e riacceso dopo le corse. `bench.lock` non
va mai cancellato a mano; se esiste `lab_locks\pause` nessuna corsa parte.

```bash
cd C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/strata_adattivo/corse_2080ti/20261019_passata_unica

# 1) banco 4 agenti a contesti misti, B-A-B sullo stesso exe (senza argomento prende build-passata-e29c8065)
bash coda_lc_miste.sh build-passata-e29c8065
#    bracci: b1 = base (STRATA_PIPED_CONCURRENT=1) | a1 = + PACK_PREFILL=3 PACK_CONCURRENT=1 (finestra server 30 ms)
#            b2 = base di nuovo.  Esiti in lc_m-b1/, lc_m-a1/, lc_m-b2/ (res.json, engine.log, server.log, *.txt)

# 2) verdetto + parità
python pu_verdict.py m-b1 m-a1 m-b2
cmp lc_m-b1/par_A2k.txt lc_m-a1/par_A2k.txt        # e A8k, A30k, A90k

# 3) banco delle letture corte (quello del 19/10, 4 lettori 2-4k + 2 scrittori) sullo stesso exe
bash coda_lc.sh build-passata-e29c8065
python pu_verdict.py b1 a1 b2                       # legge lc_b1/ lc_a1/ lc_b2/

# 4) replay del lavoro reale sullo stesso exe: 4 sessioni (P, A, B, C) e poi 8
bash coda_replay_pu.sh build-passata-e29c8065 1
bash coda_replay_pu.sh build-passata-e29c8065 2
#    esiti in ../20261019_replay/replay_pu-b1-d1/res.json ecc.; riferimento 19/10: 298-302 s, TTFT 20/76 s
```

Bracci extra (dopo il B-A-B, uno alla volta):

```bash
ARMS="a2" bash coda_lc_miste.sh build-passata-e29c8065   # pacco SENZA finestra server (STRATA_PACK_WAIT_MS=0):
                                                         # isola la sola leva del motore da quella di Python
ARMS="a3" bash coda_lc_miste.sh build-passata-e29c8065   # PACK_PREFILL=2 se la VRAM libera va a 0
ARMS="b1 a1 a2 b2" bash coda_lc.sh build-passata-e29c8065 # giro completo con anche il braccio senza finestra
# variante più lunga del banco miste (più campioni, ~2x il tempo):
#   dentro coda_lc_miste.sh, all'arm(): ... letture_miste.py --rounds 4 --burst 2 ...
```

**`STRATA_PACK_CHUNK` NON va acceso in nessun braccio**: l'agente 1 ha trovato (F2 nel suo doc) che nel percorso
concorrente `pk_prepare` presta `min(total, pk_chunk)` una volta sola e il secondo chunk gira senza prestito nuovo.

## Criteri (come li ho scritti nel verdetto)

1. **tempo totale delle 4 letture** — `readers_wall` del burst: guadagno se A è più basso di entrambi i B di un margine
   maggiore della dispersione fra i due B (regola 9 del PIANO_GLOBALE: sotto la dispersione = «inconclusivo»).
   Riferimento indiretto del 19/10: 4 code da ~1,6k in 11,1 s contro 18,8 s una alla volta (−41%).
2. **t/s di decode degli altri durante** — `writers_tps_during_reads` (chunk Client nella finestra) e, lato motore, i
   `rows/s` delle finestre che decodificano mentre la lettura gira sul proprio thread. Guadagno se A non è peggiore dei
   B (e idealmente migliore, perché le 4 letture finiscono prima e liberano le finestre).
3. **token identici** — `new_tokens_read` e i token letti lato motore devono essere **uguali** fra i tre bracci (se
   differiscono il verdetto dice «CORSA NON CONFRONTABILE»); i testi di parità si confrontano byte a byte (il verdetto
   stampa il primo byte diverso). Sul 13/10 la divergenza era a metà testo e c'era anche fra due corse base: non è
   bitwise, va solo riportata.
4. **il pacco deve esserci solo in A** — righe `strata pack:` nel log motore e `[strata] pack: ... sent ahead ...` nel
   log server: se compaiono anche in B i bracci sono sporchi; se non compaiono in A la leva non è mai scattata (F3
   dell'agente 1: può essere anche un drain fallito, non solo «niente da impacchettare»).
5. **ambiente** — `load_other` (scartare la corsa se mean > 15 o p90 > 40), `jumpconnect_cpu_s.connected`, VRAM libera
   nel log motore (3 slot di pacco = ~1,1 GiB sulla 3060, 0,66 GiB ciascuno sulla 2080 Ti).

Tempi **stimati** (non misurati): riscaldamento ~130k token di contesti ≈ 2 min, braccio completo ≈ 8-12 min, B-A-B
completo ≈ 30-40 min; replay 4 sessioni ≈ 5-7 min a braccio, 8 sessioni di più con la VRAM da guardare.

## Note per chi legge i log / per gli altri pezzi

- **Perché il burst serve**: il motore impacchetta solo i `BHINT` **già in coda** quando parte la lettura; con 4 agenti
  che arrivano insieme (o con la finestra di raccolta dell'agente 3) il caso si crea, ed è quello che il 19/10 in
  `pack3-conc` non ha mai impacchettato. Nel banco: 4 invii a 50 ms l'uno dall'altro.
- Una lettura impacchettata **non prende `BYIELD`** («not taken»): la resa dello slot durante un pacco non va cercata
  nei log come un difetto del banco.
- Ho **corretto un regex** che nel mio parser non matchava nulla: la riga del motore è `... reused + 100 read in ...`,
  e `reused + (\d+)` in regex significa «reused seguito da spazi» — serve `reused \+`. **La stessa stringa è in
  `corse_2080ti/20261020_4agenti/misura_4agenti.py` (file di un altro agente, non l'ho toccato)**: quel riassunto
  molto probabilmente non ha mai letto nessuna richiesta. Da correggere lì, non da me.
- Il banco usa la config del Daily 0.1.43 copiata in `lc_<tag>/config.json` (sola lettura, senza `--prompt-cache-file`
  e senza `--vision`) + `--batch 4 --batch-groups 2 --conversation-cache-mib 20480 --conversation-cache-slots 16
  --vram-reserve-mib 1905 --vram-reserve-later-mib 700`, come nel doc della passata unica. Il Daily non è toccato.
- Serve (non è mio): quando i numeri ci sono, writing in `docs/MULTICHAT.md` + `stack/manifest.json` con
  `20261019_passata_unica/stack_add.py` e `--verify-docs` — passo 4 della «ripresa» nel doc PASSATA_UNICA.

## Se una corsa si rompe a metà

`res.json` viene riscritto dopo ogni giro, quindi il giro già finito resta. Per riprendere un solo braccio senza
rifare gli altri: `ARMS="a1" bash coda_lc_miste.sh build-passata-e29c8065`. Se il braccio non parte perché il lock è
occupato: leggere chi tiene `D:\ds4_work\strata\lab_locks\bench.lock` (contiene il nome) e attendere — mai cancellarlo.
