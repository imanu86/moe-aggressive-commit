#!/usr/bin/env bash
# ============================================================================
# tutto-dentro STEP 0-2 — harness di misura (warm leva-RAM + cache + SPEX)
# Da lanciare in WSL: wsl -d Ubuntu-24.04 -e bash scripts/tutto_dentro_measure.sh
# ZERO codice C: usa SOLO env/flag VERIFICATI dallo scoping (docs/BUILD_TUTTO_DENTRO_SPEC.md).
# Fa: baseline + ogni leva in isolamento, mediana-di-3 (rumore +/-50%), A/B SPEX corretto.
# ============================================================================
set -u

# ---------- CONFIG (CONFERMA questi valori prima di lanciare) ----------------
DS4_DIR="/root/ds4"                       # clone ds4 (DEVE essere su branch ds4-flash-unified, vedi SETUP sotto)
DS4_BIN="$DS4_DIR/ds4"                     # binario compilato (o ds4-cuda: CONFERMA)
MODEL="/root/models/ds4-2bit.gguf"        # CONFERMA il path/nome reale del gguf 2-bit
SPEX_FILE="/mnt/c/Users/imanu/source/repos/moe-aggressive-commit/runs/spex/spex_model/ds4flash_d2_nextlayer.spex"  # CONFERMA
PROMPT_FILE="$DS4_DIR/prompt_bench.txt"   # un prompt FISSO reale (es. il tuo template Segnali, o il website-gen)
NGEN=200                                  # -n fisso
PREFILL=512                               # --prefill-chunk
CACHE_GB=5                                # --ssd-streaming-cache-experts <G>GB  (tara dal log)
RESERVE_GB=5                              # DS4_CUDA_STREAMING_EXPERT_CACHE_RESERVE_GB (su 12GB >6 e' troncato)
REPS=3                                    # mediana-di-3
OUT="$DS4_DIR/../out_tuttodentro/$(date -u +%Y%m%dT%H%M%SZ)"   # dir timestampata PER-RUN (regola playbook)

# >>> IL TUO COMANDO DI LANCIO ds4 <<<  (incolla la TUA invocazione abituale; usa $MODEL $PROMPT_FILE $NGEN $PREFILL)
# Deve stampare a fine generazione la riga con i tok/s. NON aggiungere env qui: li setto io per-profilo.
run_ds4() {
  # ESEMPIO da adattare al tuo daily-driver:
  "$DS4_BIN" --model "$MODEL" -f "$PROMPT_FILE" -n "$NGEN" --prefill-chunk "$PREFILL" "$@"
}
TPS_REGEX='([0-9]+\.[0-9]+)[[:space:]]*(tok/s|tokens/s|t/s)'   # regex per estrarre i tok/s dal log (adatta se serve)
# ----------------------------------------------------------------------------

# ---------- SETUP una-tantum (fallo A MANO, non lo faccio io per non toccare /root/ds4 condiviso) -----
#   cd /root/ds4 && git fetch && git checkout -b ds4-flash-unified spex/trace-ext   # (@7a93e3b)
#   make cuda CUDA_ARCH=sm_86 -j    # BUILD
#   .wslconfig (Windows): [wsl2] autoMemoryReclaim=disabled  -> wsl --shutdown   (per leva-RAM)
# ---------------------------------------------------------------------------------------------------

mkdir -p "$OUT"
echo "OUT=$OUT"

preflight() {
  local ok=1
  [ -x "$DS4_BIN" ]     || { echo "!! binario ds4 non trovato/eseguibile: $DS4_BIN"; ok=0; }
  [ -f "$MODEL" ]       || { echo "!! modello non trovato: $MODEL"; ok=0; }
  [ -f "$SPEX_FILE" ]   || { echo "!! .spex non trovato: $SPEX_FILE (SPEX-off girera' comunque)"; }
  [ -f "$PROMPT_FILE" ] || { echo "!! prompt non trovato: $PROMPT_FILE"; ok=0; }
  git -C "$DS4_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null | grep -q ds4-flash-unified \
     || echo "!! ATTENZIONE: /root/ds4 non e' su ds4-flash-unified (fai il SETUP sopra)"
  nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null | head -1
  [ "$ok" = 1 ] || { echo "PREFLIGHT FALLITO — sistema la CONFIG e ritenta."; exit 1; }
}

