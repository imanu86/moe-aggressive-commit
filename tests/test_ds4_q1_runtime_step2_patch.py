from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "ds4" / "0053-ds4-q1-0-runtime-step2.patch"
NOTE = ROOT / "patches" / "ds4" / "0053-ds4-q1-0-runtime-step2.md"


def _patch_text() -> str:
    return PATCH.read_text(encoding="utf-8")


def test_step2_adds_separate_q1_sidecar_binder_and_source() -> None:
    text = _patch_text()
    assert "ds4_q1_0_sidecar" in text
    assert "static ds4_q1_0_sidecar g_q1_0_sidecar" in text
    assert "q1_0_sidecar_bind" in text
    assert "q1_0_sidecar_layer_active" in text
    assert "DS4_Q1_0_LAYER_FIRST" in text
    assert "DS4_Q1_0_LAYER_LAST" in text
    assert "source.model = g_q1_0_sidecar.model" in text


def test_step2_binder_validates_type41_offsets_and_bounds() -> None:
    text = _patch_text()
    assert "const uint32_t routed_first_layer = 3u" in text
    assert "const uint32_t routed_last_layer = DS4_N_LAYER - 1u" in text
    assert "uint32_t first_layer = routed_first_layer" in text
    assert "for (uint32_t il = first_layer; il <= last_layer; il++)" in text
    assert "first < routed_first_layer || first > routed_last_layer" in text
    assert "last < routed_first_layer || last > routed_last_layer" in text
    assert "tensor_expect_layout(gate, DS4_TENSOR_Q1_0" in text
    assert "tensor_expect_layout(up, DS4_TENSOR_Q1_0" in text
    assert "tensor_expect_layout(down, DS4_TENSOR_Q1_0" in text
    assert "g_q1_0_sidecar.gate_row_bytes[il] = gate_row_bytes" in text
    assert "g_q1_0_sidecar.down_expert_bytes[il] = down_expert_bytes" in text
    assert "Q1_0 sidecar routed expert tensor extends past file end" in text
    assert "dispatch=fail-closed" in text


def test_step2_accepts_type41_only_through_explicit_sidecar_binder() -> None:
    text = _patch_text()
    assert "q1_0_sidecar_bind" in text
    assert "tensor_expect_layout(gate, DS4_TENSOR_Q1_0, 3" in text
    assert "tensor_expect_layout(up, DS4_TENSOR_Q1_0, 3" in text
    assert "tensor_expect_layout(down, DS4_TENSOR_Q1_0, 3" in text
    assert "q1_0_sidecar_layer_active(model, layer_index)" in text


def test_step2_q1_sidecar_rejects_iq1_mixed_smoke_combo() -> None:
    text = _patch_text()
    assert "e->q1_0_sidecar_ready && iq1_s_mixed_cold_one_requested()" in text
    assert "Q1_0 expert sidecar is not compatible with DS4_IQ1_S_MIXED_COLD_K=1" in text


def test_step2_adds_q1_qwarp32_kernels_without_dispatching_them() -> None:
    text = _patch_text()
    assert "moe_gate_up_mid_q1_0_qwarp32_kernel" in text
    assert "moe_down_q1_0_qwarp32_kernel" in text
    assert "dev_dot_q1_0_q8_K_pair(gr + 2u * b" in text
    assert "dev_dot_q1_0_q8_K_pair(wr + 2u * b" in text
    assert "moe_gate_up_mid_q1_0_qwarp32_kernel<<<" not in text
    assert "moe_down_q1_0_qwarp32_kernel<<<" not in text


def test_step2_does_not_delete_iq1_env_or_mixed_path() -> None:
    text = _patch_text()
    deleted_lines = [
        line
        for line in text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    assert not any("DS4_IQ1_S_EXPERT_SIDECAR" in line for line in deleted_lines)
    assert not any("DS4_IQ1_S_MIXED_COLD_K" in line for line in deleted_lines)
    assert not any("g_iq1_s_sidecar" in line for line in deleted_lines)


def test_step2_note_records_fixture_and_smoke_sequence() -> None:
    note = NOTE.read_text(encoding="utf-8")
    assert "0052-ds4-q1-0-runtime-step1.patch" in note
    assert "DS4_Q1_0_EXPERT_SIDECAR" in note
    assert "--write-fixture" in note
    assert "Build `ds4` and `ds4_cuda` only" in note
