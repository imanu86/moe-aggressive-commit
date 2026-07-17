from __future__ import annotations

import json

from tools.ds4_q1_sidecar_converter import (
    GGUF_VALUE_TYPE_STRING,
    MANIFEST_SCHEMA,
    Q1_TYPE_ID,
    RUNTIME_MANIFEST_SCHEMA,
    REAL_DEQUANT_BLOCKED_MESSAGE,
    SYNTHETIC_IQ2_TYPE_ID,
    SYNTHETIC_Q2_TYPE_ID,
    GgufMetadata,
    GgufWriteTensor,
    convert_synthetic_iq2_to_q1,
    convert_runtime_valid_single_layer_sidecar,
    estimate_runtime_sidecar_plan,
    parse_gguf_header,
    validate_manifest,
    validate_runtime_sidecar_manifest,
    write_gguf,
    write_synthetic_iq2_fixture,
)
from tools.ds4_q1_smoke import Q1_BLOCK_BYTES, Q1_BLOCK_WEIGHTS, deterministic_values, read_synthetic_q1_gguf


def _i16_payload(count: int, seed: int) -> bytes:
    out = bytearray()
    for value in deterministic_values(count, seed=seed):
        out += int(max(-32768, min(32767, round(value * 2048.0)))).to_bytes(2, "little", signed=True)
    return bytes(out)


def _runtime_fixture(path, target_layer: int = 42) -> None:
    tensors: list[GgufWriteTensor] = []
    for layer in range(43):
        for suffix in ("attn_norm.weight", "ffn_norm.weight"):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{suffix}",
                    (8,),
                    SYNTHETIC_IQ2_TYPE_ID,
                    _i16_payload(8, seed=layer * 7 + len(tensors)),
                )
            )
    for layer in range(3, 43):
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.exp_probs_b.bias",
                (4,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(4, seed=200 + layer),
            )
        )
    for kind, type_id in (
        ("ffn_gate_exps.weight", SYNTHETIC_IQ2_TYPE_ID),
        ("ffn_up_exps.weight", SYNTHETIC_IQ2_TYPE_ID),
        ("ffn_down_exps.weight", SYNTHETIC_Q2_TYPE_ID),
    ):
        tensors.append(
            GgufWriteTensor(
                f"blk.{target_layer}.{kind}",
                (Q1_BLOCK_WEIGHTS, 1, 2),
                type_id,
                _i16_payload(Q1_BLOCK_WEIGHTS * 2, seed=500 + len(tensors)),
            )
        )
    write_gguf(
        path,
        [GgufMetadata("general.name", GGUF_VALUE_TYPE_STRING, "ds4-mini-fixture")],
        tensors,
    )


def _runtime_real_like_blocked_fixture(path, target_layer: int = 42) -> None:
    tensors: list[GgufWriteTensor] = []
    for layer in range(43):
        for suffix in ("attn_norm.weight", "ffn_norm.weight"):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{suffix}",
                    (8,),
                    SYNTHETIC_IQ2_TYPE_ID,
                    _i16_payload(8, seed=layer * 11 + len(tensors)),
                )
            )
    for layer in range(3, 43):
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.exp_probs_b.bias",
                (4,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(4, seed=300 + layer),
            )
        )
    for kind in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
        tensors.append(
            GgufWriteTensor(
                f"blk.{target_layer}.{kind}",
                (256, 1, 1),
                16,
                bytes(66),
            )
        )
    write_gguf(
        path,
        [GgufMetadata("general.name", GGUF_VALUE_TYPE_STRING, "ds4-real-like-blocked-fixture")],
        tensors,
    )


def test_synthetic_iq2_fixture_and_q1_sidecar_conversion(tmp_path) -> None:
    source = tmp_path / "synthetic_iq2.gguf"
    sidecar = tmp_path / "synthetic_q1_sidecar.gguf"
    manifest = tmp_path / "synthetic_q1_sidecar.manifest.json"

    source_tensors = write_synthetic_iq2_fixture(source, experts=2)
    assert all(t.type_id == SYNTHETIC_IQ2_TYPE_ID for t in source_tensors)

    obj = convert_synthetic_iq2_to_q1(source, sidecar, manifest)
    assert obj["schema"] == MANIFEST_SCHEMA
    assert obj["derived"] is True
    assert "not quality-optimal" in obj["quality_note"]

    sidecar_tensors = read_synthetic_q1_gguf(sidecar)
    assert [t.name for t in sidecar_tensors] == [t.name for t in source_tensors]
    assert all(t.type_id == Q1_TYPE_ID for t in sidecar_tensors)
    assert all(t.nbytes == 2 * Q1_BLOCK_BYTES for t in sidecar_tensors)
    assert [t.offset for t in sidecar_tensors] == [0, 64, 128]

    validated = validate_manifest(source, sidecar, manifest)
    assert validated["sidecar"]["sha256"] == obj["sidecar"]["sha256"]


