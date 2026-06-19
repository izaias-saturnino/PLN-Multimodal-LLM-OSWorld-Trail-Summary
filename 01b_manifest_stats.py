#!/usr/bin/env python3

"""
01b_manifest_stats.py

Basic statistics for manifest.jsonl.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def percentile(values, p):
    if not values:
        return None

    values = sorted(values)

    k = (len(values) - 1) * (p / 100)

    f = int(k)
    c = min(f + 1, len(values) - 1)

    if f == c:
        return values[f]

    d = k - f

    return values[f] * (1 - d) + values[c] * d


def print_distribution(name, values):
    if not values:
        print(f"\n{name}: no data")
        return

    print(f"\n{name}")
    print("-" * len(name))

    print(f"count : {len(values)}")
    print(f"min   : {min(values):.2f}")
    print(f"p25   : {percentile(values, 25):.2f}")
    print(f"p50   : {percentile(values, 50):.2f}")
    print(f"p75   : {percentile(values, 75):.2f}")
    print(f"p90   : {percentile(values, 90):.2f}")
    print(f"p95   : {percentile(values, 95):.2f}")
    print(f"max   : {max(values):.2f}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to manifest.jsonl",
    )

    args = parser.parse_args()

    manifest_path = Path(args.manifest)

    total = 0

    model_counter = Counter()

    success_counter = Counter()

    continuous_scores = []

    steps = []
    durations = []

    with open(
        manifest_path,
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            record = json.loads(line)

            total += 1

            model_counter[
                record["source_model"]
            ] += 1

            success_counter[
                str(record.get("success_binary"))
            ] += 1

            raw = record.get("success_raw")

            if (
                isinstance(raw, (int, float))
                and raw not in (0.0, 1.0)
            ):
                continuous_scores.append(raw)

            if record.get("num_steps") is not None:
                steps.append(
                    record["num_steps"]
                )

            if (
                record.get("duration_seconds")
                is not None
            ):
                durations.append(
                    record["duration_seconds"]
                )

    print()
    print("=" * 60)
    print("MANIFEST STATISTICS")
    print("=" * 60)

    print(f"\nTotal trajectories: {total}")

    print("\nModels")
    print("------")

    for model, count in sorted(
        model_counter.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{model}: {count}"
        )

    print("\nSuccess")
    print("-------")

    for label, count in sorted(
        success_counter.items()
    ):
        pct = (
            count / total * 100
            if total > 0
            else 0
        )

        print(
            f"{label}: {count} ({pct:.2f}%)"
        )

    print_distribution(
        "num_steps",
        steps,
    )

    print_distribution(
        "duration_seconds",
        durations,
    )

    print_distribution(
        "continuous_success_scores",
        continuous_scores,
    )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()