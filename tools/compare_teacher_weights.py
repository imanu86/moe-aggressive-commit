#!/usr/bin/env python3
"""Assert byte-for-byte equality of two teacher weight NPZ archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


WEIGHT_KEYS = ("gate", "up", "down")


def array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(memoryview(contiguous).cast("B")).hexdigest()


def compare_weight_archives(first_path: Path, second_path: Path) -> dict:
    result: dict[str, object] = {
        "first": str(first_path),
        "second": str(second_path),
        "npz_byte_identical": (
            first_path.stat().st_size == second_path.stat().st_size
            and hashlib.sha256(first_path.read_bytes()).digest()
            == hashlib.sha256(second_path.read_bytes()).digest()
        ),
        "arrays": {},
    }
    with (
        np.load(first_path, allow_pickle=False) as first,
        np.load(second_path, allow_pickle=False) as second,
    ):
        missing_first = [key for key in WEIGHT_KEYS if key not in first.files]
        missing_second = [key for key in WEIGHT_KEYS if key not in second.files]
        if missing_first or missing_second:
            raise AssertionError(
                f"missing weights: first={missing_first}, second={missing_second}"
            )
        arrays = result["arrays"]
        assert isinstance(arrays, dict)
        for key in WEIGHT_KEYS:
            left = np.ascontiguousarray(first[key])
            right = np.ascontiguousarray(second[key])
            if left.shape != right.shape:
                raise AssertionError(f"{key}: shape differs: {left.shape} != {right.shape}")
            if left.dtype != right.dtype:
                raise AssertionError(f"{key}: dtype differs: {left.dtype} != {right.dtype}")
            left_bytes = memoryview(left).cast("B")
            right_bytes = memoryview(right).cast("B")
            if left_bytes != right_bytes:
                unequal = int(np.count_nonzero(left.view(np.uint32) != right.view(np.uint32)))
                raise AssertionError(f"{key}: {unequal} float32 bit patterns differ")
            arrays[key] = {
                "shape": list(left.shape),
                "dtype": left.dtype.str,
                "bytes": left.nbytes,
                "sha256": array_sha256(left),
                "exact": True,
            }
    result["exact"] = True
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path, help="First gate/up/down weights.npz")
    parser.add_argument("second", type=Path, help="Second gate/up/down weights.npz")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(compare_weight_archives(args.first, args.second), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
