# P7 · cella 7 — MTP bozza 2, ragionamento spento, contesto lungo 131k — 15 settembre 2026

Operatore: cella 7 di P7. Decisione dell'utente: **UNA SOLA corsa di misura**, candidato B = MTP bozza 2
(preset `M2`) con il ragionamento SPENTO, sul profilo `lungo_131k` (L01/L02 a prefisso `ctx131k`,
appena estesi in `casi.json`). Punto operativo dichiarato: contesto ~100k+, KV 250k (il preset ha
contesto 262144). Nessuna modifica di codice del motore, nessuna build: solo un preset e le corse
sottostanti, con i binari sperimentali ORIGINALI `qwen38_clean\build\bin`.

**Scostamento dal mandato, dichiarato subito**: la corsa di misura richiesta era una sola. La manopola
scelta per prima (`--reasoning-budget 0`, la "config canonica" del resto del repo) è stata **provata e
falsificata** sul primo caso (L01): il mandato stesso prescriveva di fermarsi, cambiare manopola e
ripartire in quel caso. È quello che è successo — **due corse in tutto**, la prima invalida per la
domanda della cella (r1, manopola sbagliata) e la seconda valida per la manopola (r2, con un
avvertimento separato sulla RAM, §4).

---

## 0. Verdetto in tre righe

1. **La manopola giusta è `--reasoning off`, non `--reasoning-budget 0`.** Quest'ultima è la prassi
   documentata altrove nel repo ma qui **non funziona**: il log conferma che il forcing si attiva
   (`common_reaso: forced sequence complete, done`) e sui riscaldamenti banali produce davvero un
   pensiero da 29 caratteri, ma su L01/L02 (prompt tecnici lunghi, contesto 131k) il modello continua
   comunque a riempire `reasoning_content` (2.903 e 4.359 caratteri) lasciando `content` a **zero** su
   entrambi — lo stesso guasto già noto con `--reasoning on` senza budget (D15, 14/9). Con `--reasoning
   off` invece `reasoning_content` è **vuoto su tutti e quattro i casi** (verificato) e il testo finale
   arriva regolarmente.
2. **A 131k, con ragionamento spento, MTP bozza 2 rende 25,479 t/s** sull'insieme libero (L01+L02),
   **38,030-40,468 ms/token accettato**, con accettazione alla seconda posizione fra **0,434 e 0,546**
   per caso (0,489 nella riga cumulativa di fine corsa) — **sotto la soglia di pareggio 0,633** della
   cella 1: la bozza da 2 token non paga qui più che a 32k, anzi un po' meno. Nessun NaN, nessun errore.
3. **Allarme di validità dichiarato dal mandato stesso**: la RAM libera è scesa a **3,3 GiB** durante
   L01 (sotto i 4 GiB indicati come soglia di invalidità) — e lo stesso vale per la corsa fallita (3,45
   GiB). Non è un guasto (nessun OOM, nessun crash, corsa completata pulita), ma **per il criterio
   dichiarato dal mandato la corsa non supera la soglia di validità sulla RAM**: i numeri sopra vanno
   letti come "misurati, con margine di RAM sotto la soglia dichiarata", non come un verdetto pulito.

---

## 1. La manopola: due tentativi, uno dei due falsificato

| tentativo | manopola | risultato su L01/L02 (131k) | esito |
|---|---|---|---|
| r1 (fallito) | `--reasoning on --reasoning-preserve --reasoning-budget 0` | `reasoning_content` = 2.903 / 4.359 caratteri, `content` = **0/0** | **FALSIFICATO** |
| r2 (valido per la manopola) | `--reasoning off` | `reasoning_content` = **0/0** caratteri, `content` = 3.415 / 4.123 caratteri | **CONFERMATO** |

