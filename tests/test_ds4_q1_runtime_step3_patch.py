from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "ds4" / "0055-ds4-q1-0-runtime-step3-dispatch.patch"
INCREMENTAL = ROOT / "patches" / "ds4" / "0055-ds4-q1-0-runtime-step3-on-6a44578.patch"
NOTE = ROOT / "patches" / "ds4" / "0055-ds4-q1-0-runtime-step3-dispatch.md"
DS4_6A44578_REPO = Path(
    r"C:\Users\imanu\Documents\Codex\w\q1step3-6a44578-4b1eea07"
)


def _text(path: Path = PATCH) -> str:
    return path.read_text(encoding="utf-8")


def test_step3_patches_are_lf_git_patches() -> None:
    for patch in (PATCH, INCREMENTAL):
        data = patch.read_bytes()
        assert data.startswith(b"diff")
        assert not data.startswith(b"\xef\xbb\xbf")
        assert not data.startswith(b"\xff\xfe")
        assert b"\x00" not in data
        assert b"\r\n" not in data


def test_step3_adds_dedicated_q1_sidecar_setter_and_file_source() -> None:
    text = _text()
    assert "ds4_gpu_set_q1_0_sidecar" in text
    assert "g_q1_0_sidecar_file" in text
    assert "g_q1_0_sidecar_host_base" in text
    assert "g_q1_0_sidecar_size" in text
    assert "CUDA Q1_0 routed-expert sidecar installed" in text
    assert "failed to install Q1_0 expert sidecar in CUDA" in text


def test_step3_adds_q1_selected_load_opt_in_and_telemetry() -> None:
    text = _text()
    assert "cuda_moe_selected_load_q1_0" in text
    assert "DS4_Q1_0_SELECTED_LOAD" in text
    assert "cuda_pread_full(&g_q1_0_sidecar_file" in text
    assert "g_q1_0_route_calls" in text
    assert "g_q1_0_route_slots" in text
    assert "g_q1_0_selected_loads" in text
    assert "g_q1_0_selected_load_failures" in text
    assert "Q1_0 sidecar selected load failed closed" in text


def test_step3_dispatches_q1_qwarp32_kernels_only_after_selected_load() -> None:
    text = _text()
    assert "route_q1_0" in text
    assert "moe_gate_up_mid_q1_0_qwarp32_kernel<<<" in text
    assert "moe_down_q1_0_qwarp32_kernel<<<" in text
    assert "routed_moe Q1_0 gate/up launch" in text
    assert "routed_moe Q1_0 down launch" in text
    assert "return ok;" in text


def test_step3_keeps_iq1_paths_separate() -> None:
    text = _text()
    deleted_lines = [
        line
        for line in text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    assert not any("DS4_IQ1_S_EXPERT_SIDECAR" in line for line in deleted_lines)
    assert not any("DS4_IQ1_S_MIXED_COLD_K" in line for line in deleted_lines)
    assert "route_iq1_s || route_q1_0" in text


def test_step3_note_records_6a44578_incremental_base() -> None:
    note = NOTE.read_text(encoding="utf-8")
    assert "6a44578" in note
    assert "direct `pread` path is a structural smoke" in note


def test_step3_incremental_apply_check_on_6a44578(tmp_path: Path) -> None:
    checkout = tmp_path / "ds4-6a44578"
    subprocess.check_call(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "clone",
            "--shared",
            "--no-checkout",
            str(DS4_6A44578_REPO),
            str(checkout),
        ]
    )
    subprocess.check_call(["git", "config", "core.autocrlf", "false"], cwd=checkout)
    subprocess.check_call(["git", "checkout", "-q", "6a44578"], cwd=checkout)
    subprocess.check_call(["git", "apply", "--check", str(INCREMENTAL)], cwd=checkout)