# esegue run_ds4 REPS volte con l'env passato, estrae i tok/s, stampa la MEDIANA
run_median() {  # $1=nome $2=env-string  (resto = flag extra a run_ds4)
  local name="$1"; local envs="$2"; shift 2
  local vals=()
  for i in $(seq 1 "$REPS"); do
    local log="$OUT/${name}_r${i}.log"
    ( eval "$envs"; run_ds4 "$@" ) >"$log" 2>&1
    local tps; tps=$(grep -oE "$TPS_REGEX" "$log" | grep -oE '[0-9]+\.[0-9]+' | tail -1)
    echo "   [$name r$i] tok/s=${tps:-NA}  (log: $log)"
    [ -n "${tps:-}" ] && vals+=("$tps")
  done
  local med
  med=$(printf '%s\n' "${vals[@]}" | sort -n | awk '{a[NR]=$1} END{print (NR? a[int((NR+1)/2)] : "NA")}')
  echo "== $name : MEDIANA tok/s = $med (n=${#vals[@]}/$REPS)" | tee -a "$OUT/SUMMARY.txt"
}

preflight

WARM="export DS4_CUDA_KEEP_MODEL_PAGES=1; export DS4_CUDA_NO_DIRECT_IO=1"
CACHEFLAGS=(--ssd-streaming --ssd-streaming-cache-experts "${CACHE_GB}GB")
CACHEENV="export DS4_CUDA_STREAMING_EXPERT_CACHE_RESERVE_GB=$RESERVE_GB"

echo "===== P0 STOCK (baseline) ====="        | tee -a "$OUT/SUMMARY.txt"
run_median "P0_stock" "true"

echo "===== P1a WARM leva-RAM ====="           | tee -a "$OUT/SUMMARY.txt"
run_median "P1a_warm" "$WARM"

echo "===== P1b WARM + CACHE ====="            | tee -a "$OUT/SUMMARY.txt"
run_median "P1b_cache" "$WARM; $CACHEENV" "${CACHEFLAGS[@]}"

echo "===== P2 SPEX OFF (A) ====="             | tee -a "$OUT/SUMMARY.txt"
run_median "P2_spex_off" "$WARM; $CACHEENV; export DS4_SPEX_MARKOV_FILE=$SPEX_FILE; export DS4_SPEX_DISABLE_PREFETCH_NEXT_LAYER=1" "${CACHEFLAGS[@]}"

echo "===== P2 SPEX ON (B) ====="              | tee -a "$OUT/SUMMARY.txt"
run_median "P2_spex_on"  "$WARM; $CACHEENV; export DS4_SPEX_MARKOV_FILE=$SPEX_FILE; export DS4_SPEX_PREFETCH_NEXT_LAYER=1; export DS4_SPEX_PREFETCH_PROFILE=1" "${CACHEFLAGS[@]}"

# --- correttezza-neutralita' SPEX: l'OUTPUT deve essere IDENTICO ON vs OFF (predice loading non gating) ---
echo "===== SPEX A/B byte-identity check =====" | tee -a "$OUT/SUMMARY.txt"
# estrae il testo generato (adatta il filtro se ds4 antepone log): confronto grezzo dei log meno le righe di timing
diff <(grep -vE "$TPS_REGEX|^ds4:" "$OUT/P2_spex_off_r1.log") \
     <(grep -vE "$TPS_REGEX|^ds4:" "$OUT/P2_spex_on_r1.log") >/dev/null 2>&1 \
  && echo "OK: output SPEX ON == OFF (correttezza-neutrale)" | tee -a "$OUT/SUMMARY.txt" \
  || echo "!! DIFF: output SPEX ON != OFF -> e' un BUG, non una misura. Ispeziona i log." | tee -a "$OUT/SUMMARY.txt"

echo; echo "FATTO. Riassunto: $OUT/SUMMARY.txt"
echo "Delta da riportare: P1a-P0 (warm), P1b-P1a (cache), P2on-P2off (SPEX). Hit prefetch SPEX nel log P2_spex_on (PROFILE=1)."
