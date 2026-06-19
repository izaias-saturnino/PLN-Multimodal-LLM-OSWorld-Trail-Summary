#!/usr/bin/env python3

"""
08_compute_reference_metrics.py

Computes reference-based automatic metrics for model summaries.

Input:
    outputs/model_summaries.jsonl

Expected fields:
    gold_summary
    model_summary
    model_summary_status
    eval_model_name
    trajectory_id
    source_model
    domain
    success_binary

Output:
    outputs/reference_metrics.jsonl
    outputs/reference_metrics_summary.csv
    outputs/reference_metrics_summary.json

Metrics:
    - ROUGE-1
    - ROUGE-2
    - ROUGE-L
    - BERTScore precision/recall/F1
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from bert_score import score as bert_score
from rouge_score import rouge_scorer
from tqdm import tqdm


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


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_valid_eval_record(record: dict[str, Any]) -> bool:
    if record.get("model_summary_status") != "OK":
        return False

    gold = record.get("gold_summary")
    pred = record.get("model_summary")

    if not isinstance(gold, str) or not gold.strip():
        return False

    if not isinstance(pred, str) or not pred.strip():
        return False

    return True


def compute_rouge(
    gold: str,
    pred: str,
    scorer: rouge_scorer.RougeScorer,
) -> dict[str, float]:
    scores = scorer.score(
        target=gold,
        prediction=pred,
    )

    return {
        "rouge1_precision": scores["rouge1"].precision,
        "rouge1_recall": scores["rouge1"].recall,
        "rouge1_f1": scores["rouge1"].fmeasure,
        "rouge2_precision": scores["rouge2"].precision,
        "rouge2_recall": scores["rouge2"].recall,
        "rouge2_f1": scores["rouge2"].fmeasure,
        "rougeL_precision": scores["rougeL"].precision,
        "rougeL_recall": scores["rougeL"].recall,
        "rougeL_f1": scores["rougeL"].fmeasure,
    }


def add_bertscore(
    metric_records: list[dict[str, Any]],
    lang: str,
    model_type: str | None,
    batch_size: int,
):
    predictions = [
        record["model_summary"]
        for record in metric_records
    ]

    references = [
        record["gold_summary"]
        for record in metric_records
    ]

    kwargs = {
        "cands": predictions,
        "refs": references,
        "lang": lang,
        "batch_size": batch_size,
        "verbose": True,
        "rescale_with_baseline": False,
    }

    if model_type is not None:
        kwargs["model_type"] = model_type

    precision, recall, f1 = bert_score(**kwargs)

    for idx, record in enumerate(metric_records):
        record["bertscore_precision"] = float(precision[idx])
        record["bertscore_recall"] = float(recall[idx])
        record["bertscore_f1"] = float(f1[idx])


def mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None

    return float(sum(values) / len(values))


def summarize_group(
    records: list[dict[str, Any]],
    group_fields: list[str],
    metric_fields: list[str],
) -> list[dict[str, Any]]:
    groups = defaultdict(list)

    for record in records:
        key = tuple(
            str(record.get(field))
            for field in group_fields
        )

        groups[key].append(record)

    summary_records = []

    for key, items in sorted(groups.items()):
        row = {
            field: value
            for field, value in zip(group_fields, key)
        }

        row["n"] = len(items)

        for metric in metric_fields:
            row[f"{metric}_mean"] = mean_or_none(
                [
                    item[metric]
                    for item in items
                    if item.get(metric) is not None
                ]
            )

        summary_records.append(row)

    return summary_records


def build_all_summaries(
    metric_records: list[dict[str, Any]],
    metric_fields: list[str],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "by_eval_model": summarize_group(
            metric_records,
            ["eval_model_name"],
            metric_fields,
        ),
        "by_eval_model_and_domain": summarize_group(
            metric_records,
            ["eval_model_name", "domain"],
            metric_fields,
        ),
        "by_eval_model_and_source_agent": summarize_group(
            metric_records,
            ["eval_model_name", "source_model"],
            metric_fields,
        ),
        "by_eval_model_and_success": summarize_group(
            metric_records,
            ["eval_model_name", "success_binary"],
            metric_fields,
        ),
        "by_eval_model_domain_success": summarize_group(
            metric_records,
            ["eval_model_name", "domain", "success_binary"],
            metric_fields,
        ),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to model_summaries.jsonl",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to per-example metrics JSONL",
    )

    parser.add_argument(
        "--summary-csv",
        required=True,
        help="Path to summary CSV",
    )

    parser.add_argument(
        "--summary-json",
        required=True,
        help="Path to summary JSON",
    )

    parser.add_argument(
        "--bertscore-lang",
        default="en",
    )

    parser.add_argument(
        "--bertscore-model-type",
        default=None,
        help=(
            "Optional BERTScore model type, e.g. "
            "microsoft/deberta-xlarge-mnli. If omitted, BERTScore "
            "chooses a default for the language."
        ),
    )

    parser.add_argument(
        "--bertscore-batch-size",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--skip-bertscore",
        action="store_true",
        help="Compute only ROUGE metrics.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_csv_path = Path(args.summary_csv)
    summary_json_path = Path(args.summary_json)

    all_records = list(load_jsonl(input_path))

    valid_records = [
        record
        for record in all_records
        if is_valid_eval_record(record)
    ]

    invalid_records = [
        record
        for record in all_records
        if not is_valid_eval_record(record)
    ]

    scorer = rouge_scorer.RougeScorer(
        ["rouge1", "rouge2", "rougeL"],
        use_stemmer=True,
    )

    metric_records = []

    for record in tqdm(
        valid_records,
        desc="ROUGE",
    ):
        gold = record["gold_summary"].strip()
        pred = record["model_summary"].strip()

        rouge = compute_rouge(
            gold=gold,
            pred=pred,
            scorer=scorer,
        )

        metric_record = {
            "trajectory_id": record.get("trajectory_id"),
            "source_model": record.get("source_model"),
            "example_id": record.get("example_id"),
            "domain": record.get("domain"),
            "success_binary": record.get("success_binary"),
            "success_raw": record.get("success_raw"),
            "eval_model_name": record.get("eval_model_name"),
            "eval_litellm_model": record.get("eval_litellm_model"),
            "gold_summary": gold,
            "model_summary": pred,
            "gold_word_count": len(gold.split()),
            "model_word_count": len(pred.split()),
            **rouge,
        }

        metric_records.append(metric_record)

    if not args.skip_bertscore and metric_records:
        add_bertscore(
            metric_records=metric_records,
            lang=args.bertscore_lang,
            model_type=args.bertscore_model_type,
            batch_size=args.bertscore_batch_size,
        )

    elif args.skip_bertscore:
        for record in metric_records:
            record["bertscore_precision"] = None
            record["bertscore_recall"] = None
            record["bertscore_f1"] = None

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

    summaries = build_all_summaries(
        metric_records,
        metric_fields,
    )

    write_jsonl(
        output_path,
        metric_records,
    )

    flat_summary_rows = []

    for summary_name, rows in summaries.items():
        for row in rows:
            flat_summary_rows.append(
                {
                    "summary": summary_name,
                    **row,
                }
            )

    summary_csv_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(flat_summary_rows).to_csv(
        summary_csv_path,
        index=False,
    )

    summary_json = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "num_input_records": len(all_records),
        "num_valid_eval_records": len(valid_records),
        "num_invalid_eval_records": len(invalid_records),
        "metrics": metric_fields,
        "summaries": summaries,
    }

    write_json(
        summary_json_path,
        summary_json,
    )

    print()
    print("=" * 60)
    print("Reference metrics completed")
    print("=" * 60)
    print(f"Input records: {len(all_records)}")
    print(f"Valid eval records: {len(valid_records)}")
    print(f"Invalid eval records: {len(invalid_records)}")
    print(f"Per-example metrics: {output_path}")
    print(f"Summary CSV: {summary_csv_path}")
    print(f"Summary JSON: {summary_json_path}")

    print()
    print("Main summary by eval model")
    print("--------------------------")

    for row in summaries["by_eval_model"]:
        print(
            f"{row['eval_model_name']}: "
            f"n={row['n']} "
            f"ROUGE-L={row.get('rougeL_f1_mean')} "
            f"BERTScore-F1={row.get('bertscore_f1_mean')}"
        )

    print("=" * 60)


if __name__ == "__main__":
    main()