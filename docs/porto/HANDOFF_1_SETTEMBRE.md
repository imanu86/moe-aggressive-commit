# HANDOFF — 1 settembre 2026, sera
## DS4 · il default è cambiato: `DeepSeek-V4-Flash-Vision-Exp`

> **Documento per una IA che riprende il progetto da zero.** Contiene stato, numeri, percorsi,
> protocollo, trappole e coda. Tutto ciò che è scritto qui è **misurato** o **letto nel
> sorgente**; le ipotesi sono marcate come tali. Cronaca completa: `docs/porto/LEDGER_25_AGOSTO.md`
> **§22-§54** (branch `claude/jovial-sammet-3f148f`).

---

# 0. ⚠ LEGGERE PRIMA DI TOCCARE QUALSIASI COSA

> **AGGIORNAMENTO 2/9 (notte)**: la campagna «tutte le altre strade» verso i 20 t/s è **CHIUSA** —
> otto bracci, ogni via env-only sul Vision sta in ±2% dell'ancora, **nessuna promozione**, config e
> ancore INVARIATE. Vedi **§12** in fondo e ledger §56-§59. Le tre sessioni di §0.1 risultano offline.
>
> **⚑ AGGIORNAMENTO 2/9 (mattina) — IL RISCHIO DI §0.1/§0.2 È RISOLTO PER MISURA.** Le modifiche
> della «terza mano» (1/9 19:24) sono state **compilate** (2/9 07:25) e il binario risultante è
> **CERTIFICATO SU ENTRAMBI I CAMMINI**: `G1` 0731 **3/3 `AD3D3770…`** (ledger §62-bis) e
> non-regressione della config di servizio Vision **`28ADE339…` identico, contatori uguali alla
> cifra** (§62-ter). ⇒ **quelle modifiche non toccano né la produzione né il servizio.**
> **Identità del banco AGGIORNATE**: `llama.dll` `9E8E8D46…` (invariata), **`ggml-cuda.dll`
> `18444E20BE90538F…`** (non più `6A98BE10…`); backup completo in `backup_pre_chirurgo20\` con i
> sorgenti. **La produzione (`D:\ds4_prod`, `ECAEA60B…`) non è mai stata toccata.**
> **Resta aperto** solo il verdetto dell'esperimento §6.5 (i due bracci del bivio §49/§50), che
> attende il via dell'utente, e che ora ha attribuzione pulita: la config di servizio gira a
> `COMPATTA=0`, quindi **i due bracci sono l'unico posto in cui quella patch può manifestarsi**.
> **Percorsi durevoli nuovi**: `…\lanciatori_salvati_20260825\vision_corto\` (ratifica config A)
> e `…\difetto1_piattaforma\` (script della piattaforma del difetto n.1), entrambi con
> `ORIGINE.txt` e **le identità DLL attese come PARAMETRI a difetto invariato**, mai letterali.

## 0.1 Tre sessioni indipendenti sono attive sullo stesso albero
L'utente ha avviato da chip, la sera dell'1/9, tre sessioni parallele:

| task | oggetto | file bersaglio |
|---|---|---|
| `task_39f6918a` | fix `registra_router` (assi 3-D + guardia mancante) | `ggml-cuda.cu`, `cache-esperti.cu` |
| `task_badf1635` | interazione AcceptMoE × partizione overlap | idem |
| `task_9812c2b9` | guardia contro quant miste degli esperti | `cache-esperti.cu` |

**Tutte e tre possono modificare il sorgente e COMPILARE.** È la condizione che il protocollo
vieta («mai build sotto campagne altrui»), e l'identità del progetto **è la DLL, non l'exe**.

**Regole non negoziabili per chiunque di loro costruisca:**
1. Banco libero dichiarato (nessun `llama-server`/`llama-cli`/`llama-mtmd-cli`, RAM > 82 GiB,
   **stabile per 3 controlli consecutivi a 40 s**: i check istantanei mentono, §37).
2. **Backup DLL** in `D:\llama-subtract\build\bin\backup_pre_<nome>\` con `SHA256.txt`
   **E copia del sorgente accanto** (regola nuova del §49: i backup con le sole DLL non
   permettono di ricostruire nulla).
3. Build **MAI** via `D:\llama-subtract\build_cuda.bat` — fa `cd /d D:\llama-overlap` e
   **compila l'albero SBAGLIATO riuscendo in silenzio**. Procedura a mano + `editbin /STACK`.
4. **G1 obbligatorio dopo la build**: banco corto 0731, 3 corse, SHA
   `AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11`. Se diverge: ripristino
   dal backup.
5. **Ri-baseline del difetto n.1**: `S1` deve ridare
   `97DF3AB0C56EC7A1651B68A205638916627EB19DF73E7788048C32E583135EC0`. Se cambia, tutte le
   sonde della sera 1/9 vanno rifatte.

## 0.2 La «terza mano» — anomalia aperta, autore mai confermato
`ggml-cuda.cu` (19:24:13), `cache-esperti.cu` (19:24:37), `cache-esperti.cuh` (19:24:41) sono
stati modificati **mentre giravano le misure**, con marcatore `// chirurgo19 (1/9)`. Verificato
dalla regia alle 19:31: **non era nessun agente di questa sessione**, nessun processo di build
attivo, DLL invariate. L'ipotesi «era il chip `task_39f6918a`» **non è confermata** (quel chip
risulta avviato dall'utente più tardi).
⇒ **Le misure restano valide** (l'identità è la DLL e la DLL non si è mossa) **ma ogni deduzione
dal sorgente CUDA sul comportamento dei binari attuali è inaffidabile.**
**Snapshot d'emergenza creato**: `D:\ds4_work\snapshot_sorgente_20260901_2145\` (4,4 MB, tutti
i `.cu/.cuh` + `src/` + `MTIME_INVENTARIO.txt`).
**Reperto utile**: `src/models/deepseek4.cpp` e `dflash.cpp` sono fermi a **13:55**, coerenti con
`llama.dll` delle **14:03** ⇒ **il lato `src/` È verificabile**; solo i tre file CUDA sono avanti
rispetto a `ggml-cuda.dll` (14:33).

