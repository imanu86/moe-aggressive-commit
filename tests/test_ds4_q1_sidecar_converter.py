from __future__ import annotations

import json

from tools.ds4_q1_sidecar_converter import (
    MANIFEST_SCHEMA,
    Q1_TYPE_ID,
    SYNTHETIC_IQ2_TYPE_ID,
    convert_synthetic_iq2_to_q1,
    validate_manifest,
    write_synthetic_iq2_fixture,
)
from tools.ds4_q1_smoke import Q1_BLOCK_BYTES, read_synthetic_q1_gguf


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
