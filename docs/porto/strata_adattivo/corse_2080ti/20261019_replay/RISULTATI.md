# Standard di confronto onesto del multi-chat Strata - 19 ottobre 2026

Solo conteggi e tempi (nessun contenuto). Compilato no, installato no. Build `build-upsmain-d06429ee` (0.1.45 + pila),
provata con il replay sul PC dell'owner. M = misurato, S = stimato.

## A. Come calcolano gli altri i loro numeri

Fonti: PR #2058, #1179, #1547, #559 e `docs/BATCHING.md` di `Niko1221/Strata`; script in `bench/results/*` e `tools/batch_test.py`.
L'harness di blange48 (quello del «1 / 4 / 8 clients, 300 tokens (2nd pass)») **non e' pubblicato**: i parametri vengono dalle sue PR.

| punto | cosa dicono le fonti |
|---|---|
| rig | 4x RTX 5080 16 GB, PCIe Gen3, `--layer-split 12,24,36 --trim-stage-weights --batch 8 --batch-groups 4`, IQ3_S, 262K |
| passaggio | server HTTP, N client in parallelo, T=0,7 (a volte 0), 300 token a risposta, 3 richieste per client (#1179), «due passate», la seconda misurata |
| solo decode? | di fatto si': 2nd pass = stesso prompt gia' letto (cache di prompt e conversazioni), prefill ~0. La lunghezza dei prompt di quella riga non e' dichiarata (le righe a 1 client citano 3,9K e 31K a parte) - dedotto, non verificato |
| aggregato | token generati da tutti i client / tempo della passata (= somma dei tok/s per client quando gli stream si sovrappongono del tutto); #559: 8 client a 45 tok/s ciascuno = 360 |
| slot | con `--batch` gli slot decodificano **senza MTP** (1 token a finestra); il client singolo usa il percorso solo con MTP |
| altri harness | `conc_bench.py` (4090): N richieste con etichetta casuale (prefisso mai riusato), 8000 token, 256 token, 2 passate; `BATCHING.md`: saggio da 800 parole, 256 token, mediana di 3 giri; `tools/batch_test.py`: motore diretto, greedy, prompt brevi |

**Confrontabile con `mc2.py`? No, non direttamente.** Il suo `diff:N:S` ci somiglia (N chat insieme, contesti S da ~8K token gia'
in cache dopo il warm, temperatura 0, 384 token, aggregato = token / wall, piu' il «decode» a parte), ma cambiano: hardware
(4 schede Blackwell in pipeline contro 3060 + 2080 Ti senza P2P), temperatura 0,7 contro 0, numero di slot (8 contro 4),
lunghezza e provenienza dei prompt, e il loro non misura mai la lettura. Mai mettere le due colonne nella stessa tabella senza dirlo.

**Cosa daremmo noi sulla stessa misura** (contesti ~8K in cache, 300-384 token, Daily + `--batch 4 --batch-groups 2`):

| client | blange48 (4x5080) | noi (M dove indicato) |
|---|---|---|
| 1 | 144 | 56-64 (M, `solo:S`) |
| 4 | 268 | **75-86** (M: `diff:4:S` 74,8 b-g2cc del 18/10; 84,7-85,9 in `PIANO_MULTICHAT_180.md`); senza batch (Daily) 33 (M) |
| 8 | 392 | ~75-86 con `--batch 4` (otto client in due ondate, S); con 8 slot mai provato: ~90-110 (S, +7,4 ms per riga) |

Rapporto a 4 client: loro 3,6x noi. Per i numeri futuri: stessa tabella con **tre colonne** (decode con prompt in cache, lettura
a freddo, lavoro reale a replay) e sempre rig, slot, T, token e prompt dichiarati.

## B. Il lavoro reale: i 3 agenti DSH del 16/10

Sessione DSH «handoff sul lavoro del sito delle promo» (orchestratore `session-1c512c...` + 3 sotto-agenti A=`41c81312`,
B=`7ad02764`, C=`67383909`), tutte su `strata-local` (Qwen3.8 sul Daily 0.1.43, senza `--batch`, cache conversazioni 2 slot / 6144 MiB).
Tempi lato client dalle sessioni DSH (`session.v4.jsonl.zstd`), tempi lato server dal log del Daily: 198 richieste su 198
abbinate a una riga del log per (token di prompt, token generati); il server e' seriale, quindi l'ordine delle righe e' l'ordine di servizio.
`trace_dsh_20261016.json` ha invio, primo token, fine, prompt, riusati, nuovi, generati, pensiero, lettura e decode del server.

| misura | valore |
|---|---|
| durata (fase a 3 agenti, 05:48-09:55) | **14 812 s = 4 h 07 min** (la sessione e' partita alle 05:39) |
| richieste | 198 (orchestratore 45, A 48, B 45, C 60); 10 timeout di 600 s dello stream DSH con ripetizione |
| token | prompt 22,6 M, riusati 10,4 M (46%), **riletti 12,2 M**, generati 167 k |
| server occupato | 14 066 s = **95%** del tempo: lettura 11 046 s (**78,5%**), decode 3 019 s; lettura ~1 100 tok/s, decode ~56 tok/s |
| alternanza | 187 passaggi di sessione su 197 richieste servite di fila; solo 10 richieste hanno seguito la propria; 2 slot di cache per 4 conversazioni da 100-160K |
| coda | TTFT p50/p90/max **182 / 486 / 1 483 s**; attesa (TTFT meno lettura) media 195 s, somma 38 567 s |
| concorrenza | richieste in volo: 4 per il 71,9% del tempo, 3 per il 17,1%, 2 per il 5,7%, 1 per il 5,0% |
| pensiero fra turni | mediana 1,8 s: gli agenti non aspettano niente se non il server |

Gli agenti si **alternavano**: ogni turno dopo quello di un'altra sessione rileggeva da zero 100-140 K token (riuso 8-9K = il solo
prefisso fisso) in 100-140 s, mentre le richieste riusate costavano 1-20 s. Da solo (C dopo 233 min) lo stesso agente ha TTFT 1-3 s.

### Replay (`replay_trace.py`) - finestra 3600-4800 s, 24 richieste, 4 sessioni, build `d06429ee`

Prima del cronometro si rileggono le conversazioni gia' in corso (nell'ordine originale). Testo sintetico (fixture), lunghezza
regolata sul conteggio del server; il riuso lo decide il server. Carico CPU altrui 6-7% in tutte le corse valide (OktoCGControl ~3,3%).

| | tempo per finire | TTFT p50 / p90 | riuso | riletti | note |
|---|---:|---:|---:|---:|---|
| originale (Daily 0.1.43) | **1 583 s** (26,4 min) | 216 / 428 s | 34% | 1,79 M | M, dalla traccia |
| config 1: Daily senza `--batch` | **937 s** e 1 069 s | 135 / 334 e 171 / 275 s | 55% e 46% | 1,21 M e 1,45 M | 2 corse |
| config 2: `--batch 4 --batch-groups 2`, cache 28 GiB / 16 slot, `STRATA_PIPED_CONCURRENT=1` | **298 s** e 302 s | 20 / 76 e 17 / 72 s | 93% | 0,19 M | 2 corse |

**Quel lavoro (la finestra) aveva impiegato 1 583 s; il replay lo finisce in ~1 000 s (937-1 069) con la config 1 e in ~300 s con la config 2.**
A parita' di build e di harness la config 2 e' **3,1-3,5x** piu' veloce della 1 (TTFT p50 7-10x piu' basso). Estrapolazione al lavoro
intero (S, vale se le altre fasi somigliano a questa): config 2 ~47 min contro 4 h 07; config 1 ~2,4-2,8 h.