## 0.3 Divieti permanenti (valgono sempre, per tutti)
- **MAI comandi git** in `D:\llama-subtract`, `D:\llama-dspark`, `D:\llama-overlap`, `D:\b*`,
  `D:\wt-*`. `D:\llama-subtract` è un **worktree collegato** di `D:\llama-dspark`, che è
  **CONGELATO dal 28/8** (201 voci staged, ~30 worktree ancorati). `D:\b52` è standalone: lì
  git in sola lettura è ammesso.
- **MAI toccare** `D:\ds4_prod\` (binari stabili di produzione) né `avvia ds4 locale.bat`
  (Desktop) senza mandato esplicito.
- **MAI** `LLAMA_DSV4_DECODE_TILE_VRES`. **MAI** toccare clock/power della GPU.
- Commit solo con **percorsi espliciti**, mai `git add -A`.
- Le ~130 directory `D:\b*` / `D:\wt-*` sono worktree del repo congelato: **non cancellare**.

---

# 1. STATO DEL PROGETTO IN UNA PAGINA

**Che cos'è**: fork di llama.cpp («llama-subtract»/«llama-overlap») che serve un MoE DeepSeek-V4
su **RTX 3060 12 GB + Ryzen 5800X (8c/16t) + 96 GB DDR4-3000** (kit misto 64+32, i 3000 sono
deliberati: sopra non regge — **non riproporre 3200/XMP**).

**Il cambio del 1/9**: l'utente ha deciso che **`DeepSeek-V4-Flash-Vision-Exp` è il nuovo modello
di default su cui lavorare**. È stato scaricato, portato nel fork, misurato su entrambi i banchi,
ancorato quattro volte, collaudato su testo e su immagini.

**Numeri di oggi (banco lungo reale: prompt 101.691 token, ctx 150.016, completion 1200,
no-think)**:

| | t/s |
|---|---|
| llama.cpp upstream liscio (nessuna nostra patch) | **5,5** |
| fork, modello vecchio `DS4-0731` | **12,65-12,79** |
| fork, **Vision con config vecchia** (AM=0) | 11,76-11,87 |
| fork, **Vision con config PROMOSSA** (A) | **12,30 / 12,38 / 12,39** |

**La produzione NON è stata toccata**: gira ancora su `DS4-0731-IQ2XXS`. Il passaggio del `.bat`
al Vision è una decisione dell'utente, non ancora presa.

---

# 2. LE CONFIGURAZIONI (esatte, riga per riga)

## 2.1 CONFIG DI SERVIZIO DEL VISION — **promossa il 1/9** (§52, §54)

```
Modello : C:\ds4-models\Vision-Exp-GGUF\DeepSeek-V4-Flash-Vision-Exp-IQ2_XXS-00001-of-00004.gguf
Drafter : D:\ds4-models\DSpark-draft-Q2K.gguf
mmproj  : C:\ds4-models\Vision-Exp-GGUF\mmproj-DeepSeek-V4-Flash-Vision-Exp-F16.gguf
```
**CLI (banco corto, ctx 4096)**
```
-c 4096 -ub 64 -np 1 -ngl 99 -t 7 --no-mmap --fit off
-ot  ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped
-otd blk\.0\.ffn_(gate|up|down)_exps\.weight=CUDA0_Mapped,ffn_(gate|up|down)_exps\.weight=CPU
-md <draft> --spec-type draft-dspark -ngld 99
     --spec-draft-n-max 2 --spec-draft-ubatch-size 16 --spec-draft-conf-min 0.80
