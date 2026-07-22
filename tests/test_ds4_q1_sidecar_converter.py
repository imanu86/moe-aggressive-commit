from __future__ import annotations

import json
import struct
import hashlib

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
    convert_runtime_extension_layer_range_sidecar,
    convert_runtime_valid_single_layer_sidecar,
    convert_runtime_valid_layer_range_sidecar,
    estimate_runtime_extension_layer_range_plan,
    estimate_runtime_sidecar_plan,
    estimate_runtime_layer_range_sidecar_plan,
    parse_gguf_header,
    validate_manifest,
    validate_runtime_extension_manifest,
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
    tensors.append(
        GgufWriteTensor(
            f"blk.{target_layer}.ffn_gate_inp.weight",
            (8,),
            SYNTHETIC_IQ2_TYPE_ID,
            _i16_payload(8, seed=500 + target_layer),
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


def _runtime_range_fixture(path, layer_first: int = 3, layer_last: int = 5) -> None:
    tensors: list[GgufWriteTensor] = []
    target_layers = tuple(range(layer_first, layer_last + 1))
    for layer in range(43):
        for suffix in ("attn_norm.weight", "ffn_norm.weight"):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{suffix}",
                    (8,),
                    SYNTHETIC_IQ2_TYPE_ID,
                    _i16_payload(8, seed=layer * 17 + len(tensors)),
                )
            )
    for layer in range(3, 43):
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.exp_probs_b.bias",
                (4,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(4, seed=900 + layer),
            )
        )
    for layer in target_layers:
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.ffn_gate_inp.weight",
                (8,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(8, seed=1000 + layer),
            )
        )
        for kind, type_id in (
            ("ffn_gate_exps.weight", SYNTHETIC_IQ2_TYPE_ID),
            ("ffn_up_exps.weight", SYNTHETIC_IQ2_TYPE_ID),
            ("ffn_down_exps.weight", SYNTHETIC_Q2_TYPE_ID),
        ):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{kind}",
                    (Q1_BLOCK_WEIGHTS, 1, 2),
                    type_id,
                    _i16_payload(Q1_BLOCK_WEIGHTS * 2, seed=1000 + len(tensors)),
                )
            )
    write_gguf(
        path,
        [GgufMetadata("general.name", GGUF_VALUE_TYPE_STRING, "ds4-mini-range-fixture")],
        tensors,
    )


