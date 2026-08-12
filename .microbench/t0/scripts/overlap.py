#!/usr/bin/env python3
"""Compare adjacent-token overlap, LRU140, and perfect sliding windows."""

import argparse
import json
import sys
from collections import OrderedDict, defaultdict


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", help="compact JSON from parse_trace.py")
    parser.add_argument("--capacity", type=int, default=140)
    parser.add_argument(
        "--windows", default="10,20",
        help="comma-separated exact lookahead windows in layers (default: 10,20)",
    )
    return parser.parse_args()


def load_trace(path):
    with open(path, "r", encoding="utf-8") as source:
        raw = json.load(source)
    trace = {}
    for token_text, raw_layers in raw.items():
        token = int(token_text)
        layers = {}
        for layer_text, raw_ids in raw_layers.items():
            layer = int(layer_text)
            ids = tuple(int(expert) for expert in raw_ids)
            if len(ids) != 6 or len(set(ids)) != 6:
                raise ValueError(f"token={token} layer={layer}: expected 6 unique IDs")
            if any(expert < 0 or expert >= 256 for expert in ids):
                raise ValueError(f"token={token} layer={layer}: ID outside [0,255]")
            layers[layer] = ids
        trace[token] = layers
    if not trace:
        raise ValueError("empty trace")
    layer_set = set(next(iter(trace.values())))
    if not layer_set or any(set(layers) != layer_set for layers in trace.values()):
        raise ValueError("all tokens must contain the same layer set")
    return trace, sorted(trace), sorted(layer_set)


def adjacent_overlap(trace, tokens, layers):
    hits = defaultdict(int)
    total = defaultdict(int)
    for left, right in zip(tokens, tokens[1:]):
        for layer in layers:
            truth = set(trace[left][layer])
            hits[layer] += len(truth.intersection(trace[right][layer]))
            total[layer] += len(truth)
    return hits, total


def lru_curve(trace, tokens, layers, capacity):
    cache = OrderedDict()
    hits = defaultdict(int)
    total = defaultdict(int)
    for token in tokens:
        for layer in layers:
            for expert in trace[token][layer]:
                key = (layer, expert)
                total[layer] += 1
                if key in cache:
                    hits[layer] += 1
                    cache.move_to_end(key)
                else:
                    if len(cache) >= capacity:
                        cache.popitem(last=False)
                    cache[key] = None
    return hits, total


def evict_unprotected(cache, protected):
    for key in cache:
        if key not in protected:
            del cache[key]
            return
    raise ValueError("capacity cannot hold the protected oracle window")


def oracle_curve(trace, tokens, layers, capacity, window):
    cache = OrderedDict()
    hits = defaultdict(int)
    total = defaultdict(int)
    for token_index, token in enumerate(tokens):
        for layer_index, layer in enumerate(layers):
            protected = set()
            if token_index:
                last = min(len(layers), layer_index + window + 1)
                for future_layer in layers[layer_index:last]:
                    protected.update(
                        (future_layer, expert)
                        for expert in trace[token][future_layer]
                    )
                if len(protected) > capacity:
                    raise ValueError(
                        f"window {window} needs {len(protected)} slots "
                        f"at token={token} layer={layer}"
                    )
                for key in protected:
                    if key in cache:
                        continue
                    if len(cache) >= capacity:
                        evict_unprotected(cache, protected)
                    cache[key] = None
            for expert in trace[token][layer]:
                key = (layer, expert)
                total[layer] += 1
                if key in cache:
                    hits[layer] += 1
                    cache.move_to_end(key)
                else:
                    if len(cache) >= capacity:
                        evict_unprotected(cache, protected)
                    cache[key] = None
    return hits, total


def ratio(numerator, denominator):
    denominator = sum(denominator.values())
    return sum(numerator.values()) / denominator if denominator else 0.0


def main():
    args = parse_args()
    if args.capacity <= 0:
        raise ValueError("capacity must be positive")
    windows = sorted({int(value) for value in args.windows.split(",")})
    if not windows or any(window < 1 for window in windows):
        raise ValueError("windows must contain positive integers")
    trace, tokens, layers = load_trace(args.trace)
    overlap_hits, overlap_total = adjacent_overlap(trace, tokens, layers)
    lru_hits, lru_total = lru_curve(trace, tokens, layers, args.capacity)
    oracle = {
        window: oracle_curve(trace, tokens, layers, args.capacity, window)
        for window in windows
    }

    print(
        f"tokens={len(tokens)} layers={len(layers)} capacity={args.capacity} "
        "(oracle scores token 0 cold; exact one-token lookahead starts at token 1)"
    )
    print("\nAGGREGATE")
    print(f"{'curve':<24} {'hit_rate':>10} {'lru_miss_conversion':>20}")
    print(f"{'overlap t->t+1':<24} {ratio(overlap_hits, overlap_total):10.6f} {'-':>20}")
    lru_rate = ratio(lru_hits, lru_total)
    print(f"{'LRU':<24} {lru_rate:10.6f} {'-':>20}")
    for window in windows:
        oracle_rate = ratio(*oracle[window])
        conversion = (
            (oracle_rate - lru_rate) / (1.0 - lru_rate)
            if lru_rate < 1.0 else 0.0
        )
        print(f"{('perfect window W' + str(window)):<24} "
              f"{oracle_rate:10.6f} {conversion:20.6f}")

    print("\nPER-LAYER CURVES")
    headings = ["layer", "overlap", f"LRU{args.capacity}"] + [
        f"W{window}" for window in windows
    ]
    print(" ".join(f"{heading:>10}" for heading in headings))
    for layer in layers:
        values = [
            layer,
            overlap_hits[layer] / overlap_total[layer]
            if overlap_total[layer] else 0.0,
            lru_hits[layer] / lru_total[layer] if lru_total[layer] else 0.0,
        ]
        values.extend(
            hits[layer] / totals[layer] if totals[layer] else 0.0
            for hits, totals in (oracle[window] for window in windows)
        )
        print(f"{values[0]:10d} " + " ".join(
            f"{value:10.6f}" for value in values[1:]
        ))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"overlap.py: {error}", file=sys.stderr)
        raise SystemExit(2)