```
**CLI (banco lungo, ctx 150000)**: come sopra ma `b/ub 2048`, `nmax 3`, `conf 0.70`,
`KV_GATHER=1`, **e OBBLIGATORIO** `-OtDraft 'ffn_(gate|up|down)_exps\.weight=CPU'`.

**ENV**: la SOTA integrale (`LLAMA_CACHE_ESPERTI_SLOT=473`, `FORK=2`, `FORK_BLOCCHI=8`,
`MASSA=2`, `MASSA_AMMISSIONE=0`, `LRU=1`, `SFRATTO_PAR=1`, `BATCH=8`, `W=0`, `CURA=0`,
`SCUDO=0`, `OVERLAP_K=2`, `OVERLAP_ASYNC=1`, `OVERLAP_BATCH_MAX=3`, `OVERLAP_PIN=1`,
`MAPPED_IBRIDO=1` soglia 2, `KV_RING=1`, `VRAM_A_FASI=0`, `PORTO_SPEC_NMAX=2`) **con due
differenze**:
```
LLAMA_ACCEPTMOE           = 1      ← acceso
LLAMA_ACCEPTMOE_COMPATTA  = 0      ← spento
```
**Corpo della richiesta**: `thinking_budget_tokens: 0`, `max_tokens: 1200`, `temperature: 0`,
`cache_prompt: false`.

**Perché A batte la vecchia — tre gambe**: (1) **velocità**: pari sul corto, **+3,6…+5,3% sul
lungo**; (2) **byte**: −23,4% (corto) / −14,1% (lungo) con colpi 67,7→75,2% / 58→63,4%;
(3) **immunità per costruzione**: senza compattazione la scrittura dei `-1` non esiste, quindi
l'intera classe dei difetti n.1/n.2 è *impossibile*, non solo evitata.

⚠ **Nomi esatti**: la variabile è **`LLAMA_ACCEPTMOE`**, NON `LLAMA_CACHE_ESPERTI_ACCEPTMOE`
(quel nome non ha lettori: sarebbe assente in silenzio). `MASSA=2` **esige** `FORK=1|2`: si
muovono sempre insieme, o il cancello STRICT ferma la corsa.

## 2.2 Config del modello vecchio (0731) — riferimento storico, ancora viva
Uguale, ma modello `C:\ds4-models\DS4-0731-IQ2XXS.gguf` e `LLAMA_ACCEPTMOE=0`.
**Candidato di promozione non validato**: sul lungo, `-OtDraft 'ffn_…_exps\.weight=CPU'` dà
**12,788 t/s = +1,10%** rispetto alla mappata (SHA `A0F49B89`, replica il reperto del 9/8
«380+0 batte 380+32»). **Serve una replica prima di scolpirlo.**

---

# 3. LE ANCORE (tutte a load freddi indipendenti)

> **Protocollo d'ancora (§36)**: 3 cicli di *load → UNA richiesta → shutdown*, **ogni ciclo un
> PROCESSO SEPARATO** (`powershell -File`). Iterare in una sola sessione PowerShell **si
> impianta** al secondo giro (server su, POST mai emessa; sospetto: `FreeConsole()` della
> chiusura graziosa — dichiarato, non provato).

| ancora | SHA | numeri |
|---|---|---|
| **0731 corto (G1)** | `AD3D3770C7D13885AE5292442D42CC0338500B82435146AC299A5436BFCBFE11` | p1 0,77670 · mean_len 2,01 |
| **0731 lungo** | `A177DDAF3583610CDE43ED768E9D0E950AA32B0F63D7ACFA88E9657F26A47479` | 12,650-12,71 t/s · p1 0,84073 · mean_len 2,61 · C_round 205,3-206,3 |
| **Vision corto AM=0** | `88031A83F3950ACCB3A396A529FD76227CF7B998ACD71DD2F8A7D10A7773C1F1` | 12,70-12,73 · p1 0,72830 · 4633 char |
| **Vision corto A** ⭐ | `28ADE3395B5888D7DC1DB5D12A06083FFE1B2017029DC18EE87003BB090E1BBD` | 12,66-12,79 · p1 0,72693 · 4538 char · colpi 75,2% |
| **Vision lungo AM=0** | `1596D3B3C97A5B22B77C7D2DF58FD865734D72B9D5BC06730C3C9F723F2E9EE3` | 11,764/11,870/11,871 · p1 0,80914 · mean_len 2,44 |
| **Vision lungo A** ⭐ | `B2B8F84E96ED34679C53E1F194B48DB4BE54C1789462DFFAE8ACD43169FFEE8D` | 12,300/12,384/12,394 · p1 0,82683 · mean_len 2,51 · colpi 63,4% |

**Ancore del DIFETTO** (piattaforma di riproduzione, vedi §6):
- garbage riproducibile: `97DF3AB0C56EC7A1651B68A205638916627EB19DF73E7788048C32E583135EC0`
- guarigione con `COMPATTA=0`: `9F67629A4A0C04E69504F43F87A0A79FEF3CC1EB8BFBC6D627722B894C1397D5`
  (= **bit-identico** al braccio sano AM=0)

⚠ **Il determinismo del Vision vale sul PRIMO COLPO A FREDDO**: la prima richiesta dopo un load
è bit-riproducibile fra sessioni e macchine; **la seconda diverge** perché la residenza della
cache evolve e il restore non la copre. *(Correzione di casa: il determinismo del 0731 veniva dal
RESTORE — residenza inclusa — non dalla speculazione da sola.)*

---

# 4. IL MODELLO NUOVO — cosa sapere

**Release**: `deepseek-ai/DeepSeek-V4-Flash-Vision-Exp` (HF, 31/8, MIT, 305B, 154 GiB FP8).
Il «284B» che circola è **sbagliato** (testo 304B + ~1B di torre).

**Tronco**: `deepseek_v4`, **43 strati, hidden 4096, 256+1 esperti, 6/token, vocab 129280** —
sagoma identica al 0731, **ma continued-trained** (pesi diversi).
**Torre**: ViT proprietario ~0,47B (32 strati, RoPE 2D, attenzione bidirezionale per immagine),
aligner pixel-shuffle → 4096; i token visivi entrano **nel prefill** in uno span
`[IMAGE_START…END]`, **max 384 token/immagine**; niente cross-attention.

**⚠ Secondo bias di routing `exp_probs_b_vl`** per i token immagine, **decorrelato dal testo**
(r = −0,026): **le misure di cache del ledger valgono per il routing TESTO e NON trasferiscono
al prefill immagine.** Da rimisurare, mai assumere.

**Geometria mista** (causa del bug del §32): `ffn_down_exps` sono **IQ2_XS su 23 strati e
IQ3_XXS su 20** (il 0731 li ha tutti Q2_K). Slot: **7.658.112 B = 7,30 MiB** (0731: 6,75);
473 slot = 3.454 MiB (0731: 3.194) — **ci stanno**, perché il buffer CUDA0 del Vision è 1,9 GiB
più piccolo.

**Drafter**: il config Vision porta lo **stesso impianto** (`dspark_block_size 5`,
`target_layer_ids [40,41,42]`, `markov_rank 256`). **Il drafter attuale TRASFERISCE**:
accettazione 66,15% sul 0731 contro **65,50% sul Vision** — Δ 0,64 punti, indistinguibile.
Nessuna ri-estrazione necessaria.

**Capability verificate**: parla (italiano tecnico corretto, §4.10 pieno); **vede** (test
sintetico a contenuto noto: 3/3 con posizioni, colori e OCR esatti); **legge una foto vera**
(codice `REIMPOSTA-OKTOCGC` esatto carattere per carattere a **riduzione 18×**, senza crop).
**Debolezze misurate**: non riconosce il **mezzo** (tratta una foto di schermo come screenshot)
e sbaglia lo **stato dei controlli UI** (dice «campo vuoto» un campo compilato). ⇒ affidabile
per «leggimi questo schermo», prudente sui giudizi di stato.

**Limiti del quant** (dichiarati da prometheusAIR): attenzione in-span non implementata
(fallback causale); immagine singola; multi-immagine e contesti lunghi non misurati.

---

# 5. FISICA DELLA MACCHINA — cosa è chiuso e perché

## 5.1 La mappa dei tetti (campagna 20 t/s, §13-§21) — **tutte le strade software stanno sotto i 20**
| via | tetto | stato |
|---|---|---|
| speculazione (asintoto L→∞) | 20,7 | al tetto |
| politica esperti a 473 slot **con oracolo Belady** | fuori bersaglio 2,2× | chiusa |
| anticipo predittivo (prefetch/online) | +0,25% | **chiuso per CAPIENZA**: 19.885 prenotazioni rifiutate su 40.965 perché l'unica vittima era un residente vivo |
| `OVERLAP_K=5` / flip decode-su-CPU | 9,93 / 8,18 | falsificati: **dequant-bound**, 12,8 GiB/s letti su 33-37 disponibili |
| `IQ2_XXS_R4` (repack) | +6% a pieno successo | **sbarrata dall'aritmetica**: con lane CPU *gratuita* i tetti sono 15,97 / 16,56 / 18-19,3 |
| sweep `ACCEPTMOE_SOGLIA` | C_round −13,5% ma **t/s piatto** | chiuso: `mean_len` si semplifica |
| **«senza trasporto»** (slab 9,9-21 GiB) | **24,2** | **richiede VRAM che la 3060 non ha** |

⇒ **Su questo hardware resta la via VRAM (acquisto) oppure consolidare.** Il tetto onesto del
vivo è **16-17 t/s**, confermato per tre vie indipendenti.

## 5.2 Il muro è la SERIALIZZAZIONE, non la banda — **quattro conferme indipendenti**
1. Sovrapposizione trasporto/calcolo misurata al **19%**, DDR4 a duty 26% (§12).
2. Tolto il 96% dei blocchi host, il costo **migra 1:1** invece di sparire.
3. `MASSA=0` spegne l'intero router a tre vie (0 partizioni, 0 lane, 0 copie) a **C_round
   PIATTO** — il costo migra sulla cache (§19).
4. **1/9**: config A toglie il **23,4% dei byte** a partizioni e domanda identiche e la velocità
   **non si muove di un punto** (§52).
*(Nota: sul LUNGO i byte SI convertono in tempo — working set più grande, colpi più bassi. Sul
corto no.)*

## 5.3 Modello di costo
`C_round(L) = 81,4 + 48,4·L` ms (R² 0,97). `tempo totale = ms/token × N`: **`mean_len` si
semplifica** ⇒ una leva che abbassa C_round ma accorcia i round **non compra nulla** (§21).

## 5.4 Il tetto della MEMORIA PINNATA — scoperto il 1/9 (§41)
Il Vision **non caricava** sul lungo: non per la VRAM (che avanza: 1481 MiB liberi in decode
dove il 0731 ha 0) ma per il **totale pinnato**. Tetto ora stretto a **~75,7-76,1 GiB**:
75,70 passa, **76,09 fallisce** (`cudaHostAlloc di 2224 MiB fallita`). Il buffer mappato è
`cudaHostAlloc + cudaHostGetDevicePointer` (`ggml-cuda.cu:1440-1467`): **nessuna env lo rende
paginabile**. **Sfogo**: `-OtDraft 'ffn_(gate|up|down)_exps\.weight=CPU'` (gli esperti del
*drafter* su RAM liscia). Vale per ogni modello futuro più grande di ~400 MiB.

---

# 6. I DUE DIFETTI — stato della caccia (§31-§51)

## 6.1 Che cosa sono
- **n.1** — Vision, `AM=1` × `OVERLAP_K=2` × `COMPATTA=1`, **senza drafter**: garbage
  deterministico e **bit-riproducibile fra sessioni e fra esecutori**. Non è config di servizio,
  ma è una mina di correttezza riproducibile.
- **n.2** — Vision, `AM=1` **con drafter**, 1200 token: il testo **degenera** (loop). È lo
  **stesso difetto in dose minore**: il deficit di domanda compare *solo* nel braccio che
  produce garbage, e cresce con la lunghezza (2,5% → 14,3%).

## 6.2 Il meccanismo, quantificato
`kern_partiziona:7291` scrive **`-1`** quando `peso[perm[j]] == 0.0f`; `kern_decidi`
(`cache-esperti.cu:5082`) **non conta gli id `-1`** ⇒ la route sparisce. Nel braccio rotto **il
72% della domanda GPU svanisce** (4.359 contro 15.439) a partizioni e lavoro CPU identici, e la
sonda mostra **4 colonne su 6 annullate** (le altre due sono la lane CPU): quello strato calcola
con **2 esperti su 6** — uscita *sbagliata ma plausibile*, ecco perché **degenera invece di
esplodere e nessun assert scatta**. La corruzione è **progressiva dagli ULTIMI strati a monte**.

**Il passo causale è NECESSARIO E SUFFICIENTE**, provato da due manipolazioni indipendenti che
lo spengono ed entrambe guariscono:
- `COMPATTA=0` → spegne il *fetch* → **SHA bit-identico al sano**
- `TRACCIA=1` → rende *incoerente il record* → sano *(osservare guarisce: Heisenberg reale)*

## 6.3 Che cosa è ESCLUSO, con prova
scheduler (3 vie: `CERCA_CPU`, `ASYNC=0` con worker mai creato, `PIN=0` senza lane — garbage
**byte-identico**) · riconoscitore posizionale `split_id+2` (3 prove) · CUDA graph
(spegnendoli lo SHA non cambia) · geometria per-strato (curata) · replay stantio · multi-stream
(`GGML_CUDA_GRAPH_OPT=0` ⇒ macchina inerte) · l'aritmetica del kernel acceptmoe · l'ipotesi
«indice sbagliato» (il kernel non riordina, corrispondenza 1:1) · **alias d'arena**
(richiederebbe concorrenza, ma il braccio sequenziale resta rotto) · i «pesi zero legittimi»
(sono lo 0,4%, non il 71%).

## 6.4 Il vincolo residuo (consegna per chi farà il dump)
```
braccio ROTTO     : record COERENTE (pesi mancanti = 0 su 3612) + 70% di -1
                    ⇒ rr→pesi ha forma buona (passo ≥ 6) e contenuto NULLO
