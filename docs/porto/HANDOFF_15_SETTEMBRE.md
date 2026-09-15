# Handoff 15 settembre 2026 — punto di ingresso

Scritto a fine giornata, a crediti esauriti. Sostituisce come ingresso [HANDOFF_14_SETTEMBRE.md](HANDOFF_14_SETTEMBRE.md), che resta valido per il dettaglio delle giornate 14-15/9. Registro delle decisioni D01-D44: [REGISTRO_CPU_GPU_14_SETTEMBRE.md](REGISTRO_CPU_GPU_14_SETTEMBRE.md). Stato macchina a fine sessione: nessun server attivo, porta 8100 libera, `bin_prod` e lanciatore quotidiano MAI toccati.

## 1. I due risultati che contano, al punto operativo (contesto ~131k, KV 250k)

| Metrica a 131k | Riferimento (preset sperimentale, 14/9) | Candidato | Guadagno | Stato |
|---|---:|---:|---:|---|
| **Prefill freddo** (131.072 token) | 252 t/s | **397 t/s** (X4) | **+57%** | aghi 5/5, decode invariato; i 400 NON dichiarati (−0,75%) |
| **Decode**, MTP spento | 26,38 t/s | 27,25 t/s (V3) | +3,3% | lossless, testo identico; SOTTO la soglia del 5% (D42): non si valida ne' si promuove da solo |

Nessuno dei due e' in produzione. La promozione richiede la fase P6 del protocollo e l'accordo esplicito dell'utente sulla procedura di cambio (D44).

## 2. Regole dell'utente in vigore (non rinegoziabili)

- **D33** — Il punto operativo e' ~100k di contesto con KV 250k. Misure a contesto corto o a 32k non decidono nulla. Profilo del banco: `lungo_131k`, `prefill_131k`, `aghi_131k`.
- **D14** — Prima il candidato B; il controllo A solo se B non vince.
- **D42** — **Sotto il 5% di guadagno non si fa niente**: niente celle, validazioni o promozioni. "E' inutile sprecare token e giorni per qualcosa che sposta di 1 token al secondo."
- D01 — Pesi originali; IQ1 escluso; Q6_K→Q4_K sui residenti densi SALTATO per rischio qualita' (15/9).

## 3. Configurazione del candidato di prefill X4 (pronta)

Binari: `D:\ds4_work\p11_work\build\bin` = snapshot P0 + patch in ordine: `docs/porto/p8_riga_verifica/p8_cumulativa.patch` (bias QSA residente), `docs/porto/p10_token_singolo/p10_cella2.patch` (igiene sync), `docs/porto/p10_token_singolo/p10_cella3.patch` (occupazione kernel IQ2_S), `docs/porto/p11_prefill/p11.patch` (ubatch a scaletta). Applicare con `patch -p1 --binary`.

```
-b 12288 -ub 4096
QWEN4EXP_SPARSE_FA=1  QWEN_GDN_TILED=1  QWEN_PREFETCH_EXPERTS=1
QWEN_PREFILL_UBATCH_DEEP=81920:3072,114688:2048
```

Preset del banco: `docs/porto/banco_p0/preset_X4_p11.json`. Documenti: [P11_PREFILL_131K_15_SETTEMBRE.md](p11_prefill/P11_PREFILL_131K_15_SETTEMBRE.md), [P11_CELLA2_MASCHERE_15_SETTEMBRE.md](p11_prefill/P11_CELLA2_MASCHERE_15_SETTEMBRE.md).