Limiti onesti: (1) la config 1 e' piu' veloce dell'originale anche se la config e' la stessa perche' la build e' piu' recente
(lettura 1 400-1 440 tok/s contro 1 190) e perche' l'ordine di servizio cambia il riuso della cache (46-55% contro 34%): il
confronto che vale per la leva di config e' 1 contro 2; (2) i token generati sono 3,75-4,35 k contro 6,85 k (il server non ha
`min_tokens`; il decode pesa il 7% del servito originale); (3) i turni gia' in coda a t=0 ripartono da zero e quelli dopo seguono
il replay (anello chiuso), non gli istanti originali; (4) 2 corse per braccio, la variabilita' della config 1 (±7%) e' quella
delle gare sulla cache a 2 slot; (5) la corsa 0 della config 1 (`c1-daily.run0_disturbata.log`) e' scartata: il campionatore
contava il processo idle come carico altrui (corretto).

File: `build_trace.py` (DSH + log -> traccia), `dshread.py`, `replay_trace.py`, `coda_replay.sh`, `trace_dsh_20261016.json`,
`*.run.log`, `replay_*/res.json` e `config.json`. Rilancio: `python ..\20261006_due_schede\bench_lock.py REPLAY-x -- python -u replay_trace.py --tag x --t0 3600 --span 1200 [--extra "..." --env "..."]`.

## C. Le cinque domande dell'owner (stato 19/10, laboratorio in pausa)

**Da rifare dopo la pausa (GPU): punti 1 e 4.** Corse scartate o interrotte, tenute in `run_scartate/` e `run_interrotte/`:
- 8 agenti con `--batch 4` e riserva di VRAM del Daily (1393 MiB): a meta' corsa la 3060 aveva 0 MiB liberi (Windows sposta la memoria
  grafica nella RAM), il motore e' rimasto fermo 240 s e il server l'ha riavviato: corsa non valida (il suo 1 603 s non vale). Con
  `--batch 8 --batch-groups 2` la 2080 Ti restava con 154 MiB liberi e la lettura iniziale era gia' piu' lenta (234 s per 135K contro 95 s);
  interrotta dalla pausa.
