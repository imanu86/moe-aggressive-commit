from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DS4_REPO = Path(
    os.environ.get(
        "DS4_WIN_REPO",
        r"C:\Users\imanu\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\ds4-win-work",
    )
)
DS4_COMMIT = "d1505358f429128943cadd8424fcaf0f6911f931"
EXPECTED_BLOBS = {
    "ds4.c": "4cda897f489d42f131cf681447d4cb5919256c2b",
    "ds4_cuda.cu": "590233ef127262177b18a794d963bf00ac88c735",
    "ds4_gpu.h": "92609ec4fe17fbf36b548cff5b820a10aa0d8511",
}
PATCHES = [
    ROOT / "patches" / "ds4" / "0052-ds4-q1-0-runtime-step1.patch",
    ROOT / "patches" / "ds4" / "0053-ds4-q1-0-runtime-step2.patch",
]


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def test_ds4_patch_artifacts_are_lf_git_patches() -> None:
    for patch in PATCHES:
        data = patch.read_bytes()
        assert data.startswith(b"diff")
        assert not data.startswith(b"\xef\xbb\xbf")
        assert not data.startswith(b"\xff\xfe")
        assert b"\x00" not in data
        assert b"\r\n" not in data


def test_ds4_patch_chain_base_blobs_and_apply_check(tmp_path: Path) -> None:
    for path, expected in EXPECTED_BLOBS.items():
        assert _git(["rev-parse", f"{DS4_COMMIT}:{path}"], DS4_REPO) == expected

    checkout = tmp_path / "ds4-clean"
    subprocess.check_call(
        ["git", "-c", "core.autocrlf=false", "clone", "--shared", "--no-checkout", str(DS4_REPO), str(checkout)]
    )
    _git(["config", "core.autocrlf", "false"], checkout)
    _git(["checkout", "-q", DS4_COMMIT], checkout)
    for patch in PATCHES:
        subprocess.check_call(["git", "apply", "--check", str(patch)], cwd=checkout)
        subprocess.check_call(["git", "apply", str(patch)], cwd=checkout)
