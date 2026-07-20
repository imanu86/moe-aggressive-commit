#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from activation_reader import ManifestTraceReader, sha256_file
from activation_trainer import (
    ExpertWeights,
    binary_g128,
    evaluate_stream,
    quantize_expert_binary,
    quantize_expert_ternary,
    greedy_sign_flip_probe,
    tune_global_scale,
    write_delta_checkpoint,
)


def write_npy(base: Path, name: str, arr: np.ndarray) -> dict:
    path = base / name
    np.save(path, arr)
    return {"path": name, "sha256": sha256_file(path), "shape": list(arr.shape), "dtype": str(arr.dtype)}


def make_trace_fixture(base: Path, *, layer: int = 3, expert: int = 0, epoch: int = 11, n: int = 8, d: int = 128) -> Path:
    rng = np.random.default_rng(123)
    files = {
        "input_vectors": write_npy(base, "x.npy", rng.normal(size=(n, d)).astype(np.float32)),
        "route_gate": write_npy(base, "gate.npy", np.linspace(0.2, 1.0, n, dtype=np.float32)),
        "top_k": write_npy(base, "topk.npy", np.full((n, 2), [expert, expert + 1], dtype=np.int32)),
        "token": write_npy(base, "token.npy", np.arange(n, dtype=np.int64)),
        "call": write_npy(base, "call.npy", np.arange(n, dtype=np.int64) + 100),
        "request_epoch": write_npy(base, "epoch.npy", np.full(n, epoch, dtype=np.int64)),
    }
    manifest = {
        "schema": "ds4_activation_trace_manifest_v1",
        "layer": layer,
        "expert": expert,
        "request_epoch": epoch,
        "expected_request_epoch": epoch,
        "dimensions": {"input": d, "top_k": 2},
        "budget": {"max_file_bytes": 1_000_000},
        "files": files,
    }
    path = base / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