def _runtime_extension_primary_fixture(path, layer_first: int = 0, layer_last: int = 5) -> None:
    tensors: list[GgufWriteTensor] = []
    target_layers = tuple(range(layer_first, layer_last + 1))
    for layer in range(43):
        for suffix in ("attn_norm.weight", "ffn_norm.weight"):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{suffix}",
                    (8,),
                    SYNTHETIC_IQ2_TYPE_ID,
                    _i16_payload(8, seed=3000 + layer * 17 + len(tensors)),
                )
            )
    for layer in range(3, 43):
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.exp_probs_b.bias",
                (4,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(4, seed=3900 + layer),
            )
        )
    for layer in target_layers:
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.ffn_gate_inp.weight",
                (8,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(8, seed=4000 + layer),
            )
        )
        for kind, type_id in (
            ("ffn_gate_exps.weight", SYNTHETIC_IQ2_TYPE_ID),
            ("ffn_up_exps.weight", SYNTHETIC_IQ2_TYPE_ID),
            ("ffn_down_exps.weight", SYNTHETIC_Q2_TYPE_ID),
        ):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{kind}",
                    (Q1_BLOCK_WEIGHTS, 1, 2),
                    type_id,
                    _i16_payload(Q1_BLOCK_WEIGHTS * 2, seed=4100 + layer * 11 + len(tensors)),
                )
            )
    write_gguf(
        path,
        [GgufMetadata("general.name", GGUF_VALUE_TYPE_STRING, "ds4-mini-extension-fixture")],
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
    tensors.append(
        GgufWriteTensor(
            f"blk.{target_layer}.ffn_gate_inp.weight",
            (8,),
            SYNTHETIC_IQ2_TYPE_ID,
            _i16_payload(8, seed=600 + target_layer),
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


def _q2_k_fixture_payload() -> bytes:
    scales = bytes(((i % 4) + 1) | (((i % 3) + 1) << 4) for i in range(16))
    qs = bytes(((i * 37 + 11) & 0xFF) for i in range(64))
    return scales + qs + struct.pack("<e", 1.0) + struct.pack("<e", 0.5)


def _runtime_mixed_real_fixture(path, target_layer: int = 42) -> None:
    tensors: list[GgufWriteTensor] = []
    for layer in range(43):
        for suffix in ("attn_norm.weight", "ffn_norm.weight"):
            tensors.append(
                GgufWriteTensor(
                    f"blk.{layer}.{suffix}",
                    (8,),
                    SYNTHETIC_IQ2_TYPE_ID,
                    _i16_payload(8, seed=layer * 13 + len(tensors)),
                )
            )
    for layer in range(3, 43):
        tensors.append(
            GgufWriteTensor(
                f"blk.{layer}.exp_probs_b.bias",
                (4,),
                SYNTHETIC_IQ2_TYPE_ID,
                _i16_payload(4, seed=700 + layer),
            )
        )
    tensors.append(
        GgufWriteTensor(
            f"blk.{target_layer}.ffn_gate_inp.weight",
            (8,),
            SYNTHETIC_IQ2_TYPE_ID,
            _i16_payload(8, seed=800 + target_layer),
        )
    )
    iq2_payload = struct.pack("<e", 1.0) + bytes(64)
    q2_payload = _q2_k_fixture_payload()
    for kind, type_id, payload in (
        ("ffn_gate_exps.weight", 16, iq2_payload),
        ("ffn_up_exps.weight", 16, iq2_payload),
        ("ffn_down_exps.weight", 10, q2_payload),
    ):
        tensors.append(
            GgufWriteTensor(
                f"blk.{target_layer}.{kind}",
                (256,),
                type_id,
                payload,
            )
        )
    write_gguf(
        path,
        [GgufMetadata("general.name", GGUF_VALUE_TYPE_STRING, "ds4-real-mini-fixture")],
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
    assert len(plan.tensors_to_copy) == 43 * 2 + 40 + 1
    assert len(plan.tensors_to_convert) == 3
    assert plan.estimated_read_bytes < source.stat().st_size

    obj = convert_runtime_valid_single_layer_sidecar(source, sidecar, manifest, layer=42)
    assert obj["schema"] == RUNTIME_MANIFEST_SCHEMA
    assert obj["derived_from_IQ2"] is True
    assert obj["not_quality_optimal"] is True
    assert "production IQ2_XXS/Q2_K -> float -> Q1_0" in obj["quality_note"]
    assert "int16 fixture" not in obj["quality_note"]
    assert "blocked_real_dequant_source" not in obj
    assert obj["helper"] is None
    assert obj["output"]["sha256"] == hashlib.sha256(sidecar.read_bytes()).hexdigest()
    metadata_records = {m["key"]: m for m in obj["metadata"]}
    assert metadata_records["general.name"]["value"] == "ds4-mini-fixture"
    assert metadata_records["general.name"]["raw_sha256"]

    parsed = parse_gguf_header(sidecar)
    assert parsed.metadata["general.name"].value == "ds4-mini-fixture"
    for layer in range(43):
        assert f"blk.{layer}.attn_norm.weight" in parsed.tensors
        assert f"blk.{layer}.ffn_norm.weight" in parsed.tensors
    for layer in range(3, 43):
        assert f"blk.{layer}.exp_probs_b.bias" in parsed.tensors
    assert "blk.42.ffn_gate_inp.weight" in parsed.tensors
    for suffix in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
        assert parsed.tensors[f"blk.42.{suffix}"].type_id == Q1_TYPE_ID

    validated = validate_runtime_sidecar_manifest(source, sidecar, manifest)
    copy_records = [t for t in validated["tensors"] if t["action"] == "copy_byte_identical"]
    assert copy_records
    assert all(t["source_sha256"] == t["output_sha256"] for t in copy_records)
    assert len(validated["tensors"]) == 43 * 2 + 40 + 1 + 3


def test_runtime_valid_layer_range_sidecar_fixture(tmp_path) -> None:
    source = tmp_path / "ds4-mini-primary.gguf"
    sidecar = tmp_path / "ds4-mini-q1-range-sidecar.gguf"
    manifest = tmp_path / "ds4-mini-q1-range-sidecar.manifest.json"
    _runtime_range_fixture(source, layer_first=3, layer_last=5)

    plan = estimate_runtime_layer_range_sidecar_plan(source, sidecar, manifest, layer_first=3, layer_last=5)
    assert plan.layer == 3
    assert plan.layers == (3, 4, 5)
    assert len(plan.tensors_to_copy) == 43 * 2 + 40 + 3
    assert len(plan.tensors_to_convert) == 3 * 3
    assert plan.estimated_read_bytes < source.stat().st_size

    obj = convert_runtime_valid_layer_range_sidecar(source, sidecar, manifest, layer_first=3, layer_last=5)
    assert obj["schema"] == RUNTIME_MANIFEST_SCHEMA
    assert obj["layer"] == 3
    assert obj["layers"] == [3, 4, 5]
    assert obj["layer_first"] == 3
    assert obj["layer_last"] == 5
    assert obj["output"]["sha256"] == hashlib.sha256(sidecar.read_bytes()).hexdigest()

    parsed = parse_gguf_header(sidecar)
    for layer in (3, 4, 5):
        assert f"blk.{layer}.ffn_gate_inp.weight" in parsed.tensors
        for suffix in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
            assert parsed.tensors[f"blk.{layer}.{suffix}"].type_id == Q1_TYPE_ID

    validated = validate_runtime_sidecar_manifest(source, sidecar, manifest)
    assert len(validated["tensors"]) == 43 * 2 + 40 + 3 + 9
    convert_records = [t for t in validated["tensors"] if t["action"] == "convert_iq2_or_q2_to_q1_0"]
    assert len(convert_records) == 9
    assert all(t["output_type_id"] == Q1_TYPE_ID for t in convert_records)


def test_runtime_extension_reuses_base_q1_and_converts_only_prefix_layers(tmp_path) -> None:
    primary = tmp_path / "ds4-mini-primary.gguf"
    base = tmp_path / "ds4-mini-base-q1.gguf"
    base_manifest = tmp_path / "ds4-mini-base-q1.manifest.json"
    extended = tmp_path / "ds4-mini-extended-q1.gguf"
    manifest = tmp_path / "ds4-mini-extended-q1.manifest.json"
    _runtime_extension_primary_fixture(primary, layer_first=0, layer_last=5)
    convert_runtime_valid_layer_range_sidecar(primary, base, base_manifest, layer_first=3, layer_last=5)

    plan = estimate_runtime_extension_layer_range_plan(
        primary,
        base,
        extended,
        manifest,
        convert_layer_first=0,
        convert_layer_last=2,
        base_layer_first=3,
        base_layer_last=5,
    )
    assert plan.layers == (0, 1, 2)
    assert plan.base_layers == (3, 4, 5)
    assert len(plan.primary_copy_tensors) == 3
    assert len(plan.primary_convert_tensors) == 9
    assert len(plan.base_reuse_tensors) == len(parse_gguf_header(base).tensors)

    obj = convert_runtime_extension_layer_range_sidecar(
        primary,
        base,
        extended,
        manifest,
        convert_layer_first=0,
        convert_layer_last=2,
        base_layer_first=3,
        base_layer_last=5,
    )
    assert obj["schema"] == "ds4_q1_0_runtime_sidecar_extension_manifest_v1"
    assert obj["converted_layers"] == [0, 1, 2]
    assert obj["base_reused_layers"] == [3, 4, 5]
    assert obj["primary"]["sha256"] == hashlib.sha256(primary.read_bytes()).hexdigest()
    assert obj["base_sidecar"]["sha256"] == hashlib.sha256(base.read_bytes()).hexdigest()
    assert obj["output"]["sha256"] == hashlib.sha256(extended.read_bytes()).hexdigest()

    parsed = parse_gguf_header(extended)
    for layer in range(6):
        assert f"blk.{layer}.ffn_gate_inp.weight" in parsed.tensors
        for suffix in ("ffn_gate_exps.weight", "ffn_up_exps.weight", "ffn_down_exps.weight"):
            assert parsed.tensors[f"blk.{layer}.{suffix}"].type_id == Q1_TYPE_ID

    validated = validate_runtime_extension_manifest(primary, base, extended, manifest)
    reused = [t for t in validated["tensors"] if t["action"] == "reuse_q1_byte_identical_from_base"]
    converted = [t for t in validated["tensors"] if t["action"] == "convert_primary_iq2_or_q2_to_q1_0"]
    copied = [t for t in validated["tensors"] if t["action"] == "copy_primary_byte_identical"]
    assert len(reused) == len(parse_gguf_header(base).tensors)
    assert len(converted) == 9
    assert len(copied) == 3
    assert all(t["source_sha256"] == t["output_sha256"] for t in reused)
    assert not list(tmp_path.glob("*.partial.*"))


def test_runtime_extension_rejects_stale_base_hash(tmp_path) -> None:
    primary = tmp_path / "ds4-mini-primary.gguf"
    base = tmp_path / "ds4-mini-base-q1.gguf"
    base_manifest = tmp_path / "ds4-mini-base-q1.manifest.json"
    extended = tmp_path / "ds4-mini-extended-q1.gguf"
    manifest = tmp_path / "ds4-mini-extended-q1.manifest.json"
    _runtime_extension_primary_fixture(primary, layer_first=0, layer_last=5)
    convert_runtime_valid_layer_range_sidecar(primary, base, base_manifest, layer_first=3, layer_last=5)
    convert_runtime_extension_layer_range_sidecar(
        primary,
        base,
        extended,
        manifest,
        convert_layer_first=0,
        convert_layer_last=2,
        base_layer_first=3,
        base_layer_last=5,
    )

    data = bytearray(base.read_bytes())
    data[-1] ^= 1
    base.write_bytes(bytes(data))
    try:
        validate_runtime_extension_manifest(primary, base, extended, manifest)
    except ValueError as exc:
        assert "base sidecar full hash mismatch" in str(exc)
    else:
        raise AssertionError("runtime extension validator accepted stale base sidecar")


def test_runtime_sidecar_rejects_out_of_range_layer(tmp_path) -> None:
    source = tmp_path / "ds4-mini-primary.gguf"
    _runtime_fixture(source, target_layer=42)
    try:
        estimate_runtime_sidecar_plan(source, tmp_path / "out.gguf", tmp_path / "out.json", layer=2)
    except ValueError as exc:
        assert "3..42" in str(exc)
    else:
        raise AssertionError("layer 2 should not be accepted for Q1_0 runtime sidecar")


def test_runtime_sidecar_rejects_out_of_range_layer_range(tmp_path) -> None:
    source = tmp_path / "ds4-mini-primary.gguf"
    _runtime_range_fixture(source, layer_first=3, layer_last=5)
    try:
        estimate_runtime_layer_range_sidecar_plan(source, tmp_path / "out.gguf", tmp_path / "out.json", layer_first=2, layer_last=5)
    except ValueError as exc:
        assert "3..42" in str(exc)
    else:
        raise AssertionError("layer range starting at 2 should not be accepted")

    try:
        estimate_runtime_layer_range_sidecar_plan(source, tmp_path / "out.gguf", tmp_path / "out.json", layer_first=6, layer_last=5)
    except ValueError as exc:
        assert "3..42" in str(exc)
    else:
        raise AssertionError("inverted layer range should not be accepted")


def test_runtime_validator_rejects_incomplete_duplicate_or_stale_metadata(tmp_path) -> None:
    source = tmp_path / "ds4-mini-primary.gguf"
    sidecar = tmp_path / "ds4-mini-q1-sidecar.gguf"
    manifest = tmp_path / "ds4-mini-q1-sidecar.manifest.json"
    _runtime_fixture(source, target_layer=42)
    convert_runtime_valid_single_layer_sidecar(source, sidecar, manifest, layer=42)

    obj = json.loads(manifest.read_text(encoding="utf-8"))
    original = json.dumps(obj, indent=2, sort_keys=True)
    obj["tensors"] = obj["tensors"][:-1]
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    try:
        validate_runtime_sidecar_manifest(source, sidecar, manifest)
    except ValueError as exc:
        assert "record set mismatch" in str(exc)
    else:
        raise AssertionError("validator accepted an incomplete runtime tensor manifest")

    obj = json.loads(original)
    obj["tensors"].append(obj["tensors"][0])
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    try:
        validate_runtime_sidecar_manifest(source, sidecar, manifest)
    except ValueError as exc:
        assert "duplicate runtime tensor records" in str(exc)
    else:
        raise AssertionError("validator accepted duplicate runtime tensor records")

    obj = json.loads(original)
    obj["metadata"][0]["value"] = "wrong-model-name"
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    try:
        validate_runtime_sidecar_manifest(source, sidecar, manifest)
    except ValueError as exc:
        assert "metadata provenance mismatch" in str(exc)
    else:
        raise AssertionError("validator accepted stale runtime metadata")


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
