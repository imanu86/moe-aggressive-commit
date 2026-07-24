#!/usr/bin/env python3
"""Reconstruct DS4 single-expert teacher outputs from captured trace inputs.

On Windows, ``--backend auto`` preserves the legacy MSVC source-extraction
path.  On Linux and other non-Windows hosts it builds the checked-in portable
C++ helper with g++ and the same ds4_q1_ref.c dequantization implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np


TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_LEGACY_TRAINER = Path(r"C:\Users\imanu\g130i\ste_trainer")
DEFAULT_REF_SOURCE = TOOLS_DIR / "ds4_q1_ref.c"
DEFAULT_PORTABLE_SOURCE = TOOLS_DIR / "teacher_backend_portable.cpp"
DEFAULT_VCVARS64 = Path(
    r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
)
N_EMBD = 4096
GCC_FLAGS = (
    "-std=c++17",
    "-O3",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-fopenmp",
    "-ffp-contract=off",
    "-fno-fast-math",
)
RAW_FILENAMES = (
    "teacher_y.f32le",
    "teacher_gate.f32le",
    "teacher_up.f32le",
    "teacher_down.f32le",
    "teacher_y.meta.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "ds4_expert_recovery_manifest_v1":
        raise ValueError(f"bad trace schema: {path}")
    if value.get("status") != "complete":
        raise ValueError(f"trace is not complete: {path}")
    if not value.get("input_only") or value.get("teacher_output_captured"):
        raise ValueError(f"trace is not the input-only recovery contract: {path}")
    if value.get("teacher_output_reconstruction") != "offline_exact_iq2_from_captured_input":
        raise ValueError(f"unexpected reconstruction contract: {path}")
    if int(value.get("vector_dim", 0)) != N_EMBD:
        raise ValueError(f"unexpected vector_dim in {path}")
    return value


def validate_trace_files(path: Path, manifest: dict) -> None:
    for file_key, bytes_key, sha_key in (
        ("binary_file", "binary_bytes", "binary_sha256"),
        ("jsonl_file", "jsonl_bytes", "jsonl_sha256"),
    ):
        payload = path.parent / Path(manifest[file_key])
        if not payload.is_file():
            raise FileNotFoundError(payload)
        if payload.stat().st_size != int(manifest[bytes_key]):
            raise ValueError(f"{file_key} byte-size mismatch: {payload}")
        expected_sha = str(manifest.get(sha_key, ""))
        if expected_sha and sha256_file(payload) != expected_sha:
            raise ValueError(f"{file_key} SHA-256 mismatch: {payload}")


def helper_main_source() -> str:
    # This is kept byte-for-byte equivalent to the existing Windows driver.
    return r'''
int main(int argc,char**argv){try{
    auto wall=Clock::now();
    Options o=parse_args(argc,argv);
    fs::path out=fs::absolute(o.out);
    fs::create_directories(out);
    TraceData td=load_traces(o);
    auto dec=Clock::now();
    ModelInfo tm;
    Expert teacher=decode_expert(o.teacher,o.layer,o.expert,false,&tm);
    std::vector<float> yt;
    forward_expert(td.x.data(),(int)td.meta.size(),teacher,yt);
    auto write_raw=[&](const fs::path&p,const std::vector<float>&v){
        std::ofstream f(p,std::ios::binary);
        if(!f) fail("cannot create "+p.string());
        f.write((const char*)v.data(),(std::streamsize)(v.size()*sizeof(float)));
        if(!f) fail("raw write failed: "+p.string());
    };
    fs::path raw=out/"teacher_y.f32le";
    write_raw(raw,yt);
    write_raw(out/"teacher_gate.f32le",teacher.gate);
    write_raw(out/"teacher_up.f32le",teacher.up);
    write_raw(out/"teacher_down.f32le",teacher.down);
    std::ofstream mf(out/"teacher_y.meta.json",std::ios::binary);
    mf<<std::setprecision(17)
      <<"{\"schema\":\"ds4_teacher_outputs_raw_v1\","
      <<"\"layer\":"<<o.layer<<",\"expert\":"<<o.expert
      <<",\"sample_count\":"<<td.meta.size()
      <<",\"shape\":["<<td.meta.size()<<","<<N_EMBD<<"]"
      <<",\"dtype\":\"float32-le\",\"raw_file\":\"teacher_y.f32le\""
      <<",\"weight_files\":{\"gate\":\"teacher_gate.f32le\",\"up\":\"teacher_up.f32le\",\"down\":\"teacher_down.f32le\"}"
      <<",\"teacher\":\""<<json_escape(fs::absolute(o.teacher).string())<<"\""
      <<",\"source_types\":{\"teacher\":["<<tm.gate.type<<","<<tm.up.type<<","<<tm.down.type<<"]}"
      <<",\"decode_forward_seconds\":"<<seconds_since(dec)
      <<",\"wall_seconds\":"<<seconds_since(wall)
      <<"}\n";
    std::cout<<"teacher_y raw: "<<raw.string()<<"\n";
    std::cout<<"samples: "<<td.meta.size()<<" shape: ["<<td.meta.size()<<","<<N_EMBD<<"]\n";
    return 0;
}catch(const std::exception&e){std::cerr<<"teacher_backend: "<<e.what()<<"\n";return 1;}}
'''


def write_msvc_helper_source(legacy_source: Path, helper_source: Path) -> None:
    text = legacy_source.read_text(encoding="utf-8")
    marker = "int main(int argc,char**argv){try{"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"could not find native backend main in {legacy_source}")
    helper_source.write_text(text[:start] + helper_main_source().lstrip(), encoding="utf-8")


def resolve_backend(requested: str) -> str:
    if requested != "auto":
        return requested
    return "msvc" if os.name == "nt" else "gcc"


def build_msvc_helper(args: argparse.Namespace, build_dir: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    legacy_source = (args.legacy_trainer_dir / "ste_backend.cpp").resolve()
    ref_source = args.ref_source.resolve()
    if not legacy_source.exists():
        raise FileNotFoundError(legacy_source)
    if not ref_source.exists():
        raise FileNotFoundError(ref_source)
    if not args.vcvars64.exists():
        raise FileNotFoundError(args.vcvars64)

    helper_source = build_dir / "teacher_backend.cpp"
    helper_exe = build_dir / "teacher_backend.exe"
    stamp = build_dir / "teacher_backend.msvc.inputs.sha256"
    digest = hashlib.sha256()
    digest.update(legacy_source.read_bytes())
    digest.update(ref_source.read_bytes())
    digest.update(helper_main_source().encode("utf-8"))
    wanted = digest.hexdigest()
    if helper_exe.exists() and stamp.exists() and stamp.read_text(encoding="utf-8").strip() == wanted:
        return helper_exe

    write_msvc_helper_source(legacy_source, helper_source)
    command = (
        f'call "{args.vcvars64}" >nul && '
        f'cl /nologo /std:c++17 /O2 /W4 /EHsc /openmp '
        f'/I "{ref_source.parent}" "{helper_source}" "{ref_source}" '
        f'/Fe:"{helper_exe}" /link bcrypt.lib psapi.lib'
    )
    result = subprocess.run(["cmd", "/d", "/s", "/c", command], cwd=build_dir, check=False)
    if result.returncode:
        raise RuntimeError(f"teacher backend MSVC build failed: exit={result.returncode}")
    stamp.write_text(wanted + "\n", encoding="utf-8")
    return helper_exe


def build_gcc_helper(args: argparse.Namespace, build_dir: Path) -> Path:
    build_dir.mkdir(parents=True, exist_ok=True)
    portable_source = args.portable_source.resolve()
    ref_source = args.ref_source.resolve()
    if not portable_source.exists():
        raise FileNotFoundError(portable_source)
    if not ref_source.exists():
        raise FileNotFoundError(ref_source)
    compiler = shutil.which(args.cxx)
    if compiler is None:
        raise FileNotFoundError(f"C++ compiler not found on PATH: {args.cxx}")

    helper_exe = build_dir / "teacher_backend"
    stamp = build_dir / "teacher_backend.gcc.inputs.sha256"
    digest = hashlib.sha256()
    digest.update(portable_source.read_bytes())
    digest.update(ref_source.read_bytes())
    digest.update("\0".join(GCC_FLAGS).encode("utf-8"))
    digest.update(os.fsencode(os.path.realpath(compiler)))
    wanted = digest.hexdigest()
    if helper_exe.exists() and stamp.exists() and stamp.read_text(encoding="utf-8").strip() == wanted:
        return helper_exe

    command = [
        compiler,
        *GCC_FLAGS,
        "-I",
        os.fspath(ref_source.parent),
        os.fspath(portable_source),
        os.fspath(ref_source),
        "-o",
        os.fspath(helper_exe),
    ]
    result = subprocess.run(command, cwd=build_dir, check=False)
    if result.returncode:
        raise RuntimeError(f"teacher backend GCC build failed: exit={result.returncode}")
    stamp.write_text(wanted + "\n", encoding="utf-8")
    return helper_exe


def build_helper(args: argparse.Namespace, build_dir: Path) -> tuple[Path, str]:
    backend = resolve_backend(args.backend)
    build_dir = build_dir.resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    if backend == "msvc":
        helper = build_msvc_helper(args, build_dir)
    elif backend == "gcc":
        helper = build_gcc_helper(args, build_dir)
    else:  # argparse choices make this defensive only.
        raise ValueError(f"unsupported backend: {backend}")
    return helper, backend


def run_helper(helper: Path, args: argparse.Namespace, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    command = [
        os.fspath(helper),
        "--layer",
        str(args.layer),
        "--expert",
        str(args.expert),
        "--teacher",
        os.fspath(args.teacher),
        "--out",
        os.fspath(raw_dir),
    ]
    for trace in args.trace:
        command += ["--traces", os.fspath(trace)]
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise RuntimeError(f"teacher backend failed: exit={result.returncode}")
    return raw_dir / "teacher_y.f32le"


def package_npz(raw_path: Path, meta_path: Path, out_path: Path, manifests: list[Path]) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sample_count = int(meta["sample_count"])
    shape = (sample_count, N_EMBD)
    expected_bytes = sample_count * N_EMBD * 4
    if raw_path.stat().st_size != expected_bytes:
        raise ValueError(f"raw teacher_y byte mismatch: {raw_path}")
    teacher_y = np.memmap(raw_path, mode="r", dtype="<f4", shape=shape)
    array = np.array(teacher_y, dtype=np.float32, copy=True)
    if not np.isfinite(array).all():
        raise ValueError("teacher_y contains non-finite values")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(out_path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            teacher_y=array,
            layer=np.int32(meta["layer"]),
            expert=np.int32(meta["expert"]),
            trace_manifests=np.array([os.fspath(path) for path in manifests]),
            raw_sha256=sha256_file(raw_path),
        )
    os.replace(temporary, out_path)


def package_weights(raw_dir: Path, out_path: Path) -> None:
    specs = {
        "gate": ("teacher_gate.f32le", (2048, 4096)),
        "up": ("teacher_up.f32le", (2048, 4096)),
        "down": ("teacher_down.f32le", (4096, 2048)),
    }
    arrays = {}
    for name, (filename, shape) in specs.items():
        path = raw_dir / filename
        expected = int(np.prod(shape)) * 4
        if path.stat().st_size != expected:
            raise ValueError(f"{name} weight byte mismatch: {path}")
        array = np.array(
            np.memmap(path, mode="r", dtype="<f4", shape=shape),
            dtype=np.float32,
            copy=True,
        )
        if not np.isfinite(array).all():
            raise ValueError(f"{name} weight contains non-finite values")
        arrays[name] = array
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(out_path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    os.replace(temporary, out_path)


def cleanup_raw_dir(raw_dir: Path) -> None:
    for filename in RAW_FILENAMES:
        path = raw_dir / filename
        if path.is_file():
            path.unlink()
    try:
        raw_dir.rmdir()
    except OSError:
        # Preserve the directory if the caller placed unrelated files in it.
        pass


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", action="append", type=Path)
    parser.add_argument("--teacher", type=Path, help="Primary DS4 GGUF")
    parser.add_argument("--layer", type=int)
    parser.add_argument("--expert", type=int)
    parser.add_argument("--out", type=Path, help="Output teacher_y.npz")
    parser.add_argument("--weights-out", type=Path, help="Output teacher FP32 gate/up/down NPZ")
    parser.add_argument("--legacy-trainer-dir", type=Path, default=DEFAULT_LEGACY_TRAINER)
    parser.add_argument("--ref-source", type=Path, default=DEFAULT_REF_SOURCE)
    parser.add_argument("--vcvars64", type=Path, default=DEFAULT_VCVARS64)
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=TOOLS_DIR / ".teacher_backend",
    )
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument(
        "--backend",
        choices=("auto", "msvc", "gcc"),
        default="auto",
        help="auto selects MSVC on Windows and g++ elsewhere",
    )
    parser.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    parser.add_argument("--portable-source", type=Path, default=DEFAULT_PORTABLE_SOURCE)
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="build the selected helper and exit without requiring a trace/model",
    )
    parser.add_argument(
        "--cleanup-raw",
        action="store_true",
        help="remove only the five generated raw files after packaging",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if not args.build_only:
        missing = [
            option
            for option, value in (
                ("--trace", args.trace),
                ("--teacher", args.teacher),
                ("--layer", args.layer),
                ("--expert", args.expert),
                ("--out", args.out),
            )
            if value is None
        ]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    helper, backend = build_helper(args, args.build_dir)
    if args.build_only:
        print(json.dumps({"backend": backend, "helper": os.fspath(helper)}, separators=(",", ":")))
        return 0

    common_provenance: tuple[str, str] | None = None
    for trace in args.trace:
        manifest = load_manifest(trace)
        if int(manifest["layer"]) != args.layer or int(manifest["expert"]) != args.expert:
            raise ValueError(f"trace target mismatch: {trace}")
        validate_trace_files(trace, manifest)
        provenance = (
            str(manifest.get("model_sha256", "")),
            str(manifest.get("sidecar_sha256", "")),
        )
        if common_provenance is None:
            common_provenance = provenance
        elif provenance != common_provenance:
            raise ValueError(f"merged traces have different model provenance: {trace}")

    raw_dir = args.raw_dir or (args.out.parent / (args.out.stem + ".raw"))
    raw = run_helper(helper, args, raw_dir)
    package_npz(raw, raw_dir / "teacher_y.meta.json", args.out, args.trace)
    if args.weights_out:
        weights_out = args.weights_out
    else:
        weight_stem = (
            args.out.stem.replace("teacher_y", "teacher_fp32")
            if "teacher_y" in args.out.stem
            else args.out.stem + "_teacher_fp32"
        )
        weights_out = args.out.with_name(weight_stem + ".npz")
    package_weights(raw_dir, weights_out)
    with np.load(args.out, allow_pickle=False) as data:
        summary = {
            "backend": backend,
            "teacher_outputs": os.fspath(args.out),
            "teacher_weights": os.fspath(weights_out),
            "shape": list(data["teacher_y"].shape),
            "raw_sha256": str(data["raw_sha256"]),
        }
    if args.cleanup_raw:
        cleanup_raw_dir(raw_dir)
    print(json.dumps(summary, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