Da dove viene il +57%: sparse FA a teste 256 (+17%, paga solo in profondita'), batch 3072 invece di 2048 (+12%), GDN a tile (+1,6%), staging asincrono degli esperti (+12%, si spegneva da solo in fondo per VRAM), ubatch ristretto in profondita' per lasciare 1,4 GiB allo staging, `-b 12288` divisibile per 4096/3072/2048 (+2%). Batch 4096 fisso CROLLA (paginazione WDDM: la workspace dell'indicizzatore QSA cresce di ~242 byte per coppia token×cella). Le patch GDN e staging di Codex del 13/9 erano gia' nei binari.

## 4. Cosa e' chiuso con prova (non riaprire)

| Pista | Esito | Dove |
|---|---|---|
| Esperti sulla CPU (riga principale) | −1,6% a 8 strati, −5,9% a 24: chiusa (D18) | p3_uno_strato, p4_costo, p4_estensione |
| Esperti CPU sulle sole righe di bozza MTP | negativa a 2/3/4/6 thread (D31); trovato e corretto un bug del descrittore (D29) | p7_speculazione celle 4-6 |
| Bozza MTP a 2-3 token | −4% a 32k, −11% a 131k; 3 token abortisce (assert) | P7 cella 1, P8 |
| Testa MTP non condivisa | accetta 0,780 contro 0,785 (D23) | P7 cella 2 |
| Ragionamento spento per alzare l'accettazione | scende (0,735/0,489) (D34); `--reasoning-budget 0` non spegne, serve `--reasoning off` | P7 cella 7 |
| Prefetch degli esperti durante la testa | nulla e' conoscibile, finestra insufficiente (D24) | P7 cella 3 |
| Divario dei colpi di cache 41%/75% | FALSIFICATO da Codex il 13/9 (75,55% reale) (D19) | RIPRESA_CACHE_13_SETTEMBRE_CODEX |
| Teste MTP riaddestrate su HF/GitHub | non esistono per Flash-Next; dzannotti = stessa testa riquantizzata | SCANDAGLIO_TESTE_MTP_15_SETTEMBRE |
| MTP a 131k con la testa spedita | −0,5% contro spento; +1,8% con la leva B: piatta | P8 |
| Maschere F32 non materializzate (A1) | la riserva dell'allocatore non scende: non paga | P11 cella 2 |

## 5. Il tetto del decode a 131k (P9, D37)

Un token legge 5,11 GiB obbligati (densi Q6_K 2,68 GiB, esperti in cache, 168 MiB dal PCIe): **pavimento dei byte 21,9 ms/token**. I 50 t/s = 20 ms stanno sotto il pavimento: **non stanno in 3060 + questo GGUF**. Scala onesta: 26,4 oggi → 27,25 lossless → ~31 con Q4_K sui densi (saltata) → ~33 con tutto. Anatomia: [P9_ANATOMIA_131K_15_SETTEMBRE.md](p9_anatomia_131k/P9_ANATOMIA_131K_15_SETTEMBRE.md). Per i 50 serve un cambio strutturale: meno byte per token (modello o quantizzazione) o piu' banda (VRAM).

## 6. Cosa resta aperto, sopra la soglia del 5%

1. **Validazione P6 e promozione del candidato di prefill X4** (+57%): cinque coppie abbinate a 131k, aghi e casi strutturati, 30 minuti di stabilita' (annullamenti, secondo turno, cambio taglia, prefill/decode, memoria che torna), rollback provato, poi le DLL che differiscono in `bin_prod` e le env nel lanciatore. ~3 ore di macchina. Richiede il si' dell'utente.
2. **Prefill a 250k** (tetto KV dell'utente): fixture da costruire (il filler e' in `banco_p0/fixtures/`), una corsa da ~12 minuti; probabile un gradino in piu' nella scaletta.
3. **Speculazione**: nulla sopra soglia con la testa attuale. Una testa riaddestrata alla ricorsione (FastMTP via `vllm-project/speculators`, su pod) vale forse +5-10% a 131k solo se la riga di verifica (20 ms a 131k) scende; non prima.

## 7. Strumenti e riferimenti

- Banco P0: `docs/porto/banco_p0/` (`avvia_blocco.ps1`, `banco_p0.py` profili `fumo`, `solo_libero`, `lungo_131k`, `prefill_131k`, `aghi_131k`; `aggrega.py`); corse in `D:\ds4_work\banco_p0_run\`; rumore fra repliche a 131k 0,15 ms/token; cancello di adozione 0,5 ms.
- Riferimenti a 32k (solo per rumore e impronte): spento 24,44; MTP bozza 1 28,66.
- Alberi: snapshot immutabile `D:\ds4_work\p0_snapshot_20260914`; copie di lavoro `D:\ds4_work\p3_work` (esperti CPU, chiusa), `p8_work` (lossless decode), `p11_work` (prefill, = p8 + p11.patch). Produzione `qwen38_clean\bin_prod` intatta; sperimentale originale `qwen38_clean\build\bin`.
- Digest delle chat Codex del 13/9: [DIGEST_CHAT_CODEX_13_SETTEMBRE.md](DIGEST_CHAT_CODEX_13_SETTEMBRE.md). Leggere sempre i `*_CODEX.md` prima di aprire un fronte.
- Regole di metodo imparate: contatori del ramo oltre alle impronte (il ramo puo' non partire con testo identico); un banco che esercita solo la riga 0 non valida un descrittore multi-riga; mai testare una corsia solo senza MTP; una lettura di memoria mappata da kernel costa 1,1 µs; RAM libera minima da registrare (sotto 4 GB il decode crolla); stimare il tetto dal profilo PRIMA di costruire.
