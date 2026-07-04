# Rischi e Modalità di Fallimento

Ordinati per severità sul *verdetto scientifico*. Ogni rischio ha: sintomo, perché morde, e la
mitigazione **già prevista nel disegno** (sezione di `00_architecture.md` o file dello scaffold).

---

## R1 — "Regge a contesto corto, collassa a contesto lungo" ⚠️ (il principale)

**Sintomo.** A 1k–4k token il drop è < 2 %; a 16k–64k l'accuratezza crolla, ma una media
sui prompt corti lo nasconde.

**Perché morde.** Due cause si sommano:
1. A contesto lungo il routing diventa **meno locale** → il working set stimato in warm-up corto è
   sotto-dimensionato → miss_rate sale proprio dove non guardi.
2. Fallimenti di **attention a lungo raggio** (indexed/long-context) sono invisibili su task corti
   che non attendono a contesto distante.

**Mitigazione (nel disegno).**
- Validazione come **curva vs ctx**, mai media (§8, §10).
- **Due** meccanismi di crescita del contesto: padding-distrattori *e* probe di retrieval
  needle-in-haystack (§8.2) — il secondo forza l'attention a lungo raggio.
- **Protocollo di falsificazione** (§12): promozione solo se < 2 % su *tutte* le ctx.
- Diagnostico **miss_rate vs ctx** in overlay alla curva di accuratezza: se divergono, è R1.

**Residuo.** Se il modello non ha un range "max" abbastanza grande, R1 può restare latente oltre il
testato → riportare esplicitamente la ctx massima coperta e NON estrapolare.

---

## R2 — Workload a bassa località (la scommessa non si applica)

**Sintomo.** Entropia d'uso degli expert alta / `N_eff` ≈ `n_total` → nessun working set piccolo →
il commit aggressivo non ha spazio (curva accuratezza-vs-VRAM ripida ovunque).

**Perché morde.** La tesi vale *per workload ad alta località*. Su task diversificati la
distribuzione è quasi uniforme e tagliare expert = perdere accuratezza subito.

**Mitigazione.**
- La **concentrazione empirica** è una metrica riportata (§7), non un assunto: misuriamo *quanto*
  è locale il workload prima di committare.
- Caratterizziamo il guadagno **in funzione della concentrazione**, così "bassa località = poco
  guadagno" diventa un *risultato atteso e quantificato*, non un fallimento.
- Scelta dei task di validazione esplicitamente **ad alta località** (coding ripetitivo); un task
  "control" a bassa località come contro-prova.

---

## R3 — Costo del fallback sui miss (latenza PCIe)

**Sintomo.** Con `fetch-lossless`, l'accuratezza è perfetta ma la latenza per token esplode se il
miss_rate è alto; il "guadagno VRAM" è reale ma inutilizzabile.

**Perché morde.** Fetch RAM→VRAM su PCIe 4.0 ×16 ha banda finita; un expert per layer per token in
miss serializza male.

**Mitigazione.**
- Latenza è **metrica registrata** per ogni cella, non ignorata (§9).
- `fetch-lossless` serve da **baseline latenza-pura**: rende esplicito il prezzo in tempo del
  taglio VRAM senza perdita di accuratezza.
- Prefetch col predittore pre-attention noto (riuso, non ricerca) come opzione per ammortizzare.

---

## R4 — Overhead del predittore / della stima

**Sintomo.** Il tempo di warm-up + stima working set + gestione residenza mangia il guadagno.

**Perché morde.** Su sessioni corte l'ammortamento del warm-up non avviene.

**Mitigazione.**
- Convergenza del working set tracciata (§7): se serve poco warm-up, il costo è ammortizzato presto.
- Il warm-up è **una tantum per sessione** (assunzione di località): riportiamo il break-even in
  numero di token oltre cui il commit conviene.

---

## R5 — Validatore debole (segnale non davvero binario/deterministico)

**Sintomo.** Unit test troppo permissivi, non-determinismo nel decoding, flakiness → il "drop < 2 %"
è rumore.

**Perché morde.** Se il segnale di correttezza è fragile, l'intera superficie è inaffidabile.

**Mitigazione.**
- Greedy (T = 0) + seed fissi + prompt fissi (§8.1).
- `tests/test_validator_determinism.py`: stesso input → stesso verdetto, gate del repo.
- Suite di unit test **nascosta** e con copertura di edge case; doppio binario (codegen +
  closed-form) per triangolare.
- Sandbox di esecuzione del codice generato isolata e con timeout (no side-effect, no rete).

---

## R6 — Contabilità VRAM ingannevole (KV cache maschera il guadagno)

**Sintomo.** A 64k il "guadagno VRAM" sembra sparire — ma è la **KV cache** che cresce, non gli expert.

**Mitigazione.** Riportare `VRAM_kv` e `VRAM_expert` **separati** (§11). Il claim del progetto è sul
secondo termine.

---

## R7 — Confondenti nello sweep di sparsità

**Sintomo.** Due modelli a sparsità diversa differiscono anche per dati di training, dimensione,
tokenizer → attribuire la differenza alla sola sparsità è scorretto.

**Mitigazione.** Oltre al confronto *between-model*, lo **sweep del top-k within-model** (§3, Asse B)
isola l'effetto della sparsità a parità di pesi. Riportare entrambi e dichiarare i limiti.

---

## R8 — `hard-drop` con reroute altera il routing a valle

**Sintomo.** Rerouting su residente più vicino cambia il path di attivazione → la traccia di warm-up
non è più valida e la stima del working set si auto-conferma in modo distorto.

**Mitigazione.** Per `hard-drop`+reroute, ri-tracciare sotto policy (§9, nota scorciatoie); oppure
preferire `hard-drop`=zero-contributo (più pulito da analizzare) come variante primaria.
