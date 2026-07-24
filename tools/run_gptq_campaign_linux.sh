#!/usr/bin/env bash
# Resumable 40-layer DS4 expert GPTQ campaign for Linux CPU pods.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CAPTURES_DIR=""
TEACHER_GGUF="/workspace/ds4-2bit.gguf"
OUT_DIR="/workspace/gptq_campaign"
BONSAI_DIR="$SCRIPT_DIR/../c7_bonsai"
if [[ ! -d "$BONSAI_DIR" && -d "$SCRIPT_DIR/../../c7_bonsai" ]]; then
  BONSAI_DIR="$SCRIPT_DIR/../../c7_bonsai"
fi
JOBS=40
MIN_SAMPLES=200
DEVICE="cpu"
CXX_BIN="${CXX:-g++}"
KEEP_WORK=0
PLAN_ONLY=0

usage() {
  cat <<'EOF'
Usage:
  tools/run_gptq_campaign_linux.sh CAPTURES_DIR [options]

Options:
  --teacher GGUF       Primary DS4 GGUF (default: /workspace/ds4-2bit.gguf)
  --out DIR            Campaign output (default: /workspace/gptq_campaign)
  --bonsai-dir DIR     Directory containing extract_expert_shard.py and gptq_q1.py
  -P, --jobs N         Concurrent experts for xargs (default: 40)
  --min-samples N      Minimum deduped rows (default: 200)
  --device DEVICE      gptq_q1.py device (default: cpu)
  --cxx PATH           GNU-compatible C++ compiler (default: $CXX or g++)
  --keep-work          Retain shard/calibration/FP32 teacher intermediates
  --plan-only          Discover eligible layer/expert tasks, then stop
  -h, --help           Show this help

Every matching {prefix}.L{3..42}.manifest.json is passed as a repeated
--trace argument. Completed gate/up/down Q1 NPZs are skipped on rerun.
EOF
}

if (($# > 0)) && [[ "$1" != -* ]]; then
  CAPTURES_DIR="$1"
  shift
fi
while (($#)); do
  case "$1" in
    --teacher) TEACHER_GGUF="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --bonsai-dir) BONSAI_DIR="$2"; shift 2 ;;
    -P|--jobs) JOBS="$2"; shift 2 ;;
    --min-samples) MIN_SAMPLES="$2"; shift 2 ;;
    --device) DEVICE="$2"; shift 2 ;;
    --cxx) CXX_BIN="$2"; shift 2 ;;
    --keep-work) KEEP_WORK=1; shift ;;
    --plan-only) PLAN_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$CAPTURES_DIR" ]] || { echo "CAPTURES_DIR is required" >&2; usage >&2; exit 2; }
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo "--jobs must be positive" >&2; exit 2; }
[[ "$MIN_SAMPLES" =~ ^[1-9][0-9]*$ ]] || {
  echo "--min-samples must be positive" >&2
  exit 2
}
[[ -d "$CAPTURES_DIR" ]] || { echo "captures directory not found: $CAPTURES_DIR" >&2; exit 2; }

mkdir -p "$OUT_DIR"
CAPTURES_DIR="$(cd -- "$CAPTURES_DIR" && pwd)"
OUT_DIR="$(cd -- "$OUT_DIR" && pwd)"
TASKS_TSV="$OUT_DIR/tasks.tsv"
RESULTS_TSV="$OUT_DIR/results.tsv"

python3 - "$CAPTURES_DIR" "$TASKS_TSV" "$MIN_SAMPLES" <<'PY'
from __future__ import annotations

from collections import defaultdict
import glob
import json
import os
from pathlib import Path
import sys

captures = Path(sys.argv[1])
tasks_path = Path(sys.argv[2])
minimum = int(sys.argv[3])
tasks = []
manifest_total = 0

