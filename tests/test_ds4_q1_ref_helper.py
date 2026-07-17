from __future__ import annotations

import os
import struct
import subprocess
from pathlib import Path

from tools.ds4_q1_smoke import Q1_BLOCK_BYTES, Q1_BLOCK_WEIGHTS


REPO = Path(__file__).resolve().parents[1]
VCVARS64 = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat")


def _build_ref_tool(tmp_path: Path) -> Path:
    exe = tmp_path / "ds4_q1_ref_tool.exe"
    bat = tmp_path / "build_ref_tool.bat"
    bat.write_text(
        "@echo off\n"
        f'call "{VCVARS64}" >nul\n'
        "if errorlevel 1 exit /b 1\n"
        f'cl /nologo /std:c11 /W4 /WX /I "{REPO / "tools"}" '
        f'"{REPO / "tools" / "ds4_q1_ref.c"}" '
        f'"{REPO / "tools" / "ds4_q1_ref_tool.c"}" '
        f'/Fe:"{exe}"\n',
        encoding="utf-8",
    )
    proc = subprocess.run([str(bat)], cwd=REPO, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.returncode == 0, proc.stdout
    assert exe.exists()
    return exe


def _q1_pack(values: list[float]) -> bytes:
    assert len(values) % Q1_BLOCK_WEIGHTS == 0
    out = bytearray()
    for start in range(0, len(values), Q1_BLOCK_WEIGHTS):
        block = values[start : start + Q1_BLOCK_WEIGHTS]
        d = sum(abs(v) for v in block) / Q1_BLOCK_WEIGHTS
        bits = 0
        for i, value in enumerate(block):
            if value >= 0.0:
                bits |= 1 << i
        out += struct.pack("<e", d)
        out += bits.to_bytes(16, "little")
    return bytes(out)


def _convert(tool: Path, type_name: str, nrows: int, ncols: int, payload: bytes) -> bytes:
    proc = subprocess.run(
        [str(tool), "convert", type_name, str(nrows), str(ncols)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    return proc.stdout


def _q2_k_payload() -> tuple[bytes, list[float]]:
    scales = bytes(((i % 4) + 1) | (((i % 3) + 1) << 4) for i in range(16))
    qs = bytes(((i * 37 + 11) & 0xFF) for i in range(64))
    d = 0.25
    dmin = 0.125
    payload = scales + qs + struct.pack("<e", d) + struct.pack("<e", dmin)
    values: list[float] = []
    qpos = 0
    iscale = 0
    for _ in range(0, 256, 128):
        shift = 0
        for _ in range(4):
            sc = scales[iscale]
            iscale += 1
            dl = d * (sc & 0xF)
            ml = dmin * (sc >> 4)
            for l in range(16):
                values.append(dl * ((qs[qpos + l] >> shift) & 3) - ml)
            sc = scales[iscale]
            iscale += 1
            dl = d * (sc & 0xF)
            ml = dmin * (sc >> 4)
            for l in range(16):
                values.append(dl * ((qs[qpos + 16 + l] >> shift) & 3) - ml)
            shift += 2
        qpos += 32
    return payload, values


def test_ref_tool_builds_and_converts_q2_k_golden(tmp_path) -> None:
    assert VCVARS64.exists(), "Visual Studio vcvars64.bat is required for CPU helper build"
    tool = _build_ref_tool(tmp_path)
    payload, expected_values = _q2_k_payload()
    assert _convert(tool, "q2_k", 1, 256, payload) == _q1_pack(expected_values)


def test_ref_tool_converts_iq2_xxs_zero_golden(tmp_path) -> None:
    assert VCVARS64.exists(), "Visual Studio vcvars64.bat is required for CPU helper build"
    tool = _build_ref_tool(tmp_path)
    payload = struct.pack("<e", 1.0) + bytes(64)
    expected = _q1_pack([1.0] * 256)
    assert _convert(tool, "iq2_xxs", 1, 256, payload) == expected


def test_converter_accepts_real_types_only_with_explicit_ref_tool(tmp_path, monkeypatch) -> None:
    from tests.test_ds4_q1_sidecar_converter import _runtime_mixed_real_fixture
    from tools.ds4_q1_sidecar_converter import (
        Q1_TYPE_ID,
        convert_runtime_valid_single_layer_sidecar,
        parse_gguf_header,
        validate_runtime_sidecar_manifest,
    )

    assert VCVARS64.exists(), "Visual Studio vcvars64.bat is required for CPU helper build"
    tool = _build_ref_tool(tmp_path)
    source = tmp_path / "ds4-real-mini-primary.gguf"
    sidecar = tmp_path / "ds4-real-mini-q1.gguf"
    manifest = tmp_path / "ds4-real-mini-q1.manifest.json"
    _runtime_mixed_real_fixture(source, target_layer=42)

    monkeypatch.setenv("DS4_Q1_REF_TOOL", str(tool))
    obj = convert_runtime_valid_single_layer_sidecar(source, sidecar, manifest, layer=42)
    assert obj["schema"] == "ds4_q1_0_runtime_sidecar_manifest_v1"
    parsed = parse_gguf_header(sidecar)
    for suffix in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
        assert parsed.tensors[f"blk.42.{suffix}"].type_id == Q1_TYPE_ID
    validate_runtime_sidecar_manifest(source, sidecar, manifest)
