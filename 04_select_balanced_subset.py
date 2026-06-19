#!/usr/bin/env python3

"""
04_select_balanced_subset.py

Selects a paired balanced subset from screened_manifest.jsonl.

Core requirement:
    The final subset must contain paired trajectories for the same
    OSWorld task across source agents. This is required for ablation
    experiments where the task is fixed and the source-agent trajectory
    varies.

Default behavior:
    - Keep only records with selected_for_gold_generation == True.
    - Group records by trajectory_id.
    - Keep only task groups with the required source models.
    - Select task groups, not individual records.
    - When a task group is selected, include all required source-model
      trajectories for that task.
    - Balance over task-level strata derived from the selected records.

This script does not call any LLM.
"""

from __future__ import annotations

import argparse
import json
import random
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


def value_to_str(value: Any) -> str:
    if value is None:
        return "None"

    return str(value)


def group_by_task(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = defaultdict(list)

    for record in records:
        groups[record["trajectory_id"]].append(record)

    return groups


def source_models_in_group(group: list[dict[str, Any]]) -> set[str]:
    return {
        record["source_model"]
        for record in group
    }


def select_required_records_from_group(
    group: list[dict[str, Any]],
    required_source_models: list[str],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    Returns exactly one selected record per required source model.

    If duplicate records exist for the same source_model and trajectory_id,
    choose one reproducibly.
    """
    by_model = defaultdict(list)

    for record in group:
        by_model[record["source_model"]].append(record)

    selected = []

    for source_model in required_source_models:
        candidates = by_model[source_model]

        if len(candidates) == 1:
            selected.append(candidates[0])
        else:
            selected.append(rng.choice(candidates))

    return selected


def task_group_key(
    paired_records: list[dict[str, Any]],
    balance_columns: list[str],
) -> tuple[str, ...]:
    """
    Builds a task-level stratum key.

    For task-level fields such as domain, all paired records should usually
    agree. For record-level fields such as success_binary, paired records may
    differ by source model. In that case we encode the multiset of values.

    Example:
        source_model is intentionally ignored at task-group level unless
        explicitly passed, because every valid group already contains the
        required source models.

        success_binary across paired records:
            False + True -> "False+True"
            True + True  -> "True+True"
    """
    key_parts = []

    for column in balance_columns:
        values = [
            value_to_str(record.get(column))
            for record in paired_records
        ]

        unique_values = sorted(set(values))

        if len(unique_values) == 1:
            key_parts.append(unique_values[0])
        else:
            key_parts.append("+".join(sorted(values)))

    return tuple(key_parts)


def group_task_groups_by_stratum(
    paired_task_groups: list[list[dict[str, Any]]],
    balance_columns: list[str],
) -> dict[tuple[str, ...], list[list[dict[str, Any]]]]:
    groups = defaultdict(list)

    for paired_records in paired_task_groups:
        key = task_group_key(
            paired_records,
            balance_columns,
        )

        groups[key].append(paired_records)

    return groups


def round_robin_sample_task_groups(
    groups: dict[tuple[str, ...], list[list[dict[str, Any]]]],
    target_num_tasks: int | None,
    max_tasks_per_stratum: int | None,
    rng: random.Random,
) -> list[list[dict[str, Any]]]:
    shuffled_groups = {}

    for key, task_groups in groups.items():
        copied = list(task_groups)
        rng.shuffle(copied)

        if max_tasks_per_stratum is not None:
            copied = copied[:max_tasks_per_stratum]

        shuffled_groups[key] = copied

    selected_task_groups = []

    active_keys = [
        key
        for key, items in shuffled_groups.items()
        if items
    ]

    rng.shuffle(active_keys)

    while active_keys:
        next_active_keys = []

        for key in active_keys:
            items = shuffled_groups[key]

            if not items:
                continue

            selected_task_groups.append(items.pop())

            if target_num_tasks is not None:
                if len(selected_task_groups) >= target_num_tasks:
                    return selected_task_groups

            if items:
                next_active_keys.append(key)

        active_keys = next_active_keys

    return selected_task_groups


def flatten_task_groups(
    task_groups: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    records = []

    for group in task_groups:
        records.extend(group)

    return records


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


def summarize_task_group_strata(
    task_groups: list[list[dict[str, Any]]],
    balance_columns: list[str],
) -> dict[str, int]:
    counter = Counter()

    for group in task_groups:
        key = task_group_key(group, balance_columns)

        key_str = " | ".join(
            f"{column}={value}"
            for column, value in zip(balance_columns, key)
        )

        counter[key_str] += 1

    return dict(sorted(counter.items()))


def summarize_pairing(
    records: list[dict[str, Any]],
    required_source_models: list[str],
) -> dict[str, Any]:
    grouped = group_by_task(records)

    required_set = set(required_source_models)

    complete_pairs = 0
    incomplete_tasks = 0
    source_model_sets = Counter()

    for _, group in grouped.items():
        models = source_models_in_group(group)
        source_model_sets[" + ".join(sorted(models))] += 1

        if required_set.issubset(models):
            complete_pairs += 1
        else:
            incomplete_tasks += 1

    return {
        "required_source_models": required_source_models,
        "num_task_ids": len(grouped),
        "complete_paired_task_ids": complete_pairs,
        "incomplete_task_ids": incomplete_tasks,
        "source_model_set_counts": dict(sorted(source_model_sets.items())),
        "paired_task_requirement": True,
    }


def print_record_summary(
    title: str,
    records: list[dict[str, Any]],
    columns: list[str],
    required_source_models: list[str],
):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Total records: {len(records)}")

    pairing = summarize_pairing(records, required_source_models)

    print()
    print("Pairing")
    print("-------")
    print(f"Task IDs: {pairing['num_task_ids']}")
    print(f"Complete paired task IDs: {pairing['complete_paired_task_ids']}")
    print(f"Incomplete task IDs: {pairing['incomplete_task_ids']}")
    print(f"Required source models: {', '.join(required_source_models)}")

    print()
    print("Source-model sets")
    print("-----------------")

    for model_set, count in pairing["source_model_set_counts"].items():
        print(f"{model_set}: {count}")

    column_counts = summarize_counts(records, columns)

    for column, counts in column_counts.items():
        print()
        print(column)
        print("-" * len(column))

        for value, count in counts.items():
            pct = count / len(records) * 100 if records else 0
            print(f"{value}: {count} ({pct:.2f}%)")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to screened_manifest.jsonl",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to output paired balanced JSONL file",
    )

    parser.add_argument(
        "--stats-output",
        default=None,
        help="Optional path to write selection stats as JSON",
    )

    parser.add_argument(
        "--target-size",
        type=int,
        default=None,
        help=(
            "Target number of records. Since selection is paired, "
            "the effective number of records will be "
            "target_num_tasks * len(required_source_models)."
        ),
    )

    parser.add_argument(
        "--target-num-tasks",
        type=int,
        default=None,
        help=(
            "Target number of paired OSWorld tasks. If provided, this "
            "overrides --target-size."
        ),
    )

    parser.add_argument(
        "--max-tasks-per-stratum",
        type=int,
        default=None,
        help="Maximum number of paired tasks per balance stratum.",
    )

    parser.add_argument(
        "--balance-columns",
        nargs="+",
        default=[
            "domain",
            "success_binary",
        ],
        help=(
            "Columns used to define task-level balance strata. "
            "Default: domain success_binary. Do not include source_model "
            "unless you specifically want it encoded in task groups."
        ),
    )

    parser.add_argument(
        "--required-source-models",
        nargs="+",
        required=True,
        help=(
            "Required source models for each selected task. "
            "Every selected trajectory_id must have one record for each."
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help=(
            "Include records with selected_for_gold_generation == null. "
            "Default is false."
        ),
    )

    args = parser.parse_args()

    rng = random.Random(args.seed)

    input_path = Path(args.input)
    output_path = Path(args.output)

    records = list(load_jsonl(input_path))

    candidates = []

    for record in records:
        selected = record.get("selected_for_gold_generation")

        if selected is True:
            candidates.append(record)

        elif selected is None and args.include_incomplete:
            candidates.append(record)

    candidates_by_task = group_by_task(candidates)

    required_models = args.required_source_models
    required_model_set = set(required_models)

    paired_task_groups = []

    for _, group in candidates_by_task.items():
        models = source_models_in_group(group)

        if not required_model_set.issubset(models):
            continue

        paired_records = select_required_records_from_group(
            group=group,
            required_source_models=required_models,
            rng=rng,
        )

        paired_task_groups.append(paired_records)

    if args.target_num_tasks is not None:
        target_num_tasks = args.target_num_tasks

    elif args.target_size is not None:
        group_size = len(required_models)

        target_num_tasks = args.target_size // group_size

        if target_num_tasks * group_size != args.target_size:
            print(
                "[WARNING] target-size is not divisible by the number "
                "of required source models. The final selected record "
                "count will be rounded down."
            )

    else:
        target_num_tasks = None

    groups = group_task_groups_by_stratum(
        paired_task_groups,
        args.balance_columns,
    )

    selected_task_groups = round_robin_sample_task_groups(
        groups=groups,
        target_num_tasks=target_num_tasks,
        max_tasks_per_stratum=args.max_tasks_per_stratum,
        rng=rng,
    )

    selected_records = flatten_task_groups(
        selected_task_groups,
    )

    write_jsonl(
        output_path,
        selected_records,
    )

    print_record_summary(
        "CANDIDATE RECORDS BEFORE PAIR FILTERING",
        candidates,
        args.balance_columns + ["source_model"],
        required_models,
    )

    print()
    print("=" * 60)
    print("PAIRED TASK GROUPS")
    print("=" * 60)
    print(f"Candidate paired task groups: {len(paired_task_groups)}")
    print(f"Selected paired task groups: {len(selected_task_groups)}")
    print(f"Selected records: {len(selected_records)}")

    print()
    print("Selected task-level strata")
    print("--------------------------")

    selected_strata = summarize_task_group_strata(
        selected_task_groups,
        args.balance_columns,
    )

    for stratum, count in selected_strata.items():
        print(f"{stratum}: {count}")

    print_record_summary(
        "SELECTED PAIRED BALANCED SUBSET",
        selected_records,
        args.balance_columns + ["source_model"],
        required_models,
    )

    stats = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "seed": args.seed,
        "target_size": args.target_size,
        "target_num_tasks": target_num_tasks,
        "max_tasks_per_stratum": args.max_tasks_per_stratum,
        "balance_columns": args.balance_columns,
        "required_source_models": required_models,
        "include_incomplete": args.include_incomplete,
        "paired_task_requirement": True,
        "selection_unit": "trajectory_id_task_group",
        "num_input_records": len(records),
        "num_candidate_records": len(candidates),
        "num_candidate_paired_task_groups": len(paired_task_groups),
        "num_selected_paired_task_groups": len(selected_task_groups),
        "num_selected_records": len(selected_records),
        "candidate_pairing_summary": summarize_pairing(
            candidates,
            required_models,
        ),
        "selected_pairing_summary": summarize_pairing(
            selected_records,
            required_models,
        ),
        "candidate_record_column_counts": summarize_counts(
            candidates,
            args.balance_columns + ["source_model"],
        ),
        "selected_record_column_counts": summarize_counts(
            selected_records,
            args.balance_columns + ["source_model"],
        ),
        "candidate_task_strata_counts": summarize_task_group_strata(
            paired_task_groups,
            args.balance_columns,
        ),
        "selected_task_strata_counts": summarize_task_group_strata(
            selected_task_groups,
            args.balance_columns,
        ),
    }

    if args.stats_output is not None:
        stats_output_path = Path(args.stats_output)

        stats_output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        stats_output_path.write_text(
            json.dumps(
                stats,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print()
        print(f"Stats written to: {stats_output_path}")

    print()
    print("=" * 60)
    print("Paired balanced subset selection completed")
    print("=" * 60)
    print(f"Output file: {output_path}")
    print(f"Selected paired tasks: {len(selected_task_groups)}")
    print(f"Selected records: {len(selected_records)}")
    print("Paired task requirement: enforced")
    print("=" * 60)


if __name__ == "__main__":
    main()