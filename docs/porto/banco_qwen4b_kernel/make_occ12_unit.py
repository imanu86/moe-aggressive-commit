"""Generate validator from the exact current kernel source; never compile or run it."""
import hashlib
import json
import pathlib

lab = pathlib.Path(r'D:\ds4_work\qwen4b_kernel_lab')
path = lab / 'source/ggml/src/ggml-cuda/mmvq.cu'
source = path.read_text(encoding='utf-8')

def between(start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError(f'Nonunique source boundary: {start} / {end}')
    return source[source.index(start):source.index(end)]

parts = [
    between('typedef float (*vec_dot_q_cuda_t)', 'static __host__ mmvq_parameter_table_id get_device_table_id(int cc)'),
    between('static constexpr __host__ __device__ int calc_nwarps(', '// P10 cella 3 -'),
    between('template <ggml_type type, int ncols_dst, bool has_fusion, bool small_k = false, bool halve_iters = false, bool sampled_ids = false, int min_blocks = 1>', '// Dedicated MoE multi-token kernel.'),
]
header = '#include "mmvq.cuh"\n#include "quantize.cuh"\n#include "unary.cuh"\n#include "vecdotq.cuh"\n'
driver_path = lab / 'unit_occ12_driver.cu'
driver = driver_path.read_text(encoding='utf-8')
output = lab / 'evidence/unit_occ12.cu'
output.write_text(header + '\n'.join(parts) + '\n' + driver, encoding='utf-8')
manifest = dict(source_path=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                driver_sha256=hashlib.sha256(driver_path.read_bytes()).hexdigest(),
                kernel_sha256=hashlib.sha256(parts[-1].encode()).hexdigest(),
                extracted_sha256=[hashlib.sha256(p.encode()).hexdigest() for p in parts],
                output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                purpose='Bitwise min_blocks=1 vs min_blocks=12, exact Q4_K fused SwiGLU template, twelve fixtures, canaries, finite outputs; does not validate dispatch or full model logits.')
(lab / 'evidence/unit-occ12-source-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
