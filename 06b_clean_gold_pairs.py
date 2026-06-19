#!/usr/bin/env python3

"""
06b_clean_gold_pairs.py

Cleans the human-revised gold dataset and keeps only complete paired
tasks.

This is needed when gold summaries were successfully revised for only a
subset of the selected trajectories.

Core requirement:
    A task is valid only if it has a revised gold summary for every
    required source model.

Example:
    trajectory_id X
        Doubao gold summary: OK
        UI-TARS gold summary: OK
    -> keep both records

    trajectory_id Y
        Doubao gold summary: OK
        UI-TARS gold summary: missing/error
    -> drop the task entirely

Input:
    outputs/gold_final.jsonl

Output:
    outputs/gold_final_paired_clean.jsonl
    outputs/gold_final_paired_clean_stats.json
    optional dropped-records JSONL
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                yield json.loads(line)


def write_jsonl(path: Path, records: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def value_to_str(value: Any) -> str:
    if value is None:
        return "None"

    return str(value)


def has_valid_gold(record: dict[str, Any]) -> bool:
    status = record.get("gold_summary_status")
    summary = record.get("gold_summary")

    if status != "OK":
        return False

    if not isinstance(summary, str):
        return False

    if not summary.strip():
        return False

    return True


def group_by_task(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = defaultdict(list)

    for record in records:
        groups[record["trajectory_id"]].append(record)

    return groups


def source_models_in_group(records: list[dict[str, Any]]) -> set[str]:
    return {
        record["source_model"]
        for record in records
    }


def select_one_record_per_required_model(
    records: list[dict[str, Any]],
    required_source_models: list[str],
) -> list[dict[str, Any]]:
    """
    Keeps exactly one record per required source model.

    In your current setup there should normally be exactly one record per
    trajectory_id/source_model. If duplicates exist, this keeps the first
    stable occurrence.
    """
    by_model = defaultdict(list)

    for record in records:
        by_model[record["source_model"]].append(record)

    selected = []

    for source_model in required_source_models:
        selected.append(by_model[source_model][0])

    return selected


def summarize_counts(
    records: list[dict[str, Any]],
    columns: list[str],
) -> dict[str, dict[str, int]]:
    summary = {}

    for column in columns:
        counter = Counter(
            value_to_str(record.get(column))
            for record in records
        )

        summary[column] = dict(sorted(counter.items()))

    return summary


def summarize_pairing(
    records: list[dict[str, Any]],
    required_source_models: list[str],
) -> dict[str, Any]:
    groups = group_by_task(records)
    required_set = set(required_source_models)

    source_model_sets = Counter()
    complete_task_ids = 0
    incomplete_task_ids = 0

    for _, group in groups.items():
        models = source_models_in_group(group)
        model_set_name = " + ".join(sorted(models))
        source_model_sets[model_set_name] += 1

        if required_set.issubset(models):
            complete_task_ids += 1
        else:
            incomplete_task_ids += 1

    return {
        "required_source_models": required_source_models,
        "num_task_ids": len(groups),
        "complete_paired_task_ids": complete_task_ids,
        "incomplete_task_ids": incomplete_task_ids,
        "source_model_set_counts": dict(sorted(source_model_sets.items())),
    }


def summarize_task_success_patterns(
    paired_records: list[dict[str, Any]],
    required_source_models: list[str],
) -> dict[str, int]:
    groups = group_by_task(paired_records)
    counter = Counter()

    for _, records in groups.items():
        by_model = {
            record["source_model"]: record
            for record in records
        }

        parts = []

        for source_model in required_source_models:
            record = by_model[source_model]
            value = value_to_str(record.get("success_binary"))
            parts.append(f"{source_model}={value}")

        counter[" | ".join(parts)] += 1

    return dict(sorted(counter.items()))


def summarize_task_domains(
    paired_records: list[dict[str, Any]],
) -> dict[str, int]:
    groups = group_by_task(paired_records)
    counter = Counter()

    for _, records in groups.items():
        domains = sorted(
            {
                value_to_str(record.get("domain"))
                for record in records
            }
        )

        counter["+".join(domains)] += 1

    return dict(sorted(counter.items()))


def print_summary(
    title: str,
    records: list[dict[str, Any]],
    required_source_models: list[str],
):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Records: {len(records)}")

    pairing = summarize_pairing(
        records,
        required_source_models,
    )

    print(f"Task IDs: {pairing['num_task_ids']}")
    print(f"Complete paired task IDs: {pairing['complete_paired_task_ids']}")
    print(f"Incomplete task IDs: {pairing['incomplete_task_ids']}")

    print()
    print("Source-model sets")
    print("-----------------")

    for model_set, count in pairing["source_model_set_counts"].items():
        print(f"{model_set}: {count}")

    columns = [
        "source_model",
        "domain",
        "success_binary",
        "gold_summary_status",
    ]

    counts = summarize_counts(records, columns)

    for column in columns:
        print()
        print(column)
        print("-" * len(column))

        for value, count in counts[column].items():
            pct = count / len(records) * 100 if records else 0
            print(f"{value}: {count} ({pct:.2f}%)")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to gold_final.jsonl",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to clean paired gold JSONL output",
    )

    parser.add_argument(
        "--stats-output",
        required=True,
        help="Path to stats JSON output",
    )

    parser.add_argument(
        "--dropped-output",
        default=None,
        help="Optional path to JSONL file with dropped records",
    )

    parser.add_argument(
        "--required-source-models",
        nargs="+",
        required=True,
        help=(
            "Required source models. Every kept trajectory_id must have "
            "a valid gold summary for each of these."
        ),
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    stats_output_path = Path(args.stats_output)

    required_source_models = args.required_source_models
    required_set = set(required_source_models)

    records = list(load_jsonl(input_path))

    valid_gold_records = [
        record
        for record in records
        if has_valid_gold(record)
    ]

    invalid_gold_records = [
        {
            **record,
            "drop_reason": "invalid_or_missing_gold_summary",
        }
        for record in records
        if not has_valid_gold(record)
    ]

    valid_groups = group_by_task(valid_gold_records)

    kept_records = []
    dropped_unpaired_records = []

    kept_task_ids = []
    dropped_unpaired_task_ids = []

    for trajectory_id, group in sorted(valid_groups.items()):
        models = source_models_in_group(group)

        if required_set.issubset(models):
            selected_group_records = select_one_record_per_required_model(
                records=group,
                required_source_models=required_source_models,
            )

            kept_records.extend(selected_group_records)
            kept_task_ids.append(trajectory_id)

        else:
            dropped_unpaired_task_ids.append(trajectory_id)

            for record in group:
                dropped_unpaired_records.append(
                    {
                        **record,
                        "drop_reason": "valid_gold_but_missing_required_pair",
                        "available_source_models_for_task": sorted(models),
                        "required_source_models": required_source_models,
                    }
                )

    dropped_records = invalid_gold_records + dropped_unpaired_records

    write_jsonl(
        output_path,
        kept_records,
    )

    if args.dropped_output is not None:
        write_jsonl(
            Path(args.dropped_output),
            dropped_records,
        )

    print_summary(
        "ALL INPUT RECORDS",
        records,
        required_source_models,
    )

    print_summary(
        "VALID GOLD RECORDS BEFORE PAIR FILTERING",
        valid_gold_records,
        required_source_models,
    )

    print_summary(
        "CLEAN PAIRED GOLD RECORDS",
        kept_records,
        required_source_models,
    )

    stats = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "dropped_output_file": args.dropped_output,
        "required_source_models": required_source_models,
        "paired_task_requirement": True,
        "gold_validity_requirement": (
            "gold_summary_status == OK and gold_summary is non-empty"
        ),
        "num_input_records": len(records),
        "num_valid_gold_records_before_pair_filtering": len(valid_gold_records),
        "num_invalid_or_missing_gold_records": len(invalid_gold_records),
        "num_clean_paired_gold_records": len(kept_records),
        "num_clean_paired_tasks": len(kept_task_ids),
        "num_dropped_unpaired_valid_gold_records": len(dropped_unpaired_records),
        "num_dropped_records_total": len(dropped_records),
        "dropped_unpaired_task_ids": dropped_unpaired_task_ids,
        "input_pairing_summary": summarize_pairing(
            records,
            required_source_models,
        ),
        "valid_gold_pairing_summary": summarize_pairing(
            valid_gold_records,
            required_source_models,
        ),
        "clean_paired_pairing_summary": summarize_pairing(
            kept_records,
            required_source_models,
        ),
        "input_column_counts": summarize_counts(
            records,
            [
                "source_model",
                "domain",
                "success_binary",
                "gold_summary_status",
            ],
        ),
        "valid_gold_column_counts": summarize_counts(
            valid_gold_records,
            [
                "source_model",
                "domain",
                "success_binary",
                "gold_summary_status",
            ],
        ),
        "clean_paired_column_counts": summarize_counts(
            kept_records,
            [
                "source_model",
                "domain",
                "success_binary",
                "gold_summary_status",
            ],
        ),
        "clean_paired_task_domain_counts": summarize_task_domains(
            kept_records,
        ),
        "clean_paired_task_success_patterns": summarize_task_success_patterns(
            kept_records,
            required_source_models,
        ),
    }

    write_json(
        stats_output_path,
        stats,
    )

    print()
    print("=" * 60)
    print("Clean paired gold completed")
    print("=" * 60)
    print(f"Input records: {len(records)}")
    print(f"Valid gold records before pair filtering: {len(valid_gold_records)}")
    print(f"Clean paired tasks: {len(kept_task_ids)}")
    print(f"Clean paired records: {len(kept_records)}")
    print(f"Dropped records total: {len(dropped_records)}")
    print(f"Output file: {output_path}")
    print(f"Stats file: {stats_output_path}")

    if args.dropped_output is not None:
        print(f"Dropped records file: {args.dropped_output}")

    print("=" * 60)


if __name__ == "__main__":
    main()