def test_validator_rejects_hash_mismatch(tmp_path) -> None:
    source = tmp_path / "synthetic_iq2.gguf"
    sidecar = tmp_path / "synthetic_q1_sidecar.gguf"
    manifest = tmp_path / "synthetic_q1_sidecar.manifest.json"
    write_synthetic_iq2_fixture(source, experts=1)
    convert_synthetic_iq2_to_q1(source, sidecar, manifest)

    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sidecar"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")

    try:
        validate_manifest(source, sidecar, manifest)
    except ValueError as exc:
        assert "sidecar hash mismatch" in str(exc)
    else:
        raise AssertionError("validator accepted a mismatched sidecar hash")


def test_runtime_valid_single_layer_sidecar_fixture(tmp_path) -> None:
    source = tmp_path / "ds4-mini-primary.gguf"
    sidecar = tmp_path / "ds4-mini-q1-sidecar.gguf"
    manifest = tmp_path / "ds4-mini-q1-sidecar.manifest.json"
    _runtime_fixture(source, target_layer=42)

    plan = estimate_runtime_sidecar_plan(source, sidecar, manifest, layer=42)
    assert plan.layer == 42
    assert len(plan.tensors_to_copy) == 43 * 2 + 40
    assert len(plan.tensors_to_convert) == 3
    assert plan.estimated_read_bytes < source.stat().st_size

    obj = convert_runtime_valid_single_layer_sidecar(source, sidecar, manifest, layer=42)
    assert obj["schema"] == RUNTIME_MANIFEST_SCHEMA
    assert obj["derived_from_IQ2"] is True
    assert obj["not_quality_optimal"] is True

    parsed = parse_gguf_header(sidecar)
    assert parsed.metadata["general.name"].value == "ds4-mini-fixture"
    for layer in range(43):
        assert f"blk.{layer}.attn_norm.weight" in parsed.tensors
        assert f"blk.{layer}.ffn_norm.weight" in parsed.tensors
    for layer in range(3, 43):
        assert f"blk.{layer}.exp_probs_b.bias" in parsed.tensors
    for suffix in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
        assert parsed.tensors[f"blk.42.{suffix}"].type_id == Q1_TYPE_ID

    validated = validate_runtime_sidecar_manifest(source, sidecar, manifest)
    copy_records = [t for t in validated["tensors"] if t["action"] == "copy_byte_identical"]
    assert copy_records
    assert all(t["source_sha256"] == t["output_sha256"] for t in copy_records)


def test_runtime_sidecar_rejects_out_of_range_layer(tmp_path) -> None:
    source = tmp_path / "ds4-mini-primary.gguf"
    _runtime_fixture(source, target_layer=42)
    try:
        estimate_runtime_sidecar_plan(source, tmp_path / "out.gguf", tmp_path / "out.json", layer=2)
    except ValueError as exc:
        assert "3..42" in str(exc)
    else:
        raise AssertionError("layer 2 should not be accepted for Q1_0 runtime sidecar")


def test_runtime_real_iq2_payload_conversion_is_blocked_without_verified_dequant(tmp_path) -> None:
    source = tmp_path / "ds4-real-like-primary.gguf"
    sidecar = tmp_path / "blocked-sidecar.gguf"
    manifest = tmp_path / "blocked-sidecar.manifest.json"
    _runtime_real_like_blocked_fixture(source, target_layer=42)

    plan = estimate_runtime_sidecar_plan(source, sidecar, manifest, layer=42)
    assert plan.estimated_read_bytes > 0

    try:
        convert_runtime_valid_single_layer_sidecar(source, sidecar, manifest, layer=42)
    except ValueError as exc:
        assert REAL_DEQUANT_BLOCKED_MESSAGE in str(exc)
        assert "type16" in str(exc)
    else:
        raise AssertionError("real IQ2_XXS-like payload conversion must be blocked")
    assert not sidecar.exists()
    assert not manifest.exists()
