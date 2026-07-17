from __future__ import annotations

import os
import hashlib
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


IQ2XXS_GRID = {
    1: [43, 8, 8, 8, 8, 8, 8, 8],
    5: [25, 8, 25, 8, 8, 8, 8, 8],
    17: [8, 8, 8, 43, 8, 8, 8, 8],
    42: [8, 25, 8, 43, 8, 25, 8, 8],
    73: [8, 25, 8, 8, 8, 8, 25, 8],
    91: [8, 8, 43, 8, 8, 25, 25, 8],
    128: [8, 43, 8, 8, 8, 43, 43, 8],
    170: [25, 8, 43, 25, 25, 43, 8, 25],
    201: [25, 25, 25, 25, 25, 8, 43, 25],
    213: [25, 8, 8, 25, 8, 8, 8, 43],
    230: [8, 8, 43, 25, 43, 25, 8, 43],
    255: [8, 25, 8, 8, 25, 43, 43, 43],
}


def _ksigns_iq2xs(sign_index: int) -> int:
    parity = sign_index.bit_count() & 1
    return sign_index | (parity << 7)


def _iq2_xxs_block(scale_seed: int, d: float) -> tuple[bytes, list[float]]:
    groups = []
    values: list[float] = []
    grid_choices = [1, 42, 73, 170, 5, 91, 128, 255, 17, 201, 213, 230]
    sign_choices = [0x01, 0x12, 0x2A, 0x55, 0x03, 0x1C, 0x63, 0x7E, 0x05, 0x31, 0x4D, 0x6A]
    d_half = struct.unpack("<e", struct.pack("<e", d))[0]
    for ib32 in range(8):
        grid_indices = [grid_choices[(scale_seed + ib32 * 3 + l) % len(grid_choices)] for l in range(4)]
        sign_indices = [sign_choices[(scale_seed + ib32 * 5 + l) % len(sign_choices)] for l in range(4)]
        scale_nibble = (scale_seed + ib32) % 15 + 1
        aux_hi = scale_nibble << 28
        for l, sign_index in enumerate(sign_indices):
            aux_hi |= sign_index << (7 * l)
        groups.append(bytes(grid_indices) + aux_hi.to_bytes(4, "little"))
        db = d_half * (0.5 + scale_nibble) * 0.25
        for grid_index, sign_index in zip(grid_indices, sign_indices):
            sign_mask = _ksigns_iq2xs(sign_index)
            for j, grid_value in enumerate(IQ2XXS_GRID[grid_index]):
                sign = -1.0 if sign_mask & (1 << j) else 1.0
                values.append(db * grid_value * sign)
    return struct.pack("<e", d) + b"".join(groups), values


def _iq2_xxs_nontrivial_payload() -> tuple[bytes, list[float]]:
    payload = bytearray()
    values: list[float] = []
    for row in range(2):
        for block in range(2):
            block_payload, block_values = _iq2_xxs_block(scale_seed=3 + row * 7 + block * 11, d=0.75 + 0.25 * row + 0.125 * block)
            payload += block_payload
            values.extend(block_values)
    return bytes(payload), values


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


def test_ref_tool_converts_iq2_xxs_nontrivial_two_rows_two_blocks_golden(tmp_path) -> None:
    assert VCVARS64.exists(), "Visual Studio vcvars64.bat is required for CPU helper build"
    tool = _build_ref_tool(tmp_path)
    payload, expected_values = _iq2_xxs_nontrivial_payload()
    assert len(payload) == 2 * 2 * 66
    assert _convert(tool, "iq2_xxs", 2, 512, payload) == _q1_pack(expected_values)


def test_ref_tool_rejects_short_extra_and_overflow_payloads(tmp_path) -> None:
    assert VCVARS64.exists(), "Visual Studio vcvars64.bat is required for CPU helper build"
    tool = _build_ref_tool(tmp_path)
    payload = struct.pack("<e", 1.0) + bytes(64)

    short = subprocess.run(
        [str(tool), "convert", "iq2_xxs", "1", "256"],
        input=payload[:-1],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert short.returncode == 4
    assert b"too short" in short.stderr

    extra = subprocess.run(
        [str(tool), "convert", "iq2_xxs", "1", "256"],
        input=payload + b"x",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert extra.returncode == 4
    assert b"too long" in extra.stderr

    overflow = subprocess.run(
        [str(tool), "convert", "iq2_xxs", "9223372036854775807", "256"],
        input=b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert overflow.returncode == 2
    assert b"overflow" in overflow.stderr


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
    assert obj["helper"]["path"] == str(tool.resolve())
    assert obj["helper"]["size"] == tool.stat().st_size
    assert obj["helper"]["sha256"] == hashlib.sha256(tool.read_bytes()).hexdigest()
    assert "production IQ2_XXS/Q2_K -> float -> Q1_0" in obj["quality_note"]
    assert "blocked_real_dequant_source" not in obj
    parsed = parse_gguf_header(sidecar)
    for suffix in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
        assert parsed.tensors[f"blk.42.{suffix}"].type_id == Q1_TYPE_ID
    validate_runtime_sidecar_manifest(source, sidecar, manifest)
