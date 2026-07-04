# HANDOFF 3 — tassonomia V3.1 unificata + kickoff fine-tuning (2026-07-02)

> Ripresa da chat nuova: questo doc + la memory `project_moe_aggressive_commit.md` (log dettagliato)
> bastano. Precedente: `HANDOFF_2_bonusx_ai.md` (pivot). Qui: cosa è LIVE, cosa è il prossimo passo.

## 0. TL;DR — stato (tutto verificato live)
1. **Sistema retrieval `promo_recall` COSTRUITO E LIVE**: `bonus-kb/bonusx-kb/retrieval/` (chunker,
   BM25 self-contained, matrice e5-base, ricerca ibrida RRF, ~35 ms/query in-process).
   - **Railway**: `https://promo-recall-production.up.railway.app` (progetto `promo-recall`, API-key nei
     service env). **Plancia**: `dev.cgctrl.app/recall` sezione "Promo Recall" (function proxy + SSO).
2. **TASSONOMIA V3.1 UNIFICATA END-TO-END** (era il drift §6: 3 vocabolari, 89% KB mislabeled):
   grammatica `MECCANICA{1,2}[_GIOCATO][_BONUS]`, REAL implicito (eccezione DEPOSITO_REAL/FUN).
   SSOT: **`bonus-kb/bonusx-kb/retrieval/TAXONOMY_SSOT_V3.md`** + mapper `taxonomy_v3.py`.
   - KB rietichettata V3.1 + redeploy ✓ · runner BILINGUE (`cgc-ia-pipeline@3b2b4bf`: TECH_FIX promuove
     V2→V3.1, `derive_bonus_type` dal suffisso, +18 famiglie, gate esteso) ✓ · TS compat+dropdown puliti
     (`promo-platform@254a168`+`3cadf8f`, Netlify auto) ✓. bonus_type INVARIANTE → EV invariato.
3. **Fase 4 (few-shot dinamici)**: `kb_block.py` RAFFINATO (ibrido def-statica+esempi, routing
   no-esempi SUPERQUOTA+CONDIZIONATA*, anti-leakage, ponte `LEGACY_TO_V3`). Flag runner
   `USE_PROMO_RECALL_KB` **OFF** — verdetto "GO-CON-SHADOW-RUN" (gate: shadow-run per-campo prima del flip).
4. **Fase 5 (fine-tuning) AVVIATA**: recon dati fatto. Supabase è THIN (385 drafts, 7 correzioni) →
   **TRAIN = KB (1468 promo V3.1) in formato RAFT** (promo + vicini da promo_recall → JSON gold);
   **EVAL = i 385 drafts reali** (140 review_required = casi difficili). Dataset delegato ad agente
   (output atteso in `retrieval/ft/`: `build_raft_dataset.py`, `raft_train.jsonl`, `raft_eval.jsonl`).

## 1. Prossimi passi (in ordine)
1. **Dataset RAFT** — se l'agente ha finito, verificare `retrieval/ft/` (stats, anti-leakage: vicini
   con `exclude_id`=se-stesso e senza promo dell'eval-set nei blocchi train).
2. **QLoRA su RunPod A100 80GB** (pod attivo, vedi memory handoff-comfyui) — il 30B NON entra nella
   3060 per training; inferenza resta locale. ⚠️ **includere il ROUTER/gate nei `target_modules`**:
   senza, il routing resta diffuso e l'expert-parking non si riapre. Modello: Qwen3-30B-A3B (prod).
3. **Eval qualità** su drafts reali (Supabase ref `ommcxachjukbbighzpqc`, service-key in
   `C:\Users\imanu\llama\.env.local_runner`; l'URL NON è in env → usare il ref hardcoded).
4. **LA domanda aggressive-commit**: coverage/committed_fraction FT-vs-base su prompt BonusX —
   script esistenti `scripts/validate_probe_qwen3.py` + memmap `D:/qwen3_memmap`. Se concentra →
   parking SSD → VRAM per modello più grosso o più contesto. (Il vecchio "no" era sul workload, non sui pesi.)
5. (Qualità, dopo) rewrite 8 prompt → V3.1 nativo + giocato fine + `bonus_components` (EV=Σ, patch TS)
   + regola NON_PROMO/fasce-orarie nel triage; fold DEPOSITO_FUN_SPORT; togliere i ponti alias.
6. (Fase 4 flip) shadow-run con metrica per-campo → `USE_PROMO_RECALL_KB=1` in `.env.local_runner`.

## 2. Path e fatti chiave
| Cosa | Dove |
|---|---|
| Retrieval + SSOT + docs | `C:\Users\imanu\source\repos\bonus-kb\bonusx-kb\retrieval\` (TAXONOMY_SSOT_V3.md, kb_block.py, taxonomy_v3.py, INGEST_CONTRACT.md, TODO_*.md) |
| KB chunks V3.1 | `retrieval/out/chunks.jsonl` (backup `.v1bak`/`.v2bak`); emb.npy 2595×768 |
| Runner (prod .10) | `C:\Users\imanu\llama\pipeline\local_runner_v2.py` = repo cgc-ia-pipeline main |
| TS piattaforma | `C:\Users\imanu\source\repos\promo-platform` (Netlify **autodeploy da main**!) |
| Plancia | `C:\Users\imanu\source\repos\cgc-plancia` (NO autodeploy → `netlify deploy --prod` con PAT) |
| Vault segreti | `C:\Users\imanu\.cgc\` (decrypt: SYSTEM_MAP §13; token Railway/Netlify/GitHub dentro important.txt) |
| recall mappe ecosistema | `node C:\Users\imanu\source\repos\cgc-infra\src\server.js recall "..."` (CLI) |
| Modelli scaricati | Qwen3-30B bf16 (cache HF) + memmap `D:/qwen3_memmap` + 235B GGUF `D:/models/qwen3-235b` |

## 3. Gotchas (impari a tue spese, evitali)
- **Railway API dietro Cloudflare**: urllib default → 403 err 1010; serve User-Agent browser. Token
  Railway = scoped "Projects" (whoami CLI fallisce, GraphQL+`railway up` con project-token funzionano).
- **Netlify env API**: campo `scopes` vietato su free plan → ometterlo.
- **kb_block ponte**: il legacy-dict va controllato PRIMA di `parse_v3` (PLAYBACK_FUN/CASHBACK
  parserebbero come V3 validi con semantica diversa).
- **Runner**: drain-then-exit (codice nuovo al prossimo wake-cycle; runner VIVO in RAM = codice vecchio
  fino a idle-exit). Prompt = prefix-cached (`cache_prompt=True`) → snellirli NON risparmia token.
- **Vision v2 ingest**: `parsed_v2_vision.jsonl` non ha `book` → chunker ripiega su channel_slug (bug noto).
- I file `family_DEPOSITO_FUN_SPORT.json` e copie-gemello V3.1 in kb_v2 sono transitori (rimuovere al
  rewrite prompt). TS: `TECHNIQUES` = validazione (legacy ok), `TECHNIQUES_CANONICAL` = dropdown.
