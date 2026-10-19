# Bisezione del calo 0.1.45 (senza batch) contro Daily 0.1.43 r2 (19/10/2026) - INTERROTTA dall'owner

Stato: **causa del decode NON trovata**; interrotta alle 19:40 (token finiti). Esclusi: tre differenze di config (PIPED_CONCURRENT,
P2_FLUSH_NOSWITCH, cache conversazioni) e la riserva VRAM. Prompt: la differenza e' l'assenza di hc16 nella build (gia' nota, non
rimisurata qui). Compilato no, installato no. Jump scollegato (CPU di JumpConnect sessione 1 ferma a 194 s in tutte le corse, `ambiente.txt`);
OktoCGControl aperto; GPU0 al 12-44% per processi estranei (schermo), uguale in tutti i bracci.

Metodo: `bisezione/bab.py <tag> <braccio> [--targets ..] [--runs ..]` (copia del runner, stesso benchmark.py, porta 8105, bench.lock),
`bisezione/seq.py` alterna i bracci, `bisezione/analizza.py` stampa le mediane. 4K e 32K, 3 corse ciascuno (a 32K la
serie c: 4 corse). STRATA_PROMPT_ENCODER=1 messo nell'ambiente del server di tutti i bracci (la bat della 0.1.43 lo imposta fuori dal json;
nel json non c'e'; nella 0.1.45 e' incondizionato). Nessuna corsa scartata per disturbo, ma l'attesa sul lock (altri agenti) ha spezzato gli intervalli.

## Risultati (mediane prompt tok/s / decode tok/s; fra parentesi n, ms per finestra, drafts accettati)

| braccio | corse | 4K | 32K |
|---|---|---|---|
| B = Daily 0.1.43 r2 (`build-0143-daily`) | a01 a03 a05 a07 a09 b01 b03 c01 | 692 / 74,2 (n21, 32,6 ms, 66%) | 1436 / 73,0 (n25, 30,7 ms, 64%) |
| N = 0.1.45 nobatch (`strata-0145-nobatch.json`) | a02 a06 | 665 / 68,0 (n6, 34,8 ms, 63%) | 1293 / 64,1 (n6, 32,7 ms, 60%) |
| C = N con `STRATA_PIPED_CONCURRENT=0`, senza `STRATA_P2_FLUSH_NOSWITCH`, cache conv. 6144 MiB / 2 slot come la 0.1.43 | a04 a08 | 669 / 68,2 (n6, 35,5 ms, 63%) | 1292 / 65,6 (n6, 32,7 ms, 61%) |
| R = N con `--vram-reserve-mib 1905 --vram-reserve-later-mib 700` | b02 | 654 / 57,9 (n3, 39,3 ms) | 1287 / 63,2 (n3, 32,5 ms) |

Ordine delle corse (B-A-B): a01-B a02-N a03-B a04-C a05-B a06-N a07-B a08-C a09-B; b01-B b02-R b03-B; c01-B (poi fermata). Quattro coppie B-N/B-C
complete, una B-R.

## Conclusioni

1. **Il calo c'e' anche in alternanza B-A-B**: decode -8% a 4K, -12% a 32K; prompt -4% a 4K, -10% a 32K. Non e' rumore di sessione (B ripetuta 8 volte,
   74,2 / 73,0 con scarto di 1-2 t/s fra le mediane delle corse).
2. **Decode**: drafts accettati uguali (60-66% in tutti i bracci) e finestre per richiesta uguali (105-115): la perdita e' nel **costo per finestra**,
   +2,2 ms a 4K (34,8 contro 32,6) e +2,0 ms a 32K (32,7 contro 30,7), cioe' +7%. Non e' la politica di draft.