- Chat singola con `STRATA_BATCH_PIPELINE=1` sulla build `multichat45` con riserva 1393 MiB: 0 MiB liberi, lettura di 8K in 980 s;
  uccisa. Il 50,5 t/s «di stanotte» puo' avere la stessa causa (avvio a 436 s, contaminata): da verificare con la riserva piu' larga.
- Misura valida finora: Daily su `multichat45`, chat singola, `solo:S`: 65,5 e 59,6 t/s (decode medio).
- Pronto da lanciare: `coda_domande3.sh` (riserva 1905/700 MiB per 4 slot, 3400/1100 per 8, cache conversazioni 20 GiB, poi nucleo RAM 6 900).

**2. Tetto di contesto per agente.** Esiste solo `--max-context` globale, uguale per ogni slot (le sessioni sono scavate con le stesse celle).
Una richiesta con prompt + `max_tokens` oltre il limite riceve **400** («request exceeds the context window ... never truncated»,
`serve/server.py` ~r.4053-4078); `fit_max_tokens` accorcia solo l'output. Niente troncamento. Per un tetto per richiesta bastano 6 righe
nel server: `patch_tetto_prompt_per_richiesta.diff` (`STRATA_MAX_PROMPT_TOKENS`, stesso 400; non applicata, non provata). Il posto giusto per
far *compattare* invece di fallire e' la finestra di contesto che DSH dichiara per il modello (nelle sessioni e' 262144; DSH compatta
da solo quando la raggiunge): abbassarla a 100K li' fa compattare l'agente prima; il server resta la rete di sicurezza.

**3. Prefisso comune.** Oggi **duplicato**, non condiviso: ogni conversazione parcheggiata e' un'immagine intera (K/V + stato) e ogni slot
ha la sua sessione. Misurato sui log (28 parcheggi): **18,1 KB per token + 295 MB fissi** per immagine; un prefisso di 40K token pesa
**0,69 GiB per copia** (1,0 GiB con la parte fissa); sessioni degli slot: 0,36 GiB sulla 3060 + 0,66 GiB sulla 2080 Ti ciascuna,
allocate per intero. Il prestito di prefisso (#1164) copia da una conversazione parcheggiata invece di rubarla, ma con lo split «le
fasi ripristinano solo immagini intere», quindi qui non agisce. Servirebbe: ripristino del solo prefisso per ogni scheda, donatore bloccato
su tutte le schede, e per la VRAM degli slot un blocco di K/V di prefisso in sola lettura referenziato dalle sessioni (copia alla scrittura):
lavoro di settimane (stima). Risparmio: RAM ~0,69 GiB per agente oltre il primo (8 agenti: ~4,9 GiB su ~24); VRAM ~0 (le sessioni sono a
dimensione fissa); ammissione: lettura una tantum del prefisso ~29 s a 1 400 tok/s (gia' coperta dal file di prefisso del Daily), poi
parcheggio mediano 0,22 s: il guadagno per turno e' sotto il mezzo secondo.

**5. Memoria (Daily, build 0.1.43 e 0.1.45).** Il Daily ha working set 33,5-46,3 GiB (mediana 39) e privata 65,6-77,2 GiB (mediana 73,5)
su 1 185 richieste; il PC a ~69 GB usati = Strata ~35-40 + ~30 GiB di altri programmi (misurato 33 GiB di altri). Dopo il nucleo RAM:
arena esperti **29,7-30 GiB** (era 39,97), 5 500 esperti della 2080 Ti (9,56 GiB) e 352-636 della 3060 (0,5-0,8 GiB) senza copia in RAM; il
resto del working set (~4-6 GiB all'avvio, fino a +6 con la cache conversazioni del Daily) e' K/V fissato 1,03 GiB, cache conversazioni,
cache di prefisso, embedding 0,26 GiB. PLE: **non in RAM** (lettura diretta dal file, 26 K righe/s; cache di righe 16 MiB; il file sta
nella cache del sistema e non nel working set). Pesi densi in VRAM. Si puo' liberare di piu': `STRATA_RAM_CORE_SLOTS_DEV1` fino a ~6 900
(+2,5 GiB, meno slot che ruotano per l'adattamento: costo da misurare, in coda), registrazione dell'arena sulla 3060 (7,4 GiB fissati nel prefisso
registrato, `STRATA_ARENA_PIN_GIB`: cambia la banda PCIe dei prompt); l'arena in mmap (`STRATA_ARENA_MMAP`) esiste **solo su Linux**.
Cache conversazioni senza swap: con 4 slot e 27,5 GiB di cache (10 parcheggi) il sistema e' sceso a **2,9 GiB disponibili** (working
set 72,5 GiB, impegnata 109 GiB su 95,9 + file di paging 75 GiB, swap usato 0,5 GiB; corsa poi scartata per il riavvio, ma la memoria e'
reale) - troppo stretto; la quota sicura, lasciando ~8 GiB liberi con gli altri programmi al livello attuale, e' **~16-20 GiB
(8-10 conversazioni da 100K)**. Dato da una sola corsa, da riconfermare.