braccio TRACCIA   : record INCOERENTE (1760/1892) + SANO
braccio COMPATTA=0: nessun fetch (3612/3612)      + SANO
braccio AM=0      : record COERENTE + pesi GIUSTI + SANO   ← il più stringente
```
**Fatto verificato sul lato affidabile del sorgente** (`llama-graph.cpp`, mtime 13:55 = coerente
con `llama.dll` 14:03): il nome `ffn_moe_weights_norm` sta sul tensore **2-D [6, n_tok]**
(`:2231`, **ne0=6, coerente**) e solo **dopo** viene rimodellato a `[1,6,n_tok]` (`:2233`);
`acceptmoe_pesi` riceve la vista 3-D ⇒ **ne0=1, degenere** (`:2291-2293`).
⇒ **I due bracci hanno REGISTRANTI DIVERSI**: rotto = `weights_norm` (coerente), traccia =
`acceptmoe_pesi` (degenere). La «contraddizione insolubile» era questo.

## 6.5 I due modelli superstiti — e l'esperimento che li decide
| | **modello «registrazione»** (§49) | **modello «vita del buffer»** (§50) |
|---|---|---|
| tesi | il record puntava all'uscita mascherata | il buffer di `weights_norm` è **già riciclato**: con AM=1 il suo ultimo consumatore *di grafo* si sposta in testa allo strato, ma la cache lo legge **fuori banda**, con un puntatore che l'allocatore non vede |
| dopo la build della terza mano, braccio ROTTO | **GUARISCE** | **RESTA ROTTO** |
| dopo la build, braccio TRACCIA | resta sano, `pesi mancanti`→~0 | **DIVENTA ROTTO** |

Il §50 spiega **tutti e quattro** i vincoli, incluso il progressivo (la pressione di riuso
dell'arena cresce lungo il grafo) e l'indifferenza a concorrenza/stream/grafi. È il **fratello
non-concorrente** dell'esposizione «alias d'arena» del 30/8 (`ggml-backend.cpp:2082-2086`).
**Se vince il §50, il fix non è togliere una registrazione: è DICHIARARE LA DIPENDENZA** (dare
alla partizione un arco su `weights_norm`, come fa TRACCIA per caso) **o tenere vivo il
tensore.**

**Il dump, quando si farà, deve stampare per la STESSA colonna**: `perm[j]`, l'id, il peso
letto, **il puntatore `rr→pesi` con la forma registrata, il NOME del tensore che l'ha
registrato** e — se si segue il §50 — **l'intervallo di vita del suo buffer**.
*(Serve una build: backup DLL + sorgente, G1, ri-baseline S1.)*

---

# 7. PERCORSI

## 7.1 Alberi e binari
```
D:\llama-subtract\              albero di lavoro (worktree di D:\llama-dspark, CONGELATO)
  build\bin\  llama.dll      9E8E8D469A7B047FDAF863E384EE1A6EEC37C54C062FF9A412D3D2787F6D7131  (14:03)
              ggml-cuda.dll  6A98BE102ED767F1E3B78FB642C4F4C3C67A4E5B6BF3094273A88BA9D3BF6007  (14:33)
              backup_pre_chirurgo17\ , backup_pre_chirurgo18\      (SOLO DLL: vedi §0.2)