class ActivationAwareTrainerTests(unittest.TestCase):
    def test_reader_happy_path_and_batches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = make_trace_fixture(Path(td))
            reader = ManifestTraceReader(manifest, expected_layer=3, expected_expert=0)
            batches = list(reader.batches(3))
            self.assertEqual(len(batches), 3)
            self.assertEqual(batches[0].x.shape, (3, 128))

    def test_negative_sha_shape_epoch_expert_budget_and_partial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            manifest = make_trace_fixture(base)
            m = json.loads(manifest.read_text(encoding="utf-8"))

            bad = dict(m)
            bad["files"] = json.loads(json.dumps(m["files"]))
            bad["files"]["input_vectors"]["sha256"] = "0" * 64
            p = base / "bad_sha.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "sha mismatch"):
                ManifestTraceReader(p, expected_layer=3, expected_expert=0)

            bad = dict(m)
            bad["files"] = json.loads(json.dumps(m["files"]))
            bad["files"]["input_vectors"]["shape"] = [7, 128]
            p = base / "bad_shape.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "shape mismatch"):
                ManifestTraceReader(p, expected_layer=3, expected_expert=0)

            with self.assertRaisesRegex(RuntimeError, "expert mismatch"):
                ManifestTraceReader(manifest, expected_layer=3, expected_expert=9)

            bad = dict(m)
            bad["expected_request_epoch"] = 12
            p = base / "bad_epoch.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "request_epoch mismatch"):
                ManifestTraceReader(p, expected_layer=3, expected_expert=0)

            bad = dict(m)
            bad["budget"] = {"max_file_bytes": 8}
            p = base / "bad_budget.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "budget exceeded"):
                ManifestTraceReader(p, expected_layer=3, expected_expert=0)

            partial = base / "partial.npy"
            partial.write_bytes((base / "x.npy").read_bytes()[:20])
            bad = dict(m)
            bad["files"] = json.loads(json.dumps(m["files"]))
            bad["files"]["input_vectors"] = {
                "path": "partial.npy",
                "sha256": sha256_file(partial),
                "shape": [8, 128],
                "dtype": "float32",
            }
            p = base / "bad_partial.json"
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(Exception):
                ManifestTraceReader(p, expected_layer=3, expected_expert=0)

    def test_binary_optimum_known_for_constant_block(self) -> None:
        w = np.full((2, 128), -3.0, dtype=np.float32)
        q, scales = binary_g128(w)
        self.assertTrue(np.allclose(scales, 3.0))
        self.assertTrue(np.allclose(q, w))

    def test_streaming_metrics_and_coordinate_update_on_small_subset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = make_trace_fixture(Path(td), n=6, d=128)
            reader = ManifestTraceReader(manifest, expected_layer=3, expected_expert=0)
            rng = np.random.default_rng(77)
            teacher = ExpertWeights(
                rng.normal(scale=0.02, size=(16, 128)).astype(np.float32),
                rng.normal(scale=0.02, size=(16, 128)).astype(np.float32),
                rng.normal(scale=0.02, size=(8, 128)).astype(np.float32),
            )
            # Keep hidden size consistent with down input.
            teacher.down = rng.normal(scale=0.02, size=(8, 16)).astype(np.float32)
            with self.assertRaisesRegex(RuntimeError, "multiple of 128"):
                quantize_expert_binary(teacher)
            teacher.down = rng.normal(scale=0.02, size=(8, 128)).astype(np.float32)
            teacher.gate = rng.normal(scale=0.02, size=(128, 128)).astype(np.float32)
            teacher.up = rng.normal(scale=0.02, size=(128, 128)).astype(np.float32)
            candidate, _ = quantize_expert_binary(teacher)
            batches = list(reader.batches(2))
            before = evaluate_stream(teacher, candidate, batches)
            tuned, info = tune_global_scale(teacher, candidate, batches, tensor_name="down")
            after = evaluate_stream(teacher, tuned, batches)
            self.assertLessEqual(after.weighted_nmse, before.weighted_nmse + 1e-12)
            self.assertEqual(info["tensor"], "down")

    def test_ternary_and_delta_checkpoint_are_small_deltas(self) -> None:
        rng = np.random.default_rng(9)
        teacher = ExpertWeights(
            rng.normal(size=(4, 128)).astype(np.float32),
            rng.normal(size=(4, 128)).astype(np.float32),
            rng.normal(size=(4, 128)).astype(np.float32),
        )
        _, state = quantize_expert_ternary(teacher, 48)
        with tempfile.TemporaryDirectory() as td:
            ckpt = Path(td) / "delta.json"
            write_delta_checkpoint(ckpt, kind="ternary", metadata={"layer": 3, "expert": 0}, deltas={"gate_scale": state["gate_scale"]})
            payload = json.loads(ckpt.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "ds4_activation_aware_delta_checkpoint_v1")
            self.assertIn("gate_scale", payload["deltas"])
            self.assertNotIn("gate", payload["deltas"])

    def test_bounded_sign_flip_probe_is_deterministic_and_non_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = make_trace_fixture(Path(td), n=4, d=128)
            reader = ManifestTraceReader(manifest, expected_layer=3, expected_expert=0)
            batches = list(reader.batches(2))
            rng = np.random.default_rng(42)
            teacher = ExpertWeights(
                rng.normal(scale=0.01, size=(128, 128)).astype(np.float32),
                rng.normal(scale=0.01, size=(128, 128)).astype(np.float32),
                rng.normal(scale=0.01, size=(128, 128)).astype(np.float32),
            )
            candidate, _ = quantize_expert_binary(teacher)
            before = evaluate_stream(teacher, candidate, batches)
            tuned, info = greedy_sign_flip_probe(teacher, candidate, batches, tensor_name="gate", max_flips=1, max_candidates=4)
            after = evaluate_stream(teacher, tuned, batches)
            self.assertLessEqual(after.weighted_nmse, before.weighted_nmse + 1e-12)
            self.assertLessEqual(len(info["applied"]), 1)


if __name__ == "__main__":
    unittest.main()
