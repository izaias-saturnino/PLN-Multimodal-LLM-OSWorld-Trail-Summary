#!/usr/bin/env python3

"""
06_collect_revised_gold.py

Collects human-revised gold summaries from markdown review files
and consolidates them into a final JSONL dataset.

Input:
    outputs/gold_drafts.jsonl
    outputs/gold_drafts_review/*.md

Output:
    outputs/gold_final.jsonl

Expected markdown section:
    ## Human-Revised Gold Summary

The text under that heading is treated as the final gold summary.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REVISED_SECTION_RE = re.compile(
    r"^##\s+Human-Revised Gold Summary\s*$"
    r"(.*?)(?=^##\s+|\Z)",
    re.DOTALL | re.MULTILINE | re.IGNORECASE,
)


COMMENT_RE = re.compile(
    r"<!--.*?-->",
    re.DOTALL,
)


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
            f.write(
                json.dumps(record, ensure_ascii=False)
                + "\n"
            )


def make_example_id(record: dict[str, Any]) -> str:
    return (
        f"{record['source_model']}__"
        f"{record['trajectory_id']}"
    )


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = text.strip("_")

    return text[:180]


def review_file_path(
    review_dir: Path,
    record: dict[str, Any],
) -> Path:
    example_id = make_example_id(record)
    filename = safe_filename(example_id) + ".md"

    return review_dir / filename


def clean_summary(text: str) -> str:
    text = COMMENT_RE.sub("", text)
    text = text.strip()

    lines = [
        line.rstrip()
        for line in text.splitlines()
    ]

    while lines and not lines[0].strip():
        lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines).strip()


def extract_revised_summary(markdown_text: str) -> str | None:
    match = REVISED_SECTION_RE.search(markdown_text)

    if not match:
        return None

    summary = clean_summary(
        match.group(1)
    )

    if not summary:
        return None

    return summary


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        help="Path to gold_drafts.jsonl",
    )

    parser.add_argument(
        "--review-dir",
        required=True,
        help="Directory containing reviewed markdown files",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to final gold JSONL output",
    )

    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Do not fail if some review files or revised summaries "
            "are missing. Missing records will be marked accordingly."
        ),
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    review_dir = Path(args.review_dir)
    output_path = Path(args.output)

    records = list(load_jsonl(input_path))

    final_records = []

    missing_files = []
    missing_summaries = []

    for record in records:
        path = review_file_path(
            review_dir,
            record,
        )

        if not path.exists():
            missing_files.append(str(path))

            final_records.append(
                {
                    **record,
                    "gold_summary": None,
                    "gold_summary_status": "MISSING_REVIEW_FILE",
                    "gold_review_file": str(path),
                }
            )

            continue

        markdown_text = path.read_text(
            encoding="utf-8",
        )

        revised_summary = extract_revised_summary(
            markdown_text,
        )

        if revised_summary is None:
            missing_summaries.append(str(path))

            final_records.append(
                {
                    **record,
                    "gold_summary": None,
                    "gold_summary_status": "MISSING_REVISED_SUMMARY",
                    "gold_review_file": str(path),
                }
            )

            continue

        final_records.append(
            {
                **record,
                "gold_summary": revised_summary,
                "gold_summary_status": "OK",
                "gold_review_file": str(path),
            }
        )

    if not args.allow_missing:
        if missing_files or missing_summaries:
            print()
            print("=" * 60)
            print("Missing gold summaries detected")
            print("=" * 60)

            if missing_files:
                print()
                print("Missing review files:")
                for path in missing_files[:20]:
                    print(f"- {path}")

                if len(missing_files) > 20:
                    print(f"... and {len(missing_files) - 20} more")

            if missing_summaries:
                print()
                print("Missing revised summary sections:")
                for path in missing_summaries[:20]:
                    print(f"- {path}")

                if len(missing_summaries) > 20:
                    print(f"... and {len(missing_summaries) - 20} more")

            raise SystemExit(
                "Aborting because some gold summaries are missing. "
                "Use --allow-missing only for debugging."
            )

    write_jsonl(
        output_path,
        final_records,
    )

    ok = sum(
        1
        for record in final_records
        if record["gold_summary_status"] == "OK"
    )

    missing_file_count = sum(
        1
        for record in final_records
        if record["gold_summary_status"] == "MISSING_REVIEW_FILE"
    )

    missing_summary_count = sum(
        1
        for record in final_records
        if record["gold_summary_status"] == "MISSING_REVISED_SUMMARY"
    )

    print()
    print("=" * 60)
    print("Gold collection completed")
    print("=" * 60)
    print(f"Input records: {len(records)}")
    print(f"Output file: {output_path}")
    print(f"OK: {ok}")
    print(f"Missing review files: {missing_file_count}")
    print(f"Missing revised summaries: {missing_summary_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()