D:\llama-vision-upstream\       build upstream pulita (via A)
  build\bin\      variante «as-is» ricetta prometheusAIR   (banner b10734-9c9a1546d)
  build-fix\bin\  variante «fix ripristinato» ← LA BUILD DI LAVORO per le immagini
D:\ds4_prod\bin_stabile_20260825\   PRODUZIONE (ECAEA60B / 6EF5B781 / BAD51D94)
D:\ds4_work\snapshot_sorgente_20260901_2145\   snapshot del sorgente (§0.2)
```
**Perché due varianti upstream**: la patch di prometheusAIR conteneva un **esperimento di
bisezione altrui** che commentava tre `ggml_build_forward_expand` (metà del fix upstream
`dee2a846b`). Le due varianti **divergono dai primi token, ciascuna deterministica** ⇒ le tre
righe cambiano la numerica. **Si lavora sulla `build-fix`**; la `build` as-is si conserva perché
i numeri pubblicati da prometheusAIR sono stati prodotti con quella.
*(Nota: nel NOSTRO `deepseek4.cpp` quelle tre chiamate **non esistono** — il fork è già sul lato
«senza expand».)*

## 7.2 Modelli
```
C:\ds4-models\DS4-0731-IQ2XXS.gguf                    modello di PRODUZIONE (80,76 GiB)
C:\ds4-models\Vision-Exp-GGUF\                        il nuovo default (80,15 GiB, 8 file, SHA verificati)
D:\ds4-models\DSpark-draft-Q2K.gguf                   drafter in uso (6,69 GiB)
D:\ds4-models\DS4-0731-GateUp-MXFP4Down.gguf          quant unico, spostato da C: il 1/9 (112 GiB)
D:\ds4-models\DS4-0731-Q2K-GateUp.gguf                quant unico (92,86 GiB)
D:\ds4-models\DeepSeek-V4-Flash-IQ1_S-XL-merged.gguf  tenuto (gli split sono stati cancellati)
```
⚠ **Il modello di produzione NON ha backup su disco**: la copia che sembrava gemella
(`D:\models\ds4\DeepSeek-V4-Flash-IQ2XXS-imatrix.gguf`) ha **hash diverso**.
**Spazio**: C: ~63,6 GiB liberi · D: ~143,7 GiB liberi.

## 7.3 Lanciatori e banchi
```
D:\ds4_work\llama_run\lanciatori_salvati_20260825\p1b_conf.ps1   ← IL LANCIATORE DEL LUNGO
   backup: .bak_20260831_pre_w , _pre_flip , _pre_amsoglia , .bak_20260901_pre_lungo_vision ,
           .bak_20260901_pre_otdraft , .bak_20260901_pre_compatta
   bracci: r57_arm.ps1 , r58_arm.ps1 , sw_arm.ps1 , vl_arm.ps1 (braccio `vision_A`)
