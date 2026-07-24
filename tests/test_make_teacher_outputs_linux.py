from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from tools import compare_teacher_weights
from tools import make_teacher_outputs


REPO = Path(__file__).resolve().parents[1]


def test_backend_selection_keeps_explicit_choices() -> None:
    assert make_teacher_outputs.resolve_backend("gcc") == "gcc"
    assert make_teacher_outputs.resolve_backend("msvc") == "msvc"


def test_gcc_build_command_is_portable_and_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_compiler = tmp_path / "g++"
    fake_compiler.write_bytes(b"")
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess:
        assert check is False
        calls.append((command, cwd))
        Path(command[command.index("-o") + 1]).write_bytes(b"helper")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(make_teacher_outputs.shutil, "which", lambda _: str(fake_compiler))
    monkeypatch.setattr(make_teacher_outputs.subprocess, "run", fake_run)
    args = argparse.Namespace(
        portable_source=REPO / "tools" / "teacher_backend_portable.cpp",
        ref_source=REPO / "tools" / "ds4_q1_ref.c",
        cxx="g++",
    )
    helper = make_teacher_outputs.build_gcc_helper(args, tmp_path / "build")

    assert helper.read_bytes() == b"helper"
    command, cwd = calls[0]
    assert cwd == (tmp_path / "build").resolve()
    assert "-std=c++17" in command
    assert "-fopenmp" in command
    assert "-ffp-contract=off" in command
    assert "-fno-fast-math" in command
    assert "vcvars64" not in " ".join(command).lower()


def test_portable_source_has_no_windows_api_dependency() -> None:
    source = (REPO / "tools" / "teacher_backend_portable.cpp").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "#include <windows.h>" not in lowered
    assert "bcrypt" not in lowered
    assert "findfirstfile" not in lowered
    assert "ds4_q1_ref_dequant_row" in source


def test_validate_trace_files_accepts_empty_or_matching_sha(tmp_path: Path) -> None:
    binary = tmp_path / "trace.vectors.f32le"
    jsonl = tmp_path / "trace.samples.jsonl"
    binary.write_bytes(b"binary")
    jsonl.write_text("{}\n", encoding="utf-8")
    manifest = {
        "binary_file": binary.name,
        "binary_bytes": binary.stat().st_size,
        "binary_sha256": make_teacher_outputs.sha256_file(binary),
        "jsonl_file": jsonl.name,
        "jsonl_bytes": jsonl.stat().st_size,
        "jsonl_sha256": "",
    }
    make_teacher_outputs.validate_trace_files(tmp_path / "trace.manifest.json", manifest)


def test_compare_weights_checks_float_bits_not_zip_container(tmp_path: Path) -> None:
    arrays = {
        "gate": np.arange(12, dtype=np.float32).reshape(3, 4),
        "up": np.arange(8, dtype=np.float32).reshape(2, 4),
        "down": np.arange(8, dtype=np.float32).reshape(4, 2),
    }
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    np.savez(first, **arrays)
    np.savez_compressed(second, **arrays)

    result = compare_teacher_weights.compare_weight_archives(first, second)
    assert result["exact"] is True
    assert result["npz_byte_identical"] is False
    assert all(value["exact"] for value in result["arrays"].values())

    changed = tmp_path / "changed.npz"
    changed_arrays = {name: value.copy() for name, value in arrays.items()}
    changed_arrays["gate"][0, 0] = np.float32(-0.0)
    np.savez(changed, **changed_arrays)
    with pytest.raises(AssertionError, match="bit patterns differ"):
        compare_teacher_weights.compare_weight_archives(first, changed)


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ is not installed")
def test_gcc_helper_builds(tmp_path: Path) -> None:
    args = argparse.Namespace(
        portable_source=REPO / "tools" / "teacher_backend_portable.cpp",
        ref_source=REPO / "tools" / "ds4_q1_ref.c",
        cxx="g++",
    )
    helper = make_teacher_outputs.build_gcc_helper(args, tmp_path / "gcc")
    assert helper.is_file()
    output = subprocess.run(
        [str(helper), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert output.returncode == 0
    assert "Portable single-expert DS4 teacher extractor" in output.stdout


def test_campaign_script_uses_repeated_trace_and_parallel_xargs() -> None:
    script = (REPO / "tools" / "run_gptq_campaign_linux.sh").read_text(encoding="utf-8")
    assert 'trace_arguments+=(--trace "$manifest")' in script
    assert 'xargs -r -P "$JOBS"' in script
    assert "range(3, 43)" in script
    assert "expert\\tlayer\\tn_samples\\tcosine" in script
