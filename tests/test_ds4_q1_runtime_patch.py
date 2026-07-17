from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "ds4" / "0052-ds4-q1-0-runtime-step1.patch"
NOTE = ROOT / "patches" / "ds4" / "0052-ds4-q1-0-runtime-step1.md"


def _patch_text() -> str:
    return PATCH.read_text(encoding="utf-8")


def test_q1_0_type41_layout_and_block_size_are_declared() -> None:
    text = _patch_text()
    assert '[41] = {"q1_0",   128,  18}' in text
    assert "DS4_TENSOR_Q1_0     = 41" in text
    assert "sizeof(block_q1_0) == 18" in text
    assert "sizeof(cuda_block_q1_0) == 18" in text
    assert "uint8_t  qs[128 / 8]" in text
    assert "routed_expert_block_elems" in text
    assert "case DS4_TENSOR_Q1_0: return 128u" in text


def test_q1_0_offsets_use_two_128_blocks_per_q8_k_block() -> None:
    text = _patch_text()
    assert "dev_dot_q1_0_q8_K_half128" in text
    assert "dev_dot_q1_0_q8_K_pair" in text
    assert "const uint32_t byte_base = half * 16u" in text
    assert "const uint32_t q8_base = half * 128u" in text
    assert "y->bsums[half * 8u + i]" in text
    assert "return (t->dim[0] / block_elems) * routed_expert_block_bytes(t->type)" in text


def test_q1_0_polarity_formula_is_positive_bit_and_fail_closed() -> None:
    text = _patch_text()
    assert "bit 1 => +d, bit 0 => -d" in text
    assert "2 * (int32_t)bit - 1" in text
    assert "const int32_t signed_sum = 2 * positive_sum - sum_all" in text
    assert "route_q1_0" in text
    assert "Q1_0 routed expert dispatch recognized" in text
    assert "return 0;" in text


def test_q1_0_binder_is_separate_from_iq1_s_and_iq1_env_off_is_not_deleted() -> None:
    text = _patch_text()
    assert "DS4_Q1_0_EXPERT_SIDECAR" in text
    assert "DS4_IQ1_S_EXPERT_SIDECAR" in text
    assert "DS4_IQ1_S_MIXED_COLD_K" not in "\n".join(
        line for line in text.splitlines() if line.startswith("-") and not line.startswith("---")
    )
    deleted_lines = [
        line
        for line in text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    assert not any("DS4_IQ1_S_EXPERT_SIDECAR" in line for line in deleted_lines)
    assert not any("g_iq1_s_" in line for line in deleted_lines)
    assert "gate_type == 19u && (down_type == 19u || down_type == 10u)" in text


def test_patch_note_cites_primary_source_commits_and_ds4_base() -> None:
    note = NOTE.read_text(encoding="utf-8")
    assert "d1505358f429128943cadd8424fcaf0f6911f931" in note
    assert "635cdd5fcc5bdeb8ec2e108bb2a40acf62d9039b" in note
    assert "ggml/src/ggml-cuda/dequantize.cuh:17-22" in note
    assert "c6747ad7a5d5d7a9d115ff211ca819ff262dfe1f" in note
