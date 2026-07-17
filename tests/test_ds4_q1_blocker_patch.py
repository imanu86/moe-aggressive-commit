from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "ds4" / "0054-ds4-q1-0-blocker-fixes-on-60f743d.patch"
NOTE = ROOT / "patches" / "ds4" / "0054-ds4-q1-0-blocker-fixes-on-60f743d.md"


def _patch_text() -> str:
    return PATCH.read_text(encoding="utf-8")


def test_incremental_patch_is_lf_git_patch() -> None:
    data = PATCH.read_bytes()
    assert data.startswith(b"diff")
    assert not data.startswith(b"\xef\xbb\xbf")
    assert not data.startswith(b"\xff\xfe")
    assert b"\x00" not in data
    assert b"\r\n" not in data


def test_q1_dot_half128_uses_current_block_qs_only() -> None:
    text = _patch_text()
    assert "-    const uint32_t byte_base = half * 16u;" in text
    assert "+        const uint32_t bits = (uint32_t)x->qs[byte];" in text
    assert "x->qs[byte_base + byte]" in text
    assert "const uint32_t q8_base = half * 128u;" not in "\n".join(
        line for line in text.splitlines() if line.startswith("-")
    )


def test_q1_binder_is_routed_only_3_to_42() -> None:
    text = _patch_text()
    assert "+    const uint32_t routed_first_layer = 3u;" in text
    assert "+    uint32_t first_layer = routed_first_layer;" in text
    assert "+    for (uint32_t il = first_layer; il <= last_layer; il++)" in text
    assert "+            first < routed_first_layer || first > routed_last_layer ||" in text
    assert "+            last < routed_first_layer || last > routed_last_layer ||" in text
    assert "-    for (uint32_t il = 0; il < DS4_N_LAYER; il++)" in text
    assert "DS4_IQ1_S_LAYER_FIRST" not in text


def test_primary_type41_is_removed_from_generic_routed_expert_gate() -> None:
    text = _patch_text()
    assert "-           type == DS4_TENSOR_Q1_0 ||" in text
    assert "+           type == DS4_TENSOR_Q1_0 ||" not in text
    assert "case DS4_TENSOR_Q1_0:    return sizeof(block_q1_0)" not in text


def test_q1_and_iq1_mixed_are_fail_closed_for_first_smoke() -> None:
    text = _patch_text()
    assert "+    if (e->q1_0_sidecar_ready && iq1_s_mixed_cold_one_requested()) {" in text
    assert "Q1_0 expert sidecar is not compatible with DS4_IQ1_S_MIXED_COLD_K=1" in text


def test_note_records_60f743d_base() -> None:
    note = NOTE.read_text(encoding="utf-8")
    assert "60f743de1104b1c8be6aadedde1f80d5470899dc" in note
    assert "ds4_cuda" in note
    assert "Do not run DS4" in note