for layer in range(3, 43):
    manifests = [Path(value) for value in sorted(glob.glob(str(captures / f"*.L{layer}.manifest.json")))]
    if not manifests:
        raise SystemExit(f"no {{prefix}}.L{layer}.manifest.json files under {captures}")
    manifest_total += len(manifests)
    seen: dict[int, set[tuple[object, object, object]]] = defaultdict(set)
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "ds4_expert_recovery_manifest_v1":
            raise SystemExit(f"bad trace schema: {manifest_path}")
        if int(manifest.get("layer", -1)) != layer:
            raise SystemExit(f"layer mismatch: {manifest_path}")
        jsonl_path = manifest_path.parent / Path(manifest["jsonl_file"]).name
        with jsonl_path.open("r", encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                try:
                    sample = json.loads(line)
                    expert = int(sample.get("expert", -1))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if not 0 <= expert < 256:
                    continue
                # Must match extract_expert_shard.py --dedup exactly.
                key = (
                    sample.get("request_epoch"),
                    sample.get("call_tick"),
                    sample.get("token_index"),
                )
                seen[expert].add(key)
    for expert, tokens in seen.items():
        if len(tokens) >= minimum:
            tasks.append((expert, layer, len(tokens)))

# Expert-major order spreads the first xargs wave across all 40 capture files.
tasks.sort()
temporary = tasks_path.with_suffix(tasks_path.suffix + ".tmp")
with temporary.open("w", encoding="utf-8", newline="\n") as stream:
    for expert, layer, count in tasks:
        stream.write(f"{layer}\t{expert}\t{count}\n")
os.replace(temporary, tasks_path)
print(f"eligible_tasks={len(tasks)} manifests={manifest_total} task_file={tasks_path}")
PY

if ((PLAN_ONLY)); then
  echo "plan-only: $(wc -l < "$TASKS_TSV") eligible layer/expert tasks"
  exit 0
fi

EXTRACT_TOOL="$BONSAI_DIR/extract_expert_shard.py"
GPTQ_TOOL="$BONSAI_DIR/gptq_q1.py"
TEACHER_TOOL="$SCRIPT_DIR/make_teacher_outputs.py"
[[ -f "$TEACHER_GGUF" ]] || { echo "teacher GGUF not found: $TEACHER_GGUF" >&2; exit 2; }
[[ -f "$EXTRACT_TOOL" ]] || { echo "extract tool not found: $EXTRACT_TOOL" >&2; exit 2; }
[[ -f "$GPTQ_TOOL" ]] || { echo "GPTQ tool not found: $GPTQ_TOOL" >&2; exit 2; }

BUILD_DIR="$OUT_DIR/.teacher_backend"
python3 "$TEACHER_TOOL" \
  --backend gcc \
  --cxx "$CXX_BIN" \
  --build-dir "$BUILD_DIR" \
  --build-only

NPROC="$(nproc)"
WORKER_THREADS=$((NPROC / JOBS))
((WORKER_THREADS > 0)) || WORKER_THREADS=1

aggregate_results() {
  local temporary="$RESULTS_TSV.tmp"
  {
    printf 'expert\tlayer\tn_samples\tcosine\n'
    find "$OUT_DIR" -mindepth 3 -maxdepth 3 -type f -name result.tsv -print0 \
      | sort -z \
      | xargs -0 -r cat \
      | sort -t $'\t' -k2,2n -k1,1n
  } > "$temporary"
  mv -f -- "$temporary" "$RESULTS_TSV"
}
trap aggregate_results EXIT

campaign_worker() (
  set -euo pipefail
  local layer="$1"
  local expert="$2"
  local planned_samples="$3"
  local layer_tag expert_tag task_dir shard_dir shard_manifest calib weights teacher_npz q1_dir
  local result_fragment log_file

  printf -v layer_tag 'L%02d' "$layer"
  printf -v expert_tag 'e%03d' "$expert"
  task_dir="$OUT_DIR/$layer_tag/$expert_tag"
  shard_dir="$task_dir/shard"
  shard_manifest="$shard_dir/L${layer}_e${expert}.manifest.json"
  calib="$task_dir/calib.npz"
  weights="$task_dir/weights.npz"
  teacher_npz="$task_dir/teacher.npz"
  q1_dir="$task_dir/q1"
  result_fragment="$task_dir/result.tsv"
  log_file="$task_dir/campaign.log"
  mkdir -p "$task_dir"

  export OMP_NUM_THREADS="$WORKER_THREADS"
  export MKL_NUM_THREADS="$WORKER_THREADS"
  export OPENBLAS_NUM_THREADS="$WORKER_THREADS"
  export NUMEXPR_NUM_THREADS="$WORKER_THREADS"

  write_result_fragment() {
    python3 - "$q1_dir/manifest.json" "$result_fragment" "$expert" "$layer" "$planned_samples" <<'PY'
import json
import os
from pathlib import Path
import sys

manifest_path, result_path = map(Path, sys.argv[1:3])
expert, layer, planned = map(int, sys.argv[3:6])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
verification = manifest.get("verification") or {}
cosine = verification.get("cosine_similarity")
if cosine is None:
    raise SystemExit(f"missing verification.cosine_similarity: {manifest_path}")
n_samples = int(manifest.get("calibration", {}).get("source_rows", planned))
temporary = result_path.with_suffix(result_path.suffix + ".tmp")
temporary.write_text(f"{expert}\t{layer}\t{n_samples}\t{float(cosine):.17g}\n", encoding="utf-8")
os.replace(temporary, result_path)
PY
  }

  if [[ -f "$q1_dir/manifest.json" &&
        -f "$q1_dir/gate.q1.npz" &&
        -f "$q1_dir/up.q1.npz" &&
        -f "$q1_dir/down.q1.npz" ]]; then
    [[ -f "$result_fragment" ]] || write_result_fragment
    echo "skip complete $layer_tag/$expert_tag"
    exit 0
  fi

  {
    echo "start layer=$layer expert=$expert planned_samples=$planned_samples"
    if [[ ! -f "$shard_manifest" ]]; then
      trace_arguments=()
      while IFS= read -r -d '' manifest; do
        trace_arguments+=(--trace "$manifest")
      done < <(
        find "$CAPTURES_DIR" -maxdepth 1 -type f \
          -name "*.L${layer}.manifest.json" -print0 | sort -z
      )
      ((${#trace_arguments[@]} > 0)) || {
        echo "no trace manifests for layer $layer" >&2
        exit 1
      }
      python3 "$EXTRACT_TOOL" \
        "${trace_arguments[@]}" \
        --expert "$expert" \
        --layer "$layer" \
        --dedup \
        --out-dir "$shard_dir" \
        --prefix "L${layer}_e${expert}"
    fi

    if [[ ! -f "$calib" ]]; then
      python3 - "$shard_manifest" "$calib" "$MIN_SAMPLES" <<'PY'
import json
import os
from pathlib import Path
import sys
import numpy as np

manifest_path, output_path = map(Path, sys.argv[1:3])
minimum = int(sys.argv[3])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
count = int(manifest["sample_count"])
if count < minimum:
    raise SystemExit(f"post-extract sample count {count} < {minimum}: {manifest_path}")
vectors = manifest_path.parent / Path(manifest["binary_file"]).name
x = np.memmap(vectors, dtype="<f4", mode="r", offset=64, shape=(count, 4096))
temporary = output_path.with_suffix(output_path.suffix + ".tmp")
with temporary.open("wb") as stream:
    np.savez(stream, x=np.asarray(x, dtype=np.float32))
os.replace(temporary, output_path)
PY
    fi

    if [[ ! -f "$weights" || ! -f "$teacher_npz" ]]; then
      python3 "$TEACHER_TOOL" \
        --backend gcc \
        --cxx "$CXX_BIN" \
        --build-dir "$BUILD_DIR" \
        --trace "$shard_manifest" \
        --teacher "$TEACHER_GGUF" \
        --layer "$layer" \
        --expert "$expert" \
        --out "$teacher_npz" \
        --weights-out "$weights" \
        --raw-dir "$task_dir/teacher.raw" \
        --cleanup-raw
    fi

    python3 "$GPTQ_TOOL" \
      --weights "$weights" \
      --calib "$calib" \
      --calib-key x \
      --out "$q1_dir" \
      --device "$DEVICE" \
      --holdout-fraction 0.15
    write_result_fragment

    if ((KEEP_WORK == 0)); then
      rm -f -- "$calib" "$weights" "$teacher_npz"
      rm -rf -- "$shard_dir"
    fi
    echo "done layer=$layer expert=$expert"
  } >> "$log_file" 2>&1
)

export -f campaign_worker
export CAPTURES_DIR OUT_DIR EXTRACT_TOOL GPTQ_TOOL TEACHER_TOOL TEACHER_GGUF
export BUILD_DIR CXX_BIN DEVICE MIN_SAMPLES KEEP_WORK WORKER_THREADS

echo "running $(wc -l < "$TASKS_TSV") experts with xargs -P $JOBS ($WORKER_THREADS threads/worker)"
xargs -r -P "$JOBS" -n 3 bash -c 'campaign_worker "$@"' _ < "$TASKS_TSV"
aggregate_results
trap - EXIT
echo "campaign complete: $RESULTS_TSV"
