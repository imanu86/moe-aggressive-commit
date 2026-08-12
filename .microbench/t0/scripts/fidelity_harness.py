#!/usr/bin/env python3
"""Score approximate route IDs against an authoritative route trace."""

import argparse
import json
import sys
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("truth", help="authoritative compact JSON")
    parser.add_argument("predicted", help="approximate-forward compact JSON")
    parser.add_argument("--conversion-threshold", type=float, default=0.75)
    parser.add_argument("--precision-threshold", type=float, default=0.85)
    return parser.parse_args()


def load_trace(path, truth=False):
    with open(path, "r", encoding="utf-8") as source:
        raw = json.load(source)
    trace = {}
    for token_text, raw_layers in raw.items():
        token = int(token_text)
        for layer_text, raw_ids in raw_layers.items():
            layer = int(layer_text)
            ids = tuple(int(expert) for expert in raw_ids)
            if not ids or len(set(ids)) != len(ids):
                raise ValueError(f"{path}: token={token} layer={layer}: bad ID set")
            if truth and len(ids) != 6:
                raise ValueError(
                    f"{path}: token={token} layer={layer}: truth must have 6 IDs"
                )
            if any(expert < 0 or expert >= 256 for expert in ids):
                raise ValueError(f"{path}: token={token} layer={layer}: bad ID")
            trace[(token, layer)] = set(ids)
    if not trace:
        raise ValueError(f"{path}: empty trace")
    return trace


def rate(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def main():
    args = parse_args()
    truth = load_trace(args.truth, truth=True)
    predicted = load_trace(args.predicted)
    coordinates = sorted(set(truth).union(predicted))
    by_layer = defaultdict(lambda: [0, 0, 0, 0])
    matched = true_ids = predicted_ids = 0
    for coordinate in coordinates:
        actual = truth.get(coordinate, set())
        guess = predicted.get(coordinate, set())
        common = len(actual.intersection(guess))
        layer = coordinate[1]
        by_layer[layer][0] += common
        by_layer[layer][1] += len(actual)
        by_layer[layer][2] += len(guess)
        by_layer[layer][3] += 1
        matched += common
        true_ids += len(actual)
        predicted_ids += len(guess)

    missing = sorted(set(truth).difference(predicted))
    extra = sorted(set(predicted).difference(truth))
    conversion = rate(matched, true_ids)
    precision = rate(matched, predicted_ids)

    print(f"{'layer':>7} {'conversion':>12} {'precision':>11} "
          f"{'matched':>9} {'true':>8} {'predicted':>10} {'coords':>8}")
    for layer in sorted(by_layer):
        layer_matched, layer_true, layer_predicted, count = by_layer[layer]
        print(
            f"{layer:7d} {rate(layer_matched, layer_true):12.6f} "
            f"{rate(layer_matched, layer_predicted):11.6f} "
            f"{layer_matched:9d} {layer_true:8d} "
            f"{layer_predicted:10d} {count:8d}"
        )
    print(
        f"{'ALL':>7} {conversion:12.6f} {precision:11.6f} "
        f"{matched:9d} {true_ids:8d} {predicted_ids:10d} "
        f"{len(coordinates):8d}"
    )
    print(
        f"coordinates truth={len(truth)} predicted={len(predicted)} "
        f"missing={len(missing)} extra={len(extra)}"
    )
    passed = (
        conversion >= args.conversion_threshold
        and precision >= args.precision_threshold
        and not missing
        and not extra
    )
    status = "PASS" if passed else "KILL"
    print(
        f"{status}: conversion={conversion:.6f} "
        f"(threshold {args.conversion_threshold:.2f}), "
        f"precision={precision:.6f} "
        f"(threshold {args.precision_threshold:.2f}), "
        f"coordinate_match={'yes' if not missing and not extra else 'no'}"
    )
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"fidelity_harness.py: {error}", file=sys.stderr)
        raise SystemExit(2)
