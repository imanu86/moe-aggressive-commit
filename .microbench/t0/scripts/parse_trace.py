#!/usr/bin/env python3
"""Extract compact route-ID JSON from a ds4 server stderr log."""

import argparse
import json
import re
import sys


ROUTE_RE = re.compile(
    r"\[route-ids\]\s+token=(\d+)\s+layer=(\d+)\s+"
    r"ids=(-?\d+(?:,-?\d+){5})(?:\s|$)"
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="server.stderr.log, or - for stdin")
    parser.add_argument("output", help="compact JSON output, or - for stdout")
    parser.add_argument("--expect-tokens", type=int)
    parser.add_argument("--expect-layers", type=int, default=43)
    return parser.parse_args()


def fail(message):
    raise ValueError(message)


def main():
    args = parse_args()
    source = sys.stdin if args.log == "-" else open(
        args.log, "r", encoding="utf-8", errors="replace"
    )
    trace = {}
    matched = 0
    duplicates = 0
    try:
        for line_no, line in enumerate(source, 1):
            if "[route-ids]" not in line:
                continue
            match = ROUTE_RE.search(line)
            if not match:
                fail(f"{args.log}:{line_no}: malformed [route-ids] line")
            token, layer = int(match.group(1)), int(match.group(2))
            ids = [int(value) for value in match.group(3).split(",")]
            if layer >= args.expect_layers:
                fail(f"{args.log}:{line_no}: layer {layer} outside expected range")
            if any(expert < 0 or expert >= 256 for expert in ids):
                fail(f"{args.log}:{line_no}: expert ID outside [0,255]")
            if len(set(ids)) != 6:
                fail(f"{args.log}:{line_no}: expert IDs are not unique")
            layers = trace.setdefault(token, {})
            if layer in layers:
                if layers[layer] != ids:
                    fail(f"{args.log}:{line_no}: conflicting token/layer duplicate")
                duplicates += 1
            else:
                layers[layer] = ids
            matched += 1
    finally:
        if source is not sys.stdin:
            source.close()

    if not trace:
        fail(f"{args.log}: no [route-ids] lines found")
    expected_layers = set(range(args.expect_layers))
    incomplete = {
        token: sorted(expected_layers.difference(layers))
        for token, layers in trace.items()
        if set(layers) != expected_layers
    }
    if incomplete:
        first = next(iter(sorted(incomplete.items())))
        fail(f"token {first[0]} missing layers {first[1]}")
    if args.expect_tokens is not None and len(trace) != args.expect_tokens:
        fail(f"expected {args.expect_tokens} tokens, found {len(trace)}")

    compact = {
        str(token): {
            str(layer): trace[token][layer] for layer in sorted(trace[token])
        }
        for token in sorted(trace)
    }
    target = sys.stdout if args.output == "-" else open(
        args.output, "w", encoding="utf-8", newline="\n"
    )
    try:
        json.dump(compact, target, separators=(",", ":"))
        target.write("\n")
    finally:
        if target is not sys.stdout:
            target.close()
    print(
        f"route rows={matched} tokens={len(trace)} "
        f"layers={args.expect_layers} exact_duplicates={duplicates}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"parse_trace.py: {error}", file=sys.stderr)
        raise SystemExit(2)
