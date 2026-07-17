import pytest

from tools.ds4_q1_smoke import (
    GIB,
    Q1_BLOCK_BYTES,
    Q1_BLOCK_WEIGHTS,
    Q1_TYPE_ID,
    Q8KBlock,
    deterministic_values,
    dot_q1_pair_against_q8k,
    expert_offsets,
    q1_row_bytes,
    quantize_q1_0,
    read_synthetic_q1_gguf,
    reference_dot,
    residual_entry,
    routed_sizes,
    smoke_report,
    synthetic_q1_gguf_tensors,
    write_synthetic_q1_gguf,
)


def test_q1_0_type41_layout_contract() -> None:
    assert Q1_TYPE_ID == 41
    assert Q1_BLOCK_WEIGHTS == 128
    assert Q1_BLOCK_BYTES == 18
    assert Q1_BLOCK_BYTES * 8 / Q1_BLOCK_WEIGHTS == 1.125
    assert q1_row_bytes(4096) == 576
    assert q1_row_bytes(2048) == 288


def test_q1_0_routed_size_accounting() -> None:
    sizes = routed_sizes()
    assert sizes["q1_gate_or_up_expert_bytes"] == 1_179_648
    assert sizes["q1_down_expert_bytes"] == 1_179_648
    assert sizes["q1_expert_bytes"] == 3_538_944
    assert sizes["q1_expert_mib"] == 3.375
    assert sizes["q1_all_routed_gib"] == 33.75
    assert sizes["q1_all_routed_gib"] < 46.875


def test_q1_pack_roundtrip_and_dot_identity() -> None:
    values = deterministic_values(256)
    low = quantize_q1_0(values[:128])
    high = quantize_q1_0(values[128:])
    packed = low.pack() + high.pack()
    assert len(packed) == 36
    x = Q8KBlock.from_values(values)
    fast = dot_q1_pair_against_q8k(low, high, x)
    ref = reference_dot((low, high), x)
    assert fast == pytest.approx(ref, abs=1e-5)


def test_expert_offsets_are_monotonic_and_layer_scoped() -> None:
    first = expert_offsets(3, 0)
    next_expert = expert_offsets(3, 1)
    next_layer = expert_offsets(4, 0)
    sizes = routed_sizes()
    assert first.q1_gate == 0
    assert first.q1_up == sizes["q1_gate_or_up_expert_bytes"]
    assert first.q1_down == sizes["q1_gate_or_up_expert_bytes"] * 2
    assert next_expert.q1_gate - first.q1_gate == sizes["q1_expert_bytes"]
    assert next_layer.q1_gate - first.q1_gate == sizes["q1_expert_bytes"] * 256


def test_residual_index_points_to_q1_block_and_authoritative_iq2_tensor() -> None:
    entry = residual_entry(3, 7, "gate", block_first=5, block_count=9, residual_offset=4096)
    offsets = expert_offsets(3, 7)
    assert entry.q1_offset == offsets.q1_gate + 5 * Q1_BLOCK_BYTES
    assert entry.iq2_offset == offsets.iq2_gate
    assert entry.residual_bytes == 18


def test_smoke_report_passes_without_model_payloads() -> None:
    report = smoke_report()
    assert report["synthetic_block"]["roundtrip_equal"] is True
    assert report["synthetic_block"]["dot_pass"] is True
    assert report["sizes"]["q1_all_routed_gib"] == pytest.approx(33.75)
    assert report["sizes"]["q1_all_routed_gib"] * GIB == report["sizes"]["q1_expert_bytes"] * 256 * 40


def test_synthetic_q1_gguf_fixture_type41_offsets(tmp_path) -> None:
    path = tmp_path / "q1_0_type41_fixture.gguf"
    expected = synthetic_q1_gguf_tensors(experts=2)
    written = write_synthetic_q1_gguf(path, experts=2)
    parsed = read_synthetic_q1_gguf(path)
    assert written == expected
    assert parsed == expected
    assert path.stat().st_size < 1024
    assert [t.name for t in parsed] == [
        "blk.3.ffn_gate_exps.weight",
        "blk.3.ffn_up_exps.weight",
        "blk.3.ffn_down_exps.weight",
    ]
    assert all(t.type_id == Q1_TYPE_ID for t in parsed)
    assert all(t.dims == (Q1_BLOCK_WEIGHTS, 1, 2) for t in parsed)
    assert all(t.nbytes == 2 * Q1_BLOCK_BYTES for t in parsed)
    assert [t.offset for t in parsed] == [0, 64, 128]
