#!/usr/bin/env python3

"""
10_analyze_judge_results.py

Aggregates LLM judge results into paper-ready analysis tables.

Inputs:
    outputs/judge_results_by_model.jsonl
    outputs/judge_results.jsonl
    outputs/reference_metrics.jsonl

Outputs:
    outputs/judge_analysis_summary.json
    outputs/judge_analysis_by_model.csv
    outputs/judge_analysis_by_domain.csv
    outputs/judge_analysis_by_source_agent.csv
    outputs/judge_analysis_by_success.csv
    outputs/judge_analysis_with_metrics.csv
    outputs/judge_error_examples.jsonl

This script does not call any LLM.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


SCORE_FIELDS = [
    "coverage_score",
    "factuality_score",
    "temporal_order_score",
    "specificity_score",
    "procedural_usefulness_score",
]

SEVERITY_ORDER = {
    "none": 0,
    "minor": 1,
    "major": 2,
    "critical": 3,
}


def load_jsonl(path: Path):
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                yield json.loads(line)


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def value_to_str(value: Any) -> str:
    if value is None:
        return "None"

    return str(value)


def safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def mean(values: list[Any]) -> float | None:
    clean = [
        safe_float(value)
        for value in values
    ]

    clean = [
        value
        for value in clean
        if value is not None
    ]

    if not clean:
        return None

    return float(sum(clean) / len(clean))


def count_severity_at_least(
    rows: list[dict[str, Any]],
    field: str,
    minimum: str,
) -> int:
    minimum_value = SEVERITY_ORDER[minimum]

    count = 0

    for row in rows:
        severity = row.get(field)

        if SEVERITY_ORDER.get(severity, -1) >= minimum_value:
            count += 1

    return count


def flatten_main_errors(row: dict[str, Any]) -> list[dict[str, Any]]:
    errors = row.get("main_errors")

    if not isinstance(errors, list):
        return []

    flattened = []

    for error in errors:
        if isinstance(error, dict):
            flattened.append(error)
        elif isinstance(error, str):
            flattened.append(
                {
                    "error_type": "unknown",
                    "description": error,
                    "why_it_matters": "",
                    "severity": None,
                }
            )

    return flattened


def summarize_error_types(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    counter = Counter()

    for row in rows:
        for error in flatten_main_errors(row):
            counter[value_to_str(error.get("error_type"))] += 1

    return dict(sorted(counter.items()))


def summarize_error_severities_from_main_errors(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    counter = Counter()

    for row in rows:
        for error in flatten_main_errors(row):
            counter[value_to_str(error.get("severity"))] += 1

    return dict(sorted(counter.items()))


def aggregate_group(
    rows: list[dict[str, Any]],
    group_fields: list[str],
) -> list[dict[str, Any]]:
    grouped = defaultdict(list)

    for row in rows:
        key = tuple(
            value_to_str(row.get(field))
            for field in group_fields
        )

        grouped[key].append(row)

    output_rows = []

    for key, items in sorted(grouped.items()):
        output = {
            field: value
            for field, value in zip(group_fields, key)
        }

        output["n"] = len(items)

        for field in SCORE_FIELDS:
            output[f"{field}_mean"] = mean(
                [
                    item.get(field)
                    for item in items
                ]
            )

        output["best_count"] = sum(
            1
            for item in items
            if item.get("is_best") is True
        )

        output["tie_count"] = sum(
            1
            for item in items
            if item.get("is_tie") is True
        )

        output["best_rate"] = (
            output["best_count"] / output["n"]
            if output["n"]
            else None
        )

        output["tie_rate"] = (
            output["tie_count"] / output["n"]
            if output["n"]
            else None
        )

        output["major_or_critical_omission_count"] = (
            count_severity_at_least(
                items,
                "omission_severity",
                "major",
            )
        )

        output["major_or_critical_hallucination_count"] = (
            count_severity_at_least(
                items,
                "hallucination_severity",
                "major",
            )
        )

        output["major_or_critical_omission_rate"] = (
            output["major_or_critical_omission_count"] / output["n"]
            if output["n"]
            else None
        )

        output["major_or_critical_hallucination_rate"] = (
            output["major_or_critical_hallucination_count"] / output["n"]
            if output["n"]
            else None
        )

        output["omission_severity_counts"] = dict(
            sorted(
                Counter(
                    value_to_str(item.get("omission_severity"))
                    for item in items
                ).items()
            )
        )

        output["hallucination_severity_counts"] = dict(
            sorted(
                Counter(
                    value_to_str(item.get("hallucination_severity"))
                    for item in items
                ).items()
            )
        )

        output["main_error_type_counts"] = summarize_error_types(
            items
        )

        output["main_error_severity_counts"] = (
            summarize_error_severities_from_main_errors(items)
        )

        output_rows.append(output)

    return output_rows


def load_reference_metrics_index(
    path: Path | None,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    if path is None:
        return {}

    if not path.exists():
        return {}

    index = {}

    for record in load_jsonl(path):
        key = (
            record["trajectory_id"],
            record["source_model"],
            record["eval_model_name"],
        )

        index[key] = record

    return index


def join_reference_metrics(
    judge_rows: list[dict[str, Any]],
    reference_metrics_index: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    joined = []

    metric_fields = [
        "rouge1_f1",
        "rouge2_f1",
        "rougeL_f1",
        "bertscore_precision",
        "bertscore_recall",
        "bertscore_f1",
        "gold_word_count",
        "model_word_count",
    ]

    for row in judge_rows:
        key = (
            row["trajectory_id"],
            row["source_model"],
            row["eval_model_name"],
        )

        metrics = reference_metrics_index.get(key, {})

        joined_row = dict(row)

        for field in metric_fields:
            joined_row[field] = metrics.get(field)

        joined.append(joined_row)

    return joined


def summarize_pairwise_winners(
    judge_records: list[dict[str, Any]],
) -> dict[str, int]:
    counter = Counter()

    for record in judge_records:
        if record.get("status") != "OK":
            continue

        judge_json = record.get("judge_json", {})

        best = judge_json.get("best_summary")

        if best == "tie":
            counter["tie"] += 1
            continue

        hidden = record.get("hidden_model_mapping", {})

        if best not in hidden:
            counter["unknown"] += 1
            continue

        model_name = hidden[best]["eval_model_name"]
        counter[model_name] += 1

    return dict(sorted(counter.items()))


def summarize_score_gaps_between_two_models(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Computes per-example score gaps when exactly two evaluated models
    are present for each trajectory/source example.
    """
    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["trajectory_id"],
            row["source_model"],
        )

        grouped[key].append(row)

    gap_rows = []

    for key, items in grouped.items():
        model_names = sorted(
            {
                item["eval_model_name"]
                for item in items
            }
        )

        if len(model_names) != 2:
            continue

        by_model = {
            item["eval_model_name"]: item
            for item in items
        }

        model_a, model_b = model_names

        gap = {
            "trajectory_id": key[0],
            "source_model": key[1],
            "model_a": model_a,
            "model_b": model_b,
        }

        for field in SCORE_FIELDS:
            a_value = safe_float(by_model[model_a].get(field))
            b_value = safe_float(by_model[model_b].get(field))

            if a_value is None or b_value is None:
                gap[f"{field}_gap_{model_a}_minus_{model_b}"] = None
            else:
                gap[f"{field}_gap_{model_a}_minus_{model_b}"] = (
                    a_value - b_value
                )

        gap_rows.append(gap)

    if not gap_rows:
        return {
            "n": 0,
            "note": "No exactly-two-model examples found.",
        }

    summary = {
        "n": len(gap_rows),
        "models_compared": [
            gap_rows[0]["model_a"],
            gap_rows[0]["model_b"],
        ],
        "mean_gaps": {},
    }

    model_a = gap_rows[0]["model_a"]
    model_b = gap_rows[0]["model_b"]

    for field in SCORE_FIELDS:
        gap_field = f"{field}_gap_{model_a}_minus_{model_b}"

        summary["mean_gaps"][gap_field] = mean(
            [
                row.get(gap_field)
                for row in gap_rows
            ]
        )

    return summary


