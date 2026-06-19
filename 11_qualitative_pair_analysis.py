#!/usr/bin/env python3

"""
11_qualitative_pair_analysis.py

Analyzes paired OSWorld tasks where the same task has trajectories from
two different source agents.

Main focus:
    - Same task, different source-agent trajectory.
    - Cases where one source agent succeeded and the other failed.
    - How evaluated summarization models behave across those paired cases.

Inputs:
    outputs/gold_final_paired_clean.jsonl
    outputs/model_summaries.jsonl
    outputs/reference_metrics.jsonl
    outputs/judge_results_by_model.jsonl

Outputs:
    outputs/qualitative_pair_analysis.jsonl
    outputs/qualitative_pair_analysis_summary.json
    outputs/qualitative_pair_success_failure_cases.jsonl
    outputs/qualitative_pair_cases_for_paper.jsonl

This script does not call any LLM.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SEVERITY_ORDER = {
    "none": 0,
    "minor": 1,
    "major": 2,
    "critical": 3,
}


JUDGE_SCORE_FIELDS = [
    "coverage_score",
    "factuality_score",
    "temporal_order_score",
    "specificity_score",
    "procedural_usefulness_score",
]


REFERENCE_METRIC_FIELDS = [
    "rouge1_f1",
    "rouge2_f1",
    "rougeL_f1",
    "bertscore_precision",
    "bertscore_recall",
    "bertscore_f1",
]


def load_jsonl(path: Path):
    if not path.exists():
        return

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


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def group_by_task(
    records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped = defaultdict(list)

    for record in records:
        grouped[record["trajectory_id"]].append(record)

    return grouped


def build_model_summary_index(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}

    for record in records:
        key = (
            record["trajectory_id"],
            record["source_model"],
            record["eval_model_name"],
        )

        index[key] = record

    return index


def build_reference_metrics_index(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}

    for record in records:
        key = (
            record["trajectory_id"],
            record["source_model"],
            record["eval_model_name"],
        )

        index[key] = record

    return index


def build_judge_index(
    records: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index = {}

    for record in records:
        key = (
            record["trajectory_id"],
            record["source_model"],
            record["eval_model_name"],
        )

        index[key] = record

    return index


def get_success_pattern(
    paired_records: list[dict[str, Any]],
) -> str:
    values = [
        value_to_str(record.get("success_binary"))
        for record in paired_records
    ]

    return "+".join(sorted(values))


def classify_pair_outcome(
    paired_records: list[dict[str, Any]],
) -> str:
    values = [
        record.get("success_binary")
        for record in paired_records
    ]

    unique = set(values)

    if unique == {True}:
        return "both_success"

    if unique == {False}:
        return "both_failure"

    if unique == {None}:
        return "both_unknown"

    if True in unique and False in unique:
        return "mixed_success_failure"

    if True in unique and None in unique:
        return "mixed_success_unknown"

    if False in unique and None in unique:
        return "mixed_failure_unknown"

    return "other"


def severity_rank(value: Any) -> int:
    return SEVERITY_ORDER.get(value_to_str(value), -1)


def flatten_main_errors(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    if row is None:
        return []

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


def summarize_eval_for_record(
    gold_record: dict[str, Any],
    eval_model_names: list[str],
    model_summary_index: dict[tuple[str, str, str], dict[str, Any]],
    reference_metrics_index: dict[tuple[str, str, str], dict[str, Any]],
    judge_index: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    trajectory_id = gold_record["trajectory_id"]
    source_model = gold_record["source_model"]

    per_model = {}

    for eval_model_name in eval_model_names:
        key = (
            trajectory_id,
            source_model,
            eval_model_name,
        )

        summary_record = model_summary_index.get(key)
        metric_record = reference_metrics_index.get(key)
        judge_record = judge_index.get(key)

        model_entry = {
            "model_summary_status": (
                summary_record.get("model_summary_status")
                if summary_record
                else "MISSING"
            ),
            "model_summary": (
                summary_record.get("model_summary")
                if summary_record
                else None
            ),
        }

        if metric_record is not None:
            for field in REFERENCE_METRIC_FIELDS:
                model_entry[field] = metric_record.get(field)
        else:
            for field in REFERENCE_METRIC_FIELDS:
                model_entry[field] = None

        if judge_record is not None:
            for field in JUDGE_SCORE_FIELDS:
                model_entry[field] = judge_record.get(field)

            model_entry["omission_severity"] = judge_record.get(
                "omission_severity"
            )
            model_entry["hallucination_severity"] = judge_record.get(
                "hallucination_severity"
            )
            model_entry["is_best"] = judge_record.get("is_best")
            model_entry["is_tie"] = judge_record.get("is_tie")
            model_entry["main_errors"] = judge_record.get(
                "main_errors"
            )
            model_entry["judge_rationale"] = judge_record.get(
                "judge_rationale"
            )

        else:
            for field in JUDGE_SCORE_FIELDS:
                model_entry[field] = None

            model_entry["omission_severity"] = None
            model_entry["hallucination_severity"] = None
            model_entry["is_best"] = None
            model_entry["is_tie"] = None
            model_entry["main_errors"] = None
            model_entry["judge_rationale"] = None

        per_model[eval_model_name] = model_entry

    return per_model


def build_pair_records(
    gold_records: list[dict[str, Any]],
    eval_model_names: list[str],
    model_summary_index: dict[tuple[str, str, str], dict[str, Any]],
    reference_metrics_index: dict[tuple[str, str, str], dict[str, Any]],
    judge_index: dict[tuple[str, str, str], dict[str, Any]],
    required_source_models: list[str],
) -> list[dict[str, Any]]:
    grouped = group_by_task(gold_records)

    required_set = set(required_source_models)
    pair_records = []

    for trajectory_id, group in sorted(grouped.items()):
        by_source = {
            record["source_model"]: record
            for record in group
        }

        if not required_set.issubset(set(by_source.keys())):
            continue

        paired_gold_records = [
            by_source[source_model]
            for source_model in required_source_models
        ]

        source_entries = {}

        for source_model in required_source_models:
            gold_record = by_source[source_model]

            source_entries[source_model] = {
                "trajectory_id": trajectory_id,
                "source_model": source_model,
                "domain": gold_record.get("domain"),
                "instruction": gold_record.get("instruction"),
                "success_binary": gold_record.get("success_binary"),
                "success_raw": gold_record.get("success_raw"),
                "num_steps": gold_record.get("num_steps"),
                "gold_summary": gold_record.get("gold_summary"),
                "eval_models": summarize_eval_for_record(
                    gold_record=gold_record,
                    eval_model_names=eval_model_names,
                    model_summary_index=model_summary_index,
                    reference_metrics_index=reference_metrics_index,
                    judge_index=judge_index,
                ),
            }

        pair_records.append(
            {
                "trajectory_id": trajectory_id,
                "domain": paired_gold_records[0].get("domain"),
                "instruction": paired_gold_records[0].get("instruction"),
                "source_models": required_source_models,
                "pair_outcome": classify_pair_outcome(
                    paired_gold_records
                ),
                "success_pattern": get_success_pattern(
                    paired_gold_records
                ),
                "sources": source_entries,
            }
        )

    return pair_records


def summarize_pair_records(
    pair_records: list[dict[str, Any]],
    eval_model_names: list[str],
    required_source_models: list[str],
) -> dict[str, Any]:
    pair_outcome_counts = Counter(
        record["pair_outcome"]
        for record in pair_records
    )

    domain_counts = Counter(
        record.get("domain")
        for record in pair_records
    )

    success_pattern_counts = Counter(
        record.get("success_pattern")
        for record in pair_records
    )

    by_eval_model = {}

    for eval_model_name in eval_model_names:
        model_rows = []

        for pair_record in pair_records:
            for source_model in required_source_models:
                source_entry = pair_record["sources"][source_model]
                model_entry = source_entry["eval_models"][eval_model_name]

                row = {
                    **model_entry,
                    "trajectory_id": pair_record["trajectory_id"],
                    "source_model": source_model,
                    "domain": pair_record["domain"],
                    "success_binary": source_entry.get(
                        "success_binary"
                    ),
                    "pair_outcome": pair_record["pair_outcome"],
                }

                model_rows.append(row)

        by_eval_model[eval_model_name] = {
            "n": len(model_rows),
            "reference_metric_means": {
                field: mean(
                    [
                        row.get(field)
                        for row in model_rows
                    ]
                )
                for field in REFERENCE_METRIC_FIELDS
            },
            "judge_score_means": {
                field: mean(
                    [
                        row.get(field)
                        for row in model_rows
                    ]
                )
                for field in JUDGE_SCORE_FIELDS
            },
            "best_count": sum(
                1
                for row in model_rows
                if row.get("is_best") is True
            ),
            "tie_count": sum(
                1
                for row in model_rows
                if row.get("is_tie") is True
            ),
            "omission_severity_counts": dict(
                sorted(
                    Counter(
                        value_to_str(row.get("omission_severity"))
                        for row in model_rows
                    ).items()
                )
            ),
            "hallucination_severity_counts": dict(
                sorted(
                    Counter(
                        value_to_str(row.get("hallucination_severity"))
                        for row in model_rows
                    ).items()
                )
            ),
        }

    mixed_success_failure_records = [
        record
        for record in pair_records
        if record["pair_outcome"] == "mixed_success_failure"
    ]

    return {
        "num_paired_tasks": len(pair_records),
        "num_records": len(pair_records) * len(required_source_models),
        "required_source_models": required_source_models,
        "eval_model_names": eval_model_names,
        "pair_outcome_counts": dict(sorted(pair_outcome_counts.items())),
        "success_pattern_counts": dict(sorted(success_pattern_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "num_mixed_success_failure_pairs": len(
            mixed_success_failure_records
        ),
        "by_eval_model": by_eval_model,
    }


def model_gap_for_pair(
    pair_record: dict[str, Any],
    eval_model_name: str,
    source_model_a: str,
    source_model_b: str,
    field: str,
) -> float | None:
    a = pair_record["sources"][source_model_a]["eval_models"][
        eval_model_name
    ].get(field)
    b = pair_record["sources"][source_model_b]["eval_models"][
        eval_model_name
    ].get(field)

    a = safe_float(a)
    b = safe_float(b)

    if a is None or b is None:
        return None

    return a - b


def select_cases_for_paper(
    pair_records: list[dict[str, Any]],
    eval_model_names: list[str],
    required_source_models: list[str],
    max_cases: int,
) -> list[dict[str, Any]]:
    """
    Selects qualitative cases likely to be useful in the paper.

    Priority:
        1. Mixed success/failure pairs.
        2. Pairs with major/critical judge errors.
        3. Pairs with large specificity/usefulness gaps.
    """
    candidates = []

    for pair_record in pair_records:
        score = 0

        if pair_record["pair_outcome"] == "mixed_success_failure":
            score += 100

        for source_model in required_source_models:
            source_entry = pair_record["sources"][source_model]

            for eval_model_name in eval_model_names:
                model_entry = source_entry["eval_models"][eval_model_name]

                omission_rank = severity_rank(
                    model_entry.get("omission_severity")
                )
                hallucination_rank = severity_rank(
                    model_entry.get("hallucination_severity")
                )

                score += max(omission_rank, hallucination_rank) * 10

                specificity = safe_float(
                    model_entry.get("specificity_score")
                )

                usefulness = safe_float(
                    model_entry.get("procedural_usefulness_score")
                )

                if specificity is not None and specificity <= 3:
                    score += 5

                if usefulness is not None and usefulness <= 3:
                    score += 5

        candidates.append(
            {
                "_selection_score": score,
                **pair_record,
            }
        )

    candidates.sort(
        key=lambda item: item["_selection_score"],
        reverse=True,
    )

    selected = []

    for item in candidates[:max_cases]:
        cleaned = dict(item)
        cleaned.pop("_selection_score", None)
        selected.append(cleaned)

    return selected


def extract_success_failure_pairs(
    pair_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        record
        for record in pair_records
        if record["pair_outcome"] == "mixed_success_failure"
    ]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--gold",
        required=True,
        help="Path to gold_final_paired_clean.jsonl",
    )

    parser.add_argument(
        "--model-summaries",
        required=True,
        help="Path to model_summaries.jsonl",
    )

    parser.add_argument(
        "--reference-metrics",
        required=True,
        help="Path to reference_metrics.jsonl",
    )

    parser.add_argument(
        "--judge-by-model",
        required=True,
        help="Path to judge_results_by_model.jsonl",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to full qualitative pair analysis JSONL",
    )

    parser.add_argument(
        "--summary-output",
        required=True,
        help="Path to summary JSON",
    )

    parser.add_argument(
        "--success-failure-output",
        required=True,
        help="Path to mixed success/failure pair JSONL",
    )

    parser.add_argument(
        "--cases-for-paper-output",
        required=True,
        help="Path to selected qualitative cases JSONL",
    )

    parser.add_argument(
        "--required-source-models",
        nargs="+",
        required=True,
    )

    parser.add_argument(
        "--max-cases-for-paper",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    gold_records = list(load_jsonl(Path(args.gold)))
    model_summary_records = list(load_jsonl(Path(args.model_summaries)))
    reference_metric_records = list(load_jsonl(Path(args.reference_metrics)))
    judge_by_model_records = list(load_jsonl(Path(args.judge_by_model)))

    eval_model_names = sorted(
        {
            record["eval_model_name"]
            for record in model_summary_records
            if record.get("model_summary_status") == "OK"
        }
    )

    model_summary_index = build_model_summary_index(
        model_summary_records
    )

    reference_metrics_index = build_reference_metrics_index(
        reference_metric_records
    )

    judge_index = build_judge_index(
        judge_by_model_records
    )

    pair_records = build_pair_records(
        gold_records=gold_records,
        eval_model_names=eval_model_names,
        model_summary_index=model_summary_index,
        reference_metrics_index=reference_metrics_index,
        judge_index=judge_index,
        required_source_models=args.required_source_models,
    )

    summary = summarize_pair_records(
        pair_records=pair_records,
        eval_model_names=eval_model_names,
        required_source_models=args.required_source_models,
    )

    success_failure_pairs = extract_success_failure_pairs(
        pair_records
    )

    cases_for_paper = select_cases_for_paper(
        pair_records=pair_records,
        eval_model_names=eval_model_names,
        required_source_models=args.required_source_models,
        max_cases=args.max_cases_for_paper,
    )

    write_jsonl(
        Path(args.output),
        pair_records,
    )

    write_json(
        Path(args.summary_output),
        summary,
    )

    write_jsonl(
        Path(args.success_failure_output),
        success_failure_pairs,
    )

    write_jsonl(
        Path(args.cases_for_paper_output),
        cases_for_paper,
    )

    print()
    print("=" * 60)
    print("Qualitative pair analysis completed")
    print("=" * 60)
    print(f"Paired tasks: {summary['num_paired_tasks']}")
    print(f"Records: {summary['num_records']}")
    print()
    print("Pair outcomes")
    print("-------------")

    for outcome, count in summary["pair_outcome_counts"].items():
        print(f"{outcome}: {count}")

    print()
    print("Mixed success/failure pairs:")
    print(summary["num_mixed_success_failure_pairs"])

    print()
    print("By eval model")
    print("-------------")

    for model_name, model_summary in summary["by_eval_model"].items():
        print(
            f"{model_name}: "
            f"n={model_summary['n']} "
            f"ROUGE-L={model_summary['reference_metric_means'].get('rougeL_f1')} "
            f"BERTScore-F1={model_summary['reference_metric_means'].get('bertscore_f1')} "
            f"specificity={model_summary['judge_score_means'].get('specificity_score')} "
            f"usefulness={model_summary['judge_score_means'].get('procedural_usefulness_score')}"
        )

    print()
    print(f"Full analysis: {args.output}")
    print(f"Summary: {args.summary_output}")
    print(f"Mixed success/failure cases: {args.success_failure_output}")
    print(f"Cases for paper: {args.cases_for_paper_output}")
    print("=" * 60)


if __name__ == "__main__":
    main()