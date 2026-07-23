from __future__ import annotations

import mmap
import struct
from pathlib import Path

import numpy as np

from tools import gptq_to_sidecar as converter


def _metadata() -> list[converter.GgufMetadata]:
    values = {
        "deepseek4.block_count": 4,
        "deepseek4.hash_layer_count": 4,
        "deepseek4.expert_count": 3,
    }
    entries: list[converter.GgufMetadata] = []
    for key in converter.RUNTIME_REQUIRED_METADATA_KEYS:
        if key == "general.name":
            value = "multi-layer-golden"
            entries.append(
                converter.GgufMetadata(
                    key,
                    converter.GGUF_VALUE_TYPE_STRING,
                    value,
                    converter._gguf_string(value),
                )
            )
        else:
            value = values.get(key, 1)
            entries.append(
                converter.GgufMetadata(
                    key,
                    converter.GGUF_VALUE_TYPE_UINT32,
                    value,
                    struct.pack("<I", value),
                )
            )
    return entries


def _q1_fixture_payload(layer: int, part_index: int) -> bytes:
    payload = bytearray()
    for expert in range(3):
        for row in range(2):
            scale = np.asarray(
                0.25 + layer + part_index / 8 + expert / 32 + row / 64,
                dtype="<f2",
            ).tobytes()
            signs = bytes(
                (layer * 41 + part_index * 17 + expert * 5 + row + byte) & 0xFF
                for byte in range(16)
            )
            payload += scale + signs
    return bytes(payload)


def _write_base(path: Path) -> None:
    tensors: list[converter.OutputTensor] = []
    payloads: dict[str, bytes] = {}
    for layer in range(4):
        for stem in ("attn_norm", "ffn_norm", "ffn_gate_inp"):
            name = f"blk.{layer}.{stem}.weight"
            tensors.append(converter.OutputTensor(name, (1,), 0, 4))
            payloads[name] = struct.pack("<f", layer + 0.5)
        for part_index, suffix in enumerate(converter.PART_SUFFIX.values()):
            name = f"blk.{layer}.{suffix}"
            payload = _q1_fixture_payload(layer, part_index)
            tensors.append(
                converter.OutputTensor(
                    name,
                    (128, 2, 3),
                    converter.Q1_TYPE_ID,
                    len(payload),
                )
            )
            payloads[name] = payload

    header = converter._build_header(
        _metadata(),
        tensors,
        converter.DEFAULT_ALIGNMENT,
    )
    output = bytearray(header)
    for tensor in tensors:
        desired = len(header) + tensor.offset
        output += bytes(desired - len(output))
        output += payloads[tensor.name]
    path.write_bytes(output)


def _write_campaign(root: Path, layer: int, experts: tuple[int, ...]) -> None:
    for expert in experts:
        out_dir = root / f"e{expert}" / "out"
        out_dir.mkdir(parents=True)
        for part_index, part in enumerate(converter.PART_SUFFIX):
            signs = np.empty((2, 1, 16), dtype=np.uint8)
            for row in range(2):
                signs[row, 0] = np.asarray(
                    [
                        (
                            layer * 53
                            + expert * 19
                            + part_index * 7
                            + row * 3
                            + byte
                        )
                        & 0xFF
                        for byte in range(16)
                    ],
                    dtype=np.uint8,
                )
            scales = np.asarray(
                [
                    [layer + expert / 8 + part_index / 32 + 0.5],
                    [layer + expert / 8 + part_index / 32 + 0.75],
                ],
                dtype="<f2",
            )
            np.savez(
                out_dir / f"{part}.q1.npz",
                sign_bits=signs,
                scales=scales,
                shape=np.asarray((2, 128), dtype=np.int64),
                block_size=np.asarray(128, dtype=np.int64),
            )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    base_path = tmp_path / "base.gguf"
    root0 = tmp_path / "campaign0"
    root2 = tmp_path / "campaign2"
    _write_base(base_path)
    _write_campaign(root0, 0, (0, 1))
    _write_campaign(root2, 2, (0, 1))
    return base_path, root0, root2


def _tensor_bytes(
    path: Path,
    model: converter.GgufModel,
    name: str,
) -> bytes:
    tensor = model.tensors[name]
    with path.open("rb") as source:
        with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            start = model.data_start + tensor.offset
            return bytes(mapped[start : start + tensor.nbytes])