def extract_error_examples(
    rows: list[dict[str, Any]],
    max_examples_per_model: int,
) -> list[dict[str, Any]]:
    """
    Extracts examples with substantive errors for qualitative inspection.
    Prioritizes critical/major omissions and hallucinations.
    """
    candidates = []

    for row in rows:
        omission_rank = SEVERITY_ORDER.get(
            row.get("omission_severity"),
            -1,
        )

        hallucination_rank = SEVERITY_ORDER.get(
            row.get("hallucination_severity"),
            -1,
        )

        max_rank = max(omission_rank, hallucination_rank)

        if max_rank < SEVERITY_ORDER["major"]:
            continue

        candidates.append(
            {
                **row,
                "_error_rank": max_rank,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["_error_rank"],
            len(flatten_main_errors(item)),
        ),
        reverse=True,
    )

    per_model_count = Counter()
    selected = []

    for row in candidates:
        model_name = row["eval_model_name"]

        if per_model_count[model_name] >= max_examples_per_model:
            continue

        per_model_count[model_name] += 1

        cleaned = dict(row)
        cleaned.pop("_error_rank", None)

        selected.append(cleaned)

    return selected


def save_csv(path: Path, rows: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(rows).to_csv(
        path,
        index=False,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--judge-by-model",
        required=True,
        help="Path to judge_results_by_model.jsonl",
    )

    parser.add_argument(
        "--judge-results",
        required=True,
        help="Path to judge_results.jsonl",
    )

    parser.add_argument(
        "--reference-metrics",
        default=None,
        help="Optional path to reference_metrics.jsonl",
    )

    parser.add_argument(
        "--summary-output",
        required=True,
        help="Path to output summary JSON",
    )

    parser.add_argument(
        "--by-model-csv",
        required=True,
    )

    parser.add_argument(
        "--by-domain-csv",
        required=True,
    )

    parser.add_argument(
        "--by-source-agent-csv",
        required=True,
    )

    parser.add_argument(
        "--by-success-csv",
        required=True,
    )

    parser.add_argument(
        "--with-metrics-csv",
        required=True,
    )

    parser.add_argument(
        "--error-examples-output",
        required=True,
    )

    parser.add_argument(
        "--max-error-examples-per-model",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    judge_by_model_path = Path(args.judge_by_model)
    judge_results_path = Path(args.judge_results)
    reference_metrics_path = (
        Path(args.reference_metrics)
        if args.reference_metrics is not None
        else None
    )

    rows = list(load_jsonl(judge_by_model_path))
    judge_records = list(load_jsonl(judge_results_path))

    reference_metrics_index = load_reference_metrics_index(
        reference_metrics_path
    )

    joined_rows = join_reference_metrics(
        rows,
        reference_metrics_index,
    )

    by_model = aggregate_group(
        joined_rows,
        ["eval_model_name"],
    )

    by_domain = aggregate_group(
        joined_rows,
        ["eval_model_name", "domain"],
    )

    by_source_agent = aggregate_group(
        joined_rows,
        ["eval_model_name", "source_model"],
    )

    by_success = aggregate_group(
        joined_rows,
        ["eval_model_name", "success_binary"],
    )

    save_csv(
        Path(args.by_model_csv),
        by_model,
    )

    save_csv(
        Path(args.by_domain_csv),
        by_domain,
    )

    save_csv(
        Path(args.by_source_agent_csv),
        by_source_agent,
    )

    save_csv(
        Path(args.by_success_csv),
        by_success,
    )

    save_csv(
        Path(args.with_metrics_csv),
        joined_rows,
    )

    error_examples = extract_error_examples(
        joined_rows,
        max_examples_per_model=args.max_error_examples_per_model,
    )

    write_jsonl(
        Path(args.error_examples_output),
        error_examples,
    )

    summary = {
        "num_judge_by_model_rows": len(rows),
        "num_judge_comparisons": len(judge_records),
        "num_joined_rows": len(joined_rows),
        "score_fields": SCORE_FIELDS,
        "pairwise_winners": summarize_pairwise_winners(
            judge_records,
        ),
        "by_model": by_model,
        "score_gap_summary_for_two_model_setting": (
            summarize_score_gaps_between_two_models(joined_rows)
        ),
        "outputs": {
            "by_model_csv": args.by_model_csv,
            "by_domain_csv": args.by_domain_csv,
            "by_source_agent_csv": args.by_source_agent_csv,
            "by_success_csv": args.by_success_csv,
            "with_metrics_csv": args.with_metrics_csv,
            "error_examples_output": args.error_examples_output,
        },
    }

    write_json(
        Path(args.summary_output),
        summary,
    )

    print()
    print("=" * 60)
    print("Judge analysis completed")
    print("=" * 60)
    print(f"Judge by-model rows: {len(rows)}")
    print(f"Judge comparisons: {len(judge_records)}")
    print(f"Joined rows: {len(joined_rows)}")
    print()
    print("Pairwise winners")
    print("----------------")

    for winner, count in summary["pairwise_winners"].items():
        print(f"{winner}: {count}")

    print()
    print("By model")
    print("--------")

    for row in by_model:
        print(
            f"{row['eval_model_name']}: "
            f"n={row['n']} "
            f"coverage={row.get('coverage_score_mean')} "
            f"factuality={row.get('factuality_score_mean')} "
            f"temporal={row.get('temporal_order_score_mean')} "
            f"specificity={row.get('specificity_score_mean')} "
            f"usefulness={row.get('procedural_usefulness_score_mean')} "
            f"best_rate={row.get('best_rate')}"
        )

    print()
    print(f"Summary JSON: {args.summary_output}")
    print(f"Error examples: {args.error_examples_output}")
    print("=" * 60)


if __name__ == "__main__":
    main()