#!/bin/sh
# P3 - genera la patch unificata della copia di lavoro rispetto allo snapshot di P0.
# Lo snapshot NON viene modificato: e' solo il lato sinistro del diff.
A="D:/ds4_work/p0_snapshot_20260914/source"
B="D:/ds4_work/p3_work/source"
OUT="C:/Users/imanu/source/repos/moe-aggressive-commit/docs/porto/p3_uno_strato/p3_uno_strato.patch"
: > "$OUT"
FILES="
ggml/include/ggml-moe-cpu.h
ggml/include/moe_cpu_job.h
ggml/src/ggml.c
ggml/src/ggml-cuda/fork-moe-kernels.cuh
ggml/src/ggml-cuda/moe-demand.cuh
ggml/src/ggml-cuda/moe-demand-api.cuh
ggml/src/ggml-cuda/mmvq.cu
ggml/src/ggml-cuda/ggml-cuda.cu
src/CMakeLists.txt
src/llama-graph.cpp
src/llama-context.cpp
src/llama-moecpu.h
src/llama-moecpu.cpp
src/moe_cpu_executor.h
src/moe_cpu_executor.cpp
src/moe_cpu_host_memory.h
src/moe_cpu_host_memory_cuda.cpp
"
for f in $FILES; do
  if [ -f "$A/$f" ]; then L="$A/$f"; else L="/dev/null"; fi
  diff -u --label "a/$f" "$L" --label "b/$f" "$B/$f" >> "$OUT"
done
wc -l "$OUT"
