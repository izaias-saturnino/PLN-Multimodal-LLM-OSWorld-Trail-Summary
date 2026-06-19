#!/usr/bin/env python3

"""
12_export_paper_tables.py

Consolidates pipeline outputs into paper-ready tables.

Inputs are optional where possible. Missing files are skipped with warnings.

Expected inputs:
    outputs/screened_manifest.jsonl
    outputs/selected_paired_balanced_stats.json
    outputs/gold_final_paired_clean_stats.json
    outputs/reference_metrics_summary.json
    outputs/judge_analysis_summary.json
    outputs/qualitative_pair_analysis_summary.json

Primary qualitative analysis:
    outputs/llm_qualitative_pair_analysis_success_failure_summary.json
    outputs/llm_qualitative_pair_analysis_success_failure.jsonl

Optional broader qualitative analysis:
    outputs/llm_qualitative_pair_analysis_cases_summary.json
    outputs/llm_qualitative_pair_analysis_cases.jsonl

Outputs:
    outputs/paper_tables/table1_dataset_construction.csv
    outputs/paper_tables/table2_final_gold_distribution.csv
    outputs/paper_tables/table3_reference_metrics.csv
    outputs/paper_tables/table4_llm_judge_results.csv
    outputs/paper_tables/table5_paired_outcome_distribution.csv
    outputs/paper_tables/table6_qualitative_findings.csv
    outputs/paper_tables/paper_tables_summary.json

This script does not call any LLM.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


def load_json(path: Path) -> Any | None:
    if not path.exists():
        print(f"[WARNING] Missing JSON file: {path}")
        return None

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"[WARNING] Missing JSONL file: {path}")
        return []

    records = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                records.append(json.loads(line))

    return records


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(rows).to_csv(
        path,
        index=False,
    )


def value_to_str(value: Any) -> str:
    if value is None:
        return "None"

    return str(value)


def count_screened_manifest(
    screened_records: list[dict[str, Any]],
) -> dict[str, Any]:
    if not screened_records:
        return {}

    total = len(screened_records)

    selected = sum(
        1
        for r in screened_records
        if r.get("selected_for_gold_generation") is True
    )

    rejected = sum(
        1
        for r in screened_records
        if r.get("selected_for_gold_generation") is False
    )

    incomplete = sum(
        1
        for r in screened_records
        if r.get("selected_for_gold_generation") is None
    )

    status_counts = Counter(
        value_to_str(r.get("screening_status"))
        for r in screened_records
    )

    return {
        "screened_total": total,
        "screened_selected": selected,
        "screened_rejected": rejected,
        "screened_incomplete": incomplete,
        "screening_status_counts": dict(sorted(status_counts.items())),
    }


def build_table1_dataset_construction(
    screened_records: list[dict[str, Any]],
    selected_stats: dict[str, Any] | None,
    gold_clean_stats: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows = []

    screened = count_screened_manifest(screened_records)

    if screened:
        rows.append(
            {
                "stage": "Screened trajectories",
                "unit": "trajectory",
                "count": screened["screened_total"],
                "notes": "All trajectories after LLM complexity screening.",
            }
        )

        rows.append(
            {
                "stage": "Selected by complexity screening",
                "unit": "trajectory",
                "count": screened["screened_selected"],
                "notes": "selected_for_gold_generation == true.",
            }
        )

        rows.append(
            {
                "stage": "Rejected by complexity screening",
                "unit": "trajectory",
                "count": screened["screened_rejected"],
                "notes": "selected_for_gold_generation == false.",
            }
        )

        rows.append(
            {
                "stage": "Incomplete screening",
                "unit": "trajectory",
                "count": screened["screened_incomplete"],
                "notes": "No final screening decision.",
            }
        )

    if selected_stats:
        rows.append(
            {
                "stage": "Paired balanced selected tasks",
                "unit": "task pair",
                "count": selected_stats.get(
                    "num_selected_paired_task_groups"
                ),
                "notes": "Task-level paired subset before gold revision.",
            }
        )

        rows.append(
            {
                "stage": "Paired balanced selected trajectories",
                "unit": "trajectory",
                "count": selected_stats.get("num_selected_records"),
                "notes": "Two source-agent trajectories per selected task.",
            }
        )

    if gold_clean_stats:
        rows.append(
            {
                "stage": "Valid gold records before pair filtering",
                "unit": "trajectory",
                "count": gold_clean_stats.get(
                    "num_valid_gold_records_before_pair_filtering"
                ),
                "notes": "Human-revised gold summaries with non-empty gold.",
            }
        )

        rows.append(
            {
                "stage": "Final clean paired gold tasks",
                "unit": "task pair",
                "count": gold_clean_stats.get(
                    "num_clean_paired_tasks"
                ),
                "notes": (
                    "Final paired tasks with valid gold for all required "
                    "source agents."
                ),
            }
        )

        rows.append(
            {
                "stage": "Final clean paired gold trajectories",
                "unit": "trajectory",
                "count": gold_clean_stats.get(
                    "num_clean_paired_gold_records"
                ),
                "notes": "Final evaluation trajectories.",
            }
        )

    return rows


def build_table2_final_gold_distribution(
    gold_clean_stats: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not gold_clean_stats:
        return []

    rows = []

    clean_counts = gold_clean_stats.get(
        "clean_paired_column_counts",
        {},
    )

    for column, counts in clean_counts.items():
        for value, count in sorted(counts.items()):
            rows.append(
                {
                    "distribution": column,
                    "value": value,
                    "count": count,
                }
            )

    task_domain_counts = gold_clean_stats.get(
        "clean_paired_task_domain_counts",
        {},
    )

    for value, count in sorted(task_domain_counts.items()):
        rows.append(
            {
                "distribution": "task_domain",
                "value": value,
                "count": count,
            }
        )

    task_success_patterns = gold_clean_stats.get(
        "clean_paired_task_success_patterns",
        {},
    )

    for value, count in sorted(task_success_patterns.items()):
        rows.append(
            {
                "distribution": "task_success_pattern",
                "value": value,
                "count": count,
            }
        )

    return rows


def build_table3_reference_metrics(
    reference_metrics_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not reference_metrics_summary:
        return []

    summaries = reference_metrics_summary.get(
        "summaries",
        {},
    )

    by_model = summaries.get(
        "by_eval_model",
        [],
    )

    rows = []

    for row in by_model:
        rows.append(
            {
                "eval_model_name": row.get("eval_model_name"),
                "n": row.get("n"),
                "rouge1_f1_mean": row.get("rouge1_f1_mean"),
                "rouge2_f1_mean": row.get("rouge2_f1_mean"),
                "rougeL_f1_mean": row.get("rougeL_f1_mean"),
                "bertscore_precision_mean": row.get(
                    "bertscore_precision_mean"
                ),
                "bertscore_recall_mean": row.get(
                    "bertscore_recall_mean"
                ),
                "bertscore_f1_mean": row.get("bertscore_f1_mean"),
                "gold_word_count_mean": row.get(
                    "gold_word_count_mean"
                ),
                "model_word_count_mean": row.get(
                    "model_word_count_mean"
                ),
            }
        )

    return rows


def build_table4_llm_judge_results(
    judge_analysis_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not judge_analysis_summary:
        return []

    rows = []

    by_model = judge_analysis_summary.get(
        "by_model",
        [],
    )

    pairwise_winners = judge_analysis_summary.get(
        "pairwise_winners",
        {},
    )

    for row in by_model:
        model = row.get("eval_model_name")

        output = {
            "eval_model_name": model,
            "n": row.get("n"),
            "winner_count": pairwise_winners.get(model, 0),
            "tie_count_global": pairwise_winners.get("tie", 0),
            "best_count": row.get("best_count"),
            "best_rate": row.get("best_rate"),
            "tie_count": row.get("tie_count"),
            "tie_rate": row.get("tie_rate"),
            "major_or_critical_omission_rate": row.get(
                "major_or_critical_omission_rate"
            ),
            "major_or_critical_hallucination_rate": row.get(
                "major_or_critical_hallucination_rate"
            ),
        }

        for field in [
            "coverage_score",
            "factuality_score",
            "temporal_order_score",
            "specificity_score",
            "procedural_usefulness_score",
        ]:
            output[f"{field}_mean"] = row.get(
                f"{field}_mean"
            )

        rows.append(output)

    return rows


def build_table5_paired_outcome_distribution(
    qualitative_pair_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not qualitative_pair_summary:
        return []

    rows = []

    for outcome, count in sorted(
        qualitative_pair_summary.get(
            "pair_outcome_counts",
            {},
        ).items()
    ):
        rows.append(
            {
                "distribution": "pair_outcome",
                "value": outcome,
                "count": count,
            }
        )

    for pattern, count in sorted(
        qualitative_pair_summary.get(
            "success_pattern_counts",
            {},
        ).items()
    ):
        rows.append(
            {
                "distribution": "success_pattern",
                "value": pattern,
                "count": count,
            }
        )

    for domain, count in sorted(
        qualitative_pair_summary.get(
            "domain_counts",
            {},
        ).items()
    ):
        rows.append(
            {
                "distribution": "paired_task_domain",
                "value": domain,
                "count": count,
            }
        )

    return rows


def build_table6_qualitative_findings(
    qualitative_sets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for qualitative_set in qualitative_sets:
        analysis_set = qualitative_set["analysis_set"]
        summary = qualitative_set["summary"]
        records = qualitative_set["records"]

        if summary:
            for value, count in sorted(
                summary.get(
                    "recommended_paper_use_counts",
                    {},
                ).items()
            ):
                rows.append(
                    {
                        "analysis_set": analysis_set,
                        "category": "recommended_paper_use",
                        "value": value,
                        "count": count,
                    }
                )

            for value, count in sorted(
                summary.get(
                    "case_type_counts",
                    {},
                ).items()
            ):
                rows.append(
                    {
                        "analysis_set": analysis_set,
                        "category": "case_type",
                        "value": value,
                        "count": count,
                    }
                )

            for value, count in sorted(
                summary.get(
                    "better_failure_awareness_counts",
                    {},
                ).items()
            ):
                rows.append(
                    {
                        "analysis_set": analysis_set,
                        "category": "better_failure_awareness",
                        "value": value,
                        "count": count,
                    }
                )

        finding_counter = Counter()

        for record in records:
            if record.get("status") != "OK":
                continue

            analysis = record.get("analysis_json", {})
            findings = analysis.get(
                "main_qualitative_findings",
                [],
            )

            if not isinstance(findings, list):
                continue

            for finding in findings:
                if not isinstance(finding, dict):
                    continue

                text = finding.get("finding")

                if text:
                    finding_counter[text] += 1

        for finding, count in finding_counter.most_common():
            rows.append(
                {
                    "analysis_set": analysis_set,
                    "category": "main_qualitative_finding_text",
                    "value": finding,
                    "count": count,
                }
            )

    return rows


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--screened-manifest",
        default="outputs/screened_manifest.jsonl",
    )

    parser.add_argument(
        "--selected-stats",
        default="outputs/selected_paired_balanced_stats.json",
    )

    parser.add_argument(
        "--gold-clean-stats",
        default="outputs/gold_final_paired_clean_stats.json",
    )

    parser.add_argument(
        "--reference-metrics-summary",
        default="outputs/reference_metrics_summary.json",
    )

    parser.add_argument(
        "--judge-analysis-summary",
        default="outputs/judge_analysis_summary.json",
    )

    parser.add_argument(
        "--qualitative-pair-summary",
        default="outputs/qualitative_pair_analysis_summary.json",
    )

    parser.add_argument(
        "--llm-qual-summary",
        default=(
            "outputs/"
            "llm_qualitative_pair_analysis_success_failure_summary.json"
        ),
    )

    parser.add_argument(
        "--llm-qual-records",
        default=(
            "outputs/"
            "llm_qualitative_pair_analysis_success_failure.jsonl"
        ),
    )

    parser.add_argument(
        "--optional-llm-qual-summary",
        default=(
            "outputs/"
            "llm_qualitative_pair_analysis_cases_summary.json"
        ),
    )

    parser.add_argument(
        "--optional-llm-qual-records",
        default=(
            "outputs/"
            "llm_qualitative_pair_analysis_cases.jsonl"
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/paper_tables",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    screened_records = load_jsonl(
        Path(args.screened_manifest)
    )

    selected_stats = load_json(
        Path(args.selected_stats)
    )

    gold_clean_stats = load_json(
        Path(args.gold_clean_stats)
    )

    reference_metrics_summary = load_json(
        Path(args.reference_metrics_summary)
    )

    judge_analysis_summary = load_json(
        Path(args.judge_analysis_summary)
    )

    qualitative_pair_summary = load_json(
        Path(args.qualitative_pair_summary)
    )

    llm_qual_summary = load_json(
        Path(args.llm_qual_summary)
    )

    llm_qual_records = load_jsonl(
        Path(args.llm_qual_records)
    )

    optional_llm_qual_summary = load_json(
        Path(args.optional_llm_qual_summary)
    )

    optional_llm_qual_records = load_jsonl(
        Path(args.optional_llm_qual_records)
    )

    qualitative_sets = [
        {
            "analysis_set": "success_failure_cases",
            "summary": llm_qual_summary,
            "records": llm_qual_records,
        },
        {
            "analysis_set": "selected_paper_cases",
            "summary": optional_llm_qual_summary,
            "records": optional_llm_qual_records,
        },
    ]

    tables = {
        "table1_dataset_construction": build_table1_dataset_construction(
            screened_records,
            selected_stats,
            gold_clean_stats,
        ),
        "table2_final_gold_distribution": build_table2_final_gold_distribution(
            gold_clean_stats,
        ),
        "table3_reference_metrics": build_table3_reference_metrics(
            reference_metrics_summary,
        ),
        "table4_llm_judge_results": build_table4_llm_judge_results(
            judge_analysis_summary,
        ),
        "table5_paired_outcome_distribution": build_table5_paired_outcome_distribution(
            qualitative_pair_summary,
        ),
        "table6_qualitative_findings": build_table6_qualitative_findings(
            qualitative_sets,
        ),
    }

    output_files = {}

    for table_name, rows in tables.items():
        path = output_dir / f"{table_name}.csv"

        write_csv(path, rows)

        output_files[table_name] = str(path)

    summary = {
        "output_dir": str(output_dir),
        "output_files": output_files,
        "num_rows": {
            table_name: len(rows)
            for table_name, rows in tables.items()
        },
        "inputs": {
            "screened_manifest": args.screened_manifest,
            "selected_stats": args.selected_stats,
            "gold_clean_stats": args.gold_clean_stats,
            "reference_metrics_summary": args.reference_metrics_summary,
            "judge_analysis_summary": args.judge_analysis_summary,
            "qualitative_pair_summary": args.qualitative_pair_summary,
            "llm_qual_summary": args.llm_qual_summary,
            "llm_qual_records": args.llm_qual_records,
            "optional_llm_qual_summary": args.optional_llm_qual_summary,
            "optional_llm_qual_records": args.optional_llm_qual_records,
        },
    }

    summary_path = output_dir / "paper_tables_summary.json"

    write_json(
        summary_path,
        summary,
    )

    print()
    print("=" * 60)
    print("Paper tables exported")
    print("=" * 60)

    for table_name, path in output_files.items():
        print(
            f"{table_name}: {path} "
            f"({len(tables[table_name])} rows)"
        )

    print()
    print(f"Summary: {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()