3. **Esclusi** (braccio C, tre differenze di config insieme, nessuna variazione: 68,2/65,6 contro 68,0/64,1) `STRATA_PIPED_CONCURRENT`,
   `STRATA_P2_FLUSH_NOSWITCH` e la cache conversazioni 18432/16 contro 6144/2. Esclusa la riserva VRAM (R: nessun guadagno; il warning
   "only 543-820 MiB free at request start" di N compare anche con R a 702 MiB, perche' la cache elastica riempie fino alla riserva).
4. **Env della 0.1.43 non rimettibili**: nel sorgente `lab/multichat45` (e in `upsync-main`) `STRATA_NODECUT`, `STRATA_TOPK_GRID`, `STRATA_B6_HEAD_MINB`
   **non esistono**: sono leve di `lab/struct-a` (`verify.cpp` `nodecut_env`: FUSE_WAIT e FUSE_HITS; `qsa_select.cu` TOPK_GRID; `native_mmvq.cu` HEAD_MINB),
   non portate perche' "neutre sul banco forzato" (stack/INDEX.md, UPSYNC_MAIN.md par. 2). Il json della 0.1.45 non le ha e la build le ignorerebbe.
   `STRATA_QFUSE_HC` esiste ma su CUDA non e' acceso di default (=0 equivale a non impostarlo). Il banco forzato (finestre replay) puo' non vederle
   mentre il flusso naturale si': **e' il sospettato principale** (ma non provato).
5. **Differenza di json residua** (diff completo): solo `--conversation-cache-mib/-slots`, il file prefisso e le tre env di sopra; piu' le due env nuove della
   0.1.45. Nessun'altra opzione e' diversa (stessi `--pipeline-windows 2`, `--spec 4`, `--kv-resident`, `--vram-reserve-*`, `--host-core last`).
6. **Prompt**: nella 0.1.45 manca hc16 (il registro `stack/` lo segna "not ported"; nel Daily toglieva il 19,5% del tempo GPU del prompt). Il divario cresce con
   il contesto (-4% / -10% / -12% a 4K / 32K / 128K), coerente con una voce che scala col numero di token. Le misure dell'agente BF16 (coordinatore):
   `STRATA_HC16_SM75=1` -11,6% e `STRATA_BF16_TC=1` -12,5% sul tempo del prompt 131K. Qualita' del testo (parole distinte/totali) non controllata qui.
7. **Segnalazioni dai log**: nella 0.1.45 la 2080 Ti parte con 252 MiB liberi ("LOW", #2192) e a inizio richiesta la 3060 ne ha 543-820 (warning #2065); nella 0.1.43 nessun
   warning. L'impronta VRAM finale e' pero' uguale (nvidia-smi a fine corsa: 21878 contro 21890 MiB sulla 2080 Ti), quindi non e' la causa.
   Un altro agente ha provato `STRATA_MTP_STAGE0=1` (mtpst0-0145-a): non migliora (65,9 / 63,0 / 65,7).

## Config consigliata (provvisoria)

Per il prompt: build `build-upsmain-d9a26384` (0.1.45 + hc16 opt-in) con `STRATA_HC16_SM75=1` e, da misurare insieme, `STRATA_BF16_TC=1`.
Per il decode: nessuna correzione trovata; **portare in 0.1.45 i tre nodi di struct-a** (NODECUT = FUSE_WAIT + FUSE_HITS, TOPK_GRID, B6_HEAD_MINB) solo se il
braccio Bx qui sotto dimostra che la 0.1.43 senza di loro scende al livello di N.

## Bracci rimasti (comandi pronti; lanciare dalla cartella `bisezione`, un braccio alla volta, bench.lock automatico)

```
PY=D:\ds4_work\strata\Strata\.venv\Scripts\python.exe
# 3. 0.1.43 senza le leve struct-a (NODECUT, TOPK_GRID, B6_HEAD_MINB, QFUSE_HC): se il decode scende a ~65-68, e' la causa
$PY -u seq.py d B,Bx,B,Bx,B --targets 32768 --runs 4
# NAN_GUARD (#1892) spento sulla 0.1.45
$PY -u seq.py e B,G,B,G,B --targets 32768 --runs 4
# 5. prompt: build con hc16 (H0 = stessa build senza hc16, H = con STRATA_HC16_SM75=1); controllare anche il testo (parole distinte/totali ~0,55)
$PY -u seq.py f B,H0,B,H,B,H0,B,H --targets 4096,32768
# finale richiesto dal coordinatore: build d9a26384 + STRATA_HC16_SM75=1 + STRATA_BF16_TC=1 (+ correzione del decode) contro la 0.1.43, tutti i punti
#   aggiungere in bab.py un braccio 'F' (env STRATA_HC16_SM75=1, STRATA_BF16_TC=1 su bld = HCB) e lanciare:  $PY -u seq.py g B,F,B,F,B   (4K/32K/128K, senza --targets)
# 6. se il decode resta sotto: confrontare nei log "drafts accepted" e i tempi per stadio con STRATA_DECODE_TIMING=1 STRATA_P2_SWITCH_STAT=1 (env del json), sospetti
#    upstream 0.1.43 -> 0.1.45: ngram.cpp #2622 (gather_batch) e std::recursive_mutex su PleTable (a2de7446), cambi di verify.cpp/generate.cpp.
```

I bracci `Bx`, `G`, `H`, `H0`, `HC` sono gia' definiti in `bisezione/bab.py`; `F` no.
Grezzi (`*-raw.json`, `*-request.json`) non committati; restano su disco in `bisezione/<tag>-<braccio>/`.