`--reasoning-budget 0` è la "config canonica" citata in `docs/porto/PROTOCOLLO_MACCHINA.md` e
`docs/porto/CANCELLO_NEUTRALITA.md` (`params.sampling.reasoning_budget_tokens = 0`, "0 for immediate
end" nell'help CLI, `arg.cpp:3322-3329`). Il log di r1 mostra che il meccanismo si attiva davvero:

```
3.27.084.627 I cmn  common_reaso: activated, budget=0 tokens
3.27.084.628 I cmn  common_reaso: budget=0, forcing immediately
3.27.084.628 I cmn  common_reaso: forced sequence complete, done
```

— una volta per richiesta (4 richieste, 4 attivazioni). Sui riscaldamenti (prompt banale, 8 token di
budget) funziona: `reasoning_content` tagliato a 29 caratteri ("We need to respond to user: \"").
Su L01/L02 (prompt tecnici, contesto 131k, budget 1024) **non funziona**: il testo di pensiero
recuperato da `output/L01_ctx131k.reasoning.txt` è un ragionamento completo e ben formato da 2.903
caratteri, non un frammento troncato. **Ipotesi non verificata** (non falsificata ulteriormente, per
protocollo si è cambiata manopola invece di indagare): il forcing chiude un primo segmento di pensiero
ma il modello ne riapre uno che il parser reasoning/content non intercetta più come "oltre budget",
oppure l'accettazione a blocchi della bozza MTP (2 token per volta, non uno alla volta) salta il
controllo per-token del budget su prompt lunghi. Non è stata indagata oltre: cambiare manopola era la
prescrizione esplicita del mandato in questo caso.

**Manopola dichiarata per il resto del documento: `--reasoning off`** (`enable_reasoning = 0`,
`default_template_kwargs["enable_thinking"] = "false"`, nel template jinja del GGUF). Verificata
empiricamente vuota su tutti e 4 i casi di r2 (2 riscaldamenti + L01 + L02).

---

## 2. Tabella per caso (r2, `--reasoning off`, unica corsa valida per la manopola)

Corsa: `20260915_103715_P7_p7_n2l131_ragionamento_spento_r2`. Preset `preset_N2L131_p7.json`
(`docs/porto/banco_p0/preset_N2L131_p7.json`). Budget 1024, greedy, seed 1234, MTP bozza 2 (identico a
M2), 64 slot, sparse FA spenta, contesto 262144.

| caso | prompt_n | cache_n | prefill t/s | predicted_n | decode t/s | ms/token accett. | accettazione (pos1,pos2) | mean acc len | motivo fine | testo finale | reasoning |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|
| **L01@ctx131k** (prefill freddo) | 131.208 | 0 | **250,047** | 1.024 | **26,270** | **38,030** | (0,763 ; 0,546) | 2,31 | length | 3.415 car. | **0 car.** |
| **L02@ctx131k** (prefisso riusato) | 96 | 131.103 | 48,590 (banale, solo la domanda) | 1.024 | **24,687** | **40,468** | (0,709 ; 0,434) | 2,14 | length | 4.123 car. | **0 car.** |
| **Aggregato (L01+L02)** | — | — | — | 2.048 | **25,479** | **39,248** | (0,735 ; 0,489) cumulativo* | 2,22 cumulativo* | — | — | **0 car. su entrambi** |

\* Riga cumulativa `common_specu: statistics draft-mtp` a fine corsa (log del server, `-lv 4`), come
prescrive la cella 1. Include i due riscaldamenti banali (2 token ciascuno, accettazione (1.000,1.000)):
peso trascurabile, 4 token su 1.843 totali (0,2%). I valori per-caso in tabella sono le righe
per-richiesta (`slot print_timing ... acc per pos`), esatte e non contaminate dai riscaldamenti.

`draft acceptance` per-richiesta: L01 = 0,65537 (580 accettati / 885 generati); L02 = 0,57128 (545/954).
Nessun caso finito per `stop`: entrambi finiscono per `length`, cioè il budget di 1024 token si esaurisce
dentro il testo finale (mai nel ragionamento, perché è vuoto). **Nessun NaN, nessun errore, nessun
assert** in nessuno dei due log (ricerca case-insensitive `error|exception|nan|fatal|assert|abort`: 0
occorrenze in r1 e in r2).

Riscaldamenti (esclusi dalle metriche, solo controllo): identici fra loro (stessa impronta SHA256),
finiscono per `stop` con 3 token e `content` di 6 caratteri, `reasoning_content` **vuoto**.

### Verifica `reasoning_content` vuoto

Controllo diretto sui quattro file `output/*.reasoning.txt` della corsa r2: tutti e quattro **0 byte**
(`wc -c` conferma). La manopola funziona su questo profilo, non solo sui riscaldamenti banali.

---

## 3. Qualità (rubrica sui due casi liberi)

Entrambi i testi sono **tecnicamente solidi** dove arrivano — ma **entrambi vengono troncati dal budget
di 1024 token prima dell'ultimo punto della rubrica**, un effetto opposto a quello che affliggeva
`--reasoning on`: lì il budget finiva nel pensiero e il testo finale restava vuoto; qui il pensiero è
zero ma la prosa finale è così articolata che 1024 token non bastano a chiuderla.

**L01** (byte/token vs FLOP, MoE su PCIe): definisce correttamente il meccanismo, porta un conto
numerico esplicito e completo con unità (`0,5 GB / 25 GB/s = 20 ms`, `50 token/s`), non afferma che il
calcolo è sempre il collo di bottiglia, risposta in italiano senza domande di chiarimento — **ma il
testo si interrompe a metà frase** ("...saresti limitato dai **2 ms** di") **prima di elencare le tre
misure** richieste dalla rubrica. 4 criteri su 5 soddisfatti, il quinto non raggiungibile per
troncamento.
**Verdetto: NON SUPERATO — buona qualità, troncato dal budget prima del punto conclusivo della rubrica.**

**L02** (LFU decaduta vs LRU per cache esperti): definisce correttamente entrambe le politiche, descrive
con meccanismo esplicito sia il carico in cui LFU-decaduta vince (esperti caldi persistenti, "sticky
popularity" a suo favore) sia quello in cui perde (cambi di contesto rapidi, cold-start di LRU più
veloce), risposta in italiano — **ma si interrompe proprio all'inizio del punto 3** ("Non serve
implementare entrambe le politiche nel motore di inferenza. Il...") **prima di proporre la misura
economica** richiesta dalla rubrica. 4 criteri su 5 soddisfatti, il quinto non raggiungibile per
troncamento.
**Verdetto: NON SUPERATO — stessa causa: ottima struttura, troncato dal budget prima della conclusione.**

Nessun caso è "non giudicabile": entrambi producono testo finale sufficiente a valutare 4 dei 5 criteri
di rubrica; il quinto manca per un limite di budget del banco, non per un difetto della risposta.

(Per la corsa fallita r1: **non giudicabile** — `content_caratteri = 0` su L01 e L02, nessun testo da
valutare.)

---

## 4. RAM e VRAM — l'allarme dichiarato dal mandato

| | r1 (fallita) | r2 (valida per la manopola) |
|---|---:|---:|
| RAM libera minima | **3,45 GiB** | **3,3 GiB** |
| campione minimo, quando | durante L01@ctx131k | durante L01@ctx131k, GPU 94% |
| campioni sotto 4 GiB (su 299/302 totali) | — (non ricontato) | **122** (~41% dei campioni) |
| VRAM usata di picco | — | 11.461 MiB / 12.288 |
| VRAM libera minima | — | **827 MiB** |
| GPU media | — | 96,3% |

Il mandato dichiara esplicitamente: *"a 131k il margine e' piccolo: sotto 4 GB di RAM libera la corsa e'
invalida"*. **Entrambe le corse scendono sotto quella soglia**, e non per un istante isolato: nella
corsa valida (r2) **122 campioni su 299** (~41%, campionati ogni 2 s) durante L01 sono sotto i 4 GiB, con
un minimo di 3,3 GiB. Non è un guasto operativo — nessun OOM, nessun crash, `guasto: nessuno` in
entrambi i riepiloghi, la corsa è arrivata pulita a fine budget — ma **per il criterio di validità
dichiarato dal mandato la misura non lo supera**. Il fatto che r1 (manopola diversa, stesso preset per
il resto) tocchi un minimo quasi identico (3,45 contro 3,3 GiB) dice che il margine di RAM è una
proprietà della configurazione a 131k (contesto 262144, 64 slot, bozza MTP2, `--n-cpu-moe 48`), non
un effetto del ragionamento acceso o spento: spegnere il pensiero non ha peggiorato né migliorato il
quadro di RAM in modo apprezzabile.

**Questo va riportato al registro come un limite aperto**, non risolto qui: il mandato di questa cella
era "una sola corsa" sulla manopola del ragionamento, non un giro su `--n-cpu-moe` o sul numero di
slot per liberare RAM. Non è stato tentato nessun aggiustamento della configurazione per restare dentro
il mandato.

---

## 5. Confronto

### Contro M2 a 32k (stessa bozza, ragionamento ACCESO, contesto diverso — due variabili cambiate insieme, dichiarato)

| | M2 @ 32k (14/9, rag. ACCESO) | N2L131 @ 131k (rag. SPENTO) | delta |
|---|---:|---:|---:|
| t/s insieme libero | 26,224 | 25,479 | **-2,84%** |
| accettazione pos1 / pos2 | 0,766 / 0,553 | 0,735 / 0,489 (cumulativo) | pos2 peggiora |
| mean acc len | 2,323 | 2,22 (cumulativo) | leggermente peggio |

**Non è un A/B pulito**: contesto (32k contro 131k) e ragionamento (acceso contro spento) cambiano
insieme, quindi il -2,84% non è attribuibile a una sola causa. Va letto come "nello stesso ordine di
grandezza", non come una misura di una singola leva.

### Contro il riferimento storico MTP-spento a 131k (13/9, 24,6 t/s — altro albero/binario, dichiarato)

N2L131 (MTP bozza2 ACCESO, 131k, ragionamento spento) = 25,479 t/s, **+3,57%** sul 24,6 t/s del 13/9.
Anche qui: giorni diversi, build potenzialmente diverse, fixture diverse, un solo campione per lato —
**indicativo, non un verdetto**. Non esiste, come dichiarato nel mandato, un riferimento MTP a 131k
sulle fixture di questa cella.

### Aritmetica del ciclo — la seconda posizione supera 0,633?

**No.** La seconda posizione osservata è **0,489** (cumulativo di fine corsa) o **0,434-0,546** per
singolo caso — **sotto** la soglia di pareggio 0,633 determinata nella cella 1, e anzi **più bassa**
della cifra di M2 a 32k con ragionamento acceso (0,553). Per la clausola condizionale del mandato ("se
sì, stima con l'aritmetica cosa darebbe una bozza 1"): **non si applica**, la risposta è no, quindi
nessuna stima di bozza 1 è stata calcolata.

Osservazione qualitativa, non misurata: l'accettazione alla seconda posizione cala ulteriormente al
crescere del contesto (0,553 a 32k → 0,489 a 131k, stessa bozza, sparse FA spenta in questo preset),
coerente con un'attenzione densa più incerta su una finestra più larga. Non è stato isolato il costo
della riga di verifica a 131k in questa cella (servirebbe una cella dedicata con bozza 1 e bozza 2 sulle
stesse fixture lunghe): resta un'apertura, non una misura.

---

## 6. Bozza di voce di registro

> **15 settembre 2026 — fase P7, cella 7: MTP bozza 2, ragionamento spento, contesto lungo 131k.**
>
> *Ipotesi.* Con la bozza MTP a 2 token (M2) e il ragionamento spento, il profilo `lungo_131k`
> (prefill freddo di 131.072 token, poi due decodifiche fino a 1024 token) produce un testo finale
> misurabile (a differenza di `--reasoning on` dove 14/16 casi liberi finivano vuoti nello screening del
> 14/9) e un throughput confrontabile con il riferimento storico MTP-spento a 131k (24,6 t/s).
>
> *File toccati.* Nuovi: `docs/porto/banco_p0/preset_N2L131_p7.json` (due varianti in-place: manopola
> `--reasoning-budget 0` poi corretta a `--reasoning off`, entrambe documentate nel file stesso in
> `nota_manopola_r1`), `docs/porto/p7_speculazione/P7_CELLA7_RAGIONAMENTO_SPENTO_131K_15_SETTEMBRE.md`,
> `docs/porto/p7_speculazione/log/*_N2L131_*`. Rigenerato (non modificato a mano)
> `docs/porto/banco_p0/fixtures/fixtures_manifest.json` con `sigilla_fixture.py --rifai` (implicito:
> file cancellato e ricreato dentro la stessa sessione server) per includere `ctx131k` su L01/L02, già
> presente in `casi.json` ma non ancora sigillato; backup del manifest precedente salvato come
> `fixtures_manifest.json.bak_pre_ctx131k_L01L02_15set`. Nessun sorgente, nessuna build, nessun
> lanciatore quotidiano toccato.
>
> *Configurazioni.* Binari `qwen38_clean\build\bin` (gli stessi di M2/M1/preset_A). Preset
> `preset_N2L131_p7.json`, identico a `preset_M2_p7.json` (bozza MTP 2 token, n-grammi spenti, 64 slot,
> sparse FA spenta, contesto 262144, `-b`/`-ub` 2048, `-np 1`, greedy seed 1234) tranne il ragionamento:
> tentativo 1 (FALSIFICATO) `--reasoning on --reasoning-preserve --reasoning-budget 0`; tentativo 2
> (VALIDO per la manopola) `--reasoning off`. Profilo del banco `lungo_131k`, budget `screening` = 1024.
>
> *Run validi / invalidi.* Due corse: `20260915_102009_P7_p7_n2l131_ragionamento_spento_r1`
> (**INVALIDA per l'obiettivo della cella** — la manopola non spegne il ragionamento sui casi reali,
> `content_caratteri = 0` su L01 e L02) e `20260915_103715_P7_p7_n2l131_ragionamento_spento_r2`
> (**valida per la manopola, con riserva**: `reasoning_content` vuoto su tutti i casi verificato, ma la
> RAM libera minima durante L01 è 3,3 GiB, sotto la soglia di 4 GiB dichiarata dal mandato come limite
> di validità — non un guasto, un margine insufficiente per il criterio dato). Nessun NaN, nessun
> errore, nessun assert in nessuna delle due corse. Nessun processo residuo a fine sessione (verificato
> due volte: dopo r1 e dopo r2).
>
> *Risultato e limite.* r2: t/s insieme libero = **25,479** (L01 26,270 / L02 24,687), **39,248
> ms/token accettato** aggregato, accettazione per posizione (0,735 ; 0,489) cumulativa — **sotto la
> soglia di pareggio 0,633** della seconda posizione (cella 1), quindi nessuna stima di bozza 1 a parità
> (clausola condizionale non applicabile). Qualità: entrambi i casi liberi **NON SUPERANO** la rubrica,
> non per errori di contenuto ma perché il budget di 1024 token tronca il testo prima dell'ultimo punto
> richiesto in entrambi. Limiti dichiarati: una sola replica per manopola valida; RAM sotto soglia
> (§4); confronto con M2@32k a due variabili cambiate insieme (§5); nessun riferimento MTP a 131k
> preesistente su queste fixture; la causa esatta del fallimento di `--reasoning-budget 0` sui prompt
> lunghi non è stata indagata oltre il log (ipotesi qualitativa in §1, non falsificata).
>
> *Decisione.* **`--reasoning off` è la manopola da usare per spegnere il ragionamento su questo
> binario/modello**; `--reasoning-budget 0` va evitato per questo scopo finché non si capisce perché
> fallisce sui prompt lunghi (rischio concreto: sembra funzionare sui casi banali e inganna). Il
> numero di velocità (25,479 t/s a 131k, ragionamento spento, bozza 2) è **utilizzabile come primo
> punto**, ma con la riserva di RAM dichiarata al §4: non è una misura "pulita" secondo il criterio del
> mandato.
>
> *Prossima azione.* Se serve un numero di RAM pulito a 131k, la cella successiva deve toccare la
> configurazione (slot, `--n-cpu-moe`, o il contesto) per riportare il margine sopra i 4 GiB — fuori
> mandato qui. Se invece si vuole isolare l'effetto del contesto sull'accettazione alla seconda
> posizione, serve una cella con bozza 1 e bozza 2 sulle stesse fixture `ctx131k`, a ragionamento
> spento, per separare "contesto lungo" da "ragionamento spento" nel confronto del §5. Indagare, se
> interessa capire il meccanismo e non solo aggirarlo, perché `--reasoning-budget 0` si attiva (log lo
> conferma) ma non produce l'effetto atteso sui prompt lunghi.

---

## 7. Artefatti

| dove | che cosa |
|---|---|
| `docs/porto/banco_p0/preset_N2L131_p7.json` | preset finale (manopola valida `--reasoning off`; il tentativo fallito con `--reasoning-budget 0` è documentato dentro il file in `nota_manopola_r1`, non in un file separato) |
| `docs/porto/banco_p0/fixtures/fixtures_manifest.json` | rigenerato con `ctx131k` su L01/L02 (28 casi); backup del precedente in `fixtures_manifest.json.bak_pre_ctx131k_L01L02_15set` |
| `docs/porto/p7_speculazione/log/blocco_N2L131_r1_FALLITO_reasoning_budget0.txt` | uscita completa di `avvia_blocco.ps1` per il tentativo fallito |
| `docs/porto/p7_speculazione/log/blocco_N2L131_r2_VALIDO_reasoning_off.txt` | uscita completa per la corsa valida |
| `docs/porto/p7_speculazione/log/riepilogo_N2L131_r{1,2}_*.txt` | riepiloghi del banco con le impronte |
| `docs/porto/p7_speculazione/log/results_N2L131_r{1,2}_*.jsonl` | una riga per richiesta: timings del server, `draft_n`, `draft_n_accepted`, impronte, conteggi caratteri |
| `docs/porto/p7_speculazione/log/server_estratto_N2L131_r{1,2}_*.txt` | righe `n_rs_seq`, `graph nodes`, `print_timing`, `acc per pos`, `common_specu`, `common_reaso` estratte dal log del server |
| `D:\ds4_work\banco_p0_run\20260915_102009_P7_p7_n2l131_ragionamento_spento_r1` | corsa r1 completa (fallita per la manopola) |
| `D:\ds4_work\banco_p0_run\20260915_103715_P7_p7_n2l131_ragionamento_spento_r2` | corsa r2 completa (valida per la manopola, RAM sotto soglia) |
