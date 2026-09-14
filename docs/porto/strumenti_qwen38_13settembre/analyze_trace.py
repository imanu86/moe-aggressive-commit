"""Replay Qwen MoE cache plans from the direct JSONL trace schema.

Each input line is one plan record.  The cache is independent per ``group``
and starts empty for every group.  The replay uses the CUDA step convention:
epoch = (step - 1) >> 6.
"""

import argparse
import collections
import json
import pathlib
import sys


REQUIRED = {
    "group", "layer", "step", "k", "rows", "requested", "misses",
    "bytes_per_miss", "ids",
}


class Cache:
    def __init__(self, slots):
        self.n = slots
        self.slot_for = {}
        self.expert_for = [-1] * slots
        self.last = [0] * slots
        self.freq = collections.defaultdict(int)
        self.epoch_of = collections.defaultdict(int)
        self.clock = 0

    @staticmethod
    def effective(freq, stored, epoch):
        elapsed = epoch - stored
        return freq >> elapsed if elapsed < 32 else 0

    def replay(self, experts, step):
        epoch = (step - 1) >> 6
        used = {self.slot_for[e] for e in experts if e in self.slot_for}
        misses = [e for e in experts if e not in self.slot_for]
        for expert in misses:
            candidates = []
            for slot in range(self.n):
                if slot in used:
                    continue
                resident = self.expert_for[slot]
                freq = (0 if resident < 0 else
                        self.effective(self.freq[resident], self.epoch_of[resident], epoch))
                candidates.append((freq, self.last[slot], slot))
            if not candidates:
                raise ValueError("no evictable slot (requested set exceeds slots)")
            slot = min(candidates)[2]
            old = self.expert_for[slot]
            if old >= 0:
                del self.slot_for[old]
            self.expert_for[slot] = expert
            self.slot_for[expert] = slot
            used.add(slot)
        for expert in experts:
            self.clock += 1
            self.last[self.slot_for[expert]] = self.clock
            self.freq[expert] = self.effective(self.freq[expert], self.epoch_of[expert], epoch) + 1
            self.epoch_of[expert] = epoch
        return len(experts), len(misses)


def fail(message, line=None):
    where = f" at line {line}" if line is not None else ""
    raise ValueError(message + where)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slots", type=int, default=64)
    args = ap.parse_args()
    if args.slots < 1:
        fail("--slots must be positive")

    caches = {}
    previous = {}
    errors = []
    mismatches = []
    mismatch_count = 0
    aggregate = collections.defaultdict(lambda: {"plans": 0, "expected_requested": 0,
                                                   "record_requested": 0, "expected_misses": 0,
                                                   "record_misses": 0, "bytes": 0})
    warm = collections.defaultdict(lambda: {"plans": 0, "expected_requested": 0,
                                              "record_requested": 0, "expected_misses": 0,
                                              "record_misses": 0, "bytes": 0})

    with open(args.trace, encoding="utf-8") as src:
        for line_no, line in enumerate(src, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    fail("record is not an object", line_no)
                missing = REQUIRED - rec.keys()
                if missing:
                    fail("missing fields: " + ",".join(sorted(missing)), line_no)
                group, layer, step = (int(rec[x]) for x in ("group", "layer", "step"))
                k, rows = int(rec["k"]), int(rec["rows"])
                requested, recorded_misses = int(rec["requested"]), int(rec["misses"])
                bytes_per_miss = int(rec["bytes_per_miss"])
                ids = rec["ids"]
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
                continue
            if step < 1:
                errors.append(f"line {line_no}: step must start at 1")
                continue
            key = (group, layer)
            expected_step = previous.get(key, 0) + 1
            if step != expected_step:
                errors.append(f"line {line_no}: {key} step {step}, expected {expected_step}")
            previous[key] = step
            if k < 1 or rows < 1 or len(ids) != k * rows:
                errors.append(f"line {line_no}: ids length {len(ids)} != k*rows {k*rows}")
                continue
            if requested < 0 or recorded_misses < 0 or bytes_per_miss < 0:
                errors.append(f"line {line_no}: negative count/byte field")
                continue
            try:
                ids = [int(x) for x in ids]
            except (TypeError, ValueError):
                errors.append(f"line {line_no}: ids must be integers")
                continue
            if any(x < 0 or x >= 512 for x in ids):
                errors.append(f"line {line_no}: id outside [0,512)")
                continue
            experts = list(dict.fromkeys(ids))
            if len(experts) > args.slots:
                errors.append(f"line {line_no}: unique ids {len(experts)} exceed slots {args.slots}")
                continue
            if requested != len(experts):
                errors.append(f"line {line_no}: requested {requested}, unique ids {len(experts)}")
                continue
            cache = caches.setdefault(key, Cache(args.slots))
            expected_requested, expected_misses = cache.replay(experts, step)
            bucket = aggregate[layer]
            bucket["plans"] += 1
            bucket["expected_requested"] += expected_requested
            bucket["record_requested"] += requested
            bucket["expected_misses"] += expected_misses
            bucket["record_misses"] += recorded_misses
            bucket["bytes"] += recorded_misses * bytes_per_miss
            if step > 64:
                wb = warm[layer]
                wb["plans"] += 1
                wb["expected_requested"] += expected_requested
                wb["record_requested"] += requested
                wb["expected_misses"] += expected_misses
                wb["record_misses"] += recorded_misses
                wb["bytes"] += recorded_misses * bytes_per_miss
            if expected_requested != requested or expected_misses != recorded_misses:
                mismatch_count += 1
                if len(mismatches) < 10:
                    mismatches.append({"line": line_no, "group": group, "layer": layer,
                                       "step": step, "expected_requested": expected_requested,
                                       "record_requested": requested, "expected_misses": expected_misses,
                                       "record_misses": recorded_misses})

    def totals(source):
        out = {"plans": 0, "expected_requested": 0, "record_requested": 0,
               "expected_misses": 0, "record_misses": 0, "bytes": 0}
        for value in source.values():
            for name in out:
                out[name] += value[name]
        return out

    result = {"slots": args.slots, "errors": errors, "mismatch_count": mismatch_count,
              "mismatches_first10": mismatches,
              "all": {"total": totals(aggregate), "per_layer": {str(k): v for k, v in sorted(aggregate.items())}},
              "warmup_excluded_step_gt_64": {"total": totals(warm),
                                               "per_layer": {str(k): v for k, v in sorted(warm.items())}}}
    pathlib.Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"errors": len(errors), "mismatch_count": result["mismatch_count"],
                      "out": args.out}, ensure_ascii=False))
    return 1 if errors or mismatch_count else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
