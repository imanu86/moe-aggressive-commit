"""Make an isolated 0.1.38 candidate for PR #547; never edit the installed Daily."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
DAILY_SOURCE = Path(r"D:\ds4_work\strata\Strata\build-0138-daily\source")
CANDIDATE = HERE / "source-547"
if CANDIDATE.exists():
    raise SystemExit("Candidate already exists; preserving it")
shutil.copytree(DAILY_SOURCE, CANDIDATE)

def replace(path, old, new, count=1):
    p = CANDIDATE / path
    s = p.read_text(encoding="utf-8")
    if s.count(old) != count:
        raise RuntimeError(f"Expected {count} copies in {path}; found {s.count(old)}")
    p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")

replace(
    "include/strata/prefill/prefill.hpp",
    "static uint64_t bytes_needed(const core::ModelGeometry& g, const core::SessionState& ss, int64_t chunk);",
    "static uint64_t bytes_needed(const core::ModelGeometry& g, const core::SessionState& ss, int64_t chunk,\n"
    "                                 bool src = true);",
)
replace(
    "src/prefill/prefill.cpp",
    "uint64_t Prefill::bytes_needed(const core::ModelGeometry& g, const core::SessionState& ss, int64_t chunk) {",
    "uint64_t Prefill::bytes_needed(const core::ModelGeometry& g, const core::SessionState& ss, int64_t chunk, bool src) {",
)
replace(
    "src/prefill/prefill.cpp",
    "f(T * N); f(T * D); f(T * D); o.take<uint16_t>(T * D, ok); f(T * LR); o.take<uint16_t>(T * LR, ok);",
    "f(T * N); f(T * D);\n"
    "    if (gr_unfused()) f(T * D);\n"
    "    f(T * HC);\n"
    "    o.take<uint16_t>(T * D, ok); f(T * LR); o.take<uint16_t>(T * LR, ok);",
)
replace(
    "src/prefill/prefill.cpp",
    "moe_set_bytes(T, g.n_expert, fused_layout(T, true))",
    "moe_set_bytes(T, g.n_expert, fused_layout(T, src))",
)
replace("src/program/generate.cpp", "Prefill::bytes_needed(g, ss, 256)",
        "Prefill::bytes_needed(g, ss, 256, srcp != nullptr)")
replace("src/program/generate.cpp", "Prefill::bytes_needed(g, ss, c)",
        "Prefill::bytes_needed(g, ss, c, srcp != nullptr)")
replace("src/program/generate.cpp", "Prefill::bytes_needed(g, *p.ses, c)",
        "Prefill::bytes_needed(g, *p.ses, c, srcp != nullptr)")
replace("src/program/generate.cpp", "Prefill::bytes_needed(g, *p.ses, chunk)",
        "Prefill::bytes_needed(g, *p.ses, chunk, srcp != nullptr)")
replace("src/program/generate.cpp", "Prefill::bytes_needed(g, i == 0 ? ss : stages[i - 1]->ss, c)",
        "Prefill::bytes_needed(g, i == 0 ? ss : stages[i - 1]->ss, c, srcp != nullptr)")

files = [
    "include/strata/prefill/prefill.hpp",
    "src/prefill/prefill.cpp",
    "src/program/generate.cpp",
]
report = {
    "upstream_base": "99f3dbd0b21d1401b3769e0c0d963913607f380b",
    "pr547_head": "4072b708e94d06cadee61a47df1930f22d313d86",
    "daily_source": str(DAILY_SOURCE),
    "candidate_source": str(CANDIDATE),
    "port": "PR #547 allocation count plus explicit source-dependent layout at all five 0.1.38 call sites",
    "sm75_allocations_preserved": "all tc_sm75 buffers remain counted in the original position",
    "files_sha256": {name: hashlib.sha256((CANDIDATE / name).read_bytes()).hexdigest() for name in files},
}
(HERE / "candidate-547.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))

