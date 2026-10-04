#!/usr/bin/env python3
"""CPU-only analyzer for matched neuron-routing trace and replay binaries.

This summarizes observed routing, replay arithmetic, error distributions and
hypothetical masks. It does not run a model, predict future routes, or claim
end-to-end quality, latency, or a realizable model-wide cache budget.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
import struct
from pathlib import Path
from typing import BinaryIO

import numpy as np

TRACE_MAGIC = b"SNTv0001"
REPLAY_MAGIC = b"SNRv0001"
HIDDEN = 2560
FF = 640
TOP_K = 10
N_LAYERS = 4
LAYERS = (0, 1, 35, 36)
TIERS = {0: "CPU", 1: "VRAM", 2: "PCIe"}
GU_ROW_BYTES = {16: 660, 17: 740, 18: 980, 21: 1100, 22: 820}
DOWN_GEOMETRY = {42: (64, 18, "Q2_0"), 20: (32, 18, "IQ4_NL")}
OUTPUTS = ("grouped_gpu_full", "mmvq_full", "oracle_160", "oracle_320", "oracle_480",
           "last_160", "last_320", "last_480")
TRACE_FIXED = struct.Struct("<IIqQ")
REPLAY_FIXED = struct.Struct("<Qq6if")
# `h` is the intermediate activation over FF neurons; replay output vectors
# are hidden-size residuals.
REPLAY_ENTRY_BYTES = REPLAY_FIXED.size + 4 * FF + 4 * len(OUTPUTS) * HIDDEN


class FormatError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise FormatError(message)


def read_exact(stream: BinaryIO, n: int, what: str) -> bytes:
    raw = stream.read(n)
    if len(raw) != n:
        raise FormatError(f"truncated {what}: wanted {n} bytes, got {len(raw)}")
    return raw


def read_array(stream: BinaryIO, dtype: str, count: int, what: str) -> np.ndarray:
    dt = np.dtype(dtype)
    raw = read_exact(stream, dt.itemsize * count, what)
    return np.frombuffer(raw, dtype=dt, count=count)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_header(stream: BinaryIO, expected_magic: bytes, label: str) -> tuple[int, int, int, int, tuple[int, ...]]:
    magic = read_exact(stream, 8, f"{label} magic")
    require(magic == expected_magic, f"{label} magic mismatch: {magic!r}")
    dims = struct.unpack("<4I", read_exact(stream, 16, f"{label} dimensions"))
    layers = struct.unpack("<4i", read_exact(stream, 16, f"{label} layer IDs"))
    require(dims == (HIDDEN, FF, TOP_K, N_LAYERS), f"{label} dimensions unsupported: {dims}")
    require(layers == LAYERS, f"{label} layer order mismatch: {layers}")
    return (*dims, layers)


def _add_actual_group(group_actual: dict, key: tuple[int, int, int], tier: int,
                      weight: np.float32, part: np.ndarray) -> None:
    state = group_actual.get(key)
    if state is None:
        state = {"all": np.zeros(HIDDEN, dtype=np.float64),
                 "by_tier": np.zeros((3, HIDDEN), dtype=np.float64), "counts": np.zeros(3, dtype=np.int64)}
        group_actual[key] = state
    weighted = float(weight) * part.astype(np.float64, copy=False)
    state["all"] += weighted
    state["by_tier"][tier] += weighted
    state["counts"][tier] += 1


def parse_trace(stream: BinaryIO) -> tuple[dict, dict, dict]:
    header = read_header(stream, TRACE_MAGIC, "trace")
    rows: dict[tuple[int, int, int, int], dict] = {}
    groups: dict[tuple[int, int, int], set[int]] = defaultdict(set)
    group_actual: dict = {}
    routed_positions: set[tuple[int, int]] = set()
    tier_counts: Counter = Counter()
    record_count = 0
    last_accepted_pos: dict[int, int] = {}

    while True:
        raw_head = stream.read(TRACE_FIXED.size)
        if not raw_head:
            break
        if len(raw_head) != TRACE_FIXED.size:
            raise FormatError(f"truncated trace record header at record {record_count}")
        T, nkeep, pos0, serial = TRACE_FIXED.unpack(raw_head)
        record_count += 1
        require(record_count <= 64, "trace contains more than 64 records")
        require(1 <= T <= 8, f"invalid trace T={T}; expected 1..8")
        require(1 <= nkeep <= T, f"invalid trace nkeep={nkeep} for T={T} at record {record_count}")
        require(pos0 >= 0, f"negative trace pos0={pos0} at record {record_count}")
        require(serial > 0, f"invalid trace serial={serial} at record {record_count}")
        toks = read_array(stream, "<i4", T, f"trace record {record_count} tokens")
        require(np.all(toks >= 0), f"negative token ID in trace record {record_count}")

        for layer_index, layer in enumerate(LAYERS):
            x = read_array(stream, "<f4", T * HIDDEN, f"trace layer {layer} x").reshape(T, HIDDEN)
            ids = read_array(stream, "<i4", T * TOP_K, f"trace layer {layer} expert IDs").reshape(T, TOP_K)
            weights = read_array(stream, "<f4", T * TOP_K, f"trace layer {layer} route weights").reshape(T, TOP_K)
            parts = read_array(stream, "<f4", T * TOP_K * HIDDEN,
                               f"trace layer {layer} expert parts").reshape(T, TOP_K, HIDDEN)
            tiers = read_array(stream, "<i4", T * TOP_K, f"trace layer {layer} tiers").reshape(T, TOP_K)
            require(np.isfinite(x).all(), f"nonfinite x in trace layer {layer}")
            require(np.isfinite(weights).all(), f"nonfinite route weight in trace layer {layer}")
            require(np.isfinite(parts).all(), f"nonfinite original part in trace layer {layer}")
            require(np.all((ids >= 0) & (ids < 512)), f"expert ID outside [0,511] in trace layer {layer}")
            require(np.all((tiers >= 0) & (tiers <= 2)), f"invalid tier in trace layer {layer}")
            for t in range(nkeep):
                route_ids = ids[t]
                require(np.unique(route_ids).size == TOP_K,
                        f"duplicate expert IDs at serial={serial}, pos={pos0+t}, layer={layer}")
                pos = int(pos0 + t)
                previous_pos = last_accepted_pos.get(layer)
                require(previous_pos is None or pos > previous_pos,
                        f"non-monotonic accepted position for layer={layer}: {pos} after {previous_pos}")
                last_accepted_pos[layer] = pos
                pos_key = (layer, pos)
                require(pos_key not in routed_positions,
                        f"duplicate trace (layer,pos) row: {pos_key}")
                routed_positions.add(pos_key)
                group_key = (int(serial), pos, layer)
                for k in range(TOP_K):
                    expert = int(route_ids[k])
                    tier = int(tiers[t, k])
                    weight = np.float32(weights[t, k])
                    key = (*group_key, expert)
                    require(key not in rows, f"duplicate trace route key {key}")
                    rows[key] = {"key": key, "group": group_key, "tier": tier,
                                 "weight": weight, "weight_bytes": weight.tobytes(),
                                 "part": parts[t, k].copy()}
                    groups[group_key].add(expert)
                    tier_counts[tier] += 1
                    _add_actual_group(group_actual, group_key, tier, weight, parts[t, k])

    require(record_count > 0, "trace contains no records")
    require(rows, "trace contains no accepted routed entries (nkeep is zero)")
    for group, experts in groups.items():
        require(len(experts) == TOP_K, f"trace routed group has {len(experts)} experts, expected {TOP_K}: {group}")
    return rows, group_actual, {"header": header, "records": record_count,
        "accepted_routed_positions": len(routed_positions), "accepted_entries": len(rows),
        "tier_counts": {TIERS[k]: int(tier_counts[k]) for k in sorted(TIERS)}}


def rel_l2(a: np.ndarray, b: np.ndarray) -> float | None:
    aa = a.astype(np.float64, copy=False)
    bb = b.astype(np.float64, copy=False)
    den = float(np.linalg.norm(bb.ravel()))
    num = float(np.linalg.norm((aa - bb).ravel()))
    if den == 0.0:
        return 0.0 if num == 0.0 else None
    return num / den


def distribution(values: list[float | None]) -> dict:
    defined = [value for value in values if value is not None]
    undefined = len(values) - len(defined)
    if not defined:
        return {"count": 0, "undefined_zero_reference_count": undefined,
                "mean": None, "median": None, "p95": None, "p99": None, "max": None}
    a = np.asarray(defined, dtype=np.float64)
    require(np.isfinite(a).all(), "nonfinite metric produced during analysis")
    return {"count": int(a.size), "undefined_zero_reference_count": undefined,
            "mean": float(np.mean(a)), "median": float(np.median(a)),
            "p95": float(np.percentile(a, 95)), "p99": float(np.percentile(a, 99)), "max": float(np.max(a))}


def geometry(gu_type: int, down_type: int) -> dict:
    require(gu_type in GU_ROW_BYTES, f"unvalidated gate/up GGML type {gu_type}")
    require(down_type in DOWN_GEOMETRY, f"unvalidated down GGML type {down_type}")
    block_width, block_bytes, down_name = DOWN_GEOMETRY[down_type]
    return {"gu_type": int(gu_type), "gu_row_bytes": GU_ROW_BYTES[gu_type],
            "down_type": int(down_type), "down_format": down_name,
            "down_block_width": block_width, "down_block_bytes": block_bytes,
            "down_block_count": FF // block_width,
            "full_expert_weight_bytes": 2 * GU_ROW_BYTES[gu_type] * FF +
                                        (FF // block_width) * block_bytes * HIDDEN}


def selected(h: np.ndarray, k: int) -> np.ndarray:
    require(k in (160, 320, 480), f"unsupported mask width {k}")
    # Stable descending absolute value makes ties deterministic by original index.
    return np.argsort(-np.abs(h), kind="stable")[:k]


def mask_footprint(indices: np.ndarray, geo: dict) -> dict:
    blocks = np.unique(indices // geo["down_block_width"])
    gu_bytes = 2 * geo["gu_row_bytes"] * int(indices.size)
    down_bytes = int(blocks.size) * geo["down_block_bytes"] * HIDDEN
    total = gu_bytes + down_bytes
    return {"selected_neurons": int(indices.size), "down_blocks_touched": int(blocks.size),
            "gate_up_bytes": int(gu_bytes), "down_bytes": int(down_bytes),
            "weight_bytes": int(total), "fraction_of_full_expert": total / geo["full_expert_weight_bytes"]}


def accepted_position_window_metrics(by_layer_pos: dict, window_width: int = 64) -> dict[str, dict[str, list[float]]]:
    """Oracle union footprint across contiguous accepted positions, by layer."""
    rows_out: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    positions_by_layer: dict[int, list[int]] = defaultdict(list)
    for layer, pos in by_layer_pos:
        positions_by_layer[layer].append(pos)
    for layer, positions in positions_by_layer.items():
        positions = sorted(set(positions))
        for start in range(max(0, len(positions) - window_width + 1)):
            window = positions[start:start + window_width]
            if len(window) != window_width or any(b != a + 1 for a, b in zip(window, window[1:])):
                continue
            expert_rows: dict[int, list[dict]] = defaultdict(list)
            for pos in window:
                for row in by_layer_pos[(layer, pos)]:
                    expert_rows[row["key"][3]].append(row)
            for k in (160, 320, 480):
                compact_total = 0
                full_total = 0
                for calls in expert_rows.values():
                    geo = calls[0]["geometry"]
                    union: set[int] = set()
                    for row in calls:
                        union.update(int(x) for x in selected(row["h"], k))
                    idx_arr = np.fromiter(sorted(union), dtype=np.int64, count=len(union))
                    compact_total += mask_footprint(idx_arr, geo)["weight_bytes"]
                    full_total += geo["full_expert_weight_bytes"]
                key = f"oracle_union_{window_width}_accepted_positions_top{k}"
                rows_out[key]["unique_experts"].append(float(len(expert_rows)))
                rows_out[key]["compact_weight_bytes"].append(float(compact_total))
                rows_out[key]["full_weight_bytes"].append(float(full_total))
                rows_out[key]["compact_fraction_of_full"].append(
                    compact_total / full_total if full_total else 0.0)
    return rows_out


def parse_replay(stream: BinaryIO, trace_rows: dict, group_actual: dict) -> tuple[dict, dict]:
    header = read_header(stream, REPLAY_MAGIC, "replay")
    require(header == (HIDDEN, FF, TOP_K, N_LAYERS, LAYERS), "replay header disagrees with trace dimensions")
    seen: set[tuple[int, int, int, int]] = set()
    replay_rows: dict[tuple[int, int, int, int], dict] = {}
    per_route: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    tier_counts: Counter = Counter()
    # Eight weighted sums per routed layer-position, plus actual trace sums by tier.
    group_acc: dict = {}
    layer_types: dict[int, tuple[int, int]] = {}

    while True:
        raw = stream.read(REPLAY_ENTRY_BYTES)
        if not raw:
            break
        if len(raw) != REPLAY_ENTRY_BYTES:
            raise FormatError(f"truncated replay entry {len(seen)}: {len(raw)} of {REPLAY_ENTRY_BYTES} bytes")
        serial, pos, layer, expert, tier, gu_type, down_type, cold, weight = REPLAY_FIXED.unpack_from(raw, 0)
        key = (int(serial), int(pos), int(layer), int(expert))
        require(key in trace_rows, f"replay has no matching accepted trace row: {key}")
        require(key not in seen, f"duplicate replay entry: {key}")
        require(layer in LAYERS, f"replay layer is not in header: {layer}")
        require(0 <= expert < 512 and 0 <= tier <= 2, f"invalid replay expert/tier in {key}")
        require(cold in (0, 1), f"invalid cold flag in {key}: {cold}")
        require(math.isfinite(weight), f"nonfinite replay route weight in {key}")
        trace_row = trace_rows[key]
        require(int(tier) == trace_row["tier"], f"tier mismatch for {key}: {tier} != {trace_row['tier']}")
        require(struct.pack("<f", weight) == trace_row["weight_bytes"], f"route weight mismatch for {key}")
        gkey = (int(serial), int(pos), int(layer))
        geo = geometry(gu_type, down_type)
        if layer in layer_types:
            require(layer_types[layer] == (gu_type, down_type), f"GGML types vary within layer {layer}")
        else:
            layer_types[layer] = (gu_type, down_type)

        offset = REPLAY_FIXED.size
        h = np.frombuffer(raw, dtype="<f4", count=FF, offset=offset).copy()
        offset += 4 * FF
        vals = np.frombuffer(raw, dtype="<f4", count=len(OUTPUTS) * HIDDEN, offset=offset).reshape(len(OUTPUTS), HIDDEN)
        require(np.isfinite(h).all(), f"nonfinite replay h in {key}")
        require(np.isfinite(vals).all(), f"nonfinite replay output in {key}")
        seen.add(key)
        tier_counts[tier] += 1
        replay_rows[key] = {"key": key, "group": gkey, "tier": int(tier), "weight": np.float32(weight),
                           "cold": bool(cold), "h": h, "geometry": geo}

        original = trace_row["part"]
        grouped, mmvq = vals[0], vals[1]
        per_route["grouped_gpu_full_vs_original"][TIERS[tier]].append(rel_l2(grouped, original))
        per_route["mmvq_full_vs_original"][TIERS[tier]].append(rel_l2(mmvq, original))
        per_route["mmvq_full_vs_grouped_gpu_floor"]["all"].append(rel_l2(mmvq, grouped))
        for j, k in enumerate((160, 320, 480), start=2):
            per_route[f"oracle_{k}_vs_mmvq_full"]["all"].append(rel_l2(vals[j], mmvq))
            per_route[f"last_{k}_vs_mmvq_full"]["all"].append(rel_l2(vals[j + 3], mmvq))
            per_route[f"oracle_{k}_vs_original"][TIERS[tier]].append(rel_l2(vals[j], original))
            per_route[f"last_{k}_vs_original"][TIERS[tier]].append(rel_l2(vals[j + 3], original))

        acc = group_acc.get(gkey)
        if acc is None:
            acc = {"all": np.zeros((len(OUTPUTS), HIDDEN), dtype=np.float64),
                   "by_tier": np.zeros((len(OUTPUTS), 3, HIDDEN), dtype=np.float64),
                   "counts": np.zeros(3, dtype=np.int64)}
            group_acc[gkey] = acc
        w64 = float(weight)
        for i in range(len(OUTPUTS)):
            weighted = w64 * vals[i].astype(np.float64, copy=False)
            acc["all"][i] += weighted
            acc["by_tier"][i, tier] += weighted
        acc["counts"][tier] += 1

    require(seen, "replay contains no entries")
    missing = set(trace_rows) - seen
    if missing:
        raise FormatError(f"replay is missing {len(missing)} matched entries; first missing key: {next(iter(missing))}")
    require(len(seen) == len(trace_rows), "replay and trace entry counts differ")

    weighted: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for gkey, acc in group_acc.items():
        actual = group_actual[gkey]
        for i, name in enumerate(OUTPUTS):
            weighted[f"{name}_vs_actual_trace"]["all"].append(rel_l2(acc["all"][i], actual["all"]))
            for tier in range(3):
                if actual["counts"][tier]:
                    weighted[f"{name}_vs_actual_trace"][TIERS[tier]].append(
                        rel_l2(acc["by_tier"][i, tier], actual["by_tier"][tier]))
        weighted["mmvq_full_vs_grouped_gpu_floor"]["all"].append(
            rel_l2(acc["all"][1], acc["all"][0]))
        for j, k in enumerate((160, 320, 480), start=2):
            weighted[f"oracle_{k}_vs_mmvq_full"]["all"].append(rel_l2(acc["all"][j], acc["all"][1]))
            weighted[f"last_{k}_vs_mmvq_full"]["all"].append(rel_l2(acc["all"][j + 3], acc["all"][1]))

    summaries = {}
    for metric, tiers in per_route.items():
        summaries[metric] = {tier: distribution(vals) for tier, vals in tiers.items()}
    weighted_summaries = {metric: {tier: distribution(vals) for tier, vals in tiers.items()}
                          for metric, tiers in weighted.items()}
    return replay_rows, {"header": header, "entries": len(seen),
        "tier_counts": {TIERS[k]: int(tier_counts[k]) for k in sorted(TIERS)},
        "per_expert_route_error": summaries,
        "router_weighted_routed_layer_sum_error": weighted_summaries,
        "interpretation": "The router-weighted metrics sum the 10 expert outputs for each matched (serial, position, layer), then compare the resulting hidden vectors."}


def mask_analysis(replay_rows: dict) -> dict:
    by_expert: dict[tuple[int, int], list[dict]] = defaultdict(list)
    by_layer_pos: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in replay_rows.values():
        by_expert[(row["key"][2], row["key"][3])].append(row)
        by_layer_pos[(row["key"][2], row["key"][1])].append(row)
    call_window_rows: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    position_window_rows: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    footprint_rows: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    cold_counts: Counter = Counter()
    causal_misses = []
    per_layer_expert = []
    last_recall_all: dict[int, list[float]] = {k: [] for k in (160, 320, 480)}
    last_recall_hot: dict[int, list[float]] = {k: [] for k in (160, 320, 480)}
    current_recall_all: dict[int, list[float]] = {k: [] for k in (160, 320, 480)}

    for (layer, expert), rows in sorted(by_expert.items()):
        rows.sort(key=lambda r: (r["key"][0], r["key"][1]))
        geo = rows[0]["geometry"]
        require(all(r["geometry"] == geo for r in rows), f"geometry changes for layer={layer}, expert={expert}")
        keys = [(r["key"][0], r["key"][1]) for r in rows]
        require(len(keys) == len(set(keys)), f"duplicate temporal row in layer={layer}, expert={expert}")
        prev: dict[int, np.ndarray] = {}
        group_masks = {k: [set() for _ in rows] for k in (160, 320, 480)}
        recalls: dict[int, list[float]] = {k: [] for k in (160, 320, 480)}
        recalls_hot: dict[int, list[float]] = {k: [] for k in (160, 320, 480)}
        cold_n = 0
        tier_n = Counter()
        expert_union_summary = {}
        for idx, row in enumerate(rows):
            serial, pos = row["key"][0], row["key"][1]
            h = row["h"]
            tier_n[row["tier"]] += 1
            cold_counts[(row["tier"], row["cold"])] += 1
            if row["cold"]:
                cold_n += 1
            prior = prev.get(layer)
            require(row["cold"] == (prior is None),
                    f"cold flag disagrees with same-layer/expert history for layer={layer}, expert={expert}, serial={serial}, pos={pos}")
            if not row["cold"] and prior is None:
                causal_misses.append({"layer": layer, "expert": expert, "serial": serial, "position": pos,
                                      "reason": "hot last-mask row has no prior same-expert input"})
            for k in (160, 320, 480):
                cur_mask = selected(h, k)
                group_masks[k][idx] = set(int(x) for x in cur_mask)
                fp = mask_footprint(cur_mask, geo)
                for metric, value in fp.items():
                    if metric == "fraction_of_full_expert":
                        footprint_rows[f"top_{k}"][metric].append(value)
                    elif metric in ("selected_neurons", "down_blocks_touched", "weight_bytes"):
                        footprint_rows[f"top_{k}"][metric].append(float(value))
                norm2 = float(np.dot(h.astype(np.float64), h.astype(np.float64)))
                current_recall_all[k].append(1.0 if norm2 == 0 else
                    float(np.sum(h[cur_mask].astype(np.float64) ** 2) / norm2))
                if row["cold"]:
                    recall = 1.0
                    last_mask = np.arange(FF)
                elif prior is not None:
                    last_mask = selected(prior, k)
                    recall = (1.0 if norm2 == 0 else
                              float(np.sum(h[last_mask].astype(np.float64) ** 2) / norm2))
                else:
                    recall = 1.0
                    last_mask = np.arange(FF)
                recalls[k].append(recall)
                last_recall_all[k].append(recall)
                if not row["cold"]:
                    recalls_hot[k].append(recall)
                    last_recall_hot[k].append(recall)
                fp_last = mask_footprint(last_mask, geo)
                footprint_rows[f"last_{k}"]["selected_neurons"].append(float(fp_last["selected_neurons"]))
                footprint_rows[f"last_{k}"]["down_blocks_touched"].append(float(fp_last["down_blocks_touched"]))
                footprint_rows[f"last_{k}"]["weight_bytes"].append(float(fp_last["weight_bytes"]))
                footprint_rows[f"last_{k}"]["fraction_of_full_expert"].append(fp_last["fraction_of_full_expert"])
            prev[layer] = h

        # Oracle unions span 8/16 invocations of this same expert, not tokens.
        # Each threshold gets a separate aggregate to avoid mixing footprints.
        for width in (8, 16):
            width_summary = {str(k): {"windows": 0, "selected_neurons": [], "weight_bytes": [],
                                      "fraction_of_full_expert": [], "h_energy_recall": []}
                             for k in (160, 320, 480)}
            if len(rows) >= width:
                for start in range(len(rows) - width + 1):
                    for k in (160, 320, 480):
                        union = set().union(*group_masks[k][start:start + width])
                        idx_arr = np.fromiter(sorted(union), dtype=np.int64, count=len(union))
                        fp = mask_footprint(idx_arr, geo)
                        item = width_summary[str(k)]
                        item["windows"] += 1
                        item["selected_neurons"].append(len(union))
                        item["weight_bytes"].append(fp["weight_bytes"])
                        item["fraction_of_full_expert"].append(fp["fraction_of_full_expert"])
                        for r in rows[start:start + width]:
                            den = float(np.dot(r["h"].astype(np.float64), r["h"].astype(np.float64)))
                            item["h_energy_recall"].append(1.0 if den == 0 else
                                float(np.sum(r["h"][idx_arr].astype(np.float64) ** 2) / den))
            expert_union_summary[f"same_expert_calls_{width}"] = {str(k): {
                "windows": int(v["windows"]),
                "selected_neurons": distribution(v["selected_neurons"]),
                "weight_bytes": distribution(v["weight_bytes"]),
                "fraction_of_full_expert": distribution(v["fraction_of_full_expert"]),
                "h_energy_recall": distribution(v["h_energy_recall"])}
                for k, v in width_summary.items()}

        per_layer_expert.append({"layer": layer, "expert": expert,
            "rows": len(rows), "cold_rows": cold_n, "cold_fraction": cold_n / len(rows),
            "tier_rows": {TIERS[k]: int(tier_n[k]) for k in sorted(TIERS)},
            "geometry": geo,
            "lastmask_h_energy_recall": {str(k): {"all_rows": distribution(recalls[k]),
                "hot_only": distribution(recalls_hot[k]),
                "lost_energy_all_rows": distribution([1.0 - x for x in recalls[k]]),
                "lost_energy_hot_only": distribution([1.0 - x for x in recalls_hot[k]])}
                for k in (160, 320, 480)},
            "oracle_future_window_union": expert_union_summary})

        # The union uses observed h vectors over future windows. It is an oracle
        # footprint calculation, not a causal predictor or an online policy.
        for width in (8, 16):
            if len(rows) < width:
                continue
            union_sizes = []
            union_bytes = []
            union_full_fraction = []
            union_recall_by_k = {k: [] for k in (160, 320, 480)}
            for start in range(len(rows) - width + 1):
                for k in (160, 320, 480):
                    union = set().union(*group_masks[k][start:start + width])
                    idx_arr = np.fromiter(sorted(union), dtype=np.int64, count=len(union))
                    fp = mask_footprint(idx_arr, geo)
                    union_sizes.append(float(len(union)))
                    union_bytes.append(float(fp["weight_bytes"]))
                    union_full_fraction.append(float(fp["fraction_of_full_expert"]))
                    for r in rows[start:start + width]:
                        den = float(np.dot(r["h"].astype(np.float64), r["h"].astype(np.float64)))
                        rec = (1.0 if den == 0 else
                               float(np.sum(r["h"][idx_arr].astype(np.float64) ** 2) / den))
                        union_recall_by_k[k].append(rec)
            for k in (160, 320, 480):
                key = f"oracle_union_same_expert_calls_{width}_top{k}"
                threshold_idx = (160, 320, 480).index(k)
                call_window_rows[key]["selected_neurons"].extend(union_sizes[threshold_idx::3])
                call_window_rows[key]["weight_bytes"].extend(union_bytes[threshold_idx::3])
                call_window_rows[key]["fraction_of_full_expert"].extend(union_full_fraction[threshold_idx::3])
                call_window_rows[key]["h_energy_recall"].extend(union_recall_by_k[k])

    # Optimistic position-window cache: rolling windows of 8, 16, and 64
    # contiguous accepted positions, with one compact/full blob per expert.
    position_window_rows = {}
    for width in (8, 16, 64):
        position_window_rows.update(accepted_position_window_metrics(by_layer_pos, width))

    require(not causal_misses, f"invalid last-mask causal history: {causal_misses[:3]}")
    return {"geometry_by_layer_expert": per_layer_expert,
        "actual_top_mask_footprints": {name: {k: distribution(v) for k, v in rows.items()}
                                       for name, rows in footprint_rows.items()},
        "cold_fallback": {"counts_by_tier": {TIERS[t]: {"cold": int(cold_counts[(t, True)]),
            "hot": int(cold_counts[(t, False)])} for t in sorted(TIERS)},
            "rows_total": int(sum(cold_counts.values())),
            "cold_fraction": (sum(v for (t, cold), v in cold_counts.items() if cold) /
                              max(1, sum(cold_counts.values())))},
        "lastmask_h_energy_recall": {str(k): {"all_rows": distribution(last_recall_all[k]),
            "hot_only": distribution(last_recall_hot[k]),
            "lost_energy_all_rows": distribution([1.0 - x for x in last_recall_all[k]]),
            "lost_energy_hot_only": distribution([1.0 - x for x in last_recall_hot[k]])}
            for k in (160, 320, 480)},
        "current_topmask_h_energy_recall": {str(k): distribution(current_recall_all[k])
            for k in (160, 320, 480)},
        "oracle_future_window_union_hypothesis": {
            "same_expert_invocation_windows": {name: {metric: distribution(values) for metric, values in rows.items()}
                for name, rows in call_window_rows.items()},
            "accepted_position_windows": {name: {metric: distribution(values) for metric, values in rows.items()}
                for name, rows in position_window_rows.items()},
        },
        "scope": "Same-expert windows count 8/16 invocations of one expert, not tokens. Accepted-position windows are rolling windows of 8/16/64 contiguous accepted positions within one layer and sum each unique expert once. Both use observed future h vectors as oracle unions, not causal predictions or an online policy. Last masks use the previous observed h for the same layer/expert; cold rows use full-width fallback."}


def analyze_streams(trace_stream: BinaryIO, replay_stream: BinaryIO) -> dict:
    trace_rows, group_actual, trace_meta = parse_trace(trace_stream)
    replay_rows, replay_meta = parse_replay(replay_stream, trace_rows, group_actual)
    masks = mask_analysis(replay_rows)
    return {"schema": "neuron-trace-analysis-v1", "status": "completed",
        "dimensions": {"hidden": HIDDEN, "intermediate": FF, "top_k": TOP_K, "layers": list(LAYERS)},
        "trace": trace_meta, "replay": replay_meta, "masks_and_footprints": masks,
        "scope": "Offline matched-trace and per-expert replay diagnostics only. Pruning-oracle masks use current/future captured activations and are not end-to-end quality or latency evidence."}


def make_selftest_files() -> tuple[bytes, bytes]:
    trace = bytearray(TRACE_MAGIC + struct.pack("<4I", HIDDEN, FF, TOP_K, N_LAYERS) + struct.pack("<4i", *LAYERS))
    trace += TRACE_FIXED.pack(1, 1, 100, 7)
    trace += np.asarray([123], dtype="<i4").tobytes()
    gu_types = (16, 17, 18, 21)
    down_types = (42, 20, 42, 20)
    ids = np.arange(TOP_K, dtype="<i4")
    weights = np.full(TOP_K, 0.1, dtype="<f4")
    parts = np.zeros((TOP_K, HIDDEN), dtype="<f4")
    parts[0, :] = 1.0
    parts[1, :] = -1.0  # weighted layer sum cancels for this pair
    for layer in LAYERS:
        trace += np.zeros((1, HIDDEN), dtype="<f4").tobytes()
        trace += ids.tobytes() + weights.tobytes() + parts.tobytes()
        trace += np.full(TOP_K, layer % 3, dtype="<i4").tobytes()
    replay = bytearray(REPLAY_MAGIC + struct.pack("<4I", HIDDEN, FF, TOP_K, N_LAYERS) + struct.pack("<4i", *LAYERS))
    for layer_i, layer in enumerate(LAYERS):
        for expert in range(TOP_K):
            tier = layer % 3
            gu, down = gu_types[layer_i], down_types[layer_i]
            cold = 1
            weight = float(weights[expert])
            replay += REPLAY_FIXED.pack(7, 100, layer, expert, tier, gu, down, cold, weight)
            h = np.arange(FF, dtype="<f4") * (1.0 if expert % 2 == 0 else -1.0)
            out = parts[expert].copy()
            vals = np.stack([out, out, out, out, out, out, out, out])
            replay += h.tobytes() + vals.astype("<f4").tobytes()
    return bytes(trace), bytes(replay)


def self_test() -> None:
    trace, replay = make_selftest_files()
    report = analyze_streams(io.BytesIO(trace), io.BytesIO(replay))
    require(report["trace"]["accepted_entries"] == 40, "self-test trace route count")
    require(report["replay"]["entries"] == 40, "self-test replay route count")
    floor = report["replay"]["per_expert_route_error"]["mmvq_full_vs_grouped_gpu_floor"]["all"]
    require(floor["max"] == 0.0, "self-test full grouped/MMVQ parity")
    require(report["masks_and_footprints"]["cold_fallback"]["cold_fraction"] == 1.0,
            "self-test cold fallback count")
    require(rel_l2(np.ones(4, dtype=np.float32), np.zeros(4, dtype=np.float32)) is None,
            "self-test zero-reference relative error")
    zero_metric = distribution([0.0, None])
    require(zero_metric["count"] == 1 and zero_metric["undefined_zero_reference_count"] == 1,
            "self-test undefined relative-error accounting")
    window_rows = defaultdict(list)
    test_geo = geometry(16, 42)
    for pos in range(100, 164):
        window_rows[(LAYERS[0], pos)].append({"key": (7, pos, LAYERS[0], 3),
            "geometry": test_geo, "h": np.arange(FF, dtype=np.float32)})
    window_metrics = {width: accepted_position_window_metrics(window_rows, width) for width in (8, 16, 64)}
    require(window_metrics[8]["oracle_union_8_accepted_positions_top160"]["unique_experts"] == [1.0] * 57,
            "self-test rolling 8-position unions")
    require(window_metrics[16]["oracle_union_16_accepted_positions_top160"]["unique_experts"] == [1.0] * 49,
            "self-test rolling 16-position unions")
    require(window_metrics[64]["oracle_union_64_accepted_positions_top160"]["unique_experts"] == [1.0],
            "self-test rolling 64-position union")
    require(window_metrics[64]["oracle_union_64_accepted_positions_top160"]["compact_weight_bytes"][0] <=
            window_metrics[64]["oracle_union_64_accepted_positions_top160"]["full_weight_bytes"][0],
            "self-test compact/full window footprint")
    gap_rows = defaultdict(list, {key: value for key, value in window_rows.items() if key[1] != 130})
    require(not accepted_position_window_metrics(gap_rows, 64),
            "self-test rejects windows with missing accepted positions")

    one_record = trace[32:]
    out_of_order = bytearray(trace[:32] + one_record + one_record)
    second_header_pos_offset = 32 + len(one_record) + 8
    out_of_order[second_header_pos_offset:second_header_pos_offset + 8] = struct.pack("<q", 99)
    bad_trace_cases = [
        ("truncated trace", trace[:-1]),
        ("T=9", bytes(trace[:32] + struct.pack("<I", 9) + trace[36:])),
        ("nkeep=0", bytes(trace[:36] + struct.pack("<I", 0) + trace[40:])),
        ("non-monotonic accepted position", bytes(out_of_order)),
    ]
    for label, bad_trace in bad_trace_cases:
        try:
            analyze_streams(io.BytesIO(bad_trace), io.BytesIO(replay))
        except FormatError:
            pass
        else:
            raise AssertionError(f"self-test failed to reject {label}")
    for label, bad_replay in (("truncated replay", replay[:-1]),):
        try:
            analyze_streams(io.BytesIO(trace), io.BytesIO(bad_replay))
        except FormatError:
            pass
        else:
            raise AssertionError(f"self-test failed to reject {label}")
    cold_mismatch = bytearray(replay)
    first_cold_offset = 40 + 36
    cold_mismatch[first_cold_offset:first_cold_offset + 4] = struct.pack("<i", 0)
    try:
        analyze_streams(io.BytesIO(trace), io.BytesIO(cold_mismatch))
    except FormatError:
        pass
    else:
        raise AssertionError("self-test failed to reject a cold/history mismatch")
    # A wrong exact route weight must fail the keyed join.
    changed = bytearray(replay)
    first_record_float_weight_offset = 40 + REPLAY_FIXED.size - 4
    changed[first_record_float_weight_offset:first_record_float_weight_offset + 4] = struct.pack("<f", 0.2)
    try:
        analyze_streams(io.BytesIO(trace), io.BytesIO(changed))
    except FormatError:
        pass
    else:
        raise AssertionError("self-test failed to reject a route-weight mismatch")
    print(json.dumps({"self_test": "passed", "synthetic_entries": 40,
                      "malformed_cases_rejected": 7, "weighted_cancellation_fixture": "included",
                      "zero_reference_relative_error": "counted_as_undefined",
        "oracle_accepted_position_window_widths": [8, 16, 64]}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", type=Path)
    ap.add_argument("--replay", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true", help="run small CPU-only in-memory parser/metric fixtures")
    args = ap.parse_args()
    if args.self_test:
        require(args.trace is None and args.replay is None and args.out is None,
                "--self-test cannot be combined with trace, replay, or out")
        self_test()
        return
    require(args.trace is not None and args.replay is not None and args.out is not None,
            "--trace, --replay, and --out are required")
    trace_path, replay_path, out_path = args.trace.resolve(), args.replay.resolve(), args.out.resolve()
    require(trace_path.is_file() and replay_path.is_file(), "trace or replay input file does not exist")
    require(not out_path.exists(), "output exists; choose a new name to preserve prior evidence")
    with trace_path.open("rb") as tf, replay_path.open("rb") as rf:
        result = analyze_streams(tf, rf)
    result["inputs"] = {"trace": {"path": str(trace_path), "bytes": trace_path.stat().st_size,
                                    "sha256": file_sha256(trace_path)},
                        "replay": {"path": str(replay_path), "bytes": replay_path.stat().st_size,
                                    "sha256": file_sha256(replay_path)}}
    result["geometry_assumptions"] = {"gate_up_row_bytes_by_ggml_type": GU_ROW_BYTES,
        "down_block_geometry_by_ggml_type": {str(k): {"width": v[0], "bytes": v[1], "name": v[2]}
                                             for k, v in DOWN_GEOMETRY.items()},
        "footprint_formula": "gate/up bytes = 2 * row-bytes[type] * selected rows; down bytes = touched original quantized blocks * block-bytes * hidden-size",
        "router_weighted_parts": "trace parts and replay vectors are treated as unweighted expert outputs; recorded route weight is applied exactly once during routed-layer aggregation"}
    result["limitations"] = [
        "Replay grouped/MMVQ and oracle outputs are local one-layer computations, not end-to-end model responses.",
        "Router-weighted routed-layer sums are an FP64 analyzer-side sum of the 10 routed expert vectors; they do not model shared experts, residual addition, or the complete transformer layer.",
        "Only accepted positions (nkeep) are replayed and analyzed. Draft/rejected candidate positions are not represented, so this does not evaluate an alternate 100-candidate path.",
        "Replay computes and loads the full expert blob; no bandwidth reduction, cache-traffic reduction, or timing benefit is measured by these local arithmetic summaries.",
        "Top-|h| masks optimize captured activation energy, not output error after W_down*h; the ranking is only an energy proxy.",
        "Last-mask rows use the complete previous GPU-replay h for the same layer/expert. That activation required the previous full compute, so it is not a deployable predictor that avoids running the gate/up path.",
        "Last-mask requantization uses Q8_1 and does not always preserve the original max/scales; current-position top-|h| selection preserves the max of each nonempty group.",
        "Oracle 160/320/480 masks and observed-window unions use captured h values; future-window unions are hypothetical and are not predictors.",
        "Footprint counts original gate/up rows and whole touched down quantization blocks; it excludes metadata, alignment, scratch, cache churn, and dispatch overhead.",
        "The analyzer reports numerical residuals, not latency gains, quality preservation, deployment safety, or a model-wide feasible cache budget.",
        "Relative L2 is undefined when the reference vector has zero norm and the candidate is nonzero; those cases are counted separately rather than mixed with absolute errors.",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "trace_entries": result["trace"]["accepted_entries"],
                      "replay_entries": result["replay"]["entries"], "output": str(out_path),
                      "trace_sha256": result["inputs"]["trace"]["sha256"],
                      "replay_sha256": result["inputs"]["replay"]["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
