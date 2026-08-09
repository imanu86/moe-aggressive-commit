# 33 — IL ROLLBACK PARZIALE DEL KV: la tesi regge nella meccanica, i numeri vanno corretti, il cantiere è più piccolo del temuto

Data: 10 agosto 2026, notte. Radice `D:\llama-overlap`, ramo `overlap`, HEAD
`0adb16c`. **Niente compilato, niente eseguito** (campagna 4 in corsa: alle
01:23 girava `c4_n2bm3c08`): solo codice letto riga per riga, i log già su
disco in `D:\ds4_work\llama_run\`, e i rapporti in `audit/`. Marcatura:
[MISURATO] = log o codice letto; [DEDOTTO] = aritmetica su misure; [IPOTESI] =
da falsificare, misura indicata. Sono il settimo agente: ogni conversione
dichiara la voce, i ms e la banda.

## L'esito in sei righe

1. **La meccanica dell'audit 32 è vera e verificata**: `seq_rm` rifiuta ogni
   rimozione parziale (false, senza toccare niente), il server usa i
   checkpoint, e ogni accettazione parziale ripristina lo stato e **rigioca un
   forward intero** che non verifica nessuna bozza nuova. Confermato riga per
   riga su cache, common e server.
2. **Il 13,7%/30,9% è DEDOTTO, ma da contatori esatti — e si leggeva già dai
   log**: contrariamente a quanto scrive l'audit 32, il conteggio dei
   ripristini NON richiede di eseguire niente. Ogni episodio non-pieno fa
   esattamente un restore (codice alla mano), e i log stampano
   accepted/generated e `acc per pos`: sulla base attuale i ripristini sono il
   **13,2% degli episodi a n-max 1** (79/599) e il **24,5-32,6% a n-max 2**. I
   numeri specifici 13,7% (517/599) e 30,9% vengono da bracci **FUSO=0** e dal
   banco chat, non dalla base attuale.
3. **La conversione in t/s dell'audit 32 regge nel punto di lavoro**: rifatta
   col modello a episodi completo, la riparazione a n-max 1 vale **13,2-14,3**
   da 12,83-12,89 (audit 32: 13,5-13,9 — compatibile), a n-max 2 vale
   **11,2-11,6** su fu7_n2 (audit 32: 11,1-11,6 — coincide).
4. **Il "tetto 13,79" invece è mal posto, e il "15,2" non è dimostrato**: il
   145 ms del "ciclo" è un ibrido che CONTIENE già la tassa replay, e a p1→1
   quella tassa sparisce da sola. Il tetto vero della base ATTUALE è ~14,4 (non
   13,79: siamo all'89%, non al 93,3%); quello riparato è 14,4-15,3, dove la
   banda è interamente il costo ignoto del checkpoint per ciclo. Il 15,2
   dell'audit 32 risorge solo se quel costo è ~8 ms — ed è esattamente il
   numero che il passo 1 del progetto misura. La Via 5 compra intanto il
   **punto di lavoro** (+0,4/+1,4 t/s a n-max 1).
5. **C'è un costo che l'audit 32 non conta**: il checkpoint viene **salvato a
   ogni episodio con bozza** (599 volte per 1200 token), non solo ai
   ripristini — ed è un D2H da **11,7 MiB** (misurato nei log: 11,693 MiB) in
   ~124 letture-tensore separate, con il gemello H2D a ogni restore. Anche
   questo sparisce con la riparazione.
6. **Il cantiere è più piccolo del temuto**: le cache compresse sono
   auto-riparanti per costruzione (la visibilità deriva dal pos), il cammino
   server "senza difetto" esiste già (è il ramo standard non-checkpoint), e il
   pezzo da versionare è il solo ring di stato dei compressori: **~290
   KB/posizione di delta**, ripristinabile device-side in µs contro i 120-250
   ms del forward rigiocato.

---

## 1. Cosa fa davvero `seq_rm` [MISURATO codice]

`llama-kv-cache-dsv4.cpp:1307-1330`:

```cpp
bool llama_kv_cache_dsv4::seq_rm(llama_seq_id seq_id, llama_pos p0, llama_pos p1) {
    if (p1 >= 0) {
        return false;                      // (a) estremo destro finito: MAI
    }
    if (p0 > 0) {
        // "compressed cache rows are derived from running compressor state,
        //  so arbitrary rollback is not reconstructible from the raw cache alone"
        if (seq_id >= 0 && p0 > kv_raw->seq_pos_max(seq_id)) {
            return true;                   // (b) no-op oltre la fine: true
        }
        return false;                      // (c) coda vera: MAI
    }
    const bool res = kv_raw->seq_rm(seq_id, p0, p1);   // (d) solo rimozione TOTALE
    if (res) clear_compressed(true);
    return res;
}
```

Risposta secca alle domande del mandato: **ritorna false e non cancella
niente** per ogni richiesta parziale; il solo parziale che "riesce" è il no-op
`[oltre-fine, ∞)`. La rimozione totale passa e azzera anche il compresso.

**Chi lo chiama nel cammino speculativo**: nessuno gli chiede mai il parziale,
perché il server lo ha già escluso a monte. La catena:

- `common_context_can_seq_rm` (`common/common.cpp:1481-1521`) è un **probe
  attivo**: decodifica 2 token finti e tenta `seq_rm(0, 1, -1)`. Da noi
  fallisce (caso (c)) → `COMMON_CONTEXT_SEQ_RM_TYPE_FULL`. Nei log è la riga
  `speculative decoding will use checkpoints` — presente in TUTTI i log della
  campagna (riga 423) [MISURATO].
- da lì in poi le sole `seq_rm` sul target nel loop di generazione sono: al
  restore (`server-context.cpp:3872`, `seq_rm(ckpt.pos_max+1, -1)`) e dopo
  l'accettazione (`:3919`, `seq_rm(pos_next, -1)`). **Entrambe passano solo
  grazie al no-op (b)**: `common_context_seq_rm` fa `GGML_ABORT` se il memory
  ritorna false (`common.cpp:1523-1528`) — il no-op alle righe 1315-1318 è ciò
  che tiene in vita il cammino, non un dettaglio.
- la bozza (`common/speculative.cpp:748,1084,1169,1599`) usa
  `llama_memory_seq_rm` diretto sul SUO contesto; il suo stato viene comunque
  ripristinato dal checkpoint a ogni ciclo (`server-context.cpp:2999-3005`,
  `TAG_SPEC_AVOID_DRAFT_REEVAL`).

**Sulla radice comune con `get_can_shift`** (domanda del mandato): la guardia è
diversa ma la radice è la stessa. `get_can_shift` (righe 1296-1300) dice "le
posizioni delle righe compresse derivano dai blocchi"; `seq_rm` dice "lo stato
del compressore è running, non ricostruibile". In entrambi i casi: **lo stato
compresso è una funzione della storia, non una struttura indicizzabile per
posizione**. Lo shift chiederebbe di rinumerare, il rollback di riavvolgere;
context-shift e `--cache-reuse` muoiono della prima manifestazione, la
speculazione paga la seconda.

## 2. Il flusso vero del ciclo, e dove nasce il replay [MISURATO codice]

Per episodio speculativo (n-max 1, bozza da 1):

1. `spec_ckpt.update_pos` + bozza (`server-context.cpp:2955-2978`);
2. ripristino del contesto BOZZA dal checkpoint (`:2999-3005`, ogni ciclo);
3. **salvataggio del checkpoint target** (`:3015-3027`, `update_tgt` con
   `PARTIAL_ONLY`) — a OGNI episodio con bozza, non solo quando servirà;
4. batch `[campionato, bozza]` (`:486-519`), forward, campionamento
   (`:3834`);
5. se accettazione piena: emette 2 token, `seq_rm(pos_next,-1)` è il no-op (b);
6. se rigetto (`n_rollback > 0`, `:3846-3885`): aggiorna le statistiche,
   `spec_draft = accepted`, `spec_replay = true`, **`load_tgt`** (H2D del
   checkpoint), `seq_rm` no-op, sampler ripristinato, **return senza emettere
   nulla**;
7. ciclo successivo: niente bozza (`:2950`: "previous draft to reuse"), batch
   `[campionato_vecchio, accettati]`, il forward **rigioca** le stesse
   posizioni, emette gli accettati + 1 token nuovo.

Tre conseguenze contabili verificate nel codice:

- **ogni episodio produce 2 token comunque** (a n-max 1): l'episodio-rigetto li
  produce in 2 forward invece che in 1. Il replay non "non produce token": ne
  produce 1 nuovo, come un decode liscio — lo spreco è che **non verifica
  nessuna bozza nuova** mentre lo fa.
- `mean_len` stampato = `1 + n_draft_accepted/n_draft_verif_steps`
  (`server-context.cpp:654`), e il replay non conta come verifica (`:3906`).
  È una statistica di ACCETTAZIONE, non "token per forward". Quindi il
  `ciclo = 1000·mean_len/t_s` usato dagli audit è un **ibrido**: né tempo per
  episodio né tempo per forward. Su questo si rompe il "tetto" (§4).
- lo stato PARTIAL (`llama-kv-cache-dsv4.cpp:1405-1427`) = raw KV (finestra
  SWA 128) + i tre stati compressori, **niente cache compresse grandi**. Dal
  log: CSA 1,31 MiB + HCA 10,00 MiB + LID 0,33 MiB = 11,64 MiB **tutti in
  VRAM (CUDA0)**, e il checkpoint stampato pesa **11,693 MiB a n_tokens=1**
  [MISURATO, `c4_gate.server.log`]. Save = D2H da 11,7 MiB in ~124
  `tensor_get` separati; load = l'inverso. Il cronometro c'era ed è commentato
  (`server-context.cpp:3016-3021`).

## 3. La conferma nei log: il conteggio è GIÀ misurabile [MISURATO]

I log della campagna sono a livello INFO: le righe `SLT_DBG` ("restoring/
created speculative checkpoint") non compaiono, e la `SLT_INF` "restore
checkpoint" è dietro `LLAMA_TRACE` (`server-context.cpp:959,1361`), mai attivo.
Fin qui l'audit 32 ha ragione. **Ma il conteggio non serve tracciarlo: è
identico per costruzione agli episodi non-pieni**, che i contatori stampati
danno esatti (non sono contatori a battito: `update_spec_stats` è chiamato una
volta per verifica, senza campionamento):

| braccio | n-max | acc/gen | acc per pos | restore (esatti) | % episodi | % forward | t/s |
|---|---|---|---|---|---:|---:|---:|
| `c2_f5` / `c3_f5b` / `c4_gate` (base F5) | 1 | 520/599 | 0,868 | 79 | **13,2%** | 11,7% | 12,83-12,92 |
| `c2_base`/`c3_base`/`c2_k2go` (F7) | 1 | 509/599 | 0,841 | 90 | 15,0% | 13,1% | 12,65-12,71 |
| `c2_k2fork` (FORK=1) | 1 | 534/599 | 0,891 | 65 | 10,9% | 9,8% | 12,95 |
| `fu0_k2b` (**FUSO=0**) | 1 | **517/599** | 0,850 | 82 | **13,7%** | 12,0% | 10,86 |
| `fu7_n2` | 2 | 683/834 | 0,867 / 0,755 | 102/417 | **24,5%** | 19,7% | 10,01 |
| `c3_n2c0` | 2 | 662/837 | 0,863 / 0,706 | 123/418 | **29,4%** | 22,7% | 8,69 |
| `fu0_n2` (**FUSO=0**) | 2 | 643/846 | 0,832 / 0,688 | 132/423 | 31,2% | 23,8% | 7,63 |
| `c4_n2bm3` (campagna 4) | 2 | 651/837 | 0,865 / 0,674 | 136/418 | 32,6% | 24,6% | 9,43 |

(A n-max 2 con conf=0 gli episodi sono generated/2; restore = episodi ×
(1 − acc_pos[1]). Con conf-min attiva le bozze sono miste e il conteggio non è
più derivabile dai soli aggregati — limite dichiarato.)

**Verdetto sulla domanda del mandato**: il 13,7% e il 30,9% sono **DEDOTTI da
contatori misurati esatti**, con la meccanica "1 episodio non-pieno = 1
restore = 1 forward in più" che il codice conferma. Ma la provenienza è da
correggere: 517/599 è `fu0_k2b` e i controlli sk_20/df_20 del banco chat
(SINKHORN.md) — bracci FUSO=0 — e 30,9% non corrisponde a nessun braccio della
base attuale (la banda misurata a n-max 2 è 24,5-32,6%). I numeri giusti per
la base attuale sono **13,2%** e **24,5-29,4%**. La parte davvero non
misurata è il **costo unitario** (ms del save/load e del forward rigiocato):
quello sì, solo eseguendo (§7).

## 4. Il conto rifatto: cosa vale la riparazione [DEDOTTO su MISURATO]

Modello a episodi, dichiarato per esteso. Per 1200 token: E episodi, R
restore; tempo eval T. Ogni episodio paga bozza + save; ogni restore paga
load + un forward in più:

```
T/E = T_bozza + C_save + (1 + R/E)·T_fwd + (R/E)·C_load
riparato:  T'/E = T_bozza + T_fwd        token/episodio: da 2,004 a 1+p1
t/s' = 1000·(1+p1)/(T_bozza + T_fwd)
```

Su `c2_f5` (T=93.557 ms, E=599, R=79, T_bozza=8,43, p1=0,868 → T/E=156,2):

| ipotesi C_save / C_load | T_fwd fittato | t/s riparato | Δ da 12,83 |
|---|---:|---:|---:|
| 0 / 0 ms (limite prudente) | 130,5 | 13,45 | +4,8% |
| 4 / 4 ms | 126,5 | 13,85 | +8,0% |
| 8 / 8 ms | 122,7 | 14,25 | +11,1% |

Su `fu7_n2` (n-max 2: T/E=287,4, restore 24,5%, T_bozza=11,87): riparato
**11,2-11,6** (C=0→8). Su `c3_n2c0`: **10,0-10,3**. Le cifre dell'audit 32
(13,5-13,9 e 11,1-11,6) escono CONFERMATE dal rifacimento — con la coda bassa
un filo più prudente a n-max 1.

**Le due incertezze che allargano la banda, dichiarate**:

- **C_save/C_load ignoti** (0-10 ms è la mia forcella per 11,7 MiB × 124
  trasferimenti con latenza per-chiamata; il cronometro commentato esiste
  apposta). È la voce che decide se il premio è +5% o +11%.
- **p1 post-rigetto** [IPOTESI]: nel mondo attuale il replay "salta" gratis il
  punto difficile (il token dopo un rigetto nasce senza bozza); nel mondo
  riparato si ribozza SUBITO sul punto difficile. Se lì p1' < p1, il guadagno
  cala: con p1'≈0,6 sui cicli post-rigetto (13% dei casi), il 13,45 scende a
  ~13,2. **Banda finale n-max 1: 13,2-14,3, centro 13,6.** In formula: la
  riparazione tocca `ms_ciclo` (−17/−33 ms per episodio) e lascia `mean_len`
  invariato a meno del termine p1' (−0/−0,04).
- Sul fattore storico 0,08-0,43: qui non si applica ai forward (un
  `llama_decode` è seriale per costruzione, α≈1 — confermo l'audit 32), ma ho
  tenuto la calibrazione nel verso giusto mettendo a zero i costi checkpoint
  nel limite basso e scontando p1'.

**La correzione al tetto** (il punto dove l'audit 32 va raddrizzato): "tetto
2000/145 = 13,79" usa il ciclo ibrido, che contiene la tassa
restore+replay+checkpoint spalmata sui cicli buoni. A p1→1 quella tassa
**sparisce da sola** (zero rigetti, zero restore). Il tetto della base
ATTUALE è `2000/(T_fwd+T_bozza+C_save)` = **14,4** su ogni ipotesi di fit (a
p1→1 resta solo il costo osservato meno la parte restore, e il fit conserva la
somma). Il tetto RIPARATO toglie anche C_save: `2000/(T_fwd+T_bozza)` =
**14,4 / 14,8 / 15,3** per C_save = 0 / 4 / 8 ms. Quindi: il "13,79 come
tetto" era comunque sbagliato (siamo all'**89%**, non al 93,3%, e la distanza
dal tetto È la tassa dei cicli non pieni); il "15,2" non è dimostrato ma
nemmeno escluso — vive o muore col C_save che il cronometro commentato
misurerebbe in una corsa. Riparare il rollback incassa la tassa senza
aspettare una bozza perfetta, e SE il checkpoint è caro alza anche il tetto.

## 5. Cosa impedisce oggi il rollback parziale: formato, scelta, o guardia? [MISURATO codice]

Tutte e tre, ma su componenti DIVERSE — ed è la notizia buona:

- **Cache compresse (CSA/HCA/LID e ring hot): nessun impedimento reale.** La
  visibilità è derivata dal pos a ogni piano (`n_visible = (pos+1)/ratio`,
  `llama-kv-cache-dsv4.cpp:530`) e il commit al confine di blocco riscrive la
  riga `pos/ratio` (`:557`). Dopo un rollback della coda, le righe committate
  dal forward annullato restano scritte ma **invisibili**, e verranno
  sovrascritte al ricommit quando le posizioni vere arriveranno.
  Auto-riparanti per costruzione: zero lavoro.
- **Ring di stato dei compressori: è QUI il formato.** Ogni posizione
  sovrascrive la riga `pos % state_size` di kv+score (CSA/LID: 8 righe; HCA:
  128) — `:518,537`. Un forward da B posizioni distrugge B righe che
  contenevano `pos−state_size`. Il rollback della coda è ricostruibile SOLO se
  quelle righe vengono fotografate prima. Il commit con overlap legge fino a
  `2·ratio` righe indietro (`:560-568`), quindi il ring è dimensionato giusto e
  non c'è margine gratuito: serve il delta.
- **Raw SWA: probabilmente solo guardia, con una condizione.** Le celle della
  coda esistono e la unified sa rimuoverle; la condizione di correttezza è che
  il forward annullato non abbia già riusato celle appena sotto la finestra
  (margine di pruning ≥ n-max+1 celle). Il costruttore riceve `swa_full`
  (`:1021,1054`) che risolverebbe in modo brutale. **Punto da verificare
  leggendo il pruning della iswa prima di scrivere** — è l'unico rischio di
  correttezza aperto del progetto.
- **La delta-riparazione è anche l'unica CORRETTA**: ripristinare l'intero
  stato pre-forward (come fa oggi il checkpoint) butta anche le righe delle
  posizioni ACCETTATE, che invece sono giuste e devono restare — è per questo
  che oggi si rigioca. Il ripristino selettivo delle sole righe delle
  posizioni scartate rimette il ring ESATTAMENTE nello stato "quelle posizioni
  non sono mai successe", con le righe accettate già avanti. Delta per
  posizione: CSA 21×2×1024×4B = 168 KB, HCA 20×2×512×4B = 80 KB, LID
  21×2×256×4B = 42 KB → **~290 KB/posizione**, contro gli 11,7 MiB del
  checkpoint intero (40× meno), e device-side (µs, niente PCIe).

**Sui checkpoint esistenti "da usare a grana più fine"** (ipotesi del
mandato): no. I 32 checkpoint di contesto servono il riuso del prompt e sono
ortogonali; il checkpoint speculativo è già alla grana minima possibile PER
QUEL MECCANISMO (uno per episodio). Il replay non nasce dalla grana ma dal
fatto che il restore riavvolge tutto perché non sa riavvolgere solo la coda.
La grana più fine giusta non è "più checkpoint": è il delta del ring.

**Perché NON dichiarare PART globalmente**: il probe piloterebbe anche il
riuso del prompt (`server-context.cpp:3385`: `seq_rm(p0,-1)` con p0 profondo
arbitrario) — oltre il margine di coda il nostro seq_rm direbbe false e
`common_context_seq_rm` **abortirebbe il server**. La riparazione deve stare
sul solo ramo speculativo, lasciando il probe a FULL e i checkpoint come rete.

## 6. Il progetto, dal pezzo più piccolo

**Passo 0 — già fatto qui, gratis**: il conteggio esatto dei restore dai log
(§3). Decide che il canale esiste: 79-90 forward su ~678 a n-max 1 sono
replay.

**Passo 1 — la misura che manca (2 righe, zero rischio, alla prossima
finestra di ricompilazione)**: scommentare il cronometro di
`update_tgt` (`server-context.cpp:3016-3021`) e gemellarlo su `load_tgt` nel
ramo restore. Un numero per corsa: C_save e C_load. Decide la banda del
premio (13,2-13,4 contro 13,8-14,3) e ricalibra la soglia dell'audit 32: la
tassa per episodio è `C_save + 0,132·(T_fwd + C_load)` ≥ 16-17 ms **già a
C=0** — la soglia "< 8 ms/ciclo → non merita il cantiere" è quasi certamente
superata in partenza, salvo sorprese sul T_fwd del replay (più corto del
forward pieno? non c'è ragione strutturale: stessa forma di batch).

**Passo 2 — la patch minima che muove un numero**:

1. shadow del ring in `llama_kv_cache_dsv4_context::apply()` (gira PRIMA del
   grafo, il piano conosce già le righe destinande:
   `state_persist_dst_idxs`): copia DtoD delle B righe per i 3 compressori in
   un buffer shadow preallocato (~1 MiB VRAM). Costo stimato 0,1-1 ms per
   forward — da gate-are (attivo solo a batch ≤ n-max+2, o via env
   `LLAMA_DSV4_KV_TAIL_RM=1`);
2. estensione di `seq_rm`: accettare `[p0, -1)` quando
   `seq_pos_max − p0 + 1 ≤ B_ultimo_forward`: ripristino DtoD selettivo delle
   righe delle posizioni ≥ p0, `seq_rm` parziale sul raw, niente per le
   compresse;
3. server, ramo `n_rollback > 0` (`:3846`): tentare prima la via parziale; se
   riesce, **cadere nel ramo standard già esistente** (`:3888-3947`:
   `common_speculative_accept` + emissione immediata + `seq_rm(pos_next,-1)`)
   che è il mondo-senza-difetto già scritto da upstream; altrimenti restore
   come oggi. Il checkpoint resta come fallback (e per la bozza).

Ordine di grandezza del cantiere: ~150-250 righe totali, nessun cambio al
grafo, nessun formato su disco toccato (il PARTIAL resta com'è).

**Il cancello che falsifica, per passo**:

- Passo 1: se `C_save + 0,132·(T_fwd+C_load)` misurato < 8 ms/episodio la via
  si ridimensiona sotto le vie gratis (non lo credo possibile: il solo termine
  replay è ≥ 15 ms — ma il numero va guardato, non creduto);
- Passo 2, correttezza: (i) spec OFF e K=0 bit-esatto con la base (lo SHA di
  riferimento del cancello RAM, unico regime in cui lo SHA vale — regola di
  casa); (ii) a leva accesa, `acc per pos` stabile rispetto alla base
  (0,84-0,87 a n-max 1): se p1 crolla, il ripristino selettivo del ring è
  sbagliato e la via si chiude finché il raw/margine SWA non è capito; (iii)
  nessuna degenerazione del testo (la firma 41/11 righe uniche);
- Passo 2, resa: se il braccio A/B non porta il t/s a ≥ 13,2 a n-max 1
  (metà bassa della banda), il modello di costo di questo audit è
  falsificato e va cercato il termine mancante (candidato primo: il p1'
  post-rigetto, leggibile dal confronto `acc per pos` fra i due bracci);
- falsificatore architetturale: se il margine di pruning della SWA non esiste
  e servisse `swa_full`, il costo memoria/velocità di quel ramo va rimisurato
  prima di proseguire — è l'unico punto in cui "snapshot ≥ costo del replay"
  potrebbe ancora avverarsi (sul raw, non sui compressori).

## 7. Dati che si ottengono solo eseguendo (in ordine di valore)

1. **C_save / C_load** (cronometro commentato + gemello sul load): decide la
   banda 13,2-14,3 e chiude la voce più grossa di incertezza. Costo: 2 righe e
   una corsa qualunque — accodare alla prossima ricompilazione, NON durante la
   campagna 4.
2. **T_fwd del replay vs T_fwd d'episodio** (con `LLAMA_TRACE=1` una corsa
   corta: le righe "accepted (restore checkpoint)" hanno timestamp): verifica
   che il replay costi quanto un forward pieno (assunzione α≈1 di questo
   audit e del 32).
3. **Margine di pruning della SWA raw** (test mirato o lettura di
   `llama-kv-cache-iswa`/unified con una sonda): condizione di correttezza del
   passo 2 sul raw.
4. **p1 condizionato post-rigetto** (analisi offline di una corsa con
   TRACE: la distribuzione di `accepted` nel ciclo successivo a un restore):
   stringe la coda bassa della banda (13,2 vs 13,45).
5. **Il braccio A/B post-patch** (base F5, n-max 1, poi fu7_n2): il verdetto.
   Contatori da leggere: t/s, `acc per pos` A PARITÀ (spia del ripristino
   sbagliato), episodi/forward dal conteggio di questo audit.
