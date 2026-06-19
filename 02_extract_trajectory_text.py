#!/usr/bin/env python3

"""
02_extract_trajectory_text.py

Converts OSWorld trajectories into normalized text files
for complexity screening and summarization experiments.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


THOUGHT_PATTERN = re.compile(
    r"Thought:\s*(.*?)\n\s*'''",
    re.DOTALL,
)


def extract_thought(action_text: str) -> str:
    if not isinstance(action_text, str):
        return ""

    match = THOUGHT_PATTERN.search(action_text)

    if not match:
        return ""

    return match.group(1).strip()


def extract_action_code(action_text: str) -> str:
    if not isinstance(action_text, str):
        return ""

    if action_text.strip() == "DONE":
        return "DONE"

    parts = action_text.split("'''")

    if len(parts) < 2:
        return action_text.strip()

    code = "'''".join(parts[2:]).strip()

    cleaned_lines = []

    for line in code.splitlines():

        stripped = line.strip()

        if stripped.startswith("import "):
            continue

        if stripped.startswith("from "):
            continue

        if stripped.startswith("time.sleep("):
            continue

        if not stripped:
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def load_manifest(manifest_path: Path):
    with open(
        manifest_path,
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if line:
                yield json.loads(line)


def build_text(record: dict) -> str:

    trail_file = Path(record["trail_file"])

    lines = []

    lines.append(
        f"Trajectory ID: {record['trajectory_id']}"
    )

    lines.append(
        f"Source Model: {record['source_model']}"
    )

    lines.append(
        f"Domain: {record['domain']}"
    )

    lines.append("")

    lines.append("Task:")
    lines.append(
        record.get("instruction", "")
    )

    lines.append("")

    lines.append(
        f"Success Binary: {record.get('success_binary')}"
    )

    lines.append(
        f"Success Raw: {record.get('success_raw')}"
    )

    lines.append("")

    lines.append(
        f"Number of Steps: {record.get('num_steps')}"
    )

    lines.append("")
    lines.append("=" * 60)
    lines.append("TRAJECTORY")
    lines.append("=" * 60)
    lines.append("")

    with open(
        trail_file,
        "r",
        encoding="utf-8",
    ) as f:

        for raw_line in f:

            raw_line = raw_line.strip()

            if not raw_line:
                continue

            step = json.loads(raw_line)

            step_num = step.get(
                "step_num",
                "?"
            )

            action_blob = step.get(
                "action",
                ""
            )

            thought = extract_thought(
                action_blob
            )

            action_code = extract_action_code(
                action_blob
            )

            lines.append(
                "=" * 50
            )

            lines.append(
                f"STEP {step_num}"
            )

            lines.append(
                "=" * 50
            )

            lines.append("")

            if thought:

                lines.append(
                    "Thought:"
                )

                lines.append(
                    thought
                )

                lines.append("")

            if action_code:

                lines.append(
                    "Action:"
                )

                lines.append(
                    action_code
                )

                lines.append("")

    return "\n".join(lines)


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    args = parser.parse_args()

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    count = 0

    for record in load_manifest(
        Path(args.manifest)
    ):

        filename = (
            f"{record['source_model']}__"
            f"{record['trajectory_id']}.txt"
        )

        output_file = (
            output_dir / filename
        )

        text = build_text(record)

        output_file.write_text(
            text,
            encoding="utf-8",
        )

        count += 1

    print(
        f"Generated {count} trajectory texts."
    )


if __name__ == "__main__":
    main()