def test_joint_layer_spec_gap_fills_and_round_trips_two_by_two(
    tmp_path: Path,
    capsys,
) -> None:
    base_path, root0, root2 = _fixture(tmp_path)
    out_path = tmp_path / "joint.gguf"

    assert converter.main(
        (
            "--layer-spec",
            f"0:{root0},2:{root2}",
            "--experts",
            "0,1",
            "--base-model",
            str(base_path),
            "--out",
            str(out_path),
        )
    ) == 0

    base = converter.parse_gguf_header(base_path)
    sidecar = converter.parse_gguf_header(out_path)
    for layer in (0, 1, 2):
        for suffix in converter.PART_SUFFIX.values():
            assert f"blk.{layer}.{suffix}" in sidecar.tensors
    assert "blk.3.ffn_gate_exps.weight" not in sidecar.tensors
    assert "blk.1.ffn_gate_inp.weight" in sidecar.tensors
    assert "blk.3.ffn_gate_inp.weight" not in sidecar.tensors

    # The unrequested layer is a byte-for-byte Q1 base fill in this fixture.
    for suffix in converter.PART_SUFFIX.values():
        name = f"blk.1.{suffix}"
        assert _tensor_bytes(out_path, sidecar, name) == _tensor_bytes(
            base_path,
            base,
            name,
        )

    # Independent 2 experts x 2 layers byte-level NPZ -> GGUF golden.
    for layer, root in ((0, root0), (2, root2)):
        tensor = sidecar.tensors[f"blk.{layer}.ffn_gate_exps.weight"]
        expert_bytes = 2 * converter.Q1_BLOCK_BYTES
        tensor_payload = _tensor_bytes(out_path, sidecar, tensor.name)
        for expert in (0, 1):
            signs, scales = converter._load_gptq_npz(
                root,
                expert,
                "gate",
                2,
                128,
            )
            expected = scales[0, 0].tobytes() + signs[0, 0].tobytes()
            start = expert * expert_bytes
            assert tensor_payload[start : start + converter.Q1_BLOCK_BYTES] == expected

    output = capsys.readouterr().out
    assert "active=0..2" in output
    assert "base-only-gap-layers=1" in output
    assert "4 NPZ round-trip blocks" in output


def test_split_layer_spec_emits_each_contiguous_run(tmp_path: Path, capsys) -> None:
    base_path, root0, root2 = _fixture(tmp_path)
    out_path = tmp_path / "split.gguf"

    assert converter.main(
        (
            "--layer-spec",
            f"0:{root0},2:{root2}",
            "--output-mode",
            "split",
            "--experts",
            "0,1",
            "--base-model",
            str(base_path),
            "--out",
            str(out_path),
        )
    ) == 0

    out0 = tmp_path / "split.L0.gguf"
    out2 = tmp_path / "split.L2.gguf"
    assert out0.is_file()
    assert out2.is_file()
    sidecar0 = converter.parse_gguf_header(out0)
    sidecar2 = converter.parse_gguf_header(out2)
    assert "blk.0.ffn_gate_exps.weight" in sidecar0.tensors
    assert "blk.2.ffn_gate_exps.weight" not in sidecar0.tensors
    assert "blk.2.ffn_gate_exps.weight" in sidecar2.tensors
    assert "blk.0.ffn_gate_exps.weight" not in sidecar2.tensors
    assert "cannot be served jointly" in capsys.readouterr().out


def test_legacy_single_layer_cli_keeps_exact_output_path(tmp_path: Path) -> None:
    base_path, root0, _ = _fixture(tmp_path)
    out_path = tmp_path / "legacy.gguf"

    assert converter.main(
        (
            "--layer",
            "0",
            "--gptq-root",
            str(root0),
            "--experts",
            "0,1",
            "--base-model",
            str(base_path),
            "--out",
            str(out_path),
        )
    ) == 0

    assert out_path.is_file()
    sidecar = converter.parse_gguf_header(out_path)
    assert "blk.0.ffn_gate_exps.weight" in sidecar.tensors
    assert "blk.1.ffn_gate_exps.weight" not in sidecar.tensors