C:\Users\imanu\Documents\Codex\2026-08-15\handoff-nuova-chat-15-agosto-md-3\work\run_porto_hot.ps1
   ← IL BANCO CORTO (G1)
```
Log/summary del lungo: `D:\ds4_work\llama_run\sota100k_ctx150k_densefa_stage_hc5_<tag>.summary.txt`
e `sota_ctx150000_densefa_stage_hc5_<tag>_f2_b2048.server.log`.
Fascicolo del difetto (sessione peer): `D:\ds4_work\llama_run\fascicolo_difetto1_20260901.md`.

---

# 8. PROTOCOLLO DI MISURA (non negoziabile)

1. **Si ESEGUE lo script, non si ricostruisce il comando.** `--no-host` e `-otd` non compaiono
   nel manifesto: ricostruire a mano ha già causato un OOM.
2. **Il manifesto non è la configurazione**: `manifesto_check.py` è **rosso con 59 leve vive non
   stampate**, e la guardia **non gira in nessun cancello**.
3. **Cancelli pre-registrati PRIMA di correre**, con soglie numeriche.
4. **Contatore di raggiungibilità sempre**: una leva il cui ramo non è raggiungibile dà
   **verdetto NULLO**, non «innocente». *(Violata da noi il 1/9: la bisezione girava senza
   drafter, dove AcceptMoE è disarmato — ci è costata un fascicolo intero.)*
5. **§4.10 — leggere il testo, sempre**, in **UTF-8 esplicito** (`Get-Content` senza encoding
   falsa il conteggio dei caratteri non latini). Nessun numero di velocità vale senza.
6. **p1 molto SOPRA l'ancora è un ALLARME, non un premio**: un testo degenere è banale da
   bozzare, quindi accettazione e t/s salgono *con* la corruzione (0,95 vs 0,73 = corruzione).
7. **Mai promuovere da corse corte**: a 200 token la config bocciata sembrava sana; il collaudo
   a 1200 l'ha smentita.
8. **Cancello quantitativo nuovo**: `domanda/partizioni`. Sul **corto** vale ~4,0 (k_cpu=2), sul
   **lungo** ~7,6 (il prefill aggiunge domanda senza partizioni) ⇒ **conta il SEGNO del
   deficit**, non il valore: **un deficit POSITIVO grande è la firma del difetto**.
9. **Un load per volta** (~86 GiB), quiete stabile 3×40 s, controllo e lancio **nello stesso
   processo**.
10. Mediana su tripletta, mai il massimo; ri-ancorare ogni tre bracci; SHA lunghi in banda ±3%.

---

# 9. LE TRAPPOLE (pagate, tutte)

## 9.1 Le NOVE del lanciatore
`W` · `FORK` · `MASSA` · `SOGLIA` · `SLOT` · `BOZZA_SLOT` · `MAPPED_IBRIDO_SOGLIA` ·
`ACCEPTMOE_SOGLIA` · **`ACCEPTMOE_COMPATTA`** — tutte **inchiodate a mano dentro
`Set-SotaEnvironment`**, che gira *nel ciclo delle shape*: impostarle dall'esterno è **INERTE** e
la corsa misura la SOTA piena credendo di misurare la leva. **L'ultima avrebbe pubblicato un +4%
falso.** Cura: parametro col **difetto invariante**, backup datato, e **verifica del testimone
`OVERRIDE:` nel log prima di lasciar correre**.
⇒ **`Set-SotaEnvironment` inchioda ~40 env var: la bonifica sistematica non è più rimandabile.**

## 9.2 Strumenti che mentono (cinque nuove istanze il 1/9)
- `test-quantize-perf` con un tipo **non compilato** esce con **codice 0 e output vuoto**.
- `Get-Content` senza encoding **inventa** caratteri non latini (ha quasi bocciato una config
  sana).
- Una **sonda a budget** (`OVERLAP_VERIFICA`, 100 lanci) se l'è mangiato tutto nel **warmup**:
  produceva righe, ma il regime d'interesse non era mai stato raggiunto.
- **Il sorgente non descrive il binario** (§0.2): quando una deduzione dal codice contraddice
  una misura ripetibile, **sospettare per prima la corrispondenza sorgente↔binario**.
- Una **«progressione»** che era il **righello**: i dump escono a *battito d'orologio*, non a
  evento ⇒ corse identiche danno curve diverse. **Stabilire se una sonda campiona a TEMPO o a
  EVENTO prima di leggerne un andamento.**

## 9.3 Architetturali
`OVERLAP_K=6` **spegne il fork** (max utile 5) · `-ot …=CPU`/`-ncmoe` mandano il **prefill** su
CPU ⇒ OOM · il cancello di fusione di `MUL_MAT_ID` legge `SLOT>0 || BOZZA_SLOT>0` **senza
consapevolezza di fase** (spiega un −11,6% di prefill che sembrava del flip; fix da ~2 righe in
coda) · `MASSA=2` esige `FORK=1|2` · con `COMPATTA=1` la sonda di verifica **sovra-riporta**
(conta i `-1` by-design come disallineamenti).

---

# 10. CODA APERTA (in ordine di valore)

1. **Decidere la radice del difetto n.1** — l'esperimento è disegnato e **discrimina i due
   modelli superstiti** (§6.5). Richiede build col protocollo pieno. **Le tre sessioni attive
   (§0.1) toccano proprio quei file**: chi costruisce deve leggere per primi quei due bracci.
2. **Passare la produzione al Vision** (decisione utente): il `.bat` sul Desktop e i binari di
   `D:\ds4_prod` sono ancora sul 0731. Il Vision è misurato, ancorato e collaudato, ma **il
   binario di produzione non contiene il porto vl-routing**: serve una copia stabile nuova.
3. **Bonifica di `Set-SotaEnvironment`** (~40 env inchiodate) — nona trappola in un giorno.
4. **Fix del cancello di fusione consapevole di fase** (~2 righe): ripara la misurabilità di
   ogni braccio a `slot=0`.
5. **Porto mtmd nel fork**: oggi le immagini si servono dalla build upstream `build-fix`. Il
   fork ha lo stack mtmd **presente e non modificato** (`mtmd.dll` già compilata, `--mmproj`
   cablato a `server-context.cpp:1545`), ma il porto tocca `server-context.cpp` (262 KB, che
   contiene sia mtmd sia ~205 punti di cache/kv-ring/speculazione).
6. **Replica del candidato `OtDraft=CPU` sul 0731 lungo** (+1,10%, un solo braccio).
7. **Verifica di `-OtDraft` anche sulla config CORTA del Vision** (non misurata lì).
8. **Riconciliazione delle 59 leve non stampate nel manifesto** + far girare la guardia in un
   cancello.
9. **Bug indice −1** (`ops.cpp:4831`, `BATCH_MAX=4` al taglio del reasoning): il 1/9 la
   transizione è stata attraversata **senza assert a BM=3**; il README del quantizzatore
   descrive **lo stesso assert** per il crash-immagine (`ubatch->token` non popolato →
   `get_rows` su `tid2eid`): **possibile stesso fascicolo**.
10. **Decisioni disco rimaste** (nessuna bloccante): sidecar `q1` v1/v2 (67,66 GiB, quale?),
    `Q2K-GateUp` (92,86), progetti altrui `qwen3/dsv2 memmap` (81,84) e `qwen3-bonusx` (~59,5),
    dati campagne luglio (~116), residui cosmetici (0,055).
11. **Il bersaglio dei 20 t/s**: su questo hardware **ogni strada software è misurata sotto**.
    Restano la **VRAM** (una GPU da 24 GB riaprirebbe la campagna: il tetto «senza trasporto» è
    24,2 t/s) o **consolidare**.

---

# 11. COME LAVORA QUESTO PROGETTO (per una IA che subentra)

- **Regia e braccia sono separate**: chi coordina non esegue banchi né chirurgie; dispaccia
  esecutori con mandati che contengono **cancelli pre-registrati** e **trappole note**.
- **Il ledger è il bus di coordinamento**: quando più sessioni lavorano in parallelo e i canali
  diretti falliscono, **il commit è il recapito**. Marcare i commit che NON sono segnali quando
  qualcuno ha una sentinella armata.
- **I negativi si registrano.** L'1/9 sono state proposte e **ritirate dai proponenti stessi
  otto ipotesi**, quasi tutte con falsificatori trovati **nei dati già su disco**. È il
  comportamento corretto, non un fallimento: costa meno di una corsa.
- **Quando una misura contraddice una deduzione, la misura vince** — e si va a cercare **quale
  premessa** è falsa.
- **Ogni output nel ledger**, ogni commit con percorsi espliciti, e la memoria persistente
  aggiornata (indice in `MEMORY.md`).

---

*Documento generato il 1/9/2026. Cronaca completa: `docs/porto/LEDGER_25_AGOSTO.md` §22-§54.
Handoff precedente (campagna 20 t/s): `docs/porto/HANDOFF_26_AGOSTO.md`.*


---

# 12. AGGIORNAMENTO 2/9 (notte) — la campagna «tutte le altre strade» verso i 20 t/s: CHIUSA

**Direttiva utente**: «proviamo a spingere questo modello a 20 t/s?» → «iq1 escluso a priori» →
«proviamo tutte le altre strade». Otto bracci sul banco lungo (04:00-07:08), zero guasti, DLL
invariate, ancora riprodotta al quarto load freddo (4/4). Cronaca: ledger **§56-§59**.

| via | braccio migliore | decode | esito |
|---|---|---|---|
| slot sulla VRAM libera del Vision (1479 MiB) | 623 puro | 12,47 (+1,1%) | byte −9% ma la traiettoria domina; 623 regge (385 MiB liberi) |
| trasporto online + 150 slot di staging (pool 473) | T2 | 12,19 | rifiutate 19.885 → **0**: la capienza ERA il vincolo del 31/8, ma i byte cambiano stream e non spariscono |
| trasporto online senza staging | T1 | 11,45 | −8,1% a mean_len uguale: chiuso per la seconda volta |
| massa, emivita 16 / 256 | M1a | 12,51 (traiettoria) | byte +10% / +14%: 64 è già l'ottimo |
| solo predittore W | wsolo | 12,34 | **gratis**: uscita bit-identica a 623 puro, −1% |

**Cosa cambia per chi subentra: NIENTE nella configurazione.** Config di servizio e ancore
restano quelle di §2-§3. **Ogni strada env-only sul Vision sta in ±2% dell'ancora**: la mappa
dei tetti di §5.1 è confermata su un secondo modello. I 20 t/s restano nella VRAM (§10, voce 11).

**Fatti nuovi da tenere a mente**
- **Il consumatore del trasporto online costa ~7% di macchina FISSI** (~70 µs per confine di
  strato, anche con 386 copie); il predittore è gratis; l'atterraggio con staging vale +6,4%.
  Tetto della strada a consumatore gratuito: ~13,3. Corregge la lettura «C_round piatto» del §16.
- **Ogni leva di residenza cambia la traiettoria** (SHA diverge) e la bozzabilità del testo
  muove il t/s di ±5%, più dell'effetto cercato; C_round scende con mean_len. Prima di riaprire
  un fronte di residenza serve un metro a traiettoria fissa (ms/forward normalizzato, spec OFF, o
  restore). Cancello del deficit riformulato: `domanda/partizioni ≥ 6,5` sano (ancora A 7,485),
  difetto ≈ 3,7.
- `LLAMA_TRASPORTO_STAGE_SLOT` **ritaglia** gli ultimi N slot dal pool (pool reattivo = SLOT−N)
  ed è inerte senza `TRASPORTO_ONLINE≥1`; `kern_acceptmoe` scarta per RESIDENZA (la SOGLIA
  ripesca; §18 p.3 impreciso); nella famiglia massa sono vive ed env-only solo `MASSA_EMIVITA`
  e `MASSA_UNITA` (FLOOR/MARGINE inerti sotto `AMMISSIONE=0` inchiodata).
- `SLOT` non ha rete di ripiego: se lo slab non entra la cache resta SPENTA (fail-loud `FALLITA,
  cache spenta` / `ATTENZIONE, voluti`); i `*.summary.txt` sono **UTF-16LE**; `C_round` non è
  stampato (= `1000/decode × mean_len`).

**Strumenti nuovi**: `D:\ds4_work\llama_run\lanciatori_salvati_20260825\vl_sonde_arm.ps1`
(bracci `online` / `massa` / `wsolo`, guardie sui clamp del codice, testimoni in intestazione);
`docs/porto/AUDIT_SET_SOTA_ENVIRONMENT.md` (zen-morse: 62 env censite, 21 rosse).

**Coda aggiunta a §10**: metro a traiettoria fissa · rete di ripiego di `SLOT` (build) ·
manifesto che stampi `TRASPORTO_*`/`MASSA_*`/`PF_LEGACY` (build) · consumatore online senza
sync per confine (tetto +6%) · correggere §16/§18 nel ledger come da §57-§59.
